"""Hardened (``workload_step``) contract amendment: AD-04 shape and AD-25 rule."""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from poc_contract import _digest, _validate_document, load, validate
from test_poc_contract import change, fixture

ROOT = Path(__file__).resolve().parents[2]
# Digest of the committed registry contract before the S1.1 amendment.
REGISTRY_DIGEST = "c8581077695bbc0fdfd5045fc24e8fcec21d2c13effe198539f8f3cb5dc85f5f"
HARDENED_TOP = ("workload_operation", "documentdb_secret_policy", "scaling")
XP8 = {
    "lambda_network": {
        "subnet_ids": ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"],
        "bootstrap_job_security_group_id": "sg-0123456789abcdef0",
    },
    "documentdb_managed_secret_arn": (
        "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
        "rds!cluster-00000000-0000-4000-8000-000000000003-AbCdEf"
    ),
}


def hardened():
    return fixture("workload-hardened")


def references(contract):
    return contract["workload"]["secret_lifecycle"]["references"]


def step_two():
    contract = hardened()
    contract["workload_step"] = 2
    contract["workload_operation"] = {"mode": "step2", "sequence": 2}
    contract["workload"]["central"].update(copy.deepcopy(XP8))
    return contract


def test_registry_contract_digest_and_shape_are_unchanged():
    contract = load(ROOT / "specs/poc/poc-test.json")
    assert _digest(contract) == REGISTRY_DIGEST
    assert validate(contract, initial_registry=True) == REGISTRY_DIGEST
    assert "workload_step" not in contract and "admission" not in contract


def test_hardened_projection_declares_only_seeded_purposes():
    contract = hardened()
    assert len(validate(contract, previous=fixture("registry"))) == 64
    assert contract["workload_step"] == 1
    lifecycle = contract["workload"]["secret_lifecycle"]
    assert lifecycle["generation"] == "rotation-seed"
    assert "provider_refresh_actions" not in lifecycle
    rotated = {
        purpose
        for purpose, secret in references(contract).items()
        if secret["rotation"] != "non_rotatable"
    }
    assert rotated == {"app_secret", "oauth_encryption_key"}
    assert all(
        secret["rotation"] == {"function_ref": "app_rotation", "schedule_days": 90}
        for purpose, secret in references(contract).items()
        if purpose in rotated
    )
    _validate_document(step_two())


@pytest.mark.parametrize(
    "purpose",
    ["redis_auth_token", "redis_url", "document_db_password", "document_db_url"],
)
def test_removed_and_redis_purposes_are_rejected_by_the_schema(purpose):
    contract = hardened()
    declared = copy.deepcopy(references(contract)["oauth_passphrase"])
    declared["name"] = f"/user-service-infrastructure/runtime/test/synthetic-{purpose}"
    references(contract)[purpose] = declared
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


@pytest.mark.parametrize(
    "missing",
    [
        "rotation_function_arns",
        "redeploy_function_arn",
        "cmk",
        "cmk.runtime",
        "cmk.jwt",
        "cmk.two_factor",
        "app_rotation_role_arn",
        "bootstrap_job_role_arn",
        "exercise_role_arn",
    ],
)
def test_missing_central_function_or_cmk_is_rejected(missing):
    contract = hardened()
    target = contract["workload"]["central"]
    *parents, leaf = missing.split(".")
    for key in parents:
        target = target[key]
    del target[leaf]
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


def test_rotation_function_must_be_declared_in_central_metadata():
    contract = hardened()
    contract["workload"]["central"]["rotation_function_arns"] = {
        "other_rotation": contract["workload"]["central"]["redeploy_function_arn"]
    }
    with pytest.raises(ValueError, match="rotation function missing"):
        _validate_document(contract)


