#!/usr/bin/env python3
"""Observe TEST backend facts privately; never authorize an initial/prior phase.

Run installed main under python3 -I in a trusted-only job after reviewed OIDC
admission. Environment coordinates must be the existing load-aws-ci-env outputs.
No PR code, raw checkpoint, secret value, Pulumi export or AWS write is emitted.
Only project-scoped Pulumi metadata version 1 is supported; missing/legacy or
compressed/ambiguous checkpoints require reconciliation. An absent checkpoint
is an observation, never permission to initialize. Accepted receipts are separate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import base64  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import selectors  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402  # nosec B404
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from tempfile import TemporaryDirectory  # noqa: E402
from typing import Any  # noqa: E402

import poc_contract  # noqa: E402
import poc_source_artifact as source_artifact  # noqa: E402

ACCOUNT = "891377212104"
REGION = "eu-central-1"
PROJECT = "user-service-infrastructure"
BUCKET = f"pulumi-{PROJECT}-test-state"
PROVIDER = f"awskms://alias/pulumi-{PROJECT}-test-secrets?region={REGION}"
CHECKPOINT = f".pulumi/stacks/{PROJECT}/test.json"
LOCKS = f".pulumi/locks/organization/{PROJECT}/test/"
MAX_BYTES = 16 * 1024 * 1024
MAX_METADATA = 2 * 1024 * 1024


@dataclass(frozen=True, repr=False)
class PrivateBackendCapture:
    """In-memory input to trusted graph validation; never serialize this object.

    Only summary is public. Resources retain complete private checkpoint values,
    are not phase authority, and must not enter logs or job artifacts. Suppress
    generated repr so accidental object formatting cannot expose those values.
    """

    summary: dict[str, Any]
    resources: list[dict[str, Any]]


def _require(condition):
    """Never include remote or checkpoint values in an exception."""
    if not condition:
        raise ValueError("Backend observation precondition failed")


def _json(raw):
    """Decode bounded private JSON without ambiguous keys/nonfinite numbers."""
    _require(len(raw) <= MAX_BYTES)
    value = json.loads(
        raw,
        object_pairs_hook=poc_contract._pairs,
        parse_constant=poc_contract._reject_nonfinite,
    )
    _require(type(value) is dict)
    return value


def _digest(value):
    """Bind exact bytes or a sanitized inventory deterministically."""
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )
    return hashlib.sha256(raw).hexdigest()


def _stream(process):
    """Bound trusted CLI stdout; discard stderr, including service error bodies."""
    _require(process.stdout is not None)
    data = bytearray()
    deadline = time.monotonic() + 120
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            _require(time.monotonic() < deadline)
            if not selector.select(timeout=1):
                continue
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            data.extend(chunk)
            _require(len(data) <= MAX_METADATA)
    _require(process.wait(timeout=10) == 0)
    return bytes(data)


def aws_read(service, operation, arguments, output=None):
    """Use native authenticated AWS CLI with fixed AWS endpoints and no retries."""
    allowed = {
        ("sts", "get-caller-identity"),
        ("kms", "describe-key"),
        ("s3api", "get-bucket-versioning"),
        ("s3api", "list-objects-v2"),
        ("s3api", "head-object"),
        ("s3api", "get-object"),
    }
    _require((service, operation) in allowed)
    endpoint = "s3" if service == "s3api" else service
    command = [
        "aws",
        service,
        operation,
        "--region",
        REGION,
        "--endpoint-url",
        f"https://{endpoint}.{REGION}.amazonaws.com",
        "--output",
        "json",
        "--no-cli-pager",
        "--no-paginate",
    ]
    for key, value in arguments.items():
        command.extend(["--" + key, str(value)])
    _require((output is not None) == (operation == "get-object"))
    if output is not None:
        command.append(str(output))
    environment = {**os.environ, "AWS_MAX_ATTEMPTS": "1"}
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=environment,
    ) as process:  # nosec B603 B607
        try:
            return _json(_stream(process))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


def _operation_identity(operation):
    """Only the installed runner's two saved-plan operations select a caller."""
    identities = {
        "plan": ("AWS_PREVIEW_ROLE_ARN", "Preview", "preview"),
        "up-plan": ("AWS_APPLY_ROLE_ARN", "Apply", "apply"),
    }
    _require(type(operation) is str and operation in identities)
    return identities[operation]


