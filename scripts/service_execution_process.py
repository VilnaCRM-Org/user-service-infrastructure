"""Bounded isolated processes shared with the reviewed bootstrap worker pattern.

The installed worker must be root PID 1 in a private container namespace. These
primitives do not authenticate source or grant cloud authority.
"""

from __future__ import annotations

import os
import selectors
import signal
import stat
import subprocess  # nosec B404
import time
from pathlib import Path
from typing import BinaryIO, cast

MAX_BYTES = 16 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def private_write(path, raw, *, child=False):
    """Create a fresh private file; never follow existing paths or symlinks."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
    if child:
        os.chown(path, 2000, 2000)


def protected_write(path, raw):
    """Keep verifier-owned inputs readable, never writable, by the PR UID."""
    private_write(path, raw)
    os.chown(path, 0, 2000)
    path.chmod(0o440)


def private_read(path):
    """Read only a regular nonsymlink private process result with a strict bound."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ValueError("private-file-required") from None
    with os.fdopen(descriptor, "rb") as handle:
        require(
            stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "private-file-required"
        )
        raw = handle.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "private-document-bound")
    return raw


def _streams(process, timeout):
    """Drain bounded stdout/stderr concurrently to prevent pipe deadlocks."""
    result = bytearray()
    errors = 0
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(cast(BinaryIO, process.stdout), selectors.EVENT_READ, True)
        selector.register(cast(BinaryIO, process.stderr), selectors.EVENT_READ, False)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            require(remaining > 0, "private-process-timeout")
            for key, _ in selector.select(remaining):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                elif key.data:
                    require(
                        len(result) + len(chunk) <= MAX_BYTES, "private-output-bound"
                    )
                    result.extend(chunk)
                else:
                    errors += len(chunk)
                    require(errors <= 1024 * 1024, "private-error-bound")
        require(
            process.wait(timeout=max(0.01, deadline - time.monotonic())) == 0,
            "private-process-failed",
        )
    return bytes(result)


def _child_pids():
    """Find every live PR UID in the worker's private PID namespace."""
    found = []
    for path in Path("/proc").glob("[0-9]*/status"):
        try:
            fields = dict(row.split(":", 1) for row in path.read_text().splitlines())
        except FileNotFoundError:
            continue
        if fields["Uid"].split()[0] == "2000" and "Z" not in fields["State"]:
            found.append(int(path.parent.name))
    return found


def _stop_children():
    """Kill detached descendants too; no PR process survives a verifier recheck."""
    require(os.getpid() == 1, "private-pid-namespace-required")
    deadline = time.monotonic() + 5
    while pids := _child_pids():
        require(time.monotonic() < deadline, "child-cleanup-timeout")
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.01)


def run(command, *, env, cwd, child=False, timeout=1200):
    """Execute trusted absolute binaries without a shell or unbounded output."""
    require(Path(command[0]).is_absolute(), "absolute-executable-required")
    try:
        # Only installed fixed executables reach this private dispatcher.
        with subprocess.Popen(  # nosec B603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
            shell=False,
            user=2000 if child else None,
            group=2000 if child else None,
            extra_groups=() if child else None,
        ) as process:
            try:
                return _streams(process, timeout)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if child:
                    _stop_children()
    except Exception:
        raise ValueError("private-process-failed") from None
