"""Synthetic ownership metadata plus real protected-file materialization tests."""

import base64
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_materializer as module  # noqa: E402
from test_poc_workload_child_entrypoint import projection


def baseline(value):
    backend = value.contract["backend"]
    prefix = backend["project"] + ":"
    return module._canonical(
        {
            "secretsprovider": backend["secrets_provider"],
            "encryptedkey": base64.b64encode(b"synthetic-encrypted-key").decode(),
            "config": {
                prefix + "environment": "test",
                prefix + "serviceName": backend["project"],
                prefix + "repoSlug": backend["project"],
                prefix + "pulumiBackendUrl": backend["url"],
                prefix + "pulumiSecretsProvider": backend["secrets_provider"],
                prefix + "owner": "team-user-service",
                prefix + "costCenter": "core",
                "aws:region": "eu-central-1",
                "aws:allowedAccountIds": ["891377212104"],
            },
        }
    )


@pytest.fixture
def protected(tmp_path, monkeypatch):
    """Simulate the root namespace identity; do not claim native ownership proof."""
    real_fstat = os.fstat
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.os, "getpid", lambda: 1)
    monkeypatch.setattr(
        module.os, "statvfs", lambda *_: SimpleNamespace(f_flag=os.ST_RDONLY)
    )
    monkeypatch.setattr(module.os, "fchown", lambda *_: None)

    def metadata(fd):
        values = list(real_fstat(fd))
        values[4] = 0
        values[5] = module.GROUP
        return os.stat_result(values)

    monkeypatch.setattr(module.os, "fstat", metadata)
    area = tmp_path / "inputs"
    area.mkdir(mode=0o750)
    value = projection()
    return area, value, baseline(value)


def test_materializes_only_fixed_files_and_binds_their_exact_private_bytes(protected):
    area, value, original = protected
    result = module.materialize_workload(area, value, original)
    assert result.directory == area / "workload"
    assert result.python_command == result.directory / "python"
    assert set(p.name for p in result.directory.iterdir()) == set(module.FILES)
    assert stat.S_IMODE(result.directory.stat().st_mode) == 0o750
    assert result.baseline_sha256 == hashlib.sha256(original).hexdigest()
    assert (
        result.projection_sha256
        == hashlib.sha256(module.bridge.encode_workload_projection(value)).hexdigest()
    )
    for name, digest in result.files:
        path = result.directory / name
        assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
        assert stat.S_IMODE(path.stat().st_mode) == (
            0o550 if name == "python" else 0o440
        )
        assert path.stat().st_nlink == 1
    config = json.loads((result.directory / "Pulumi.test.yaml").read_bytes())
    assert config["encryptedkey"] == json.loads(original)["encryptedkey"]
    assert config["secretsprovider"] == json.loads(original)["secretsprovider"]
    assert (
        config["config"].items() >= module.bridge.workload_configuration(value).items()
    )
    assert {
        key: value for key, value in config["config"].items() if key.startswith("aws:")
    } == {
        "aws:region": "eu-central-1",
        "aws:allowedAccountIds": ["891377212104"],
        "aws:skipCredentialsValidation": False,
        "aws:skipRegionValidation": False,
        "aws:skipRequestingAccountId": False,
    }
    assert config["config"]["user-service-infrastructure:owner"] == "team-user-service"
    project = json.loads((result.directory / "Pulumi.yaml").read_bytes())
    assert project == {
        "name": "user-service-infrastructure",
        "runtime": {"name": "python"},
    }
    assert (
        result.directory / "python"
    ).read_text() == module.bridge.workload_python_wrapper_source()
    assert (
        result.directory / "__main__.py"
    ).read_text() == module.bridge.workload_program_source(value)
    assert "encryptedkey" not in repr(result) and "synthetic-encrypted-key" not in repr(
        result
    )


def test_directory_is_private_until_all_complete_readbacks(protected, monkeypatch):
    area, value, raw = protected
    original = module._readback
    checked = []

    def readback(directory, name, expected):
        assert stat.S_IMODE(os.fstat(directory).st_mode) == 0o700
        assert set(os.listdir(directory)) == set(module.FILES)
        checked.append(name)
        return original(directory, name, expected)

    monkeypatch.setattr(module, "_readback", readback)
    module.materialize_workload(area, value, raw)
    assert tuple(checked) == module.FILES


@pytest.mark.parametrize("fault", ["uid", "pid", "writable-root"])
def test_wrong_worker_context_rejects_before_any_write(protected, monkeypatch, fault):
    area, value, raw = protected
    if fault == "uid":
        monkeypatch.setattr(module.os, "geteuid", lambda: 1000)
    elif fault == "pid":
        monkeypatch.setattr(module.os, "getpid", lambda: 2)
    else:
        monkeypatch.setattr(module.os, "statvfs", lambda *_: SimpleNamespace(f_flag=0))
    with pytest.raises(ValueError, match="materializer-worker|materializer-readonly"):
        module.materialize_workload(area, value, raw)
    assert list(area.iterdir()) == []


