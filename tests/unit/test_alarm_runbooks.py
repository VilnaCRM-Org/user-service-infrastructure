"""Every declared alarm has a runbook entry in ``docs/sre-operations.md`` (S2.4).

FR-13 and m18: each entry names the severity, the first responder, the
escalation, the containment action and the evidence to keep. The declared
alarms are the metric alarms of the rendered hardened TEST graph, and their
suffixes are also checked against the PRD §3.1 rows written out here.
N: an entry without severity, escalation or containment fails the doc test.
Gate fixes: each entry records its alarm's missing-data mode (F3), no
containment uses a ``policy-update`` plan outside the FR-07 set (F4), the PROD
stop rule is kept, and the V-11 and V-25 cases carry their full fallback (I3).
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
    "Missing data",
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
def rendered(tmp_path_factory):
    """The inputs of each metric alarm the hardened TEST program declares."""
    receipt = graph(tmp_path_factory.mktemp("runbooks"), "hardened")
    assert receipt["error"] is None
    return {
        row["inputs"]["name"].removeprefix(PREFIX): row["inputs"]
        for row in receipt["registrations"].values()
        if row["type"] == ALARM
    }


@pytest.fixture(scope="module")
def declared(rendered):
    """The alarm suffixes the hardened TEST program declares."""
    return set(rendered)


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


# Gate F3: the missing-data mode of each alarm, written from the gate scope.
MISSING_DATA = {
    "dlq-failed-send-email": "notBreaching",
    "dlq-failed-domain-events": "notBreaching",
    "dlq-failed-insert-user-batch": "notBreaching",
    "alb-target-5xx": "notBreaching",
    "alb-elb-5xx": "notBreaching",
    "alb-unhealthy-targets": "notBreaching",
    "ecs-web-below-desired": "notBreaching",
    "ecs-worker-below-desired": "notBreaching",
    "docdb-cpu": "breaching",
    "docdb-freeable-memory": "breaching",
    "redis-memory": "missing",
    "redis-evictions": "notBreaching",
    "redis-auth-failures": "notBreaching",
    "docdb-sts-calls": "missing",
}


def _missing_data_modes(text):
    """Map each entry to the mode its ``Missing data`` line names, with a reason."""
    modes = {}
    for alarm, body in _entries(text).items():
        match = re.search(
            r"^- \*\*Missing data:\*\* `(\w+)`: \S.*$", body, flags=re.MULTILINE
        )
        modes[alarm] = match.group(1) if match else None
    return modes


def test_each_entry_records_the_declared_missing_data_mode(rendered):
    """F3 P: the runbook names the mode the alarm declares, and gives a reason."""
    modes = _missing_data_modes(DOC.read_text())
    assert modes == MISSING_DATA
    assert {
        alarm: inputs["treatMissingData"] for alarm, inputs in rendered.items()
    } == MISSING_DATA


def test_a_changed_missing_data_line_fails():
    """F3 N: an entry that names another mode differs from the declaration."""
    text = DOC.read_text().replace(
        "- **Missing data:** `breaching`: every instance",
        "- **Missing data:** `notBreaching`: every instance",
        1,
    )
    assert _missing_data_modes(text) != MISSING_DATA


# FR-07: ``policy-update`` admits one ``update`` of the managed-secret
# ``SecretPolicy`` or a ``VpcEndpoint`` policy, and nothing else.
POLICY_UPDATE_TARGETS = ("`SecretPolicy`", "`VpcEndpoint`")


def _containments(text):
    return {
        alarm: re.search(r"^- \*\*Containment:\*\* (.*)$", body, re.MULTILINE).group(1)
        for alarm, body in _entries(text).items()
    }


def _policy_update_violations(text):
    """Return each containment that uses ``policy-update`` outside the FR-07 set."""
    return sorted(
        alarm
        for alarm, line in _containments(text).items()
        if "`policy-update`" in line
        and not any(target in line for target in POLICY_UPDATE_TARGETS)
    )


def test_no_containment_uses_a_policy_update_outside_fr07():
    """F4 P: a ``policy-update`` plan appears only for an FR-07 policy."""
    assert _policy_update_violations(DOC.read_text()) == []


def test_a_policy_update_for_a_security_group_fails():
    """F4 N: the rejected security-group containment is found."""
    text = DOC.read_text().replace(
        "remove its network or IAM path by a reviewed PR",
        "close its security-group path by a `policy-update` plan",
        1,
    )
    assert _policy_update_violations(text) == ["redis-auth-failures"]


PROD_STOP_RULE = (
    "- A containment that stops PROD (the `rollback-zero` stop plan) records the\n"
    "  incident reason in the stop PR (AD-10)."
)


def _prod_stop_violations(text):
    """Return what breaks the AD-10 rule: a stop without the incident reason."""
    found = [] if PROD_STOP_RULE in text else ["rule"]
    found += sorted(
        alarm
        for alarm, line in _containments(text).items()
        if "`rollback-zero`" in line and "incident reason" not in line
    )
    return found


def test_the_prod_stop_records_the_incident_reason():
    """AD-10 P: the rule is kept and every PROD stop records the reason."""
    assert _prod_stop_violations(DOC.read_text()) == []


def test_a_prod_stop_without_the_incident_reason_fails():
    """AD-10 N: dropping the rule or one entry's reason is found."""
    text = DOC.read_text()
    assert _prod_stop_violations(text.replace(PROD_STOP_RULE, "")) == ["rule"]
    changed = text.replace(
        "apply the `rollback-zero` stop plan and record the incident reason (AD-10).",
        "apply the `rollback-zero` stop plan.",
    )
    assert "alb-target-5xx" in _prod_stop_violations(changed)


def _case(text, name):
    """Return the docs-verified case ``name`` (V-11 or V-25) as one line."""
    match = re.search(rf"^- \*\*{name}:\*\* (.*?)(?=^- |^###)", text, re.M | re.S)
    assert match is not None
    return " ".join(match.group(1).split())


def test_v25_records_the_full_fallback():
    """I3: both fallback parts, their installer, slot and the step-7 re-run."""
    case = _case(DOC.read_text(), "V-25")
    for part in (
        "`kms:GenerateDataKey`",
        "`Modify` rows on the execution role's policy",
        "`-Boundary` and `-Guard` policies",
        "XP-17 installer",
        "runtime-CMK key-policy statement",
        "row-43 serialization slot",
        "step 7 is re-run",
    ):
        assert part in case, part


def test_v11_checks_the_alarm_dimension():
    """I3: the live V-11 check confirms data at ``DBClusterIdentifier``."""
    case = _case(DOC.read_text(), "V-11")
    assert "`DBClusterIdentifier` dimension" in case
    assert "user-service-infrastructure-test-docdb" in case
