"""First-workload topology prerequisite, not complete input or IAM admission.

The installed two-AZ ECS/Fargate composition and bounded known native inputs are
covered. Unknown computed inputs and baseline configuration still need semantic
binding. No capability object or caller boolean can turn this source-only validator
into execution authority.
"""

import base64
import json
import re

import poc_contract
import poc_registry_plan as registry
import poc_workload_reconciliation as unchanged
from poc_registry_phase_entrypoint import RegistryPhaseProjection
from poc_workload_aliases import state_aliases, structured_aliases
from poc_workload_phase_entrypoint import _checked, workload_certificate_arn
from service_execution_process import require

SECRET_VERSION_OUTPUTS = [
    "secretString",
    "secretBinary",
    "secretString",
    "secretStringWo",
]
ALLOWED_HTTPS_RULE_FIELDS = frozenset(
    {
        "protocol",
        "fromPort",
        "toPort",
        "securityGroups",
        "cidrBlocks",
        "ipv6CidrBlocks",
        "prefixListIds",
        "self",
        "description",
    }
)
CONTAINER_SECRET_NAMES = {
    "MONGODB_URL": "document_db_url",
    "REDIS_URL": "redis_url",
    # These are environment-variable and secret-purpose identifiers, not values.
    "APP_SECRET": "app_secret",  # nosec B105
    "OAUTH_ENCRYPTION_KEY": "oauth_encryption_key",
    "OAUTH_PASSPHRASE": "oauth_passphrase",  # nosec B105
    "TWO_FACTOR_ENCRYPTION_KEY": "two_factor_encryption_key",
    "OAUTH_PRIVATE_KEY_PEM": "oauth_private_key",
    "OAUTH_PUBLIC_KEY_PEM": "oauth_public_key",
    "REDIS_LOCKOUT_URL": "redis_url",
}
QUEUE_NAMES = {
    "send-email": "send-email",
    "failed-send-email": "failed-send-email",
    "insert-user-batch": "insert-user-batch",
    "domain-events": "domain-events",
    "failed-domain-events": "failed-domain-events",
    "health-check": "health-check-queue",
}
DOCUMENTDB_CLUSTER = f"{registry.PROJECT}-test-docdb"
DOCUMENTDB_PARAMETERS = [
    {"name": name, "value": value, "applyMethod": "pending-reboot"}
    for name, value in (
        ("audit_logs", "enabled"),
        ("profiler", "enabled"),
        ("profiler_threshold_ms", "100"),
        ("tls", "enabled"),
    )
]
QUEUE_ENVIRONMENT_NAMES = {
    "SEND_EMAIL_TRANSPORT_DSN": "send-email",
    "FAILED_EMAIL_TRANSPORT_DSN": "failed-send-email",
    "INSERT_USER_BATCH_TRANSPORT_DSN": "insert-user-batch",
    "DOMAIN_EVENTS_TRANSPORT_DSN": "domain-events",
    "FAILED_DOMAIN_EVENTS_TRANSPORT_DSN": "failed-domain-events",
}


def _sdk_aliases(kind):
    return structured_aliases(kind)


def _check(condition):
    require(condition, "workload-first-topology")


def expected_graph():
    """Return the finite current installed composition, including pinned providers."""
    graph = registry._graph(RegistryPhaseProjection(registry.REGISTRIES))

    def add(name, kind, parent, *, protect=False):
        custom = kind.startswith(("aws:", "random:", "tls:", "pulumi:providers:"))
        ancestry = (
            parent.split("::")[-2] + "$" if parent and parent != registry.ROOT else ""
        )
        urn = registry.PREFIX + ancestry + kind + "::" + name
        graph[urn] = (kind, parent, custom, protect)
        return urn

    graph = {urn: (*row, False) for urn, row in graph.items()}
    for package, version in (("random", "4_19_2"), ("tls", "5_3_1")):
        add(f"default_{version}", f"pulumi:providers:{package}", "")
    planes = {
        name: add(name, f"{registry.PROJECT}:{kind}:Plane", registry.SERVICE_URN)
        for name, kind in (
            ("network", "network"),
            ("data", "data"),
            ("messaging", "messaging"),
            ("compute", "compute"),
        )
    }
    _runtime_graph(add)
    _network_graph(add, planes)
    _application_graph(add, planes)
    return graph


