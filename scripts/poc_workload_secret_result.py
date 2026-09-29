"""Read first-workload secret metadata without fetching any secret value.

This is one component of a future authenticated result observer. The caller
must bind the before/after checkpoint reads, source, accepted apply and native
AWS session before treating these observations as a deployment receipt.
"""

from __future__ import annotations

import os
from pathlib import Path

import poc_backend_observer as backend
import poc_contract as contracts
import poc_registry_plan as registry
import poc_secret_observation as secret_history
import poc_workload_reconciliation as state
import poc_workload_topology as topology
from poc_registry_phase_entrypoint import RegistryPhaseProjection
from service_execution_process import require, run
from service_execution_transport import AWS


def _check(condition):
    require(condition, "workload-secret-result")


def _native(name):
    """Read only fixed Secrets Manager metadata with the admitted AWS session."""
    environment = {
        key: os.environ[key]
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    }
    environment.update(
        PATH="/usr/local/bin:/usr/bin:/bin",
        HOME=os.environ["HOME"],
        AWS_CONFIG_FILE="/dev/null",
        AWS_SHARED_CREDENTIALS_FILE="/dev/null",
        AWS_EC2_METADATA_DISABLED="true",
        AWS_MAX_ATTEMPTS="1",
    )
    raw = run(
        [
            AWS,
            "secretsmanager",
            "describe-secret",
            "--secret-id",
            name,
            "--region",
            backend.REGION,
            "--endpoint-url",
            f"https://secretsmanager.{backend.REGION}.amazonaws.com",
            "--output",
            "json",
            "--no-cli-pager",
            "--no-paginate",
        ],
        env=environment,
        cwd=Path("/trusted"),
        timeout=120,
    )
    _check(len(raw) <= backend.MAX_METADATA)
    return backend._json(raw)


def _rows(before_resources, after_resources):
    baseline = registry._graph(RegistryPhaseProjection(registry.REGISTRIES))
    before = registry._prior(before_resources, baseline)
    _check(before.keys() == baseline.keys())
    after = state._inventory(after_resources)
    graph = topology.expected_graph()
    _check(after.keys() == graph.keys())
    for urn, row in after.items():
        _check(
            state._same(
                (
                    row["type"],
                    row.get("parent", ""),
                    row["custom"],
                    row.get("protect", False),
                ),
                graph[urn],
            )
        )
        if urn in before:
            previous = {
                key: value
                for key, value in before[urn].items()
                if key not in state.OBSERVATION_FIELDS
            }
            current = {
                key: value
                for key, value in row.items()
                if key not in state.OBSERVATION_FIELDS
            }
            _check(state._same(current, previous))
    rows = {urn.rsplit("::", 1)[-1]: row for urn, row in after.items()}
    _check(len(rows) == len(after))
    return rows


def _version_stages(detail):
    versions = detail.get("VersionIdsToStages")
    _check(type(versions) is dict and bool(versions))
    current = []
    for identifier, stages in versions.items():
        secret_history._validate_secret_version(identifier)
        _check(
            type(stages) is list
            and all(type(stage) is str for stage in stages)
            and len(stages) == len(set(stages))
            and "AWSPENDING" not in stages
        )
        if "AWSCURRENT" in stages:
            current.append(identifier)
    _check(len(current) == 1)
    return current[0]


def _current_version(native, declaration, arn):
    """Accept one current version and no pending deletion or rotation.

    DescribeSecret omits ``RotationEnabled`` for a secret that has never had
    rotation configured, so an absent field means disabled; any value other
    than a native ``false`` still rejects.
    """
    detail = native(declaration["name"])
    _check(type(detail) is dict)
    _check(detail.get("ARN") == arn and detail.get("Name") == declaration["name"])
    _check(detail.get("KmsKeyId") == declaration["kms_key_arn"])
    _check(
        detail.get("RotationEnabled", False) is False and "DeletedDate" not in detail
    )
    return _version_stages(detail)


def _checkpoint_secret(secret, declaration):
    arn = secret.get("id")
    _check(
        type(arn) is str
        and secret["inputs"].get("name") == declaration["name"]
        and secret["inputs"].get("kmsKeyId") == declaration["kms_key_arn"]
        and secret["outputs"].get("arn") == arn
        and secret["outputs"].get("name") == declaration["name"]
        and secret["outputs"].get("kmsKeyId") == declaration["kms_key_arn"]
    )
    return arn


