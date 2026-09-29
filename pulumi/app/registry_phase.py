"""Internal registry and mail prerequisite graph without phase-selection authority."""

from __future__ import annotations

import pulumi
from app.environment import EnvironmentSettings
from app.mail_identity import create_mail_identity
from app.registry import RegistryInputs, RegistryPlane


class RegistryPhaseStack(pulumi.ComponentResource):
    """Own stable registry and SES/DNS URNs retained by the full workload."""

    registries: RegistryPlane
    environment_settings: EnvironmentSettings

    def __init__(self, *, registries: RegistryInputs) -> None:
        """Create registries and mail prerequisites under the future workload owner."""
        settings = preserve_baseline()
        self.environment_settings = settings
        super().__init__(
            "user-service-infrastructure:stack:UserService", "user-service"
        )
        self.mail_identity, self.mail_dkim_records = create_mail_identity(
            parent=self, tags=settings.default_tags
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