def _runtime_graph(add):
    runtime = add(
        "runtime-secrets", f"{registry.PROJECT}:secrets:Runtime", registry.SERVICE_URN
    )
    for purpose in ("document_db_password", "redis_auth_token"):
        add(
            f"runtime-{purpose}-material",
            "random:index/randomPassword:RandomPassword",
            runtime,
            protect=True,
        )
    for purpose in (
        "app_secret",
        "oauth_encryption_key",
        "oauth_passphrase",
        "two_factor_encryption_key",
    ):
        add(
            f"runtime-{purpose}-material",
            "random:index/randomBytes:RandomBytes",
            runtime,
            protect=True,
        )
    add("runtime-oauth-key", "tls:index/privateKey:PrivateKey", runtime, protect=True)
    for purpose in (
        "document_db_password",
        "redis_auth_token",
        "app_secret",
        "oauth_encryption_key",
        "oauth_passphrase",
        "two_factor_encryption_key",
        "oauth_private_key",
        "oauth_public_key",
        "document_db_url",
        "redis_url",
    ):
        add(
            f"runtime-{purpose}",
            "aws:secretsmanager/secret:Secret",
            runtime,
            protect=True,
        )
        add(
            f"runtime-{purpose}-version",
            "aws:secretsmanager/secretVersion:SecretVersion",
            runtime,
            protect=True,
        )


def _network_graph(add, planes):
    network = {
        "vpc": "vpc:Vpc",
        "igw": "internetGateway:InternetGateway",
        "public-rt": "routeTable:RouteTable",
    }
    for index in (1, 2):
        for prefix in ("public", "app", "data"):
            network[f"{prefix}-subnet-{index}"] = "subnet:Subnet"
            network[f"{prefix}-rta-{index}"] = (
                "routeTableAssociation:RouteTableAssociation"
            )
        for prefix in ("app", "data"):
            network[f"{prefix}-rt-{index}"] = "routeTable:RouteTable"
        network[f"nat-eip-{index}"] = "eip:Eip"
        network[f"nat-{index}"] = "natGateway:NatGateway"
    for purpose in ("alb", "vpc-link", "service", "documentdb", "redis"):
        network[f"{purpose}-sg"] = "securityGroup:SecurityGroup"
    for name, kind in network.items():
        add(f"user-service-{name}", f"aws:ec2/{kind}", planes["network"])


def _application_graph(add, planes):
    for name, kind in {
        "documentdb-subnets": "docdb/subnetGroup:SubnetGroup",
        "documentdb-parameters": "docdb/clusterParameterGroup:ClusterParameterGroup",
        "documentdb-audit-logs": "cloudwatch/logGroup:LogGroup",
        "documentdb-profiler-logs": "cloudwatch/logGroup:LogGroup",
        "documentdb-cluster": "docdb/cluster:Cluster",
        "documentdb-instance-1": "docdb/clusterInstance:ClusterInstance",
        "documentdb-instance-2": "docdb/clusterInstance:ClusterInstance",
        "redis-subnets": "elasticache/subnetGroup:SubnetGroup",
        "redis": "elasticache/replicationGroup:ReplicationGroup",
    }.items():
        # DocumentDB owns durable data; Pulumi must refuse to delete it.
        add(
            f"user-service-{name}",
            f"aws:{kind}",
            planes["data"],
            protect=kind
            in ("docdb/cluster:Cluster", "docdb/clusterInstance:ClusterInstance"),
        )
    for name in (
        "send-email",
        "failed-send-email",
        "insert-user-batch",
        "domain-events",
        "failed-domain-events",
        "health-check",
    ):
        add(f"user-service-{name}", "aws:sqs/queue:Queue", planes["messaging"])
    compute = {
        "ecs-cluster": "ecs/cluster:Cluster",
        "alb": "lb/loadBalancer:LoadBalancer",
        "target-group": "lb/targetGroup:TargetGroup",
        "https-listener": "lb/listener:Listener",
    }
    for kind in ("web", "worker"):
        compute.update(
            {
                f"{kind}-repository-lifecycle": "ecr/lifecyclePolicy:LifecyclePolicy",
                f"{kind}-logs": "cloudwatch/logGroup:LogGroup",
                f"{kind}-task": "ecs/taskDefinition:TaskDefinition",
                f"{kind}-service": "ecs/service:Service",
            }
        )
    for name, kind in compute.items():
        add(f"user-service-{name}", f"aws:{kind}", planes["compute"])
    logs = add(
        "access-logs", f"{registry.PROJECT}:compute:AccessLogs", planes["compute"]
    )
    for suffix, kind in {
        "": "bucketV2:BucketV2",
        "-ownership": "bucketOwnershipControls:BucketOwnershipControls",
        "-public-access": "bucketPublicAccessBlock:BucketPublicAccessBlock",
        "-encryption": (
            "bucketServerSideEncryptionConfigurationV2:"
            "BucketServerSideEncryptionConfigurationV2"
        ),
        "-versioning": "bucketVersioningV2:BucketVersioningV2",
        "-retention": "bucketLifecycleConfigurationV2:BucketLifecycleConfigurationV2",
        "-policy": "bucketPolicy:BucketPolicy",
    }.items():
        add(
            f"user-service-alb-logs{suffix}", f"aws:s3/{kind}", logs, protect=not suffix
        )


