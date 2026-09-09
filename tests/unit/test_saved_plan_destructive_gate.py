"""Exercise saved-plan sealing and replay through real manifest validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from test_shared_command_entrypoints import load_script_module


def preview(operation: str = "create", resource: str = "aws:s3/bucket:Bucket") -> str:
    """Return a Pulumi preview with an explicit resource operation."""
    state = "oldState" if operation in {"delete", "delete-replaced"} else "newState"
    return json.dumps({"steps": [{"op": operation, state: {"type": resource}}]})


def setup_command(monkeypatch, tmp_path, payload: str):
    """Use a local backend and capture the external command boundary only."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        if "--save-plan" in command:
            Path(command[command.index("--save-plan") + 1]).write_text("sealed plan")
            kwargs["stdout"].write(payload)
        return subprocess.CompletedProcess(command, 0, stdout="summary\n", stderr="")

    monkeypatch.setattr(module, "run", runner)
    context = module.CommandContext(
        root_dir=tmp_path,
        env={
            "PULUMI_COMMIT_SHA": "a" * 40,
            "PULUMI_EXPECTED_SHA": "a" * 40,
            "PULUMI_PLAN_NOW_EPOCH": "1000",
            "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        },
        pulumi_dir=tmp_path / "pulumi",
        policy_pack_dir=tmp_path / "policy",
        plan_dir=tmp_path / "plans",
        preview_artifact_dir=tmp_path / "previews",
        backend_url=(tmp_path / "backend").as_uri(),
        secrets_provider="",
        runner=runner,
    )
    return module, context, commands


def seal_existing(module, context, stack: str, payload: str):
    """Model an authentic earlier producer without bypassing replay validation."""
    context.plan_dir.mkdir()
    context.preview_artifact_dir.mkdir()
    plan_path = module._plan_file(context.plan_dir, stack)
    preview_path = module._preview_file(context.preview_artifact_dir, stack)
    plan_path.write_text("sealed plan")
    preview_path.write_text(payload)
    entry = module._plan_manifest_entry(context, stack, plan_path, preview_path)
    manifest = module._write_plan_manifest(context, [entry])
    return preview_path, manifest


@pytest.mark.parametrize("stack", ["test", "prod"])
@pytest.mark.parametrize("operation", ["delete", "replace", "delete-replaced"])
@pytest.mark.parametrize(
    "label", [None, "allow-destructive-infra-change", "stale-label"]
)
def test_authentic_destructive_plan_never_reaches_stack_selection(
    monkeypatch, tmp_path, stack, operation, label
):
    """Correct head, age, backend and both hashes do not authorize destruction."""
    module, context, commands = setup_command(monkeypatch, tmp_path, preview(operation))

    def forbidden_override_lookup(*_args):
        raise AssertionError("Labels must not be read as authorization")

    monkeypatch.setattr(
        module.guardrails, "load_destructive_override", forbidden_override_lookup
    )
    event = tmp_path / "event.json"
    labels = [{"name": label}] if label else []
    event.write_text(json.dumps({"pull_request": {"labels": labels}}))
    context.env["GITHUB_EVENT_PATH"] = str(event)
    seal_existing(module, context, stack, preview(operation))
    assert module._run_up_plan_command(context, [stack]) == 1
    assert commands == []


@pytest.mark.parametrize("stack", ["test", "prod"])
def test_new_destructive_plan_cannot_seal_manifest(monkeypatch, tmp_path, stack):
    """A failed new preview also invalidates any stale manifest from an earlier run."""
    module, context, commands = setup_command(monkeypatch, tmp_path, preview("delete"))
    context.plan_dir.mkdir()
    module._plan_manifest_file(context).write_text("stale manifest")
    assert module._run_plan_command(context, [stack]) == 1
    assert not module._plan_manifest_file(context).exists()
    assert not Path(context.env["GITHUB_OUTPUT"]).exists()
    assert any("--save-plan" in command for command in commands)
    assert not any("--plan" in command for command in commands)


@pytest.mark.parametrize("stack", ["test", "prod"])
@pytest.mark.parametrize(
    "operation,resource",
    [
        ("create", "aws:s3/bucket:Bucket"),
        ("update", "aws:s3/bucket:Bucket"),
        ("replace", "aws:ecs/taskDefinition:TaskDefinition"),
    ],
)
def test_benign_generated_plan_seals_and_replays(
    monkeypatch, tmp_path, stack, operation, resource
):
    """Preserve normal creates, updates and permitted stateless replacement."""
    module, context, commands = setup_command(
        monkeypatch, tmp_path, preview(operation, resource)
    )
    assert module._run_plan_command(context, [stack]) == 0
    assert module._plan_manifest_file(context).is_file()
    commands.clear()
    assert module._run_up_plan_command(context, [stack]) == 0
    assert commands[0][3:5] == ["stack", "select"]
    assert "--plan" in commands[-1]


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        "[]",
        "null",
        '{"steps":null}',
        '{"steps":[null]}',
        '{"steps":[{"op":"delete"}]}',
        '{"steps":[{"op":"unknown","oldState":{"type":"aws:s3/bucket:Bucket"}}]}',
        '{"steps":[{"op":[],"oldState":{"type":"aws:s3/bucket:Bucket"}}]}',
        '{"steps":[{"op":"delete","oldState":{"type":5}}]}',
        '{"steps":[{"op":"delete","oldState":{"type":""}}]}',
        '{"steps":[{"op":"delete","oldState":[]}]}',
        '{"steps":[{"op":"delete","oldState":{"type":"aws:s3/bucket:Bucket"},'
        '"newState":{"type":"aws:ecs/taskDefinition:TaskDefinition"}}]}',
        '{"steps":[],"steps":[]}',
        '{"steps":[],"other":NaN}',
        "not json",
    ],
)
def test_hash_sealed_malformed_preview_fails_closed(monkeypatch, tmp_path, payload):
    """A valid preview hash cannot turn an ambiguous preview into a safe plan."""
    module, context, commands = setup_command(monkeypatch, tmp_path, payload)
    seal_existing(module, context, "test", payload)
    assert module._run_up_plan_command(context, ["test"]) == 1
    assert commands == []


