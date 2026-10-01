"""Internal workload composition that retains the complete registry baseline.

This is an ownership prerequisite, not phase admission. Its caller must supply
admitted settings and registry data. Only the protected workload runner reaches
this class, and only for a ``workload`` phase contract; verified releases,
secrets, capabilities and native transition acceptance remain separate
prerequisites of that path.

Transition rule (AD-25): only a projection with ``workload_step`` renders the
hardened composition, which holds no generator and no ``SecretVersion``. The
pre-hardening composition stays unchanged until the topology story removes it.
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
from app.runtime_secrets import RuntimeSecrets, RuntimeSecretsDescriptor

# Closed taggable resource types used by the four installed workload planes.
# SecretVersion, lifecycle policies and route associations do not accept tags.
# This set selects what ``_tag_resource`` tags; it never admits a type to the
# hardened graph, which ``HARDENED_TYPES`` alone decides.
TAGGABLE_TYPES = frozenset(
    {
        "aws:cloudwatch/logGroup:LogGroup",
        "aws:docdb/cluster:Cluster",
        "aws:docdb/clusterInstance:ClusterInstance",
        "aws:docdb/clusterParameterGroup:ClusterParameterGroup",
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
        "aws:s3/bucketV2:BucketV2",
        "aws:sqs/queue:Queue",
    }
)
# Secret material may never enter a hardened graph or its Pulumi state (FR-09).
SECRET_MATERIAL_TYPES = (
    "random:",
    "tls:",
    "aws:secretsmanager/secretVersion:SecretVersion",
)
# Closed allowlist of the hardened graph (F3, N1): exactly the types it renders
# today. Any other type, including a packaged component, fails; widening it is
# a reviewed change. When the data and compute planes rejoin (S1.3, S4.10),
# that story adds their types here together with property checks in
# ``HARDENED_PROPERTY_CHECKS``: DocumentDB ``manageMasterUserPassword`` true and
# no ``masterPassword`` or ``masterPasswordWo``; no ElastiCache ``authToken``;
# and TaskDefinition environment names disjoint from the secret names.
HARDENED_TAGGED_TYPES = frozenset(
    {
        "aws:ec2/eip:Eip",
        "aws:ec2/internetGateway:InternetGateway",
        "aws:ec2/natGateway:NatGateway",
        "aws:ec2/routeTable:RouteTable",
        "aws:ec2/securityGroup:SecurityGroup",
        "aws:ec2/subnet:Subnet",
        "aws:ec2/vpc:Vpc",
        "aws:secretsmanager/secret:Secret",
        "aws:sqs/queue:Queue",
    }
)
HARDENED_UNTAGGED_TYPES = frozenset(
    {
        "aws:ec2/routeTableAssociation:RouteTableAssociation",
        "aws:ecr/repository:Repository",
        "aws:route53/record:Record",
        "aws:sesv2/emailIdentity:EmailIdentity",
    }
)
HARDENED_COMPONENT_TYPES = frozenset(
    {
        "user-service-infrastructure:core:EnvironmentSettings",
        "user-service-infrastructure:messaging:Plane",
        "user-service-infrastructure:network:Plane",
        "user-service-infrastructure:registry:Plane",
        "user-service-infrastructure:secrets:Runtime",
        "user-service-infrastructure:stack:UserService",
    }
)
HARDENED_TYPES = (
    HARDENED_TAGGED_TYPES | HARDENED_UNTAGGED_TYPES | HARDENED_COMPONENT_TYPES
)
# The SES identity may only choose its Easy DKIM key length. A BYODKIM
# ``domainSigningPrivateKey`` (or selector) would put a private key in state.
# The SDK transformation sees snake_case keys, the engine transform camelCase.
EASY_DKIM_KEYS = frozenset({"next_signing_key_length", "nextSigningKeyLength"})
# Provider functions (invokes) a hardened program may call: none (N2). No
# hardened module calls one; a reviewed story widens this list explicitly.
HARDENED_INVOKES: frozenset[str] = frozenset()


def _easy_dkim_only(props) -> bool:
    """Accept no DKIM attributes or a plain map of the key length alone."""
    return all(
        props.get(key) is None
        or (type(props[key]) is dict and set(props[key]) <= EASY_DKIM_KEYS)
        for key in ("dkim_signing_attributes", "dkimSigningAttributes")
    )


# Reviewed property checks for allowlisted types whose typed inputs could
# carry secret material. Every other allowlisted type has no such input.
HARDENED_PROPERTY_CHECKS = {"aws:sesv2/emailIdentity:EmailIdentity": _easy_dkim_only}


def _merge_tags(existing, baseline: dict[str, str]) -> dict[str, str]:
    """Preserve extra explicit tags, rejecting conflicts with baseline metadata."""
    existing = {} if existing is None else existing
    if type(existing) is not dict or any(
        key in baseline and value != baseline[key] for key, value in existing.items()
    ):
        raise ValueError("Workload resource overrides preserved baseline tags")
    return {**existing, **baseline}


def _reject_secret_material(
    args: pulumi.ResourceTransformationArgs | pulumi.ResourceTransformArgs,
) -> None:
    """Fail closed before secret material or an unreviewed type joins the graph.

    One check serves the SDK transformation and the engine transform alike;
    both argument types carry ``type_`` and ``None`` keeps the resource as is.
    """
    if args.type_.startswith(SECRET_MATERIAL_TYPES):
        raise ValueError("Hardened workload graph must not hold secret material")
    if args.type_ not in HARDENED_TYPES:
        raise ValueError("Hardened workload graph holds an unreviewed type")
    check = HARDENED_PROPERTY_CHECKS.get(args.type_)
    if check is not None and not check(args.props):
        raise ValueError("Hardened workload graph holds an unreviewed property")
    return None


def _reject_invoke(args: pulumi.InvokeTransformArgs) -> None:
    """Fail closed on any provider function outside the empty allowlist (N2)."""
    if args.token not in HARDENED_INVOKES:
        raise ValueError("Hardened workload graph must not call a provider function")
    return None


def _guard_hardened_stack() -> None:
    """Guard the whole stack before its first hardened resource (FR-09, F1).

    The SDK stack transformation reaches every resource this program builds,
    whatever its parent, including the registry owner and root resources. The
    engine resource transform also reaches the children of a packaged
    component, which no in-process transformation sees. The engine invoke
    transform refuses every provider function call (N2). The component-level
    transformation in ``_compose_hardened`` stays as a second layer.
    """
    pulumi.runtime.register_stack_transformation(_reject_secret_material)
    pulumi.runtime.register_resource_transform(_reject_secret_material)
    pulumi.runtime.register_invoke_transform(_reject_invoke)


class WorkloadPhaseStack(RegistryPhaseStack):
    """Add workload children under the existing user-service owner and provider."""

    def __init__(
        self,
        *,
        settings: StackSettings,
        registries: RegistryInputs,
        secrets: RuntimeSecretsDescriptor,
    ) -> None:
        if type(settings) is not StackSettings or not settings.is_managed:
            raise ValueError("Workload composition requires explicit managed settings")
        self._validate_target(settings, registries)
        self._validate_metadata(settings)
        validate_runtime_roles(settings.runtime, settings.environment)
        validate_health_check_runtime(settings.runtime, settings.queues)
        if type(secrets) is not RuntimeSecretsDescriptor:
            raise ValueError("Workload composition requires a secret declaration")
        secrets.validate_target(settings)
        if secrets.hardened:
            _guard_hardened_stack()
        super().__init__(registries=registries)
        self.settings = settings
        if secrets.hardened:
            self._compose_hardened(settings, secrets)
        else:
            self._compose_pre_hardening(settings, secrets)
        # Keep existing root/UserService outputs unchanged. New child components
        # expose workload outputs; an authenticated result observer can read them.

    def _compose_hardened(
        self, settings: StackSettings, secrets: RuntimeSecretsDescriptor
    ) -> None:
        """Compose seeded secret metadata and the credential-free planes only.

        The data and compute planes join this branch once they need no generated
        credential; no workload phase can be admitted before that composition.
        """
        opts = pulumi.ResourceOptions(
            parent=self,
            transformations=[_reject_secret_material, self._tag_resource],
        )
        self.runtime_secrets = RuntimeSecrets(
            "runtime-secrets", descriptor=secrets, opts=opts
        )
        self.network = NetworkPlane(
            "network", settings=settings, private_gateway=True, opts=opts
        )
        self.messaging = MessagingPlane("messaging", settings=settings, opts=opts)
        self.runtime_secrets.complete()

    def _compose_pre_hardening(
        self, settings: StackSettings, secrets: RuntimeSecretsDescriptor
    ) -> None:
        """Keep the installed composition, generators included, unchanged."""
        # No provider override: preserve the installed default AWS provider,
        # including the existing ECR provider links and canonical account pins.
        opts = pulumi.ResourceOptions(parent=self, transformations=[self._tag_resource])
        self.runtime_secrets = RuntimeSecrets(
            "runtime-secrets", descriptor=secrets, opts=opts
        )
        self.network = NetworkPlane(
            "network", settings=settings, private_gateway=True, opts=opts
        )
        self.data = DataPlane(
            "data",
            settings=settings,
            network=self.network,
            runtime_secrets=self.runtime_secrets,
            opts=opts,
        )
        self.runtime_secrets.complete()
        self.messaging = MessagingPlane("messaging", settings=settings, opts=opts)
        self.compute = ComputePlane(
            "compute",
            settings=settings,
            network=self.network,
            data=self.data,
            messaging=self.messaging,
            registries=self.registries.outputs,
            runtime_secrets=self.runtime_secrets,
            opts=opts,
        )

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