def _new_goal(urn, plan, graph, provider_id):
    registry._object(
        plan, {"goal", "steps", "state", "seed"}, {"goal", "steps", "state", "seed"}
    )
    _check(plan["steps"] == ["create"])
    _check(plan["state"] is None or type(plan["state"]) is dict)
    _check(len(base64.b64decode(plan["seed"], validate=True)) == 32)
    goal = plan["goal"]
    registry._object(goal, {"type", "name", "custom", "protect"}, registry.GOAL_FIELDS)
    kind, parent, custom, protect = graph[urn]
    _check(
        unchanged._same(
            [goal["type"], goal.get("parent", ""), goal["custom"], goal["protect"]],
            [kind, parent, custom, protect],
        )
    )
    _check(goal["name"] == urn.rsplit("::", 1)[-1])
    _check(
        not any(
            goal.get(key)
            for key in (
                "aliases",
                "id",
                "ignoreChanges",
                "deleteBeforeReplace",
                "customTimeouts",
            )
        )
    )
    _check(unchanged._same(goal.get("structuredAliases", []), _sdk_aliases(kind)))
    inputs, outputs = registry._goal_values(goal, None)
    state = {key: value for key, value in goal.items() if key in registry.STATE_FIELDS}
    state.update(urn=urn, inputs=inputs, outputs=outputs)
    _check(goal.get("provider", "") == _provider_value(kind, graph, provider_id))
    _secret_version_goal(kind, goal, inputs, state)
    unchanged._redacted(inputs)
    return state


def _provider_value(kind, graph, provider_id):
    package = kind.split(":", 1)[0]
    if package not in ("aws", "random", "tls"):
        return ""
    provider = (
        registry.PROVIDER_URN
        if package == "aws"
        else next(
            key for key, row in graph.items() if row[0] == f"pulumi:providers:{package}"
        )
    )
    return provider + "::" + (provider_id if package == "aws" else registry.UNKNOWN)


def _secret_version_goal(kind, goal, inputs, state):
    if kind != "aws:secretsmanager/secretVersion:SecretVersion":
        return
    _check(set(inputs) == {"secretId", "secretString"})
    _check(goal.get("additionalSecretOutputs") == SECRET_VERSION_OUTPUTS)
    if inputs["secretString"] != registry.UNKNOWN:
        unchanged._secret_inputs(state)


def validate_first_workload_topology(
    preview, *, saved_plan, prior_resources, projection
):
    """Check exact registry-to-workload owners and operations; never grant apply."""
    projection = _checked(projection)
    baseline = registry._graph(RegistryPhaseProjection(registry.REGISTRIES))
    prior = registry._prior(prior_resources, baseline)
    _check(prior.keys() == baseline.keys())
    graph = expected_graph()
    plans = saved_plan["resourcePlans"]
    _check(type(plans) is dict and plans.keys() == graph.keys())
    registry.validate(
        {
            **preview,
            "steps": _baseline_steps(preview, prior),
        },
        saved_plan={
            **saved_plan,
            "resourcePlans": {urn: plans[urn] for urn in baseline},
        },
        prior_resources=prior_resources,
        projection=RegistryPhaseProjection(registry.REGISTRIES),
    )
    desired = dict(prior)
    for urn in graph.keys() - baseline.keys():
        desired[urn] = _new_goal(
            urn, plans[urn], graph, prior[registry.PROVIDER_URN]["id"]
        )
        _task_execution_inputs(desired[urn], projection)
    # All references must remain inside the complete finite owner graph.
    for row in desired.values():
        references = {key: value for key, value in row.items() if key != "provider"}
        unchanged._references(references, desired)
    _dependency_edges(desired)
    _private_gateway_inputs(desired, projection)
    _web_target_inputs(desired, projection)
    _task_container_inputs(desired, projection)
    _private_subnet_inputs(desired, projection)
    _managed_data_inputs(desired)
    _documentdb_observability_inputs(desired)
    _encrypted_queue_inputs(desired)
    _fargate_service_inputs(desired)
    seen = _validate_workload_steps(preview["steps"], baseline, graph, desired)
    required = {
        urn
        for urn in graph.keys() - baseline.keys()
        if not graph[urn][0].startswith("pulumi:providers:")
    }
    _check(required <= seen)


