"""Native read-only observation rejects missing authority and checkpoint races."""

import base64
import copy
import importlib
import json
import os
import subprocess
import sys

import pytest
import test_poc_source_artifact as source_tests

observer = importlib.import_module("poc_backend_observer")
prepared = source_tests.prepared


@pytest.mark.parametrize("operation", ["up", "destroy", "drift", "prod", "", None])
def test_capture_rejects_unknown_operation_before_aws(native, operation):
    with pytest.raises(ValueError):
        observer.capture_backend(
            native["source"], aws=native["aws"], operation=operation
        )
    assert native["calls"] == []


def test_apply_capture_requires_exact_apply_role_and_session(native, monkeypatch):
    monkeypatch.setenv(
        "AWS_APPLY_ROLE_ARN",
        f"arn:aws:iam::{observer.ACCOUNT}:role/GitHubCiApply-{observer.PROJECT}-test",
    )
    with pytest.raises(ValueError):
        observer.capture_backend(
            native["source"], aws=native["aws"], operation="up-plan"
        )
    native["caller"]["Arn"] = (
        native["caller"]["Arn"]
        .replace("GitHubCiPreview", "GitHubCiApply")
        .replace("test-preview-", "test-apply-")
    )
    captured = observer.capture_backend(
        native["source"], aws=native["aws"], operation="up-plan"
    )
    assert captured.summary["prior_authority"] == "not-evaluated"
    assert captured.resources
    with pytest.raises(ValueError):
        observer.capture_backend(native["source"], aws=native["aws"], operation="plan")


@pytest.fixture
def native(prepared, monkeypatch):
    for key, value in {
        "AWS_ACCOUNT_ID": observer.ACCOUNT,
        "AWS_REGION": observer.REGION,
        "AWS_PREVIEW_ROLE_ARN": (
            f"arn:aws:iam::{observer.ACCOUNT}:role/"
            f"GitHubCiPreview-{observer.PROJECT}-test"
        ),
        "PULUMI_BACKEND_URL": f"s3://{observer.BUCKET}",
        "PULUMI_SECRETS_PROVIDER": observer.PROVIDER,
    }.items():
        monkeypatch.setenv(key, value)
    prefix = f"urn:pulumi:test::{observer.PROJECT}::"
    deployment = {
        "pending_operations": [],
        "secrets_providers": {
            "type": "cloud",
            "state": {
                "url": observer.PROVIDER,
                "encryptedkey": base64.b64encode(b"SYNTHETIC_PRIVATE_KEY").decode(),
            },
        },
        "resources": [
            {
                "urn": prefix + "pulumi:pulumi:Stack::user-service-infrastructure-test",
                "type": "pulumi:pulumi:Stack",
                "outputs": {"secret": "PRIVATE_SENTINEL"},
            },
            {
                "urn": prefix + "pulumi:providers:aws::default_7_23_0",
                "type": "pulumi:providers:aws",
                "inputs": {
                    "region": observer.REGION,
                    "allowedAccountIds": json.dumps([observer.ACCOUNT]),
                },
            },
        ],
    }
    document = {
        "version": 3,
        "checkpoint": {
            "stack": f"organization/{observer.PROJECT}/test",
            "latest": deployment,
        },
    }
    objects = {
        ".pulumi/meta.yaml": b"version: 1\n",
        observer.CHECKPOINT: json.dumps(document).encode(),
    }
    key = {
        "Arn": f"arn:aws:kms:{observer.REGION}:{observer.ACCOUNT}:key/" + "1" * 36,
        "KeyState": "Enabled",
        "KeyUsage": "ENCRYPT_DECRYPT",
        "KeyManager": "CUSTOMER",
    }
    caller = {
        "Account": observer.ACCOUNT,
        "Arn": (
            f"arn:aws:sts::{observer.ACCOUNT}:assumed-role/"
            f"GitHubCiPreview-{observer.PROJECT}-test/gha-pr-test-preview-101"
        ),
    }
    calls = []

    def aws(service, operation, arguments, output=None):
        calls.append((service, operation, arguments.copy()))
        if service == "sts":
            return copy.deepcopy(caller)
        if service == "kms":
            assert arguments == {
                "key-id": f"alias/pulumi-{observer.PROJECT}-test-secrets"
            }
            return {"KeyMetadata": copy.deepcopy(key)}
        assert arguments["bucket"] == observer.BUCKET
        assert arguments["expected-bucket-owner"] == observer.ACCOUNT
        if operation == "get-bucket-versioning":
            return {"Status": "Enabled"}
        if operation == "list-objects-v2":
            return {
                "IsTruncated": False,
                "Contents": [
                    {"Key": key}
                    for key in sorted(objects)
                    if key.startswith(arguments["prefix"])
                ],
            }
        assert operation in ("head-object", "get-object")
        body = objects[arguments["key"]]
        head = {
            "VersionId": "version-1",
            "ETag": '"opaque-etag"',
            "ContentLength": len(body),
            "ServerSideEncryption": "AES256",
        }
        if operation == "get-object":
            assert arguments["version-id"] == "version-1"
            assert arguments["if-match"] == head["ETag"]
            assert output.stat().st_mode & 0o777 == 0o600
            assert output.parent.stat().st_mode & 0o777 == 0o700
            output.write_bytes(body)
        return head

    return {
        "source": prepared["source"],
        "objects": objects,
        "document": document,
        "key": key,
        "caller": caller,
        "calls": calls,
        "aws": aws,
        "prepared": prepared,
    }


