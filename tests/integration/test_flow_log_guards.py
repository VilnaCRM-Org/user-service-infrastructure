"""Fail-closed guards of the S3.1 flow logs in the integration suite.

The integration coverage gate includes ``pulumi/app``. The hardened graph
renders only the reviewed flow log and bucket family, so these cases drive the
refusals directly: an IAM role or partial traffic on the flow log, a
force-destroy bucket, SSE-S3 or another key, an unreviewed bucket policy and
an environment without a FR-15 retention (FR-15).
"""

import pytest
from app.flow_logs import (
    flow_log_bucket_policy,
    flow_log_retention_days,
    require_retained_bucket,
    require_reviewed_flow_log_policy,
    require_roleless_flow_log,
    require_runtime_cmk_encryption,
)
from app.workload_phase import _reject_secret_material

import pulumi

ACCOUNT = "891377212104"
REGION = "eu-central-1"
BUCKET_ARN = "arn:aws:s3:::user-service-infrastructure-test-891377212104-flow-logs"
RUNTIME_CMK = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000010"
)


def _args(kind, props):
    return pulumi.ResourceTransformationArgs(
        resource=None, type_=kind, name="probe", props=props, opts=None
    )


@pytest.mark.parametrize(
    ("kind", "props"),
    [
        (
            "aws:ec2/flowLog:FlowLog",
            {
                "traffic_type": "ALL",
                "log_destination_type": "s3",
                "iam_role_arn": "arn:aws:iam::891377212104:role/fixture",
            },
        ),
        (
            "aws:ec2/flowLog:FlowLog",
            {"traffic_type": "REJECT", "log_destination_type": "s3"},
        ),
        ("aws:s3/bucketV2:BucketV2", {"force_destroy": True}),
    ],
)
def test_a_role_partial_flow_log_or_force_destroy_fails_the_guard(kind, props):
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_args(kind, props))


def test_a_roleless_flow_log_and_a_retained_bucket_pass_the_guard():
    flow_log = {"traffic_type": "ALL", "log_destination_type": "s3"}
    assert _reject_secret_material(_args("aws:ec2/flowLog:FlowLog", flow_log)) is None
    bucket = {"force_destroy": False}
    assert _reject_secret_material(_args("aws:s3/bucketV2:BucketV2", bucket)) is None


def test_the_component_validators_fail_closed():
    with pytest.raises(ValueError, match="IAM role"):
        require_roleless_flow_log(
            {"traffic_type": "ALL", "log_destination_type": "s3", "iam_role_arn": "r"}
        )
    with pytest.raises(ValueError, match="ALL traffic"):
        require_roleless_flow_log({"traffic_type": "ACCEPT"})
    with pytest.raises(ValueError, match="force_destroy=false"):
        require_retained_bucket(True)
    with pytest.raises(ValueError, match="runtime CMK"):
        require_runtime_cmk_encryption(
            {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}},
            RUNTIME_CMK,
        )
    with pytest.raises(ValueError, match="test or prod"):
        flow_log_retention_days("smoke")


def test_an_unreviewed_bucket_policy_fails():
    with pytest.raises(ValueError, match="statement list"):
        require_reviewed_flow_log_policy({}, BUCKET_ARN, REGION, ACCOUNT)
    policy = flow_log_bucket_policy(BUCKET_ARN, REGION, ACCOUNT)
    policy["Statement"] = policy["Statement"][1:]
    with pytest.raises(ValueError, match="reviewed document"):
        require_reviewed_flow_log_policy(policy, BUCKET_ARN, REGION, ACCOUNT)
