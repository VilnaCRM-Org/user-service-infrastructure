"""Managed data services for the user-service stack."""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from typing import Any, Optional, cast
from urllib.parse import quote, urlsplit

import pulumi_aws as aws

import pulumi
from app.environment import (
    StackSettings,
    build_resource_name,
    reject_documentdb_password_config,
    reject_redis_auth_token_config,
    require_application_secrets,
)
from app.network import NetworkPlane
from app.runtime_secrets import RuntimeSecrets, RuntimeSecretsDescriptor

__all__ = ["DataPlane"]

DOCUMENTDB_LOG_EXPORTS = ("audit", "profiler")
DOCUMENTDB_LOG_RETENTION_DAYS = 30
# TLS must not rely on the engine default; audit and profiler exports only emit
# events when the cluster parameter group enables them.
DOCUMENTDB_CLUSTER_PARAMETERS = {
    "tls": "enabled",
    "audit_logs": "enabled",
    "profiler": "enabled",
    "profiler_threshold_ms": "100",
}


# IAM (MONGODB-AWS) authentication exists only on instance-based DocumentDB 5.0
# clusters (A-01, V-17); any other engine version or an elastic cluster raises.
DOCUMENTDB_IAM_ENGINE_VERSION = "5.0.0"
# The task role authenticates through the ``$external`` source (FR-02, AD-01).
DOCUMENTDB_IAM_OPTIONS = (
    "replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    "&authSource=%24external&authMechanism=MONGODB-AWS"
)


# Redis IAM authentication (D-1, AD-02, V-9): Redis OSS 7.0 or later with
# in-transit encryption required. The engine stays Redis OSS (AS-2).
REDIS_ENGINE = "redis"
REDIS_IAM_MIN_MAJOR_VERSION = 7
REDIS_TRANSIT_ENCRYPTION_MODE = "required"
# Every Redis OSS user group must hold a user named ``default`` (V-5); this one
# is stack-scoped, needs no password and is disabled for every command.
REDIS_DEFAULT_USER_NAME = "default"
REDIS_DEFAULT_ACCESS_STRING = "off -@all"
REDIS_APP_ACCESS_STRING = "on ~* +@all -@dangerous"
_REDIS_ENGINE_VERSION = re.compile(r"([0-9]{1,3})\.[0-9]{1,3}(?:\.[0-9]{1,3})?")


def require_iam_redis_engine(engine_version: Any) -> None:
    """Refuse a Redis engine without IAM authentication (FR-04, V-9)."""
    match = (
        _REDIS_ENGINE_VERSION.fullmatch(engine_version)
        if type(engine_version) is str
        else None
    )
    if match is None or int(match.group(1)) < REDIS_IAM_MIN_MAJOR_VERSION:
        raise ValueError(
            "Redis IAM authentication requires Redis OSS "
            f"{REDIS_IAM_MIN_MAJOR_VERSION}.0 or later (V-9)"
        )


def redis_iam_url(endpoint: str, port: int) -> str:
    """Compose the plain ``rediss://`` URL; it may never carry userinfo.

    The task role signs a fresh IAM token per connection, so the URL holds no
    credential and ``REDIS_LOCKOUT_URL`` is the same value (FR-04, FR-08).
    """
    url = f"rediss://{endpoint}:{port}"
    if "@" in urlsplit(url).netloc:
        raise ValueError("REDIS_URL must not carry userinfo")
    return url


def redis_iam_identity(stack_tag: str) -> tuple[str, str, str, str]:
    """Return the replication-group, app-user, default-user and group IDs.

    ElastiCache stores user IDs in lower case and an IAM user's name must equal
    its ID (V-9), so the user and group IDs are lower-cased here. The
    replication-group ID keeps its configured case; the service lower-cases
    it, and the env value does so too (FR-04 B).
    """
    return (
        build_resource_name(stack_tag, "redis", max_length=40),
        build_resource_name(stack_tag, "app", max_length=40).lower(),
        build_resource_name(stack_tag, "redis-default", max_length=40).lower(),
        build_resource_name(stack_tag, "redis-users", max_length=40).lower(),
    )


