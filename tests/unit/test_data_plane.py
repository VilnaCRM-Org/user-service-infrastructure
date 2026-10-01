"""Hardened data plane: DocumentDB managed password (S1.2), MONGODB-AWS URL
(S1.3) and Redis IAM authentication (S1.4, FR-04, D-1)."""

import ast
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from app.data import (
    REDIS_APP_ACCESS_STRING,
    DataPlane,
    _managed_secret_arn,
    documentdb_iam_url,
    redis_iam_identity,
    redis_iam_url,
    require_iam_redis_engine,
)
from app.environment import (
    DOCUMENTDB_PASSWORD_CONFIG_KEYS,
    reject_documentdb_password_config,
    reject_redis_auth_token_config,
)
from test_environment_component import (
    OptionRecordingMonitor,
    RecordingMocks,
    _run_pulumi_program,
    mocked_pulumi_context,
)

import pulumi

CLUSTER = "user-service-documentdb-cluster"
ARN = "arn:aws:secretsmanager:eu-central-1:891377212104:secret:synthetic-AbCdEf"
MANAGED_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "rds!cluster-00000000-0000-4000-8000-000000000003-AbCdEf"
)
ENDPOINT = "synthetic.cluster-abc.eu-central-1.docdb.amazonaws.com"
REDIS_ENDPOINT = "master.synthetic.abc.euc1.cache.amazonaws.com"
REPLICATION_GROUP = "user-service-redis"
APP_USER = "user-service-redis-app-user"
DEFAULT_USER = "user-service-redis-default-user"
USER_GROUP = "user-service-redis-user-group"


class DocumentDbMocks(RecordingMocks):
    """Report the cluster endpoint and its one managed secret, as DocumentDB does."""

    def new_resource(self, args):
        resource_id, outputs = super().new_resource(args)
        if args.typ == "aws:docdb/cluster:Cluster":
            outputs["endpoint"] = ENDPOINT
            if args.inputs.get("manageMasterUserPassword") is True:
                outputs["masterUserSecrets"] = [{"secretArn": MANAGED_ARN}]
        if args.typ == "aws:elasticache/replicationGroup:ReplicationGroup":
            outputs["primaryEndpointAddress"] = REDIS_ENDPOINT
        return resource_id, outputs


def _settings(
    engine_version="5.0.0", redis_version="7.1", stack_tag="user-service-dev"
):
    return SimpleNamespace(
        is_managed=True,
        stack_tag=stack_tag,
        region="eu-central-1",
        documentdb=SimpleNamespace(
            username="synthetic",
            port=27017,
            engine_version=engine_version,
            instance_class="db.t3.medium",
            instance_count=1,
            backup_retention_days=7,
            preferred_backup_window="01:00-02:00",
            preferred_maintenance_window="sun:03:00-sun:04:00",
        ),
        redis=SimpleNamespace(
            port=6379,
            engine_version=redis_version,
            node_type="cache.t3.micro",
            replicas_per_node_group=0,
            snapshot_retention_limit=1,
            snapshot_window="02:00-03:00",
            maintenance_window="sun:04:00-sun:05:00",
        ),
    )


def _network():
    return SimpleNamespace(
        outputs=SimpleNamespace(
            data_subnet_ids=["subnet-a", "subnet-b"],
            redis_security_group_id="sg-redis",
            documentdb_security_group_id="sg-docdb",
        )
    )


def _secrets(hardened, database="user_service"):
    return SimpleNamespace(
        descriptor=SimpleNamespace(
            hardened=hardened, database_name=database, ca_bundle_path="/etc/ca.pem"
        ),
        secret_arns={"document_db_url": ARN, "redis_url": ARN},
        values={},
    )


