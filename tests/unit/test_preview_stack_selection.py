"""The local fixture preview default must not silently select shared stacks."""

import importlib
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "configured,expected",
    [(None, ["dev"]), ("", ["dev"]), ("test prod", ["test", "prod"])],
)
def test_fixture_preview_default_and_explicit_override(
    monkeypatch, tmp_path, configured, expected
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    preview = importlib.import_module("run_pulumi_preview")
    project = tmp_path / "pulumi"
    project.mkdir()
    for name in ("dev", "test", "prod"):
        (project / f"Pulumi.{name}.yaml").write_text("config: {}\n")
    for name in (
        "PULUMI_DIR",
        "POLICY_PACK_DIR",
        "PREVIEW_ARTIFACT_DIR",
        "PULUMI_BACKEND_URL",
        "PULUMI_PREVIEW_STACKS",
        "PULUMI_CONFIG_PASSPHRASE",
    ):
        monkeypatch.delenv(name, raising=False)
    if configured is not None:
        monkeypatch.setenv("PULUMI_PREVIEW_STACKS", configured)
    monkeypatch.setattr(preview, "repo_root", lambda _: tmp_path)
    monkeypatch.setattr(preview, "find_uv_binary", lambda: "synthetic-uv")
    selected = []
    commands = []

    def run(argv, **kwargs):
        commands.append(argv)
        if "preview" in argv:
            selected.append(argv[argv.index("--stack") + 1])
            kwargs["stdout"].write('{"steps": []}')
        return subprocess.CompletedProcess(argv, 0, "synthetic summary\n", "")

    monkeypatch.setattr(preview, "run", run)
    assert preview.main() == 0
    assert selected == expected
    assert all(argv[0] in {"pulumi", "synthetic-uv"} for argv in commands)
    assert [
        argv[5] for argv in commands if argv[3:5] == ["stack", "select"]
    ] == expected