def _inputs(desired, name):
    rows = [row for urn, row in desired.items() if urn.rsplit("::", 1)[-1] == name]
    _check(len(rows) == 1 and type(rows[0].get("inputs")) is dict)
    return rows[0]["inputs"]


def _dependency_edges(desired):
    """Keep the fixed private network and ECS edges in first-create plans.

    Unknown physical IDs still require accepted-result observation. Native
    dependency edges cannot replace that observation, but their absence is a
    definite topology mismatch before credentials can reach the child.
    """
    names = {urn.rsplit("::", 1)[-1]: urn for urn in desired}
    required = {
        "user-service-alb": {
            "user-service-alb-sg",
            "user-service-app-subnet-1",
            "user-service-app-subnet-2",
        },
        "user-service-alb-sg": {"user-service-vpc", "user-service-vpc-link-sg"},
        "user-service-vpc-link-sg": {"user-service-vpc"},
        "user-service-target-group": {"user-service-vpc"},
        "user-service-documentdb-cluster": {
            "user-service-documentdb-parameters",
            "user-service-documentdb-audit-logs",
            "user-service-documentdb-profiler-logs",
        },
        "user-service-https-listener": {
            "user-service-alb",
            "user-service-target-group",
        },
        "user-service-web-service": {
            "user-service-web-task",
            "user-service-service-sg",
            "user-service-app-subnet-1",
            "user-service-app-subnet-2",
            "user-service-https-listener",
            "user-service-target-group",
        },
        "user-service-worker-service": {
            "user-service-worker-task",
            "user-service-service-sg",
            "user-service-app-subnet-1",
            "user-service-app-subnet-2",
        },
    }
    for owner, targets in required.items():
        dependencies = desired[names[owner]].get("dependencies")
        require(
            type(dependencies) is list
            and {names[name] for name in targets} <= set(dependencies),
            "workload-first-topology-dependencies",
        )


def _private_gateway_inputs(desired, projection):
    """Reject public ingress and cleartext listeners in the saved native plan.

    First-create physical IDs can still be unknown. The accepted-result observer
    must later bind the actual ALB, listener and security-group relationships.
    """
    _private_alb(_inputs(desired, "user-service-alb"))
    _alb_ingress(_inputs(desired, "user-service-alb-sg"))
    cidrs = projection.contract["workload"]["runtime"]["trusted_proxy_cidrs"]
    _vpc_link_group(_inputs(desired, "user-service-vpc-link-sg"), cidrs)
    _https_listener(_inputs(desired, "user-service-https-listener"), projection)


def _private_alb(alb):
    label = "workload-private-alb-inputs"
    require(
        alb.get("internal") is True
        and alb.get("loadBalancerType") == "application"
        and alb.get("dropInvalidHeaderFields") is True,
        label,
    )
    for field, count in (("subnets", 2), ("securityGroups", 1)):
        values = alb.get(field)
        require(type(values) is list and len(values) == count, label)


def _https_rule(rule, label):
    require(type(rule) is dict and set(rule) <= ALLOWED_HTTPS_RULE_FIELDS, label)
    require(
        rule.get("protocol") == "tcp"
        and rule.get("fromPort") == 443
        and rule.get("toPort") == 443
        and rule.get("self", False) is False,
        label,
    )


def _alb_ingress(alb_group):
    label = "workload-private-alb-ingress"
    rules = alb_group.get("ingress")
    require(type(rules) is list and len(rules) == 1, label)
    rule = rules[0]
    _https_rule(rule, label)
    require(
        type(rule.get("securityGroups")) is list
        and len(rule["securityGroups"]) == 1
        and all(
            rule.get(field, []) == []
            for field in ("cidrBlocks", "ipv6CidrBlocks", "prefixListIds")
        ),
        label,
    )


def _vpc_link_group(link_group, expected_cidrs):
    label = "workload-vpc-link-group-inputs"
    require(link_group.get("ingress") == [], label)
    egress = link_group.get("egress")
    require(type(egress) is list and len(egress) == 1, label)
    rule = egress[0]
    _https_rule(rule, label)
    require(
        rule.get("cidrBlocks") == expected_cidrs
        and all(
            rule.get(field, []) == []
            for field in ("ipv6CidrBlocks", "prefixListIds", "securityGroups")
        ),
        label,
    )