def _register(secrets, config=None, material=False, engine_version="5.0.0", **redis):
    recorder = DocumentDbMocks()
    monitor = OptionRecordingMonitor(recorder)
    captured = {}

    def program():
        if material:
            secrets.values = {
                "document_db_password": pulumi.Output.secret("synthetic-password"),
                "redis_auth_token": pulumi.Output.secret("synthetic-token"),
            }
        plane = DataPlane(
            "data",
            settings=_settings(engine_version, **redis),
            network=_network(),
            runtime_secrets=secrets,
        )
        captured["plane"] = plane
        if hasattr(plane, "documentdb"):
            for field in ("mongodb_url", "managed_secret_arn"):
                getattr(plane.documentdb, field).apply(
                    lambda value, field=field: captured.__setitem__(field, value)
                )
            plane.redis.url.apply(
                lambda value: captured.__setitem__("redis_url", value)
            )

    with mocked_pulumi_context(config or {}):
        _run_pulumi_program(program, test_mocks=recorder, monitor=monitor)
    resources = {str(row["name"]): row for row in recorder.resources}
    return resources, captured


def _password_inputs(inputs):
    """Every cluster input naming a password, except the managed-password flag."""
    return {
        key
        for key in inputs
        if "password" in key.lower() and key != "manageMasterUserPassword"
    }


def test_hardened_cluster_uses_the_managed_password_without_a_master_password():
    resources, _ = _register(_secrets(hardened=True))
    cluster = resources[CLUSTER]["inputs"]
    assert cluster["manageMasterUserPassword"] is True
    # F-10: no masterPassword, masterPasswordWo or any other password input.
    assert _password_inputs(cluster) == set()
    assert cluster["masterUsername"] == "synthetic"


def test_the_password_input_scan_finds_a_write_only_password():
    inputs = {"manageMasterUserPassword": True, "masterPasswordWo": "synthetic"}
    assert _password_inputs(inputs) == {"masterPasswordWo"}


def test_hardened_cluster_keeps_the_aws_managed_key_under_exception_a05():
    # A-05: pulumi-aws 7.23.0 exposes no master_user_secret_kms_key_id, so the
    # managed secret stays on the AWS-managed key and no key is ever passed.
    resources, _ = _register(_secrets(hardened=True))
    inputs = resources[CLUSTER]["inputs"]
    assert "masterUserSecretKmsKeyId" not in inputs
    assert not any("kms" in key.lower() for key in inputs)


def test_hardened_data_plane_holds_no_generated_secret_material():
    resources, captured = _register(_secrets(hardened=True))
    assert not any(
        row["type"].startswith(("random:", "tls:"))
        or row["type"] == "aws:secretsmanager/secretVersion:SecretVersion"
        for row in resources.values()
    )
    assert captured["plane"]._runtime_secrets.values == {}


def test_hardened_outputs_expose_the_iam_url_and_no_url_secret():
    """S1.3: MONGODB_URL is plain; no URL or Redis secret exists (D-1)."""
    resources, captured = _register(_secrets(hardened=True))
    plane = captured["plane"]
    assert not hasattr(plane, "outputs")
    assert len(plane.documentdb.instances) == 1
    assert captured["managed_secret_arn"] == MANAGED_ARN
    assert captured["mongodb_url"] == (
        f"mongodb://{ENDPOINT}:27017/user_service?tls=true"
        "&tlsCAFile=%2Fetc%2Fca.pem&replicaSet=rs0"
        "&readPreference=secondaryPreferred&retryWrites=false"
        "&authSource=%24external&authMechanism=MONGODB-AWS"
    )
    assert not [
        row
        for row in resources.values()
        if row["type"].startswith("aws:secretsmanager/")
    ]


def test_iam_url_carries_mechanism_source_tls_and_ca():
    """FR-02 P: the URL names MONGODB-AWS, ``$external``, TLS and the CA."""
    url = documentdb_iam_url(ENDPOINT, 27017, "user_service", "/etc/ca.pem")
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert (parts.scheme, parts.hostname, parts.port) == ("mongodb", ENDPOINT, 27017)
    assert (parts.username, parts.password) == (None, None)
    assert query["authMechanism"] == ["MONGODB-AWS"]
    assert query["authSource"] == ["$external"]
    assert (query["tls"], query["tlsCAFile"]) == (["true"], ["/etc/ca.pem"])
    assert query["retryWrites"] == ["false"]


