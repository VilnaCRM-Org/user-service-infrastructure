"""PRD §3.1 alarm catalogue (S2.4, FR-13) in the hardened TEST graph.

The oracle below is written from the PRD §3.1 table, not from the program's
constants: one alarm per metric row, its threshold and window, an explicit
missing-data mode, and actions only to the S2.3 alarm topic. The checker
``_violations`` is also run against mutated rows, so a missing alarm, a missing
topic action, an action to another ARN or a changed threshold fails the suite.
"""

import copy
import re
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
from test_poc_workload_phase import graph

ALARM = "aws:cloudwatch/metricAlarm:MetricAlarm"
PREFIX = "user-service-infrastructure-test-"
TOPIC_ARN = (
    "arn:aws:sns:eu-central-1:891377212104:user-service-infrastructure-test-alarms"
)
OTHER_ARN = "arn:aws:sns:eu-central-1:891377212104:someone-else"
LOAD_BALANCER = "app/user-service-alb/123"
TARGET_GROUP = "targetgroup/user-service-target-group/123"
DOCDB = {"DBClusterIdentifier": "user-service-infrastructure-test-docdb"}
REDIS_MEMBERS = (
    "user-service-infrastructure-test-redis-001",
    "user-service-infrastructure-test-redis-002",
)
# 10% of the 4 GiB of the TEST class ``db.t4g.medium`` (§3.1), in bytes.
DOCDB_MEMORY_FLOOR = 429496729


def _single(namespace, metric, statistic, period, dims, op, threshold, periods, points):
    return {
        "namespace": namespace,
        "metricName": metric,
        "statistic": statistic,
        "period": period,
        "dimensions": dims,
        "comparisonOperator": op,
        "threshold": threshold,
        "evaluationPeriods": periods,
        "datapointsToAlarm": points,
    }


def _dlq(queue):
    # §3.1: ≥1 for 5 min.
    return _single(
        "AWS/SQS",
        "ApproximateNumberOfMessagesVisible",
        "Maximum",
        60,
        {"QueueName": queue},
        "GreaterThanOrEqualToThreshold",
        1,
        5,
        5,
    )


def _five_xx(metric):
    # §3.1: >5/min for 3 of 5 min.
    return _single(
        "AWS/ApplicationELB",
        metric,
        "Sum",
        60,
        {"LoadBalancer": LOAD_BALANCER},
        "GreaterThanThreshold",
        5,
        5,
        3,
    )


# PRD §3.1, one row per declared alarm suffix.
EXPECTED = {
    "dlq-failed-send-email": _dlq("failed-send-email"),
    "dlq-failed-domain-events": _dlq("failed-domain-events"),
    "dlq-failed-insert-user-batch": _dlq("failed-insert-user-batch"),
    "alb-target-5xx": _five_xx("HTTPCode_Target_5XX_Count"),
    "alb-elb-5xx": _five_xx("HTTPCode_ELB_5XX_Count"),
    # §3.1: ≥1 for 3 min.
    "alb-unhealthy-targets": _single(
        "AWS/ApplicationELB",
        "UnHealthyHostCount",
        "Maximum",
        60,
        {"LoadBalancer": LOAD_BALANCER, "TargetGroup": TARGET_GROUP},
        "GreaterThanOrEqualToThreshold",
        1,
        3,
        3,
    ),
    # §3.1: >80% for 15 min.
    "docdb-cpu": _single(
        "AWS/DocDB",
        "CPUUtilization",
        "Average",
        300,
        DOCDB,
        "GreaterThanThreshold",
        80,
        3,
        3,
    ),
    # §3.1: below 10% of the class for 15 min.
    "docdb-freeable-memory": _single(
        "AWS/DocDB",
        "FreeableMemory",
        "Minimum",
        300,
        DOCDB,
        "LessThanThreshold",
        DOCDB_MEMORY_FLOOR,
        3,
        3,
    ),
}
# §3.1 rows rendered with metric math: (metric, stat, function, op, threshold,
# periods, datapoints).
REDIS = {
    # >80% within the 5-15 min window: 15 min.
    "redis-memory": ("DatabaseMemoryUsagePercentage", "Maximum", "MAX", 80, 3),
    # >0 within 5-15 min: 5 min.
    "redis-evictions": ("Evictions", "Sum", "SUM", 0, 1),
    # >0 for 5 min.
    "redis-auth-failures": ("AuthenticationFailures", "Sum", "SUM", 0, 1),
}
ECS = {
    "ecs-web-below-desired": "user-service-infrastructure-test-web",
    "ecs-worker-below-desired": "user-service-infrastructure-test-worker",
}
STS = "docdb-sts-calls"
ALL = {*EXPECTED, *REDIS, *ECS, STS}


