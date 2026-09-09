"""Check secret metadata from a trusted observer; this does not authenticate AWS."""

from __future__ import annotations

import re
from typing import Any

from poc_contract import _validate_document

SECRET_PREFIX = "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
FIELDS = {"arn", "version_id", "kms_key_arn", "owner"}


def _validate_references(desired: dict[str, Any], observed: dict[str, Any]) -> None:
    """Bind every native secret identity to its reviewed name and encryption key."""
    if type(observed) is not dict or set(observed) != set(desired):
        raise ValueError("Observed secret purposes differ")
    for purpose, declaration in desired.items():
        secret = observed[purpose]
        if type(secret) is not dict or set(secret) != FIELDS:
            raise ValueError("Observed secret fields differ")
        arn_pattern = (
            re.escape(SECRET_PREFIX + declaration["name"]) + r"-[A-Za-z0-9]{6}"
        )
        if type(secret["arn"]) is not str or not re.fullmatch(
            arn_pattern, secret["arn"]
        ):
            raise ValueError("Observed secret identity differs")
        version = secret["version_id"]
        if type(version) is not str or not re.fullmatch(
            r"[A-Za-z0-9-]{32,64}", version
        ):
            raise ValueError("Observed secret version invalid")
        if (
            secret["kms_key_arn"] != declaration["kms_key_arn"]
            or secret["owner"] != declaration["owner"]
        ):
            raise ValueError("Observed secret ownership or encryption differs")


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
    Secret values are neither accepted nor returned.
    """
    _validate_document(contract)
    if contract["phase"] != "workload":
        raise ValueError("Registry phase cannot contain secret observations")
    desired = contract["workload"]["secret_lifecycle"]["references"]
    _validate_references(desired, observed)
    if previous is not None:
        _validate_references(desired, previous)
        if observed != previous:
            raise ValueError("Generated secret rotation or replacement forbidden")