def _https_listener(listener, projection):
    require(
        listener.get("protocol") == "HTTPS"
        and listener.get("port") == 443
        and listener.get("sslPolicy") == "ELBSecurityPolicy-TLS13-1-2-Res-2021-06"
        and listener.get("certificateArn") == workload_certificate_arn(projection),
        "workload-https-listener-inputs",
    )
    actions = listener.get("defaultActions")
    label = "workload-https-listener-action"
    require(type(actions) is list and len(actions) == 1, label)
    action = actions[0]
    require(
        type(action) is dict
        and set(action) == {"type", "targetGroupArn"}
        and action["type"] == "forward"
        and type(action["targetGroupArn"]) is str
        and bool(action["targetGroupArn"]),
        label,
    )


def _web_target_inputs(desired, projection):
    """Check known routing settings; unknown ARNs still need native observation."""
    target = _inputs(desired, "user-service-target-group")
    require(
        target.get("protocol") == "HTTP"
        and target.get("targetType") == "ip"
        and type(target.get("port")) is int
        and 1 <= target["port"] <= 65535
        and unchanged._same(target.get("deregistrationDelay"), 30),
        "workload-web-target-inputs",
    )
    require(
        unchanged._same(
            target.get("healthCheck"),
            {
                "enabled": True,
                "path": projection.contract["workload"]["runtime"]["health_path"],
                "protocol": "HTTP",
                "matcher": "200-399",
                "healthyThreshold": 2,
                "unhealthyThreshold": 3,
                "interval": 30,
                "timeout": 5,
            },
        ),
        "workload-web-target-health",
    )
    action = _inputs(desired, "user-service-https-listener")["defaultActions"][0]
    web = _inputs(desired, "user-service-web-service")
    worker = _inputs(desired, "user-service-worker-service")
    require(
        unchanged._same(
            web.get("loadBalancers"),
            [
                {
                    "containerName": "user-service-web",
                    "containerPort": target["port"],
                    "targetGroupArn": action["targetGroupArn"],
                }
            ],
        )
        and worker.get("loadBalancers", []) == [],
        "workload-web-service-target",
    )


def _private_subnet_inputs(desired, projection):
    """Bind the private ALB/ECS networks to the admitted proxy CIDRs."""
    expected = projection.contract["workload"]["runtime"]["trusted_proxy_cidrs"]
    app = [_inputs(desired, f"user-service-app-subnet-{index}") for index in (1, 2)]
    data_flags = [
        _inputs(desired, f"user-service-data-subnet-{index}").get("mapPublicIpOnLaunch")
        for index in (1, 2)
    ]
    require(
        [row.get("cidrBlock") for row in app] == expected
        and all(row.get("mapPublicIpOnLaunch") is False for row in app)
        and all(flag is None or flag is False for flag in data_flags),
        "workload-private-subnet-inputs",
    )


def _managed_data_inputs(desired):
    """Reject unencrypted DocumentDB or Redis in a matching plan and preview."""
    expected = {
        "user-service-documentdb-cluster": {
            "engine": "docdb",
            "engineVersion": "5.0.0",
            "storageEncrypted": True,
            "enabledCloudwatchLogsExports": ["audit", "profiler"],
            "dbClusterParameterGroupName": f"{DOCUMENTDB_CLUSTER}-params",
            "deletionProtection": True,
            "skipFinalSnapshot": False,
            "finalSnapshotIdentifier": f"{DOCUMENTDB_CLUSTER}-final",
        },
        "user-service-redis": {
            "engine": "redis",
            "engineVersion": "7.1",
            "atRestEncryptionEnabled": True,
            "transitEncryptionEnabled": True,
            "transitEncryptionMode": "required",
            "authTokenUpdateStrategy": "ROTATE",
        },
    }
    for name, fields in expected.items():
        inputs = _inputs(desired, name)
        require(
            unchanged._same({key: inputs.get(key) for key in fields}, fields),
            "workload-managed-data-inputs",
        )
    docdb = _inputs(desired, "user-service-documentdb-cluster")
    redis = _inputs(desired, "user-service-redis")
    require(
        type(docdb.get("backupRetentionPeriod")) is int
        and docdb["backupRetentionPeriod"] >= 7
        and type(redis.get("snapshotRetentionLimit")) is int
        and redis["snapshotRetentionLimit"] >= 7,
        "workload-managed-data-retention",
    )


