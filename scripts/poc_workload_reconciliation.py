"""Supplementary no-change check, never workload admission or replay authority.

The caller must first authenticate the accepted workload receipt, full native
checkpoint, capabilities, source and original plan bytes. This reducer cannot
admit a first workload or a release change. The worker intentionally does not
call it until those independent gates and result observation are implemented.
"""

from __future__ import annotations

import base64
import hashlib
import json

from poc_registry_plan import GOAL_FIELDS, PREFIX, ROOT, STATE_FIELDS
from service_execution_process import require

PULUMI_SECRET_SIGNATURE = "4dabf181930729395" + "15e22adb298388d"  # nosec B105
PULUMI_SECRET_SENTINEL = "1b47061264138c4a" + "c30d75fd1eb44270"  # nosec B105
GOAL_DEFAULTS = {
    "parent": "",
    "provider": "",
    "dependencies": [],
    "propertyDependencies": {},
    "protect": False,
    "ignoreChanges": [],
    "additionalSecretOutputs": [],
    "aliases": [],
    "customTimeouts": {},
}
UNSAFE_STATE = (
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
)
OBSERVATION_FIELDS = {"created", "modified", "sourcePosition", "stackTrace"}


def _check(condition):
    require(condition, "workload-no-change-reconciliation")


def _same(left, right):
    # Native JSON booleans must not compare equal to integer values.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _object(value, required, allowed):
    _check(type(value) is dict and required <= value.keys() <= allowed)


def _redacted(value):
    """Project authenticated secret wrappers to the CLI preview representation."""
    if type(value) is dict:
        if value.get(PULUMI_SECRET_SIGNATURE) == PULUMI_SECRET_SENTINEL:
            _check(
                set(value)
                in (
                    {PULUMI_SECRET_SIGNATURE, "value"},
                    {PULUMI_SECRET_SIGNATURE, "ciphertext"},
                )
            )
            return "[secret]"
        return {key: _redacted(item) for key, item in value.items()}
    if type(value) is list:
        return [_redacted(item) for item in value]
    return value


def _inventory(resources):
    _check(type(resources) is list and bool(resources))
    result = {}
    for row in resources:
        _object(row, {"urn", "type", "custom"}, STATE_FIELDS)
        urn = row["urn"]
        _check(type(urn) is str and urn.startswith(PREFIX) and urn not in result)
        _check(type(row["custom"]) is bool and type(row["type"]) is str)
        _check(not row["type"].startswith("aws:iam/"))
        _check(not any(row.get(key) for key in UNSAFE_STATE))
        _check(type(row.get("inputs", {})) is dict)
        _check(type(row.get("outputs", {})) is dict)
        _secret_inputs(row)
        _redacted(row.get("inputs", {}))
        _redacted(row.get("outputs", {}))
        _check(not row["custom"] or bool(row.get("id")))
        result[urn] = row
    _check(ROOT in result)
    for row in result.values():
        _references(row, result)
    return result


def _secret_inputs(row):
    if row["type"] == "aws:secretsmanager/secretVersion:SecretVersion":
        inputs = row.get("inputs", {})
        for key in ("secretString", "secretBinary"):
            if key in inputs:
                value = inputs[key]
                _check(
                    type(value) is dict
                    and value.get(PULUMI_SECRET_SIGNATURE) == PULUMI_SECRET_SENTINEL
                )


def _references(row, inventory):
    _check(not row.get("parent") or row["parent"] in inventory)
    dependencies = row.get("dependencies", [])
    _check(type(dependencies) is list and len(dependencies) == len(set(dependencies)))
    _check(set(dependencies) <= inventory.keys() - {row["urn"]})
    properties = row.get("propertyDependencies", {})
    _check(
        type(properties) is dict and properties.keys() <= row.get("inputs", {}).keys()
    )
    for values in properties.values():
        _check(type(values) is list and set(values) <= inventory.keys() - {row["urn"]})
    provider = row.get("provider", "")
    if provider:
        _check(type(provider) is str and "::" in provider)
        urn, identifier = provider.rsplit("::", 1)
        _check(urn in inventory and inventory[urn].get("id") == identifier)
        _check(inventory[urn]["type"].startswith("pulumi:providers:"))


