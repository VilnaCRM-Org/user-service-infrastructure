"""Executable mock registrations prove source ownership, not a native state plan."""

import asyncio
import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from coverage import Coverage, CoverageData

ROOT = Path(__file__).resolve().parents[2]
TAGS = {
    "Project": "user-service-infrastructure",
    "Environment": "test",
    "Owner": "team-user-service",
    "CostCenter": "core",
    "DataClassification": "internal",
    "Criticality": "high",
    "RetentionClass": "standard",
}
REGISTRIES = {
    kind: {
        "logical_name": f"user-service-{kind}-repository",
        "name": f"user-service-test-{kind}",
    }
    for kind in ("web", "worker")
}


# Synthetic provider identities shaped like the XP-8 contract fields.
MANAGED_SECRET_ARN = (
    "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
    "rds!cluster-00000000-0000-4000-8000-000000000003-AbCdEf"
)
XP8_IDS = {
    **{
        f"user-service-app-subnet-{index}": f"subnet-0123456789abcdef{index}"
        for index in (1, 2)
    },
    "user-service-bootstrap-job-sg": "sg-0123456789abcdef0",
}


# Synthetic ARN suffixes of the web load balancer and its target group.
ARN_SUFFIX_TYPES = {
    "aws:lb/loadBalancer:LoadBalancer": "app",
    "aws:lb/targetGroup:TargetGroup": "targetgroup",
}
# Each one-time action time of the scaling variants below (UTC, ``at()``).
AT = {
    "start-1": "2026-10-02T08:00:00",
    "stop-1": "2026-10-03T08:00:00",
    "start-2": "2026-10-04T08:00:00",
}


def _entries(*names):
    """Build the ``scaling.starts``/``scaling.stops`` lists of these entries."""
    lists = {"starts": [], "stops": []}
    for name in names:
        kind, seq = name.split("-")
        lists[kind + "s"].append({"seq": int(seq), "at": AT[name]})
    return lists


# Contract variants of the hardened probe (S2.1, FR-11 B1-B3): the step-2
# operation, its one-time entries, consumed names and the hold flag.
SCALING_VARIANTS = {
    "step2": ({"mode": "step2", "sequence": 2}, ("start-1",), (), False),
    "step2-stop": (
        {"mode": "rollback-zero", "phase": "stop", "sequence": 3},
        ("start-1", "stop-1"),
        (),
        False,
    ),
    "step2-hold": (
        {"mode": "rollback-zero", "phase": "hold", "sequence": 4},
        ("start-1", "stop-1"),
        (),
        True,
    ),
    "step2-policy-update": (
        {"mode": "policy-update", "sequence": 5},
        ("start-1", "stop-1"),
        (),
        True,
    ),
    "step2-restart": (
        {"mode": "rollback-zero", "phase": "start", "sequence": 5},
        ("start-1", "stop-1", "start-2"),
        (),
        False,
    ),
    "step2-moved": (
        {"mode": "rollback-zero", "phase": "start", "sequence": 5},
        ("start-1", "stop-1", "start-2"),
        (),
        False,
    ),
    "step2-consumed": (
        {"mode": "rollback-zero", "phase": "start", "sequence": 5},
        ("start-1", "stop-1", "start-2"),
        ("start-1",),
        False,
    ),
    # S2.2 FR-12 N: a dead-letter queue configured as a work queue.
    "step2-dlq-backlog": ({"mode": "step2", "sequence": 2}, ("start-1",), (), False),
    # S1.5 B: the step-2 graph with another managed-secret policy state.
    "step2-allow-rotation": ({"mode": "step2", "sequence": 2}, ("start-1",), (), False),
    "step2-tls-only": ({"mode": "step2", "sequence": 2}, ("start-1",), (), False),
}
SECRET_POLICY_VARIANTS = {
    "step2-allow-rotation": "allow-rotation",
    "step2-tls-only": "tls-only",
}


def _scaling_variant(contract, mode, mutation):
    """Apply one hardened step-2 variant; any other probe keeps its contract."""
    if mode != "hardened" or mutation not in SCALING_VARIANTS:
        return
    operation, names, consumed, suspended = SCALING_VARIANTS[mutation]
    from test_poc_contract_hardened import XP8

    contract["workload_step"] = 2
    contract["workload_operation"] = operation
    contract["workload"]["central"].update(copy.deepcopy(XP8))
    scaling = contract["scaling"]
    scaling.update(_entries(*names), consumed=list(consumed))
    if suspended:
        scaling["scheduled_scaling_suspended"] = True
    if mutation in SECRET_POLICY_VARIANTS:
        contract["documentdb_secret_policy"] = SECRET_POLICY_VARIANTS[mutation]
    if mutation == "step2-moved":
        # B2: an earlier entry's time changes (S4.9 admission refuses it).
        scaling["starts"][0]["at"] = "2026-10-02T09:00:00"


