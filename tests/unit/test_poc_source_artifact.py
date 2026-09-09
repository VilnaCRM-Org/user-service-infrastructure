"""Authenticated same-run artifact and isolated CLI adversarial regressions."""

import copy
import hashlib
import importlib
import io
import json
import os
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
artifact = importlib.import_module("poc_source_artifact")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def zip_bytes(payload, name="source.json", mode=stat.S_IFREG | 0o600, duplicate=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        entry = zipfile.ZipInfo(name)
        entry.external_attr = mode << 16
        archive.writestr(entry, payload)
        if duplicate:
            with pytest.warns(UserWarning):
                archive.writestr(entry, payload)
    return stream.getvalue()


@pytest.fixture
def prepared(monkeypatch):
    sha = "a" * 40
    environment = {
        "GITHUB_EVENT_NAME": "repository_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": artifact.REPOSITORY,
        "GITHUB_REPOSITORY_ID": "911736693",
        "GITHUB_REPOSITORY_OWNER_ID": "114362548",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "101",
        "GITHUB_SHA": sha,
        "GITHUB_WORKFLOW_SHA": sha,
        "GITHUB_WORKFLOW_REF": (
            f"{artifact.REPOSITORY}/{artifact.WORKFLOW}@refs/heads/main"
        ),
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    source = {
        "kind": "poc-phase-source/v1",
        "request": {
            "pull_request_number": "19",
            "head_sha": "b" * 40,
            "comment_id": "12",
            "source_run_id": "13",
            "command": "plan",
            "target_environment": "test",
        },
        "review": {
            "head_sha": "b" * 40,
            "base_sha": "c" * 40,
            "review_id": "PRR_review",
            "reviewer_id": "U_writer",
            "reviewer_login": "reviewer",
            "review_protection_sha256": "d" * 64,
        },
        "source": {
            "head_sha": "b" * 40,
            "base_sha": "c" * 40,
            "contract_sha256": "e" * 64,
            "blob_sha": "f" * 40,
            "path": artifact.admission.CONTRACT_PATH,
            "schema_sha256": digest(artifact.poc_contract.SCHEMA_PATH.read_bytes()),
            "validator_sha256": digest(
                Path(artifact.poc_contract.__file__).read_bytes()
            ),
        },
    }
    repository = {
        "id": 911736693,
        "full_name": artifact.REPOSITORY,
        "owner": {"id": 114362548},
    }
    run = {
        "id": 101,
        "run_attempt": 1,
        "event": "repository_dispatch",
        "path": artifact.WORKFLOW,
        "head_branch": "main",
        "head_sha": sha,
        "status": "in_progress",
        "conclusion": None,
        "repository": repository,
        "head_repository": copy.deepcopy(repository),
    }
    payload = json.dumps(source).encode()
    raw = zip_bytes(payload)
    now = datetime.now(timezone.utc)
    metadata = {
        "id": 102,
        "name": "poc-phase-source-101-1",
        "expired": False,
        "digest": f"sha256:{digest(raw)}",
        "size_in_bytes": len(raw),
        "created_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "workflow_run": {
            "id": 101,
            "repository_id": 911736693,
            "head_repository_id": 911736693,
            "head_branch": "main",
            "head_sha": sha,
        },
    }
    return {
        "source": source,
        "run": run,
        "metadata": metadata,
        "payload": payload,
        "raw": raw,
        "environment": environment,
    }


def invoke(prepared, monkeypatch, *, raw=None, gh=None):
    raw = prepared["raw"] if raw is None else raw

    def read(endpoint):
        if endpoint == f"{artifact.API}/actions/runs/101":
            return prepared["run"]
        assert endpoint == f"{artifact.API}/actions/artifacts/102"
        return prepared["metadata"]

    monkeypatch.setattr(artifact.preflight, "gh", gh or read)
    monkeypatch.setattr(artifact, "_download_zip", lambda identifier: raw)
    return artifact.load_verified_source(
        artifact_id="102",
        archive_sha256=digest(prepared["raw"]),
        source_sha256=digest(prepared["payload"]),
    )


def test_same_run_source_facts_only(prepared, monkeypatch):
    assert invoke(prepared, monkeypatch) == prepared["source"]
    assert prepared["source"]["request"]["source_run_id"] != "101"


@pytest.mark.parametrize(
    "path,value",
    [
        (("run", "id"), 103),
        (("run", "run_attempt"), 2),
        (("run", "path"), ".github/workflows/foreign.yml"),
        (("run", "head_sha"), "0" * 40),
        (("run", "head_branch"), "feature"),
        (("run", "event"), "pull_request"),
        (("run", "status"), "completed"),
        (("run", "repository", "id"), 1),
        (("run", "head_repository", "owner", "id"), 1),
        (("metadata", "workflow_run", "id"), 103),
        (("metadata", "workflow_run", "head_repository_id"), 1),
        (("metadata", "id"), True),
        (("metadata", "expired"), True),
        (("metadata", "name"), "poc-phase-source-103-1"),
        (("metadata", "digest"), "sha256:" + "0" * 64),
        (("metadata", "size_in_bytes"), 0),
        (("metadata", "size_in_bytes"), artifact.MAX_ZIP_BYTES + 1),
        (("metadata", "expires_at"), "2000-01-01T00:00:00Z"),
        (("metadata", "expires_at"), "2099-01-01T00:00:00"),
        (("metadata", "created_at"), "2099-01-01T00:00:00Z"),
        (("metadata", "expires_at"), None),
    ],
)
def test_authenticated_api_identity_failures(prepared, monkeypatch, path, value):
    target = prepared
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        invoke(prepared, monkeypatch)


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("GITHUB_RUN_ID", "../other"),
        ("GITHUB_SHA", "x"),
        ("GITHUB_WORKFLOW_SHA", "0" * 40),
        ("GITHUB_REPOSITORY_ID", "1"),
        ("GITHUB_REF", "refs/heads/feature"),
    ],
)
def test_context_rejects_before_external_reads(prepared, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        invoke(prepared, monkeypatch, gh=lambda _: pytest.fail("No API allowed"))


@pytest.mark.parametrize(
    "name,mode,duplicate",
    [
        ("../source.json", stat.S_IFREG, False),
        ("/source.json", stat.S_IFREG, False),
        ("source.json/", stat.S_IFDIR, False),
        ("source.json", stat.S_IFLNK, False),
        ("source.json", stat.S_IFREG, True),
        ("source.json\\other", stat.S_IFREG, False),
    ],
)
def test_zip_attack_rejected_with_correct_digest(
    prepared, monkeypatch, name, mode, duplicate
):
    prepared["raw"] = zip_bytes(prepared["payload"], name, mode, duplicate)
    prepared["metadata"]["digest"] = f"sha256:{digest(prepared['raw'])}"
    with pytest.raises(ValueError):
        invoke(prepared, monkeypatch)


def test_raw_archive_and_member_digest_both_required(prepared, monkeypatch):
    with pytest.raises(ValueError):
        invoke(prepared, monkeypatch, raw=prepared["raw"] + b"different")
    prepared["raw"] = zip_bytes(b"{}")
    prepared["metadata"]["digest"] = f"sha256:{digest(prepared['raw'])}"
    with pytest.raises(ValueError):
        invoke(prepared, monkeypatch)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(prior={}),
        lambda p: p.update(kind="poc-phase-admission/v1"),
        lambda p: p["source"].update(phase="registry"),
        lambda p: p["source"].update(head_sha="0" * 40),
        lambda p: p["review"].update(base_sha="0" * 40),
        lambda p: p["source"].update(schema_sha256="0" * 64),
        lambda p: p["source"].update(validator_sha256="0" * 64),
        lambda p: p["request"].update(comment_id=True),
    ],
)
def test_source_fields_closed_and_installed_pins(prepared, mutation):
    mutation(prepared["source"])
    with pytest.raises(ValueError):
        artifact._decode(json.dumps(prepared["source"]).encode())