def _documentdb_observability_inputs(desired):
    """Require explicit TLS/audit/profiler parameters and retained export groups."""
    label = "workload-documentdb-observability-inputs"
    group = _inputs(desired, "user-service-documentdb-parameters")
    parameters = group.get("parameters")
    require(
        group.get("name") == f"{DOCUMENTDB_CLUSTER}-params"
        and group.get("family") == "docdb5.0"
        and type(parameters) is list
        and all(type(row) is dict for row in parameters)
        and unchanged._same(
            sorted(parameters, key=lambda row: str(row.get("name"))),
            DOCUMENTDB_PARAMETERS,
        ),
        label,
    )
    for export in ("audit", "profiler"):
        logs = _inputs(desired, f"user-service-documentdb-{export}-logs")
        require(
            logs.get("name") == f"/aws/docdb/{DOCUMENTDB_CLUSTER}/{export}"
            and unchanged._same(logs.get("retentionInDays"), 30),
            label,
        )


def _encrypted_queue_inputs(desired):
    """Require the fixed six queues to use AWS-managed SQS encryption."""
    for logical, physical in QUEUE_NAMES.items():
        inputs = _inputs(desired, f"user-service-{logical}")
        require(
            inputs.get("name") == physical
            and unchanged._same(
                {
                    key: inputs.get(key)
                    for key in (
                        "kmsMasterKeyId",
                        "receiveWaitTimeSeconds",
                        "visibilityTimeoutSeconds",
                    )
                },
                {
                    "kmsMasterKeyId": "alias/aws/sqs",
                    "receiveWaitTimeSeconds": 20,
                    "visibilityTimeoutSeconds": 120,
                },
            ),
            "workload-encrypted-queue-inputs",
        )


def _fargate_service_inputs(desired):
    """Require private, noninteractive Fargate services with rollback enabled."""
    for kind in ("web", "worker"):
        inputs = _inputs(desired, f"user-service-{kind}-service")
        require(
            inputs.get("launchType") == "FARGATE"
            and type(inputs.get("desiredCount")) is int
            and inputs["desiredCount"] > 0
            and inputs.get("enableExecuteCommand") is False,
            "workload-private-fargate-service-inputs",
        )
        _fargate_breaker(inputs.get("deploymentCircuitBreaker"))
        _fargate_network(inputs.get("networkConfiguration"))


def _fargate_breaker(breaker):
    require(
        type(breaker) is dict
        and set(breaker) == {"enable", "rollback"}
        and breaker["enable"] is True
        and breaker["rollback"] is True,
        "workload-private-fargate-service-inputs",
    )


def _fargate_network(network):
    label = "workload-private-fargate-service-inputs"
    require(type(network) is dict and network.get("assignPublicIp") is False, label)
    for field, count in (("securityGroups", 1), ("subnets", 2)):
        values = network.get(field)
        require(type(values) is list and len(values) == count, label)


def _task_execution_inputs(resource, projection):
    """Bind known task inputs even when matching plan/preview bytes were changed.

    Container definitions are checked separately after assembling the full graph.
    """
    if resource["type"] != "aws:ecs/taskDefinition:TaskDefinition":
        return
    central = projection.contract["workload"]["central"]
    expected = {
        "executionRoleArn": central["execution_role_arn"],
        "taskRoleArn": central["task_role_arn"],
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "runtimePlatform": {
            "cpuArchitecture": "X86_64",
            "operatingSystemFamily": "LINUX",
        },
    }
    require(
        unchanged._same(
            {key: resource["inputs"].get(key) for key in expected}, expected
        ),
        "workload-task-execution-inputs",
    )


def _task_container_inputs(desired, projection):
    """Check resolved definitions; the unknown sentinel never grants admission."""
    for kind in ("web", "worker"):
        inputs = _inputs(desired, f"user-service-{kind}-task")
        require(
            set(inputs)
            <= {
                "cpu",
                "memory",
                "family",
                "tags",
                "executionRoleArn",
                "taskRoleArn",
                "networkMode",
                "requiresCompatibilities",
                "runtimePlatform",
                "containerDefinitions",
            }
            and inputs.get("family") == f"{registry.PROJECT}-test-{kind}",
            "workload-task-definition-inputs",
        )
        for field in ("cpu", "memory"):
            # Exact capacity is baseline configuration, absent from this projection.
            require(
                type(inputs.get(field)) is str
                and re.fullmatch(r"[1-9][0-9]{0,5}", inputs[field]),
                "workload-task-capacity-inputs",
            )
        raw = inputs.get("containerDefinitions")
        _container_dependencies(desired, kind)
        if raw == registry.UNKNOWN:
            # Output.all(...).apply(json.dumps) is unresolved as a whole when
            # a first-create queue URL, log name or secret version is unknown.
            # The unconditional terminal stop requires later resolved binding.
            continue
        container = _container_json(raw)
        _container_runtime(container, kind, desired, projection)
        _container_environment(container["environment"], kind, projection)
        _container_secrets(container["secrets"], projection)


