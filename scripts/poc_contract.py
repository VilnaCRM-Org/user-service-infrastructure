"""Local proposed-contract checks. No external identity or approval authentication."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError, validators

SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "poc-test-v1.schema.json"
MAX_BYTES = 131072


@dataclass(frozen=True)
class RegistryReleaseBinding:
    """Original registry reference supplied by a separate trusted authenticator.

    The receipt identifier is a GitHub deployment ID, never an artifact ID.
    Constructing this value does not authenticate its issuer or checkpoint.
    """

    registry_phase_receipt_id: int
    registry_contract_digest: str
    registry_checkpoint_version: str


def _registry_release_fields(release: dict[str, Any]) -> None:
    """Reject ambiguous IDs and preserve opaque, bounded native S3 versions."""
    receipt = release["registry_phase_receipt_id"]
    digest = release["registry_contract_digest"]
    version = release["registry_checkpoint_version"]
    if type(receipt) is not int or receipt < 1:
        raise ValueError("registry receipt must be a positive deployment ID")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid registry contract digest")
    if (
        type(version) is not str
        or not 1 <= len(version) <= 1024
        or version == "null"
        or re.search(r"[\x00-\x1f\x7f]", version) is not None
    ):
        raise ValueError("invalid registry checkpoint version")
    try:
        version.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid registry checkpoint version") from None


def _digest(document: dict[str, Any]) -> str:
    """Hash the complete canonical document, including its registry declarations."""
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


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
    # Schema ``pattern`` runs as ``re.search``: ``$`` also matches before a final
    # newline. ``_hardened_semantics`` re-validates a ``workload_step`` contract
    # with ``re.fullmatch`` patterns; the pre-hardening shape keeps ``re.search``
    # (AD-25), and the S4.11 receipt library must re-check receipt fields.
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    if next(validator.iter_errors(contract), None) is not None:
        raise ValueError("contract violates poc-test-v1 schema")


def _fullmatch_pattern(_validator, pattern, instance, _schema):
    """Apply a schema ``pattern`` to the whole string, as ECMA-262 ``$`` does."""
    if type(instance) is str and re.fullmatch(pattern, instance) is None:
        yield ValidationError("string does not fully match its schema pattern")


# Every poc-test-v1 pattern is anchored with ``^`` and ``$``, so a full match
# only adds the refusal of a trailing newline that ``re.search`` accepts.
_FullmatchValidator = validators.extend(
    Draft202012Validator, {"pattern": _fullmatch_pattern}
)


def _fullmatch_shape(contract: dict[str, Any]) -> None:
    """Refuse any hardened string that only matches before a final newline (N3)."""
    validator = _FullmatchValidator(json.loads(SCHEMA_PATH.read_text()))
    if next(validator.iter_errors(contract), None) is not None:
        raise ValueError("hardened contract strings must fully match the schema")


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
    if identity != "user.vilnacrmtest.com" or sender.split("@")[1] != identity:
        raise ValueError("SES identity/sender must match the TEST owned domain")


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


def _trusted_proxy_semantics(cidrs: list[str]) -> None:
    """Require canonical, explicit, non-overlapping networks without catchalls."""
    networks = []
    for cidr in cidrs:
        if "%" in cidr:
            raise ValueError("trusted proxy CIDRs must not contain scope IDs")
        try:
            network = ipaddress.ip_network(cidr, strict=True)
        except ValueError:
            raise ValueError("trusted proxy CIDRs must be canonical networks") from None
        if str(network) != cidr or network.prefixlen == 0:
            raise ValueError(
                "trusted proxy CIDRs must be explicit non-default networks"
            )
        if any(network.overlaps(previous) for previous in networks):
            raise ValueError("trusted proxy CIDRs must not overlap")
        networks.append(network)


def _workload_semantics(workload: dict[str, Any], registries: dict[str, Any]) -> None:
    """Bind workload mail, roles, releases and secrets to fixed declarations."""
    _mail_semantics(workload["external"]["mail"])
    _trusted_proxy_semantics(workload["runtime"]["trusted_proxy_cidrs"])
    central = workload["central"]
    roles = [
        central[key]
        for key in ("execution_role_arn", "task_role_arn", "publisher_role_arn")
    ]
    if len(set(roles)) != 3:
        raise ValueError("runtime and publisher roles must be distinct")
    release = workload["release"]
    _registry_release_fields(release)
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


def _capacity_integers(capacity: dict[str, Any]) -> list[Any]:
    """Return every D-16 count, target and cooldown of the capacity block."""
    web, worker = capacity["web"], capacity["worker"]
    return [
        *(capacity[service][key] for service in SCALED_SERVICES for key in BOUNDS),
        *web["target_tracking"].values(),
        *worker["backlog"].values(),
    ]


def _strict_integers(contract: dict[str, Any]) -> None:
    """Reject JSON numbers such as ``1.0`` where the contract means an integer."""
    scaling = contract["scaling"]
    references = contract["workload"]["secret_lifecycle"]["references"]
    values = [
        contract["workload_step"],
        contract["workload_operation"]["sequence"],
        *(entry["seq"] for entry in [*scaling["starts"], *scaling["stops"]]),
        *_capacity_integers(scaling["capacity"]),
        *(
            secret["rotation"]["schedule_days"]
            for secret in references.values()
            if type(secret["rotation"]) is dict
        ),
    ]
    if any(type(value) is not int for value in values):
        raise ValueError("hardened contract integers must be exact")


# The ECS services the scalable targets name (AD-10) and their capacity bounds.
SCALED_SERVICES = ("web", "worker")
BOUNDS = ("min_capacity", "max_capacity")
# D-16: a PROD minimum of 2 keeps one task per AZ.
PROD_MIN_CAPACITY = 2


def _capacity_semantics(capacity: dict[str, Any], environment: str) -> None:
    """Bind each service's bounds: ``1 <= min <= max``, PROD ``min >= 2`` (D-16).

    FR-11: a minimum below 1 or above the maximum raises. The PROD contract
    schema is S4.14's; this check takes the environment so it serves both.
    """
    for service in SCALED_SERVICES:
        minimum, maximum = (capacity[service][key] for key in BOUNDS)
        if minimum < 1:
            raise ValueError("scaling capacity minimum must be at least 1")
        if minimum > maximum:
            raise ValueError("scaling capacity minimum must not exceed its maximum")
        if environment == "prod" and minimum < PROD_MIN_CAPACITY:
            raise ValueError("PROD scaling capacity minimum must be at least 2")


def _scaling_semantics(scaling: dict[str, Any]) -> None:
    """Keep one-time actions append-only and consumed names bound to entries."""
    names = set()
    for kind in ("start", "stop"):
        sequence = [entry["seq"] for entry in scaling[kind + "s"]]
        if sequence != sorted(set(sequence)):
            raise ValueError("scaling entries must have strictly increasing seq")
        names.update(f"{kind}-{seq}" for seq in sequence)
    if not set(scaling["consumed"]) <= names:
        raise ValueError("consumed scaling names must name declared entries")


def _distinct_cmk_semantics(cmk: dict[str, Any]) -> None:
    """Refuse two D-4 keys (previous JWT key included) sharing an ARN or alias."""
    for field, label in (("arn", "ARNs"), ("alias", "aliases")):
        values = [key[field] for key in cmk.values()]
        if len(set(values)) != len(values):
            raise ValueError(f"central CMK {label} must be distinct")


def _central_semantics(workload: dict[str, Any]) -> None:
    """Bind secrets to reviewed central functions, distinct roles and the D-4 key.

    D-4: one runtime CMK encrypts every declared secret; the JWT and 2FA CMKs
    are separate keys. The optional previous JWT key (D-17) is a fourth key.
    No two keys share an ARN or an alias. S1.9 binds the DocumentDB log groups
    to the runtime CMK in the program.
    """
    central = workload["central"]
    roles = [value for key, value in central.items() if key.endswith("_role_arn")]
    if len(set(roles)) != len(roles):
        raise ValueError("central role ARNs must be distinct")
    _distinct_cmk_semantics(central["cmk"])
    functions = central["rotation_function_arns"]
    for secret in workload["secret_lifecycle"]["references"].values():
        if secret["kms_key_arn"] != central["cmk"]["runtime"]["arn"]:
            raise ValueError("declared secret must use the runtime CMK")
        rotation = secret["rotation"]
        if type(rotation) is dict and rotation["function_ref"] not in functions:
            raise ValueError("rotation function missing from central metadata")


def _hardened_semantics(contract: dict[str, Any]) -> None:
    """Check the seeded shape; it exists only with ``workload_step`` (AD-25)."""
    if "workload_step" not in contract:
        return
    _fullmatch_shape(contract)
    _strict_integers(contract)
    _scaling_semantics(contract["scaling"])
    _capacity_semantics(contract["scaling"]["capacity"], contract["environment"])
    _central_semantics(contract["workload"])


def _semantics(contract: dict[str, Any]) -> None:
    """Apply registry semantics and workload-only semantic bindings."""
    registries = contract["registries"]
    _registry_semantics(registries)
    if contract["phase"] == "workload":
        _workload_semantics(contract["workload"], registries)
        _hardened_semantics(contract)


def _validate_document(contract: dict[str, Any]) -> None:
    """Apply every local shape and semantic check to one contract document."""
    _shape(contract)
    _semantics(contract)


def _registry_transition(previous: dict[str, Any], contract: dict[str, Any]) -> None:
    """Bind first-workload publication to the actual supplied registry contract."""
    if previous["phase"] == "registry" and contract["phase"] == "workload":
        if contract["workload"]["release"]["registry_contract_digest"] != _digest(
            previous
        ):
            raise ValueError("release registry contract binding differs")


def _validate_transition(previous: dict[str, Any], contract: dict[str, Any]) -> None:
    """Keep one authenticated contract's immutable ownership and secret bindings."""
    if previous["phase"] == "workload" and contract["phase"] != "workload":
        raise ValueError("workload to registry downgrade forbidden")
    for field in (
        "account_id",
        "region",
        "environment",
        "backend",
        "registries",
        "mail_identity",
    ):
        if previous[field] != contract[field]:
            raise ValueError("stack or registry ownership changed")
    _registry_transition(previous, contract)
    if previous["phase"] == "workload":
        _secret_transition(previous, contract)
        _scaling_transition(previous, contract)


