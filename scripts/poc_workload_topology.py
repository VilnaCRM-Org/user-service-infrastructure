"""First-workload topology prerequisite, not complete input or IAM admission.

Only the installed two-AZ ECS/Fargate composition is covered. Unknown computed
inputs still need semantic validation. No capability object or caller boolean can
turn this source-only validator into execution authority.
"""

import base64

import poc_registry_plan as registry
import poc_workload_reconciliation as unchanged
from poc_registry_phase_entrypoint import RegistryPhaseProjection
from poc_workload_phase_entrypoint import _checked
from service_execution_process import require

SECRET_VERSION_OUTPUTS = [
    "secretString",
    "secretBinary",
    "secretString",
    "secretStringWo",
]
SDK_ALIASES = {
    f"aws:lb/{kind}": f"aws:elasticloadbalancingv2/{kind}"
    for kind in (
        "listener:Listener",
        "loadBalancer:LoadBalancer",
        "targetGroup:TargetGroup",
    )
}
SDK_ALIASES.update(
    {
        token: token
        for token in (
            f"aws:s3/{kind[0].lower() + kind[1:]}:{kind}"
            for kind in (
                "BucketLifecycleConfigurationV2",
                "BucketServerSideEncryptionConfigurationV2",
                "BucketVersioningV2",
            )
        )
    }
)


def _sdk_aliases(kind):
    if kind not in SDK_ALIASES:
        return []
    return [
        {
            "URN": "",
            "Name": "",
            "Type": SDK_ALIASES[kind],
            "Project": "",
            "Stack": "",
            "Parent": "",
            "NoParent": False,
        }
    ]


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
    for purpose in ("alb", "service", "documentdb", "redis"):
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
        "http-listener": "lb/listener:Listener",
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
    package = kind.split(":", 1)[0]
    expected = ""
    if package in ("aws", "random", "tls"):
        provider = (
            registry.PROVIDER_URN
            if package == "aws"
            else next(
                key
                for key, row in graph.items()
                if row[0] == f"pulumi:providers:{package}"
            )
        )
        expected = (
            provider + "::" + (provider_id if package == "aws" else registry.UNKNOWN)
        )
    _check(goal.get("provider", "") == expected)
    if kind == "aws:secretsmanager/secretVersion:SecretVersion":
        _check(set(inputs) == {"secretId", "secretString"})
        _check(goal.get("additionalSecretOutputs") == SECRET_VERSION_OUTPUTS)
        # Pulumi serializes an unresolved secret as the exact unknown sentinel.
        # This is only a topology allowance, never approval of its future value.
        if inputs["secretString"] != registry.UNKNOWN:
            unchanged._secret_inputs(state)
    unchanged._redacted(inputs)
    return state


def validate_first_workload_topology(
    preview, *, saved_plan, prior_resources, projection
):
    """Check exact registry-to-workload owners and operations; never grant apply."""
    _checked(projection)
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
    # All references must remain inside the complete finite owner graph.
    for row in desired.values():
        references = {key: value for key, value in row.items() if key != "provider"}
        unchanged._references(references, desired)
    seen = set()
    for step in preview["steps"]:
        urn = step["urn"]
        _check(urn in graph and urn not in seen)
        seen.add(urn)
        if urn in baseline:
            continue
        _check(step["op"] == "create" and step.get("oldState") is None)
        new = step["newState"]
        registry._object(new, {"urn", "type", "custom"}, registry.STATE_FIELDS)
        _check(
            not any(new.get(key) for key in unchanged.UNSAFE_STATE if key != "aliases")
        )
        aliases = new.get("aliases", [])
        expected_aliases = (
            [urn.replace(graph[urn][0] + "::", SDK_ALIASES[graph[urn][0]] + "::")]
            if graph[urn][0] in SDK_ALIASES
            else []
        )
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
                unchanged._same(
                    new.get(field, default), desired[urn].get(field, default)
                )
            )
        _check(
            unchanged._same(
                new.get("inputs", {}), unchanged._redacted(desired[urn]["inputs"])
            )
        )
        _check(
            not any(
                step.get(key)
                for key in ("detailedDiff", "diffReasons", "replaceReasons")
            )
        )
    required = {
        urn
        for urn in graph.keys() - baseline.keys()
        if not graph[urn][0].startswith("pulumi:providers:")
    }
    _check(required <= seen)


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
