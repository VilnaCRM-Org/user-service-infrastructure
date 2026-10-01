"""Compute plane for ECS, ALB, and runtime secret delivery."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional, cast
from urllib.parse import parse_qsl, urlsplit

import pulumi_aws as aws

import pulumi
from app.access_logs import AlbAccessLogs
from app.data import DataPlane
from app.environment import (
    StackSettings,
    build_resource_name,
    require_application_secrets,
    validate_health_check_runtime,
    validate_runtime_roles,
)
from app.messaging import MessagingPlane
from app.network import NetworkPlane
from app.registry import RegistryOutputs
from app.runtime_secrets import RuntimeSecrets, require_unversioned_reference

__all__ = ["ComputePlane"]

# Release images are pushed with immutable sha- tags and stay available for
# rollback; only untagged leftovers (failed or superseded pushes) expire.
UNTAGGED_IMAGE_EXPIRY_DAYS = 14
# Apply fails when ECS never reaches steady state instead of reporting success
# with flapping tasks. The web and worker services each wait up to this bound.
# The whole first create must finish within 55 minutes (every service-transport
# `pulumi up`, registry and workload, has the 3300 s process timeout
# <= 3600 s STS session <= test_apply job timeout in
# self-deploy.yml); if a measured first create is longer, a bootstrap
# MaxSessionDuration increase plus role-duration-seconds is required first
# (see tests/unit/test_apply_timeout_budget.py and specs/poc/README.md).
SERVICE_STEADY_STATE_MINUTES = 10
SERVICE_STEADY_STATE_TIMEOUT = f"{SERVICE_STEADY_STATE_MINUTES}m"
# Docker's default Linux capability set, which Fargate grants unless dropped.
DEFAULT_CAPABILITIES = (
    "AUDIT_WRITE",
    "CHOWN",
    "DAC_OVERRIDE",
    "FOWNER",
    "FSETID",
    "KILL",
    "MKNOD",
    "NET_BIND_SERVICE",
    "NET_RAW",
    "SETFCAP",
    "SETGID",
    "SETPCAP",
    "SETUID",
    "SYS_CHROOT",
)
# The FrankenPHP binary carries cap_net_bind_service=+ep to bind :80, and PHP
# preloads as opcache.preload_user=www-data, which needs SETUID/SETGID. Fargate can
# add back only SYS_PTRACE, so the web container drops every other default
# capability; the PHP CLI worker drops them all.
WEB_REQUIRED_CAPABILITIES = frozenset({"NET_BIND_SERVICE", "SETGID", "SETUID"})
WEB_DROPPED_CAPABILITIES = [
    capability
    for capability in DEFAULT_CAPABILITIES
    if capability not in WEB_REQUIRED_CAPABILITIES
]
WORKER_DROPPED_CAPABILITIES = ["ALL"]
# The root filesystem is read-only. These ephemeral task-storage volumes cover
# every path the image entrypoint, PHP, Caddy and supervisord write; PHP and
# supervisord temporary files use TMPDIR inside the application var volume.
APPLICATION_TMPDIR = "/srv/app/var/tmp"
WEB_WRITABLE_PATHS = (
    ("app-var", "/srv/app/var"),
    ("caddy-data", "/data"),
    ("caddy-config", "/config"),
)
WORKER_WRITABLE_PATHS = (
    ("app-var", "/srv/app/var"),
    ("run", "/run"),
)
# supervisord otherwise writes its log and pid file into the read-only WORKDIR.
WORKER_RUNTIME_COMMAND = (
    "/usr/bin/supervisord -c /etc/supervisor/supervisord.conf "
    "-l /srv/app/var/log/supervisord.log -j /srv/app/var/run/supervisord.pid"
)
# Parent directories of every path the runtime command writes; the bootstrap
# creates them before exec because the ephemeral volumes start empty.
RUNTIME_WRITABLE_DIRECTORIES = ("/srv/app/var/log", "/srv/app/var/run")
# Step 1 creates both hardened services at zero tasks; only the step-2 one-time
# start action scales them, after the seed and rotation exist (FR-34, AD-18).
INITIAL_SERVICE_SCALE = 0
# AWS access key IDs (long-term, temporary and service-specific prefixes).
_ACCESS_KEY_ID = re.compile(
    r"(?<![A-Z0-9])(?:AKIA|ASIA|ABIA|ACCA|AGPA|AIDA|AROA)[A-Z0-9]{16}(?![A-Z0-9])"
)
# DSN query parameters that would carry a credential, such as the Symfony SQS
# ``access_key`` and ``secret_key`` or a SigV4 presigned ``X-Amz-Credential``.
CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "access_key",
        "access_key_id",
        "accesskey",
        "api_key",
        "apikey",
        "passwd",
        "password",
        "pwd",
        "secret",
        "secret_access_key",
        "secret_key",
        "secretkey",
        "security_token",
        "session_token",
        "token",
        "x_amz_credential",
        "x_amz_security_token",
        "x_amz_signature",
    }
)


def require_credential_free(value: Any) -> str:
    """Refuse an environment value or DSN that carries a credential (FR-03, AD-20).

    AWS clients use the task role, so no value may hold an access key, URL
    userinfo or a credential query parameter. A value that is not a plain
    string fails closed.
    """
    if type(value) is not str:
        raise ValueError("Workload environment value must be a plain string")
    if _ACCESS_KEY_ID.search(value):
        raise ValueError("Workload environment value carries an AWS access key")
    parts = urlsplit(value)
    if "@" in parts.netloc:
        raise ValueError("Workload DSN must not carry userinfo")
    if any(
        key.lower().replace("-", "_") in CREDENTIAL_QUERY_KEYS
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    ):
        raise ValueError("Workload DSN must not carry a credential parameter")
    return value


# The hardened containers reach Redis through these two equal plain URLs.
REDIS_URL_NAMES = frozenset({"REDIS_URL", "REDIS_LOCKOUT_URL"})
REDIS_IAM_SCHEME = "rediss://"


def _valid_endpoint(parts) -> bool:
    """A non-empty host and, when present, a port in 1-65535 (N1)."""
    try:
        port = parts.port
    except ValueError:
        return False
    return bool(parts.hostname) and (port is None or port > 0)


def _require_iam_redis_urls(values: dict[str, str]) -> None:
    """Hold the hardened Redis URLs to the plain IAM shape (FR-04, FR-08 B).

    Both URLs are plain rows; since plain and secret names are disjoint,
    neither can be a ``secrets`` row. The URL is ``rediss://`` with a host and
    no path, query or fragment (``redis_iam_url``); ``hostname`` must be
    non-empty and any port a valid 1-65535 number (N1). Equality is checked by
    ``require_plain_environment`` for every shape.

    Duty (N2): the hardened task definition holds the Redis URLs in every
    container, so each container is held to this rule. A future hardened task
    definition or sidecar that does not use Redis must re-scope this
    per-container rule under review before it is added.
    """
    if not REDIS_URL_NAMES <= set(values):
        raise ValueError(
            "Hardened REDIS_URL and REDIS_LOCKOUT_URL must both be plain values (FR-08)"
        )
    url = values["REDIS_URL"]
    parts = urlsplit(url)
    if (
        not url.startswith(REDIS_IAM_SCHEME)
        or not _valid_endpoint(parts)
        or parts.path
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            "Hardened REDIS_URL must be a rediss:// URL with no path or query (FR-04)"
        )


def require_plain_environment(
    environment: list[dict[str, Any]],
    secrets: list[dict[str, Any]],
    *,
    unversioned: bool = False,
) -> None:
    """Keep plain environment names apart from secret names (FR-03, FR-08).

    Only ``secrets[].valueFrom`` may reference secret material (a log-driver
    ``secretOptions`` reference is refused by ``require_plain_containers``);
    every plain value must be credential-free and no name may be both plain and secret.
    A plain ``REDIS_LOCKOUT_URL`` must equal ``REDIS_URL`` (FR-08 B, S1.4).
    With ``unversioned`` (the hardened shape) both Redis URLs must be plain
    rows and the URL a bare ``rediss://`` endpoint (S1.4 gate F5).
    """
    names = [row["name"] for row in environment]
    if len(set(names)) != len(names) or set(names) & {row["name"] for row in secrets}:
        raise ValueError("Workload environment names overlap secret names")
    for row in environment:
        require_credential_free(row["value"])
    values = {row["name"]: row["value"] for row in environment}
    if unversioned:
        _require_iam_redis_urls(values)
    if "REDIS_LOCKOUT_URL" in values and (
        values["REDIS_LOCKOUT_URL"] != values.get("REDIS_URL")
    ):
        raise ValueError("REDIS_LOCKOUT_URL must equal REDIS_URL (FR-08)")


# The exact keys ``_container_definitions_json`` emits for one container. ECS
# decodes container definitions with case-insensitive JSON key matching, so a
# key outside this exact-case set, or two keys that differ only in case, could
# reach a field no check reads (FR-03, FR-08).
CONTAINER_KEYS = frozenset(
    {
        "command",
        "environment",
        "essential",
        "healthCheck",
        "image",
        "linuxParameters",
        "logConfiguration",
        "mountPoints",
        "name",
        "portMappings",
        "readonlyRootFilesystem",
        "secrets",
    }
)
ENVIRONMENT_ROW_KEYS = frozenset({"name", "value"})
SECRET_ROW_KEYS = frozenset({"name", "valueFrom"})
# The log configuration ``_container_definitions_json`` emits: the awslogs
# driver with its three options, and no ``secretOptions`` (FR-03).
LOG_DRIVER = "awslogs"
LOG_CONFIGURATION_KEYS = frozenset({"logDriver", "options"})
LOG_OPTION_KEYS = frozenset(
    {"awslogs-group", "awslogs-region", "awslogs-stream-prefix"}
)


def _require_awslogs_configuration(log: Any) -> None:
    """Accept only the closed awslogs shape, with no secret options (FR-03)."""
    if (
        type(log) is not dict
        or set(log) != LOG_CONFIGURATION_KEYS
        or log["logDriver"] != LOG_DRIVER
        or type(log["options"]) is not dict
        or not set(log["options"]) <= LOG_OPTION_KEYS
    ):
        raise ValueError("Workload log configuration must be the closed awslogs shape")


def _require_unversioned_value_from(value: Any) -> None:
    """Hold every ``valueFrom`` found anywhere in the tree to the bare ARN shape.

    Defence in depth: the closed keys leave no such field outside
    ``secrets[]``, so this only fires if a future key set admits one.
    """
    if type(value) is list:
        for item in value:
            _require_unversioned_value_from(item)
    elif type(value) is dict:
        for key, item in value.items():
            if key.casefold() == "valuefrom":
                require_unversioned_reference(item)
            else:
                _require_unversioned_value_from(item)


def _closed_rows(rows: Any, keys: frozenset[str]) -> list[dict[str, Any]]:
    """Accept only a list of exact-key rows with a plain string name."""
    if type(rows) is not list or not all(
        type(row) is dict and set(row) == keys and type(row["name"]) is str
        for row in rows
    ):
        raise ValueError("Workload container rows must be closed name pairs")
    return rows


def _require_credential_free_tree(value: Any, exempt: str = "") -> None:
    """Scan every map key and string leaf; skip only the value under ``exempt``."""
    if type(value) is str:
        require_credential_free(value)
    elif type(value) is list:
        for item in value:
            _require_credential_free_tree(item)
    elif type(value) is dict:
        folded = {require_credential_free(key).casefold() for key in value}
        if len(folded) != len(value):
            raise ValueError("Workload container repeats a key in another case")
        for key, item in value.items():
            if key != exempt:
                _require_credential_free_tree(item)


def require_plain_containers(containers: Any, *, unversioned: bool) -> None:
    """Refuse container definitions that could carry secret material (FR-03).

    Keys are the closed exact-case set the compute plane emits; environment
    and secret rows are closed name pairs with disjoint names; every key and
    string leaf except ``secrets[].valueFrom`` is credential-free. With
    ``unversioned`` (the hardened shape) each ``valueFrom`` must be a bare
    secret ARN (S1.7); the pre-hardening shape stays version-pinned (AD-25).
    ``logConfiguration`` is the closed awslogs shape with the three emitted
    option keys and no ``secretOptions``; any other ``valueFrom`` in the tree
    gets the same bare-ARN check when ``unversioned``, as do the two plain
    Redis URLs (``require_plain_environment``).
    The guard and ``ComputePlane`` apply this one check, so they agree.
    """
    if type(containers) is not list:
        raise ValueError("Workload container definitions must be a list")
    for container in containers:
        if type(container) is not dict or not set(container) <= CONTAINER_KEYS:
            raise ValueError("Workload container holds an unreviewed key")
        environment = _closed_rows(
            container.get("environment", []), ENVIRONMENT_ROW_KEYS
        )
        secrets = _closed_rows(container.get("secrets", []), SECRET_ROW_KEYS)
        require_plain_environment(environment, secrets, unversioned=unversioned)
        _require_credential_free_tree({**container, "secrets": None})
        if "logConfiguration" in container:
            _require_awslogs_configuration(container["logConfiguration"])
        if unversioned:
            _require_unversioned_value_from({**container, "secrets": None})
        for row in secrets:
            _require_credential_free_tree(row, exempt="valueFrom")
            if unversioned:
                require_unversioned_reference(row["valueFrom"])


@dataclass(frozen=True)
class ComputeOutputs:
    """Compute-plane outputs exported by the stack."""

    cluster_name: pulumi.Input[str]
    load_balancer_dns_name: pulumi.Input[str]
    service_url: pulumi.Input[str]
    web_repository_url: pulumi.Input[str]
    worker_repository_url: pulumi.Input[str]
    web_service_name: pulumi.Input[str]
    worker_service_name: pulumi.Input[str]


def _task_volumes(
    writable_paths: tuple[tuple[str, str], ...],
) -> list[aws.ecs.TaskDefinitionVolumeArgs]:
    """Declare one Fargate ephemeral volume per writable container path."""
    return [aws.ecs.TaskDefinitionVolumeArgs(name=name) for name, _ in writable_paths]


def _service_timeouts() -> pulumi.CustomTimeouts:
    """Bound ECS steady-state waits for service creation and deployments."""
    return pulumi.CustomTimeouts(
        create=SERVICE_STEADY_STATE_TIMEOUT, update=SERVICE_STEADY_STATE_TIMEOUT
    )


class ComputePlane(pulumi.ComponentResource):
    """Provision ECS/Fargate, ALB and runtime secrets using caller-owned registries."""

    outputs: ComputeOutputs
    _runtime_secrets: RuntimeSecrets | None = None
    _hardened = False
    _initial_service_scale: int | None = None

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        network: NetworkPlane,
        data: DataPlane,
        messaging: MessagingPlane,
        registries: RegistryOutputs | None = None,
        runtime_secrets: RuntimeSecrets | None = None,
        initial_service_scale: int | None = None,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Build preview-safe outputs or provision the managed compute plane.

        ``initial_service_scale`` overrides both desired counts; the hardened
        step-1 shape requires exactly ``INITIAL_SERVICE_SCALE`` (FR-34).
        """
        if settings.is_managed:
            validate_runtime_roles(settings.runtime, settings.environment)
            validate_health_check_runtime(settings.runtime, settings.queues)
            if runtime_secrets is None:
                require_application_secrets(settings)
            else:
                runtime_secrets.descriptor.validate_target(settings)
        self._hardened = (
            runtime_secrets is not None and runtime_secrets.descriptor.hardened
        )
        if self._hardened and initial_service_scale != INITIAL_SERVICE_SCALE:
            raise ValueError("Hardened workload services start at zero tasks (FR-34)")
        self._runtime_secrets = runtime_secrets
        self._initial_service_scale = initial_service_scale
        super().__init__("user-service-infrastructure:compute:Plane", name, None, opts)

        self.outputs = (
            self._build_managed_outputs(settings, network, data, messaging, registries)
            if settings.is_managed
            else self._build_preview_outputs(settings)
        )
        self.register_outputs(
            {
                "clusterName": self.outputs.cluster_name,
                "loadBalancerDnsName": self.outputs.load_balancer_dns_name,
                "serviceUrl": self.outputs.service_url,
                "webRepositoryUrl": self.outputs.web_repository_url,
                "workerRepositoryUrl": self.outputs.worker_repository_url,
                "webServiceName": self.outputs.web_service_name,
                "workerServiceName": self.outputs.worker_service_name,
            }
        )

    def _build_preview_outputs(self, settings: StackSettings) -> ComputeOutputs:
        """Return stable placeholders for preview mode."""
        return ComputeOutputs(
            cluster_name=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "ecs")
            ),
            load_balancer_dns_name=pulumi.Output.from_input(
                f"{build_resource_name(settings.stack_tag, 'alb')}.elb.amazonaws.com"
            ),
            service_url=pulumi.Output.from_input(settings.runtime.api_base_url),
            web_repository_url=pulumi.Output.from_input(
                f"123456789012.dkr.ecr.{settings.region}.amazonaws.com/"
                f"{settings.images.web_repository_name}"
            ),
            worker_repository_url=pulumi.Output.from_input(
                f"123456789012.dkr.ecr.{settings.region}.amazonaws.com/"
                f"{settings.images.worker_repository_name}"
            ),
            web_service_name=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "web")
            ),
            worker_service_name=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "worker")
            ),
        )

    def _build_managed_outputs(
        self,
        settings: StackSettings,
        network: NetworkPlane,
        data: DataPlane,
        messaging: MessagingPlane,
        registries: RegistryOutputs | None,
    ) -> ComputeOutputs:
        """Provision the managed compute plane."""
        if registries is None:
            raise ValueError("Managed compute requires caller-owned registry outputs")
        self._create_repository_lifecycle(
            logical_name="web-repository",
            repository_name=registries.web.name,
        )
        self._create_repository_lifecycle(
            logical_name="worker-repository",
            repository_name=registries.worker.name,
        )

        cluster = aws.ecs.Cluster(
            "user-service-ecs-cluster",
            name=build_resource_name(settings.stack_tag, "ecs", max_length=255),
            settings=[
                aws.ecs.ClusterSettingArgs(
                    name="containerInsights",
                    value="enhanced",
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )

        web_log_group = aws.cloudwatch.LogGroup(
            "user-service-web-logs",
            name=f"/aws/ecs/{settings.stack_tag}/web",
            retention_in_days=30,
            opts=pulumi.ResourceOptions(parent=self),
        )
        worker_log_group = aws.cloudwatch.LogGroup(
            "user-service-worker-logs",
            name=f"/aws/ecs/{settings.stack_tag}/worker",
            retention_in_days=30,
            opts=pulumi.ResourceOptions(parent=self),
        )

        runtime_secrets = (
            {}
            if self._runtime_secrets is not None
            else self._create_runtime_secrets(settings)
        )
        web_image = self._resolve_image_uri(
            repository_url=registries.web.uri,
            image_tag=settings.images.web_image_tag,
            override=settings.images.web_image_override,
        )
        worker_image = self._resolve_image_uri(
            repository_url=registries.worker.uri,
            image_tag=settings.images.worker_image_tag,
            override=settings.images.worker_image_override,
        )

        access_logs_bucket, access_logs_dependencies = self._access_logs(settings)
        private_gateway = network.outputs.vpc_link_security_group_id is not None
        load_balancer = aws.lb.LoadBalancer(
            "user-service-alb",
            name=build_resource_name(settings.stack_tag, "alb", max_length=32),
            internal=private_gateway,
            load_balancer_type="application",
            security_groups=[network.outputs.alb_security_group_id],
            subnets=(
                network.outputs.app_subnet_ids
                if private_gateway
                else network.outputs.public_subnet_ids
            ),
            access_logs=aws.lb.LoadBalancerAccessLogsArgs(
                bucket=access_logs_bucket,
                enabled=True,
                prefix=f"{settings.stack_tag}/alb",
            ),
            drop_invalid_header_fields=True,
            idle_timeout=60,
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=access_logs_dependencies
            ),
        )

        target_group = aws.lb.TargetGroup(
            "user-service-target-group",
            name=build_resource_name(settings.stack_tag, "tg", max_length=32),
            port=settings.capacity.container_port,
            protocol="HTTP",
            target_type="ip",
            vpc_id=network.outputs.vpc_id,
            health_check=aws.lb.TargetGroupHealthCheckArgs(
                enabled=True,
                path=settings.capacity.health_check_path,
                protocol="HTTP",
                matcher="200-399",
                healthy_threshold=2,
                unhealthy_threshold=3,
                interval=30,
                timeout=5,
            ),
            deregistration_delay=30,
            opts=pulumi.ResourceOptions(parent=self),
        )

        http_listener = self._create_http_listener(
            settings,
            load_balancer,
            target_group,
            private_gateway=private_gateway,
        )

        web_task_definition = aws.ecs.TaskDefinition(
            "user-service-web-task",
            family=build_resource_name(settings.stack_tag, "web", max_length=255),
            cpu=settings.capacity.web_cpu,
            memory=settings.capacity.web_memory,
            network_mode="awsvpc",
            requires_compatibilities=["FARGATE"],
            runtime_platform=aws.ecs.TaskDefinitionRuntimePlatformArgs(
                cpu_architecture="X86_64", operating_system_family="LINUX"
            ),
            execution_role_arn=settings.runtime.execution_role_arn,
            task_role_arn=settings.runtime.task_role_arn,
            volumes=_task_volumes(WEB_WRITABLE_PATHS),
            container_definitions=self._web_container_definitions(
                settings=settings,
                image=web_image,
                log_group_name=web_log_group.name,
                data=data,
                messaging=messaging,
                runtime_secret_arns=runtime_secrets,
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        worker_task_definition = aws.ecs.TaskDefinition(
            "user-service-worker-task",
            family=build_resource_name(settings.stack_tag, "worker", max_length=255),
            cpu=settings.capacity.worker_cpu,
            memory=settings.capacity.worker_memory,
            network_mode="awsvpc",
            requires_compatibilities=["FARGATE"],
            runtime_platform=aws.ecs.TaskDefinitionRuntimePlatformArgs(
                cpu_architecture="X86_64", operating_system_family="LINUX"
            ),
            execution_role_arn=settings.runtime.execution_role_arn,
            task_role_arn=settings.runtime.task_role_arn,
            volumes=_task_volumes(WORKER_WRITABLE_PATHS),
            container_definitions=self._worker_container_definitions(
                settings=settings,
                image=worker_image,
                log_group_name=worker_log_group.name,
                data=data,
                messaging=messaging,
                runtime_secret_arns=runtime_secrets,
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        web_service = aws.ecs.Service(
            "user-service-web-service",
            name=build_resource_name(settings.stack_tag, "web", max_length=255),
            cluster=cluster.arn,
            task_definition=web_task_definition.arn,
            desired_count=self._desired_count(settings.capacity.web_desired_count),
            launch_type="FARGATE",
            platform_version="LATEST",
            enable_execute_command=False,
            enable_ecs_managed_tags=True,
            propagate_tags="SERVICE",
            health_check_grace_period_seconds=180,
            deployment_circuit_breaker=aws.ecs.ServiceDeploymentCircuitBreakerArgs(
                enable=True,
                rollback=True,
            ),
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                assign_public_ip=False,
                security_groups=[network.outputs.service_security_group_id],
                subnets=network.outputs.app_subnet_ids,
            ),
            load_balancers=[
                aws.ecs.ServiceLoadBalancerArgs(
                    container_name="user-service-web",
                    container_port=settings.capacity.container_port,
                    target_group_arn=target_group.arn,
                )
            ],
            wait_for_steady_state=True,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[http_listener, *self._documentdb_instances(data)],
                custom_timeouts=_service_timeouts(),
            ),
        )

        worker_service = aws.ecs.Service(
            "user-service-worker-service",
            name=build_resource_name(settings.stack_tag, "worker", max_length=255),
            cluster=cluster.arn,
            task_definition=worker_task_definition.arn,
            desired_count=self._desired_count(settings.capacity.worker_desired_count),
            launch_type="FARGATE",
            platform_version="LATEST",
            enable_execute_command=False,
            enable_ecs_managed_tags=True,
            propagate_tags="SERVICE",
            deployment_circuit_breaker=aws.ecs.ServiceDeploymentCircuitBreakerArgs(
                enable=True,
                rollback=True,
            ),
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                assign_public_ip=False,
                security_groups=[network.outputs.service_security_group_id],
                subnets=network.outputs.app_subnet_ids,
            ),
            wait_for_steady_state=True,
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=list(self._documentdb_instances(data)),
                custom_timeouts=_service_timeouts(),
            ),
        )

        return ComputeOutputs(
            cluster_name=cluster.name,
            load_balancer_dns_name=load_balancer.dns_name,
            service_url=pulumi.Output.from_input(settings.runtime.api_base_url),
            web_repository_url=registries.web.uri,
            worker_repository_url=registries.worker.uri,
            web_service_name=web_service.name,
            worker_service_name=worker_service.name,
        )

    def _desired_count(self, configured: int) -> int:
        """Return the step-1 scale when one is set, else the configured count."""
        if self._initial_service_scale is None:
            return configured
        return self._initial_service_scale

    def _documentdb_instances(self, data: DataPlane) -> tuple[pulumi.Resource, ...]:
        """Return the instances ECS waits for; the endpoint alone is no edge."""
        if self._hardened:
            return data.documentdb.instances
        return data.outputs.documentdb_instances

    def _data_environment(
        self, settings: StackSettings, data: DataPlane
    ) -> list[dict[str, pulumi.Input[str]]]:
        """Pass the hardened data-plane IAM values as plain env (S1.3, S1.4).

        MONGODB-AWS (FR-02) and Redis IAM (FR-04): ``REDIS_URL`` and
        ``REDIS_LOCKOUT_URL`` are the same credential-free ``rediss://`` URL;
        the token signer needs the user ID, the lower-case replication-group
        ID and the region.
        """
        if not self._hardened:
            return []
        redis = data.redis
        return [
            {"name": "MONGODB_URL", "value": data.documentdb.mongodb_url},
            {"name": "REDIS_URL", "value": redis.url},
            {"name": "REDIS_LOCKOUT_URL", "value": redis.url},
            {"name": "REDIS_IAM_USER_ID", "value": redis.iam_user_id},
            {
                "name": "REDIS_REPLICATION_GROUP_ID",
                "value": redis.replication_group_id,
            },
            {"name": "AWS_REGION", "value": settings.region},
        ]

    def _create_repository_lifecycle(
        self,
        *,
        logical_name: str,
        repository_name: pulumi.Input[str],
    ) -> None:
        """Expire only untagged images; tagged sha- releases stay for rollback."""
        aws.ecr.LifecyclePolicy(
            f"user-service-{logical_name}-lifecycle",
            repository=repository_name,
            policy=json.dumps(
                {
                    "rules": [
                        {
                            "rulePriority": 1,
                            "description": (
                                "Expire untagged images; tagged sha- release "
                                "images are retained."
                            ),
                            "selection": {
                                "tagStatus": "untagged",
                                "countType": "sinceImagePushed",
                                "countUnit": "days",
                                "countNumber": UNTAGGED_IMAGE_EXPIRY_DAYS,
                            },
                            "action": {"type": "expire"},
                        }
                    ]
                }
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _create_runtime_secrets(
        self,
        settings: StackSettings,
    ) -> dict[str, pulumi.Input[str]]:
        """Persist application secrets to Secrets Manager for ECS injection."""
        material = require_application_secrets(settings)
        definitions = {
            "app-secret": material.app_secret,
            "mailer-dsn": material.mailer_dsn,
            "oauth-encryption-key": material.oauth_encryption_key,
            "oauth-passphrase": material.oauth_passphrase,
            "twofactor-encryption-key": material.two_factor_encryption_key,
            "oauth-private-key": material.oauth_private_key_pem,
            "oauth-public-key": material.oauth_public_key_pem,
            "github-client-secret": material.github_client_secret,
            "google-client-secret": material.google_client_secret,
            "facebook-client-secret": material.facebook_client_secret,
            "twitter-client-secret": material.twitter_client_secret,
        }
        secret_arns: dict[str, pulumi.Input[str]] = {}
        for key, value in definitions.items():
            secret = aws.secretsmanager.Secret(
                f"user-service-{key}",
                description=f"Runtime secret for {key}.",
                opts=pulumi.ResourceOptions(parent=self),
            )
            aws.secretsmanager.SecretVersion(
                f"user-service-{key}-version",
                secret_id=secret.id,
                secret_string=value,
                opts=pulumi.ResourceOptions(parent=self),
            )
            secret_arns[key] = secret.arn
        return secret_arns

    def _resolve_image_uri(
        self,
        *,
        repository_url: pulumi.Input[str],
        image_tag: str,
        override: str | None,
    ) -> pulumi.Input[str]:
        """Resolve either an explicit image or the managed ECR image URL."""
        if override is not None:
            return override
        return pulumi.Output.from_input(repository_url).apply(
            lambda url: f"{url}:{image_tag}"
        )

    def _create_http_listener(
        self,
        settings: StackSettings,
        load_balancer: aws.lb.LoadBalancer,
        target_group: aws.lb.TargetGroup,
        *,
        private_gateway: bool = False,
    ) -> aws.lb.Listener:
        """Create HTTP and optional HTTPS listeners."""
        if settings.runtime.certificate_arn is None:
            if private_gateway:
                raise ValueError(
                    "Private gateway listener requires an admitted certificate"
                )
            return aws.lb.Listener(
                "user-service-http-listener",
                load_balancer_arn=load_balancer.arn,
                port=80,
                protocol="HTTP",
                default_actions=[
                    aws.lb.ListenerDefaultActionArgs(
                        type="forward",
                        target_group_arn=target_group.arn,
                    )
                ],
                opts=pulumi.ResourceOptions(parent=self),
            )

        https_listener = aws.lb.Listener(
            "user-service-https-listener",
            load_balancer_arn=load_balancer.arn,
            port=443,
            protocol="HTTPS",
            certificate_arn=settings.runtime.certificate_arn,
            ssl_policy="ELBSecurityPolicy-TLS13-1-2-Res-2021-06",
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="forward",
                    target_group_arn=target_group.arn,
                )
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )
        if private_gateway:
            return https_listener
        return aws.lb.Listener(
            "user-service-http-listener",
            load_balancer_arn=load_balancer.arn,
            port=80,
            protocol="HTTP",
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="redirect",
                    redirect=aws.lb.ListenerDefaultActionRedirectArgs(
                        port="443",
                        protocol="HTTPS",
                        status_code="HTTP_301",
                    ),
                )
            ],
            opts=pulumi.ResourceOptions(parent=self, depends_on=[https_listener]),
        )

    def _web_container_definitions(
        self,
        *,
        settings: StackSettings,
        image: pulumi.Input[str],
        log_group_name: pulumi.Input[str],
        data: DataPlane,
        messaging: MessagingPlane,
        runtime_secret_arns: dict[str, pulumi.Input[str]],
    ) -> pulumi.Output[str]:
        """Build the ECS container definition for the public API."""
        return self._container_definitions_json(
            name="user-service-web",
            command=[
                "/bin/sh",
                "-ec",
                self._bootstrap_command("frankenphp run --config /etc/caddy/Caddyfile"),
            ],
            image=image,
            region=settings.region,
            log_group_name=log_group_name,
            environment=self._common_environment(
                settings,
                messaging,
                include_worker_name=False,
            )
            + self._trusted_proxy_environment()
            + self._data_environment(settings, data),
            secrets=self._common_secrets(data, runtime_secret_arns),
            port_mappings=[
                {
                    "containerPort": settings.capacity.container_port,
                    "hostPort": settings.capacity.container_port,
                    "protocol": "tcp",
                }
            ],
            writable_paths=WEB_WRITABLE_PATHS,
            dropped_capabilities=WEB_DROPPED_CAPABILITIES,
        )

    def _trusted_proxy_environment(self) -> list[dict[str, pulumi.Input[str]]]:
        """Format one validated list for Symfony and Caddy's distinct parsers."""
        if self._runtime_secrets is None:
            return []
        cidrs = self._runtime_secrets.descriptor.trusted_proxy_cidrs
        return [
            {"name": "TRUSTED_PROXIES", "value": ",".join(cidrs)},
            {"name": "TRUSTED_PROXY_CIDRS", "value": " ".join(cidrs)},
        ]

    def _access_logs(
        self, settings: StackSettings
    ) -> tuple[pulumi.Input[str] | None, list[pulumi.Resource]]:
        """Preserve legacy external storage; generated workload owns its log bucket."""
        if self._runtime_secrets is None:
            return settings.runtime.access_logs_bucket_name, []
        self._runtime_secrets.descriptor.validate_target(settings)
        logs = AlbAccessLogs(
            "access-logs",
            settings=settings,
            account_id=self._runtime_secrets.descriptor.account_id,
            opts=pulumi.ResourceOptions(parent=self),
        )
        return logs.bucket.bucket, [logs.policy]

    def _worker_container_definitions(
        self,
        *,
        settings: StackSettings,
        image: pulumi.Input[str],
        log_group_name: pulumi.Input[str],
        data: DataPlane,
        messaging: MessagingPlane,
        runtime_secret_arns: dict[str, pulumi.Input[str]],
    ) -> pulumi.Output[str]:
        """Build the ECS container definition for the worker fleet."""
        return self._container_definitions_json(
            name="user-service-worker",
            command=[
                "/bin/sh",
                "-ec",
                self._bootstrap_command(WORKER_RUNTIME_COMMAND),
            ],
            image=image,
            region=settings.region,
            log_group_name=log_group_name,
            environment=self._common_environment(
                settings,
                messaging,
                include_worker_name=True,
            )
            + self._data_environment(settings, data),
            secrets=self._common_secrets(data, runtime_secret_arns),
            port_mappings=None,
            writable_paths=WORKER_WRITABLE_PATHS,
            dropped_capabilities=WORKER_DROPPED_CAPABILITIES,
            health_check=(
                {
                    "command": [
                        "CMD",
                        *self._runtime_secrets.descriptor.worker_health_command,
                    ],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60,
                }
                if self._runtime_secrets is not None
                else None
            ),
        )

    def _container_definitions_json(
        self,
        *,
        name: str,
        command: list[str],
        image: pulumi.Input[str],
        region: str,
        log_group_name: pulumi.Input[str],
        environment: list[dict[str, pulumi.Input[str]]],
        secrets: list[dict[str, pulumi.Input[str]]],
        port_mappings: list[dict[str, Any]] | None,
        writable_paths: tuple[tuple[str, str], ...],
        dropped_capabilities: list[str],
        health_check: dict[str, Any] | None = None,
    ) -> pulumi.Output[str]:
        """Serialize a hardened single-container task definition."""
        return pulumi.Output.all(
            image,
            pulumi.Output.from_input(environment),
            pulumi.Output.from_input(secrets),
            log_group_name,
        ).apply(
            lambda parts: self._serialize_container(
                unversioned=self._hardened,
                containers=[
                    {
                        "name": name,
                        "image": parts[0],
                        "essential": True,
                        "command": command,
                        "environment": parts[1],
                        "secrets": parts[2],
                        "portMappings": port_mappings or [],
                        "readonlyRootFilesystem": True,
                        "mountPoints": [
                            {
                                "sourceVolume": volume,
                                "containerPath": path,
                                "readOnly": False,
                            }
                            for volume, path in writable_paths
                        ],
                        "linuxParameters": {
                            "capabilities": {"drop": dropped_capabilities}
                        },
                        **({"healthCheck": health_check} if health_check else {}),
                        "logConfiguration": {
                            "logDriver": "awslogs",
                            "options": {
                                "awslogs-group": parts[3],
                                "awslogs-region": region,
                                "awslogs-stream-prefix": name,
                            },
                        },
                    }
                ],
            )
        )

    @staticmethod
    def _serialize_container(
        containers: list[dict[str, Any]], *, unversioned: bool
    ) -> str:
        """Serialize after the checks the guard repeats on the JSON (FR-03)."""
        require_plain_containers(containers, unversioned=unversioned)
        return json.dumps(containers)

    def _common_environment(
        self,
        settings: StackSettings,
        messaging: MessagingPlane,
        *,
        include_worker_name: bool,
    ) -> list[dict[str, pulumi.Input[str]]]:
        """Build the non-secret environment variables shared by both workloads."""
        environment: list[dict[str, pulumi.Input[str]]] = [
            {"name": "APP_ENV", "value": settings.runtime.app_env},
            {"name": "APP_DEBUG", "value": settings.runtime.app_debug},
            {"name": "API_BASE_URL", "value": settings.runtime.api_base_url},
            {"name": "API_URL", "value": settings.runtime.api_url},
            {"name": "CORS_ALLOW_ORIGIN", "value": settings.runtime.cors_allow_origin},
            {"name": "MAIL_SENDER", "value": settings.runtime.mail_sender},
            {"name": "JWT_ISSUER", "value": settings.runtime.jwt_issuer},
            {"name": "JWT_AUDIENCE", "value": settings.runtime.jwt_audience},
            {"name": "AWS_EMF_NAMESPACE", "value": settings.runtime.emf_namespace},
            {"name": "TMPDIR", "value": APPLICATION_TMPDIR},
            {"name": "AWS_SQS_VERSION", "value": "latest"},
            {"name": "AWS_SQS_REGION", "value": settings.region},
            {
                "name": "AWS_SQS_ENDPOINT_BASE",
                "value": settings.runtime.aws_sqs_endpoint_base,
            },
            {"name": "LOCALSTACK_PORT", "value": settings.runtime.aws_sqs_port},
            {
                "name": "OAUTH_PRIVATE_KEY",
                "value": "/srv/app/var/run/secrets/oauth-private.pem",
            },
            {
                "name": "OAUTH_PUBLIC_KEY",
                "value": "/srv/app/var/run/secrets/oauth-public.pem",
            },
            {
                "name": "OAUTH_GITHUB_CLIENT_ID",
                "value": settings.social.github_client_id,
            },
            {
                "name": "OAUTH_GITHUB_REDIRECT_URI",
                "value": settings.social.github_redirect_uri,
            },
            {
                "name": "OAUTH_GOOGLE_CLIENT_ID",
                "value": settings.social.google_client_id,
            },
            {
                "name": "OAUTH_GOOGLE_REDIRECT_URI",
                "value": settings.social.google_redirect_uri,
            },
            {
                "name": "OAUTH_FACEBOOK_CLIENT_ID",
                "value": settings.social.facebook_client_id,
            },
            {
                "name": "OAUTH_FACEBOOK_REDIRECT_URI",
                "value": settings.social.facebook_redirect_uri,
            },
            {
                "name": "OAUTH_FACEBOOK_GRAPH_API_VERSION",
                "value": settings.social.facebook_graph_api_version,
            },
            {
                "name": "OAUTH_TWITTER_CLIENT_ID",
                "value": settings.social.twitter_client_id,
            },
            {
                "name": "OAUTH_TWITTER_REDIRECT_URI",
                "value": settings.social.twitter_redirect_uri,
            },
            {
                "name": "SEND_EMAIL_TRANSPORT_DSN",
                "value": self._queue_dsn(
                    messaging.outputs.queue_urls["sendEmail"],
                    settings.region,
                ),
            },
            {
                "name": "FAILED_EMAIL_TRANSPORT_DSN",
                "value": self._queue_dsn(
                    messaging.outputs.queue_urls["failedSendEmail"],
                    settings.region,
                ),
            },
            {
                "name": "INSERT_USER_BATCH_TRANSPORT_DSN",
                "value": self._queue_dsn(
                    messaging.outputs.queue_urls["insertUserBatch"],
                    settings.region,
                ),
            },
            {
                "name": "DOMAIN_EVENTS_TRANSPORT_DSN",
                "value": self._queue_dsn(
                    messaging.outputs.queue_urls["domainEvents"],
                    settings.region,
                ),
            },
            {
                "name": "FAILED_DOMAIN_EVENTS_TRANSPORT_DSN",
                "value": self._queue_dsn(
                    messaging.outputs.queue_urls["failedDomainEvents"],
                    settings.region,
                ),
            },
        ]
        if include_worker_name:
            environment.append(
                {
                    "name": "MESSENGER_CONSUMER_NAME",
                    "value": build_resource_name(
                        settings.stack_tag,
                        "worker-consumer",
                        max_length=64,
                    ),
                }
            )
        if self._runtime_secrets is not None:
            descriptor = self._runtime_secrets.descriptor
            environment = [
                item
                for item in environment
                if item["name"] != "MAIL_SENDER"
                and not cast(str, item["name"]).startswith(
                    (
                        "OAUTH_GITHUB_",
                        "OAUTH_GOOGLE_",
                        "OAUTH_FACEBOOK_",
                        "OAUTH_TWITTER_",
                    )
                )
            ]
            environment.extend(
                [
                    {"name": "MAIL_SENDER", "value": descriptor.mail_sender},
                    {"name": "MAILER_DSN", "value": descriptor.mailer_dsn},
                    {"name": "SOCIAL_OAUTH_ENABLED", "value": "false"},
                    {"name": "OAUTH_ENCRYPTION_KEY_TYPE", "value": "plain"},
                ]
            )
        return environment

    def _common_secrets(
        self,
        data: DataPlane,
        runtime_secret_arns: dict[str, pulumi.Input[str]],
    ) -> list[dict[str, pulumi.Input[str]]]:
        """Build the ECS secrets mapping used by both services."""
        if self._runtime_secrets is not None:
            return self._runtime_secrets.ecs_secrets()
        return [
            {
                "name": "MONGODB_URL",
                "valueFrom": data.outputs.documentdb_url_secret_arn,
            },
            {"name": "REDIS_URL", "valueFrom": data.outputs.redis_url_secret_arn},
            {"name": "APP_SECRET", "valueFrom": runtime_secret_arns["app-secret"]},
            {"name": "MAILER_DSN", "valueFrom": runtime_secret_arns["mailer-dsn"]},
            {
                "name": "OAUTH_ENCRYPTION_KEY",
                "valueFrom": runtime_secret_arns["oauth-encryption-key"],
            },
            {
                "name": "OAUTH_PASSPHRASE",
                "valueFrom": runtime_secret_arns["oauth-passphrase"],
            },
            {
                "name": "TWO_FACTOR_ENCRYPTION_KEY",
                "valueFrom": runtime_secret_arns["twofactor-encryption-key"],
            },
            {
                "name": "OAUTH_PRIVATE_KEY_PEM",
                "valueFrom": runtime_secret_arns["oauth-private-key"],
            },
            {
                "name": "OAUTH_PUBLIC_KEY_PEM",
                "valueFrom": runtime_secret_arns["oauth-public-key"],
            },
            {
                "name": "OAUTH_GITHUB_CLIENT_SECRET",
                "valueFrom": runtime_secret_arns["github-client-secret"],
            },
            {
                "name": "OAUTH_GOOGLE_CLIENT_SECRET",
                "valueFrom": runtime_secret_arns["google-client-secret"],
            },
            {
                "name": "OAUTH_FACEBOOK_CLIENT_SECRET",
                "valueFrom": runtime_secret_arns["facebook-client-secret"],
            },
            {
                "name": "OAUTH_TWITTER_CLIENT_SECRET",
                "valueFrom": runtime_secret_arns["twitter-client-secret"],
            },
        ]

    def _bootstrap_command(self, runtime_command: str) -> str:
        """Write PEM material to files before launching the container process."""
        return (
            "set -eu; "
            "install -d -m 700 /srv/app/var/run/secrets; "
            f"install -d -m 1777 {APPLICATION_TMPDIR}; "
            f"install -d -m 755 {' '.join(RUNTIME_WRITABLE_DIRECTORIES)}; "
            'printf "%s" "$OAUTH_PRIVATE_KEY_PEM"'
            " > /srv/app/var/run/secrets/oauth-private.pem; "
            'printf "%s" "$OAUTH_PUBLIC_KEY_PEM"'
            " > /srv/app/var/run/secrets/oauth-public.pem; "
            "chmod 600 /srv/app/var/run/secrets/oauth-private.pem; "
            "chmod 644 /srv/app/var/run/secrets/oauth-public.pem; "
            f"exec {runtime_command}"
        )

    def _queue_dsn(
        self,
        queue_url: pulumi.Input[str],
        region: str,
    ) -> pulumi.Output[str]:
        """Build the credential-free Symfony SQS DSN from the full queue URL."""
        options = f"?region={region}&auto_setup=false"
        return pulumi.Output.from_input(queue_url).apply(
            lambda value: require_credential_free(value + options)
        )
