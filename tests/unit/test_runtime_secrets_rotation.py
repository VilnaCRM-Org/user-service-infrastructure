"""S1.6: rotation wiring and the idempotent synchronous seed (FR-05, FR-09).

AD-06 orders step 2: the seed ``aws.lambda.Invocation`` of each rotated
secret, then its ``SecretRotation(rotate_immediately=False)``, then the
autoscaling targets and policies. D-5 (decided 2026-09-30) rotates
``APP_SECRET`` and ``OAUTH_ENCRYPTION_KEY`` every 90 days and never rotates
``OAUTH_PASSPHRASE``. Every oracle below is a literal from the PRD,
architecture or the synthetic fixture, never one of the module's constants.

V-7 and V-18 provider-source record (first cases of S1.6), in the form of
the S1.1 V-8 record. pulumi-aws 7.23.0 pins the upstream submodule
hashicorp/terraform-provider-aws at commit
4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d ("chore: prepare v6.36.0 release").
Lifecycle paths in internal/service/lambda/invocation.go at that commit:
  create                          -> lambda Invoke, once
  read   schema.NoopContext       -> no API call (refresh never sees drift)
  update resourceInvocationUpdate -> lambda Invoke, whatever lifecycle_scope
  delete                          -> nothing under CREATE_ONLY; Invoke (delete
                                     action) under CRUD
No path calls GetFunction, so the apply role needs only lambda:InvokeFunction
(V-7). The default lifecycle_scope is CREATE_ONLY. function_name, qualifier
and triggers are ForceNew, and under CREATE_ONLY a change to input forces a
replace (customizeDiffInputChangeWithCreateOnlyScope); a replace re-invokes
the seed, which is why the seed must stay idempotent and why a replace or
delete is critical. terraform_key, tenant_id and lifecycle_scope are not
ForceNew: a change to any of them is an in-place update, and an update calls
Invoke, which re-seeds. So the seed and the guard pin lifecycle_scope to
CREATE_ONLY and leave terraform_key, tenant_id, qualifier and triggers absent
(V-18). The installed SDK text below is documentation evidence for the
CREATE_ONLY default only. The live half of V-18 is S4.6 step 19.
"""

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from app import runtime_secrets as module
from app import workload_phase
from poc_contract import _validate_document
from test_poc_contract import change
from test_poc_contract_hardened import hardened, step_two
from test_poc_workload_phase import graph

INVOCATION = "aws:lambda/invocation:Invocation"
ROTATION = "aws:secretsmanager/secretRotation:SecretRotation"
TARGET = "aws:appautoscaling/target:Target"
POLICY = "aws:appautoscaling/policy:Policy"
FUNCTION_ARN = (
    "arn:aws:lambda:eu-central-1:891377212104:function:synthetic-poc-app-rotation"
)
ARN_PREFIX = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "/user-service-infrastructure/runtime/test/synthetic-"
)
ROTATED = ("app_secret", "oauth_encryption_key")
VERSION_ID = "00000000-0000-4000-8000-0000000000a1"
CURRENT_VERSION_ID = "00000000-0000-4000-8000-0000000000c1"
ROOT = Path(__file__).resolve().parents[2]
# V-7/V-18 literals from the provider-source record in the module docstring.
V7_V18_PROVIDER_VERSION = "7.23.0"
V7_V18_UPSTREAM_COMMIT = "4981ec2b44ea4892c1ee4f0c1ed23b761a55f44d"
V18_FORCE_NEW_INPUTS = ("function_name", "qualifier", "triggers")
V18_IN_PLACE_REINVOKE_INPUTS = ("terraform_key", "tenant_id", "lifecycle_scope")


def _arn(purpose):
    return f"{ARN_PREFIX}{purpose}-abcdef"


@pytest.fixture(scope="module")
def render(tmp_path_factory):
    cache = {}

    def get(mutation):
        if mutation not in cache:
            receipt = graph(tmp_path_factory.mktemp("rotation"), "hardened", mutation)
            assert receipt["error"] is None
            cache[mutation] = receipt
        return cache[mutation]

    return get


def _of(rows, kind):
    return {name: row for name, row in rows.items() if row["type"] == kind}


# Contract rows (B1, N4).


@pytest.mark.parametrize("purpose", ROTATED)
def test_b1_a_90_day_schedule_is_accepted(purpose):
    contract = step_two()
    change(
        contract,
        f"workload.secret_lifecycle.references.{purpose}.rotation.schedule_days",
        90,
    )
    _validate_document(contract)
    assert (
        module.rotation_schedule(purpose, {"function_ref": "x", "schedule_days": 90})
        == 90
    )


