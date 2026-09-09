"""Shared Pulumi configuration, naming, and environment metadata helpers."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Final, Optional

import pulumi
from app.guardrails import validate_environment_name, validate_service_name

__all__ = [
    "ApplicationSecretInputs",
    "ContainerImageSettings",
    "DocumentDbSettings",
    "EnvironmentSettings",
    "NetworkSettings",
    "QueueSettings",
    "RedisSettings",
    "RuntimeSettings",
    "ServiceCapacitySettings",
    "SocialProviderSettings",
    "StackSettings",
    "build_resource_name",
    "has_aws_credentials",
    "is_production_environment",
    "resolve_config_value",
    "resolve_deployment_mode",
    "resolve_stack_settings",
]

DEFAULT_OWNER: Final[str] = "platform"
DEFAULT_COST_CENTER: Final[str] = "engineering"
DEFAULT_REGION: Final[str] = "eu-central-1"
DEFAULT_CONTAINER_PORT: Final[int] = 80
DEFAULT_DOCUMENTDB_PORT: Final[int] = 27017
DEFAULT_REDIS_PORT: Final[int] = 6379
DEFAULT_HEALTH_CHECK_PATH: Final[str] = "/api/health"
PREVIEW_PLACEHOLDER_PREFIX: Final[str] = "preview-only"
DEPLOYMENT_MODES: Final[set[str]] = {"auto", "preview", "managed"}


@dataclass(frozen=True)
class NetworkSettings:
    """Network topology configuration for the stack."""

    vpc_cidr: str
    availability_zones: tuple[str, ...]
    public_subnet_cidrs: tuple[str, ...]
    app_subnet_cidrs: tuple[str, ...]
    data_subnet_cidrs: tuple[str, ...]


@dataclass(frozen=True)
class ServiceCapacitySettings:
    """Compute capacity settings for the public API and workers."""

    container_port: int
    health_check_path: str
    web_cpu: str
    web_memory: str
    worker_cpu: str
    worker_memory: str
    web_desired_count: int
    worker_desired_count: int


@dataclass(frozen=True)
class DocumentDbSettings:
    """DocumentDB cluster sizing and protection settings."""

    username: str
    instance_class: str
    instance_count: int
    port: int
    engine_version: str
    backup_retention_days: int
    preferred_backup_window: str
    preferred_maintenance_window: str
    deletion_protection: bool
    skip_final_snapshot: bool


@dataclass(frozen=True)
class RedisSettings:
    """ElastiCache Redis settings."""

    node_type: str
    replicas_per_node_group: int
    port: int
    engine_version: str
    snapshot_retention_limit: int
    snapshot_window: str
    maintenance_window: str


@dataclass(frozen=True)
class ContainerImageSettings:
    """Container image contract for the ECS workloads."""

    web_repository_name: str
    worker_repository_name: str
    web_image_tag: str
    worker_image_tag: str
    web_image_override: str | None
    worker_image_override: str | None
    image_tag_mutability: str


@dataclass(frozen=True)
class QueueSettings:
    """SQS queue names used by the application."""

    send_email: str
    failed_send_email: str
    insert_user_batch: str
    domain_events: str
    failed_domain_events: str
    health_check: str


@dataclass(frozen=True)
class RuntimeSettings:
    """Plain-text application runtime configuration."""

    access_logs_bucket_name: str | None
    app_env: str
    app_debug: str
    api_base_url: str
    api_url: str
    cors_allow_origin: str
    certificate_arn: str | None
    mail_sender: str
    jwt_issuer: str
    jwt_audience: str
    emf_namespace: str
    aws_sqs_endpoint_base: str
    aws_sqs_port: str
    execution_role_arn: str | None
    task_role_arn: str | None


def validate_runtime_roles(runtime: RuntimeSettings, environment: str) -> None:
    """Bind supplied roles to the protected account and repository environment."""
    accounts = pulumi.Config("aws").get_object("allowedAccountIds")
    if (
        not isinstance(accounts, list)
        or len(accounts) != 1
        or not isinstance(accounts[0], str)
        or re.fullmatch(r"[0-9]{12}", accounts[0]) is None
    ):
        raise ValueError("Managed runtime roles require one protected AWS account.")
    prefix = f"arn:aws:iam::{accounts[0]}:role/{pulumi.get_project()}-{environment}"
    if (
        runtime.execution_role_arn != f"{prefix}-EcsExecution"
        or runtime.task_role_arn != f"{prefix}-EcsTask"
    ):
        raise ValueError("Managed runtime roles must match the central role contract.")


def validate_health_check_runtime(
    runtime: RuntimeSettings, queues: QueueSettings
) -> None:
    """Require the application's production role-chain and fixed health queue."""
    if runtime.app_env != "prod" or queues.health_check != "health-check-queue":
        raise ValueError(
            "Managed SQS health checks require appEnv=prod and "
            "healthCheckQueueName=health-check-queue."
        )


