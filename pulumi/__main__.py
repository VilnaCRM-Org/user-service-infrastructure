"""Pulumi entrypoint for the user-service infrastructure stack."""

import pulumi_aws as aws
from app import UserServiceStack

import pulumi

config = pulumi.Config()
stack_name = pulumi.get_stack()
environment = config.get("environment")
if stack_name in {"test", "prod"} or environment in {"test", "prod"}:
    if environment != stack_name:
        raise ValueError("Configured environment differs from selected shared stack")
    expected_account = config.require("awsAccountId")
    if aws.get_caller_identity().account_id != expected_account:
        raise ValueError("AWS caller account differs from configured awsAccountId")

stack = UserServiceStack("user-service")

pulumi.export("deploymentMode", stack.settings.deployment_mode)
pulumi.export("environment", stack.environment_settings.environment)
pulumi.export("serviceName", stack.environment_settings.service_name)
pulumi.export("stackTag", stack.environment_settings.stack_tag)
pulumi.export("defaultTags", stack.environment_settings.default_tags)
pulumi.export("region", stack.settings.region)
pulumi.export("serviceUrl", stack.compute.outputs.service_url)
pulumi.export("loadBalancerDnsName", stack.compute.outputs.load_balancer_dns_name)
pulumi.export("clusterName", stack.compute.outputs.cluster_name)
pulumi.export("webServiceName", stack.compute.outputs.web_service_name)
pulumi.export("workerServiceName", stack.compute.outputs.worker_service_name)
pulumi.export("webRepositoryUrl", stack.compute.outputs.web_repository_url)
pulumi.export("workerRepositoryUrl", stack.compute.outputs.worker_repository_url)
pulumi.export("queueUrls", stack.messaging.outputs.queue_urls)
pulumi.export("documentDbEndpoint", stack.data.outputs.documentdb_endpoint)
pulumi.export("redisEndpoint", stack.data.outputs.redis_endpoint)

if environment in {"test", "prod"}:
    pulumi.export("repoSlug", config.require("repoSlug"))
    pulumi.export("pulumiBackendUrl", config.require("pulumiBackendUrl"))
    pulumi.export("pulumiSecretsProvider", config.require("pulumiSecretsProvider"))
