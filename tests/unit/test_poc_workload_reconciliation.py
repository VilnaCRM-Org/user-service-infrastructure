"""Unchanged native plan shapes cannot conceal mutation or ownership movement."""

import base64
import copy
import importlib

import pytest
from test_poc_registry_plan import case

gate = importlib.import_module("poc_workload_reconciliation")
SECRET_URN = gate.PREFIX + "aws:secretsmanager/secretVersion:SecretVersion::runtime"


@pytest.fixture
def data():
    """Synthetic accepted graph, including an encrypted secret input."""
    value = case("repeat")
    value.pop("projection")
    provider = value["prior_resources"][-1]["provider"]
    secret = {
        "urn": SECRET_URN,
        "type": "aws:secretsmanager/secretVersion:SecretVersion",
        "custom": True,
        "id": "synthetic-secret|synthetic-version",
        "parent": gate.ROOT,
        "provider": provider,
        "protect": True,
        "inputs": {
            "secretString": {
                gate.PULUMI_MARKER_SIGNATURE: gate.PULUMI_MARKER_SENTINEL,
                "ciphertext": "synthetic",
            },
            "nested": [1, {"enabled": True}],
        },
        "outputs": {},
        "dependencies": [gate.ROOT],
        "propertyDependencies": {"secretString": [gate.ROOT]},
    }
    value["prior_resources"].append(secret)
    goal = {
        key: copy.deepcopy(secret[key])
        for key in (
            "type",
            "custom",
            "protect",
            "parent",
            "provider",
            "dependencies",
            "propertyDependencies",
        )
    }
    goal.update(name="runtime", inputDiff={}, outputDiff={})
    value["saved_plan"]["resourcePlans"][SECRET_URN] = {
        "goal": goal,
        "steps": ["same"],
        "state": None,
        "seed": base64.b64encode(bytes(32)).decode(),
    }
    preview = copy.deepcopy(secret)
    preview["inputs"]["secretString"] = "[secret]"
    value["preview"]["steps"].append(
        {
            "urn": SECRET_URN,
            "op": "same",
            "provider": provider,
            "oldState": copy.deepcopy(preview),
            "newState": preview,
        }
    )
    return value


def test_accepts_complete_same_graph_and_redacted_preview_without_mutation(data):
    original = copy.deepcopy(data)
    gate.validate_no_change(**data)
    assert data == original


def test_accepts_hidden_unchanged_preview_and_advisory_plan_state(data):
    data["preview"] = {"steps": [], "changeSummary": {"same": 8}}
    data["saved_plan"]["resourcePlans"][SECRET_URN]["state"] = {"untrusted": "advisory"}
    gate.validate_no_change(**data)


@pytest.mark.parametrize(
    "operation", ["create", "update", "delete", "replace", "read", "refresh", "discard"]
)
def test_rejects_every_non_same_native_plan_operation(data, operation):
    data["saved_plan"]["resourcePlans"][SECRET_URN]["steps"] = [operation]
    with pytest.raises(ValueError):
        gate.validate_no_change(**data)


