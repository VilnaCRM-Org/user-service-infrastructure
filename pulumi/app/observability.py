"""Service-owned alarm topic and the PRD §3.1 alarm catalogue (AD-11).

S2.3 adds one SNS topic encrypted with the D-4 runtime CMK (D-8: CloudWatch
alarms cannot publish to a topic on the AWS-managed ``alias/aws/sns`` key) and
its topic policy, which lets only CloudWatch and EventBridge in the workload
account publish (FR-13). S2.4 adds one CloudWatch metric alarm per §3.1 metric
row; each sends its actions only to that topic, and each has a runbook entry in
``docs/sre-operations.md``. The EventBridge rules (S2.5) join this plane later.
The subscription endpoint is XP-6, so no subscription exists.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import pulumi_aws as aws

import pulumi
from app.compute import ScalableServices
from app.environment import StackSettings, build_resource_name

__all__ = [
    "ALARM_TOPIC_PUBLISHERS",
    "AlarmTargets",
    "ObservabilityPlane",
    "alarm_definitions",
    "alarm_targets",
    "alarm_topic_arn",
    "alarm_topic_policy",
    "require_reviewed_topic_policy",
    "require_runtime_cmk",
    "stack_alarm_topic_arn",
]

# The only principals that may publish to the alarm topic (FR-13).
ALARM_TOPIC_PUBLISHERS = ("cloudwatch.amazonaws.com", "events.amazonaws.com")
ALARM_TOPIC_ACTION = "sns:Publish"
# AWS reserves ``alias/aws/``; an AWS-managed key is never the runtime CMK.
AWS_MANAGED_KEY_PREFIX = "alias/aws/"
_KMS_KEY_ARN = re.compile(r"arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]+")
_ACCOUNT_ID = re.compile(r"[0-9]{12}")
_TOPIC_ARN = r"arn:aws:sns:[a-z0-9-]+:{account}:[A-Za-z0-9_-]{{1,256}}"


def require_runtime_cmk(key: Any) -> str:
    """Return ``key`` only if it is a customer-managed KMS key ARN (D-4, D-8).

    No key, an ``alias/aws/`` key such as ``alias/aws/sns``, an alias or any
    value that is not a key ARN fails closed. The hardened guard then binds the
    rendered topic to the contract's ``central.cmk.runtime.arn`` exactly.
    """
    if type(key) is str and key.startswith(AWS_MANAGED_KEY_PREFIX):
        raise ValueError("Alarm topic must not use an AWS-managed key")
    if type(key) is not str or not _KMS_KEY_ARN.fullmatch(key):
        raise ValueError("Alarm topic must use the runtime CMK key ARN")
    return key


def _require_account(account_id: Any) -> str:
    """Accept only a 12-digit AWS account ID."""
    if type(account_id) is not str or not _ACCOUNT_ID.fullmatch(account_id):
        raise ValueError("Alarm topic policy requires the workload account ID")
    return account_id


def alarm_topic_arn(region: str, account_id: str, name: str) -> str:
    """Build the topic ARN from its parts, so the policy is known at preview."""
    return f"arn:aws:sns:{region}:{_require_account(account_id)}:{name}"


def _require_topic_arn(topic_arn: Any, account_id: str) -> str:
    """Accept only an SNS topic ARN in the workload account."""
    pattern = _TOPIC_ARN.format(account=account_id)
    if type(topic_arn) is not str or not re.fullmatch(pattern, topic_arn):
        raise ValueError("Alarm topic policy requires the topic ARN in the account")
    return topic_arn


def alarm_topic_policy(topic_arn: str, account_id: str) -> dict[str, Any]:
    """Render one ``sns:Publish`` allow per publisher, bound to the account."""
    _require_account(account_id)
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": f"Allow{publisher.split('.')[0].title()}Publish",
                "Effect": "Allow",
                "Principal": {"Service": publisher},
                "Action": ALARM_TOPIC_ACTION,
                "Resource": topic_arn,
                "Condition": {"StringEquals": {"aws:SourceAccount": account_id}},
            }
            for publisher in ALARM_TOPIC_PUBLISHERS
        ],
    }


def _reviewed_statement(statement: Any, account_id: str, topic_arn: str) -> str | None:
    """Return the publisher of one reviewed statement, or ``None``.

    The statement must hold exactly the reviewed keys: an ``Allow`` of
    ``sns:Publish`` on the topic ARN for one service principal, conditioned
    only on ``aws:SourceAccount`` equal to the workload account.
    """
    if type(statement) is not dict or set(statement) != {
        "Sid",
        "Effect",
        "Principal",
        "Action",
        "Resource",
        "Condition",
    }:
        return None
    principal = statement["Principal"]
    if type(principal) is not dict or set(principal) != {"Service"}:
        return None
    publisher = principal["Service"]
    reviewed = (
        statement["Effect"] == "Allow"
        and statement["Action"] == ALARM_TOPIC_ACTION
        and statement["Resource"] == topic_arn
        and publisher in ALARM_TOPIC_PUBLISHERS
        and statement["Condition"]
        == {"StringEquals": {"aws:SourceAccount": account_id}}
    )
    return publisher if reviewed else None


def require_reviewed_topic_policy(
    policy: Any, account_id: str, topic_arn: str
) -> dict[str, Any]:
    """Fail closed unless the policy allows exactly the two publishers (FR-13).

    Every statement must be a reviewed allow on ``topic_arn`` with the
    ``aws:SourceAccount`` condition; a missing condition, another principal, a
    wildcard principal or resource, another action or a repeated publisher
    fails.
    """
    _require_account(account_id)
    _require_topic_arn(topic_arn, account_id)
    statements = policy.get("Statement") if type(policy) is dict else None
    if type(statements) is not list:
        raise ValueError("Alarm topic policy is not a statement list")
    publishers = [
        _reviewed_statement(entry, account_id, topic_arn) for entry in statements
    ]
    if sorted(map(str, publishers)) != sorted(ALARM_TOPIC_PUBLISHERS):
        raise ValueError("Alarm topic policy grants an unreviewed publisher")
    return policy


# PRD §3.1 alarm catalogue (FR-13). Every alarm sets its own missing-data mode
# (gate F3). ``notBreaching``: a quiet metric (no messages, no requests, no
# errors, no tasks) is not a failure. ``breaching``: an always-published
# metric bound to the data plane's outputs that stops reporting means the
# dimension is wrong or the instance is gone. ``missing``: the alarm holds its
# state; it has no insufficient-data action, so it pages nobody.
NOT_BREACHING = "notBreaching"
BREACHING = "breaching"
MISSING = "missing"
SQS_NAMESPACE = "AWS/SQS"
ALB_NAMESPACE = "AWS/ApplicationELB"
ECS_NAMESPACE = "ECS/ContainerInsights"
DOCUMENTDB_NAMESPACE = "AWS/DocDB"
REDIS_NAMESPACE = "AWS/ElastiCache"
# The ``ALBRequestCountPerTarget`` label joins the load balancer and target
# group ARN suffixes; the target group suffix starts with this segment.
TARGET_GROUP_SEGMENT = "targetgroup/"
# Container Insights math (§3.1, boundary B): the shortfall is positive only
# while the service wants tasks, so a desired count of 0 never alarms. A
# missing ``RunningTaskCount`` counts as 0 running tasks (gate F1), so a
# service whose tasks never start still alarms.
ECS_SHORTFALL_EXPRESSION = "IF(desired > 0, desired - FILL(running, 0), 0)"
# Memory of the reviewed DocumentDB instance classes, in GiB. ``FreeableMemory``
# alarms below 10% of the class (§3.1); an unknown class fails closed.
DOCUMENTDB_CLASS_MEMORY_GIB = {
    "db.t3.medium": 4,
    "db.t4g.medium": 4,
    "db.r5.large": 16,
    "db.r6g.large": 16,
    "db.r5.xlarge": 32,
    "db.r6g.xlarge": 32,
}
GIB = 1024**3
# StsGetCallerIdentityCalls is informational (§3.1, V-11): it has no fixed
# threshold, so it alarms above a two-deviation anomaly band.
STS_ANOMALY_BAND_WIDTH = 2


@dataclass(frozen=True)
class AlarmTargets:
    """The dimension values the §3.1 alarms name.

    ``request_count_label`` is the compute plane's ``ALBRequestCountPerTarget``
    label (``<load balancer suffix>/<target group suffix>``). The Redis member
    IDs are the replication group's cache clusters, ``<group>-001`` onwards.
    The DocumentDB cluster and instance identifiers are the data plane's
    ``ClusterInstance`` outputs (gate I5), so the alarms name what it declares.
    """

    failed_queue_names: tuple[str, ...]
    request_count_label: pulumi.Input[str]
    cluster_name: pulumi.Input[str]
    service_names: dict[str, pulumi.Input[str]]
    documentdb_cluster_identifier: pulumi.Input[str]
    documentdb_instance_identifiers: tuple[pulumi.Input[str], ...]
    documentdb_instance_class: str
    redis_cache_cluster_ids: tuple[str, ...]


def alarm_targets(
    settings: StackSettings,
    services: Any,
    redis_group_id: str,
    documentdb_instances: tuple[Any, ...],
) -> AlarmTargets:
    """Collect the alarm dimensions from the settings and the hardened planes.

    Only the hardened compute plane sets ``services``; without it the ALB and
    ECS alarms would name nothing, so the catalogue fails closed. The same
    holds for a data plane without DocumentDB instances.
    """
    if type(services) is not ScalableServices:
        raise ValueError("Alarm catalogue requires the hardened compute services")
    if set(services.service_names) != {"web", "worker"}:
        raise ValueError("Alarm catalogue requires the web and worker services")
    if type(documentdb_instances) is not tuple or not documentdb_instances:
        raise ValueError("Alarm catalogue requires the DocumentDB instances")
    members = settings.redis.replicas_per_node_group + 1
    return AlarmTargets(
        failed_queue_names=(
            settings.queues.failed_send_email,
            settings.queues.failed_domain_events,
            settings.queues.failed_insert_user_batch,
        ),
        request_count_label=services.request_count_label,
        cluster_name=services.cluster_name,
        service_names=dict(services.service_names),
        documentdb_cluster_identifier=documentdb_instances[0].cluster_identifier,
        documentdb_instance_identifiers=tuple(
            instance.identifier for instance in documentdb_instances
        ),
        documentdb_instance_class=settings.documentdb.instance_class,
        redis_cache_cluster_ids=tuple(
            f"{redis_group_id}-{index:03d}" for index in range(1, members + 1)
        ),
    )


def _label_part(label: str, index: int) -> str:
    """Split the request-count label into its load balancer and target group."""
    load_balancer, separator, target_group = label.partition(f"/{TARGET_GROUP_SEGMENT}")
    if not (separator and load_balancer and target_group):
        raise ValueError("Alarm catalogue requires the ALB request-count label")
    return (load_balancer, f"{TARGET_GROUP_SEGMENT}{target_group}")[index]


def _metric(namespace: str, metric_name: str, statistic: str, period: int, **dims):
    """Render one single-metric alarm body."""
    return {
        "namespace": namespace,
        "metric_name": metric_name,
        "statistic": statistic,
        "period": period,
        "dimensions": dims,
    }


def _query(query_id: str, namespace: str, metric_name: str, stat: str, **dims):
    """Render one metric query that feeds an expression (no data of its own)."""
    return aws.cloudwatch.MetricAlarmMetricQueryArgs(
        id=query_id,
        return_data=False,
        metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
            namespace=namespace,
            metric_name=metric_name,
            stat=stat,
            period=60 if namespace == ECS_NAMESPACE else 300,
            dimensions=dims,
        ),
    )


def _expression(query_id: str, expression: str, label: str):
    """Render the one returned expression of a metric-math alarm."""
    return aws.cloudwatch.MetricAlarmMetricQueryArgs(
        id=query_id, expression=expression, label=label, return_data=True
    )


def _window(
    comparison: str, threshold: float, periods: int, datapoints: int, missing: str
):
    """Render the threshold, evaluation window and missing-data mode."""
    return {
        "comparison_operator": comparison,
        "threshold": threshold,
        "evaluation_periods": periods,
        "datapoints_to_alarm": datapoints,
        "treat_missing_data": missing,
    }


def _ecs_shortfall(cluster: pulumi.Input[str], service: pulumi.Input[str]):
    """Alarm 10 min of running below desired, suppressed while desired is 0."""
    dims = {"ClusterName": cluster, "ServiceName": service}
    return {
        "metric_queries": [
            _query("running", ECS_NAMESPACE, "RunningTaskCount", "Average", **dims),
            _query("desired", ECS_NAMESPACE, "DesiredTaskCount", "Average", **dims),
            _expression("shortfall", ECS_SHORTFALL_EXPRESSION, "Tasks below desired"),
        ],
        **_window("GreaterThanThreshold", 0, 10, 10, NOT_BREACHING),
    }


def _member_math(
    namespace: str,
    metric_name: str,
    stat: str,
    function: str,
    dimension: str,
    members: tuple[pulumi.Input[str], ...],
):
    """Combine one metric across every member (cache cluster or instance)."""
    ids = [f"m{index}" for index in range(len(members))]
    queries = [
        _query(query_id, namespace, metric_name, stat, **{dimension: member})
        for query_id, member in zip(ids, members)
    ]
    expression = f"{function}([{', '.join(ids)}])"
    return [*queries, _expression("group", expression, metric_name)]


def _redis_math(targets: AlarmTargets, metric_name: str, stat: str, function: str):
    """Combine one Redis metric across every cache cluster of the group."""
    return _member_math(
        REDIS_NAMESPACE,
        metric_name,
        stat,
        function,
        "CacheClusterId",
        targets.redis_cache_cluster_ids,
    )


def _documentdb_memory_floor(instance_class: str) -> int:
    """Return 10% of the instance class memory in bytes (§3.1)."""
    if instance_class not in DOCUMENTDB_CLASS_MEMORY_GIB:
        raise ValueError("Alarm catalogue has no memory size for the DocumentDB class")
    return DOCUMENTDB_CLASS_MEMORY_GIB[instance_class] * GIB // 10


def _sts_anomaly(cluster_identifier: pulumi.Input[str]):
    """Alarm, for information, on DocumentDB STS calls above their band (V-11)."""
    return {
        "metric_queries": [
            aws.cloudwatch.MetricAlarmMetricQueryArgs(
                id="sts",
                return_data=True,
                metric=aws.cloudwatch.MetricAlarmMetricQueryMetricArgs(
                    namespace=DOCUMENTDB_NAMESPACE,
                    metric_name="StsGetCallerIdentityCalls",
                    stat="Sum",
                    period=300,
                    dimensions={"DBClusterIdentifier": cluster_identifier},
                ),
            ),
            _expression(
                "band",
                f"ANOMALY_DETECTION_BAND(sts, {STS_ANOMALY_BAND_WIDTH})",
                "StsGetCallerIdentityCalls band",
            ),
        ],
        "threshold_metric_id": "band",
        "comparison_operator": "GreaterThanUpperThreshold",
        "evaluation_periods": 3,
        "datapoints_to_alarm": 3,
        # Published only while clients authenticate with IAM: absent is quiet.
        "treat_missing_data": MISSING,
    }


def alarm_definitions(targets: AlarmTargets) -> dict[str, dict[str, Any]]:
    """Render the §3.1 metric alarms, keyed by alarm-name suffix (FR-13).

    Each value holds the ``MetricAlarm`` inputs except the name and actions.
    The suffix is also the runbook heading in ``docs/sre-operations.md``.
    """
    if len(targets.failed_queue_names) != 3:
        raise ValueError("Alarm catalogue requires the three failed-* queues")
    memory_floor = _documentdb_memory_floor(targets.documentdb_instance_class)
    label = pulumi.Output.from_input(targets.request_count_label)
    load_balancer = label.apply(lambda value: _label_part(value, 0))
    target_group = label.apply(lambda value: _label_part(value, 1))
    documentdb = {"DBClusterIdentifier": targets.documentdb_cluster_identifier}
    definitions: dict[str, dict[str, Any]] = {
        f"dlq-{queue}": {
            **_metric(
                SQS_NAMESPACE,
                "ApproximateNumberOfMessagesVisible",
                "Maximum",
                60,
                QueueName=queue,
            ),
            **_window("GreaterThanOrEqualToThreshold", 1, 5, 5, NOT_BREACHING),
        }
        for queue in targets.failed_queue_names
    }
    definitions.update(
        {
            "alb-target-5xx": {
                **_metric(
                    ALB_NAMESPACE,
                    "HTTPCode_Target_5XX_Count",
                    "Sum",
                    60,
                    LoadBalancer=load_balancer,
                ),
                **_window("GreaterThanThreshold", 5, 5, 3, NOT_BREACHING),
            },
            "alb-elb-5xx": {
                **_metric(
                    ALB_NAMESPACE,
                    "HTTPCode_ELB_5XX_Count",
                    "Sum",
                    60,
                    LoadBalancer=load_balancer,
                ),
                **_window("GreaterThanThreshold", 5, 5, 3, NOT_BREACHING),
            },
            "alb-unhealthy-targets": {
                **_metric(
                    ALB_NAMESPACE,
                    "UnHealthyHostCount",
                    "Maximum",
                    60,
                    LoadBalancer=load_balancer,
                    TargetGroup=target_group,
                ),
                **_window("GreaterThanOrEqualToThreshold", 1, 3, 3, NOT_BREACHING),
            },
            "ecs-web-below-desired": _ecs_shortfall(
                targets.cluster_name, targets.service_names["web"]
            ),
            "ecs-worker-below-desired": _ecs_shortfall(
                targets.cluster_name, targets.service_names["worker"]
            ),
            # The busiest instance, not the cluster average (gate F2).
            "docdb-cpu": {
                "metric_queries": _member_math(
                    DOCUMENTDB_NAMESPACE,
                    "CPUUtilization",
                    "Average",
                    "MAX",
                    "DBInstanceIdentifier",
                    targets.documentdb_instance_identifiers,
                ),
                **_window("GreaterThanThreshold", 80, 3, 3, BREACHING),
            },
            "docdb-freeable-memory": {
                **_metric(
                    DOCUMENTDB_NAMESPACE, "FreeableMemory", "Minimum", 300, **documentdb
                ),
                **_window("LessThanThreshold", memory_floor, 3, 3, BREACHING),
            },
            # The member IDs are derived names, not outputs: the alarm can
            # exist before the group, so missing data holds its state.
            "redis-memory": {
                "metric_queries": _redis_math(
                    targets, "DatabaseMemoryUsagePercentage", "Maximum", "MAX"
                ),
                **_window("GreaterThanThreshold", 80, 3, 3, MISSING),
            },
            "redis-evictions": {
                "metric_queries": _redis_math(targets, "Evictions", "Sum", "SUM"),
                **_window("GreaterThanThreshold", 0, 1, 1, NOT_BREACHING),
            },
            "redis-auth-failures": {
                "metric_queries": _redis_math(
                    targets, "AuthenticationFailures", "Sum", "SUM"
                ),
                **_window("GreaterThanThreshold", 0, 1, 1, NOT_BREACHING),
            },
            "docdb-sts-calls": _sts_anomaly(targets.documentdb_cluster_identifier),
        }
    )
    return definitions


def stack_alarm_topic_arn(settings: StackSettings, account_id: str) -> str:
    """Return this stack's alarm topic ARN, the only alarm action (FR-13).

    The observability plane names its topic with it, and the hardened guard
    binds every metric alarm's actions to it.
    """
    return alarm_topic_arn(
        settings.region, account_id, build_resource_name(settings.stack_tag, "alarms")
    )


class ObservabilityPlane(pulumi.ComponentResource):
    """Own the encrypted alarm topic, its publish policy and alarms (AD-11)."""

    topic_arn: pulumi.Output[str]

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        runtime_cmk_arn: str,
        account_id: str,
        targets: AlarmTargets,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        """Validate the key and account, then declare the topic and its alarms.

        The policy document and every alarm action name the topic ARN built
        from the region, the account and the topic name, so both are plain
        strings at preview. The alarms wait for the topic policy.
        """
        key = require_runtime_cmk(runtime_cmk_arn)
        topic_name = build_resource_name(settings.stack_tag, "alarms")
        topic_arn = stack_alarm_topic_arn(settings, account_id)
        policy = require_reviewed_topic_policy(
            alarm_topic_policy(topic_arn, account_id), account_id, topic_arn
        )
        definitions = alarm_definitions(targets)
        super().__init__(
            "user-service-infrastructure:observability:Plane", name, None, opts
        )
        topic = aws.sns.Topic(
            "user-service-alarms",
            name=topic_name,
            kms_master_key_id=key,
            opts=pulumi.ResourceOptions(parent=self),
        )
        topic_policy = aws.sns.TopicPolicy(
            "user-service-alarms-policy",
            arn=topic.arn,
            policy=json.dumps(policy),
            opts=pulumi.ResourceOptions(parent=self),
        )
        # The hardened guard admits an alarm only with exactly these actions.
        for suffix, definition in definitions.items():
            aws.cloudwatch.MetricAlarm(
                f"user-service-alarm-{suffix}",
                name=build_resource_name(settings.stack_tag, suffix, max_length=255),
                actions_enabled=True,
                alarm_actions=[topic_arn],
                ok_actions=[topic_arn],
                **definition,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[topic_policy]),
            )
        self.topic_arn = topic.arn
        self.register_outputs({"topicArn": self.topic_arn})