def _jwt_window_variant(contract, mode, mutation):
    """S1.8 (D-17): a JWT key change window holds a verify-only key."""
    if mode == "hardened" and mutation == "jwt-previous":
        contract["workload"]["central"]["cmk"]["jwt_previous"] = {
            "arn": (
                "arn:aws:kms:eu-central-1:891377212104:key/"
                "00000000-0000-4000-8000-000000000013"
            ),
            "alias": "alias/synthetic-poc-jwt-previous",
        }


def _mutate(value, registries, mutation):
    if mutation == "type":
        return None
    if mutation == "registries":
        registries["web"]["name"] = "foreign"
    if mutation in (
        "environment",
        "region",
        "service_name",
        "owner",
        "cost_center",
        "stack_tag",
    ):
        return replace(value, **{mutation: "foreign"})
    changes = {
        "preview": {"deployment_mode": "preview"},
        "tags": {
            "default_tags": {
                key: val for key, val in TAGS.items() if key != "Criticality"
            }
        },
        "images": {"images": replace(value.images, web_repository_name="foreign")},
        "role": {"runtime": replace(value.runtime, task_role_arn="foreign")},
        "runtime": {"runtime": replace(value.runtime, app_env="dev")},
        "proxy-subnets": {
            "network": replace(value.network, app_subnet_cidrs=("10.42.0.0/16",))
        },
    }
    return replace(value, **changes.get(mutation, {}))


SEED_VERSION_ID = "00000000-0000-4000-8000-0000000000a1"


def _seed_outputs(args, values):
    """Answer a seed Invocation as a first seed: no AWSCURRENT yet (AD-06)."""
    if args.typ == "aws:lambda/invocation:Invocation":
        values["result"] = json.dumps(
            {
                "secret_arn": json.loads(args.inputs["input"])["secret_arn"],
                "version_id": SEED_VERSION_ID,
                "status": "seeded",
            }
        )
    return values


def _generated_outputs(args, values):
    """Supply deterministic synthetic provider outputs without real generation."""
    if args.typ == "aws:s3/bucketV2:BucketV2":
        values["arn"] = f"arn:aws:s3:::{args.inputs['bucket']}"
    if args.typ == "random:index/randomPassword:RandomPassword":
        values["result"] = "synthetic-password-unchanging"
    if args.typ == "random:index/randomBytes:RandomBytes":
        values.update({"hex": "ab" * 32, "base64": "YWJj"})
    if args.typ == "tls:index/privateKey:PrivateKey":
        values.update(
            {
                "privateKeyPem": "synthetic-private",
                "publicKeyPem": "synthetic-public",
            }
        )
    if args.typ == "aws:secretsmanager/secret:Secret":
        values["arn"] = (
            f"arn:aws:secretsmanager:eu-central-1:891377212104:secret:{args.inputs['name']}-abcdef"
        )
    if args.typ == "aws:secretsmanager/secretVersion:SecretVersion":
        values["versionId"] = "1" * 32
    if args.typ == "aws:sesv2/emailIdentity:EmailIdentity":
        values["dkimSigningAttributes"] = {"tokens": [letter * 32 for letter in "abc"]}
    if args.typ == "aws:docdb/cluster:Cluster":
        values["endpoint"] = f"{args.inputs['clusterIdentifier']}.cluster.local"
        if args.inputs.get("manageMasterUserPassword") is True:
            # DocumentDB reports its one managed primary secret (S1.2, XP-8).
            values["masterUserSecrets"] = [
                {"secretArn": MANAGED_SECRET_ARN, "secretStatus": "active"}
            ]
    return values


def _arn_suffix_outputs(args, values):
    """The ALB request-count resource label joins both ARN suffixes (S2.1)."""
    if args.typ in ARN_SUFFIX_TYPES:
        values["arnSuffix"] = f"{ARN_SUFFIX_TYPES[args.typ]}/{args.name}/123"
    return values


def _topic_outputs(args, values):
    """Keep the synthetic alarm topic ARN in the contract's TEST account (S2.3)."""
    if args.typ == "aws:sns/topic:Topic":
        values["arn"] = f"arn:aws:sns:eu-central-1:891377212104:{args.inputs['name']}"
    return values


def _redis_outputs(args, values):
    """Report the primary endpoint ElastiCache derives from the group ID."""
    if args.typ == "aws:elasticache/replicationGroup:ReplicationGroup":
        group = args.inputs["replicationGroupId"].lower()
        values["primaryEndpointAddress"] = f"master.{group}.euc1.cache.amazonaws.com"
    return values


def _workload_queue_outputs(args, resource_id, values):
    """Keep synthetic SQS identities in the contract's TEST account."""
    if args.typ != "aws:sqs/queue:Queue":
        return resource_id, values
    name = args.inputs["name"]
    resource_id = f"https://sqs.eu-central-1.amazonaws.com/891377212104/{name}"
    values["id"] = resource_id
    values["arn"] = f"arn:aws:sqs:eu-central-1:891377212104:{name}"
    return resource_id, values


