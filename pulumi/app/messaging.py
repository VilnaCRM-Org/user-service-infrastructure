"""SQS queues and narrowly scoped health-check credentials."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import pulumi_aws as aws

import pulumi
from app.environment import StackSettings, build_resource_name

__all__ = ["MessagingPlane"]


@dataclass(frozen=True)
class MessagingOutputs:
    """Messaging resources consumed by the compute plane."""

    queue_urls: dict[str, pulumi.Input[str]]
    queue_arns: dict[str, pulumi.Input[str]]
    health_check_access_key_id: pulumi.Input[str]
    health_check_secret_arn: pulumi.Input[str]


class MessagingPlane(pulumi.ComponentResource):
    """Provision application queues and the health-check IAM user."""

    outputs: MessagingOutputs

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Build preview-safe outputs or provision managed queue resources."""
        super().__init__(
            "user-service-infrastructure:messaging:Plane",
            name,
            None,
            opts,
        )

        self.outputs = (
            self._build_managed_outputs(settings)
            if settings.is_managed
            else self._build_preview_outputs(settings)
        )
        self.register_outputs(
            {
                "queueUrls": self.outputs.queue_urls,
                "queueArns": self.outputs.queue_arns,
                "healthCheckAccessKeyId": self.outputs.health_check_access_key_id,
                "healthCheckSecretArn": self.outputs.health_check_secret_arn,
            }
        )

    def _build_preview_outputs(self, settings: StackSettings) -> MessagingOutputs:
        """Return deterministic queue URLs and secret placeholders."""
        queue_names = self._queue_names(settings)
        queue_urls = {
            key: pulumi.Output.from_input(
                f"https://sqs.{settings.region}.amazonaws.com/preview/{value}"
            )
            for key, value in queue_names.items()
        }
        queue_arns = {
            key: pulumi.Output.from_input(
                f"arn:aws:sqs:{settings.region}:preview:{value}"
            )
            for key, value in queue_names.items()
        }
        return MessagingOutputs(
            queue_urls=queue_urls,
            queue_arns=queue_arns,
            health_check_access_key_id=pulumi.Output.from_input(
                build_resource_name(settings.stack_tag, "healthcheck-key")
            ),
            health_check_secret_arn=pulumi.Output.from_input(
                f"arn:aws:secretsmanager:{settings.region}:preview:"
                f"{build_resource_name(settings.stack_tag, 'healthcheck-secret')}"
            ),
        )

    def _build_managed_outputs(self, settings: StackSettings) -> MessagingOutputs:
        """Create queue topology plus a dedicated health-check IAM user."""
        failed_send_email = self._create_queue(
            logical_name="failed-send-email",
            queue_name=settings.queues.failed_send_email,
            retention_seconds=1_209_600,
            settings=settings,
        )
        failed_domain_events = self._create_queue(
            logical_name="failed-domain-events",
            queue_name=settings.queues.failed_domain_events,
            retention_seconds=1_209_600,
            settings=settings,
        )
        send_email = self._create_queue(
            logical_name="send-email",
            queue_name=settings.queues.send_email,
            settings=settings,
            redrive_policy=self._redrive_policy(failed_send_email.arn),
        )
        insert_user_batch = self._create_queue(
            logical_name="insert-user-batch",
            queue_name=settings.queues.insert_user_batch,
            settings=settings,
        )
        domain_events = self._create_queue(
            logical_name="domain-events",
            queue_name=settings.queues.domain_events,
            settings=settings,
            redrive_policy=self._redrive_policy(failed_domain_events.arn),
        )
        health_check = self._create_queue(
            logical_name="health-check",
            queue_name=settings.queues.health_check,
            settings=settings,
        )

        queue_urls = {
            "sendEmail": send_email.id,
            "failedSendEmail": failed_send_email.id,
            "insertUserBatch": insert_user_batch.id,
            "domainEvents": domain_events.id,
            "failedDomainEvents": failed_domain_events.id,
            "healthCheck": health_check.id,
        }
        queue_arns = {
            "sendEmail": send_email.arn,
            "failedSendEmail": failed_send_email.arn,
            "insertUserBatch": insert_user_batch.arn,
            "domainEvents": domain_events.arn,
            "failedDomainEvents": failed_domain_events.arn,
            "healthCheck": health_check.arn,
        }

        health_check_user = aws.iam.User(
            "user-service-healthcheck-user",
            name=build_resource_name(settings.stack_tag, "healthcheck", max_length=64),
            opts=pulumi.ResourceOptions(parent=self),
        )
        aws.iam.UserPolicy(
            "user-service-healthcheck-policy",
            user=health_check_user.name,
            policy=health_check.arn.apply(self._health_check_policy_json),
            opts=pulumi.ResourceOptions(parent=self),
        )

        access_key = aws.iam.AccessKey(
            "user-service-healthcheck-access-key",
            user=health_check_user.name,
            opts=pulumi.ResourceOptions(parent=self),
        )
        health_check_secret = aws.secretsmanager.Secret(
            "user-service-healthcheck-secret",
            description="Static SQS secret used only by the app health-check client.",
            opts=pulumi.ResourceOptions(parent=self),
        )
        aws.secretsmanager.SecretVersion(
            "user-service-healthcheck-secret-version",
            secret_id=health_check_secret.id,
            secret_string=access_key.secret,
            opts=pulumi.ResourceOptions(parent=self),
        )

        return MessagingOutputs(
            queue_urls=queue_urls,
            queue_arns=queue_arns,
            health_check_access_key_id=access_key.id,
            health_check_secret_arn=health_check_secret.arn,
        )

    def _create_queue(
        self,
        *,
        logical_name: str,
        queue_name: str,
        settings: StackSettings,
        retention_seconds: int = 345_600,
        redrive_policy: pulumi.Input[str] | None = None,
    ) -> aws.sqs.Queue:
        """Create an encrypted SQS queue with long polling enabled."""
        return aws.sqs.Queue(
            f"user-service-{logical_name}",
            name=queue_name,
            message_retention_seconds=retention_seconds,
            receive_wait_time_seconds=20,
            visibility_timeout_seconds=120,
            kms_master_key_id="alias/aws/sqs",
            redrive_policy=redrive_policy,
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _queue_names(self, settings: StackSettings) -> dict[str, str]:
        """Return queue names in a stable logical order."""
        return {
            "sendEmail": settings.queues.send_email,
            "failedSendEmail": settings.queues.failed_send_email,
            "insertUserBatch": settings.queues.insert_user_batch,
            "domainEvents": settings.queues.domain_events,
            "failedDomainEvents": settings.queues.failed_domain_events,
            "healthCheck": settings.queues.health_check,
        }

    def _redrive_policy(self, dead_letter_arn: pulumi.Input[str]) -> pulumi.Output[str]:
        """Render the queue redrive policy JSON."""
        return pulumi.Output.from_input(dead_letter_arn).apply(
            lambda arn: json.dumps(
                {
                    "deadLetterTargetArn": arn,
                    "maxReceiveCount": 3,
                }
            )
        )

    def _health_check_policy_json(self, queue_arn: str) -> str:
        """Limit the health-check IAM user to readonly queue access."""
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "HealthCheckQueueAccess",
                        "Effect": "Allow",
                        "Action": [
                            "sqs:GetQueueAttributes",
                            "sqs:GetQueueUrl",
                        ],
                        "Resource": [queue_arn],
                    }
                ],
            }
        )