@pytest.mark.parametrize("key", ["lambda_network", "documentdb_managed_secret_arn"])
def test_step_two_requires_the_xp8_central_values(key):
    contract = step_two()
    del contract["workload"]["central"][key]
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("scaling.starts", [{"seq": 1}]),
        ("scaling.stops", [{"at": "2026-10-02T08:00:00"}]),
        ("scaling.starts", [{"seq": 1, "at": "2026-10-02 08:00"}]),
        ("scaling.consumed", ["web-start"]),
        ("scaling.scheduled_scaling_suspended", "false"),
        ("workload_operation", {"mode": "rollback-zero", "sequence": 2}),
        ("workload_operation", {"mode": "resume", "sequence": 2}),
        ("workload_operation", {"mode": "step2", "phase": "stop", "sequence": 2}),
        (
            "workload_operation",
            {"mode": "first", "sequence": 1, "resumes": {"mode": "first"}},
        ),
        (
            "workload_operation",
            {"mode": "resume", "sequence": 2, "resumes": {"mode": "rollback-zero"}},
        ),
        (
            "workload_operation",
            {"mode": "resume", "sequence": 2, "resumes": {"mode": "resume"}},
        ),
        ("workload_operation", {"mode": "recovery-import", "sequence": 2}),
        ("workload_operation", {"mode": "first", "sequence": 0}),
        ("workload_step", 3),
        ("workload_step", True),
        ("documentdb_secret_policy", "allow-all"),
        ("admission", {"test": True, "prod": 0}),
        ("admission", {"test": True}),
        (
            "workload.secret_lifecycle.generation",
            "generate-once-persist-explicit-rotation",
        ),
        (
            "workload.secret_lifecycle.provider_refresh_actions",
            ["secretsmanager:GetSecretValue"],
        ),
        (
            "workload.secret_lifecycle.references.app_secret.rotation",
            "non_rotatable",
        ),
        (
            "workload.secret_lifecycle.references.app_secret.rotation",
            {"function_ref": "app_rotation", "schedule_days": 30},
        ),
        (
            "workload.secret_lifecycle.references.oauth_passphrase.rotation",
            {"function_ref": "app_rotation", "schedule_days": 90},
        ),
        ("workload.secret_lifecycle.references.app_secret.value_kind", "base64-256"),
        ("workload.secret_lifecycle.references.app_secret.owner", "service-generated"),
        ("workload.secret_lifecycle.references.app_secret.value", "synthetic"),
    ],
)
def test_hardened_operation_scaling_and_secret_shapes_fail_closed(path, value):
    contract = hardened()
    change(contract, path, value)
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


@pytest.mark.parametrize(
    "operation",
    [
        {"mode": "rollback-zero", "phase": "stop", "sequence": 3},
        {"mode": "rollback-zero", "phase": "hold", "sequence": 4},
        {"mode": "policy-update", "sequence": 5},
        {"mode": "resume", "sequence": 6, "resumes": {"mode": "step2"}},
        {
            "mode": "resume",
            "sequence": 7,
            "resumes": {"mode": "rollback-zero", "phase": "start"},
        },
    ],
)
def test_reviewed_operations_carry_their_phase_or_resumed_operation(operation):
    contract = step_two()
    contract["workload_operation"] = operation
    contract["scaling"] = {
        **contract["scaling"],
        "starts": [{"seq": 1, "at": "2026-10-02T08:00:00"}],
        "stops": [{"seq": 1, "at": "2026-10-03T08:00:00"}],
        "consumed": ["start-1"],
        "scheduled_scaling_suspended": True,
    }
    contract["admission"] = {"test": True, "prod": "preview"}
    _validate_document(contract)


@pytest.mark.parametrize(
    "extra",
    [*HARDENED_TOP, "central-hardened", "central-xp8", "secret-hardened"],
)
def test_hardened_fields_require_workload_step(extra):
    contract = fixture("workload")
    source = step_two()
    if extra in HARDENED_TOP:
        contract[extra] = source[extra]
    elif extra == "central-hardened":
        contract["workload"]["central"]["cmk"] = source["workload"]["central"]["cmk"]
    elif extra == "central-xp8":
        contract["workload"]["central"]["lambda_network"] = XP8["lambda_network"]
    else:
        contract["workload"]["secret_lifecycle"] = source["workload"][
            "secret_lifecycle"
        ]
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