def _fixture_contract(root, config, name="workload"):
    """Bind synthetic declarations to this exact mocked workload target."""
    contract = json.loads(
        (root / f"tests/fixtures/poc-contract/{name}.synthetic.json").read_text()
    )
    central = contract["workload"]["central"]
    central["execution_role_arn"] = config["executionRoleArn"]
    central["task_role_arn"] = config["taskRoleArn"]
    for kind in ("web", "worker"):
        name = REGISTRIES[kind]["name"]
        registry = contract["registries"][kind]
        registry.update(REGISTRIES[kind])
        registry["arn"] = f"arn:aws:ecr:eu-central-1:891377212104:repository/{name}"
        registry["uri"] = f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{name}"
        contract["workload"]["release"][kind]["repository_uri"] = registry["uri"]
    return contract


def _bridge(contract, config, aws_config, mutation, *, generated_child=False):
    """Use the actual bridge with synthetic evidence in an isolated child."""
    from poc_workload_phase_entrypoint import (
        project_workload_phase,
        run_workload_phase,
        workload_configuration,
        workload_program_source,
    )
    from pulumi.runtime import set_all_config
    from test_poc_registry_phase_entrypoint import source

    images = {
        kind: {
            "uri": row["repository_uri"] + "@" + row["digest"],
            "platform": "linux/amd64",
            "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
            "config_digest": "sha256:" + "c" * 64,
            "config_size": 100,
        }
        for kind, row in contract["workload"]["release"].items()
        if kind in ("web", "worker")
    }
    projection = project_workload_phase(source(contract), contract, images)
    generated = workload_configuration(projection)
    if mutation == "config":
        generated["user-service-infrastructure:webImage"] = "foreign"
    set_all_config(
        {
            **{
                f"user-service-infrastructure:{key}": val for key, val in config.items()
            },
            **{f"aws:{key}": val for key, val in aws_config.items()},
            **generated,
        }
    )
    with patch(
        "app.environment._secret_value",
        side_effect=AssertionError("manual secret lookup"),
    ):
        if generated_child:
            arguments = ["/protected/pulumi/__main__.py"]
            if mutation == "cli":
                arguments.extend(["--phase", "workload"])
            with patch.object(sys, "argv", arguments):
                exec(
                    compile(
                        workload_program_source(projection),
                        "/protected/pulumi/__main__.py",
                        "exec",
                    ),
                    {"__name__": "__main__"},
                )
        else:
            _add_secret_material(run_workload_phase(projection), mutation)


def _mutation_config(mutation):
    """Composition-level N cases: a non-IAM engine, a configured password or a
    dead-letter queue configured as a work queue (S2.2)."""
    if mutation.startswith("engine-"):
        return {"documentDbEngineVersion": mutation.removeprefix("engine-")}
    if mutation == "password-config":
        return {"documentDbPassword": "synthetic-documentdb-password"}
    if mutation.startswith("redis-engine-"):
        return {"redisEngineVersion": mutation.removeprefix("redis-engine-")}
    if mutation == "redis-token-config":
        return {"redisAuthToken": "synthetic-redis-token"}
    if mutation == "step2-dlq-backlog":
        return {"sendEmailQueueName": "failed-send-email"}
    return {}


