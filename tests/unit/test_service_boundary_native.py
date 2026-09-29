"""Opt-in real container isolation and disabled-entrypoint regressions."""

import os
import subprocess

import pytest

IMAGE = os.environ.get("SERVICE_BOUNDARY_TEST_IMAGE")


@pytest.mark.skipif(not IMAGE, reason="Explicit locally built boundary image required")
@pytest.mark.parametrize(
    "arguments,environment,code,message",
    [
        (["smoke"], [], 0, "ISOLATED_BOUNDARY_PASS"),
        ([], [], 1, "PR deployment is disabled"),
        (["execute", "/source/PR.py"], [], 1, "PR deployment is disabled"),
        (
            ["smoke"],
            ["-e", "AWS_SESSION_TOKEN=synthetic-not-a-credential"],
            1,
            "Isolated boundary smoke failed",
        ),
    ],
)
def test_real_boundary_rejects_deployment_and_credentials(
    arguments, environment, code, message
):
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=16m",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "SETUID",
            "--cap-add",
            "SETGID",
            "--cap-add",
            "KILL",
            "--pids-limit",
            "32",
            "--security-opt",
            "no-new-privileges",
            *environment,
            IMAGE,
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == code, result.stderr
    assert message in result.stdout + result.stderr