@pytest.mark.parametrize("days", [89, 91])
@pytest.mark.parametrize("purpose", ROTATED)
def test_b1_an_89_or_91_day_schedule_is_refused(purpose, days):
    contract = step_two()
    change(
        contract,
        f"workload.secret_lifecycle.references.{purpose}.rotation.schedule_days",
        days,
    )
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)
    with pytest.raises(ValueError, match="90 days"):
        module.rotation_schedule(purpose, {"function_ref": "x", "schedule_days": days})


@pytest.mark.parametrize("schedule", [90.0, True, "90", None])
def test_b1_the_program_schedule_must_be_the_integer_90(schedule):
    rotation = {"function_ref": "app_rotation", "schedule_days": schedule}
    with pytest.raises(ValueError, match="90 days"):
        module.rotation_schedule("app_secret", rotation)
    with pytest.raises(ValueError, match="90 days"):
        module.rotation_schedule("app_secret", "non_rotatable")


def test_n4_an_oauth_passphrase_rotation_entry_is_refused():
    """D-5: ``OAUTH_PASSPHRASE`` is not rotated, in the contract or the program.

    S1.8 retired the purpose, so a rotated entry for it fails the schema.
    """
    contract = step_two()
    entry = dict(contract["workload"]["secret_lifecycle"]["references"]["app_secret"])
    entry["name"] = (
        "/user-service-infrastructure/runtime/test/synthetic-oauth_passphrase"
    )
    change(contract, "workload.secret_lifecycle.references.oauth_passphrase", entry)
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)
    with pytest.raises(ValueError, match="D-5"):
        module.rotation_schedule(
            "oauth_passphrase", {"function_ref": "app_rotation", "schedule_days": 90}
        )


# The seed input (FR-09) and the output schema (N1, B2).


def test_the_seed_input_is_exactly_secret_arn_and_purpose():
    contract = step_two()
    payload = json.loads(module.seed_input(contract, _arn("app_secret"), "app_secret"))
    assert payload == {"secret_arn": _arn("app_secret"), "purpose": "app_secret"}
    for purpose in ("oauth_passphrase", "two_factor_encryption_key"):
        with pytest.raises(ValueError, match="not a rotated declaration"):
            module.seed_input(contract, _arn(purpose), purpose)
    for arn in (None, _arn("oauth_encryption_key"), _arn("app_secret") + ":v1"):
        with pytest.raises(ValueError, match="identity differs"):
            module.seed_input(contract, arn, "app_secret")


def _result(**changes):
    document = {
        "secret_arn": _arn("app_secret"),
        "version_id": VERSION_ID,
        "status": "seeded",
    }
    document.update(changes)
    return json.dumps(document)


def test_the_seed_output_schema_accepts_seeded_and_noop():
    for status in ("seeded", "noop"):
        assert module.seed_result(
            _result(status=status), secret_arn=_arn("app_secret")
        ) == {
            "secret_arn": _arn("app_secret"),
            "version_id": VERSION_ID,
            "status": status,
        }


@pytest.mark.parametrize(
    "result",
    [
        _result(value="material"),
        _result(purpose="app_secret"),
        json.dumps({"secret_arn": _arn("app_secret"), "status": "seeded"}),
        json.dumps({"version_id": VERSION_ID, "status": "seeded"}),
        _result(status="rotated"),
        _result(status=""),
        _result(version_id=""),
        _result(version_id=1),
        _result(secret_arn=_arn("oauth_encryption_key")),
        json.dumps([_result()]),
        "not json",
        None,
    ],
)
def test_n1_an_output_outside_the_closed_schema_fails(result):
    with pytest.raises(ValueError, match="secret_arn, version_id, status"):
        module.seed_result(result, secret_arn=_arn("app_secret"))


def test_b2_a_seed_on_a_secret_with_awscurrent_returns_noop():
    """The seed writes nothing when ``AWSCURRENT`` exists (FR-05, AD-06)."""
    noop = _result(status="noop", version_id=CURRENT_VERSION_ID)
    assert (
        module.seed_result(
            noop, secret_arn=_arn("app_secret"), current_version_id=CURRENT_VERSION_ID
        )["status"]
        == "noop"
    )
    for written in (
        _result(status="seeded", version_id=VERSION_ID),
        _result(status="seeded", version_id=CURRENT_VERSION_ID),
        _result(status="noop", version_id=VERSION_ID),
    ):
        with pytest.raises(ValueError, match="noop"):
            module.seed_result(
                written,
                secret_arn=_arn("app_secret"),
                current_version_id=CURRENT_VERSION_ID,
            )