def _checkpoint_version(version, arn, identifier):
    _check(
        version.get("id") == f"{arn}|{identifier}"
        and version["outputs"].get("versionId") == identifier
        and version["inputs"].get("secretId") == arn
        and version["outputs"].get("secretId") == arn
        and version.get("additionalSecretOutputs") == topology.SECRET_VERSION_OUTPUTS
    )
    for field in ("secretString", "secretBinary"):
        if field in version["outputs"]:
            value = version["outputs"][field]
            _check(
                type(value) is dict
                and value.get(state.PULUMI_MARKER_SIGNATURE)
                == state.PULUMI_MARKER_SENTINEL
            )
            state._redacted(value)


def _observed_secret(rows, purpose, declaration, native):
    secret = rows[f"runtime-{purpose}"]
    version = rows[f"runtime-{purpose}-version"]
    arn = _checkpoint_secret(secret, declaration)
    identifier = _current_version(native, declaration, arn)
    _checkpoint_version(version, arn, identifier)
    return {
        "arn": arn,
        "version_id": identifier,
        "kms_key_arn": declaration["kms_key_arn"],
        "owner": declaration["owner"],
    }


def inspect_first_secret_history(
    contract, before_resources, after_resources, *, native=None
):
    """Bind protected first-create checkpoint rows to stable native metadata.

    The return value is not a receipt. The caller must recheck its authenticated
    checkpoint, native AWS identity and source around this bounded observation.
    """
    contracts._validate_document(contract)
    _check(contract["phase"] == "workload")
    rows = _rows(before_resources, after_resources)
    declarations = contract["workload"]["secret_lifecycle"]["references"]
    read = native or _native
    first = {
        purpose: _observed_secret(rows, purpose, declaration, read)
        for purpose, declaration in declarations.items()
    }
    second = {
        purpose: _observed_secret(rows, purpose, declaration, read)
        for purpose, declaration in declarations.items()
    }
    _check(first == second)
    secret_history.validate_secret_observation(contract, second)
    return second


def _workload_rows(resources):
    """Require a complete, fixed workload checkpoint before comparing versions."""
    inventory = state._inventory(resources)
    graph = topology.expected_graph()
    _check(inventory.keys() == graph.keys())
    for urn, row in inventory.items():
        _check(
            state._same(
                (
                    row["type"],
                    row.get("parent", ""),
                    row["custom"],
                    row.get("protect", False),
                ),
                graph[urn],
            )
        )
    rows = {urn.rsplit("::", 1)[-1]: row for urn, row in inventory.items()}
    _check(len(rows) == len(inventory))
    return rows


def _stable_row(before, after):
    """Ignore observation timestamps, not resource identity or secret metadata."""
    fields = state.OBSERVATION_FIELDS
    _check(
        state._same(
            {key: value for key, value in before.items() if key not in fields},
            {key: value for key, value in after.items() if key not in fields},
        )
    )


def inspect_retained_secret_history(
    contract, before_resources, after_resources, previous, *, native=None
):
    """Reject secret replacement or rotation across release and rollback.

    ``previous`` must come from an authenticated accepted-workload receipt. The
    caller must also authenticate both checkpoints, source and AWS session; this
    bounded metadata check does not issue a receipt or enable workload apply.
    """
    contracts._validate_document(contract)
    _check(contract["phase"] == "workload")
    secret_history.validate_secret_observation(contract, previous)
    before = _workload_rows(before_resources)
    after = _workload_rows(after_resources)
    declarations = contract["workload"]["secret_lifecycle"]["references"]
    for purpose in declarations:
        for suffix in ("", "-version"):
            name = f"runtime-{purpose}{suffix}"
            _stable_row(before[name], after[name])
    read = native or _native
    first = {
        purpose: _observed_secret(after, purpose, declaration, read)
        for purpose, declaration in declarations.items()
    }
    second = {
        purpose: _observed_secret(after, purpose, declaration, read)
        for purpose, declaration in declarations.items()
    }
    _check(first == second)
    secret_history.validate_secret_observation(contract, second, previous=previous)
    return second
