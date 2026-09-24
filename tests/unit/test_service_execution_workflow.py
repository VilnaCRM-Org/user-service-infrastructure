"""Every credentialed execution path uses installed-main isolated execution."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ("self-deploy", "test_preview"),
    ("self-deploy", "test_apply"),
    ("self-deploy", "test_post_apply_drift"),
)


@pytest.mark.parametrize("filename,name", CASES)
def test_all_credentialed_jobs_build_before_credentials(filename, name):
    document = yaml.safe_load((ROOT / f".github/workflows/{filename}.yml").read_text())
    job = document["jobs"][name]
    steps = job["steps"]
    setup = next(
        s
        for s in steps
        if s.get("uses") == "./.trusted/.github/actions/setup-service-execution"
    )
    checkout = next(s for s in steps if s.get("with", {}).get("path") == ".trusted")
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    assert steps.index(checkout) < steps.index(setup)
    credentials = [
        s
        for s in steps
        if s.get("uses", "").startswith("aws-actions/")
        or s.get("uses", "").endswith("load-aws-ci-env")
    ]
    assert credentials and all(steps.index(setup) < steps.index(s) for s in credentials)
    executions = [
        s for s in steps if 'service_execution_host.py" execute' in s.get("run", "")
    ]
    assert len(executions) == 1
    assert all(steps.index(s) < steps.index(executions[0]) for s in credentials)
    for step in steps:
        assert "make " not in step.get("run", "")
        assert "continue-on-error" not in step
    assert job["permissions"]["actions"] == "read"
    assert job["permissions"]["id-token"] == "write"
    assert job["concurrency"]["cancel-in-progress"] is False
    assert "environment" in job


def test_test_only_dag_keeps_unvalidated_completion_and_prod_routes_absent():
    jobs = yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())[
        "jobs"
    ]
    assert "PROD promotion is unavailable" in str(jobs["poc_prepare_source"])
    assert "poc_prepare_source" in jobs["test_preview"]["needs"]
    assert "test_apply" in jobs["test_post_apply_drift"]["needs"]
    assert not any(name.startswith("prod_") for name in jobs)
    assert not any(name.startswith("test_registry_") for name in jobs)


def test_composite_uses_installed_tools_and_exact_build_recipe():
    action = yaml.safe_load(
        (ROOT / ".github/actions/setup-service-execution/action.yml").read_text()
    )
    assert "inputs" not in action
    steps = action["runs"]["steps"]
    assert steps[0]["uses"] == "./.trusted/.github/actions/setup-poc-runtime"
    assert len(steps) == 2 and steps[1]["shell"] == "bash"
    run = steps[1]["run"]
    assert run.count('"${GITHUB_WORKSPACE}/.trusted/.venv/bin/python" -I') == 2
    assert run.index("prepare") < run.index("build")
    assert not any(
        value in run for value in ("AWS_", "GH_TOKEN", "GITHUB_TOKEN", "make ")
    )
    recipe = (ROOT / "Dockerfile.service-execution").read_text()
    assert "ARG SERVICE_EXECUTION_BASE=service-execution-base" in recipe.splitlines()
    assert "FROM ${SERVICE_EXECUTION_BASE}" in recipe.splitlines()
    assert "USER root" in recipe.splitlines()
    assert "poc_provider_runtime.py install" in recipe
    assert "COPY scripts/poc_provider_runtime.py" in recipe
    assert "COPY pulumi" not in recipe and "COPY policy" not in recipe