def _target(source, operation="plan"):
    """Cross-check fixed installed constants with authenticated source and loader."""
    _require(source["request"]["target_environment"] == "test")
    role_key, role_kind, _ = _operation_identity(operation)
    expected = {
        "AWS_ACCOUNT_ID": ACCOUNT,
        "AWS_REGION": REGION,
        role_key: (f"arn:aws:iam::{ACCOUNT}:role/GitHubCi{role_kind}-{PROJECT}-test"),
        "PULUMI_BACKEND_URL": f"s3://{BUCKET}",
        "PULUMI_SECRETS_PROVIDER": PROVIDER,
    }
    _require(all(os.environ.get(key) == value for key, value in expected.items()))
    schema = poc_contract.load(poc_contract.SCHEMA_PATH)["properties"]
    _require(
        schema["account_id"]["const"] == ACCOUNT and schema["region"]["const"] == REGION
    )
    backend = schema["backend"]["properties"]
    for key, value in {
        "project": PROJECT,
        "stack": "test",
        "url": f"s3://{BUCKET}",
        "secrets_provider": PROVIDER,
    }.items():
        _require(backend[key]["const"] == value)


def _caller(aws, operation="plan"):
    """Require the exact TEST operation role/session from the admitted root run."""
    _, role_kind, purpose = _operation_identity(operation)
    run_id = os.environ["GITHUB_RUN_ID"]
    caller = aws("sts", "get-caller-identity", {})
    arn = (
        f"arn:aws:sts::{ACCOUNT}:assumed-role/GitHubCi{role_kind}-{PROJECT}-test/"
        f"gha-pr-test-{purpose}-{run_id}"
    )
    _require(caller.get("Account") == ACCOUNT and caller.get("Arn") == arn)
    return arn


def _bucket_args():
    """Never accept a bucket or expected owner from dispatch/PR inputs."""
    return {"bucket": BUCKET, "expected-bucket-owner": ACCOUNT}


def _list(aws, prefix):
    """Exhaust native pagination with a finite bound, preserving absence proof."""
    keys, tokens, token = set(), set(), None
    for _ in range(20):
        args = {**_bucket_args(), "prefix": prefix, "max-keys": "1000"}
        if token is not None:
            args["continuation-token"] = token
        page = aws("s3api", "list-objects-v2", args)
        _require(type(page.get("IsTruncated")) is bool)
        rows = page.get("Contents", [])
        _require(type(rows) is list and len(rows) <= 1000)
        for row in rows:
            key = row.get("Key")
            _require(type(key) is str and key.startswith(prefix) and key not in keys)
            keys.add(key)
        if not page["IsTruncated"]:
            _require(not page.get("NextContinuationToken"))
            return sorted(keys)
        token = page.get("NextContinuationToken")
        _require(type(token) is str and 0 < len(token) <= 4096 and token not in tokens)
        tokens.add(token)
    raise ValueError("Backend listing incomplete")


def _head(aws, key, limit):
    """Retain native SSE separately from Pulumi's KMS secrets provider."""
    head = aws("s3api", "head-object", {**_bucket_args(), "key": key})
    for field in ("VersionId", "ETag"):
        _require(type(head.get(field)) is str and head[field] not in ("", "null"))
    _require(
        type(head.get("ContentLength")) is int and 0 < head["ContentLength"] <= limit
    )
    encryption = head.get("ServerSideEncryption")
    _require(encryption in ("AES256", "aws:kms"))
    key_arn = head.get("SSEKMSKeyId")
    if encryption == "AES256":
        _require(key_arn is None)
    else:
        _require(
            type(key_arn) is str
            and re.fullmatch(
                f"arn:aws:kms:{REGION}:{ACCOUNT}:key/[0-9a-f-]{{36}}", key_arn
            )
        )
    _require(not head.get("DeleteMarker"))
    return {
        key: head.get(key)
        for key in (
            "VersionId",
            "ETag",
            "ContentLength",
            "ServerSideEncryption",
            "SSEKMSKeyId",
        )
    }


def _capture(aws, key, limit):
    """Read a version-pinned object only in a private temporary directory."""
    before = _head(aws, key, limit)
    with TemporaryDirectory(prefix="poc-private-observation-") as directory:
        path = Path(directory) / "object"
        path.touch(mode=0o600)
        metadata = aws(
            "s3api",
            "get-object",
            {
                **_bucket_args(),
                "key": key,
                "version-id": before["VersionId"],
                "if-match": before["ETag"],
            },
            path,
        )
        _require(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= limit)
        raw = path.read_bytes()
    _require(len(raw) == before["ContentLength"])
    _require(all(metadata.get(field) == value for field, value in before.items()))
    _require(_head(aws, key, limit) == before)
    return before, raw


def _key(aws):
    """Resolve the real account-local alias without decryption or key creation."""
    key = aws(
        "kms", "describe-key", {"key-id": f"alias/pulumi-{PROJECT}-test-secrets"}
    )["KeyMetadata"]
    _require(
        key.get("KeyState") == "Enabled"
        and key.get("KeyUsage") == "ENCRYPT_DECRYPT"
        and key.get("KeyManager") == "CUSTOMER"
    )
    arn = key.get("Arn")
    _require(
        type(arn) is str
        and re.fullmatch(f"arn:aws:kms:{REGION}:{ACCOUNT}:key/[0-9a-f-]{{36}}", arn)
    )
    return arn


