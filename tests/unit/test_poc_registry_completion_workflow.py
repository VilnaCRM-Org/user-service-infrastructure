"""Keep TEST registry proof dependent on a fresh native observation."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def jobs():
    return yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())[
        "jobs"
    ]


def test_observation_requires_successful_test_apply_and_drift():
    graph = jobs()
    observer = graph["test_registry_observation"]
    assert observer["needs"] == [
        "preflight",
        "poc_prepare_source",
        "test_post_apply_drift",
    ]
    assert "command == 'up'" in observer["if"]
    assert "target_environment == 'test'" in observer["if"]
    assert observer["environment"] == "test-preview"
    assert observer["permissions"] == {
        "contents": "read",
        "actions": "read",
        "id-token": "write",
        "pull-requests": "read",
    }
    assert observer["concurrency"]["cancel-in-progress"] is False
    assert (
        observer["concurrency"]["group"]
        == graph["test_post_apply_drift"]["concurrency"]["group"]
    )
    assert observer["env"]["POC_SOURCE_ARTIFACT_ID"] == (
        "${{ needs.poc_prepare_source.outputs.artifact_id }}"
    )
    assert observer["outputs"]["archive_sha256"] == (
        "${{ steps.observation_artifact.outputs.artifact-digest }}"
    )
    steps = observer["steps"]
    assert steps[0]["with"]["ref"] == "${{ github.sha }}"
    assert steps[0]["with"]["persist-credentials"] is False
    assert steps[1]["uses"] == "./.trusted/.github/actions/setup-poc-runtime"
    assert 'poc_registry_completion.py" admit' in steps[2]["run"]
    assert 'poc_registry_completion.py" admit' in steps[4]["run"]
    assert steps[5]["with"]["role-session-name"] == (
        "gha-pr-test-preview-${{ github.run_id }}"
    )
    assert steps[6]["working-directory"] == ".trusted"
    assert "poc_registry_completion.py observe" in steps[6]["run"]
    assert steps[7]["with"]["retention-days"] == 7
    assert all("service_execution_host.py" not in step.get("run", "") for step in steps)
    assert all(
        "actions/create-github-app-token@" not in step.get("uses", "") for step in steps
    )


def test_proof_uses_protected_issuer_without_full_promotion_status():
    graph = jobs()
    proof = graph["test_registry_proof"]
    assert proof["needs"] == [
        "preflight",
        "poc_prepare_source",
        "test_registry_observation",
    ]
    assert proof["if"] == ("${{ needs.test_registry_observation.result == 'success' }}")
    assert proof["environment"] == "governance-evidence"
    assert proof["permissions"] == {
        "actions": "read",
        "contents": "read",
        "deployments": "read",
        "pull-requests": "read",
    }
    assert "id-token" not in proof["permissions"]
    assert proof["env"]["POC_OBSERVATION_ARTIFACT_ID"] == (
        "${{ needs.test_registry_observation.outputs.artifact_id }}"
    )
    assert proof["env"]["POC_OBSERVATION_ARCHIVE_SHA256"] == (
        "${{ needs.test_registry_observation.outputs.archive_sha256 }}"
    )
    assert proof["env"]["POC_OBSERVATION_FILE_SHA256"] == (
        "${{ needs.test_registry_observation.outputs.file_sha256 }}"
    )
    steps = proof["steps"]
    assert steps[0]["with"]["ref"] == "${{ github.sha }}"
    assert steps[0]["with"]["persist-credentials"] is False
    assert steps[1]["uses"] == "./.trusted/.github/actions/setup-poc-runtime"
    assert "poc_registry_completion.py prepare" in steps[2]["run"]
    token = steps[3]
    assert token["with"]["permission-deployments"] == "write"
    assert token["with"]["permission-actions"] == "read"
    assert "permission-statuses" not in token["with"]
    assert "REGISTRY_PROOF_APP_TOKEN" in steps[4]["env"]
    assert "poc_registry_completion.py publish" in steps[4]["run"]
    assert proof["outputs"]["receipt_id"] == (
        "${{ steps.publish.outputs.registry_phase_receipt_id }}"
    )
    assert "Governance Promotion" not in str(proof)


def test_image_dispatch_and_workload_execution_stay_closed():
    graph = jobs()
    assert "test_registry_dispatch" not in graph
    assert "test_workload_apply" not in graph
    assert all("poc_publisher_dispatch.py" not in str(job) for job in graph.values())
    result = graph["comment_result"]
    assert "test_registry_observation" in result["needs"]
    assert "test_registry_proof" in result["needs"]
    assert "TEST registry proof" in result["steps"][0]["run"]
