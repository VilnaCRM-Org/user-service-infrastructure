"""Top-level orchestration for the user-service infrastructure stack."""

from __future__ import annotations

from typing import Optional

import pulumi_aws as aws

import pulumi
from app.compute import ComputePlane
from app.data import DataPlane
from app.environment import (
    EnvironmentSettings,
    StackSettings,
    has_aws_credentials,
    resolve_stack_settings,
)
from app.messaging import MessagingPlane
from app.network import NetworkPlane

__all__ = ["UserServiceStack"]


class UserServiceStack(pulumi.ComponentResource):
    """Compose the environment, network, data, messaging, and compute planes."""

    settings: StackSettings
    environment_settings: EnvironmentSettings
    network: NetworkPlane
    data: DataPlane
    messaging: MessagingPlane
    compute: ComputePlane

    def __init__(
        self,
        name: str,
        *,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        super().__init__(
            "user-service-infrastructure:stack:UserService", name, None, opts
        )

        self.environment_settings = EnvironmentSettings(
            "environment",
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.settings = resolve_stack_settings(self.environment_settings)

        provider = self._build_provider()
        component_opts = (
            pulumi.ResourceOptions(parent=self, provider=provider)
            if provider is not None
            else pulumi.ResourceOptions(parent=self)
        )

        self.network = NetworkPlane(
            "network", settings=self.settings, opts=component_opts
        )
        self.data = DataPlane(
            "data",
            settings=self.settings,
            network=self.network,
            opts=component_opts,
        )
        self.messaging = MessagingPlane(
            "messaging",
            settings=self.settings,
            opts=component_opts,
        )
        self.compute = ComputePlane(
            "compute",
            settings=self.settings,
            network=self.network,
            data=self.data,
            messaging=self.messaging,
            opts=component_opts,
        )

        self.register_outputs(
            {
                "deploymentMode": self.settings.deployment_mode,
                "environment": self.environment_settings.environment,
                "serviceName": self.environment_settings.service_name,
                "stackTag": self.environment_settings.stack_tag,
                "defaultTags": self.environment_settings.default_tags,
                "region": self.settings.region,
                "serviceUrl": self.compute.outputs.service_url,
                "loadBalancerDnsName": self.compute.outputs.load_balancer_dns_name,
                "clusterName": self.compute.outputs.cluster_name,
                "webServiceName": self.compute.outputs.web_service_name,
                "workerServiceName": self.compute.outputs.worker_service_name,
                "webRepositoryUrl": self.compute.outputs.web_repository_url,
                "workerRepositoryUrl": self.compute.outputs.worker_repository_url,
                "queueUrls": self.messaging.outputs.queue_urls,
                "documentDbEndpoint": self.data.outputs.documentdb_endpoint,
                "redisEndpoint": self.data.outputs.redis_endpoint,
            }
        )

    def _build_provider(self) -> aws.Provider | None:
        """Create the AWS provider only when managed resources are enabled."""
        if not self.settings.is_managed:
            return None

        preview_without_credentials = pulumi.runtime.is_dry_run() and not (
            has_aws_credentials()
        )
        preview_access_key = "pulumi-preview" if preview_without_credentials else None
        preview_secret_key = "pulumi-preview" if preview_without_credentials else None

        return aws.Provider(
            "managed-provider",
            region=self.settings.region,
            access_key=preview_access_key,
            secret_key=preview_secret_key,
            default_tags=aws.ProviderDefaultTagsArgs(tags=self.settings.default_tags),
            skip_credentials_validation=pulumi.runtime.is_dry_run(),
            skip_metadata_api_check=pulumi.runtime.is_dry_run(),
            skip_requesting_account_id=pulumi.runtime.is_dry_run(),
            skip_region_validation=preview_without_credentials,
            opts=pulumi.ResourceOptions(parent=self),
        )