def require_iam_documentdb_engine(engine_version: Any) -> None:
    """Refuse any engine but instance-based DocumentDB 5.0.0 (FR-02, V-17)."""
    if engine_version != DOCUMENTDB_IAM_ENGINE_VERSION:
        raise ValueError(
            "DocumentDB IAM authentication requires the instance-based "
            f"{DOCUMENTDB_IAM_ENGINE_VERSION} engine (V-17)"
        )


def documentdb_iam_url(
    endpoint: str, port: int, database: str, ca_bundle_path: str
) -> str:
    """Compose the non-secret MONGODB-AWS URL; it may never carry userinfo.

    The task role signs the authentication, so the URL holds no credential:
    the database and CA path are URL-encoded and any userinfo raises (FR-02).
    """
    url = (
        f"mongodb://{endpoint}:{port}/{quote(database, safe='')}"
        f"?tls=true&tlsCAFile={quote(ca_bundle_path, safe='')}"
        f"&{DOCUMENTDB_IAM_OPTIONS}"
    )
    if "@" in urlsplit(url).netloc:
        raise ValueError("MONGODB_URL must not carry userinfo")
    return url


def _managed_secret_arn(secrets: Any) -> str:
    """Return the one DocumentDB-managed primary secret ARN (XP-8)."""
    if type(secrets) is not list or len(secrets) != 1:
        raise ValueError("DocumentDB must report exactly one managed secret")
    return secrets[0].secret_arn


def _documentdb_parameter_family(engine_version: str) -> str:
    """Map an engine version such as ``5.0.0`` to its ``docdb5.0`` family."""
    return "docdb" + ".".join(engine_version.split(".")[:2])


