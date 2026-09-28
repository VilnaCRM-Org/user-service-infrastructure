"""First topology checks retain registry owners and never enable capabilities."""

import base64
import copy
import importlib
import json

import pytest
from test_poc_registry_phase_entrypoint import source
from test_poc_registry_plan import case
from test_poc_workload_phase import graph
from test_poc_workload_phase_entrypoint import fixture

gate = importlib.import_module("poc_workload_topology")
bridge = importlib.import_module("poc_workload_phase_entrypoint")


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    value = graph(tmp_path_factory.mktemp("topology"), "bridge")
    assert value["error"] is None
    return value["registrations"]


def _native_numbers(kind, inputs):
    """Restore integer JSON shapes lost by the SDK MockMonitor wire format."""
    if kind == "aws:ecs/service:Service":
        # SDK MockMonitor encodes numeric inputs as floats; native Pulumi
        # saved plans retain desiredCount as an integer.
        assert inputs["desiredCount"] == 2.0
        inputs["desiredCount"] = 2
        for target in inputs.get("loadBalancers", []):
            target["containerPort"] = int(target["containerPort"])
    if kind == "aws:lb/targetGroup:TargetGroup":
        for field in ("port", "deregistrationDelay"):
            inputs[field] = int(inputs[field])
        for field in (
            "healthyThreshold",
            "unhealthyThreshold",
            "interval",
            "timeout",
        ):
            inputs["healthCheck"][field] = int(inputs["healthCheck"][field])
    for field in {
        "aws:docdb/cluster:Cluster": ("backupRetentionPeriod",),
        "aws:elasticache/replicationGroup:ReplicationGroup": (
            "snapshotRetentionLimit",
        ),
        "aws:sqs/queue:Queue": (
            "receiveWaitTimeSeconds",
            "visibilityTimeoutSeconds",
        ),
    }.get(kind, ()):
        # The native saved-plan JSON keeps these integer settings.
        assert type(inputs[field]) is float and inputs[field].is_integer()
        inputs[field] = int(inputs[field])


@pytest.fixture
def data(captured):
    value = case("repeat")
    contract, images = fixture()
    # This graph uses the synthetic composition release; bind the projection to
    # those exact digests instead of a different image-observation test fixture.
    for kind in ("web", "worker"):
        container = json.loads(
            captured[f"user-service-{kind}-task"]["inputs"]["containerDefinitions"]
        )[0]
        images[kind]["uri"] = container["image"]
        contract["workload"]["release"][kind]["digest"] = container["image"].split("@")[
            1
        ]
    value["projection"] = bridge.project_workload_phase(
        source(contract), contract, images
    )
    existing = {row["urn"] for row in value["prior_resources"]}
    expected = gate.expected_graph()
    expected_names = {
        urn.rsplit("::", 1)[-1]: urn
        for urn, row in expected.items()
        if not row[0].startswith("pulumi:providers:")
    }
    assert set(captured) == set(expected_names)
    # SDK MockMonitor does not preserve native ancestor URNs. Native CLI tests
    # below independently verify those; unit fixtures compare logical owners.
    rows = {}
    for name, captured_row in captured.items():
        row = copy.deepcopy(captured_row)
        urn = expected_names[name]
        assert row["type"] == expected[urn][0]
        assert row["parent"].rsplit("::", 1)[-1] == expected[urn][1].rsplit("::", 1)[-1]
        row["dependencies"] = [
            expected_names[item.rsplit("::", 1)[-1]] for item in row["dependencies"]
        ]
        rows[urn] = row
    for urn, (kind, parent, custom, protect) in expected.items():
        if urn in existing:
            continue
        row = rows.get(urn, {})
        inputs = copy.deepcopy(row.get("inputs", {}))
        _native_numbers(kind, inputs)
        if "secretString" in inputs:
            inputs["secretString"] = {
                gate.unchanged.PULUMI_MARKER_SIGNATURE: (
                    gate.unchanged.PULUMI_MARKER_SENTINEL
                ),
                "value": "synthetic",
            }
        package = kind.split(":", 1)[0]
        provider = ""
        if package in ("aws", "random", "tls"):
            target = next(
                key
                for key, candidate in expected.items()
                if candidate[0] == f"pulumi:providers:{package}"
            )
            provider = (
                target
                + "::"
                + ("provider-id" if package == "aws" else gate.registry.UNKNOWN)
            )
        goal = {
            "type": kind,
            "name": urn.rsplit("::", 1)[-1],
            "custom": custom,
            "parent": parent,
            "protect": protect,
            "provider": provider,
            "inputDiff": {"adds": inputs},
            "outputDiff": {},
            "dependencies": row.get("dependencies", []),
            "additionalSecretOutputs": row.get("additional_secret_outputs", []),
            "structuredAliases": gate._sdk_aliases(kind),
        }
        value["saved_plan"]["resourcePlans"][urn] = {
            "goal": goal,
            "steps": ["create"],
            "state": None,
            "seed": base64.b64encode(bytes(32)).decode(),
        }
        if not kind.startswith("pulumi:providers:"):
            state = {
                key: val
                for key, val in goal.items()
                if key in gate.registry.STATE_FIELDS
            }
            state.update(urn=urn, inputs=gate.unchanged._redacted(inputs))
            value["preview"]["steps"].append(
                {"urn": urn, "op": "create", "newState": state}
            )
    return value


