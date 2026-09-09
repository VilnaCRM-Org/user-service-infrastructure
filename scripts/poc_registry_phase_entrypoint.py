"""Internal registry graph projection; no config or CLI may select this phase."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

import poc_contract
from poc_phase_admission import SourceAdmission

_REGISTRIES = {
    "web": {
        "logical_name": "user-service-web-repository",
        "name": "user-service-test-web",
    },
    "worker": {
        "logical_name": "user-service-worker-repository",
        "name": "user-service-test-worker",
    },
}


@dataclass(frozen=True)
class RegistryPhaseProjection:
    """Internal data projection, not deployment authority or phase permission."""

    registries: dict[str, dict[str, str]]


def _require(condition: bool, message: str) -> None:
    """Reject unsuitable source facts before registering Pulumi resources."""
    if not condition:
        raise ValueError(message)


def _stable_registries(registries: object) -> dict[str, dict[str, str]]:
    """Copy only the fixed two-repository identity into an internal graph input."""
    _require(type(registries) is dict, "Registry contract differs")
    projected: dict[str, dict[str, str]] = {}
    for kind, expected in _REGISTRIES.items():
        candidate = registries.get(kind)
        _require(type(candidate) is dict, "Registry contract differs")
        _require(
            {key: candidate.get(key) for key in expected} == expected,
            "Registry ownership differs",
        )
        projected[kind] = dict(expected)
    return projected


def project_registry_phase(
    source: SourceAdmission, contract: Mapping[str, object]
) -> RegistryPhaseProjection:
    """Bind a registry-only graph to authenticated source facts, never config."""
    _require(type(source) is SourceAdmission, "Typed source facts required")
    _require(type(contract) is dict, "Registry contract must be an object")
    document: dict[str, Any] = contract
    poc_contract._shape(document)
    poc_contract._semantics(document)
    _require(document["phase"] == "registry", "Registry phase evidence required")
    digest = hashlib.sha256(
        json.dumps(
            document, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    _require(digest == source.contract_sha256, "Source contract binding differs")
    registries = document["registries"]
    for candidate in registries.values():
        _require(candidate.get("owner") == "service", "Registry owner differs")
    return RegistryPhaseProjection(registries=_stable_registries(registries))


def run_registry_phase(projection: RegistryPhaseProjection):
    """Register the internal two-repository graph after a trusted caller projects it."""
    _require(
        type(projection) is RegistryPhaseProjection, "Registry projection required"
    )
    from app.registry_phase import RegistryPhaseStack

    return RegistryPhaseStack(registries=_stable_registries(projection.registries))
