#!/usr/bin/env python3
"""Authenticate same-run PoC source facts, without admitting a phase or AWS.

Run the installed main copy with python3 -I. Artifact ID and digests must come
from trusted upload outputs, never dispatch/PR inputs. No archive is extracted.
Fresh review and authenticated prior-state admission remain separate requirements.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import selectors  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402  # nosec B404
import time  # noqa: E402
import zipfile  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from typing import Any, Callable, Mapping  # noqa: E402

import poc_contract  # noqa: E402
import poc_phase_admission as admission  # noqa: E402
import pulumi_command_preflight as preflight  # noqa: E402

WORKFLOW = ".github/workflows/self-deploy.yml"
MEMBER = "source.json"
MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = admission.MAX_EVIDENCE_BYTES
REPOSITORY = admission.REPOSITORY
API = f"repos/{REPOSITORY}"


def _require(condition: object) -> None:
    """Use one fixed diagnostic that cannot disclose response content."""
    if not condition:
        raise ValueError("Invalid source artifact")


def _matches(actual: Any, expected: Mapping[str, object]) -> None:
    """Compare API field values and their types, rejecting boolean IDs."""
    _require(type(actual) is dict)
    for key, value in expected.items():
        _require(type(actual.get(key)) is type(value) and actual[key] == value)


def _pattern(value: object, pattern: str) -> None:
    """Close path components and identifiers before API access."""
    _require(type(value) is str and re.fullmatch(pattern, value) is not None)


def _context(environment: Mapping[str, str]) -> tuple[str, str]:
    """Read trusted current-job context, not a caller-supplied producer object."""
    _matches(
        dict(environment),
        {
            "GITHUB_EVENT_NAME": "repository_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(admission.REPOSITORY_ID),
            "GITHUB_REPOSITORY_OWNER_ID": str(admission.OWNER_ID),
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW_REF": f"{REPOSITORY}/{WORKFLOW}@refs/heads/main",
        },
    )
    run_id, sha = (
        environment.get("GITHUB_RUN_ID", ""),
        environment.get("GITHUB_SHA", ""),
    )
    _pattern(run_id, r"[1-9][0-9]*")
    _pattern(sha, r"[0-9a-f]{40}")
    _require(environment.get("GITHUB_WORKFLOW_SHA") == sha)
    return run_id, sha


def _producer(gh: Callable[..., Any], run_id: str, sha: str) -> None:
    """Authenticate the actual service main workflow run and both repositories."""
    run = gh(f"{API}/actions/runs/{run_id}")
    _matches(
        run,
        {
            "id": int(run_id),
            "run_attempt": 1,
            "event": "repository_dispatch",
            "path": WORKFLOW,
            "head_branch": "main",
            "head_sha": sha,
            "status": "in_progress",
            "conclusion": None,
        },
    )
    for key in ("repository", "head_repository"):
        repository = run.get(key)
        _matches(repository, {"id": admission.REPOSITORY_ID, "full_name": REPOSITORY})
        _matches(repository.get("owner"), {"id": admission.OWNER_ID})


def _timestamp(value: Any) -> datetime:
    """Reject missing or timezone-free expiry evidence."""
    _require(type(value) is str)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None)
    return parsed


def _artifact(gh, artifact_id: str, digest: str, run_id: str, sha: str) -> None:
    """Bind immutable upload metadata and expiry to this exact run."""
    artifact = gh(f"{API}/actions/artifacts/{artifact_id}")
    _matches(
        artifact,
        {
            "id": int(artifact_id),
            "name": f"poc-phase-source-{run_id}-1",
            "expired": False,
            "digest": f"sha256:{digest}",
        },
    )
    _matches(
        artifact.get("workflow_run"),
        {
            "id": int(run_id),
            "repository_id": admission.REPOSITORY_ID,
            "head_repository_id": admission.REPOSITORY_ID,
            "head_branch": "main",
            "head_sha": sha,
        },
    )
    size = artifact.get("size_in_bytes")
    _require(type(size) is int and 0 < size <= MAX_ZIP_BYTES)
    _require(
        _timestamp(artifact.get("created_at"))
        <= datetime.now(timezone.utc)
        < _timestamp(artifact.get("expires_at"))
    )


def _download_zip(artifact_id: str) -> bytes:
    """Bound authenticated gh redirects, memory, runtime and stderr exposure."""
    process = subprocess.Popen(
        ["gh", "api", f"{API}/actions/artifacts/{artifact_id}/zip"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )  # nosec B603 B607
    data = bytearray()
    try:
        if process.stdout is None:
            raise ValueError("Invalid source artifact")
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 120
            while True:
                _require(time.monotonic() < deadline)
                if not selector.select(timeout=1):
                    continue
                chunk = os.read(
                    process.stdout.fileno(), min(65536, MAX_ZIP_BYTES + 1 - len(data))
                )
                if not chunk:
                    break
                data.extend(chunk)
                _require(len(data) <= MAX_ZIP_BYTES)
        _require(process.wait(timeout=10) == 0)
        return bytes(data)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        if process.stdout is not None:
            process.stdout.close()


def _payload(raw: bytes) -> bytes:
    """Read only one regular bounded protocol member; never extract paths."""
    _require(0 < len(raw) <= MAX_ZIP_BYTES)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        _require(len(entries) == 1)
        member = entries[0]
        _require(
            member.filename == member.orig_filename == MEMBER and not member.is_dir()
        )
        _require(not member.flag_bits & 1)
        _require(stat.S_IFMT(member.external_attr >> 16) in (0, stat.S_IFREG))
        _require(0 < member.file_size <= MAX_SOURCE_BYTES)
        with archive.open(member) as stream:
            payload = stream.read(MAX_SOURCE_BYTES + 1)
        _require(len(payload) == member.file_size and len(payload) <= MAX_SOURCE_BYTES)
    return payload


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous JSON objects before interpreting source facts."""
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _fields(value: Any, patterns: Mapping[str, str]) -> None:
    """Require one closed object with bounded string fields."""
    _require(type(value) is dict and set(value) == set(patterns))
    for key, pattern in patterns.items():
        _pattern(value[key], pattern)


