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

from service_execution_transport import project_document  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PATH = "/opt/pulumi:/usr/local/bin:/usr/bin:/bin"
JOBS = frozenset(
    {
        "test_preview",
        "test_apply",
        "test_post_apply_drift",
        "prod_preview",
        "prod_apply",
        "prod_post_apply_drift",
        "scheduled_test_drift",
        "scheduled_prod_drift",
    }
)
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
    "GOVERNANCE_PROMOTION_APP_ID",
    "GOVERNANCE_PROMOTION_APP_SLUG",
    "POC_REGISTRY_WORKFLOW_SHA",
    "POC_PUBLISHER_WORKFLOW_SHA",
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
    if "prod" in job:
        source = Path(os.environ["GITHUB_WORKSPACE"])
        project_document((source / "pulumi/Pulumi.yaml").read_bytes())


def execute():
    _trusted()
    job = os.environ.get("GITHUB_JOB", "")
    require(job in JOBS)
    require(all(os.environ.get(key) for key in FIELDS[:4]))
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    require(ROOT == workspace / ".trusted")
    source = ROOT if job == "scheduled_test_drift" else workspace
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
        f"type=bind,src={source},dst=/source,readonly",
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
        destination = ROOT if job == "test_preview" else workspace
        for name in ("pulumi-plan", "pulumi-preview"):
            target = destination / ".artifacts" / name
            require(not target.exists())
            shutil.copytree(public / name, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "prepare", "execute"))
    args = parser.parse_args(argv)
    try:
        {"build": build, "prepare": prepare, "execute": execute}[args.command]()
        return 0
    except Exception:
        print("Service worker host failed its trusted prerequisites.", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
