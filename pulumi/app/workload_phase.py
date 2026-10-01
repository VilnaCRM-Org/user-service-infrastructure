"""Internal workload composition that retains the complete registry baseline.

This is an ownership prerequisite, not phase admission. Its caller must supply
admitted settings and registry data. Only the protected workload runner reaches
this class, and only for a ``workload`` phase contract; verified releases,
secrets, capabilities and native transition acceptance remain separate
prerequisites of that path.

Transition rule (AD-25): only a projection with ``workload_step`` renders the
hardened composition, which holds no generator and no ``SecretVersion``. The
pre-hardening composition stays unchanged until the topology story removes it.

Two-step first workload (FR-34, AD-18): step 1 renders the network, data,
secret metadata and ECS services at zero tasks; no step-2 type (seed, rotation,
secret policy, autoscaling or scheduled action) may join it. Step 2 adds only
those types, each with its own story (S1.5, S1.6, S2.1, S2.2, S2.6); its
create-only admission is S4.9. After step 1 the XP-8 values are exported.
"""

from __future__ import annotations

import asyncio
import functools
import json
from typing import Any

import pulumi_aws as aws
from pulumi.output import Unknown
from pulumi.runtime.rpc import is_rpc_secret

import pulumi
from app.compute import INITIAL_SERVICE_SCALE, ComputePlane, require_plain_containers
from app.data import (
    DOCUMENTDB_IAM_ENGINE_VERSION,
    DataPlane,
    require_iam_documentdb_engine,
)
from app.environment import (
    DEFAULT_COST_CENTER,
    DEFAULT_OWNER,
    StackSettings,
    _default_tags_from_parts,
    _normalize_tag_value,
    reject_documentdb_password_config,
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
# Step-2 types (FR-34, AD-18): a step-1 graph never holds one. Each joins the
# allowlist only with its own story; until then the allowlist refuses it too.
STEP_TWO_TYPES = frozenset(
    {
        "aws:appautoscaling/policy:Policy",
        "aws:appautoscaling/scheduledAction:ScheduledAction",
        "aws:appautoscaling/target:Target",
        "aws:lambda/invocation:Invocation",
        "aws:secretsmanager/secretPolicy:SecretPolicy",
        "aws:secretsmanager/secretRotation:SecretRotation",
    }
)
# IAM authentication exists only on instance-based DocumentDB 5.0 (V-17, A-01).
ELASTIC_DOCUMENTDB_TYPE = "aws:docdb/elasticCluster:ElasticCluster"
# Closed allowlist of the hardened graph (F3, N1): exactly the types it renders
# today. Any other type, including a packaged component, fails; widening it is
# a reviewed change. S1.3 added the data and compute planes with the property
# checks in ``HARDENED_PROPERTY_CHECKS``. Redis (and its ``authToken`` check)
# joins with S1.4 (D-1).
HARDENED_TAGGED_TYPES = frozenset(
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
        "aws:lb/listener:Listener",
        "aws:lb/loadBalancer:LoadBalancer",
        "aws:lb/targetGroup:TargetGroup",
        "aws:s3/bucketV2:BucketV2",
        "aws:secretsmanager/secret:Secret",
        "aws:sqs/queue:Queue",
    }
)
HARDENED_UNTAGGED_TYPES = frozenset(
    {
        "aws:ec2/routeTableAssociation:RouteTableAssociation",
        "aws:ecr/lifecyclePolicy:LifecyclePolicy",
        "aws:ecr/repository:Repository",
        "aws:route53/record:Record",
        "aws:s3/bucketLifecycleConfigurationV2:BucketLifecycleConfigurationV2",
        "aws:s3/bucketOwnershipControls:BucketOwnershipControls",
        "aws:s3/bucketPolicy:BucketPolicy",
        "aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock",
        "aws:s3/bucketServerSideEncryptionConfigurationV2:"
        "BucketServerSideEncryptionConfigurationV2",
        "aws:s3/bucketVersioningV2:BucketVersioningV2",
        "aws:sesv2/emailIdentity:EmailIdentity",
    }
)
HARDENED_COMPONENT_TYPES = frozenset(
    {
        "user-service-infrastructure:compute:AccessLogs",
        "user-service-infrastructure:compute:Plane",
        "user-service-infrastructure:core:EnvironmentSettings",
        "user-service-infrastructure:data:Plane",
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


def _easy_dkim_only(props, _sdk_path: bool) -> bool:
    """Accept no DKIM attributes or a plain map of the key length alone."""
    return all(
        props.get(key) is None
        or (type(props[key]) is dict and set(props[key]) <= EASY_DKIM_KEYS)
        for key in ("dkim_signing_attributes", "dkimSigningAttributes")
    )


def _either(props, snake: str, camel: str):
    """Read one input in the SDK (snake_case) or engine (camelCase) casing."""
    return props[snake] if snake in props else props.get(camel)


DOCUMENTDB_PASSWORD_INPUTS = (
    "master_password",
    "masterPassword",
    "master_password_wo",
    "masterPasswordWo",
)


def _managed_iam_documentdb(props, _sdk_path: bool) -> bool:
    """Accept only the managed password on the IAM-capable engine (S1.2, S1.3).

    ``manageMasterUserPassword`` must be literally true, no primary password
    input may be present, and the engine must be DocumentDB 5.0.0 (V-17).
    """
    return (
        _either(props, "manage_master_user_password", "manageMasterUserPassword")
        is True
        and all(props.get(key) is None for key in DOCUMENTDB_PASSWORD_INPUTS)
        and props.get("engine") == "docdb"
        and _either(props, "engine_version", "engineVersion")
        == DOCUMENTDB_IAM_ENGINE_VERSION
    )


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object; ECS would merge keys that differ only in case."""
    if len({key.casefold() for key, _ in pairs}) != len(pairs):
        raise ValueError("Container definitions repeat a key")
    return dict(pairs)


# Marks a value the check cannot inspect yet and leaves to a later layer.
DEFERRED = object()


def _resolved(future: Any) -> bool:
    """Tell whether a future already holds a result, without awaiting it."""
    return (
        isinstance(future, asyncio.Future)
        and future.done()
        and not future.cancelled()
        and future.exception() is None
    )


def _engine_output(value: pulumi.Output) -> Any:
    """Read an engine-path output value without awaiting it.

    ``deserialize_output_value`` resolves the value and secret futures before
    the transform runs, and leaves an unknown preview value ``None``. A secret
    or an unresolved output stays opaque, so the caller refuses it.
    """
    # ``vars`` avoids ``Output.__getattr__``, which would lift a missing
    # attribute into a new pending output instead of failing.
    fields = vars(value)
    secret, future = fields.get("_is_secret"), fields.get("_future")
    if not (_resolved(secret) and _resolved(future)) or secret.result() is not False:
        return value
    result = future.result()
    return Unknown() if result is None else result


def _inspectable(value: Any, sdk_path: bool) -> Any:
    """Return ``DEFERRED`` or the value the check inspects.

    On the SDK path an ``Output`` is not yet inspectable. It reaches the
    engine transform once the SDK serializes it: resolved for an ``up``,
    unknown in a preview, or secret, which fails. On the engine path the SDK
    sends an output value, read by ``_engine_output``, or a plain value; a
    secret arrives as a secret map or a secret output value and fails. Only
    an unknown preview value is deferred there: a preview writes nothing, and
    the ``up`` that writes the definition sends it resolved.
    """
    if sdk_path:
        return DEFERRED if isinstance(value, pulumi.Output) else value
    if type(value) is pulumi.Output:
        value = _engine_output(value)
    return DEFERRED if type(value) is Unknown else value


def _plain_task_environment(props, sdk_path: bool) -> bool:
    """Accept container definitions that hold no secret material (FR-03, FR-08).

    A JSON string is inspected; an SDK ``Output`` or an unknown engine-path
    preview value is deferred (``_inspectable``). Anything else fails,
    including a secret-marked input, a map, a list or any other object. The
    string must pass ``require_plain_containers`` with bare-ARN references,
    and no JSON object may repeat a key in any case.
    """
    value = _inspectable(
        _either(props, "container_definitions", "containerDefinitions"), sdk_path
    )
    if value is DEFERRED:
        return True
    if type(value) is not str:
        return False
    try:
        containers = json.loads(value, object_pairs_hook=_unique_keys)
        require_plain_containers(containers, unversioned=True)
    except (ValueError, TypeError):
        return False
    return True


# SDK input types the guard reads field by field. Any other object, such as an
# ``Output``, a preview ``Unknown`` or the engine's secret map, is opaque.
REVIEWED_INPUT_TYPES = (
    aws.ecs.TaskDefinitionVolumeArgs,
    aws.lb.ListenerDefaultActionArgs,
)


def _fields(value: Any) -> dict[str, Any] | None:
    """Read a plain map or a reviewed input type; ``None`` means opaque."""
    if type(value) is dict and not is_rpc_secret(value):
        return value
    if type(value) in REVIEWED_INPUT_TYPES:
        return vars(value)
    return None


def _name_only_volumes(props) -> bool:
    """Accept task volumes that only name ephemeral storage.

    The FSx ``authorizationConfig.credentialsParameter`` and the free-form
    Docker ``driverOpts`` fail with every other volume setting (F-02 audit).
    """
    volumes = props.get("volumes")
    if volumes is None:
        return True
    return type(volumes) is list and all(
        (fields := _fields(volume)) is not None and set(fields) == {"name"}
        for volume in volumes
    )


def _reviewed_task_definition(props, sdk_path: bool) -> bool:
    """Check the container definitions and the task volumes."""
    return _plain_task_environment(props, sdk_path) and _name_only_volumes(props)


def _no_oidc_action(props, _sdk_path: bool) -> bool:
    """Refuse a listener action that could carry an OIDC ``clientSecret`` (F-02).

    Each default action must be a readable map or input type with no
    ``authenticate_oidc`` key in any casing; an opaque action or list fails.
    """
    actions = _either(props, "default_actions", "defaultActions")
    if actions is None:
        return True
    if type(actions) is not list:
        return False
    for action in actions:
        fields = _fields(action)
        if fields is None or any(
            str(key).replace("_", "").casefold() == "authenticateoidc" for key in fields
        ):
            return False
    return True


def _no_inline_secret_policy(props, _sdk_path: bool) -> bool:
    """Refuse an inline ``policy``: it would bypass the SecretPolicy refusal.

    A resource policy joins only as the step-2 ``SecretPolicy`` with its own
    story (FR-34 B, AD-08). The key is ``policy`` in both casings.
    """
    return props.get("policy") is None


def _no_service_connect(props, _sdk_path: bool) -> bool:
    """Refuse Service Connect, whose log configuration has ``secretOptions``."""
    return (
        _either(props, "service_connect_configuration", "serviceConnectConfiguration")
        is None
    )


# Reviewed property checks for allowlisted types whose typed inputs could
# carry secret material or bypass a step-1 refusal. The typed-input audit of
# pulumi-aws 7.23.0 (secret, password, token, private_key, client_secret)
# found these types and no other: the DocumentDB password inputs, the task
# definition's container definitions and FSx credentials parameter, the
# listener OIDC ``clientSecret``, the secret's inline ``policy``, the Service
# Connect ``secretOptions`` and the SES BYODKIM private key. Each check gets
# the props and whether they come from the SDK path (snake_case, raw inputs)
# rather than the engine path (camelCase, deserialized).
HARDENED_PROPERTY_CHECKS = {
    "aws:docdb/cluster:Cluster": _managed_iam_documentdb,
    "aws:ecs/service:Service": _no_service_connect,
    "aws:ecs/taskDefinition:TaskDefinition": _reviewed_task_definition,
    "aws:lb/listener:Listener": _no_oidc_action,
    "aws:secretsmanager/secret:Secret": _no_inline_secret_policy,
    "aws:sesv2/emailIdentity:EmailIdentity": _easy_dkim_only,
}


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
    step: int = 1,
) -> None:
    """Fail closed before secret material or an unreviewed type joins the graph.

    One check serves the SDK transformation and the engine transform alike;
    both argument types carry ``type_`` and ``None`` keeps the resource as is.
    ``step`` is the contract's ``workload_step``; step 1 refuses every step-2
    type (FR-34), and the default is that stricter step.
    """
    if args.type_.startswith(SECRET_MATERIAL_TYPES):
        raise ValueError("Hardened workload graph must not hold secret material")
    if args.type_ == ELASTIC_DOCUMENTDB_TYPE:
        raise ValueError("Hardened DocumentDB must be an instance-based cluster")
    if step == 1 and args.type_ in STEP_TWO_TYPES:
        raise ValueError("Step-1 workload graph must not hold a step-2 resource")
    if args.type_ not in HARDENED_TYPES:
        raise ValueError("Hardened workload graph holds an unreviewed type")
    check = HARDENED_PROPERTY_CHECKS.get(args.type_)
    sdk_path = isinstance(args, pulumi.ResourceTransformationArgs)
    if check is not None and not check(args.props, sdk_path):
        raise ValueError("Hardened workload graph holds an unreviewed property")
    return None


def _reject_invoke(_args: pulumi.InvokeTransformArgs) -> None:
    """Fail closed on every provider function call (N2).

    The invoke allowlist is empty: no hardened module calls a provider
    function. A story that needs one adds a reviewed allowlist and its tests.
    """
    raise ValueError("Hardened workload graph must not call a provider function")


def _step_guard(step: int):
    """Bind the guard to the contract's step; both registrations share it."""
    return functools.partial(_reject_secret_material, step=step)


def _guard_hardened_stack(step: int) -> None:
    """Guard the whole stack before its first hardened resource (FR-09, F1).

    The SDK stack transformation reaches every resource this program builds,
    whatever its parent, including the registry owner and root resources. The
    engine resource transform also reaches the children of a packaged
    component, which no in-process transformation sees. The engine invoke
    transform refuses every provider function call (N2). The component-level
    transformation in ``_compose_hardened`` stays as a second layer. These
    are the last transforms the program registers.
    """
    guard = _step_guard(step)
    pulumi.runtime.register_stack_transformation(guard)
    pulumi.runtime.register_resource_transform(guard)
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
            # Refuse a configured primary password or a non-IAM engine (V-17)
            # before any registration; DataPlane repeats the engine check.
            reject_documentdb_password_config()
            require_iam_documentdb_engine(settings.documentdb.engine_version)
            _guard_hardened_stack(secrets.workload_step)
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
        """Compose the step-1 resource set and export the XP-8 values (FR-34).

        Every plane is credential-free: seeded secret metadata, the network
        with the bootstrap-job SG, DocumentDB with the managed password and the
        plain MONGODB-AWS URL, the queues, and ECS services at zero tasks. A
        step-2 contract renders the same set until each step-2 story adds its
        resources; the guard refuses those types at step 1.
        """
        opts = pulumi.ResourceOptions(
            parent=self,
            transformations=[_step_guard(secrets.workload_step), self._tag_resource],
        )
        self.runtime_secrets = RuntimeSecrets(
            "runtime-secrets", descriptor=secrets, opts=opts
        )
        self.network = NetworkPlane(
            "network",
            settings=settings,
            private_gateway=True,
            bootstrap_job=True,
            opts=opts,
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
            initial_service_scale=INITIAL_SERVICE_SCALE,
            opts=opts,
        )
        self._export_xp8()

    def _export_xp8(self) -> None:
        """Export the non-deterministic XP-8 values in the contract's shape.

        A reviewed BI metadata PR copies them into ``central.lambda_network``
        and ``central.documentdb_managed_secret_arn`` after step 1 (XP-8).
        """
        pulumi.export(
            "lambda_network",
            {
                "subnet_ids": self.network.outputs.app_subnet_ids,
                "bootstrap_job_security_group_id": (
                    self.network.outputs.bootstrap_job_security_group_id
                ),
            },
        )
        pulumi.export(
            "documentdb_managed_secret_arn",
            self.data.documentdb.managed_secret_arn,
        )

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