@pytest.mark.parametrize(
    "fault",
    [
        "type",
        "empty",
        "bound",
        "invalid",
        "duplicate",
        "nan",
        "shape",
        "settings-type",
        "extra",
        "provider",
        "key-type",
        "key-empty",
        "key-malformed",
        "target",
        "canonical",
        "provider-override",
        "image-override",
    ],
)
def test_invalid_protected_baseline_rejects_without_files(protected, fault):
    area, value, raw = protected
    document = json.loads(raw)
    changes = {
        "extra": (document, "encryptionsalt", "unsupported"),
        "provider": (document, "secretsprovider", "passphrase"),
        "key-type": (document, "encryptedkey", True),
        "key-empty": (document, "encryptedkey", ""),
        "key-malformed": (document, "encryptedkey", "not-base64"),
        "settings-type": (document, "config", []),
        "target": (
            document["config"],
            "user-service-infrastructure:environment",
            "prod",
        ),
        "provider-override": (
            document["config"],
            "aws:endpoint",
            "https://foreign.invalid",
        ),
        "image-override": (
            document["config"],
            "user-service-infrastructure:webImage",
            "foreign",
        ),
    }
    if fault in changes:
        target, key, replacement = changes[fault]
        target[key] = replacement
        raw = module._canonical(document)
    replacements = {
        "type": None,
        "empty": b"",
        "bound": b" " * (module.MAX_FILE_BYTES + 1),
        "invalid": b"\xff",
        "duplicate": b'{"x":1,"x":2}',
        "nan": b'{"x":NaN}',
        "shape": b"[]",
        "canonical": raw + b"\n",
    }
    raw = replacements.get(fault, raw)
    with pytest.raises(ValueError):
        module.materialize_workload(area, value, raw)
    assert list(area.iterdir()) == []


@pytest.mark.parametrize(
    "fault",
    [
        "symlink",
        "ancestor-symlink",
        "writable",
        "sticky-final",
        "relative",
        "traversal",
        "root",
        "type",
    ],
)
def test_area_redirects_or_replaceable_parent_reject(protected, fault):
    area, value, raw = protected
    selected = area
    if fault == "symlink":
        selected = area.parent / "alias"
        selected.symlink_to(area, target_is_directory=True)
    elif fault == "ancestor-symlink":
        alias = area.parent / "alias"
        alias.symlink_to(area.parent, target_is_directory=True)
        selected = alias / area.name
    elif fault in {"writable", "sticky-final"}:
        area.chmod(0o777 if fault == "writable" else 0o1777)
    elif fault == "relative":
        selected = Path("relative")
    elif fault == "traversal":
        selected = area / ".." / area.name
    elif fault == "root":
        selected = Path("/")
    else:
        selected = str(area)
    with pytest.raises((ValueError, OSError)):
        module.materialize_workload(selected, value, raw)
    assert not (area / "workload").exists()


@pytest.mark.parametrize("existing", ["directory", "file", "symlink"])
def test_existing_destination_is_never_reused_or_replaced(protected, existing):
    area, value, raw = protected
    destination = area / "workload"
    if existing == "directory":
        destination.mkdir()
    elif existing == "file":
        destination.write_text("keep")
    else:
        destination.symlink_to(area, target_is_directory=True)
    before = destination.lstat()
    with pytest.raises(FileExistsError):
        module.materialize_workload(area, value, raw)
    assert destination.lstat().st_ino == before.st_ino


def test_partial_write_failure_removes_only_its_new_private_directory(
    protected, monkeypatch
):
    area, value, raw = protected
    (area / "keep").write_text("existing")
    original = module._write

    def fail(directory, name, data):
        original(directory, name, data)
        if name == "Pulumi.test.yaml":
            raise OSError("synthetic-write-failure")

    monkeypatch.setattr(module, "_write", fail)
    with pytest.raises(OSError, match="synthetic-write-failure"):
        module.materialize_workload(area, value, raw)
    assert sorted(p.name for p in area.iterdir()) == ["keep"]


@pytest.mark.parametrize("fault", ["content", "mode", "hardlink", "fifo", "symlink"])
def test_readback_failure_prevents_publication(protected, monkeypatch, fault):
    area, value, raw = protected
    original = module._write

    def change(directory, name, data):
        original(directory, name, data)
        if name == "python":
            path = area / "workload" / "__main__.py"
            if fault == "mode":
                path.chmod(0o660)
            elif fault == "content":
                path.chmod(0o600)
                data = path.read_bytes()
                path.write_bytes(b"X" + data[1:])
                path.chmod(0o440)
            elif fault == "hardlink":
                os.link(path, area / "extra-link")
            else:
                path.unlink()
                if fault == "fifo":
                    os.mkfifo(path, 0o440)
                else:
                    path.symlink_to(area / "outside")

    monkeypatch.setattr(module, "_write", change)
    with pytest.raises((ValueError, OSError)):
        module.materialize_workload(area, value, raw)
    assert not (area / "workload").exists()


def test_oversized_generated_bytes_reject_before_writes(protected, monkeypatch):
    area, value, raw = protected
    monkeypatch.setattr(
        module.bridge,
        "workload_program_source",
        lambda _: "x" * (module.MAX_FILE_BYTES + 1),
    )
    with pytest.raises(ValueError, match="file-bound"):
        module.materialize_workload(area, value, raw)
    assert list(area.iterdir()) == []


def test_projection_is_revalidated_before_materialization(protected):
    area, value, raw = protected
    value.images["web"]["uri"] = "foreign"
    with pytest.raises(ValueError, match="image-binding"):
        module.materialize_workload(area, value, raw)
    assert list(area.iterdir()) == []


def test_nonroot_parent_ownership_rejects():
    with pytest.raises(ValueError, match="materializer-parent"):
        module._directory_metadata(
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=2000), final=True
        )


@pytest.mark.parametrize("field,value", [(4, 1000), (5, 0)])
def test_wrong_file_owner_or_group_prevents_publication(
    protected, monkeypatch, field, value
):
    area, projection, raw = protected
    original = module.os.fstat

    def wrong_owner(descriptor):
        metadata = original(descriptor)
        if stat.S_ISREG(metadata.st_mode):
            values = list(metadata)
            values[field] = value
            return os.stat_result(values)
        return metadata

    monkeypatch.setattr(module.os, "fstat", wrong_owner)
    with pytest.raises(ValueError, match="materializer-file-metadata"):
        module.materialize_workload(area, projection, raw)
    assert not (area / "workload").exists()
