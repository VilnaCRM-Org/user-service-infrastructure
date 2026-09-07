"""Structural tests for the AI-safe CI/CD guardrail layer."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"
GUARDRAILS_DOC = PROJECT_ROOT / "docs" / "ci-guardrails.md"
PREVIEW_SCRIPT = PROJECT_ROOT / "scripts" / "run_pulumi_preview.py"
PREVIEW_SUMMARY_SCRIPT = PROJECT_ROOT / "scripts" / "publish_pulumi_preview_summary.py"
DRIFT_SCRIPT = PROJECT_ROOT / "scripts" / "run_pulumi_drift_check.py"
GITLEAKS_CONFIG = PROJECT_ROOT / ".gitleaks.toml"
ACTION_SHA_REF = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def _workflow(name: str) -> dict:
    """Load a workflow YAML file from disk."""
    return yaml.safe_load((WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    """Normalize the GitHub Actions `on` key when YAML parses it as a boolean."""
    return workflow.get("on", workflow.get(True, {}))


def test_preview_guardrail_workflow_remains_credential_free() -> None:
    """Ordinary PR code cannot request cloud credentials through a legacy path."""
    workflow = _workflow("pulumi-pr-guardrails.yml")
    assert set(workflow["jobs"]) == {"preview", "destructive_diff"}
    assert workflow["jobs"]["preview"]["env"]["PULUMI_PREVIEW_STACKS"] == "dev"
    assert "id-token" not in str(workflow)
    assert "configure-aws-credentials" not in str(workflow)
    assert workflow["jobs"]["destructive_diff"]["needs"] == ["preview"]


def test_security_scan_workflow_runs_repo_make_targets() -> None:
    """Keep the security-scan workflow easy to reproduce locally."""
    workflow = _workflow("security-scans.yml")
    jobs = workflow["jobs"]

    assert jobs["secrets"]["timeout-minutes"] == 10
    assert jobs["dependency_audit"]["timeout-minutes"] == 15
    assert jobs["actionlint"]["timeout-minutes"] == 10
    assert any(
        step.get("run") == "make test-secrets" for step in jobs["secrets"]["steps"]
    )
    assert any(
        step.get("run") == "make test-deps-security"
        for step in jobs["dependency_audit"]["steps"]
    )
    assert any(
        step.get("run") == "make test-actionlint"
        for step in jobs["actionlint"]["steps"]
    )


def test_codeql_workflow_covers_python_and_github_actions() -> None:
    """Require GitHub-native code scanning for both Python and workflow code."""
    workflow = _workflow("codeql.yml")
    matrix_languages = workflow["jobs"]["analyze"]["strategy"]["matrix"]["language"]
    uses_steps = [
        step.get("uses")
        for step in workflow["jobs"]["analyze"]["steps"]
        if step.get("uses")
    ]

    assert workflow["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }
    assert workflow["concurrency"] == {
        "group": (
            "${{ github.workflow }}-"
            "${{ github.event.pull_request.number || github.ref }}"
        ),
        "cancel-in-progress": True,
    }
    assert "concurrency" not in workflow["jobs"]["analyze"]
    assert matrix_languages == ["python", "actions"]
    assert any("github/codeql-action/init@" in uses for uses in uses_steps)
    assert any("github/codeql-action/analyze@" in uses for uses in uses_steps)


def test_nightly_guardrails_preserves_scorecard_without_legacy_cloud_path() -> None:
    """Shared drift belongs to protected self-deploy, not generic token variables."""
    workflow = _workflow("nightly-guardrails.yml")
    assert set(workflow["jobs"]) == {"scorecard"}
    assert "PULUMI_ACCESS_TOKEN" not in str(workflow)
    assert "configure-aws-credentials" not in str(workflow)
    assert "test_post_apply_drift" in _workflow("self-deploy.yml")["jobs"]
    assert "prod_post_apply_drift" in _workflow("self-deploy.yml")["jobs"]


def test_new_guardrail_scripts_and_configs_are_present() -> None:
    """Keep the repo-local building blocks for CI guardrails discoverable."""
    preview_text = PREVIEW_SCRIPT.read_text(encoding="utf-8")
    preview_summary_text = PREVIEW_SUMMARY_SCRIPT.read_text(encoding="utf-8")
    drift_text = DRIFT_SCRIPT.read_text(encoding="utf-8")
    dockerfile_text = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert GITLEAKS_CONFIG.exists()
    assert PREVIEW_SUMMARY_SCRIPT.exists()
    assert "gh auth token" not in preview_text
    assert '"pulumi"' in preview_text
    assert '"--cwd"' in preview_text
    assert '"login"' in preview_text
    assert '"--non-interactive"' in preview_text
    assert "PULUMI_REQUIRE_SHARED_BACKEND" in preview_summary_text
    assert '"make", "test-preview"' in preview_summary_text
    assert "GITHUB_STEP_SUMMARY" in preview_summary_text
    assert '"preview"' in preview_text
    assert '"--stack"' in preview_text
    assert '"summarize"' in preview_text
    assert '"login"' in drift_text
    assert "PULUMI_DIR '" in drift_text
    assert "does not exist" in drift_text
    assert "Checking drift for stack" in drift_text
    assert "expect-no-changes" in drift_text
    assert "ARG TARGETARCH=amd64" not in dockerfile_text
    assert "actionlint" in dockerfile_text
    assert "gitleaks" in dockerfile_text


def test_guardrail_docs_are_indexed_from_root_docs() -> None:
    """Require operator docs for the new CI safety layer."""
    docs_index = (PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    root_readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    content = GUARDRAILS_DOC.read_text(encoding="utf-8")

    assert GUARDRAILS_DOC.exists()
    assert "ci-guardrails.md" in docs_index
    assert "docs/ci-guardrails.md" in root_readme
    assert "AWS_OIDC_ROLE_ARN" in content
    assert "<BRANCH_REF>" in content
    assert "allowed branch" in content
    assert "allow-destructive-infra-change" in content
    assert "CodeQL" in content
    assert "Gitleaks" in content


def test_new_workflows_keep_actions_pinned_to_full_shas() -> None:
    """Avoid drifting back to mutable action tags in the new workflows."""
    for workflow_name in (
        "pulumi-pr-guardrails.yml",
        "security-scans.yml",
        "codeql.yml",
        "nightly-guardrails.yml",
    ):
        workflow = _workflow(workflow_name)
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses is None:
                    continue
                assert ACTION_SHA_REF.match(uses), (
                    f"{workflow_name} must pin `{uses}` to a full commit SHA"
                )


def test_scheduled_drift_uses_only_protected_main_read_roles():
    """Scheduled runs cannot enter comment apply or promotion jobs."""
    workflow = _workflow("scheduled-drift.yml")
    dispatch = _workflow("self-deploy.yml")
    assert set(_triggers(workflow)) == {"schedule"}
    assert _triggers(workflow)["schedule"] == [{"cron": "17 3 * * *"}]
    assert set(_triggers(dispatch)) == {"repository_dispatch"}
    assert set(workflow["jobs"]) == {"scheduled_test_drift", "scheduled_prod_drift"}
    assert not set(workflow["jobs"]) & set(dispatch["jobs"])
    assert workflow["name"] == "Service Scheduled Drift"
    assert dispatch["name"] == "Service Self Deploy"
    assert workflow["concurrency"] == {
        "group": "pulumi-command-schedule",
        "cancel-in-progress": False,
    }
    assert "needs.preflight" not in str(workflow)
    assert "client_payload" not in str(workflow)
    assert (
        dispatch["jobs"]["preflight"]["if"]
        == "github.event_name == 'repository_dispatch'"
    )
    for environment in ("test", "prod"):
        job = workflow["jobs"][f"scheduled_{environment}_drift"]
        assert (
            job["if"]
            == "github.event_name == 'schedule' && github.ref == 'refs/heads/main'"
        )
        assert job["environment"] == f"{environment}-drift"
        assert "needs" not in job
        assert job["permissions"]["id-token"] == "write"
        steps = job["steps"]
        checkouts = [
            step
            for step in steps
            if step.get("uses", "").startswith("actions/checkout@")
        ]
        assert all(step["with"]["ref"] == "${{ github.sha }}" for step in checkouts)
        guard_index = next(
            i
            for i, step in enumerate(steps)
            if step.get("name")
            == "Verify trusted scheduled revision before credentials"
        )
        loader_index = next(
            i for i, step in enumerate(steps) if step.get("id") == "ci_config"
        )
        assert guard_index < loader_index
        loader = steps[loader_index]["with"]
        assert loader["environment"] == (
            "prod-preview" if environment == "prod" else "test"
        )
        role_variable = (
            "AWS_PROD_PREVIEW_CI_CONFIG_ROLE_ARN"
            if environment == "prod"
            else "AWS_TEST_CI_CONFIG_ROLE_ARN"
        )
        assert loader["config-role-arn"] == "${{ vars." + role_variable + " }}"
        assert "AWS_DRIFT_ROLE_ARN" in loader["required-keys"]
        assert "AWS_APPLY_ROLE_ARN" not in loader["required-keys"]
        role = next(
            step
            for step in steps
            if step.get("uses", "").startswith("aws-actions/configure-aws-credentials@")
        )
        assert (
            role["with"]["role-to-assume"]
            == "${{ steps.ci_config.outputs.aws-drift-role-arn }}"
        )
        assert (
            role["with"]["allowed-account-ids"]
            == "${{ vars.AWS_" + environment.upper() + "_ACCOUNT_ID }}"
        )
        assert steps[-1]["run"] == "make test-drift"
        assert "pulumi-up" not in str(job) and "deployments: write" not in str(job)


def test_pr_destructive_gates_exclude_scheduled_execution():
    """PR-head gates explicitly exclude schedule even before needs resolution."""
    jobs = _workflow("self-deploy.yml")["jobs"]
    dispatch = "github.event_name == 'repository_dispatch'"
    for environment in ("test", "prod"):
        job = jobs[f"{environment}_destructive_diff"]
        expected = dispatch
        if environment == "prod":
            expected += " && needs.preflight.outputs.target_environment == 'prod'"
        assert " ".join(job.get("if", "").split()) == expected
        assert "preflight" in job["needs"]
        assert f"{environment}_preview" in job["needs"]


def test_state_operations_share_cross_workflow_stack_mutex():
    """A cron drift and a PR state operation cannot hold the same stack at once."""
    load = _workflow
    workflows = {
        name: load(name) for name in ("self-deploy.yml", "scheduled-drift.yml")
    }
    operations = {"make pulumi-plan", "make pulumi-up-plan", "make test-drift"}
    state_jobs = {
        name: (workflow, job)
        for workflow in workflows.values()
        for name, job in workflow["jobs"].items()
        if any(step.get("run") in operations for step in job["steps"])
    }
    assert set(state_jobs) == {
        "test_preview",
        "test_apply",
        "test_post_apply_drift",
        "prod_preview",
        "prod_apply",
        "prod_post_apply_drift",
        "scheduled_test_drift",
        "scheduled_prod_drift",
    }
    groups = {}
    for name, (workflow, job) in state_jobs.items():
        environment = "test" if "test" in name else "prod"
        group = (
            "pulumi-state-${{ github.repository }}-" + environment + "-" + environment
        )
        assert job["concurrency"] == {"group": group, "cancel-in-progress": False}
        assert workflow["concurrency"]["group"] != group
        if name.startswith("scheduled_"):
            assert job["environment"] == environment + "-drift"
        else:
            assert job["environment"] in {environment, environment + "-preview"}
        groups.setdefault(environment, set()).add(group)
    assert len(groups["test"]) == len(groups["prod"]) == 1
    assert groups["test"].isdisjoint(groups["prod"])


@pytest.mark.parametrize(
    "job_id",
    [
        "test_preview",
        "test_apply",
        "test_post_apply_drift",
        "prod_preview",
        "prod_apply",
        "prod_post_apply_drift",
    ],
)
@pytest.mark.parametrize(
    "change,accepted",
    [
        ("none", True),
        ("retarget", False),
        ("base_moved", False),
        ("base_missing", False),
        ("head_moved", False),
        ("closed", False),
        ("merged", False),
        ("checkout_moved", False),
    ],
)
def test_credential_jobs_recheck_authenticated_pr_base(
    tmp_path, job_id, change, accepted
):
    """Execute each credential guard; moved PR metadata cannot reach credentials."""
    workflow = _workflow("self-deploy.yml")
    assert (
        workflow["jobs"]["preflight"]["outputs"]["base_sha"]
        == "${{ steps.resolve.outputs.base_sha }}"
    )
    steps = workflow["jobs"][job_id]["steps"]
    guard = next(
        s
        for s in steps
        if s.get("name") == "Recheck current PR head before credentials"
    )
    loader_index = next(
        i for i, s in enumerate(steps) if "load-aws-ci-env" in s.get("uses", "")
    )
    assert steps.index(guard) < loader_index
    assert (
        guard["env"]["EXPECTED_BASE_SHA"] == "${{ needs.preflight.outputs.base_sha }}"
    )
    assert guard["env"]["EXPECTED_SHA"] == "${{ needs.preflight.outputs.head_sha }}"
    head, base = "a" * 40, "b" * 40
    payload = {
        "state": "open",
        "merged": False,
        "head": {"sha": head},
        "base": {"ref": "main", "sha": base},
    }
    if change == "retarget":
        payload["base"]["ref"] = "unprotected"
    elif change == "base_moved":
        payload["base"]["sha"] = "c" * 40
    elif change == "base_missing":
        del payload["base"]
    elif change == "head_moved":
        payload["head"]["sha"] = "c" * 40
    elif change == "closed":
        payload["state"] = "closed"
    elif change == "merged":
        payload["merged"] = True
    response = tmp_path / "pr.json"
    response.write_text(json.dumps(payload))
    tools = tmp_path / "bin"
    tools.mkdir()
    for name, body in {
        "gh": 'cat "$PR_RESPONSE_FILE"',
        "git": 'printf "%s\\n" "$CHECKOUT_SHA"',
    }.items():
        tool = tools / name
        tool.write_text("#!/bin/sh\n" + body + "\n")
        tool.chmod(0o755)
    marker = tmp_path / "credentials-reached"
    result = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-e",
            "-o",
            "pipefail",
            "-c",
            guard["run"] + '\nprintf ready > "$CREDENTIAL_MARKER"',
        ],
        env={
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "GH_TOKEN": "synthetic",
            "GITHUB_REPOSITORY": "org/repo",
            "PR_NUMBER": "39",
            "PR_RESPONSE_FILE": str(response),
            "EXPECTED_SHA": head,
            "EXPECTED_BASE_SHA": base,
            "CHECKOUT_SHA": "c" * 40 if change == "checkout_moved" else head,
            "CREDENTIAL_MARKER": str(marker),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is accepted, result.stderr
    assert marker.exists() is accepted
