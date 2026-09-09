"""Synthetic-only contract checks; no AWS or approval evidence is fabricated."""

import copy
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest
from jsonschema import Draft202012Validator
from poc_contract import MAX_BYTES, SCHEMA_PATH, load, validate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HERE = PROJECT_ROOT / "tests" / "fixtures" / "poc-contract"
SCRIPT = PROJECT_ROOT / "scripts" / "poc_contract.py"


def fixture(name):
    return load(HERE / f"{name}.synthetic.json")


def change(value, path, replacement):
    target = value
    for key in path.split(".")[:-1]:
        target = target[key]
    target[path.split(".")[-1]] = replacement


def test_schema_and_phase_transitions():
    Draft202012Validator.check_schema(json.loads(SCHEMA_PATH.read_text()))
    registry, workload = fixture("registry"), fixture("workload")
    assert len(validate(registry, initial_registry=True)) == 64
    assert len(validate(registry, previous=registry)) == 64
    assert len(validate(workload, previous=registry)) == 64
    assert validate(workload, previous=workload) == validate(
        workload, previous=registry
    )
    reordered = dict(reversed(list(workload.items())))
    assert validate(reordered, previous=registry) == validate(
        workload, previous=registry
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("account_id", "933245420672"),
        ("region", "us-east-1"),
        ("backend.url", "s3://another-stack"),
        ("status", "installed"),
        ("source.repository_id", True),
        ("source.head_sha", "main"),
        ("workload.central.task_role_arn", "arn:aws:iam::933245420672:role/Foreign"),
        ("workload.central.owner", "service"),
        ("workload.central.publisher_workflow_path", None),
        ("workload.release.repository_id", 911736693),
        ("workload.release.source_sha", "latest"),
        ("workload.release.web.digest", "latest"),
        ("workload.release.web.target", "app_workers"),
        ("workload.release.web.repository_uri", "foreign"),
        (
            "workload.release.workflow_ref",
            "VilnaCRM-Org/user-service/.github/workflows/other.yml@refs/heads/main",
        ),
        ("workload.release.publisher_run_attempt", 2),
        ("workload.external.domain.review", {}),
        ("workload.external.mail.review", {}),
        ("workload.secret_lifecycle.references.app_secret.name", "plaintext-value"),
        (
            "workload.secret_lifecycle.references.app_secret.name",
            "arn:aws:secretsmanager:eu-central-1:891377212104:secret:/user-service-infrastructure/ci/test-AbCdEf",
        ),
        (
            "workload.secret_lifecycle.references.app_secret.owner",
            "external-mail-owner",
        ),
        ("workload.secret_lifecycle.guard_amendment", "installed"),
        ("workload.runtime.ecs_exec", True),
        ("workload.runtime.queue_auto_setup", True),
        (
            "workload.runtime.optional_social_providers",
            "disabled-requires-application-repair",
        ),
        ("workload.runtime.optional_social_providers.value", "true"),
        ("workload.runtime.optional_social_providers.value", False),
        ("workload.runtime.optional_social_providers.environment_variable", "APP_ENV"),
        ("workload.runtime.optional_social_providers", {}),
        ("workload.service_components", ["iam:Role"]),
        (
            "registries.web.arn",
            "arn:aws:ecr:eu-central-1:891377212104:repository/wrong",
        ),
        ("registries.web.uri", "891377212104.dkr.ecr.eu-central-1.amazonaws.com/wrong"),
        ("registries.web.logical_name", "synthetic-worker"),
    ],
)
def test_invalid_workload(path, value):
    contract = fixture("workload")
    change(contract, path, value)
    with pytest.raises(ValueError):
        validate(contract, previous=fixture("registry"))


def test_secret_and_role_aliases_rejected():
    for kind in ("secret", "role"):
        contract = fixture("workload")
        if kind == "secret":
            refs = contract["workload"]["secret_lifecycle"]["references"]
            refs["app_secret"] = copy.deepcopy(refs["oauth_passphrase"])
        else:
            central = contract["workload"]["central"]
            central["task_role_arn"] = central["execution_role_arn"]
        with pytest.raises(ValueError):
            validate(contract, previous=fixture("registry"))


