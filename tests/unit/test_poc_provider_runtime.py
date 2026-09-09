"""Pinned provider installation rejects archive, SDK and executable substitutions."""

import hashlib
import importlib
import io
import os
import subprocess
import sys
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
module = importlib.import_module("poc_provider_runtime")
OFFICIAL_PINS = module.PINS


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    archives = {}
    pins = []
    for pin in OFFICIAL_PINS:
        binary = f"#!/bin/sh\nprintf '%s\\n' '{pin.version}'\n".encode()
        archive = tmp_path / f"{pin.name}.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            member = tarfile.TarInfo(f"./{pin.filename}")
            member.size = len(binary)
            bundle.addfile(member, io.BytesIO(binary))
            # Extra files are never extracted.
            member = tarfile.TarInfo("../../escape")
            member.size = 1
            bundle.addfile(member, io.BytesIO(b"x"))
        pins.append(
            replace(
                pin,
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                binary_sha256=hashlib.sha256(binary).hexdigest(),
            )
        )
        archives[pin.url] = archive
    monkeypatch.setattr(module, "PINS", tuple(pins))
    versions = {"pulumi": "3.223.0", **{f"pulumi-{p.name}": p.version for p in pins}}
    (tmp_path / "uv.lock").write_text(
        "".join(
            f'[[package]]\nname = "{name}"\nversion = "{version}"\n'
            for name, version in versions.items()
        )
    )
    monkeypatch.setattr(module.importlib.metadata, "version", versions.__getitem__)
    calls = []
    actual_run = subprocess.run

    def run(command, **kwargs):
        assert kwargs["env"] == {"PATH": os.defpath, "LANG": "C.UTF-8"}
        calls.append(command)
        if command[0] == "curl":
            assert command[command.index("--proto-redir") + 1] == "=https"
            destination = Path(command[-1])
            destination.write_bytes(archives[command[-3]].read_bytes())
            return subprocess.CompletedProcess(command, 0, b"", b"")
        return actual_run(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic-not-a-credential")
    monkeypatch.setenv("GH_TOKEN", "synthetic-not-a-token")
    return tmp_path, archives, calls, versions


def test_official_finite_pins_are_fixed_and_aws_is_unchanged():
    assert [(p.name, p.version) for p in OFFICIAL_PINS] == [
        ("aws", "7.23.0"),
        ("random", "4.19.2"),
        ("tls", "5.3.1"),
    ]
    assert [p.archive_sha256 for p in OFFICIAL_PINS] == [
        "f5c585152bbacf11a0c02376ade122b7e74095e9b2f98dd291cbec1d880e7b4c",
        "89065248950ea63d206ca17c7ec3d6b68bcb1460948ffc13a0ded7292d7b528a",
        "bdedb2c018e523f39c6cbce7a9cb0f6ef4f1e396f8321c50ef624981fd058919",
    ]
    assert OFFICIAL_PINS[0].binary_sha256 == (
        "ad2008620e4504705db055f27c2cbd76f34c6e29fb465278464c286c30d63196"
    )


def test_verified_install_and_repeat_verification(runtime):
    root, _, calls, _ = runtime
    module.install(root)
    home = module.verify_runtime(root)
    assert home == root / ".poc-provider-runtime"
    assert home.stat().st_mode & 0o777 == 0o700
    assert not (root.parent / "escape").exists()
    assert list(home.glob("*.tar.gz")) == []
    assert len([c for c in calls if c[0] == "curl"]) == 3
    for pin in module.PINS:
        assert module._binary(home, pin).stat().st_mode & 0o777 == 0o500
    with pytest.raises(FileExistsError):
        module.install(root)
    assert module.verify_runtime(root) == home


@pytest.mark.parametrize("kind", ["corrupt", "missing", "symlink", "directory"])
def test_unverified_binary_blocks_runtime(runtime, kind):
    root, _, _, _ = runtime
    module.install(root)
    binary = module._binary(module.plugin_home(root), module.PINS[0])
    binary.unlink()
    if kind == "corrupt":
        binary.write_text("untrusted")
    elif kind == "symlink":
        binary.symlink_to(root / "uv.lock")
    elif kind == "directory":
        binary.mkdir()
    with pytest.raises(ValueError):
        module.verify_runtime(root)


def test_symlink_home_rejected(runtime):
    root, _, _, _ = runtime
    module.install(root)
    home = module.plugin_home(root)
    moved = root / "moved"
    home.rename(moved)
    home.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError):
        module.verify_runtime(root)


