"""Workload apply ordering: process timeout <= STS session <= job timeout."""

import re
import sys
from pathlib import Path

import pytest
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


# FR-24 (N-04) gate-2 budget over recorded timing evidence. The bounds are the
# PRD literals: process <= 3000 s (3300 - 300), window <= 3300 s (3600 - 300).
def _budget():
    import poc_workload_runner as runner

    check = getattr(runner, "timing_within_budget", None)
    assert callable(check), "FR-24 timing budget check is missing"
    return check


def _evidence(oidc, start, end):
    day = "2026-10-01T"
    return {
        "oidc_issued_at": day + oidc + "Z",
        "runner_started_at": day + start + "Z",
        "observation_ended_at": day + end + "Z",
    }


def test_measured_times_within_margin_pass():
    """FR-24 P: a 40 min process inside a 45 min credential window passes."""
    assert _budget()(_evidence("10:00:00", "10:05:00", "10:45:00")) is True


def test_process_time_over_3000_seconds_blocks_gate_2():
    """FR-24 N: 3001 s process time blocks gate 2."""
    assert _budget()(_evidence("10:00:00", "10:00:00", "10:50:01")) is False


def test_credential_window_over_3300_seconds_blocks_gate_2():
    """FR-24 N: a 3301 s credential window blocks gate 2."""
    assert _budget()(_evidence("10:00:00", "10:05:01", "10:55:01")) is False


def test_exact_bounds_pass():
    """FR-24 B: exactly 3000 s process and 3300 s window pass."""
    assert _budget()(_evidence("10:00:00", "10:05:00", "10:55:00")) is True


@pytest.mark.parametrize(
    "fault",
    [
        {"oidc_issued_at": None},
        {"observation_ended_at": "2026-10-01 10:45:00"},
        {"runner_started_at": "2026-10-01T09:59:59Z"},
        {"observation_ended_at": "2026-10-01T10:04:59Z"},
    ],
)
def test_incomplete_or_disordered_evidence_is_refused(fault):
    record = _evidence("10:00:00", "10:05:00", "10:45:00")
    record.update(fault)
    with pytest.raises(ValueError, match="^timing-evidence-"):
        _budget()(record)
