#!/usr/bin/env python3
"""Prepare fixed PoC source facts from trusted GitHub reads only.

This helper does not issue AWS credentials, choose a deployment phase, inspect
backend state, or execute PR code. The caller must run it from installed main
with a read-only GitHub token and the existing six-field command intake.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import base64  # noqa: E402
import binascii  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402  # nosec B404
from dataclasses import asdict, dataclass  # noqa: E402
from typing import Any, Callable, Mapping  # noqa: E402

import poc_contract  # noqa: E402
import poc_phase_admission as admission  # noqa: E402
import pulumi_command_preflight as preflight  # noqa: E402
from reviewed_source_admission import verify_reviewed_source  # noqa: E402

GitHubRead = Callable[..., Any]


@dataclass(frozen=True)
class PreparedSource:
    """Serialized source facts only; it contains no phase or accepted prior."""

    kind: str
    request: dict[str, str]
    review: dict[str, str]
    source: admission.SourceAdmission


def _require(condition: bool, message: str) -> None:
    """Fail closed without rendering GitHub or token-bearing response content."""
    if not condition:
        raise ValueError(message)


def _object(value: object, label: str) -> dict[str, Any]:
    """Require a JSON object before selecting API response fields."""
    _require(type(value) is dict, f"{label} must be an object")
    return value


def _request(request: Mapping[str, object]) -> dict[str, str]:
    """Preserve the existing immutable six-field intake shape exactly."""
    expected = {
        "pull_request_number",
        "head_sha",
        "comment_id",
        "source_run_id",
        "command",
        "target_environment",
    }
    _require(set(request) == expected, "Request fields differ")
    checked = {key: request[key] for key in expected}
    preflight.require(
        all(type(value) is str for value in checked.values()), "Invalid request"
    )
    return checked


def _validated_evidence(
    request: dict[str, str],
    *,
    intake: dict[str, Any],
    collect_evidence: Callable[..., dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Reapply service request/authentication checks against current GitHub facts."""
    evidence = collect_evidence(request, intake=intake)
    validated = preflight.validate_request(
        request, evidence, governance=False, service=True
    )
    _require(validated["head_sha"] == request["head_sha"], "PR head moved")
    _require(type(validated["base_sha"]) is str, "Invalid PR base")
    return evidence, validated


def _refreshed_intake(
    request: dict[str, str], intake: dict[str, Any], gh: GitHubRead
) -> dict[str, Any]:
    """Re-read the original comment without replacing its authenticated origin."""
    origin = _object(intake, "Intake")
    original = _object(origin.get("comment"), "Intake comment")
    fresh = _object(
        gh(
            f"repos/{origin['repository']}/issues/comments/"
            f"{request['comment_id']}"
        ),
        "Current comment",
    )
    for field in ("id", "issue_url", "created_at", "body"):
        _require(fresh.get(field) == original.get(field), "Comment evidence changed")
    for field in ("id", "login"):
        _require(
            _object(fresh.get("user"), "Current commenter").get(field)
            == _object(original.get("user"), "Intake commenter").get(field),
            "Comment evidence changed",
        )
    refreshed = {**origin, "comment": fresh}
    preflight.authenticate_intake(request, refreshed)
    return refreshed


def _content_bytes(value: object) -> tuple[str, bytes]:
    """Decode one bounded fixed-path GitHub contents response without URLs."""
    content = _object(value, "Contract content")
    expected = {"type", "path", "sha", "size", "encoding", "content"}
    _require(expected <= set(content), "Contract content fields missing")
    _require(content["type"] == "file", "Contract content is not a file")
    _require(content["path"] == admission.CONTRACT_PATH, "Contract path differs")
    _require(content["encoding"] == "base64", "Contract content encoding differs")
    _require(
        type(content["sha"]) is str
        and admission.SHA1_PATTERN.fullmatch(content["sha"]),
        "Contract blob differs",
    )
    _require(
        type(content["size"]) is int and 0 <= content["size"] <= poc_contract.MAX_BYTES,
        "Contract size differs",
    )
    _require(type(content["content"]) is str, "Contract bytes missing")
    encoded = content["content"].replace("\n", "")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Contract content is not base64") from exc
    _require(len(raw) == content["size"], "Contract content size differs")
    _require(len(raw) <= poc_contract.MAX_BYTES, "Contract exceeds size limit")
    _require(admission._git_blob_sha(raw) == content["sha"], "Contract blob differs")
    return content["sha"], raw


