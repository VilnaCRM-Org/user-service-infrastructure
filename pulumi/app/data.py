"""Managed data services for the user-service stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import pulumi_aws as aws

import pulumi
from app.environment import (
    StackSettings,
    build_resource_name,
    reject_documentdb_password_config,
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
        # Boolean flag that hands the password to DocumentDB; B105 matches the key name only.
        return {"manage_master_user_password": True}  # nosec B105
    return {"master_password": password}


@dataclass(frozen=True)
class HardenedDocumentDbOutputs:
    """Hardened DocumentDB outputs; the DSN and Redis join in S1.3+ (AD-25)."""

    endpoint: pulumi.Input[str]
    port: pulumi.Input[int]
    instances: tuple[pulumi.Resource, ...]


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
    # ``documentdb`` until S1.3 wires the plain-env DSN and Redis (C-composition).
    outputs: DataOutputs
    documentdb: HardenedDocumentDbOutputs
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
        super().__init__("user-service-infrastructure:data:Plane", name, None, opts)

        if hardened:
            self.documentdb = self._build_hardened_documentdb(settings, network)
            self.register_outputs(
                {
                    "documentDbEndpoint": self.documentdb.endpoint,
                    "documentDbPort": self.documentdb.port,
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
        """Compose DocumentDB with the managed password; Redis and DSN are S1.3+.

        Scoped seam for S1.2: the hardened branch of ``WorkloadPhaseStack`` does
        not compose this plane yet (S1.3, C-composition). The pre-hardening path
        is unchanged until S4.10.
        """
        cluster, instances = self._build_documentdb(settings, network, None)
        return HardenedDocumentDbOutputs(
            endpoint=cluster.endpoint,
            port=pulumi.Output.from_input(settings.documentdb.port),
            instances=tuple(instances),
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

        redis_subnet_group = aws.elasticache.SubnetGroup(
            "user-service-redis-subnets",
            subnet_ids=network.outputs.data_subnet_ids,
            description="User service Redis subnets.",
            opts=pulumi.ResourceOptions(parent=self),
        )

        redis_replication_group = aws.elasticache.ReplicationGroup(
            "user-service-redis",
            replication_group_id=build_resource_name(
                settings.stack_tag,
                "redis",
                max_length=40,
            ),
            description="Redis cache for the user-service application.",
            engine="redis",
            engine_version=settings.redis.engine_version,
            node_type=settings.redis.node_type,
            port=settings.redis.port,
            subnet_group_name=redis_subnet_group.name,
            security_group_ids=[network.outputs.redis_security_group_id],
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=True,
            transit_encryption_mode="required",
            auth_token=token,
            auth_token_update_strategy="ROTATE",  # nosec B106
            automatic_failover_enabled=settings.redis.replicas_per_node_group > 0,
            multi_az_enabled=settings.redis.replicas_per_node_group > 0,
            num_cache_clusters=settings.redis.replicas_per_node_group + 1,
            snapshot_retention_limit=settings.redis.snapshot_retention_limit,
            snapshot_window=settings.redis.snapshot_window,
            maintenance_window=settings.redis.maintenance_window,
            opts=pulumi.ResourceOptions(parent=self),
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
