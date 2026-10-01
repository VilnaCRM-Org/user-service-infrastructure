"""S2.1 web autoscaling: FR-11 rows, N, B1, B2 and B3 (AD-10, D-16).

The contract holds the D-16 capacity and target-tracking values. The step-2
projection renders, per service, the scalable target and the one-time start
and stop actions, plus the two web target-tracking policies. Every resource
and ``ignore_changes`` of this story renders only for a ``workload_step``
projection (AD-25), so the pre-hardening graph is unchanged.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from app.autoscaling import SERVICES, start_capacity
from poc_contract import _capacity_semantics, _validate_document, validate
from test_poc_contract import change
from test_poc_contract_hardened import hardened, step_two
from test_poc_workload_phase import AT, TAGS, graph

TARGET = "aws:appautoscaling/target:Target"
POLICY = "aws:appautoscaling/policy:Policy"
ACTION = "aws:appautoscaling/scheduledAction:ScheduledAction"
SERVICE = "aws:ecs/service:Service"
AUTOSCALING = (TARGET, POLICY, ACTION)
# D-16 TEST values, as the synthetic hardened fixture holds them.
COOLDOWNS = {"scale_out_cooldown_seconds": 60, "scale_in_cooldown_seconds": 300}
TEST_CAPACITY = {
    "web": {
        "min_capacity": 1,
        "max_capacity": 2,
        "target_tracking": {
            "cpu_utilization_percent": 60,
            "alb_request_count_per_target": 1000,
            **COOLDOWNS,
        },
    },
    "worker": {
        "min_capacity": 1,
        "max_capacity": 2,
        "backlog": {"visible_messages_per_task": 100, **COOLDOWNS},
    },
}
# D-16 PROD values; the PROD schema itself is S4.14's.
PROD_CAPACITY = {
    "web": {**TEST_CAPACITY["web"], "min_capacity": 2, "max_capacity": 6},
    "worker": {**TEST_CAPACITY["worker"], "min_capacity": 2, "max_capacity": 4},
}
REQUEST_LABEL = "app/user-service-alb/123/targetgroup/user-service-target-group/123"


@pytest.fixture(scope="module")
def render(tmp_path_factory):
    """Render each probe variant once; every render must succeed."""
    cache = {}

    def get(mutation, mode="hardened"):
        key = (mode, mutation)
        if key not in cache:
            receipt = graph(tmp_path_factory.mktemp("autoscaling"), mode, mutation)
            assert receipt["error"] is None
            cache[key] = receipt["registrations"]
        return cache[key]

    return get


def _of(rows, *kinds):
    return {name: row for name, row in rows.items() if row["type"] in kinds}


def _canonical(value):
    return json.dumps(value, sort_keys=True)


def _scaled(**scaling):
    """A step-2 contract with the given ``scaling`` entries."""
    contract = step_two()
    contract["scaling"].update(scaling)
    return contract


# Contract rows (FR-11 values and negatives, N).


def test_the_hardened_fixture_holds_the_d16_test_values():
    assert hardened()["scaling"]["capacity"] == TEST_CAPACITY
    _capacity_semantics(TEST_CAPACITY, "test")
    _capacity_semantics(PROD_CAPACITY, "prod")


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("scaling.capacity", None),
        ("scaling.capacity.web.min_capacity", 0),
        ("scaling.capacity.worker.max_capacity", 0),
        ("scaling.capacity.web.max_capacity", 5001),
        ("scaling.capacity.web.min_capacity", "1"),
        ("scaling.capacity.web.target_tracking.cpu_utilization_percent", 0),
        ("scaling.capacity.web.target_tracking.cpu_utilization_percent", 101),
        ("scaling.capacity.web.target_tracking.alb_request_count_per_target", 0),
        ("scaling.capacity.web.target_tracking.scale_in_cooldown_seconds", -1),
        ("scaling.capacity.worker.backlog.visible_messages_per_task", 0),
        ("scaling.capacity.worker.backlog.scale_out_cooldown_seconds", -1),
        ("scaling.capacity.web.target_tracking.disable_scale_in", True),
        ("scaling.capacity.web.backlog", TEST_CAPACITY["worker"]["backlog"]),
        ("scaling.capacity.worker.target_tracking", {}),
        ("scaling.capacity.api", TEST_CAPACITY["web"]),
    ],
)
def test_the_closed_capacity_schema_fails_closed(path, value):
    """FR-11 N: a start minimum below 1, and any unreviewed key, fail."""
    contract = hardened()
    if value is None:
        del contract["scaling"]["capacity"]
    else:
        change(contract, path, value)
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


@pytest.mark.parametrize(
    "path",
    [
        "web.min_capacity",
        "worker.max_capacity",
        "web.target_tracking.cpu_utilization_percent",
        "web.target_tracking.alb_request_count_per_target",
        "web.target_tracking.scale_out_cooldown_seconds",
        "web.target_tracking.scale_in_cooldown_seconds",
        "worker.backlog.visible_messages_per_task",
        "worker.backlog.scale_out_cooldown_seconds",
        "worker.backlog.scale_in_cooldown_seconds",
    ],
)
def test_capacity_integers_must_be_exact(path):
    """``1.0`` passes the schema's ``integer`` but is not an exact integer."""
    contract = hardened()
    change(contract, f"scaling.capacity.{path}", 1.0)
    with pytest.raises(ValueError, match="exact"):
        _validate_document(contract)