def _goal(urn, plan, prior):
    _object(
        plan, {"goal", "steps", "state", "seed"}, {"goal", "steps", "state", "seed"}
    )
    _check(plan["steps"] == ["same"])
    _check(plan["state"] is None or type(plan["state"]) is dict)
    _check(len(base64.b64decode(plan["seed"], validate=True)) == 32)
    goal = plan["goal"]
    _object(goal, {"type", "name", "custom", "protect"}, GOAL_FIELDS)
    _check(goal["name"] == urn.rsplit("::", 1)[-1])
    _check(
        _same(goal["type"], prior["type"]) and _same(goal["custom"], prior["custom"])
    )
    for field in ("id", "structuredAliases", "deleteBeforeReplace"):
        _check(not goal.get(field))
    for field, default in GOAL_DEFAULTS.items():
        _check(_same(goal.get(field, default), prior.get(field, default)))
    for field in ("inputDiff", "outputDiff"):
        diff = goal.get(field, {})
        _object(diff, set(), {"adds", "updates", "deletes"})
        _check(_same(diff.get("adds", {}), {}) and _same(diff.get("updates", {}), {}))
        _check(_same(diff.get("deletes", []), []))


def _preview_step(step, inventory, seen):
    _object(
        step,
        {"urn", "op", "oldState", "newState"},
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
    _check(urn in inventory and urn not in seen and step["op"] == "same")
    seen.add(urn)
    _check(
        not any(
            step.get(key) for key in ("detailedDiff", "diffReasons", "replaceReasons")
        )
    )
    _check(step.get("provider", "") == inventory[urn].get("provider", ""))
    expected = _redacted(
        {
            key: value
            for key, value in inventory[urn].items()
            if key not in OBSERVATION_FIELDS
        }
    )
    for field in ("oldState", "newState"):
        state = step[field]
        _object(state, {"urn", "type", "custom"}, STATE_FIELDS)
        actual = {
            key: value for key, value in state.items() if key not in OBSERVATION_FIELDS
        }
        _check(_same(actual, expected))


def _preview(preview, inventory):
    _object(
        preview,
        {"steps"},
        {"steps", "changeSummary", "config", "diagnostics", "duration", "maybeCorrupt"},
    )
    _check(
        type(preview["steps"]) is list and preview.get("maybeCorrupt", False) is False
    )
    summary = preview.get("changeSummary", {})
    _object(summary, set(), {"same"})
    _check(type(summary.get("same", 0)) is int and summary.get("same", 0) >= 0)
    seen = set()
    for step in preview["steps"]:
        _preview_step(step, inventory, seen)


def validate_no_change(preview, *, saved_plan, prior_resources):
    """Reject any operation or goal/preview change against an authenticated graph.

    Prior inputs remain private; only preview values use redaction. Advisory
    saved-plan state and summary counts never substitute for the complete goals.
    Empty previews are valid because Pulumi can omit all unchanged resources.
    """
    inventory = _inventory(prior_resources)
    _object(
        saved_plan,
        {"manifest", "resourcePlans"},
        {"manifest", "resourcePlans", "config"},
    )
    manifest = saved_plan["manifest"]
    _object(manifest, {"version", "magic"}, {"version", "magic", "time", "plugins"})
    _check(manifest["version"] == "v3.223.0")
    _check(manifest["magic"] == hashlib.sha256(b"v3.223.0").hexdigest())
    plans = saved_plan["resourcePlans"]
    _check(type(plans) is dict and plans.keys() == inventory.keys())
    for urn, plan in plans.items():
        _goal(urn, plan, inventory[urn])
    _preview(preview, inventory)
