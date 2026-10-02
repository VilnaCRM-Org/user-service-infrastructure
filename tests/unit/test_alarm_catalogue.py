"""PRD §3.1 alarm catalogue (S2.4, FR-13) in the hardened TEST graph.

The oracle below is written from the PRD §3.1 table, not from the program's
constants: one alarm per metric row, its threshold and window, an explicit
missing-data mode chosen per alarm, and actions only to the S2.3 alarm topic.
The checker ``_violations`` is also run against mutated rows, so a missing
alarm, a missing topic action, an action to another ARN or a changed threshold
fails the suite. The S2.4 gate fixes add the busiest-instance DocumentDB CPU
alarm (F2), the ``FILL`` shortfall (F1), the per-alarm missing-data modes (F3),
the hardened-guard action check (I1) and the data-plane binding (I5).
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
)
from app.workload_phase import _reject_secret_material
from test_poc_workload_phase import graph
from test_runtime_secrets import _transform_args
from test_workload_step_one import RUNTIME_CMK, _secret, _unresolved

ALARM = "aws:cloudwatch/metricAlarm:MetricAlarm"
PREFIX = "user-service-infrastructure-test-"
TOPIC_ARN = (
    "arn:aws:sns:eu-central-1:891377212104:user-service-infrastructure-test-alarms"
)
OTHER_ARN = "arn:aws:sns:eu-central-1:891377212104:someone-else"
LOAD_BALANCER = "app/user-service-alb/123"
TARGET_GROUP = "targetgroup/user-service-target-group/123"
DOCDB = {"DBClusterIdentifier": "user-service-infrastructure-test-docdb"}
# The data plane's two TEST instances (``documentDbInstanceCount`` default 2).
DOCDB_INSTANCES = (
    "user-service-infrastructure-test-docdb-1",
    "user-service-infrastructure-test-docdb-2",
)
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
# §3.1: >80% for 15 min, on the busiest instance (gate F2).
DOCDB_CPU = "docdb-cpu"
ALL = {*EXPECTED, *REDIS, *ECS, STS, DOCDB_CPU}
# Gate F3: the missing-data mode of each alarm. A quiet DLQ, ALB, eviction,
# auth-failure or ECS series is no failure; an always-published DocumentDB
# series bound to the data plane breaches when absent; Redis memory and the
# informational STS alarm keep their state.
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


@pytest.fixture(scope="module")
def alarms(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("alarms"), "hardened")
    assert receipt["error"] is None
    rows = [r for r in receipt["registrations"].values() if r["type"] == ALARM]
    return {row["inputs"]["name"].removeprefix(PREFIX): row for row in rows}


def _member_queries(namespace, dimension, members, metric, stat, function):
    return [
        *(
            {
                "id": f"m{index}",
                "metric": {
                    "dimensions": {dimension: member},
                    "metricName": metric,
                    "namespace": namespace,
                    "period": 300,
                    "stat": stat,
                },
                "returnData": False,
            }
            for index, member in enumerate(members)
        ),
        {
            "expression": f"{function}([m0, m1])",
            "id": "group",
            "label": metric,
            "returnData": True,
        },
    ]


def _redis_queries(metric, stat, function):
    return _member_queries(
        "AWS/ElastiCache", "CacheClusterId", REDIS_MEMBERS, metric, stat, function
    )


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
            "expression": "IF(desired > 0, desired - FILL(running, 0), 0)",
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
    elif suffix == DOCDB_CPU:
        expected = {
            "metricQueries": _member_queries(
                "AWS/DocDB",
                "DBInstanceIdentifier",
                DOCDB_INSTANCES,
                "CPUUtilization",
                "Average",
                "MAX",
            ),
            "comparisonOperator": "GreaterThanThreshold",
            "threshold": 80,
            "evaluationPeriods": 3,
            "datapointsToAlarm": 3,
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
        if inputs.get("alarmActions") != [TOPIC_ARN]:
            found.append(f"{suffix}: alarmActions")
        if inputs.get("okActions") != [TOPIC_ARN]:
            found.append(f"{suffix}: okActions")
        if inputs.get("insufficientDataActions") not in (None, []):
            found.append(f"{suffix}: insufficientDataActions")
        if inputs.get("actionsEnabled") is not True:
            found.append(f"{suffix}: actionsEnabled")
        if inputs.get("treatMissingData") != MISSING_DATA.get(suffix):
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


def _global_missing_data(alarms):
    alarms["docdb-cpu"]["inputs"]["treatMissingData"] = "notBreaching"


def _no_ok_action(alarms):
    alarms["docdb-sts-calls"]["inputs"]["okActions"] = []


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
        _global_missing_data,
        _no_ok_action,
    ],
)
def test_a_changed_catalogue_fails_the_suite(alarms, mutate):
    """FR-13 N: a missing alarm, action, foreign ARN or §3.1 change is found."""
    changed = copy.deepcopy(alarms)
    mutate(changed)
    assert _violations(changed)


def _shortfall(expression, desired, running):
    """Evaluate the reviewed shortfall shape for one datapoint.

    ``running`` is ``None`` when ``RunningTaskCount`` has no datapoint. A bare
    ``running`` then has no value, so the expression has none either; only
    ``FILL(running, 0)`` turns the gap into 0 running tasks.
    """
    match = re.fullmatch(
        r"IF\(desired > 0, desired - (FILL\(running, 0\)|running), 0\)", expression
    )
    assert match is not None
    if desired == 0:
        return 0
    if running is None and match.group(1) == "running":
        return None
    return desired - (running or 0)


@pytest.mark.parametrize("suffix", sorted(ECS))
@pytest.mark.parametrize(
    ("desired", "running", "fires"),
    [
        # B: desired = 0 (TEST night or weekend stop, PROD rollback-zero).
        (0, 0, False),
        (0, 2, False),
        (0, None, False),
        (2, 1, True),
        (2, 2, False),
        (1, 3, False),
        # Gate F1: no task ever starts, so RunningTaskCount is missing.
        (2, None, True),
        (2, 0, True),
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
    assert (value is not None and value > inputs["threshold"]) is fires


def _documentdb_cpu(inputs, per_instance):
    """Model the alarm's value from per-instance CPU averages.

    A cluster-level ``Average`` is the mean of the instances; the reviewed
    ``MAX`` expression over per-instance queries is the busiest instance.
    """
    queries = inputs.get("metricQueries")
    if queries is None:
        assert inputs["dimensions"] == DOCDB
        assert inputs["statistic"] == "Average"
        return sum(per_instance.values()) / len(per_instance)
    values = {
        query["id"]: per_instance[query["metric"]["dimensions"]["DBInstanceIdentifier"]]
        for query in queries
        if "metric" in query
    }
    (expression,) = [query["expression"] for query in queries if query["returnData"]]
    match = re.fullmatch(r"MAX\(\[(\w+(?:, \w+)*)\]\)", expression)
    assert match is not None
    return max(values[query_id] for query_id in match.group(1).split(", "))


@pytest.mark.parametrize(
    ("writer", "reader", "fires"),
    [
        # Gate F2: a 95% writer with a 10% reader averages 52.5%.
        (95, 10, True),
        (10, 95, True),
        (81, 0, True),
        (80, 80, False),
        (50, 10, False),
    ],
)
def test_documentdb_cpu_alarms_on_the_busiest_instance(alarms, writer, reader, fires):
    """§3.1 >80%: one hot instance fires even when the cluster average is low."""
    inputs = alarms["docdb-cpu"]["inputs"]
    value = _documentdb_cpu(
        inputs, {DOCDB_INSTANCES[0]: writer, DOCDB_INSTANCES[1]: reader}
    )
    assert inputs["comparisonOperator"] == "GreaterThanThreshold"
    assert (value > inputs["threshold"]) is fires


def test_the_documentdb_alarms_name_the_data_plane_resources(tmp_path_factory):
    """Gate I5: the alarm dimensions are the declared cluster and instances."""
    receipt = graph(tmp_path_factory.mktemp("bound"), "hardened")
    rows = list(receipt["registrations"].values())
    instances = [
        row["inputs"]
        for row in rows
        if row["type"] == "aws:docdb/clusterInstance:ClusterInstance"
    ]
    (cluster,) = [
        row["inputs"] for row in rows if row["type"] == "aws:docdb/cluster:Cluster"
    ]
    alarms = {
        row["inputs"]["name"].removeprefix(PREFIX): row["inputs"]
        for row in rows
        if row["type"] == ALARM
    }
    named = [
        query["metric"]["dimensions"]
        for query in alarms["docdb-cpu"].get("metricQueries", [])
        if "metric" in query
    ]
    assert sorted(dims["DBInstanceIdentifier"] for dims in named) == sorted(
        instance["identifier"] for instance in instances
    )
    assert sorted(instance["identifier"] for instance in instances) == list(
        DOCDB_INSTANCES
    )
    assert {instance["clusterIdentifier"] for instance in instances} == {
        cluster["clusterIdentifier"]
    }
    sts = alarms["docdb-sts-calls"]["metricQueries"][0]["metric"]["dimensions"]
    for dims in (alarms["docdb-freeable-memory"]["dimensions"], sts):
        assert dims == {"DBClusterIdentifier": cluster["clusterIdentifier"]}
    assert cluster["clusterIdentifier"] == DOCDB["DBClusterIdentifier"]


@pytest.mark.parametrize(
    "addition",
    [
        "root:alarm-foreign-action",
        "stack:alarm-foreign-action",
        "root:alarm-extra-action",
        "root:alarm-no-ok-action",
        "stack:alarm-foreign-ok-action",
        "root:alarm-insufficient-data-action",
        "root:alarm-no-action",
    ],
)
def test_the_hardened_guard_refuses_an_alarm_off_the_topic(tmp_path, addition):
    """Gate I1 N: an alarm whose actions are not exactly the topic never registers."""
    receipt = graph(tmp_path, "hardened", addition)
    assert receipt["error"] is not None
    assert "unreviewed property" in receipt["error"]
    assert not [
        name for name in receipt["registrations"] if name.startswith("fixture-")
    ]


def test_the_hardened_guard_admits_an_alarm_on_the_topic(tmp_path):
    """Gate I1 P: exact topic alarm and OK actions pass the stack guard."""
    receipt = graph(tmp_path, "hardened", "root:alarm-on-topic")
    assert receipt["error"] is None
    assert "fixture-alarm" in receipt["registrations"]


def _alarm_args(engine_path, alarm=None, ok=None, insufficient=None):
    """One metric alarm's guard arguments in the casing of its path."""
    names = (
        ("alarmActions", "okActions", "insufficientDataActions")
        if engine_path
        else ("alarm_actions", "ok_actions", "insufficient_data_actions")
    )
    props = {"metricName": "Evictions"}
    props.update(
        {key: value for key, value in zip(names, (alarm, ok, insufficient)) if value}
    )
    return _transform_args(engine_path, ALARM, props)


