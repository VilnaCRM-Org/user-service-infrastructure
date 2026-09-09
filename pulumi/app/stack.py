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
from app.registry import RegistryPlane

__all__ = ["UserServiceStack"]


class UserServiceStack(pulumi.ComponentResource):
    """Compose the environment, network, data, messaging, and compute planes."""

    settings: StackSettings
    environment_settings: EnvironmentSettings
    network: NetworkPlane
    data: DataPlane
    messaging: MessagingPlane
    compute: ComputePlane
    registries: RegistryPlane | None

    def __init__(
        self,
        name: str,
        *,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Compose the full user-service infrastructure stack for the active config."""
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
            pulumi.ResourceOptions(parent=self, providers=[provider])
            if provider is not None
            else pulumi.ResourceOptions(parent=self)
        )

        # This legacy config projection is not shared-contract admission. The
        # future phase dispatcher must authenticate its contract and prior state.
        # Keep this owner/parent identical in registry and workload phases.
        self.registries = (
            RegistryPlane(
                "registries",
                registries={
                    "web": {
                        "logical_name": "user-service-web-repository",
                        "name": self.settings.images.web_repository_name,
                    },
                    "worker": {
                        "logical_name": "user-service-worker-repository",
                        "name": self.settings.images.worker_repository_name,
                    },
                },
                opts=component_opts,
            )
            if self.settings.is_managed
            else None
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
            registries=self.registries.outputs if self.registries is not None else None,
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
            skip_credentials_validation=preview_without_credentials,
            skip_metadata_api_check=preview_without_credentials,
            skip_requesting_account_id=preview_without_credentials,
            skip_region_validation=preview_without_credentials,
            opts=pulumi.ResourceOptions(parent=self),
        )
