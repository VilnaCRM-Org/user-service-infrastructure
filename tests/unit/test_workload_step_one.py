"""Hardened step-1 composition (S1.3): guard checks, network, XP-8 exports.

FR-02 (V-17: DocumentDB 5.0.0 instance-based only), FR-34 (the step-1 graph
holds no step-2 type and its services start at zero tasks) and XP-8 (the
subnet IDs, the bootstrap-job SG ID and the managed secret ARN).
"""

import asyncio
import json
from pathlib import Path

import jsonschema
import pulumi_aws as aws
import pytest
from app.workload_phase import (
    ELASTIC_DOCUMENTDB_TYPE,
    HARDENED_PROPERTY_CHECKS,
    HARDENED_TYPES,
    STEP_TWO_TYPES,
    _reject_secret_material,
)
from pulumi.output import Unknown
from pulumi.runtime import rpc, settings
from test_poc_workload_phase import graph
from test_runtime_secrets import _transform_args

import pulumi

ROOT = Path(__file__).parents[2]
CLUSTER = "aws:docdb/cluster:Cluster"
TASK = "aws:ecs/taskDefinition:TaskDefinition"
SECRET_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "/user-service-infrastructure/runtime/test/synthetic-app_secret-AbCdEf"
)
LISTENER = "aws:lb/listener:Listener"
SECRET = "aws:secretsmanager/secret:Secret"
SERVICE = "aws:ecs/service:Service"
ACCESS_KEY = "AKIA" + "SYNTHETIC0000000"
USERINFO = "https://user:synthetic@host.example"


def _secret(value):
    """The engine path's view of a secret-marked input (``wrap_rpc_secret``)."""
    return {rpc._special_sig_key: rpc._special_secret_sig, "value": value}


def _unresolved():
    """An SDK ``Output`` that is never awaited, so no event loop is needed."""
    return object.__new__(pulumi.Output)


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


# Every key ``ComputePlane._container_definitions_json`` emits for a container.
FULL_CONTAINER = {
    "name": "fixture",
    "image": "891377212104.dkr.ecr.eu-central-1.amazonaws.com/fixture:sha-1",
    "essential": True,
    "command": ["/bin/sh", "-ec", "exec /synthetic/run"],
    "environment": [{"name": "APP_ENV", "value": "prod"}],
    "secrets": [{"name": "APP_SECRET", "valueFrom": SECRET_ARN}],
    "portMappings": [{"containerPort": 80, "hostPort": 80, "protocol": "tcp"}],
    "readonlyRootFilesystem": True,
    "mountPoints": [
        {"sourceVolume": "app-var", "containerPath": "/srv/app/var", "readOnly": False}
    ],
    "linuxParameters": {"capabilities": {"drop": ["ALL"]}},
    "healthCheck": {"command": ["CMD", "/synthetic/check"], "interval": 30},
    "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
            "awslogs-group": "/aws/ecs/fixture",
            "awslogs-region": "eu-central-1",
        },
    },
}


@pytest.mark.parametrize("engine", [False, True])
def test_a_plain_or_deferred_task_definition_passes_the_guard(engine):
    """F-01: a str is inspected; an SDK Output or a preview Unknown is deferred."""
    key = "containerDefinitions" if engine else "container_definitions"
    deferred = Unknown() if engine else _unresolved()
    for value in (
        _definitions(),
        json.dumps([{"name": "fixture"}]),
        json.dumps([FULL_CONTAINER]),
        deferred,
    ):
        args = _transform_args(engine, TASK, {key: value})
        assert _reject_secret_material(args) is None


@pytest.mark.parametrize("engine", [False, True])
def test_an_unreviewed_task_definition_value_fails_closed(engine):
    """F-01 (a): a secret wrapper, a map, a list or any other object fails."""
    key = "containerDefinitions" if engine else "container_definitions"
    dirty = _definitions([{"name": "DSN", "value": USERINFO}])
    for value in (
        # The engine path deserializes a secret-marked input to this map.
        _secret(dirty),
        _secret(_definitions()),
        json.loads(_definitions())[0],
        json.loads(_definitions()),
        object(),
        None,
        b"[]",
        # An Output is deferred only on the SDK path, Unknown only on the engine.
        _unresolved() if engine else Unknown(),
    ):
        args = _transform_args(engine, TASK, {key: value})
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args)
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_transform_args(engine, TASK, {}))
    # Reading an opaque Output never lifts a new pending output (a later
    # in-process program would wait on it forever).
    assert not settings.SETTINGS.outputs