@pytest.mark.parametrize("service", SERVICES)
def test_a_minimum_above_the_maximum_fails(service):
    """FR-11 N: min > max raises."""
    contract = hardened()
    contract["scaling"]["capacity"][service]["min_capacity"] = 3
    with pytest.raises(ValueError, match="minimum must not exceed"):
        _validate_document(contract)


@pytest.mark.parametrize(
    ("service", "minimum", "environment", "message"),
    [
        ("web", 0, "test", "at least 1"),
        ("worker", 0, "prod", "at least 1"),
        ("web", 1, "prod", "PROD"),
        ("worker", 1, "prod", "PROD"),
    ],
)
def test_capacity_semantics_refuse_a_low_minimum(
    service, minimum, environment, message
):
    """FR-11 N: PROD min < 1 raises; D-16 keeps one PROD task per AZ (min 2)."""
    capacity = copy.deepcopy(PROD_CAPACITY if environment == "prod" else TEST_CAPACITY)
    capacity[service]["min_capacity"] = minimum
    with pytest.raises(ValueError, match=message):
        _capacity_semantics(capacity, environment)


def test_a_start_action_minimum_is_at_least_one():
    """AD-10: ``min = max(contract min, 1)``; exactly 1 is admitted."""
    assert start_capacity(TEST_CAPACITY["web"]) == (1, 2)
    assert start_capacity(PROD_CAPACITY["web"]) == (2, 6)
    assert start_capacity({"min_capacity": 0, "max_capacity": 2}) == (1, 2)


START_1 = [{"seq": 1, "at": AT["start-1"]}]
STOP_1 = [{"seq": 1, "at": AT["stop-1"]}]


@pytest.mark.parametrize(
    "change_target",
    [
        lambda scaling: scaling.update(scheduled_scaling_suspended=True),
        lambda scaling: scaling["capacity"]["web"].update(max_capacity=3),
        lambda scaling: scaling["capacity"]["worker"].update(min_capacity=2),
    ],
)
def test_a_stop_in_a_plan_that_also_changes_the_target_fails(change_target):
    """N: a stop action in a plan that also changes the target fails."""
    previous = _scaled(starts=START_1)
    contract = _scaled(starts=START_1, stops=STOP_1)
    change_target(contract["scaling"])
    _validate_document(contract)
    with pytest.raises(ValueError, match="stop plan must not change"):
        validate(contract, previous=previous)


def test_a_stop_alone_and_a_later_hold_are_valid_transitions():
    """The stop and the hold are two plans (AD-10); each alone is valid."""
    start = _scaled(starts=START_1)
    stop = _scaled(starts=START_1, stops=STOP_1)
    hold = _scaled(starts=START_1, stops=STOP_1, scheduled_scaling_suspended=True)
    assert len(validate(stop, previous=start)) == 64
    assert len(validate(hold, previous=stop)) == 64
    # A false flag equals an absent one: no target change, so still a stop.
    stop["scaling"]["scheduled_scaling_suspended"] = False
    assert len(validate(stop, previous=start)) == 64


