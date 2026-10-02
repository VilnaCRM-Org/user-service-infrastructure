"""Fail-closed guards of the S2.4 alarm catalogue in the integration suite.

The integration coverage gate includes ``pulumi/app``. The hardened graph
renders only the reviewed catalogue, so these cases drive the refusals
directly: an action off the alarm topic (FR-13), missing hardened services, an
ALB label without both ARN suffixes, an unknown DocumentDB class and a missing
failed-* queue.
"""

from types import SimpleNamespace

import pytest
from app.compute import ScalableServices
from app.observability import (
    AlarmTargets,
    _label_part,
    alarm_definitions,
    alarm_targets,
    require_topic_actions,
)

TOPIC_ARN = (
    "arn:aws:sns:eu-central-1:891377212104:user-service-infrastructure-test-alarms"
)
SETTINGS = SimpleNamespace(
    stack_tag="user-service-infrastructure-test",
    queues=SimpleNamespace(
        failed_send_email="failed-send-email",
        failed_domain_events="failed-domain-events",
        failed_insert_user_batch="failed-insert-user-batch",
    ),
    documentdb=SimpleNamespace(instance_class="db.t4g.medium"),
    redis=SimpleNamespace(replicas_per_node_group=1),
)


def _targets(**changes):
    values = {
        "failed_queue_names": ("a", "b", "c"),
        "request_count_label": "app/alb/1/targetgroup/tg/2",
        "cluster_name": "cluster",
        "service_names": {"web": "web", "worker": "worker"},
        "documentdb_cluster_identifier": "docdb",
        "documentdb_instance_class": "db.t4g.medium",
        "redis_cache_cluster_ids": ("redis-001",),
    }
    return AlarmTargets(**{**values, **changes})


@pytest.mark.parametrize(
    ("alarm_actions", "ok_actions"),
    [
        ([], []),
        (["arn:aws:sns:eu-central-1:891377212104:other"], []),
        ([TOPIC_ARN], ["arn:aws:sns:eu-central-1:891377212104:other"]),
    ],
)
def test_an_action_off_the_alarm_topic_cannot_reach_an_alarm(alarm_actions, ok_actions):
    with pytest.raises(ValueError, match="only the alarm topic"):
        require_topic_actions(alarm_actions, ok_actions, TOPIC_ARN)


def test_the_topic_actions_are_accepted():
    assert require_topic_actions([TOPIC_ARN], [], TOPIC_ARN) == ([TOPIC_ARN], [])


@pytest.mark.parametrize(
    ("services", "message"),
    [
        (None, "hardened compute services"),
        (
            ScalableServices(
                cluster_name="c", service_names={"web": "w"}, request_count_label="l"
            ),
            "web and worker services",
        ),
    ],
)
def test_the_catalogue_requires_the_hardened_services(services, message):
    with pytest.raises(ValueError, match=message):
        alarm_targets(SETTINGS, services, "group")


def test_the_targets_name_the_redis_members():
    services = ScalableServices(
        cluster_name="c",
        service_names={"web": "w", "worker": "k"},
        request_count_label="app/alb/1/targetgroup/tg/2",
    )
    targets = alarm_targets(SETTINGS, services, "group")
    assert targets.redis_cache_cluster_ids == ("group-001", "group-002")


@pytest.mark.parametrize("label", ["app/alb/1", "/targetgroup/tg/2"])
def test_a_label_without_both_arn_suffixes_fails_closed(label):
    with pytest.raises(ValueError, match="request-count label"):
        _label_part(label, 1)


@pytest.mark.parametrize(
    ("targets", "message"),
    [
        (_targets(failed_queue_names=("a",)), "three failed-\\* queues"),
        (_targets(documentdb_instance_class="db.unknown"), "memory size"),
    ],
)
def test_an_incomplete_target_fails_closed(targets, message):
    with pytest.raises(ValueError, match=message):
        alarm_definitions(targets)


def test_the_label_splits_into_the_load_balancer_and_target_group():
    label = "app/user-service-alb/123/targetgroup/user-service-target-group/456"
    assert _label_part(label, 0) == "app/user-service-alb/123"
    assert _label_part(label, 1) == "targetgroup/user-service-target-group/456"
