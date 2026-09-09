"""Internal, registry-only Pulumi graph with no phase-selection authority."""

from __future__ import annotations

import pulumi
from app.environment import EnvironmentSettings
from app.registry import RegistryInputs, RegistryPlane


class RegistryPhaseStack(pulumi.ComponentResource):
    """Own the stable full-workload registry URNs and nothing else."""

    registries: RegistryPlane

    def __init__(self, *, registries: RegistryInputs) -> None:
        """Create the two repositories under the future workload's root owner."""
        settings = preserve_baseline()
        super().__init__(
            "user-service-infrastructure:stack:UserService", "user-service"
        )
        self.registries = RegistryPlane(
            "registries",
            registries=registries,
            tags=settings.default_tags,
            opts=pulumi.ResourceOptions(parent=self),
        )


def preserve_baseline() -> EnvironmentSettings:
    """Keep the installed e2461876 root metadata component and exports unchanged."""
    settings = EnvironmentSettings("environment-settings")
    config = pulumi.Config()
    pulumi.export("environment", settings.environment)
    pulumi.export("serviceName", settings.service_name)
    pulumi.export("stackTag", settings.stack_tag)
    pulumi.export("defaultTags", settings.default_tags)
    for field in ("repoSlug", "pulumiBackendUrl", "pulumiSecretsProvider"):
        pulumi.export(field, config.require(field))
    return settings
