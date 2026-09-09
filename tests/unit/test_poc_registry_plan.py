"""Real Pulumi PlanDiff/PreviewStep wire shapes, with closed registry ownership."""

import base64
import copy
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
plan = importlib.import_module("poc_registry_plan")


def projection():
    return plan.RegistryPhaseProjection(copy.deepcopy(plan.REGISTRIES))


def states():
    """Represent ResourceV3, which has URN/type and no resource-name field."""
    result = {}
    for urn, (kind, parent, custom) in plan._graph(projection()).items():
        row = {
            "urn": urn,
            "type": kind,
            "custom": custom,
            "parent": parent,
            "protect": False,
            "inputs": {},
            "outputs": (
                copy.deepcopy(plan._component_outputs(kind))
                if kind in (plan.STACK, plan.ENVIRONMENT)
                else {}
            ),
        }
        if kind == plan.PROVIDER:
            row.update(
                id="provider-id",
                inputs={
                    "version": "7.23.0",
                    "region": plan.REGION,
                    "allowedAccountIds": json.dumps([plan.ACCOUNT]),
                    "__internal": {},
                    "skipCredentialsValidation": "false",
                    "skipRegionValidation": "false",
                    "skipRequestingAccountId": "false",
                },
            )
        if kind == plan.ECR:
            name = plan._repository(urn)
            row.update(
                id=name,
                provider=f"{plan.PROVIDER_URN}::provider-id",
                inputs={
                    "name": name,
                    "imageTagMutability": "IMMUTABLE",
                    "forceDelete": False,
                    "imageScanningConfiguration": {"scanOnPush": True},
                    "tags": copy.deepcopy(plan.DEFAULT_TAGS),
                },
            )
            row["outputs"] = {
                **row["inputs"],
                "arn": f"arn:aws:ecr:{plan.REGION}:{plan.ACCOUNT}:repository/{name}",
                "repositoryUrl": (
                    f"{plan.ACCOUNT}.dkr.ecr.{plan.REGION}.amazonaws.com/{name}"
                ),
                "registryId": plan.ACCOUNT,
            }
        result[urn] = row
    return result


def case(prior_kind="baseline"):
    """Serialize engine GoalV1 adds/same diffs and its separate JSON preview."""
    complete = states()
    prior = {
        key: row
        for key, row in complete.items()
        if prior_kind == "repeat"
        or (
            prior_kind == "baseline"
            and key in (plan.ROOT, plan.PROVIDER_URN, plan.ENVIRONMENT_URN)
        )
    }
    saved = {
        "manifest": {
            "version": "v3.223.0",
            "magic": hashlib.sha256(b"v3.223.0").hexdigest(),
            "time": "2026-09-09T00:00:00Z",
        },
        "resourcePlans": {},
    }
    preview = {"steps": [], "changeSummary": {}}
    for urn, existing in complete.items():
        row = copy.deepcopy(existing)
        old = prior.get(urn)
        operation = "same" if old else "create"
        if old is None:
            row.pop("id", None)
            row["outputs"] = {}
            if row["type"] == plan.ECR and plan.PROVIDER_URN not in prior:
                row["provider"] = f"{plan.PROVIDER_URN}::{plan.UNKNOWN}"
        goal = {
            key: copy.deepcopy(row[key])
            for key in ("type", "custom", "parent", "protect", "provider")
            if key in row
        }
        goal.update(
            name=urn.rsplit("::", 1)[-1],
            inputDiff={} if old else {"adds": row["inputs"]},
            outputDiff={},
        )
        saved["resourcePlans"][urn] = {
            "goal": goal,
            "steps": [operation],
            "state": None,
            "seed": base64.b64encode(bytes(range(32))).decode(),
        }
        # The real JSON digest hides default-provider events, including creates.
        if row["type"] != plan.PROVIDER:
            step = {
                "urn": urn,
                "op": operation,
                "provider": row.get("provider", ""),
                "newState": row,
                "detailedDiff": None,
            }
            if old:
                step["oldState"] = copy.deepcopy(old)
            preview["steps"].append(step)
    return {
        "preview": preview,
        "saved_plan": saved,
        "prior_resources": list(prior.values()),
        "projection": projection(),
    }


def validate(data):
    return plan.validate(**data)


def ecr_goal(data):
    return next(
        row["goal"]
        for urn, row in data["saved_plan"]["resourcePlans"].items()
        if urn.endswith("::user-service-web-repository")
    )


def ecr_step(data):
    return next(
        row
        for row in data["preview"]["steps"]
        if row["urn"].endswith("::user-service-web-repository")
    )