def test_exact_composition_topology_matches_and_cannot_authorize_execution(data):
    before = copy.deepcopy(data)
    gate.validate_first_workload_topology(**data)
    with pytest.raises(
        ValueError, match="native-capability-and-input-admission-required"
    ):
        gate.admit_first_workload_plan(**data)
    assert data == before


@pytest.mark.parametrize(
    "owner,target",
    [
        ("user-service-alb", "user-service-alb-sg"),
        ("user-service-alb", "user-service-app-subnet-1"),
        ("user-service-alb-sg", "user-service-vpc-link-sg"),
        ("user-service-vpc-link-sg", "user-service-vpc"),
        ("user-service-https-listener", "user-service-alb"),
        ("user-service-target-group", "user-service-vpc"),
        ("user-service-web-service", "user-service-web-task"),
        ("user-service-web-service", "user-service-https-listener"),
        ("user-service-worker-service", "user-service-worker-task"),
        ("user-service-worker-service", "user-service-service-sg"),
    ],
)
def test_first_workload_requires_fixed_private_resource_dependencies(
    data, owner, target
):
    owner_urn = next(
        urn for urn in data["saved_plan"]["resourcePlans"] if urn.endswith("::" + owner)
    )
    target_urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::" + target)
    )
    goal = data["saved_plan"]["resourcePlans"][owner_urn]["goal"]
    assert target_urn in goal["dependencies"]
    goal["dependencies"].remove(target_urn)
    step = next(row for row in data["preview"]["steps"] if row["urn"] == owner_urn)
    step["newState"]["dependencies"] = [
        dependency
        for dependency in step["newState"]["dependencies"]
        if dependency != target_urn
    ]
    with pytest.raises(ValueError, match="workload-first-topology-dependencies"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize("task", ["web", "worker"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("executionRoleArn", "arn:aws:iam::891377212104:role/foreign"),
        ("taskRoleArn", "arn:aws:iam::933245420672:role/foreign"),
        ("networkMode", "host"),
        ("requiresCompatibilities", ["EC2"]),
        ("requiresCompatibilities", ["FARGATE", "EC2"]),
        (
            "runtimePlatform",
            {"cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX"},
        ),
        (
            "runtimePlatform",
            {
                "cpuArchitecture": "X86_64",
                "operatingSystemFamily": "WINDOWS_SERVER_2022_CORE",
            },
        ),
        ("runtimePlatform", {"cpuArchitecture": "X86_64"}),
        (
            "runtimePlatform",
            {
                "cpuArchitecture": "X86_64",
                "operatingSystemFamily": "LINUX",
                "foreign": True,
            },
        ),
    ]
    + [
        (field, value)
        for field in (
            "executionRoleArn",
            "taskRoleArn",
            "networkMode",
            "requiresCompatibilities",
            "runtimePlatform",
        )
        for value in (None, gate.registry.UNKNOWN)
    ],
)
def test_matching_plan_and_preview_cannot_change_task_execution_inputs(
    data, task, field, value
):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith(f"::user-service-{task}-task")
    )
    inputs = data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"]["adds"]
    preview_inputs = next(
        step["newState"]["inputs"]
        for step in data["preview"]["steps"]
        if step["urn"] == urn
    )
    for target in (inputs, preview_inputs):
        if value is None:
            target.pop(field)
        else:
            target[field] = copy.deepcopy(value)
    with pytest.raises(ValueError, match="workload-task-execution-inputs"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "name,path,value,error",
    [
        ("user-service-alb", ("internal",), False, "private-alb-inputs"),
        (
            "user-service-alb-sg",
            ("ingress", 0, "cidrBlocks"),
            ["0.0.0.0/0"],
            "private-alb-ingress",
        ),
        (
            "user-service-alb-sg",
            ("ingress", 0, "unexpectedRule"),
            True,
            "private-alb-ingress",
        ),
        (
            "user-service-vpc-link-sg",
            ("ingress",),
            [{"protocol": "tcp", "fromPort": 443, "toPort": 443}],
            "vpc-link-group-inputs",
        ),
        (
            "user-service-vpc-link-sg",
            ("egress", 0, "cidrBlocks"),
            ["0.0.0.0/0"],
            "vpc-link-group-inputs",
        ),
        (
            "user-service-https-listener",
            ("protocol",),
            "HTTP",
            "https-listener-inputs",
        ),
        (
            "user-service-https-listener",
            ("certificateArn",),
            "arn:aws:acm:eu-central-1:891377212104:certificate/foreign",
            "https-listener-inputs",
        ),
        (
            "user-service-web-service",
            ("networkConfiguration", "assignPublicIp"),
            True,
            "private-fargate-service-inputs",
        ),
        (
            "user-service-worker-service",
            ("enableExecuteCommand",),
            True,
            "private-fargate-service-inputs",
        ),
        (
            "user-service-web-service",
            ("deploymentCircuitBreaker", "rollback"),
            False,
            "private-fargate-service-inputs",
        ),
        (
            "user-service-web-service",
            ("deploymentCircuitBreaker", "rollback"),
            1,
            "private-fargate-service-inputs",
        ),
        (
            "user-service-worker-service",
            ("desiredCount",),
            0,
            "private-fargate-service-inputs",
        ),
        (
            "user-service-worker-service",
            ("desiredCount",),
            True,
            "private-fargate-service-inputs",
        ),
        (
            "user-service-web-service",
            ("launchType",),
            "EC2",
            "private-fargate-service-inputs",
        ),
    ],
)
def test_matching_plan_and_preview_cannot_expose_private_workload(
    data, name, path, value, error
):
    urn = next(
        urn for urn in data["saved_plan"]["resourcePlans"] if urn.endswith(f"::{name}")
    )
    goal = data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"]["adds"]
    preview = next(
        step["newState"]["inputs"]
        for step in data["preview"]["steps"]
        if step["urn"] == urn
    )
    for inputs in (goal, preview):
        current = inputs
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = copy.deepcopy(value)
    with pytest.raises(ValueError, match=error):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "name,field,value,error",
    [
        (
            "user-service-app-subnet-1",
            "cidrBlock",
            "10.42.99.0/24",
            "private-subnet-inputs",
        ),
        (
            "user-service-app-subnet-2",
            "mapPublicIpOnLaunch",
            True,
            "private-subnet-inputs",
        ),
        (
            "user-service-data-subnet-1",
            "mapPublicIpOnLaunch",
            True,
            "private-subnet-inputs",
        ),
        (
            "user-service-data-subnet-2",
            "mapPublicIpOnLaunch",
            0,
            "private-subnet-inputs",
        ),
        ("user-service-documentdb-cluster", "engine", "mysql", "managed-data-inputs"),
        (
            "user-service-documentdb-cluster",
            "engineVersion",
            "4.0.0",
            "managed-data-inputs",
        ),
        (
            "user-service-documentdb-cluster",
            "storageEncrypted",
            False,
            "managed-data-inputs",
        ),
        (
            "user-service-documentdb-cluster",
            "enabledCloudwatchLogsExports",
            [],
            "managed-data-inputs",
        ),
        (
            "user-service-documentdb-cluster",
            "backupRetentionPeriod",
            0,
            "managed-data-retention",
        ),
        (
            "user-service-documentdb-cluster",
            "backupRetentionPeriod",
            True,
            "managed-data-retention",
        ),
        ("user-service-redis", "engine", "memcached", "managed-data-inputs"),
        ("user-service-redis", "engineVersion", "6.0", "managed-data-inputs"),
        (
            "user-service-redis",
            "atRestEncryptionEnabled",
            False,
            "managed-data-inputs",
        ),
        (
            "user-service-redis",
            "transitEncryptionEnabled",
            False,
            "managed-data-inputs",
        ),
        (
            "user-service-redis",
            "transitEncryptionMode",
            "preferred",
            "managed-data-inputs",
        ),
        (
            "user-service-redis",
            "authTokenUpdateStrategy",
            "SET",
            "managed-data-inputs",
        ),
        (
            "user-service-redis",
            "snapshotRetentionLimit",
            0,
            "managed-data-retention",
        ),
        (
            "user-service-redis",
            "snapshotRetentionLimit",
            True,
            "managed-data-retention",
        ),
        (
            "user-service-send-email",
            "kmsMasterKeyId",
            "",
            "encrypted-queue-inputs",
        ),
        (
            "user-service-domain-events",
            "receiveWaitTimeSeconds",
            0,
            "encrypted-queue-inputs",
        ),
        (
            "user-service-health-check",
            "visibilityTimeoutSeconds",
            0,
            "encrypted-queue-inputs",
        ),
        (
            "user-service-send-email",
            "name",
            "foreign-queue",
            "encrypted-queue-inputs",
        ),
        (
            "user-service-health-check",
            "name",
            "foreign-health-queue",
            "encrypted-queue-inputs",
        ),
    ],
)
def test_matching_plan_and_preview_cannot_weaken_private_data_or_queues(
    data, name, field, value, error
):
    urn = next(
        urn for urn in data["saved_plan"]["resourcePlans"] if urn.endswith(f"::{name}")
    )
    goal = data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"]["adds"]
    preview = next(
        step["newState"]["inputs"]
        for step in data["preview"]["steps"]
        if step["urn"] == urn
    )
    for inputs in (goal, preview):
        inputs[field] = copy.deepcopy(value)
    with pytest.raises(ValueError, match=error):
        gate.validate_first_workload_topology(**data)