def _decode(payload: bytes) -> dict[str, Any]:
    """Accept only PreparedSource facts, excluding phase/prior/approval fields."""
    value = json.loads(payload, object_pairs_hook=_pairs)
    _require(
        type(value) is dict and set(value) == {"kind", "request", "review", "source"}
    )
    _require(value["kind"] == "poc-phase-source/v1")
    _fields(
        value["request"],
        {
            "pull_request_number": r"[1-9][0-9]*",
            "head_sha": r"[0-9a-f]{40}",
            "comment_id": r"[1-9][0-9]*",
            "source_run_id": r"[1-9][0-9]*",
            "command": r"plan|up",
            "target_environment": r"test|prod",
        },
    )
    _fields(
        value["review"],
        {
            "head_sha": r"[0-9a-f]{40}",
            "base_sha": r"[0-9a-f]{40}",
            "review_id": r"[A-Za-z0-9_=-]{1,256}",
            "reviewer_id": r"[A-Za-z0-9_=-]{1,256}",
            "reviewer_login": r"[A-Za-z0-9-]{1,39}",
            "review_protection_sha256": r"[0-9a-f]{64}",
        },
    )
    _fields(
        value["source"],
        {
            "contract_sha256": r"[0-9a-f]{64}",
            "head_sha": r"[0-9a-f]{40}",
            "base_sha": r"[0-9a-f]{40}",
            "blob_sha": r"[0-9a-f]{40}",
            "path": re.escape(admission.CONTRACT_PATH),
            "schema_sha256": r"[0-9a-f]{64}",
            "validator_sha256": r"[0-9a-f]{64}",
        },
    )
    _require(value["request"]["head_sha"] == value["source"]["head_sha"])
    for key in ("head_sha", "base_sha"):
        _require(value["review"][key] == value["source"][key])
    for key, path in (
        ("schema_sha256", poc_contract.SCHEMA_PATH),
        ("validator_sha256", Path(poc_contract.__file__)),
    ):
        installed = admission._read_bounded_regular_file(
            path, poc_contract.MAX_BYTES, "Installed source validator"
        )
        _require(hashlib.sha256(installed).hexdigest() == value["source"][key])
    return value


def load_verified_source(
    *, artifact_id: str, archive_sha256: str, source_sha256: str, gh=None, download=None
) -> dict[str, Any]:
    """Authenticate source transport; do not infer current review or prior state."""
    _pattern(artifact_id, r"[1-9][0-9]*")
    _pattern(archive_sha256, r"[0-9a-f]{64}")
    _pattern(source_sha256, r"[0-9a-f]{64}")
    gh, download = gh or preflight.gh, download or _download_zip
    run_id, sha = _context(os.environ)
    _producer(gh, run_id, sha)
    _artifact(gh, artifact_id, archive_sha256, run_id, sha)
    raw = download(artifact_id)
    _require(hashlib.sha256(raw).hexdigest() == archive_sha256)
    payload = _payload(raw)
    _require(hashlib.sha256(payload).hexdigest() == source_sha256)
    source = _decode(payload)
    _artifact(gh, artifact_id, archive_sha256, run_id, sha)
    _producer(gh, run_id, sha)
    return source


def main(argv=None) -> int:
    """Emit only verified public facts or a fixed redacted failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("artifact-id", "archive-sha256", "source-sha256"):
        parser.add_argument(f"--{field}", required=True)
    args = parser.parse_args(argv)
    try:
        source = load_verified_source(**vars(args))
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        EOFError,
        zipfile.BadZipFile,
        NotImplementedError,
        RuntimeError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print("INVALID: source artifact verification failed", file=sys.stderr)
        return 1
    print(json.dumps(source, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
