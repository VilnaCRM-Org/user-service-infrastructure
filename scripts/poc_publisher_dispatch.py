#!/usr/bin/env python3
"""Dispatch only the pinned installed TEST publisher after same-run proof issuance."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402  # nosec B404

import poc_registry_completion as completion  # noqa: E402

artifacts = completion.source_api
APP_ID = 4853984
APP_SLUG = "vilnacrm-user-service-evidence"
BOT_ID = 325789989
REPOSITORY = "VilnaCRM-Org/user-service"
REPOSITORY_ID = 646535009
API = f"repos/{REPOSITORY}"
WORKFLOW = ".github/workflows/publish-poc-images.yml"
ENDPOINT = f"{API}/actions/workflows/publish-poc-images.yml"


def require(value, category):
    """Keep diagnostics fixed and free of GitHub response or credential content."""
    if not value:
        raise ValueError(category)


def repository(value):
    """Authenticate the fixed application and organization identities."""
    artifacts._matches(value, {"id": REPOSITORY_ID, "full_name": REPOSITORY})
    artifacts._matches(value.get("owner"), {"id": artifacts.admission.OWNER_ID})


def main_review_protection(gh):
    """Require observable effective PR review rules; bypass lists need admin audit."""
    rules = gh(f"{API}/rules/branches/main?per_page=100")
    require(type(rules) is list and len(rules) < 100, "main-rules-incomplete")
    require(all(type(rule) is dict for rule in rules), "main-rules-invalid")
    reviews = [rule for rule in rules if rule.get("type") == "pull_request"]
    require(len(reviews) == 1, "main-review-rule-required")
    rule = reviews[0]
    parameters = rule["parameters"]
    artifacts._matches(
        parameters,
        {
            "require_code_owner_review": True,
            "require_last_push_approval": True,
            "dismiss_stale_reviews_on_push": True,
            "required_review_thread_resolution": True,
        },
    )
    count = parameters.get("required_approving_review_count")
    require(type(count) is int and count >= 1, "main-review-approval-required")
    artifacts._matches(
        rule,
        {
            "ruleset_source_type": "Repository",
            "ruleset_source": REPOSITORY,
        },
    )
    identifier = rule.get("ruleset_id")
    require(type(identifier) is int and identifier > 0, "main-ruleset-required")
    native = gh(f"{API}/rulesets/{identifier}")
    artifacts._matches(
        native,
        {
            "id": identifier,
            "target": "branch",
            "source_type": "Repository",
            "source": REPOSITORY,
            "enforcement": "active",
        },
    )
    require(
        {"type": "pull_request", "parameters": parameters} in native["rules"],
        "main-review-ruleset-mismatch",
    )


def publisher_environment(gh):
    """Mirror the publisher's exact-main, independent-human OIDC admission gate."""
    endpoint = f"{API}/environments/poc-test-images"
    environment = gh(endpoint)
    require(
        not completion.boundary.verification_blockers(
            environment, gh(f"{endpoint}/deployment-branch-policies?per_page=100")
        ),
        "publisher-environment-main-only-required",
    )
    user = gh("users/Kravalg")
    artifacts._matches(user, {"login": "Kravalg", "type": "User"})
    identifier = user.get("id")
    require(
        type(identifier) is int and identifier > 0 and identifier != BOT_ID,
        "publisher-environment-reviewer-required",
    )
    reviews = [
        rule
        for rule in environment["protection_rules"]
        if rule.get("type") == "required_reviewers"
    ]
    require(len(reviews) == 1, "publisher-environment-reviewer-required")
    artifacts._matches(reviews[0], {"prevent_self_review": True})
    reviewers = reviews[0]["reviewers"]
    require(len(reviewers) == 1, "publisher-environment-reviewer-required")
    artifacts._matches(reviewers[0], {"type": "User"})
    artifacts._matches(reviewers[0].get("reviewer"), {"id": identifier})


def publisher(sha, gh):
    """Require the App grant and an active publisher at the protected revision pin."""
    artifacts._pattern(sha, r"[0-9a-f]{40}")
    app = gh(f"apps/{APP_SLUG}")
    artifacts._matches(app, {"id": APP_ID, "slug": APP_SLUG})
    require(
        app.get("permissions", {}).get("actions") == "write",
        "app-actions-write-required",
    )
    native = gh(API)
    repository(native)
    artifacts._matches(native, {"default_branch": "main"})
    main_review_protection(gh)
    publisher_environment(gh)
    artifacts._matches(
        gh(f"{API}/git/ref/heads/main").get("object"), {"sha": sha, "type": "commit"}
    )
    workflow = gh(ENDPOINT)
    artifacts._matches(workflow, {"path": WORKFLOW, "state": "active"})
    require(
        type(workflow.get("id")) is int and workflow["id"] > 0,
        "publisher-workflow-required",
    )
    return workflow["id"]


