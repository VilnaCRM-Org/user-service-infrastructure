"""Hardened task environment: plain IAM URL and credential-free DSNs (S1.3).

FR-02 (MONGODB_URL is a plain value), FR-03 and AD-20 (no DSN or environment
value carries a key or userinfo) and S1.7 F6 (bare-ARN ``valueFrom``).
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from app import compute as module
from app.compute import (
    INITIAL_SERVICE_SCALE,
    ComputePlane,
    require_credential_free,
    require_plain_environment,
)
from app.runtime_secrets import ENVIRONMENT_NAMES
from test_poc_workload_phase import graph

import pulumi

ROOT = Path(__file__).parents[2]
TASKS = ("user-service-web-task", "user-service-worker-task")
QUEUE_DSNS = (
    "SEND_EMAIL_TRANSPORT_DSN",
    "FAILED_EMAIL_TRANSPORT_DSN",
    "INSERT_USER_BATCH_TRANSPORT_DSN",
    "DOMAIN_EVENTS_TRANSPORT_DSN",
    "FAILED_DOMAIN_EVENTS_TRANSPORT_DSN",
)
ACCESS_KEY = "AKIA" + "SYNTHETIC0000000"
QUEUE = "https://sqs.eu-central-1.amazonaws.com/891377212104/send-email"


@pytest.fixture(autouse=True)
def trusted_script_path(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def hardened(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("compute-env"), "hardened")
    assert receipt["error"] is None
    return receipt


def _containers(receipt):
    rows = receipt["registrations"]
    return {
        task: json.loads(rows[task]["inputs"]["containerDefinitions"])[0]
        for task in TASKS
    }


def _environment(container):
    return {row["name"]: row["value"] for row in container["environment"]}


def test_mongodb_url_is_a_plain_environment_value_with_no_userinfo(hardened):
    """FR-02 P: the URL names the mechanism, source, TLS and CA."""
    for container in _containers(hardened).values():
        url = _environment(container)["MONGODB_URL"]
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.scheme == "mongodb" and "@" not in parts.netloc
        assert parts.path == "/user_service"
        assert query["authMechanism"] == ["MONGODB-AWS"]
        assert query["authSource"] == ["$external"]
        assert (query["tls"], query["tlsCAFile"]) == (["true"], ["/synthetic/ca.pem"])
        assert "MONGODB_URL" not in {row["name"] for row in container["secrets"]}


def test_hardened_graph_holds_no_url_secret(hardened):
    """S1.3 removes ``document_db_url``; Redis holds no secret either (D-1)."""
    rows = hardened["registrations"]
    names = {
        row["inputs"]["name"]
        for row in rows.values()
        if row["type"] == "aws:secretsmanager/secret:Secret"
    }
    assert not [name for name in names if name.endswith(("_url", "-url"))]
    for container in _containers(hardened).values():
        secret_names = {row["name"] for row in container["secrets"]}
        assert not secret_names & {"MONGODB_URL", "REDIS_URL", "REDIS_LOCKOUT_URL"}


def test_queue_and_mailer_dsns_are_credential_free_with_region(hardened):
    """FR-03 P and B: no userinfo, the region is present, ``auto_setup=false``."""
    for container in _containers(hardened).values():
        environment = _environment(container)
        for name in QUEUE_DSNS:
            parts = urlsplit(environment[name])
            query = parse_qs(parts.query)
            assert (parts.username, parts.password) == (None, None), name
            assert query == {"region": ["eu-central-1"], "auto_setup": ["false"]}
        mailer = urlsplit(environment["MAILER_DSN"])
        assert mailer.netloc == "default" and mailer.username is None
        assert parse_qs(mailer.query) == {"region": ["eu-central-1"]}
        assert not [
            value for value in environment.values() if re.search(r"A[KS]IA", value)
        ]


def test_secret_references_are_bare_arns_without_a_version(hardened):
    """S1.7 F6: rendered ``valueFrom`` is the declared ARN, never a version."""
    from poc_secret_observation import secret_arn_regex

    contract = json.loads(
        (
            ROOT / "tests/fixtures/poc-contract/workload-hardened.synthetic.json"
        ).read_text()
    )
    references = contract["workload"]["secret_lifecycle"]["references"]
    expected = {ENVIRONMENT_NAMES[purpose]: purpose for purpose in references}
    for container in _containers(hardened).values():
        rows = {row["name"]: row["valueFrom"] for row in container["secrets"]}
        assert set(rows) == set(expected)
        for name, reference in rows.items():
            pattern = secret_arn_regex(
                "eu-central-1", "891377212104", references[expected[name]]["name"]
            )
            assert re.fullmatch(pattern, reference), reference
            assert ":::" not in reference and "AWSCURRENT" not in reference
        assert not set(rows) & set(_environment(container))


def test_hardened_services_start_at_zero_tasks(hardened):
    """FR-34 step 1: both ECS services exist at ``initial_service_scale=0``."""
    rows = hardened["registrations"]
    services = [
        row for row in rows.values() if row["type"] == "aws:ecs/service:Service"
    ]
    assert len(services) == 2
    assert {row["inputs"]["desiredCount"] for row in services} == {
        INITIAL_SERVICE_SCALE
    }


class _Known:
    """Stand-in for a known Output: ``apply`` runs the callback at once.

    A real Output that fails inside ``apply`` would leave its error with the
    Pulumi runtime and fail an unrelated later program.
    """

    def __init__(self, value):
        self.value = value

    def apply(self, callback):
        return callback(self.value)


def test_the_queue_dsn_builder_keeps_the_dsn_credential_free(monkeypatch):
    monkeypatch.setattr(pulumi.Output, "from_input", _Known)
    compute = object.__new__(ComputePlane)
    assert compute._queue_dsn(QUEUE, "eu-central-1") == (
        f"{QUEUE}?region=eu-central-1&auto_setup=false"
    )
    with pytest.raises(ValueError, match="userinfo"):
        compute._queue_dsn(
            QUEUE.replace("https://", "https://user:synthetic@"), "eu-central-1"
        )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (QUEUE.replace("https://", "https://user:synthetic@"), "userinfo"),
        (QUEUE.replace("https://", "https://user@"), "userinfo"),
        (f"sqs://default?region=eu-central-1&access_key={ACCESS_KEY}", "access key"),
        (f"{QUEUE}?region=eu-central-1&secret_key=synthetic", "credential parameter"),
        (f"{QUEUE}?Secret-Key=synthetic", "credential parameter"),
        (f"{QUEUE}?X-Amz-Credential=synthetic", "credential parameter"),
        (f"{QUEUE}?session_token=synthetic", "credential parameter"),
        ("ses+api://default?region=eu-central-1&password=x", "credential parameter"),
        ("ASIA" + "SYNTHETIC0000000", "access key"),
        (None, "plain string"),
        (443, "plain string"),
    ],
)
def test_a_key_or_userinfo_in_a_dsn_raises(value, message):
    """FR-03 N (AD-20): a key, userinfo or credential parameter fails."""
    with pytest.raises(ValueError, match=message):
        require_credential_free(value)


@pytest.mark.parametrize(
    "value",
    [
        f"{QUEUE}?region=eu-central-1&auto_setup=false",
        "ses+api://default?region=eu-central-1",
        "sender@user.vilnacrmtest.com",
        "^https://user\\.vilnacrmtest\\.com$",
        "mongodb://host:27017/db?authSource=%24external&authMechanism=MONGODB-AWS",
        "AKIA-not-a-key",
        "",
    ],
)
def test_credential_free_values_pass_unchanged(value):
    assert require_credential_free(value) == value


@pytest.mark.parametrize(
    ("environment", "secrets"),
    [
        ([{"name": "APP_SECRET", "value": "x"}], [{"name": "APP_SECRET"}]),
        ([{"name": "A", "value": "x"}, {"name": "A", "value": "y"}], []),
        ([{"name": "MONGODB_URL", "value": "mongodb://u:p@h/db"}], []),
    ],
)
def test_overlapping_or_credential_environment_raises(environment, secrets):
    with pytest.raises(ValueError):
        require_plain_environment(environment, secrets)
    with pytest.raises(ValueError):
        ComputePlane._serialize_container(
            [{"environment": environment, "secrets": secrets}]
        )


def test_plain_container_serializes_unchanged():
    containers = [{"environment": [{"name": "A", "value": "x"}], "secrets": []}]
    assert ComputePlane._serialize_container(containers) == json.dumps(containers)


@pytest.mark.parametrize("scale", [None, 1, 2])
def test_hardened_compute_refuses_any_initial_scale_but_zero(monkeypatch, scale):
    """FR-34: the hardened step-1 services cannot start with tasks."""
    for name in ("validate_runtime_roles", "validate_health_check_runtime"):
        monkeypatch.setattr(module, name, lambda *_: None)
    monkeypatch.setattr(
        pulumi.ComponentResource,
        "__init__",
        lambda *_a, **_k: pytest.fail("registered before the scale check"),
    )
    secrets = SimpleNamespace(
        descriptor=SimpleNamespace(hardened=True, validate_target=lambda _: None)
    )
    with pytest.raises(ValueError, match="zero tasks"):
        ComputePlane(
            "compute",
            settings=SimpleNamespace(
                is_managed=True, environment="test", runtime=None, queues=None
            ),
            network=None,
            data=None,
            messaging=None,
            runtime_secrets=secrets,
            initial_service_scale=scale,
        )


def test_desired_count_override_applies_only_when_set():
    compute = object.__new__(ComputePlane)
    assert compute._desired_count(2) == 2
    compute._initial_service_scale = INITIAL_SERVICE_SCALE
    assert compute._desired_count(2) == 0
