"""Build and launch only installed-main service execution assets.

Run with isolated Python from .trusted. The child container receives a closed
environment; Docker credentials, host sockets and Actions command files are never
mounted. Runtime upgrades must be installed on main before credentialed use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402  # nosec B404
import tempfile  # noqa: E402

import pulumi_command_preflight as preflight  # noqa: E402
from reviewed_source_admission import verify_reviewed_source  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PATH = "/opt/pulumi:/usr/local/bin:/usr/bin:/bin"
JOBS = frozenset({"test_preview", "test_apply", "test_post_apply_drift"})
FIELDS = (
    "GH_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_ACCOUNT_ID",
    "AWS_REGION",
    "PULUMI_BACKEND_URL",
    "PULUMI_SECRETS_PROVIDER",
    "GITHUB_REPOSITORY",
    "GITHUB_REPOSITORY_ID",
    "GITHUB_REPOSITORY_OWNER_ID",
    "GITHUB_SHA",
    "GITHUB_REF",
    "GITHUB_EVENT_NAME",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_WORKFLOW_REF",
    "GITHUB_WORKFLOW_SHA",
    "GITHUB_JOB",
    "GITHUB_ACTOR",
    "GITHUB_TRIGGERING_ACTOR",
    "REQUEST_PULL_REQUEST_NUMBER",
    "REQUEST_HEAD_SHA",
    "REQUEST_COMMENT_ID",
    "REQUEST_SOURCE_RUN_ID",
    "REQUEST_COMMAND",
    "REQUEST_TARGET_ENVIRONMENT",
    "EXPECTED_BASE_SHA",
    "POC_SOURCE_ARTIFACT_ID",
    "POC_SOURCE_ARCHIVE_SHA256",
    "POC_SOURCE_SHA256",
)


def require(value):
    if not value:
        raise ValueError("Invalid service worker host prerequisites")


def _run(command, *, environment=None):
    return subprocess.run(  # nosec B603
        command,
        cwd=ROOT,
        env=environment
        or {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": os.environ["HOME"]},
        check=True,
    )


def _trusted():
    require(os.environ.get("GITHUB_REF") == "refs/heads/main")
    require(os.environ.get("GITHUB_SHA") == os.environ.get("GITHUB_WORKFLOW_SHA"))
    _run(["/usr/bin/git", "diff", "--quiet", "--no-ext-diff", "HEAD"])
    head = subprocess.run(  # nosec B603
        ["/usr/bin/git", "rev-parse", "HEAD"],
        cwd=ROOT,
        env={"PATH": "/usr/bin:/bin"},
        check=True,
        capture_output=True,
        text=True,
    )
    require(head.stdout.strip() == os.environ.get("GITHUB_SHA"))


def build():
    """Build from trusted main before the configuration/OIDC credential steps."""
    _trusted()
    _run(
        [
            "/usr/bin/docker",
            "build",
            "--target",
            "dev",
            "--tag",
            "service-execution-base",
            "--file",
            str(ROOT / "Dockerfile"),
            str(ROOT),
        ]
    )
    _run(
        [
            "/usr/bin/docker",
            "build",
            "--tag",
            "service-execution-worker",
            "--file",
            str(ROOT / "Dockerfile.service-execution"),
            str(ROOT),
        ]
    )


def prepare():
    """Reject incompatible PR project runtime before credential issuance."""
    _trusted()
    job = os.environ.get("GITHUB_JOB", "")
    require(job in JOBS)


def recheck():
    """Revalidate the exact request and independent review before credentials."""
    _trusted()
    require(os.environ.get("GITHUB_JOB") in JOBS)
    request = preflight.read_request()
    require(request["target_environment"] == "test")
    require(os.environ.get("EXPECTED_BASE_SHA") == os.environ["GITHUB_SHA"])
    preflight.revalidate_requester(request)
    verify_reviewed_source(
        os.environ["GITHUB_REPOSITORY"],
        request["pull_request_number"],
        request["head_sha"],
        os.environ["EXPECTED_BASE_SHA"],
        gh=preflight.gh,
    )


def execute():
    _trusted()
    job = os.environ.get("GITHUB_JOB", "")
    require(job in JOBS)
    require(all(os.environ.get(key) for key in FIELDS[:4]))
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    require(ROOT == workspace / ".trusted")
    recheck()
    public = Path(
        tempfile.mkdtemp(prefix="service-worker-public-", dir=os.environ["RUNNER_TEMP"])
    )
    command = [
        "/usr/bin/docker",
        "run",
        "--rm",
        "--user",
        "0:0",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=3g",  # nosec B108 - private container tmpfs
        "--cap-drop",
        "ALL",
        "--cap-add",
        "SETUID",
        "--cap-add",
        "SETGID",
        "--cap-add",
        "CHOWN",
        "--cap-add",
        "DAC_OVERRIDE",
        "--cap-add",
        "KILL",
        "--pids-limit",
        "512",
        "--security-opt",
        "no-new-privileges",
        "--mount",
        f"type=bind,src={ROOT},dst=/trusted,readonly",
        "--mount",
        f"type=bind,src={public},dst=/public",
    ]
    environment = {key: os.environ[key] for key in FIELDS if key in os.environ}
    environment["PATH"] = PATH
    for key in (*FIELDS, "PATH"):
        if key in environment:
            command.extend(["-e", key])
    command.extend(
        [
            "service-execution-worker",
            "/opt/service-runtime/bin/python",
            "-I",
            "/trusted/scripts/service_execution_worker.py",
            job,
        ]
    )
    _run(command, environment=environment)
    if job.endswith("_preview"):
        destination = ROOT
        for name in ("pulumi-plan", "pulumi-preview"):
            target = destination / ".artifacts" / name
            require(not target.exists())
            shutil.copytree(public / name, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "prepare", "recheck", "execute"))
    args = parser.parse_args(argv)
    try:
        {"build": build, "prepare": prepare, "recheck": recheck, "execute": execute}[
            args.command
        ]()
        return 0
    except Exception:
        print("Service worker host failed its trusted prerequisites.", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
