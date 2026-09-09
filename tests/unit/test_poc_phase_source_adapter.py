"""Tests for trusted-GitHub-only PoC source preparation."""

from __future__ import annotations

import base64
import copy
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

adapter = importlib.import_module("poc_phase_source_adapter")
admission = importlib.import_module("poc_phase_admission")
preflight = importlib.import_module("pulumi_command_preflight")

HEAD = "a" * 40
BASE = "b" * 40
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/poc-contract/registry.synthetic.json"
)


def request() -> dict[str, str]:
    """Return the installed six-field intake contract, with no phase controls."""
    return {
        "pull_request_number": "19",
        "head_sha": HEAD,
        "comment_id": "12",
        "source_run_id": "13",
        "command": "plan",
        "target_environment": "test",
    }


def intake() -> dict[str, Any]:
    """Build authenticated intake evidence accepted by the existing preflight."""
    value = request()
    created = "2026-09-09T00:00:00Z"
    repository = admission.REPOSITORY
    return {
        "repository": repository,
        "api_url": "https://api.github.com",
        "artifact": copy.deepcopy(value),
        "pr": {
            "state": "open",
            "merged": False,
            "head": {"sha": HEAD, "repo": {"full_name": repository}},
            "base": {
                "sha": BASE,
                "ref": "main",
                "repo": {"full_name": repository},
            },
        },
        "comment": {
            "id": 12,
            "issue_url": f"https://api.github.com/repos/{repository}/issues/19",
            "created_at": created,
            "updated_at": created,
            "user": {"id": 20, "login": "requester"},
            "body": "/pulumi test plan",
        },
        "run": {
            "id": 13,
            "event": "issue_comment",
            "path": preflight.INTAKE_PATH,
            "head_repository": {"full_name": repository},
            "run_attempt": 1,
            "actor": {"id": 20},
            "created_at": created,
        },
    }


def collect(value, *, intake):
    """Return fresh service preflight evidence without exposing a phase selector."""
    return {
        **intake,
        "now": datetime(2026, 9, 9, 0, 1, tzinfo=timezone.utc),
        "permission": "write",
        "scope_base_sha": BASE,
        "files": ["README.md"],
    }


def review_response(*, state: str = "APPROVED", head: str = HEAD) -> dict[str, Any]:
    """Return one complete current-head independent-review GraphQL response."""
    repository = admission.REPOSITORY
    return {
        "data": {
            "repository": {
                "nameWithOwner": repository,
                "pullRequest": {
                    "number": 19,
                    "state": "OPEN",
                    "isDraft": False,
                    "headRefOid": head,
                    "baseRefOid": BASE,
                    "baseRefName": "main",
                    "headRepository": {"nameWithOwner": repository},
                    "baseRepository": {"nameWithOwner": repository},
                    "reviewDecision": "APPROVED",
                    "author": {
                        "__typename": "User",
                        "id": "U_author",
                        "login": "author",
                    },
                    "latestOpinionatedReviews": {
                        "totalCount": 1,
                        "pageInfo": {"hasNextPage": False, "hasPreviousPage": False},
                        "nodes": [
                            {
                                "id": "R_review",
                                "state": state,
                                "commit": {"oid": head},
                                "author": {
                                    "__typename": "User",
                                    "id": "U_reviewer",
                                    "login": "reviewer",
                                },
                            }
                        ],
                    },
                },
            }
        }
    }


def rules() -> list[dict[str, Any]]:
    """Return effective branch protections required by the reviewed-source verifier."""
    return [
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 2,
                "require_code_owner_review": True,
                "require_last_push_approval": True,
                "dismiss_stale_reviews_on_push": True,
                "required_review_thread_resolution": True,
            },
        }
    ]


def current_comment(*, fetched: bool, change: str | None) -> dict[str, Any]:
    """Return the original comment or one controlled post-fetch mutation."""
    if fetched and change == "deleted":
        raise subprocess.CalledProcessError(1, "gh", stderr="gone")
    comment = copy.deepcopy(intake()["comment"])
    if fetched and change == "body":
        comment["body"] = "/pulumi test up"
    if fetched and change == "user":
        comment["user"]["login"] = "replacement"
    return comment


