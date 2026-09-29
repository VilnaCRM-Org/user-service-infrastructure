"""Pulumi entrypoint that exports baseline stack metadata."""

import pulumi_aws as aws
from app import EnvironmentSettings

import pulumi

config = pulumi.Config()
stack = pulumi.get_stack()
environment = config.get("environment")
if stack in {"test", "prod"} or environment in {"test", "prod"}:
    if environment != stack:
        raise ValueError("Configured environment differs from selected shared stack")
    expected_account = config.require("awsAccountId")
    if aws.get_caller_identity().account_id != expected_account:
        raise ValueError("AWS caller account differs from configured awsAccountId")

settings = EnvironmentSettings("environment-settings")

pulumi.export("environment", settings.environment)
pulumi.export("serviceName", settings.service_name)
pulumi.export("stackTag", settings.stack_tag)
pulumi.export("defaultTags", settings.default_tags)

# Shared TEST/PROD stacks consume governance-owned backends and keys. Preserve
# the existing development metadata component and exports above.
if config.get("environment") in {"test", "prod"}:
    pulumi.export("repoSlug", config.require("repoSlug"))
    pulumi.export("pulumiBackendUrl", config.require("pulumiBackendUrl"))
    pulumi.export("pulumiSecretsProvider", config.require("pulumiSecretsProvider"))