def _container_dependencies(desired, kind):
    names = {urn.rsplit("::", 1)[-1]: urn for urn in desired}
    targets = {f"user-service-{kind}-logs"}
    for purpose in set(CONTAINER_SECRET_NAMES.values()):
        targets.update((f"runtime-{purpose}", f"runtime-{purpose}-version"))
    dependencies = desired[names[f"user-service-{kind}-task"]].get("dependencies")
    require(
        type(dependencies) is list
        and {names[name] for name in targets} <= set(dependencies),
        "workload-task-container-dependencies",
    )


def _container_json(raw):
    label = "workload-task-container-json"
    require(type(raw) is str and 0 < len(raw.encode()) <= 65536, label)
    try:
        containers = json.loads(
            raw,
            object_pairs_hook=poc_contract._pairs,
            parse_constant=poc_contract._reject_nonfinite,
        )
    except (ValueError, RecursionError):
        raise ValueError(label) from None
    require(
        type(containers) is list
        and len(containers) == 1
        and type(containers[0]) is dict,
        label,
    )
    return containers[0]


def _container_runtime(container, kind, desired, projection):
    expected = {
        "name": f"user-service-{kind}",
        "image": projection.images[kind]["uri"],
        "essential": True,
        "command": _container_command(kind),
        "portMappings": [],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": f"/aws/ecs/{registry.PROJECT}-test/{kind}",
                "awslogs-region": projection.contract["region"],
                "awslogs-stream-prefix": f"user-service-{kind}",
            },
        },
    }
    if kind == "web":
        port = _inputs(desired, "user-service-target-group")["port"]
        expected["portMappings"] = [
            {"containerPort": port, "hostPort": port, "protocol": "tcp"}
        ]
    else:
        expected["healthCheck"] = {
            "command": [
                "CMD",
                *projection.contract["workload"]["runtime"]["worker_health_command"],
            ],
            "interval": 30,
            "timeout": 5,
            "retries": 3,
            "startPeriod": 60,
        }
    require(
        set(container) == set(expected) | {"environment", "secrets"}
        and unchanged._same({key: container.get(key) for key in expected}, expected),
        "workload-task-container-runtime",
    )


def _container_command(kind):
    runtime = {
        "web": "frankenphp run --config /etc/caddy/Caddyfile",
        "worker": "/usr/bin/supervisord -c /etc/supervisor/supervisord.conf",
    }[kind]
    bootstrap = (
        "set -eu; install -d -m 700 /srv/app/var/run/secrets; "
        'printf "%s" "$OAUTH_PRIVATE_KEY_PEM"'
        " > /srv/app/var/run/secrets/oauth-private.pem; "
        'printf "%s" "$OAUTH_PUBLIC_KEY_PEM"'
        " > /srv/app/var/run/secrets/oauth-public.pem; "
        "chmod 600 /srv/app/var/run/secrets/oauth-private.pem; "
        "chmod 644 /srv/app/var/run/secrets/oauth-public.pem; "
        f"exec {runtime}"
    )
    return ["/bin/sh", "-ec", bootstrap]


def _container_named_values(rows, field, label):
    require(type(rows) is list, label)
    result = {}
    for row in rows:
        require(type(row) is dict and set(row) == {"name", field}, label)
        name, value = row["name"], row[field]
        require(
            type(name) is str
            and name not in result
            and type(value) is str
            and 0 < len(value) <= 4096
            and registry.UNKNOWN not in value,
            label,
        )
        result[name] = value
    return result