@pytest.mark.parametrize(
    "endpoint",
    ["user@" + ENDPOINT, "user:synthetic@" + ENDPOINT, "@" + ENDPOINT],
)
def test_userinfo_in_the_iam_url_raises(endpoint):
    """FR-02 N: the URL never carries userinfo."""
    with pytest.raises(ValueError, match="userinfo"):
        documentdb_iam_url(endpoint, 27017, "user_service", "/etc/ca.pem")


def test_the_database_name_is_url_encoded():
    """FR-02 B: a database name cannot alter the path or the query."""
    url = documentdb_iam_url(ENDPOINT, 27017, "app/db?x=1 &y", "/etc/ca.pem")
    assert urlsplit(url).path == "/app%2Fdb%3Fx%3D1%20%26y"
    assert "x" not in parse_qs(urlsplit(url).query)


@pytest.mark.parametrize("version", ["4.0.0", "3.6.0", "5.0", "8.0.0", None])
def test_a_non_iam_engine_version_raises(version):
    """N (V-17): only instance-based DocumentDB 5.0.0 supports IAM auth."""
    with pytest.raises(ValueError, match="V-17"):
        _register(_secrets(hardened=True), engine_version=version)


def test_the_managed_secret_must_be_exactly_one():
    assert _managed_secret_arn([SimpleNamespace(secret_arn=MANAGED_ARN)]) == (
        MANAGED_ARN
    )
    for secrets in (None, [], [SimpleNamespace(secret_arn=MANAGED_ARN)] * 2):
        with pytest.raises(ValueError, match="exactly one managed secret"):
            _managed_secret_arn(secrets)


def test_pre_hardening_cluster_keeps_the_generated_master_password():
    secrets = _secrets(hardened=False, database="app")
    secrets.persist_url = lambda purpose, value: pulumi.Output.from_input(ARN)
    resources, _ = _register(secrets, material=True, engine_version="4.0.0")
    cluster = resources[CLUSTER]["inputs"]
    assert "masterPassword" in cluster
    assert "manageMasterUserPassword" not in cluster


@pytest.mark.parametrize("key", ["documentDbPassword", "documentDbMasterPassword"])
def test_a_password_config_key_raises_on_the_hardened_path(key):
    with pytest.raises(ValueError, match=key):
        _register(_secrets(hardened=True), {key: "synthetic"})


def test_unset_password_config_keys_are_accepted():
    with mocked_pulumi_context({}):
        reject_documentdb_password_config()


def test_password_config_is_refused_before_any_resource_registers():
    """F-05/F-06: the refusal runs before the component, so nothing is created."""
    recorder = RecordingMocks()
    monitor = OptionRecordingMonitor(recorder)

    def program():
        DataPlane(
            "data",
            settings=_settings(),
            network=_network(),
            runtime_secrets=_secrets(hardened=True),
        )

    with mocked_pulumi_context({"documentDbPassword": "synthetic"}):
        with pytest.raises(ValueError, match="documentDbPassword"):
            _run_pulumi_program(program, test_mocks=recorder, monitor=monitor)
    assert not [row for row in recorder.resources if "data" in str(row["name"])]
    assert not [row for row in recorder.resources if row["type"].startswith("aws:")]


# F-09: case-insensitive, so ``documentDBPassword`` is caught as well.
PASSWORD_KEY = re.compile(r"documentdb\w*password\w*", re.IGNORECASE)


def _password_key_literals(source):
    """Return every string literal in ``source`` that names a DocumentDB password."""
    return {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and PASSWORD_KEY.fullmatch(node.value)
    }


def test_every_documentdb_password_config_key_is_refused_on_the_hardened_path():
    """F-03/F-09: a new password config key cannot bypass the hardened refusal."""
    root = Path(__file__).parents[2]
    found = set()
    for directory in ("pulumi", "scripts", "policy"):
        for path in sorted((root / directory).rglob("*.py")):
            found |= _password_key_literals(path.read_text())
    assert found, "the scan must see at least the existing password keys"
    assert found <= set(DOCUMENTDB_PASSWORD_CONFIG_KEYS), found


