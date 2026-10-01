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
from app.environment import resolve_stack_settings  # noqa: E402
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
elif hardened:
    # A workload_step contract renders the hardened composition (AD-25). Since
    # S1.3 it composes the data and compute planes under the stack-wide guard;
    # a documentDbPassword or engine version arrives only through stack config.
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
    # N1: an allowlisted DocumentDB cluster still refuses a primary password.
    if kind == "docdb-cluster":
        import pulumi_aws as aws

        aws.docdb.Cluster(
            "fixture-cluster",
            master_username="synthetic",
            master_password="synthetic-not-a-secret",
            opts=options,
        )
    # N (V-17): an elastic cluster has no IAM authentication.
    if kind == "docdb-elastic-cluster":
        import pulumi_aws as aws

        aws.docdb.ElasticCluster(
            "fixture-elastic-cluster",
            admin_user_name="synthetic",
            admin_user_password="synthetic-not-a-secret",
            auth_type="PLAIN_TEXT",
            shard_capacity=2,
            shard_count=1,
            opts=options,
        )
    # B (FR-34): a step-2 type never joins the step-1 graph.
    if kind == "secret-policy":
        import pulumi_aws as aws

        aws.secretsmanager.SecretPolicy(
            "fixture-policy", secret_arn="synthetic", policy="{}", opts=options
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
    # F-01 (a): a secret-marked definition reaches the engine as a secret map.
    if kind == "secret-task":
        import pulumi_aws as aws

        definitions = [{"name": "fixture", "environment": []}]
        aws.ecs.TaskDefinition(
            "fixture-task",
            family="fixture",
            container_definitions=pulumi.Output.secret(json.dumps(definitions)),
            opts=options,
        )
    # F-01 (b): ECS reads PascalCase keys case-insensitively; the guard refuses.
    if kind == "pascal-task":
        import pulumi_aws as aws

        row = {"Name": "DSN", "Value": "https://user:synthetic@host"}
        aws.ecs.TaskDefinition(
            "fixture-task",
            family="fixture",
            container_definitions=json.dumps([{"name": "f", "Environment": [row]}]),
            opts=options,
        )
    # F-02: an OIDC listener action carries a client secret.
    if kind == "oidc-listener":
        import pulumi_aws as aws

        aws.lb.Listener(
            "fixture-listener",
            load_balancer_arn="arn:aws:fixture",
            default_actions=[
                {
                    "type": "authenticate-oidc",
                    "authenticate_oidc": {
                        "authorization_endpoint": "https://idp.example/authorize",
                        "client_id": "fixture",
                        "client_secret": "synthetic-not-a-secret",
                        "issuer": "https://idp.example",
                        "token_endpoint": "https://idp.example/token",
                        "user_info_endpoint": "https://idp.example/userinfo",
                    },
                }
            ],
            opts=options,
        )
    # F-03: an inline secret policy bypasses the step-1 SecretPolicy refusal.
    if kind == "policy-secret":
        import pulumi_aws as aws

        aws.secretsmanager.Secret(
            "fixture-secret", name="fixture", policy="{}", opts=options
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
