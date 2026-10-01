"""Hardened step-1 composition (S1.3): guard checks, network, XP-8 exports.

FR-02 (V-17: DocumentDB 5.0.0 instance-based only), FR-34 (the step-1 graph
holds no step-2 type and its services start at zero tasks) and XP-8 (the
subnet IDs, the bootstrap-job SG ID and the managed secret ARN).
"""

import json
from pathlib import Path

import jsonschema
import pytest
from app.workload_phase import (
    ELASTIC_DOCUMENTDB_TYPE,
    HARDENED_PROPERTY_CHECKS,
    HARDENED_TYPES,
    STEP_TWO_TYPES,
    _reject_secret_material,
)
from test_poc_workload_phase import graph
from test_runtime_secrets import _transform_args

ROOT = Path(__file__).parents[2]
CLUSTER = "aws:docdb/cluster:Cluster"
TASK = "aws:ecs/taskDefinition:TaskDefinition"
SECRET_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "/user-service-infrastructure/runtime/test/synthetic-app_secret-AbCdEf"
)


@pytest.fixture(scope="module")
def hardened(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("step-one"), "hardened")
    assert receipt["error"] is None
    return receipt


def _cluster(engine_path, **changes):
    """Build SDK (snake_case) or engine (camelCase) cluster inputs."""
    snake = ("engine_version", "manage_master_user_password")
    camel = ("engineVersion", "manageMasterUserPassword")
    keys = camel if engine_path else snake
    props = {"engine": "docdb", keys[0]: "5.0.0", keys[1]: True}
    for key, value in changes.items():
        props[keys[snake.index(key)] if key in snake else key] = value
    return _transform_args(engine_path, CLUSTER, props)


@pytest.mark.parametrize("engine_path", [False, True])
def test_the_managed_password_cluster_on_engine_5_passes_the_guard(engine_path):
    assert _reject_secret_material(_cluster(engine_path)) is None


@pytest.mark.parametrize("engine_path", [False, True])
@pytest.mark.parametrize(
    "change",
    [
        {"master_password": "synthetic"},
        {"masterPassword": "synthetic"},
        {"master_password_wo": "synthetic"},
        {"masterPasswordWo": "synthetic"},
        {"manage_master_user_password": False},
        {"manage_master_user_password": None},
        {"manage_master_user_password": "true"},
        {"engine_version": "4.0.0"},
        {"engine_version": None},
        {"engine": None},
        {"engine": "aurora-postgresql"},
    ],
)
def test_the_cluster_property_check_refuses_a_password_or_engine(engine_path, change):
    """S1.2 F-07 and V-17: managed password only, on engine 5.0.0 only."""
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_cluster(engine_path, **change))


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize("step", [1, 2])
def test_an_elastic_cluster_is_refused_at_every_step(engine, step):
    """N (V-17): an elastic cluster has no IAM authentication."""
    args = _transform_args(engine, ELASTIC_DOCUMENTDB_TYPE, {})
    with pytest.raises(ValueError, match="instance-based"):
        _reject_secret_material(args, step=step)
    assert ELASTIC_DOCUMENTDB_TYPE not in HARDENED_TYPES


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize("kind", sorted(STEP_TWO_TYPES))
def test_a_step_two_type_is_refused_at_step_one(engine, kind):
    """B (FR-34): no seed, rotation, policy, autoscaling or scheduled action."""
    args = _transform_args(engine, kind, {})
    with pytest.raises(ValueError, match="step-2 resource"):
        _reject_secret_material(args)
    # Step 2 admits each type only once its own story allowlists it.
    with pytest.raises(ValueError, match="unreviewed type"):
        _reject_secret_material(args, step=2)


def _definitions(environment=None, secrets=None, **extra):
    container = {
        "name": "fixture",
        "environment": environment or [{"name": "APP_ENV", "value": "prod"}],
        "secrets": secrets or [{"name": "APP_SECRET", "valueFrom": SECRET_ARN}],
        **extra,
    }
    return json.dumps([container])


