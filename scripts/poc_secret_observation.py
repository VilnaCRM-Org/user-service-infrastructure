"""Check secret metadata from a trusted observer; this does not authenticate AWS."""

from __future__ import annotations

import re
from typing import Any

from poc_contract import _validate_document

# Resource identifier prefix, never credential material.
SECRET_PREFIX = "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"  # nosec B105
FIELDS = {"arn", "version_id", "kms_key_arn", "owner"}
IDENTITY = ("arn", "kms_key_arn", "owner")
SEED_FIELDS = {"secret_arn", "purpose"}


def _validate_secret_arn(arn: Any, declaration: dict[str, Any]) -> None:
    """Require the reviewed account-local name plus one native ARN suffix."""
    arn_pattern = re.escape(SECRET_PREFIX + declaration["name"]) + r"-[A-Za-z0-9]{6}"
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
    """Keep identities; only a seeded secret's first version may appear later."""
    if not seeded:
        if observed != previous:
            raise ValueError("Generated secret rotation or replacement forbidden")
        return
    for purpose, prior in previous.items():
        current = observed[purpose]
        if any(current[key] != prior[key] for key in IDENTITY) or prior[
            "version_id"
        ] not in (None, current["version_id"]):
            raise ValueError("Seeded secret replacement or version change forbidden")


def validate_secret_observation(
    contract: dict[str, Any],
    observed: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
) -> None:
    """Preserve authenticated versions across releases, without predeclaring them.

    The trusted result observer must supply native current metadata and, for an
    accepted workload, its authenticated previous receipt. Omitting previous is
    only valid for first creation; this pure checker cannot establish that fact.
    A hardened (``workload_step``) contract declares seeded secrets, which have
    no version until the seed runs. Secret values are neither accepted nor
    returned.
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
