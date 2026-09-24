"""First topology checks retain registry owners and never enable capabilities."""

import base64
import copy
import importlib

import pytest
from test_poc_registry_phase_entrypoint import source
from test_poc_registry_plan import case
from test_poc_workload_phase import graph
from test_poc_workload_phase_entrypoint import fixture

gate = importlib.import_module("poc_workload_topology")
bridge = importlib.import_module("poc_workload_phase_entrypoint")


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    value = graph(tmp_path_factory.mktemp("topology"), "bridge")
    assert value["error"] is None
    return value["registrations"]


@pytest.fixture
def data(captured):
    value = case("repeat")
    contract, images = fixture()
    value["projection"] = bridge.project_workload_phase(
        source(contract), contract, images
    )
    existing = {row["urn"] for row in value["prior_resources"]}
    expected = gate.expected_graph()
    expected_names = {
        urn.rsplit("::", 1)[-1]: urn
        for urn, row in expected.items()
        if not row[0].startswith("pulumi:providers:")
    }
    assert set(captured) == set(expected_names)
    # SDK MockMonitor does not preserve native ancestor URNs. Native CLI tests
    # below independently verify those; unit fixtures compare logical owners.
    rows = {}
    for name, captured_row in captured.items():
        row = copy.deepcopy(captured_row)
        urn = expected_names[name]
        assert row["type"] == expected[urn][0]
        assert row["parent"].rsplit("::", 1)[-1] == expected[urn][1].rsplit("::", 1)[-1]
        row["dependencies"] = [
            expected_names[item.rsplit("::", 1)[-1]] for item in row["dependencies"]
        ]
        rows[urn] = row
    for urn, (kind, parent, custom, protect) in expected.items():
        if urn in existing:
            continue
        row = rows.get(urn, {})
        inputs = copy.deepcopy(row.get("inputs", {}))
        if "secretString" in inputs:
            inputs["secretString"] = {
                gate.unchanged.PULUMI_MARKER_SIGNATURE: (
                    gate.unchanged.PULUMI_MARKER_SENTINEL
                ),
                "value": "synthetic",
            }
        package = kind.split(":", 1)[0]
        provider = ""
        if package in ("aws", "random", "tls"):
            target = next(
                key
                for key, candidate in expected.items()
                if candidate[0] == f"pulumi:providers:{package}"
            )
            provider = (
                target
                + "::"
                + ("provider-id" if package == "aws" else gate.registry.UNKNOWN)
            )
        goal = {
            "type": kind,
            "name": urn.rsplit("::", 1)[-1],
            "custom": custom,
            "parent": parent,
            "protect": protect,
            "provider": provider,
            "inputDiff": {"adds": inputs},
            "outputDiff": {},
            "dependencies": row.get("dependencies", []),
            "additionalSecretOutputs": row.get("additional_secret_outputs", []),
            "structuredAliases": gate._sdk_aliases(kind),
        }
        value["saved_plan"]["resourcePlans"][urn] = {
            "goal": goal,
            "steps": ["create"],
            "state": None,
            "seed": base64.b64encode(bytes(32)).decode(),
        }
        if not kind.startswith("pulumi:providers:"):
            state = {
                key: val
                for key, val in goal.items()
                if key in gate.registry.STATE_FIELDS
            }
            state.update(urn=urn, inputs=gate.unchanged._redacted(inputs))
            value["preview"]["steps"].append(
                {"urn": urn, "op": "create", "newState": state}
            )
    return value


def test_exact_composition_topology_matches_and_cannot_authorize_execution(data):
    before = copy.deepcopy(data)
    gate.validate_first_workload_topology(**data)
    with pytest.raises(
        ValueError, match="native-capability-and-input-admission-required"
    ):
        gate.admit_first_workload_plan(**data)
    assert data == before


def test_native_omitted_component_outputs_require_unchanged_saved_goal(data):
    root = next(
        step for step in data["preview"]["steps"] if step["urn"] == gate.registry.ROOT
    )
    root["newState"].pop("outputs")
    gate.validate_first_workload_topology(**data)
    data["saved_plan"]["resourcePlans"][gate.registry.ROOT]["goal"]["outputDiff"] = {
        "updates": {"repoSlug": "foreign"}
    }
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)


def test_explicitly_changed_component_outputs_still_reject(data):
    root = next(
        step for step in data["preview"]["steps"] if step["urn"] == gate.registry.ROOT
    )
    root["newState"]["outputs"] = {}
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "value,marked,valid",
    [
        ("raw", True, False),
        ("[secret]", True, False),
        (gate.registry.UNKNOWN, False, False),
        (gate.registry.UNKNOWN, True, True),
    ],
)
def test_first_secret_unknown_requires_secret_output_marking(
    data, value, marked, valid
):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::runtime-document_db_url-version")
    )
    goal = data["saved_plan"]["resourcePlans"][urn]["goal"]
    goal["inputDiff"]["adds"]["secretString"] = value
    goal["additionalSecretOutputs"] = gate.SECRET_VERSION_OUTPUTS if marked else []
    state = next(
        step["newState"] for step in data["preview"]["steps"] if step["urn"] == urn
    )
    state["inputs"]["secretString"] = value
    state["additionalSecretOutputs"] = goal["additionalSecretOutputs"]
    if valid:
        gate.validate_first_workload_topology(**data)
    else:
        with pytest.raises(ValueError):
            gate.validate_first_workload_topology(**data)


def test_sdk_alias_cannot_retarget_an_owner(data):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::user-service-alb")
    )
    data["saved_plan"]["resourcePlans"][urn]["goal"]["structuredAliases"][0]["Name"] = (
        "foreign"
    )
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "parent",
        "kind",
        "provider",
        "protect",
        "alias",
        "import",
        "delete",
        "update",
        "dependency",
        "preview-type",
        "preview-input",
        "preview-missing",
        "duplicate",
        "prior-partial",
        "prior-workload",
    ],
)
def test_first_workload_rejects_unreviewed_or_partial_graph(data, mutation):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::user-service-web-task")
    )
    plans = data["saved_plan"]["resourcePlans"]
    step = next(row for row in data["preview"]["steps"] if row["urn"] == urn)
    goal = plans[urn]["goal"]
    mutations = {
        "missing": lambda: plans.pop(urn),
        "extra": lambda: plans.update(foreign=copy.deepcopy(plans[urn])),
        "parent": lambda: goal.update(parent=gate.registry.ROOT),
        "kind": lambda: goal.update(type="aws:iam/role:Role"),
        "provider": lambda: goal.update(provider="foreign"),
        "protect": lambda: goal.update(protect=True),
        "alias": lambda: goal.update(aliases=["foreign"]),
        "import": lambda: goal.update(id="foreign"),
        "delete": lambda: plans[urn].update(steps=["delete"]),
        "update": lambda: plans[urn].update(steps=["update"]),
        "dependency": lambda: goal.update(dependencies=["foreign"]),
        "preview-type": lambda: step["newState"].update(type="aws:iam/role:Role"),
        "preview-input": lambda: step["newState"]["inputs"].update(networkMode="host"),
        "preview-missing": lambda: data["preview"]["steps"].remove(step),
        "duplicate": lambda: data["preview"]["steps"].append(copy.deepcopy(step)),
        "prior-partial": lambda: data["prior_resources"].pop(),
        "prior-workload": lambda: data["prior_resources"].append(
            copy.deepcopy(step["newState"])
        ),
    }
    mutations[mutation]()
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)
