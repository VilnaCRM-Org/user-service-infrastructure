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
    monkeypatch.setattr(
        worker.scheduled, "verify_provenance", lambda: SimpleNamespace(sha="b" * 40)
    )
    return request, calls


def test_native_authority_reused_before_execution(authority):
    _, calls = authority
    assert worker.admit("test_apply") == "a" * 40
    assert calls == ["producer", "checkout", "requester", "review"]
    assert worker.admit("scheduled_prod_drift") == "b" * 40


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


def test_source_mount_and_checkout_are_exact(monkeypatch):
    monkeypatch.setattr(worker.os, "statvfs", lambda _: SimpleNamespace(f_flag=1))
    calls = []

    def run(argv, **options):
        calls.append((argv, options))
        return b"a" * 40 + b"\n" if "rev-parse" in argv else b""

    monkeypatch.setattr(worker, "run", run)
    worker.source_head("a" * 40)
    assert len(calls) == 3
    assert all(
        row[0][:5] == ["/usr/bin/git", "-c", "safe.directory=/source", "-C", "/source"]
        for row in calls
    )
    assert all(
        row[1]["env"] == {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}
        for row in calls
    )
    with pytest.raises(ValueError, match="source-head"):
        worker.source_head("c" * 40)
    monkeypatch.setattr(worker, "run", lambda *_a, **_k: b"a" * 40 + b"\n")
    with pytest.raises(ValueError, match="source-untracked"):
        worker.source_head("a" * 40)
    monkeypatch.setattr(worker.os, "statvfs", lambda _: SimpleNamespace(f_flag=0))
    with pytest.raises(ValueError, match="source-readonly"):
        worker.source_head("a" * 40)


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
    monkeypatch.setattr(worker.scheduled, "execute", execute)
    monkeypatch.setattr(worker, "_prod", lambda port, *_: execute(transport=port))
    monkeypatch.setattr(worker, "_replay_inputs", lambda *_: calls.append("replay"))
    copied = []
    monkeypatch.setattr(worker, "copy_tree", lambda *args: copied.append(args))
    worker.execute(job, tmp_path)
    assert calls[-3:] == ["execute", "admit", "admit"]
    assert ("replay" in calls) == (command == "up-plan")
    assert len(copied) == (2 if command == "plan" else 0)
    assert all(target.parent == Path("/public") for _, target in copied)


def test_failure_and_changed_final_head_cannot_publish(monkeypatch, tmp_path):
    coordinates(monkeypatch, "prod")
    monkeypatch.setenv("GITHUB_JOB", "prod_preview")
    monkeypatch.setattr(
        worker, "ServiceTransport", lambda *_, **__: SimpleNamespace(repo=tmp_path)
    )
    monkeypatch.setattr(worker, "admit", lambda _: "a" * 40)
    monkeypatch.setattr(worker, "_prod", lambda *_: 1)
    monkeypatch.setattr(
        worker, "copy_tree", lambda *_: pytest.fail("exported failed plan")
    )
    with pytest.raises(ValueError, match="worker-execution"):
        worker.execute("prod_preview", tmp_path)
    monkeypatch.setattr(worker, "_prod", lambda *_: 0)
    heads = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(worker, "admit", lambda _: next(heads))
    with pytest.raises(ValueError, match="worker-final-admission"):
        worker.execute("prod_preview", tmp_path)
    with pytest.raises(ValueError, match="worker-job"):
        worker.execute("foreign", tmp_path)
    monkeypatch.setenv("AWS_ACCOUNT_ID", "000000000000")
    with pytest.raises(ValueError, match="worker-coordinates"):
        worker._coordinates("prod")


def test_prod_uses_trusted_runner_with_original_provider_and_manifest(
    monkeypatch, tmp_path
):
    coordinates(monkeypatch, "prod")
    calls = []
    port = SimpleNamespace(
        repo=tmp_path,
        project=lambda source: calls.append(source) or tmp_path / "pulumi",
        bind=lambda context: context,
    )
    monkeypatch.setattr(worker, "source_head", lambda head: calls.append(head))

    def dispatch(command, context, stacks):
        assert command == "up-plan" and stacks == ["prod"]
        assert context.root_dir == tmp_path
        assert context.policy_pack_dir == Path("/source/policy")
        assert context.plan_dir == tmp_path / ".artifacts/pulumi-plan"
        assert context.env == {"PULUMI_COMMIT_SHA": "a" * 40}
        return 0

    monkeypatch.setattr(worker.registry.runner, "_dispatch_command", dispatch)
    assert worker._prod(port, "up-plan", "a" * 40) == 0
    assert calls == ["a" * 40, Path("/source/pulumi")]


@pytest.mark.parametrize("account", ["test", "prod"])
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