@pytest.fixture(scope="module")
def alarms(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("alarms"), "hardened")
    assert receipt["error"] is None
    rows = [r for r in receipt["registrations"].values() if r["type"] == ALARM]
    return {row["inputs"]["name"].removeprefix(PREFIX): row for row in rows}


def _redis_queries(metric, stat, function):
    return [
        *(
            {
                "id": f"m{index}",
                "metric": {
                    "dimensions": {"CacheClusterId": member},
                    "metricName": metric,
                    "namespace": "AWS/ElastiCache",
                    "period": 300,
                    "stat": stat,
                },
                "returnData": False,
            }
            for index, member in enumerate(REDIS_MEMBERS)
        ),
        {
            "expression": f"{function}([m0, m1])",
            "id": "group",
            "label": metric,
            "returnData": True,
        },
    ]


def _ecs_queries(service):
    dims = {
        "ClusterName": "user-service-infrastructure-test-ecs",
        "ServiceName": service,
    }
    return [
        {
            "id": query_id,
            "metric": {
                "dimensions": dims,
                "metricName": metric,
                "namespace": "ECS/ContainerInsights",
                "period": 60,
                "stat": "Average",
            },
            "returnData": False,
        }
        for query_id, metric in (
            ("running", "RunningTaskCount"),
            ("desired", "DesiredTaskCount"),
        )
    ] + [
        {
            "expression": "IF(desired > 0, desired - running, 0)",
            "id": "shortfall",
            "label": "Tasks below desired",
            "returnData": True,
        }
    ]


def _shape_violations(suffix, inputs):
    """Compare one alarm with its §3.1 row; return the mismatched fields."""
    if suffix in EXPECTED:
        expected = EXPECTED[suffix]
    elif suffix in REDIS:
        metric, stat, function, threshold, periods = REDIS[suffix]
        expected = {
            "metricQueries": _redis_queries(metric, stat, function),
            "comparisonOperator": "GreaterThanThreshold",
            "threshold": threshold,
            "evaluationPeriods": periods,
            "datapointsToAlarm": periods,
        }
    elif suffix in ECS:
        # §3.1: 10 min; suppressed when desired = 0.
        expected = {
            "metricQueries": _ecs_queries(ECS[suffix]),
            "comparisonOperator": "GreaterThanThreshold",
            "threshold": 0,
            "evaluationPeriods": 10,
            "datapointsToAlarm": 10,
        }
    else:
        # §3.1: informational (V-11), above the anomaly band for 15 min.
        expected = {
            "metricQueries": [
                {
                    "id": "sts",
                    "metric": {
                        "dimensions": DOCDB,
                        "metricName": "StsGetCallerIdentityCalls",
                        "namespace": "AWS/DocDB",
                        "period": 300,
                        "stat": "Sum",
                    },
                    "returnData": True,
                },
                {
                    "expression": "ANOMALY_DETECTION_BAND(sts, 2)",
                    "id": "band",
                    "label": "StsGetCallerIdentityCalls band",
                    "returnData": True,
                },
            ],
            "thresholdMetricId": "band",
            "comparisonOperator": "GreaterThanUpperThreshold",
            "evaluationPeriods": 3,
            "datapointsToAlarm": 3,
        }
    return [key for key, value in expected.items() if inputs.get(key) != value]


