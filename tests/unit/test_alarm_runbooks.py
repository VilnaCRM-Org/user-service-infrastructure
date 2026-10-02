"""Every declared alarm has a runbook entry in ``docs/sre-operations.md`` (S2.4).

FR-13 and m18: each entry names the severity, the first responder, the
escalation, the containment action and the evidence to keep. The declared
alarms are the metric alarms of the rendered hardened TEST graph, and their
suffixes are also checked against the PRD §3.1 rows written out here.
N: an entry without severity, escalation or containment fails the doc test.
"""

import re
from pathlib import Path

import pytest
from test_poc_workload_phase import graph

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "sre-operations.md"
SECTION = "## Alarm Runbooks"
FIELDS = (
    "Severity",
    "First responder",
    "Escalation",
    "Containment",
    "Evidence to keep",
)
# PRD §3.1 metric rows as alarm suffixes (S2.4).
PRD_ALARMS = {
    "dlq-failed-send-email",
    "dlq-failed-domain-events",
    "dlq-failed-insert-user-batch",
    "alb-target-5xx",
    "alb-elb-5xx",
    "alb-unhealthy-targets",
    "ecs-web-below-desired",
    "ecs-worker-below-desired",
    "docdb-cpu",
    "docdb-freeable-memory",
    "redis-memory",
    "redis-evictions",
    "redis-auth-failures",
    "docdb-sts-calls",
}
ALARM = "aws:cloudwatch/metricAlarm:MetricAlarm"
PREFIX = "user-service-infrastructure-test-"


def _entries(text):
    """Map each ``### `suffix``` heading of the runbook section to its body."""
    start = text.index(SECTION) + len(SECTION)
    end = text.find("\n## ", start)
    section = text[start : None if end < 0 else end]
    parts = re.split(r"^### `([a-z0-9-]+)`\s*$", section, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def _violations(text, alarms):
    """Return every declared alarm whose runbook entry is missing or incomplete."""
    entries = _entries(text)
    found = [f"{alarm}: no entry" for alarm in sorted(alarms - set(entries))]
    for alarm in sorted(alarms & set(entries)):
        for field in FIELDS:
            pattern = rf"^- \*\*{re.escape(field)}:\*\* \S.*$"
            if not re.search(pattern, entries[alarm], flags=re.MULTILINE):
                found.append(f"{alarm}: {field}")
    return found


@pytest.fixture(scope="module")
def declared(tmp_path_factory):
    """The alarm suffixes the hardened TEST program declares."""
    receipt = graph(tmp_path_factory.mktemp("runbooks"), "hardened")
    assert receipt["error"] is None
    return {
        row["inputs"]["name"].removeprefix(PREFIX)
        for row in receipt["registrations"].values()
        if row["type"] == ALARM
    }


def test_the_program_declares_the_prd_alarms(declared):
    assert declared == PRD_ALARMS


def test_every_declared_alarm_has_a_complete_runbook_entry(declared):
    """FR-13 P: one complete entry per declared alarm, and no stray entry."""
    text = DOC.read_text()
    assert _violations(text, declared) == []
    assert set(_entries(text)) == PRD_ALARMS


def test_every_entry_escalates_to_a_named_owner():
    """m18: the first responder is the on-call owner; IAM events reach Kravalg."""
    entries = _entries(DOC.read_text())
    for alarm, body in entries.items():
        assert "- **First responder:** the service owner on call." in body, alarm
    assert "- **Escalation:** Kravalg" in entries["redis-auth-failures"]


@pytest.mark.parametrize("field", ["Severity", "Escalation", "Containment"])
def test_an_entry_without_a_required_field_fails(declared, field):
    """N: removing severity, escalation or containment from one entry fails."""
    text = DOC.read_text()
    changed = re.sub(
        rf"(### `docdb-cpu`\n(?:.*\n)*?)- \*\*{field}:\*\* .*\n",
        r"\1",
        text,
        count=1,
    )
    assert changed != text
    assert _violations(changed, declared) == [f"docdb-cpu: {field}"]


def test_an_alarm_without_an_entry_fails(declared):
    text = DOC.read_text().replace("### `redis-evictions`", "### `redis-other`")
    assert "redis-evictions: no entry" in _violations(text, declared)


def test_an_empty_field_fails(declared):
    text = DOC.read_text().replace(
        "- **Severity:** SEV-3 (SEV-2 when API latency", "- **Severity:** \n(", 1
    )
    assert "docdb-cpu: Severity" in _violations(text, declared)