@pytest.mark.parametrize("engine_path", [False, True])
def test_an_alarm_on_the_topic_passes_the_bound_guard(engine_path):
    for insufficient in (None, []):
        args = _alarm_args(engine_path, [TOPIC_ARN], [TOPIC_ARN], insufficient)
        assert (
            _reject_secret_material(
                args, runtime_cmk=RUNTIME_CMK, alarm_topic=TOPIC_ARN
            )
            is None
        )


@pytest.mark.parametrize("engine_path", [False, True])
def test_an_unbound_guard_admits_no_alarm(engine_path):
    """Gate I1 N: without the stack's topic ARN no metric alarm passes."""
    args = _alarm_args(engine_path, [TOPIC_ARN], [TOPIC_ARN])
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(args, runtime_cmk=RUNTIME_CMK)


@pytest.mark.parametrize("engine_path", [False, True])
@pytest.mark.parametrize(
    ("alarm", "ok", "insufficient"),
    [
        ([OTHER_ARN], [TOPIC_ARN], None),
        ([TOPIC_ARN, OTHER_ARN], [TOPIC_ARN], None),
        ([TOPIC_ARN], None, None),
        ([TOPIC_ARN], [OTHER_ARN], None),
        ([TOPIC_ARN], [TOPIC_ARN, TOPIC_ARN], None),
        ([TOPIC_ARN], [TOPIC_ARN], [TOPIC_ARN]),
        (None, [TOPIC_ARN], None),
        (TOPIC_ARN, [TOPIC_ARN], None),
        ([_secret(TOPIC_ARN)], [TOPIC_ARN], None),
        (_unresolved(), [TOPIC_ARN], None),
    ],
)
def test_an_alarm_off_the_topic_fails_the_bound_guard(
    engine_path, alarm, ok, insufficient
):
    """Gate I1 N: any other, extra, missing or opaque action fails closed."""
    args = _alarm_args(engine_path, alarm, ok, insufficient)
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(args, runtime_cmk=RUNTIME_CMK, alarm_topic=TOPIC_ARN)


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