def transport(*, revoked: bool = False, comment_change: str | None = None):
    """Return a fake GitHub API that exposes only fixed endpoint responses."""
    contract = FIXTURE.read_bytes()
    blob = admission._git_blob_sha(contract)
    fetched = False

    def gh(endpoint: str, *_: str) -> Any:
        nonlocal fetched
        if endpoint == f"repos/{admission.REPOSITORY}":
            return {
                "full_name": admission.REPOSITORY,
                "id": admission.REPOSITORY_ID,
                "owner": {"id": admission.OWNER_ID},
            }
        if endpoint == f"repos/{admission.REPOSITORY}/issues/comments/12":
            return current_comment(fetched=fetched, change=comment_change)
        if endpoint == f"repos/{admission.REPOSITORY}/rules/branches/main?per_page=100":
            return rules()
        if endpoint == "graphql":
            return review_response(
                state="DISMISSED" if revoked and fetched else "APPROVED"
            )
        if (
            endpoint
            == f"repos/{admission.REPOSITORY}/collaborators/reviewer/permission"
        ):
            return {
                "permission": "write",
                "user": {"node_id": "U_reviewer", "login": "reviewer", "type": "User"},
            }
        if endpoint == (
            f"repos/{admission.REPOSITORY}/contents/{admission.CONTRACT_PATH}?ref={HEAD}"
        ):
            fetched = True
            return {
                "type": "file",
                "path": admission.CONTRACT_PATH,
                "sha": blob,
                "size": len(contract),
                "encoding": "base64",
                "content": base64.b64encode(contract).decode(),
            }
        raise AssertionError(f"Unexpected GitHub endpoint {endpoint}")

    return gh


def live_collect_transport(*, comment_change: str):
    """Provide the extra current-PR reads used by the installed collector."""
    source_read = transport(comment_change=comment_change)

    def gh(endpoint: str, *arguments: str) -> Any:
        if endpoint == f"repos/{admission.REPOSITORY}/pulls/19":
            return {**copy.deepcopy(intake()["pr"]), "changed_files": 1}
        if endpoint == f"repos/{admission.REPOSITORY}/compare/{BASE}...{HEAD}":
            return {"files": [{"filename": "README.md"}]}
        if endpoint == (
            f"repos/{admission.REPOSITORY}/collaborators/requester/permission"
        ):
            return {"permission": "write"}
        return source_read(endpoint, *arguments)

    return gh


def test_source_adapter_binds_fixed_blob_after_fresh_review_rechecks() -> None:
    """Produce fixed API source facts from the current six-field request."""
    result = adapter.prepare_authenticated_source(
        request(), intake=intake(), gh=transport(), collect_evidence=collect
    )

    assert result.kind == "poc-phase-source/v1"
    assert result.request == request()
    assert result.source.head_sha == HEAD
    assert result.source.base_sha == BASE
    assert result.source.path == admission.CONTRACT_PATH
    assert "phase" not in result.__dict__
    assert "prior" not in result.__dict__


@pytest.mark.parametrize("field", ["phase", "initial_registry", "approved"])
def test_source_adapter_rejects_expanded_intake(field: str) -> None:
    """No phase or approval claim extends the inherited six-field request."""
    value = request()
    value[field] = "registry"

    with pytest.raises(ValueError, match="Request fields differ"):
        adapter.prepare_authenticated_source(
            value, intake=intake(), gh=transport(), collect_evidence=collect
        )


def test_source_adapter_rejects_moved_head_after_blob_fetch() -> None:
    """A source movement between fixed-blob fetch and recheck fails closed."""
    calls = 0

    def moved(value, *, intake):
        nonlocal calls
        calls += 1
        evidence = collect(value, intake=intake)
        if calls == 2:
            evidence["pr"] = copy.deepcopy(evidence["pr"])
            evidence["pr"]["head"]["sha"] = "c" * 40
        return evidence

    with pytest.raises(ValueError, match="head moved"):
        adapter.prepare_authenticated_source(
            request(), intake=intake(), gh=transport(), collect_evidence=moved
        )