def observe(native, aws=None):
    return observer.observe_backend(native["source"], aws=aws or native["aws"])


def update_checkpoint(native):
    native["objects"][observer.CHECKPOINT] = json.dumps(native["document"]).encode()


def test_existing_baseline_is_not_initial_authority(native):
    result = observe(native)
    assert result["state"]["kind"] == "observed_checkpoint"
    assert result["state"]["baseline_inventory_only"] is True
    assert result["state"]["resource_count"] == 2
    assert result["state"]["sha256"] == observer._digest(
        native["objects"][observer.CHECKPOINT]
    )
    assert result["prior_authority"] == "not-evaluated"
    assert "PRIVATE" not in json.dumps(result)
    assert not any("put" in call[1] or "decrypt" in call[1] for call in native["calls"])


def test_existing_workload_is_observed_without_claiming_phase(native):
    rows = native["document"]["checkpoint"]["latest"]["resources"]
    rows.append(
        {
            "urn": f"urn:pulumi:test::{observer.PROJECT}::aws:ecs/service:Service::web",
            "type": "aws:ecs/service:Service",
            "custom": True,
        }
    )
    update_checkpoint(native)
    result = observe(native)
    assert result["state"]["baseline_inventory_only"] is False
    assert result["state"]["resource_count"] == 3
    assert result["prior_authority"] == "not-evaluated"


def test_absence_requires_successful_complete_native_listing(native):
    del native["objects"][observer.CHECKPOINT]
    result = observe(native)
    assert result["state"] == {"kind": "observed_absence"}
    assert result["prior_authority"] == "not-evaluated"
    assert not any(c[2].get("key") == observer.CHECKPOINT for c in native["calls"])


@pytest.mark.parametrize(
    "operation",
    ["get-bucket-versioning", "list-objects-v2", "head-object", "get-object"],
)
def test_access_denied_and_missing_proof_are_never_empty(native, operation):
    def denied(service, action, args, output=None):
        if action == operation:
            raise ValueError("AccessDenied PRIVATE_SENTINEL")
        return native["aws"](service, action, args, output)

    with pytest.raises(ValueError):
        observe(native, denied)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda n: n["caller"].update(Account="933245420672"),
        lambda n: n["caller"].update(Arn=f"arn:aws:iam::{observer.ACCOUNT}:root"),
        lambda n: n["caller"].update(
            Arn=n["caller"]["Arn"].replace("preview-101", "preview-102")
        ),
        lambda n: n["key"].update(KeyState="Disabled"),
        lambda n: n["key"].update(
            Arn=n["key"]["Arn"].replace(observer.ACCOUNT, "933245420672")
        ),
        lambda n: n["objects"].update({".pulumi/meta.yaml": b"version: 0\n"}),
        lambda n: n["objects"].update({observer.LOCKS + "lock.json": b"private"}),
        lambda n: n["objects"].update({observer.CHECKPOINT + ".gz": b"compressed"}),
    ],
)
def test_native_target_layout_lock_and_kms_reject(native, mutation):
    mutation(native)
    with pytest.raises(ValueError):
        observe(native)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(version=4),
        lambda d: d["checkpoint"].update(stack="organization/foreign/test"),
        lambda d: d["checkpoint"]["latest"].update(pending_operations=[{}]),
        lambda d: d["checkpoint"]["latest"]["secrets_providers"]["state"].update(
            url="awskms://foreign"
        ),
        lambda d: d["checkpoint"]["latest"]["secrets_providers"]["state"].update(
            encryptedkey="!"
        ),
        lambda d: d["checkpoint"]["latest"]["resources"][0].update(delete=True),
        lambda d: d["checkpoint"]["latest"]["resources"][0].update(
            urn="urn:pulumi:prod::foreign::x::x"
        ),
        lambda d: d["checkpoint"]["latest"]["resources"][1]["inputs"].update(
            allowedAccountIds='["933245420672"]'
        ),
        lambda d: d["checkpoint"]["latest"]["resources"].append(
            d["checkpoint"]["latest"]["resources"][0]
        ),
    ],
)
def test_private_checkpoint_constraints(native, mutation):
    mutation(native["document"])
    update_checkpoint(native)
    with pytest.raises(ValueError):
        observe(native)