def _resource(row, urns):
    """Validate ownership coordinates and retain no resource input/output values."""
    urn = row.get("urn")
    _require(
        type(urn) is str
        and urn.startswith(f"urn:pulumi:test::{PROJECT}::")
        and urn not in urns
    )
    _require(not row.get("delete") and not row.get("pendingReplacement"))
    kind = row.get("type")
    _require(type(kind) is str and kind)
    if kind == "pulumi:providers:aws":
        inputs = row.get("inputs", {})
        accounts = inputs.get("allowedAccountIds")
        if type(accounts) is str:
            accounts = json.loads(accounts)
        _require(inputs.get("region") == REGION and accounts == [ACCOUNT])
    return {
        key: row.get(key)
        for key in ("urn", "type", "id", "parent", "provider", "custom", "external")
    }


def _inventory(raw):
    """Validate checkpoint and return separate public inventory/private rows."""
    document = _json(raw)
    _require(type(document.get("version")) is int and document["version"] == 3)
    checkpoint = document["checkpoint"]
    _require(checkpoint.get("stack") == f"organization/{PROJECT}/test")
    deployment = checkpoint["latest"]
    _require(deployment.get("pending_operations", []) == [])
    provider = deployment["secrets_providers"]
    _require(provider["type"] == "cloud" and provider["state"]["url"] == PROVIDER)
    _require(bool(base64.b64decode(provider["state"]["encryptedkey"], validate=True)))
    rows = deployment.get("resources", [])
    _require(type(rows) is list and len(rows) <= 10000)
    inventory, urns = [], set()
    for row in rows:
        item = _resource(row, urns)
        urns.add(item["urn"])
        inventory.append(item)
    inventory.sort(key=lambda row: row["urn"])
    baseline = all(
        row["type"] in ("pulumi:pulumi:Stack", "pulumi:providers:aws")
        for row in inventory
    )
    return {
        "resource_count": len(rows),
        "inventory_sha256": _digest(inventory),
        "baseline_inventory_only": baseline,
    }, rows


def capture_backend(source, *, aws=None, operation="plan") -> PrivateBackendCapture:
    """Return private rows only after all native end-of-observation rechecks."""
    aws = aws or aws_read
    _target(source, operation)
    caller = _caller(aws, operation)
    _require(
        aws("s3api", "get-bucket-versioning", _bucket_args()).get("Status") == "Enabled"
    )
    key_arn = _key(aws)
    meta_head, meta = _capture(aws, ".pulumi/meta.yaml", 4096)
    _require(re.fullmatch(rb"version: 1\s*", meta) is not None)
    _require(_list(aws, LOCKS) == [])
    listing = _list(aws, CHECKPOINT)
    _require(CHECKPOINT + ".gz" not in listing)
    state = {"kind": "observed_absence"}
    resources = []
    if CHECKPOINT in listing:
        head, raw = _capture(aws, CHECKPOINT, MAX_BYTES)
        inventory, resources = _inventory(raw)
        state = {
            "kind": "observed_checkpoint",
            **head,
            "sha256": _digest(raw),
            **inventory,
        }
        _require(_head(aws, CHECKPOINT, MAX_BYTES) == head)
    _require(_list(aws, CHECKPOINT) == listing and _list(aws, LOCKS) == [])
    _require(
        _head(aws, ".pulumi/meta.yaml", 4096) == meta_head and _key(aws) == key_arn
    )
    _require(_caller(aws, operation) == caller)
    _require(
        aws("s3api", "get-bucket-versioning", _bucket_args()).get("Status") == "Enabled"
    )
    summary = {
        "kind": "poc-backend-observation/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "account_id": ACCOUNT,
        "region": REGION,
        "bucket": BUCKET,
        "key": CHECKPOINT,
        "kms_key_arn": key_arn,
        "backend_metadata": meta_head,
        "source_contract_sha256": source["source"]["contract_sha256"],
        "state": state,
        "prior_authority": "not-evaluated",
    }

    return PrivateBackendCapture(summary=summary, resources=resources)


def observe_backend(source, *, aws=None):
    """Return authenticated observation facts, never initial/accepted authority."""
    return capture_backend(source, aws=aws).summary


def main(argv=None):
    """Authenticate source artifacts first and emit only fixed public summaries."""
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("artifact-id", "archive-sha256", "source-sha256"):
        parser.add_argument(f"--{field}", required=True)
    args = parser.parse_args(argv)
    try:
        source = source_artifact.load_verified_source(**vars(args))
        result = observe_backend(source)
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print("INVALID: backend observation failed", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
