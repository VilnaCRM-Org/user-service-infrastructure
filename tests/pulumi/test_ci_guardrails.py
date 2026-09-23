"""Structural tests for the AI-safe CI/CD guardrail layer."""

from __future__ import annotations

import importlib
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
    assert not any(
        job.startswith("prod_") for job in _workflow("self-deploy.yml")["jobs"]
    )


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
    assert "AWS_TEST_CI_CONFIG_ROLE_ARN" in content
    assert "Service Scheduled Drift" in content
    assert "credential-free previews" in content
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
    """The TEST diff gate requires dispatch and the disabled preview dependency."""
    jobs = _workflow("self-deploy.yml")["jobs"]
    assert "prod_destructive_diff" not in jobs
    job = jobs["test_destructive_diff"]
    assert job["if"] == "github.event_name == 'repository_dispatch'"
    assert job["needs"] == ["preflight", "test_preview"]
    assert "id-token" not in job.get("permissions", {})
    assert "configure-aws-credentials" not in str(job)
    assert "destructive-gate" in job["steps"][-1]["run"]


def test_test_controller_remains_fail_closed(tmp_path):
    """Installing the TEST graph cannot enable credentials or PROD execution."""
    workflow = _workflow("self-deploy.yml")
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "preflight",
        "poc_prepare_source",
        "test_preview",
        "test_destructive_diff",
        "test_apply",
        "test_post_apply_drift",
        "comment_result",
    }
    preflight = jobs["preflight"]
    assert "id-token" not in preflight["permissions"]
    assert "configure-aws-credentials" not in str(preflight)
    closure = preflight["steps"][-1]
    assert (
        closure["name"]
        == "Keep deployment closed pending complete controller validation"
    )
    assert "if" not in closure and "continue-on-error" not in closure
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", closure["run"]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "no AWS role is assumed" in result.stderr
    disabled = {
        "poc_prepare_source": "${{ false && success() }}",
        "test_preview": "${{ false && success() }}",
        "test_apply": "${{ false && needs.preflight.outputs.command == 'up' }}",
        "test_post_apply_drift": (
            "${{ false && needs.preflight.outputs.command == 'up' }}"
        ),
    }
    for name, condition in disabled.items():
        assert jobs[name]["if"] == condition
        assert "preflight" in jobs[name]["needs"]
    credential_jobs = {
        name
        for name, job in jobs.items()
        if job.get("permissions", {}).get("id-token") == "write"
        or "configure-aws-credentials" in str(job)
        or "load-aws-ci-env" in str(job)
    }
    assert credential_jobs == {"test_preview", "test_apply", "test_post_apply_drift"}
    assert "test_destructive_diff" in jobs["test_apply"]["needs"]
    assert "test_apply" in jobs["test_post_apply_drift"]["needs"]
    assert "all PR deployment remains disabled" in str(jobs["comment_result"])


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
        if any(
            operations.intersection(step.get("run", "").splitlines())
            or 'service_execution_host.py" execute' in step.get("run", "")
            for step in job["steps"]
        )
    }
    assert set(state_jobs) == {
        "test_preview",
        "test_apply",
        "test_post_apply_drift",
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


def _assert_credential_guards(steps):
    """Every credential hop immediately follows the isolated trusted recheck."""
    expected_guard = (
        '"${GITHUB_WORKSPACE}/.trusted/.venv/bin/python" -I '
        '"${GITHUB_WORKSPACE}/.trusted/scripts/service_execution_host.py" recheck'
    )
    for index, step in enumerate(steps):
        if "load-aws-ci-env" in step.get(
            "uses", ""
        ) or "configure-aws-credentials" in step.get("uses", ""):
            guard = steps[index - 1]
            assert (
                " ".join(guard["run"].replace(chr(92) + chr(10), " ").split())
                == expected_guard
            )
            assert "if" not in guard and "continue-on-error" not in guard


@pytest.mark.parametrize(
    "job_id",
    [
        "test_preview",
        "test_apply",
        "test_post_apply_drift",
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
    tmp_path, monkeypatch, job_id, change, accepted
):
    """Real host and review checks reject moved source before every credential hop."""
    workflow = _workflow("self-deploy.yml")
    assert (
        workflow["jobs"]["preflight"]["outputs"]["base_sha"]
        == "${{ steps.resolve.outputs.base_sha }}"
    )
    job = workflow["jobs"][job_id]
    steps = job["steps"]
    assert job["env"]["EXPECTED_BASE_SHA"] == "${{ needs.preflight.outputs.base_sha }}"
    assert job["env"]["REQUEST_HEAD_SHA"] == "${{ needs.preflight.outputs.head_sha }}"
    _assert_credential_guards(steps)
    checkout = steps[0]["with"]
    assert checkout == {
        "ref": "${{ github.sha }}",
        "path": ".trusted",
        "persist-credentials": False,
    }

    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    host = importlib.import_module("service_execution_host")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    base = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    head = "a" * 40
    monkeypatch.setattr(host, "ROOT", tmp_path)
    for key, value in {
        "GITHUB_JOB": job_id,
        "GITHUB_REPOSITORY": "org/repo",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": base,
        "GITHUB_WORKFLOW_SHA": base,
        "EXPECTED_BASE_SHA": base,
        "REQUEST_HEAD_SHA": head,
        "REQUEST_PULL_REQUEST_NUMBER": "39",
        "REQUEST_TARGET_ENVIRONMENT": "test",
        "REQUEST_COMMAND": "up",
        "REQUEST_COMMENT_ID": "123",
        "REQUEST_SOURCE_RUN_ID": "456",
    }.items():
        monkeypatch.setenv(key, value)
    if change == "checkout_moved":
        monkeypatch.setenv("GITHUB_SHA", "c" * 40)
        monkeypatch.setenv("GITHUB_WORKFLOW_SHA", "c" * 40)
    # Intake transport is covered by preflight tests; keep the real review and
    # installed-checkout validators in this workflow-to-host contract.
    requester_calls = []
    monkeypatch.setattr(host.preflight, "revalidate_requester", requester_calls.append)
    pr = {
        "number": 39,
        "state": "OPEN",
        "isDraft": False,
        "headRefOid": head,
        "baseRefOid": base,
        "baseRefName": "main",
        "reviewDecision": "APPROVED",
        "headRepository": {"nameWithOwner": "org/repo"},
        "baseRepository": {"nameWithOwner": "org/repo"},
        "author": {"__typename": "User", "id": "U_author", "login": "author"},
        "latestOpinionatedReviews": {
            "totalCount": 1,
            "pageInfo": {"hasNextPage": False, "hasPreviousPage": False},
            "nodes": [
                {
                    "id": "R_review",
                    "state": "APPROVED",
                    "commit": {"oid": head},
                    "author": {
                        "__typename": "User",
                        "id": "U_reviewer",
                        "login": "reviewer",
                    },
                }
            ],
        },
    }
    changes = {
        "retarget": ("baseRefName", "unprotected"),
        "base_moved": ("baseRefOid", "c" * 40),
        "head_moved": ("headRefOid", "c" * 40),
        "closed": ("state", "CLOSED"),
        "merged": ("state", "MERGED"),
    }
    if change in changes:
        key, value = changes[change]
        pr[key] = value
    elif change == "base_missing":
        del pr["baseRefOid"]

    def gh(path, *args):
        if path == "graphql":
            assert "number=39" in args
            return {
                "data": {"repository": {"nameWithOwner": "org/repo", "pullRequest": pr}}
            }
        if path == "repos/org/repo/rules/branches/main?per_page=100":
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
        assert path == "repos/org/repo/collaborators/reviewer/permission"
        return {
            "permission": "write",
            "user": {"node_id": "U_reviewer", "login": "reviewer", "type": "User"},
        }

    monkeypatch.setattr(host.preflight, "gh", gh)
    assert (host.main(["recheck"]) == 0) is accepted
    if change != "checkout_moved":
        assert len(requester_calls) == 1
        assert requester_calls[0]["head_sha"] == head
