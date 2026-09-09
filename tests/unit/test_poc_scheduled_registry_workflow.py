"""Scheduled TEST uses trusted runtime and a diagnostic-only registry command."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/scheduled-drift.yml").read_text())


def test_schedule_has_no_dispatch_input_or_pr_revision_authority():
    document = workflow()
    assert set(document[True]) == {"schedule"}
    assert document["name"] == "Service Scheduled Drift"
    job = document["jobs"]["scheduled_test_drift"]
    assert (
        job["if"]
        == "github.event_name == 'schedule' && github.ref == 'refs/heads/main'"
    )
    assert job["environment"] == "test-drift"
    assert job["permissions"]["actions"] == "read"
    assert all(
        value != "write"
        for key, value in job["permissions"].items()
        if key != "id-token"
    )
    assert "continue-on-error" not in job
    assert job["concurrency"] == {
        "group": "pulumi-state-${{ github.repository }}-test-test",
        "cancel-in-progress": False,
    }


def test_trusted_dependencies_and_native_provenance_precede_all_credentials():
    steps = workflow()["jobs"]["scheduled_test_drift"]["steps"]
    assert len(steps) == 6
    checkout, setup, verify, config, credentials, check = steps
    assert (
        checkout["uses"] == "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"
    )
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "path": ".trusted",
        "persist-credentials": False,
    }
    assert setup["uses"] == "./.trusted/.github/actions/setup-poc-runtime"
    assert config["uses"] == "./.trusted/.github/actions/load-aws-ci-env"
    assert config["with"]["environment"] == "test"
    assert config["with"]["expected-account-id"] == "${{ vars.AWS_TEST_ACCOUNT_ID }}"
    assert "AWS_DRIFT_ROLE_ARN" in config["with"]["required-keys"]
    assert (
        credentials["uses"] == "aws-actions/configure-aws-credentials@"
        "8df5847569e6427dd6c4fb1cf565c83acfa8afa7"
    )
    assert (
        credentials["with"]["role-to-assume"]
        == "${{ steps.ci_config.outputs.aws-drift-role-arn }}"
    )
    assert (
        credentials["with"]["role-session-name"]
        == "gha-scheduled-test-drift-${{ github.run_id }}"
    )
    assert (
        credentials["with"]["allowed-account-ids"] == "${{ vars.AWS_TEST_ACCOUNT_ID }}"
    )
    for step, command in ((verify, "verify"), (check, "check")):
        assert step["env"] == {"GH_TOKEN": "${{ github.token }}"}
        assert (
            step["run"].strip().endswith(f'poc_scheduled_registry_drift.py" {command}')
        )
        assert " -I " in step["run"]
    for step in steps:
        assert "if" not in step and "continue-on-error" not in step
        for forbidden in (
            "make ",
            "uv sync",
            "uv run",
            "client_payload",
            "head_sha",
            "SourceAdmission",
            "--artifact-id",
        ):
            assert forbidden not in str(step)


@pytest.mark.parametrize("command", ["verify", "check"])
@pytest.mark.parametrize("status", [0, 17])
def test_real_workflow_wrapper_preserves_isolated_cli_and_failure(
    tmp_path, command, status
):
    steps = workflow()["jobs"]["scheduled_test_drift"]["steps"]
    step = next(
        step for step in steps if step.get("run", "").strip().endswith(f" {command}")
    )
    workspace = tmp_path / "workspace with spaces"
    interpreter = workspace / ".trusted/.venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text(
        "#!/bin/bash\n"
        'test "$#" = 3 || exit 90\n'
        'test "$1" = -I || exit 91\n'
        'test "$2" = "${GITHUB_WORKSPACE}/.trusted/scripts/'
        'poc_scheduled_registry_drift.py" || exit 92\n'
        'test "$3" = "${EXPECTED_COMMAND}" || exit 93\n'
        'exit "${EXPECTED_STATUS}"\n'
    )
    interpreter.chmod(0o700)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={
            "PATH": os.defpath,
            "GITHUB_WORKSPACE": str(workspace),
            "EXPECTED_COMMAND": command,
            "EXPECTED_STATUS": str(status),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == status, result.stderr


def test_prod_route_remains_distinct_and_has_no_registry_diagnostic():
    job = workflow()["jobs"]["scheduled_prod_drift"]
    assert job["environment"] == "prod-drift"
    assert (
        job["concurrency"]["group"] == "pulumi-state-${{ github.repository }}-prod-prod"
    )
    assert "poc_scheduled_registry_drift" not in str(job)