def test_no_untyped_policy_or_secret_values():
    for path in ("iam_policy", "workload.secret_lifecycle.references.app_secret.value"):
        contract = fixture("workload")
        change(contract, path, "not-a-secret-fixture")
        with pytest.raises(ValueError):
            validate(contract, previous=fixture("registry"))


def test_transition_requires_explicit_prior_state():
    registry, workload = fixture("registry"), fixture("workload")
    cases = [
        (registry, {}),
        (workload, {}),
        (workload, {"initial_registry": True}),
        (registry, {"previous": workload}),
        (registry, {"previous": registry, "initial_registry": True}),
        (registry, {"initial_registry": 1}),
    ]
    for contract, kwargs in cases:
        with pytest.raises(ValueError):
            validate(contract, **kwargs)


def test_registry_owner_cannot_change_during_upgrade():
    contract = fixture("workload")
    web = contract["registries"]["web"]
    for field in ("name", "uri", "arn"):
        web[field] = web[field].replace(
            "synthetic-poc-web", "synthetic-replacement-web"
        )
    contract["workload"]["release"]["web"]["repository_uri"] = web["uri"]
    with pytest.raises(ValueError, match="ownership changed"):
        validate(contract, previous=fixture("registry"))


def test_workload_fields_rejected_in_registry():
    registry = fixture("registry")
    registry["workload"] = fixture("workload")["workload"]
    with pytest.raises(ValueError):
        validate(registry, initial_registry=True)


@pytest.mark.parametrize(
    "raw",
    [b'{"x":1,"x":2}', b"[]", b"{", b"\xff", b'{"value":NaN}', b" " * (MAX_BYTES + 1)],
)
def test_bad_json(tmp_path, raw):
    path = tmp_path / "contract.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        load(path)


