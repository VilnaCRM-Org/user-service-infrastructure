"""Check the exact registry graph in a Pulumi 3.223 saved plan and JSON preview.

This pure validator authenticates nothing. The trusted caller must supply the
complete privately observed prior resource list, authenticated source projection,
and original same-run plan/preview bytes decoded without duplicate JSON keys.
No count, self-declared phase, advisory plan state or preview alone is authority.
Wire shapes follow sdk/go/common/apitype/plan.go and pkg/backend/display/json.go.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from poc_registry_phase_entrypoint import RegistryPhaseProjection
from pulumi_ci_guardrails import preview_steps, step_resource_type

ACCOUNT, REGION, PROJECT = "891377212104", "eu-central-1", "user-service-infrastructure"
STACK, PROVIDER = "pulumi:pulumi:Stack", "pulumi:providers:aws"
SERVICE, REGISTRY = f"{PROJECT}:stack:UserService", f"{PROJECT}:registry:Plane"
ECR = "aws:ecr/repository:Repository"
PREFIX = f"urn:pulumi:test::{PROJECT}::"
ROOT = f"{PREFIX}{STACK}::{PROJECT}-test"
PROVIDER_URN = f"{PREFIX}{PROVIDER}::default_7_23_0"
SERVICE_URN = f"{PREFIX}{SERVICE}::user-service"
REGISTRY_URN = f"{PREFIX}{SERVICE}${REGISTRY}::registries"
UNKNOWN = "04da6b54-80e4-46f7-96ec-b56ff0331ba9"
REGISTRIES = {
    kind: {
        "logical_name": f"user-service-{kind}-repository",
        "name": f"user-service-test-{kind}",
    }
    for kind in ("web", "worker")
}
GOAL_FIELDS = set(
    "type name custom inputDiff outputDiff parent protect dependencies provider "
    "propertyDependencies deleteBeforeReplace ignoreChanges additionalSecretOutputs "
    "aliases structuredAliases id customTimeouts".split()
)
STATE_FIELDS = set(
    "urn type custom id inputs outputs parent protect external provider dependencies "
    "propertyDependencies additionalSecretOutputs aliases customTimeouts importID "
    "created modified sourcePosition stackTrace ignoreChanges hideDiff "
    "replaceOnChanges replacementTrigger refreshBeforeUpdate resourceHooks "
    "delete taint pendingReplacement "
    "initErrors retainOnDelete deletedWith replaceWith viewOf".split()
)


def _require(condition: object) -> None:
    if not condition:
        raise ValueError("Invalid registry-only plan")


def _object(value, required, allowed):
    _require(type(value) is dict and required <= value.keys() <= allowed)
    return value


def _graph(projection):
    _require(
        type(projection) is RegistryPhaseProjection
        and projection.registries == REGISTRIES
    )
    result = {
        ROOT: (STACK, "", False),
        PROVIDER_URN: (PROVIDER, "", True),
        SERVICE_URN: (SERVICE, ROOT, False),
        REGISTRY_URN: (REGISTRY, SERVICE_URN, False),
    }
    for row in REGISTRIES.values():
        result[f"{PREFIX}{SERVICE}${REGISTRY}${ECR}::{row['logical_name']}"] = (
            ECR,
            REGISTRY_URN,
            True,
        )
    return result


def _provider_inputs(inputs):
    _object(
        inputs,
        {
            "region",
            "allowedAccountIds",
            "version",
            "skipCredentialsValidation",
            "skipRegionValidation",
            "skipRequestingAccountId",
        },
        {
            "region",
            "allowedAccountIds",
            "version",
            "__internal",
            "skipCredentialsValidation",
            "skipRegionValidation",
            "skipRequestingAccountId",
        },
    )
    _require(inputs["region"] == REGION and inputs["version"] == "7.23.0")
    accounts = inputs["allowedAccountIds"]
    if type(accounts) is str:
        accounts = json.loads(accounts)
    _require(accounts == [ACCOUNT] and inputs.get("__internal", {}) == {})
    for key in (
        "skipCredentialsValidation",
        "skipRegionValidation",
        "skipRequestingAccountId",
    ):
        _require(inputs[key] is False or inputs[key] == "false")


def _repository(urn):
    logical = urn.rsplit("::", 1)[-1]
    return next(
        row["name"] for row in REGISTRIES.values() if row["logical_name"] == logical
    )


def _computed(outputs, expected, *, new):
    _require(type(outputs) is dict and outputs.keys() <= expected.keys())
    for key, value in outputs.items():
        _require(value == expected[key] or (new and value == UNKNOWN))


def _ecr_values(row, inputs, outputs, *, new):
    name = _repository(row["urn"])
    expected = {
        "name": name,
        "imageTagMutability": "IMMUTABLE",
        "forceDelete": False,
        "imageScanningConfiguration": {"scanOnPush": True},
    }
    _require(inputs == expected)
    _computed(
        outputs,
        {
            **expected,
            "arn": f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{name}",
            "repositoryUrl": f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{name}",
            "registryId": ACCOUNT,
        },
        new=new,
    )
    if not new:
        _require(
            row.get("id") == name
            and outputs.get("arn")
            == f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{name}"
        )
    else:
        _require(row.get("id", "") in ("", UNKNOWN))


def _inputs_outputs(row, *, new):
    inputs, outputs = row.get("inputs", {}), row.get("outputs", {})
    _require(type(inputs) is dict and type(outputs) is dict)
    kind = row["type"]
    if kind == PROVIDER:
        _provider_inputs(inputs)
        _require(outputs == {} or outputs == inputs)
    elif kind == ECR:
        _ecr_values(row, inputs, outputs, new=new)
    else:
        _require(inputs == {})
        expected = {}
        if kind == REGISTRY:
            for purpose, registry in REGISTRIES.items():
                name = registry["name"]
                expected[f"{purpose}RepositoryArn"] = (
                    f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{name}"
                )
                expected[f"{purpose}RepositoryUrl"] = (
                    f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{name}"
                )
        _computed(outputs, expected, new=new)
        _require(not row.get("id"))


def _state(row, graph, *, new):
    _object(row, {"urn", "type", "custom"}, STATE_FIELDS)
    urn = row["urn"]
    _require(urn in graph)
    kind, parent, custom = graph[urn]
    _require(
        row["type"] == kind and type(row["custom"]) is bool and row["custom"] is custom
    )
    _require(row.get("parent", "") == parent)
    for key in (
        "external",
        "delete",
        "pendingReplacement",
        "taint",
        "initErrors",
        "importID",
        "aliases",
        "ignoreChanges",
        "hideDiff",
        "replaceOnChanges",
        "replacementTrigger",
        "refreshBeforeUpdate",
        "resourceHooks",
        "retainOnDelete",
        "deletedWith",
        "replaceWith",
        "viewOf",
    ):
        _require(not row.get(key))
    _require(type(row.get("protect", False)) is bool)
    _inputs_outputs(row, new=new)
    return row


def _references(row, graph, provider_id):
    expected = f"{PROVIDER_URN}::{provider_id}" if row["type"] == ECR else ""
    _require(row.get("provider", "") == expected)
    dependencies = row.get("dependencies", [])
    _require(type(dependencies) is list and len(dependencies) == len(set(dependencies)))
    _require(set(dependencies) <= graph.keys() - {row["urn"]})
    properties = row.get("propertyDependencies", {})
    _require(
        type(properties) is dict and properties.keys() <= row.get("inputs", {}).keys()
    )
    for values in properties.values():
        _require(type(values) is list and set(values) <= graph.keys() - {row["urn"]})


def _prior(resources, graph):
    _require(type(resources) is list and len(resources) <= 6)
    result = {}
    for value in resources:
        row = _state(value, graph, new=False)
        _require(row["urn"] not in result)
        result[row["urn"]] = row
    _require(set(result) <= {ROOT, PROVIDER_URN} or set(result) == set(graph))
    if PROVIDER_URN in result:
        identifier = result[PROVIDER_URN].get("id")
        _require(type(identifier) is str and identifier not in ("", UNKNOWN))
    else:
        identifier = UNKNOWN
    for row in result.values():
        _references(row, result, identifier)
    return result


def _diff_parts(value):
    row = _object(value, set(), {"adds", "updates", "deletes"})
    adds, updates, deletes = (
        row.get("adds", {}),
        row.get("updates", {}),
        row.get("deletes", []),
    )
    _require(type(adds) is dict and type(updates) is dict and type(deletes) is list)
    _require(
        all(type(key) is str for key in deletes) and len(set(deletes)) == len(deletes)
    )
    return adds, updates, deletes


def _diff(value, old):
    adds, updates, deletes = _diff_parts(value)
    _require(
        not adds.keys() & old.keys()
        and updates.keys() <= old.keys()
        and set(deletes) <= old.keys()
    )
    _require(
        not (
            adds.keys() & updates.keys()
            or adds.keys() & set(deletes)
            or updates.keys() & set(deletes)
        )
    )
    return {
        **{key: value for key, value in old.items() if key not in deletes},
        **adds,
        **updates,
    }


def _goal_values(goal, prior):
    inputs = _diff(goal.get("inputDiff", {}), prior.get("inputs", {}) if prior else {})
    outputs = _diff(
        goal.get("outputDiff", {}), prior.get("outputs", {}) if prior else {}
    )
    if prior is not None:
        _require(
            not any(goal.get("inputDiff", {}).values())
            and not any(goal.get("outputDiff", {}).values())
        )
    return inputs, outputs


def _goal(urn, plan, prior, graph):
    _object(
        plan, {"goal", "steps", "state", "seed"}, {"goal", "steps", "state", "seed"}
    )
    operation = "same" if prior is not None else "create"
    _require(plan["steps"] == [operation])
    _require(
        plan["state"] is None or type(plan["state"]) is dict
    )  # advisory outputs, not old state
    _require(len(base64.b64decode(plan["seed"], validate=True)) == 32)
    goal = _object(plan["goal"], {"type", "name", "custom", "protect"}, GOAL_FIELDS)
    _require(goal["name"] == urn.rsplit("::", 1)[-1])
    for key in (
        "aliases",
        "structuredAliases",
        "ignoreChanges",
        "id",
        "deleteBeforeReplace",
    ):
        _require(not goal.get(key))
    inputs, outputs = _goal_values(goal, prior)
    desired = {key: value for key, value in goal.items() if key in STATE_FIELDS}
    desired.update(urn=urn, inputs=inputs, outputs=outputs)
    if prior:
        desired["id"] = prior.get("id", "")
        _require(_ownership(desired) == _ownership(prior))
    elif urn == PROVIDER_URN:
        desired["id"] = UNKNOWN
    return _state(desired, graph, new=prior is None)


def _ownership(row):
    return {
        key: row.get(key, default)
        for key, default in (
            ("urn", ""),
            ("type", ""),
            ("custom", False),
            ("parent", ""),
            ("provider", ""),
            ("id", ""),
            ("protect", False),
            ("external", False),
        )
    }


def _preview_old(step, old, graph):
    if old:
        observed_old = _state(step.get("oldState"), graph, new=False)
        _require(
            _ownership(observed_old) == _ownership(old)
            and observed_old.get("inputs", {}) == old.get("inputs", {})
            and observed_old.get("outputs", {}) == old.get("outputs", {})
        )
    else:
        _require(step.get("oldState") is None)


def _preview_step(step, prior, desired, graph, seen):
    _object(
        step,
        {"urn", "op", "newState"},
        {
            "urn",
            "op",
            "provider",
            "oldState",
            "newState",
            "detailedDiff",
            "diffReasons",
            "replaceReasons",
        },
    )
    urn = step["urn"]
    _require(urn in graph and urn not in seen and urn != PROVIDER_URN)
    old = prior.get(urn)
    _require(
        step["op"] == ("same" if old else "create")
        and step_resource_type(step) == desired[urn]["type"]
    )
    _require(
        not step.get("replaceReasons")
        and not step.get("diffReasons")
        and not step.get("detailedDiff")
    )
    _require(step.get("provider", "") == desired[urn].get("provider", ""))
    _preview_old(step, old, graph)
    new = _state(step["newState"], graph, new=old is None)
    if old is None and new.get("id") == UNKNOWN:
        new = {**new, "id": ""}
    _require(
        _ownership(new) == _ownership(desired[urn])
        and new.get("inputs", {}) == desired[urn]["inputs"]
    )


def _preview(preview, prior, desired, graph):
    _object(
        preview,
        {"steps"},
        {"steps", "changeSummary", "config", "diagnostics", "duration", "maybeCorrupt"},
    )
    _require(
        type(preview["steps"]) is list
        and len(preview_steps(preview)) == len(preview["steps"])
    )
    _require(preview.get("maybeCorrupt", False) is False)
    seen = set()
    for step in preview_steps(preview):
        _preview_step(step, prior, desired, graph, seen)
        seen.add(step["urn"])
    # Pulumi hides the default provider and may omit unchanged resources.
    _require(set(graph) - set(prior) - {PROVIDER_URN} <= seen)


def validate(
    preview: dict[str, Any],
    *,
    saved_plan: dict[str, Any],
    prior_resources: list[dict[str, Any]],
    projection: RegistryPhaseProjection,
) -> None:
    """Require one coherent old/goal/preview graph. Provenance belongs to caller."""
    graph = _graph(projection)
    prior = _prior(prior_resources, graph)
    _object(
        saved_plan,
        {"manifest", "resourcePlans"},
        {"manifest", "resourcePlans", "config"},
    )
    manifest = _object(
        saved_plan["manifest"],
        {"version", "magic"},
        {"version", "magic", "time", "plugins"},
    )
    _require(
        manifest.get("version") == "v3.223.0"
        and manifest.get("magic") == hashlib.sha256(b"v3.223.0").hexdigest()
    )
    plans = saved_plan["resourcePlans"]
    _require(type(plans) is dict and set(plans) == set(graph))
    desired = {
        urn: _goal(urn, plan, prior.get(urn), graph) for urn, plan in plans.items()
    }
    provider_id = desired[PROVIDER_URN]["id"]
    for row in desired.values():
        _references(row, desired, provider_id)
    _preview(preview, prior, desired, graph)