def test_json_and_zip_bounds(prepared, monkeypatch):
    with pytest.raises(ValueError):
        artifact._decode(b'{"kind":1,"kind":2}')
    for raw in (
        b"",
        b"x" * (artifact.MAX_ZIP_BYTES + 1),
        zip_bytes(b"x" * (artifact.MAX_SOURCE_BYTES + 1)),
    ):
        with pytest.raises(ValueError):
            artifact._payload(raw)
    monkeypatch.setattr(artifact, "MAX_SOURCE_BYTES", 1)
    with pytest.raises(ValueError):
        artifact._payload(prepared["raw"])


def test_expiry_rechecked_after_download(prepared, monkeypatch):
    reads = 0

    def gh(endpoint):
        nonlocal reads
        if endpoint.endswith("runs/101"):
            return prepared["run"]
        reads += 1
        if reads == 2:
            prepared["metadata"]["expired"] = True
        return prepared["metadata"]

    with pytest.raises(ValueError):
        invoke(prepared, monkeypatch, gh=gh)


def test_main_success_and_redacted_failure(prepared, monkeypatch, capsys):
    invoke(prepared, monkeypatch)
    args = [
        "--artifact-id",
        "102",
        "--archive-sha256",
        digest(prepared["raw"]),
        "--source-sha256",
        digest(prepared["payload"]),
    ]
    assert artifact.main(args) == 0
    assert json.loads(capsys.readouterr().out) == prepared["source"]
    monkeypatch.setattr(
        artifact.preflight, "gh", lambda _: (_ for _ in ()).throw(ValueError("PRIVATE"))
    )
    assert artifact.main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INVALID: source artifact verification failed\n"


