"""First-workload topology prerequisite, not complete input or IAM admission.

Only the installed two-AZ ECS/Fargate composition and its task execution identity,
network mode and platform are covered. Unknown computed inputs still need semantic
validation. No capability object or caller boolean can turn this source-only
validator into execution authority.
"""

import base64

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
        "documentdb-cluster": "docdb/cluster:Cluster",
        "documentdb-instance-1": "docdb/clusterInstance:ClusterInstance",
        "documentdb-instance-2": "docdb/clusterInstance:ClusterInstance",
        "redis-subnets": "elasticache/subnetGroup:SubnetGroup",
        "redis": "elasticache/replicationGroup:ReplicationGroup",
    }.items():
        add(f"user-service-{name}", f"aws:{kind}", planes["data"])
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
    _private_gateway_inputs(desired, projection)
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
        and listener.get("certificateArn") == workload_certificate_arn(projection),
        "workload-https-listener-inputs",
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

    Container definitions can be unknown in the first native preview. This check
    does not authenticate images, commands, secrets or the remaining task inputs.
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
    """Keep execution closed until native capability and input gates are installed."""
    validate_first_workload_topology(*args, **kwargs)
    raise ValueError("workload-native-capability-and-input-admission-required")
