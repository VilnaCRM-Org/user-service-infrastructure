"""Workload apply ordering: process timeout <= STS session <= job timeout."""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

DEFAULT_STS_SECONDS = 3600  # role default when no role-duration-seconds is set
MARGIN_SECONDS = 300  # process timeout must leave this much below the STS session
JOB_SETUP_MARGIN_MINUTES = 10  # setup, plan replay and checks around the apply
WORKFLOW = ROOT / ".github/workflows/self-deploy.yml"


def _job():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["test_apply"]


def _sts_seconds(job):
    """Return the explicit role-duration-seconds of the apply OIDC step, else 3600."""
    for step in job["steps"]:
        uses = step.get("uses", "")
        if uses.startswith("aws-actions/configure-aws-credentials"):
            return int(step.get("with", {}).get("role-duration-seconds", 3600))
    raise AssertionError("apply job has no OIDC credentials step")


def test_workload_up_process_timeout_is_explicit_and_below_sts_session():
    import service_execution_process as process

    assert process.APPLY_TIMEOUT_SECONDS == 3300
    assert process.DEFAULT_TIMEOUT_SECONDS == 1200
    assert process.APPLY_TIMEOUT_SECONDS <= DEFAULT_STS_SECONDS - MARGIN_SECONDS


def test_transport_passes_apply_timeout_only_to_up(monkeypatch):
    import service_execution_process as process
    import service_execution_transport as transport

    source = (ROOT / "scripts/service_execution_transport.py").read_text()
    assert "timeout=self._timeout(command, child)" in source
    assert 'command[3:4] == ["up"]' in source
    assert transport.APPLY_TIMEOUT_SECONDS is process.APPLY_TIMEOUT_SECONDS


def test_sts_duration_covers_process_timeout():
    import service_execution_process as process

    assert _sts_seconds(_job()) >= process.APPLY_TIMEOUT_SECONDS + MARGIN_SECONDS


def test_job_timeout_covers_process_timeout_plus_setup_margin():
    import service_execution_process as process

    job_seconds = _job()["timeout-minutes"] * 60
    assert job_seconds >= _sts_seconds(_job())
    assert job_seconds >= (
        process.APPLY_TIMEOUT_SECONDS + JOB_SETUP_MARGIN_MINUTES * 60
    )


def test_steady_state_bound_is_documented_next_to_the_ordering():
    from app.compute import SERVICE_STEADY_STATE_MINUTES, SERVICE_STEADY_STATE_TIMEOUT

    assert SERVICE_STEADY_STATE_TIMEOUT == f"{SERVICE_STEADY_STATE_MINUTES}m"
    compute = (ROOT / "pulumi/app/compute.py").read_text()
    assert "3300 s" in compute and "MaxSessionDuration" in compute


def test_workflow_documents_ordering_hard_stop_and_shared_concurrency():
    text = WORKFLOW.read_text()
    assert re.search(r"3300 s.*<=.*3600 s.*<=.*job timeout", text, re.S)
    assert "MaxSessionDuration" in text
    assert "test_apply_timeout_budget" in text
    assert "scheduled-drift.yml" in text and "pending" in text
    assert "measured" in text
