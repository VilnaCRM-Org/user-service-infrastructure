"""Compute plane for ECS, ALB, and runtime secret delivery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import pulumi_aws as aws

import pulumi
from app.data import DataPlane
from app.environment import (
    StackSettings,
    build_resource_name,
    validate_health_check_runtime,
    validate_runtime_roles,
)
from app.messaging import MessagingPlane
from app.network import NetworkPlane
from app.registry import RegistryOutputs

__all__ = ["ComputePlane"]


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


class ComputePlane(pulumi.ComponentResource):
    """Provision ECS/Fargate, ALB and runtime secrets using caller-owned registries."""

    outputs: ComputeOutputs

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        network: NetworkPlane,
        data: DataPlane,
        messaging: MessagingPlane,
        registries: RegistryOutputs | None = None,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Build preview-safe outputs or provision the managed compute plane."""
        if settings.is_managed:
            validate_runtime_roles(settings.runtime, settings.environment)
            validate_health_check_runtime(settings.runtime, settings.queues)
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

        runtime_secrets = self._create_runtime_secrets(settings)
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

        load_balancer = aws.lb.LoadBalancer(
            "user-service-alb",
            name=build_resource_name(settings.stack_tag, "alb", max_length=32),
            internal=False,
            load_balancer_type="application",
            security_groups=[network.outputs.alb_security_group_id],
            subnets=network.outputs.public_subnet_ids,
            access_logs=aws.lb.LoadBalancerAccessLogsArgs(
                bucket=settings.runtime.access_logs_bucket_name,
                enabled=True,
                prefix=f"{settings.stack_tag}/alb",
            ),
            drop_invalid_header_fields=True,
            idle_timeout=60,
            opts=pulumi.ResourceOptions(parent=self),
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
        )

        web_task_definition = aws.ecs.TaskDefinition(
            "user-service-web-task",
            family=build_resource_name(settings.stack_tag, "web", max_length=255),
            cpu=settings.capacity.web_cpu,
            memory=settings.capacity.web_memory,
            network_mode="awsvpc",
            requires_compatibilities=["FARGATE"],
            execution_role_arn=settings.runtime.execution_role_arn,
            task_role_arn=settings.runtime.task_role_arn,
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
            execution_role_arn=settings.runtime.execution_role_arn,
            task_role_arn=settings.runtime.task_role_arn,
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
            desired_count=settings.capacity.web_desired_count,
            launch_type="FARGATE",
            platform_version="LATEST",
            enable_execute_command=True,
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
            wait_for_steady_state=False,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[http_listener]),
        )

        worker_service = aws.ecs.Service(
            "user-service-worker-service",
            name=build_resource_name(settings.stack_tag, "worker", max_length=255),
            cluster=cluster.arn,
            task_definition=worker_task_definition.arn,
            desired_count=settings.capacity.worker_desired_count,
            launch_type="FARGATE",
            platform_version="LATEST",
            enable_execute_command=True,
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
            wait_for_steady_state=False,
            opts=pulumi.ResourceOptions(parent=self),
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

    def _create_repository_lifecycle(
        self,
        *,
        logical_name: str,
        repository_name: pulumi.Input[str],
    ) -> None:
        """Retain existing image lifecycle policy without owning the repository."""
        aws.ecr.LifecyclePolicy(
            f"user-service-{logical_name}-lifecycle",
            repository=repository_name,
            policy=json.dumps(
                {
                    "rules": [
                        {
                            "rulePriority": 1,
                            "description": "Retain the most recent production images.",
                            "selection": {
                                "tagStatus": "any",
                                "countType": "imageCountMoreThan",
                                "countNumber": 30,
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
        definitions = {
            "app-secret": settings.secrets.app_secret,
            "mailer-dsn": settings.secrets.mailer_dsn,
            "oauth-encryption-key": settings.secrets.oauth_encryption_key,
            "oauth-passphrase": settings.secrets.oauth_passphrase,
            "twofactor-encryption-key": settings.secrets.two_factor_encryption_key,
            "oauth-private-key": settings.secrets.oauth_private_key_pem,
            "oauth-public-key": settings.secrets.oauth_public_key_pem,
            "github-client-secret": settings.secrets.github_client_secret,
            "google-client-secret": settings.secrets.google_client_secret,
            "facebook-client-secret": settings.secrets.facebook_client_secret,
            "twitter-client-secret": settings.secrets.twitter_client_secret,
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
    ) -> aws.lb.Listener:
        """Create HTTP and optional HTTPS listeners."""
        if settings.runtime.certificate_arn is None:
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
            ),
            secrets=self._common_secrets(data, runtime_secret_arns),
            port_mappings=[
                {
                    "containerPort": settings.capacity.container_port,
                    "hostPort": settings.capacity.container_port,
                    "protocol": "tcp",
                }
            ],
        )

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
                self._bootstrap_command(
                    "/usr/bin/supervisord -c /etc/supervisor/supervisord.conf"
                ),
            ],
            image=image,
            region=settings.region,
            log_group_name=log_group_name,
            environment=self._common_environment(
                settings,
                messaging,
                include_worker_name=True,
            ),
            secrets=self._common_secrets(data, runtime_secret_arns),
            port_mappings=None,
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
    ) -> pulumi.Output[str]:
        """Serialize a single-container task definition."""
        return pulumi.Output.all(
            image,
            pulumi.Output.from_input(environment),
            pulumi.Output.from_input(secrets),
            log_group_name,
        ).apply(
            lambda parts: json.dumps(
                [
                    {
                        "name": name,
                        "image": parts[0],
                        "essential": True,
                        "command": command,
                        "environment": parts[1],
                        "secrets": parts[2],
                        "portMappings": port_mappings or [],
                        "logConfiguration": {
                            "logDriver": "awslogs",
                            "options": {
                                "awslogs-group": parts[3],
                                "awslogs-region": region,
                                "awslogs-stream-prefix": name,
                            },
                        },
                    }
                ]
            )
        )

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
        return environment

    def _common_secrets(
        self,
        data: DataPlane,
        runtime_secret_arns: dict[str, pulumi.Input[str]],
    ) -> list[dict[str, pulumi.Input[str]]]:
        """Build the ECS secrets mapping used by both services."""
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
        """Build the Symfony SQS DSN from the full queue URL."""
        return pulumi.Output.from_input(queue_url).apply(
            lambda value: f"{value}?region={region}&auto_setup=false"
        )
