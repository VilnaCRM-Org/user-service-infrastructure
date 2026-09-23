"""Simulated metadata and real file checks for the isolated service transport."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import service_execution_transport as transport  # noqa: E402
from _pulumi_command_support import CommandContext  # noqa: E402


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(transport.os, "geteuid", lambda: 0)
    monkeypatch.setattr(transport.os, "getpid", lambda: 1)
    monkeypatch.setattr(transport.os, "chown", lambda *_: None)
    monkeypatch.setattr(transport.os, "statvfs", lambda *_: SimpleNamespace(f_flag=1))
    original_stat = Path.stat

    def root_stat(path, *args, **kwargs):
        result = list(original_stat(path, *args, **kwargs))
        result[4] = 0
        return os.stat_result(result)

    monkeypatch.setattr(Path, "stat", root_stat)
    monkeypatch.setattr(transport, "PYTHON", str(tmp_path / "venv/bin/python"))
    (tmp_path / "venv/bin").mkdir(parents=True)
    area = tmp_path / "area"
    area.mkdir()
    calls = []
    port = transport.ServiceTransport(
        area,
        session={
            "AWS_ACCESS_KEY_ID": "synthetic",
            "AWS_SECRET_ACCESS_KEY": "synthetic",
            "AWS_SESSION_TOKEN": "synthetic",
        },
        region="eu-central-1",
        account="891377212104",
        before_program=lambda: calls.append("admission"),
    )
    return port, calls


@pytest.mark.parametrize(
    "runtime",
    [
        "python",
        {"name": "python"},
        {"name": "python", "options": {"virtualenv": ".venv"}},
    ],
)
def test_fixed_project_runtime(runtime):
    document = yaml.safe_load(
        transport.project_document(
            yaml.safe_dump(
                {
                    "name": "user-service-infrastructure",
                    "runtime": runtime,
                }
            ).encode()
        )
    )
    assert document["runtime"]["options"]["virtualenv"] == "/opt/service-runtime"


@pytest.mark.parametrize(
    "document",
    [
        [],
        {},
        {"name": "foreign", "runtime": "python"},
        {"name": "user-service-infrastructure", "runtime": "nodejs"},
        {
            "name": "user-service-infrastructure",
            "runtime": "python",
            "main": "/tmp/foreign",
        },
        {
            "name": "user-service-infrastructure",
            "runtime": {"name": "python", "options": {"virtualenv": "evil"}},
        },
    ],
)
def test_foreign_project_discovery_rejected(document):
    with pytest.raises(ValueError):
        transport.project_document(yaml.safe_dump(document).encode())
    with pytest.raises(yaml.YAMLError):
        transport.project_document(b"name: first\nname: second\n")


def test_public_tree_is_bounded_regular_and_nonwritable(tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    (source / "nested/module.py").write_bytes(b"public")
    destination = tmp_path / "copy"
    transport.copy_tree(source, destination)
    assert (destination / "nested/module.py").read_bytes() == b"public"
    assert (destination / "nested/module.py").stat().st_mode & 0o777 == 0o644
    (source / "escape").symlink_to("/tmp")
    with pytest.raises(ValueError):
        transport.copy_tree(source, tmp_path / "symlink")
    (source / "escape").unlink()
    monkeypatch.setattr(transport, "MAX_FILES", 1)
    with pytest.raises(ValueError):
        transport.copy_tree(source, tmp_path / "count")
    monkeypatch.setattr(transport, "MAX_FILES", 10)
    monkeypatch.setattr(transport, "MAX_TREE_BYTES", 1)
    with pytest.raises(ValueError):
        transport.copy_tree(source, tmp_path / "bytes")


def test_bound_context_reuses_schema_and_never_imports_policy(installed, tmp_path):
    port, _ = installed
    source = tmp_path / "source"
    source.mkdir()
    (source / "Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime: python\n"
    )
    (source / "__main__.py").write_text("raise AssertionError('must run as child')")
    project = port.project(source)
    policy = tmp_path / "policy"
    policy.mkdir()
    (policy / "PulumiPolicy.yaml").write_text(
        "runtime:\n  name: python\n  options:\n    virtualenv: .venv\n"
    )
    (policy / "__main__.py").write_text(
        "raise AssertionError('must not import as root')"
    )
    context = CommandContext(
        root_dir=tmp_path,
        env={
            "GH_TOKEN": "synthetic",
            "GITHUB_OUTPUT": "forbidden",
            "PULUMI_COMMIT_SHA": "a" * 40,
        },
        pulumi_dir=project,
        policy_pack_dir=policy,
        plan_dir=port.repo / ".artifacts/pulumi-plan",
        preview_artifact_dir=port.repo / ".artifacts/pulumi-preview",
        backend_url="s3://fixed",
        secrets_provider="awskms://fixed",
    )
    bound = port.bind(context)
    assert bound.root_dir == port.repo and bound.runner is port
    assert (
        not {"GH_TOKEN", "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_PATH"}
        & bound.env.keys()
    )
    assert bound.env["PULUMI_COMMIT_SHA"] == "a" * 40
    bound.prepare_policy_pack(bound)
    preview = tmp_path / "preview.json"
    preview.write_text(json.dumps({"changeSummary": {"same": 1}, "steps": []}))
    summary = tmp_path / "summary.md"
    bound.summarize_preview(preview, summary)
    assert "same" in summary.read_text()
    (bound.policy_pack_dir / ".venv").unlink()
    with pytest.raises(ValueError):
        bound.prepare_policy_pack(bound)


def test_invalid_policy_is_rejected_before_any_program(installed, tmp_path):
    port, calls = installed
    policy = tmp_path / "policy"
    policy.mkdir()
    (policy / "PulumiPolicy.yaml").write_text("runtime: nodejs\n")
    with pytest.raises(ValueError):
        port.bind(SimpleNamespace(policy_pack_dir=policy))
    assert calls == []


@pytest.mark.parametrize("operation", ["preview", "up", "stack", "login"])
def test_commands_protect_inputs_and_strip_host_authority(
    installed, tmp_path, monkeypatch, operation
):
    port, calls = installed
    config = tmp_path / "config.yaml"
    config.write_bytes(b"synthetic-config")
    plan = tmp_path / "original.plan"
    plan.write_bytes(b"synthetic-plan")
    saved = tmp_path / "created.plan"
    arguments = [
        "pulumi",
        "-C",
        str(port.repo / "pulumi"),
        operation,
        "--config-file",
        str(config),
        "--plan",
        str(plan),
    ]
    if operation == "preview":
        arguments += ["--save-plan", str(saved)]

    def run(argv, *, env, cwd, child, check):
        calls.append("process")
        assert check is True
        assert child and cwd == port.work and argv[0] == transport.PULUMI
        assert (
            not {
                "GH_TOKEN",
                "GITHUB_TOKEN",
                "GITHUB_ENV",
                "GITHUB_OUTPUT",
                "GITHUB_PATH",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
                "PYTHONPATH",
            }
            & env.keys()
        )
        assert env["PATH"] == "/opt/pulumi:/usr/local/bin:/usr/bin:/bin"
        for flag in ("--config-file", "--plan"):
            path = Path(argv[argv.index(flag) + 1])
            assert path.parent == port.inputs
            assert path.stat().st_mode & 0o777 == 0o440
            assert path.read_bytes().startswith(b"synthetic-")
        if "--save-plan" in argv:
            Path(argv[argv.index("--save-plan") + 1]).write_bytes(b"bounded-result")
        return b"{}"

    monkeypatch.setattr(transport, "run", run)
    output = io.StringIO()
    result = port(
        arguments,
        env={
            "GH_TOKEN": "synthetic",
            "GITHUB_OUTPUT": "forbidden",
            "PYTHONPATH": "evil",
            "PATH": "evil",
            "PULUMI_BACKEND_URL": "s3://fixed",
        },
        stdout=output,
    )
    assert result.returncode == 0 and output.getvalue() == "{}"
    assert calls == (
        ["admission", "process"] if operation in {"preview", "up"} else ["process"]
    )
    if operation == "preview":
        assert saved.read_bytes() == b"bounded-result"
    assert (
        config.read_bytes() == b"synthetic-config"
        and plan.read_bytes() == b"synthetic-plan"
    )


@pytest.mark.parametrize("returncode", [0, 17])
def test_unchecked_command_preserves_private_result(installed, monkeypatch, returncode):
    port, _ = installed
    saved = port.repo / ".artifacts" / "unchecked.plan"

    def run(argv, *, env, cwd, child, check):
        assert check is False and child is True and cwd == port.work
        if returncode == 0:
            Path(argv[argv.index("--save-plan") + 1]).write_bytes(b"bounded-result")
        return subprocess.CompletedProcess(
            argv, returncode, b"private output\n", b"private diagnostic\n"
        )

    monkeypatch.setattr(transport, "run", run)
    result = port(
        [
            "pulumi",
            "-C",
            str(port.repo / "pulumi"),
            "preview",
            "--save-plan",
            str(saved),
        ],
        env={},
        check=False,
        capture_output=True,
    )
    assert result.returncode == returncode
    assert (
        result.stdout == "private output\n" and result.stderr == "private diagnostic\n"
    )
    if returncode == 0:
        assert saved.read_bytes() == b"bounded-result"
        assert saved.stat().st_mode & 0o777 == 0o600
    else:
        assert not saved.exists()


def test_native_metadata_dispatch_and_forbidden_tools(installed, monkeypatch):
    port, _ = installed
    calls = []
    monkeypatch.setattr(
        transport, "run", lambda argv, **kw: calls.append((argv, kw)) or b"{}"
    )
    assert port(["aws", "sts", "get-caller-identity"], env={}).stdout == "{}"
    assert calls[0][0][0] == transport.AWS and calls[0][1]["child"] is False
    for command in (["sh", "-c", "anything"], ["/tmp/aws"], ["uv", "sync"]):
        with pytest.raises(ValueError):
            port(command, env={})
    assert len(calls) == 1


def test_failed_last_admission_prevents_program(installed, monkeypatch):
    port, _ = installed
    port.before_program = lambda: (_ for _ in ()).throw(ValueError("changed head"))
    monkeypatch.setattr(
        transport, "run", lambda *_a, **_k: pytest.fail("program executed")
    )
    with pytest.raises(ValueError, match="changed head"):
        port(["pulumi", "-C", "/project", "up"], env={})


@pytest.mark.parametrize("fault", ["uid", "pid", "mount", "area", "session"])
def test_missing_container_prerequisites_fail_before_process(
    installed, monkeypatch, tmp_path, fault
):
    if fault == "uid":
        monkeypatch.setattr(transport.os, "geteuid", lambda: 2000)
    if fault == "pid":
        monkeypatch.setattr(transport.os, "getpid", lambda: 2)
    if fault == "mount":
        monkeypatch.setattr(
            transport.os, "statvfs", lambda *_: SimpleNamespace(f_flag=0)
        )
    area = tmp_path / "other"
    if fault != "area":
        area.mkdir()
    with pytest.raises(ValueError):
        transport.ServiceTransport(
            area,
            session={},
            region="eu-central-1",
            account="891377212104",
            before_program=lambda: None,
        )
