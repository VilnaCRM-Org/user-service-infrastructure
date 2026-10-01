"""Step-2 ECS service autoscaling and create-only start/stop (FR-11, FR-12, AD-10).

Only a ``workload_step`` 2 projection renders this plane (AD-18, AD-25). Per
service it renders one scalable target and one one-time ``ScheduledAction``
per unconsumed ``scaling.starts`` and ``scaling.stops`` entry. The web service
also gets its two target-tracking policies (S2.1) and the worker its backlog
policy (S2.2). Every value comes from the reviewed contract (D-16).

- The target registers ``min = max(contract min, 1)`` and the contract max.
  It ignores ``minCapacity`` and ``maxCapacity``, which the one-time and the
  TEST recurring actions change (AD-23). Its ``suspendedState`` renders the
  persistent TEST hold flag ``scaling.scheduled_scaling_suspended``, so an
  operation that keeps the flag renders the target unchanged (R6-m7).
- ``<svc>-start-<seq>`` scales to ``max(contract min, 1)`` and the contract
  max at ``at(<entry at>)``, after the target and every policy of the service.
  ``<svc>-stop-<seq>`` scales to ``min = max = 0`` at its own entry time.
- An entry's rendered inputs depend only on that entry, so appending an entry
  never changes an earlier action (R5-M3). A ``start-<seq>`` or
  ``stop-<seq>`` name in ``scaling.consumed`` is not rendered.
- The worker backlog policy (A-17) tracks the visible messages of the three
  work queues, summed and divided by the worker's Container Insights
  ``RunningTaskCount``. The divisor is ``max(RunningTaskCount, 1)``, so a zero
  count never divides by zero (the AD-10 zero-task guard; the floor of 1 is a
  planning choice). If any input has no datapoint, the returned series has
  none and the policy stays in INSUFFICIENT_DATA; it never divides by zero.
  No dead-letter or health-check queue enters the math.
"""

from __future__ import annotations

from typing import Any, Optional

import pulumi_aws as aws
from pulumi_aws.appautoscaling import (
    PolicyTargetTrackingScalingPolicyConfigurationArgs as TrackingArgs,
)
from pulumi_aws.appautoscaling import (
    ScheduledActionScalableTargetActionArgs as ActionArgs,
)

import pulumi
from app.compute import ScalableServices
from app.environment import QueueSettings, StackSettings, build_resource_name

SERVICES = ("web", "worker")
ECS_NAMESPACE = "ecs"
ECS_DIMENSION = "ecs:service:DesiredCount"
# The one-time and recurring actions own the live bounds (AD-23).
TARGET_IGNORED_CHANGES = ["minCapacity", "maxCapacity"]
# The web target-tracking policies: logical name, AWS name suffix, metric and
# the contract key of its target value (FR-11, D-16).
REQUEST_COUNT_METRIC = "ALBRequestCountPerTarget"
WEB_POLICIES = (
    (
        "web-cpu-tracking",
        "web-cpu",
        "ECSServiceAverageCPUUtilization",
        "cpu_utilization_percent",
    ),
    (
        "web-request-tracking",
        "web-requests",
        REQUEST_COUNT_METRIC,
        "alb_request_count_per_target",
    ),
)
ACTION_KINDS = ("start", "stop")
# The worker backlog policy (FR-12, A-17): the three work queues, each a
# ``QueueSettings`` field that messaging.py redrives to its own dead-letter
# queue. The field name is also the metric query id of that queue.
BACKLOG_POLICY = ("worker-backlog-tracking", "worker-backlog")
WORK_QUEUES = ("send_email", "insert_user_batch", "domain_events")
# The only division is by ``tasks = max(RunningTaskCount, 1)``: both IF branches
# are at least 1, so a zero count never divides by zero (AD-10). If any input
# has no datapoint, the series has none (INSUFFICIENT_DATA); S4.6 step 12
# observes zero-task publishing before FILL() is considered.
BACKLOG_EXPRESSIONS = (
    ("backlog", " + ".join(WORK_QUEUES), False),
    ("tasks", "IF(running_tasks > 1, running_tasks, 1)", False),
    ("backlog_per_task", "backlog / tasks", True),
)