@pytest.mark.parametrize(
    "key", ["documentDbRotatedPassword", "documentDBPassword", "DocumentDbPassword"]
)
def test_the_password_key_scan_finds_an_unlisted_key(key):
    source = f'config.get("{key}")\nx = "documentDbHost"'
    assert _password_key_literals(source) == {key}


def test_lifecycle_doc_records_the_composed_refusal_and_the_iam_url():
    """F-04: S1.3 composes the data plane, so the stack-level refusal is real."""
    text = " ".join(
        (Path(__file__).parents[2] / "specs/poc/secret-lifecycle.md")
        .read_text()
        .split()
    )
    section = text[text.index("### DocumentDB primary password") :]
    for marker in (
        "composes the data plane under its stack-wide guard",
        "before any resource registers",
        "without echoing its value",
        "MONGODB-AWS",
        "authSource=%24external",
        "V-17",
        "document_db_url",
        "lambda_network",
        "documentdb_managed_secret_arn",
    ):
        assert marker in section, marker
    assert "only once S1.3 composes it" not in section


def _hardened_redis(**redis):
    resources, captured = _register(_secrets(hardened=True), **redis)
    return resources, captured


def test_hardened_redis_requires_tls_and_holds_no_auth_token():
    """FR-04 P: TLS required, one user group, no ``auth_token`` (D-1, AD-02)."""
    resources, _ = _hardened_redis()
    group = resources[REPLICATION_GROUP]["inputs"]
    assert group["transitEncryptionEnabled"] is True
    assert group["transitEncryptionMode"] == "required"
    assert group["atRestEncryptionEnabled"] is True
    assert (group["engine"], group["engineVersion"]) == ("redis", "7.1")
    assert group["userGroupIds"] == ["user-service-dev-redis-users"]
    assert not [key for key in group if key.lower().startswith("authtoken")]
    assert group["securityGroupIds"] == ["sg-redis"]


def test_hardened_redis_users_are_the_iam_app_user_and_a_disabled_default():
    """FR-04 P (V-5, V-9): ``user_name == user_id``; ``default`` is ``off``."""
    resources, _ = _hardened_redis()
    app = resources[APP_USER]["inputs"]
    assert app["authenticationMode"] == {"type": "iam"}
    assert app["userName"] == app["userId"] == "user-service-dev-app"
    assert app["accessString"] == REDIS_APP_ACCESS_STRING
    default = resources[DEFAULT_USER]["inputs"]
    assert default["userName"] == "default"
    assert default["userId"] not in ("default", app["userId"])
    assert default["accessString"] == "off -@all"
    assert default["authenticationMode"] == {"type": "no-password-required"}
    for user in (app, default):
        assert user["engine"] == "redis"
        assert not [key for key in user if "password" in key.lower()]
    group = resources[USER_GROUP]["inputs"]
    assert group["userGroupId"] == "user-service-dev-redis-users"
    assert group["userIds"] == [default["userId"], app["userId"]]


def test_hardened_redis_outputs_are_plain_iam_values():
    """FR-04 P: a ``rediss://`` URL with no userinfo and the signer inputs."""
    resources, captured = _hardened_redis()
    redis = captured["plane"].redis
    assert captured["redis_url"] == f"rediss://{REDIS_ENDPOINT}:6379"
    assert urlsplit(captured["redis_url"]).username is None
    assert (redis.iam_user_id, redis.replication_group_id, redis.port) == (
        "user-service-dev-app",
        "user-service-dev-redis",
        6379,
    )
    assert not [row for row in resources.values() if "secret" in row["type"].lower()]


def test_a_mixed_case_replication_group_id_is_lower_cased_in_the_env_value():
    """FR-04 B: the token signer needs the lower-case replication-group ID."""
    resources, captured = _hardened_redis(stack_tag="User-Service-Dev")
    redis = captured["plane"].redis
    assert resources[REPLICATION_GROUP]["inputs"]["replicationGroupId"] == (
        "User-Service-Dev-redis"
    )
    assert redis.replication_group_id == "user-service-dev-redis"
    app = resources[APP_USER]["inputs"]
    # ElastiCache stores user IDs in lower case; the IAM name must equal it.
    assert app["userName"] == app["userId"] == redis.iam_user_id
    assert redis.iam_user_id == "user-service-dev-app"


