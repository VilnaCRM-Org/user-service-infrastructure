"""VPC flow logs to a runtime-CMK S3 bucket (S3.1, FR-15).

FR-15: one flow log with ``traffic_type`` ``ALL`` to a service-owned bucket and
no IAM role. The bucket uses SSE-KMS with the runtime CMK and a bucket key,
blocks public access, enforces ``BucketOwnerEnforced``, keeps
``force_destroy=false`` and expires records after 30 days in TEST (90 in
PROD). Its policy denies non-TLS access and allows only
``delivery.logs.amazonaws.com`` ``s3:PutObject`` on ``AWSLogs/<acct>/*`` and
``s3:GetBucketAcl``, each with ``aws:SourceAccount`` and ``aws:SourceArn``.
N: an IAM role argument, a bucket without TLS-only, a delivery statement
without ``aws:SourceArn``, SSE-S3, SSE-KMS with another key, or
``force_destroy=true`` fails. The FR-15 N row "SSE-KMS without the delivery
principal in the runtime key policy fails" has no input here: the runtime key
policy is owned and tested by bootstrap-infrastructure S5.4 (AD-15a), and S4.6
step 12 is the live proof (V-16). This module only pins that record in the ops
guide. The write statement mirrors the AWS-documented flow-log statement,
including ``s3:x-amz-acl`` = ``bucket-owner-full-control`` (V-16). Every
oracle is a literal from the PRD, the AWS documentation and the hardened TEST
fixture (account 891377212104, eu-central-1).
"""

import json
from pathlib import Path

import pytest
from app.flow_logs import (
    flow_log_bucket_policy,
    flow_log_encryption_rule,
    flow_log_retention_days,
    require_retained_bucket,
    require_reviewed_flow_log_policy,
    require_roleless_flow_log,
    require_runtime_cmk_encryption,
)
from app.workload_phase import _reject_secret_material
from test_poc_workload_phase import graph
from test_runtime_secrets import _transform_args

ROOT = Path(__file__).parents[2]
ACCOUNT = "891377212104"
REGION = "eu-central-1"
RUNTIME_CMK = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000010"
)
JWT_CMK = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000011"
)
BUCKET = "user-service-infrastructure-test-891377212104-flow-logs"
BUCKET_ARN = "arn:aws:s3:::user-service-infrastructure-test-891377212104-flow-logs"
FLOW_LOG = "aws:ec2/flowLog:FlowLog"
BUCKET_TYPE = "aws:s3/bucketV2:BucketV2"
DELIVERY_CONDITION = {
    "StringEquals": {"aws:SourceAccount": "891377212104"},
    "ArnLike": {"aws:SourceArn": "arn:aws:logs:eu-central-1:891377212104:*"},
}
WRITE_CONDITION = {
    "StringEquals": {
        "aws:SourceAccount": "891377212104",
        "s3:x-amz-acl": "bucket-owner-full-control",
    },
    "ArnLike": {"aws:SourceArn": "arn:aws:logs:eu-central-1:891377212104:*"},
}
REVIEWED_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [BUCKET_ARN, BUCKET_ARN + "/*"],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        },
        {
            "Sid": "AWSLogDeliveryWrite",
            "Effect": "Allow",
            "Principal": {"Service": "delivery.logs.amazonaws.com"},
            "Action": "s3:PutObject",
            "Resource": BUCKET_ARN + "/AWSLogs/891377212104/*",
            "Condition": WRITE_CONDITION,
        },
        {
            "Sid": "AWSLogDeliveryAclCheck",
            "Effect": "Allow",
            "Principal": {"Service": "delivery.logs.amazonaws.com"},
            "Action": "s3:GetBucketAcl",
            "Resource": BUCKET_ARN,
            "Condition": DELIVERY_CONDITION,
        },
    ],
}


@pytest.fixture(scope="module")
def hardened(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("flow-logs"), "hardened")
    assert receipt["error"] is None
    return receipt


def _only(rows, kind):
    (row,) = [row for row in rows.values() if row["type"] == kind]
    return row