@pytest.mark.parametrize("engine", [False, True])
def test_a_plain_task_environment_passes_the_guard(engine):
    key = "containerDefinitions" if engine else "container_definitions"
    for value in (_definitions(), json.dumps([{"name": "fixture"}]), object()):
        args = _transform_args(engine, TASK, {key: value})
        assert _reject_secret_material(args) is None


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize(
    "definitions",
    [
        # A plain name that is also a secret name (FR-08).
        _definitions([{"name": "APP_SECRET", "value": "plain"}]),
        # A credential in a plain value (FR-03, AD-20).
        _definitions([{"name": "DSN", "value": "https://user:synthetic@host"}]),
        _definitions([{"name": "KEY", "value": "AKIA" + "SYNTHETIC0000000"}]),
        # A versioned secret reference (S1.7).
        _definitions(
            secrets=[{"name": "A", "valueFrom": SECRET_ARN + ":::" + "1" * 32}]
        ),
        _definitions(
            secrets=[{"name": "A", "valueFrom": SECRET_ARN + "::AWSCURRENT:"}]
        ),
        # Closed row shapes: a secret value inlined in a row fails.
        _definitions([{"name": "A", "value": "x", "valueFrom": SECRET_ARN}]),
        _definitions(secrets=[{"name": "A", "valueFrom": SECRET_ARN, "value": "x"}]),
        _definitions(["APP_ENV=prod"]),
        _definitions([{"name": "A", "value": None}]),
        _definitions([{"name": ["A"], "value": "x"}]),
        json.dumps({"environment": []}),
        json.dumps(["fixture"]),
        json.dumps([{"environment": {"name": "A"}}]),
        "not-json",
    ],
)
def test_the_task_property_check_refuses_secret_shaped_environment(engine, definitions):
    key = "containerDefinitions" if engine else "container_definitions"
    args = _transform_args(engine, TASK, {key: definitions})
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(args)


def test_property_checks_cover_every_secret_bearing_rendered_type():
    assert set(HARDENED_PROPERTY_CHECKS) == {
        CLUSTER,
        TASK,
        "aws:sesv2/emailIdentity:EmailIdentity",
    }
    assert set(HARDENED_PROPERTY_CHECKS) <= HARDENED_TYPES


def test_the_step_one_graph_holds_no_step_two_type(hardened):
    """B (FR-34): no seed, rotation, secret policy or autoscaling target."""
    types = {row["type"] for row in hardened["registrations"].values()}
    assert not types & STEP_TWO_TYPES
    assert not [kind for kind in types if kind.startswith("aws:lambda/")]
    assert not [kind for kind in types if kind.startswith("aws:appautoscaling/")]
    assert {
        "aws:docdb/cluster:Cluster",
        "aws:ecs/service:Service",
        "aws:secretsmanager/secret:Secret",
        "aws:ec2/securityGroup:SecurityGroup",
    } <= types


def test_the_cluster_uses_the_managed_password_on_engine_5(hardened):
    """S1.2 F-07/F-10 in the composed graph: no password input of any kind."""
    (cluster,) = [
        row
        for row in hardened["registrations"].values()
        if row["type"] == "aws:docdb/cluster:Cluster"
    ]
    inputs = cluster["inputs"]
    assert inputs["manageMasterUserPassword"] is True
    assert (inputs["engine"], inputs["engineVersion"]) == ("docdb", "5.0.0")
    assert not [
        key
        for key in inputs
        if "password" in key.lower() and key != "manageMasterUserPassword"
    ]


def test_the_bootstrap_job_sg_reaches_documentdb_and_stays_in_the_vpc(hardened):
    rows = hardened["registrations"]
    bootstrap = rows["user-service-bootstrap-job-sg"]
    assert bootstrap["inputs"]["vpcId"] == rows["user-service-vpc"]["id"]
    assert bootstrap["inputs"]["ingress"] == []
    assert bootstrap["inputs"]["egress"] == [
        {
            "protocol": "tcp",
            "fromPort": port,
            "toPort": port,
            "cidrBlocks": ["10.42.0.0/16"],
        }
        for port in (27017, 443)
    ]
    documentdb = rows["user-service-documentdb-sg"]["inputs"]["ingress"]
    assert documentdb == [
        {
            "protocol": "tcp",
            "fromPort": 27017,
            "toPort": 27017,
            "securityGroups": [
                rows["user-service-service-sg"]["id"],
                bootstrap["id"],
            ],
        }
    ]
    network = rows["network"]["urn"]
    assert (
        hardened["outputs"][network]["bootstrapJobSecurityGroupId"] == bootstrap["id"]
    )


