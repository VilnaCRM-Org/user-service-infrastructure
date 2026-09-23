#!/usr/bin/env python3
"""Install and verify the finite trusted Linux amd64 Pulumi provider runtime.

Only installed source chooses versions, release URLs, hashes and plugin location.
Installation runs before AWS credentials; execution never acquires plugins.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import shutil
import subprocess  # nosec B404
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path

import tomllib  # ty: ignore[unresolved-import]  # Trusted action pins Python 3.11.

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProviderPin:
    name: str
    version: str
    archive_sha256: str
    binary_sha256: str

    @property
    def filename(self):
        return f"pulumi-resource-{self.name}"

    @property
    def url(self):
        return (
            f"https://github.com/pulumi/pulumi-{self.name}/releases/download/"
            f"v{self.version}/{self.filename}-v{self.version}-linux-amd64.tar.gz"
        )


PINS = (
    ProviderPin(
        "aws",
        "7.23.0",
        "f5c585152bbacf11a0c02376ade122b7e74095e9b2f98dd291cbec1d880e7b4c",
        "ad2008620e4504705db055f27c2cbd76f34c6e29fb465278464c286c30d63196",
    ),
    ProviderPin(
        "random",
        "4.19.2",
        "89065248950ea63d206ca17c7ec3d6b68bcb1460948ffc13a0ded7292d7b528a",
        "738079d3c3965b85566d8bba1f510a90122ded34687d15d6c8acbfc51328f0aa",
    ),
    ProviderPin(
        "tls",
        "5.3.1",
        "bdedb2c018e523f39c6cbce7a9cb0f6ef4f1e396f8321c50ef624981fd058919",
        "31bf0c74e121c3f150b0af37c47459add7d001d5b7ca6d937303535a4b2a857e",
    ),
)


def _require(value):
    if not value:
        raise ValueError("Trusted provider runtime verification failed")


def plugin_home(root):
    return root / ".poc-provider-runtime"


def _binary(home, pin):
    return home / "plugins" / f"resource-{pin.name}-v{pin.version}" / pin.filename


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sdk_versions(root):
    lock = tomllib.loads((root / "uv.lock").read_text())
    expected = {"pulumi": "3.223.0"}
    expected.update({f"pulumi-{pin.name}": pin.version for pin in PINS})
    for name, version in expected.items():
        rows = [row for row in lock["package"] if row["name"] == name]
        _require(len(rows) == 1 and rows[0]["version"] == version)
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as error:
            raise ValueError("Trusted SDK is missing") from error
        _require(installed == version)


def _clean_environment():
    # Provider --version and curl cannot inherit cloud or GitHub credentials.
    return {"PATH": os.defpath, "LANG": "C.UTF-8"}


def _verify_binary(home, pin):
    binary = _binary(home, pin)
    for path in (home, home / "plugins", binary.parent, binary):
        _require(not path.is_symlink())
    _require(binary.is_file() and _digest(binary) == pin.binary_sha256)
    result = subprocess.run(  # nosec B603
        [str(binary), "--version"],
        env=_clean_environment(),
        capture_output=True,
        check=True,
        timeout=30,
    )
    _require(result.stdout.decode().strip() == pin.version)


def verify_runtime(root):
    """Verify SDK compatibility and every executable before any Pulumi dispatch."""
    _sdk_versions(root)
    home = plugin_home(root)
    for pin in PINS:
        _verify_binary(home, pin)
    return home


def _download(pin, destination):
    subprocess.run(  # nosec B603 B607
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--tlsv1.2",
            "--connect-timeout",
            "30",
            "--max-time",
            "600",
            pin.url,
            "--output",
            str(destination),
        ],
        env=_clean_environment(),
        capture_output=True,
        check=True,
        timeout=610,
    )
    _require(_digest(destination) == pin.archive_sha256)


def _extract_binary(archive, home, pin):
    binary = _binary(home, pin)
    binary.parent.mkdir(mode=0o700)
    with tarfile.open(archive, "r:gz") as bundle:
        candidates = [
            member
            for member in bundle.getmembers()
            if member.name in (pin.filename, f"./{pin.filename}")
        ]
        _require(len(candidates) == 1 and candidates[0].isfile())
        stream = bundle.extractfile(candidates[0])
        if stream is None:
            raise ValueError("Provider archive has no binary")
        with stream, binary.open("xb") as output:
            shutil.copyfileobj(stream, output)
    binary.chmod(0o500)
    _verify_binary(home, pin)


def install(root):
    """Create an exclusive private cache from verified release archives."""
    _sdk_versions(root)
    home = plugin_home(root)
    home.mkdir(mode=0o700)  # Never reuse ambient or partially installed plugins.
    try:
        (home / "plugins").mkdir(mode=0o700)
        for pin in PINS:
            archive = home / f"{pin.name}.tar.gz"
            _download(pin, archive)
            _extract_binary(archive, home, pin)
            archive.unlink()
        verify_runtime(root)
    except (
        OSError,
        ValueError,
        KeyError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ):
        shutil.rmtree(home)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "verify"))
    args = parser.parse_args(argv)
    try:
        _require(Path(sys.prefix).resolve() == (ROOT / ".venv").resolve())
        if args.command == "install":
            install(ROOT)
        else:
            verify_runtime(ROOT)
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ):
        print("INVALID: trusted provider runtime failed", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
