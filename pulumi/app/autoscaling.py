"""Step-2 ECS service autoscaling and create-only start/stop (S2.1, FR-11, AD-10).

Only a ``workload_step`` 2 projection renders this plane (AD-18, AD-25). Per
service it renders one scalable target and one one-time ``ScheduledAction``
per unconsumed ``scaling.starts`` and ``scaling.stops`` entry; the web service
also gets its two target-tracking policies. The worker backlog policy is
S2.2's. Every value comes from the reviewed contract (D-16).

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
from app.environment import StackSettings, build_resource_name

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


def start_capacity(capacity: dict[str, Any]) -> tuple[int, int]:
    """Return the start bounds, ``(max(contract min, 1), contract max)``."""
    return max(capacity["min_capacity"], 1), capacity["max_capacity"]


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
                else []
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
