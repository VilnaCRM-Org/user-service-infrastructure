"""Trusted service workers require current review at every credential boundary."""

from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path

import pytest
import yaml
from test_pulumi_command_preflight import fixture_data, preflight
from test_reviewed_source_admission import review_api

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/self-deploy.yml"
CLOUD_JOBS = (
    "test_preview",
    "test_apply",
    "test_post_apply_drift",
    "prod_preview",
    "prod_apply",
    "prod_post_apply_drift",
)


def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def review_step(steps, purpose):
    return next(
        s for s in steps if s.get("name") == f"Verify reviewed source before {purpose}"
    )


@pytest.mark.parametrize("job_name", CLOUD_JOBS)
def test_each_protected_worker_rechecks_before_credentials_and_pr_execution(job_name):
    job = workflow()["jobs"][job_name]
    steps = job["steps"]
    assert job["environment"] in {"test-preview", "test", "prod-preview", "prod"}
    assert "preflight" in job["needs"]
    trusted = next(
        s for s in steps if s.get("name") == "Check out trusted credential helper"
    )
    assert trusted["with"] == {
        "ref": "${{ github.sha }}",
        "path": ".trusted",
        "persist-credentials": False,
    }
    execution = next(
        s
        for s in steps
        if (
            "poc_registry_runner.py" in s.get("run", "")
            if job_name.startswith("test_")
            else s.get("run") == "make start"
        )
    )
    execution_review = (
        "saved-plan replay" if job_name == "test_apply" else "PR execution"
    )
    boundaries = {
        "config credentials": next(
            s for s in steps if s.get("uses", "").endswith("load-aws-ci-env")
        ),
        "execution credentials": next(
            s
            for s in steps
            if s.get("uses", "").startswith("aws-actions/configure-aws-credentials@")
        ),
        execution_review: execution,
    }
    for purpose, boundary in boundaries.items():
        review = review_step(steps, purpose)
        assert steps.index(trusted) < steps.index(review) < steps.index(boundary)
        assert steps[steps.index(boundary) - 1] == review
        assert "if" not in review and "continue-on-error" not in review
        assert review["env"] == {
            "GH_TOKEN": "${{ github.token }}",
            "REVIEW_REPOSITORY": "${{ github.repository }}",
            "PR_NUMBER": "${{ needs.preflight.outputs.pull_request_number }}",
            "EXPECTED_SHA": "${{ needs.preflight.outputs.head_sha }}",
            "EXPECTED_BASE_SHA": "${{ needs.preflight.outputs.base_sha }}",
        }
        assert (
            'python3 -I "${GITHUB_WORKSPACE}/.trusted/scripts/'
            'reviewed_source_admission.py"' in review["run"]
        )
        for flag, variable in (
            ("repository", "REVIEW_REPOSITORY"),
            ("pr-number", "PR_NUMBER"),
            ("expected-head-sha", "EXPECTED_SHA"),
            ("expected-base-sha", "EXPECTED_BASE_SHA"),
        ):
            assert f'--{flag} "${{{variable}}}"' in review["run"]
        assert "${{" not in review["run"]


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_saved_plan_replay_rechecks_after_all_artifact_downloads(environment):
    steps = workflow()["jobs"][environment + "_apply"]["steps"]
    review = review_step(steps, "saved-plan replay")
    downloads = [
        i
        for i, s in enumerate(steps)
        if s.get("uses", "").startswith("actions/download-artifact@")
    ]
    apply = next(s for s in steps if s.get("name", "").startswith("Apply saved "))
    assert downloads and max(downloads) < steps.index(review)
    assert steps[steps.index(apply) - 1] == review
    assert "if" not in review and "continue-on-error" not in review
    if environment == "test":
        assert 'poc_registry_runner.py" up-plan' in apply["run"]
        assert "make " not in apply["run"]
    else:
        assert "make pulumi-up-plan" in apply["run"]


def test_automatic_pr_and_main_push_remain_unprivileged_and_noncircular():
    path = ROOT / ".github/workflows/pulumi-pr-guardrails.yml"
    document = yaml.safe_load(path.read_text())
    events = document.get("on", document.get(True))
    assert set(events) == {"pull_request", "push"}
    assert events["push"]["branches"] == ["main"]
    assert document["permissions"] == {"contents": "read"}
    for job in document["jobs"].values():
        assert job.get("permissions", document["permissions"]) == {"contents": "read"}
        assert "environment" not in job
        for step in job["steps"]:
            assert not any(
                word in step.get("uses", "")
                for word in ("configure-aws-credentials", "load-aws-ci-env")
            )
            assert "reviewed_source_admission" not in step.get("run", "")
    preview = document["jobs"]["preview"]
    assert preview["env"]["PULUMI_BACKEND_URL"].startswith("file://")
    assert preview["env"]["PULUMI_PREVIEW_STACKS"] == "dev"


