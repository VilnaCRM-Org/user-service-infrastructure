"""TEST registry execution stays on installed code across plan, replay and drift."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKERS = {
    "test_preview": ("Save test update plan and preview artifact", "plan"),
    "test_apply": ("Apply saved test plan", "up-plan"),
    "test_post_apply_drift": ("Run test post-apply drift detection", "drift"),
}
RUNTIME = "./.trusted/.github/actions/setup-poc-runtime"


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())[
        "jobs"
    ]


def runtime():
    return yaml.safe_load(
        (ROOT / ".github/actions/setup-poc-runtime/action.yml").read_text()
    )


def step_for(job):
    return next(
        step for step in workflow()[job]["steps"] if step.get("name") == WORKERS[job][0]
    )


@pytest.mark.parametrize("name", WORKERS)
def test_each_worker_installs_trusted_runtime_before_credentials(name):
    """Installation cannot run from PR code or inside the AWS credential boundary."""
    job = workflow()[name]
    steps = job["steps"]
    install = next(s for s in steps if s.get("uses") == RUNTIME)
    checkout = next(s for s in steps if s.get("with", {}).get("path") == ".trusted")
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    assert steps.index(checkout) < steps.index(install)
    assert "preflight" in job["needs"] and "poc_prepare_source" in job["needs"]
    assert job["permissions"]["actions"] == "read"
    for step in steps:
        if step.get("uses", "").endswith("load-aws-ci-env") or step.get(
            "uses", ""
        ).startswith("aws-actions/"):
            assert steps.index(install) < steps.index(step)
            assert "Verify reviewed source" in steps[steps.index(step) - 1]["name"]
        assert "make " not in step.get("run", "")
        assert "continue-on-error" not in step
    assert "if" not in install and "env" not in install
    assert job["concurrency"]["cancel-in-progress"] is False
    assert (
        job["concurrency"]["group"] == "pulumi-state-${{ github.repository }}-test-test"
    )


@pytest.mark.parametrize("name", WORKERS)
def test_driver_receives_only_same_run_source_coordinates(name):
    """The fixed installed entrypoint receives upload outputs through quoted env."""
    step = step_for(name)
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    for key, output in (
        ("POC_SOURCE_ARTIFACT_ID", "artifact_id"),
        ("POC_SOURCE_ARCHIVE_SHA256", "archive_sha256"),
        ("POC_SOURCE_SHA256", "source_sha256"),
    ):
        assert (
            step["env"][key] == "${{ needs.poc_prepare_source.outputs." + output + " }}"
        )
    assert '"${GITHUB_WORKSPACE}/.trusted/.venv/bin/python" -I' in step["run"]
    assert (
        '"${GITHUB_WORKSPACE}/.trusted/scripts/poc_registry_runner.py" '
        + WORKERS[name][1]
        in step["run"]
    )
    assert "${{" not in step["run"]
    assert "if" not in step and "continue-on-error" not in step


def test_artifacts_round_trip_under_driver_root_and_replay_rechecks_after_downloads():
    """Both original artifacts arrive where the driver's manifest resolves them."""
    jobs = workflow()
    uploads = [
        s
        for s in jobs["test_preview"]["steps"]
        if s.get("uses", "").startswith("actions/upload-artifact@")
    ]
    downloads = [
        s
        for s in jobs["test_apply"]["steps"]
        if s.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert len(uploads) == len(downloads) == 2
    assert {s["with"]["path"] for s in downloads} == {
        ".trusted/.artifacts/pulumi-plan",
        ".trusted/.artifacts/pulumi-preview",
    }
    assert {(s["with"]["name"], s["with"]["path"]) for s in uploads} == {
        (s["with"]["name"], s["with"]["path"]) for s in downloads
    }
    assert all(s["with"]["if-no-files-found"] == "error" for s in uploads)
    steps = jobs["test_apply"]["steps"]
    replay = steps.index(step_for("test_apply"))
    assert (
        steps[replay - 1]["name"] == "Verify reviewed source before saved-plan replay"
    )
    assert all(steps.index(s) < replay - 1 for s in downloads)
    assert "git rev-parse HEAD" in steps[replay]["run"]
    assert "EXPECTED_BASE_SHA" in steps[replay]["run"]


def test_post_apply_drift_uses_closed_driver_with_preview_identity():
    """Drift requires successful apply and retains native observer authority."""
    job = workflow()["test_post_apply_drift"]
    assert "test_apply" in job["needs"]
    assert job["if"] == "needs.preflight.outputs.command == 'up'"
    assert job["environment"] == "test-preview"
    config = next(s for s in job["steps"] if s.get("id") == "ci_config")
    assert "AWS_PREVIEW_ROLE_ARN" in config["with"]["required-keys"]
    assert "AWS_DRIFT_ROLE_ARN" not in config["with"]["required-keys"]
    credentials = next(
        s for s in job["steps"] if s.get("uses", "").startswith("aws-actions/")
    )
    assert (
        credentials["with"]["role-to-assume"]
        == "${{ steps.ci_config.outputs.aws-preview-role-arn }}"
    )
    assert (
        credentials["with"]["role-session-name"]
        == "gha-pr-test-preview-${{ github.run_id }}"
    )
    assert not any(
        s.get("uses", "").startswith("actions/download-artifact@") for s in job["steps"]
    )


def test_noncredential_destructive_gate_runs_trusted_helper():
    """The review gate must never execute the downloaded PR Makefile."""
    job = workflow()["test_destructive_diff"]
    checkout = job["steps"][0]
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert "environment" not in job
    runs = "\n".join(s.get("run", "") for s in job["steps"])
    assert "make " not in runs
    assert 'python3 -I "${GITHUB_WORKSPACE}/scripts/pulumi_ci_guardrails.py"' in runs
    assert 'destructive-gate "${previews[@]}"' in runs
    assert 'test "${#previews[@]}" -gt 0' in runs


@pytest.mark.parametrize(
    "name,head_moved",
    [(name, False) for name in WORKERS] + [("test_apply", True)],
)
@pytest.mark.parametrize("exit_code", [0, 7])
def test_actual_driver_wrapper_preserves_arguments_and_exit_status(
    tmp_path, name, head_moved, exit_code
):
    """Execute the workflow shell with only external driver/GitHub transports faked."""
    trusted = tmp_path / ".trusted"
    python = trusted / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    output = tmp_path / "invocation.json"
    python.write_text(
        f"#!{sys.executable}\nimport json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(int(os.environ['DRIVER_EXIT']))\n"
    )
    python.chmod(0o700)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    head, base = "a" * 40, "b" * 40
    pr = json.dumps(
        {
            "state": "open",
            "merged": False,
            "head": {"sha": "c" * 40 if head_moved else head},
            "base": {"ref": "main", "sha": base},
        }
    )
    for filename, contents in {
        "gh": f"#!{sys.executable}\nprint({pr!r})\n",
        "git": f"#!/bin/sh\nprintf '%s\\n' '{head}'\n",
    }.items():
        path = binaries / filename
        path.write_text(contents)
        path.chmod(0o700)
    preview = trusted / ".artifacts/pulumi-preview/test.json"
    preview.parent.mkdir(parents=True)
    preview.write_text('{"steps":[]}')
    coordinates = ["123", "c" * 64, "d" * 64]
    environment = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "GITHUB_WORKSPACE": str(tmp_path),
        "GITHUB_REPOSITORY": "VilnaCRM-Org/user-service-infrastructure",
        "PR_NUMBER": "219",
        "EXPECTED_SHA": head,
        "EXPECTED_BASE_SHA": base,
        "RECORD": str(output),
        "DRIVER_EXIT": str(exit_code),
        "POC_SOURCE_ARTIFACT_ID": coordinates[0],
        "POC_SOURCE_ARCHIVE_SHA256": coordinates[1],
        "POC_SOURCE_SHA256": coordinates[2],
    }
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step_for(name)["run"]],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if head_moved:
        assert result.returncode != 0
        assert not output.exists()
        return
    assert result.returncode == exit_code, result.stderr
    assert json.loads(output.read_text()) == [
        "-I",
        str(trusted / "scripts/poc_registry_runner.py"),
        WORKERS[name][1],
        "--artifact-id",
        coordinates[0],
        "--archive-sha256",
        coordinates[1],
        "--source-sha256",
        coordinates[2],
    ]
    assert preview.read_text() == '{"steps":[]}'


