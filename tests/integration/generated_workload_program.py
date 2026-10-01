"""Native Automation test program; no deployment or admission entrypoint."""

import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

source_root = Path((Path(__file__).parent / "source-root.txt").read_text())
sys.path[:0] = [str(source_root / "pulumi"), str(source_root / "scripts")]

# This test-only program adds the source tree after interpreter startup, so its
# sitecustomize module cannot start configured subprocess coverage on its own.
if os.environ.get("COVERAGE_PROCESS_START"):
    import coverage

    coverage.process_startup()

from app.compute import ComputePlane  # noqa: E402
from app.data import DataPlane  # noqa: E402
from app.environment import resolve_stack_settings  # noqa: E402
from app.network import NetworkPlane  # noqa: E402
from app.registry_phase import RegistryPhaseStack  # noqa: E402
from app.runtime_secrets import RuntimeSecrets, RuntimeSecretsDescriptor  # noqa: E402
from app.stack import UserServiceStack  # noqa: E402
from app.workload_phase import WorkloadPhaseStack  # noqa: E402

import pulumi  # noqa: E402

root = Path(__file__).parent
scenario = json.loads((root / "scenario.json").read_text())
mode = scenario["mode"]
hardened = mode.startswith("hardened")
contract = json.loads(
    (root / ("hardened-contract.json" if hardened else "contract.json")).read_text()
)
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
if mode == "registry":
    RegistryPhaseStack(registries=registries)
elif mode.startswith("hardened-data"):
    # S1.2 seam, built outside WorkloadPhaseStack and so outside its stack-wide
    # closed type guard: S1.3 composes the data plane into the hardened graph
    # and widens that allowlist then. S1.2 does not widen it.
    settings = resolve_stack_settings(metadata, generated_secrets=True)
    if mode == "hardened-data-password":
        pulumi.runtime.set_config(
            "user-service-infrastructure:documentDbPassword", "synthetic"
        )
    runtime_secrets = RuntimeSecrets(
        "runtime-secrets", descriptor=RuntimeSecretsDescriptor(contract)
    )
    network = NetworkPlane("network", settings=settings, private_gateway=True)
    DataPlane(
        "data",
        settings=settings,
        network=network,
        runtime_secrets=runtime_secrets,
    )
elif hardened:
    # A workload_step contract renders the hardened composition (AD-25).
    workload = WorkloadPhaseStack(
        settings=resolve_stack_settings(metadata, generated_secrets=True),
        registries=registries,
        secrets=RuntimeSecretsDescriptor(contract),
    )
    # N1 (F1, F3): material or an unlisted type under any owner fails the program.
    owner, _, kind = scenario.get("addition", ":").partition(":")
    parent = {
        "runtime-secrets": workload.runtime_secrets,
        "stack": workload,
        "root": None,
    }.get(owner)
    options = pulumi.ResourceOptions(parent=parent)
    if kind == "random-password":
        import pulumi_random as random

        random.RandomPassword("fixture-material", length=16, opts=options)
    if kind == "secret-version":
        import pulumi_aws as aws

        aws.secretsmanager.SecretVersion(
            "fixture-version",
            secret_id="synthetic",
            secret_string="synthetic",
            opts=options,
        )
    if kind == "ssm-parameter":
        import pulumi_aws as aws

        aws.ssm.Parameter(
            "fixture-parameter", type="String", value="synthetic", opts=options
        )
    # N1: a credential-bearing data-plane type is refused before its story.
    if kind == "docdb-cluster":
        import pulumi_aws as aws

        aws.docdb.Cluster(
            "fixture-cluster",
            master_username="synthetic",
            master_password="synthetic-not-a-secret",
            opts=options,
        )
    # N1: an allowlisted SES identity still refuses a BYODKIM private key.
    if kind == "byodkim-identity":
        import pulumi_aws as aws

        aws.sesv2.EmailIdentity(
            "fixture-identity",
            email_identity="fixture.example",
            dkim_signing_attributes={
                # Base64 of "synthetic": a well-formed, non-secret key value.
                "domain_signing_private_key": "c3ludGhldGlj",
                "domain_signing_selector": "fixture",
            },
            opts=options,
        )
    # N2: the engine invoke guard refuses a provider function call.
    if kind == "random-password-invoke":
        import pulumi_aws as aws

        aws.secretsmanager.get_random_password(password_length=16)
elif mode == "legacy-workload":
    # The installed entrypoint stays metadata-only. Exercise the legacy managed
    # topology through this explicit integration-only program instead.
    UserServiceStack("user-service")
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