@pytest.mark.parametrize(
    "field,value",
    [
        ("VersionId", "null"),
        ("ContentLength", 0),
        ("ContentLength", observer.MAX_BYTES + 1),
        ("ETag", ""),
        ("ServerSideEncryption", None),
        ("SSEKMSKeyId", "foreign"),
        ("DeleteMarker", True),
    ],
)
def test_head_requires_version_bounds_and_real_encryption(native, field, value):
    def changed(service, operation, args, output=None):
        result = native["aws"](service, operation, args, output)
        if operation == "head-object":
            result[field] = value
        return result

    with pytest.raises(ValueError):
        observe(native, changed)


def test_pointer_move_and_get_identity_mismatch_reject(native):
    reads = 0

    def changed(service, operation, args, output=None):
        nonlocal reads
        result = native["aws"](service, operation, args, output)
        if operation == "head-object":
            reads += 1
            if reads > 1:
                result["VersionId"] = "new-version"
        return result

    with pytest.raises(ValueError):
        observe(native, changed)

    def wrong_get(service, operation, args, output=None):
        result = native["aws"](service, operation, args, output)
        if operation == "get-object":
            result["ETag"] = '"foreign"'
        return result

    with pytest.raises(ValueError):
        observe(native, wrong_get)


def test_sse_kms_separate_from_pulumi_key(native):
    def encrypted(service, operation, args, output=None):
        result = native["aws"](service, operation, args, output)
        if operation in ("head-object", "get-object"):
            result.update(
                ServerSideEncryption="aws:kms", SSEKMSKeyId=native["key"]["Arn"]
            )
        return result

    assert observe(native, encrypted)["state"]["ServerSideEncryption"] == "aws:kms"


def test_complete_pagination_and_repeated_tokens(native):
    pages = iter(
        [
            {
                "IsTruncated": True,
                "Contents": [{"Key": "prefix/one"}],
                "NextContinuationToken": "next",
            },
            {"IsTruncated": False, "Contents": [{"Key": "prefix/two"}]},
        ]
    )
    assert observer._list(lambda *args: next(pages), "prefix/") == [
        "prefix/one",
        "prefix/two",
    ]
    with pytest.raises(ValueError):
        observer._list(
            lambda *args: {"IsTruncated": True, "NextContinuationToken": "same"},
            "prefix/",
        )
    count = 0

    def endless(*args):
        nonlocal count
        count += 1
        return {"IsTruncated": True, "NextContinuationToken": str(count)}

    with pytest.raises(ValueError):
        observer._list(endless, "prefix/")


def test_loader_target_must_be_present_and_exact(native, monkeypatch):
    monkeypatch.delenv("PULUMI_BACKEND_URL")
    with pytest.raises(ValueError):
        observe(native, lambda *args: pytest.fail("No AWS before target validation"))


def test_cli_failure_redacts_source_and_aws_errors(native, monkeypatch, capsys):
    monkeypatch.setattr(
        observer.source_artifact, "load_verified_source", lambda **_: native["source"]
    )
    monkeypatch.setattr(
        observer,
        "aws_read",
        lambda *args: (_ for _ in ()).throw(ValueError("PRIVATE_SENTINEL")),
    )
    args = [
        "--artifact-id",
        "102",
        "--archive-sha256",
        "a" * 64,
        "--source-sha256",
        "b" * 64,
    ]
    assert observer.main(args) == 1
    result = capsys.readouterr()
    assert result.out == "" and result.err == "INVALID: backend observation failed\n"