def _fixture_builders(options, identity):
    """Map each N-case kind to the forbidden registration it attempts.

    ``identity`` is this graph's ``redis_iam_identity``, so each Redis fixture
    differs from the reviewed shape in exactly one input.
    """
    import json

    import pulumi_aws as aws
    import pulumi_random as random
    from app.data import REDIS_APP_ACCESS_STRING

    import pulumi

    user_group_id, app_user_id = identity[3], identity[1]
    task_definitions = json.dumps(
        [
            {
                "name": "fixture",
                "environment": [
                    {"name": "DSN", "value": "https://user:synthetic@host"}
                ],
            }
        ]
    )
    pascal_definitions = json.dumps(
        [
            {
                "name": "fixture",
                "Environment": [
                    {"Name": "DSN", "Value": "https://user:synthetic@host"}
                ],
            }
        ]
    )
    oidc = aws.lb.ListenerDefaultActionArgs(
        type="authenticate-oidc",
        authenticate_oidc=aws.lb.ListenerDefaultActionAuthenticateOidcArgs(
            authorization_endpoint="https://idp.example/authorize",
            client_id="fixture",
            client_secret="synthetic-not-a-secret",
            issuer="https://idp.example",
            token_endpoint="https://idp.example/token",
            user_info_endpoint="https://idp.example/userinfo",
        ),
    )
    topic = (
        "arn:aws:sns:eu-central-1:891377212104:user-service-infrastructure-test-alarms"
    )
    other = "arn:aws:sns:eu-central-1:891377212104:someone-else"

    def alarm(**actions):
        """S2.4 gate I1: a metric alarm that differs only in its actions."""
        return lambda: aws.cloudwatch.MetricAlarm(
            "fixture-alarm",
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=1,
            metric_name="Evictions",
            namespace="AWS/ElastiCache",
            period=300,
            statistic="Sum",
            threshold=0,
            **actions,
            opts=options,
        )

    return {
        "alarm-on-topic": alarm(alarm_actions=[topic], ok_actions=[topic]),
        "alarm-foreign-action": alarm(alarm_actions=[other], ok_actions=[topic]),
        "alarm-extra-action": alarm(alarm_actions=[topic, other], ok_actions=[topic]),
        "alarm-no-ok-action": alarm(alarm_actions=[topic]),
        "alarm-foreign-ok-action": alarm(alarm_actions=[topic], ok_actions=[other]),
        "alarm-insufficient-data-action": alarm(
            alarm_actions=[topic], ok_actions=[topic], insufficient_data_actions=[topic]
        ),
        "alarm-no-action": alarm(),
        "random-password": lambda: random.RandomPassword(
            "fixture-material", length=16, opts=options
        ),
        "secret-version": lambda: aws.secretsmanager.SecretVersion(
            "fixture-version",
            secret_id="synthetic",
            secret_string="synthetic",
            opts=options,
        ),
        "ssm-parameter": lambda: aws.ssm.Parameter(
            "fixture-parameter", type="String", value="synthetic", opts=options
        ),
        # N1: an allowlisted DocumentDB cluster still refuses a primary password.
        "docdb-cluster": lambda: aws.docdb.Cluster(
            "fixture-cluster",
            master_username="synthetic",
            master_password="synthetic-not-a-secret",
            opts=options,
        ),
        # N (V-17): a managed-password cluster on a non-IAM engine fails.
        "docdb-cluster-4": lambda: aws.docdb.Cluster(
            "fixture-cluster",
            engine="docdb",
            engine_version="4.0.0",
            manage_master_user_password=True,
            opts=options,
        ),
        # FR-10 N (S1.9, m10): a DocumentDB log group off the runtime CMK.
        "docdb-audit-logs-no-key": lambda: aws.cloudwatch.LogGroup(
            "fixture-logs", name="/aws/docdb/fixture/audit", opts=options
        ),
        "docdb-profiler-logs-no-key": lambda: aws.cloudwatch.LogGroup(
            "fixture-logs", name="/aws/docdb/fixture/profiler", opts=options
        ),
        "docdb-audit-logs-jwt-key": lambda: aws.cloudwatch.LogGroup(
            "fixture-logs",
            name="/aws/docdb/fixture/audit",
            kms_key_id=(
                "arn:aws:kms:eu-central-1:891377212104:key/"
                "00000000-0000-4000-8000-000000000011"
            ),
            opts=options,
        ),
        # N (V-17): an elastic cluster has no IAM authentication.
        "docdb-elastic-cluster": lambda: aws.docdb.ElasticCluster(
            "fixture-elastic-cluster",
            admin_user_name="synthetic",
            admin_user_password="synthetic-not-a-secret",
            auth_type="PLAIN_TEXT",
            shard_capacity=2,
            shard_count=1,
            opts=options,
        ),
        # B (FR-34): a step-2 type never joins the step-1 graph.
        "secret-policy": lambda: aws.secretsmanager.SecretPolicy(
            "fixture-policy", secret_arn="synthetic", policy="{}", opts=options
        ),
        # FR-03 N: a plain environment value may not carry userinfo.
        "userinfo-task": lambda: aws.ecs.TaskDefinition(
            "fixture-task",
            family="fixture",
            container_definitions=task_definitions,
            opts=options,
        ),
        # F-01 (a): a secret-marked definition reaches the engine as a map.
        "secret-task": lambda: aws.ecs.TaskDefinition(
            "fixture-task",
            family="fixture",
            container_definitions=pulumi.Output.secret(task_definitions),
            opts=options,
        ),
        # F-01 (b): ECS would read PascalCase keys; the guard refuses them.
        "pascal-task": lambda: aws.ecs.TaskDefinition(
            "fixture-task",
            family="fixture",
            container_definitions=pascal_definitions,
            opts=options,
        ),
        # F-02: an OIDC listener action carries a client secret.
        "oidc-listener": lambda: aws.lb.Listener(
            "fixture-listener",
            load_balancer_arn="arn:aws:fixture",
            default_actions=[oidc],
            opts=options,
        ),
        # F-03: an inline policy bypasses the step-1 SecretPolicy refusal.
        "policy-secret": lambda: aws.secretsmanager.Secret(
            "fixture-secret", name="fixture", policy="{}", opts=options
        ),
        # N1: an allowlisted SES identity still refuses a BYODKIM private key.
        "byodkim-identity": lambda: aws.sesv2.EmailIdentity(
            "fixture-identity",
            email_identity="fixture.example",
            dkim_signing_attributes={
                # Base64 of "synthetic": a well-formed, non-secret key value.
                "domain_signing_private_key": "c3ludGhldGlj",
                "domain_signing_selector": "fixture",
            },
            opts=options,
        ),
        # FR-04 N (D-1): an AUTH token, TLS disabled or ``preferred``, an IAM
        # user whose name differs from its ID, or a declared Redis secret.
        "redis-auth-token": lambda: _redis_group(
            aws, options, user_group_id, auth_token="x" * 16
        ),
        "redis-tls-disabled": lambda: _redis_group(
            aws, options, user_group_id, transit_encryption_enabled=False
        ),
        "redis-tls-preferred": lambda: _redis_group(
            aws, options, user_group_id, transit_encryption_mode="preferred"
        ),
        # F1: a replication group bound to a user group this graph lacks.
        "redis-foreign-user-group": lambda: _redis_group(
            aws, options, user_group_id, user_group_ids=["fixture-users"]
        ),
        "redis-user-mismatch": lambda: aws.elasticache.User(
            "fixture-user",
            user_id=app_user_id,
            user_name="fixture-other",
            engine="redis",
            access_string=REDIS_APP_ACCESS_STRING,
            authentication_mode={"type": "iam"},
            opts=options,
        ),
        # F1: the AWS built-in ``default`` user is open (on ~* +@all, no password).
        "redis-open-default-group": lambda: aws.elasticache.UserGroup(
            "fixture-user-group",
            user_group_id=user_group_id,
            engine="redis",
            user_ids=["default", app_user_id],
            opts=options,
        ),
        # F11: a member this graph does not declare, a foreign group ID and a
        # foreign app-user ID; each differs from the reviewed shape by one input.
        "redis-foreign-member-group": lambda: aws.elasticache.UserGroup(
            "fixture-user-group",
            user_group_id=user_group_id,
            engine="redis",
            user_ids=["legacy-open-default", app_user_id],
            opts=options,
        ),
        "redis-foreign-group-id": lambda: aws.elasticache.UserGroup(
            "fixture-user-group",
            user_group_id="fixture-users",
            engine="redis",
            user_ids=[identity[2], app_user_id],
            opts=options,
        ),
        "redis-foreign-app-user": lambda: aws.elasticache.User(
            "fixture-user",
            user_id="fixture-app",
            user_name="fixture-app",
            engine="redis",
            access_string=REDIS_APP_ACCESS_STRING,
            authentication_mode={"type": "iam"},
            opts=options,
        ),
        "redis-secret": lambda: aws.secretsmanager.Secret(
            "fixture-secret",
            name="/user-service-infrastructure/runtime/test/redis_url",
            opts=options,
        ),
        # FR-16 N (S3.2): a default security group may hold no rule.
        "default-sg-ingress": lambda: aws.ec2.DefaultSecurityGroup(
            "fixture-default-sg",
            vpc_id="vpc-fixture",
            ingress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "self": True}],
            egress=[],
            opts=options,
        ),
        "default-sg-egress": lambda: aws.ec2.DefaultSecurityGroup(
            "fixture-default-sg",
            vpc_id="vpc-fixture",
            ingress=[],
            egress=[
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
            opts=options,
        ),
        # FR-15 N (S3.1): a flow log with an IAM role, or a bucket that
        # could be force-destroyed.
        "flow-log-role": lambda: aws.ec2.FlowLog(
            "fixture-flow-log",
            vpc_id="vpc-fixture",
            traffic_type="ALL",
            log_destination_type="cloud-watch-logs",
            log_destination="arn:aws:logs:eu-central-1:891377212104:log-group:fixture",
            iam_role_arn="arn:aws:iam::891377212104:role/fixture",
            opts=options,
        ),
        "bucket-force-destroy": lambda: aws.s3.BucketV2(
            "fixture-bucket", bucket="fixture-bucket", force_destroy=True, opts=options
        ),
        # N2: a hardened program calls no provider function.
        "random-password-invoke": lambda: aws.secretsmanager.get_random_password(
            password_length=16
        ),
    }