def test_redis_identity_is_deterministic_and_lower_case():
    identity = redis_iam_identity("user-service-infrastructure-test")
    assert identity[:2] == (
        "user-service-infrastructure-test-redis",
        "user-service-infrastructure-test-app",
    )
    assert all(len(value) <= 40 and value == value.lower() for value in identity)
    assert len(set(identity)) == 4


@pytest.mark.parametrize("version", ["6.2", "6.0", "5.0.6", "7", "seven", None, 7.1])
def test_a_redis_engine_without_iam_raises_before_registration(version):
    """N (V-9): IAM authentication needs Redis OSS 7.0 or later."""
    with pytest.raises(ValueError, match="V-9"):
        require_iam_redis_engine(version)
    with pytest.raises(ValueError, match="V-9"):
        _hardened_redis(redis_version=version)


@pytest.mark.parametrize("version", ["7.0", "7.1", "7.0.5", "8.0"])
def test_iam_capable_redis_engines_pass(version):
    assert require_iam_redis_engine(version) is None


@pytest.mark.parametrize("endpoint", ["user@host", "user:synthetic@host", "@host"])
def test_userinfo_in_the_redis_url_raises(endpoint):
    """FR-04 N: ``REDIS_URL`` never carries userinfo."""
    with pytest.raises(ValueError, match="userinfo"):
        redis_iam_url(endpoint, 6379)


def test_a_redis_auth_token_config_raises_before_any_resource():
    """FR-04 N: a configured AUTH token is refused, never silently ignored."""
    recorder = RecordingMocks()
    monitor = OptionRecordingMonitor(recorder)

    def program():
        DataPlane(
            "data",
            settings=_settings(),
            network=_network(),
            runtime_secrets=_secrets(hardened=True),
        )

    with mocked_pulumi_context({"redisAuthToken": "synthetic-token"}):
        with pytest.raises(ValueError, match="redisAuthToken must not") as failure:
            _run_pulumi_program(program, test_mocks=recorder, monitor=monitor)
    assert "synthetic-token" not in str(failure.value)
    assert not [row for row in recorder.resources if row["type"].startswith("aws:")]
    with mocked_pulumi_context({}):
        reject_redis_auth_token_config()


def test_pre_hardening_redis_keeps_its_auth_token_until_s4_10():
    """AD-25: the pre-hardening branch is unchanged."""
    secrets = _secrets(hardened=False, database="app")
    secrets.persist_url = lambda purpose, value: pulumi.Output.from_input(ARN)
    resources, _ = _register(secrets, material=True, engine_version="4.0.0")
    group = resources[REPLICATION_GROUP]["inputs"]
    assert group["authTokenUpdateStrategy"] == "ROTATE"
    assert "authToken" in group and "userGroupIds" not in group
    assert not [row for row in resources.values() if row["type"].endswith(":User")]


def test_lifecycle_doc_records_redis_iam_and_its_evidence():
    """S1.4: the doc names the shape, the V-5/V-9 findings and the live steps."""
    text = " ".join(
        (Path(__file__).parents[2] / "specs/poc/secret-lifecycle.md")
        .read_text()
        .split()
    )
    section = text[text.index("### Redis authenticates with IAM") :]
    for marker in (
        'transit_encryption_mode="required"',
        "no `auth_token`",
        "`user_name == user_id`",
        "access string `off -@all`",
        "`REDIS_LOCKOUT_URL` are the same",
        "lower-case `REDIS_REPLICATION_GROUP_ID`",
        "`AWS_REGION`",
        "redisAuthToken",
        "V-5 (docs and provider source)",
        "pulumi-aws 7.23.0",
        "`password | no-password-required | iam`",
        "V-9 (docs, ElastiCache",
        "Redis OSS 7.0",
        "12 hours",
        "15 minutes",
        "S4.6 step 4",
        "step 7",
        "step 10",
        "AD-25",
    ):
        assert marker in section, marker
    assert "ElastiCache stays outside it until S1.4" not in text
