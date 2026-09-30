"""Receipt and observation schemas that later runner stories read (S1.1, AD-24)."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
KINDS = ("step-receipt", "export-receipt", "import-receipt", "abandon-receipt")
NAMES = (*(f"poc-workload-{kind}" for kind in KINDS), "poc-workload-accepted-receipt")
CHECKPOINT = {
    "version": "synthetic-version",
    "etag": '"' + "a" * 32 + '"',
    "sha256": "b" * 64,
}
OPERATION = {"mode": "step2", "sequence": 2}
PREDECESSOR = {"receipt_id": 11, "checkpoint_sha256": "c" * 64}
URN = (
    "urn:pulumi:test::user-service-infrastructure::"
    "user-service-infrastructure:secrets:Runtime$aws:secretsmanager/secret:Secret"
    "::runtime-app_secret"
)
SECRET_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "/user-service-infrastructure/runtime/test/synthetic-app_secret-AbCdEf"
)
IMAGE = {
    "uri": "891377212104.dkr.ecr.eu-central-1.amazonaws.com/user-service-test-web"
    "@sha256:" + "d" * 64,
    "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
    "config_digest": "sha256:" + "e" * 64,
    "config_size": 100,
    "platform": "linux/amd64",
}
SUCCESS_BINDING = {
    "receipt_id": 12,
    "run_id": 13,
    "run_attempt": 1,
    "checkpoint_sha256": "b" * 64,
}


def validator(name):
    return Draft202012Validator(
        json.loads((SCHEMAS / f"{name}-v1.schema.json").read_text())
    )


def step_receipt():
    return {
        "schema_version": "poc-workload-step-receipt-v1",
        "stack": "test",
        "workload_operation": dict(OPERATION),
        "outcome": "success",
        "checkpoint": dict(CHECKPOINT),
        "run_id": 13,
        "run_attempt": 1,
        "source_sha": "f" * 40,
        "contract_digest": "1" * 64,
        "projection_digest": "2" * 64,
        "generated_files_digest": "3" * 64,
        "secret_metadata": {
            "app_secret": {
                "arn": SECRET_ARN,
                "version_id": "a" * 32,
                "kms_key_arn": (
                    "arn:aws:kms:eu-central-1:891377212104:key/"
                    "00000000-0000-4000-8000-000000000010"
                ),
                "owner": "service-seeded",
            },
            "documentdb_primary": {
                "arn": "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
                "rds!cluster-00000000-0000-4000-8000-000000000003-AbCdEf",
                "version_id": "b" * 32,
                "kms_key_arn": None,
                "owner": "service-managed",
            },
        },
        "projection_inputs": {
            "source": {
                "contract_sha256": "1" * 64,
                "head_sha": "4" * 40,
                "base_sha": "5" * 40,
                "path": "specs/poc/poc-test.json",
                "blob_sha": "6" * 40,
                "schema_sha256": "7" * 64,
                "validator_sha256": "8" * 64,
            },
            "images": {"web": dict(IMAGE), "worker": dict(IMAGE)},
            "certificate": None,
        },
        "program_trees": {
            name: "9" * 40
            for name in (
                "scripts",
                "pulumi",
                "policy",
                "schemas",
                "pyproject.toml",
                "uv.lock",
            )
        },
    }


def export_receipt(cause="export"):
    value = {
        "schema_version": "poc-workload-export-receipt-v1",
        "stack": "test",
        "workload_operation": dict(OPERATION),
        "cause": cause,
        "checkpoint": dict(CHECKPOINT),
        "pending_operations": 2 if cause == "export" else 0,
        "lock_present": cause == "export",
        "run_id": 14,
        "run_attempt": 1,
    }
    if cause == "clear-pending":
        value["predecessor"] = dict(PREDECESSOR)
    return value


def import_receipt():
    return {
        "schema_version": "poc-workload-import-receipt-v1",
        "stack": "test",
        "workload_operation": {"mode": "recovery-import", "sequence": 9},
        "checkpoint": dict(CHECKPOINT),
        "run_id": 15,
        "run_attempt": 1,
        "predecessor": dict(PREDECESSOR),
        "imported": [URN],
    }


def abandon_receipt():
    return {
        "schema_version": "poc-workload-abandon-receipt-v1",
        "stack": "test",
        "workload_operation": {"mode": "recovery-abandon", "sequence": 8},
        "checkpoint": dict(CHECKPOINT),
        "run_id": 16,
        "run_attempt": 1,
        "predecessor": dict(PREDECESSOR),
        "manifest": {
            "path": "recovery/abandon-manifest.json",
            "sha256": "d" * 64,
            "approver": "Kravalg",
        },
        "deleted": [URN.replace("runtime-app_secret", "runtime-other")],
        "retain": [
            {
                "urn": URN,
                "import_id": SECRET_ARN,
                "secret": {
                    "arn": SECRET_ARN,
                    "version_id": "a" * 32,
                    "rotation_enabled": True,
                },
            }
        ],
    }


def accepted_receipt():
    return {
        "schema_version": "poc-workload-accepted-receipt-v1",
        "stack": "test",
        "workload_operation": dict(OPERATION),
        "run_id": 13,
        "run_attempt": 1,
        "success_receipt": dict(SUCCESS_BINDING),
        "checkpoint": dict(CHECKPOINT),
        "observation": {
            "kind": "start",
            "artifact_id": 17,
            "archive_sha256": "e" * 64,
            "file_sha256": "f" * 64,
        },
    }


def observation(kind="start"):
    started = {
        "desired_count": 1,
        "running_count": 1,
        "steady_state": True,
        "targets_healthy": True,
    }
    stopped = dict.fromkeys(
        ("desired_count", "running_count", "min_capacity", "max_capacity"), 0
    )
    value = {
        "schema_version": "poc-workload-observation-v1",
        "stack": "test",
        "kind": kind,
        "success_receipt": dict(SUCCESS_BINDING),
        "checkpoint": dict(CHECKPOINT),
        "action": {"seq": 1, "at": "2026-10-02T08:00:00"},
        "observed_at": "2026-10-02T08:21:00Z",
        "services": {
            "web": dict(started if kind == "start" else stopped),
            "worker": dict(started if kind == "start" else stopped),
        },
    }
    if kind == "start":
        value["health"] = {"path": "/api/health", "status": 204}
    return value


VALID = {
    "poc-workload-step-receipt": [step_receipt],
    "poc-workload-export-receipt": [
        export_receipt,
        lambda: export_receipt("clear-pending"),
    ],
    "poc-workload-import-receipt": [import_receipt],
    "poc-workload-abandon-receipt": [abandon_receipt],
    "poc-workload-accepted-receipt": [accepted_receipt],
    "poc-workload-observation": [observation, lambda: observation("stop")],
}


def test_every_receipt_schema_is_closed_draft_2020_12_and_accepts_its_example():
    assert sorted(path.name for path in SCHEMAS.glob("poc-workload-*.json")) == sorted(
        f"{name}-v1.schema.json" for name in VALID
    )
    for name, builders in VALID.items():
        schema = json.loads((SCHEMAS / f"{name}-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == f"urn:vilnacrm:{name}:v1"
        assert schema["additionalProperties"] is False
        for build in builders:
            document = build()
            assert list(validator(name).iter_errors(document)) == []
            document["value"] = "synthetic"
            assert not validator(name).is_valid(document)


def _failed(value, **changes):
    for key in ("projection_inputs", "program_trees"):
        value.pop(key)
    value.update(outcome="failed", **changes)
    return value


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.pop("projection_inputs"),
        lambda v: v.pop("program_trees"),
        lambda v: v["projection_inputs"].pop("certificate"),
        lambda v: v["projection_inputs"]["images"]["web"].pop("config_size"),
        lambda v: v["projection_inputs"]["images"]["web"].update(config_size=2**21),
        lambda v: v["projection_inputs"]["source"].pop("validator_sha256"),
        lambda v: v["program_trees"].pop("uv.lock"),
        lambda v: v.update(cause="apply"),
        lambda v: _failed(v),
        lambda v: _failed(v, cause="timeout"),
        lambda v: _failed(v, cause="apply", projection_inputs={}),
        lambda v: v.update(outcome="partial"),
        lambda v: v["secret_metadata"]["app_secret"].update(value="synthetic"),
        lambda v: v["secret_metadata"]["app_secret"].update(owner="service-generated"),
        lambda v: v.update(secret_metadata={}),
        lambda v: v["workload_operation"].update(mode="rollback-zero"),
        lambda v: v.update(workload_operation={"mode": "resume", "sequence": 3}),
        lambda v: v["checkpoint"].update(etag="a" * 32),
        lambda v: v.update(run_attempt=0),
    ],
)
def test_step_receipt_requires_projection_inputs_on_success_and_cause_on_failure(
    mutate,
):
    value = step_receipt()
    mutate(value)
    assert not validator("poc-workload-step-receipt").is_valid(value)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.update(outcome="failed", cause="apply"),
        lambda v: v.update(outcome="failed", cause="result-inspection"),
        lambda v: v["projection_inputs"].update(
            certificate={
                "parameter_arn": "arn:aws:ssm:eu-central-1:891377212104:parameter/"
                "vilnacrm/test/user-service/gateway-certificate-arn",
                "parameter_version": 3,
                "certificate_arn": "arn:aws:acm:eu-central-1:891377212104:certificate/"
                "00000000-0000-4000-8000-000000000002",
            }
        ),
        lambda v: v["secret_metadata"]["app_secret"].update(version_id=None),
        lambda v: v.update(
            workload_operation={
                "mode": "resume",
                "sequence": 3,
                "resumes": {"mode": "rollback-zero", "phase": "stop"},
            }
        ),
    ],
)
def test_step_receipt_accepts_both_outcomes_null_versions_and_closed_certificate(
    mutate,
):
    value = step_receipt()
    mutate(value)
    if value["outcome"] == "failed":
        for key in ("projection_inputs", "program_trees"):
            value.pop(key)
    assert list(validator("poc-workload-step-receipt").iter_errors(value)) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.pop("predecessor"),
        lambda v: v.update(pending_operations=1),
        lambda v: v["predecessor"].pop("checkpoint_sha256"),
        lambda v: v.update(cause="release-lock"),
    ],
)
def test_clear_pending_export_receipt_requires_its_predecessor(mutate):
    value = export_receipt("clear-pending")
    mutate(value)
    assert not validator("poc-workload-export-receipt").is_valid(value)


def test_plain_export_receipt_carries_no_predecessor():
    value = export_receipt()
    value["predecessor"] = dict(PREDECESSOR)
    assert not validator("poc-workload-export-receipt").is_valid(value)


@pytest.mark.parametrize(
    ("build", "mutate"),
    [
        (import_receipt, lambda v: v.pop("predecessor")),
        (import_receipt, lambda v: v.update(imported=[])),
        (import_receipt, lambda v: v.update(imported=["arn:aws:foreign"])),
        (abandon_receipt, lambda v: v.update(stack="prod")),
        (abandon_receipt, lambda v: v["manifest"].update(approver="dmytrocraft")),
        (abandon_receipt, lambda v: v.update(deleted=[])),
        (abandon_receipt, lambda v: v["retain"][0]["secret"].update(value="x")),
        (accepted_receipt, lambda v: v["observation"].update(kind="stop")),
        (accepted_receipt, lambda v: v["success_receipt"].pop("run_attempt")),
        (observation, lambda v: v.pop("health")),
        (observation, lambda v: v["services"]["web"].update(running_count=0)),
        (observation, lambda v: v["success_receipt"].pop("checkpoint_sha256")),
        (observation, lambda v: v["action"].pop("at")),
        (
            lambda: observation("stop"),
            lambda v: v["services"]["worker"].update(max_capacity=1),
        ),
        (
            lambda: observation("stop"),
            lambda v: v.update(health={"path": "/api/health", "status": 204}),
        ),
    ],
)
def test_recovery_acceptance_and_observation_records_fail_closed(build, mutate):
    value = build()
    name = value["schema_version"].removesuffix("-v1")
    mutate(value)
    assert not validator(name).is_valid(value)


def test_receipts_share_one_operation_and_checkpoint_definition():
    schemas = {
        name: json.loads((SCHEMAS / f"{name}-v1.schema.json").read_text())
        for name in VALID
    }
    for key in ("checkpoint", "sha256", "positive_integer"):
        assert len({json.dumps(s["$defs"][key]) for s in schemas.values()}) == 1
    operations = [
        s["$defs"]["workload_operation"] for n, s in schemas.items() if n in NAMES
    ]
    assert len({json.dumps(value) for value in operations}) == 1
    assert operations[0]["properties"]["mode"]["enum"] == [
        "first",
        "step2",
        "resume",
        "rollback-zero",
        "policy-update",
        "rebuild-first",
        "recovery-import",
        "recovery-abandon",
    ]
