"""Exact proxy declarations and web-only serialization; no live subnet evidence."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from test_poc_contract import fixture
from test_poc_workload_phase import graph


@pytest.mark.parametrize(
    "cidrs",
    [
        None,
        [],
        "10.42.0.0/24",
        [""],
        ["private_ranges"],
        ["REMOTE_ADDR"],
        ["*"],
        ["0.0.0.0/0"],
        ["::/0"],
        ["fe80::%eth0/64"],
        ["10.42.0.1"],
        ["10.42.0.1/24"],
        ["10.42.0.0/255.255.255.0"],
        [" 10.42.0.0/24"],
        ["10.42.0.0/24\n"],
        ["10.42.0.0/24,10.42.1.0/24"],
        ["10.42.0.0/24", "10.42.0.0/24"],
        ["10.42.0.0/24", "10.42.0.0/25"],
        ["10.42.0.0/24"] * 17,
    ],
)
def test_invalid_trusted_proxy_declarations_fail_closed(cidrs):
    from poc_contract import _validate_document

    contract = fixture("workload")
    contract["workload"]["runtime"]["trusted_proxy_cidrs"] = cidrs
    with pytest.raises(ValueError):
        _validate_document(contract)


def test_trusted_proxy_declaration_is_required_and_digest_bound():
    from poc_contract import _validate_document, validate

    contract = fixture("workload")
    before = validate(contract, previous=fixture("registry"))
    contract["workload"]["runtime"]["trusted_proxy_cidrs"] = ["10.43.0.0/24"]
    assert validate(contract, previous=fixture("registry")) != before
    del contract["workload"]["runtime"]["trusted_proxy_cidrs"]
    with pytest.raises(ValueError, match="schema"):
        _validate_document(contract)


def test_canonical_ipv6_is_valid_without_expanding_trust():
    from poc_contract import _validate_document

    contract = fixture("workload")
    contract["workload"]["runtime"]["trusted_proxy_cidrs"] = [
        "10.42.0.0/24",
        "fd00::/64",
    ]
    _validate_document(contract)


def test_web_injects_same_exact_set_in_both_parser_formats(tmp_path):
    result = graph(tmp_path, "bridge")
    assert result["error"] is None
    rows = result["registrations"]
    web = json.loads(rows["user-service-web-task"]["inputs"]["containerDefinitions"])[0]
    environment = {item["name"]: item["value"] for item in web["environment"]}
    cidrs = fixture("workload")["workload"]["runtime"]["trusted_proxy_cidrs"]
    assert environment["TRUSTED_PROXIES"] == ",".join(cidrs)
    assert environment["TRUSTED_PROXY_CIDRS"] == " ".join(cidrs)
    registered_subnets = {
        rows[f"user-service-public-subnet-{index}"]["inputs"]["cidrBlock"]
        for index in (1, 2)
    }
    assert set(environment["TRUSTED_PROXIES"].split(",")) == registered_subnets
    assert set(environment["TRUSTED_PROXY_CIDRS"].split(" ")) == registered_subnets
    worker = json.loads(
        rows["user-service-worker-task"]["inputs"]["containerDefinitions"]
    )[0]
    assert not {"TRUSTED_PROXIES", "TRUSTED_PROXY_CIDRS"} & {
        item["name"] for item in worker["environment"]
    }


@pytest.mark.parametrize(
    "cidrs", [["10.42.0.0/16"], ["10.42.0.0/24"], ["10.42.2.0/24", "10.42.1.0/24"]]
)
def test_descriptor_rejects_broader_missing_or_foreign_subnets(cidrs):
    from app.runtime_secrets import RuntimeSecretsDescriptor

    contract = fixture("workload")
    contract["workload"]["runtime"]["trusted_proxy_cidrs"] = cidrs
    descriptor = RuntimeSecretsDescriptor(contract)
    settings = SimpleNamespace(
        network=SimpleNamespace(public_subnet_cidrs=("10.42.0.0/24", "10.42.1.0/24"))
    )
    with patch.object(descriptor, "validate_context"):
        with pytest.raises(ValueError, match="exactly match"):
            descriptor.validate_target(settings)


def test_descriptor_list_is_detached_and_legacy_has_no_implicit_trust():
    from app.compute import ComputePlane
    from app.runtime_secrets import RuntimeSecretsDescriptor

    descriptor = RuntimeSecretsDescriptor(fixture("workload"))
    descriptor.trusted_proxy_cidrs.append("10.42.2.0/24")
    assert descriptor.trusted_proxy_cidrs == ["10.42.0.0/24", "10.42.1.0/24"]
    assert object.__new__(ComputePlane)._trusted_proxy_environment() == []
