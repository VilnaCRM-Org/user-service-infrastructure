"""Ordinary scheduled drift preserves the installed metadata component graph."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _pulumi_command_support import (  # noqa: E402
    CommandContext,
    StackCommand,
    _pulumi_command,
)


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_scheduled_drift_preserves_baseline_metadata_graph(
    tmp_path, ensure_pulumi_cli, environment
):
    """Use the real CLI/policy pack with a synthetic caller and local checkpoint."""
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/scheduled-drift.yml").read_text()
    )
    job = workflow["jobs"][f"scheduled_{environment}_drift"]
    assert job["steps"][-1]["run"] == "make test-drift"
    assert (
        "uv run --frozen python scripts/run_pulumi_command.py drift"
        in (ROOT / "Makefile").read_text()
    )

    project = tmp_path / "project"
    project.mkdir()
    shutil.copytree(
        ROOT / "pulumi/app",
        project / "app",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    policy = tmp_path / "policy"
    shutil.copytree(
        ROOT / "policy", policy, ignore=shutil.ignore_patterns(".venv", "__pycache__")
    )
    (policy / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    (project / "Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime:\n  name: python\n"
        f"  options:\n    virtualenv: {json.dumps(sys.prefix)}\n"
    )
    baseline = {
        "environment": environment,
        "serviceName": "user-service",
        "awsAccountId": "123456789012",
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": f"s3://synthetic-{environment}-state",
        "pulumiSecretsProvider": "awskms://alias/synthetic?region=eu-central-1",
        # A managed hint cannot enable workload composition via the ordinary entrypoint.
        "deploymentMode": "managed",
    }
    (project / f"Pulumi.{environment}.yaml").write_text(
        json.dumps(
            {
                "config": {
                    f"user-service-infrastructure:{key}": value
                    for key, value in baseline.items()
                }
            }
        )
    )
    metadata_program = (
        "import pulumi\nfrom app import EnvironmentSettings\n"
        "settings = EnvironmentSettings('environment-settings')\n"
        "config = pulumi.Config()\n"
        "pulumi.export('environment', settings.environment)\n"
        "pulumi.export('serviceName', settings.service_name)\n"
        "pulumi.export('stackTag', settings.stack_tag)\n"
        "pulumi.export('defaultTags', settings.default_tags)\n"
        "for key in ('repoSlug', 'pulumiBackendUrl', 'pulumiSecretsProvider'):\n"
        "    pulumi.export(key, config.require(key))\n"
    )
    (project / "__main__.py").write_text(metadata_program)
    backend = tmp_path / "backend"
    backend.mkdir()
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    env.update(
        PULUMI_BACKEND_URL=backend.as_uri(),
        PULUMI_HOME=str(tmp_path / "home"),
        PULUMI_CONFIG_PASSPHRASE="synthetic-local-test-only",
        PULUMI_SKIP_UPDATE_CHECK="true",
        PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION="true",
        PULUMI_PYTHON_CMD=sys.executable,
    )

    def cli(*arguments):
        result = subprocess.run(
            ["pulumi", "-C", str(project), *arguments],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    cli(
        "stack",
        "init",
        environment,
        "--secrets-provider",
        "passphrase",
        "--non-interactive",
    )
    cli("up", "--yes", "--skip-preview", "--non-interactive")
    prior = json.loads(cli("stack", "export"))["deployment"]["resources"]
    assert {resource["type"] for resource in prior} == {
        "pulumi:pulumi:Stack",
        "user-service-infrastructure:core:EnvironmentSettings",
    }
    assert len(prior) == 2
    assert any(resource["urn"].endswith("::environment-settings") for resource in prior)

    # Fake only STS identity. The installed entrypoint, component registration,
    # native checkpoint comparison and policy pack run unchanged without AWS access.
    (project / "__main__.py").write_text(
        "from types import SimpleNamespace\nimport pulumi_aws as aws\n"
        "aws.get_caller_identity = lambda: SimpleNamespace(account_id='123456789012')\n"
        + (ROOT / "pulumi/__main__.py").read_text()
    )
    context = CommandContext(
        root_dir=tmp_path,
        env=env,
        pulumi_dir=project,
        policy_pack_dir=policy,
        plan_dir=tmp_path / "plan",
        preview_artifact_dir=tmp_path / "preview",
        backend_url=backend.as_uri(),
        secrets_provider="passphrase",
    )
    command = _pulumi_command(context, StackCommand("drift", environment))
    assert command[:4] == ["pulumi", "-C", str(project), "preview"]
    assert "--refresh" in command and "--expect-no-changes" in command
    assert command[-2:] == ["--policy-pack", str(policy)]
    result = subprocess.run(
        [*command, "--json", "--show-sames"],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert all(
        operation == "same" or count == 0
        for operation, count in preview["changeSummary"].items()
    )
    assert {step["urn"] for step in preview["steps"]} <= {
        resource["urn"] for resource in prior
    }
    assert all(step["op"] in {"same", "refresh"} for step in preview["steps"])
    # Refresh pre-events and same.newState are partial CLI event projections.
    # Final same.oldState carries the observed graph and must match the baseline.
    final = {
        step["urn"]: step["oldState"]
        for step in preview["steps"]
        if step["op"] == "same"
    }
    assert set(final) == {resource["urn"] for resource in prior}
    for resource in prior:
        for field in ("urn", "type", "parent", "inputs", "outputs"):
            assert final[resource["urn"]].get(field) == resource.get(field)
    assert json.loads(cli("stack", "export"))["deployment"]["resources"] == prior
