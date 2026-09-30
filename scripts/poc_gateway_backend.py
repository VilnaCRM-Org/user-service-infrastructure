"""Project nonsecret gateway coordinates from authenticated workload state.

This function validates correspondence, not authenticity. Its future trusted
result observer must authenticate the accepted workload receipt and fresh native
checkpoint before calling it. Never publish a descriptor from preview values.
"""

import re

import poc_workload_reconciliation as state
import poc_workload_topology as topology
from poc_workload_phase_entrypoint import _checked, workload_certificate_arn
from service_execution_process import require


def _check(condition):
    require(condition, "workload-gateway-backend")


def _physical(row, prefix):
    identifier = row.get("id")
    _check(
        type(identifier) is str
        and re.fullmatch(rf"{prefix}-[0-9a-f]{{8}}(?:[0-9a-f]{{9}})?", identifier)
        and row["outputs"].get("id") == identifier
    )
    return identifier


def _pair(row, key, expected):
    _check(
        state._same(row["inputs"].get(key), expected)
        and state._same(row["outputs"].get(key), expected)
    )


def project_gateway_backend(projection, resources):
    """Return a versioned HTTP API VPC-link target, never a deployment receipt."""
    projection = _checked(projection)
    inventory = state._inventory(resources)
    graph = topology.expected_graph()
    _check(inventory.keys() == graph.keys())
    for urn, row in inventory.items():
        _check(
            state._same(
                [
                    row["type"],
                    row.get("parent", ""),
                    row["custom"],
                    row.get("protect", False),
                ],
                list(graph[urn]),
            )
        )
    rows = {urn.rsplit("::", 1)[-1]: row for urn, row in inventory.items()}
    vpc = _physical(rows["user-service-vpc"], "vpc")
    subnets = []
    for index in (1, 2):
        subnet = rows[f"user-service-app-subnet-{index}"]
        _pair(subnet, "vpcId", vpc)
        _pair(subnet, "mapPublicIpOnLaunch", False)
        subnets.append(_physical(subnet, "subnet"))
    _check(len(set(subnets)) == 2)
    security_group = rows["user-service-alb-sg"]
    _pair(security_group, "vpcId", vpc)
    group = _physical(security_group, "sg")
    link = rows["user-service-vpc-link-sg"]
    _pair(link, "vpcId", vpc)
    link_group = _physical(link, "sg")
    _check(link_group != group)
    _pair(link, "ingress", [])
    for section in ("inputs", "outputs"):
        _gateway_ingress(security_group[section].get("ingress"), link_group)
    listener_arn = _listener(rows, projection, vpc, group, subnets)
    return {
        "schema_version": "poc-api-gateway-backend/v1",
        "account_id": projection.contract["account_id"],
        "region": projection.contract["region"],
        "integration_type": "HTTP_PROXY",
        "connection_type": "VPC_LINK",
        "listener_arn": listener_arn,
        "vpc_id": vpc,
        "subnet_ids": subnets,
        "alb_security_group_id": group,
        "vpc_link_security_group_id": link_group,
        "tls_server_name": projection.contract["workload"]["external"]["domain"][
            "fqdn"
        ],
        "certificate_arn": workload_certificate_arn(projection),
        "request_parameters": {"overwrite:path": "$request.path"},
    }


def _gateway_ingress(rules, group):
    _check(type(rules) is list and len(rules) == 1 and type(rules[0]) is dict)
    rule = rules[0]
    expected = {
        "protocol": "tcp",
        "fromPort": 443,
        "toPort": 443,
        "securityGroups": [group],
    }
    defaults = {
        "cidrBlocks": [],
        "ipv6CidrBlocks": [],
        "prefixListIds": [],
        "self": False,
        "description": "",
    }
    _check(set(rule) <= set(expected) | set(defaults))
    _check(all(state._same(rule.get(key), value) for key, value in expected.items()))
    _check(
        all(state._same(rule.get(key, value), value) for key, value in defaults.items())
    )


def _listener(rows, projection, vpc, group, subnets):
    contract = projection.contract
    prefix = (
        f"arn:aws:elasticloadbalancing:{contract['region']}:{contract['account_id']}:"
    )
    alb = rows["user-service-alb"]
    arn = alb.get("id")
    _check(
        type(arn) is str
        and re.fullmatch(
            re.escape(prefix) + r"loadbalancer/app/[a-zA-Z0-9-]{1,32}/[0-9a-f]{16}", arn
        )
        and alb["outputs"].get("arn") == arn
        and alb["outputs"].get("vpcId") == vpc
    )
    _pair(alb, "internal", True)
    _pair(alb, "subnets", subnets)
    _pair(alb, "loadBalancerType", "application")
    _pair(alb, "securityGroups", [group])
    listener = rows["user-service-https-listener"]
    identifier = listener.get("id")
    listener_prefix = prefix + "listener/" + arn.split("loadbalancer/", 1)[1] + "/"
    _check(
        type(identifier) is str
        and re.fullmatch(re.escape(listener_prefix) + r"[0-9a-f]{16}", identifier)
        and listener["outputs"].get("arn") == identifier
    )
    _pair(listener, "loadBalancerArn", arn)
    _pair(listener, "protocol", "HTTPS")
    _pair(listener, "port", 443)
    _pair(
        listener,
        "certificateArn",
        workload_certificate_arn(projection),
    )
    return identifier