def test_explicit_private_data_subnet_flag_is_accepted(data):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::user-service-data-subnet-1")
    )
    data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"]["adds"][
        "mapPublicIpOnLaunch"
    ] = False
    step = next(row for row in data["preview"]["steps"] if row["urn"] == urn)
    step["newState"]["inputs"]["mapPublicIpOnLaunch"] = False
    gate.validate_first_workload_topology(**data)


def _set_matching_input(data, name, path, value):
    """Change saved and preview inputs together to exercise semantic admission."""
    urn = next(
        urn for urn in data["saved_plan"]["resourcePlans"] if urn.endswith(f"::{name}")
    )
    goal = data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"]["adds"]
    preview = next(
        step["newState"]["inputs"]
        for step in data["preview"]["steps"]
        if step["urn"] == urn
    )
    for inputs in (goal, preview):
        current = inputs
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = copy.deepcopy(value)


@pytest.mark.parametrize(
    "path,value",
    [
        (("sslPolicy",), "ELBSecurityPolicy-2016-08"),
        (("sslPolicy",), gate.registry.UNKNOWN),
        (("defaultActions",), []),
        (("defaultActions",), gate.registry.UNKNOWN),
        (("defaultActions",), [None]),
        (("defaultActions",), [{"type": "forward"}]),
        (("defaultActions", 0, "type"), "redirect"),
        (("defaultActions", 0, "targetGroupArn"), ""),
        (("defaultActions", 0, "targetGroupArn"), None),
        (("defaultActions", 0, "redirect"), {"statusCode": "HTTP_302"}),
    ],
)
def test_matching_plan_and_preview_cannot_change_https_routing(data, path, value):
    _set_matching_input(data, "user-service-https-listener", path, value)
    with pytest.raises(ValueError, match="workload-https-listener"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "path,value",
    [
        (("protocol",), "HTTPS"),
        (("targetType",), "instance"),
        (("port",), True),
        (("port",), 0),
        (("port",), 65536),
        (("port",), gate.registry.UNKNOWN),
        (("deregistrationDelay",), 0),
        (("healthCheck",), gate.registry.UNKNOWN),
        (("healthCheck", "enabled"), False),
        (("healthCheck", "enabled"), 1),
        (("healthCheck", "path"), "/"),
        (("healthCheck", "protocol"), "HTTPS"),
        (("healthCheck", "matcher"), "200-499"),
        (("healthCheck", "healthyThreshold"), True),
        (("healthCheck", "unhealthyThreshold"), 10),
        (("healthCheck", "interval"), 300),
        (("healthCheck", "timeout"), 60),
        (("healthCheck", "port"), "443"),
    ],
)
def test_matching_plan_and_preview_cannot_change_web_target(data, path, value):
    _set_matching_input(data, "user-service-target-group", path, value)
    with pytest.raises(ValueError, match="workload-web-target"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "name,path,value",
    [
        ("web", ("loadBalancers",), []),
        ("web", ("loadBalancers",), gate.registry.UNKNOWN),
        ("web", ("loadBalancers", 0, "containerName"), "user-service-worker"),
        ("web", ("loadBalancers", 0, "containerPort"), 8080),
        ("web", ("loadBalancers", 0, "containerPort"), True),
        ("web", ("loadBalancers", 0, "targetGroupArn"), "foreign"),
        ("web", ("loadBalancers", 0, "elbName"), "foreign"),
        ("worker", ("loadBalancers",), [{"containerName": "user-service-worker"}]),
        ("worker", ("loadBalancers",), None),
    ],
)
def test_matching_plan_and_preview_cannot_rewire_web_service(data, name, path, value):
    _set_matching_input(data, f"user-service-{name}-service", path, value)
    with pytest.raises(ValueError, match="workload-web-service-target"):
        gate.validate_first_workload_topology(**data)


