"""S1.8: consume the KMS JWT and 2FA keys; drop the PEM purposes (FR-06).

AD-03 cuts the hardened declared purposes to ``app_secret`` and
``oauth_encryption_key``; ``oauth_private_key``, ``oauth_public_key``,
``oauth_passphrase`` (D-5: retired, never rotated) and
``two_factor_encryption_key`` leave the contract. AD-15 passes the key ARNs as
plain environment values ``JWT_KMS_KEY_ID``, ``JWT_KMS_PREVIOUS_KEY_ID`` (D-17,
empty outside a key change), ``TWO_FACTOR_KMS_KEY_ID`` and ``AWS_REGION``. D-4
puts the runtime CMK on the ECS web and worker log groups and on a
pre-created Container Insights performance group the cluster depends on.
Every oracle is a literal from the PRD, architecture or synthetic fixture.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from app import workload_phase
from poc_contract import _validate_document
from test_poc_contract import change
from test_poc_contract_hardened import hardened
from test_poc_workload_phase import graph

TASK = "aws:ecs/taskDefinition:TaskDefinition"
LOG_GROUP = "aws:cloudwatch/logGroup:LogGroup"
CLUSTER = "aws:ecs/cluster:Cluster"
RUNTIME_CMK = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000010"
)
JWT_KEY = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000011"
)
TWO_FACTOR_KEY = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000012"
)
JWT_PREVIOUS_KEY = (
    "arn:aws:kms:eu-central-1:891377212104:key/00000000-0000-4000-8000-000000000013"
)
# Purposes and value kinds are listed apart, so no line pairs a purpose name
# with its value kind (that shape trips the gitleaks generic-api-key rule).
RETIRED_PURPOSE_NAMES = (
    "oauth_private_key",
    "oauth_public_key",
    "oauth_passphrase",
    "two_factor_encryption_key",
)
RETIRED_VALUE_KINDS = (
    "rsa-4096-private-pem",
    "rsa-4096-public-pem",
    "hex-256",
    "base64-256",
)
RETIRED = tuple(zip(RETIRED_PURPOSE_NAMES, RETIRED_VALUE_KINDS, strict=True))
RETIRED_NAMES = (
    "OAUTH_PRIVATE_KEY",
    "OAUTH_PUBLIC_KEY",
    "OAUTH_PRIVATE_KEY_PEM",
    "OAUTH_PUBLIC_KEY_PEM",
    "OAUTH_PASSPHRASE",
    "TWO_FACTOR_ENCRYPTION_KEY",
)


@pytest.fixture(scope="module")
def render(tmp_path_factory):
    cache = {}

    def get(mutation):
        if mutation not in cache:
            receipt = graph(tmp_path_factory.mktemp("kms"), "hardened", mutation)
            assert receipt["error"] is None
            cache[mutation] = receipt
        return cache[mutation]

    return get


def _containers(rows):
    return {
        container["name"]: container
        for row in rows.values()
        if row["type"] == TASK
        for container in json.loads(row["inputs"]["containerDefinitions"])
    }


def _environment(container):
    return {item["name"]: item["value"] for item in container["environment"]}


# The contract (N, B).


def _retired_entry(contract, purpose, value_kind):
    entry = dict(contract["workload"]["secret_lifecycle"]["references"]["app_secret"])
    entry.update(
        name=f"/user-service-infrastructure/runtime/test/synthetic-{purpose}",
        value_kind=value_kind,
        rotation="non_rotatable",
    )
    return entry


def test_the_hardened_contract_declares_exactly_the_two_rotated_purposes():
    contract = hardened()
    _validate_document(contract)
    assert set(contract["workload"]["secret_lifecycle"]["references"]) == {
        "app_secret",
        "oauth_encryption_key",
    }


@pytest.mark.parametrize(("purpose", "value_kind"), RETIRED)
def test_n_readding_a_pem_passphrase_or_2fa_purpose_fails_the_schema(
    purpose, value_kind
):
    contract = hardened()
    change(
        contract,
        f"workload.secret_lifecycle.references.{purpose}",
        _retired_entry(contract, purpose, value_kind),
    )
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


@pytest.mark.parametrize(("purpose", "value_kind"), RETIRED)
def test_b_gate_one_is_refused_while_a_non_rotatable_purpose_exists(
    purpose, value_kind
):
    """FR-31 gate 1 (``admission.test``) admits no ``non_rotatable`` purpose."""
    contract = hardened()
    contract["admission"] = {"test": True, "prod": False}
    _validate_document(contract)
    change(
        contract,
        f"workload.secret_lifecycle.references.{purpose}",
        _retired_entry(contract, purpose, value_kind),
    )
    with pytest.raises(ValueError, match="poc-test-v1 schema"):
        _validate_document(contract)


# The rendered task definitions (P, FR-06).


@pytest.mark.parametrize("service", ["user-service-web", "user-service-worker"])
def test_p_the_bootstrap_command_writes_no_pem(render, service):
    container = _containers(render("none")["registrations"])[service]
    shell, flag, command = container["command"]
    assert (shell, flag) == ("/bin/sh", "-ec")
    for marker in ("PEM", "pem", "printf", "/srv/app/var/run/secrets", "chmod"):
        assert marker not in command
    assert command.startswith("set -eu; install -d -m 1777 ")
    assert command.split("; ")[-1].startswith("exec ")


@pytest.mark.parametrize("service", ["user-service-web", "user-service-worker"])
def test_the_kms_key_ids_are_plain_environment_values(render, service):
    container = _containers(render("none")["registrations"])[service]
    environment = _environment(container)
    assert environment["JWT_KMS_KEY_ID"] == JWT_KEY
    assert environment["JWT_KMS_PREVIOUS_KEY_ID"] == ""
    assert environment["TWO_FACTOR_KMS_KEY_ID"] == TWO_FACTOR_KEY
    assert environment["AWS_REGION"] == "eu-central-1"
    names = set(environment) | {item["name"] for item in container["secrets"]}
    assert not names & set(RETIRED_NAMES)
    assert {item["name"] for item in container["secrets"]} == {
        "APP_SECRET",
        "OAUTH_ENCRYPTION_KEY",
    }


def test_a_jwt_key_change_window_passes_the_verify_only_key(render):
    """D-17: ``cmk.jwt_previous`` reaches ``JWT_KMS_PREVIOUS_KEY_ID``."""
    containers = _containers(render("jwt-previous")["registrations"])
    for container in containers.values():
        environment = _environment(container)
        assert environment["JWT_KMS_PREVIOUS_KEY_ID"] == JWT_PREVIOUS_KEY
        assert environment["JWT_KMS_KEY_ID"] == JWT_KEY


# The log groups (D-4, FR-10).


def test_the_ecs_log_groups_use_the_runtime_cmk(render):
    rows = render("none")["registrations"]
    groups = {
        row["inputs"]["name"]: row for row in rows.values() if row["type"] == LOG_GROUP
    }
    ecs = {name: row for name, row in groups.items() if name.startswith("/aws/ecs/")}
    cluster = next(row for row in rows.values() if row["type"] == CLUSTER)
    insights = f"/aws/ecs/containerinsights/{cluster['inputs']['name']}/performance"
    assert insights in ecs
    assert len(ecs) == 3
    for row in ecs.values():
        assert row["inputs"]["kmsKeyId"] == RUNTIME_CMK
        assert row["inputs"]["retentionInDays"] == 30
    assert cluster["inputs"]["settings"] == [
        {"name": "containerInsights", "value": "enhanced"}
    ]
    assert ecs[insights]["urn"] in cluster["dependencies"]


def _group(name, key):
    props = {"name": name}
    if key is not None:
        props["kmsKeyId"] = key
    return props


@pytest.mark.parametrize(
    "name",
    [
        "/aws/ecs/user-service-infrastructure-test/web",
        "/aws/ecs/containerinsights/fixture/performance",
    ],
)
def test_an_ecs_log_group_without_the_runtime_cmk_fails_the_guard(name):
    check = workload_phase.HARDENED_PROPERTY_CHECKS[LOG_GROUP]
    assert check(_group(name, RUNTIME_CMK), False, runtime_cmk=RUNTIME_CMK)
    assert not check(_group(name, None), False, runtime_cmk=RUNTIME_CMK)
    assert not check(_group(name, JWT_KEY), False, runtime_cmk=RUNTIME_CMK)
    assert not check(_group(name, RUNTIME_CMK), False)