def test_cli_success_and_redacted_failure(tmp_path):
    cli = [sys.executable, str(SCRIPT)]
    good = subprocess.run(
        cli
        + [
            str(HERE / "workload.synthetic.json"),
            "--previous",
            str(HERE / "registry.synthetic.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert good.returncode == 0
    assert "VALID_PROPOSED_ONLY" in good.stdout
    bad = tmp_path / "bad.json"
    bad.write_text('{"secret":"DO_NOT_ECHO_TEST_MARKER"}')
    failed = subprocess.run(
        cli + [str(bad), "--initial-registry"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 1
    assert "DO_NOT_ECHO_TEST_MARKER" not in failed.stdout + failed.stderr
    assert "INVALID" in failed.stderr


@pytest.mark.parametrize("field", ["name", "kms_key_arn"])
def test_generated_secret_transition_is_stable(field):
    previous = fixture("workload")
    contract = copy.deepcopy(previous)
    secret = contract["workload"]["secret_lifecycle"]["references"]["app_secret"]
    if field == "name":
        secret[field] = secret[field].replace(
            "synthetic-app_secret", "synthetic-replaced"
        )
    else:
        secret[field] = secret[field][:-1] + "2"
    with pytest.raises(ValueError, match="rotation or replacement"):
        validate(contract, previous=previous)


def test_release_update_and_rollback_preserve_secrets():
    old = fixture("workload")
    new = copy.deepcopy(old)
    new["workload"]["release"]["source_sha"] = "f" * 40
    new["workload"]["release"]["publisher_run_id"] = 2
    # Equal content hashes are valid if both target and registry bindings are correct.
    for kind in ("web", "worker"):
        new["workload"]["release"][kind]["digest"] = "sha256:" + "e" * 64
    assert len(validate(new, previous=old)) == 64
    assert len(validate(old, previous=new)) == 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("transport", "smtp"),
        ("transport", "ses+smtp"),
        ("authentication", "static-access-key"),
        ("account_id", "933245420672"),
        ("region", "us-east-1"),
        ("identity_arn", "arn:aws:ses:eu-central-1:933245420672:identity/poc.example"),
        ("identity_arn", "arn:aws:ses:us-east-1:891377212104:identity/poc.example"),
        ("identity_arn", "arn:aws:ses:eu-central-1:891377212104:identity/*"),
        (
            "identity_arn",
            "arn:aws:ses:eu-central-1:891377212104:identity/other.example",
        ),
        (
            "identity_arn",
            "arn:aws:ses:eu-central-1:891377212104:identity/other@poc.example",
        ),
        ("sender", "sender@notpoc.example"),
        ("sender", "sender@poc.example.evil.example"),
        ("sender", "sender@poc.example\n"),
        ("sender", "*@poc.example"),
        ("recipients", []),
        ("recipients", ["*@poc.example"]),
        ("recipients", ["recipient@poc.example", "recipient@poc.example"]),
        ("recipients", ["recipient@poc.example\n"]),
        ("recipients", [f"recipient{i}@poc.example" for i in range(11)]),
        ("action", "ses:*"),
        ("action", "ses:SendRawEmail"),
        ("required_iam_conditions", ["ses:FromAddress"]),
        ("access_key_id", "SYNTHETIC_NOT_A_CREDENTIAL"),
        ("secret_access_key", "SYNTHETIC_NOT_A_CREDENTIAL"),
        ("session_token", "SYNTHETIC_NOT_A_CREDENTIAL"),
        ("endpoint", "https://override.example"),
        ("profile", "default"),
        ("dsn", "smtp://synthetic:fixture@poc.example"),
        ("dsn", "ses+api://default?region=eu-central-1"),
    ],
)
def test_ses_rejects_unsafe_transport_and_bindings(field, value):
    contract = fixture("workload")
    contract["workload"]["external"]["mail"][field] = value
    with pytest.raises(ValueError):
        validate(contract, previous=fixture("registry"))


@pytest.mark.parametrize(
    ("identity", "sender"),
    [
        ("poc.example", "sender@poc.example"),
        ("poc.example", "sender@sub.poc.example"),
        ("sender@poc.example", "sender@poc.example"),
    ],
)
def test_ses_identity_matches_sender_independently_of_web_domain(identity, sender):
    contract = fixture("workload")
    mail = contract["workload"]["external"]["mail"]
    mail["identity_arn"] = "arn:aws:ses:eu-central-1:891377212104:identity/" + identity
    mail["sender"] = sender
    assert len(validate(contract, previous=fixture("registry"))) == 64
    assert contract["workload"]["external"]["domain"]["fqdn"] == "user.vilnacrmtest.com"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fqdn", "user.vilnacrm.com"),
        ("fqdn", "other.vilnacrmtest.com"),
        ("dns_authority", "external-dns"),
        ("account_id", "933245420672"),
        ("hosted_zone_id", "Z_SYNTHETIC_FOREIGN"),
        (
            "certificate_arn",
            "arn:aws:acm:eu-central-1:933245420672:certificate/"
            "00000000-0000-4000-8000-000000000002",
        ),
    ],
)
def test_dns_is_bound_to_approved_test_endpoint(field, value):
    contract = fixture("workload")
    contract["workload"]["external"]["domain"][field] = value
    with pytest.raises(ValueError):
        validate(contract, previous=fixture("registry"))


def test_mail_secret_is_rejected_and_generated_secrets_remain_required():
    previous = fixture("workload")
    references = previous["workload"]["secret_lifecycle"]["references"]
    assert len(references) == 10
    for purpose in references:
        candidate = copy.deepcopy(previous)
        del candidate["workload"]["secret_lifecycle"]["references"][purpose]
        with pytest.raises(ValueError):
            validate(candidate, previous=previous)
    candidate = copy.deepcopy(previous)
    candidate["workload"]["secret_lifecycle"]["references"]["mailer_dsn"] = references[
        "app_secret"
    ]
    with pytest.raises(ValueError):
        validate(candidate, previous=previous)


@pytest.mark.parametrize(
    "field",
    [
        "transport",
        "authentication",
        "identity_arn",
        "sender",
        "recipients",
        "required_iam_conditions",
        "review",
    ],
)
def test_ses_binding_fields_cannot_be_omitted(field):
    contract = fixture("workload")
    del contract["workload"]["external"]["mail"][field]
    with pytest.raises(ValueError):
        validate(contract, previous=fixture("registry"))