def test_unresolved_target_arn_keeps_terminal_admission_closed(data):
    for name, path in (
        ("user-service-https-listener", ("defaultActions", 0, "targetGroupArn")),
        ("user-service-web-service", ("loadBalancers", 0, "targetGroupArn")),
    ):
        _set_matching_input(data, name, path, gate.registry.UNKNOWN)
    gate.validate_first_workload_topology(**data)
    with pytest.raises(
        ValueError, match="workload-native-capability-and-input-admission-required"
    ):
        gate.admit_first_workload_plan(**data)


def test_coherent_configured_target_port_is_accepted(data):
    # Container port is baseline configuration, not a fixed contract literal.
    _set_matching_input(data, "user-service-target-group", ("port",), 8080)
    _set_matching_input(
        data, "user-service-web-service", ("loadBalancers", 0, "containerPort"), 8080
    )
    _set_matching_input(data, "user-service-worker-service", ("loadBalancers",), [])
    _set_container_field(data, "web", ("portMappings", 0, "containerPort"), 8080)
    _set_container_field(data, "web", ("portMappings", 0, "hostPort"), 8080)
    gate.validate_first_workload_topology(**data)


def _task_containers(data, kind):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith(f"::user-service-{kind}-task")
    )
    raw = data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"]["adds"][
        "containerDefinitions"
    ]
    return json.loads(raw)


