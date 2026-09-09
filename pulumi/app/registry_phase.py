"""Internal, registry-only Pulumi graph with no phase-selection authority."""

from __future__ import annotations

import pulumi
from app.registry import RegistryInputs, RegistryPlane


class RegistryPhaseStack(pulumi.ComponentResource):
    """Own the stable full-workload registry URNs and nothing else."""

    registries: RegistryPlane

    def __init__(self, *, registries: RegistryInputs) -> None:
        """Create the two repositories under the future workload's root owner."""
        super().__init__(
            "user-service-infrastructure:stack:UserService", "user-service"
        )
        self.registries = RegistryPlane(
            "registries",
            registries=registries,
            opts=pulumi.ResourceOptions(parent=self),
        )
