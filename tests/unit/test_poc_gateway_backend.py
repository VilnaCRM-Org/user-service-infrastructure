"""Gateway coordinates require matching native outputs, never guessed defaults."""

import copy
import importlib

import pytest
from test_poc_workload_child_entrypoint import projection

module = importlib.import_module("poc_gateway_backend")


@pytest.fixture
def data():
    value = projection()
    resources = []
    rows = {}
    for urn, (
        kind,
        parent,
        custom,
        protect,
    ) in module.topology.expected_graph().items():
        name = urn.rsplit("::", 1)[-1]
        row = {
            "urn": urn,
            "type": kind,
            "parent": parent,
            "custom": custom,
            "protect": protect,
            "id": name + "-id",
            "inputs": {},
            "outputs": {},
            "aliases": module.state.state_aliases(urn, kind),
        }
        rows[name] = row
        resources.append(row)

    def native(name, identifier, inputs):
        row = rows["user-service-" + name]
        row.update(id=identifier, inputs=copy.deepcopy(inputs))
        row["outputs"] = {**copy.deepcopy(inputs), "id": identifier}
        return row

    vpc = "vpc-" + "1" * 17
    native("vpc", vpc, {})
    for index in (1, 2):
        native(
            f"app-subnet-{index}",
            "subnet-" + str(index) * 17,
            {
                "vpcId": vpc,
                "mapPublicIpOnLaunch": False,
            },
        )
    group = "sg-" + "1" * 17
    link_group = "sg-" + "2" * 17
    native("vpc-link-sg", link_group, {"vpcId": vpc, "ingress": []})
    native(
        "alb-sg",
        group,
        {
            "vpcId": vpc,
            "ingress": [
                {
                    "protocol": "tcp",
                    "fromPort": 443,
                    "toPort": 443,
                    "securityGroups": [link_group],
                }
            ],
        },
    )
    prefix = "arn:aws:elasticloadbalancing:eu-central-1:891377212104:"
    alb_arn = prefix + "loadbalancer/app/service/" + "1" * 16
    alb = native(
        "alb",
        alb_arn,
        {
            "loadBalancerType": "application",
            "securityGroups": [group],
            "internal": True,
            "subnets": ["subnet-" + str(index) * 17 for index in (1, 2)],
        },
    )
    alb["outputs"].update(arn=alb_arn, vpcId=vpc)
    listener_arn = prefix + "listener/app/service/" + "1" * 16 + "/" + "2" * 16
    listener = native(
        "https-listener",
        listener_arn,
        {
            "loadBalancerArn": alb_arn,
            "protocol": "HTTPS",
            "port": 443,
            "certificateArn": value.contract["workload"]["external"]["domain"][
                "certificate_arn"
            ],
        },
    )
    listener["outputs"]["arn"] = listener_arn
    return value, resources, rows


