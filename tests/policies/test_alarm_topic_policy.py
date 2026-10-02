"""The reviewed alarm TopicPolicy against the wildcard IAM guardrail (NFR-02).

S2.3 renders one ``sns:Publish`` allow per service publisher on the alarm
topic's own ARN. This boundary row proves that reviewed document passes
``wildcard_iam_violations`` without an allowlist, while a widened copy fails.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from app.observability import alarm_topic_policy

POLICY_DIR = Path(__file__).resolve().parents[2] / "policy"
TOPIC_POLICY = "aws:sns/topicPolicy:TopicPolicy"
ACCOUNT = "891377212104"
TOPIC_NAME = "user-service-infrastructure-test-alarms"
TOPIC_ARN = f"arn:aws:sns:eu-central-1:{ACCOUNT}:{TOPIC_NAME}"


@pytest.fixture
def guardrails(monkeypatch: pytest.MonkeyPatch):
    """Load the policy modules under their flat names, as the pack does."""
    modules = {}
    for name in ("config", "reviewed_iam", "guardrails"):
        spec = importlib.util.spec_from_file_location(name, POLICY_DIR / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules["guardrails"]


def _props(document):
    return {"arn": TOPIC_ARN, "policy": document}


def test_the_reviewed_topic_policy_passes_the_wildcard_guardrail(guardrails):
    """NFR-02 P: the reviewed document needs no wildcard allowlist."""
    document = alarm_topic_policy(TOPIC_ARN, ACCOUNT)
    assert guardrails.wildcard_iam_violations(TOPIC_POLICY, _props(document)) == []


@pytest.mark.parametrize(
    "change",
    [{"Action": "sns:*"}, {"Resource": "*"}],
)
def test_a_widened_topic_policy_fails_the_wildcard_guardrail(guardrails, change):
    """NFR-02 N: a wildcard action or resource is a violation."""
    document = alarm_topic_policy(TOPIC_ARN, ACCOUNT)
    document["Statement"][0].update(change)
    assert guardrails.wildcard_iam_violations(TOPIC_POLICY, _props(document))