def _set_container_field(data, kind, path, value):
    containers = _task_containers(data, kind)
    current = containers[0]
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    _set_matching_input(
        data,
        f"user-service-{kind}-task",
        ("containerDefinitions",),
        json.dumps(containers),
    )


@pytest.mark.parametrize("kind", ["web", "worker"])
@pytest.mark.parametrize(
    "path,value",
    [
        (
            ("image",),
            "891377212104.dkr.ecr.eu-central-1.amazonaws.com/user-service-test-web:latest",
        ),
        (("image",), "foreign@sha256:" + "a" * 64),
        (("image",), gate.registry.UNKNOWN),
        (("command",), ["/bin/sh", "-c", "echo changed"]),
        (("name",), "foreign"),
        (("essential",), 1),
        (("privileged",), True),
        (("entryPoint",), ["/bin/sh"]),
        (("mountPoints",), []),
        (("environmentFiles",), []),
        (("logConfiguration", "logDriver"), "fluentd"),
        (("logConfiguration", "options", "awslogs-group"), "/foreign"),
        (("logConfiguration", "options", "awslogs-region"), "us-east-1"),
        (("logConfiguration", "options", "awslogs-stream-prefix"), "foreign"),
        (("logConfiguration", "options", "awslogs-create-group"), "true"),
    ],
)
def test_matching_known_container_cannot_change_runtime(data, kind, path, value):
    _set_container_field(data, kind, path, value)
    with pytest.raises(ValueError, match="workload-task-container-runtime"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize("kind", ["web", "worker"])
@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "[secret]",
        "{}",
        "[]",
        "[null]",
        "[{}, {}]",
        "[",
        "[NaN]",
        '[{"name":"first","name":"second"}]',
        " " * 65537,
    ],
)
def test_container_json_is_closed_and_bounded(data, kind, raw):
    _set_matching_input(
        data, f"user-service-{kind}-task", ("containerDefinitions",), raw
    )
    with pytest.raises(ValueError, match="workload-task-container-json"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize("kind", ["web", "worker"])
@pytest.mark.parametrize(
    "name,value",
    [
        ("APP_ENV", "dev"),
        ("APP_DEBUG", "1"),
        ("API_URL", "https://foreign"),
        ("MAIL_SENDER", "foreign@example.com"),
        ("MAILER_DSN", "smtp://foreign"),
        ("SOCIAL_OAUTH_ENABLED", "true"),
        ("OAUTH_ENCRYPTION_KEY_TYPE", "defuse"),
        ("AWS_SQS_ENDPOINT_BASE", "https://foreign"),
        ("LOCALSTACK_PORT", "4566"),
        ("OAUTH_PRIVATE_KEY", "/tmp/foreign"),
        ("AWS_ACCESS_KEY_ID", "synthetic-credential"),
        ("JWT_ISSUER", gate.registry.UNKNOWN),
        (
            "SEND_EMAIL_TRANSPORT_DSN",
            "https://sqs.eu-central-1.amazonaws.com/123456789012/send-email?region=eu-central-1&auto_setup=false",
        ),
        (
            "SEND_EMAIL_TRANSPORT_DSN",
            "https://sqs.eu-central-1.amazonaws.com/891377212104/foreign-queue?region=eu-central-1&auto_setup=false",
        ),
    ],
)
def test_container_environment_rejects_known_contract_changes(data, kind, name, value):
    rows = _task_containers(data, kind)[0]["environment"]
    rows = [row for row in rows if row["name"] != name] + [
        {"name": name, "value": value}
    ]
    _set_container_field(data, kind, ("environment",), rows)
    with pytest.raises(ValueError, match="workload-task-container-environment"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize("field", ["environment", "secrets"])
@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing", "extra-field", "wrong-type"]
)
def test_container_named_values_reject_ambiguous_mappings(data, field, mutation):
    rows = _task_containers(data, "web")[0][field]
    if mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "missing":
        rows.pop()
    elif mutation == "extra-field":
        rows[0]["unexpected"] = "foreign"
    else:
        rows = {}
    _set_container_field(data, "web", (field,), rows)
    with pytest.raises(ValueError, match=f"workload-task-container-{field}"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize("kind", ["web", "worker"])
@pytest.mark.parametrize(
    "mutation", ["account", "name", "unpinned", "stage", "version", "unknown", "redis"]
)
def test_container_secrets_require_declared_version_pinned_references(
    data, kind, mutation
):
    rows = _task_containers(data, kind)[0]["secrets"]
    original = rows[0]["valueFrom"]
    if mutation == "redis":
        rows[-1]["valueFrom"] = rows[1]["valueFrom"].rsplit(":", 1)[0] + ":" + "2" * 32
    else:
        rows[0]["valueFrom"] = {
            "account": original.replace("891377212104", "123456789012"),
            "name": original.replace("synthetic-document_db_url", "foreign"),
            "unpinned": original.split(":::")[0],
            "stage": original.split(":::")[0] + "::AWSCURRENT:",
            "version": original.rsplit(":", 1)[0] + ":short",
            "unknown": gate.registry.UNKNOWN,
        }[mutation]
    _set_container_field(data, kind, ("secrets",), rows)
    with pytest.raises(ValueError, match="workload-task-container-secrets"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "kind,path,value",
    [
        ("web", ("portMappings", 0, "hostPort"), 81),
        ("web", ("portMappings", 0, "containerPort"), True),
        ("web", ("portMappings", 0, "protocol"), "udp"),
        ("web", ("healthCheck",), {}),
        ("worker", ("portMappings",), [{"containerPort": 80}]),
        ("worker", ("healthCheck", "command"), ["CMD-SHELL", "true"]),
        ("worker", ("healthCheck", "interval"), 300),
    ],
)
def test_container_ports_and_worker_health_are_fixed(data, kind, path, value):
    _set_container_field(data, kind, path, value)
    with pytest.raises(ValueError, match="workload-task-container-runtime"):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu", gate.registry.UNKNOWN),
        ("memory", "0"),
        ("cpu", 512),
        ("memory", "1e3"),
        ("cpu", "9999999"),
        ("family", "foreign"),
        ("volumes", []),
    ],
)
def test_task_inputs_reject_unknown_capacity_or_additional_configuration(
    data, field, value
):
    _set_matching_input(data, "user-service-web-task", (field,), value)
    with pytest.raises(ValueError, match="workload-task-(capacity|definition)-inputs"):
        gate.validate_first_workload_topology(**data)


