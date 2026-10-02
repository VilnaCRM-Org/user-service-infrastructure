"""Service-owned VPC flow-log storage for the hardened workload graph (S3.1).

FR-15: one flow log (``traffic_type=ALL``) delivers every VPC record to a
dedicated S3 bucket. The bucket uses SSE-KMS with the contract's runtime CMK
(D-4) and a bucket key, blocks public access, enforces bucket-owner object
ownership, keeps ``force_destroy=false`` and expires records after 30 days in
TEST and 90 days in PROD. Its policy denies non-TLS access and lets only
``delivery.logs.amazonaws.com`` write ``AWSLogs/<acct>/*`` and read the bucket
ACL, each bound to ``aws:SourceAccount`` and ``aws:SourceArn``. No IAM role is
used: S3 delivery runs as the log-delivery service. The runtime key policy
grant for that service is governance-owned (V-16). SSE-S3 is not a fallback.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import pulumi_aws as aws

import pulumi
from app.environment import StackSettings
from app.observability import require_runtime_cmk

__all__ = [
    "FLOW_LOG_DELIVERY_SERVICE",
    "FlowLogs",
    "flow_log_bucket_arn",
    "flow_log_bucket_name",
    "flow_log_bucket_policy",
    "flow_log_encryption_rule",
    "flow_log_retention_days",
    "require_retained_bucket",
    "require_reviewed_flow_log_policy",
    "require_roleless_flow_log",
    "require_runtime_cmk_encryption",
]

FLOW_LOG_DELIVERY_SERVICE = "delivery.logs.amazonaws.com"
# FR-15 retention: 30 days in TEST, 90 days in PROD.
RETENTION_DAYS = {"test": 30, "prod": 90}
# A log-delivery destination cannot usefully log to itself; the policy pack
# accepts this reviewed exemption only with a stated reason.
LOGGING_EXEMPTION = {
    "LoggingExempt": "true",
    "LoggingExemptReason": "VPC flow-log destination bucket",
}
# The flow-log arguments that would make delivery assume an IAM role.
ROLE_ARGUMENTS = ("iam_role_arn", "deliver_cross_account_role")


def flow_log_bucket_name(settings: StackSettings, account_id: str) -> str:
    """Name the bucket from the stack tag and the account, like the ALB logs."""
    return f"{settings.stack_tag}-{account_id}-flow-logs"


def flow_log_bucket_arn(bucket_name: str) -> str:
    """Build the bucket ARN from its name, so the policy is known at preview."""
    return f"arn:aws:s3:::{bucket_name}"


def flow_log_retention_days(environment: str) -> int:
    """Return the FR-15 expiry for a shared environment; any other fails."""
    if environment not in RETENTION_DAYS:
        raise ValueError("Flow-log retention requires the test or prod environment")
    return RETENTION_DAYS[environment]


def require_retained_bucket(force_destroy: Any) -> bool:
    """Refuse ``force_destroy`` on the flow-log bucket (FR-15)."""
    if force_destroy is not False:
        raise ValueError("Flow-log bucket must keep force_destroy=false")
    return force_destroy


def flow_log_encryption_rule(runtime_cmk_arn: str) -> dict[str, Any]:
    """Render the SSE-KMS default rule on the runtime CMK with a bucket key."""
    return {
        "apply_server_side_encryption_by_default": {
            "sse_algorithm": "aws:kms",
            "kms_master_key_id": runtime_cmk_arn,
        },
        "bucket_key_enabled": True,
    }


def require_runtime_cmk_encryption(rule: Any, runtime_cmk_arn: str) -> dict[str, Any]:
    """Fail closed unless the rule is SSE-KMS on the runtime CMK with a bucket key.

    SSE-S3 (``AES256``), SSE-KMS with any other key or no key, and a rule
    without the bucket key fail (D-4: SSE-S3 is not a fallback).
    """
    key = require_runtime_cmk(runtime_cmk_arn)
    if rule != flow_log_encryption_rule(key):
        raise ValueError("Flow-log bucket must use SSE-KMS with the runtime CMK")
    return rule


def require_roleless_flow_log(arguments: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on an IAM role argument or a partial traffic type (FR-15)."""
    if any(arguments.get(key) is not None for key in ROLE_ARGUMENTS):
        raise ValueError("Flow log must not use an IAM role")
    if (arguments.get("traffic_type"), arguments.get("log_destination_type")) != (
        "ALL",
        "s3",
    ):
        raise ValueError("Flow log must send ALL traffic to S3")
    return arguments


def _delivery_condition(region: str, account_id: str) -> dict[str, Any]:
    """Bind a delivery statement to this account's log-delivery sources."""
    return {
        "StringEquals": {"aws:SourceAccount": account_id},
        "ArnLike": {"aws:SourceArn": f"arn:aws:logs:{region}:{account_id}:*"},
    }