def _violations(alarms):
    """Return every way the rendered alarms differ from the §3.1 catalogue."""
    found = [f"missing {name}" for name in sorted(ALL - set(alarms))]
    found += [f"extra {name}" for name in sorted(set(alarms) - ALL)]
    for suffix, row in alarms.items():
        inputs = row["inputs"]
        if suffix in ALL:
            found += [f"{suffix}: {key}" for key in _shape_violations(suffix, inputs)]
        ok_expected = [] if suffix == STS else [TOPIC_ARN]
        if inputs.get("alarmActions") != [TOPIC_ARN]:
            found.append(f"{suffix}: alarmActions")
        if inputs.get("okActions") != ok_expected:
            found.append(f"{suffix}: okActions")
        if inputs.get("insufficientDataActions") not in (None, []):
            found.append(f"{suffix}: insufficientDataActions")
        if inputs.get("actionsEnabled") is not True:
            found.append(f"{suffix}: actionsEnabled")
        if inputs.get("treatMissingData") != "notBreaching":
            found.append(f"{suffix}: treatMissingData")
    return found


def test_the_hardened_graph_declares_exactly_the_prd_catalogue(alarms):
    """FR-13 P: one alarm per §3.1 metric row, each on the alarm topic."""
    assert len(alarms) == 14
    assert _violations(alarms) == []


def _drop(alarms):
    del alarms["dlq-failed-domain-events"]


def _no_action(alarms):
    alarms["alb-target-5xx"]["inputs"]["alarmActions"] = []


def _other_arn(alarms):
    alarms["redis-auth-failures"]["inputs"]["alarmActions"] = [OTHER_ARN]


def _extra_arn(alarms):
    alarms["docdb-cpu"]["inputs"]["okActions"] = [TOPIC_ARN, OTHER_ARN]


def _threshold(alarms):
    alarms["docdb-cpu"]["inputs"]["threshold"] = 90


def _window(alarms):
    alarms["alb-unhealthy-targets"]["inputs"]["evaluationPeriods"] = 5


def _expression(alarms):
    query = alarms["ecs-web-below-desired"]["inputs"]["metricQueries"][2]
    query["expression"] = "desired - running"


def _missing_data(alarms):
    del alarms["redis-memory"]["inputs"]["treatMissingData"]


@pytest.mark.parametrize(
    "mutate",
    [
        _drop,
        _no_action,
        _other_arn,
        _extra_arn,
        _threshold,
        _window,
        _expression,
        _missing_data,
    ],
)
def test_a_changed_catalogue_fails_the_suite(alarms, mutate):
    """FR-13 N: a missing alarm, action, foreign ARN or §3.1 change is found."""
    changed = copy.deepcopy(alarms)
    mutate(changed)
    assert _violations(changed)


def _shortfall(expression, desired, running):
    """Evaluate the reviewed ``IF(d > 0, d - r, 0)`` shape for one datapoint."""
    match = re.fullmatch(r"IF\((\w+) > 0, (\w+) - (\w+), 0\)", expression)
    assert match is not None
    values = {"desired": desired, "running": running}
    first, minuend, subtrahend = match.groups()
    return values[minuend] - values[subtrahend] if values[first] > 0 else 0


@pytest.mark.parametrize("suffix", sorted(ECS))
@pytest.mark.parametrize(
    ("desired", "running", "fires"),
    [
        # B: desired = 0 (TEST night or weekend stop, PROD rollback-zero).
        (0, 0, False),
        (0, 2, False),
        (2, 1, True),
        (2, 2, False),
        (1, 3, False),
    ],
)
def test_running_below_desired_is_suppressed_while_desired_is_zero(
    alarms, suffix, desired, running, fires
):
    """§3.1 boundary B: the shortfall math never alarms at a desired count of 0."""
    inputs = alarms[suffix]["inputs"]
    expression = inputs["metricQueries"][2]["expression"]
    value = _shortfall(expression, desired, running)
    assert inputs["comparisonOperator"] == "GreaterThanThreshold"
    assert (value > inputs["threshold"]) is fires