def _engine_output_check(key, **fields):
    """Run the guard on an engine-path output value, as the engine sends it.

    The real engine serializes an unknown or secret input as an output value
    (``deserialize_output_value``); the transform runs before the loop does.
    """
    loop = asyncio.new_event_loop()

    async def probe():
        value = rpc.deserialize_output_value(fields)
        try:
            return _reject_secret_material(_transform_args(True, TASK, {key: value}))
        finally:
            await value.is_known()

    try:
        return loop.run_until_complete(probe())
    finally:
        loop.close()


@pytest.mark.parametrize("key", ["containerDefinitions", "container_definitions"])
def test_an_engine_output_value_is_deferred_only_while_unknown(key):
    """F-01: the native preview sends the definition as an output value."""
    assert _engine_output_check(key) is None
    assert _engine_output_check(key, value=_definitions()) is None
    for fields in (
        {"value": _definitions([{"name": "DSN", "value": USERINFO}])},
        {"value": json.loads(_definitions())},
        # A secret output value fails, known or unknown.
        {"secret": True},
        {"value": _definitions(), "secret": True},
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _engine_output_check(key, **fields)


def test_an_unresolved_engine_output_value_fails_closed():
    """F-01: an output whose futures are pending is opaque on the engine path."""
    loop = asyncio.new_event_loop()

    async def probe():
        pending = loop.create_future()
        value = pulumi.Output(set(), pending, pending, pending)
        args = _transform_args(True, TASK, {"containerDefinitions": value})
        try:
            with pytest.raises(ValueError, match="unreviewed property"):
                _reject_secret_material(args)
        finally:
            pending.set_result(None)
            await value.is_known()

    try:
        loop.run_until_complete(probe())
    finally:
        loop.close()


@pytest.mark.parametrize("engine", [False, True])
def test_a_secret_reference_is_exempt_only_from_the_credential_scan(engine):
    """F-01: ``secrets[].valueFrom`` keeps the bare-ARN check, not the scan."""
    key = "containerDefinitions" if engine else "container_definitions"
    arn = SECRET_ARN.replace("synthetic-app_secret", ACCESS_KEY)
    accepted = _definitions(secrets=[{"name": "APP_SECRET", "valueFrom": arn}])
    assert (
        _reject_secret_material(_transform_args(engine, TASK, {key: accepted})) is None
    )
    for refused in (
        _definitions([{"name": "A", "value": arn}]),
        _definitions(secrets=[{"name": "A", "valueFrom": "plain-secret-material"}]),
    ):
        args = _transform_args(engine, TASK, {key: refused})
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args)


