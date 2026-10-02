"""Owned alarm SNS topic (S2.3): runtime CMK and the publish policy.

FR-10 and D-8 bind the topic to the D-4 runtime CMK (CloudWatch alarms cannot
publish to an ``alias/aws/sns`` topic). FR-13 lets only CloudWatch and
EventBridge publish, each with ``aws:SourceAccount`` equal to the workload
account. The subscription endpoint is XP-6, so the graph holds none.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pulumi_aws as aws
import pytest
from app.observability import (
    ALARM_TOPIC_PUBLISHERS,
    AlarmTargets,
    ObservabilityPlane,
    alarm_topic_policy,
    require_reviewed_topic_policy,
    require_runtime_cmk,
)
from app.workload_phase import _reject_secret_material
from pulumi.runtime import mocks, settings, stack
from test_poc_workload_phase import TAGS, graph
from test_runtime_secrets import _transform_args
from test_workload_step_one import JWT_CMK, RUNTIME_CMK, _secret, _unresolved

TOPIC = "aws:sns/topic:Topic"
TOPIC_POLICY = "aws:sns/topicPolicy:TopicPolicy"
ACCOUNT = "891377212104"
TOPIC_NAME = "user-service-infrastructure-test-alarms"
TOPIC_ARN = f"arn:aws:sns:eu-central-1:{ACCOUNT}:{TOPIC_NAME}"
# FR-13 names exactly these publishers; the literal keeps the code honest.
PUBLISHERS = {"cloudwatch.amazonaws.com", "events.amazonaws.com"}


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("observability"), "hardened")
    assert receipt["error"] is None
    return list(receipt["registrations"].values())


def _only(rows, kind):
    matches = [row for row in rows if row["type"] == kind]
    assert len(matches) == 1
    return matches[0]


def test_the_hardened_graph_declares_one_topic_on_the_runtime_cmk(rows):
    """FR-13 P (D-4, D-8): one tagged topic whose key is the runtime CMK."""
    topic = _only(rows, TOPIC)
    assert topic["inputs"]["kmsMasterKeyId"] == RUNTIME_CMK
    assert topic["inputs"]["name"] == TOPIC_NAME
    assert topic["inputs"]["tags"] == TAGS
    plane = _only(rows, "user-service-infrastructure:observability:Plane")
    assert topic["parent"] == plane["urn"]
    # XP-6: the subscription endpoint is not known, so none is declared.
    assert not [row for row in rows if row["type"].startswith("aws:sns/topicSub")]
    # An inline topic ``policy`` would bypass the reviewed TopicPolicy.
    assert "policy" not in topic["inputs"]


def test_the_publisher_constant_names_exactly_the_reviewed_publishers():
    """FR-13: a third publisher in the constant fails the suite."""
    assert set(ALARM_TOPIC_PUBLISHERS) == PUBLISHERS
    assert len(ALARM_TOPIC_PUBLISHERS) == 2


def test_the_topic_policy_allows_only_the_two_publishers_in_the_account(rows):
    """FR-13 P: each allow names one service principal and the account."""
    policy = _only(rows, TOPIC_POLICY)["inputs"]
    assert policy["arn"] == TOPIC_ARN
    document = json.loads(policy["policy"])
    statements = document["Statement"]
    assert len(statements) == 2
    assert {s["Principal"]["Service"] for s in statements} == PUBLISHERS
    for statement in statements:
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == "sns:Publish"
        assert statement["Resource"] == TOPIC_ARN
        assert statement["Condition"] == {
            "StringEquals": {"aws:SourceAccount": ACCOUNT}
        }
    assert require_reviewed_topic_policy(document, ACCOUNT, TOPIC_ARN) == document


def _statement(index=0, **changes):
    policy = alarm_topic_policy(TOPIC_ARN, ACCOUNT)
    policy["Statement"][index].update(changes)
    return policy


def _without_condition():
    policy = alarm_topic_policy(TOPIC_ARN, ACCOUNT)
    del policy["Statement"][1]["Condition"]
    return policy


@pytest.mark.parametrize(
    "policy",
    [
        # FR-13 N: an allow without the ``aws:SourceAccount`` condition.
        _without_condition(),
        _statement(Condition={}),
        _statement(Condition={"StringEquals": {"aws:SourceAccount": "000000000000"}}),
        _statement(Condition={"StringLike": {"aws:SourceAccount": ACCOUNT}}),
        # Any other or wildcard principal.
        _statement(Principal="*"),
        _statement(Principal={"AWS": "*"}),
        _statement(Principal={"Service": "*"}),
        _statement(Principal={"Service": "sns.amazonaws.com"}),
        _statement(Principal={"Service": "events.amazonaws.com", "AWS": "*"}),
        # The same publisher with an extra principal key fails on its own.
        _statement(Principal={"Service": "cloudwatch.amazonaws.com", "AWS": "*"}),
        _statement(Principal=None),
        _statement(Principal=7),
        # Another or a wildcard resource.
        _statement(Resource="*"),
        _statement(Resource=f"{TOPIC_ARN}-other"),
        # Another action, a deny, an extra key or a repeated publisher.
        _statement(Action="sns:*"),
        _statement(Effect="Deny"),
        _statement(NotPrincipal={"AWS": "*"}),
        _statement(Principal={"Service": "events.amazonaws.com"}),
        {"Statement": alarm_topic_policy(TOPIC_ARN, ACCOUNT)["Statement"][:1]},
        {
            "Statement": [
                *alarm_topic_policy(TOPIC_ARN, ACCOUNT)["Statement"],
                "statement",
            ]
        },
        {"Statement": {}},
        [],
    ],
)
def test_an_unreviewed_topic_policy_fails_closed(policy):
    """FR-13 N: the suite detects every policy that is not the reviewed one."""
    with pytest.raises(ValueError, match="Alarm topic policy"):
        require_reviewed_topic_policy(policy, ACCOUNT, TOPIC_ARN)


@pytest.mark.parametrize(
    "topic_arn",
    [None, "*", "", f"arn:aws:sns:eu-central-1:000000000000:{TOPIC_NAME}"],
)
def test_the_reviewed_policy_requires_the_topic_arn_in_the_account(topic_arn):
    """FR-13 N: a policy reviewed against no topic or another account fails."""
    policy = alarm_topic_policy(topic_arn, ACCOUNT)
    with pytest.raises(ValueError, match="Alarm topic"):
        require_reviewed_topic_policy(policy, ACCOUNT, topic_arn)


@pytest.mark.parametrize("account", [None, "", "12345678901", "*", 891377212104])
def test_the_topic_policy_requires_the_workload_account(account):
    with pytest.raises(ValueError, match="workload account ID"):
        alarm_topic_policy(TOPIC_ARN, account)
    with pytest.raises(ValueError, match="workload account ID"):
        require_reviewed_topic_policy(
            alarm_topic_policy(TOPIC_ARN, ACCOUNT), account, TOPIC_ARN
        )


def test_the_runtime_cmk_key_arn_is_accepted():
    assert require_runtime_cmk(RUNTIME_CMK) == RUNTIME_CMK


@pytest.mark.parametrize(
    ("key", "message"),
    [
        ("alias/aws/sns", "AWS-managed key"),
        ("alias/aws/kms", "AWS-managed key"),
        (None, "runtime CMK key ARN"),
        ("", "runtime CMK key ARN"),
        ("alias/synthetic-poc-runtime", "runtime CMK key ARN"),
        (f"{RUNTIME_CMK}\n", "runtime CMK key ARN"),
        (["alias/aws/sns"], "runtime CMK key ARN"),
    ],
)
def test_a_missing_or_aws_managed_key_fails_closed(key, message):
    """S2.3 N: no key or ``alias/aws/sns`` never reaches the topic."""
    with pytest.raises(ValueError, match=message):
        require_runtime_cmk(key)


def _topic(engine_path, key=None, **extra):
    props = {"name": "synthetic-alarms"}
    if key is not None:
        props["kmsMasterKeyId" if engine_path else "kms_master_key_id"] = key
    return _transform_args(engine_path, TOPIC, {**props, **extra})


@pytest.mark.parametrize("engine_path", [False, True])
def test_a_topic_on_the_runtime_cmk_passes_the_guard(engine_path):
    args = _topic(engine_path, RUNTIME_CMK)
    assert _reject_secret_material(args, runtime_cmk=RUNTIME_CMK) is None


@pytest.mark.parametrize("engine_path", [False, True])
@pytest.mark.parametrize(
    "key",
    [
        None,
        "alias/aws/sns",
        JWT_CMK,
        "alias/synthetic-poc-runtime",
        _secret(RUNTIME_CMK),
    ],
)
def test_a_topic_off_the_runtime_cmk_fails_the_guard(engine_path, key):
    """S2.3 N (D-8): no key, the AWS-managed key or any other key fails."""
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_topic(engine_path, key), runtime_cmk=RUNTIME_CMK)


@pytest.mark.parametrize("engine_path", [False, True])
@pytest.mark.parametrize("policy", ["{}", alarm_topic_policy(TOPIC_ARN, ACCOUNT)])
def test_a_topic_with_an_inline_policy_fails_the_guard(engine_path, policy):
    """M2: an inline ``policy`` would bypass the reviewed TopicPolicy."""
    args = _topic(engine_path, RUNTIME_CMK, policy=policy)
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(args, runtime_cmk=RUNTIME_CMK)


@pytest.mark.parametrize("engine_path", [False, True])
def test_an_unbound_or_opaque_topic_key_fails_closed(engine_path):
    for args, bound in (
        (_topic(engine_path, RUNTIME_CMK), None),
        (_topic(engine_path, _unresolved()), RUNTIME_CMK),
        (
            _topic(
                engine_path,
                RUNTIME_CMK,
                kms_master_key_id=RUNTIME_CMK,
                kmsMasterKeyId=RUNTIME_CMK,
            ),
            RUNTIME_CMK,
        ),
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args, runtime_cmk=bound)


class PreviewMocks(mocks.Mocks):
    """Echo inputs and leave every provider output unknown, as in a preview."""

    def new_resource(self, args):
        return f"{args.name}-id", dict(args.inputs)

    def call(self, args):
        return args.inputs


def _run_preview(program):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        mocks.set_mocks(
            PreviewMocks(),
            project="user-service-infrastructure",
            stack="test",
            preview=True,
            monitor=mocks.MockMonitor(PreviewMocks()),
        )
        loop.run_until_complete(stack.run_pulumi_func(program))
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        settings.reset_options(project=None, stack=None)
        loop.close()
        asyncio.set_event_loop(None)


STACK = SimpleNamespace(
    stack_tag="user-service-infrastructure-test", region="eu-central-1"
)


TARGETS = AlarmTargets(
    failed_queue_names=("failed-a", "failed-b", "failed-c"),
    request_count_label="app/alb/1/targetgroup/tg/2",
    cluster_name="cluster",
    service_names={"web": "web", "worker": "worker"},
    documentdb_cluster_identifier="docdb",
    documentdb_instance_identifiers=("docdb-1",),
    documentdb_instance_class="db.t4g.medium",
    redis_cache_cluster_ids=("redis-001",),
)


def _plane(key=RUNTIME_CMK):
    return ObservabilityPlane(
        "observability",
        settings=STACK,
        runtime_cmk_arn=key,
        account_id=ACCOUNT,
        targets=TARGETS,
    )


def test_the_topic_policy_document_is_known_at_preview():
    """L4: the reviewed document never waits on the unknown topic ARN."""
    policies = []
    declare = aws.sns.TopicPolicy

    def capture(*args, **kwargs):
        policies.append(kwargs["policy"])
        # The alarms wait on the policy, so it stays a real resource.
        return declare(*args, **kwargs)

    with patch("app.observability.aws.sns.TopicPolicy", side_effect=capture):
        _run_preview(_plane)
    assert len(policies) == 1
    assert type(policies[0]) is str
    document = json.loads(policies[0])
    assert require_reviewed_topic_policy(document, ACCOUNT, TOPIC_ARN) == document


def test_every_alarm_action_is_the_plain_topic_arn_at_preview():
    """S2.4: the alarm actions never wait on the unknown topic ARN."""
    alarms = []

    def capture(*args, **kwargs):
        alarms.append(kwargs)

    with patch("app.observability.aws.cloudwatch.MetricAlarm", side_effect=capture):
        _run_preview(_plane)
    assert len(alarms) == 14
    for alarm in alarms:
        assert alarm["alarm_actions"] == [TOPIC_ARN]
        assert alarm["ok_actions"] in ([], [TOPIC_ARN])


@pytest.mark.parametrize("key", [None, "alias/aws/sns", "alias/synthetic-poc-runtime"])
def test_the_plane_refuses_a_key_that_is_not_the_runtime_cmk(key):
    """S2.3 N: the plane fails closed before it declares any resource."""
    topics = []
    with (
        patch("app.observability.aws.sns.Topic", side_effect=topics.append),
        pytest.raises(ValueError, match="Alarm topic"),
    ):
        _run_preview(lambda: _plane(key))
    assert topics == []