def test_v7_v18_the_record_names_the_pinned_provider_source():
    """The record cites the version, commit, file and lifecycle facts (V-7, V-18)."""
    from poc_provider_runtime import PINS

    assert {pin.name: pin.version for pin in PINS}["aws"] == V7_V18_PROVIDER_VERSION
    text = (ROOT / "specs/poc/secret-lifecycle.md").read_text()
    start = text.index("- **V-7 (provider source):**")
    record = " ".join(text[start : text.index("## Secret resource policies")].split())
    for marker in (
        f"pulumi-aws {V7_V18_PROVIDER_VERSION}",
        V7_V18_UPSTREAM_COMMIT,
        "internal/service/lambda/invocation.go",
        "schema.NoopContext",
        "resourceInvocationUpdate",
        "customizeDiffInputChangeWithCreateOnlyScope",
        "No path calls `GetFunction`",
        *(f"`{name}`" for name in V18_FORCE_NEW_INPUTS),
        *(f"`{name}`" for name in V18_IN_PLACE_REINVOKE_INPUTS),
    ):
        assert marker in record, marker


@pytest.mark.parametrize(
    "changes",
    [
        {"lifecycle_scope": "CRUD"},
        {"lifecycle_scope": None},
        {"qualifier": "1"},
        {"triggers": {"rerun": "1"}},
        {"terraform_key": "tf"},
        {"tenant_id": "tenant"},
    ],
)
def test_v18_an_sdk_seed_that_could_reinvoke_fails_the_guard(changes):
    """Each V-18 re-invoke input fails on the SDK path too (in-place or replace)."""
    seed = {
        "input": json.dumps({"secret_arn": "a", "purpose": "app_secret"}),
        "lifecycle_scope": "CREATE_ONLY",
    }
    assert _check(INVOCATION, seed, sdk_path=True)
    assert not _check(INVOCATION, {**seed, **changes}, sdk_path=True)


def test_v7_v18_the_installed_provider_documents_create_only_invocation():
    from pulumi_aws.lambda_ import InvocationArgs

    doc = " ".join(str(inspect.getdoc(InvocationArgs.__init__)).split())
    assert "Defaults to `CREATE_ONLY`." in doc
    assert (
        "`CREATE_ONLY` will invoke the function only on creation or replacement." in doc
    )


# The step-2 graph (FR-05 P, AD-06 order, edge).


def test_step_one_renders_no_seed_and_no_rotation(render):
    rows = render("none")["registrations"]
    assert not _of(rows, INVOCATION) and not _of(rows, ROTATION)


def test_each_rotated_secret_gets_one_create_only_seed(render):
    rows = render("step2")["registrations"]
    seeds = _of(rows, INVOCATION)
    assert set(seeds) == {
        "runtime-app_secret-seed",
        "runtime-oauth_encryption_key-seed",
    }
    for purpose in ROTATED:
        row = seeds[f"runtime-{purpose}-seed"]
        assert row["parent"] == rows["runtime-secrets"]["urn"]
        assert set(row["inputs"]) == {"functionName", "input", "lifecycleScope"}
        assert row["inputs"]["functionName"] == FUNCTION_ARN
        assert row["inputs"]["lifecycleScope"] == "CREATE_ONLY"
        assert json.loads(row["inputs"]["input"]) == {
            "secret_arn": _arn(purpose),
            "purpose": purpose,
        }
        assert rows[f"runtime-{purpose}"]["urn"] in row["dependencies"]


def test_each_rotation_waits_for_its_seed_on_the_d5_schedule(render):
    rows = render("step2")["registrations"]
    rotations = _of(rows, ROTATION)
    assert set(rotations) == {
        "runtime-app_secret-rotation",
        "runtime-oauth_encryption_key-rotation",
    }
    for purpose in ROTATED:
        row = rotations[f"runtime-{purpose}-rotation"]
        assert row["inputs"] == {
            "secretId": f"runtime-{purpose}_id",
            "rotationLambdaArn": FUNCTION_ARN,
            "rotationRules": {"automaticallyAfterDays": 90},
            "rotateImmediately": False,
        }
        assert rows[f"runtime-{purpose}-seed"]["urn"] in row["dependencies"]


def test_edge_every_autoscaling_target_and_policy_waits_for_the_rotations(render):
    """AD-06 (gate S21 nit): the S2.1/S2.2 targets and policies depend on them."""
    rows = render("step2")["registrations"]
    rotations = {
        rows["runtime-app_secret-rotation"]["urn"],
        rows["runtime-oauth_encryption_key-rotation"]["urn"],
    }
    scaled = {**_of(rows, TARGET), **_of(rows, POLICY)}
    assert set(scaled) == {
        "web-scaling-target",
        "worker-scaling-target",
        "web-cpu-tracking",
        "web-request-tracking",
        "worker-backlog-tracking",
    }
    for row in scaled.values():
        assert rotations <= set(row["dependencies"])