def _redis_group(aws, options, user_group_id, **changes):
    """Register an otherwise reviewed IAM replication group with one change."""
    arguments = {
        "description": "fixture",
        "transit_encryption_enabled": True,
        "transit_encryption_mode": "required",
        "engine": "redis",
        "engine_version": "7.1",
        "user_group_ids": [user_group_id],
        **changes,
    }
    return aws.elasticache.ReplicationGroup("fixture-redis", opts=options, **arguments)


def _add_secret_material(stack, mutation):
    """Re-add a forbidden generator or version under the hardened owner (N case)."""
    import pulumi

    # The owner varies: a runtime-secrets child, a direct stack child or a
    # root resource with no parent at all (F1: the guard is stack-wide).
    owner, _, kind = mutation.rpartition(":")
    parents = {"": stack.runtime_secrets, "stack": stack, "root": None}
    options = pulumi.ResourceOptions(parent=parents[owner])
    from app.data import redis_iam_identity

    identity = redis_iam_identity(stack.settings.stack_tag)
    builder = _fixture_builders(options, identity).get(kind)
    if builder is not None:
        builder()


class EngineTransforms:
    """Stand in for the engine callback server, which mocks do not run."""

    def __init__(self):
        self.registered = []
        self.invokes = []
        self.applied = []
        self.task_definitions = {}

    def register_stack_transform(self, transform):
        self.registered.append(transform)

    def register_invoke_transform(self, transform):
        self.invokes.append(transform)

    def apply(self, request):
        """Apply each registered engine transform as the engine would."""
        from pulumi.runtime import rpc

        import pulumi

        props = rpc.deserialize_properties(request.object)
        if request.type == "aws:ecs/taskDefinition:TaskDefinition":
            # Non-vacuity: record what the engine-path check inspected.
            value = props.get("containerDefinitions")
            self.task_definitions[request.name] = type(value).__name__
        for transform in self.registered:
            args = pulumi.ResourceTransformArgs(
                custom=request.custom,
                type_=request.type,
                name=request.name,
                props=props,
                opts=pulumi.ResourceOptions(),
            )
            assert transform(args) is None
            self.applied.append(request.name)

    def apply_invoke(self, request):
        """Apply each registered invoke transform before the mock answers."""
        from pulumi.runtime import rpc

        import pulumi

        for transform in self.invokes:
            args = pulumi.InvokeTransformArgs(
                token=request.tok,
                args=rpc.deserialize_properties(request.args),
                opts=pulumi.InvokeOptions(),
            )
            assert transform(args) is None