def test_projects_exact_nonsecret_closed_coordinates_without_mutating_state(data):
    value, resources, rows = data
    before = copy.deepcopy(resources)
    result = module.project_gateway_backend(value, resources)
    assert result == {
        "schema_version": "poc-api-gateway-backend/v1",
        "account_id": "891377212104",
        "region": "eu-central-1",
        "integration_type": "HTTP_PROXY",
        "connection_type": "VPC_LINK",
        "listener_arn": rows["user-service-https-listener"]["id"],
        "vpc_id": "vpc-" + "1" * 17,
        "subnet_ids": ["subnet-" + str(index) * 17 for index in (1, 2)],
        "alb_security_group_id": "sg-" + "1" * 17,
        "vpc_link_security_group_id": "sg-" + "2" * 17,
        "tls_server_name": value.contract["workload"]["external"]["domain"]["fqdn"],
        "certificate_arn": value.contract["workload"]["external"]["domain"][
            "certificate_arn"
        ],
        "request_parameters": {"overwrite:path": "$request.path"},
    }
    assert resources == before


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("https-listener", "arn", "foreign"),
        ("https-listener", "loadBalancerArn", "foreign"),
        ("https-listener", "certificateArn", "foreign"),
        ("https-listener", "protocol", "HTTP"),
        ("https-listener", "port", True),
        ("app-subnet-1", "vpcId", "vpc-" + "9" * 17),
        ("app-subnet-1", "mapPublicIpOnLaunch", True),
        ("alb-sg", "vpcId", "vpc-" + "9" * 17),
        ("alb", "vpcId", "vpc-" + "9" * 17),
        ("vpc-link-sg", "vpcId", "vpc-" + "9" * 17),
        ("vpc-link-sg", "ingress", [{"protocol": "-1"}]),
        ("alb", "internal", False),
        ("alb", "subnets", ["subnet-" + "9" * 17]),
        ("alb", "loadBalancerType", "network"),
        ("alb", "securityGroups", ["sg-" + "9" * 17]),
        ("vpc", "id", "vpc-" + "9" * 17),
    ],
)
def test_mismatched_or_missing_native_values_reject(data, name, field, value):
    projection, resources, rows = data
    output = rows["user-service-" + name]["outputs"]
    original = output[field]
    output[field] = value
    with pytest.raises(ValueError, match="gateway-backend"):
        module.project_gateway_backend(projection, resources)
    output[field] = original
    del output[field]
    with pytest.raises(ValueError, match="gateway-backend"):
        module.project_gateway_backend(projection, resources)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "parent",
        "duplicate-subnets",
        "foreign-alb",
        "foreign-listener",
        "unknown-vpc",
    ],
)
def test_partial_graph_foreign_ids_and_unknown_coordinates_reject(data, mutation):
    projection, resources, rows = data
    if mutation == "missing":
        resources.remove(rows["user-service-app-subnet-1"])
    elif mutation == "extra":
        extra = copy.deepcopy(rows["user-service-vpc"])
        extra["urn"] += "-extra"
        resources.append(extra)
    elif mutation == "parent":
        rows["user-service-vpc"]["parent"] = module.state.ROOT
    else:
        name, identifier = {
            "duplicate-subnets": (
                "app-subnet-2",
                rows["user-service-app-subnet-1"]["id"],
            ),
            "foreign-alb": (
                "alb",
                rows["user-service-alb"]["id"].replace("891377212104", "933245420672"),
            ),
            "foreign-listener": (
                "https-listener",
                rows["user-service-https-listener"]["id"].replace(
                    "891377212104", "933245420672"
                ),
            ),
            "unknown-vpc": ("vpc", module.topology.registry.UNKNOWN),
        }[mutation]
        row = rows["user-service-" + name]
        row["id"] = identifier
        row["outputs"].update(id=identifier, arn=identifier)
    with pytest.raises(ValueError, match="gateway-backend"):
        module.project_gateway_backend(projection, resources)


@pytest.mark.parametrize(
    "rule",
    [
        None,
        [],
        [None],
        [{"protocol": "tcp"}],
        [{"protocol": "-1"}],
        [
            {
                "protocol": "tcp",
                "fromPort": 80,
                "toPort": 80,
                "cidrBlocks": ["0.0.0.0/0"],
            }
        ],
    ],
)
def test_direct_alb_access_rules_reject(data, rule):
    value, resources, rows = data
    for section in ("inputs", "outputs"):
        rows["user-service-alb-sg"][section]["ingress"] = rule
    with pytest.raises(ValueError, match="gateway-backend"):
        module.project_gateway_backend(value, resources)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cidrBlocks", ["0.0.0.0/0"]),
        ("ipv6CidrBlocks", ["::/0"]),
        ("self", True),
        ("securityGroups", ["sg-" + "9" * 17]),
        ("unknown", False),
    ],
)
def test_additional_ingress_sources_reject(data, field, value):
    projection, resources, rows = data
    for section in ("inputs", "outputs"):
        rows["user-service-alb-sg"][section]["ingress"][0][field] = value
    with pytest.raises(ValueError, match="gateway-backend"):
        module.project_gateway_backend(projection, resources)


def test_provider_empty_rule_defaults_are_accepted(data):
    projection, resources, rows = data
    rows["user-service-alb-sg"]["outputs"]["ingress"][0].update(
        cidrBlocks=[], ipv6CidrBlocks=[], prefixListIds=[], self=False, description=""
    )
    module.project_gateway_backend(projection, resources)


def test_link_group_cannot_be_alb_group(data):
    projection, resources, rows = data
    row = rows["user-service-vpc-link-sg"]
    row["id"] = row["outputs"]["id"] = rows["user-service-alb-sg"]["id"]
    with pytest.raises(ValueError, match="gateway-backend"):
        module.project_gateway_backend(projection, resources)
