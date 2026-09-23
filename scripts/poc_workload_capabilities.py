"""Read bounded TEST prerequisites; never grant workload execution authority.

IAM simulation is a necessary check of the named execution role, not proof of an
actual ECS pull or the complete runtime/deployer/organization permission graph.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import poc_backend_observer as backend
import poc_contract as contracts
from poc_registry_phase_entrypoint import _stable_registries
from service_execution_process import require, run
from service_execution_transport import AWS

ROLE_NAMES = {
    "execution": f"{backend.PROJECT}-test-EcsExecution",
    "task": f"{backend.PROJECT}-test-EcsTask",
}
PULL_ACTIONS = (
    "ecr:BatchCheckLayerAvailability",
    "ecr:BatchGetImage",
    "ecr:GetDownloadUrlForLayer",
)


def _native(service, operation, arguments):
    """Use fixed read APIs/endpoints and only the admitted private AWS session."""
    require(
        (service, operation)
        in {
            ("iam", "get-role"),
            ("iam", "simulate-principal-policy"),
            ("acm", "describe-certificate"),
        },
        "workload-capability-operation",
    )
    environment = {
        key: os.environ[key]
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    }
    environment.update(
        PATH="/usr/local/bin:/usr/bin:/bin",
        HOME=os.environ["HOME"],
        AWS_CONFIG_FILE="/dev/null",
        AWS_SHARED_CREDENTIALS_FILE="/dev/null",
        AWS_EC2_METADATA_DISABLED="true",
        AWS_MAX_ATTEMPTS="1",
    )
    endpoint = (
        "https://iam.amazonaws.com"
        if service == "iam"
        else f"https://acm.{backend.REGION}.amazonaws.com"
    )
    raw = run(
        [
            AWS,
            service,
            operation,
            *arguments,
            "--region",
            "us-east-1" if service == "iam" else backend.REGION,
            "--endpoint-url",
            endpoint,
            "--output",
            "json",
            "--no-cli-pager",
            "--no-paginate",
        ],
        env=environment,
        cwd=Path("/trusted"),
        timeout=120,
    )
    require(len(raw) <= backend.MAX_METADATA, "workload-capability-response-bound")
    return backend._json(raw)


def _role(native, purpose, central):
    """Require the fixed central identity and independently enrolled boundary."""
    name = ROLE_NAMES[purpose]
    arn = f"arn:aws:iam::{backend.ACCOUNT}:role/{name}"
    require(central[purpose + "_role_arn"] == arn, "workload-role-binding")
    role = native("iam", "get-role", ["--role-name", name])["Role"]
    require(
        role.get("Arn") == arn
        and role.get("RoleName") == name
        and role.get("Path") == "/",
        "workload-native-role-identity",
    )
    require(
        type(role.get("RoleId")) is str
        and re.fullmatch(r"AROA[A-Z0-9]{17}", role["RoleId"]),
        "workload-native-role-id",
    )
    require(
        role.get("PermissionsBoundary")
        == {
            "PermissionsBoundaryType": "Policy",
            "PermissionsBoundaryArn": (
                f"arn:aws:iam::{backend.ACCOUNT}:policy/issue219/test/boundary/"
                f"{name}-Boundary"
            ),
        },
        "workload-native-role-boundary",
    )
    return role


def _execution_trust(role):
    """Require the existing centrally specified ECS account/region trust."""
    expected = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": backend.ACCOUNT},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:ecs:{backend.REGION}:{backend.ACCOUNT}:*"
                        )
                    },
                },
            }
        ],
    }
    require(
        role.get("AssumeRolePolicyDocument") == expected,
        "workload-execution-trust",
    )


def _allowed(detail, key):
    """Require the exact native boolean decision, never a truthy substitute."""
    return type(detail) is dict and set(detail) == {key} and detail[key] is True


def _organization(row):
    """A missing organization decision is unknown; an explicit denial rejects."""
    detail = row.get("OrganizationsDecisionDetail")
    require(
        detail is None or _allowed(detail, "AllowedByOrganizations"),
        "workload-execution-pull-organization-deny",
    )


def _decision(row, action, resource):
    """Reject denies, unresolved context or incomplete boundary evaluation."""
    require(
        row.get("EvalActionName") == action
        and row.get("EvalResourceName") == resource
        and row.get("EvalDecision") == "allowed"
        and row.get("MissingContextValues") == []
        and _allowed(
            row.get("PermissionsBoundaryDecisionDetail"), "AllowedByPermissionsBoundary"
        ),
        "workload-execution-pull-decision",
    )
    _organization(row)
    # One action/resource per request avoids aggregate decisions masking a deny.
    resources = row.get("ResourceSpecificResults", [])
    require(
        type(resources) is list and len(resources) <= 1,
        "workload-execution-pull-resource-response",
    )
    for result in resources:
        require(
            result.get("EvalResourceName") == resource
            and result.get("EvalResourceDecision") == "allowed"
            and result.get("MissingContextValues") == []
            and _allowed(
                result.get("PermissionsBoundaryDecisionDetail"),
                "AllowedByPermissionsBoundary",
            ),
            "workload-execution-pull-resource-decision",
        )
        _organization(result)


def _pull(native, role, registries):
    """Simulate installed role policies without supplying replacement policies."""
    requests = [("ecr:GetAuthorizationToken", "*")] + [
        (action, registry["arn"])
        for registry in registries.values()
        for action in PULL_ACTIONS
    ]
    context = json.dumps(
        [
            {
                "ContextKeyName": "aws:RequestedRegion",
                "ContextKeyValues": [backend.REGION],
                "ContextKeyType": "string",
            }
        ]
    )
    for action, resource in requests:
        result = native(
            "iam",
            "simulate-principal-policy",
            [
                "--policy-source-arn",
                role["Arn"],
                "--action-names",
                action,
                "--resource-arns",
                resource,
                "--context-entries",
                context,
            ],
        )
        rows = result.get("EvaluationResults")
        require(
            result.get("IsTruncated") is False
            and not result.get("Marker")
            and type(rows) is list
            and len(rows) == 1,
            "workload-execution-pull-response",
        )
        _decision(rows[0], action, resource)


def _timestamp(value):
    """Accept native CLI timestamps without accepting naive dates or booleans."""
    require(type(value) is str, "workload-certificate-time")
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "workload-certificate-time")
    return parsed


def _certificate(native, domain):
    """Read the exact regional certificate without retrieving certificate data."""
    certificate = native(
        "acm", "describe-certificate", ["--certificate-arn", domain["certificate_arn"]]
    )["Certificate"]
    names = certificate.get("SubjectAlternativeNames")
    usages = certificate.get("ExtendedKeyUsages")
    require(
        certificate.get("CertificateArn") == domain["certificate_arn"]
        and certificate.get("Status") == "ISSUED"
        and type(names) is list
        and domain["fqdn"] in names
        and type(usages) is list
        and {"Name": "TLS_WEB_SERVER_AUTHENTICATION", "OID": "1.3.6.1.5.5.7.3.1"}
        in usages,
        "workload-certificate-binding",
    )
    require(
        _timestamp(certificate["NotBefore"])
        <= datetime.now(timezone.utc)
        < _timestamp(certificate["NotAfter"]),
        "workload-certificate-validity",
    )
    return certificate


def inspect_capabilities(contract, *, native=None):
    """Check prerequisites only; no settings, receipt, plan or authority is returned."""
    contracts._validate_document(contract)
    require(contract["phase"] == "workload", "workload-contract-required")
    _stable_registries(contract["registries"])
    require(
        contract["workload"]["release"]["platform"] == "linux/amd64",
        "workload-supported-platform",
    )
    native = native or _native
    central = contract["workload"]["central"]
    roles = {purpose: _role(native, purpose, central) for purpose in ROLE_NAMES}
    _execution_trust(roles["execution"])
    domain = contract["workload"]["external"]["domain"]
    certificate = _certificate(native, domain)
    _pull(native, roles["execution"], contract["registries"])
    require(
        {purpose: _role(native, purpose, central) for purpose in ROLE_NAMES} == roles
        and _certificate(native, domain) == certificate,
        "workload-native-inputs-changed",
    )