@pytest.mark.parametrize("mutation", ["tamper", "missing", "directory"])
def test_original_preview_bytes_are_required(monkeypatch, tmp_path, mutation):
    """Never substitute a fresh preview for the one bound by the saved manifest."""
    module, context, commands = setup_command(monkeypatch, tmp_path, preview())
    path, _ = seal_existing(module, context, "test", preview())
    path.unlink()
    if mutation == "tamper":
        path.write_text(preview("update"))
    elif mutation == "directory":
        path.mkdir()
    assert module._run_up_plan_command(context, ["test"]) == 1
    assert commands == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("previewFile", None),
        ("previewFile", ""),
        ("previewFile", "../outside.json"),
        ("previewFile", "/tmp/outside.json"),
        ("previewSha256", None),
        ("previewSha256", ""),
        ("previewSha256", 64),
        ("previewSha256", "z" * 64),
    ],
)
def test_manifest_requires_contained_hash_bound_preview(
    monkeypatch, tmp_path, field, value
):
    """Missing or invalid preview binding blocks before any Pulumi operation."""
    module, context, commands = setup_command(monkeypatch, tmp_path, preview())
    _, manifest_path = seal_existing(module, context, "test", preview())
    manifest = json.loads(manifest_path.read_text())
    manifest["stacks"][0][field] = value
    manifest_path.write_text(json.dumps(manifest))
    assert module._run_up_plan_command(context, ["test"]) == 1
    assert commands == []


def test_preview_symlink_cannot_escape_repository(monkeypatch, tmp_path):
    """Matching bytes outside the repository do not satisfy path containment."""
    root = tmp_path / "repo"
    root.mkdir()
    module, context, commands = setup_command(monkeypatch, root, preview())
    path, _ = seal_existing(module, context, "test", preview())
    outside = tmp_path / "outside.json"
    path.rename(outside)
    path.symlink_to(outside)
    assert module._run_up_plan_command(context, ["test"]) == 1
    assert commands == []
