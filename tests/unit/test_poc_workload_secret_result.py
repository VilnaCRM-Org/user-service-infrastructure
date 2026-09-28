"""Synthetic state/native metadata checks; never fetch or log secret values."""

import copy
import importlib
import json

import pytest
from test_poc_contract import fixture as contract_fixture
from test_poc_registry_plan import states

module = importlib.import_module("poc_workload_secret_result")


@pytest.fixture
def data():
    contract = contract_fixture("workload")
    before = list(states().values())
    after = copy.deepcopy(before)
    rows = {row["urn"].rsplit("::", 1)[-1]: row for row in after}
    baseline = {row["urn"] for row in before}
    for urn, (
        kind,
        parent,
        custom,
        protect,
    ) in module.topology.expected_graph().items():
        if urn in baseline:
            continue
        name = urn.rsplit("::", 1)[-1]
        row = {
            "urn": urn,
            "type": kind,
            "parent": parent,
            "custom": custom,
            "protect": protect,
            "inputs": {},
            "outputs": {},
            "aliases": module.state.state_aliases(urn, kind),
        }
        if custom:
            row["id"] = name + "-id"
        after.append(row)
        rows[name] = row

    native = {}
    marker = module.state.PULUMI_MARKER_SIGNATURE
    sentinel = module.state.PULUMI_MARKER_SENTINEL
    for index, (purpose, declaration) in enumerate(
        contract["workload"]["secret_lifecycle"]["references"].items()
    ):
        arn = (
            "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
            + declaration["name"]
            + "-ABC123"
        )
        identifier = f"{index + 1:032x}"
        secret = rows[f"runtime-{purpose}"]
        secret["id"] = arn
        secret["inputs"] = {
            "name": declaration["name"],
            "kmsKeyId": declaration["kms_key_arn"],
        }
        secret["outputs"] = {**secret["inputs"], "arn": arn}
        version = rows[f"runtime-{purpose}-version"]
        version["id"] = f"{arn}|{identifier}"
        version["inputs"] = {
            "secretId": arn,
            "secretString": {
                marker: sentinel,
                "ciphertext": "synthetic-encrypted-placeholder",
            },
        }
        version["outputs"] = {
            "secretId": arn,
            "versionId": identifier,
            "secretString": copy.deepcopy(version["inputs"]["secretString"]),
        }
        version["additionalSecretOutputs"] = module.topology.SECRET_VERSION_OUTPUTS
        native[declaration["name"]] = {
            "ARN": arn,
            "Name": declaration["name"],
            "KmsKeyId": declaration["kms_key_arn"],
            "RotationEnabled": False,
            "VersionIdsToStages": {identifier: ["AWSCURRENT"]},
        }
    return contract, before, after, rows, native


def observe(data, *, native=None):
    contract, before, after, _, details = data
    return module.inspect_first_secret_history(
        contract, before, after, native=native or (lambda name: details[name])
    )


def test_reads_all_native_descriptions_twice_and_returns_only_metadata(data):
    contract, before, after, _, native = data
    saved = copy.deepcopy((contract, before, after, native))
    calls = []

    def read(name):
        calls.append(name)
        return copy.deepcopy(native[name])

    result = observe(data, native=read)
    names = [
        row["name"]
        for row in contract["workload"]["secret_lifecycle"]["references"].values()
    ]
    assert calls == names + names
    assert set(result) == set(contract["workload"]["secret_lifecycle"]["references"])
    assert all(set(item) == module.secret_history.FIELDS for item in result.values())
    assert (contract, before, after, native) == saved