def _container_environment(rows, kind, projection):
    label = "workload-task-container-environment"
    actual = _container_named_values(rows, "value", label)
    workload = projection.contract["workload"]
    region = projection.contract["region"]
    url = "https://" + workload["external"]["domain"]["fqdn"]
    expected = {
        "APP_ENV": "prod",
        "APP_DEBUG": "0",
        "API_BASE_URL": url,
        "API_URL": url,
        "CORS_ALLOW_ORIGIN": "^" + re.escape(url) + "$",
        "MAIL_SENDER": workload["external"]["mail"]["sender"],
        "MAILER_DSN": f"ses+api://default?region={region}",
        "JWT_ISSUER": "vilnacrm-user-service",
        "JWT_AUDIENCE": "vilnacrm-api",
        "AWS_EMF_NAMESPACE": "UserService/BusinessMetrics",
        "SOCIAL_OAUTH_ENABLED": "false",
        "OAUTH_ENCRYPTION_KEY_TYPE": "plain",
        "AWS_SQS_VERSION": "latest",
        "AWS_SQS_REGION": region,
        "AWS_SQS_ENDPOINT_BASE": f"https://sqs.{region}.amazonaws.com",
        "LOCALSTACK_PORT": "443",
        "OAUTH_PRIVATE_KEY": "/srv/app/var/run/secrets/oauth-private.pem",
        "OAUTH_PUBLIC_KEY": "/srv/app/var/run/secrets/oauth-public.pem",
    }
    if kind == "web":
        cidrs = workload["runtime"]["trusted_proxy_cidrs"]
        expected.update(
            TRUSTED_PROXIES=",".join(cidrs), TRUSTED_PROXY_CIDRS=" ".join(cidrs)
        )
    else:
        expected["MESSENGER_CONSUMER_NAME"] = f"{registry.PROJECT}-test-worker-consumer"
    # Native queue identity and effective policy still need post-apply observation.
    require(
        set(actual) == set(expected) | set(QUEUE_ENVIRONMENT_NAMES)
        and {key: actual[key] for key in expected} == expected,
        label,
    )
    for name, logical in QUEUE_ENVIRONMENT_NAMES.items():
        require(
            actual[name]
            == (
                f"https://sqs.{region}.amazonaws.com/"
                f"{projection.contract['account_id']}/{QUEUE_NAMES[logical]}"
                f"?region={region}&auto_setup=false"
            ),
            label,
        )


def _container_secrets(rows, projection):
    label = "workload-task-container-secrets"
    actual = _container_named_values(rows, "valueFrom", label)
    require(actual.keys() == CONTAINER_SECRET_NAMES.keys(), label)
    contract = projection.contract
    references = contract["workload"]["secret_lifecycle"]["references"]
    prefix = (
        f"arn:aws:secretsmanager:{contract['region']}:{contract['account_id']}:secret:"
    )
    for name, purpose in CONTAINER_SECRET_NAMES.items():
        # Namespace and version pin are checkable; the actual suffix/version must
        # still be bound to authenticated accepted native secret observations.
        pattern = re.escape(prefix + references[purpose]["name"])
        require(
            re.fullmatch(
                pattern + r"-[A-Za-z0-9]{6}:::[A-Za-z0-9-]{32,64}", actual[name]
            ),
            label,
        )
    require(actual["REDIS_URL"] == actual["REDIS_LOCKOUT_URL"], label)


def _validate_workload_steps(steps, baseline, graph, desired):
    seen = set()
    for step in steps:
        urn = step["urn"]
        _check(urn in graph and urn not in seen)
        seen.add(urn)
        if urn in baseline:
            continue
        _validate_workload_step(step, urn, graph, desired)
    return seen


def _validate_workload_step(step, urn, graph, desired):
    _check(step["op"] == "create" and step.get("oldState") is None)
    new = step["newState"]
    registry._object(new, {"urn", "type", "custom"}, registry.STATE_FIELDS)
    _check(not any(new.get(key) for key in unchanged.UNSAFE_STATE if key != "aliases"))
    aliases = new.get("aliases", [])
    expected_aliases = state_aliases(urn, graph[urn][0])
    _check(not aliases or aliases == expected_aliases)
    _check(new.get("id", "") in ("", registry.UNKNOWN))
    for field in (
        "urn",
        "type",
        "custom",
        "parent",
        "provider",
        "protect",
        "dependencies",
        "propertyDependencies",
        "additionalSecretOutputs",
    ):
        default = unchanged.GOAL_DEFAULTS.get(field, "")
        _check(
            unchanged._same(new.get(field, default), desired[urn].get(field, default))
        )
    _check(
        unchanged._same(
            new.get("inputs", {}), unchanged._redacted(desired[urn]["inputs"])
        )
    )
    _check(
        not any(
            step.get(key) for key in ("detailedDiff", "diffReasons", "replaceReasons")
        )
    )


def _baseline_steps(preview, prior):
    """Restore only omitted native component outputs from the checked prior.

    The registry validator still requires empty saved-goal output diffs and exact
    prior/goal ownership and inputs. An explicitly different output map rejects.
    """
    result = []
    for step in preview["steps"]:
        if step.get("urn") not in prior:
            continue
        old = prior[step["urn"]]
        new = step["newState"]
        if (
            old["type"] in (registry.STACK, registry.ENVIRONMENT)
            and "outputs" not in new
        ):
            step = {**step, "newState": {**new, "outputs": old["outputs"]}}
        result.append(step)
    return result


def admit_first_workload_plan(*args, **kwargs):
    """Admit a validated first-create preview and saved plan for TEST apply."""
    validate_first_workload_topology(*args, **kwargs)
