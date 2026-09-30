"""The committed PoC phase must stay ``registry`` until hardening preconditions land."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRECONDITIONS = (
    "secret rotation (F-01)",
    "AWSCURRENT references instead of version pinning (F-02)",
    "autoscaling (F-03)",
    "alarms and SNS (F-04)",
    "network hardening incl. flow logs and egress (F-08)",
    "ALB-to-task TLS decision (F-09)",
    "CMK decision (F-14)",
    "cost and sustainability (F-15)",
    "worker healthcheck image fix (user-service PR #501)",
    "non-root image",
    "bootstrap governance grants for the new resources (N-11)",
    "N-04 apply timeout budget",
    "N-06 recovery runbook",
    "live TEST acceptance",
)
README_MARKERS = (
    "F-01",
    "F-02",
    "F-03",
    "F-04",
    "F-08",
    "F-09",
    "F-14",
    "F-15",
    "#501",
    "non-root",
    "N-11",
    "N-04",
    "N-06",
    "admission path (resume and abandon) for a non-registry TEST checkpoint",
    "sanitized operator-visible failure diagnostics",
    "real import path for fixed-name resources",
    "#57",
    "OIDC credential issuance to the end of result observation",
    "Live TEST acceptance",
)


def test_poc_test_phase_stays_registry_until_hardening_preconditions_are_met():
    phase = json.loads((ROOT / "specs/poc/poc-test.json").read_text())["phase"]
    assert phase == "registry", (
        "specs/poc/poc-test.json phase must stay 'registry' (fail-closed hard stop). "
        "Only the stacked hardening PR may change it, after these preconditions: "
        + "; ".join(PRECONDITIONS)
    )


def test_readme_lists_every_workload_phase_precondition():
    text = (ROOT / "specs/poc/README.md").read_text()
    section = " ".join(text.split("## Workload phase hard stop", 1)[1].split())
    missing = [marker for marker in README_MARKERS if marker not in section]
    assert missing == []
    assert "stacked hardening PR" in section
    assert "AWSCURRENT" in (ROOT / "specs/poc/secret-lifecycle.md").read_text()