def start_capacity(capacity: dict[str, Any]) -> tuple[int, int]:
    """Return the start bounds, ``(max(contract min, 1), contract max)``."""
    return max(capacity["min_capacity"], 1), capacity["max_capacity"]


def work_queue_names(queues: QueueSettings) -> tuple[tuple[str, str], ...]:
    """Return ``(query id, queue name)`` for each of the three work queues.

    A work queue that repeats another or names a dead-letter or health-check
    queue fails: only the three work queues enter the backlog (FR-12 N).
    """
    names = tuple((field, getattr(queues, field)) for field in WORK_QUEUES)
    work = {name for _, name in names}
    others = {name for field, name in vars(queues).items() if field not in WORK_QUEUES}
    if len(work) != len(WORK_QUEUES) or work & others:
        raise ValueError(
            "The worker backlog sums exactly the three distinct work queues; "
            "no dead-letter or health-check queue may enter it (FR-12)."
        )
    return names


def _visible_messages(query_id: str, queue: str) -> dict[str, Any]:
    """One work queue's ``ApproximateNumberOfMessagesVisible`` (``Sum``, A-17)."""
    return {
        "id": query_id,
        "metric_stat": {
            "metric": {
                "metric_name": "ApproximateNumberOfMessagesVisible",
                "namespace": "AWS/SQS",
                "dimensions": [{"name": "QueueName", "value": queue}],
            },
            "stat": "Sum",
        },
        "return_data": False,
    }


def _running_tasks(services: ScalableServices) -> dict[str, Any]:
    """The worker's Container Insights ``RunningTaskCount`` (``Average``, A-17)."""
    return {
        "id": "running_tasks",
        "metric_stat": {
            "metric": {
                "metric_name": "RunningTaskCount",
                "namespace": "ECS/ContainerInsights",
                "dimensions": [
                    {"name": "ClusterName", "value": services.cluster_name},
                    {"name": "ServiceName", "value": services.service_names["worker"]},
                ],
            },
            "stat": "Average",
        },
        "return_data": False,
    }


def rendered_entries(scaling: dict[str, Any]) -> list[tuple[str, int, str]]:
    """Return ``(kind, seq, at)`` for every entry not in ``scaling.consumed``."""
    consumed = set(scaling["consumed"])
    return [
        (kind, entry["seq"], entry["at"])
        for kind in ACTION_KINDS
        for entry in scaling[kind + "s"]
        if f"{kind}-{entry['seq']}" not in consumed
    ]


