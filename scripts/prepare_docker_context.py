#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path


def _ensure_dir(path: Path, mode: int) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise NotADirectoryError(path)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)


def _is_regular_directory_path(path: Path, label: str) -> bool:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        print(f"error: {label} must be a regular directory", file=sys.stderr)
        return False
    return True


def _bootstrap_env_file(env_path: Path, empty_env_path: Path) -> bool:
    if env_path.is_symlink() or (env_path.exists() and not env_path.is_file()):
        print("error: .env must be a regular file", file=sys.stderr)
        return False

    if env_path.exists():
        return True

    if empty_env_path.is_symlink() or (
        empty_env_path.exists() and not empty_env_path.is_file()
    ):
        print("error: .env.empty must be a regular file", file=sys.stderr)
        return False
    if not empty_env_path.is_file():
        print("error: .env.empty not found; cannot bootstrap .env", file=sys.stderr)
        return False

    shutil.copyfile(empty_env_path, env_path)
    return True


def main() -> int:
    home_dir = Path.home()
    repo_dir = Path.cwd()
    env_path = repo_dir / ".env"
    empty_env_path = repo_dir / ".env.empty"
    backend_dir = repo_dir / ".pulumi-backend"
    aws_path = home_dir / ".aws"

    if not _is_regular_directory_path(aws_path, "~/.aws"):
        return 1
    _ensure_dir(aws_path, 0o700)

    if not _bootstrap_env_file(env_path, empty_env_path):
        return 1

    os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    if not _is_regular_directory_path(backend_dir, ".pulumi-backend"):
        return 1
    _ensure_dir(backend_dir, 0o700)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
