"""Fail-closed guards of the S2.4 alarm catalogue in the integration suite.

The integration coverage gate includes ``pulumi/app``. The hardened graph
renders only the reviewed catalogue, so these cases drive the refusals
directly: an action off the alarm topic at the hardened guard (FR-13, gate
I1), missing hardened services or DocumentDB instances, an ALB label without
both ARN suffixes, an unknown DocumentDB class and a missing failed-* queue.
"""

from types import SimpleNamespace

import pytest
from app.compute import ScalableServices
from app.observability import (
    AlarmTargets,
    _label_part,
    alarm_definitions,
    alarm_targets,
)
from app.workload_phase import _reject_secret_material

import pulumi

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
INSTANCES = (SimpleNamespace(identifier="docdb-1", cluster_identifier="docdb"),)
ALARM = "aws:cloudwatch/metricAlarm:MetricAlarm"
OTHER_ARN = "arn:aws:sns:eu-central-1:891377212104:other"


def _targets(**changes):
    values = {
        "failed_queue_names": ("a", "b", "c"),
        "request_count_label": "app/alb/1/targetgroup/tg/2",
        "cluster_name": "cluster",
        "service_names": {"web": "web", "worker": "worker"},
        "documentdb_cluster_identifier": "docdb",
        "documentdb_instance_identifiers": ("docdb-1",),
        "documentdb_instance_class": "db.t4g.medium",
        "redis_cache_cluster_ids": ("redis-001",),
    }
    return AlarmTargets(**{**values, **changes})


def _alarm(props):
    return pulumi.ResourceTransformationArgs(
        resource=None, type_=ALARM, name="probe", props=props, opts=None
    )


@pytest.mark.parametrize(
    ("props", "topic"),
    [
        ({"alarm_actions": [TOPIC_ARN], "ok_actions": [TOPIC_ARN]}, None),
        ({"alarm_actions": [OTHER_ARN], "ok_actions": [TOPIC_ARN]}, TOPIC_ARN),
        ({"alarm_actions": [TOPIC_ARN]}, TOPIC_ARN),
        (
            {
                "alarm_actions": [TOPIC_ARN],
                "ok_actions": [TOPIC_ARN],
                "insufficient_data_actions": [TOPIC_ARN],
            },
            TOPIC_ARN,
        ),
    ],
)
def test_an_action_off_the_alarm_topic_cannot_reach_an_alarm(props, topic):
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_alarm(props), alarm_topic=topic)


def test_the_topic_actions_are_accepted():
    props = {"alarm_actions": [TOPIC_ARN], "ok_actions": [TOPIC_ARN]}
    assert _reject_secret_material(_alarm(props), alarm_topic=TOPIC_ARN) is None


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
        alarm_targets(SETTINGS, services, "group", INSTANCES)


def test_the_catalogue_requires_the_documentdb_instances():
    services = ScalableServices(
        cluster_name="c",
        service_names={"web": "w", "worker": "k"},
        request_count_label="app/alb/1/targetgroup/tg/2",
    )
    with pytest.raises(ValueError, match="DocumentDB instances"):
        alarm_targets(SETTINGS, services, "group", ())


def test_the_targets_name_the_redis_members():
    services = ScalableServices(
        cluster_name="c",
        service_names={"web": "w", "worker": "k"},
        request_count_label="app/alb/1/targetgroup/tg/2",
    )
    targets = alarm_targets(SETTINGS, services, "group", INSTANCES)
    assert targets.redis_cache_cluster_ids == ("group-001", "group-002")
    assert targets.documentdb_instance_identifiers == ("docdb-1",)
    assert targets.documentdb_cluster_identifier == "docdb"


@pytest.mark.parametrize("label", ["app/alb/1", "/targetgroup/tg/2"])
def test_a_label_without_both_arn_suffixes_fails_closed(label):
    with pytest.raises(ValueError, match="request-count label"):
        _label_part(label, 1)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"failed_queue_names": ("a",)}, "three failed-\\* queues"),
        ({"documentdb_instance_class": "db.unknown"}, "memory size"),
    ],
)
def test_an_incomplete_target_fails_closed(changes, message):
    with pytest.raises(ValueError, match=message):
        alarm_definitions(_targets(**changes))


def test_the_label_splits_into_the_load_balancer_and_target_group():
    label = "app/user-service-alb/123/targetgroup/user-service-target-group/456"
    assert _label_part(label, 0) == "app/user-service-alb/123"
    assert _label_part(label, 1) == "targetgroup/user-service-target-group/456"