def _repository_identity(value: object) -> dict[str, int | str]:
    """Derive the fixed repository and owner IDs from one trusted API response."""
    repository = _object(value, "Repository")
    owner = _object(repository.get("owner"), "Repository owner")
    _require(repository.get("full_name") == admission.REPOSITORY, "Foreign repository")
    _require(repository.get("id") == admission.REPOSITORY_ID, "Foreign repository")
    _require(owner.get("id") == admission.OWNER_ID, "Foreign repository owner")
    return {
        "repository": repository["full_name"],
        "repository_id": repository["id"],
        "owner_id": owner["id"],
    }


def prepare_authenticated_source(
    request: Mapping[str, object],
    *,
    intake: dict[str, Any],
    gh: GitHubRead,
    collect_evidence: Callable[..., dict[str, Any]],
) -> PreparedSource:
    """Fetch one fixed PR blob after, then recheck, source and review identity."""
    intake_request = _request(request)
    preflight.authenticate_intake(intake_request, intake)
    before, validated = _validated_evidence(
        intake_request, intake=intake, collect_evidence=collect_evidence
    )
    repository = before["repository"]
    _require(repository == admission.REPOSITORY, "Foreign source repository")
    identity = _repository_identity(gh(f"repos/{repository}"))
    review_before = verify_reviewed_source(
        repository,
        intake_request["pull_request_number"],
        intake_request["head_sha"],
        validated["base_sha"],
        gh=gh,
    )
    blob_sha, contract_bytes = _content_bytes(
        gh(
            f"repos/{repository}/contents/{admission.CONTRACT_PATH}"
            f"?ref={intake_request['head_sha']}"
        )
    )
    refreshed_intake = _refreshed_intake(intake_request, intake, gh)
    after, revalidated = _validated_evidence(
        intake_request, intake=refreshed_intake, collect_evidence=collect_evidence
    )
    _require(after["repository"] == repository, "Source repository changed")
    _require(revalidated["base_sha"] == validated["base_sha"], "PR base moved")
    review_after = verify_reviewed_source(
        repository,
        intake_request["pull_request_number"],
        intake_request["head_sha"],
        revalidated["base_sha"],
        gh=gh,
    )
    _require(review_after == review_before, "Review evidence changed")
    schema_bytes = admission._read_bounded_regular_file(
        poc_contract.SCHEMA_PATH, poc_contract.MAX_BYTES, "Installed schema"
    )
    validator_bytes = admission._read_bounded_regular_file(
        Path(poc_contract.__file__), poc_contract.MAX_BYTES, "Installed validator"
    )
    source = admission.prepare_source(
        {
            "repository": identity["repository"],
            "repository_id": identity["repository_id"],
            "owner_id": identity["owner_id"],
            "pull_request_number": int(intake_request["pull_request_number"]),
            "head_sha": intake_request["head_sha"],
            "base_sha": revalidated["base_sha"],
            "path": admission.CONTRACT_PATH,
            "blob_sha": blob_sha,
            "raw_sha256": admission._sha256(contract_bytes),
            "schema_sha256": admission._sha256(schema_bytes),
            "validator_sha256": admission._sha256(validator_bytes),
        },
        contract_bytes,
        schema_bytes=schema_bytes,
        validator_bytes=validator_bytes,
    )
    return PreparedSource(
        kind="poc-phase-source/v1",
        request=intake_request,
        review=review_after,
        source=source,
    )


def main(argv: list[str] | None = None) -> int:
    """Emit bounded source facts after trusted GitHub reads; never authorize work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        request = preflight.read_request()
        intake = preflight.collect_intake_evidence(request)
        result = prepare_authenticated_source(
            request,
            intake=intake,
            gh=preflight.gh,
            collect_evidence=preflight.collect_evidence,
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("INVALID: trusted source preparation failed", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "kind": result.kind,
                "request": result.request,
                "review": result.review,
                "source": asdict(result.source),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
