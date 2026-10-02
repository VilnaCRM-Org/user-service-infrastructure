"""Service-owned alarm topic, the head of the observability plane (AD-11).

S2.3 adds one SNS topic encrypted with the D-4 runtime CMK (D-8: CloudWatch
alarms cannot publish to a topic on the AWS-managed ``alias/aws/sns`` key) and
its topic policy, which lets only CloudWatch and EventBridge in the workload
account publish (FR-13). The alarms (S2.4) and EventBridge rules (S2.5) join
this plane later. The subscription endpoint is XP-6, so no subscription exists.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import pulumi_aws as aws

import pulumi
from app.environment import StackSettings

__all__ = [
    "ALARM_TOPIC_PUBLISHERS",
    "ObservabilityPlane",
    "alarm_topic_policy",
    "require_reviewed_topic_policy",
    "require_runtime_cmk",
]

# The only principals that may publish to the alarm topic (FR-13).
ALARM_TOPIC_PUBLISHERS = ("cloudwatch.amazonaws.com", "events.amazonaws.com")
ALARM_TOPIC_ACTION = "sns:Publish"
# AWS reserves ``alias/aws/``; an AWS-managed key is never the runtime CMK.
AWS_MANAGED_KEY_PREFIX = "alias/aws/"
_KMS_KEY_ARN = re.compile(r"arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]+")
_ACCOUNT_ID = re.compile(r"[0-9]{12}")


def require_runtime_cmk(key: Any) -> str:
    """Return ``key`` only if it is a customer-managed KMS key ARN (D-4, D-8).

    No key, an ``alias/aws/`` key such as ``alias/aws/sns``, an alias or any
    value that is not a key ARN fails closed. The hardened guard then binds the
    rendered topic to the contract's ``central.cmk.runtime.arn`` exactly.
    """
    if type(key) is str and key.startswith(AWS_MANAGED_KEY_PREFIX):
        raise ValueError("Alarm topic must not use an AWS-managed key")
    if type(key) is not str or not _KMS_KEY_ARN.fullmatch(key):
        raise ValueError("Alarm topic must use the runtime CMK key ARN")
    return key


def _require_account(account_id: Any) -> str:
    """Accept only a 12-digit AWS account ID."""
    if type(account_id) is not str or not _ACCOUNT_ID.fullmatch(account_id):
        raise ValueError("Alarm topic policy requires the workload account ID")
    return account_id


def alarm_topic_policy(topic_arn: str, account_id: str) -> dict[str, Any]:
    """Render one ``sns:Publish`` allow per publisher, bound to the account."""
    _require_account(account_id)
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": f"Allow{publisher.split('.')[0].title()}Publish",
                "Effect": "Allow",
                "Principal": {"Service": publisher},
                "Action": ALARM_TOPIC_ACTION,
                "Resource": topic_arn,
                "Condition": {"StringEquals": {"aws:SourceAccount": account_id}},
            }
            for publisher in ALARM_TOPIC_PUBLISHERS
        ],
    }


def _reviewed_statement(statement: Any, account_id: str) -> str | None:
    """Return the publisher of one reviewed statement, or ``None``.

    The statement must hold exactly the reviewed keys: an ``Allow`` of
    ``sns:Publish`` for one service principal, conditioned only on
    ``aws:SourceAccount`` equal to the workload account.
    """
    if type(statement) is not dict or set(statement) != {
        "Sid",
        "Effect",
        "Principal",
        "Action",
        "Resource",
        "Condition",
    }:
        return None
    principal = statement["Principal"]
    publisher = principal.get("Service") if type(principal) is dict else None
    reviewed = (
        statement["Effect"] == "Allow"
        and statement["Action"] == ALARM_TOPIC_ACTION
        and set(principal) == {"Service"}
        and publisher in ALARM_TOPIC_PUBLISHERS
        and statement["Condition"]
        == {"StringEquals": {"aws:SourceAccount": account_id}}
    )
    return publisher if reviewed else None


def require_reviewed_topic_policy(policy: Any, account_id: str) -> dict[str, Any]:
    """Fail closed unless the policy allows exactly the two publishers (FR-13).

    Every statement must be a reviewed allow with the ``aws:SourceAccount``
    condition; a missing condition, another principal, a wildcard principal,
    another action or a repeated publisher fails.
    """
    _require_account(account_id)
    statements = policy.get("Statement") if type(policy) is dict else None
    if type(statements) is not list:
        raise ValueError("Alarm topic policy is not a statement list")
    publishers = [_reviewed_statement(entry, account_id) for entry in statements]
    if sorted(map(str, publishers)) != sorted(ALARM_TOPIC_PUBLISHERS):
        raise ValueError("Alarm topic policy grants an unreviewed publisher")
    return policy


class ObservabilityPlane(pulumi.ComponentResource):
    """Own the encrypted alarm topic and its publish policy (AD-11)."""

    topic_arn: pulumi.Output[str]

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        runtime_cmk_arn: str,
        account_id: str,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Validate the key and account, then declare the topic and its policy."""
        key = require_runtime_cmk(runtime_cmk_arn)
        _require_account(account_id)
        super().__init__(
            "user-service-infrastructure:observability:Plane", name, None, opts
        )
        topic = aws.sns.Topic(
            "user-service-alarms",
            name=f"{settings.stack_tag}-alarms",
            kms_master_key_id=key,
            opts=pulumi.ResourceOptions(parent=self),
        )
        aws.sns.TopicPolicy(
            "user-service-alarms-policy",
            arn=topic.arn,
            policy=topic.arn.apply(
                lambda arn: json.dumps(
                    require_reviewed_topic_policy(
                        alarm_topic_policy(arn, account_id), account_id
                    )
                )
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.topic_arn = topic.arn
        self.register_outputs({"topicArn": self.topic_arn})