def flow_log_bucket_policy(
    bucket_arn: str, region: str, account_id: str
) -> dict[str, Any]:
    """Render the TLS-only deny and the two log-delivery allows (FR-15)."""
    condition = _delivery_condition(region, account_id)
    service = {"Service": FLOW_LOG_DELIVERY_SERVICE}
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [bucket_arn, f"{bucket_arn}/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            },
            {
                "Sid": "AWSLogDeliveryWrite",
                "Effect": "Allow",
                "Principal": service,
                "Action": "s3:PutObject",
                "Resource": f"{bucket_arn}/AWSLogs/{account_id}/*",
                "Condition": condition,
            },
            {
                "Sid": "AWSLogDeliveryAclCheck",
                "Effect": "Allow",
                "Principal": service,
                "Action": "s3:GetBucketAcl",
                "Resource": bucket_arn,
                "Condition": condition,
            },
        ],
    }


def require_reviewed_flow_log_policy(
    policy: Any, bucket_arn: str, region: str, account_id: str
) -> dict[str, Any]:
    """Fail closed unless the policy is exactly the reviewed FR-15 document.

    A missing TLS deny, a delivery statement without ``aws:SourceArn`` or
    ``aws:SourceAccount``, another principal, action or resource, or any
    extra statement fails.
    """
    if type(policy) is not dict or type(policy.get("Statement")) is not list:
        raise ValueError("Flow-log bucket policy is not a statement list")
    if policy != flow_log_bucket_policy(bucket_arn, region, account_id):
        raise ValueError("Flow-log bucket policy is not the reviewed document")
    return policy


class FlowLogs(pulumi.ComponentResource):
    """Own the flow-log bucket family and the role-less VPC flow log (AD-12)."""

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        vpc_id: pulumi.Input[str],
        account_id: str,
        runtime_cmk_arn: str,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Validate every reviewed document, then declare the bucket and log.

        The bucket name and ARN come from the stack tag and the account, so
        the policy is a plain string at preview. The flow log waits for the
        bucket controls and the delivery policy.
        """
        bucket_name = flow_log_bucket_name(settings, account_id)
        bucket_arn = flow_log_bucket_arn(bucket_name)
        encryption_rule = require_runtime_cmk_encryption(
            flow_log_encryption_rule(runtime_cmk_arn), runtime_cmk_arn
        )
        policy = require_reviewed_flow_log_policy(
            flow_log_bucket_policy(bucket_arn, settings.region, account_id),
            bucket_arn,
            settings.region,
            account_id,
        )
        expiry = flow_log_retention_days(settings.environment)
        super().__init__(
            "user-service-infrastructure:network:FlowLogs", name, None, opts
        )
        self.bucket = aws.s3.BucketV2(
            "user-service-flow-logs",
            bucket=bucket_name,
            force_destroy=require_retained_bucket(False),
            tags={**settings.default_tags, **LOGGING_EXEMPTION},
            opts=pulumi.ResourceOptions(parent=self, protect=True),
        )
        child = pulumi.ResourceOptions(parent=self)
        controls = [
            aws.s3.BucketOwnershipControls(
                "user-service-flow-logs-ownership",
                bucket=self.bucket.id,
                rule={"object_ownership": "BucketOwnerEnforced"},
                opts=child,
            ),
            aws.s3.BucketPublicAccessBlock(
                "user-service-flow-logs-public-access",
                bucket=self.bucket.id,
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True,
                opts=child,
            ),
            aws.s3.BucketServerSideEncryptionConfigurationV2(
                "user-service-flow-logs-encryption",
                bucket=self.bucket.id,
                rules=[encryption_rule],
                opts=child,
            ),
            aws.s3.BucketLifecycleConfigurationV2(
                "user-service-flow-logs-retention",
                bucket=self.bucket.id,
                rules=[
                    {
                        "id": "flow-log-retention",
                        "status": "Enabled",
                        "filter": {"prefix": "AWSLogs/"},
                        "expiration": {"days": expiry},
                        "abort_incomplete_multipart_upload": {
                            "days_after_initiation": 7
                        },
                    }
                ],
                opts=child,
            ),
        ]
        bucket_policy = aws.s3.BucketPolicy(
            "user-service-flow-logs-policy",
            bucket=self.bucket.id,
            policy=json.dumps(policy, separators=(",", ":")),
            opts=pulumi.ResourceOptions(parent=self, depends_on=controls),
        )
        arguments = require_roleless_flow_log(
            {
                "vpc_id": vpc_id,
                "traffic_type": "ALL",
                "log_destination_type": "s3",
                "log_destination": self.bucket.arn,
            }
        )
        self.flow_log = aws.ec2.FlowLog(
            "user-service-vpc-flow-log",
            **arguments,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[bucket_policy]),
        )
        self.register_outputs({"bucket": self.bucket.bucket})