AWSLOGS = {
    "logDriver": "awslogs",
    "options": {"awslogs-group": "/g", "awslogs-region": "r"},
}
VERSIONED_ARN = SECRET_ARN + ":password:AWSPREVIOUS:"
# The N-01 static trigger: a splunk driver whose token rides in secretOptions.
SPLUNK_LOG = {
    "logDriver": "splunk",
    "options": {"splunk-url": "https://collector.example"},
    "secretOptions": [{"name": "splunk-token", "valueFrom": VERSIONED_ARN}],
}


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
        # F-01 (b): ECS matches keys case-insensitively; only exact case passes.
        json.dumps(
            [{"name": "f", "Environment": [{"Name": "DSN", "Value": USERINFO}]}]
        ),
        json.dumps([{"name": "f", "Secrets": [{"Name": "A", "ValueFrom": "plain"}]}]),
        _definitions(
            secrets=[{"name": "A", "valueFrom": SECRET_ARN, "ValueFrom": "x"}]
        ),
        _definitions([{"name": "A", "value": "x", "Value": USERINFO}]),
        '[{"name": "fixture", "name": "other"}]',
        json.dumps(
            [{"name": "f", "logConfiguration": {"options": {}, "Options": {"a": "b"}}}]
        ),
        # F-01 (c): a key outside the emitted set fails, whatever it holds.
        _definitions(dockerLabels={"label": "plain"}),
        _definitions(entryPoint=["/bin/sh"]),
        _definitions(repositoryCredentials={"credentialsParameter": SECRET_ARN}),
        _definitions(environmentFiles=[{"type": "s3", "value": "arn:aws:s3:::f/e"}]),
        # F-01 (c): every other string leaf is scanned for a credential.
        _definitions(command=["/bin/sh", "-ec", f"export KEY={ACCESS_KEY}"]),
        _definitions(healthCheck={"command": ["CMD", ACCESS_KEY]}),
        _definitions(logConfiguration={"options": {"awslogs-endpoint": USERINFO}}),
        _definitions(logConfiguration={"options": {ACCESS_KEY: "x"}}),
        _definitions(image="https://user:synthetic@registry.example/app:1"),
        _definitions(mountPoints=[{"containerPath": "/x?token=synthetic"}]),
        _definitions(name=f"{USERINFO}/fixture"),
        _definitions(secrets=[{"name": ACCESS_KEY, "valueFrom": SECRET_ARN}]),
        # N-01: logConfiguration is the closed awslogs shape, no secretOptions.
        _definitions(logConfiguration=SPLUNK_LOG),
        _definitions(logConfiguration={**AWSLOGS, "logDriver": "splunk"}),
        _definitions(
            logConfiguration={**AWSLOGS, "options": {"awslogs-endpoint": "https://x"}}
        ),
        _definitions(logConfiguration={**AWSLOGS, "secretOptions": []}),
        _definitions(
            logConfiguration={
                **AWSLOGS,
                "secretOptions": [{"name": "t", "valueFrom": SECRET_ARN}],
            }
        ),
        _definitions(
            logConfiguration={
                **AWSLOGS,
                "secretOptions": [{"name": "t", "valueFrom": VERSIONED_ARN}],
            }
        ),
        _definitions(logConfiguration=SPLUNK_LOG, secrets=[]),
        _definitions(logConfiguration="awslogs"),
    ],
)
def test_the_task_property_check_refuses_secret_shaped_environment(engine, definitions):
    key = "containerDefinitions" if engine else "container_definitions"
    args = _transform_args(engine, TASK, {key: definitions})
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(args)


def test_property_checks_cover_every_secret_bearing_rendered_type():
    """F-02: the typed-input audit (pulumi-aws 7.23.0) names these types."""
    assert set(HARDENED_PROPERTY_CHECKS) == {
        CLUSTER,
        TASK,
        LISTENER,
        SECRET,
        SERVICE,
        "aws:sesv2/emailIdentity:EmailIdentity",
    }
    assert set(HARDENED_PROPERTY_CHECKS) <= HARDENED_TYPES


OIDC = {
    "authorization_endpoint": "https://idp.example/authorize",
    "client_id": "fixture",
    "client_secret": "synthetic-not-a-secret",
    "issuer": "https://idp.example",
    "token_endpoint": "https://idp.example/token",
    "user_info_endpoint": "https://idp.example/userinfo",
}
OIDC_CAMEL = {
    "authorizationEndpoint": OIDC["authorization_endpoint"],
    "clientId": OIDC["client_id"],
    "clientSecret": OIDC["client_secret"],
    "issuer": OIDC["issuer"],
    "tokenEndpoint": OIDC["token_endpoint"],
    "userInfoEndpoint": OIDC["user_info_endpoint"],
}
FORWARD = {"type": "forward", "targetGroupArn": "arn:aws:fixture"}


def _oidc_action():
    return aws.lb.ListenerDefaultActionArgs(
        type="authenticate-oidc",
        authenticate_oidc=aws.lb.ListenerDefaultActionAuthenticateOidcArgs(**OIDC),
    )


@pytest.mark.parametrize(
    ("engine", "actions"),
    [
        (False, None),
        (True, None),
        (
            False,
            [aws.lb.ListenerDefaultActionArgs(type="forward", target_group_arn="x")],
        ),
        (False, [{"type": "forward", "target_group_arn": "arn:aws:fixture"}]),
        (True, [FORWARD]),
        (
            True,
            [{"type": "redirect", "redirect": {"port": "443", "protocol": "HTTPS"}}],
        ),
    ],
)
def test_a_listener_without_an_oidc_action_passes(engine, actions):
    args = _transform_args(engine, LISTENER, {"port": 443, "defaultActions": actions})
    assert _reject_secret_material(args) is None