# Rendering rows (FR-11 values, AD-10, AD-25).


def test_step_one_and_pre_hardening_render_no_autoscaling(render):
    """FR-34 B and the AD-25 transition rule: only step 2 renders it."""
    for rows in (render("none"), render("none", "workload")):
        assert not _of(rows, *AUTOSCALING)
        assert "autoscaling" not in rows


def test_desired_count_is_ignored_only_on_the_hardened_services(render):
    """FR-11 / FR-32: Pulumi ignores ``desiredCount`` (AD-23)."""
    for mutation in ("none", "step2"):
        services = _of(render(mutation), SERVICE)
        assert len(services) == 2
        assert all(
            row["ignore_changes"] == ["desiredCount"] for row in services.values()
        )
    legacy = _of(render("none", "workload"), SERVICE)
    assert len(legacy) == 2
    assert all(row["ignore_changes"] == [] for row in legacy.values())


def _resource_id(rows, service):
    cluster = rows["user-service-ecs-cluster"]["inputs"]["name"]
    name = rows[f"user-service-{service}-service"]["inputs"]["name"]
    return f"service/{cluster}/{name}"


@pytest.mark.parametrize("service", SERVICES)
def test_each_service_has_one_target_at_its_start_capacity(render, service):
    """FR-11: target ``min = max(contract min, 1)`` and ``max = contract max``."""
    rows = render("step2")
    target = rows[f"{service}-scaling-target"]
    assert target["type"] == TARGET
    assert target["parent"] == rows["autoscaling"]["urn"]
    assert target["ignore_changes"] == ["minCapacity", "maxCapacity"]
    inputs = target["inputs"]
    assert inputs == {
        "minCapacity": 1,
        "maxCapacity": 2,
        "resourceId": _resource_id(rows, service),
        "scalableDimension": "ecs:service:DesiredCount",
        "serviceNamespace": "ecs",
        "suspendedState": {
            "dynamicScalingInSuspended": False,
            "dynamicScalingOutSuspended": False,
            "scheduledScalingSuspended": False,
        },
        "tags": TAGS,
    }
    assert rows[f"user-service-{service}-service"]["urn"] in target["dependencies"]


def test_the_web_service_has_the_two_d16_target_tracking_policies(render):
    """FR-11: CPU 60 % and ALB requests 1000 per target; 60 s out, 300 s in."""
    rows = render("step2")
    policies = _of(rows, POLICY)
    assert set(policies) == {"web-cpu-tracking", "web-request-tracking"}
    metrics = {
        "web-cpu-tracking": (
            60,
            {"predefinedMetricType": "ECSServiceAverageCPUUtilization"},
            "user-service-infrastructure-test-web-cpu",
        ),
        "web-request-tracking": (
            1000,
            {
                "predefinedMetricType": "ALBRequestCountPerTarget",
                "resourceLabel": REQUEST_LABEL,
            },
            "user-service-infrastructure-test-web-requests",
        ),
    }
    target = rows["web-scaling-target"]
    for name, (value, metric, policy_name) in metrics.items():
        row = policies[name]
        assert row["inputs"] == {
            "name": policy_name,
            "policyType": "TargetTrackingScaling",
            "resourceId": _resource_id(rows, "web"),
            "scalableDimension": "ecs:service:DesiredCount",
            "serviceNamespace": "ecs",
            "targetTrackingScalingPolicyConfiguration": {
                "targetValue": value,
                "predefinedMetricSpecification": metric,
                "scaleOutCooldown": 60,
                "scaleInCooldown": 300,
                "disableScaleIn": False,
            },
        }
        assert target["urn"] in row["dependencies"]
        assert row["ignore_changes"] == []


