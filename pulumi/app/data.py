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
    require_application_secrets,
)
from app.network import NetworkPlane
from app.runtime_secrets import RuntimeSecrets

__all__ = ["DataPlane"]


@dataclass(frozen=True)
class DataOutputs:
    """Data-plane outputs consumed by the compute layer."""

    documentdb_endpoint: pulumi.Input[str]
    documentdb_port: pulumi.Input[int]
    documentdb_url_secret_arn: pulumi.Input[str]
    redis_endpoint: pulumi.Input[str]
    redis_port: pulumi.Input[int]
    redis_url_secret_arn: pulumi.Input[str]


class DataPlane(pulumi.ComponentResource):
    """Provision preview placeholders or managed database/cache resources."""

    outputs: DataOutputs
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
        super().__init__("user-service-infrastructure:data:Plane", name, None, opts)

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
        documentdb_subnet_group = aws.docdb.SubnetGroup(
            "user-service-documentdb-subnets",
            subnet_ids=network.outputs.data_subnet_ids,
            description="User service DocumentDB subnets.",
            opts=pulumi.ResourceOptions(parent=self),
        )

        documentdb_cluster = aws.docdb.Cluster(
            "user-service-documentdb-cluster",
            cluster_identifier=build_resource_name(
                settings.stack_tag,
                "docdb",
                max_length=63,
            ),
            engine="docdb",
            engine_version=settings.documentdb.engine_version,
            master_username=settings.documentdb.username,
            master_password=password,
            db_subnet_group_name=documentdb_subnet_group.name,
            vpc_security_group_ids=[network.outputs.documentdb_security_group_id],
            storage_encrypted=True,
            enabled_cloudwatch_logs_exports=["audit", "profiler"],
            port=settings.documentdb.port,
            backup_retention_period=settings.documentdb.backup_retention_days,
            preferred_backup_window=settings.documentdb.preferred_backup_window,
            preferred_maintenance_window=(
                settings.documentdb.preferred_maintenance_window
            ),
            deletion_protection=settings.documentdb.deletion_protection,
            skip_final_snapshot=settings.documentdb.skip_final_snapshot,
            final_snapshot_identifier=(
                None
                if settings.documentdb.skip_final_snapshot
                else build_resource_name(
                    settings.stack_tag, "docdb-final", max_length=63
                )
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        if settings.documentdb.instance_count < 1:
            raise ValueError(
                "documentDbInstanceCount must be at least 1 for managed deployments."
            )

        for index in range(settings.documentdb.instance_count):
            aws.docdb.ClusterInstance(
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
                opts=pulumi.ResourceOptions(parent=self),
            )

        documentdb_url_secret_arn = self._persist_url(
            "document_db_url",
            "user-service-documentdb-url",
            pulumi.Output.all(
                settings.documentdb.username,
                password,
                documentdb_cluster.endpoint,
            ).apply(
                lambda parts: (
                    "mongodb://"
                    f"{quote(parts[0], safe='')}:{quote(parts[1], safe='')}@"
                    f"{parts[2]}:{settings.documentdb.port}/"
                    "?tls=true&replicaSet=rs0&readPreference=secondaryPreferred"
                    "&retryWrites=false"
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
