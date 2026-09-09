#!/usr/bin/env python3
"""Validate one fixed PoC contract source artifact without authorizing a phase.

This source-only core binds bytes to trusted adapter metadata. It deliberately
does not read AWS state, select an initial transition, or grant a dispatcher
permission. A future trusted workflow must authenticate the GitHub metadata
before it calls this helper.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import poc_contract

CONTRACT_PATH = "specs/poc/poc-test.json"
REPOSITORY = "VilnaCRM-Org/user-service-infrastructure"
REPOSITORY_ID = 911736693
OWNER_ID = 114362548
MAX_EVIDENCE_BYTES = 16384
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SHA1_PATTERN = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class SourceAdmission:
    """Bound source facts for a later trusted adapter; this is not authority."""

    contract_sha256: str
    head_sha: str
    base_sha: str
    path: str
    blob_sha: str
    schema_sha256: str
    validator_sha256: str


def _require(condition: bool, message: str) -> None:
    """Fail closed without including untrusted values in the diagnostic."""
    if not condition:
        raise ValueError(message)


def _object(value: object, label: str) -> dict[str, Any]:
    """Require an ordinary JSON object before selecting any fields."""
    _require(type(value) is dict, f"{label} must be an object")
    return value


def _sha256(value: bytes) -> str:
    """Return the canonical SHA-256 representation used by source metadata."""
    return hashlib.sha256(value).hexdigest()


def _git_blob_sha(value: bytes) -> str:
    """Bind GitHub's current SHA-1 blob identity to the exact raw contract bytes."""
    prefix = f"blob {len(value)}\0".encode()
    return hashlib.sha1(prefix + value, usedforsecurity=False).hexdigest()


def _read_bounded_regular_file(path: Path, limit: int, label: str) -> bytes:
    """Read a regular non-symlink file only after its size is bounded."""
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode), f"{label} must be a regular file")
    _require(metadata.st_size <= limit, f"{label} exceeds size limit")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    _require(len(value) <= limit, f"{label} exceeds size limit")
    return value


def _read_root_file(root: Path, relative: str, limit: int, label: str) -> bytes:
    """Read a fixed root-relative file without trusting symlinked PR directories."""
    current = root
    for index, part in enumerate(Path(relative).parts):
        current /= part
        metadata = current.lstat()
        _require(not stat.S_ISLNK(metadata.st_mode), f"{label} symlink rejected")
        if index < len(Path(relative).parts) - 1:
            _require(
                stat.S_ISDIR(metadata.st_mode), f"{label} parent is not a directory"
            )
    return _read_bounded_regular_file(current, limit, label)


def _fixed_metadata(value: Mapping[str, object]) -> dict[str, Any]:
    """Reject caller-selected paths, phases, flags and unclosed metadata."""
    metadata = _object(value, "Source metadata")
    expected = {
        "repository",
        "repository_id",
        "owner_id",
        "pull_request_number",
        "head_sha",
        "base_sha",
        "path",
        "blob_sha",
        "raw_sha256",
        "schema_sha256",
        "validator_sha256",
    }
    _require(set(metadata) == expected, "Source metadata fields differ")
    _require(metadata["repository"] == REPOSITORY, "Foreign source repository")
    _require(metadata["repository_id"] == REPOSITORY_ID, "Foreign source repository")
    _require(metadata["owner_id"] == OWNER_ID, "Foreign source owner")
    _require(
        type(metadata["pull_request_number"]) is int
        and metadata["pull_request_number"] > 0,
        "Invalid pull request number",
    )
    _require(metadata["path"] == CONTRACT_PATH, "Contract path differs")
    for field, pattern in (
        ("head_sha", SHA1_PATTERN),
        ("base_sha", SHA1_PATTERN),
        ("blob_sha", SHA1_PATTERN),
        ("raw_sha256", SHA256_PATTERN),
        ("schema_sha256", SHA256_PATTERN),
        ("validator_sha256", SHA256_PATTERN),
    ):
        _require(
            type(metadata[field]) is str and pattern.fullmatch(metadata[field]),
            f"Invalid {field}",
        )
    return metadata


def _decode_contract(raw: bytes) -> dict[str, Any]:
    """Reuse the strict proposed validator's bounded duplicate-key decoder."""
    _require(len(raw) <= poc_contract.MAX_BYTES, "Contract exceeds size limit")
    try:
        contract = json.loads(
            raw,
            object_pairs_hook=poc_contract._pairs,
            parse_constant=poc_contract._reject_nonfinite,
        )
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid contract JSON") from exc
    return _object(contract, "Contract")


def prepare_source(
    metadata: Mapping[str, object],
    contract_bytes: bytes,
    *,
    schema_bytes: bytes,
    validator_bytes: bytes,
) -> SourceAdmission:
    """Verify fixed-path source bytes; callers still need external authentication."""
    source = _fixed_metadata(metadata)
    _require(_sha256(contract_bytes) == source["raw_sha256"], "Contract hash differs")
    _require(
        _git_blob_sha(contract_bytes) == source["blob_sha"], "Contract blob differs"
    )
    _require(_sha256(schema_bytes) == source["schema_sha256"], "Schema hash differs")
    _require(
        _sha256(validator_bytes) == source["validator_sha256"], "Validator hash differs"
    )
    _require(
        schema_bytes
        == _read_bounded_regular_file(
            poc_contract.SCHEMA_PATH,
            poc_contract.MAX_BYTES,
            "Installed schema",
        ),
        "Source schema differs from installed validator",
    )
    _require(
        validator_bytes
        == _read_bounded_regular_file(
            Path(poc_contract.__file__), poc_contract.MAX_BYTES, "Installed validator"
        ),
        "Source validator differs from installed validator",
    )
    contract = _decode_contract(contract_bytes)
    poc_contract._shape(contract)
    poc_contract._semantics(contract)
    return SourceAdmission(
        contract_sha256=_sha256(
            json.dumps(
                contract, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ),
        head_sha=source["head_sha"],
        base_sha=source["base_sha"],
        path=source["path"],
        blob_sha=source["blob_sha"],
        schema_sha256=source["schema_sha256"],
        validator_sha256=source["validator_sha256"],
    )


def _read_json(path: Path) -> dict[str, Any]:
    """Read bounded duplicate-key-rejecting metadata without printing it."""
    raw = _read_bounded_regular_file(path, MAX_EVIDENCE_BYTES, "Source metadata")
    return _decode_contract(raw)


def main(argv: list[str] | None = None) -> int:
    """Validate a fixed source artifact and emit only redacted binding fields."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        root = arguments.source_root.resolve(strict=True)
        admission = prepare_source(
            _read_json(arguments.metadata),
            _read_root_file(root, CONTRACT_PATH, poc_contract.MAX_BYTES, "Contract"),
            schema_bytes=_read_root_file(
                root,
                "schemas/poc-test-v1.schema.json",
                poc_contract.MAX_BYTES,
                "Source schema",
            ),
            validator_bytes=_read_root_file(
                root,
                "scripts/poc_contract.py",
                poc_contract.MAX_BYTES,
                "Source validator",
            ),
        )
    except (OSError, ValueError):
        print("INVALID: source artifact admission failed", file=sys.stderr)
        return 1
    print(json.dumps(asdict(admission), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
