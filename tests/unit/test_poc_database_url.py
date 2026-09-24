"""Exercise declared database settings using only synthetic credentials and mocks."""

import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from app.data import _documentdb_url
from app.runtime_secrets import RuntimeSecretsDescriptor
from test_poc_workload_phase import graph

ROOT = Path(__file__).parents[2]


@pytest.fixture
def contract(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return json.loads(
        (ROOT / "tests/fixtures/poc-contract/workload.synthetic.json").read_text()
    )


def test_descriptor_fields_are_detached_from_caller(contract):
    descriptor = RuntimeSecretsDescriptor(contract)
    runtime = dict(contract["workload"]["runtime"])
    account = contract["account_id"]
    contract["workload"]["runtime"] = {}
    contract["account_id"] = "changed"
    command = descriptor.worker_health_command
    command.clear()
    assert descriptor.database_name == runtime["database_name"]
    assert descriptor.ca_bundle_path == runtime["ca_bundle_path"]
    assert descriptor.worker_health_command == runtime["worker_health_command"]
    assert descriptor.account_id == account


def test_declared_database_and_ca_keep_tls_and_admin_auth(contract):
    contract["workload"]["runtime"]["ca_bundle_path"] = "/opt/ca/test_bundle-1.pem"
    descriptor = RuntimeSecretsDescriptor(contract)
    url = _documentdb_url(
        "user@example.com",
        "synthetic:/?#@%password",
        "database.example",
        27017,
        descriptor,
    )
    parsed = urlsplit(url)
    assert parsed.scheme == "mongodb"
    assert parsed.hostname == "database.example"
    assert parsed.port == 27017
    assert unquote(parsed.username) == "user@example.com"
    assert unquote(parsed.password) == "synthetic:/?#@%password"
    assert parsed.path == "/user_service"
    assert parsed.fragment == ""
    assert parse_qs(parsed.query, strict_parsing=True) == {
        "tls": ["true"],
        "replicaSet": ["rs0"],
        "readPreference": ["secondaryPreferred"],
        "retryWrites": ["false"],
        "authSource": ["admin"],
        "tlsCAFile": [descriptor.ca_bundle_path],
    }
    assert "tlsCAFile=%2Fopt%2Fca%2Ftest_bundle-1.pem" in url


def test_legacy_url_preserves_existing_connection_options():
    assert _documentdb_url("u@x", "synthetic:/?#@p", "db.example", 27017) == (
        "mongodb://u%40x:synthetic%3A%2F%3F%23%40p@db.example:27017/"
        "?tls=true&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    )


def test_generated_graph_persists_declared_url_as_protected_secret(tmp_path, contract):
    rows = graph(tmp_path)["registrations"]
    version = rows["runtime-document_db_url-version"]
    secret = version["inputs"]["secretString"]
    assert (
        secret["4dabf18193072939515e22adb298388d"] == "1b47061264138c4ac30d75fd1eb44270"
    )
    parsed = urlsplit(secret["value"])
    runtime = contract["workload"]["runtime"]
    assert parsed.path == "/" + runtime["database_name"]
    query = parse_qs(parsed.query, strict_parsing=True)
    assert query["tlsCAFile"] == [runtime["ca_bundle_path"]]
    assert query["tls"] == ["true"]
    assert query["authSource"] == ["admin"]
    assert query["retryWrites"] == ["false"]
    assert version["protect"] is True
    assert "secretString" in version["additional_secret_outputs"]
    reference = contract["workload"]["secret_lifecycle"]["references"][
        "document_db_url"
    ]
    persisted = rows["runtime-document_db_url"]
    assert persisted["inputs"]["name"] == reference["name"]
    assert persisted["inputs"]["kmsKeyId"] == reference["kms_key_arn"]
    assert persisted["protect"] is True
