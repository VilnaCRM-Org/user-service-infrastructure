"""Materialize protected TEST child inputs; never dispatch Pulumi or admit apply.

The caller authenticates the projection, baseline config, source and native
prerequisites. Digests here bind bytes only, not installation or phase authority.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import _pulumi_stack_config as stack_config
import poc_contract
import poc_workload_phase_entrypoint as bridge
from service_execution_process import require

DIRECTORY = "workload"
FILES = ("Pulumi.yaml", "Pulumi.test.yaml", "__main__.py", "python")
MAX_FILE_BYTES = 1024 * 1024
GROUP = 2000


@dataclass(frozen=True)
class MaterializedWorkload:
    """Immutable byte bindings and fixed paths; no config or secret values."""

    directory: Path
    files: tuple[tuple[str, str], ...]
    projection_sha256: str
    baseline_sha256: str

    @property
    def python_command(self):
        """Return only the fixed generated isolated interpreter wrapper."""
        return self.directory / "python"


def _canonical(document):
    """Serialize bounded deterministic JSON, also valid as Pulumi YAML."""
    raw = json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    require(len(raw) <= MAX_FILE_BYTES, "workload-materializer-file-bound")
    return raw


def _baseline(raw, projection):
    """Retain the authenticated encrypted key without fetching or decrypting it."""
    require(
        type(raw) is bytes and 0 < len(raw) <= MAX_FILE_BYTES,
        "workload-materializer-config-bound",
    )
    try:
        document = json.loads(
            raw,
            object_pairs_hook=poc_contract._pairs,
            parse_constant=poc_contract._reject_nonfinite,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("workload-materializer-config-json") from None
    require(
        type(document) is dict
        and set(document) == {"config", "secretsprovider", "encryptedkey"}
        and type(document["config"]) is dict,
        "workload-materializer-config-fields",
    )
    require(raw == _canonical(document), "workload-materializer-config-canonical")
    backend = projection.contract["backend"]
    require(
        document["secretsprovider"] == backend["secrets_provider"],
        "workload-materializer-secrets-provider",
    )
    encrypted = document["encryptedkey"]
    require(
        type(encrypted) is str and 0 < len(encrypted) <= 8192,
        "workload-materializer-encrypted-key",
    )
    try:
        require(bool(base64.b64decode(encrypted, validate=True)), "invalid-key")
    except ValueError:
        raise ValueError("workload-materializer-encrypted-key") from None
    expected = {
        "environment": "test",
        "serviceName": backend["project"],
        "repoSlug": backend["project"],
        "pulumiBackendUrl": backend["url"],
        "pulumiSecretsProvider": backend["secrets_provider"],
    }
    require(
        all(
            document["config"].get(backend["project"] + ":" + key) == value
            for key, value in expected.items()
        ),
        "workload-materializer-baseline-target",
    )
    return document


def _documents(projection, baseline):
    """Produce only fixed project, program, wrapper and merged protected config."""
    projection = bridge._checked(projection)
    config = _baseline(baseline, projection)
    target = {
        "accountId": projection.contract["account_id"],
        "region": projection.contract["region"],
    }
    stack_config._materialize_provider_pins(config, target)
    stack_config._materialize_workload_config(
        config, bridge.workload_configuration(projection), target
    )
    documents = {
        "Pulumi.yaml": _canonical(
            {
                "name": projection.contract["backend"]["project"],
                # A virtualenv option bypasses PULUMI_PYTHON_CMD in 3.223.0.
                # The protected wrapper selects the installed interpreter.
                "runtime": {"name": "python"},
            }
        ),
        "Pulumi.test.yaml": _canonical(config),
        "__main__.py": bridge.workload_program_source(projection).encode(),
        "python": bridge.workload_python_wrapper_source().encode(),
    }
    require(
        all(0 < len(raw) <= MAX_FILE_BYTES for raw in documents.values()),
        "workload-materializer-file-bound",
    )
    return projection, documents


def _worker():
    """Require the existing isolated root worker contract, with no local bypass."""
    require(os.geteuid() == 0 and os.getpid() == 1, "workload-materializer-worker")
    require(
        all(os.statvfs(path).f_flag & os.ST_RDONLY for path in ("/", "/trusted")),
        "workload-materializer-readonly",
    )


def _directory_metadata(metadata, *, final=False):
    """Allow root's sticky temporary ancestor, never a replaceable owned area."""
    mode = metadata.st_mode
    protected = not mode & 0o022
    sticky = bool(mode & stat.S_ISVTX)
    require(
        stat.S_ISDIR(mode)
        and metadata.st_uid == 0
        and (protected or (sticky and not final)),
        "workload-materializer-parent",
    )


@contextmanager
def _area(path):
    """Traverse using directory descriptors; reject every symlink component."""
    require(isinstance(path, Path), "workload-materializer-area")
    require(path.is_absolute() and ".." not in path.parts, "workload-materializer-area")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open("/", flags)
    try:
        _directory_metadata(os.fstat(descriptor))
        for index, part in enumerate(path.parts[1:], 1):
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            _directory_metadata(
                os.fstat(descriptor), final=index == len(path.parts) - 1
            )
        require(len(path.parts) > 1, "workload-materializer-area")
        yield descriptor
    finally:
        os.close(descriptor)


def _write(directory, name, raw):
    """Create inaccessible exclusive files before assigning final read/exec modes."""
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory,
    )
    with os.fdopen(descriptor, "wb") as handle:
        os.fchown(handle.fileno(), 0, GROUP)
        handle.write(raw)
        handle.flush()
        os.fchmod(handle.fileno(), 0o550 if name == "python" else 0o440)
        os.fsync(handle.fileno())


def _readback(directory, name, expected):
    """Verify private bytes, ownership, modes and single-link regular files."""
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
        dir_fd=directory,
    )
    with os.fdopen(descriptor, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_nlink == 1
            and metadata.st_uid == 0
            and metadata.st_gid == GROUP
            and stat.S_IMODE(metadata.st_mode) == (0o550 if name == "python" else 0o440)
            and metadata.st_size == len(expected),
            "workload-materializer-file-metadata",
        )
        raw = handle.read(MAX_FILE_BYTES + 1)
    require(raw == expected, "workload-materializer-readback")
    return hashlib.sha256(raw).hexdigest()


def _populate(parent, documents):
    """Publish all files with one directory permission change, or remove them."""
    os.mkdir(DIRECTORY, 0o700, dir_fd=parent)
    directory = os.open(
        DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
    )
    try:
        os.fchown(directory, 0, GROUP)
        os.fchmod(directory, 0o700)
        for name in FILES:
            _write(directory, name, documents[name])
        digests = tuple(
            (name, _readback(directory, name, documents[name])) for name in FILES
        )
        os.fsync(directory)
        # Only the fixed child group gains read/traverse; no group/other write.
        os.fchmod(directory, 0o750)  # nosec B103
        os.fsync(directory)
        os.fsync(parent)
        return digests
    except BaseException:
        os.fchmod(directory, 0o700)
        for name in FILES:
            try:
                os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass
        os.rmdir(DIRECTORY, dir_fd=parent)
        raise
    finally:
        os.close(directory)


def materialize_workload(area, projection, baseline_config):
    """Write protected inputs only; caller still owns admission and saved-plan gates."""
    _worker()
    projection, documents = _documents(projection, baseline_config)
    with _area(area) as parent:
        digests = _populate(parent, documents)
    return MaterializedWorkload(
        area / DIRECTORY,
        digests,
        hashlib.sha256(bridge.encode_workload_projection(projection)).hexdigest(),
        hashlib.sha256(baseline_config).hexdigest(),
    )
