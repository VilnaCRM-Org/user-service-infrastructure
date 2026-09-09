"""Tests for source-only PoC phase-admission bindings."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from poc_phase_admission import (
    CONTRACT_PATH,
    OWNER_ID,
    REPOSITORY,
    REPOSITORY_ID,
    _git_blob_sha,
    _sha256,
    prepare_source,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests/fixtures/poc-contract/registry.synthetic.json"
SCHEMA = PROJECT_ROOT / "schemas/poc-test-v1.schema.json"
VALIDATOR = PROJECT_ROOT / "scripts/poc_contract.py"
SCRIPT = PROJECT_ROOT / "scripts/poc_phase_admission.py"


def _source_artifact(*, raw: bytes | None = None) -> tuple[dict[str, object], bytes]:
    """Return internally consistent synthetic trusted-adapter inputs."""
    contract = FIXTURE.read_bytes() if raw is None else raw
    return (
        {
            "repository": REPOSITORY,
            "repository_id": REPOSITORY_ID,
            "owner_id": OWNER_ID,
            "pull_request_number": 19,
            "head_sha": "2" * 40,
            "base_sha": "1" * 40,
            "path": CONTRACT_PATH,
            "blob_sha": _git_blob_sha(contract),
            "raw_sha256": _sha256(contract),
            "schema_sha256": _sha256(SCHEMA.read_bytes()),
            "validator_sha256": _sha256(VALIDATOR.read_bytes()),
        },
        contract,
    )


def _prepare(metadata: dict[str, object], contract: bytes):
    """Call the source-only core with this checkout's installed files."""
    return prepare_source(
        metadata,
        contract,
        schema_bytes=SCHEMA.read_bytes(),
        validator_bytes=VALIDATOR.read_bytes(),
    )


def test_prepare_source_binds_fixed_path_bytes_and_external_pr_sha() -> None:
    """Return only fixed source facts after all content bindings validate."""
    metadata, contract = _source_artifact()

    result = _prepare(metadata, contract)

    assert result.path == CONTRACT_PATH
    assert result.head_sha == "2" * 40
    assert result.base_sha == "1" * 40
    assert result.contract_sha256 == _sha256(
        json.dumps(
            json.loads(contract), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("path", "contracts/selected-by-user.json"),
        ("repository", "VilnaCRM-Org/foreign"),
        ("repository_id", 1),
        ("owner_id", 1),
        ("pull_request_number", 0),
        ("head_sha", "main"),
        ("base_sha", "main"),
        ("blob_sha", "0" * 40),
        ("raw_sha256", "0" * 64),
        ("schema_sha256", "0" * 64),
        ("validator_sha256", "0" * 64),
    ],
)
def test_prepare_source_rejects_untrusted_or_mismatched_metadata(
    field: str, replacement: object
) -> None:
    """Reject every fixed source identity mutation before contract admission."""
    metadata, contract = _source_artifact()
    metadata[field] = replacement

    with pytest.raises(ValueError):
        _prepare(metadata, contract)


@pytest.mark.parametrize("forbidden", ["phase", "initial_registry", "approved"])
def test_prepare_source_rejects_caller_authorization_flags(forbidden: str) -> None:
    """No source metadata flag can select a phase or establish authority."""
    metadata, contract = _source_artifact()
    metadata[forbidden] = True

    with pytest.raises(ValueError, match="fields differ"):
        _prepare(metadata, contract)


def test_prepare_source_rejects_contract_source_mismatch() -> None:
    """Desired contract source fields remain fixed service identities only."""
    contract = json.loads(FIXTURE.read_text())
    contract["source"]["repository"] = "VilnaCRM-Org/foreign"
    raw = json.dumps(contract, separators=(",", ":")).encode()
    metadata, raw = _source_artifact(raw=raw)

    with pytest.raises(ValueError, match="schema"):
        _prepare(metadata, raw)


@pytest.mark.parametrize("source", ["schema", "validator"])
def test_prepare_source_rejects_modified_pr_validation_code(source: str) -> None:
    """A matching PR hash cannot replace the installed contract interpretation."""
    metadata, contract = _source_artifact()
    schema = SCHEMA.read_bytes()
    validator = VALIDATOR.read_bytes()
    if source == "schema":
        schema += b" "
        metadata["schema_sha256"] = _sha256(schema)
    else:
        validator += b" "
        metadata["validator_sha256"] = _sha256(validator)

    with pytest.raises(ValueError, match="differs from installed validator"):
        prepare_source(
            metadata, contract, schema_bytes=schema, validator_bytes=validator
        )


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b"[]", b"{", b'{"x":NaN}'])
def test_prepare_source_rejects_malformed_contract_before_output(raw: bytes) -> None:
    """The core shares the validator's strict duplicate-key parser."""
    metadata, raw = _source_artifact(raw=raw)

    with pytest.raises(ValueError):
        _prepare(metadata, raw)


def test_cli_accepts_real_external_git_head_without_contract_self_hash(
    tmp_path: Path,
) -> None:
    """A contract committed at an ordinary Git head needs no impossible fixed point."""
    root = tmp_path / "source"
    (root / "specs/poc").mkdir(parents=True)
    (root / "schemas").mkdir()
    (root / "scripts").mkdir()
    shutil.copy(FIXTURE, root / CONTRACT_PATH)
    shutil.copy(SCHEMA, root / "schemas/poc-test-v1.schema.json")
    shutil.copy(VALIDATOR, root / "scripts/poc_contract.py")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "contract",
        ],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    metadata, _ = _source_artifact()
    metadata["head_sha"] = head
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(root),
            "--metadata",
            str(metadata_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["head_sha"] == head


def test_cli_rejects_symlinked_pr_schema(tmp_path: Path) -> None:
    """A matching target file cannot be reached through a PR-controlled symlink."""
    root = tmp_path / "source"
    (root / "specs/poc").mkdir(parents=True)
    (root / "schemas").mkdir()
    (root / "scripts").mkdir()
    shutil.copy(FIXTURE, root / CONTRACT_PATH)
    target = tmp_path / "schema.json"
    shutil.copy(SCHEMA, target)
    (root / "schemas/poc-test-v1.schema.json").symlink_to(target)
    shutil.copy(VALIDATOR, root / "scripts/poc_contract.py")
    metadata, _ = _source_artifact()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(root),
            "--metadata",
            str(metadata_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1


def test_cli_reads_only_fixed_contract_path_and_redacts_bad_input(
    tmp_path: Path,
) -> None:
    """The CLI cannot choose a contract file and never echoes hostile metadata."""
    root = tmp_path / "source"
    (root / "specs/poc").mkdir(parents=True)
    (root / "schemas").mkdir()
    (root / "scripts").mkdir()
    shutil.copy(FIXTURE, root / CONTRACT_PATH)
    shutil.copy(SCHEMA, root / "schemas/poc-test-v1.schema.json")
    shutil.copy(VALIDATOR, root / "scripts/poc_contract.py")
    metadata, _ = _source_artifact()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))

    good = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(root),
            "--metadata",
            str(metadata_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert good.returncode == 0
    assert json.loads(good.stdout)["path"] == CONTRACT_PATH

    metadata["path"] = "secret/DO_NOT_ECHO.json"
    metadata_path.write_text(json.dumps(metadata))
    bad = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(root),
            "--metadata",
            str(metadata_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 1
    assert "DO_NOT_ECHO" not in bad.stdout + bad.stderr