def test_one_roleless_flow_log_sends_all_vpc_traffic_to_the_bucket(hardened):
    rows = hardened["registrations"]
    inputs = _only(rows, FLOW_LOG)["inputs"]
    assert inputs["vpcId"] == rows["user-service-vpc"]["id"]
    assert (inputs["trafficType"], inputs["logDestinationType"]) == ("ALL", "s3")
    assert inputs["logDestination"] == BUCKET_ARN
    assert not {"iamRoleArn", "deliverCrossAccountRole"} & set(inputs)


def test_the_bucket_family_holds_every_fr15_control(hardened):
    rows = hardened["registrations"]
    bucket = rows["user-service-flow-logs"]
    assert bucket["inputs"]["bucket"] == BUCKET
    assert bucket["inputs"]["forceDestroy"] is False
    family = {
        name: row["inputs"]
        for name, row in rows.items()
        if name.startswith("user-service-flow-logs-")
    }
    assert {inputs["bucket"] for inputs in family.values()} == {bucket["id"]}
    assert family["user-service-flow-logs-encryption"]["rules"] == [
        {
            "applyServerSideEncryptionByDefault": {
                "sseAlgorithm": "aws:kms",
                "kmsMasterKeyId": RUNTIME_CMK,
            },
            "bucketKeyEnabled": True,
        }
    ]
    public_access = family["user-service-flow-logs-public-access"]
    assert all(
        public_access[key] is True
        for key in (
            "blockPublicAcls",
            "blockPublicPolicy",
            "ignorePublicAcls",
            "restrictPublicBuckets",
        )
    )
    assert family["user-service-flow-logs-ownership"]["rule"] == {
        "objectOwnership": "BucketOwnerEnforced"
    }
    (rule,) = family["user-service-flow-logs-retention"]["rules"]
    assert (rule["status"], rule["expiration"]) == ("Enabled", {"days": 30})
    policy = json.loads(family["user-service-flow-logs-policy"]["policy"])
    assert policy == REVIEWED_POLICY


def test_the_flow_log_waits_for_the_reviewed_bucket_policy(hardened):
    """V-16 (c): AWS must find the reviewed policy before the flow log exists."""
    rows = hardened["registrations"]
    flow_log = _only(rows, FLOW_LOG)
    assert rows["user-service-flow-logs-policy"]["urn"] in flow_log["dependencies"]


def test_prod_records_expire_after_90_days_and_other_environments_fail():
    assert (flow_log_retention_days("test"), flow_log_retention_days("prod")) == (
        30,
        90,
    )
    with pytest.raises(ValueError, match="test or prod"):
        flow_log_retention_days("smoke")


def _without_condition(index, key):
    policy = json.loads(json.dumps(REVIEWED_POLICY))
    condition = policy["Statement"][index]["Condition"]
    for operator in condition.values():
        operator.pop(key, None)
    policy["Statement"][index]["Condition"] = {
        operator: values for operator, values in condition.items() if values
    }
    return policy