def test_composite_reuses_exact_runtime_pins_and_isolates_dependency_install():
    """Both archives are verified before extraction and sync uses the trusted lock."""
    action = runtime()
    assert action["runs"]["using"] == "composite"
    assert "inputs" not in action
    step = action["runs"]["steps"][0]
    assert step["working-directory"] == "${{ github.workspace }}/.trusted"
    assert step["env"]["UV_PYTHON_PREFERENCE"] == "only-managed"
    script = step["run"]
    dockerfile = (ROOT / "Dockerfile").read_text()
    for name in (
        "UV_VERSION",
        "UV_SHA256_AMD64",
        "PULUMI_VERSION",
        "PULUMI_SHA256_AMD64",
    ):
        assert re.search(rf"^ARG {name}=(.+)$", dockerfile, re.MULTILINE)[1] in script
    assert script.count("sha256sum --check --status") == 2
    assert script.count("tar -xzf") == 2
    assert 'UV_PROJECT_ENVIRONMENT="${GITHUB_WORKSPACE}/.trusted/.venv"' in script
    assert "sync --frozen --no-dev --python 3.11" in script
    assert "GITHUB_TOKEN" not in script and "GH_TOKEN" not in script
    provider_install = (
        '"${GITHUB_WORKSPACE}/.trusted/scripts/poc_provider_runtime.py" install'
    )
    assert provider_install in script
    assert script.index("sync --frozen") < script.index(provider_install)
    assert script.index(provider_install) < script.index('>> "${GITHUB_PATH}"')
    assert '"${GITHUB_WORKSPACE}/.trusted/.venv/bin/python" -I' in script
    assert (
        'test "$(git rev-parse --show-toplevel)" = "${GITHUB_WORKSPACE}/.trusted"'
        in script
    )