def test_the_seed_results_are_exported_as_metadata_only(render):
    receipt = render("step2")
    urn = receipt["registrations"]["runtime-secrets"]["urn"]
    assert receipt["outputs"][urn]["seedResults"] == {
        purpose: {
            "secret_arn": _arn(purpose),
            "version_id": VERSION_ID,
            "status": "seeded",
        }
        for purpose in ROTATED
    }
    step_one = render("none")
    urn = step_one["registrations"]["runtime-secrets"]["urn"]
    assert "seedResults" not in step_one["outputs"][urn]


# The guard's property checks (FR-09 N, D-5) on both transform paths.

SEED_PROPS = {
    "functionName": FUNCTION_ARN,
    "input": json.dumps({"secret_arn": _arn("app_secret"), "purpose": "app_secret"}),
    "lifecycleScope": "CREATE_ONLY",
}
ROTATION_PROPS = {
    "secretId": "runtime-app_secret_id",
    "rotationLambdaArn": FUNCTION_ARN,
    "rotationRules": {"automaticallyAfterDays": 90.0},
    "rotateImmediately": False,
}


def _check(kind, props, sdk_path=False):
    return workload_phase.HARDENED_PROPERTY_CHECKS[kind](props, sdk_path)


def test_the_reviewed_seed_and_rotation_pass_the_guard():
    assert _check(INVOCATION, SEED_PROPS)
    assert _check(ROTATION, ROTATION_PROPS)
    sdk_rotation = {
        "secret_id": "id",
        "rotation_rules": {"automatically_after_days": 90},
        "rotate_immediately": False,
    }
    assert _check(ROTATION, sdk_rotation, sdk_path=True)
    sdk_seed = {"input": None, "lifecycle_scope": "CREATE_ONLY", "triggers": None}
    sdk_seed["input"] = json.dumps({"secret_arn": "a", "purpose": "app_secret"})
    assert _check(INVOCATION, sdk_seed, sdk_path=True)


@pytest.mark.parametrize(
    "changes",
    [
        {
            "input": json.dumps(
                {
                    "secret_arn": _arn("app_secret"),
                    "purpose": "app_secret",
                    "value": "x",
                }
            )
        },
        {"input": json.dumps({"secret_arn": _arn("app_secret")})},
        {
            "input": json.dumps(
                {"secret_arn": _arn("oauth_passphrase"), "purpose": "oauth_passphrase"}
            )
        },
        {"input": json.dumps({"secret_arn": 1, "purpose": "app_secret"})},
        {"input": '{"purpose": "app_secret", "secret_arn": "a", "PURPOSE": "x"}'},
        {"input": json.dumps(["app_secret"])},
        {"input": "not json"},
        {"input": {"secret_arn": _arn("app_secret"), "purpose": "app_secret"}},
        {"lifecycleScope": "CRUD"},
        {"lifecycleScope": None},
        {"qualifier": "1"},
        {"triggers": {"rerun": "1"}},
        {"terraformKey": "tf"},
        {"tenantId": "tenant"},
    ],
)
def test_an_unreviewed_seed_invocation_fails_the_guard(changes):
    assert not _check(INVOCATION, {**SEED_PROPS, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"rotateImmediately": True},
        {"rotateImmediately": None},
        {"rotationRules": {"automaticallyAfterDays": 89.0}},
        {"rotationRules": {"automaticallyAfterDays": 91}},
        {"rotationRules": {"automaticallyAfterDays": True}},
        {"rotationRules": {"automaticallyAfterDays": 90, "duration": "2h"}},
        {"rotationRules": {"scheduleExpression": "rate(90 days)"}},
        {"rotationRules": None},
        {"rotationRules": [{"automaticallyAfterDays": 90}]},
    ],
)
def test_an_unreviewed_rotation_fails_the_guard(changes):
    assert not _check(ROTATION, {**ROTATION_PROPS, **changes})


def test_a_step_two_graph_admits_the_seed_and_rotation_types():
    """The closed allowlist names both types; step 1 still refuses them."""
    assert {INVOCATION, ROTATION} <= workload_phase.HARDENED_TYPES
    assert {INVOCATION, ROTATION} <= workload_phase.STEP_TWO_TYPES
    assert hardened()["workload_step"] == 1
