"""Installed service worker: authenticate in root, execute Pulumi as UID 2000.

The workflow supplies immutable mounts and its existing credentials. This entry
point observes workload prerequisites but does not execute a workload graph.
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
from service_execution_process import require  # noqa: E402
from service_execution_transport import ServiceTransport, copy_tree  # noqa: E402

JOBS = {
    "test_preview": ("test", "plan"),
    "test_apply": ("test", "up-plan"),
    "test_post_apply_drift": ("test", "drift"),
}
ACCOUNTS = {"test": "891377212104"}
SESSION_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def admit(job):
    """Reuse original native requester/reviewer or scheduled-main authority."""
    require(job in JOBS, "worker-job")
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
    require(account == "test", "worker-account")
    source = Path("/trusted") / ".artifacts"
    destination = port.repo / ".artifacts"
    destination.mkdir(mode=0o700, exist_ok=True)
    for name in ("pulumi-plan", "pulumi-preview"):
        copy_tree(source / name, destination / name)


def _test(port, command, head):
    references = {
        "artifact_id": os.environ["POC_SOURCE_ARTIFACT_ID"],
        "archive_sha256": os.environ["POC_SOURCE_ARCHIVE_SHA256"],
        "source_sha256": os.environ["POC_SOURCE_SHA256"],
    }
    source, contract = registry.artifact.load_verified_contract(**references)
    require(
        source["source"]["head_sha"] == head
        and source["source"]["base_sha"] == os.environ["GITHUB_SHA"]
        and source["request"]["target_environment"] == "test",
        "workload-source-binding",
    )
    registry._review(source)
    if contract["phase"] == "workload":
        raise ValueError("workload-execution-not-enabled")
    return registry.execute(command, **references, transport=port)


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
    result = _test(port, command, head)
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
