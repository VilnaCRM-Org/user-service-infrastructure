"""Fail-closed guards of the S1.5 secret policies in the integration suite.

The integration coverage gate includes ``pulumi/app``. The generated graphs
here render step 1 only, so these cases drive the S1.5 helpers directly: the
FR-07 declared-secret document and its allow-list refusals (wildcard, empty,
execution role on the write deny), the three ``documentdb_secret_policy``
documents and an unknown state (AD-08), and the guard's deny-only check.
"""

import json

import pytest
from app.runtime_secrets import declared_secret_policy, managed_secret_policy
from app.workload_phase import _reject_secret_material

import pulumi

EXECUTION = "arn:aws:iam::891377212104:role/SyntheticPocExecution"
ROTATION = "arn:aws:iam::891377212104:role/SyntheticPocAppRotation"
BOOTSTRAP = "arn:aws:iam::891377212104:role/SyntheticPocBootstrapJob"
READ = "secretsmanager:GetSecretValue"


def _policy(policy, block=True):
    return pulumi.ResourceTransformationArgs(
        resource=None,
        type_="aws:secretsmanager/secretPolicy:SecretPolicy",
        name="probe",
        props={"secretArn": "a", "blockPublicPolicy": block, "policy": policy},
        opts=None,
    )


def test_the_declared_policy_refuses_unreviewed_allow_lists():
    document = json.loads(
        declared_secret_policy(
            [EXECUTION, ROTATION], [ROTATION], execution_role_arn=EXECUTION
        )
    )
    assert [statement["Effect"] for statement in document["Statement"]] == [
        "Deny",
        "Deny",
    ]
    assert document["Statement"][1]["Condition"] == {
        "StringNotEquals": {"aws:PrincipalArn": [ROTATION]}
    }
    for allow_list in ("*", ["*"], [], None):
        with pytest.raises(ValueError, match="exact role ARNs"):
            declared_secret_policy(allow_list, [ROTATION], execution_role_arn=EXECUTION)
    with pytest.raises(ValueError, match="execution role"):
        declared_secret_policy(
            [EXECUTION, ROTATION], [EXECUTION], execution_role_arn=EXECUTION
        )


def test_each_managed_state_renders_its_document():
    conditions = {
        "deny-other-readers": {
            "StringNotEquals": {"aws:PrincipalArn": [BOOTSTRAP]},
        },
        "allow-rotation": {
            "StringNotEquals": {"aws:PrincipalArn": [BOOTSTRAP]},
            "Bool": {"aws:PrincipalIsAWSService": "false"},
        },
        "tls-only": {"Bool": {"aws:SecureTransport": "false"}},
    }
    for state, condition in conditions.items():
        document = json.loads(
            managed_secret_policy(state, bootstrap_job_role_arn=BOOTSTRAP)
        )
        (statement,) = document["Statement"]
        assert statement["Action"] == [READ]
        assert statement["Condition"] == condition
    with pytest.raises(ValueError, match="documentdb_secret_policy"):
        managed_secret_policy("allow-all", bootstrap_job_role_arn=BOOTSTRAP)


def test_the_guard_admits_only_a_deny_only_public_blocking_policy():
    reviewed = managed_secret_policy("tls-only", bootstrap_job_role_arn=BOOTSTRAP)
    assert _reject_secret_material(_policy(reviewed), 2) is None
    allow = {"Effect": "Allow", "Principal": {"AWS": EXECUTION}, "Action": READ}
    for policy, block in (
        (reviewed, False),
        (json.dumps({"Statement": [allow]}), True),
        (json.dumps({"Statement": []}), True),
        (json.dumps([allow]), True),
        ("not json", True),
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(_policy(policy, block), 2)