@pytest.mark.parametrize(
    ("alarm_actions", "ok_actions"),
    [
        ([], [TOPIC_ARN]),
        ([OTHER_ARN], []),
        ([TOPIC_ARN, OTHER_ARN], []),
        ([TOPIC_ARN], [OTHER_ARN]),
        ([TOPIC_ARN], [TOPIC_ARN, TOPIC_ARN]),
        (None, None),
        (TOPIC_ARN, []),
    ],
)
def test_an_action_off_the_alarm_topic_fails_closed(alarm_actions, ok_actions):
    """FR-13 N: only the alarm topic may receive an alarm or OK action."""
    with pytest.raises(ValueError, match="only the alarm topic"):
        require_topic_actions(alarm_actions, ok_actions, TOPIC_ARN)


def test_the_topic_actions_are_accepted():
    assert require_topic_actions([TOPIC_ARN], [], TOPIC_ARN) == ([TOPIC_ARN], [])
    assert require_topic_actions([TOPIC_ARN], [TOPIC_ARN], TOPIC_ARN) == (
        [TOPIC_ARN],
        [TOPIC_ARN],
    )


SETTINGS = SimpleNamespace(
    stack_tag="user-service-infrastructure-test",
    queues=SimpleNamespace(
        failed_send_email="failed-send-email",
        failed_domain_events="failed-domain-events",
        failed_insert_user_batch="failed-insert-user-batch",
    ),
    documentdb=SimpleNamespace(instance_class="db.t4g.medium"),
    redis=SimpleNamespace(replicas_per_node_group=2),
)


def _services(**names):
    return ScalableServices(
        cluster_name="cluster",
        service_names=names or {"web": "web", "worker": "worker"},
        request_count_label="app/alb/1/targetgroup/tg/2",
    )


def test_the_targets_name_one_redis_member_per_cache_cluster():
    targets = alarm_targets(SETTINGS, _services(), "group")
    assert targets.redis_cache_cluster_ids == ("group-001", "group-002", "group-003")
    assert targets.failed_queue_names == (
        "failed-send-email",
        "failed-domain-events",
        "failed-insert-user-batch",
    )
    assert targets.documentdb_cluster_identifier == (
        "user-service-infrastructure-test-docdb"
    )


@pytest.mark.parametrize(
    ("services", "message"),
    [
        (None, "hardened compute services"),
        (SimpleNamespace(), "hardened compute services"),
        (_services(web="web"), "web and worker services"),
        (_services(web="web", worker="worker", extra="x"), "web and worker services"),
    ],
)
def test_the_catalogue_requires_the_hardened_services(services, message):
    """N: without the hardened services the ALB and ECS alarms name nothing."""
    with pytest.raises(ValueError, match=message):
        alarm_targets(SETTINGS, services, "group")


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
    ("targets", "message"),
    [
        (_targets(failed_queue_names=("a", "b")), "three failed-\\* queues"),
        (_targets(documentdb_instance_class="db.x9.huge"), "memory size"),
    ],
)
def test_an_incomplete_target_fails_closed(targets, message):
    with pytest.raises(ValueError, match=message):
        alarm_definitions(targets)


@pytest.mark.parametrize(
    "label", ["", "app/alb/1", "/targetgroup/tg/2", "app/x/targetgroup/"]
)
def test_a_label_without_both_arn_suffixes_fails_closed(label):
    """N: the ALB alarms need the load balancer and the target group suffix."""
    with pytest.raises(ValueError, match="request-count label"):
        _label_part(label, 0)