@pytest.mark.parametrize("prior_kind", ["new", "baseline", "repeat"])
def test_create_provider_initial_and_unchanged_repeat(prior_kind):
    validate(case(prior_kind))


def test_omitted_unchanged_graph_is_reconstructed():
    data = case("repeat")
    data["preview"]["steps"] = []
    validate(data)
    data = case()
    data["preview"]["steps"] = [
        step for step in data["preview"]["steps"] if step["op"] != "same"
    ]
    validate(data)


def test_real_sdk_urn_qualification():
    """Use installed SDK create_urn to verify full parent type ancestry."""
    code = """
import asyncio, json
from pulumi.runtime.resource import create_urn
async def main():
    parent = await create_urn(
        "user-service", "user-service-infrastructure:stack:UserService",
        project="user-service-infrastructure", stack="test").future()
    registry = await create_urn(
        "registries", "user-service-infrastructure:registry:Plane",
        parent=parent).future()
    repository = await create_urn(
        "user-service-web-repository", "aws:ecr/repository:Repository",
        parent=registry).future()
    print(json.dumps([parent, registry, repository]))
asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        plan.SERVICE_URN,
        plan.REGISTRY_URN,
        f"{plan.PREFIX}{plan.SERVICE}${plan.REGISTRY}${plan.ECR}::user-service-web-repository",
    ]


@pytest.mark.parametrize(
    "operation",
    [
        "delete",
        "replace",
        "update",
        "create-replacement",
        "delete-replaced",
        "refresh",
        "read",
        "unknown",
    ],
)
def test_all_mutating_or_unknown_operations_reject(operation):
    data = case("repeat")
    ecr_step(data)["op"] = operation
    with pytest.raises(ValueError):
        validate(data)
    data = case("repeat")
    next(
        row
        for urn, row in data["saved_plan"]["resourcePlans"].items()
        if urn.endswith("::user-service-web-repository")
    )["steps"] = [operation]
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize(
    "kind",
    [
        "aws:iam/role:Role",
        "aws:ec2/vpc:Vpc",
        "aws:ecs/service:Service",
        "aws:secretsmanager/secret:Secret",
    ],
)
def test_foreign_resource_never_hides_in_prior_plan_or_preview(kind):
    foreign = {"urn": f"{plan.PREFIX}{kind}::foreign", "type": kind, "custom": True}
    for where in ("prior", "plan", "preview"):
        data = case()
        if where == "prior":
            data["prior_resources"].append(foreign)
        elif where == "plan":
            data["saved_plan"]["resourcePlans"][foreign["urn"]] = {}
        else:
            data["preview"]["steps"].append(
                {"urn": foreign["urn"], "op": "create", "newState": foreign}
            )
        with pytest.raises(ValueError):
            validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "foreign"),
        ("imageTagMutability", "MUTABLE"),
        ("forceDelete", True),
        ("imageScanningConfiguration", {"scanOnPush": False}),
        ("name", plan.UNKNOWN),
        ("encryptionConfigurations", [{"encryptionType": "KMS", "kmsKey": "foreign"}]),
    ],
)
def test_ecr_inputs_cannot_expand_or_be_unknown(field, value):
    data = case()
    ecr_goal(data)["inputDiff"]["adds"][field] = value
    ecr_step(data)["newState"]["inputs"][field] = value
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("region", "us-east-1"),
        ("allowedAccountIds", '["933245420672"]'),
        ("version", "7.24.0"),
        ("profile", "foreign"),
        ("assumeRoles", [{}]),
        ("endpoints", [{}]),
        ("accessKey", "synthetic"),
        ("skipRegionValidation", "true"),
        ("skipCredentialsValidation", 0),
        ("__internal", {"pluginDownloadURL": "foreign"}),
    ],
)
def test_hidden_provider_goals_closed(field, value):
    data = case("new")
    data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]["goal"]["inputDiff"]["adds"][
        field
    ] = value
    with pytest.raises(ValueError):
        validate(data)


def test_wrong_provider_reference_parent_and_physical_owner():
    for field, value in (
        ("provider", f"{plan.PROVIDER_URN}::foreign"),
        ("parent", plan.SERVICE_URN),
        ("custom", False),
    ):
        data = case()
        ecr_goal(data)[field] = value
        with pytest.raises(ValueError):
            validate(data)
    data = case("repeat")
    prior = next(row for row in data["prior_resources"] if row["type"] == plan.ECR)
    prior["id"] = "foreign"
    with pytest.raises(ValueError):
        validate(data)


def test_old_state_and_goal_diff_bind_authenticated_checkpoint():
    data = case("repeat")
    ecr_step(data)["oldState"]["outputs"]["arn"] = "foreign"
    with pytest.raises(ValueError):
        validate(data)
    data = case("repeat")
    ecr_goal(data)["inputDiff"] = {"updates": {"name": "foreign"}}
    with pytest.raises(ValueError):
        validate(data)
    data = case("repeat")
    ecr_goal(data)["outputDiff"] = {"updates": {"arn": "foreign"}}
    with pytest.raises(ValueError):
        validate(data)


def test_complete_graph_rejects_missing_duplicate_or_partial_prior():
    data = case()
    data["preview"]["steps"].remove(ecr_step(data))
    with pytest.raises(ValueError):
        validate(data)
    data = case()
    data["preview"]["steps"].append(copy.deepcopy(ecr_step(data)))
    with pytest.raises(ValueError):
        validate(data)
    data = case("repeat")
    data["prior_resources"].pop()
    with pytest.raises(ValueError):
        validate(data)
    data = case()
    data["prior_resources"].append(copy.deepcopy(data["prior_resources"][0]))
    with pytest.raises(ValueError):
        validate(data)
    data = case()
    del data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]
    with pytest.raises(ValueError):
        validate(data)


def test_state_name_and_advisory_outputs_are_not_identity():
    data = case()
    ecr_step(data)["newState"]["name"] = "user-service-web-repository"
    with pytest.raises(ValueError):
        validate(data)
    data = case()
    ecr_goal(data)["inputDiff"]["adds"]["name"] = "foreign"
    next(
        row
        for urn, row in data["saved_plan"]["resourcePlans"].items()
        if urn.endswith("::user-service-web-repository")
    )["state"] = states()[ecr_step(data)["urn"]]["outputs"]
    with pytest.raises(ValueError):
        validate(data)


def test_new_computed_identity_may_be_unknown_but_not_foreign():
    data = case()
    ecr_step(data)["newState"].update(id=plan.UNKNOWN, outputs={"arn": plan.UNKNOWN})
    validate(data)
    ecr_step(data)["newState"]["outputs"]["arn"] = (
        "arn:aws:ecr:us-east-1:891377212104:repository/user-service-test-web"
    )
    with pytest.raises(ValueError):
        validate(data)


def test_list_account_pin_and_closed_property_dependencies():
    data = case("new")
    provider = data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]["goal"]
    provider["inputDiff"]["adds"]["allowedAccountIds"] = [plan.ACCOUNT]
    goal = ecr_goal(data)
    goal["propertyDependencies"] = {"name": [plan.REGISTRY_URN]}
    validate(data)
    goal["propertyDependencies"]["name"] = ["foreign"]
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize(
    "key",
    [
        "skipCredentialsValidation",
        "skipRegionValidation",
        "skipRequestingAccountId",
    ],
)
def test_omitted_provider_validation_pin_rejects(key):
    data = case("new")
    provider = data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]["goal"]
    del provider["inputDiff"]["adds"][key]
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize("key", ["replaceReasons", "diffReasons", "detailedDiff"])
def test_contradictory_preview_diff_rejects(key):
    data = case("repeat")
    ecr_step(data)[key] = {"name": "changed"}
    with pytest.raises(ValueError):
        validate(data)


def test_root_only_baseline_rejects_foreign_reference():
    data = case("new")
    root = states()[plan.ROOT]
    root["provider"] = "foreign"
    data["prior_resources"] = [root]
    with pytest.raises(ValueError):
        validate(data)


def legacy_case(monkeypatch):
    """Reconstruct public fields only; timestamps stay native, so isolate hash seam."""
    data = case("baseline")
    provider = next(
        row for row in data["prior_resources"] if row["type"] == plan.PROVIDER
    )
    provider.update(
        id=plan.LEGACY_PROVIDER_ID, inputs=copy.deepcopy(plan.LEGACY_PROVIDER_INPUTS)
    )
    provider["outputs"] = {
        k: v for k, v in provider["inputs"].items() if k != "__internal"
    }
    record = data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]
    goal = record["goal"]
    desired = states()[plan.PROVIDER_URN]["inputs"]
    desired_outputs = {k: v for k, v in desired.items() if k != "__internal"}
    goal["inputDiff"] = _wire_diff(provider["inputs"], desired)
    goal["outputDiff"] = _wire_diff(provider["outputs"], desired_outputs)
    record["steps"] = ["update"]
    for saved in data["saved_plan"]["resourcePlans"].values():
        if saved["goal"].get("type") == plan.ECR:
            saved["goal"]["provider"] = (
                f"{plan.PROVIDER_URN}::{plan.LEGACY_PROVIDER_ID}"
            )
    for step in data["preview"]["steps"]:
        if step["newState"]["type"] == plan.ECR:
            step["provider"] = f"{plan.PROVIDER_URN}::{plan.LEGACY_PROVIDER_ID}"
            step["newState"]["provider"] = step["provider"]
    raw = json.dumps(
        data["prior_resources"], sort_keys=True, separators=(",", ":")
    ).encode()
    monkeypatch.setattr(
        plan, "LEGACY_RESOURCES_SHA256", hashlib.sha256(raw).hexdigest()
    )
    return data


def _wire_diff(old, new):
    return {
        "adds": {k: v for k, v in new.items() if k not in old},
        "updates": {k: v for k, v in new.items() if k in old and old[k] != v},
        "deletes": [k for k in old if k not in new],
    }


def test_native_legacy_pin_is_exact_constant():
    assert plan.LEGACY_RESOURCES_SHA256 == (
        "57ea8229ba3becac6ffc20a74f40a2bf1f93600ca1bf2b59f5c5f6d27a8dd6f8"
    )
    assert plan.LEGACY_PROVIDER_ID == "f1cec252-9073-4066-a19b-b3e950b32342"


def test_only_pinned_legacy_baseline_hardens_same_provider_identity(monkeypatch):
    data = legacy_case(monkeypatch)
    validate(data)
    assert set(plan._prior(data["prior_resources"], plan._graph(projection()))) == {
        plan.ROOT,
        plan.PROVIDER_URN,
        plan.ENVIRONMENT_URN,
    }
    monkeypatch.setattr(plan, "LEGACY_RESOURCES_SHA256", "0" * 64)
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize(
    "operation", ["same", "create", "replace", "delete", "create-replacement"]
)
def test_legacy_provider_requires_only_nonreplacing_hardening(monkeypatch, operation):
    data = legacy_case(monkeypatch)
    data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]["steps"] = [operation]
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "foreign"),
        ("inputs", {**plan.LEGACY_PROVIDER_INPUTS, "profile": "foreign"}),
        ("outputs", {"region": "eu-central-1"}),
    ],
)
def test_legacy_provider_shape_never_bypasses_canonical_hash(monkeypatch, field, value):
    data = legacy_case(monkeypatch)
    provider = next(
        row for row in data["prior_resources"] if row["type"] == plan.PROVIDER
    )
    provider[field] = value
    with pytest.raises(ValueError):
        validate(data)


def test_hardening_cannot_weaken_new_account_or_validation(monkeypatch):
    data = legacy_case(monkeypatch)
    goal = data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]["goal"]
    goal["inputDiff"]["adds"]["allowedAccountIds"] = '["933245420672"]'
    with pytest.raises(ValueError):
        validate(data)
    data = legacy_case(monkeypatch)
    goal = data["saved_plan"]["resourcePlans"][plan.PROVIDER_URN]["goal"]
    goal["inputDiff"]["updates"]["skipRegionValidation"] = "true"
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize("urn", [plan.ROOT, plan.ENVIRONMENT_URN])
def test_baseline_exports_cannot_change_or_disappear(urn):
    data = case("repeat")
    data["saved_plan"]["resourcePlans"][urn]["goal"]["outputDiff"] = {
        "deletes": ["defaultTags"]
    }
    with pytest.raises(ValueError):
        validate(data)
    data = case("repeat")
    next(row for row in data["prior_resources"] if row["urn"] == urn)["outputs"] = {}
    with pytest.raises(ValueError):
        validate(data)


def test_repository_tagging_is_exact_and_not_provider_default_authority():
    data = case()
    ecr_goal(data)["inputDiff"]["adds"]["tags"]["Owner"] = "foreign"
    with pytest.raises(ValueError):
        validate(data)
    data = case()
    ecr_goal(data)["inputDiff"]["adds"]["tagsAll"] = plan.DEFAULT_TAGS
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize("mutation", ["id", "outputs", "extra-resource"])
def test_legacy_hash_gate_does_not_replace_semantic_validation(monkeypatch, mutation):
    data = legacy_case(monkeypatch)
    provider = next(
        row for row in data["prior_resources"] if row["type"] == plan.PROVIDER
    )
    if mutation == "extra-resource":
        data["prior_resources"].append(states()[plan.SERVICE_URN])
    elif mutation == "id":
        provider["id"] = "other-provider"
    else:
        provider["outputs"] = {**provider["outputs"], "__internal": {}}
    raw = json.dumps(
        data["prior_resources"], sort_keys=True, separators=(",", ":")
    ).encode()
    monkeypatch.setattr(
        plan, "LEGACY_RESOURCES_SHA256", hashlib.sha256(raw).hexdigest()
    )
    with pytest.raises(ValueError):
        validate(data)
