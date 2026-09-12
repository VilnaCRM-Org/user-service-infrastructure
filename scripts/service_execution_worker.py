"""Installed service worker: authenticate in root, execute Pulumi as UID 2000.

The workflow supplies immutable mounts and its existing credentials. This entry
point neither admits workload phases nor changes the current TEST/PROD DAG.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import contextlib  # noqa: E402
import tempfile  # noqa: E402

import poc_registry_runner as registry  # noqa: E402
import poc_scheduled_registry_drift as scheduled  # noqa: E402
from service_execution_process import require, run  # noqa: E402
from service_execution_transport import ServiceTransport, copy_tree  # noqa: E402

JOBS = {
    "test_preview": ("test", "plan"),
    "test_apply": ("test", "up-plan"),
    "test_post_apply_drift": ("test", "drift"),
    "prod_preview": ("prod", "plan"),
    "prod_apply": ("prod", "up-plan"),
    "prod_post_apply_drift": ("prod", "drift"),
    "scheduled_test_drift": ("test", "drift"),
    "scheduled_prod_drift": ("prod", "drift"),
}
ACCOUNTS = {"test": "891377212104", "prod": "933245420672"}
SESSION_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def source_head(expected):
    require(bool(os.statvfs("/source").f_flag & os.ST_RDONLY), "source-readonly")
    command = ["/usr/bin/git", "-c", "safe.directory=/source", "-C", "/source"]
    environment = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}
    actual = run([*command, "rev-parse", "HEAD"], env=environment, cwd=Path("/trusted"))
    require(actual.decode().strip() == expected, "source-head")
    run(
        [
            *command,
            "diff",
            "--quiet",
            "--no-ext-diff",
            "HEAD",
            "--",
            "pulumi",
            "policy",
        ],
        env=environment,
        cwd=Path("/trusted"),
    )
    require(
        not run(
            [
                *command,
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
                "pulumi",
                "policy",
            ],
            env=environment,
            cwd=Path("/trusted"),
        ),
        "source-untracked",
    )


def admit(job):
    """Reuse original native requester/reviewer or scheduled-main authority."""
    if job.startswith("scheduled_"):
        provenance = scheduled.verify_provenance()
        return provenance.sha
    run_id, sha = registry.artifact._context(os.environ)
    registry.artifact._producer(registry.preflight.gh, run_id, sha)
    registry._verify_checkout(sha)
    require(os.environ.get("EXPECTED_BASE_SHA") == sha, "request-base")
    request = registry.preflight.read_request()
    registry.preflight.revalidate_requester(request)
    registry.verify_reviewed_source(
        registry.artifact.REPOSITORY,
        request["pull_request_number"],
        request["head_sha"],
        os.environ["EXPECTED_BASE_SHA"],
        gh=registry.preflight.gh,
    )
    account, command = JOBS[job]
    require(request["target_environment"] == account, "request-account")
    require(command == "plan" or request["command"] == "up", "request-command")
    return request["head_sha"]


def _coordinates(account):
    expected = {
        "AWS_ACCOUNT_ID": ACCOUNTS[account],
        "AWS_REGION": "eu-central-1",
        "PULUMI_BACKEND_URL": f"s3://pulumi-user-service-infrastructure-{account}-state",
        "PULUMI_SECRETS_PROVIDER": (
            f"awskms://alias/pulumi-user-service-infrastructure-{account}-secrets"
            "?region=eu-central-1"
        ),
    }
    require(
        all(os.environ.get(key) == value for key, value in expected.items()),
        "worker-coordinates",
    )
    return expected


def _replay_inputs(port, account):
    source = Path("/trusted" if account == "test" else "/source") / ".artifacts"
    destination = port.repo / ".artifacts"
    destination.mkdir(mode=0o700, exist_ok=True)
    for name in ("pulumi-plan", "pulumi-preview"):
        copy_tree(source / name, destination / name)


def _prod(port, command, head):
    source_head(head)
    project = port.project(Path("/source/pulumi"))
    context = registry.runner.CommandContext(
        root_dir=port.repo,
        env={"PULUMI_COMMIT_SHA": head},
        pulumi_dir=project,
        policy_pack_dir=Path("/source/policy"),
        plan_dir=port.repo / ".artifacts/pulumi-plan",
        preview_artifact_dir=port.repo / ".artifacts/pulumi-preview",
        backend_url=os.environ["PULUMI_BACKEND_URL"],
        secrets_provider=os.environ["PULUMI_SECRETS_PROVIDER"],
    )
    return registry.runner._dispatch_command(command, port.bind(context), ["prod"])


def execute(job, area):
    require(job in JOBS and os.environ.get("GITHUB_JOB") == job, "worker-job")
    account, command = JOBS[job]
    head = admit(job)
    coordinates = _coordinates(account)
    port = ServiceTransport(
        area,
        session={key: os.environ.get(key, "") for key in SESSION_KEYS},
        region=coordinates["AWS_REGION"],
        account=coordinates["AWS_ACCOUNT_ID"],
        before_program=lambda: require(
            admit(job) == head, "worker-pre-execution-admission"
        ),
    )
    if command == "up-plan":
        _replay_inputs(port, account)
    if job == "scheduled_test_drift":
        result = scheduled.execute(transport=port)
    elif account == "test":
        result = registry.execute(
            command,
            artifact_id=os.environ["POC_SOURCE_ARTIFACT_ID"],
            archive_sha256=os.environ["POC_SOURCE_ARCHIVE_SHA256"],
            source_sha256=os.environ["POC_SOURCE_SHA256"],
            transport=port,
        )
    else:
        result = _prod(port, command, head)
    require(result == 0, "worker-execution")
    require(admit(job) == head, "worker-final-admission")
    if command == "plan":
        output = Path("/public")
        for name in ("pulumi-plan", "pulumi-preview"):
            copy_tree(port.repo / ".artifacts" / name, output / name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=tuple(JOBS))
    arguments = parser.parse_args(argv)
    try:
        require(os.geteuid() == 0 and os.getpid() == 1, "worker-root-pid")
        # The launcher supplies a clean fixed PATH; private logs never reach Actions.
        require(
            os.environ.get("PATH") == "/opt/pulumi:/usr/local/bin:/usr/bin:/bin",
            "worker-path",
        )
        with tempfile.TemporaryDirectory(prefix="service-worker-") as name:
            area = Path(name)
            home = area / "root-home"
            home.mkdir(mode=0o700)
            os.environ["HOME"] = str(home)
            with (area / "private.log").open("w") as log:
                (area / "private.log").chmod(0o600)
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    execute(arguments.job, area)
        print("Service execution completed with trusted checks.")
        return 0
    except Exception:
        print("Service execution failed its trusted prerequisites.", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
