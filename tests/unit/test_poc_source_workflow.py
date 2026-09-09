"""The source-fact producer runs only trusted code and gates the cloud graph."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def jobs():
    """Load the actual workflow, including all downstream promotion edges."""
    return yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())[
        "jobs"
    ]


def source_job():
    """Select the dedicated source producer."""
    return jobs()["poc_prepare_source"]


def shell(script, environment):
    """Execute workflow shell with GitHub's fail-fast bash semantics."""
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        env={**os.environ, **environment},
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("target,code", [("test", 0), ("prod", 1), ("", 1), ("dev", 1)])
def test_test_only_route_rejects_prod_explicitly_before_runtime(target, code):
    """Unsupported targets fail instead of skipping into the promotion graph."""
    first = source_job()["steps"][0]
    result = shell(first["run"], {"TARGET_ENVIRONMENT": target})
    assert result.returncode == code
    if code:
        assert "TEST only; PROD promotion is unavailable" in result.stderr
    assert first["env"] == {
        "TARGET_ENVIRONMENT": "${{ needs.preflight.outputs.target_environment }}"
    }


def test_source_worker_has_only_read_authority_and_main_checkout():
    """No PR checkout, protected environment, OIDC or write token reaches this job."""
    job = source_job()
    assert job["needs"] == ["preflight"]
    assert job["permissions"] == {
        "contents": "read",
        "actions": "read",
        "issues": "read",
        "pull-requests": "read",
    }
    assert "environment" not in job and "env" not in job
    actions = [step for step in job["steps"] if "uses" in step]
    assert [step["uses"] for step in actions] == [
        "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ]
    assert actions[0]["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": False,
    }
    assert all(
        "continue-on-error" not in step and "if" not in step for step in job["steps"]
    )


def test_runtime_reuses_verified_docker_uv_pin_and_frozen_main_lock():
    """Install the existing pinned tool before resolving trusted locked dependencies."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    version = re.search(r"^ARG UV_VERSION=(.+)$", dockerfile, re.MULTILINE)[1]
    digest = re.search(r"^ARG UV_SHA256_AMD64=(.+)$", dockerfile, re.MULTILINE)[1]
    install = source_job()["steps"][2]
    script = install["run"]
    assert f"/download/{version}/uv-x86_64-unknown-linux-gnu.tar.gz" in script
    assert digest in script
    assert script.index("sha256sum --check --status") < script.index("tar -xzf")
    assert script.index("tar -xzf") < script.index(
        "sync --frozen --no-dev --python 3.11"
    )
    assert 'test "$(git rev-parse HEAD)" = "${GITHUB_SHA}"' in script
    assert 'test "${GITHUB_WORKFLOW_SHA}" = "${GITHUB_SHA}"' in script
    assert install["env"]["UV_PYTHON_PREFERENCE"] == "only-managed"
    assert "GH_TOKEN" not in install["env"]


def test_runtime_rejects_tampered_download_before_extraction(tmp_path):
    """Run the actual installer shell against a corrupt download, without network."""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    marker = tmp_path / "extracted"
    scripts = {
        "git": '#!/bin/sh\nprintf "%s\\n" "$GITHUB_SHA"\n',
        "curl": '#!/bin/sh\nwhile [ "$1" != --output ]; do shift; done\n'
        'printf corrupt > "$2"\n',
        "tar": f'#!/bin/sh\ntouch "{marker}"\n',
    }
    for name, contents in scripts.items():
        path = binaries / name
        path.write_text(contents)
        path.chmod(0o700)
    result = shell(
        source_job()["steps"][2]["run"],
        {
            "PATH": f"{binaries}:{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_SHA": "a" * 40,
        },
    )
    assert result.returncode != 0
    assert not marker.exists()


def test_adapter_accepts_only_six_preflight_outputs_and_isolated_main_code():
    """Dispatch payloads and PR-controlled paths never become executable inputs."""
    step = next(step for step in source_job()["steps"] if step.get("id") == "prepare")
    fields = {
        "pull_request_number",
        "head_sha",
        "comment_id",
        "source_run_id",
        "command",
        "target_environment",
    }
    assert step["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        **{
            f"REQUEST_{key.upper()}": "${{ needs.preflight.outputs." + key + " }}"
            for key in fields
        },
    }
    assert '"${GITHUB_WORKSPACE}/.venv/bin/python" -I' in step["run"]
    assert '"${GITHUB_WORKSPACE}/scripts/poc_phase_source_adapter.py"' in step["run"]
    assert "${{" not in step["run"]
    assert "make " not in step["run"] and "pulumi " not in step["run"]


@pytest.mark.parametrize("exit_code", [0, 1])
def test_adapter_output_is_hash_bound_only_after_success(tmp_path, exit_code):
    """The wrapper hashes exact stdout bytes and emits nothing after adapter failure."""
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(
        '#!/bin/sh\ntest "$1" = -I || exit 9\n'
        'test "$2" = "$GITHUB_WORKSPACE/scripts/poc_phase_source_adapter.py"'
        " || exit 9\n"
        f'printf \'{{"kind":"poc-phase-source/v1"}}\\n\'\nexit {exit_code}\n'
    )
    python.chmod(0o700)
    output = tmp_path / "outputs"
    prepare = next(
        step for step in source_job()["steps"] if step.get("id") == "prepare"
    )
    result = shell(
        prepare["run"],
        {
            "GITHUB_WORKSPACE": str(tmp_path),
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_OUTPUT": str(output),
        },
    )
    assert result.returncode == exit_code
    if exit_code:
        assert not output.exists()
    else:
        payload = (tmp_path / "poc-phase-source/source.json").read_bytes()
        assert (
            output.read_text()
            == f"source_sha256={hashlib.sha256(payload).hexdigest()}\n"
        )


def test_upload_matches_same_run_artifact_verifier_protocol():
    """Consumer coordinates come only from upload outputs and exact member bytes."""
    job = source_job()
    upload = job["steps"][-1]
    assert upload["id"] == "source_artifact"
    assert upload["with"] == {
        "name": "poc-phase-source-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "${{ runner.temp }}/poc-phase-source/source.json",
        "if-no-files-found": "error",
        "overwrite": False,
        "retention-days": 7,
    }
    assert job["outputs"] == {
        "artifact_id": "${{ steps.source_artifact.outputs.artifact-id }}",
        "archive_sha256": "${{ steps.source_artifact.outputs.artifact-digest }}",
        "source_sha256": "${{ steps.prepare.outputs.source_sha256 }}",
    }


def test_every_cloud_or_promotion_job_requires_successful_source_ancestry():
    """A failed TEST route blocks AWS and promotion; only feedback may run always."""
    graph = jobs()

    def ancestors(name):
        direct = set(graph[name].get("needs", []))
        return direct | {
            ancestor for parent in direct for ancestor in ancestors(parent)
        }

    for name in (
        "test_preview",
        "test_apply",
        "test_post_apply_drift",
        "prod_preview",
        "prod_apply",
        "prod_post_apply_drift",
        "platform_promotion",
    ):
        assert "poc_prepare_source" in ancestors(name)
        condition = graph[name].get("if", "")
        if "always(" in condition:
            # PROD preview intentionally handles a skipped post-apply drift on
            # plan commands, but still requires the source-gated TEST preview.
            assert name == "prod_preview"
            assert condition == (
                "always() && needs.preflight.result == 'success' && "
                "needs.preflight.outputs.target_environment == 'prod' && "
                "needs.test_preview.result == 'success' && "
                "(needs.preflight.outputs.command == 'plan' || "
                "needs.test_post_apply_drift.result == 'success')"
            )
            assert "test_preview" in graph[name]["needs"]
        assert "continue-on-error" not in graph[name]
    feedback = graph["comment_result"]
    assert "poc_prepare_source" in feedback["needs"]
    assert "needs.poc_prepare_source.result" in feedback["steps"][0]["run"]
