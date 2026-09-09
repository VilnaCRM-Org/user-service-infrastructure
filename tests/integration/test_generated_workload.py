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
    contract = json.loads(
        (
            PROJECT_ROOT / "tests/fixtures/poc-contract/workload.synthetic.json"
        ).read_text()
    )
    roles = {
        "execution_role_arn": (
            "arn:aws:iam::891377212104:role/"
            "user-service-infrastructure-test-EcsExecution"
        ),
        "task_role_arn": (
            "arn:aws:iam::891377212104:role/user-service-infrastructure-test-EcsTask"
        ),
    }
    contract["workload"]["central"].update(roles)
    for kind in ("web", "worker"):
        row = contract["registries"][kind]
        row["logical_name"] = f"user-service-{kind}-repository"
        row["name"] = f"user-service-test-{kind}"
        row["arn"] = f"arn:aws:ecr:eu-central-1:891377212104:repository/{row['name']}"
        row["uri"] = f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{row['name']}"
        contract["workload"]["release"][kind]["repository_uri"] = row["uri"]
    (work / "contract.json").write_text(json.dumps(contract))
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
    assert len(baseline) == 7
    events.clear()
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
