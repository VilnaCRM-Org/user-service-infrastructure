"""Check no-change wire compatibility using the pinned CLI and a local component."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
gate = importlib.import_module("poc_workload_reconciliation")


def test_native_no_change_saved_plan(tmp_path, ensure_pulumi_cli):
    """No AWS provider, network operation, real credential or cloud state is used."""
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    backend = tmp_path / "backend"
    backend.mkdir()
    env.update(
        PULUMI_BACKEND_URL=backend.as_uri(),
        PULUMI_HOME=str(tmp_path / "home"),
        PULUMI_CONFIG_PASSPHRASE="synthetic-local-test-only",
        PULUMI_SKIP_UPDATE_CHECK="true",
        PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION="true",
        PULUMI_PYTHON_CMD=sys.executable,
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / "Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime:\n  name: python\n"
        f"  options:\n    virtualenv: {json.dumps(sys.prefix)}\n"
    )
    (project / "__main__.py").write_text(
        "import pulumi\n"
        "component = pulumi.ComponentResource('synthetic:workload:Plane', 'workload')\n"
        "component.register_outputs({'private': pulumi.Output.secret('synthetic')})\n"
    )

    def cli(*args):
        result = subprocess.run(
            ["pulumi", "-C", str(project), *args],
            env=env,
            capture_output=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, f"Local Pulumi {args[0]} failed"
        return result.stdout

    if cli("version").strip() != b"v3.223.0":
        pytest.skip("Saved-plan protocol requires Pulumi v3.223.0")
    cli(
        "stack", "init", "test", "--secrets-provider", "passphrase", "--non-interactive"
    )
    cli("preview", "--save-plan", "create.plan", "--json", "--non-interactive")
    cli("up", "--plan", "create.plan", "--skip-preview", "--yes", "--non-interactive")
    state = json.loads(cli("stack", "export"))
    preview = json.loads(
        cli("preview", "--save-plan", "same.plan", "--json", "--non-interactive")
    )
    saved = json.loads((project / "same.plan").read_bytes())
    gate.validate_no_change(
        preview, saved_plan=saved, prior_resources=state["deployment"]["resources"]
    )