@dataclass(frozen=True)
class SocialProviderSettings:
    """OAuth provider identifiers and callback URLs."""

    github_client_id: str
    github_redirect_uri: str
    google_client_id: str
    google_redirect_uri: str
    facebook_client_id: str
    facebook_redirect_uri: str
    facebook_graph_api_version: str
    twitter_client_id: str
    twitter_redirect_uri: str


@dataclass(frozen=True)
class ApplicationSecretInputs:
    """Secret values consumed by the managed stack."""

    mongodb_password: pulumi.Output[str]
    redis_auth_token: pulumi.Output[str]
    app_secret: pulumi.Output[str]
    mailer_dsn: pulumi.Output[str]
    oauth_encryption_key: pulumi.Output[str]
    oauth_passphrase: pulumi.Output[str]
    two_factor_encryption_key: pulumi.Output[str]
    oauth_private_key_pem: pulumi.Output[str]
    oauth_public_key_pem: pulumi.Output[str]
    github_client_secret: pulumi.Output[str]
    google_client_secret: pulumi.Output[str]
    facebook_client_secret: pulumi.Output[str]
    twitter_client_secret: pulumi.Output[str]


@dataclass(frozen=True)
class StackSettings:
    """Resolved stack settings shared across modules."""

    environment: str
    service_name: str
    owner: str
    cost_center: str
    stack_tag: str
    default_tags: dict[str, str]
    region: str
    deployment_mode: str
    network: NetworkSettings
    capacity: ServiceCapacitySettings
    documentdb: DocumentDbSettings
    redis: RedisSettings
    images: ContainerImageSettings
    queues: QueueSettings
    runtime: RuntimeSettings
    social: SocialProviderSettings
    secrets: ApplicationSecretInputs

    @property
    def is_managed(self) -> bool:
        """Return whether the stack should provision real AWS resources."""
        return self.deployment_mode == "managed"


def _stack_metadata_from_outputs(
    parts: list[str],
) -> tuple[str, str, str, str, str, str, str]:
    """Narrow Pulumi's list-shaped Output.all result to a stable tuple."""
    return parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]


def _stack_tag_from_parts(parts: tuple[str, str, str, str, str, str, str]) -> str:
    """Build the exported stack tag from the service and environment names."""
    return f"{parts[0]}-{parts[1]}"


def _default_tags_from_parts(
    parts: tuple[str, str, str, str, str, str, str],
) -> dict[str, str]:
    """Build the default Pulumi tags shared by stack resources."""
    return {
        "Project": parts[0],
        "Environment": parts[1],
        "Owner": parts[2],
        "CostCenter": parts[3],
        "DataClassification": parts[4],
        "Criticality": parts[5],
        "RetentionClass": parts[6],
    }


def _normalize_tag_value(value: str, *, default: str) -> str:
    """Trim tag values and fall back to the default when the result is empty."""
    normalized = value.strip()
    return normalized or default


