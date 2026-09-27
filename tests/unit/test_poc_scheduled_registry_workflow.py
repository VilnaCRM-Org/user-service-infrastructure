"""Schedule retains installed drift until an isolated diagnostic is admitted."""

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
    assert set(document["jobs"]) == {"scheduled_test_drift", "scheduled_prod_drift"}


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_schedule_does_not_dispatch_removed_controller_jobs(environment):
    job = workflow()["jobs"][f"scheduled_{environment}_drift"]
    assert (
        job["if"]
        == "github.event_name == 'schedule' && github.ref == 'refs/heads/main'"
    )
    assert job["environment"] == f"{environment}-drift"
    assert job["concurrency"] == {
        "group": "pulumi-state-${{ github.repository }}-"
        + f"{environment}-{environment}",
        "cancel-in-progress": False,
    }
    for key, value in job["permissions"].items():
        assert value == ("write" if key == "id-token" else "read")
    steps = job["steps"]
    assert steps[-2]["run"] == "make start"
    assert steps[-1]["run"] == "make test-drift"
    for step in steps:
        assert "continue-on-error" not in step
        assert "service_execution_host" not in str(step)
        assert "setup-service-execution" not in str(step)
        assert "poc_scheduled_registry_drift" not in str(step)
        assert "client_payload" not in str(step)
        assert "head_sha" not in str(step)