INSTANCES = (
    SimpleNamespace(identifier="docdb-1", cluster_identifier="docdb"),
    SimpleNamespace(identifier="docdb-2", cluster_identifier="docdb"),
)


def _services(**names):
    return ScalableServices(
        cluster_name="cluster",
        service_names=names or {"web": "web", "worker": "worker"},
        request_count_label="app/alb/1/targetgroup/tg/2",
    )


def test_the_targets_name_one_redis_member_per_cache_cluster():
    targets = alarm_targets(SETTINGS, _services(), "group", INSTANCES)
    assert targets.redis_cache_cluster_ids == ("group-001", "group-002", "group-003")
    assert targets.failed_queue_names == (
        "failed-send-email",
        "failed-domain-events",
        "failed-insert-user-batch",
    )
    assert targets.documentdb_cluster_identifier == "docdb"
    assert targets.documentdb_instance_identifiers == ("docdb-1", "docdb-2")


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
        alarm_targets(SETTINGS, services, "group", INSTANCES)


@pytest.mark.parametrize("instances", [(), [INSTANCES[0]], None])
def test_the_catalogue_requires_the_documentdb_instances(instances):
    """N: without the data plane's instances the DocumentDB alarms name nothing."""
    with pytest.raises(ValueError, match="DocumentDB instances"):
        alarm_targets(SETTINGS, _services(), "group", instances)


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


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"failed_queue_names": ("a", "b")}, "three failed-\\* queues"),
        ({"documentdb_instance_class": "db.x9.huge"}, "memory size"),
    ],
)
def test_an_incomplete_target_fails_closed(changes, message):
    with pytest.raises(ValueError, match=message):
        alarm_definitions(_targets(**changes))


@pytest.mark.parametrize(
    "label", ["", "app/alb/1", "/targetgroup/tg/2", "app/x/targetgroup/"]
)
def test_a_label_without_both_arn_suffixes_fails_closed(label):
    """N: the ALB alarms need the load balancer and the target group suffix."""
    with pytest.raises(ValueError, match="request-count label"):
        _label_part(label, 0)
