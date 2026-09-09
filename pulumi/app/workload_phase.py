"""Internal workload composition that retains the complete registry baseline.

This is an ownership prerequisite, not phase admission. Its caller must supply
admitted settings and registry data. No CLI or config dispatches to this class;
verified releases, secrets, capabilities and native transition acceptance remain
separate prerequisites before wiring it into the trusted controller.
"""

from __future__ import annotations

import pulumi
from app.compute import ComputePlane
from app.data import DataPlane
from app.environment import (
    DEFAULT_COST_CENTER,
    DEFAULT_OWNER,
    StackSettings,
    _default_tags_from_parts,
    _normalize_tag_value,
    resolve_config_value,
    validate_health_check_runtime,
    validate_runtime_roles,
)
from app.messaging import MessagingPlane
from app.network import NetworkPlane
from app.registry import RegistryInputs
from app.registry_phase import RegistryPhaseStack

# Closed taggable resource types used by the four installed workload planes.
# SecretVersion, lifecycle policies and route associations do not accept tags.
TAGGABLE_TYPES = frozenset(
    {
        "aws:cloudwatch/logGroup:LogGroup",
        "aws:docdb/cluster:Cluster",
        "aws:docdb/clusterInstance:ClusterInstance",
        "aws:docdb/subnetGroup:SubnetGroup",
        "aws:ec2/eip:Eip",
        "aws:ec2/internetGateway:InternetGateway",
        "aws:ec2/natGateway:NatGateway",
        "aws:ec2/routeTable:RouteTable",
        "aws:ec2/securityGroup:SecurityGroup",
        "aws:ec2/subnet:Subnet",
        "aws:ec2/vpc:Vpc",
        "aws:ecs/cluster:Cluster",
        "aws:ecs/service:Service",
        "aws:ecs/taskDefinition:TaskDefinition",
        "aws:elasticache/replicationGroup:ReplicationGroup",
        "aws:elasticache/subnetGroup:SubnetGroup",
        "aws:lb/listener:Listener",
        "aws:lb/loadBalancer:LoadBalancer",
        "aws:lb/targetGroup:TargetGroup",
        "aws:secretsmanager/secret:Secret",
        "aws:sqs/queue:Queue",
    }
)


def _merge_tags(existing, baseline: dict[str, str]) -> dict[str, str]:
    """Preserve extra explicit tags, rejecting conflicts with baseline metadata."""
    existing = {} if existing is None else existing
    if type(existing) is not dict or any(
        key in baseline and value != baseline[key] for key, value in existing.items()
    ):
        raise ValueError("Workload resource overrides preserved baseline tags")
    return {**existing, **baseline}


class WorkloadPhaseStack(RegistryPhaseStack):
    """Add workload children under the existing user-service owner and provider."""

    def __init__(self, *, settings: StackSettings, registries: RegistryInputs) -> None:
        if type(settings) is not StackSettings or not settings.is_managed:
            raise ValueError("Workload composition requires explicit managed settings")
        self._validate_target(settings, registries)
        self._validate_metadata(settings)
        validate_runtime_roles(settings.runtime, settings.environment)
        validate_health_check_runtime(settings.runtime, settings.queues)
        super().__init__(registries=registries)
        self.settings = settings
        # No provider override: preserve the installed default AWS provider,
        # including the existing ECR provider links and canonical account pins.
        opts = pulumi.ResourceOptions(parent=self, transformations=[self._tag_resource])
        self.network = NetworkPlane("network", settings=settings, opts=opts)
        self.data = DataPlane(
            "data", settings=settings, network=self.network, opts=opts
        )
        self.messaging = MessagingPlane("messaging", settings=settings, opts=opts)
        self.compute = ComputePlane(
            "compute",
            settings=settings,
            network=self.network,
            data=self.data,
            messaging=self.messaging,
            registries=self.registries.outputs,
            opts=opts,
        )
        # Keep existing root/UserService outputs unchanged. New child components
        # expose workload outputs; an authenticated result observer can read them.

    @staticmethod
    def _validate_target(settings: StackSettings, registries: RegistryInputs) -> None:
        expected_registries: RegistryInputs = {
            "web": {
                "logical_name": "user-service-web-repository",
                "name": "user-service-test-web",
            },
            "worker": {
                "logical_name": "user-service-worker-repository",
                "name": "user-service-test-worker",
            },
        }
        actual = (
            pulumi.get_project(),
            pulumi.get_stack(),
            settings.environment,
            settings.region,
            pulumi.Config("aws").require("region"),
            settings.images.web_repository_name,
            settings.images.worker_repository_name,
            settings.images.image_tag_mutability,
        )
        expected = (
            "user-service-infrastructure",
            "test",
            "test",
            "eu-central-1",
            "eu-central-1",
            "user-service-test-web",
            "user-service-test-worker",
            "IMMUTABLE",
        )
        if actual != expected or registries != expected_registries:
            raise ValueError(
                "Workload composition differs from the TEST registry target"
            )

    @staticmethod
    def _validate_metadata(settings: StackSettings) -> None:
        config = pulumi.Config()
        parts = (
            resolve_config_value(
                None, config.get("serviceName"), default=pulumi.get_project()
            ),
            resolve_config_value(None, config.get("environment"), default="dev"),
            _normalize_tag_value(config.get("owner") or "", default=DEFAULT_OWNER),
            _normalize_tag_value(
                config.get("costCenter") or "", default=DEFAULT_COST_CENTER
            ),
            _normalize_tag_value(
                config.get("dataClassification") or "", default="internal"
            ),
            _normalize_tag_value(config.get("criticality") or "", default="high"),
            _normalize_tag_value(
                config.get("retentionClass") or "", default="standard"
            ),
        )
        actual = (
            settings.service_name,
            settings.environment,
            settings.owner,
            settings.cost_center,
            settings.stack_tag,
            settings.default_tags,
        )
        expected = (
            *parts[:4],
            f"{parts[0]}-{parts[1]}",
            _default_tags_from_parts(parts),
        )
        if actual != expected:
            raise ValueError("Workload composition changes preserved baseline metadata")

    def _tag_resource(
        self, args: pulumi.ResourceTransformationArgs
    ) -> pulumi.ResourceTransformationResult | None:
        """Apply baseline tags only within the new workload subtrees."""
        if args.type_ not in TAGGABLE_TYPES:
            return None
        props = dict(args.props)
        props["tags"] = _merge_tags(props.get("tags"), self.settings.default_tags)
        return pulumi.ResourceTransformationResult(props=props, opts=args.opts)