def test_retained_previous_version_does_not_hide_the_current_version(data):
    native = data[-1]
    name = next(iter(native))
    native[name]["VersionIdsToStages"]["f" * 32] = ["AWSPREVIOUS"]
    assert observe(data)["document_db_password"]["version_id"] == "1".zfill(32)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ARN", "foreign"),
        ("Name", "foreign"),
        ("KmsKeyId", "foreign"),
        ("RotationEnabled", True),
        ("DeletedDate", "2026-01-01T00:00:00Z"),
        ("VersionIdsToStages", {}),
        ("VersionIdsToStages", {"a" * 32: ["AWSPENDING"]}),
        ("VersionIdsToStages", {"a" * 32: ["AWSCURRENT", "AWSPENDING"]}),
        ("VersionIdsToStages", {"a" * 32: ["AWSCURRENT", "AWSCURRENT"]}),
        ("VersionIdsToStages", {"a" * 32: ["AWSCURRENT"], "b" * 32: ["AWSCURRENT"]}),
        ("VersionIdsToStages", {"invalid": ["AWSCURRENT"]}),
        ("VersionIdsToStages", {"a" * 32: "AWSCURRENT"}),
    ],
)
def test_native_secret_mismatch_rejects(data, field, value):
    native = data[-1]
    name = next(iter(native))
    native[name][field] = value
    with pytest.raises(ValueError):
        observe(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "foreign"),
        ("inputs.name", "foreign"),
        ("inputs.kmsKeyId", "foreign"),
        ("outputs.arn", "foreign"),
        ("outputs.name", "foreign"),
        ("outputs.kmsKeyId", "foreign"),
    ],
)
def test_secret_checkpoint_mismatch_rejects(data, field, value):
    row = data[3]["runtime-app_secret"]
    target = row
    keys = field.split(".")
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    with pytest.raises(ValueError):
        observe(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "foreign"),
        ("inputs.secretId", "foreign"),
        ("outputs.secretId", "foreign"),
        ("outputs.versionId", "f" * 32),
        ("outputs.secretString", "plaintext-synthetic"),
        ("additionalSecretOutputs", []),
    ],
)
def test_version_checkpoint_mismatch_rejects(data, field, value):
    row = data[3]["runtime-app_secret-version"]
    target = row
    keys = field.split(".")
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    with pytest.raises(ValueError):
        observe(data)


@pytest.mark.parametrize(
    "fault", ["missing", "extra", "parent", "baseline", "phase", "second-read"]
)
def test_partial_or_moving_state_rejects(data, fault):
    contract, _, after, rows, native = data
    if fault == "missing":
        after.remove(rows["runtime-app_secret"])
    elif fault == "extra":
        extra = copy.deepcopy(rows["runtime-app_secret"])
        extra["urn"] += "-extra"
        after.append(extra)
    elif fault == "parent":
        rows["runtime-app_secret"]["parent"] = module.registry.ROOT
    elif fault == "baseline":
        rows["user-service-web-repository"]["id"] = "replacement"
    elif fault == "phase":
        contract["phase"] = "registry"
    else:
        name = next(iter(native))
        calls = 0

        def moving(candidate):
            nonlocal calls
            calls += 1
            result = copy.deepcopy(native[candidate])
            if candidate == name and calls > len(native):
                result["VersionIdsToStages"] = {"f" * 32: ["AWSCURRENT"]}
            return result

        with pytest.raises(ValueError):
            observe(data, native=moving)
        return
    with pytest.raises(ValueError):
        observe(data)


def test_metadata_cli_uses_only_describe_secret_in_isolated_session(monkeypatch):
    calls = []
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "synthetic-session-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic-session-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "synthetic-session-token")
    monkeypatch.setenv("HOME", "/trusted")

    def run(command, **options):
        calls.append((command, options))
        return json.dumps({"Name": "synthetic"}).encode()

    monkeypatch.setattr(module, "run", run)
    assert module._native("synthetic") == {"Name": "synthetic"}
    command, options = calls.pop()
    assert command[1:3] == ["secretsmanager", "describe-secret"]
    assert command[command.index("--secret-id") + 1] == "synthetic"
    assert options["env"]["AWS_CONFIG_FILE"] == "/dev/null"
    assert options["env"]["AWS_SHARED_CREDENTIALS_FILE"] == "/dev/null"
    assert options["env"]["AWS_SESSION_TOKEN"] == "synthetic-session-token"
    assert "get-secret-value" not in command
