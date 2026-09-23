"""Synthetic process bounds and ownership tests; no cloud credentials or calls."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import service_execution_process as process  # noqa: E402


def test_private_files(tmp_path, monkeypatch):
    owned = []
    monkeypatch.setattr(process.os, "chown", lambda *args: owned.append(args))
    target = tmp_path / "protected"
    process.protected_write(target, b"synthetic")
    assert target.stat().st_mode & 0o777 == 0o440
    assert process.private_read(target) == b"synthetic"
    child = tmp_path / "child"
    process.private_write(child, b"child", child=True)
    assert owned == [(target, 0, 2000), (child, 2000, 2000)]
    with pytest.raises(FileExistsError):
        process.private_write(child, b"changed")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        process.private_read(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        process.private_read(fifo)
    monkeypatch.setattr(process, "MAX_BYTES", 2)
    with pytest.raises(ValueError):
        process.private_read(target)


@pytest.mark.parametrize(
    "script,limit,timeout,success",
    [
        ("import sys; print('ok'); print('notice',file=sys.stderr)", 100, 5, True),
        ("raise SystemExit(2)", 100, 5, False),
        ("print('too much output')", 2, 5, False),
        ("import sys; sys.stderr.write('x'*1048577)", 100, 5, False),
        ("import time; time.sleep(5)", 100, 0.01, False),
    ],
)
def test_real_process_bounds(tmp_path, monkeypatch, script, limit, timeout, success):
    monkeypatch.setattr(process, "MAX_BYTES", limit)
    command = [sys.executable, "-I", "-c", script]
    if success:
        assert process.run(command, env={}, cwd=tmp_path, timeout=timeout) == b"ok\n"
    else:
        with pytest.raises(ValueError, match="^private-process-failed$"):
            process.run(command, env={}, cwd=tmp_path, timeout=timeout)
    with pytest.raises(ValueError, match="absolute-executable"):
        process.run(["python"], env={}, cwd=tmp_path)


def test_uid_scan_handles_exit_and_zombie(monkeypatch):
    class Status:
        def __init__(self, pid, value):
            self.parent = SimpleNamespace(name=str(pid))
            self.value = value

        def read_text(self):
            if self.value is None:
                raise FileNotFoundError
            return self.value

    entries = [
        Status(1, "Uid:\t0 0 0 0\nState:\tS (sleeping)"),
        Status(2, "Uid:\t2000 2000 2000 2000\nState:\tS (sleeping)"),
        Status(3, "Uid:\t2000 2000 2000 2000\nState:\tZ (zombie)"),
        Status(4, None),
    ]
    monkeypatch.setattr(process.Path, "glob", lambda *_: entries)
    assert process._child_pids() == [2]


def test_cleanup_requires_pid1_and_kills_detached(monkeypatch):
    monkeypatch.setattr(process.os, "getpid", lambda: 2)
    with pytest.raises(ValueError, match="private-pid"):
        process._stop_children()
    monkeypatch.setattr(process.os, "getpid", lambda: 1)
    scans = iter(([2, 3], []))
    monkeypatch.setattr(process, "_child_pids", lambda: next(scans))
    killed = []

    def kill(pid, _signal):
        killed.append(pid)
        if pid == 3:
            raise ProcessLookupError

    monkeypatch.setattr(process.os, "kill", kill)
    monkeypatch.setattr(process.time, "sleep", lambda *_: None)
    process._stop_children()
    assert killed == [2, 3]
    monkeypatch.setattr(process, "_child_pids", lambda: [2])
    times = iter((0, 6))
    monkeypatch.setattr(process.time, "monotonic", lambda: next(times))
    with pytest.raises(ValueError, match="child-cleanup-timeout"):
        process._stop_children()


def test_child_dispatch_cleanup_on_all_returns(monkeypatch, tmp_path):
    calls = []

    class Child:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def poll(self):
            return 0

    def launch(argv, **kwargs):
        assert argv == ["/trusted/tool"]
        assert kwargs["user"] == kwargs["group"] == 2000
        assert kwargs["extra_groups"] == () and kwargs["shell"] is False
        assert kwargs["stdin"] == subprocess.DEVNULL
        return Child()

    monkeypatch.setattr(process.subprocess, "Popen", launch)
    monkeypatch.setattr(process, "_streams", lambda *_: b"safe")
    monkeypatch.setattr(process, "_stop_children", lambda: calls.append("cleanup"))
    assert process.run(["/trusted/tool"], env={}, cwd=tmp_path, child=True) == b"safe"
    assert calls == ["cleanup"]
    monkeypatch.setattr(
        process, "_streams", lambda *_: (_ for _ in ()).throw(ValueError())
    )
    with pytest.raises(ValueError):
        process.run(["/trusted/tool"], env={}, cwd=tmp_path, child=True)
    assert calls == ["cleanup", "cleanup"]
