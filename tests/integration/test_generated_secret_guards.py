"""Fail-closed lifecycle guards complement the native provider preview."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.runtime_secrets import RuntimeSecrets, RuntimeSecretsDescriptor
from app.workload_phase import _merge_tags

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
# F5: a hardened container holds both Redis URLs as equal plain rows.
REDIS_ROWS = [
    {"name": name, "value": "rediss://a:6379"}
    for name in ("REDIS_URL", "REDIS_LOCKOUT_URL")
]


def test_registry_contract_cannot_authorize_secret_component():
    contract = json.loads((PROJECT_ROOT / "specs/poc/poc-test.json").read_text())
    with pytest.raises(ValueError, match="workload declaration"):
        RuntimeSecretsDescriptor(contract)


def test_partial_or_duplicate_endpoint_secret_inventory_cannot_be_completed():
    # Exercise closure validation without issuing provider registrations: a caller
    # cannot publish outputs or overwrite a purpose before endpoint composition.
    partial = object.__new__(RuntimeSecrets)
    partial.references = {"redis_url": {}, "document_db_url": {}}
    partial.secret_arns = {"redis_url": "synthetic-reference"}
    with pytest.raises(ValueError, match="inventory is incomplete"):
        partial.complete()
    for purpose in ("redis_url", "foreign-purpose"):
        with pytest.raises(ValueError, match="invalid or duplicated"):
            partial.persist_url(purpose, "synthetic-url")


def test_workload_tag_composition_preserves_explicit_tags_without_owner_override():
    baseline = {"Owner": "team-user-service", "Environment": "test"}
    explicit = {"Name": "synthetic", "Owner": "team-user-service"}
    assert _merge_tags(explicit, baseline) == {**baseline, "Name": "synthetic"}
    assert explicit == {"Name": "synthetic", "Owner": "team-user-service"}
    for forbidden in ({"Owner": "foreign"}, "invalid-shape"):
        with pytest.raises(ValueError, match="preserved baseline tags"):
            _merge_tags(forbidden, baseline)


def test_private_gateway_missing_certificate_cannot_fall_back_to_http():
    from app.compute import ComputePlane

    settings = SimpleNamespace(runtime=SimpleNamespace(certificate_arn=None))
    with pytest.raises(ValueError, match="admitted certificate"):
        object.__new__(ComputePlane)._create_http_listener(
            settings, None, None, private_gateway=True
        )


PURPOSES = ("app_secret", "oauth_encryption_key")
ENV = {"app_secret": "APP_SECRET", "oauth_encryption_key": "OAUTH_ENCRYPTION_KEY"}
ARNS = {
    purpose: "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    f"/user-service-infrastructure/runtime/test/synthetic-{purpose}-AbCdEf"
    for purpose in PURPOSES
}


class _Resolved:
    """Stand-in for a resolved Output: apply runs the callback immediately."""

    def __init__(self, value):
        self.value = value

    def apply(self, callback):
        return callback(self.value)


def _hardened(arns):
    fixture = PROJECT_ROOT / "tests/fixtures/poc-contract"
    contract = json.loads((fixture / "workload-hardened.synthetic.json").read_text())
    resource = object.__new__(RuntimeSecrets)
    resource._hardened = True
    resource.descriptor = RuntimeSecretsDescriptor(contract)
    resource.references = {
        purpose: contract["workload"]["secret_lifecycle"]["references"][purpose]
        for purpose in PURPOSES
    }
    resource.secret_arns = arns
    return resource


def test_hardened_ecs_secrets_use_the_arn_and_refuse_a_version_suffix():
    arns = {purpose: _Resolved(ARNS[purpose]) for purpose in PURPOSES}
    rows = _hardened(arns).ecs_secrets()
    assert rows == [{"name": ENV[p], "valueFrom": ARNS[p]} for p in PURPOSES]
    arns["app_secret"] = _Resolved(ARNS["app_secret"] + ":::" + "1" * 32)
    with pytest.raises(ValueError, match="version"):
        _hardened(arns).ecs_secrets()
    with pytest.raises(ValueError, match="incomplete"):
        _hardened({}).ecs_secrets()


def test_hardened_ecs_secret_from_another_account_or_name_is_refused():
    foreign = ARNS["app_secret"].replace("891377212104", "123456789012")
    other_name = ARNS["oauth_encryption_key"]
    for arn in (foreign, other_name):
        arns = {purpose: _Resolved(ARNS[purpose]) for purpose in PURPOSES}
        arns["app_secret"] = _Resolved(arn)
        with pytest.raises(ValueError, match="declaration"):
            _hardened(arns).ecs_secrets()


DOCUMENTDB_ENDPOINT = "synthetic.cluster-abc.eu-central-1.docdb.amazonaws.com"
SECRET_ARN = ARNS["app_secret"]


def test_hardened_documentdb_url_and_engine_guards():
    """FR-02 and V-17 helpers that the native preview reaches only as unknowns."""
    from app.data import (
        _managed_secret_arn,
        documentdb_iam_url,
        require_iam_documentdb_engine,
    )

    url = documentdb_iam_url(DOCUMENTDB_ENDPOINT, 27017, "user service", "/ca.pem")
    assert url.startswith(f"mongodb://{DOCUMENTDB_ENDPOINT}:27017/user%20service?")
    assert url.endswith("&authSource=%24external&authMechanism=MONGODB-AWS")
    with pytest.raises(ValueError, match="userinfo"):
        documentdb_iam_url("user:x@" + DOCUMENTDB_ENDPOINT, 27017, "db", "/ca.pem")
    assert require_iam_documentdb_engine("5.0.0") is None
    with pytest.raises(ValueError, match="V-17"):
        require_iam_documentdb_engine("4.0.0")
    managed = SimpleNamespace(secret_arn="arn:synthetic")
    assert _managed_secret_arn([managed]) == "arn:synthetic"
    with pytest.raises(ValueError, match="exactly one managed secret"):
        _managed_secret_arn([])


def test_hardened_redis_url_engine_and_lockout_guards():
    """FR-04, V-9 and FR-08 B helpers the native preview reaches as unknowns."""
    from app.compute import ComputePlane
    from app.data import redis_iam_url, require_iam_redis_engine

    assert redis_iam_url("master.synthetic", 6379) == "rediss://master.synthetic:6379"
    with pytest.raises(ValueError, match="userinfo"):
        redis_iam_url(":synthetic@master.synthetic", 6379)
    assert require_iam_redis_engine("7.1") is None
    with pytest.raises(ValueError, match="V-9"):
        require_iam_redis_engine("6.2")
    url = {"name": "REDIS_URL", "value": "rediss://a:6379"}
    same = [url, {"name": "REDIS_LOCKOUT_URL", "value": "rediss://a:6379"}]
    plain = [{"environment": same, "secrets": []}]
    serialized = ComputePlane._serialize_container(plain, unversioned=True)
    assert serialized == json.dumps(plain)
    # F5: the hardened shape needs both plain URLs, as bare rediss:// URLs.
    lockout = [{"name": "REDIS_LOCKOUT_URL", "valueFrom": SECRET_ARN}]
    for environment, secrets, message in (
        ([url], [], "must both be plain values"),
        ([url], lockout, "must both be plain values"),
        (
            [{**row, "value": "redis://a:6379"} for row in same],
            [],
            "must be a rediss:// URL",
        ),
        (
            [{**row, "value": "rediss://a:6379/0"} for row in same],
            [],
            "must be a rediss:// URL",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            ComputePlane._serialize_container(
                [{"environment": environment, "secrets": secrets}],
                unversioned=True,
            )
    # The pre-hardening shape keeps only the equality rule (AD-25).
    assert ComputePlane._serialize_container(
        [{"environment": [url], "secrets": []}], unversioned=False
    )
    with pytest.raises(ValueError, match="REDIS_LOCKOUT_URL must equal"):
        ComputePlane._serialize_container(
            [
                {
                    "environment": [
                        url,
                        {"name": "REDIS_LOCKOUT_URL", "value": "rediss://b:6379"},
                    ],
                    "secrets": [],
                }
            ],
            unversioned=True,
        )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "plain string"),
        ("AKIA" + "SYNTHETIC0000000", "access key"),
        ("https://user:x@sqs.example/queue", "userinfo"),
        ("https://sqs.example/queue?secret_key=x", "credential parameter"),
    ],
)
def test_credential_bearing_environment_values_are_refused(value, message):
    """FR-03 N (AD-20): no key, userinfo or credential parameter."""
    from app.compute import require_credential_free

    with pytest.raises(ValueError, match=message):
        require_credential_free(value)


def test_plain_environment_and_hardened_scale_guards(monkeypatch):
    from app import compute

    rows = [{"name": "APP_SECRET", "value": "x"}]
    with pytest.raises(ValueError, match="overlap"):
        compute.require_plain_environment(rows, [{"name": "APP_SECRET"}])
    # The native preview leaves the container JSON unknown, so serialize here.
    plain = [
        {
            "environment": rows + REDIS_ROWS,
            "secrets": [{"name": "OTHER", "valueFrom": "x"}],
        }
    ]
    for unversioned in (False, True):
        serialize = compute.ComputePlane._serialize_container
        if unversioned:
            with pytest.raises(ValueError, match="must not pin a version"):
                serialize(plain, unversioned=unversioned)
        else:
            assert serialize(plain, unversioned=unversioned) == json.dumps(plain)
        overlap = [{"environment": rows, "secrets": [{"name": "APP_SECRET"}]}]
        with pytest.raises(ValueError, match="closed name pairs"):
            serialize(overlap, unversioned=unversioned)
        overlap[0]["secrets"][0]["valueFrom"] = SECRET_ARN
        with pytest.raises(ValueError, match="overlap"):
            serialize(overlap, unversioned=unversioned)
    fake = SimpleNamespace(apply=lambda callback: callback("https://sqs/queue"))
    monkeypatch.setattr(compute.pulumi.Output, "from_input", lambda _: fake)
    plane = object.__new__(compute.ComputePlane)
    assert plane._queue_dsn("ignored", "eu-central-1") == (
        "https://sqs/queue?region=eu-central-1&auto_setup=false"
    )
    for name in ("validate_runtime_roles", "validate_health_check_runtime"):
        monkeypatch.setattr(compute, name, lambda *_: None)
    secrets = SimpleNamespace(
        descriptor=SimpleNamespace(hardened=True, validate_target=lambda _: None)
    )
    with pytest.raises(ValueError, match="zero tasks"):
        compute.ComputePlane(
            "compute",
            settings=SimpleNamespace(
                is_managed=True, environment="test", runtime=None, queues=None
            ),
            network=None,
            data=None,
            messaging=None,
            runtime_secrets=secrets,
        )


def _task(engine, environment, secrets=None):
    import pulumi

    if type(environment) is list:
        environment = environment + REDIS_ROWS
    container = {"environment": environment, "secrets": secrets or []}
    key = "containerDefinitions" if engine else "container_definitions"
    value = container if environment is None else json.dumps([container])
    return pulumi.ResourceTransformArgs(
        custom=True,
        type_="aws:ecs/taskDefinition:TaskDefinition",
        name="probe",
        props={key: value},
        opts=None,
    )


@pytest.mark.parametrize("engine", [False, True])
def test_task_definition_property_check_reads_resolved_definitions(engine):
    """The guard checks a resolved JSON string and refuses a plain map (F-01)."""
    from app.workload_phase import _reject_secret_material

    plain = [{"name": "APP_ENV", "value": "prod"}]
    secret = [{"name": "APP_SECRET", "valueFrom": SECRET_ARN}]
    assert _reject_secret_material(_task(engine, plain, secret)) is None
    # A map is no JSON string: it was never a deferral and now fails closed.
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_task(engine, None))
    for environment, secrets in (
        ([{"name": "APP_SECRET", "value": "x"}], secret),
        (plain, [{"name": "B", "valueFrom": SECRET_ARN + ":::" + "1" * 32}]),
        (["APP_ENV=prod"], None),
        ([{"name": ["A"], "value": "x"}], None),
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(_task(engine, environment, secrets))
    import pulumi

    for value in ("not-json", "{}"):
        args = pulumi.ResourceTransformArgs(
            custom=True,
            type_="aws:ecs/taskDefinition:TaskDefinition",
            name="probe",
            props={"containerDefinitions": value},
            opts=None,
        )
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args)


@pytest.mark.parametrize("step", [1, 2])
def test_step_two_and_elastic_types_are_refused(step):
    """FR-34 B and V-17 N at the guard."""
    from app.workload_phase import STEP_TWO_TYPES, _reject_secret_material

    import pulumi

    def args(kind):
        return pulumi.ResourceTransformArgs(
            custom=True, type_=kind, name="probe", props={}, opts=None
        )

    with pytest.raises(ValueError, match="instance-based"):
        _reject_secret_material(args("aws:docdb/elasticCluster:ElasticCluster"), step)
    message = "step-2 resource" if step == 1 else "unreviewed type"
    for kind in STEP_TWO_TYPES:
        with pytest.raises(ValueError, match=message):
            _reject_secret_material(args(kind), step)


@pytest.mark.parametrize("engine", [False, True])
def test_s13_gate_property_checks_fail_closed(engine):
    """F-01..F-03: the listener, secret, service and volume checks at the guard."""
    from app.workload_phase import _reject_secret_material
    from pulumi.runtime import rpc

    import pulumi

    def args(kind, props):
        if not engine:
            return _sdk_args(kind, props)
        return pulumi.ResourceTransformArgs(
            custom=True, type_=kind, name="probe", props=props, opts=None
        )

    listener, secret = "aws:lb/listener:Listener", "aws:secretsmanager/secret:Secret"
    service, task = "aws:ecs/service:Service", "aws:ecs/taskDefinition:TaskDefinition"
    plain = json.dumps([{"name": "f", "environment": REDIS_ROWS, "secrets": []}])
    versioned = "arn:aws:secretsmanager:eu-central-1:891377212104:secret:s-AbCdEf"
    awslogs = json.dumps(
        [
            {
                "name": "f",
                "environment": REDIS_ROWS,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {"awslogs-group": "/g", "awslogs-region": "r"},
                },
            }
        ]
    )
    splunk = json.dumps(
        [
            {
                "name": "f",
                "environment": REDIS_ROWS,
                "logConfiguration": {
                    "logDriver": "splunk",
                    "options": {"splunk-url": "https://collector.example"},
                    "secretOptions": [
                        {"name": "t", "valueFrom": versioned + ":password:AWSPREVIOUS:"}
                    ],
                },
            }
        ]
    )
    for kind, props in (
        (listener, {}),
        (listener, {"defaultActions": [{"type": "forward"}]}),
        (service, {}),
        (secret, {"name": "fixture"}),
        (task, {"containerDefinitions": plain, "volumes": [{"name": "a"}]}),
        (task, {"containerDefinitions": awslogs}),
    ):
        assert _reject_secret_material(args(kind, props)) is None
    for kind, props in (
        (listener, {"defaultActions": rpc.wrap_rpc_secret([])}),
        (listener, {"defaultActions": [object()]}),
        (listener, {"defaultActions": [{"authenticateOidc": {}}]}),
        (service, {"serviceConnectConfiguration": {}}),
        (secret, {"policy": "{}"}),
        (task, {"containerDefinitions": plain, "volumes": [{"hostPath": "/"}]}),
        (task, {"containerDefinitions": '[{"name": "a", "NAME": "b"}]'}),
        # N-01: the closed awslogs shape, with no secretOptions.
        (task, {"containerDefinitions": splunk}),
        # N-03: two casings of one input are ambiguous.
        (task, {"containerDefinitions": plain, "container_definitions": plain}),
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args(kind, props))
    # An Output with no settled futures is opaque on the engine path only.
    opaque = args(task, {"containerDefinitions": object.__new__(pulumi.Output)})
    if engine:
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(opaque)
    else:
        assert _reject_secret_material(opaque) is None


def _sdk_args(kind, props):
    import pulumi

    return pulumi.ResourceTransformationArgs(
        resource=None, type_=kind, name="probe", props=props, opts=None
    )


def test_s13_gate_serializer_refuses_unreviewed_shapes():
    """F-01: ComputePlane refuses what the guard refuses before it serializes."""
    from app.compute import ComputePlane

    for containers, message in (
        ({"name": "f"}, "must be a list"),
        ([{"name": "f", "Name": "g"}], "unreviewed key"),
        (
            [
                {
                    "environment": REDIS_ROWS,
                    "logConfiguration": {"options": {}, "Options": {}},
                }
            ],
            "repeats a key",
        ),
        (
            [{"environment": REDIS_ROWS, "command": ["AKIA" + "SYNTHETIC0000000"]}],
            "access key",
        ),
        (
            [
                {
                    "environment": REDIS_ROWS,
                    "logConfiguration": {"logDriver": "splunk", "options": {}},
                }
            ],
            "closed awslogs",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            ComputePlane._serialize_container(containers, unversioned=True)
    from app.compute import _require_unversioned_value_from

    arn = "arn:aws:secretsmanager:eu-central-1:891377212104:secret:s-AbCdEf"
    _require_unversioned_value_from([{"valueFrom": arn}, {"a": 1}])
    with pytest.raises(ValueError, match="must not pin a version"):
        _require_unversioned_value_from({"a": [{"valueFrom": arn + "::AWSCURRENT:"}]})