def test_the_pre_hardening_network_is_unchanged(tmp_path):
    """AD-25: the bridge graph has no bootstrap-job SG until S4.10."""
    bridge = graph(tmp_path, "bridge")
    rows = bridge["registrations"]
    assert "user-service-bootstrap-job-sg" not in rows
    (ingress,) = rows["user-service-documentdb-sg"]["inputs"]["ingress"]
    assert ingress["securityGroups"] == [rows["user-service-service-sg"]["id"]]
    assert "bootstrapJobSecurityGroupId" not in json.dumps(bridge["outputs"])
    assert not {"lambda_network", "documentdb_managed_secret_arn"} & set(
        bridge["exports"]
    )


def _schema_property(name):
    """Find one XP-8 property schema inside the committed contract schema."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if name in node.get("properties", {}):
                found.append(node["properties"][name])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads((ROOT / "schemas/poc-test-v1.schema.json").read_text()))
    assert found
    return found[0]


def test_xp8_values_are_exported_in_the_contract_shape(hardened):
    """XP-8: subnet IDs, bootstrap-job SG ID and the managed secret ARN."""
    exports = hardened["exports"]
    rows = hardened["registrations"]
    assert exports["lambda_network"] == {
        "subnet_ids": [rows[f"user-service-app-subnet-{i}"]["id"] for i in (1, 2)],
        "bootstrap_job_security_group_id": rows["user-service-bootstrap-job-sg"]["id"],
    }
    for name in ("lambda_network", "documentdb_managed_secret_arn"):
        jsonschema.validate(exports[name], _schema_property(name))
    assert exports["documentdb_managed_secret_arn"].startswith(
        "arn:aws:secretsmanager:eu-central-1:891377212104:secret:rds!cluster-"
    )


@pytest.mark.parametrize("version", ["4.0.0", "8.0.0"])
def test_a_non_iam_engine_fails_the_hardened_composition(tmp_path, version):
    """N (V-17): the composed stack refuses engine 4.0.0 before DocumentDB."""
    receipt = graph(tmp_path, "hardened", f"engine-{version}")
    assert "V-17" in receipt["error"]
    assert not [
        row
        for row in receipt["registrations"].values()
        if row["type"].startswith("aws:docdb/")
    ]


def test_a_password_config_fails_the_hardened_composition_first(tmp_path):
    """S1.2 F-07: the stack refuses ``documentDbPassword`` before any resource."""
    receipt = graph(tmp_path, "hardened", "password-config")
    assert "documentDbPassword must not be configured" in receipt["error"]
    assert "synthetic-documentdb-password" not in receipt["error"]
    assert not [
        row
        for row in receipt["registrations"].values()
        if row["type"].startswith("aws:")
    ]


@pytest.mark.parametrize(
    ("addition", "message"),
    [
        ("stack:docdb-cluster", "unreviewed property"),
        ("root:docdb-cluster", "unreviewed property"),
        ("root:docdb-cluster-4", "unreviewed property"),
        ("stack:docdb-elastic-cluster", "instance-based"),
        ("root:docdb-elastic-cluster", "instance-based"),
        ("stack:secret-policy", "step-2 resource"),
        ("root:secret-policy", "step-2 resource"),
        ("root:userinfo-task", "unreviewed property"),
    ],
)
def test_a_readded_credential_or_step_two_resource_fails(tmp_path, addition, message):
    receipt = graph(tmp_path, "hardened", addition)
    assert message in receipt["error"]
    assert not [
        name for name in receipt["registrations"] if name.startswith("fixture-")
    ]