@pytest.mark.parametrize("service", SERVICES)
def test_start_and_stop_actions_render_their_entry_times(render, service):
    """FR-11: ``<svc>-start-<seq>`` at ``min = max(contract min, 1)`` after the
    target and its policies; ``<svc>-stop-<seq>`` at ``min = max = 0``."""
    rows = render("step2-restart")
    actions = _of(rows, ACTION)
    names = {f"{service}-{entry}" for entry in ("start-1", "stop-1", "start-2")}
    assert names <= set(actions)
    target = rows[f"{service}-scaling-target"]
    policies = [
        row["urn"]
        for name, row in _of(rows, POLICY).items()
        if name.startswith(service)
    ]
    for entry in ("start-1", "stop-1", "start-2"):
        row = actions[f"{service}-{entry}"]
        stop = entry.startswith("stop")
        assert row["inputs"] == {
            "name": f"{service}-{entry}",
            "resourceId": _resource_id(rows, service),
            "scalableDimension": "ecs:service:DesiredCount",
            "serviceNamespace": "ecs",
            "schedule": f"at({AT[entry]})",
            "scalableTargetAction": (
                {"minCapacity": 0, "maxCapacity": 0}
                if stop
                else {"minCapacity": 1, "maxCapacity": 2}
            ),
        }
        assert target["urn"] in row["dependencies"]
        if not stop:
            assert set(policies) <= set(row["dependencies"])
    assert len(policies) == (2 if service == "web" else 0)


def _actions(rows):
    return {name: row for name, row in _of(rows, ACTION).items()}


@pytest.mark.parametrize(
    ("before", "after", "added"),
    [
        ("step2", "step2-stop", "stop-1"),
        ("step2-stop", "step2-restart", "start-2"),
    ],
)
def test_appending_an_entry_renders_one_new_urn_per_service(
    render, before, after, added
):
    """B1: one new URN per service; every earlier action is byte-equal."""
    old, new = render(before), render(after)
    assert set(new) - set(old) == {f"{service}-{added}" for service in SERVICES}
    assert set(old) <= set(new)
    for name in _actions(old):
        for key in ("schedule", "scalableTargetAction"):
            assert _canonical(new[name]["inputs"][key]) == _canonical(
                old[name]["inputs"][key]
            )
    # The stop plan changes nothing else, including either target (N).
    for name, row in old.items():
        assert _canonical(new[name]["inputs"]) == _canonical(row["inputs"])


def test_a_changed_entry_time_changes_only_that_schedule(render):
    """B2: a changed ``at`` changes that URN's schedule (S4.9 refuses it)."""
    base, moved = render("step2-restart"), render("step2-moved")
    assert set(moved) == set(base)
    changed = {
        name
        for name, row in moved.items()
        if _canonical(row["inputs"]) != _canonical(base[name]["inputs"])
    }
    assert changed == {f"{service}-start-1" for service in SERVICES}
    for name in changed:
        assert moved[name]["inputs"]["schedule"] == "at(2026-10-02T09:00:00)"
        assert base[name]["inputs"]["schedule"] == f"at({AT['start-1']})"


def test_a_consumed_entry_is_not_rendered_and_changes_no_other_urn(render):
    """B2 / AD-10: a name in ``scaling.consumed`` is not rendered."""
    base, consumed = render("step2-restart"), render("step2-consumed")
    assert set(base) - set(consumed) == {f"{s}-start-1" for s in SERVICES}
    assert set(consumed) <= set(base)
    for name, row in consumed.items():
        assert _canonical(row["inputs"]) == _canonical(base[name]["inputs"])
        assert row["urn"] == base[name]["urn"]


def test_a_policy_update_during_a_hold_renders_every_target_unchanged(render):
    """B3 (R6-m7): with the flag true, no ``Target`` update."""
    stop, hold, update = (
        render(mutation)
        for mutation in ("step2-stop", "step2-hold", "step2-policy-update")
    )
    for service in SERVICES:
        name = f"{service}-scaling-target"
        assert _canonical(update[name]["inputs"]) == _canonical(hold[name]["inputs"])
        assert hold[name]["inputs"]["suspendedState"]["scheduledScalingSuspended"]
        # The hold changes only ``suspendedState.scheduledScalingSuspended``.
        expected = copy.deepcopy(stop[name]["inputs"])
        expected["suspendedState"]["scheduledScalingSuspended"] = True
        assert _canonical(hold[name]["inputs"]) == _canonical(expected)
    for name, row in hold.items():
        assert _canonical(update[name]["inputs"]) == _canonical(row["inputs"])
        if row["type"] != TARGET:
            assert _canonical(stop[name]["inputs"]) == _canonical(row["inputs"])
