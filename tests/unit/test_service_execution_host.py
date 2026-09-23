"""Launcher arguments, clean environment and immutable runtime preparation."""

import os
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_poc_registry_phase_entrypoint as phase_tests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import service_execution_host as host  # noqa: E402
import service_execution_worker as worker  # noqa: E402


@pytest.fixture
def installed(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    root = workspace / ".trusted"
    root.mkdir(parents=True)
    monkeypatch.setattr(host, "ROOT", root)
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_WORKFLOW_SHA", "a" * 40)
    for key in host.FIELDS[:4]:
        monkeypatch.setenv(key, "synthetic")
    for key, value in {
        "AWS_ACCOUNT_ID": host.backend.ACCOUNT,
        "AWS_REGION": host.backend.REGION,
        "PULUMI_BACKEND_URL": f"s3://{host.backend.BUCKET}",
        "PULUMI_SECRETS_PROVIDER": host.backend.PROVIDER,
        "AWS_PREVIEW_ROLE_ARN": (
            f"arn:aws:iam::{host.backend.ACCOUNT}:role/"
            f"GitHubCiPreview-{host.backend.PROJECT}-test"
        ),
        "AWS_APPLY_ROLE_ARN": (
            f"arn:aws:iam::{host.backend.ACCOUNT}:role/"
            f"GitHubCiApply-{host.backend.PROJECT}-test"
        ),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(host, "recheck", lambda: None)
    return workspace, root


def test_build_uses_only_installed_context_and_no_credentials(installed, monkeypatch):
    calls = []

    def run(argv, **options):
        calls.append((argv, options))
        return SimpleNamespace(stdout="a" * 40 + "\n")

    monkeypatch.setattr(host.subprocess, "run", run)
    host.build()
    assert len(calls) == 4
    for argv, options in calls:
        assert not set(host.FIELDS[:4]) & options["env"].keys()
        assert options["cwd"] == installed[1] and options["check"] is True
        assert Path(argv[0]).is_absolute()
    assert calls[-1][0][-1] == str(installed[1])
    assert calls[-1][0][-2].endswith("Dockerfile.service-execution")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/foreign")
    with pytest.raises(ValueError):
        host.build()
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setattr(
        host.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="b" * 40)
    )
    with pytest.raises(ValueError):
        host._trusted()


@pytest.mark.parametrize("job", tuple(sorted(host.JOBS)))
def test_launcher_has_exact_mounts_and_closed_environment(installed, monkeypatch, job):
    workspace, root = installed
    monkeypatch.setenv("GITHUB_JOB", job)
    for key in (
        "GITHUB_ENV",
        "GITHUB_OUTPUT",
        "GITHUB_PATH",
        "GITHUB_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "PYTHONPATH",
        "DOCKER_HOST",
    ):
        monkeypatch.setenv(key, "must-not-enter")
    monkeypatch.setattr(host, "_trusted", lambda: None)
    calls = []

    def run(argv, *, environment):
        calls.append((argv, environment))
        mounts = [
            argv[index + 1] for index, value in enumerate(argv) if value == "--mount"
        ]
        assert f"type=bind,src={root},dst=/trusted,readonly" in mounts
        assert len(mounts) == 2
        assert all("dst=/source" not in mount for mount in mounts)
        public = Path(
            next(value for value in mounts if value.endswith("dst=/public"))
            .split("src=", 1)[1]
            .split(",dst=")[0]
        )
        assert public.stat().st_mode & 0o777 == 0o700
        if job.endswith("_preview"):
            for name in ("pulumi-plan", "pulumi-preview"):
                (public / name).mkdir()
                (public / name / "result").write_bytes(b"synthetic")

    monkeypatch.setattr(host, "_run", run)
    host.execute()
    argv, environment = calls[0]
    assert argv[:8] == [
        "/usr/bin/docker",
        "run",
        "--rm",
        "--user",
        "0:0",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=3g",
    ]
    assert "--privileged" not in argv and "/var/run/docker.sock" not in str(argv)
    assert "no-new-privileges" in argv
    assert argv[-4:] == [
        "/opt/service-runtime/bin/python",
        "-I",
        "/trusted/scripts/service_execution_worker.py",
        job,
    ]
    role_key = host.backend._operation_identity(host.JOBS[job])[0]
    assert set(environment) <= {*host.FIELDS, role_key, "PATH"}
    assert environment[role_key] == os.environ[role_key]
    assert environment["PATH"] == host.PATH
    assert not any("must-not-enter" in value for value in environment.values())
    if job.endswith("_preview"):
        destination = root if job == "test_preview" else workspace
        assert (
            destination / ".artifacts/pulumi-plan/result"
        ).read_bytes() == b"synthetic"


def test_no_credentials_foreign_job_or_existing_export_fail(installed, monkeypatch):
    monkeypatch.setattr(host, "_trusted", lambda: None)
    monkeypatch.setenv("GITHUB_JOB", "foreign")
    with pytest.raises(ValueError):
        host.execute()
    monkeypatch.setenv("GITHUB_JOB", "test_preview")
    monkeypatch.delenv("GH_TOKEN")
    with pytest.raises(ValueError):
        host.execute()
    monkeypatch.setenv("GH_TOKEN", "synthetic")
    monkeypatch.setattr(host, "_run", lambda *_a, **_k: None)
    (installed[1] / ".artifacts/pulumi-plan").mkdir(parents=True)
    with pytest.raises(ValueError):
        host.execute()


def test_project_compatibility_checked_before_credentials(installed, monkeypatch):
    monkeypatch.setattr(host, "_trusted", lambda: None)
    workspace, _ = installed
    monkeypatch.setenv("GITHUB_JOB", "test_preview")
    host.prepare()
    project = workspace / "pulumi"
    project.mkdir()
    (project / "Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime: python\n"
    )
    monkeypatch.setenv("GITHUB_JOB", "prod_preview")
    with pytest.raises(ValueError):
        host.prepare()
    (project / "Pulumi.yaml").write_text("name: foreign\nruntime: nodejs\n")
    with pytest.raises(ValueError):
        host.prepare()


@pytest.mark.parametrize("command", ["build", "prepare", "recheck", "execute"])
def test_cli_redacts_failures(monkeypatch, capsys, command):
    calls = []
    monkeypatch.setattr(host, command, lambda: calls.append(command))
    assert host.main([command]) == 0 and calls == [command]
    monkeypatch.setattr(
        host, command, lambda: (_ for _ in ()).throw(ValueError("synthetic-private"))
    )
    assert host.main([command]) == 1
    assert (
        capsys.readouterr().err
        == "Service worker host failed its trusted prerequisites.\n"
    )


@pytest.mark.parametrize("fault", [None, "requester", "review", "base", "prod"])
def test_recheck_requires_current_requester_and_review(monkeypatch, fault):
    monkeypatch.setattr(host, "_trusted", lambda: None)
    monkeypatch.setenv("GITHUB_JOB", "test_apply")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("EXPECTED_BASE_SHA", ("c" if fault == "base" else "b") * 40)
    monkeypatch.setenv("GITHUB_REPOSITORY", "VilnaCRM-Org/user-service-infrastructure")
    request = {
        "target_environment": "prod" if fault == "prod" else "test",
        "head_sha": "a" * 40,
        "pull_request_number": "19",
    }
    calls = []
    monkeypatch.setattr(host.preflight, "read_request", lambda: request)

    def requester(actual):
        assert actual == request
        calls.append("requester")
        if fault == "requester":
            raise ValueError("revoked")

    def review(*args, **kwargs):
        assert args[1:] == ("19", "a" * 40, "b" * 40)
        calls.append("review")
        if fault == "review":
            raise ValueError("stale")

    monkeypatch.setattr(host.preflight, "revalidate_requester", requester)
    monkeypatch.setattr(host, "verify_reviewed_source", review)
    if fault is None:
        host.recheck()
        assert calls == ["requester", "review"]
    else:
        with pytest.raises(ValueError):
            host.recheck()


@pytest.mark.parametrize("job", tuple(sorted(host.JOBS)))
@pytest.mark.parametrize(
    "fault", [None, "missing", "role", "account", "prod", "worker"]
)
def test_role_metadata_crosses_real_host_worker_backend_seam(
    installed, monkeypatch, tmp_path, job, fault
):
    """Run real routing through backend coordinate checks to the native AWS seam."""
    contract = phase_tests.contract()
    source = {
        "source": asdict(phase_tests.source(contract)),
        "request": {"command": "up", "target_environment": "test"},
    }
    monkeypatch.setenv("GITHUB_JOB", job)
    monkeypatch.setenv("GITHUB_SHA", source["source"]["base_sha"])
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    for key in (
        "POC_SOURCE_ARTIFACT_ID",
        "POC_SOURCE_ARCHIVE_SHA256",
        "POC_SOURCE_SHA256",
    ):
        monkeypatch.setenv(key, "synthetic")
    role_key = host.backend._operation_identity(host.JOBS[job])[0]
    other_key = (
        "AWS_APPLY_ROLE_ARN"
        if role_key == "AWS_PREVIEW_ROLE_ARN"
        else "AWS_PREVIEW_ROLE_ARN"
    )
    monkeypatch.setenv(other_key, "must-not-enter")
    original_role = os.environ[role_key]
    if fault == "missing":
        monkeypatch.delenv(role_key)
    elif fault in ("role", "account", "prod"):
        replacements = {
            "role": ("GitHubCi", "Spoofed"),
            "account": (host.backend.ACCOUNT, "000000000000"),
            "prod": ("-test", "-prod"),
        }
        monkeypatch.setenv(role_key, original_role.replace(*replacements[fault]))
    monkeypatch.setattr(host, "_trusted", lambda: None)
    monkeypatch.setattr(worker, "admit", lambda _: source["source"]["head_sha"])
    monkeypatch.setattr(worker, "_replay_inputs", lambda *_: None)
    monkeypatch.setattr(
        worker, "ServiceTransport", lambda area, **_: SimpleNamespace(repo=area)
    )
    monkeypatch.setattr(worker.registry, "_trusted_root", lambda: None)
    monkeypatch.setattr(worker.registry, "_review", lambda _: None)
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (source, contract),
    )
    calls = []

    class NativeBoundaryReached(Exception):
        pass

    def aws(service, operation, arguments):
        assert (service, operation, arguments) == ("sts", "get-caller-identity", {})
        calls.append("native-sts")
        raise NativeBoundaryReached

    monkeypatch.setattr(host.backend, "aws_read", aws)

    def docker(argv, *, environment):
        calls.append("docker")
        forwarded = [
            argv[index + 1] for index, value in enumerate(argv) if value == "-e"
        ]
        assert set(forwarded) == set(environment)
        assert environment[role_key] == original_role
        assert other_key not in environment
        with monkeypatch.context() as child:
            for key in tuple(os.environ):
                child.delenv(key)
            for key, value in environment.items():
                child.setenv(key, value)
            if fault == "worker":
                child.setenv(role_key, original_role.replace("-test", "-prod"))
            worker.execute(argv[-1], tmp_path / "worker")

    monkeypatch.setattr(host, "_run", docker)
    if fault is None:
        with pytest.raises(NativeBoundaryReached):
            host.execute()
        assert calls == ["docker", "native-sts"]
    else:
        with pytest.raises(ValueError, match="Backend observation precondition failed"):
            host.execute()
        assert calls == (["docker"] if fault == "worker" else [])
