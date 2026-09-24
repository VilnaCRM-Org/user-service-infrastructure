"""Synthetic native metadata; no AWS requests or workload authorization."""

import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_capabilities as module  # noqa: E402
from test_poc_workload_phase_entrypoint import fixture


@pytest.fixture
def native_evidence():
    contract, _ = fixture()
    central = contract["workload"]["central"]
    roles = {}
    for index, (purpose, name) in enumerate(module.ROLE_NAMES.items()):
        roles[name] = {
            "Arn": central[purpose + "_role_arn"],
            "RoleName": name,
            "Path": "/",
            "RoleId": "AROA" + str(index) * 17,
            "PermissionsBoundary": {
                "PermissionsBoundaryType": "Policy",
                "PermissionsBoundaryArn": (
                    f"arn:aws:iam::891377212104:policy/issue219/test/boundary/{name}-Boundary"
                ),
            },
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                        "Condition": {
                            "StringEquals": {"aws:SourceAccount": "891377212104"},
                            "ArnLike": {
                                "aws:SourceArn": (
                                    "arn:aws:ecs:eu-central-1:891377212104:*"
                                )
                            },
                        },
                    }
                ],
            },
        }
    now = datetime.now(timezone.utc)
    certificate = {
        "CertificateArn": contract["workload"]["external"]["domain"]["certificate_arn"],
        "Status": "ISSUED",
        "SubjectAlternativeNames": ["user.vilnacrmtest.com"],
        "ExtendedKeyUsages": [
            {"Name": "TLS_WEB_SERVER_AUTHENTICATION", "OID": "1.3.6.1.5.5.7.3.1"}
        ],
        "NotBefore": (now - timedelta(days=1)).isoformat(),
        "NotAfter": (now + timedelta(days=30)).isoformat(),
    }
    calls = []

    def native(service, operation, arguments):
        calls.append((service, operation, arguments))
        if operation == "get-role":
            return {"Role": copy.deepcopy(roles[arguments[1]])}
        if operation == "describe-certificate":
            return {"Certificate": copy.deepcopy(certificate)}
        assert (service, operation) == ("iam", "simulate-principal-policy")
        assert arguments[1] == central["execution_role_arn"]
        assert json.loads(arguments[7]) == [
            {
                "ContextKeyName": "aws:RequestedRegion",
                "ContextKeyValues": ["eu-central-1"],
                "ContextKeyType": "string",
            }
        ]
        return {
            "IsTruncated": False,
            "EvaluationResults": [
                {
                    "EvalActionName": arguments[3],
                    "EvalResourceName": arguments[5],
                    "EvalDecision": "allowed",
                    "MissingContextValues": [],
                    "PermissionsBoundaryDecisionDetail": {
                        "AllowedByPermissionsBoundary": True
                    },
                }
            ],
        }

    return contract, roles, certificate, native, calls


def test_exact_roles_boundary_certificate_and_seven_pull_pairs(
    native_evidence, monkeypatch
):
    contract, _, _, native, calls = native_evidence
    monkeypatch.setattr(module, "_native", native)
    assert module.inspect_capabilities(contract) is None
    pulls = [args for _, op, args in calls if op == "simulate-principal-policy"]
    assert len(pulls) == 7
    assert {(args[3], args[5]) for args in pulls} == {
        ("ecr:GetAuthorizationToken", "*"),
        *(
            (action, row["arn"])
            for row in contract["registries"].values()
            for action in module.PULL_ACTIONS
        ),
    }
    assert len([op for _, op, _ in calls if op == "get-role"]) == 4
    assert len([op for _, op, _ in calls if op == "describe-certificate"]) == 2
    assert not any("--policy-input-list" in args for _, _, args in calls)


@pytest.mark.parametrize("purpose", module.ROLE_NAMES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("Arn", "arn:aws:iam::933245420672:role/foreign"),
        ("RoleName", "foreign"),
        ("Path", "/foreign/"),
        ("RoleId", None),
        ("RoleId", "AROAshort"),
        ("PermissionsBoundary", None),
        (
            "PermissionsBoundary",
            {"PermissionsBoundaryType": "Policy", "PermissionsBoundaryArn": "foreign"},
        ),
    ],
)
def test_native_identity_or_boundary_substitution_rejects(
    native_evidence, purpose, field, value
):
    contract, roles, _, native, _ = native_evidence
    roles[module.ROLE_NAMES[purpose]][field] = value
    with pytest.raises(ValueError, match="workload-native-role"):
        module.inspect_capabilities(contract, native=native)


