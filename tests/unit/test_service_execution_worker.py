"""Closed worker routing and fresh admission checks with simulated APIs."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import service_execution_worker as worker  # noqa: E402


@pytest.fixture
def authority(monkeypatch):
    calls = []
    request = {
        "head_sha": "a" * 40,
        "pull_request_number": "19",
        "command": "up",
        "target_environment": "test",
    }
    monkeypatch.setenv("EXPECTED_BASE_SHA", "b" * 40)
    monkeypatch.setattr(
        worker.registry.artifact, "_context", lambda _: ("123", "b" * 40)
    )
    monkeypatch.setattr(
        worker.registry.artifact, "_producer", lambda *_: calls.append("producer")
    )
    monkeypatch.setattr(
        worker.registry, "_verify_checkout", lambda *_: calls.append("checkout")
    )
    monkeypatch.setattr(worker.registry.preflight, "read_request", lambda: request)
    monkeypatch.setattr(
        worker.registry.preflight,
        "revalidate_requester",
        lambda _: calls.append("requester"),
    )
    monkeypatch.setattr(
        worker.registry,
        "verify_reviewed_source",
        lambda *_a, **_k: calls.append("review"),
    )
    return request, calls


def test_native_authority_reused_before_execution(authority):
    _, calls = authority
    assert worker.admit("test_apply") == "a" * 40
    assert calls == ["producer", "checkout", "requester", "review"]
    with pytest.raises(ValueError, match="worker-job"):
        worker.admit("scheduled_prod_drift")


@pytest.mark.parametrize("fault", ["base", "account", "command"])
def test_changed_authority_fails(authority, monkeypatch, fault):
    request, _ = authority
    if fault == "base":
        monkeypatch.setenv("EXPECTED_BASE_SHA", "c" * 40)
    elif fault == "account":
        request["target_environment"] = "prod"
    else:
        request["command"] = "plan"
    with pytest.raises(ValueError):
        worker.admit("test_apply")


def coordinates(monkeypatch, account):
    monkeypatch.setenv("AWS_ACCOUNT_ID", worker.ACCOUNTS[account])
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv(
        "PULUMI_BACKEND_URL", f"s3://pulumi-user-service-infrastructure-{account}-state"
    )
    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER",
        f"awskms://alias/pulumi-user-service-infrastructure-{account}-secrets?region=eu-central-1",
    )


@pytest.mark.parametrize("job", tuple(worker.JOBS))
def test_every_route_preserves_checks_and_exports_only_plan(monkeypatch, tmp_path, job):
    account, command = worker.JOBS[job]
    coordinates(monkeypatch, account)
    monkeypatch.setenv("GITHUB_JOB", job)
    for key in (
        *worker.SESSION_KEYS,
        "POC_SOURCE_ARTIFACT_ID",
        "POC_SOURCE_ARCHIVE_SHA256",
        "POC_SOURCE_SHA256",
    ):
        monkeypatch.setenv(key, "synthetic")
    calls = []
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (
            {
                "source": {"head_sha": "a" * 40, "base_sha": "b" * 40},
                "request": {"target_environment": "test"},
            },
            {"phase": "registry"},
        ),
    )
    monkeypatch.setattr(worker.registry, "_review", lambda _: None)
    monkeypatch.setattr(worker, "admit", lambda _: calls.append("admit") or "a" * 40)

    class Port:
        def __init__(self, area, **kwargs):
            assert calls == ["admit"]
            assert set(kwargs["session"]) == set(worker.SESSION_KEYS)
            self.repo = area
            self.before_program = kwargs["before_program"]
            calls.append("port")

    def execute(*_a, transport=None, **_k):
        calls.append("execute")
        transport.before_program()
        return 0

    monkeypatch.setattr(worker, "ServiceTransport", Port)
    monkeypatch.setattr(worker.registry, "execute", execute)
    monkeypatch.setattr(worker, "_replay_inputs", lambda *_: calls.append("replay"))
    copied = []
    monkeypatch.setattr(worker, "copy_tree", lambda *args: copied.append(args))
    worker.execute(job, tmp_path)
    assert calls[-3:] == ["execute", "admit", "admit"]
    assert ("replay" in calls) == (command == "up-plan")
    assert len(copied) == (2 if command == "plan" else 0)
    assert all(target.parent == Path("/public") for _, target in copied)


def test_workload_branch_reads_verified_source_and_cannot_fall_through(monkeypatch):
    for key in (
        "POC_SOURCE_ARTIFACT_ID",
        "POC_SOURCE_ARCHIVE_SHA256",
        "POC_SOURCE_SHA256",
    ):
        monkeypatch.setenv(key, "synthetic")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    source = {
        "source": {"head_sha": "a" * 40, "base_sha": "b" * 40},
        "request": {"target_environment": "test"},
    }
    contract = {"phase": "workload"}
    calls = []
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (source, contract),
    )
    monkeypatch.setattr(worker.registry, "_review", lambda _: calls.append("review"))
    monkeypatch.setattr(
        worker.registry,
        "execute",
        lambda *_a, **_k: pytest.fail("registry execution after workload admission"),
    )
    with pytest.raises(ValueError, match="workload-execution-not-enabled"):
        worker._test(None, "plan", "a" * 40)
    assert calls == ["review"]
    source["source"]["head_sha"] = "c" * 40
    with pytest.raises(ValueError, match="workload-source-binding"):
        worker._test(None, "plan", "a" * 40)


def test_failure_and_changed_final_head_cannot_publish(monkeypatch, tmp_path):
    coordinates(monkeypatch, "test")
    monkeypatch.setenv("GITHUB_JOB", "test_preview")
    monkeypatch.setattr(
        worker, "ServiceTransport", lambda *_, **__: SimpleNamespace(repo=tmp_path)
    )
    monkeypatch.setattr(worker, "admit", lambda _: "a" * 40)
    monkeypatch.setattr(worker, "_test", lambda *_: 1)
    monkeypatch.setattr(
        worker, "copy_tree", lambda *_: pytest.fail("exported failed plan")
    )
    with pytest.raises(ValueError, match="worker-execution"):
        worker.execute("test_preview", tmp_path)
    monkeypatch.setattr(worker, "_test", lambda *_: 0)
    heads = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(worker, "admit", lambda _: next(heads))
    with pytest.raises(ValueError, match="worker-final-admission"):
        worker.execute("test_preview", tmp_path)
    with pytest.raises(ValueError, match="worker-job"):
        worker.execute("foreign", tmp_path)
    monkeypatch.setenv("AWS_ACCOUNT_ID", "000000000000")
    with pytest.raises(ValueError, match="worker-coordinates"):
        worker._coordinates("test")


@pytest.mark.parametrize("account", ["test"])
def test_replay_copy_preserves_legacy_input_paths(monkeypatch, tmp_path, account):
    copied = []
    monkeypatch.setattr(worker, "copy_tree", lambda *args: copied.append(args))
    worker._replay_inputs(SimpleNamespace(repo=tmp_path), account)
    source = Path("/trusted" if account == "test" else "/source") / ".artifacts"
    assert copied == [
        (source / name, tmp_path / ".artifacts" / name)
        for name in ("pulumi-plan", "pulumi-preview")
    ]


@pytest.mark.parametrize("success", [True, False])
def test_entrypoint_redacts_private_output(monkeypatch, capsys, success):
    monkeypatch.setattr(worker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(worker.os, "getpid", lambda: 1)
    monkeypatch.setenv("PATH", "/opt/pulumi:/usr/local/bin:/usr/bin:/bin")

    def execute(job, area):
        assert job == "test_preview"
        assert (area / "private.log").stat().st_mode & 0o777 == 0o600
        assert Path(os.environ["HOME"]).stat().st_mode & 0o777 == 0o700
        print("synthetic-private-payload")
        print("synthetic-private-error", file=sys.stderr)
        if not success:
            raise ValueError("synthetic-private-exception")

    monkeypatch.setattr(worker, "execute", execute)
    assert worker.main(["test_preview"]) == (0 if success else 1)
    captured = capsys.readouterr()
    assert "synthetic-private" not in captured.out + captured.err
    monkeypatch.setattr(worker.os, "getpid", lambda: 2)
    assert worker.main(["test_preview"]) == 1