def _target_state(scaling: dict[str, Any]) -> tuple[Any, bool]:
    """Return what renders the scalable targets: capacity and the hold flag."""
    return scaling["capacity"], scaling.get("scheduled_scaling_suspended", False)


def _scaling_transition(previous: dict[str, Any], contract: dict[str, Any]) -> None:
    """Refuse a new stop entry in a plan that also changes the target (N, AD-10).

    Suspending scheduled scaling also blocks one-time actions, so the stop and
    the hold are two plans: a contract that appends a ``scaling.stops`` entry
    keeps the capacity and the ``scheduled_scaling_suspended`` flag unchanged.
    """
    if "workload_step" not in contract:
        return
    before, after = previous["scaling"], contract["scaling"]
    stops = {entry["seq"] for entry in before["stops"]}
    appended = any(entry["seq"] not in stops for entry in after["stops"])
    if appended and _target_state(before) != _target_state(after):
        raise ValueError("a stop plan must not change the scalable target")


def _secret_transition(previous: dict[str, Any], contract: dict[str, Any]) -> None:
    """Keep declared secrets immutable and never switch the generation model."""
    if ("workload_step" in previous) != ("workload_step" in contract):
        raise ValueError("secret generation model change requires a state migration")
    before = previous["workload"]["secret_lifecycle"]["references"]
    after = contract["workload"]["secret_lifecycle"]["references"]
    for purpose, secret in before.items():
        if after.get(purpose) != secret:
            raise ValueError(
                "generated secret rotation or replacement requires a separate contract"
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
    return _digest(contract)


def validate_registry_release_binding(
    contract: dict[str, Any],
    *,
    registry_contract: dict[str, Any],
    expected: RegistryReleaseBinding,
) -> None:
    """Compare a release to its separately authenticated original registry anchor.

    The caller must authenticate the App-issued service-poc-phase-v1 deployment,
    its original registry contract and versioned checkpoint before this call.
    For updates/rollback this is the release's original registry anchor, not the
    current workload checkpoint. Current state, publisher provenance, images and
    secret history require independent checks; this function grants no admission.
    """
    if type(expected) is not RegistryReleaseBinding:
        raise ValueError("typed registry reference required")
    reference = asdict(expected)
    _registry_release_fields(reference)
    _validate_document(registry_contract)
    _validate_document(contract)
    if registry_contract["phase"] != "registry" or contract["phase"] != "workload":
        raise ValueError("registry to workload reference required")
    _validate_transition(registry_contract, contract)
    release = contract["workload"]["release"]
    if any(release[key] != value for key, value in reference.items()):
        raise ValueError("release registry receipt binding differs")


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
