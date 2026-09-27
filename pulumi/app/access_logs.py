"""Service-owned ALB log storage for the generated TEST workload graph."""

from __future__ import annotations

import json

import pulumi_aws as aws

import pulumi
from app.environment import StackSettings, build_resource_name


class AlbAccessLogs(pulumi.ComponentResource):
    """Keep delivery, encryption and retention under the existing compute owner."""

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        account_id: str,
        opts: pulumi.ResourceOptions,
    ) -> None:
        super().__init__(
            "user-service-infrastructure:compute:AccessLogs", name, None, opts
        )
        self.prefix = f"{settings.stack_tag}/alb"
        bucket_name = f"{settings.stack_tag}-{account_id}-alb-logs"
        self.bucket = aws.s3.BucketV2(
            "user-service-alb-logs",
            bucket=bucket_name,
            force_destroy=False,
            tags=settings.default_tags,
            opts=pulumi.ResourceOptions(parent=self, protect=True),
        )
        child = pulumi.ResourceOptions(parent=self)
        ownership = aws.s3.BucketOwnershipControls(
            "user-service-alb-logs-ownership",
            bucket=self.bucket.id,
            rule={"object_ownership": "BucketOwnerEnforced"},
            opts=child,
        )
        public_access = aws.s3.BucketPublicAccessBlock(
            "user-service-alb-logs-public-access",
            bucket=self.bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=child,
        )
        encryption = aws.s3.BucketServerSideEncryptionConfigurationV2(
            "user-service-alb-logs-encryption",
            bucket=self.bucket.id,
            rules=[
                {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}}
            ],
            opts=child,
        )
        versioning = aws.s3.BucketVersioningV2(
            "user-service-alb-logs-versioning",
            bucket=self.bucket.id,
            versioning_configuration={"status": "Enabled"},
            opts=child,
        )
        lifecycle = aws.s3.BucketLifecycleConfigurationV2(
            "user-service-alb-logs-retention",
            bucket=self.bucket.id,
            rules=[
                {
                    "id": "alb-access-log-retention",
                    "status": "Enabled",
                    "filter": {"prefix": self.prefix + "/"},
                    "expiration": {"days": 90},
                    "noncurrent_version_expiration": {"noncurrent_days": 30},
                    "abort_incomplete_multipart_upload": {"days_after_initiation": 7},
                }
            ],
            opts=pulumi.ResourceOptions(parent=self, depends_on=[versioning]),
        )
        self.policy = aws.s3.BucketPolicy(
            "user-service-alb-logs-policy",
            bucket=self.bucket.id,
            policy=self.bucket.arn.apply(
                lambda arn: delivery_policy(arn, self.prefix, account_id, settings)
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[
                    ownership,
                    public_access,
                    encryption,
                    versioning,
                    lifecycle,
                ],
            ),
        )
        self.register_outputs({"bucket": self.bucket.bucket, "prefix": self.prefix})


def delivery_policy(
    bucket_arn: str, prefix: str, account_id: str, settings: StackSettings
) -> str:
    """Allow this named regional ALB's delivery and require TLS for API clients."""
    alb_name = build_resource_name(settings.stack_tag, "alb", max_length=32)
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowAlbLogDelivery",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "logdelivery.elasticloadbalancing.amazonaws.com"
                    },
                    "Action": "s3:PutObject",
                    "Resource": f"{bucket_arn}/{prefix}/AWSLogs/{account_id}/*",
                    "Condition": {
                        "ArnLike": {
                            "aws:SourceArn": (
                                f"arn:aws:elasticloadbalancing:{settings.region}:"
                                f"{account_id}:loadbalancer/app/{alb_name}/*"
                            )
                        }
                    },
                },
                {
                    "Sid": "DenyInsecureClientTransport",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [bucket_arn, bucket_arn + "/*"],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false",
                            "aws:PrincipalIsAWSService": "false",
                        }
                    },
                },
            ],
        },
        separators=(",", ":"),
    )