def test_first_create_unknown_containers_never_authorize_execution(data):
    for kind in ("web", "worker"):
        _set_matching_input(
            data,
            f"user-service-{kind}-task",
            ("containerDefinitions",),
            gate.registry.UNKNOWN,
        )
    gate.validate_first_workload_topology(**data)
    with pytest.raises(
        ValueError, match="workload-native-capability-and-input-admission-required"
    ):
        gate.admit_first_workload_plan(**data)


def test_named_environment_and_secret_order_is_not_semantic(data):
    for kind in ("web", "worker"):
        for field in ("environment", "secrets"):
            rows = _task_containers(data, kind)[0][field]
            _set_container_field(data, kind, (field,), list(reversed(rows)))
    gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize("kind", ["web", "worker"])
@pytest.mark.parametrize(
    "target", ["logs", "runtime-app_secret", "runtime-app_secret-version"]
)
def test_unknown_containers_still_require_native_secret_and_log_edges(
    data, kind, target
):
    plans = data["saved_plan"]["resourcePlans"]
    name = f"user-service-{kind}-task"
    target = f"user-service-{kind}-logs" if target == "logs" else target
    owner_urn = next(urn for urn in plans if urn.endswith("::" + name))
    target_urn = next(urn for urn in plans if urn.endswith("::" + target))
    goal = plans[owner_urn]["goal"]
    assert target_urn in goal["dependencies"]
    goal["dependencies"].remove(target_urn)
    step = next(row for row in data["preview"]["steps"] if row["urn"] == owner_urn)
    step["newState"]["dependencies"] = list(goal["dependencies"])
    _set_matching_input(data, name, ("containerDefinitions",), gate.registry.UNKNOWN)
    with pytest.raises(ValueError, match="workload-task-container-dependencies"):
        gate.validate_first_workload_topology(**data)


