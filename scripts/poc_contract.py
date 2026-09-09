"""Local proposed-contract checks. No external identity or approval authentication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "poc-test-v1.schema.json"
MAX_BYTES = 131072


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_nonfinite(_: str) -> None:
    """Reject non-standard JSON constants before they enter canonical hashing."""
    raise ValueError("non-finite JSON value")


def load(path: Path) -> dict[str, Any]:
    """Read bounded strict JSON without echoing potentially unsafe input."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("contract exceeds size limit")
    try:
        value = json.loads(
            raw, object_pairs_hook=_pairs, parse_constant=_reject_nonfinite
        )
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("contract must be an object")
    return value


def _shape(contract: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    if next(validator.iter_errors(contract), None) is not None:
        raise ValueError("contract violates poc-test-v1 schema")


def _mail_semantics(mail: dict[str, Any]) -> None:
    domain_pattern = r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}"
    address_pattern = rf"[A-Za-z0-9._+\-]+@{domain_pattern}"
    for address in [mail["sender"], *mail["recipients"]]:
        if not re.fullmatch(address_pattern, address):
            raise ValueError("invalid SES mailbox")
    identity = mail["identity_arn"].removeprefix(
        "arn:aws:ses:eu-central-1:891377212104:identity/"
    )
    sender = mail["sender"]
    if "@" in identity:
        if not re.fullmatch(address_pattern, identity) or sender != identity:
            raise ValueError("SES sender/email identity mismatch")
    else:
        sender_domain = sender.split("@")[1]
        if not re.fullmatch(domain_pattern, identity) or not (
            sender_domain == identity or sender_domain.endswith("." + identity)
        ):
            raise ValueError("SES sender/domain identity mismatch")


def _registry_semantics(registries: dict[str, Any]) -> None:
    """Bind ECR identifiers to their distinct registry names."""
    for registry in registries.values():
        name = registry["name"]
        if (
            registry["arn"]
            != f"arn:aws:ecr:eu-central-1:891377212104:repository/{name}"
        ):
            raise ValueError("registry ARN/name mismatch")
        if registry["uri"] != f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{name}":
            raise ValueError("registry URI/name mismatch")
    for key in ("name", "logical_name"):
        if registries["web"][key] == registries["worker"][key]:
            raise ValueError("web and worker registry identities must differ")


def _workload_semantics(workload: dict[str, Any], registries: dict[str, Any]) -> None:
    """Bind workload mail, roles, releases and secrets to fixed declarations."""
    _mail_semantics(workload["external"]["mail"])
    central = workload["central"]
    roles = [
        central[key]
        for key in ("execution_role_arn", "task_role_arn", "publisher_role_arn")
    ]
    if len(set(roles)) != 3:
        raise ValueError("runtime and publisher roles must be distinct")
    release = workload["release"]
    expected_ref = (
        "VilnaCRM-Org/user-service/"
        f"{central['publisher_workflow_path']}@refs/heads/main"
    )
    if release["workflow_ref"] != expected_ref:
        raise ValueError("release publisher workflow mismatch")
    for kind, target in [("web", "frankenphp_prod"), ("worker", "app_workers")]:
        image = release[kind]
        if (
            image["repository_uri"] != registries[kind]["uri"]
            or image["target"] != target
        ):
            raise ValueError("release image/registry/target mismatch")
    secrets = workload["secret_lifecycle"]["references"]
    if len({secret["name"] for secret in secrets.values()}) != len(secrets):
        raise ValueError("secret identities must be distinct")


def _semantics(contract: dict[str, Any]) -> None:
    """Apply registry semantics and workload-only semantic bindings."""
    registries = contract["registries"]
    _registry_semantics(registries)
    if contract["phase"] == "workload":
        _workload_semantics(contract["workload"], registries)


def _validate_document(contract: dict[str, Any]) -> None:
    """Apply every local shape and semantic check to one contract document."""
    _shape(contract)
    _semantics(contract)


def _validate_transition(previous: dict[str, Any], contract: dict[str, Any]) -> None:
    """Keep one authenticated contract's immutable ownership and secret bindings."""
    if previous["phase"] == "workload" and contract["phase"] != "workload":
        raise ValueError("workload to registry downgrade forbidden")
    for field in ("account_id", "region", "environment", "backend", "registries"):
        if previous[field] != contract[field]:
            raise ValueError("stack or registry ownership changed")
    if previous["phase"] == "workload":
        before = previous["workload"]["secret_lifecycle"]["references"]
        after = contract["workload"]["secret_lifecycle"]["references"]
        for purpose, secret in before.items():
            if secret["owner"] == "service-generated" and secret != after[purpose]:
                raise ValueError(
                    "generated secret rotation or replacement requires a separate "
                    "contract"
                )


def validate(
    contract: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    initial_registry: bool = False,
) -> str:
    """Return canonical digest only. Caller must authenticate previous state separately.

    Missing previous state is never interpreted as permission to omit workload.
    initial_registry is an explicit local assertion, not proof of an empty AWS stack.
    """
    if type(initial_registry) is not bool:
        raise ValueError("initial_registry must be boolean")
    _validate_document(contract)
    if previous is None:
        if not initial_registry or contract["phase"] != "registry":
            raise ValueError("authenticated prior contract required")
    else:
        if initial_registry:
            raise ValueError("initial and previous modes are exclusive")
        _validate_document(previous)
        _validate_transition(previous, contract)
    canonical = json.dumps(
        contract, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--previous", type=Path)
    mode.add_argument("--initial-registry", action="store_true")
    args = parser.parse_args()
    try:
        digest = validate(
            load(args.contract),
            previous=load(args.previous) if args.previous else None,
            initial_registry=args.initial_registry,
        )
    except (OSError, ValueError):
        print(
            "INVALID: local proposed contract or transition check failed",
            file=sys.stderr,
        )
        return 1
    print(f"VALID_PROPOSED_ONLY sha256={digest}; no external facts authenticated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
