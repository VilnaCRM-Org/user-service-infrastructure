"""Execute Make against a fake Compose binary without cloud or container calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "target,command",
    [
        ("pulumi-plan", "plan"),
        ("pulumi-up-plan", "up-plan"),
        ("test-drift", "drift"),
        ("initialize-stack", "initialize"),
    ],
)
@pytest.mark.parametrize("mode", ["local", "static-ci", "temporary-ci"])
def test_cloud_make_commands_export_selected_stack_and_scoped_credentials(
    tmp_path, target, command, mode
):
    """Make passes names, preserving stack selection without leaking token values."""
    recorder = tmp_path / "compose.py"
    record = tmp_path / "record.json"
    recorder.write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['RECORD']).write_text(json.dumps({"
        "'argv': sys.argv[1:], 'stack': os.environ.get('PULUMI_STACK'),"
        "'github': os.environ.get('GITHUB_TOKEN')}))\n"
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "RECORD": str(record),
        "AWS_ACCESS_KEY_ID": "synthetic-access",
        "AWS_SECRET_ACCESS_KEY": "synthetic-secret",
    }
    if mode != "local":
        env["GITHUB_ACTIONS"] = "true"
    if mode == "temporary-ci":
        env["AWS_SESSION_TOKEN"] = "synthetic-session"
    result = subprocess.run(
        [
            "make",
            "--no-print-directory",
            target,
            f"DOCKER_COMPOSE={sys.executable} {recorder}",
            "ENV_FILE=/does/not/exist",
            "PULUMI_STACK=prod",
            "GITHUB_TOKEN=synthetic-github",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(record.read_text())
    assert payload["stack"] == "prod"
    assert payload["github"] == "synthetic-github"
    args = payload["argv"]
    assert args[-1] == command
    forwarded = {args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "-e"}
    assert {"PULUMI_STACK", "GITHUB_TOKEN"} <= forwarded
    credential_names = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    }
    assert forwarded & credential_names == (
        credential_names if mode == "temporary-ci" else set()
    )
    assert not any(
        value in result.stdout
        for value in (
            "synthetic-access",
            "synthetic-secret",
            "synthetic-session",
            "synthetic-github",
        )
    )