def prepare(environment=None, *, gh=None):
    """Authenticate proof, source and the main-only key boundary before minting."""
    environment = os.environ if environment is None else environment
    gh = gh or completion.runtime.preflight.gh
    require(
        environment.get("GITHUB_JOB") == "test_registry_dispatch",
        "dispatcher-job-required",
    )
    identifier = environment.get("POC_REGISTRY_RECEIPT_ID", "")
    artifacts._pattern(identifier, r"[1-9][0-9]*")
    proof = completion.prepare(environment)
    observed = proof["observation"]
    completion._jobs(
        gh,
        str(observed["run_id"]),
        observed["workflow_sha"],
        completed=True,
        observed_at=observed["observed_at"],
        uploaded_at=gh(
            f"{artifacts.API}/actions/artifacts/{proof['observation_artifact']['artifact_id']}"
        )["created_at"],
    )
    completion._deployment(gh, int(identifier), proof, APP_ID, APP_SLUG)
    sha = environment.get("POC_PUBLISHER_WORKFLOW_SHA", "")
    workflow_id = publisher(sha, gh)
    request = {
        "source_sha": sha,
        "platform": "linux/amd64",
        "registry_phase_receipt_id": int(identifier),
        "registry_contract_sha256": observed["source"]["contract_sha256"],
        "registry_checkpoint_version": observed["checkpoint"]["version"],
    }
    return request, workflow_id


def app_api(endpoint, payload=None):
    """Use the separate application-only token; never inherit the proof token."""
    arguments = [
        "/usr/bin/gh",
        "api",
        "--hostname",
        "github.com",
        endpoint,
        "-H",
        "X-GitHub-Api-Version: 2026-03-10",
    ]
    if payload is not None:
        arguments.extend(["--method", "POST", "--input", "-"])
    result = subprocess.run(  # nosec B603
        arguments,
        input=None if payload is None else completion._canonical(payload),
        capture_output=True,
        check=False,
        timeout=60,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": os.environ["HOME"],
            "GH_TOKEN": os.environ["PUBLISHER_DISPATCH_APP_TOKEN"],
            "GH_PROMPT_DISABLED": "1",
        },
    )
    require(
        result.returncode == 0 and len(result.stdout) <= 1024 * 1024,
        "dispatcher-api-failed",
    )
    return json.loads(result.stdout, object_pairs_hook=artifacts._pairs)


def dispatch():
    """Send once, then authenticate the exact native run returned by GitHub."""
    installation = app_api("installation/repositories?per_page=100")
    artifacts._matches(installation, {"total_count": 1})
    require(len(installation["repositories"]) == 1, "application-only-token-required")
    repository(installation["repositories"][0])
    request, workflow_id = prepare()
    result = app_api(
        ENDPOINT + "/dispatches",
        {
            "ref": "main",
            "inputs": {"request": completion._canonical(request).decode()},
        },
    )
    identifier = result["workflow_run_id"]
    require(type(identifier) is int and identifier > 0, "publisher-run-id-required")
    artifacts._matches(
        result,
        {
            "run_url": f"https://api.github.com/{API}/actions/runs/{identifier}",
            "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{identifier}",
        },
    )
    native = app_api(f"{API}/actions/runs/{identifier}")
    artifacts._matches(
        native,
        {
            "id": identifier,
            "workflow_id": workflow_id,
            "run_attempt": 1,
            "head_branch": "main",
            "head_sha": request["source_sha"],
            "event": "workflow_dispatch",
            "path": WORKFLOW,
        },
    )
    for field in ("repository", "head_repository"):
        repository(native.get(field))
    for field in ("actor", "triggering_actor"):
        artifacts._matches(
            native.get(field),
            {
                "id": BOT_ID,
                "login": f"{APP_SLUG}[bot]",
                "type": "Bot",
            },
        )
    return identifier


def main(argv=None):
    """Expose only prerequisite checking and one non-retrying dispatch attempt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "dispatch"))
    mode = parser.parse_args(argv).mode
    try:
        if mode == "prepare":
            prepare()
            print("VALID: TEST publisher dispatch prerequisites")
        else:
            print(f"publisher_run_id={dispatch()}")
        return 0
    except (
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
        RuntimeError,
        EOFError,
        RecursionError,
        artifacts.zipfile.BadZipFile,
        subprocess.SubprocessError,
    ):
        print(
            "INVALID: TEST publisher dispatch failed; do not retry an uncertain POST",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