@pytest.mark.parametrize(
    "policy",
    [
        # Not TLS-only: the deny statement is gone.
        {**REVIEWED_POLICY, "Statement": REVIEWED_POLICY["Statement"][1:]},
        _without_condition(1, "aws:SourceArn"),
        _without_condition(2, "aws:SourceArn"),
        _without_condition(1, "aws:SourceAccount"),
        # The AWS-documented write statement requires bucket-owner-full-control.
        _without_condition(1, "s3:x-amz-acl"),
        {
            **REVIEWED_POLICY,
            "Statement": [
                *REVIEWED_POLICY["Statement"],
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": BUCKET_ARN + "/*",
                },
            ],
        },
        {"Statement": "not-a-list"},
    ],
)
def test_an_unreviewed_bucket_policy_fails(policy):
    with pytest.raises(ValueError, match="Flow-log bucket policy"):
        require_reviewed_flow_log_policy(policy, BUCKET_ARN, REGION, ACCOUNT)


def test_the_rendered_policy_is_the_reviewed_document():
    policy = flow_log_bucket_policy(BUCKET_ARN, REGION, ACCOUNT)
    assert policy == REVIEWED_POLICY
    assert require_reviewed_flow_log_policy(policy, BUCKET_ARN, REGION, ACCOUNT)


@pytest.mark.parametrize(
    "rule",
    [
        {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}},
        {
            "apply_server_side_encryption_by_default": {
                "sse_algorithm": "aws:kms",
                "kms_master_key_id": JWT_CMK,
            },
            "bucket_key_enabled": True,
        },
        {
            "apply_server_side_encryption_by_default": {"sse_algorithm": "aws:kms"},
            "bucket_key_enabled": True,
        },
        {
            "apply_server_side_encryption_by_default": {
                "sse_algorithm": "aws:kms",
                "kms_master_key_id": RUNTIME_CMK,
            },
            "bucket_key_enabled": False,
        },
    ],
)
def test_sse_s3_or_any_other_key_fails(rule):
    with pytest.raises(ValueError, match="SSE-KMS with the runtime CMK"):
        require_runtime_cmk_encryption(rule, RUNTIME_CMK)


@pytest.mark.parametrize(
    "key",
    [
        # A key ID can make the destination undeliverable (V-16).
        "00000000-0000-4000-8000-000000000010",
        "alias/pulumi-user-service-infrastructure-test-runtime",
        "arn:aws:kms:eu-central-1:891377212104:alias/user-service-runtime",
    ],
)
def test_the_encryption_rule_must_name_the_runtime_cmk_key_arn(key):
    """V-16 (b): the bucket encryption names the key ARN, never an ID or alias."""
    with pytest.raises(ValueError, match="runtime CMK key ARN"):
        require_runtime_cmk_encryption(flow_log_encryption_rule(key), key)


def test_the_runtime_cmk_rule_passes_and_an_aws_managed_key_fails():
    rule = flow_log_encryption_rule(RUNTIME_CMK)
    assert require_runtime_cmk_encryption(rule, RUNTIME_CMK) is rule
    with pytest.raises(ValueError, match="AWS-managed key"):
        require_runtime_cmk_encryption(
            flow_log_encryption_rule("alias/aws/s3"), "alias/aws/s3"
        )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {
                "traffic_type": "ALL",
                "log_destination_type": "s3",
                "iam_role_arn": "arn:aws:iam::891377212104:role/fixture",
            },
            "IAM role",
        ),
        (
            {
                "traffic_type": "ALL",
                "log_destination_type": "s3",
                "deliver_cross_account_role": "arn:aws:iam::891377212104:role/x",
            },
            "IAM role",
        ),
        ({"traffic_type": "ACCEPT", "log_destination_type": "s3"}, "ALL traffic"),
        (
            {"traffic_type": "ALL", "log_destination_type": "cloud-watch-logs"},
            "ALL traffic",
        ),
    ],
)
def test_a_flow_log_with_a_role_or_partial_traffic_fails(arguments, message):
    with pytest.raises(ValueError, match=message):
        require_roleless_flow_log(arguments)


@pytest.mark.parametrize("force_destroy", [True, None, "false"])
def test_force_destroy_fails(force_destroy):
    with pytest.raises(ValueError, match="force_destroy=false"):
        require_retained_bucket(force_destroy)


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize(
    "props",
    [
        {"iam_role_arn": "arn:aws:iam::891377212104:role/fixture"},
        {"deliver_cross_account_role": "arn:aws:iam::891377212104:role/x"},
        {"traffic_type": "REJECT"},
        {"log_destination_type": "cloud-watch-logs"},
    ],
)
def test_the_guard_refuses_a_role_or_partial_flow_log(engine, props):
    reviewed = {"traffic_type": "ALL", "log_destination_type": "s3"}
    changed = {**reviewed, **props}
    if engine:
        changed = {
            "".join(
                part.title() if index else part
                for index, part in enumerate(key.split("_"))
            ): value
            for key, value in changed.items()
        }
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_transform_args(engine, FLOW_LOG, changed))


@pytest.mark.parametrize("engine", [False, True])
def test_the_guard_refuses_a_force_destroy_bucket(engine):
    key = "forceDestroy" if engine else "force_destroy"
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_transform_args(engine, BUCKET_TYPE, {key: True}))


@pytest.mark.parametrize("owner", ["root", "stack"])
@pytest.mark.parametrize("kind", ["flow-log-role", "bucket-force-destroy"])
def test_a_rendered_role_or_force_destroy_fails_the_composition(tmp_path, owner, kind):
    receipt = graph(tmp_path, "hardened", f"{owner}:{kind}")
    assert "unreviewed property" in receipt["error"]
    assert not [
        name for name in receipt["registrations"] if name.startswith("fixture-")
    ]


def test_the_ops_guide_documents_flow_logs_and_v16():
    section = _flow_log_section()
    for marker in (
        "`traffic_type` `ALL`",
        "no IAM role argument",
        "SSE-KMS with the runtime CMK",
        "`BucketOwnerEnforced`",
        "`force_destroy=false`",
        "30 days in TEST and 90 days in PROD",
        "`delivery.logs.amazonaws.com` `s3:PutObject` on `AWSLogs/<acct>/*`",
        "Sid `AWSLogDeliveryWrite`",
        "`s3:x-amz-acl` = `bucket-owner-full-control`",
        "Sid `AWSLogDeliveryAclCheck`",
        "the flow log depends on the bucket policy",
        "by key ARN, never by key ID or alias",
        "`kms:GenerateDataKey*` and `kms:Decrypt`",
        "SSE-S3 is not a fallback",
    ):
        assert marker in section, marker


def test_the_key_policy_n_row_is_recorded_as_enforced_in_bootstrap_s54():
    """S31-F1: FR-15's key-policy N row is owned by BI S5.4, proven by S4.6."""
    section = _flow_log_section()
    for marker in (
        "**Runtime key policy (enforced elsewhere):**",
        "SSE-KMS without the delivery principal in the runtime key policy fails",
        "has no input in this repository",
        "`central.cmk.runtime` holds only `arn` and `alias`",
        "`kms:GenerateDataKey*` and `kms:Decrypt`, with `aws:SourceAccount` and "
        "`aws:SourceArn` like `arn:aws:logs:<region>:<acct>:*`",
        "owned and tested by bootstrap-infrastructure S5.4",
        "S4.6 step 12 (a TEST object delivered with the runtime CMK)",
        "under the V-16 STOP rule",
    ):
        assert marker in section, marker


def test_the_import_and_abandon_owners_are_recorded():
    """S31-F2: S4.2, S4.3 and S4.10 own the N-06 artefacts (AD-16, D-11)."""
    section = _flow_log_section()
    for marker in (
        'S4.2 owns the abandon-manifest schema, including "log-bucket families '
        'always retain" and the N5 refusal of delete on the flow-log bucket',
        "S4.3 owns `import-list.json`",
        "S4.10 owns `delete-actions.json` and the `retainOnDelete` allowance",
    ):
        assert marker in section, marker


def test_v16_is_closed_from_dated_aws_sources():
    """S31-F3: V-16 cites the AWS pages, the date and the STOP rule."""
    section = _flow_log_section()
    for marker in (
        "**V-16 (closed offline from AWS docs, verified 2026-10-02):**",
        "<https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-permissions.html>",
        "<https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3-cmk-policy.html>",
        "<https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/"
        "AWS-logs-infrastructure-V2-S3.html>",
        "<https://docs.aws.amazon.com/vpc/latest/tgw/flow-logs-s3.html>",
        '"overwrites any existing policy"',
        '"LogDestination undeliverable"',
        "`kms:Encrypt`, `kms:Decrypt`, `kms:ReEncrypt*`, `kms:GenerateDataKey*` and "
        "`kms:DescribeKey`",
        "AD-15a stands",
        "`logs:CreateLogDelivery` and `logs:DeleteLogDelivery`",
        "**STOP rule:** if live delivery in S4.6 step 12 fails, STOP and widen the "
        "runtime key policy by a reviewed bootstrap-infrastructure PR",
        "**Auto-attach and drift check:**",
        "compare it with the reviewed document",
        "If the live policy differs from the reviewed document, STOP",
    ):
        assert marker in section, marker


def _flow_log_section():
    text = " ".join((ROOT / "docs/sre-operations.md").read_text().split())
    section = text[text.index("### VPC flow logs (S3.1, FR-15)") :]
    return section[: section.index("## CI Troubleshooting")]
