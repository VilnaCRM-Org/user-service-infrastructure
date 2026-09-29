"""Require fresh independent approval before trusted workers issue credentials.

The caller supplies authenticated source coordinates and a read-only GitHub API
adapter. Two snapshots detect observed review/source/protection changes; these
reads are not an atomic transaction with STS or a revocation of issued sessions.
Native reviewDecision enforces the current last-push rule. Git commit metadata
is deliberately not used to infer who pushed the PR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any, Callable, cast

GitHubRead = Callable[..., Any]
_QUERY = """query($owner:String!,$name:String!,$number:Int!){
 repository(owner:$owner,name:$name){nameWithOwner
  pullRequest(number:$number){number state isDraft headRefOid baseRefOid baseRefName
   headRepository{nameWithOwner} baseRepository{nameWithOwner} reviewDecision
   author{__typename login ... on User{id} ... on Bot{id}}
   latestOpinionatedReviews(first:100,writersOnly:true){totalCount
    pageInfo{hasNextPage hasPreviousPage}
    nodes{id state commit{oid} author{__typename login ... on User{id} ... on Bot{id}}}
   }
  }
 }
}"""


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _object(value: Any) -> dict:
    _require(type(value) is dict, "Malformed review evidence object")
    return value


def _identity(value: Any) -> tuple[str, str, str]:
    actor = _object(value)
    kind, node, login = (actor.get(k) for k in ("__typename", "id", "login"))
    _require(kind in ("User", "Bot"), "Unknown review actor type")
    _require(
        isinstance(node, str) and bool(re.fullmatch(r"[A-Za-z0-9_=-]+", node)),
        "Unknown review actor identity",
    )
    _require(
        isinstance(login, str) and bool(re.fullmatch(r"[A-Za-z0-9_\[\]-]+", login)),
        "Unknown review actor login",
    )
    return cast(str, kind), cast(str, node), cast(str, login)


def _review_nodes(pr: dict) -> list:
    """Require one complete bounded latest-review inventory before iteration."""
    connection = _object(pr.get("latestOpinionatedReviews"))
    nodes, count = connection.get("nodes"), connection.get("totalCount")
    page = _object(connection.get("pageInfo"))
    _require(
        type(nodes) is list
        and type(count) is int
        and 0 <= count <= 100
        and len(nodes) == count
        and page.get("hasNextPage") is False
        and page.get("hasPreviousPage") is False,
        "Incomplete or excessive latest review inventory",
    )
    return cast(list, nodes)


def _approvals(pr: dict, head: str) -> dict[str, tuple[str, str]]:
    _, author_id, _ = _identity(pr.get("author"))
    approvals, reviewers, ids = {}, set(), set()
    for value in _review_nodes(pr):
        review = _object(value)
        kind, reviewer, login = _identity(review.get("author"))
        review_id = review.get("id")
        _require(isinstance(review_id, str) and bool(review_id), "Missing review ID")
        _require(
            review_id not in ids and reviewer not in reviewers,
            "Duplicate latest review",
        )
        ids.add(review_id)
        reviewers.add(reviewer)
        state = review.get("state")
        _require(
            state
            in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED", "COMMENTED", "PENDING"),
            "Unknown review state",
        )
        if state == "APPROVED" and kind == "User" and reviewer != author_id:
            if _object(review.get("commit")).get("oid") == head:
                approvals[review_id] = (reviewer, login)
    _require(bool(approvals), "Independent human approval of current head is required")
    return approvals


def _snapshot(
    gh: GitHubRead, repository: str, number: str, head: str, base: str
) -> dict:
    owner, name = repository.split("/")
    response = _object(
        gh(
            "graphql",
            "-f",
            f"query={_QUERY}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={number}",
        )
    )
    _require(not response.get("errors"), "GitHub review query failed")
    repo = _object(_object(response.get("data")).get("repository"))
    _require(repo.get("nameWithOwner") == repository, "Review repository changed")
    pr = _object(repo.get("pullRequest"))
    expected = {
        "number": int(number),
        "state": "OPEN",
        "isDraft": False,
        "headRefOid": head,
        "baseRefOid": base,
        "baseRefName": "main",
        "reviewDecision": "APPROVED",
    }
    _require(
        all(type(pr.get(k)) is type(v) and pr[k] == v for k, v in expected.items()),
        "Current PR source or review decision is not approved",
    )
    for field in ("headRepository", "baseRepository"):
        _require(
            _object(pr.get(field)).get("nameWithOwner") == repository,
            "Foreign review source repository",
        )
    return {"author": _identity(pr.get("author")), "approvals": _approvals(pr, head)}


def _protection(gh: GitHubRead, repository: str) -> str:
    # This endpoint returns active applicable rules, including inherited rules.
    # A full page is conservatively rejected instead of assuming completeness.
    rules = gh(f"repos/{repository}/rules/branches/main?per_page=100")
    _require(
        type(rules) is list and len(rules) < 100, "Incomplete effective review rules"
    )
    valid = False
    for value in rules:
        rule = _object(value)
        if rule.get("type") != "pull_request":
            continue
        params = _object(rule.get("parameters"))
        count = params.get("required_approving_review_count")
        valid |= (
            type(count) is int
            and count >= 2
            and all(
                params.get(flag) is True
                for flag in (
                    "require_code_owner_review",
                    "require_last_push_approval",
                    "dismiss_stale_reviews_on_push",
                    "required_review_thread_resolution",
                )
            )
        )
    _require(valid, "Effective main review protections are insufficient")
    return hashlib.sha256(
        json.dumps(
            rules, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def verify_reviewed_source(
    repository: str,
    pr_number: str,
    expected_head_sha: str,
    expected_base_sha: str,
    *,
    gh: GitHubRead,
) -> dict:
    """Return public fresh review evidence; never authorize or issue AWS tokens."""
    _require(
        isinstance(repository, str)
        and bool(
            re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", repository
            )
        ),
        "Invalid review repository",
    )
    _require(
        isinstance(pr_number, str) and bool(re.fullmatch(r"[1-9][0-9]*", pr_number)),
        "Invalid review PR number",
    )
    _require(
        all(
            isinstance(s, str) and bool(re.fullmatch(r"[0-9a-f]{40}", s))
            for s in (expected_head_sha, expected_base_sha)
        )
        and expected_head_sha != expected_base_sha,
        "Invalid review source revisions",
    )
    protection = _protection(gh, repository)
    before = _snapshot(gh, repository, pr_number, expected_head_sha, expected_base_sha)
    review_id, (reviewer, login) = sorted(before["approvals"].items())[0]
    permission = _object(gh(f"repos/{repository}/collaborators/{login}/permission"))
    user = _object(permission.get("user"))
    _require(
        permission.get("permission") in ("write", "maintain", "admin")
        and user.get("node_id") == reviewer
        and user.get("login") == login
        and user.get("type") == "User",
        "Approving reviewer is no longer an authorized human writer",
    )
    _require(
        _protection(gh, repository) == protection,
        "Effective review protections changed",
    )
    after = _snapshot(gh, repository, pr_number, expected_head_sha, expected_base_sha)
    _require(
        before["author"] == after["author"]
        and after["approvals"].get(review_id) == (reviewer, login),
        "Independent approval changed during verification",
    )
    return {
        "head_sha": expected_head_sha,
        "base_sha": expected_base_sha,
        "review_id": review_id,
        "reviewer_id": reviewer,
        "reviewer_login": login,
        "review_protection_sha256": protection,
    }


def main(argv=None) -> int:
    """Expose only fixed review inputs; failures never print API response bodies."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository", "pr-number", "expected-head-sha", "expected-base-sha"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    # -I omits the script directory; this path is the trusted checkout, not PR cwd.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pulumi_command_preflight import gh  # noqa: PLC0415

    try:
        result = verify_reviewed_source(
            args.repository,
            args.pr_number,
            args.expected_head_sha,
            args.expected_base_sha,
            gh=gh,
        )
    except (ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("Reviewed-source admission failed.", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
