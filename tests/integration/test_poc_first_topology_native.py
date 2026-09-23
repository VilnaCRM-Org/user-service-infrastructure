"""Native engine/SDK plan shapes over test-only loopback provider transports.

These providers do not implement AWS behavior or capabilities. They allow the
actual installed workload program to register its complete graph without AWS.
"""

import importlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import grpc
import pytest
import yaml
from google.protobuf.empty_pb2 import Empty
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from pulumi.runtime.proto import plugin_pb2, provider_pb2, provider_pb2_grpc

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests/unit")]
from test_environment_component import _resource_mock_outputs  # noqa: E402
from test_poc_registry_phase_entrypoint import source  # noqa: E402
from test_poc_workload_phase import _generated_outputs  # noqa: E402
from test_poc_workload_phase_entrypoint import fixture  # noqa: E402

gate = importlib.import_module("poc_workload_topology")
bridge = importlib.import_module("poc_workload_phase_entrypoint")


class LocalProvider(provider_pb2_grpc.ResourceProviderServicer):
    """Test-only provider: deterministic fixtures and no network/cloud operations."""

    def __init__(self, version):
        self.version = version

    def GetPluginInfo(self, request, context):
        return plugin_pb2.PluginInfo(version=self.version)

    def Handshake(self, request, context):
        return provider_pb2.ProviderHandshakeResponse()

    def Attach(self, request, context):
        return Empty()

    def CheckConfig(self, request, context):
        return provider_pb2.CheckResponse(inputs=request.news)

    Check = CheckConfig

    def DiffConfig(self, request, context):
        return provider_pb2.DiffResponse(changes=provider_pb2.DiffResponse.DIFF_NONE)

    Diff = DiffConfig

    def Configure(self, request, context):
        return provider_pb2.ConfigureResponse(acceptSecrets=True, supportsPreview=True)

    def Cancel(self, request, context):
        return Empty()

    def Create(self, request, context):
        kind = request.urn.split("::")[-2].rsplit("$", 1)[-1]
        name = request.urn.rsplit("::", 1)[-1]
        inputs = MessageToDict(request.properties)
        args = SimpleNamespace(typ=kind, name=name, inputs=inputs)
        identifier, outputs = _resource_mock_outputs(
            args, dict(inputs), resource_id=name + "-id"
        )
        outputs = _generated_outputs(args, outputs)
        if kind == gate.registry.ECR:
            identifier = inputs["name"]
            outputs.update(
                arn=f"arn:aws:ecr:eu-central-1:891377212104:repository/{identifier}",
                repositoryUrl=f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{identifier}",
                registryId="891377212104",
            )
            outputs.pop("id", None)
        if kind == gate.registry.mail.SES:
            identifier = gate.registry.mail.DOMAIN
            outputs["arn"] = gate.registry.mail.ARN
            outputs.pop("id", None)
        if kind == gate.registry.mail.DNS:
            identifier = f"{inputs['zoneId']}_{inputs['name']}_CNAME"
            outputs["fqdn"] = inputs["name"]
            outputs.pop("id", None)
        return provider_pb2.CreateResponse(
            id=identifier, properties=ParseDict(outputs, Struct())
        )


def test_actual_workload_program_native_first_plan(tmp_path, ensure_pulumi_cli):
    servers, addresses = [], []
    for package, version in (("aws", "7.23.0"), ("random", "4.19.2"), ("tls", "5.3.1")):
        server = grpc.server(ThreadPoolExecutor(max_workers=16))
        provider_pb2_grpc.add_ResourceProviderServicer_to_server(
            LocalProvider(version), server
        )
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        servers.append(server)
        addresses.append(f"{package}:{port}")
    try:
        _run_native(tmp_path, addresses)
    finally:
        for server in servers:
            server.stop(0).wait()