def _normalize_choice(value: str, *, allowed: set[str], label: str) -> str:
    """Normalize a simple enumerated configuration value."""
    normalized = value.strip().lower()
    if normalized not in allowed:
        allowed_display = ", ".join(sorted(allowed))
        raise ValueError(f"{label} must be one of: {allowed_display}.")
    return normalized


def _normalize_csv(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse comma-separated config into a tuple while ignoring empty segments."""
    if value is None:
        return default
    parts = tuple(segment.strip() for segment in value.split(",") if segment.strip())
    return parts or default


def _preview_placeholder(name: str) -> str:
    """Return a stable placeholder value for preview-only execution."""
    normalized = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return f"{PREVIEW_PLACEHOLDER_PREFIX}-{normalized}"


def _required_managed_string(
    config: pulumi.Config,
    key: str,
    *,
    managed: bool,
    preview_default: str,
) -> str:
    """Require explicit config on managed apply while staying preview-friendly."""
    configured = config.get(key)
    if configured is not None and configured.strip():
        return configured
    if managed and not pulumi.runtime.is_dry_run():
        raise ValueError(f"{key} must be configured for managed deployments.")
    return preview_default


def _secret_value(
    config: pulumi.Config,
    key: str,
    *,
    managed: bool,
    preview_default: str,
) -> pulumi.Output[str]:
    """Resolve secret config while keeping managed previews credential-safe."""
    configured_secret = config.get_secret(key)
    if configured_secret is not None:
        return configured_secret

    configured_plain = config.get(key)
    if configured_plain is not None:
        if managed:
            raise ValueError(
                f"{key} is configured as plain text; re-set it with "
                f"`pulumi -C pulumi config set --secret {key} <value>` for managed "
                f"deployments."
            )
        return pulumi.Output.secret(configured_plain)

    if managed and not pulumi.runtime.is_dry_run():
        raise ValueError(
            f"{key} must be configured as a secret for managed deployments."
        )

    return pulumi.Output.secret(preview_default)


def _derived_cors_pattern(api_base_url: str) -> str:
    """Convert a single public origin into the regex format the app expects."""
    return f"^{re.escape(api_base_url)}$"


def _availability_zones_for_region(region: str, *, count: int) -> tuple[str, ...]:
    """Build a stable two-or-three AZ default without invoking AWS at preview time."""
    suffixes = ("a", "b", "c")
    return tuple(f"{region}{suffix}" for suffix in suffixes[:count])


def _validate_parallel_lengths(
    network: NetworkSettings,
) -> NetworkSettings:
    """Ensure the VPC subnet partitions stay aligned by availability zone."""
    expected = len(network.availability_zones)
    groups = (
        network.public_subnet_cidrs,
        network.app_subnet_cidrs,
        network.data_subnet_cidrs,
    )
    if any(len(group) != expected for group in groups):
        raise ValueError(
            "availability zones, public subnets, app subnets, and data subnets "
            "must have the same number of entries."
        )
    return network


def has_aws_credentials() -> bool:
    """Return whether the current execution environment exposes AWS credentials."""
    credential_markers = (
        "AWS_ACCESS_KEY_ID",
        "AWS_PROFILE",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    )
    return any(os.getenv(marker) for marker in credential_markers)


def resolve_deployment_mode(explicit_mode: str, *, credentials_present: bool) -> str:
    """Resolve the effective deployment mode from config and runtime context."""
    normalized = _normalize_choice(
        explicit_mode,
        allowed=DEPLOYMENT_MODES,
        label="deployment mode",
    )
    if normalized == "auto":
        return "managed" if credentials_present else "preview"
    return normalized


def resolve_config_value(
    explicit: str | None, configured: str | None, *, default: str
) -> str:
    """Preserve intentionally empty config values so guardrails can reject them."""
    if explicit is not None:
        return explicit
    if configured is not None:
        return configured
    return default


def _get_int(config: pulumi.Config, key: str, *, default: int) -> int:
    """Return configured integers verbatim while keeping defaults for missing keys."""
    value = config.get_int(key)
    return default if value is None else value


def is_production_environment(environment: str) -> bool:
    """Return whether the environment should enable stricter protections."""
    return environment in {"prod", "production"}


def build_resource_name(
    stack_tag: str,
    suffix: str,
    *,
    max_length: int | None = None,
) -> str:
    """Build deterministic resource identifiers that stay within AWS limits."""
    name = f"{stack_tag}-{suffix}".replace("_", "-")
    if max_length is None or len(name) <= max_length:
        return name

    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    if max_length <= len(digest):
        return digest[:max_length]
    prefix_length = max_length - len(digest) - 1
    truncated_prefix = name[:prefix_length].rstrip("-")
    return f"{truncated_prefix}-{digest}"


class EnvironmentSettings(pulumi.ComponentResource):
    """Expose shared environment metadata for the rest of the Pulumi program."""

    def __init__(
        self,
        name: str,
        *,
        environment: Optional[str] = None,
        service_name: Optional[str] = None,
        owner: Optional[str] = None,
        cost_center: Optional[str] = None,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Create the component and resolve environment/service configuration."""
        super().__init__(
            "user-service-infrastructure:core:EnvironmentSettings", name, None, opts
        )

        config = pulumi.Config()

        resolved_environment = validate_environment_name(
            resolve_config_value(
                environment,
                config.get("environment"),
                default="dev",
            )
        )

        resolved_service = validate_service_name(
            resolve_config_value(
                service_name,
                config.get("serviceName"),
                default=pulumi.get_project(),
            )
        )
        resolved_owner = _normalize_tag_value(
            resolve_config_value(
                owner,
                config.get("owner"),
                default=DEFAULT_OWNER,
            ),
            default=DEFAULT_OWNER,
        )
        resolved_cost_center = _normalize_tag_value(
            resolve_config_value(
                cost_center,
                config.get("costCenter"),
                default=DEFAULT_COST_CENTER,
            ),
            default=DEFAULT_COST_CENTER,
        )

        self.environment_name = resolved_environment
        self.service_name_value = resolved_service
        self.owner = resolved_owner
        self.cost_center = resolved_cost_center

        self.environment = pulumi.Output.from_input(resolved_environment)
        self.service_name = pulumi.Output.from_input(resolved_service)

        stack_metadata: pulumi.Output[tuple[str, str, str, str, str, str, str]] = (
            pulumi.Output.all(
                self.service_name,
                self.environment,
                resolved_owner,
                resolved_cost_center,
                _normalize_tag_value(
                    config.get("dataClassification") or "", default="internal"
                ),
                _normalize_tag_value(config.get("criticality") or "", default="high"),
                _normalize_tag_value(
                    config.get("retentionClass") or "", default="standard"
                ),
            ).apply(_stack_metadata_from_outputs)
        )
        self.stack_tag = stack_metadata.apply(_stack_tag_from_parts)
        self.default_tags = stack_metadata.apply(_default_tags_from_parts)

        self.register_outputs(
            {
                "environment": self.environment,
                "serviceName": self.service_name,
                "stackTag": self.stack_tag,
                "defaultTags": self.default_tags,
            }
        )


def resolve_stack_settings(environment_settings: EnvironmentSettings) -> StackSettings:
    """Resolve the full stack contract from Pulumi config and repo defaults."""
    config = pulumi.Config()
    aws_config = pulumi.Config("aws")

    environment = environment_settings.environment_name
    service_name = environment_settings.service_name_value
    owner = environment_settings.owner
    cost_center = environment_settings.cost_center

    stack_tag = f"{service_name}-{environment}"
    default_tags = {
        "Project": service_name,
        "Environment": environment,
        "Owner": owner,
        "CostCenter": cost_center,
    }

    region = resolve_config_value(
        config.get("region"),
        aws_config.get("region"),
        default=DEFAULT_REGION,
    )
    deployment_mode = resolve_deployment_mode(
        resolve_config_value(
            None,
            config.get("deploymentMode"),
            default="auto",
        ),
        credentials_present=has_aws_credentials(),
    )

    network = _validate_parallel_lengths(
        NetworkSettings(
            vpc_cidr=resolve_config_value(
                None,
                config.get("vpcCidr"),
                default="10.42.0.0/16",
            ),
            availability_zones=_normalize_csv(
                config.get("availabilityZones"),
                default=_availability_zones_for_region(region, count=2),
            ),
            public_subnet_cidrs=_normalize_csv(
                config.get("publicSubnetCidrs"),
                default=("10.42.0.0/24", "10.42.1.0/24"),
            ),
            app_subnet_cidrs=_normalize_csv(
                config.get("appSubnetCidrs"),
                default=("10.42.10.0/24", "10.42.11.0/24"),
            ),
            data_subnet_cidrs=_normalize_csv(
                config.get("dataSubnetCidrs"),
                default=("10.42.20.0/24", "10.42.21.0/24"),
            ),
        )
    )

    is_production = is_production_environment(environment)
    api_base_url = resolve_config_value(
        None,
        config.get("apiBaseUrl"),
        default=f"https://{service_name}.{environment}.internal",
    )
    api_url = resolve_config_value(None, config.get("apiUrl"), default=api_base_url)

    capacity = ServiceCapacitySettings(
        container_port=_get_int(
            config,
            "containerPort",
            default=DEFAULT_CONTAINER_PORT,
        ),
        health_check_path=resolve_config_value(
            None,
            config.get("healthCheckPath"),
            default=DEFAULT_HEALTH_CHECK_PATH,
        ),
        web_cpu=resolve_config_value(None, config.get("webCpu"), default="512"),
        web_memory=resolve_config_value(None, config.get("webMemory"), default="1024"),
        worker_cpu=resolve_config_value(None, config.get("workerCpu"), default="512"),
        worker_memory=resolve_config_value(
            None,
            config.get("workerMemory"),
            default="1024",
        ),
        web_desired_count=_get_int(config, "webDesiredCount", default=2),
        worker_desired_count=_get_int(config, "workerDesiredCount", default=2),
    )

    documentdb = DocumentDbSettings(
        username=resolve_config_value(
            None,
            config.get("documentDbUsername"),
            default="user_service",
        ),
        instance_class=resolve_config_value(
            None,
            config.get("documentDbInstanceClass"),
            default="db.t4g.medium",
        ),
        instance_count=_get_int(config, "documentDbInstanceCount", default=2),
        port=_get_int(config, "documentDbPort", default=DEFAULT_DOCUMENTDB_PORT),
        engine_version=resolve_config_value(
            None,
            config.get("documentDbEngineVersion"),
            default="5.0.0",
        ),
        backup_retention_days=_get_int(
            config,
            "documentDbBackupRetentionDays",
            default=7,
        ),
        preferred_backup_window=resolve_config_value(
            None,
            config.get("documentDbPreferredBackupWindow"),
            default="03:00-05:00",
        ),
        preferred_maintenance_window=resolve_config_value(
            None,
            config.get("documentDbPreferredMaintenanceWindow"),
            default="sun:05:00-sun:07:00",
        ),
        deletion_protection=is_production,
        skip_final_snapshot=not is_production,
    )

    redis = RedisSettings(
        node_type=resolve_config_value(
            None,
            config.get("redisNodeType"),
            default="cache.t4g.small",
        ),
        replicas_per_node_group=_get_int(
            config,
            "redisReplicasPerNodeGroup",
            default=1,
        ),
        port=_get_int(config, "redisPort", default=DEFAULT_REDIS_PORT),
        engine_version=resolve_config_value(
            None,
            config.get("redisEngineVersion"),
            default="7.1",
        ),
        snapshot_retention_limit=_get_int(
            config,
            "redisSnapshotRetentionLimit",
            default=7,
        ),
        snapshot_window=resolve_config_value(
            None,
            config.get("redisSnapshotWindow"),
            default="06:00-07:00",
        ),
        maintenance_window=resolve_config_value(
            None,
            config.get("redisMaintenanceWindow"),
            default="sun:07:00-sun:08:00",
        ),
    )

    images = ContainerImageSettings(
        web_repository_name=resolve_config_value(
            None,
            config.get("webRepositoryName"),
            default="user-service",
        ),
        worker_repository_name=resolve_config_value(
            None,
            config.get("workerRepositoryName"),
            default="user-service-workers",
        ),
        web_image_tag=resolve_config_value(
            None, config.get("webImageTag"), default="latest"
        ),
        worker_image_tag=resolve_config_value(
            None,
            config.get("workerImageTag"),
            default="latest",
        ),
        web_image_override=config.get("webImage"),
        worker_image_override=config.get("workerImage"),
        image_tag_mutability=_normalize_choice(
            resolve_config_value(
                None,
                config.get("imageTagMutability"),
                default="IMMUTABLE",
            ),
            allowed={"mutable", "immutable"},
            label="image tag mutability",
        ).upper(),
    )

    queues = QueueSettings(
        send_email=resolve_config_value(
            None, config.get("sendEmailQueueName"), default="send-email"
        ),
        failed_send_email=resolve_config_value(
            None,
            config.get("failedSendEmailQueueName"),
            default="failed-send-email",
        ),
        insert_user_batch=resolve_config_value(
            None,
            config.get("insertUserBatchQueueName"),
            default="insert-user-batch",
        ),
        domain_events=resolve_config_value(
            None,
            config.get("domainEventsQueueName"),
            default="domain-events",
        ),
        failed_domain_events=resolve_config_value(
            None,
            config.get("failedDomainEventsQueueName"),
            default="failed-domain-events",
        ),
        health_check=resolve_config_value(
            None,
            config.get("healthCheckQueueName"),
            default="health-check-queue",
        ),
    )

    runtime = RuntimeSettings(
        execution_role_arn=config.get("executionRoleArn"),
        task_role_arn=config.get("taskRoleArn"),
        access_logs_bucket_name=_required_managed_string(
            config,
            "accessLogsBucketName",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("alb-access-logs"),
        ),
        app_env=resolve_config_value(None, config.get("appEnv"), default="prod"),
        app_debug=resolve_config_value(None, config.get("appDebug"), default="0"),
        api_base_url=api_base_url,
        api_url=api_url,
        cors_allow_origin=resolve_config_value(
            None,
            config.get("corsAllowOrigin"),
            default=_derived_cors_pattern(api_base_url),
        ),
        certificate_arn=config.get("certificateArn"),
        mail_sender=resolve_config_value(
            None,
            config.get("mailSender"),
            default="noreply@vilnacrm.com",
        ),
        jwt_issuer=resolve_config_value(
            None,
            config.get("jwtIssuer"),
            default="vilnacrm-user-service",
        ),
        jwt_audience=resolve_config_value(
            None,
            config.get("jwtAudience"),
            default="vilnacrm-api",
        ),
        emf_namespace=resolve_config_value(
            None,
            config.get("awsEmfNamespace"),
            default="UserService/BusinessMetrics",
        ),
        aws_sqs_endpoint_base=resolve_config_value(
            None,
            config.get("awsSqsEndpointBase"),
            default=f"https://sqs.{region}.amazonaws.com",
        ),
        aws_sqs_port=resolve_config_value(
            None, config.get("awsSqsPort"), default="443"
        ),
    )

    if deployment_mode == "managed":
        validate_runtime_roles(runtime, environment)
        validate_health_check_runtime(runtime, queues)

    social = SocialProviderSettings(
        github_client_id=resolve_config_value(
            None, config.get("githubClientId"), default=""
        ),
        github_redirect_uri=resolve_config_value(
            None,
            config.get("githubRedirectUri"),
            default=f"{api_base_url}/api/auth/social/github/callback",
        ),
        google_client_id=resolve_config_value(
            None, config.get("googleClientId"), default=""
        ),
        google_redirect_uri=resolve_config_value(
            None,
            config.get("googleRedirectUri"),
            default=f"{api_base_url}/api/auth/social/google/callback",
        ),
        facebook_client_id=resolve_config_value(
            None, config.get("facebookClientId"), default=""
        ),
        facebook_redirect_uri=resolve_config_value(
            None,
            config.get("facebookRedirectUri"),
            default=f"{api_base_url}/api/auth/social/facebook/callback",
        ),
        facebook_graph_api_version=resolve_config_value(
            None,
            config.get("facebookGraphApiVersion"),
            default="v19.0",
        ),
        twitter_client_id=resolve_config_value(
            None, config.get("twitterClientId"), default=""
        ),
        twitter_redirect_uri=resolve_config_value(
            None,
            config.get("twitterRedirectUri"),
            default=f"{api_base_url}/api/auth/social/twitter/callback",
        ),
    )

    secrets = ApplicationSecretInputs(
        mongodb_password=_secret_value(
            config,
            "documentDbPassword",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("documentdb-password"),
        ),
        redis_auth_token=_secret_value(
            config,
            "redisAuthToken",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("redis-auth-token"),
        ),
        app_secret=_secret_value(
            config,
            "appSecret",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("app-secret"),
        ),
        mailer_dsn=_secret_value(
            config,
            "mailerDsn",
            managed=deployment_mode == "managed",
            preview_default="smtp://mailer.internal:587",
        ),
        oauth_encryption_key=_secret_value(
            config,
            "oauthEncryptionKey",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("oauth-encryption-key"),
        ),
        oauth_passphrase=_secret_value(
            config,
            "oauthPassphrase",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("oauth-passphrase"),
        ),
        two_factor_encryption_key=_secret_value(
            config,
            "twoFactorEncryptionKey",
            managed=deployment_mode == "managed",
            preview_default=_preview_placeholder("two-factor-encryption-key"),
        ),
        oauth_private_key_pem=_secret_value(
            config,
            "oauthPrivateKeyPem",
            managed=deployment_mode == "managed",
            preview_default="preview-private-key",
        ),
        oauth_public_key_pem=_secret_value(
            config,
            "oauthPublicKeyPem",
            managed=deployment_mode == "managed",
            preview_default="preview-public-key",
        ),
        github_client_secret=_secret_value(
            config,
            "githubClientSecret",
            managed=deployment_mode == "managed" and bool(social.github_client_id),
            preview_default="",
        ),
        google_client_secret=_secret_value(
            config,
            "googleClientSecret",
            managed=deployment_mode == "managed" and bool(social.google_client_id),
            preview_default="",
        ),
        facebook_client_secret=_secret_value(
            config,
            "facebookClientSecret",
            managed=deployment_mode == "managed" and bool(social.facebook_client_id),
            preview_default="",
        ),
        twitter_client_secret=_secret_value(
            config,
            "twitterClientSecret",
            managed=deployment_mode == "managed" and bool(social.twitter_client_id),
            preview_default="",
        ),
    )

    return StackSettings(
        environment=environment,
        service_name=service_name,
        owner=owner,
        cost_center=cost_center,
        stack_tag=stack_tag,
        default_tags=default_tags,
        region=region,
        deployment_mode=deployment_mode,
        network=network,
        capacity=capacity,
        documentdb=documentdb,
        redis=redis,
        images=images,
        queues=queues,
        runtime=runtime,
        social=social,
        secrets=secrets,
    )