def _synthetic_call(_mocks, _args):
    """Answer an unguarded invoke with a synthetic non-secret value."""
    return {"id": "synthetic", "randomPassword": "synthetic-not-a-secret"}


def _transformed_invoke(monitor, request):
    """Apply the engine invoke transforms before the mock monitor answers."""
    from pulumi.runtime import mocks

    monitor.engine.apply_invoke(request)
    return mocks.MockMonitor.Invoke(monitor, request)


def _record_exports(exports):
    """Record each resolved stack export; mocks register no stack outputs."""
    import pulumi

    def record(name, value):
        pulumi.Output.from_input(value).apply(
            lambda resolved: exports.__setitem__(name, resolved)
        )

    pulumi.export = record


def _probe(root, mode, mutation, coverage_path):
    """Run both actual component compositions in independent Python runtimes."""
    sys.path[:0] = [
        str(root / "pulumi"),
        str(root / "tests/unit"),
        str(root / "scripts"),
    ]
    coverage = Coverage(
        config_file=False,
        branch=True,
        include=[
            str(root / "pulumi/app/workload_phase.py"),
            str(root / "pulumi/app/registry_phase.py"),
            str(root / "pulumi/app/runtime_secrets.py"),
            str(root / "pulumi/app/network.py"),
            str(root / "pulumi/app/data.py"),
            str(root / "pulumi/app/compute.py"),
            str(root / "pulumi/app/access_logs.py"),
            str(root / "pulumi/app/autoscaling.py"),
            str(root / "pulumi/app/observability.py"),
            str(root / "pulumi/app/flow_logs.py"),
            str(root / "pulumi/app/environment.py"),
            str(root / "scripts/poc_workload_phase_entrypoint.py"),
        ],
        data_file=str(coverage_path),
    )
    coverage.start()
    from app.environment import resolve_stack_settings
    from app.registry_phase import RegistryPhaseStack
    from app.runtime_secrets import RuntimeSecretsDescriptor
    from app.workload_phase import WorkloadPhaseStack
    from pulumi.runtime import mocks, rpc, set_all_config, settings, stack
    from test_environment_component import SimpleMocks

    registrations, outputs, exports = {}, {}, {}
    _record_exports(exports)
    engine = EngineTransforms()

    class Monitor(mocks.MockMonitor):
        def RegisterResource(self, request):
            engine.apply(request)
            result = super().RegisterResource(request)
            registrations[request.name] = {
                "urn": result.urn,
                "id": result.id,
                "parent": request.parent,
                "provider": request.provider,
                "type": request.type,
                "custom": request.custom,
                "inputs": rpc.deserialize_properties(request.object),
                "protect": request.protect,
                "dependencies": list(request.dependencies),
                "version": request.version,
                "additional_secret_outputs": list(request.additionalSecretOutputs),
                "ignore_changes": list(request.ignoreChanges),
                "custom_timeouts": {
                    key: getattr(request.customTimeouts, key)
                    for key in ("create", "update", "delete")
                    if getattr(request.customTimeouts, key)
                },
            }
            return result

        def RegisterResourceOutputs(self, request):
            outputs[request.urn] = rpc.deserialize_properties(request.outputs)
            return super().RegisterResourceOutputs(request)

        Invoke = _transformed_invoke

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    class GeneratedMocks(SimpleMocks):
        def new_resource(self, args):
            resource_id, values = super().new_resource(args)
            values = _redis_outputs(args, _generated_outputs(args, values))
            values = _seed_outputs(args, values)
            values = _topic_outputs(args, _arn_suffix_outputs(args, values))
            resource_id = XP8_IDS.get(args.name, resource_id)
            return _workload_queue_outputs(args, resource_id, values)

        call = _synthetic_call

    recorder = GeneratedMocks()
    monitor = Monitor(recorder)
    monitor.engine = engine
    mocks.set_mocks(
        recorder,
        project="user-service-infrastructure",
        stack="test",
        monitor=monitor,
    )
    settings.SETTINGS.feature_support["transforms"] = True
    settings.SETTINGS.feature_support["invokeTransforms"] = True
    settings.SETTINGS.callbacks = engine
    config = {
        "environment": "test",
        "serviceName": "user-service-infrastructure",
        "owner": "team-user-service",
        "costCenter": "core",
        "deploymentMode": "managed",
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": "s3://pulumi-user-service-infrastructure-test-state",
        "pulumiSecretsProvider": "awskms://alias/pulumi-user-service-infrastructure-test-secrets?region=eu-central-1",
        "webRepositoryName": "user-service-test-web",
        "workerRepositoryName": "user-service-test-worker",
        "executionRoleArn": (
            "arn:aws:iam::891377212104:role/"
            "user-service-infrastructure-test-EcsExecution"
        ),
        "taskRoleArn": (
            "arn:aws:iam::891377212104:role/user-service-infrastructure-test-EcsTask"
        ),
        "appEnv": "prod",
    }
    config.update(_mutation_config(mutation))
    config["certificateArn"] = _fixture_contract(root, config)["workload"]["external"][
        "domain"
    ]["certificate_arn"]
    config["mailSender"] = _fixture_contract(root, config)["workload"]["external"][
        "mail"
    ]["sender"]
    aws_config = {
        "region": "eu-central-1",
        "allowedAccountIds": '["891377212104"]',
        "skipCredentialsValidation": "false",
        "skipRegionValidation": "false",
        "skipRequestingAccountId": "false",
    }
    set_all_config(
        {
            **{
                f"user-service-infrastructure:{key}": value
                for key, value in config.items()
            },
            **{f"aws:{key}": value for key, value in aws_config.items()},
        }
    )

    def program():
        if mode == "registry":
            RegistryPhaseStack(registries=copy.deepcopy(REGISTRIES))
            return
        # Pure metadata fixture avoids constructing a second EnvironmentSettings.
        metadata = SimpleNamespace(
            environment_name="test",
            service_name_value="user-service-infrastructure",
            owner="team-user-service",
            cost_center="core",
        )
        contract = _fixture_contract(
            root, config, {"hardened": "workload-hardened"}.get(mode, "workload")
        )
        _scaling_variant(contract, mode, mutation)
        _jwt_window_variant(contract, mode, mutation)
        if mode in {"bridge", "generated-child", "hardened"}:
            _bridge(
                contract,
                config,
                aws_config,
                mutation,
                generated_child=mode == "generated-child",
            )
            return
        with patch(
            "app.environment._secret_value",
            side_effect=AssertionError("manual secret lookup"),
        ):
            value = resolve_stack_settings(metadata, generated_secrets=True)
        assert value.is_managed and value.secrets is None
        registries = copy.deepcopy(REGISTRIES)
        value = _mutate(value, registries, mutation)
        descriptor = RuntimeSecretsDescriptor(contract)
        if mutation == "descriptor":
            descriptor = None
        if mutation == "descriptor-role":
            contract["workload"]["central"]["task_role_arn"] += "-foreign"
            descriptor = RuntimeSecretsDescriptor(contract)
        WorkloadPhaseStack(settings=value, registries=registries, secrets=descriptor)

    error = None
    try:
        loop.run_until_complete(stack.run_pulumi_func(program))
    except ValueError as exc:
        error = str(exc)
    loop.run_until_complete(asyncio.sleep(0))
    # Secrets in this fixture are explicitly synthetic preview values; do not
    # reuse this recorder as a live checkpoint or native ownership attestation.
    print(
        json.dumps(
            {
                "registrations": registrations,
                "outputs": outputs,
                "error": error,
                "aws_config": aws_config,
                "engine_transforms": len(engine.registered),
                "engine_applied": engine.applied,
                "engine_task_definitions": engine.task_definitions,
                "invoke_transforms": len(engine.invokes),
                "exports": exports,
            },
            default=str,
        )
    )
    settings.reset_options(project=None, stack=None)
    loop.close()
    coverage.stop()
    coverage.save()