def _mutate_snapshot(response, hostile, snapshots):
    pr = response["data"]["repository"]["pullRequest"]
    if hostile == "stale-head":
        pr["headRefOid"] = "c" * 40
    if hostile == "dismissed" and snapshots == 2:
        pr["latestOpinionatedReviews"]["nodes"][0]["state"] = "DISMISSED"
    if hostile == "author-review":
        pr["latestOpinionatedReviews"]["nodes"][0]["author"] = pr["author"]
    if hostile == "draft":
        pr["isDraft"] = True


def api_for(origin, *, hostile=None):
    """Route real collector/reviewer calls to authenticated synthetic responses."""
    snapshots = 0

    def gh(path, *args):
        nonlocal snapshots
        response = review_api(origin, path, *args)
        if response is not NotImplemented:
            if path == "graphql":
                snapshots += 1
                _mutate_snapshot(response, hostile, snapshots)
            if "/rules/branches/" in path and hostile == "weak-protection":
                response[0]["parameters"]["require_last_push_approval"] = False
            if "/collaborators/reviewer/" in path and hostile == "revoked-writer":
                response["permission"] = "read"
            return response
        if "/compare/" in path:
            return {"files": [{"filename": "README.md"}, {"filename": "Makefile"}]}
        if "/pulls/" in path:
            return copy.deepcopy(origin["pr"])
        if "/collaborators/" in path:
            return {"permission": "write"}
        raise AssertionError("Unexpected authenticated endpoint")

    return gh


def test_real_preflight_collects_bound_current_human_review(monkeypatch):
    request, origin = fixture_data()
    monkeypatch.setattr(preflight, "gh", api_for(origin))
    result = preflight.collect_evidence(request, intake=origin)
    assert result["review"]["head_sha"] == request["head_sha"]
    assert result["review"]["base_sha"] == origin["scope_base_sha"]
    assert result["review"]["reviewer_id"] == "U_reviewer"


@pytest.mark.parametrize(
    "hostile",
    [
        "stale-head",
        "dismissed",
        "author-review",
        "draft",
        "weak-protection",
        "revoked-writer",
    ],
)
def test_real_preflight_cannot_return_execution_facts_without_review(
    monkeypatch, hostile
):
    request, origin = fixture_data()
    monkeypatch.setattr(preflight, "gh", api_for(origin, hostile=hostile))
    with pytest.raises(ValueError):
        preflight.collect_evidence(request, intake=origin)


def test_actual_review_shell_step_isolated_from_hostile_pr_imports(tmp_path):
    workspace = tmp_path / "pr"
    workspace.mkdir()
    (workspace / ".trusted").symlink_to(ROOT, target_is_directory=True)
    marker = tmp_path / "imported-untrusted"
    for module in ("json", "re", "sitecustomize"):
        (workspace / f"{module}.py").write_text(
            f"open({str(marker)!r}, 'w').close()\n"
            "raise RuntimeError('untrusted import')\n"
        )
    tools = tmp_path / "bin"
    tools.mkdir()
    gh = tools / "gh"
    gh.write_text("#!/bin/sh\nprintf 'DO_NOT_ECHO_SYNTHETIC' >&2\nexit 1\n")
    gh.chmod(0o755)
    gate = review_step(
        workflow()["jobs"]["test_preview"]["steps"], "config credentials"
    )
    issued = tmp_path / "would-issue-credentials"
    script = gate["run"] + '\ntouch "${CREDENTIAL_CANARY}"\n'
    environment = {
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "PYTHONPATH": str(workspace),
        "GITHUB_WORKSPACE": str(workspace),
        "REVIEW_REPOSITORY": "org/repo",
        "PR_NUMBER": "78",
        "EXPECTED_SHA": "a" * 40,
        "EXPECTED_BASE_SHA": "b" * 40,
        "CREDENTIAL_CANARY": str(issued),
    }
    control = subprocess.run(
        ["bash", "-e", "-c", script.replace("python3 -I", "python3")],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert control.returncode != 0 and marker.exists()
    marker.unlink()
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Reviewed-source admission failed.\n"
    assert not marker.exists() and not issued.exists()