@pytest.mark.parametrize("field", ["inputDiff", "outputDiff"])
@pytest.mark.parametrize(
    "diff",
    [
        {"adds": {"extra": 1}},
        {"updates": {"secretString": "[secret]"}},
        {"deletes": ["secretString"]},
        {"adds": []},
        {"deletes": {}},
        {"unknown": {}},
    ],
)
def test_rejects_changes_even_when_plan_operation_claims_same(data, field, diff):
    data["saved_plan"]["resourcePlans"][SECRET_URN]["goal"][field] = diff
    with pytest.raises(ValueError):
        gate.validate_no_change(**data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "foreign"),
        ("type", "aws:iam/role:Role"),
        ("custom", 1),
        ("parent", "foreign"),
        ("provider", "foreign"),
        ("protect", False),
        ("id", "import-id"),
        ("structuredAliases", [{}]),
        ("deleteBeforeReplace", True),
        ("dependencies", []),
        ("propertyDependencies", {}),
        ("additionalSecretOutputs", ["secretString"]),
        ("customTimeouts", {"delete": 1}),
        ("ignoreChanges", ["secretString"]),
    ],
)
def test_rejects_goal_ownership_and_lifecycle_changes(data, field, value):
    data["saved_plan"]["resourcePlans"][SECRET_URN]["goal"][field] = value
    with pytest.raises(ValueError):
        gate.validate_no_change(**data)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-goal",
        "extra-goal",
        "duplicate-prior",
        "foreign-prior",
        "empty-prior",
        "missing-root",
        "iam",
        "pending",
        "external",
        "missing-id",
        "parent",
        "dependency",
        "property",
        "provider",
        "provider-id",
        "provider-type",
        "version",
        "magic",
        "seed",
        "state",
        "extra-plan-field",
        "summary",
        "corrupt",
        "preview-update",
        "preview-duplicate",
        "preview-missing-owner",
        "preview-input",
        "preview-output",
        "preview-provider",
        "preview-diff",
        "raw-secret",
        "fake-secret",
        "malformed-secret",
    ],
)
def test_rejects_incomplete_or_changed_native_evidence(data, mutation):
    plans = data["saved_plan"]["resourcePlans"]
    prior = data["prior_resources"]
    secret = prior[-1]
    preview = data["preview"]
    step = preview["steps"][-1]
    changes = {
        "missing-goal": lambda: plans.pop(SECRET_URN),
        "extra-goal": lambda: plans.update(foreign=copy.deepcopy(plans[SECRET_URN])),
        "duplicate-prior": lambda: prior.append(copy.deepcopy(secret)),
        "foreign-prior": lambda: secret.update(urn="urn:pulumi:prod::foreign"),
        "empty-prior": lambda: prior.clear(),
        "missing-root": lambda: prior.pop(0),
        "iam": lambda: secret.update(type="aws:iam/role:Role"),
        "pending": lambda: secret.update(pendingReplacement=True),
        "external": lambda: secret.update(external=True),
        "missing-id": lambda: secret.pop("id"),
        "parent": lambda: secret.update(parent="foreign"),
        "dependency": lambda: secret.update(dependencies=[SECRET_URN]),
        "property": lambda: secret.update(propertyDependencies={"missing": []}),
        "provider": lambda: secret.update(provider="foreign"),
        "provider-id": lambda: secret.update(provider=secret["provider"] + "wrong"),
        "provider-type": lambda: prior[1].update(type="aws:ecs/cluster:Cluster"),
        "version": lambda: data["saved_plan"]["manifest"].update(version="v9"),
        "magic": lambda: data["saved_plan"]["manifest"].update(magic="wrong"),
        "seed": lambda: plans[SECRET_URN].update(seed="YQ=="),
        "state": lambda: plans[SECRET_URN].update(state=[]),
        "extra-plan-field": lambda: plans[SECRET_URN].update(approved=True),
        "summary": lambda: preview.update(changeSummary={"create": 1}),
        "corrupt": lambda: preview.update(maybeCorrupt=True),
        "preview-update": lambda: step.update(op="update"),
        "preview-duplicate": lambda: preview["steps"].append(copy.deepcopy(step)),
        "preview-missing-owner": lambda: step["newState"].pop("parent"),
        "preview-input": lambda: step["newState"]["inputs"].update(
            nested=[1, {"enabled": 1}]
        ),
        "preview-output": lambda: step["newState"].update(outputs={"changed": True}),
        "preview-provider": lambda: step.update(provider="foreign"),
        "preview-diff": lambda: step.update(detailedDiff={"secretString": "update"}),
        "raw-secret": lambda: step["newState"]["inputs"].update(
            secretString="raw-value"
        ),
        "fake-secret": lambda: step["newState"]["inputs"].update(
            secretString="[Secret]"
        ),
        "malformed-secret": lambda: secret["inputs"]["secretString"].update(
            extra="bad"
        ),
    }
    changes[mutation]()
    with pytest.raises(ValueError):
        gate.validate_no_change(**data)


def test_wrapped_plaintext_native_state_is_redacted_only_in_preview(data):
    data["prior_resources"][-1]["inputs"]["secretString"] = {
        gate.PULUMI_MARKER_SIGNATURE: gate.PULUMI_MARKER_SENTINEL,
        "value": "synthetic-test-only",
    }
    gate.validate_no_change(**data)


def test_timestamps_do_not_change_ownership(data):
    data["preview"]["steps"][-1]["newState"]["modified"] = "2026-09-23T00:00:00Z"
    gate.validate_no_change(**data)


@pytest.mark.parametrize(
    "value",
    [
        "raw-value",
        "[secret]",
        {gate.PULUMI_MARKER_SIGNATURE: "wrong"},
        {gate.PULUMI_MARKER_SIGNATURE: gate.PULUMI_MARKER_SENTINEL},
    ],
)
def test_hidden_preview_cannot_hide_invalid_secret_checkpoint(data, value):
    data["preview"]["steps"] = []
    data["prior_resources"][-1]["inputs"]["secretString"] = value
    with pytest.raises(ValueError):
        gate.validate_no_change(**data)