def _run_native(tmp_path, addresses):
    env = {key: os.environ[key] for key in ("HOME", "PATH") if key in os.environ}
    backend = tmp_path / "backend"
    backend.mkdir()
    env.update(
        PULUMI_BACKEND_URL=backend.as_uri(),
        PULUMI_HOME=str(tmp_path / "home"),
        PULUMI_CONFIG_PASSPHRASE="synthetic-local-test-only",
        PULUMI_SKIP_UPDATE_CHECK="true",
        PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION="true",
        PULUMI_DEBUG_PROVIDERS=",".join(addresses),
        PULUMI_PYTHON_CMD=sys.executable,
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / "Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime:\n  name: python\n"
        f"  options:\n    virtualenv: {json.dumps(sys.prefix)}\n"
    )
    config = {
        "environment": "test",
        "serviceName": "user-service-infrastructure",
        "owner": "team-user-service",
        "costCenter": "core",
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": "s3://pulumi-user-service-infrastructure-test-state",
        "pulumiSecretsProvider": "awskms://alias/pulumi-user-service-infrastructure-test-secrets?region=eu-central-1",
    }
    aws = {
        "region": "eu-central-1",
        "allowedAccountIds": '["891377212104"]',
        "skipCredentialsValidation": "false",
        "skipRegionValidation": "false",
        "skipRequestingAccountId": "false",
    }
    contract, images = fixture()
    projection = bridge.project_workload_phase(source(contract), contract, images)
    values = {
        **{
            f"user-service-infrastructure:{key}": value for key, value in config.items()
        },
        **{f"aws:{key}": value for key, value in aws.items()},
        **bridge.workload_configuration(projection),
    }
    prelude = (
        "import sys,json\n"
        f"sys.path[:0] = {str([str(ROOT / 'scripts'), str(ROOT / 'pulumi')])}\n"
        "from pulumi.runtime import set_all_config\n"
        f"set_all_config(json.loads({json.dumps(values)!r}))\n"
    )
    main = project / "__main__.py"
    main.write_text(
        prelude
        + "from poc_registry_phase_entrypoint import (\n"
        + " RegistryPhaseProjection,run_registry_phase)\n"
        + f"run_registry_phase(RegistryPhaseProjection({gate.registry.REGISTRIES!r}))\n"
    )

    def cli(*args):
        result = subprocess.run(
            ["pulumi", "-C", str(project), *args],
            env=env,
            capture_output=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, (
            f"Local Pulumi {args[0]} failed: {result.stdout.decode()[-2000:]} "
            f"{result.stderr.decode()[-2000:]}"
        )
        return result.stdout

    if cli("version").strip() != b"v3.223.0":
        pytest.skip("Saved-plan protocol requires Pulumi v3.223.0")
    cli(
        "stack", "init", "test", "--secrets-provider", "passphrase", "--non-interactive"
    )
    configuration = project / "Pulumi.test.yaml"
    settings = yaml.safe_load(configuration.read_text())
    settings["config"] = values
    configuration.write_text(yaml.safe_dump(settings))
    cli("preview", "--save-plan", "registry.plan", "--json", "--non-interactive")
    cli("up", "--plan", "registry.plan", "--skip-preview", "--yes", "--non-interactive")
    prior = json.loads(cli("stack", "export"))["deployment"]["resources"]
    main.write_text(
        prelude
        + "from poc_phase_admission import SourceAdmission\n"
        + "from poc_workload_phase_entrypoint import (\n"
        + " project_workload_phase,run_workload_phase)\n"
        + "run_workload_phase(project_workload_phase(\n"
        + f"SourceAdmission(**{source(contract).__dict__!r}),\n"
        + f"json.loads({json.dumps(contract)!r}),\n"
        + f"json.loads({json.dumps(images)!r})))\n"
    )
    preview = json.loads(
        cli("preview", "--save-plan", "workload.plan", "--json", "--non-interactive")
    )
    arguments = {
        "saved_plan": json.loads((project / "workload.plan").read_bytes()),
        "prior_resources": prior,
        "projection": projection,
    }
    gate.validate_first_workload_topology(preview, **arguments)
    with pytest.raises(
        ValueError, match="native-capability-and-input-admission-required"
    ):
        gate.admit_first_workload_plan(preview, **arguments)
