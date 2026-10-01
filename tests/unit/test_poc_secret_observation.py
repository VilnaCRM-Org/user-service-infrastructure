"""Exercise desired creation and observed preservation without secret values."""

import copy
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from poc_contract import validate
from poc_secret_observation import (
    SECRET_PREFIX,
    secret_arn_regex,
    validate_secret_observation,
    validate_seed_input,
)
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
        # N2: the exact (json_key=False) pattern refuses every reference suffix.
        *[
            ("arn_suffix", suffix)
            for suffix in (":password::", ":::" + "a" * 32, "::AWSCURRENT:")
        ],
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
    if field == "arn_suffix":
        field, value = "arn", current["app_secret"]["arn"] + value
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


def test_seeded_secrets_have_no_version_until_the_seed_then_keep_it():
    contract = fixture("workload-hardened")
    before_seed = observation(contract)
    for secret in before_seed.values():
        secret["version_id"] = None
    validate_secret_observation(contract, before_seed)
    seeded = observation(contract)
    validate_secret_observation(contract, seeded, previous=before_seed)
    validate_secret_observation(contract, copy.deepcopy(seeded), previous=seeded)


def test_seeded_rotation_changes_the_current_version_as_evidence_only():
    contract = fixture("workload-hardened")
    previous = observation(contract)
    current = copy.deepcopy(previous)
    current["app_secret"]["version_id"] = "b" * 32
    validate_secret_observation(contract, current, previous=previous)


def test_seeded_prior_receipt_comparison_uses_arn_and_name_only():
    contract = fixture("workload-hardened")
    previous = observation(contract)
    current = copy.deepcopy(previous)
    for secret in current.values():
        secret["version_id"] = "c" * 32
    validate_secret_observation(contract, current, previous=previous)
    current["app_secret"]["arn"] = (
        SECRET_PREFIX
        + "/user-service-infrastructure/runtime/test/synthetic-app_secret-ZyXwVu"
    )
    with pytest.raises(ValueError, match="replacement forbidden"):
        validate_secret_observation(contract, current, previous=previous)


def test_seeded_secret_cannot_lose_its_current_version():
    contract = fixture("workload-hardened")
    previous = observation(contract)
    current = copy.deepcopy(previous)
    current["app_secret"]["version_id"] = None
    with pytest.raises(ValueError, match="lost its current version"):
        validate_secret_observation(contract, current, previous=previous)


def _seed(contract, purpose="app_secret"):
    return {
        "secret_arn": observation(contract)[purpose]["arn"],
        "purpose": purpose,
    }


@pytest.mark.parametrize("purpose", ["app_secret", "oauth_encryption_key"])
def test_seed_input_is_exactly_the_secret_arn_and_purpose(purpose):
    contract = fixture("workload-hardened")
    validate_seed_input(contract, _seed(contract, purpose))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda seed: seed.update(value="synthetic"), "fields differ"),
        (lambda seed: seed.update(version_id="a" * 32), "fields differ"),
        (lambda seed: seed.update(stage="AWSCURRENT"), "fields differ"),
        (lambda seed: seed.pop("purpose"), "fields differ"),
        (lambda seed: seed.update(purpose="oauth_passphrase"), "not a rotated"),
        (lambda seed: seed.update(purpose="redis_auth_token"), "not a rotated"),
        (lambda seed: seed.update(purpose=["app_secret"]), "not a rotated"),
        (
            lambda seed: seed.update(purpose="oauth_encryption_key"),
            "identity differs",
        ),
        (lambda seed: seed.update(secret_arn=None), "identity differs"),
        # F8: foreign account, region and partition, a trailing newline and a
        # wildcard name never name the declared TEST secret.
        (
            lambda seed: seed.update(
                secret_arn=seed["secret_arn"].replace("891377212104", "933245420672")
            ),
            "identity differs",
        ),
        (
            lambda seed: seed.update(
                secret_arn=seed["secret_arn"].replace("eu-central-1", "eu-west-1")
            ),
            "identity differs",
        ),
        (
            lambda seed: seed.update(
                secret_arn=seed["secret_arn"].replace("arn:aws:", "arn:aws-cn:")
            ),
            "identity differs",
        ),
        (
            lambda seed: seed.update(secret_arn=seed["secret_arn"] + "\n"),
            "identity differs",
        ),
        (
            lambda seed: seed.update(
                secret_arn=SECRET_PREFIX
                + "/user-service-infrastructure/runtime/test/*-AbCdEf"
            ),
            "identity differs",
        ),
        (
            lambda seed: seed.update(secret_arn=seed["secret_arn"][:-6] + "*"),
            "identity differs",
        ),
        # N2: a JSON-key, version-ID or staging-label suffix is not the ARN.
        *[
            (
                lambda seed, suffix=suffix: seed.update(
                    secret_arn=seed["secret_arn"] + suffix
                ),
                "identity differs",
            )
            for suffix in (":password::", ":::" + "a" * 32, "::AWSCURRENT:")
        ],
    ],
)
def test_seed_input_with_any_other_key_or_target_is_rejected(mutate, message):
    contract = fixture("workload-hardened")
    seed = _seed(contract)
    mutate(seed)
    with pytest.raises(ValueError, match=message):
        validate_seed_input(contract, seed)


@pytest.mark.parametrize("seed", [None, [], "app_secret"])
def test_untyped_seed_input_is_rejected(seed):
    with pytest.raises(ValueError, match="fields differ"):
        validate_seed_input(fixture("workload-hardened"), seed)


def test_pre_hardening_contract_has_no_seed_input():
    contract = fixture("workload")
    with pytest.raises(ValueError, match="hardened workload contract"):
        validate_seed_input(contract, _seed(contract))


@pytest.mark.parametrize("version", ["0123456789abcdef" * 4, "0123456789ABCDEF" * 4])
def test_observed_version_refuses_the_hex_256_value_shape(version):
    """F4: a VersionId is a 32-64 character token; a hex-256 value is refused."""
    contract = fixture("workload-hardened")
    current = observation(contract)
    current["app_secret"]["version_id"] = version
    with pytest.raises(ValueError, match="version invalid"):
        validate_secret_observation(contract, current)


_NAME = "/user-service-infrastructure/runtime/test/synthetic-app_secret"
_ARN = f"arn:aws:secretsmanager:eu-central-1:891377212104:secret:{_NAME}-AbCdEf"


@pytest.mark.parametrize(
    ("json_key", "reference", "accepted"),
    [
        (False, _ARN, True),
        (True, _ARN, True),
        (False, _ARN + ":password::", False),
        (True, _ARN + ":password::", True),
        (False, _ARN + ":::" + "a" * 32, False),
        (True, _ARN + ":::" + "a" * 32, False),
        (False, _ARN + "::AWSCURRENT:", False),
        (True, _ARN + "::AWSCURRENT:", False),
        (False, _ARN + "\n", False),
        (True, _ARN + "\n", False),
        (False, _ARN.replace("AbCdEf", "AbCdE"), False),
        (False, _ARN.replace("AbCdEf", "AbCdE\u0661"), False),
        (True, _ARN.replace("891377212104", "933245420672"), False),
        (True, _ARN.replace("eu-central-1", "eu-west-1"), False),
        (True, _ARN.replace("synthetic-app_secret", "other"), False),
    ],
)
def test_secret_arn_regex_in_both_modes(json_key, reference, accepted):
    """N2: json_key=False is the exact ARN; json_key=True adds only `:key::`."""
    pattern = secret_arn_regex("eu-central-1", "891377212104", _NAME, json_key=json_key)
    assert bool(re.fullmatch(pattern, reference)) is accepted
