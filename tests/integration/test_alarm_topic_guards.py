"""Fail-closed guards of the S2.3 alarm topic in the integration suite.

The integration coverage gate includes ``pulumi/app``. The hardened graph
renders only the reviewed topic, so these cases drive the refusals directly:
an AWS-managed or malformed key (D-4, D-8), a malformed account or topic ARN,
and every policy shape that is not the reviewed FR-13 document.
"""

import pytest
from app.observability import (
    alarm_topic_arn,
    alarm_topic_policy,
    require_reviewed_topic_policy,
    require_runtime_cmk,
)

ACCOUNT = "891377212104"
TOPIC_ARN = alarm_topic_arn(
    "eu-central-1", ACCOUNT, "user-service-infrastructure-test-alarms"
)


@pytest.mark.parametrize(
    ("key", "message"),
    [
        ("alias/aws/sns", "AWS-managed key"),
        (None, "runtime CMK key ARN"),
        ("alias/synthetic-runtime", "runtime CMK key ARN"),
    ],
)
def test_only_a_customer_managed_key_arn_can_encrypt_the_topic(key, message):
    with pytest.raises(ValueError, match=message):
        require_runtime_cmk(key)


@pytest.mark.parametrize("account", [None, "12345", "*"])
def test_the_topic_arn_requires_the_workload_account(account):
    with pytest.raises(ValueError, match="workload account ID"):
        alarm_topic_arn("eu-central-1", account, "alarms")


@pytest.mark.parametrize(
    "topic_arn", ["*", "arn:aws:sns:eu-central-1:000000000000:alarms"]
)
def test_the_policy_is_reviewed_only_against_a_topic_in_the_account(topic_arn):
    policy = alarm_topic_policy(topic_arn, ACCOUNT)
    with pytest.raises(ValueError, match="topic ARN in the account"):
        require_reviewed_topic_policy(policy, ACCOUNT, topic_arn)


def _changed(**changes):
    policy = alarm_topic_policy(TOPIC_ARN, ACCOUNT)
    policy["Statement"][0].update(changes)
    return policy


@pytest.mark.parametrize(
    ("policy", "message"),
    [
        ({"Statement": "not-a-list"}, "not a statement list"),
        (_changed(NotAction="sns:Publish"), "unreviewed publisher"),
        (_changed(Principal="*"), "unreviewed publisher"),
        (_changed(Resource="*"), "unreviewed publisher"),
        (_changed(Principal={"Service": "sns.amazonaws.com"}), "unreviewed publisher"),
    ],
)
def test_an_unreviewed_topic_policy_cannot_reach_the_topic(policy, message):
    with pytest.raises(ValueError, match=message):
        require_reviewed_topic_policy(policy, ACCOUNT, TOPIC_ARN)


def test_the_reviewed_topic_policy_is_accepted():
    policy = alarm_topic_policy(TOPIC_ARN, ACCOUNT)
    assert require_reviewed_topic_policy(policy, ACCOUNT, TOPIC_ARN) is policy
