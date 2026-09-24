"""SQS queues consumed through centrally owned ECS task roles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import pulumi_aws as aws

import pulumi
from app.environment import StackSettings, validate_health_check_runtime

__all__ = ["MessagingPlane"]


@dataclass(frozen=True)
class MessagingOutputs:
    """Messaging resources consumed by the compute plane."""

    queue_urls: dict[str, pulumi.Input[str]]
    queue_arns: dict[str, pulumi.Input[str]]


class MessagingPlane(pulumi.ComponentResource):
    """Provision application queues, including the read-only health-check target."""

    outputs: MessagingOutputs

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Build preview-safe outputs or provision managed queue resources."""
        if settings.is_managed:
            validate_health_check_runtime(settings.runtime, settings.queues)
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
            }
        )

    def _build_preview_outputs(self, settings: StackSettings) -> MessagingOutputs:
        """Return deterministic queue URLs without credentials."""
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
        )

    def _build_managed_outputs(self, settings: StackSettings) -> MessagingOutputs:
        """Create the six queues without service-owned IAM or credentials."""
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

        return MessagingOutputs(
            queue_urls=queue_urls,
            queue_arns=queue_arns,
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
