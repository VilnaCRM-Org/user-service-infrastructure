"""Current independent review admission rejects stale or incomplete authority."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
admission = importlib.import_module("reviewed_source_admission")
preflight = importlib.import_module("pulumi_command_preflight")
REPO, HEAD, BASE = "org/repo", "a" * 40, "b" * 40


def evidence():
    author = {"__typename": "User", "id": "U_author", "login": "author"}
    reviewer = {"__typename": "User", "id": "U_reviewer", "login": "reviewer"}
    pr = {
        "number": 78,
        "state": "OPEN",
        "isDraft": False,
        "headRefOid": HEAD,
        "baseRefOid": BASE,
        "baseRefName": "main",
        "headRepository": {"nameWithOwner": REPO},
        "baseRepository": {"nameWithOwner": REPO},
        "reviewDecision": "APPROVED",
        "author": author,
        "latestOpinionatedReviews": {
            "totalCount": 1,
            "pageInfo": {"hasNextPage": False, "hasPreviousPage": False},
            "nodes": [
                {
                    "id": "R_review",
                    "state": "APPROVED",
                    "commit": {"oid": HEAD},
                    "author": reviewer,
                }
            ],
        },
    }
    rules = [
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 2,
                "require_code_owner_review": True,
                "require_last_push_approval": True,
                "dismiss_stale_reviews_on_push": True,
                "required_review_thread_resolution": True,
            },
        },
        {"type": "deletion"},
    ]
    snapshot = {"data": {"repository": {"nameWithOwner": REPO, "pullRequest": pr}}}
    permission = {
        "permission": "write",
        "user": {"node_id": "U_reviewer", "login": "reviewer", "type": "User"},
    }
    return [rules, snapshot, permission, deepcopy(rules), deepcopy(snapshot)]


def review_api(origin, path, *args):
    """Model authenticated review reads bound to each collector's current PR."""
    rules, snapshot, permission, _, _ = evidence()
    repository = origin["repository"]
    if path == f"repos/{repository}/rules/branches/main?per_page=100":
        assert not args
        return rules
    if path == f"repos/{repository}/collaborators/reviewer/permission":
        assert not args
        return permission
    if path != "graphql":
        return NotImplemented
    owner, name = repository.split("/")
    assert f"owner={owner}" in args and f"name={name}" in args
    assert "number=78" in args and "writersOnly:true" in args[1]
    repo = snapshot["data"]["repository"]
    repo["nameWithOwner"] = repository
    pr, current = repo["pullRequest"], origin["pr"]
    pr.update(
        state=current["state"].upper(),
        isDraft=current.get("draft", False),
        headRefOid=current["head"]["sha"],
        baseRefOid=current["base"]["sha"],
        baseRefName=current["base"]["ref"],
        headRepository={"nameWithOwner": current["head"]["repo"]["full_name"]},
        baseRepository={"nameWithOwner": current["base"]["repo"]["full_name"]},
    )
    pr["latestOpinionatedReviews"]["nodes"][0]["commit"]["oid"] = current["head"]["sha"]
    return snapshot


def run(values=None):
    queue = evidence() if values is None else values
    calls = []

    def gh(*args):
        calls.append(args)
        return queue[len(calls) - 1]

    result = admission.verify_reviewed_source(REPO, "78", HEAD, BASE, gh=gh)
    return result, calls


@pytest.mark.parametrize("permission", ["write", "maintain", "admin"])
def test_current_review_and_rules_twice(permission):
    values = evidence()
    values[2]["permission"] = permission
    result, calls = run(values)
    assert result["reviewer_id"] == "U_reviewer"
    assert result["head_sha"] == HEAD and result["base_sha"] == BASE
    assert len(result["review_protection_sha256"]) == 64
    assert [call[0] for call in calls] == [
        f"repos/{REPO}/rules/branches/main?per_page=100",
        "graphql",
        f"repos/{REPO}/collaborators/reviewer/permission",
        f"repos/{REPO}/rules/branches/main?per_page=100",
        "graphql",
    ]
    assert "writersOnly:true" in calls[1][2]


@pytest.mark.parametrize("stage", [1, 4])
@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "CLOSED"),
        ("isDraft", True),
        ("number", True),
        ("headRefOid", "c" * 40),
        ("baseRefOid", "c" * 40),
        ("baseRefName", "other"),
        ("reviewDecision", "REVIEW_REQUIRED"),
        ("headRepository", {"nameWithOwner": "other/repo"}),
        ("baseRepository", {"nameWithOwner": "other/repo"}),
    ],
)
def test_source_or_decision_change(stage, field, value):
    values = evidence()
    values[stage]["data"]["repository"]["pullRequest"][field] = value
    with pytest.raises(ValueError):
        run(values)