def test_actual_isolated_cli_authenticates_fake_transport(prepared, tmp_path):
    """Run the real CLI/gh stream from hostile PR cwd, without network or AWS."""
    data = tmp_path / "data"
    data.mkdir()
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
    marker = tmp_path / "untrusted-import"
    for name in ("json.py", "sitecustomize.py"):
        (tmp_path / name).write_text(
            f"open({str(marker)!r}, 'w').close()\nraise RuntimeError('PR code')\n"
        )
    environment = {
        **os.environ,
        **prepared["environment"],
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PYTHONPATH": str(tmp_path),
    }
    command = [
        sys.executable,
        "-I",
        artifact.__file__,
        "--artifact-id",
        "102",
        "--archive-sha256",
        digest(prepared["raw"]),
        "--source-sha256",
        digest(prepared["payload"]),
    ]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == prepared["source"]
    assert not marker.exists()
    prepared["run"]["id"] = 999
    (data / "run").write_text(json.dumps(prepared["run"]))
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == "INVALID: source artifact verification failed\n"
    result = subprocess.run(
        command[:3],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0 and result.stdout == ""
    assert not marker.exists()


@pytest.mark.parametrize("failure", [None, "missing", "status", "overflow", "timeout"])
def test_bounded_stream_cleanup(monkeypatch, failure):
    """Exercise the real downloader's limits and cleanup without external calls."""
    from types import SimpleNamespace

    events = []
    stream = SimpleNamespace(fileno=lambda: 17, close=lambda: events.append("close"))
    process = SimpleNamespace(
        stdout=None if failure == "missing" else stream,
        wait=lambda **_: 1 if failure == "status" else 0,
        poll=lambda: 0 if failure is None else None,
        kill=lambda: events.append("kill"),
    )

    def popen(argv, **kwargs):
        assert argv == ["gh", "api", f"{artifact.API}/actions/artifacts/102/zip"]
        assert kwargs["stderr"] == subprocess.DEVNULL
        return process

    monkeypatch.setattr(artifact.subprocess, "Popen", popen)

    class Selector:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def register(self, value, event):
            assert value is stream and event == artifact.selectors.EVENT_READ

        def select(self, **kwargs):
            events.append("select")
            return len(events) > 1

    monkeypatch.setattr(artifact.selectors, "DefaultSelector", Selector)
    moments = iter([0, 121] if failure == "timeout" else [0] * 10)
    monkeypatch.setattr(artifact.time, "monotonic", lambda: next(moments))
    chunks = iter([b"abcdefgh" if failure == "overflow" else b"abc", b""])
    monkeypatch.setattr(artifact.os, "read", lambda *_: next(chunks))
    monkeypatch.setattr(artifact, "MAX_ZIP_BYTES", 7)
    if failure is None:
        assert artifact._download_zip("102") == b"abc"
    else:
        with pytest.raises(ValueError):
            artifact._download_zip("102")
        assert "kill" in events
    assert ("close" in events) == (failure != "missing")
