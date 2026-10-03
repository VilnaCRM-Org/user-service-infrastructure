"""Fail-closed guards of the S1.6 seed and rotation in the integration suite.

The integration coverage gate includes ``pulumi/app``. The generated graphs
here render step 1 only, so these cases drive the S1.6 helpers directly: the
D-5 90-day schedule (89 and 91 refused, ``OAUTH_PASSPHRASE`` never rotated),
the seed input of exactly ``{secret_arn, purpose}`` (FR-09), the closed seed
output ``{secret_arn, version_id, status}`` with ``noop`` on a secret that
already has ``AWSCURRENT`` (AD-06), and the guard's seed Invocation check.
"""

import json
import sys
from pathlib import Path

import pytest
from app.runtime_secrets import rotation_schedule, seed_input, seed_result
from app.workload_phase import _reject_secret_material

import pulumi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
SECRET_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "/user-service-infrastructure/runtime/test/synthetic-app_secret-abcdef"
)
VERSION_ID = "00000000-0000-4000-8000-0000000000a1"
CURRENT_VERSION_ID = "00000000-0000-4000-8000-0000000000c1"


def _contract():
    fixture = PROJECT_ROOT / "tests/fixtures/poc-contract"
    return json.loads((fixture / "workload-hardened.synthetic.json").read_text())


def _result(**changes):
    document = {"secret_arn": SECRET_ARN, "version_id": VERSION_ID}
    document["status"] = "seeded"
    document.update(changes)
    return json.dumps(document)


def _seed(payload):
    props = {"input": payload, "lifecycleScope": "CREATE_ONLY"}
    return pulumi.ResourceTransformationArgs(
        resource=None,
        type_="aws:lambda/invocation:Invocation",
        name="probe",
        props=props,
        opts=None,
    )


def test_the_d5_schedule_is_90_days_for_rotated_purposes_only():
    rotation = {"function_ref": "app_rotation", "schedule_days": 90}
    assert rotation_schedule("app_secret", rotation) == 90
    assert rotation_schedule("oauth_encryption_key", rotation) == 90
    for days in (89, 91):
        with pytest.raises(ValueError, match="90 days"):
            rotation_schedule("app_secret", {**rotation, "schedule_days": days})
    with pytest.raises(ValueError, match="D-5"):
        rotation_schedule("oauth_passphrase", rotation)


def test_the_seed_input_is_exactly_secret_arn_and_purpose():
    contract = _contract()
    assert json.loads(seed_input(contract, SECRET_ARN, "app_secret")) == {
        "secret_arn": SECRET_ARN,
        "purpose": "app_secret",
    }
    with pytest.raises(ValueError, match="not a rotated declaration"):
        seed_input(contract, SECRET_ARN, "oauth_passphrase")


def test_the_seed_output_is_closed_and_idempotent():
    assert seed_result(_result(), secret_arn=SECRET_ARN)["status"] == "seeded"
    for result in (_result(value="material"), "not json", None):
        with pytest.raises(ValueError, match="secret_arn, version_id, status"):
            seed_result(result, secret_arn=SECRET_ARN)
    noop = _result(status="noop", version_id=CURRENT_VERSION_ID)
    assert (
        seed_result(noop, secret_arn=SECRET_ARN, current_version_id=CURRENT_VERSION_ID)[
            "status"
        ]
        == "noop"
    )
    with pytest.raises(ValueError, match="noop"):
        seed_result(
            _result(), secret_arn=SECRET_ARN, current_version_id=CURRENT_VERSION_ID
        )


def test_the_guard_admits_only_the_reviewed_seed_payload():
    reviewed = json.dumps({"secret_arn": SECRET_ARN, "purpose": "app_secret"})
    assert _reject_secret_material(_seed(reviewed), 2) is None
    for payload in (
        json.dumps({"secret_arn": SECRET_ARN, "purpose": "app_secret", "value": "x"}),
        json.dumps({"secret_arn": SECRET_ARN, "purpose": "oauth_passphrase"}),
        "not json",
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(_seed(payload), 2)
