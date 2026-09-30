"""The TEST apply job must outlast a first create of the whole workload stack."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
# Worst-case first-create provisioning budget in minutes, mirrored by the
# arithmetic comment above the job's timeout-minutes in self-deploy.yml.
PROVISIONING_MINUTES = {
    "network (2 NAT gateways, ALB)": 15,
    "DocumentDB cluster and 2 instances": 25,
    "Redis multi-AZ with replica": 20,
    "setup, plan replay and checks": 10,
}
STEADY_STATE_WAITS = 2  # web and worker services, assumed serial


def _workflow_text_and_timeout():
    path = ROOT / ".github/workflows/self-deploy.yml"
    jobs = yaml.safe_load(path.read_text())["jobs"]
    return path.read_text(), jobs["test_apply"]["timeout-minutes"]


def test_test_apply_timeout_covers_bounded_waits_and_provisioning():
    from app.compute import SERVICE_STEADY_STATE_MINUTES, SERVICE_STEADY_STATE_TIMEOUT

    assert SERVICE_STEADY_STATE_TIMEOUT == f"{SERVICE_STEADY_STATE_MINUTES}m"
    _, timeout = _workflow_text_and_timeout()
    budget = STEADY_STATE_WAITS * SERVICE_STEADY_STATE_MINUTES + sum(
        PROVISIONING_MINUTES.values()
    )
    assert timeout >= budget, (
        f"test_apply timeout-minutes={timeout} is below the first-create budget "
        f"of {budget} minutes"
    )


def test_test_apply_timeout_arithmetic_is_documented_in_workflow():
    text, timeout = _workflow_text_and_timeout()
    assert f"= {timeout}." in text
    assert "test_apply_timeout_budget" in text