@pytest.mark.parametrize("stage", [1, 4])
@pytest.mark.parametrize(
    "path,value",
    [
        (("nodes", 0, "author", "__typename"), "Bot"),
        (("nodes", 0, "author", "id"), "U_author"),
        (("nodes", 0, "commit", "oid"), BASE),
        (("nodes", 0, "state"), "DISMISSED"),
        (("nodes", 0, "state"), "UNKNOWN"),
        (("nodes", 0, "id"), ""),
        (("nodes", 0, "author", "login"), "../escape"),
        (("nodes", 0, "author"), None),
        (("totalCount",), 101),
        (("totalCount",), 2),
        (("totalCount",), True),
        (("pageInfo", "hasNextPage"), True),
        (("pageInfo", "hasPreviousPage"), True),
        (("nodes",), {}),
        (("nodes", 0, "commit"), None),
    ],
)
def test_review_inventory_fails_closed(stage, path, value):
    values = evidence()
    target = values[stage]["data"]["repository"]["pullRequest"][
        "latestOpinionatedReviews"
    ]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        run(values)


@pytest.mark.parametrize("review_id", ["R_review", "R_other"])
def test_duplicate_latest_review(review_id):
    values = evidence()
    reviews = values[1]["data"]["repository"]["pullRequest"]["latestOpinionatedReviews"]
    reviews["nodes"].append(deepcopy(reviews["nodes"][0]))
    reviews["nodes"][1]["id"] = review_id
    reviews["totalCount"] = 2
    with pytest.raises(ValueError, match="Duplicate"):
        run(values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("permission", "read"),
        ("node_id", "U_other"),
        ("login", "other"),
        ("type", "Bot"),
    ],
)
def test_writer_permission_and_identity(field, value):
    values = evidence()
    target = values[2] if field == "permission" else values[2]["user"]
    target[field] = value
    with pytest.raises(ValueError, match="authorized human"):
        run(values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("required_approving_review_count", 1),
        ("required_approving_review_count", True),
        ("require_code_owner_review", False),
        ("require_last_push_approval", False),
        ("dismiss_stale_reviews_on_push", False),
        ("required_review_thread_resolution", False),
    ],
)
@pytest.mark.parametrize("stage", [0, 3])
def test_effective_rules_required_twice(stage, field, value):
    values = evidence()
    values[stage][0]["parameters"][field] = value
    with pytest.raises(ValueError, match="protections"):
        run(values)


@pytest.mark.parametrize("rules", [None, [], [{"type": "deletion"}] * 100])
def test_incomplete_effective_rules(rules):
    values = evidence()
    values[0] = rules
    with pytest.raises(ValueError):
        run(values)


def test_changed_valid_protection_and_changed_approval():
    values = evidence()
    values[3][0]["parameters"]["required_approving_review_count"] = 3
    with pytest.raises(ValueError, match="protections changed"):
        run(values)
    values = evidence()
    values[4]["data"]["repository"]["pullRequest"]["latestOpinionatedReviews"]["nodes"][
        0
    ]["id"] = "R_new"
    with pytest.raises(ValueError, match="approval changed"):
        run(values)
    values = evidence()
    values[4]["data"]["repository"]["pullRequest"]["author"]["id"] = "U_new"
    with pytest.raises(ValueError, match="approval changed"):
        run(values)


@pytest.mark.parametrize("change", ["errors", "foreign", "unknown-actor", "bad-id"])
def test_malformed_snapshot(change):
    values = evidence()
    repo = values[1]["data"]["repository"]
    if change == "errors":
        values[1]["errors"] = [{"message": "private"}]
    elif change == "foreign":
        repo["nameWithOwner"] = "foreign/repo"
    elif change == "unknown-actor":
        repo["pullRequest"]["author"]["__typename"] = "Mannequin"
    else:
        repo["pullRequest"]["author"]["id"] = None
    with pytest.raises(ValueError):
        run(values)


@pytest.mark.parametrize(
    "args",
    [
        ("../repo", "78", HEAD, BASE),
        (REPO, "01", HEAD, BASE),
        (REPO, "78", "A" * 40, BASE),
        (REPO, "78", HEAD, HEAD),
    ],
)
def test_bad_coordinates_before_reads(args):
    def forbidden(*_):
        pytest.fail("Invalid caller coordinates must not reach GitHub")

    with pytest.raises(ValueError):
        admission.verify_reviewed_source(*args, gh=forbidden)


def test_cli_public_result_and_redacted_failure(monkeypatch, capsys):
    args = [
        "--repository",
        REPO,
        "--pr-number",
        "78",
        "--expected-head-sha",
        HEAD,
        "--expected-base-sha",
        BASE,
    ]
    values = iter(evidence())
    monkeypatch.setattr(preflight, "gh", lambda *_: next(values))
    assert admission.main(args) == 0
    assert json.loads(capsys.readouterr().out)["reviewer_id"] == "U_reviewer"

    def failure(*_):
        raise subprocess.CalledProcessError(
            1, "private-command", stderr="private-token"
        )

    monkeypatch.setattr(preflight, "gh", failure)
    assert admission.main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Reviewed-source admission failed.\n"