@pytest.mark.parametrize("failed_archive", ["uv", "pulumi"])
def test_composite_checksum_failure_stops_before_tool_execution(
    tmp_path, failed_archive
):
    """A failed archive check stops the actual installer before tool execution."""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    marker = tmp_path / "tool-executed"
    log = tmp_path / "extracts"
    stubs = {
        "git": '#!/bin/sh\nif [ "$2" = --show-toplevel ]; then\n'
        'printf "%s/.trusted\\n" "$GITHUB_WORKSPACE"\n'
        'else printf "%s\\n" "$GITHUB_SHA"; fi\n',
        "uname": "#!/bin/sh\necho x86_64\n",
        "curl": '#!/bin/sh\nwhile [ "$1" != --output ]; do shift; done\n'
        'printf corrupt > "$2"\n',
        "sha256sum": "#!/bin/sh\nread -r line\n"
        f'case "$line" in *"/{failed_archive}.tar.gz") exit 1;; *) exit 0;; esac\n',
        "tar": f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\n',
    }
    for name, contents in stubs.items():
        path = binaries / name
        path.write_text(contents)
        path.chmod(0o700)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", runtime()["runs"]["steps"][0]["run"]],
        env={
            **os.environ,
            "PATH": f"{binaries}:{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_WORKSPACE": str(tmp_path),
            "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_SHA": "a" * 40,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_PATH": str(marker),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert not marker.exists()
    extracts = log.read_text().splitlines() if log.exists() else []
    assert len(extracts) == (0 if failed_archive == "uv" else 1)
    assert all(f"/{failed_archive}.tar.gz" not in call for call in extracts)


def test_provider_install_failure_stops_actual_composite_before_runtime_export(
    tmp_path,
):
    """The real shell propagates verifier failure instead of enabling credentials."""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    trusted_python = tmp_path / ".trusted/.venv/bin/python"
    trusted_python.parent.mkdir(parents=True)
    trusted_python.write_text(
        "#!/bin/sh\n"
        'test "$1" = -I || exit 90\n'
        'test "$2" = "${GITHUB_WORKSPACE}/.trusted/scripts/'
        'poc_provider_runtime.py" || exit 91\n'
        'test "$3" = install || exit 92\n'
        'printf verifier > "${GITHUB_WORKSPACE}/verified-step"\n'
        "exit 23\n"
    )
    trusted_python.chmod(0o700)
    stubs = {
        "git": '#!/bin/sh\nif [ "$2" = --show-toplevel ]; then\n'
        'printf "%s/.trusted\\n" "$GITHUB_WORKSPACE"\n'
        'else printf "%s\\n" "$GITHUB_SHA"; fi\n',
        "uname": "#!/bin/sh\necho x86_64\n",
        "curl": "#!/bin/sh\nexit 0\n",
        "sha256sum": "#!/bin/sh\ncat > /dev/null\nexit 0\n",
        "tar": '#!/bin/sh\nwhile [ "$1" != -C ]; do shift; done\n'
        'case "$2" in */uv) printf "#!/bin/sh\\nexit 0\\n" > "$2/uv"; '
        'chmod 700 "$2/uv";; esac\n',
    }
    for name, contents in stubs.items():
        path = binaries / name
        path.write_text(contents)
        path.chmod(0o700)
    marker = tmp_path / "runtime-export"
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", runtime()["runs"]["steps"][0]["run"]],
        env={
            "PATH": f"{binaries}:{os.defpath}",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_WORKSPACE": str(tmp_path),
            "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_SHA": "a" * 40,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_PATH": str(marker),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 23, result.stderr
    assert (tmp_path / "verified-step").read_text() == "verifier"
    assert not marker.exists()
