"""Trusted-only observation and distinct deployment issuance workflow boundaries."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def jobs():
    return yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())[
        "jobs"
    ]


@pytest.mark.parametrize("name", ["test_registry_observation", "test_registry_proof"])
def test_fresh_jobs_execute_only_trusted_main(name):
    job = jobs()[name]
    steps = job["steps"]
    assert {
        "preflight",
        "poc_prepare_source",
        "test_apply",
        "test_post_apply_drift",
    } <= set(job["needs"])
    assert "needs.preflight.outputs.command == 'up'" in job["if"]
    assert "needs.preflight.outputs.target_environment == 'test'" in job["if"]
    checkouts = [
        step for step in steps if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert len(checkouts) == 1
    assert checkouts[0]["with"] == {
        "ref": "${{ github.sha }}",
        "path": ".trusted",
        "persist-credentials": False,
    }
    for step in steps:
        script = step.get("run", "")
        assert "make " not in script and "poc_registry_runner.py" not in script
        assert "continue-on-error" not in step
        if script:
            assert '"${GITHUB_WORKSPACE}/.trusted/.venv/bin/python" -I' in script
            assert "${{" not in script


def test_observer_admits_before_both_credential_transitions():
    job = jobs()["test_registry_observation"]
    assert job["environment"] == "test-preview"
    assert job["concurrency"]["cancel-in-progress"] is False
    assert job["permissions"]["id-token"] == "write"
    steps = job["steps"]
    for index, step in enumerate(steps):
        if "load-aws-ci-env" in step.get("uses", "") or step.get("uses", "").startswith(
            "aws-actions/"
        ):
            assert steps[index - 1]["run"].rstrip().endswith(" admit")
    credentials = next(
        step for step in steps if step.get("uses", "").startswith("aws-actions/")
    )
    assert (
        credentials["with"]["role-to-assume"]
        == "${{ steps.ci_config.outputs.aws-preview-role-arn }}"
    )
    assert (
        credentials["with"]["role-session-name"]
        == "gha-pr-test-preview-${{ github.run_id }}"
    )
    upload = next(step for step in steps if step.get("id") == "observation_artifact")
    assert (
        upload["with"]["path"]
        == ".trusted/.artifacts/poc-registry-observation/observation.json"
    )
    assert (
        upload["with"]["overwrite"] is False
        and upload["with"]["if-no-files-found"] == "error"
    )
    assert "pulumi-plan" not in str(job) and "pulumi-preview/" not in str(job)


def test_proof_has_no_aws_or_full_promotion_authority():
    job = jobs()["test_registry_proof"]
    assert job["environment"] == "governance-evidence"
    assert "test_registry_observation" in job["needs"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.event_name == 'repository_dispatch'" in job["if"]
    assert (
        "github.repository == 'VilnaCRM-Org/user-service-infrastructure'" in job["if"]
    )
    assert "id-token" not in job["permissions"] and "statuses" not in job["permissions"]
    steps = job["steps"]
    token = next(step for step in steps if step.get("id") == "registry_app")
    assert set(token["with"]) == {"app-id", "private-key", "permission-deployments"}
    assert token["with"]["permission-deployments"] == "write"
    assert token["with"]["app-id"] == "${{ vars.GOVERNANCE_PROMOTION_APP_ID }}"
    assert steps[steps.index(token) - 1]["run"].rstrip().endswith(" prepare")
    assert (
        steps[-1]["env"]["REGISTRY_PROOF_APP_TOKEN"]
        == "${{ steps.registry_app.outputs.token }}"
    )
    assert job["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert not any(step.get("uses", "").startswith("aws-actions/") for step in steps)
    assert "governance_promotion.py" not in str(job)
    for field in ("ARTIFACT_ID", "ARCHIVE_SHA256", "FILE_SHA256"):
        assert (
            "needs.test_registry_observation.outputs."
            in job["env"][f"POC_OBSERVATION_{field}"]
        )


def test_completion_failure_remains_visible_in_result():
    job = jobs()["comment_result"]
    assert {"test_registry_observation", "test_registry_proof"} <= set(job["needs"])
    script = job["steps"][0]["run"]
    assert "needs.test_registry_observation.result" in script
    assert "needs.test_registry_proof.result" in script
