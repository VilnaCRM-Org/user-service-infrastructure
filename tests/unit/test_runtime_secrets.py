"""Closed declarations and synthetic registrations; never native secret material."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app import runtime_secrets as module
from app.compute import ComputePlane
from app.data import DataPlane
from app.environment import resolve_stack_settings
from test_environment_component import (
    CENTRAL_EXECUTION_ROLE,
    CENTRAL_TASK_ROLE,
    mocked_pulumi_context,
)
from test_poc_workload_phase import graph

ROOT = Path(__file__).parents[2]
SECRET_MATERIAL = ("random:", "tls:", "aws:secretsmanager/secretVersion:SecretVersion")
# V-8 provider-source record (first case of S1.1). pulumi-aws 7.23.0 builds on
# hashicorp/terraform-provider-aws v6.36.0 (upstream submodule commit
# 4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d); none of its 25 patches touches
# internal/service/secretsmanager. Read paths at that commit:
#   secret.go resourceSecretRead -> DescribeSecret, GetResourcePolicy
#   secret_rotation.go resourceSecretRotationRead -> DescribeSecret
#   secret_policy.go resourceSecretPolicyRead -> GetResourcePolicy
# None of their create, read, update or delete paths calls GetSecretValue; only
# secret_version.go does, which is why no SecretVersion may be declared (FR-09).
V8_PROVIDER_VERSION = "7.23.0"
V8_METADATA_READ_TYPES = {
    "aws:secretsmanager/secret:Secret",
    "aws:secretsmanager/secretRotation:SecretRotation",
    "aws:secretsmanager/secretPolicy:SecretPolicy",
}


@pytest.fixture(autouse=True)
def trusted_script_path(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))


@pytest.fixture
def contract():
    return json.loads(
        (ROOT / "tests/fixtures/poc-contract/workload.synthetic.json").read_text()
    )


def test_descriptor_copies_only_schema_valid_full_workload(contract):
    sender = contract["workload"]["external"]["mail"]["sender"]
    descriptor = module.RuntimeSecretsDescriptor(contract)
    original = descriptor.references
    contract["workload"]["secret_lifecycle"]["references"].clear()
    returned = descriptor.references
    returned.clear()
    assert descriptor.references == original
    assert descriptor.mailer_dsn == "ses+api://default?region=eu-central-1"
    assert descriptor.mail_sender == sender


@pytest.mark.parametrize(
    "change", ["extra", "missing", "foreign-name", "foreign-key", "duplicate", "owner"]
)
def test_invalid_secret_declarations_cannot_register_resources(
    contract, monkeypatch, change
):
    references = contract["workload"]["secret_lifecycle"]["references"]
    if change == "extra":
        references["smtp_password"] = dict(references["app_secret"])
    elif change == "missing":
        del references["app_secret"]
    elif change == "foreign-name":
        references["app_secret"]["name"] = "/foreign/secret"
    elif change == "foreign-key":
        references["app_secret"]["kms_key_arn"] = references["app_secret"][
            "kms_key_arn"
        ].replace("891377212104", "999999999999")
    elif change == "duplicate":
        references["app_secret"]["name"] = references["redis_auth_token"]["name"]
    else:
        references["app_secret"]["owner"] = "caller"
    monkeypatch.setattr(
        module.pulumi.ComponentResource,
        "__init__",
        lambda *a, **kw: pytest.fail("registered before validation"),
    )
    with pytest.raises(ValueError):
        module.RuntimeSecrets(
            "runtime", descriptor=module.RuntimeSecretsDescriptor(contract)
        )


def test_resource_entry_revalidates_tampered_descriptor(contract, monkeypatch):
    descriptor = module.RuntimeSecretsDescriptor(contract)
    descriptor._contract["workload"]["secret_lifecycle"]["references"].clear()
    monkeypatch.setattr(
        module.pulumi.ComponentResource,
        "__init__",
        lambda *a, **kw: pytest.fail("registered before validation"),
    )
    with pytest.raises(ValueError):
        module.RuntimeSecrets("runtime", descriptor=descriptor)
    with pytest.raises(ValueError, match="validated descriptor"):
        module.RuntimeSecrets("runtime", descriptor=None)


def test_registry_descriptor_cannot_construct_runtime_secrets():
    contract = json.loads((ROOT / "specs/poc/poc-test.json").read_text())
    with pytest.raises(ValueError, match="workload declaration"):
        module.RuntimeSecretsDescriptor(contract)


@pytest.mark.parametrize("target", ["project", "stack", "region", "account", "roles"])
def test_protected_context_and_settings_must_match(contract, monkeypatch, target):
    descriptor = module.RuntimeSecretsDescriptor(contract)
    central = contract["workload"]["central"]
    monkeypatch.setattr(
        module.pulumi,
        "get_project",
        lambda: "foreign" if target == "project" else "user-service-infrastructure",
    )
    monkeypatch.setattr(
        module.pulumi, "get_stack", lambda: "prod" if target == "stack" else "test"
    )
    monkeypatch.setattr(
        module.pulumi,
        "Config",
        lambda _: SimpleNamespace(
            require=lambda _: "us-east-1" if target == "region" else "eu-central-1",
            get_object=lambda _: [] if target == "account" else ["891377212104"],
        ),
    )
    settings = SimpleNamespace(
        environment="test",
        region="eu-central-1",
        network=SimpleNamespace(app_subnet_cidrs=descriptor.trusted_proxy_cidrs),
        images=SimpleNamespace(
            web_repository_name=contract["registries"]["web"]["name"],
            worker_repository_name=contract["registries"]["worker"]["name"],
        ),
        runtime=SimpleNamespace(
            mail_sender=descriptor.mail_sender,
            execution_role_arn=central["execution_role_arn"],
            task_role_arn="foreign" if target == "roles" else central["task_role_arn"],
        ),
    )
    with pytest.raises(ValueError, match="deployment context|workload target"):
        descriptor.validate_target(settings)


def _plain(value):
    if isinstance(value, dict) and "4dabf18193072939515e22adb298388d" in value:
        return value["value"]
    return value


def test_actual_graph_persists_ten_versions_and_injects_nine_names(tmp_path, contract):
    receipt = graph(tmp_path)
    assert receipt["error"] is None
    rows = receipt["registrations"]
    declarations = contract["workload"]["secret_lifecycle"]["references"]
    secrets = [
        row
        for row in rows.values()
        if row["type"] == "aws:secretsmanager/secret:Secret"
    ]
    versions = [
        row
        for row in rows.values()
        if row["type"] == "aws:secretsmanager/secretVersion:SecretVersion"
    ]
    assert len(secrets) == len(versions) == 10
    assert {(r["inputs"]["name"], r["inputs"]["kmsKeyId"]) for r in secrets} == {
        (d["name"], d["kms_key_arn"]) for d in declarations.values()
    }
    assert all(r["protect"] for r in [*secrets, *versions])
    assert all("secretString" in r["additional_secret_outputs"] for r in versions)
    assert "synthetic-password-unchanging" == _plain(
        rows["user-service-documentdb-cluster"]["inputs"]["masterPassword"]
    )
    assert "synthetic-password-unchanging" == _plain(
        rows["user-service-redis"]["inputs"]["authToken"]
    )
    for purpose in ("document_db_url", "redis_url"):
        assert "synthetic-password-unchanging" in _plain(
            rows[f"runtime-{purpose}-version"]["inputs"]["secretString"]
        )
    for row in rows.values():
        if row["type"] != "aws:ecs/taskDefinition:TaskDefinition":
            continue
        definition = json.loads(_plain(row["inputs"]["containerDefinitions"]))[0]
        injected = {
            entry["name"]: entry["valueFrom"] for entry in definition["secrets"]
        }
        assert len(definition["secrets"]) == 9
        assert set(injected) == {
            "MONGODB_URL",
            "REDIS_URL",
            "REDIS_LOCKOUT_URL",
            "APP_SECRET",
            "OAUTH_ENCRYPTION_KEY",
            "OAUTH_PASSPHRASE",
            "TWO_FACTOR_ENCRYPTION_KEY",
            "OAUTH_PRIVATE_KEY_PEM",
            "OAUTH_PUBLIC_KEY_PEM",
        }
        assert injected["REDIS_LOCKOUT_URL"] == injected["REDIS_URL"]
        assert len(set(injected.values())) == 8
        assert all(value.endswith(":::" + "1" * 32) for value in injected.values())
        environment = {
            entry["name"]: entry["value"] for entry in definition["environment"]
        }
        assert environment["MAILER_DSN"] == "ses+api://default?region=eu-central-1"
        assert (
            environment["MAIL_SENDER"]
            == contract["workload"]["external"]["mail"]["sender"]
        )
        assert environment["SOCIAL_OAUTH_ENABLED"] == "false"
        assert environment["OAUTH_ENCRYPTION_KEY_TYPE"] == "plain"
        assert not any(
            key.startswith(
                (
                    "OAUTH_GITHUB_",
                    "OAUTH_GOOGLE_",
                    "OAUTH_FACEBOOK_",
                    "OAUTH_TWITTER_",
                    "AWS_SQS_KEY",
                    "AWS_SQS_SECRET",
                )
            )
            for key in environment
        )
    assert not any(row["type"].startswith("aws:iam/") for row in rows.values())


def test_generators_are_pinned_secret_protected_and_release_independent(tmp_path):
    before, after = graph(tmp_path), graph(tmp_path)
    generators = {
        name: row
        for name, row in before["registrations"].items()
        if row["type"].startswith(("random:", "tls:"))
    }
    assert len(generators) == 7
    assert generators == {name: after["registrations"][name] for name in generators}
    for row in generators.values():
        assert row["protect"] and row["additional_secret_outputs"]
        assert row["version"] == (
            module.TLS_VERSION
            if row["type"].startswith("tls:")
            else module.RANDOM_VERSION
        )
        assert "keepers" not in row["inputs"]
    assert (
        generators["runtime-two_factor_encryption_key-material"]["inputs"]["length"]
        == 32
    )
    assert generators["runtime-oauth-key"]["inputs"] == {
        "algorithm": "RSA",
        "rsaBits": 4096,
    }


def test_partial_and_duplicate_derived_inventory_fail_closed():
    resource = object.__new__(module.RuntimeSecrets)
    resource.secret_arns = {}
    resource.references = {
        purpose: {}
        for purpose in [
            *module.ENVIRONMENT_NAMES,
            "document_db_password",
            "redis_auth_token",
        ]
    }
    with pytest.raises(ValueError, match="incomplete"):
        resource.complete()
    with pytest.raises(ValueError, match="invalid or duplicated"):
        resource.persist_url("app_secret", "synthetic")
    resource.secret_arns["redis_url"] = "synthetic-arn"
    with pytest.raises(ValueError, match="invalid or duplicated"):
        resource.persist_url("redis_url", "synthetic")


@pytest.mark.parametrize("value", [None, 1, "true"])
def test_generated_resolver_option_is_strict_python_boolean(value):
    with pytest.raises(ValueError, match="must be a boolean"):
        resolve_stack_settings(None, generated_secrets=value)


def _metadata():
    return SimpleNamespace(
        environment_name="dev",
        service_name_value="user-service-infrastructure",
        owner="team-user-service",
        cost_center="core",
    )


def test_generated_resolver_rejects_preview_mode():
    with mocked_pulumi_context({"deploymentMode": "preview"}):
        with pytest.raises(ValueError, match="require managed deployment mode"):
            resolve_stack_settings(_metadata(), generated_secrets=True)


def test_config_flag_cannot_select_generated_secret_mode():
    config = {
        "deploymentMode": "managed",
        "generatedSecrets": True,
        "executionRoleArn": CENTRAL_EXECUTION_ROLE,
        "taskRoleArn": CENTRAL_TASK_ROLE,
        "accessLogsBucketName": "synthetic-access-logs",
    }
    with mocked_pulumi_context(
        config,
        aws_config_values={"allowedAccountIds": ["123456789012"]},
        project_name="user-service-infrastructure",
    ):
        with pytest.raises(ValueError, match="documentDbPassword must be configured"):
            resolve_stack_settings(_metadata())


@pytest.mark.parametrize("plane", [DataPlane, ComputePlane])
def test_legacy_planes_reject_missing_material_before_registration(monkeypatch, plane):
    model = SimpleNamespace(
        is_managed=True,
        secrets=None,
        environment="dev",
        runtime=SimpleNamespace(
            execution_role_arn=CENTRAL_EXECUTION_ROLE,
            task_role_arn=CENTRAL_TASK_ROLE,
            app_env="prod",
        ),
        queues=SimpleNamespace(health_check="health-check-queue"),
    )
    monkeypatch.setattr(
        module.pulumi.ComponentResource,
        "__init__",
        lambda *a, **kw: pytest.fail("registered before validation"),
    )
    arguments = {"settings": model, "network": None}
    if plane is ComputePlane:
        arguments.update({"data": None, "messaging": None})
    with mocked_pulumi_context(
        aws_config_values={"allowedAccountIds": ["123456789012"]},
        project_name="user-service-infrastructure",
    ):
        with pytest.raises(ValueError, match="requires application secrets"):
            plane("legacy", **arguments)


def _hardened_contract():
    return json.loads(
        (
            ROOT / "tests/fixtures/poc-contract/workload-hardened.synthetic.json"
        ).read_text()
    )


def test_hardened_descriptor_reports_only_seeded_declarations(contract):
    assert module.RuntimeSecretsDescriptor(contract).hardened is False
    descriptor = module.RuntimeSecretsDescriptor(_hardened_contract())
    assert descriptor.hardened is True
    assert set(descriptor.references) == {
        "app_secret",
        "oauth_encryption_key",
        "oauth_passphrase",
        "two_factor_encryption_key",
        "oauth_private_key",
        "oauth_public_key",
    }


def test_v8_hardened_secret_types_are_read_by_metadata_only(tmp_path):
    from poc_provider_runtime import PINS

    assert {pin.name: pin.version for pin in PINS}["aws"] == V8_PROVIDER_VERSION
    receipt = graph(tmp_path, "hardened")
    assert receipt["error"] is None
    managed = {
        row["type"]
        for row in receipt["registrations"].values()
        if row["type"].startswith("aws:secretsmanager/")
    }
    assert managed and managed <= V8_METADATA_READ_TYPES


def test_hardened_projection_renders_seeded_metadata_and_no_secret_material(tmp_path):
    baseline, receipt = graph(tmp_path, "registry"), graph(tmp_path, "hardened")
    assert baseline["error"] is receipt["error"] is None
    rows = receipt["registrations"]
    assert {name: rows[name] for name in baseline["registrations"]} == baseline[
        "registrations"
    ]
    types = [row["type"] for row in rows.values()]
    assert not [kind for kind in types if kind.startswith(SECRET_MATERIAL)]
    assert not [kind for kind in types if kind.startswith("aws:iam/")]
    assert "aws:lambda/function:Function" not in types
    declarations = _hardened_contract()["workload"]["secret_lifecycle"]["references"]
    secrets = {
        name: row
        for name, row in rows.items()
        if row["type"] == "aws:secretsmanager/secret:Secret"
    }
    assert set(secrets) == {f"runtime-{purpose}" for purpose in declarations}
    for purpose, declaration in declarations.items():
        row = secrets[f"runtime-{purpose}"]
        assert row["protect"] and row["additional_secret_outputs"] == []
        assert row["inputs"]["name"] == declaration["name"]
        assert row["inputs"]["kmsKeyId"] == declaration["kms_key_arn"]
        assert set(row["inputs"]) == {"name", "kmsKeyId", "tags"}
    component = rows["runtime-secrets"]["urn"]
    assert receipt["outputs"][component]["versionIds"] == {}
    assert set(receipt["outputs"][component]["secretArns"]) == set(declarations)
    assert {"network", "messaging"} <= set(rows)
    assert not {"data", "compute"} & set(rows)


def test_pre_hardening_projection_keeps_its_generators_until_s4_10(tmp_path):
    rows = graph(tmp_path, "bridge")["registrations"]
    types = [row["type"] for row in rows.values()]
    assert len([kind for kind in types if kind.startswith(("random:", "tls:"))]) == 7
    assert types.count("aws:secretsmanager/secretVersion:SecretVersion") == 10
    assert {"data", "compute"} <= set(rows)


@pytest.mark.parametrize(
    "mutation",
    [
        "random-password",
        "secret-version",
        # N1 (F1): outside the runtime-secrets component, the stack-wide guard
        # still refuses material parented to the stack or to no resource.
        "stack:random-password",
        "root:random-password",
        "stack:secret-version",
        "root:secret-version",
    ],
)
def test_readding_secret_material_to_the_hardened_graph_fails(tmp_path, mutation):
    receipt = graph(tmp_path, "hardened", mutation)
    assert receipt["error"] == "Hardened workload graph must not hold secret material"
    assert not [
        name
        for name, row in receipt["registrations"].items()
        if row["type"].startswith(SECRET_MATERIAL)
    ]


@pytest.mark.parametrize("owner", ["", "stack:", "root:"])
def test_unlisted_type_in_the_hardened_graph_fails(tmp_path, owner):
    """F3: the hardened graph is a closed allowlist, not a denylist."""
    receipt = graph(tmp_path, "hardened", f"{owner}ssm-parameter")
    assert receipt["error"] == "Hardened workload graph holds an unreviewed type"
    assert "aws:ssm/parameter:Parameter" not in {
        row["type"] for row in receipt["registrations"].values()
    }


def test_hardened_inventory_has_no_version_references_or_derived_secrets():
    resource = object.__new__(module.RuntimeSecrets)
    resource.references = _hardened_contract()["workload"]["secret_lifecycle"][
        "references"
    ]
    resource.secret_arns = dict.fromkeys(resource.references, "synthetic-arn")
    resource.version_ids = {}
    with pytest.raises(ValueError, match="incomplete"):
        resource.ecs_secrets()
    for purpose in sorted(module.DERIVED):
        with pytest.raises(ValueError, match="invalid or duplicated"):
            resource.persist_url(purpose, "synthetic")


def test_hardened_guard_is_registered_stack_wide_with_the_engine(tmp_path):
    """F1: the engine transform, which reaches packaged components, is present."""
    assert graph(tmp_path, "hardened")["engine_transforms"] == 1
    assert graph(tmp_path, "bridge")["engine_transforms"] == 0


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("random:index/randomPassword:RandomPassword", "secret material"),
        ("tls:index/privateKey:PrivateKey", "secret material"),
        ("aws:secretsmanager/secretVersion:SecretVersion", "secret material"),
        ("aws:ssm/parameter:Parameter", "unreviewed type"),
        ("awsx:ec2:Vpc", "unreviewed type"),
        ("pulumi:providers:random", "unreviewed type"),
    ],
)
def test_engine_transform_refuses_packaged_component_children(kind, message):
    """A packaged component's child reaches only the engine-level transform."""
    from app.workload_phase import _reject_secret_material

    import pulumi

    args = pulumi.ResourceTransformArgs(
        custom=True, type_=kind, name="child", props={}, opts=pulumi.ResourceOptions()
    )
    with pytest.raises(ValueError, match=message):
        _reject_secret_material(args)