@pytest.fixture
def native_cli(native, tmp_path, monkeypatch):
    """Provide local protocol-faithful gh/aws executables; no service is contacted."""
    data = tmp_path / "public-fixtures"
    data.mkdir()
    prepared = native["prepared"]
    for name, value in (("run", prepared["run"]), ("artifact", prepared["metadata"])):
        (data / name).write_text(json.dumps(value))
    (data / "archive").write_bytes(prepared["raw"])
    gh = tmp_path / "gh"
    gh.write_text(
        '#!/bin/sh\ncase "$2" in\n'
        f"  */runs/101) cat '{data / 'run'}';;\n"
        f"  */artifacts/102) cat '{data / 'artifact'}';;\n"
        f"  */artifacts/102/zip) cat '{data / 'archive'}';;\n"
        "  *) exit 1;;\nesac\n"
    )
    gh.chmod(0o700)
    fixture = {
        "caller": native["caller"],
        "key": native["key"],
        "objects": {
            key: base64.b64encode(raw).decode()
            for key, raw in native["objects"].items()
        },
    }
    (data / "aws.json").write_text(json.dumps(fixture))
    aws = tmp_path / "aws"
    aws.write_text(
        f"#!{sys.executable} -I\n"
        + f"DATA = {str(data / 'aws.json')!r}\n"
        + """
import base64, json, pathlib, sys
fixture = json.loads(pathlib.Path(DATA).read_text())
service, operation = sys.argv[1:3]
args, index = {}, 3
while index < len(sys.argv):
    key = sys.argv[index]
    if key in ('--no-cli-pager', '--no-paginate'):
        index += 1
    elif key.startswith('--'):
        args[key[2:]] = sys.argv[index + 1]
        index += 2
    else:
        output = key
        index += 1
if service == 'sts':
    result = fixture['caller']
elif service == 'kms':
    result = {'KeyMetadata': fixture['key']}
elif operation == 'get-bucket-versioning':
    result = {'Status': 'Enabled'}
elif operation == 'list-objects-v2':
    result = {'IsTruncated': False, 'Contents': [
        {'Key': key} for key in fixture['objects'] if key.startswith(args['prefix'])]}
else:
    raw = base64.b64decode(fixture['objects'][args['key']])
    result = {'VersionId': 'version-1', 'ETag': '"opaque-etag"',
              'ContentLength': len(raw), 'ServerSideEncryption': 'AES256'}
    if operation == 'get-object':
        assert args['version-id'] == 'version-1'
        assert args['if-match'] == result['ETag']
        pathlib.Path(output).write_bytes(raw)
print(json.dumps(result))
"""
    )
    aws.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    return native, tmp_path, data


def test_real_aws_transport_without_network(native_cli):
    native, _, _ = native_cli
    result = observer.observe_backend(native["source"])
    assert result["state"]["resource_count"] == 2
    with pytest.raises(ValueError):
        observer.aws_read("s3api", "put-object", {})