def test_capacity_form_checks_do_not_invent_baseline_contract_pins(data):
    _set_matching_input(data, "user-service-web-task", ("cpu",), "1024")
    _set_matching_input(data, "user-service-web-task", ("memory",), "2048")
    gate.validate_first_workload_topology(**data)
    with pytest.raises(
        ValueError, match="workload-native-capability-and-input-admission-required"
    ):
        gate.admit_first_workload_plan(**data)


def test_native_omitted_component_outputs_require_unchanged_saved_goal(data):
    root = next(
        step for step in data["preview"]["steps"] if step["urn"] == gate.registry.ROOT
    )
    root["newState"].pop("outputs")
    gate.validate_first_workload_topology(**data)
    data["saved_plan"]["resourcePlans"][gate.registry.ROOT]["goal"]["outputDiff"] = {
        "updates": {"repoSlug": "foreign"}
    }
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)


def test_explicitly_changed_component_outputs_still_reject(data):
    root = next(
        step for step in data["preview"]["steps"] if step["urn"] == gate.registry.ROOT
    )
    root["newState"]["outputs"] = {}
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "value,marked,valid",
    [
        ("raw", True, False),
        ("[secret]", True, False),
        (gate.registry.UNKNOWN, False, False),
        (gate.registry.UNKNOWN, True, True),
    ],
)
def test_first_secret_unknown_requires_secret_output_marking(
    data, value, marked, valid
):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::runtime-document_db_url-version")
    )
    goal = data["saved_plan"]["resourcePlans"][urn]["goal"]
    goal["inputDiff"]["adds"]["secretString"] = value
    goal["additionalSecretOutputs"] = gate.SECRET_VERSION_OUTPUTS if marked else []
    state = next(
        step["newState"] for step in data["preview"]["steps"] if step["urn"] == urn
    )
    state["inputs"]["secretString"] = value
    state["additionalSecretOutputs"] = goal["additionalSecretOutputs"]
    if valid:
        gate.validate_first_workload_topology(**data)
    else:
        with pytest.raises(ValueError):
            gate.validate_first_workload_topology(**data)


