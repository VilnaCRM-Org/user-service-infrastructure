"""Admission and closed TEST-only workflow regression checks."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
JOBS = {"test_preview", "test_apply", "test_post_apply_drift"}


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())


def test_no_pr_code_or_production_route():
    jobs = workflow()["jobs"]
    assert set(jobs) == JOBS | {
        "preflight",
        "poc_prepare_source",
        "test_destructive_diff",
        "comment_result",
    }
    for job in jobs.values():
        for step in job["steps"]:
            assert "make " not in step.get("run", "")
            if step.get("uses", "").startswith("actions/checkout@"):
                assert (
                    step.get("with", {}).get("ref", "${{ github.sha }}")
                    == "${{ github.sha }}"
                )
                assert step["with"]["persist-credentials"] is False
            assert "AWS_ACCESS_KEY_ID" not in step.get("env", {})
    assert "test" in jobs["poc_prepare_source"]["steps"][0]["run"]


@pytest.mark.parametrize("job", sorted(JOBS))
def test_rechecks_before_each_oidc_stage_and_only_trusted_launch(job):
    document = workflow()["jobs"][job]
    assert document["permissions"]["id-token"] == "write"
    steps = document["steps"]
    install = next(
        i
        for i, step in enumerate(steps)
        if "setup-service-execution" in step.get("uses", "")
    )
    credentials = [
        i
        for i, step in enumerate(steps)
        if any(
            name in step.get("uses", "")
            for name in ("load-aws-ci-env", "configure-aws-credentials")
        )
    ]
    assert len(credentials) == 2
    for index in credentials:
        assert install < index
        assert any(
            'service_execution_host.py" recheck' in step.get("run", "")
            for step in steps[install + 1 : index]
        )
    launches = [
        step["run"]
        for step in steps
        if 'service_execution_host.py" execute' in step.get("run", "")
    ]
    assert len(launches) == 1
    assert '.trusted/.venv/bin/python" -I' in launches[0]
    assert (
        document["concurrency"]["group"]
        == "pulumi-state-${{ github.repository }}-test-test"
    )


def test_apply_reuses_same_run_artifacts_and_remains_environment_gated():
    jobs = workflow()["jobs"]
    assert jobs["test_apply"]["environment"] == "test"
    assert "command == 'up'" in jobs["test_apply"]["if"]
    assert set(jobs["test_apply"]["needs"]) >= {"test_preview", "test_destructive_diff"}
    downloads = [
        step["with"]
        for step in jobs["test_apply"]["steps"]
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert len(downloads) == 2
    assert all("run-id" not in row and "github-token" not in row for row in downloads)
    assert {row["path"] for row in downloads} == {
        ".trusted/.artifacts/pulumi-plan",
        ".trusted/.artifacts/pulumi-preview",
    }


def test_incomplete_installation_never_reaches_cloud_credentials():
    jobs = workflow()["jobs"]
    assert "exit 1" in jobs["preflight"]["steps"][-1]["run"]
    for name in JOBS | {"poc_prepare_source"}:
        assert "false" in jobs[name]["if"]
