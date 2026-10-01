"""Check secret metadata from a trusted observer; this does not authenticate AWS."""

from __future__ import annotations

import re
from typing import Any

from poc_contract import _validate_document

REGION = "eu-central-1"
ACCOUNT_ID = "891377212104"
# Resource identifier prefix, never credential material.
SECRET_PREFIX = f"arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:"  # nosec B105
FIELDS = {"arn", "version_id", "kms_key_arn", "owner"}
SEED_FIELDS = {"secret_arn", "purpose"}


def secret_arn_regex(
    region: str, account_id: str, name: str, *, json_key: bool = False
) -> str:
    """Build the one exact pattern for a declared secret: name, six-character suffix.

    ``json_key`` also admits ``:<json-key>::`` (ECS key selection). Callers must
    ``re.fullmatch`` it. ASCII digits only, never a Unicode digit class.
    """
    pattern = (
        re.escape(f"arn:aws:secretsmanager:{region}:{account_id}:secret:{name}")
        + r"-[A-Za-z0-9]{6}"
    )
    return pattern + (r"(?::[A-Za-z0-9_.-]+::)?" if json_key else "")


def _validate_secret_arn(arn: Any, declaration: dict[str, Any]) -> None:
    """Require the reviewed account-local name plus one native ARN suffix."""
    arn_pattern = secret_arn_regex(REGION, ACCOUNT_ID, declaration["name"])
    if type(arn) is not str or not re.fullmatch(arn_pattern, arn):
        raise ValueError("Observed secret identity differs")


def _validate_secret_shape(secret: Any, declaration: dict[str, Any]) -> None:
    """Require exact metadata fields and the reviewed account-local identity."""
    if type(secret) is not dict or set(secret) != FIELDS:
        raise ValueError("Observed secret fields differ")
    _validate_secret_arn(secret["arn"], declaration)


def _validate_secret_version(version: Any, *, seeded: bool = False) -> None:
    """Accept only native version identifiers; a seeded secret may have none yet.

    A VersionId is the caller's ClientRequestToken: 32-64 of ``[A-Za-z0-9-]``.
    AWS only recommends a UUID, so the charset stays; a hex-256 value shape,
    which the charset admits, is refused as possible secret material.
    """
    if seeded and version is None:
        return
    if (
        type(version) is not str
        or not re.fullmatch(r"[A-Za-z0-9-]{32,64}", version)
        or re.fullmatch(r"[0-9A-Fa-f]{64}", version)
    ):
        raise ValueError("Observed secret version invalid")


def _validate_secret_ownership(
    secret: dict[str, Any], declaration: dict[str, Any]
) -> None:
    """Bind the observer's owner and encryption key to the reviewed declaration."""
    if (
        secret["kms_key_arn"] != declaration["kms_key_arn"]
        or secret["owner"] != declaration["owner"]
    ):
        raise ValueError("Observed secret ownership or encryption differs")


def _validate_references(
    desired: dict[str, Any], observed: dict[str, Any], *, seeded: bool
) -> None:
    """Bind every native secret identity to its reviewed name and encryption key."""
    if type(observed) is not dict or set(observed) != set(desired):
        raise ValueError("Observed secret purposes differ")
    for purpose, declaration in desired.items():
        secret = observed[purpose]
        _validate_secret_shape(secret, declaration)
        _validate_secret_version(secret["version_id"], seeded=seeded)
        _validate_secret_ownership(secret, declaration)


def _validate_preserved(
    observed: dict[str, Any], previous: dict[str, Any], *, seeded: bool
) -> None:
    """Compare a prior receipt: seeded secrets by ARN and name, else exactly.

    The name is bound by the validated ARN. The observed AWSCURRENT version is
    evidence only for a seeded secret (AD-25): rotation may change it, but a
    secret that had a current version cannot lose it. This does not prove
    rotation provenance (AD-25: ``LastRotatedDate`` later than the receipt, with
    rotation enabled by the reviewed function); S4.10's result checker must.
    """
    if not seeded:
        if observed != previous:
            raise ValueError("Generated secret rotation or replacement forbidden")
        return
    for purpose, prior in previous.items():
        current = observed[purpose]
        if current["arn"] != prior["arn"]:
            raise ValueError("Seeded secret replacement forbidden")
        if prior["version_id"] is not None and current["version_id"] is None:
            raise ValueError("Seeded secret lost its current version")


def validate_secret_observation(
    contract: dict[str, Any],
    observed: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
) -> None:
    """Check a release against its prior receipt, without predeclaring versions.

    The trusted result observer must supply native current metadata and, for an
    accepted workload, its authenticated previous receipt. Omitting previous is
    only valid for first creation; this pure checker cannot establish that fact.
    A generated secret keeps its exact ARN and version. A hardened
    (``workload_step``) contract declares seeded secrets, which have no version
    until the seed runs; one keeps its identity and, once it had a current
    version, keeps one. The version may change, and that change is evidence only.
    Secret values are neither accepted nor returned.
    """
    _validate_document(contract)
    if contract["phase"] != "workload":
        raise ValueError("Registry phase cannot contain secret observations")
    seeded = "workload_step" in contract
    desired = contract["workload"]["secret_lifecycle"]["references"]
    _validate_references(desired, observed, seeded=seeded)
    if previous is not None:
        _validate_references(desired, previous, seeded=seeded)
        _validate_preserved(observed, previous, seeded=seeded)


def validate_seed_input(contract: dict[str, Any], seed: Any) -> None:
    """Accept exactly the immutable nonsecret seed input ``{secret_arn, purpose}``.

    Only a rotated declaration of a hardened contract is seeded (AD-06). Any
    other key, including a value, version or stage, is refused.
    """
    _validate_document(contract)
    if "workload_step" not in contract:
        raise ValueError("Seed input requires a hardened workload contract")
    if type(seed) is not dict or set(seed) != SEED_FIELDS:
        raise ValueError("Seed input fields differ")
    references = contract["workload"]["secret_lifecycle"]["references"]
    purpose = seed["purpose"]
    if (
        type(purpose) is not str
        or type(references.get(purpose, {}).get("rotation")) is not dict
    ):
        raise ValueError("Seed input purpose is not a rotated declaration")
    _validate_secret_arn(seed["secret_arn"], references[purpose])