def test_sdk_alias_cannot_retarget_an_owner(data):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::user-service-alb")
    )
    data["saved_plan"]["resourcePlans"][urn]["goal"]["structuredAliases"][0]["Name"] = (
        "foreign"
    )
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "parent",
        "kind",
        "provider",
        "protect",
        "alias",
        "import",
        "delete",
        "update",
        "dependency",
        "preview-type",
        "preview-input",
        "preview-missing",
        "duplicate",
        "prior-partial",
        "prior-workload",
    ],
)
def test_first_workload_rejects_unreviewed_or_partial_graph(data, mutation):
    urn = next(
        urn
        for urn in data["saved_plan"]["resourcePlans"]
        if urn.endswith("::user-service-web-task")
    )
    plans = data["saved_plan"]["resourcePlans"]
    step = next(row for row in data["preview"]["steps"] if row["urn"] == urn)
    goal = plans[urn]["goal"]
    mutations = {
        "missing": lambda: plans.pop(urn),
        "extra": lambda: plans.update(foreign=copy.deepcopy(plans[urn])),
        "parent": lambda: goal.update(parent=gate.registry.ROOT),
        "kind": lambda: goal.update(type="aws:iam/role:Role"),
        "provider": lambda: goal.update(provider="foreign"),
        "protect": lambda: goal.update(protect=True),
        "alias": lambda: goal.update(aliases=["foreign"]),
        "import": lambda: goal.update(id="foreign"),
        "delete": lambda: plans[urn].update(steps=["delete"]),
        "update": lambda: plans[urn].update(steps=["update"]),
        "dependency": lambda: goal.update(dependencies=["foreign"]),
        "preview-type": lambda: step["newState"].update(type="aws:iam/role:Role"),
        "preview-input": lambda: step["newState"]["inputs"].update(networkMode="host"),
        "preview-missing": lambda: data["preview"]["steps"].remove(step),
        "duplicate": lambda: data["preview"]["steps"].append(copy.deepcopy(step)),
        "prior-partial": lambda: data["prior_resources"].pop(),
        "prior-workload": lambda: data["prior_resources"].append(
            copy.deepcopy(step["newState"])
        ),
    }
    mutations[mutation]()
    with pytest.raises(ValueError):
        gate.validate_first_workload_topology(**data)