@pytest.mark.parametrize(
    ("engine", "actions"),
    [
        # F-02: an OIDC action carries ``clientSecret``, in either casing.
        (False, [_oidc_action()]),
        (False, [{"type": "authenticate-oidc", "authenticate_oidc": OIDC}]),
        (False, [{"type": "authenticate-oidc", "authenticateOidc": OIDC_CAMEL}]),
        (True, [{"type": "authenticate-oidc", "authenticateOidc": OIDC_CAMEL}]),
        (True, [{"type": "authenticate-oidc", "authenticate_oidc": OIDC_CAMEL}]),
        (True, [FORWARD, {"type": "authenticate-oidc", "AuthenticateOidc": {}}]),
        # Opaque values fail closed: secret, Output, Unknown or another type.
        (True, _secret([{"type": "authenticate-oidc", "authenticateOidc": {}}])),
        (True, [_secret({"type": "authenticate-oidc", "authenticateOidc": {}})]),
        (True, [_secret(FORWARD)]),
        (True, Unknown()),
        (True, [Unknown()]),
        (False, _unresolved()),
        (False, [_unresolved()]),
        (False, (FORWARD,)),
        (False, [aws.lb.ListenerRuleActionArgs(type="forward", target_group_arn="x")]),
    ],
)
def test_a_listener_oidc_action_or_opaque_action_fails(engine, actions):
    for key in ("defaultActions", "default_actions"):
        args = _transform_args(engine, LISTENER, {key: actions})
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args)


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize("step", [1, 2])
def test_an_inline_secret_policy_is_refused_at_every_step(engine, step):
    """F-03 (FR-34 B, AD-08): no inline ``policy`` bypasses SecretPolicy."""
    plain = _transform_args(engine, SECRET, {"name": "fixture"})
    assert _reject_secret_material(plain, step=step) is None
    for policy in ("{}", _secret("{}"), Unknown() if engine else _unresolved()):
        args = _transform_args(engine, SECRET, {"name": "fixture", "policy": policy})
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args, step=step)


@pytest.mark.parametrize("engine", [False, True])
def test_a_service_connect_log_secret_option_is_refused(engine):
    """F-02 audit: ``serviceConnectConfiguration`` carries ``secretOptions``."""
    assert _reject_secret_material(_transform_args(engine, SERVICE, {})) is None
    log = {"logDriver": "awslogs", "secretOptions": [{"name": "A", "valueFrom": "x"}]}
    for key in ("serviceConnectConfiguration", "service_connect_configuration"):
        args = _transform_args(engine, SERVICE, {key: {"logConfiguration": log}})
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args)


@pytest.mark.parametrize("engine", [False, True])
def test_task_volumes_hold_only_a_name(engine):
    """F-02 audit: FSx ``credentialsParameter`` and driver options fail."""
    key = "containerDefinitions" if engine else "container_definitions"

    def args(volumes):
        props = {key: _definitions(), "volumes": volumes}
        return _transform_args(engine, TASK, props)

    accepted = [{"name": "app-var"}]
    if not engine:
        accepted.append(aws.ecs.TaskDefinitionVolumeArgs(name="run"))
    for volumes in (None, [], accepted):
        assert _reject_secret_material(args(volumes)) is None
    fsx = {
        "fileSystemId": "fs-0123",
        "rootDirectory": "/",
        "authorizationConfig": {"credentialsParameter": SECRET_ARN, "domain": "d"},
    }
    for volumes in (
        [{"name": "a", "fsxWindowsFileServerVolumeConfiguration": fsx}],
        [{"name": "a", "dockerVolumeConfiguration": {"driverOpts": {"o": "x"}}}],
        [{"name": "a", "hostPath": "/"}],
        [aws.ecs.TaskDefinitionVolumeArgs(name="a", host_path="/")],
        [_secret({"name": "a"})],
        _secret([{"name": "a"}]),
        [object()],
        Unknown() if engine else _unresolved(),
    ):
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args(volumes))


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