def graph(tmp_path, mode="workload", mutation="none"):
    coverage_path = tmp_path / f"{mode}-{mutation}.coverage"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            __file__,
            "probe",
            str(ROOT),
            mode,
            mutation,
            str(coverage_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("COV_CORE_", "COVERAGE_"))
        },
    )
    assert result.returncode == 0, result.stderr
    if active := Coverage.current():
        child = CoverageData(basename=str(coverage_path))
        child.read()
        active.get_data().update(child)
    return json.loads(result.stdout)


def test_workload_extends_actual_registry_registrations_without_changing_baseline(
    tmp_path,
):
    before, after = graph(tmp_path, "registry"), graph(tmp_path)
    assert before["error"] is after["error"] is None
    baseline, workload = before["registrations"], after["registrations"]
    assert set(baseline) == {
        "user-service-infrastructure-test",
        "environment-settings",
        "user-service",
        "registries",
        "user-service-web-repository",
        "user-service-worker-repository",
        "user-service-mail-identity",
        "user-service-mail-dkim-0",
        "user-service-mail-dkim-1",
        "user-service-mail-dkim-2",
    }
    assert {name: workload[name] for name in baseline} == baseline
    assert all(
        after["outputs"][urn] == value for urn, value in before["outputs"].items()
    )
    assert after["aws_config"] == before["aws_config"]
    # MockMonitor omits the implicit AWS provider. No synthetic provider record
    # is invented; native provider identity/no-change still needs a real preview.
    assert not any(row["type"] == "pulumi:providers:aws" for row in workload.values())
    assert all(row["provider"] == "" for row in workload.values())
    owner = baseline["user-service"]["urn"]
    for name in ("network", "data", "messaging", "compute"):
        assert workload[name]["parent"] == owner
    types = {row["type"] for row in workload.values()}
    assert {
        "aws:ec2/vpc:Vpc",
        "aws:docdb/cluster:Cluster",
        "aws:elasticache/replicationGroup:ReplicationGroup",
        "aws:sqs/queue:Queue",
        "aws:ecs/taskDefinition:TaskDefinition",
        "aws:lb/loadBalancer:LoadBalancer",
        "aws:cloudwatch/logGroup:LogGroup",
        "aws:secretsmanager/secret:Secret",
    } <= types
    assert not any(kind.startswith("aws:iam/") for kind in types)
    assert (
        sum(
            kind == "aws:ecr/repository:Repository"
            for kind in (row["type"] for row in workload.values())
        )
        == 2
    )
    for name in ("user-service-web-repository", "user-service-worker-repository"):
        assert workload[name]["inputs"]["tags"] == TAGS
    from app.access_logs import LOGGING_EXEMPTION
    from app.workload_phase import TAGGABLE_TYPES

    for name, row in workload.items():
        if name == "user-service-alb-logs":
            # The log destination keeps its reviewed server-access-log exemption.
            assert row["inputs"]["tags"] == {**LOGGING_EXEMPTION, **TAGS}
        elif row["type"] in TAGGABLE_TYPES:
            assert row["inputs"]["tags"] == TAGS
        elif row["type"] not in (
            "aws:ecr/repository:Repository",
            "aws:sesv2/emailIdentity:EmailIdentity",
        ):
            assert "tags" not in row["inputs"]


