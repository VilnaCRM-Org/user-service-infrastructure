"""Hardened DocumentDB primary password: AWS-managed, never configured (S1.2)."""

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.data import DataPlane
from app.environment import (
    DOCUMENTDB_PASSWORD_CONFIG_KEYS,
    reject_documentdb_password_config,
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


def _settings():
    return SimpleNamespace(
        is_managed=True,
        stack_tag="user-service-dev",
        region="eu-central-1",
        documentdb=SimpleNamespace(
            username="synthetic",
            port=27017,
            engine_version="5.0.0",
            instance_class="db.t3.medium",
            instance_count=1,
            backup_retention_days=7,
            preferred_backup_window="01:00-02:00",
            preferred_maintenance_window="sun:03:00-sun:04:00",
        ),
        redis=SimpleNamespace(
            port=6379,
            engine_version="7.1",
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


def _secrets(hardened):
    return SimpleNamespace(
        descriptor=SimpleNamespace(hardened=hardened),
        secret_arns={"document_db_url": ARN, "redis_url": ARN},
        values={},
    )


def _register(secrets, config=None, material=False):
    recorder = RecordingMocks()
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
            settings=_settings(),
            network=_network(),
            runtime_secrets=secrets,
        )
        captured["plane"] = plane

    with mocked_pulumi_context(config or {}):
        _run_pulumi_program(program, test_mocks=recorder, monitor=monitor)
    resources = {str(row["name"]): row for row in recorder.resources}
    return resources, captured["plane"]


def test_hardened_cluster_uses_the_managed_password_without_a_master_password():
    resources, _ = _register(_secrets(hardened=True))
    cluster = resources[CLUSTER]["inputs"]
    assert cluster["manageMasterUserPassword"] is True
    assert "masterPassword" not in cluster
    assert cluster["masterUsername"] == "synthetic"


def test_hardened_cluster_keeps_the_aws_managed_key_under_exception_a05():
    # A-05: pulumi-aws 7.23.0 exposes no master_user_secret_kms_key_id, so the
    # managed secret stays on the AWS-managed key and no key is ever passed.
    resources, _ = _register(_secrets(hardened=True))
    inputs = resources[CLUSTER]["inputs"]
    assert "masterUserSecretKmsKeyId" not in inputs
    assert not any("kms" in key.lower() for key in inputs)


def test_hardened_data_plane_holds_no_generated_secret_material():
    resources, plane = _register(_secrets(hardened=True))
    assert not any(
        row["type"].startswith(("random:", "tls:"))
        or row["type"] == "aws:secretsmanager/secretVersion:SecretVersion"
        for row in resources.values()
    )
    assert plane._runtime_secrets.values == {}


def test_hardened_outputs_expose_only_documentdb_until_s13():
    _, plane = _register(_secrets(hardened=True))
    assert not hasattr(plane, "outputs")
    assert plane.documentdb.port is not None
    assert len(plane.documentdb.instances) == 1


def test_pre_hardening_cluster_keeps_the_generated_master_password():
    secrets = _secrets(hardened=False)
    secrets.descriptor.database_name = "app"
    secrets.descriptor.ca_bundle_path = "/etc/ca.pem"
    secrets.persist_url = lambda purpose, value: pulumi.Output.from_input(ARN)
    resources, _ = _register(secrets, material=True)
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


PASSWORD_KEY = re.compile(r"documentDb\w*Password\w*")


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
    """F-03: a new password config key cannot bypass the hardened refusal."""
    found = set()
    for path in sorted((Path(__file__).parents[2] / "pulumi").rglob("*.py")):
        found |= _password_key_literals(path.read_text())
    assert found, "the scan must see at least the existing password keys"
    assert found <= set(DOCUMENTDB_PASSWORD_CONFIG_KEYS), found


def test_the_password_key_scan_finds_an_unlisted_key():
    source = 'config.get("documentDbRotatedPassword")\nx = "documentDbHost"'
    assert _password_key_literals(source) == {"documentDbRotatedPassword"}


def test_lifecycle_doc_qualifies_the_refusal_until_s13_composes_the_data_plane():
    """F-04: the doc does not claim the workload stack refuses it yet."""
    text = " ".join(
        (Path(__file__).parents[2] / "specs/poc/secret-lifecycle.md")
        .read_text()
        .split()
    )
    section = text[text.index("### DocumentDB primary password") :]
    for marker in (
        "only once S1.3 composes it",
        "S1.3 owns the composition-level N test",
        "without echoing its value",
    ):
        assert marker in section, marker
