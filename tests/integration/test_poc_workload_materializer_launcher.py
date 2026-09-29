"""Native local Pulumi launcher smoke; no workload, provider download or network."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from poc_workload_phase_entrypoint import workload_python_wrapper_source  # noqa: E402


@pytest.mark.parametrize("virtualenv", [False, True])
def test_native_pulumi_wrapper_requires_project_without_virtualenv(
    tmp_path, virtualenv
):
    pulumi = shutil.which("pulumi")
    bubblewrap = shutil.which("bwrap")
    if not pulumi or not bubblewrap:
        pytest.skip("Native launcher test requires Pulumi and bubblewrap")
    available = subprocess.run(
        [
            bubblewrap,
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--ro-bind",
            "/",
            "/",
            "--clearenv",
            "/usr/bin/true",
        ],
        capture_output=True,
        check=False,
        timeout=20,
    )
    if available.returncode:
        pytest.skip("User namespaces are unavailable for fixed-path launcher smoke")
    (tmp_path / "backend").mkdir()
    (tmp_path / "home").mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / "Pulumi.yaml").write_text(
        json.dumps(
            {
                "name": "user-service-infrastructure",
                "runtime": (
                    {
                        "name": "python",
                        "options": {"virtualenv": "/opt/service-runtime"},
                    }
                    if virtualenv
                    else {"name": "python"}
                ),
            }
        )
    )
    (project / "__main__.py").write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "import pulumi\n"
        "Path('/tmp/work/observed.json').write_text(json.dumps({"
        "'isolated': sys.flags.isolated, 'argv_count': len(sys.argv), "
        "'prefix': sys.prefix}))\n"
        "assert sys.flags.isolated and len(sys.argv) == 1\n"
        "pulumi.export('isolated', True)\n"
    )
    wrapper = tmp_path / "workload-python"
    wrapper.write_text(workload_python_wrapper_source())
    wrapper.chmod(0o555)
    environment = {
        "PATH": "/opt/pulumi:/usr/local/bin:/usr/bin:/bin",
        "HOME": "/tmp/work/home",
        "PULUMI_HOME": "/tmp/work/home",
        "PULUMI_BACKEND_URL": "file:///tmp/work/backend",
        "PULUMI_CONFIG_PASSPHRASE": "synthetic-local-test-passphrase",
        "PULUMI_PYTHON_CMD": "/tmp/work/workload-python",
        "PULUMI_SKIP_UPDATE_CHECK": "true",
        "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION": "true",
        "PULUMI_IGNORE_AMBIENT_PLUGINS": "true",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    sandbox = [
        bubblewrap,
        "--unshare-user",
        "--unshare-pid",
        "--unshare-net",
        "--ro-bind",
        "/",
        "/",
        "--clearenv",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/opt",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--bind",
        str(tmp_path),
        "/tmp/work",
        "--ro-bind",
        sys.prefix,
        "/opt/service-runtime",
        "--ro-bind",
        str(Path(pulumi).parent),
        "/opt/pulumi",
        "--chdir",
        "/tmp/work",
    ]
    for key, value in environment.items():
        sandbox.extend(["--setenv", key, value])
    for arguments in (
        [
            "stack",
            "init",
            "test",
            "--secrets-provider",
            "passphrase",
            "--non-interactive",
        ],
        ["preview", "--stack", "test", "--non-interactive", "--json"],
    ):
        result = subprocess.run(
            [*sandbox, "/opt/pulumi/pulumi", "-C", "/tmp/work/project", *arguments],
            env={"PATH": os.defpath},
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        if virtualenv and arguments[0] == "preview":
            assert result.returncode != 0
            assert "AssertionError" in result.stdout
        else:
            assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads((tmp_path / "observed.json").read_text()) == {
        "isolated": 0 if virtualenv else 1,
        "argv_count": 1,
        "prefix": "/opt/service-runtime",
    }
