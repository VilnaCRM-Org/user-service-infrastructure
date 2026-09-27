"""Generated workload log/health registration checks; no native AWS evidence."""

import json
from fnmatch import fnmatchcase
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_poc_workload_phase import TAGS, graph


def test_generated_workload_owns_protected_log_delivery_before_alb(tmp_path):
    result = graph(tmp_path, "bridge")
    assert result["error"] is None
    rows = result["registrations"]
    bucket = rows["user-service-alb-logs"]
    expected_name = "user-service-infrastructure-test-891377212104-alb-logs"
    prefix = "user-service-infrastructure-test/alb"
    assert bucket["inputs"]["bucket"] == expected_name
    assert bucket["inputs"]["forceDestroy"] is False
    assert bucket["protect"] is True
    assert bucket["inputs"]["tags"] == TAGS
    assert bucket["parent"] == rows["access-logs"]["urn"]
    assert rows["access-logs"]["parent"] == rows["compute"]["urn"]
    assert rows["user-service-alb-logs-ownership"]["inputs"]["rule"] == {
        "objectOwnership": "BucketOwnerEnforced"
    }
    public = rows["user-service-alb-logs-public-access"]["inputs"]
    assert all(
        public[key] is True
        for key in (
            "blockPublicAcls",
            "blockPublicPolicy",
            "ignorePublicAcls",
            "restrictPublicBuckets",
        )
    )
    assert rows["user-service-alb-logs-encryption"]["inputs"]["rules"] == [
        {"applyServerSideEncryptionByDefault": {"sseAlgorithm": "AES256"}}
    ]
    assert rows["user-service-alb-logs-versioning"]["inputs"][
        "versioningConfiguration"
    ] == {"status": "Enabled"}
    rule = rows["user-service-alb-logs-retention"]["inputs"]["rules"][0]
    assert rule["filter"] == {"prefix": prefix + "/"}
    assert rule["expiration"] == {"days": 90}
    assert rule["noncurrentVersionExpiration"] == {"noncurrentDays": 30}
    assert rule["abortIncompleteMultipartUpload"] == {"daysAfterInitiation": 7}
    policy = rows["user-service-alb-logs-policy"]
    assert {
        rows[f"user-service-alb-logs-{suffix}"]["urn"]
        for suffix in (
            "ownership",
            "public-access",
            "encryption",
            "versioning",
            "retention",
        )
    } <= set(policy["dependencies"])
    alb = rows["user-service-alb"]
    assert policy["urn"] in alb["dependencies"]
    assert alb["inputs"]["accessLogs"] == {
        "bucket": expected_name,
        "enabled": True,
        "prefix": prefix,
    }
    assert all(not row["provider"] for row in rows.values())
    assert not any(row["type"].startswith("aws:iam/") for row in rows.values())
    assert json.loads(policy["inputs"]["policy"])["Statement"][0]["Resource"] == (
        f"arn:aws:s3:::{expected_name}/{prefix}/AWSLogs/891377212104/*"
    )


def test_worker_uses_declared_exec_health_command_and_web_has_no_override(tmp_path):
    result = graph(tmp_path, "bridge")
    assert result["error"] is None
    rows = result["registrations"]
    contract = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/poc-contract/workload.synthetic.json"
        ).read_text()
    )
    worker = json.loads(
        rows["user-service-worker-task"]["inputs"]["containerDefinitions"]
    )[0]
    assert worker["healthCheck"] == {
        "command": ["CMD", *contract["workload"]["runtime"]["worker_health_command"]],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60,
    }
    web = json.loads(rows["user-service-web-task"]["inputs"]["containerDefinitions"])[0]
    assert "healthCheck" not in web


def _policy():
    from app.access_logs import delivery_policy

    return json.loads(
        delivery_policy(
            "arn:aws:s3:::owned-logs",
            "user-service-infrastructure-test/alb",
            "891377212104",
            SimpleNamespace(
                stack_tag="user-service-infrastructure-test", region="eu-central-1"
            ),
        )
    )["Statement"]


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "account",
        "region",
        "alb",
        "prefix",
        "resource-account",
        "principal",
        "action",
    ],
)
def test_delivery_allow_is_exact_service_named_alb_and_log_path(fault):
    from app.environment import build_resource_name

    row = _policy()[0]
    name = build_resource_name("user-service-infrastructure-test", "alb", max_length=32)
    source = (
        "arn:aws:elasticloadbalancing:eu-central-1:891377212104:"
        f"loadbalancer/app/{name}/0123456789"
    )
    resource = (
        "arn:aws:s3:::owned-logs/user-service-infrastructure-test/alb/"
        "AWSLogs/891377212104/log.gz"
    )
    principal, action = "logdelivery.elasticloadbalancing.amazonaws.com", "s3:PutObject"
    if fault == "account":
        source = source.replace("891377212104", "933245420672")
    if fault == "region":
        source = source.replace("eu-central-1", "eu-west-1")
    if fault == "alb":
        source = source.replace(name, name + "-foreign")
    if fault == "prefix":
        resource = resource.replace("/alb/", "/foreign/")
    if fault == "resource-account":
        resource = resource.replace("891377212104", "933245420672")
    if fault == "principal":
        principal = "delivery.logs.amazonaws.com"
    if fault == "action":
        action = "s3:GetObject"
    allowed = (
        principal == row["Principal"]["Service"]
        and action == row["Action"]
        and fnmatchcase(source, row["Condition"]["ArnLike"]["aws:SourceArn"])
        and fnmatchcase(resource, row["Resource"])
    )
    assert allowed is (fault is None)


def test_tls_denial_does_not_break_redacted_service_delivery_context():
    row = _policy()[1]
    assert (
        row["Effect"] == "Deny" and row["Principal"] == "*" and row["Action"] == "s3:*"
    )
    assert row["Resource"] == ["arn:aws:s3:::owned-logs", "arn:aws:s3:::owned-logs/*"]
    assert row["Condition"] == {
        "Bool": {"aws:SecureTransport": "false", "aws:PrincipalIsAWSService": "false"}
    }


def test_legacy_compute_retains_external_log_destination():
    from app.compute import ComputePlane

    compute = object.__new__(ComputePlane)
    settings = SimpleNamespace(
        runtime=SimpleNamespace(access_logs_bucket_name="legacy-logs")
    )
    assert compute._access_logs(settings) == ("legacy-logs", [])
