#!/usr/bin/env python3
"""Inherited bootstrap path classifier retained for shared helper compatibility.

This service repository requires @Kravalg CODEOWNERS review for every path.
Its service-only controller deliberately does not use this bootstrap classifier
for routing: all changes stay within the service account/backend capability,
never the central governance IAM role. These globs describe the bootstrap
credential/trust surface; they are not byte-equal to downstream CODEOWNERS.
"""

from __future__ import annotations

import argparse
import posixpath
import sys
from fnmatch import fnmatchcase

# Bootstrap-origin credential/trust paths. This list does not narrow the
# downstream all-path CODEOWNERS review requirement or grant deployment rights.
GOVERNANCE_PATH_GLOBS: tuple[str, ...] = (
    "/pulumi/governance/",
    "/pulumi/github-ci-bootstrap/",
    "/pulumi/infra/governance_automation.py",
    "/pulumi/infra/github_identity.py",
    "/pulumi/infra/platform_control_iam.py",
    "/pulumi/infra/platform_iam.py",
    "/pulumi/infra/governance.py",
    "/pulumi/infra/iam/",
    "/pulumi/infra/ci_bootstrap.py",
    "/pulumi/infra/ci_config.py",
    "/pulumi/infra/automation.py",
    "/pulumi/infra/bootstrap_settings.py",
    "/pulumi/infra/pulumi_state.py",
    "/pulumi/infra/pulumi_secrets.py",
    "/pulumi/repositories.governance.json",
    "/policy/",
    "/scripts/",
    "/Makefile",
    "/Dockerfile",
    "/docker-compose*.yml",
    "/pyproject.toml",
    "/uv.lock",
    "/.github/actions/",
    "/.github/workflows/",
    "/scripts/governance_paths.py",
    "/scripts/run_pulumi_command.py",
    "/scripts/_pulumi_command_support.py",
    "/scripts/_script_support.py",
    "/scripts/prepare_policy_pack.py",
    "/scripts/pulumi_pr_comment.py",
    "/scripts/_github_repository_controls.py",
    "/scripts/configure_github_repository_controls.py",
    "/.github/CODEOWNERS",
    "/.github/workflows/pulumi-governance.yml",
    "/.github/workflows/governance-promotion.yml",
    "/.github/workflows/pulumi-pr-command-runner.yml",
    "/.github/workflows/pulumi-pr-commands.yml",
)


def _fnmatch_patterns(glob: str) -> tuple[str, ...]:
    """Translate one CODEOWNERS glob into repo-relative fnmatch patterns."""
    anchored = glob.lstrip("/")
    if anchored.endswith("/"):
        # Directory subtree: match the directory itself and any descendant.
        prefix = anchored.rstrip("/")
        return (prefix, f"{prefix}/*")
    return (anchored,)


_FNMATCH_PATTERNS: tuple[str, ...] = tuple(
    pattern for glob in GOVERNANCE_PATH_GLOBS for pattern in _fnmatch_patterns(glob)
)


def _matches_path_pattern(path: str, pattern: str) -> bool:
    """Keep file wildcards within one segment and directory globs recursive."""
    if pattern.endswith("/*"):
        return path.startswith(pattern[:-1])
    parts = path.split("/")
    patterns = pattern.split("/")
    return len(parts) == len(patterns) and all(
        fnmatchcase(part, glob) for part, glob in zip(parts, patterns, strict=True)
    )


def _path_touches_governance(path: str) -> bool:
    """Return whether one changed-file path falls under a governance glob."""
    stripped = path.strip().lstrip("/")
    if not stripped:
        return False
    # Collapse "." / ".." segments before matching so a traversal-style path
    # (e.g. "pulumi/governance/../infra/x.py") resolves to its true target
    # ("pulumi/infra/x.py") and matches the correct glob instead of spuriously
    # matching the prefix it traverses through. normpath re-strips the leading
    # "/" it may reintroduce for absolute-looking inputs.
    normalized = posixpath.normpath(stripped).lstrip("/")
    if not normalized or normalized == ".":
        return False
    return any(
        _matches_path_pattern(normalized, pattern) for pattern in _FNMATCH_PATTERNS
    )


def paths_touch_governance(files: list[str]) -> bool:
    """Return whether any changed file falls under a governance path glob."""
    return any(_path_touches_governance(path) for path in files)


def _read_stdin_files() -> list[str]:
    """Return non-blank file paths read from standard input (one per line)."""
    return [line for line in sys.stdin.read().splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """Print ``governance_touched=true|false`` for the stdin file list."""
    parser = argparse.ArgumentParser(
        description="Detect whether changed files touch governance paths.",
    )
    parser.add_argument(
        "--files-stdin",
        action="store_true",
        required=True,
        help="Read newline-delimited changed-file paths from standard input.",
    )
    parser.parse_args(argv)

    files = _read_stdin_files()
    touched = "true" if paths_touch_governance(files) else "false"
    print(f"governance_touched={touched}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
