"""Native offline provider preview of generated secrets and the preserved owner."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pulumi.automation as auto
import pytest
from pulumi.automation.errors import RuntimeError as AutomationRuntimeError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def verified_plugins(tmp_path_factory):
    """Install only pinned verified providers; never use ambient acquisitions."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    providers = importlib.import_module("poc_provider_runtime")
    root = tmp_path_factory.mktemp("verified-workload-providers")
    shutil.copyfile(PROJECT_ROOT / "uv.lock", root / "uv.lock")
    providers._sdk_versions(root)
    home = providers.plugin_home(root)
    (home / "plugins").mkdir(parents=True)
    for pin in providers.PINS:
        archive = root / f"{pin.name}.tar.gz"
        with urllib.request.urlopen(pin.url, timeout=120) as source:
            with archive.open("wb") as destination:
                shutil.copyfileobj(source, destination)
        assert providers._digest(archive) == pin.archive_sha256
        providers._extract_binary(archive, home, pin)
        archive.unlink()
    return providers.verify_runtime(root)


@pytest.fixture
def local_sts():
    """Serve local identity lookup; deny IAM fallback and every egress attempt."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            pass

        def do_CONNECT(self):
            requests.append("forbidden-egress")
            self.send_error(403)

        def do_POST(self):
            payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            action = parse_qs(payload.decode()).get("Action", [""])[0]
            requests.append(action)
            if self.path != "/":
                requests.append("forbidden-egress")
            # AWS first probes IAM GetUser. Deny that local request explicitly;
            # the pinned provider then resolves the account through local STS.
            if self.path != "/" or action != "GetCallerIdentity":
                self.send_error(403)
                return
            value = (
                '<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">'
                "<GetCallerIdentityResult><Arn>arn:aws:iam::891377212104:user/synthetic</Arn>"
                "<UserId>synthetic</UserId><Account>891377212104</Account>"
                "</GetCallerIdentityResult><ResponseMetadata><RequestId>synthetic</RequestId>"
                "</ResponseMetadata></GetCallerIdentityResponse>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(value)))
            self.end_headers()
            self.wfile.write(value)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
        assert set(requests) <= {"GetCallerIdentity", "GetUser"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _bound_contract(name, roles):
    """Bind a synthetic contract to the fixed TEST roles and registries."""
    contract = json.loads(
        (
            PROJECT_ROOT / f"tests/fixtures/poc-contract/{name}.synthetic.json"
        ).read_text()
    )
    contract["workload"]["central"].update(roles)
    for kind in ("web", "worker"):
        row = contract["registries"][kind]
        row["logical_name"] = f"user-service-{kind}-repository"
        row["name"] = f"user-service-test-{kind}"
        row["arn"] = f"arn:aws:ecr:eu-central-1:891377212104:repository/{row['name']}"
        row["uri"] = f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{row['name']}"
        contract["workload"]["release"][kind]["repository_uri"] = row["uri"]
    return contract


@pytest.fixture
def native_stack(tmp_path, verified_plugins, local_sts):
    """Prepare fixed TEST identities on an isolated file backend with fake creds."""
    work = tmp_path / "native-workload"
    work.mkdir()
    shutil.copyfile(PROJECT_ROOT / "pulumi/Pulumi.yaml", work / "Pulumi.yaml")
    shutil.copyfile(
        Path(__file__).with_name("generated_workload_program.py"), work / "__main__.py"
    )
    (work / "source-root.txt").write_text(str(PROJECT_ROOT))
    roles = {
        "execution_role_arn": (
            "arn:aws:iam::891377212104:role/"
            "user-service-infrastructure-test-EcsExecution"
        ),
        "task_role_arn": (
            "arn:aws:iam::891377212104:role/user-service-infrastructure-test-EcsTask"
        ),
    }
    for name, target in (
        ("workload", "contract.json"),
        ("workload-hardened", "hardened-contract.json"),
    ):
        contract = _bound_contract(name, roles)
        (work / target).write_text(json.dumps(contract))
    (work / "scenario.json").write_text('{"mode":"workload"}')
    backend = tmp_path / "backend"
    backend.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "COVERAGE_FILE",
            "COVERAGE_PROCESS_START",
            "COVERAGE_RCFILE",
            "PULUMI_PYTHON_CMD",
        }
    }
    env.update(
        {
            "PULUMI_HOME": str(verified_plugins),
            "PULUMI_BACKEND_URL": backend.as_uri(),
            "PULUMI_CONFIG_PASSPHRASE": "synthetic-integration-passphrase",
            "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION": "true",
            "PULUMI_IGNORE_AMBIENT_PLUGINS": "true",
            "PULUMI_SKIP_UPDATE_CHECK": "true",
            "HTTP_PROXY": local_sts[0],
            "HTTPS_PROXY": local_sts[0],
            "NO_PROXY": "127.0.0.1",
            "AWS_ENDPOINT_URL_STS": local_sts[0],
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_ACCESS_KEY_ID": "synthetic-integration",
            "AWS_SECRET_ACCESS_KEY": "synthetic-integration",
            "AWS_SESSION_TOKEN": "",
            "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "no-credentials"),
            "AWS_CONFIG_FILE": str(tmp_path / "no-config"),
        }
    )
    stack = auto.create_stack(
        stack_name="test",
        work_dir=str(work),
        opts=auto.LocalWorkspaceOptions(
            work_dir=str(work), pulumi_home=str(verified_plugins), env_vars=env
        ),
    )
    config = {
        "environment": "test",
        "serviceName": "user-service-infrastructure",
        "owner": "team-user-service",
        "costCenter": "core",
        "deploymentMode": "managed",
        "aws:region": "eu-central-1",
        "aws:allowedAccountIds": '["891377212104"]',
        "aws:skipCredentialsValidation": "true",
        "aws:skipRegionValidation": "true",
        "aws:skipRequestingAccountId": "false",
        "aws:endpoints": json.dumps([{"sts": local_sts[0], "iam": local_sts[0]}]),
        "aws:skipMetadataApiCheck": "true",
        "executionRoleArn": roles["execution_role_arn"],
        "taskRoleArn": roles["task_role_arn"],
        "accessLogsBucketName": "synthetic-access-logs",
        "mailSender": contract["workload"]["external"]["mail"]["sender"],
        "webRepositoryName": "user-service-test-web",
        "workerRepositoryName": "user-service-test-worker",
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": "s3://pulumi-user-service-infrastructure-test-state",
        "pulumiSecretsProvider": "awskms://alias/pulumi-user-service-infrastructure-test-secrets?region=eu-central-1",
    }
    stack.set_all_config(
        {key: auto.ConfigValue(value=value) for key, value in config.items()}
    )
    try:
        yield stack, work
    finally:
        # No AWS resources are applied; remove only the empty local stack record.
        stack.workspace.remove_stack(stack.name)


def resources(events):
    return [
        event.resource_pre_event.metadata
        for event in events
        if event.resource_pre_event is not None
    ]


def test_native_generated_workload_preserves_registry_and_registers_secret_versions(
    native_stack,
    local_sts,
):
    stack, work = native_stack
    events = []
    (work / "scenario.json").write_text('{"mode":"registry"}')
    stack.preview(on_event=events.append)
    baseline = {row.urn: row for row in resources(events)}
    assert len(baseline) == 11
    events.clear()
    contract = json.loads((work / "contract.json").read_text())
    stack.set_config(
        "certificateArn",
        auto.ConfigValue(
            value=contract["workload"]["external"]["domain"]["certificate_arn"]
        ),
    )
    (work / "scenario.json").write_text('{"mode":"workload"}')
    result = stack.preview(on_event=events.append)
    assert result.change_summary
    actual = {row.urn: row for row in resources(events)}
    assert set(baseline) <= set(actual)
    for urn, row in baseline.items():
        assert vars(actual[urn].new) == vars(row.new)
    types = [row.type for row in actual.values()]
    assert types.count("aws:secretsmanager/secret:Secret") == 10
    assert types.count("aws:secretsmanager/secretVersion:SecretVersion") == 10
    assert types.count("random:index/randomBytes:RandomBytes") == 4
    assert types.count("random:index/randomPassword:RandomPassword") == 2
    assert types.count("tls:index/privateKey:PrivateKey") == 1
    assert types.count("aws:ecs/taskDefinition:TaskDefinition") == 2
    assert not any(kind.startswith("aws:iam/") for kind in types)
    assert local_sts[1] == ["GetUser", "GetCallerIdentity"] * 2


SECRET_MATERIAL = ("random:", "tls:", "aws:secretsmanager/secretVersion:SecretVersion")
# FR-34: no seed, rotation, secret policy, autoscaling or scheduled action.
STEP_TWO = (
    "aws:lambda/",
    "aws:appautoscaling/",
    "aws:secretsmanager/secretPolicy:",
    "aws:secretsmanager/secretRotation:",
)


def _hardened(stack, work, scenario=None):
    """Select the hardened composition; compute needs the admitted certificate."""
    contract = json.loads((work / "hardened-contract.json").read_text())
    stack.set_config(
        "certificateArn",
        auto.ConfigValue(
            value=contract["workload"]["external"]["domain"]["certificate_arn"]
        ),
    )
    (work / "scenario.json").write_text(
        json.dumps({"mode": "hardened-workload", **(scenario or {})})
    )


def test_native_hardened_workload_renders_no_secret_material(native_stack):
    """A workload_step projection previews the step-1 set (FR-09, FR-34)."""
    stack, work = native_stack
    events = []
    (work / "scenario.json").write_text('{"mode":"registry"}')
    stack.preview(on_event=events.append)
    baseline = {row.urn: row for row in resources(events)}
    events.clear()
    _hardened(stack, work)
    result = stack.preview(on_event=events.append)
    assert result.change_summary
    actual = {row.urn: row for row in resources(events)}
    assert set(baseline) <= set(actual)
    for urn, row in baseline.items():
        assert vars(actual[urn].new) == vars(row.new)
    types = [row.type for row in actual.values()]
    assert types.count("aws:secretsmanager/secret:Secret") == 6
    assert not [kind for kind in types if kind.startswith(SECRET_MATERIAL)]
    assert not [kind for kind in types if kind.startswith("aws:iam/")]
    assert not [kind for kind in types if kind.startswith(STEP_TWO)]
    assert "aws:lambda/function:Function" not in types
    assert not [kind for kind in types if kind.startswith("aws:elasticache/")]
    services = [row for row in actual.values() if row.type == "aws:ecs/service:Service"]
    assert [row.new.inputs["desiredCount"] for row in services] == [0, 0]
    assert any(
        row.urn.endswith("::user-service-bootstrap-job-sg") for row in actual.values()
    )


def test_native_hardened_data_plane_uses_the_managed_password(native_stack):
    """S1.2/S1.3: managed password on engine 5.0.0, no password input (F-10)."""
    stack, work = native_stack
    _hardened(stack, work)
    events = []
    stack.preview(on_event=events.append)
    rows = resources(events)
    assert not [row.type for row in rows if row.type.startswith(SECRET_MATERIAL)]
    (cluster,) = [row for row in rows if row.type == "aws:docdb/cluster:Cluster"]
    inputs = cluster.new.inputs
    assert inputs["manageMasterUserPassword"] is True
    assert inputs["engineVersion"] == "5.0.0"
    assert not [
        key
        for key in inputs
        if "password" in key.lower() and key != "manageMasterUserPassword"
    ]
    assert "masterUserSecretKmsKeyId" not in inputs


def test_native_hardened_workload_rejects_a_password_config_key(native_stack):
    """S1.2 F-07: the composed hardened stack refuses a secret password config."""
    stack, work = native_stack
    _hardened(stack, work)
    # F-02: a real password arrives as secret stack config, never plain.
    synthetic = "synthetic-documentdb-password-do-not-echo"
    stack.set_config(
        "documentDbPassword", auto.ConfigValue(value=synthetic, secret=True)
    )
    events = []
    with pytest.raises(AutomationRuntimeError) as failure:
        stack.preview(on_event=events.append)
    assert "documentDbPassword must not be configured" in str(failure.value)
    assert synthetic not in str(failure.value)
    # The refusal runs before the first workload registration.
    assert not [row for row in resources(events) if row.type.startswith("aws:")]


def test_native_hardened_workload_rejects_a_non_iam_engine(native_stack):
    """N (V-17): engine 4.0.0 fails the hardened program before DocumentDB."""
    stack, work = native_stack
    _hardened(stack, work)
    stack.set_config("documentDbEngineVersion", auto.ConfigValue(value="4.0.0"))
    events = []
    with pytest.raises(AutomationRuntimeError) as failure:
        stack.preview(on_event=events.append)
    assert "V-17" in str(failure.value)
    # F-04: the refusal runs before the first workload registration.
    assert not [row for row in resources(events) if row.type.startswith("aws:")]


@pytest.mark.parametrize(
    ("addition", "message", "kind"),
    [
        ("runtime-secrets:random-password", "must not hold secret material", None),
        # N1 (F1): outside the component, the stack-wide guard still applies.
        ("stack:random-password", "must not hold secret material", None),
        ("root:random-password", "must not hold secret material", None),
        ("stack:secret-version", "must not hold secret material", None),
        ("root:secret-version", "must not hold secret material", None),
        # F3: a type outside the closed allowlist fails too.
        ("root:ssm-parameter", "unreviewed type", "aws:ssm/parameter:Parameter"),
        # N1: the allowlisted DocumentDB cluster refuses a master password,
        # whatever its parent (S1.3 property check).
        ("stack:docdb-cluster", "unreviewed property", None),
        ("root:docdb-cluster", "unreviewed property", None),
        # N (V-17): an elastic cluster fails.
        (
            "root:docdb-elastic-cluster",
            "instance-based",
            "aws:docdb/elasticCluster:ElasticCluster",
        ),
        # B (FR-34): a step-2 type fails at step 1.
        (
            "stack:secret-policy",
            "step-2 resource",
            "aws:secretsmanager/secretPolicy:SecretPolicy",
        ),
        # N1: a BYODKIM private key fails the SES identity property check.
        ("root:byodkim-identity", "unreviewed property", None),
        ("stack:byodkim-identity", "unreviewed property", None),
        # F-01 (a): the engine transform refuses a secret-marked definition.
        ("root:secret-task", "unreviewed property", None),
        # F-01 (b): PascalCase container keys fail.
        ("root:pascal-task", "unreviewed property", None),
        # F-02: an OIDC listener action carries a client secret.
        ("root:oidc-listener", "unreviewed property", None),
        # F-03: an inline policy bypasses the step-1 SecretPolicy refusal.
        ("stack:policy-secret", "unreviewed property", None),
    ],
)
def test_native_hardened_workload_rejects_readded_secret_material(
    native_stack, addition, message, kind
):
    stack, work = native_stack
    _hardened(stack, work, {"addition": addition})
    events = []
    with pytest.raises(AutomationRuntimeError) as failure:
        stack.preview(on_event=events.append)
    assert message in str(failure.value)
    assert not [
        row
        for row in resources(events)
        if row.type.startswith(SECRET_MATERIAL)
        or row.type == kind
        or "::fixture-" in row.urn
    ]


def test_native_hardened_workload_refuses_provider_function_calls(
    native_stack, local_sts
):
    """N2: the engine invoke guard, not the network, fails the provider read."""
    stack, work = native_stack
    _hardened(stack, work, {"addition": "root:random-password-invoke"})
    with pytest.raises(AutomationRuntimeError) as failure:
        stack.preview()
    assert "must not call a provider function" in str(failure.value)
    # The provider never ran the invoke: no Secrets Manager request and no
    # egress attempt reached the local endpoint that records every request.
    assert set(local_sts[1]) <= {"GetCallerIdentity", "GetUser"}


def test_native_legacy_workload_program_registers_managed_planes(native_stack):
    """Cover the legacy managed topology without widening the installed entrypoint."""
    stack, work = native_stack
    (work / "scenario.json").write_text('{"mode":"legacy-workload"}')
    events = []
    result = stack.preview(on_event=events.append)

    assert result.change_summary
    types = [row.type for row in resources(events)]
    assert "user-service-infrastructure:stack:UserService" in types
    assert "user-service-infrastructure:network:Plane" in types
    assert "user-service-infrastructure:data:Plane" in types
    assert "user-service-infrastructure:messaging:Plane" in types
    assert "user-service-infrastructure:compute:Plane" in types
    assert types.count("aws:ec2/vpc:Vpc") == 1
    # Four work/health queues plus three dead-letter queues.
    assert types.count("aws:sqs/queue:Queue") == 7
    assert types.count("aws:docdb/clusterParameterGroup:ClusterParameterGroup") == 1
    assert types.count("aws:ecs/service:Service") == 2
    assert not any(kind.startswith("aws:iam/") for kind in types)


def test_native_legacy_workload_program_uses_preview_placeholders(native_stack):
    """Exercise legacy preview placeholders without registering AWS resources."""
    stack, work = native_stack
    stack.set_config("deploymentMode", auto.ConfigValue(value="preview"))
    stack.remove_config("accessLogsBucketName")
    (work / "scenario.json").write_text('{"mode":"legacy-workload"}')
    events = []
    result = stack.preview(on_event=events.append)

    assert result.change_summary
    types = [row.type for row in resources(events)]
    assert set(types) == {
        "pulumi:pulumi:Stack",
        "user-service-infrastructure:stack:UserService",
        "user-service-infrastructure:core:EnvironmentSettings",
        "user-service-infrastructure:network:Plane",
        "user-service-infrastructure:data:Plane",
        "user-service-infrastructure:messaging:Plane",
        "user-service-infrastructure:compute:Plane",
    }
    assert not any(kind.startswith("aws:") for kind in types)


@pytest.mark.parametrize(
    "mode,message",
    [
        ("invalid-flag", "generated_secrets must be a boolean"),
        ("preview-mode", "Generated secrets require managed deployment mode"),
        ("descriptor-type", "validated descriptor"),
        ("descriptor-tampered", "poc-test-v1 schema"),
        ("descriptor-context", "protected deployment context"),
        ("legacy-secret-guard", "Legacy managed workload requires application secrets"),
        ("settings-mode", "explicit managed settings"),
        ("settings-target", "differs from the TEST registry target"),
        ("settings-tags", "preserved baseline metadata"),
        ("descriptor-target", "differs from workload target"),
        ("workload-descriptor-type", "secret declaration"),
    ],
)
def test_invalid_generated_inputs_fail_before_native_resource_registration(
    native_stack, mode, message
):
    stack, work = native_stack
    (work / "scenario.json").write_text(json.dumps({"mode": mode}))
    if mode == "preview-mode":
        stack.set_config("deploymentMode", auto.ConfigValue(value="preview"))
    events = []
    with pytest.raises(AutomationRuntimeError) as failure:
        stack.preview(on_event=events.append)
    assert message in str(failure.value)
    assert all(row.type == "pulumi:pulumi:Stack" for row in resources(events))
