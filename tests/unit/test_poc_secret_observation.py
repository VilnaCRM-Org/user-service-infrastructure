"""Exercise desired creation and observed preservation without secret values."""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from poc_contract import validate
from poc_secret_observation import SECRET_PREFIX, validate_secret_observation
from test_poc_contract import fixture


def observation(contract):
    return {
        purpose: {
            "arn": SECRET_PREFIX + secret["name"] + "-AbCdEf",
            "version_id": "a" * 32,
            "kms_key_arn": secret["kms_key_arn"],
            "owner": secret["owner"],
        }
        for purpose, secret in contract["workload"]["secret_lifecycle"][
            "references"
        ].items()
    }


def test_first_creation_needs_no_generated_arn_or_version():
    contract = fixture("workload")
    references = contract["workload"]["secret_lifecycle"]["references"]
    assert all(
        set(secret) == {"name", "kms_key_arn", "owner"}
        for secret in references.values()
    )
    assert len(validate(contract, previous=fixture("registry"))) == 64
    validate_secret_observation(contract, observation(contract))


def test_second_release_and_rollback_preserve_native_secret_versions():
    original = fixture("workload")
    second = copy.deepcopy(original)
    second["workload"]["release"]["source_sha"] = "e" * 40
    second["workload"]["release"]["web"]["digest"] = "sha256:" + "f" * 64
    previous = observation(original)
    for desired, prior in ((second, original), (original, second)):
        validate(desired, previous=prior)
        validate_secret_observation(desired, copy.deepcopy(previous), previous=previous)


@pytest.mark.parametrize("field", ["arn", "version_id", "value"])
def test_generated_or_secret_fields_cannot_enter_desired_contract(field):
    contract = fixture("workload")
    contract["workload"]["secret_lifecycle"]["references"]["app_secret"][field] = (
        "synthetic"
    )
    with pytest.raises(ValueError):
        validate(contract, previous=fixture("registry"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "arn",
            "arn:aws:secretsmanager:eu-central-1:933245420672:secret:foreign-AbCdEf",
        ),
        ("arn", 1),
        (
            "arn",
            SECRET_PREFIX + "/user-service-infrastructure/runtime/test/"
            "synthetic-app_secret-extra-AbCdEf",
        ),
        ("version_id", "latest"),
        ("version_id", None),
        (
            "kms_key_arn",
            "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000002",
        ),
        ("owner", "external"),
        ("value", "DO_NOT_ECHO_SYNTHETIC"),
    ],
)
def test_native_observation_must_match_reviewed_identity(field, value):
    contract = fixture("workload")
    current = observation(contract)
    current["app_secret"][field] = value
    with pytest.raises(ValueError) as failure:
        validate_secret_observation(contract, current)
    assert "DO_NOT_ECHO_SYNTHETIC" not in str(failure.value)


@pytest.mark.parametrize("bad", [None, [], {}, {"app_secret": {}}])
def test_missing_or_untyped_observation_rejected(bad):
    with pytest.raises(ValueError):
        validate_secret_observation(fixture("workload"), bad)


def test_untyped_secret_rejected():
    contract = fixture("workload")
    current = observation(contract)
    current["app_secret"] = None
    with pytest.raises(ValueError):
        validate_secret_observation(contract, current)


@pytest.mark.parametrize("field", ["arn", "version_id"])
def test_valid_but_replaced_native_identity_rejected(field):
    contract = fixture("workload")
    previous = observation(contract)
    current = copy.deepcopy(previous)
    current["app_secret"][field] = current["app_secret"][field][:-1] + "2"
    with pytest.raises(ValueError, match="rotation or replacement"):
        validate_secret_observation(contract, current, previous=previous)


def test_previous_observation_is_validated_not_just_compared():
    contract = fixture("workload")
    malformed = observation(contract)
    malformed["app_secret"]["value"] = "synthetic"
    with pytest.raises(ValueError, match="fields differ"):
        validate_secret_observation(contract, observation(contract), previous=malformed)


def test_registry_cannot_claim_secret_result():
    with pytest.raises(ValueError, match="Registry phase"):
        validate_secret_observation(fixture("registry"), {})


def test_cross_purpose_native_identities_rejected():
    contract = fixture("workload")
    current = observation(contract)
    current["app_secret"], current["oauth_passphrase"] = (
        current["oauth_passphrase"],
        current["app_secret"],
    )
    with pytest.raises(ValueError, match="identity differs"):
        validate_secret_observation(contract, current)


def test_foreign_region_native_identity_rejected():
    contract = fixture("workload")
    current = observation(contract)
    current["app_secret"]["arn"] = current["app_secret"]["arn"].replace(
        ":eu-central-1:", ":eu-west-1:"
    )
    with pytest.raises(ValueError, match="identity differs"):
        validate_secret_observation(contract, current)


def test_extra_native_secret_purpose_rejected():
    contract = fixture("workload")
    current = observation(contract)
    current["unreviewed"] = copy.deepcopy(current["app_secret"])
    with pytest.raises(ValueError, match="purposes differ"):
        validate_secret_observation(contract, current)
