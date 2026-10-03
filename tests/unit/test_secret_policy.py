"""S1.5: secret resource policies (FR-07, AD-08).

Every USI-declared secret gets a ``SecretPolicy(block_public_policy=True)``
with two deny statements for ``Principal "*"``: ``GetSecretValue`` unless the
execution or app-rotation role, and ``PutSecretValue`` and
``UpdateSecretVersionStage`` unless the app-rotation role. The
DocumentDB-managed secret gets a step-2 ``SecretPolicy`` rendering the
document of its contract state ``documentdb_secret_policy``. Every oracle
below is a literal from the PRD, architecture or the synthetic fixture.

V-3 docs record (first case of S1.5): the managed rotation of an
RDS-managed master secret is performed by the managing service, not by a
customer role, so ``allow-rotation`` keeps the bootstrap-job read deny and
exempts AWS service principals (``aws:PrincipalIsAWSService``), the
architecture's example condition. The live half of V-3 is S4.6 step 8.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from app import runtime_secrets as module
from app import workload_phase
from poc_contract import _validate_document
from test_poc_contract import change
from test_poc_contract_hardened import step_two
from test_poc_workload_phase import graph

POLICY = "aws:secretsmanager/secretPolicy:SecretPolicy"
TARGET = "aws:appautoscaling/target:Target"
SCALING_POLICY = "aws:appautoscaling/policy:Policy"
EXECUTION = "arn:aws:iam::891377212104:role/SyntheticPocExecution"
ROTATION = "arn:aws:iam::891377212104:role/SyntheticPocAppRotation"
BOOTSTRAP = "arn:aws:iam::891377212104:role/SyntheticPocBootstrapJob"
# The workload probe binds ``central.execution_role_arn`` to the stack's role.
PROBE_EXECUTION = (
    "arn:aws:iam::891377212104:role/user-service-infrastructure-test-EcsExecution"
)
MANAGED_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "rds!cluster-00000000-0000-4000-8000-000000000003-AbCdEf"
)
# S1.8 (AD-03) leaves exactly these two declared purposes.
DECLARED = ("app_secret", "oauth_encryption_key")
ARN_PREFIX = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "/user-service-infrastructure/runtime/test/synthetic-"
)

DECLARED_DOCUMENT = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyReadUnlessReviewedReader",
            "Effect": "Deny",
            "Principal": "*",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": "*",
            "Condition": {
                "StringNotEquals": {"aws:PrincipalArn": [EXECUTION, ROTATION]}
            },
        },
        {
            "Sid": "DenyWriteUnlessAppRotation",
            "Effect": "Deny",
            "Principal": "*",
            "Action": [
                "secretsmanager:PutSecretValue",
                "secretsmanager:UpdateSecretVersionStage",
            ],
            "Resource": "*",
            "Condition": {"StringNotEquals": {"aws:PrincipalArn": [ROTATION]}},
        },
    ],
}
BOOTSTRAP_DENY = {
    "Sid": "DenyReadUnlessBootstrapJob",
    "Effect": "Deny",
    "Principal": "*",
    "Action": ["secretsmanager:GetSecretValue"],
    "Resource": "*",
    "Condition": {"StringNotEquals": {"aws:PrincipalArn": [BOOTSTRAP]}},
}
STATE_DOCUMENTS = {
    "deny-other-readers": {"Version": "2012-10-17", "Statement": [BOOTSTRAP_DENY]},
    "allow-rotation": {
        "Version": "2012-10-17",
        "Statement": [
            {
                **BOOTSTRAP_DENY,
                "Condition": {
                    "StringNotEquals": {"aws:PrincipalArn": [BOOTSTRAP]},
                    "Bool": {"aws:PrincipalIsAWSService": "false"},
                },
            }
        ],
    },
    "tls-only": {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyReadWithoutTls",
                "Effect": "Deny",
                "Principal": "*",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": "*",
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }
        ],
    },
}


@pytest.fixture(scope="module")
def render(tmp_path_factory):
    cache = {}

    def get(mutation):
        if mutation not in cache:
            receipt = graph(tmp_path_factory.mktemp("policy"), "hardened", mutation)
            assert receipt["error"] is None
            cache[mutation] = receipt
        return cache[mutation]

    return get


def _policies(rows):
    return {name: row for name, row in rows.items() if row["type"] == POLICY}


# The declared-secret document (FR-07 P, N1, N2).


def test_the_declared_policy_denies_reads_and_writes_outside_the_allow_lists():
    document = module.declared_secret_policy(
        [EXECUTION, ROTATION], [ROTATION], execution_role_arn=EXECUTION
    )
    assert json.loads(document) == DECLARED_DOCUMENT


@pytest.mark.parametrize(
    "allow_list",
    [
        "*",
        ["*"],
        [],
        None,
        "arn:aws:iam::891377212104:role/SyntheticPocAppRotation",
        ["arn:aws:iam::891377212104:role/*"],
        ["arn:aws:iam::*:role/SyntheticPocAppRotation"],
        [ROTATION, "*"],
        [""],
    ],
)
def test_n1_a_wildcard_empty_or_missing_allow_list_fails(allow_list):
    with pytest.raises(ValueError, match="exact role ARNs"):
        module.declared_secret_policy(
            allow_list, [ROTATION], execution_role_arn=EXECUTION
        )
    with pytest.raises(ValueError, match="exact role ARNs"):
        module.declared_secret_policy(
            [EXECUTION, ROTATION], allow_list, execution_role_arn=EXECUTION
        )


def test_n2_a_write_deny_allow_list_with_the_execution_role_fails():
    for writers in ([EXECUTION], [ROTATION, EXECUTION]):
        with pytest.raises(ValueError, match="execution role"):
            module.declared_secret_policy(
                [EXECUTION, ROTATION], writers, execution_role_arn=EXECUTION
            )


# The managed-secret states (B, N3).


@pytest.mark.parametrize("state", sorted(STATE_DOCUMENTS))
def test_b_each_state_renders_exactly_its_fixture_document(state):
    document = module.managed_secret_policy(state, bootstrap_job_role_arn=BOOTSTRAP)
    assert json.loads(document) == STATE_DOCUMENTS[state]


@pytest.mark.parametrize("state", ["allow-all", "", None, "DENY-OTHER-READERS"])
def test_n3_an_unknown_policy_state_fails(state):
    contract = step_two()
    change(contract, "documentdb_secret_policy", state)
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)
    with pytest.raises(ValueError, match="documentdb_secret_policy"):
        module.managed_secret_policy(state, bootstrap_job_role_arn=BOOTSTRAP)


# The step-2 graph (FR-07 P, B, edge).


def test_step_one_renders_no_secret_policy(render):
    assert not _policies(render("none")["registrations"])


def test_every_declared_secret_gets_the_fr07_policy(render):
    rows = render("step2")["registrations"]
    policies = _policies(rows)
    assert set(policies) == {f"runtime-{purpose}-policy" for purpose in DECLARED} | {
        "documentdb-managed-secret-policy"
    }
    for purpose in DECLARED:
        row = policies[f"runtime-{purpose}-policy"]
        assert row["parent"] == rows["runtime-secrets"]["urn"]
        assert set(row["inputs"]) == {"secretArn", "blockPublicPolicy", "policy"}
        assert row["inputs"]["secretArn"] == f"{ARN_PREFIX}{purpose}-abcdef"
        assert row["inputs"]["blockPublicPolicy"] is True
        document = json.loads(row["inputs"]["policy"])
        assert document["Statement"][0]["Condition"] == {
            "StringNotEquals": {"aws:PrincipalArn": [PROBE_EXECUTION, ROTATION]}
        }
        document["Statement"][0]["Condition"] = DECLARED_DOCUMENT["Statement"][0][
            "Condition"
        ]
        assert document == DECLARED_DOCUMENT
        assert rows[f"runtime-{purpose}"]["urn"] in row["dependencies"]


def test_the_managed_secret_policy_starts_in_deny_other_readers(render):
    row = _policies(render("step2")["registrations"])[
        "documentdb-managed-secret-policy"
    ]
    assert row["inputs"]["secretArn"] == MANAGED_ARN
    assert row["inputs"]["blockPublicPolicy"] is True
    assert json.loads(row["inputs"]["policy"]) == STATE_DOCUMENTS["deny-other-readers"]


@pytest.mark.parametrize(
    ("mutation", "state"),
    [("step2-allow-rotation", "allow-rotation"), ("step2-tls-only", "tls-only")],
)
def test_b_switching_state_changes_only_the_policy_input_of_the_same_urn(
    render, mutation, state
):
    name = "documentdb-managed-secret-policy"
    before = render("step2")["registrations"][name]
    after = render(mutation)["registrations"][name]
    assert after["urn"] == before["urn"]
    assert json.loads(after["inputs"]["policy"]) == STATE_DOCUMENTS[state]
    changed = {
        key
        for key in before["inputs"].keys() | after["inputs"].keys()
        if before["inputs"].get(key) != after["inputs"].get(key)
    }
    assert changed == {"policy"}


def test_edge_every_autoscaling_target_and_policy_waits_for_the_secret_policies(
    render,
):
    """AD-06 (gate S21 nit): the S2.1/S2.2 targets and policies depend on them."""
    rows = render("step2")["registrations"]
    urns = {row["urn"] for row in _policies(rows).values()}
    assert len(urns) == 3
    scaled = {
        name: row
        for name, row in rows.items()
        if row["type"] in (TARGET, SCALING_POLICY)
    }
    assert set(scaled) == {
        "web-scaling-target",
        "worker-scaling-target",
        "web-cpu-tracking",
        "web-request-tracking",
        "worker-backlog-tracking",
    }
    for row in scaled.values():
        assert urns <= set(row["dependencies"])


# The guard's property check on both transform paths.


def _check(props, sdk_path=False):
    return workload_phase.HARDENED_PROPERTY_CHECKS[POLICY](props, sdk_path)


def test_the_reviewed_deny_only_policies_pass_the_guard():
    for document in (DECLARED_DOCUMENT, *STATE_DOCUMENTS.values()):
        policy = json.dumps(document)
        assert _check({"secretArn": "a", "blockPublicPolicy": True, "policy": policy})
        assert _check(
            {"secret_arn": "a", "block_public_policy": True, "policy": policy},
            sdk_path=True,
        )


ALLOW = {
    "Effect": "Allow",
    "Principal": {"AWS": EXECUTION},
    "Action": "secretsmanager:GetSecretValue",
    "Resource": "*",
}


@pytest.mark.parametrize(
    "changes",
    [
        {"blockPublicPolicy": False},
        {"blockPublicPolicy": None},
        {"policy": json.dumps({"Version": "2012-10-17", "Statement": [ALLOW]})},
        {
            "policy": json.dumps(
                {"Statement": [DECLARED_DOCUMENT["Statement"][0], ALLOW]}
            )
        },
        {
            "policy": json.dumps(
                {"Statement": [{**BOOTSTRAP_DENY, "Principal": {"AWS": EXECUTION}}]}
            )
        },
        {"policy": json.dumps({"Statement": []})},
        {"policy": json.dumps({"Statement": BOOTSTRAP_DENY})},
        {"policy": json.dumps([BOOTSTRAP_DENY])},
        {"policy": "not json"},
        {"policy": None},
        {"policy": DECLARED_DOCUMENT},
    ],
)
def test_an_unreviewed_secret_policy_fails_the_guard(changes):
    props = {
        "secretArn": "a",
        "blockPublicPolicy": True,
        "policy": json.dumps(DECLARED_DOCUMENT),
        **changes,
    }
    assert not _check(props)
