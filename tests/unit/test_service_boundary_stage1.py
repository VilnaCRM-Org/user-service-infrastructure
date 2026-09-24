"""Prove disabled PR jobs cannot select credentials or execute submitted code."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
worker = importlib.import_module("service_boundary_worker")


@pytest.mark.parametrize("arguments", [[], ["execute"], ["up"], ["smoke", "PR.py"]])
def test_deployment_arguments_cannot_spawn_processes(arguments, monkeypatch, capsys):
    monkeypatch.setattr(worker, "smoke", lambda: pytest.fail("runtime entered"))
    assert worker.main(arguments) == 1
    assert capsys.readouterr().err == worker.DISABLED + "\n"


def test_isolated_cli_ignores_pr_import_hooks(tmp_path):
    marker = tmp_path / "executed"
    for name in ("sitecustomize.py", "service_execution_process.py"):
        (tmp_path / name).write_text(f"open({str(marker)!r}, 'w').close()")
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts/service_boundary_worker.py"), "up"],
        cwd=tmp_path,
        env={"PATH": os.defpath, "PYTHONPATH": str(tmp_path)},
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == worker.DISABLED + "\n"
    assert not marker.exists()


@pytest.mark.parametrize(
    "key", ["AWS_SESSION_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN"]
)
def test_smoke_rejects_credentials_before_process_creation(key, monkeypatch):
    monkeypatch.setattr(worker.os, "getpid", lambda: 1)
    monkeypatch.setattr(worker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        worker.os, "statvfs", lambda _: type("Flags", (), {"f_flag": os.ST_RDONLY})()
    )
    monkeypatch.setenv(key, "synthetic-not-a-credential")
    monkeypatch.setattr(worker, "run", lambda *_a, **_k: pytest.fail("child created"))
    with pytest.raises(ValueError, match="credential-free"):
        worker.smoke()


def test_smoke_failure_is_redacted(monkeypatch, capsys):
    def reject():
        raise ValueError("synthetic-private-detail")

    monkeypatch.setattr(worker, "smoke", reject)
    assert worker.main(["smoke"]) == 1
    assert capsys.readouterr().err == "Isolated boundary smoke failed.\n"


def test_fixed_smoke_success(monkeypatch, capsys):
    monkeypatch.setattr(worker, "smoke", lambda: None)
    assert worker.main(["smoke"]) == 0
    assert capsys.readouterr().out == "ISOLATED_BOUNDARY_PASS\n"


@pytest.mark.parametrize("output", [b"ISOLATED_CHILD_PASS\n", b"unexpected"])
def test_smoke_uses_only_fixed_child_and_closed_environment(output, monkeypatch):
    monkeypatch.setattr(worker.os, "getpid", lambda: 1)
    monkeypatch.setattr(worker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(worker.os, "environ", {})
    monkeypatch.setattr(
        worker.os, "statvfs", lambda _: type("Flags", (), {"f_flag": os.ST_RDONLY})()
    )
    calls = []

    def child(command, **kwargs):
        calls.append((command, kwargs))
        return output

    monkeypatch.setattr(worker, "run", child)
    if output == b"ISOLATED_CHILD_PASS\n":
        worker.smoke()
    else:
        with pytest.raises(ValueError, match="fixed-probe"):
            worker.smoke()
    command, kwargs = calls[0]
    assert command == [sys.executable, "-I", "-c", worker.PROGRAM]
    assert kwargs == {
        "env": {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
        "cwd": Path("/tmp"),
        "child": True,
        "timeout": 10,
    }


@pytest.mark.parametrize(
    "uid,pid,readonly", [(1, 1, True), (0, 2, True), (0, 1, False)]
)
def test_smoke_rejects_missing_isolation(uid, pid, readonly, monkeypatch):
    monkeypatch.setattr(worker.os, "geteuid", lambda: uid)
    monkeypatch.setattr(worker.os, "getpid", lambda: pid)
    monkeypatch.setattr(
        worker.os,
        "statvfs",
        lambda _: type("Flags", (), {"f_flag": os.ST_RDONLY if readonly else 0})(),
    )
    monkeypatch.setattr(worker, "run", lambda *_a, **_k: pytest.fail("child created"))
    with pytest.raises(ValueError):
        worker.smoke()