class AutoscalingPlane(pulumi.ComponentResource):
    """Render the step-2 scalable targets, web policies and one-time actions."""

    def __init__(
        self,
        name: str,
        *,
        settings: StackSettings,
        services: ScalableServices,
        scaling: dict[str, Any],
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        # Refuse a non-work queue before any resource registers (FR-12 N).
        queues = work_queue_names(settings.queues)
        super().__init__(
            "user-service-infrastructure:autoscaling:Plane", name, None, opts
        )
        suspended = scaling.get("scheduled_scaling_suspended", False)
        entries = rendered_entries(scaling)
        for service in SERVICES:
            capacity = scaling["capacity"][service]
            target = self._target(service, services, capacity, suspended)
            policies = (
                self._web_policies(settings, target, services, capacity)
                if service == "web"
                else [
                    self._backlog_policy(settings, target, services, queues, capacity)
                ]
            )
            for kind, seq, at in entries:
                self._action(service, kind, seq, at, target, policies, capacity)
        self.register_outputs({})

    def _target(
        self,
        service: str,
        services: ScalableServices,
        capacity: dict[str, Any],
        suspended: bool,
    ) -> aws.appautoscaling.Target:
        minimum, maximum = start_capacity(capacity)
        return aws.appautoscaling.Target(
            f"{service}-scaling-target",
            min_capacity=minimum,
            max_capacity=maximum,
            resource_id=pulumi.Output.concat(
                "service/", services.cluster_name, "/", services.service_names[service]
            ),
            scalable_dimension=ECS_DIMENSION,
            service_namespace=ECS_NAMESPACE,
            suspended_state=aws.appautoscaling.TargetSuspendedStateArgs(
                dynamic_scaling_in_suspended=False,
                dynamic_scaling_out_suspended=False,
                scheduled_scaling_suspended=suspended,
            ),
            opts=pulumi.ResourceOptions(
                parent=self, ignore_changes=list(TARGET_IGNORED_CHANGES)
            ),
        )

    def _web_policies(
        self,
        settings: StackSettings,
        target: aws.appautoscaling.Target,
        services: ScalableServices,
        capacity: dict[str, Any],
    ) -> list[aws.appautoscaling.Policy]:
        """CPU and ALB requests per target, both with scale-in enabled (D-16)."""
        tracking = capacity["target_tracking"]
        policies = []
        for logical_name, suffix, metric, value_key in WEB_POLICIES:
            # The request metric names the web ALB and target group (AD-10).
            specification: dict[str, Any] = {"predefined_metric_type": metric}
            if metric == REQUEST_COUNT_METRIC:
                specification["resource_label"] = services.request_count_label
            configuration = TrackingArgs(
                target_value=tracking[value_key],
                predefined_metric_specification=specification,
                scale_out_cooldown=tracking["scale_out_cooldown_seconds"],
                scale_in_cooldown=tracking["scale_in_cooldown_seconds"],
                disable_scale_in=False,
            )
            policies.append(
                aws.appautoscaling.Policy(
                    logical_name,
                    name=build_resource_name(settings.stack_tag, suffix),
                    policy_type="TargetTrackingScaling",
                    resource_id=target.resource_id,
                    scalable_dimension=target.scalable_dimension,
                    service_namespace=target.service_namespace,
                    target_tracking_scaling_policy_configuration=configuration,
                    opts=pulumi.ResourceOptions(parent=self),
                )
            )
        return policies

    def _backlog_policy(
        self,
        settings: StackSettings,
        target: aws.appautoscaling.Target,
        services: ScalableServices,
        queues: tuple[tuple[str, str], ...],
        capacity: dict[str, Any],
    ) -> aws.appautoscaling.Policy:
        """Visible work-queue messages per running worker task (FR-12, A-17).

        Metric math: ``backlog`` sums the three queues' visible messages,
        ``tasks`` is ``max(RunningTaskCount, 1)`` and ``backlog / tasks`` is
        the one returned series. Scale-in stays enabled (D-16).
        """
        backlog = capacity["backlog"]
        metrics = [_visible_messages(query_id, queue) for query_id, queue in queues]
        metrics.append(_running_tasks(services))
        metrics.extend(
            {"id": query_id, "expression": expression, "return_data": returned}
            for query_id, expression, returned in BACKLOG_EXPRESSIONS
        )
        logical_name, suffix = BACKLOG_POLICY
        return aws.appautoscaling.Policy(
            logical_name,
            name=build_resource_name(settings.stack_tag, suffix),
            policy_type="TargetTrackingScaling",
            resource_id=target.resource_id,
            scalable_dimension=target.scalable_dimension,
            service_namespace=target.service_namespace,
            target_tracking_scaling_policy_configuration=TrackingArgs(
                target_value=backlog["visible_messages_per_task"],
                customized_metric_specification={"metrics": metrics},
                scale_out_cooldown=backlog["scale_out_cooldown_seconds"],
                scale_in_cooldown=backlog["scale_in_cooldown_seconds"],
                disable_scale_in=False,
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _action(
        self,
        service: str,
        kind: str,
        seq: int,
        at: str,
        target: aws.appautoscaling.Target,
        policies: list[aws.appautoscaling.Policy],
        capacity: dict[str, Any],
    ) -> aws.appautoscaling.ScheduledAction:
        """One one-time action; a start waits for the target and its policies."""
        name = f"{service}-{kind}-{seq}"
        minimum, maximum = start_capacity(capacity) if kind == "start" else (0, 0)
        return aws.appautoscaling.ScheduledAction(
            name,
            name=name,
            resource_id=target.resource_id,
            scalable_dimension=target.scalable_dimension,
            service_namespace=target.service_namespace,
            schedule=f"at({at})",
            scalable_target_action=ActionArgs(
                min_capacity=minimum, max_capacity=maximum
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[target, *policies] if kind == "start" else [target],
            ),
        )
