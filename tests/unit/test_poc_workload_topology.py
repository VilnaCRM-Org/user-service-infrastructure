"""First topology checks retain registry owners and never enable capabilities."""

import base64
import copy
import importlib

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


@pytest.fixture
def data(captured):
    value = case("repeat")
    contract, images = fixture()
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
        if kind == "aws:ecs/service:Service":
            # SDK MockMonitor encodes numeric inputs as floats; native Pulumi
            # saved plans retain desiredCount as an integer.
            assert inputs["desiredCount"] == 2.0
            inputs["desiredCount"] = 2
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