@pytest.mark.parametrize(
    "mutation",
    [
        "preview",
        "type",
        "environment",
        "region",
        "service_name",
        "owner",
        "cost_center",
        "stack_tag",
        "tags",
        "registries",
        "images",
        "role",
        "runtime",
        "proxy-subnets",
        "descriptor",
        "descriptor-role",
    ],
)
def test_bad_internal_settings_fail_before_any_aws_registration(tmp_path, mutation):
    receipt = graph(tmp_path, mutation=mutation)
    assert receipt["error"] is not None
    assert not any(
        row["type"].startswith("aws:") for row in receipt["registrations"].values()
    )
    assert set(receipt["registrations"]) <= {"user-service-infrastructure-test"}


def test_workload_tags_preserve_extra_fields_and_reject_baseline_conflicts():
    from app.workload_phase import _merge_tags

    assert _merge_tags({"Name": "workload", "Owner": TAGS["Owner"]}, TAGS) == {
        **TAGS,
        "Name": "workload",
    }
    for tags in ("unsupported", {"Owner": "foreign"}):
        with pytest.raises(ValueError, match="overrides preserved baseline tags"):
            _merge_tags(tags, TAGS)


if __name__ == "__main__":
    assert sys.argv[1] == "probe"
    _probe(Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5]))


def test_private_workload_network_has_only_gateway_https(tmp_path):
    result = graph(tmp_path, "bridge")
    assert result["error"] is None
    rows = result["registrations"]
    alb = rows["user-service-alb"]["inputs"]
    assert alb["internal"] is True
    assert alb["subnets"] == [
        rows[f"user-service-app-subnet-{index}"]["id"] for index in (1, 2)
    ]
    link = rows["user-service-vpc-link-sg"]
    assert link["inputs"]["vpcId"] == rows["user-service-vpc"]["id"]
    assert link["inputs"]["ingress"] == []
    assert link["inputs"]["egress"] == [
        {
            "protocol": "tcp",
            "fromPort": 443,
            "toPort": 443,
            "cidrBlocks": ["10.42.10.0/24", "10.42.11.0/24"],
        }
    ]
    assert rows["user-service-alb-sg"]["inputs"]["ingress"] == [
        {
            "protocol": "tcp",
            "fromPort": 443,
            "toPort": 443,
            "securityGroups": [link["id"]],
        }
    ]
    assert "user-service-http-listener" not in rows
    assert rows["user-service-https-listener"]["inputs"]["port"] == 443


def test_private_gateway_listener_requires_certificate():
    from app.compute import ComputePlane

    settings = SimpleNamespace(runtime=SimpleNamespace(certificate_arn=None))
    with pytest.raises(ValueError, match="admitted certificate"):
        object.__new__(ComputePlane)._create_http_listener(
            settings, None, None, private_gateway=True
        )
