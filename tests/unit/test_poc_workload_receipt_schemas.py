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


TEST_ACCOUNT, PROD_ACCOUNT = "891377212104", "933245420672"
HEX_256 = "0123456789abcdef" * 4
CERTIFICATE = {
    "parameter_arn": "arn:aws:ssm:eu-central-1:891377212104:parameter/"
    "vilnacrm/test/user-service/gateway-certificate-arn",
    "parameter_version": 3,
    "certificate_arn": "arn:aws:acm:eu-central-1:891377212104:certificate/"
    "00000000-0000-4000-8000-000000000002",
}
# Draft 2020-12 ``pattern`` is ``re.search`` here, so ``$`` also matches before a
# trailing newline. Fixed-length fields pin their length; the S4.11 receipt
# library must re-check every variable-length field with ``re.fullmatch``.


def _foreign(value, key):
    return {**value, key: value[key].replace(TEST_ACCOUNT, PROD_ACCOUNT)}


def _prod(value):
    """A PROD receipt is not bound to the TEST account or gateway parameter."""
    value["stack"] = "prod"
    for row in value["secret_metadata"].values():
        row["arn"] = row["arn"].replace(TEST_ACCOUNT, PROD_ACCOUNT)
        if row["kms_key_arn"] is not None:
            row["kms_key_arn"] = row["kms_key_arn"].replace(TEST_ACCOUNT, PROD_ACCOUNT)
    for row in value["projection_inputs"]["images"].values():
        row["uri"] = row["uri"].replace(TEST_ACCOUNT, PROD_ACCOUNT)
    value["projection_inputs"]["certificate"] = {
        key: item.replace(TEST_ACCOUNT, PROD_ACCOUNT).replace("/test/", "/prod/")
        if type(item) is str
        else item
        for key, item in CERTIFICATE.items()
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
        # F4/F8: a hex-256 secret value is not a version identifier.
        lambda v: v["secret_metadata"]["app_secret"].update(version_id=HEX_256),
        lambda v: v["secret_metadata"]["app_secret"].update(version_id=HEX_256.upper()),
        # F4: secret_metadata keys are the declared purposes only.
        lambda v: v["secret_metadata"].update(
            redis_url=dict(v["secret_metadata"]["app_secret"])
        ),
        lambda v: v["secret_metadata"].update(
            synthetic_value=dict(v["secret_metadata"]["app_secret"])
        ),
        # F8: a closed certificate observation takes no extra key.
        lambda v: v["projection_inputs"].update(
            certificate={**CERTIFICATE, "value": "synthetic"}
        ),
        # F5: the one gateway parameter only.
        lambda v: v["projection_inputs"].update(
            certificate={
                **CERTIFICATE,
                "parameter_arn": CERTIFICATE["parameter_arn"].replace(
                    "gateway-certificate-arn", "other"
                ),
            }
        ),
        # F5/F8: a TEST receipt names only TEST account resources.
        lambda v: v["secret_metadata"]["app_secret"].update(
            arn=SECRET_ARN.replace(TEST_ACCOUNT, PROD_ACCOUNT)
        ),
        lambda v: v["secret_metadata"]["app_secret"].update(
            kms_key_arn=v["secret_metadata"]["app_secret"]["kms_key_arn"].replace(
                TEST_ACCOUNT, PROD_ACCOUNT
            )
        ),
        lambda v: v["projection_inputs"]["images"]["web"].update(
            uri=IMAGE["uri"].replace(TEST_ACCOUNT, PROD_ACCOUNT)
        ),
        lambda v: v["projection_inputs"].update(
            certificate=_foreign(CERTIFICATE, "certificate_arn")
        ),
        lambda v: v["projection_inputs"].update(
            certificate=_foreign(CERTIFICATE, "parameter_arn")
        ),
        # F7: fixed-length fields refuse a trailing newline that ``$`` allows.
        lambda v: v.update(contract_digest="1" * 64 + "\n"),
        lambda v: v.update(source_sha="f" * 40 + "\n"),
        lambda v: v["checkpoint"].update(etag='"' + "a" * 32 + '"\n'),
        lambda v: v["secret_metadata"]["app_secret"].update(
            kms_key_arn=v["secret_metadata"]["app_secret"]["kms_key_arn"] + "\n"
        ),
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
        lambda v: v["projection_inputs"].update(certificate=dict(CERTIFICATE)),
        lambda v: v["secret_metadata"]["app_secret"].update(version_id=None),
        lambda v: v["secret_metadata"]["app_secret"].update(
            version_id="00000000-0000-4000-8000-000000000004"
        ),
        lambda v: _prod(v),
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
        # F6: each recovery receipt carries its own operation mode only.
        (abandon_receipt, lambda v: v["workload_operation"].update(mode="first")),
        (
            abandon_receipt,
            lambda v: v["workload_operation"].update(mode="recovery-import"),
        ),
        (import_receipt, lambda v: v["workload_operation"].update(mode="step2")),
        (
            import_receipt,
            lambda v: v["workload_operation"].update(mode="recovery-abandon"),
        ),
        # F5: the abandon receipt is bound to the TEST stack and account.
        (
            abandon_receipt,
            lambda v: v.update(
                deleted=[URN.replace("urn:pulumi:test::", "urn:pulumi:prod::")]
            ),
        ),
        (
            abandon_receipt,
            lambda v: v["retain"][0].update(
                urn=URN.replace("urn:pulumi:test::", "urn:pulumi:prod::")
            ),
        ),
        (abandon_receipt, lambda v: v["retain"][0].update(secret=_foreign_secret())),
        (
            abandon_receipt,
            lambda v: v["retain"][0].update(
                import_id=SECRET_ARN.replace(TEST_ACCOUNT, PROD_ACCOUNT)
            ),
        ),
        (abandon_receipt, lambda v: v["retain"][0].update(import_id="synthetic-id")),
        (
            abandon_receipt,
            lambda v: v["retain"][0]["secret"].update(version_id=HEX_256),
        ),
        (
            import_receipt,
            lambda v: v.update(
                imported=[URN.replace("urn:pulumi:test::", "urn:pulumi:prod::")]
            ),
        ),
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


def _foreign_secret():
    return {
        "arn": SECRET_ARN.replace(TEST_ACCOUNT, PROD_ACCOUNT),
        "version_id": "a" * 32,
        "rotation_enabled": True,
    }


def test_abandon_receipt_retains_resources_without_a_secret():
    value = abandon_receipt()
    value["retain"].append(
        {
            "urn": URN.replace("runtime-app_secret", "runtime-log"),
            "import_id": "/aws/ecs/user-service-test-web",
        }
    )
    assert list(validator("poc-workload-abandon-receipt").iter_errors(value)) == []


def test_import_receipt_urns_follow_their_stack():
    value = import_receipt()
    value["stack"] = "prod"
    value["imported"] = [URN.replace("urn:pulumi:test::", "urn:pulumi:prod::")]
    assert list(validator("poc-workload-import-receipt").iter_errors(value)) == []
    value["imported"] = [URN]
    assert not validator("poc-workload-import-receipt").is_valid(value)


def _objects(node, path=""):
    """Yield every nested schema that declares an object type."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield path, node
        for key, child in node.items():
            yield from _objects(child, f"{path}/{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from _objects(child, f"{path}/{index}")


# Intended open maps: the secret purpose map, whose keys are a closed enum, and
# the observation services object, which each ``oneOf`` branch closes.
MAPS = {
    ("poc-workload-step-receipt", "/$defs/secret_metadata"),
    ("poc-workload-observation", "/properties/services"),
}


def test_every_nested_object_is_closed_except_the_intended_maps():
    seen = set()
    for name in VALID:
        schema = json.loads((SCHEMAS / f"{name}-v1.schema.json").read_text())
        for path, node in _objects(schema):
            if (name, path) in MAPS:
                seen.add((name, path))
                assert node.get("additionalProperties") is not True
                continue
            assert node.get("additionalProperties") is False, (name, path)
    assert seen == MAPS
    step = json.loads(
        (SCHEMAS / "poc-workload-step-receipt-v1.schema.json").read_text()
    )
    metadata = step["$defs"]["secret_metadata"]
    assert metadata["propertyNames"] == {
        "enum": [
            "app_secret",
            "oauth_encryption_key",
            "oauth_passphrase",
            "two_factor_encryption_key",
            "oauth_private_key",
            "oauth_public_key",
            "documentdb_primary",
        ]
    }
    assert metadata["additionalProperties"]["additionalProperties"] is False
    observation_schema = json.loads(
        (SCHEMAS / "poc-workload-observation-v1.schema.json").read_text()
    )
    for branch in observation_schema["oneOf"]:
        assert branch["properties"]["services"]["additionalProperties"] is False


def test_receipts_share_every_common_definition():
    """F-3: a ``$defs`` key in two or more schemas has one definition."""
    schemas = {
        name: json.loads((SCHEMAS / f"{name}-v1.schema.json").read_text())
        for name in VALID
    }
    owners = {}
    for name, schema in schemas.items():
        for key, value in schema["$defs"].items():
            owners.setdefault(key, []).append(json.dumps(value, sort_keys=True))
    shared = {key: values for key, values in owners.items() if len(values) > 1}
    assert {"checkpoint", "sha256", "positive_integer", "workload_operation"} <= set(
        shared
    )
    for key, values in shared.items():
        assert len(set(values)) == 1, key


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