def test_contract_role_and_execution_trust_substitution_reject(native_evidence):
    contract, roles, _, native, _ = native_evidence
    roles[module.ROLE_NAMES["execution"]]["AssumeRolePolicyDocument"]["Statement"][0][
        "Principal"
    ] = {"AWS": "*"}
    with pytest.raises(ValueError, match="execution-trust"):
        module.inspect_capabilities(contract, native=native)
    contract["workload"]["central"]["task_role_arn"] = (
        "arn:aws:iam::891377212104:role/OtherTask"
    )
    with pytest.raises(ValueError, match="role-binding"):
        module.inspect_capabilities(contract, native=native)


@pytest.mark.parametrize(
    "field,value",
    [
        ("CertificateArn", "foreign"),
        ("Status", "PENDING_VALIDATION"),
        ("SubjectAlternativeNames", ["*.vilnacrmtest.com"]),
        ("SubjectAlternativeNames", "prefix-user.vilnacrmtest.com"),
        ("ExtendedKeyUsages", None),
        ("ExtendedKeyUsages", []),
        ("NotBefore", "2100-01-01T00:00:00+00:00"),
        ("NotAfter", "2000-01-01T00:00:00+00:00"),
        ("NotAfter", True),
        ("NotAfter", "2100-01-01T00:00:00"),
    ],
)
def test_certificate_prerequisites_fail_closed(native_evidence, field, value):
    contract, _, certificate, native, _ = native_evidence
    certificate[field] = value
    with pytest.raises(ValueError, match="certificate"):
        module.inspect_capabilities(contract, native=native)


@pytest.mark.parametrize(
    "field,value",
    [
        ("EvalActionName", "ecr:PutImage"),
        ("EvalResourceName", "foreign"),
        ("EvalDecision", "explicitDeny"),
        ("EvalDecision", "implicitDeny"),
        ("MissingContextValues", ["aws:SourceVpc"]),
        ("PermissionsBoundaryDecisionDetail", None),
        ("PermissionsBoundaryDecisionDetail", {"AllowedByPermissionsBoundary": False}),
        ("PermissionsBoundaryDecisionDetail", {"AllowedByPermissionsBoundary": 1}),
        ("OrganizationsDecisionDetail", {"AllowedByOrganizations": False}),
        (
            "ResourceSpecificResults",
            [{"EvalResourceName": "*", "EvalResourceDecision": "explicitDeny"}],
        ),
        ("ResourceSpecificResults", [{}, {}]),
        ("ResourceSpecificResults", None),
    ],
)
def test_pull_denies_and_ambiguous_evaluation_reject(native_evidence, field, value):
    contract, _, _, original, _ = native_evidence

    def native(service, operation, arguments):
        result = original(service, operation, arguments)
        if operation == "simulate-principal-policy":
            result["EvaluationResults"][0][field] = value
        return result

    with pytest.raises(ValueError, match="execution-pull"):
        module.inspect_capabilities(contract, native=native)


@pytest.mark.parametrize(
    "field,value",
    [
        ("IsTruncated", True),
        ("IsTruncated", 0),
        ("Marker", "next"),
        ("EvaluationResults", []),
        ("EvaluationResults", [{}, {}]),
    ],
)
def test_incomplete_simulation_response_rejects(native_evidence, field, value):
    contract, _, _, original, _ = native_evidence

    def native(service, operation, arguments):
        result = original(service, operation, arguments)
        if operation == "simulate-principal-policy":
            result[field] = value
        return result

    with pytest.raises(ValueError, match="pull-response"):
        module.inspect_capabilities(contract, native=native)