def test_source_adapter_rejects_revoked_requester_after_blob_fetch() -> None:
    """A requester who loses write access cannot retain the prepared source chain."""
    calls = 0

    def revoked(value, *, intake):
        nonlocal calls
        calls += 1
        evidence = collect(value, intake=intake)
        if calls == 2:
            evidence["permission"] = "read"
        return evidence

    with pytest.raises(ValueError, match="Write access"):
        adapter.prepare_authenticated_source(
            request(), intake=intake(), gh=transport(), collect_evidence=revoked
        )


def test_source_adapter_rejects_dismissed_review_after_blob_fetch() -> None:
    """A dismissed independent review after fetch cannot produce source facts."""
    with pytest.raises(ValueError, match="approval"):
        adapter.prepare_authenticated_source(
            request(),
            intake=intake(),
            gh=transport(revoked=True),
            collect_evidence=collect,
        )


@pytest.mark.parametrize("change", ["body", "user"])
def test_source_adapter_rejects_changed_comment_after_blob_fetch(change: str) -> None:
    """The recheck keeps the original authenticated comment intent immutable."""
    with pytest.raises(ValueError, match="Comment evidence changed"):
        adapter.prepare_authenticated_source(
            request(),
            intake=intake(),
            gh=transport(comment_change=change),
            collect_evidence=collect,
        )


@pytest.mark.parametrize("change", ["body", "deleted"])
def test_source_adapter_main_rechecks_comment_with_installed_collector(
    change: str, monkeypatch, capsys
) -> None:
    """The real preflight collector receives a fresh bound comment after fetch."""
    monkeypatch.setattr(preflight, "read_request", request)
    monkeypatch.setattr(preflight, "collect_intake_evidence", lambda _: intake())
    monkeypatch.setattr(preflight, "gh", live_collect_transport(comment_change=change))

    assert adapter.main([]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INVALID: trusted source preparation failed\n"


def test_source_adapter_rejects_invalid_base64_contract_content() -> None:
    """The fixed GitHub contents API cannot smuggle malformed encoded bytes."""
    with pytest.raises(ValueError, match="base64"):
        adapter._content_bytes(
            {
                "type": "file",
                "path": admission.CONTRACT_PATH,
                "sha": "a" * 40,
                "size": 1,
                "encoding": "base64",
                "content": "!",
            }
        )


def test_source_adapter_cli_uses_only_fake_trusted_transport(
    monkeypatch, capsys
) -> None:
    """The CLI serializes source facts and no deployment or accepted-prior state."""
    monkeypatch.setattr(preflight, "read_request", request)
    monkeypatch.setattr(preflight, "collect_intake_evidence", lambda _: intake())
    monkeypatch.setattr(preflight, "collect_evidence", collect)
    monkeypatch.setattr(preflight, "gh", transport())

    assert adapter.main([]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["kind"] == "poc-phase-source/v1"
    assert "phase" not in result and "prior" not in result


def test_source_adapter_cli_redacts_transport_failure(monkeypatch, capsys) -> None:
    """The CLI emits neither token-bearing errors nor source bytes."""
    monkeypatch.setattr(preflight, "read_request", request)
    monkeypatch.setattr(preflight, "collect_intake_evidence", lambda _: intake())

    def failure(*_):
        raise subprocess.CalledProcessError(1, "gh", stderr="token=DO_NOT_ECHO")

    monkeypatch.setattr(preflight, "gh", failure)
    assert adapter.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "DO_NOT_ECHO" not in captured.err


def test_source_adapter_isolated_cli_rejects_missing_request(tmp_path: Path) -> None:
    """Direct isolated execution cannot prepare facts without trusted intake fields."""
    result = subprocess.run(
        [sys.executable, "-I", str(Path(adapter.__file__))],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "INVALID: trusted source preparation failed\n"