def test_isolated_cli_full_authenticated_path(native_cli):
    native, directory, data = native_cli
    prepared = native["prepared"]
    marker = directory / "pr-imported"
    for name in ("json.py", "sitecustomize.py"):
        (directory / name).write_text(
            f"open({str(marker)!r}, 'w').close()\nraise RuntimeError('PR code')\n"
        )
    environment = {**os.environ, "PYTHONPATH": str(directory)}
    command = [
        sys.executable,
        "-I",
        observer.__file__,
        "--artifact-id",
        "102",
        "--archive-sha256",
        source_tests.digest(prepared["raw"]),
        "--source-sha256",
        source_tests.digest(prepared["payload"]),
    ]
    result = subprocess.run(
        command,
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["prior_authority"] == "not-evaluated"
    assert "PRIVATE" not in result.stdout and not marker.exists()
    fixture = json.loads((data / "aws.json").read_text())
    fixture["caller"]["Account"] = "933245420672"
    (data / "aws.json").write_text(json.dumps(fixture))
    result = subprocess.run(
        command,
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == "INVALID: backend observation failed\n"
    result = subprocess.run(
        command[:3],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0 and result.stdout == ""
    assert not marker.exists()


def test_list_account_pin_and_main_success(native, monkeypatch, capsys):
    inputs = native["document"]["checkpoint"]["latest"]["resources"][1]["inputs"]
    inputs["allowedAccountIds"] = [observer.ACCOUNT]
    update_checkpoint(native)
    monkeypatch.setattr(
        observer.source_artifact, "load_verified_source", lambda **_: native["source"]
    )
    monkeypatch.setattr(observer, "aws_read", native["aws"])
    args = [
        "--artifact-id",
        "102",
        "--archive-sha256",
        "a" * 64,
        "--source-sha256",
        "b" * 64,
    ]
    assert observer.main(args) == 0
    result = capsys.readouterr()
    assert json.loads(result.out)["state"]["kind"] == "observed_checkpoint"
    assert result.err == "" and "PRIVATE" not in result.out


def test_failed_native_transport_kills_child(monkeypatch):
    from types import SimpleNamespace

    events = []

    class Process:
        def __enter__(self):
            return SimpleNamespace(
                poll=lambda: None,
                kill=lambda: events.append("kill"),
                wait=lambda **_: events.append("wait"),
            )

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(observer.subprocess, "Popen", lambda *args, **kwargs: Process())
    monkeypatch.setattr(
        observer, "_stream", lambda _: (_ for _ in ()).throw(ValueError("PRIVATE"))
    )
    with pytest.raises(ValueError):
        observer.aws_read("sts", "get-caller-identity", {})
    assert events == ["kill", "wait"]


def test_stream_wait_timeout_and_output_bound(monkeypatch):
    from types import SimpleNamespace

    calls = []

    class Selector:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def register(self, *args):
            pass

        def select(self, **kwargs):
            calls.append(True)
            return len(calls) > 1

    monkeypatch.setattr(observer.selectors, "DefaultSelector", Selector)
    process = SimpleNamespace(
        stdout=SimpleNamespace(fileno=lambda: 17), wait=lambda **_: 0
    )
    moments = iter([0, 0, 121])
    monkeypatch.setattr(observer.time, "monotonic", lambda: next(moments))
    with pytest.raises(ValueError):
        observer._stream(process)
    monkeypatch.setattr(observer.time, "monotonic", lambda: 0)
    monkeypatch.setattr(observer.os, "read", lambda *_: b"oversized")
    monkeypatch.setattr(observer, "MAX_METADATA", 1)
    with pytest.raises(ValueError):
        observer._stream(process)


def test_private_capture_returns_exact_rows_without_second_fetch(native):
    result = observer.capture_backend(native["source"], aws=native["aws"])
    assert type(result) is observer.PrivateBackendCapture
    assert result.resources == native["document"]["checkpoint"]["latest"]["resources"]
    assert result.resources[0]["outputs"]["secret"] == "PRIVATE_SENTINEL"
    assert "PRIVATE" not in repr(result)
    assert "resources" not in result.summary
    assert "PRIVATE" not in json.dumps(result.summary)
    assert result.summary["state"]["resource_count"] == len(result.resources)
    gets = [args for _, op, args in native["calls"] if op == "get-object"]
    assert [args["key"] for args in gets] == [".pulumi/meta.yaml", observer.CHECKPOINT]
    assert gets[1]["version-id"] == result.summary["state"]["VersionId"]
    assert gets[1]["if-match"] == result.summary["state"]["ETag"]


def test_private_capture_absence_is_not_initial_authority(native):
    del native["objects"][observer.CHECKPOINT]
    result = observer.capture_backend(native["source"], aws=native["aws"])
    assert result.resources == []
    assert result.summary["state"] == {"kind": "observed_absence"}
    assert result.summary["prior_authority"] == "not-evaluated"


@pytest.mark.parametrize(
    "late_operation", ["get-caller-identity", "get-bucket-versioning"]
)
def test_private_capture_is_not_constructed_before_final_rechecks(
    native, monkeypatch, late_operation
):
    captures, calls = [], []
    monkeypatch.setattr(
        observer, "PrivateBackendCapture", lambda **kw: captures.append(kw)
    )

    def late_failure(service, operation, arguments, output=None):
        calls.append(operation)
        result = native["aws"](service, operation, arguments, output)
        if operation == late_operation and calls.count(operation) == 2:
            return {}
        return result

    with pytest.raises(ValueError, match="Backend observation precondition failed"):
        observer.capture_backend(native["source"], aws=late_failure)
    assert any(args.get("key") == observer.CHECKPOINT for _, _, args in native["calls"])
    assert captures == []


def test_private_capture_keeps_inventory_rejection_mandatory(native):
    native["document"]["checkpoint"]["latest"]["pending_operations"] = [{}]
    update_checkpoint(native)
    with pytest.raises(ValueError, match="Backend observation precondition failed"):
        observer.capture_backend(native["source"], aws=native["aws"])
