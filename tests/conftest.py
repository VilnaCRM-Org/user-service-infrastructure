"""Shared pytest fixtures for Pulumi automation tests."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PULUMI_PROGRAM_ROOT = PROJECT_ROOT / "pulumi"
_COVERAGE_CONFIG = PROJECT_ROOT / ".coveragerc"

if str(PULUMI_PROGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(PULUMI_PROGRAM_ROOT))


@pytest.fixture(scope="session", autouse=True)
def pulumi_automation_environment(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Ensure Pulumi automation invocations work without cloud credentials."""
    if shutil.which("pulumi") is None:
        return

    os.environ.setdefault("PULUMI_SKIP_UPDATE_CHECK", "true")
    python_cmd = sys.executable

    if _COVERAGE_CONFIG.exists():
        os.environ.setdefault("COVERAGE_PROCESS_START", str(_COVERAGE_CONFIG))
        os.environ.setdefault("COVERAGE_FILE", str(PROJECT_ROOT / ".coverage"))

    os.environ.setdefault("PULUMI_PYTHON_CMD", python_cmd)
    backend_url = os.environ.get("PULUMI_BACKEND_URL", "")

    if os.environ.get("PULUMI_ACCESS_TOKEN"):
        return
    if backend_url:
        if backend_url.startswith("file://"):
            os.environ.setdefault(
                "PULUMI_CONFIG_PASSPHRASE", "integration-test-passphrase"
            )
        return

    backend_dir = tmp_path_factory.mktemp("pulumi-backend")
    backend_uri = Path(backend_dir).resolve().as_uri()

    env = os.environ.copy()
    env["PULUMI_HOME"] = str(backend_dir)
    env["PULUMI_CONFIG_PASSPHRASE"] = env.get(
        "PULUMI_CONFIG_PASSPHRASE", "integration-test-passphrase"
    )

    subprocess.run(["pulumi", "login", backend_uri], check=True, env=env, timeout=30)

    os.environ.setdefault("PULUMI_HOME", str(backend_dir))
    os.environ.setdefault("PULUMI_BACKEND_URL", backend_uri)
    os.environ.setdefault("PULUMI_CONFIG_PASSPHRASE", env["PULUMI_CONFIG_PASSPHRASE"])


@pytest.fixture(scope="session")
def ensure_pulumi_cli() -> None:
    """Skip integration cases that require the Pulumi CLI when it is unavailable."""
    if shutil.which("pulumi") is None:
        pytest.skip("Pulumi CLI binary is not available in PATH.")