def test_explicit_resource_and_organization_allow(native_evidence):
    contract, _, _, original, _ = native_evidence

    def native(service, operation, arguments):
        result = original(service, operation, arguments)
        if operation == "simulate-principal-policy":
            row = result["EvaluationResults"][0]
            row["OrganizationsDecisionDetail"] = {"AllowedByOrganizations": True}
            row["ResourceSpecificResults"] = [
                {
                    "EvalResourceName": row["EvalResourceName"],
                    "EvalResourceDecision": "allowed",
                    "MissingContextValues": [],
                    "PermissionsBoundaryDecisionDetail": {
                        "AllowedByPermissionsBoundary": True
                    },
                }
            ]
        return result

    assert module.inspect_capabilities(contract, native=native) is None


def test_resource_organization_denial_cannot_hide_under_top_level_allow(
    native_evidence,
):
    contract, _, _, original, _ = native_evidence

    def native(service, operation, arguments):
        result = original(service, operation, arguments)
        if operation == "simulate-principal-policy":
            row = result["EvaluationResults"][0]
            row["ResourceSpecificResults"] = [
                {
                    "EvalResourceName": row["EvalResourceName"],
                    "EvalResourceDecision": "allowed",
                    "MissingContextValues": [],
                    "PermissionsBoundaryDecisionDetail": {
                        "AllowedByPermissionsBoundary": True
                    },
                    "OrganizationsDecisionDetail": {"AllowedByOrganizations": False},
                }
            ]
        return result

    with pytest.raises(ValueError, match="organization-deny"):
        module.inspect_capabilities(contract, native=native)


@pytest.mark.parametrize("changed", ["role", "certificate", "denial"])
def test_read_failure_or_native_movement_rejects(native_evidence, changed):
    contract, roles, certificate, original, _ = native_evidence

    def native(service, operation, arguments):
        result = original(service, operation, arguments)
        if operation == "simulate-principal-policy":
            if changed == "denial":
                raise ValueError("private-process-failed")
            if changed == "role":
                roles[module.ROLE_NAMES["task"]]["RoleId"] = "AROA" + "Z" * 17
            else:
                certificate["Serial"] = "changed"
        return result

    with pytest.raises(
        ValueError, match="private-process-failed|native-inputs-changed"
    ):
        module.inspect_capabilities(contract, native=native)


def test_native_adapter_closed_environment_and_operation_allowlist(monkeypatch):
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(key, "synthetic")
    monkeypatch.setenv("HOME", "/private/root")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://foreign.invalid")
    monkeypatch.setenv("AWS_PROFILE", "foreign")
    calls = []
    monkeypatch.setattr(
        module, "run", lambda command, **kw: calls.append((command, kw)) or b"{}"
    )
    for service, op in (("iam", "get-role"), ("acm", "describe-certificate")):
        assert module._native(service, op, []) == {}
    assert (
        calls[0][0][calls[0][0].index("--endpoint-url") + 1]
        == "https://iam.amazonaws.com"
    )
    assert (
        calls[1][0][calls[1][0].index("--endpoint-url") + 1]
        == "https://acm.eu-central-1.amazonaws.com"
    )
    for command, kw in calls:
        assert command[0] == module.AWS and "--no-paginate" in command
        assert set(kw["env"]) == {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "PATH",
            "HOME",
            "AWS_CONFIG_FILE",
            "AWS_SHARED_CREDENTIALS_FILE",
            "AWS_EC2_METADATA_DISABLED",
            "AWS_MAX_ATTEMPTS",
        }
        assert kw["cwd"] == Path("/trusted") and kw["timeout"] == 120
    with pytest.raises(ValueError, match="capability-operation"):
        module._native("iam", "attach-role-policy", [])
    monkeypatch.setattr(
        module, "run", lambda *_a, **_k: b" " * (module.backend.MAX_METADATA + 1)
    )
    with pytest.raises(ValueError, match="response-bound"):
        module._native("iam", "get-role", [])


def test_wrong_phase_or_unsupported_platform_rejects_before_reads(native_evidence):
    from test_poc_contract import fixture as contract_fixture

    contract, _, _, native, calls = native_evidence
    with pytest.raises(ValueError, match="workload-contract-required"):
        module.inspect_capabilities(contract_fixture("registry"), native=native)
    contract["workload"]["release"]["platform"] = "linux/arm64"
    with pytest.raises(ValueError, match="supported-platform"):
        module.inspect_capabilities(contract, native=native)
    assert calls == []