def test_the_engine_stand_in_inspected_both_container_definitions(hardened):
    """F-01 non-vacuity: the engine path checked a resolved JSON string."""
    assert hardened["engine_task_definitions"] == {
        "user-service-web-task": "str",
        "user-service-worker-task": "str",
    }


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
    """N (V-17, F-04): the stack refuses engine 4.0.0 before any resource."""
    receipt = graph(tmp_path, "hardened", f"engine-{version}")
    assert "V-17" in receipt["error"]
    assert not [
        row
        for row in receipt["registrations"].values()
        if row["type"].startswith("aws:")
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
        # F-01 (a, b): a secret-marked or PascalCase container definition.
        ("root:secret-task", "unreviewed property"),
        ("stack:secret-task", "unreviewed property"),
        ("root:pascal-task", "unreviewed property"),
        # F-02: a listener OIDC action carries a client secret.
        ("root:oidc-listener", "unreviewed property"),
        ("stack:oidc-listener", "unreviewed property"),
        # F-03: an inline secret policy bypasses the step-1 SecretPolicy refusal.
        ("root:policy-secret", "unreviewed property"),
        ("stack:policy-secret", "unreviewed property"),
    ],
)
def test_a_readded_credential_or_step_two_resource_fails(tmp_path, addition, message):
    receipt = graph(tmp_path, "hardened", addition)
    assert message in receipt["error"]
    assert not [
        name for name in receipt["registrations"] if name.startswith("fixture-")
    ]


def test_the_lifecycle_doc_records_the_s13_gate_fixes():
    """F-05/F-06 (NFR-10): the doc states the real deferral and the residuals."""
    text = " ".join((ROOT / "specs/poc/secret-lifecycle.md").read_text().split())
    for marker in (
        "defers only a value it cannot inspect yet",
        "unknown, non-secret output value",
        "secret-marked input (`Output.secret(...)`",
        "case-insensitively",
        "require_plain_containers",
        "`authenticate_oidc` in any casing",
        "inline `policy` at any step",
        "Typed-input audit",
        "are no longer residuals",
        "is a shape heuristic",
        "source review remains the control",
        "closed to the shape `ComputePlane` emits",
        "`secretOptions` is refused",
        "The pre-hardening serializer now also runs the closed-key",
        "an input present in both casings is refused",
        "`ListenerDefaultActionArgs` and `TaskDefinitionVolumeArgs`",
        "(R-1)",
        "(R-2)",
        "before any resource registers, and the data plane repeats that check",
        "S3.4 replaces both with security-group references",
        "test_the_bootstrap_job_sg_reaches_documentdb_and_stays_in_the_vpc",
    ):
        assert marker in text, marker
    for stale in (
        "passes that check only",
        "checks the same environment rules",
        "raises before the data plane registers",
    ):
        assert stale not in text, stale


@pytest.mark.parametrize("engine", [False, True])
def test_the_guard_accepts_the_emitted_awslogs_shape(engine):
    """N-01: the closed log configuration still admits what ComputePlane emits."""
    key = "containerDefinitions" if engine else "container_definitions"
    full = {"awslogs-group": "/g", "awslogs-region": "r", "awslogs-stream-prefix": "p"}
    for options in ({}, full):
        log = {"logDriver": "awslogs", "options": options}
        args = _transform_args(engine, TASK, {key: _definitions(logConfiguration=log)})
        assert _reject_secret_material(args) is None


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize(
    ("kind", "snake", "camel", "good"),
    [
        (TASK, "container_definitions", "containerDefinitions", _definitions()),
        (CLUSTER, "manage_master_user_password", "manageMasterUserPassword", True),
        (LISTENER, "default_actions", "defaultActions", []),
        (SERVICE, "service_connect_configuration", "serviceConnectConfiguration", None),
    ],
)
def test_both_casings_of_one_input_are_refused(engine, kind, snake, camel, good):
    """N-03: two casings of one input are ambiguous on either path."""
    args = _transform_args(engine, kind, {snake: good, camel: good})
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(args)


@pytest.mark.parametrize("engine", [False, True])
def test_the_casing_of_the_path_wins_and_the_other_is_still_read(engine):
    """N-03: a lone key of either casing is read, never ignored."""
    own, other = (
        ("containerDefinitions", "container_definitions")
        if engine
        else ("container_definitions", "containerDefinitions")
    )
    dirty = _definitions([{"name": "DSN", "value": USERINFO}])
    for key in (own, other):
        args = _transform_args(engine, TASK, {key: _definitions()})
        assert _reject_secret_material(args) is None
        args = _transform_args(engine, TASK, {key: dirty})
        with pytest.raises(ValueError, match="unreviewed property"):
            _reject_secret_material(args)