def _documentdb_url(
    username: str,
    password: str,
    endpoint: str,
    port: int,
    descriptor: RuntimeSecretsDescriptor | None = None,
) -> str:
    """Compose a URL inside the secret Output, preserving legacy defaults."""
    database = ""
    options = (
        "tls=true&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    )
    if descriptor is not None:
        database = quote(descriptor.database_name, safe="")
        # DocumentDB authenticates in admin even when an application DB is selected.
        options += (
            f"&authSource=admin&tlsCAFile={quote(descriptor.ca_bundle_path, safe='')}"
        )
    return (
        f"mongodb://{quote(username, safe='')}:{quote(password, safe='')}@"
        f"{endpoint}:{port}/{database}?{options}"
    )


def _master_credentials(
    password: pulumi.Input[str] | None,
) -> dict[str, pulumi.Input[str] | bool]:
    """Select the primary-password arguments for a DocumentDB cluster.

    ``None`` is the hardened shape: DocumentDB owns and rotates the primary
    password in a managed secret (S1.2, FR-01), so no password is passed. The
    managed secret stays on the AWS-managed key (exception A-05): pulumi-aws
    7.23.0 has no ``master_user_secret_kms_key_id``, and none is ever passed.
    """
    if password is None:
        # Boolean flag that hands the password to DocumentDB;
        # B105 matches the key name only.
        return {"manage_master_user_password": True}  # nosec B105
    return {"master_password": password}


@dataclass(frozen=True)
class HardenedRedisOutputs:
    """Hardened Redis outputs: plain IAM env values, no Redis secret (S1.4).

    ``url`` serves both ``REDIS_URL`` and ``REDIS_LOCKOUT_URL``;
    ``replication_group_id`` is lower-cased for the token signer (V-9).
    """

    endpoint: pulumi.Output[str]
    port: int
    url: pulumi.Output[str]
    iam_user_id: str
    replication_group_id: str


@dataclass(frozen=True)
class HardenedDocumentDbOutputs:
    """Hardened DocumentDB outputs: a plain IAM URL, no URL secret (S1.3).

    Redis has its own ``HardenedRedisOutputs`` (S1.4, D-1); the pre-hardening
    ``DataOutputs`` stay until S4.10 (AD-25).
    """

    endpoint: pulumi.Input[str]
    port: pulumi.Input[int]
    instances: tuple[pulumi.Resource, ...]
    mongodb_url: pulumi.Output[str]
    managed_secret_arn: pulumi.Output[str]


@dataclass(frozen=True)
class DataOutputs:
    """Data-plane outputs consumed by the compute layer."""

    documentdb_endpoint: pulumi.Input[str]
    documentdb_port: pulumi.Input[int]
    documentdb_url_secret_arn: pulumi.Input[str]
    redis_endpoint: pulumi.Input[str]
    redis_port: pulumi.Input[int]
    redis_url_secret_arn: pulumi.Input[str]
    # Resources ECS services must wait for: the cluster endpoint resolves before
    # any DocumentDB instance exists, so the endpoint alone is not an edge.
    documentdb_instances: tuple[pulumi.Resource, ...] = ()


class DataPlane(pulumi.ComponentResource):
    """Provision preview placeholders or managed database/cache resources."""

    # Set on the pre-hardening and preview paths only; the hardened path sets
    # ``documentdb`` and ``redis`` with plain-env IAM values (S1.3, S1.4).
    outputs: DataOutputs
    documentdb: HardenedDocumentDbOutputs
    redis: HardenedRedisOutputs
    _runtime_secrets: RuntimeSecrets | None = None

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        network: NetworkPlane,
        runtime_secrets: RuntimeSecrets | None = None,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Build preview-safe outputs or provision managed data services."""
        if settings.is_managed and runtime_secrets is None:
            require_application_secrets(settings)
        self._runtime_secrets = runtime_secrets
        hardened = (
            settings.is_managed
            and runtime_secrets is not None
            and runtime_secrets.descriptor.hardened
        )
        if hardened:
            # Refuse before the component registers, so no resource is left behind.
            reject_documentdb_password_config()
            reject_redis_auth_token_config()
            require_iam_documentdb_engine(settings.documentdb.engine_version)
            require_iam_redis_engine(settings.redis.engine_version)
        super().__init__("user-service-infrastructure:data:Plane", name, None, opts)

        if hardened:
            self.documentdb = self._build_hardened_documentdb(settings, network)
            self.redis = self._build_hardened_redis(settings, network)
            self.register_outputs(
                {
                    "documentDbEndpoint": self.documentdb.endpoint,
                    "documentDbPort": self.documentdb.port,
                    "documentDbManagedSecretArn": self.documentdb.managed_secret_arn,
                    "redisEndpoint": self.redis.endpoint,
                    "redisPort": self.redis.port,
                    "redisIamUserId": self.redis.iam_user_id,
                    "redisReplicationGroupId": self.redis.replication_group_id,
                }
            )
            return
        self.outputs = (
            self._build_managed_outputs(settings, network)
            if settings.is_managed
            else self._build_preview_outputs(settings)
        )
        self.register_outputs(
            {
                "documentDbEndpoint": self.outputs.documentdb_endpoint,
                "documentDbPort": self.outputs.documentdb_port,
                "documentDbUrlSecretArn": self.outputs.documentdb_url_secret_arn,
                "redisEndpoint": self.outputs.redis_endpoint,
                "redisPort": self.outputs.redis_port,
                "redisUrlSecretArn": self.outputs.redis_url_secret_arn,
            }
        )

    def _build_hardened_documentdb(
        self,
        settings: StackSettings,
        network: NetworkPlane,
    ) -> HardenedDocumentDbOutputs:
        """Compose DocumentDB with the managed password and the IAM URL (S1.3).

        The hardened branch of ``WorkloadPhaseStack`` composes this plane under
        its stack-wide guard. The task role authenticates with MONGODB-AWS, so
        no URL secret exists (``document_db_url`` is removed). The
        pre-hardening path is unchanged until S4.10.
        """
        descriptor = cast(RuntimeSecrets, self._runtime_secrets).descriptor
        cluster, instances = self._build_documentdb(settings, network, None)
        port = settings.documentdb.port
        return HardenedDocumentDbOutputs(
            endpoint=cluster.endpoint,
            port=pulumi.Output.from_input(port),
            instances=tuple(instances),
            mongodb_url=cluster.endpoint.apply(
                functools.partial(
                    documentdb_iam_url,
                    port=port,
                    database=descriptor.database_name,
                    ca_bundle_path=descriptor.ca_bundle_path,
                )
            ),
            managed_secret_arn=cluster.master_user_secrets.apply(_managed_secret_arn),
        )

    def _build_hardened_redis(
        self,
        settings: StackSettings,
        network: NetworkPlane,
    ) -> HardenedRedisOutputs:
        """Compose Redis with IAM authentication and no secret (S1.4, AD-02).

        The IAM app user (``user_name == user_id``) and a disabled stack-scoped
        ``default`` user form the one user group; TLS is required and no
        ``auth_token``, Redis secret or rotation function exists (D-1).
        """
        group_id, app_user_id, default_user_id, user_group_id = redis_iam_identity(
            settings.stack_tag
        )
        default_user = aws.elasticache.User(
            "user-service-redis-default-user",
            user_id=default_user_id,
            user_name=REDIS_DEFAULT_USER_NAME,
            engine=REDIS_ENGINE,
            access_string=REDIS_DEFAULT_ACCESS_STRING,
            authentication_mode={"type": "no-password-required"},
            opts=pulumi.ResourceOptions(parent=self),
        )
        app_user = aws.elasticache.User(
            "user-service-redis-app-user",
            user_id=app_user_id,
            user_name=app_user_id,
            engine=REDIS_ENGINE,
            access_string=REDIS_APP_ACCESS_STRING,
            authentication_mode={"type": "iam"},
            opts=pulumi.ResourceOptions(parent=self),
        )
        user_group = aws.elasticache.UserGroup(
            "user-service-redis-user-group",
            user_group_id=user_group_id,
            engine=REDIS_ENGINE,
            user_ids=[default_user.user_id, app_user.user_id],
            opts=pulumi.ResourceOptions(parent=self),
        )
        replication_group = self._build_redis(
            settings,
            network,
            replication_group_id=group_id,
            user_group_ids=[user_group.user_group_id],
        )
        endpoint = replication_group.primary_endpoint_address
        return HardenedRedisOutputs(
            endpoint=endpoint,
            port=settings.redis.port,
            url=endpoint.apply(
                functools.partial(redis_iam_url, port=settings.redis.port)
            ),
            iam_user_id=app_user_id,
            replication_group_id=group_id.lower(),
        )

    def _build_redis(
        self,
        settings: StackSettings,
        network: NetworkPlane,
        *,
        replication_group_id: str,
        **authentication: Any,
    ) -> aws.elasticache.ReplicationGroup:
        """Provision the TLS-required replication group and its subnet group.

        ``authentication`` is the pre-hardening ``auth_token`` pair or the
        hardened ``user_group_ids`` (AD-25 transition rule).
        """
        redis_subnet_group = aws.elasticache.SubnetGroup(
            "user-service-redis-subnets",
            subnet_ids=network.outputs.data_subnet_ids,
            description="User service Redis subnets.",
            opts=pulumi.ResourceOptions(parent=self),
        )
        return aws.elasticache.ReplicationGroup(
            "user-service-redis",
            replication_group_id=replication_group_id,
            description="Redis cache for the user-service application.",
            engine=REDIS_ENGINE,
            engine_version=settings.redis.engine_version,
            node_type=settings.redis.node_type,
            port=settings.redis.port,
            subnet_group_name=redis_subnet_group.name,
            security_group_ids=[network.outputs.redis_security_group_id],
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=True,
            transit_encryption_mode=REDIS_TRANSIT_ENCRYPTION_MODE,
            automatic_failover_enabled=settings.redis.replicas_per_node_group > 0,
            multi_az_enabled=settings.redis.replicas_per_node_group > 0,
            num_cache_clusters=settings.redis.replicas_per_node_group + 1,
            snapshot_retention_limit=settings.redis.snapshot_retention_limit,
            snapshot_window=settings.redis.snapshot_window,
            maintenance_window=settings.redis.maintenance_window,
            **authentication,
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _build_preview_outputs(self, settings: StackSettings) -> DataOutputs:
        """Return preview-safe placeholders without touching AWS APIs."""
        return DataOutputs(
            documentdb_endpoint=pulumi.Output.from_input(
                f"{build_resource_name(settings.stack_tag, 'documentdb')}.local"
            ),
            documentdb_port=pulumi.Output.from_input(settings.documentdb.port),
            documentdb_url_secret_arn=pulumi.Output.from_input(
                f"arn:aws:secretsmanager:{settings.region}:preview:"
                f"{build_resource_name(settings.stack_tag, 'documentdb-url')}"
            ),
            redis_endpoint=pulumi.Output.from_input(
                f"{build_resource_name(settings.stack_tag, 'redis')}.local"
            ),
            redis_port=pulumi.Output.from_input(settings.redis.port),
            redis_url_secret_arn=pulumi.Output.from_input(
                f"arn:aws:secretsmanager:{settings.region}:preview:"
                f"{build_resource_name(settings.stack_tag, 'redis-url')}"
            ),
        )

    def _build_documentdb(
        self,
        settings: StackSettings,
        network: NetworkPlane,
        password: pulumi.Input[str] | None,
    ) -> tuple[aws.docdb.Cluster, list[pulumi.Resource]]:
        """Provision the DocumentDB cluster; ``None`` selects the managed password."""
        documentdb_subnet_group = aws.docdb.SubnetGroup(
            "user-service-documentdb-subnets",
            subnet_ids=network.outputs.data_subnet_ids,
            description="User service DocumentDB subnets.",
            opts=pulumi.ResourceOptions(parent=self),
        )

        cluster_identifier = build_resource_name(
            settings.stack_tag,
            "docdb",
            max_length=63,
        )
        # Stack tags are at most 65 characters, far below the 255-character limit.
        parameter_group_name = build_resource_name(settings.stack_tag, "docdb-params")
        parameter_group = aws.docdb.ClusterParameterGroup(
            "user-service-documentdb-parameters",
            name=parameter_group_name,
            family=_documentdb_parameter_family(settings.documentdb.engine_version),
            description="User service DocumentDB TLS, audit and profiler settings.",
            parameters=[
                aws.docdb.ClusterParameterGroupParameterArgs(
                    name=name, value=value, apply_method="pending-reboot"
                )
                for name, value in DOCUMENTDB_CLUSTER_PARAMETERS.items()
            ],
            opts=pulumi.ResourceOptions(parent=self),
        )
        # DocumentDB creates missing export groups without retention; own them first.
        log_groups = [
            aws.cloudwatch.LogGroup(
                f"user-service-documentdb-{export}-logs",
                name=f"/aws/docdb/{cluster_identifier}/{export}",
                retention_in_days=DOCUMENTDB_LOG_RETENTION_DAYS,
                opts=pulumi.ResourceOptions(parent=self),
            )
            for export in DOCUMENTDB_LOG_EXPORTS
        ]

        # Every managed environment retains the cluster and a final snapshot.
        documentdb_cluster = aws.docdb.Cluster(
            "user-service-documentdb-cluster",
            cluster_identifier=cluster_identifier,
            engine="docdb",
            engine_version=settings.documentdb.engine_version,
            master_username=settings.documentdb.username,
            **_master_credentials(password),
            db_subnet_group_name=documentdb_subnet_group.name,
            db_cluster_parameter_group_name=parameter_group_name,
            vpc_security_group_ids=[network.outputs.documentdb_security_group_id],
            storage_encrypted=True,
            enabled_cloudwatch_logs_exports=list(DOCUMENTDB_LOG_EXPORTS),
            port=settings.documentdb.port,
            backup_retention_period=settings.documentdb.backup_retention_days,
            preferred_backup_window=settings.documentdb.preferred_backup_window,
            preferred_maintenance_window=(
                settings.documentdb.preferred_maintenance_window
            ),
            deletion_protection=True,
            skip_final_snapshot=False,
            final_snapshot_identifier=build_resource_name(
                settings.stack_tag, "docdb-final", max_length=63
            ),
            opts=pulumi.ResourceOptions(
                parent=self, protect=True, depends_on=[parameter_group, *log_groups]
            ),
        )

        if settings.documentdb.instance_count < 1:
            raise ValueError(
                "documentDbInstanceCount must be at least 1 for managed deployments."
            )

        documentdb_instances: list[pulumi.Resource] = []
        for index in range(settings.documentdb.instance_count):
            instance = aws.docdb.ClusterInstance(
                f"user-service-documentdb-instance-{index + 1}",
                identifier=build_resource_name(
                    settings.stack_tag,
                    f"docdb-{index + 1}",
                    max_length=63,
                ),
                cluster_identifier=documentdb_cluster.cluster_identifier,
                instance_class=settings.documentdb.instance_class,
                apply_immediately=True,
                enable_performance_insights=True,
                opts=pulumi.ResourceOptions(parent=self, protect=True),
            )
            documentdb_instances.append(instance)

        return documentdb_cluster, documentdb_instances

    def _build_managed_outputs(
        self,
        settings: StackSettings,
        network: NetworkPlane,
    ) -> DataOutputs:
        """Provision DocumentDB, Redis, and the derived connection secrets."""
        password = (
            self._runtime_secrets.values["document_db_password"]
            if self._runtime_secrets is not None
            else require_application_secrets(settings).mongodb_password
        )
        token = (
            self._runtime_secrets.values["redis_auth_token"]
            if self._runtime_secrets is not None
            else require_application_secrets(settings).redis_auth_token
        )
        documentdb_cluster, documentdb_instances = self._build_documentdb(
            settings, network, password
        )

        documentdb_url_secret_arn = self._persist_url(
            "document_db_url",
            "user-service-documentdb-url",
            pulumi.Output.all(
                settings.documentdb.username,
                password,
                documentdb_cluster.endpoint,
            ).apply(
                lambda parts: _documentdb_url(
                    parts[0],
                    parts[1],
                    parts[2],
                    settings.documentdb.port,
                    self._runtime_secrets.descriptor
                    if self._runtime_secrets is not None
                    else None,
                )
            ),
        )

        redis_replication_group = self._build_redis(
            settings,
            network,
            replication_group_id=build_resource_name(
                settings.stack_tag,
                "redis",
                max_length=40,
            ),
            auth_token=token,
            # B106 matches the keyword name; ROTATE is a strategy, not a token.
            auth_token_update_strategy="ROTATE",  # nosec B106
        )

        redis_url_secret_arn = self._persist_url(
            "redis_url",
            "user-service-redis-url",
            pulumi.Output.all(
                token,
                redis_replication_group.primary_endpoint_address,
            ).apply(
                lambda parts: (
                    f"rediss://:{quote(parts[0], safe='')}@"
                    f"{parts[1]}:{settings.redis.port}/0"
                )
            ),
        )

        return DataOutputs(
            documentdb_endpoint=documentdb_cluster.endpoint,
            documentdb_port=pulumi.Output.from_input(settings.documentdb.port),
            documentdb_url_secret_arn=documentdb_url_secret_arn,
            redis_endpoint=redis_replication_group.primary_endpoint_address,
            redis_port=pulumi.Output.from_input(settings.redis.port),
            redis_url_secret_arn=redis_url_secret_arn,
            documentdb_instances=tuple(documentdb_instances),
        )

    def _persist_url(
        self, purpose: str, name: str, value: pulumi.Input[str]
    ) -> pulumi.Output[str]:
        """Use the contract-owned version while retaining legacy identities."""
        if self._runtime_secrets is not None:
            return self._runtime_secrets.persist_url(purpose, value)
        descriptions = {
            "document_db_url": (
                "MongoDB connection URL for the user-service application."
            ),
            "redis_url": "Redis connection URL for the user-service application.",
        }
        secret = aws.secretsmanager.Secret(
            name,
            description=descriptions[purpose],
            opts=pulumi.ResourceOptions(parent=self),
        )
        aws.secretsmanager.SecretVersion(
            f"{name}-version",
            secret_id=secret.id,
            secret_string=value,
            opts=pulumi.ResourceOptions(parent=self),
        )
        return secret.arn