def test_hardened_allowlist_is_the_rendered_graph_plus_reviewed_taggable_types(
    tmp_path,
):
    """F3: every allowlisted untagged or component type is rendered today."""
    from app.workload_phase import (
        HARDENED_COMPONENT_TYPES,
        HARDENED_TYPES,
        HARDENED_UNTAGGED_TYPES,
        TAGGABLE_TYPES,
    )

    rendered = {
        row["type"] for row in graph(tmp_path, "hardened")["registrations"].values()
    } - {"pulumi:pulumi:Stack"}
    assert rendered <= HARDENED_TYPES
    assert HARDENED_UNTAGGED_TYPES | HARDENED_COMPONENT_TYPES <= rendered
    assert not HARDENED_UNTAGGED_TYPES & TAGGABLE_TYPES
    assert not [kind for kind in HARDENED_TYPES if kind.startswith(SECRET_MATERIAL)]


def test_secret_lifecycle_spec_records_the_hardened_contract():
    """F-4: the hardened section names its markers and the guard's real reach."""
    text = (ROOT / "specs/poc/secret-lifecycle.md").read_text()
    section = text[text.index("## Hardened (seeded) declarations") :]
    for marker in (
        "rotation-seed",
        "validate_seed_input",
        f"pulumi-aws {V8_PROVIDER_VERSION}",
        "register_stack_transformation",
        "register_resource_transform",
        "runtime CMK",
        "re.fullmatch",
    ):
        assert marker in section, marker
    assert "a transformation fails the program" not in section