def test_registry_phase_accepts_admission_but_never_workload_step():
    registry = fixture("registry")
    registry["admission"] = {"test": False, "prod": False}
    assert len(validate(registry, initial_registry=True)) == 64
    registry["workload_step"] = 1
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(registry)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("workload_step", 1.0, "exact"),
        ("workload_operation.sequence", 2.0, "exact"),
        ("scaling.starts", [{"seq": 1.0, "at": "2026-10-02T08:00:00"}], "exact"),
        (
            "scaling.starts",
            [
                {"seq": 2, "at": "2026-10-02T08:00:00"},
                {"seq": 1, "at": "2026-10-03T08:00:00"},
            ],
            "strictly increasing",
        ),
        (
            "scaling.stops",
            [
                {"seq": 1, "at": "2026-10-02T08:00:00"},
                {"seq": 1, "at": "2026-10-03T08:00:00"},
            ],
            "strictly increasing",
        ),
        ("scaling.consumed", ["stop-1"], "name declared entries"),
        (
            "workload.central.apply_role_arn",
            "arn:aws:iam::891377212104:role/SyntheticPocTask",
            "distinct",
        ),
    ],
)
def test_hardened_semantics_fail_closed(path, value, message):
    contract = hardened()
    change(contract, path, value)
    with pytest.raises(ValueError, match=message):
        _validate_document(contract)


def test_generation_model_and_seeded_declarations_are_immutable():
    registry, legacy, seeded = fixture("registry"), fixture("workload"), hardened()
    assert validate(seeded, previous=seeded) == validate(seeded, previous=registry)
    for previous, contract in ((legacy, seeded), (seeded, legacy)):
        with pytest.raises(ValueError, match="generation model"):
            validate(contract, previous=previous)
    renamed = hardened()
    references(renamed)["app_secret"]["name"] += "-renamed"
    retired = hardened()
    del references(retired)["oauth_passphrase"]
    for contract in (renamed, retired):
        with pytest.raises(ValueError, match="separate contract"):
            validate(contract, previous=seeded)


@pytest.mark.parametrize("missing", ["rotation_function_arns", "cmk"])
def test_missing_central_metadata_blocks_admission_before_any_read(missing):
    """NFR-07: BLOCKED means refused before any GitHub, AWS or program step."""
    import poc_workload_admission as admission
    from poc_workload_phase_entrypoint import project_workload_phase
    from test_poc_registry_phase_entrypoint import source

    contract = hardened()
    del contract["workload"]["central"][missing]

    def forbidden(*_args, **_kwargs):
        pytest.fail("read attempted before admission")

    authority = admission.Authority(1, "synthetic-app", "a" * 40, "b" * 40)
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        admission.inspect_registry(
            None, contract, authority, "plan", gh=forbidden, download=forbidden
        )
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        admission.inspect_release(contract, authority, gh=forbidden, download=forbidden)
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        project_workload_phase(source(contract), contract, {})


SAME_ACCOUNT_KEY = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000099"
)


@pytest.mark.parametrize(
    "key",
    [
        "workload.central.cmk.jwt.arn",
        "workload.central.cmk.two_factor.arn",
        # Any other same-account key, such as the aws/secretsmanager key.
        SAME_ACCOUNT_KEY,
    ],
)
@pytest.mark.parametrize("purpose", ["app_secret", "oauth_passphrase"])
def test_hardened_secret_must_use_the_runtime_cmk(key, purpose):
    """D-4 (F2): every declared secret is encrypted by the runtime CMK."""
    contract = hardened()
    if key.startswith("workload."):
        target = contract
        for part in key.split("."):
            target = target[part]
        key = target
    references(contract)[purpose]["kms_key_arn"] = key
    with pytest.raises(ValueError, match="runtime CMK"):
        _validate_document(contract)


@pytest.mark.parametrize(
    ("first", "second"),
    [("runtime", "jwt"), ("runtime", "two_factor"), ("jwt", "two_factor")],
)
def test_hardened_cmk_arns_are_pairwise_distinct(first, second):
    contract = hardened()
    cmk = contract["workload"]["central"]["cmk"]
    cmk[second]["arn"] = cmk[first]["arn"]
    with pytest.raises(ValueError, match="CMK ARNs must be distinct"):
        _validate_document(contract)