@pytest.mark.parametrize("kind", ["lock", "installed", "duplicate", "missing"])
def test_sdk_compatibility_fails_before_download(runtime, monkeypatch, kind):
    root, _, calls, versions = runtime
    lock = root / "uv.lock"
    if kind == "lock":
        lock.write_text(lock.read_text().replace("7.23.0", "7.24.0"))
    elif kind == "installed":
        versions["pulumi-aws"] = "7.24.0"
    elif kind == "duplicate":
        lock.write_text(
            lock.read_text() + '[[package]]\nname="pulumi-aws"\nversion="7.23.0"\n'
        )
    else:

        def missing(name):
            raise module.importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(module.importlib.metadata, "version", missing)
    with pytest.raises(ValueError):
        module.install(root)
    assert calls == []
    assert not module.plugin_home(root).exists()


def test_corrupt_archive_never_extracts_or_executes_and_removes_partial_home(runtime):
    root, archives, calls, _ = runtime
    archives[module.PINS[0].url].write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        module.install(root)
    assert len(calls) == 1 and calls[0][0] == "curl"
    assert not module.plugin_home(root).exists()


@pytest.mark.parametrize("kind", ["missing", "link", "duplicate"])
def test_archive_member_must_be_one_regular_exact_binary(runtime, monkeypatch, kind):
    root, archives, calls, _ = runtime
    pin = module.PINS[0]
    archive = archives[pin.url]
    with tarfile.open(archive, "w:gz") as bundle:
        if kind != "missing":
            member = tarfile.TarInfo(pin.filename)
            if kind == "link":
                member.type = tarfile.SYMTYPE
                member.linkname = "/tmp/foreign"
            bundle.addfile(member)
            if kind == "duplicate":
                bundle.addfile(member)
    pin = replace(pin, archive_sha256=module._digest(archive))
    monkeypatch.setattr(module, "PINS", (pin, *module.PINS[1:]))
    with pytest.raises(ValueError):
        module.install(root)
    assert len(calls) == 1
    assert not module.plugin_home(root).exists()


def test_correct_hash_wrong_reported_version_is_rejected(runtime, monkeypatch):
    root, _, _, _ = runtime
    module.install(root)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, b"99.0.0", b""),
    )
    with pytest.raises(ValueError):
        module.verify_runtime(root)


def test_cli_success_and_redacted_failure(runtime, monkeypatch, capsys):
    root, _, _, _ = runtime
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module.sys, "prefix", str(root / ".venv"))
    assert module.main(["install"]) == 0
    assert module.main(["verify"]) == 0
    assert module.main(["install"]) == 1
    assert capsys.readouterr().err == "INVALID: trusted provider runtime failed\n"


def test_real_isolated_cli_rejects_unbound_interpreter(tmp_path):
    (tmp_path / "hashlib.py").write_text("raise RuntimeError('hostile import')")
    result = subprocess.run(
        [sys.executable, "-I", module.__file__, "verify"],
        cwd=tmp_path,
        env={"PATH": os.defpath, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == "INVALID: trusted provider runtime failed\n"


def test_unreadable_verified_member_fails_closed(runtime, monkeypatch):
    root, _, _, _ = runtime
    monkeypatch.setattr(module.tarfile.TarFile, "extractfile", lambda *a: None)
    with pytest.raises(ValueError, match="no binary"):
        module.install(root)
    assert not module.plugin_home(root).exists()
