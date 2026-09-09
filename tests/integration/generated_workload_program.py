"""Native Automation test program; no deployment or admission entrypoint."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

source_root = Path((Path(__file__).parent / "source-root.txt").read_text())
sys.path[:0] = [str(source_root / "pulumi"), str(source_root / "scripts")]

from app.compute import ComputePlane  # noqa: E402
from app.environment import resolve_stack_settings  # noqa: E402
from app.registry_phase import RegistryPhaseStack  # noqa: E402
from app.runtime_secrets import RuntimeSecrets, RuntimeSecretsDescriptor  # noqa: E402
from app.workload_phase import WorkloadPhaseStack  # noqa: E402

import pulumi  # noqa: E402

root = Path(__file__).parent
scenario = json.loads((root / "scenario.json").read_text())
contract = json.loads((root / "contract.json").read_text())
registries = {
    kind: {key: row[key] for key in ("logical_name", "name")}
    for kind, row in contract["registries"].items()
}
metadata = SimpleNamespace(
    environment_name="test",
    service_name_value="user-service-infrastructure",
    owner="team-user-service",
    cost_center="core",
)
mode = scenario["mode"]
if mode == "registry":
    RegistryPhaseStack(registries=registries)
else:
    settings = resolve_stack_settings(
        metadata, generated_secrets="true" if mode == "invalid-flag" else True
    )
    assert settings.secrets is None
    descriptor = RuntimeSecretsDescriptor(contract)
    if mode == "descriptor-type":
        RuntimeSecrets("invalid", descriptor=None)
    if mode == "descriptor-tampered":
        descriptor._contract["workload"]["secret_lifecycle"]["references"].clear()
        RuntimeSecrets("invalid", descriptor=descriptor)
    if mode == "descriptor-context":
        pulumi.runtime.set_config("aws:allowedAccountIds", '["999999999999"]')
        RuntimeSecrets("invalid", descriptor=descriptor)
    if mode == "legacy-secret-guard":
        ComputePlane(
            "invalid", settings=settings, network=None, data=None, messaging=None
        )
    if mode == "settings-mode":
        settings = replace(settings, deployment_mode="preview")
    if mode == "settings-target":
        settings = replace(settings, region="us-east-1")
    if mode == "settings-tags":
        settings = replace(
            settings, default_tags={**settings.default_tags, "Owner": "foreign"}
        )
    if mode == "descriptor-target":
        settings = replace(
            settings, runtime=replace(settings.runtime, mail_sender="other@example.com")
        )
    if mode == "workload-descriptor-type":
        descriptor = None
    WorkloadPhaseStack(settings=settings, registries=registries, secrets=descriptor)