def test_rotation_schedule_days_must_be_an_exact_integer():
    """F-2: ``90.0`` equals the schema const but is not an exact integer."""
    contract = hardened()
    references(contract)["app_secret"]["rotation"]["schedule_days"] = 90.0
    with pytest.raises(ValueError, match="exact"):
        _validate_document(contract)


def test_hardened_key_arns_refuse_a_trailing_newline():
    """F7: ``$`` matches before a final newline, so key ARNs pin their length."""
    contract = hardened()
    runtime = contract["workload"]["central"]["cmk"]["runtime"]
    runtime["arn"] += "\n"
    for secret in references(contract).values():
        secret["kms_key_arn"] = runtime["arn"]
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


CENTRAL_ROLES = (
    "publisher_role_arn",
    "execution_role_arn",
    "task_role_arn",
    "app_rotation_role_arn",
    "redeploy_role_arn",
    "bootstrap_job_role_arn",
    "restore_operator_role_arn",
    "restore_reader_role_arn",
    "apply_role_arn",
    "recovery_role_arn",
    "exercise_role_arn",
)


def _append_newline(contract, path):
    target = contract
    parts = [int(part) if part.isdigit() else part for part in path.split(".")]
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] += "\n"


@pytest.mark.parametrize(
    "path",
    [
        *(f"workload.central.{role}" for role in CENTRAL_ROLES),
        "workload.central.rotation_function_arns.app_rotation",
        "workload.central.redeploy_function_arn",
        *(f"workload.central.cmk.{key}.alias" for key in ("runtime", "jwt")),
        "workload.central.cmk.two_factor.alias",
        "workload.central.inventory_sha256",
        "workload.central.seed_enrollment_revision",
        *(
            f"workload.secret_lifecycle.references.{purpose}.name"
            for purpose in (
                "app_secret",
                "oauth_encryption_key",
                "oauth_passphrase",
                "two_factor_encryption_key",
                "oauth_private_key",
                "oauth_public_key",
            )
        ),
        "step2:workload.central.lambda_network.subnet_ids.0",
        "step2:workload.central.lambda_network.bootstrap_job_security_group_id",
        "step2:workload.central.documentdb_managed_secret_arn",
        "scaled:scaling.starts.0.at",
        "scaled:scaling.consumed.0",
    ],
)
def test_hardened_string_fields_refuse_a_trailing_newline(path):
    """N3: ``$`` matches before a final newline; hardened fields fully match."""
    kind, _, path = path.rpartition(":")
    contract = step_two() if kind else hardened()
    if kind == "scaled":
        contract["scaling"] = {
            **contract["scaling"],
            "starts": [{"seq": 1, "at": "2026-10-02T08:00:00"}],
            "stops": [],
            "consumed": ["start-1"],
            "scheduled_scaling_suspended": True,
        }
    _validate_document(copy.deepcopy(contract))
    _append_newline(contract, path)
    with pytest.raises(ValueError, match="fully match"):
        _validate_document(contract)


def test_hardened_function_reference_and_key_refuse_a_trailing_newline():
    """N3: a consistent ``function_ref`` and map key still fully match."""
    contract = hardened()
    central = contract["workload"]["central"]
    central["rotation_function_arns"]["app_rotation\n"] = central[
        "rotation_function_arns"
    ].pop("app_rotation")
    for secret in references(contract).values():
        if type(secret["rotation"]) is dict:
            secret["rotation"]["function_ref"] = "app_rotation\n"
    with pytest.raises(ValueError, match="fully match"):
        _validate_document(contract)


def test_reviewer_probe_of_trailing_newlines_is_refused():
    """N3: the reviewer's three probes each fail, not only in combination."""
    names = hardened()
    for secret in references(names).values():
        secret["name"] += "\n"
    function = hardened()
    function["workload"]["central"]["rotation_function_arns"]["app_rotation"] += "\n"
    role = hardened()
    role["workload"]["central"]["app_rotation_role_arn"] += "\n"
    for contract in (names, function, role):
        with pytest.raises(ValueError, match="fully match"):
            _validate_document(contract)
