"""Proposed registry owner; not wired into the installed deployment program.

The caller projects only names/logical names from the registries section of a
validated shared poc-test-v1 contract. The legacy stack adapter instead uses its
existing config names; that projection is not shared-contract authentication.
This component does not authenticate source, prior phase,
account, capabilities or approvals. It never enables a deployment phase.

Keep this owner and its parent stable when workload consumers are added. Existing
ComputePlane-owned repositories have different URNs despite the same child
names; their adoption requires a separately reviewed state/alias plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

import pulumi_aws as aws

import pulumi


class RegistryReference(TypedDict):
    """Registry fields from the validated shared contract, without new semantics."""

    logical_name: str
    name: str


class RegistryInputs(TypedDict):
    """The fixed web and worker registry pair; no workload or IAM inputs."""

    web: RegistryReference
    worker: RegistryReference


@dataclass(frozen=True)
class RegistryEndpoint:
    """Actual provider outputs for one repository, not claimed input identities."""

    arn: pulumi.Output[str]
    uri: pulumi.Output[str]
    name: pulumi.Output[str]


@dataclass(frozen=True)
class RegistryOutputs:
    """Stable references for a future publisher and workload consumer."""

    web: RegistryEndpoint
    worker: RegistryEndpoint


class RegistryPlane(pulumi.ComponentResource):
    """Own exactly two immutable ECR repositories under one reusable parent."""

    def __init__(
        self,
        name: str,
        *,
        registries: RegistryInputs,
        tags: pulumi.Input[dict[str, str]] | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        """Register only the validated registry pair and expose actual outputs."""
        super().__init__("user-service-infrastructure:registry:Plane", name, None, opts)
        web = self._repository(registries["web"], tags=tags)
        worker = self._repository(registries["worker"], tags=tags)
        self.outputs = RegistryOutputs(
            web=RegistryEndpoint(web.arn, web.repository_url, web.name),
            worker=RegistryEndpoint(worker.arn, worker.repository_url, worker.name),
        )
        self.register_outputs(
            {
                "webRepositoryArn": self.outputs.web.arn,
                "webRepositoryUrl": self.outputs.web.uri,
                "workerRepositoryArn": self.outputs.worker.arn,
                "workerRepositoryUrl": self.outputs.worker.uri,
            }
        )

    def _repository(
        self, reference: RegistryReference, *, tags: pulumi.Input[dict[str, str]] | None
    ) -> aws.ecr.Repository:
        """Keep source-selected logical names, immutable tags and safe deletion."""
        return aws.ecr.Repository(
            reference["logical_name"],
            name=reference["name"],
            image_tag_mutability="IMMUTABLE",
            image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                scan_on_push=True,
            ),
            force_delete=False,
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self),
        )
