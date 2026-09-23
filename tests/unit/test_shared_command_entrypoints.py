"""Reviewed shared-state command tests carried with the service runtime."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def load_script_module(monkeypatch: pytest.MonkeyPatch, module_name: str):
    """Import a script module from the repo-local scripts directory."""
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    importlib.invalidate_caches()
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


CommandMatcher = Callable[[list[str]], bool]

CommandResponse = Callable[[list[str]], subprocess.CompletedProcess[str]]


def preview_binding(root_dir: Path, stack: str = "test") -> dict[str, str]:
    """Write a benign preview and supply the mandatory original-preview binding."""
    path = root_dir / ".artifacts" / "pulumi-preview" / f"{stack}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"steps": [], "changeSummary": {}}', encoding="utf-8")
    return {
        "previewFile": str(path.relative_to(root_dir)),
        "previewSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_run_pulumi_command_builds_expected_pulumi_invocations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keep the generic Pulumi command helper explicit and argument-safe."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    pulumi_dir = tmp_path / "pulumi"
    policy_dir = tmp_path / "policy"
    plan_path = tmp_path / "plan"
    context = module.CommandContext(
        root_dir=tmp_path,
        env={},
        pulumi_dir=pulumi_dir,
        policy_pack_dir=policy_dir,
        plan_dir=tmp_path / "plans",
        preview_artifact_dir=tmp_path / "previews",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
    )

    configured_stacks = module._configured_stack_names(
        "preview", pulumi_dir, {"PULUMI_STACK": "test"}
    )
    assert configured_stacks == ["test"]  # nosec B101
    drift_stacks = module._configured_stack_names(
        "drift", pulumi_dir, {"PULUMI_DRIFT_STACKS": "prod"}
    )
    assert drift_stacks == ["prod"]  # nosec B101
    assert module._validate_secrets_provider("not-kms") == 1  # nosec B101
    assert module._validate_secrets_provider("") == 1  # nosec B101
    assert (  # nosec B101
        module._validate_secrets_provider("awskms://alias/example") is None
    )
    assert module._uses_file_backend("file:///tmp/backend") is True  # nosec B101
    assert module._uses_file_backend("s3://bucket/state") is False  # nosec B101

    expected_preview_command = [
        "pulumi",
        "-C",
        str(pulumi_dir),
        "preview",
        "--stack",
        "test",
        "--non-interactive",
        "--policy-pack",
        str(policy_dir),
    ]
    preview_command = module._pulumi_command(
        context, module.StackCommand("preview", "test")
    )
    assert preview_command == expected_preview_command  # nosec B101
    assert "--save-plan" in module._pulumi_command(  # nosec B101
        context, module.StackCommand("plan", "test", plan_path=plan_path)
    )
    assert "--plan" in module._pulumi_command(  # nosec B101
        context, module.StackCommand("up-plan", "test", plan_path=plan_path)
    )
    drift_command = module._pulumi_command(
        context, module.StackCommand("drift", "test")
    )
    up_command = module._pulumi_command(context, module.StackCommand("up", "test"))
    up_without_policy_command = module._pulumi_command(
        context, module.StackCommand("up", "test", include_policy_pack=False)
    )
    refresh_command = module._pulumi_command(
        context, module.StackCommand("refresh", "test")
    )
    destroy_command = module._pulumi_command(
        context, module.StackCommand("destroy", "test")
    )
    assert "--yes" in up_command  # nosec B101
    assert "--policy-pack" in up_command  # nosec B101
    assert "--policy-pack" not in up_without_policy_command  # nosec B101
    assert "--yes" in refresh_command  # nosec B101
    assert "--expect-no-changes" in drift_command  # nosec B101
    assert "--yes" in destroy_command  # nosec B101

    with pytest.raises(ValueError, match="plan command requires"):
        module._pulumi_command(context, module.StackCommand("plan", "test"))
    with pytest.raises(ValueError, match="up-plan command requires"):
        module._pulumi_command(context, module.StackCommand("up-plan", "test"))
    with pytest.raises(ValueError, match="unsupported"):
        module._pulumi_command(context, module.StackCommand("unknown", "test"))


def test_run_pulumi_command_prefers_configured_stack_lists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Multi-stack commands should not be masked by Make's default PULUMI_STACK."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    pulumi_dir = tmp_path / "pulumi"
    pulumi_dir.mkdir()

    preview_stacks = module._configured_stack_names(
        "preview",
        pulumi_dir,
        {"PULUMI_STACK": "default", "PULUMI_PREVIEW_STACKS": "test prod/eu"},
    )
    drift_stacks = module._configured_stack_names(
        "drift",
        pulumi_dir,
        {"PULUMI_STACK": "default", "PULUMI_DRIFT_STACKS": "prod"},
    )
    up_plan_stacks = module._configured_stack_names(
        "up-plan",
        pulumi_dir,
        {"PULUMI_STACK": "default", "PULUMI_PREVIEW_STACKS": "test prod/eu"},
    )

    assert preview_stacks == ["test", "prod/eu"]  # nosec B101
    assert drift_stacks == ["prod"]  # nosec B101
    assert up_plan_stacks == ["test", "prod/eu"]  # nosec B101


def test_run_pulumi_command_safe_artifact_stem_handles_empty_sanitized_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact names should still be stable when no stack characters are safe."""
    module = load_script_module(monkeypatch, "run_pulumi_command")

    stem = module._safe_artifact_stem("")

    assert stem.startswith("stack-")  # nosec B101
    assert len(stem) == len("stack-") + 8  # nosec B101


def test_run_pulumi_command_branch_helpers_return_select_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cover helper branches that short-circuit before invoking Pulumi."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    plan_dir = repo_dir / ".artifacts" / "pulumi-plan"
    preview_dir = repo_dir / ".artifacts" / "pulumi-preview"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    plan_dir.mkdir(parents=True)
    preview_dir.mkdir(parents=True)
    context = module.CommandContext(
        root_dir=repo_dir,
        env={},
        pulumi_dir=pulumi_dir,
        policy_pack_dir=policy_dir,
        plan_dir=plan_dir,
        preview_artifact_dir=preview_dir,
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
    )

    default_plan = module._selected_plan_path(context, None, "test")
    assert default_plan == module._plan_file(plan_dir, "test")  # nosec B101

    monkeypatch.setattr(module, "_select_or_init_stack", lambda *args: 7)
    assert module._run_plan_command(context, ["test"]) == 7  # nosec B101

    select_calls = []

    def fake_up_plan_select(*args):
        select_calls.append(args)
        return 9

    monkeypatch.setattr(module, "_select_or_init_stack", fake_up_plan_select)
    assert module._run_up_plan_command(context, ["test"]) == 1  # nosec B101
    assert select_calls == []  # nosec B101


def test_run_pulumi_command_validates_plan_manifest_error_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject saved plans with stale or mismatched manifest evidence."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    plan_dir = repo_dir / ".artifacts" / "pulumi-plan"
    preview_dir = repo_dir / ".artifacts" / "pulumi-preview"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    plan_dir.mkdir(parents=True)
    preview_dir.mkdir(parents=True)
    plan_file = plan_dir / "test.plan"
    other_plan = plan_dir / "other.plan"
    plan_file.write_text("plan", encoding="utf-8")
    other_plan.write_text("other", encoding="utf-8")
    context = module.CommandContext(
        root_dir=repo_dir,
        env={"PULUMI_PLAN_NOW_EPOCH": "1000", "PULUMI_EXPECTED_SHA": "sha-a"},
        pulumi_dir=pulumi_dir,
        policy_pack_dir=policy_dir,
        plan_dir=plan_dir,
        preview_artifact_dir=preview_dir,
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
    )

    assert module._load_plan_manifest(context) is None  # nosec B101
    assert "manifest not found" in capsys.readouterr().err  # nosec B101

    valid_entry = {
        "stack": "test",
        "planFile": ".artifacts/pulumi-plan/test.plan",
        "planSha256": hashlib.sha256(b"plan").hexdigest(),
        **preview_binding(repo_dir),
    }
    valid_manifest = {
        "schemaVersion": 1,
        "createdAtEpoch": 1000,
        "commitSha": "sha-a",
        "backendUrl": "file:///tmp/backend",
        "pulumiDir": "pulumi",
        "policyPackDir": "policy",
        "stacks": [
            {"stack": "skip", "planFile": "unused", "planSha256": "unused"},
            valid_entry,
        ],
    }
    assert (  # nosec B101
        module._validate_plan_manifest(context, valid_manifest, "test", plan_file)
        is None
    )

    bad_schema = {**valid_manifest, "schemaVersion": 2}
    assert module._validate_plan_manifest(context, bad_schema, "test", plan_file) == 1
    context.env["PULUMI_PLAN_MAX_AGE_SECONDS"] = "10"
    stale = {**valid_manifest, "createdAtEpoch": 0}
    assert module._validate_plan_manifest(context, stale, "test", plan_file) == 1
    context.env.pop("PULUMI_PLAN_MAX_AGE_SECONDS")
    wrong_sha = {**valid_manifest, "commitSha": "sha-b"}
    assert module._validate_plan_manifest(context, wrong_sha, "test", plan_file) == 1
    context.env["PULUMI_COMMIT_SHA"] = "sha-b"
    assert module._validate_plan_manifest(context, wrong_sha, "test", plan_file) == 1
    context.env.pop("PULUMI_COMMIT_SHA")
    for absent_sha in (None, "", 123):
        assert (
            module._validate_plan_manifest(
                context, {**valid_manifest, "commitSha": absent_sha}, "test", plan_file
            )
            == 1
        )
    for field in ("pulumiDir", "policyPackDir"):
        for path in (None, "", "other-project", "../outside", "/absolute"):
            assert (
                module._validate_plan_manifest(
                    context, {**valid_manifest, field: path}, "test", plan_file
                )
                == 1
            )
    context.env["PULUMI_EXPECTED_SHA"] = ""
    monkeypatch.setattr(module, "_commit_sha", lambda _context: "")
    assert (
        module._validate_plan_manifest(context, valid_manifest, "test", plan_file) == 1
    )
    monkeypatch.setattr(module, "_commit_sha", lambda _context: "sha-a")
    wrong_backend = {**valid_manifest, "backendUrl": "s3://other"}
    assert (  # nosec B101
        module._validate_plan_manifest(context, wrong_backend, "test", plan_file) == 1
    )
    missing_stack = {**valid_manifest, "stacks": []}
    assert (  # nosec B101
        module._validate_plan_manifest(context, missing_stack, "test", plan_file) == 1
    )
    wrong_plan_path = {
        **valid_manifest,
        "stacks": [{**valid_entry, "planFile": ".artifacts/pulumi-plan/other.plan"}],
    }
    assert (  # nosec B101
        module._validate_plan_manifest(context, wrong_plan_path, "test", plan_file) == 1
    )
    wrong_hash = {
        **valid_manifest,
        "stacks": [{**valid_entry, "planSha256": hashlib.sha256(b"bad").hexdigest()}],
    }
    assert module._validate_plan_manifest(context, wrong_hash, "test", plan_file) == 1
    assert "hash does not match" in capsys.readouterr().err  # nosec B101


def test_run_pulumi_command_rejects_malformed_plan_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fail closed when a saved-plan artifact manifest is malformed."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    plan_dir = repo_dir / ".artifacts" / "pulumi-plan"
    preview_dir = repo_dir / ".artifacts" / "pulumi-preview"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    plan_dir.mkdir(parents=True)
    preview_dir.mkdir(parents=True)
    plan_file = plan_dir / "test.plan"
    plan_file.write_text("plan", encoding="utf-8")
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (repo_dir / "outside-link").symlink_to(outside_dir, target_is_directory=True)
    manifest_file = plan_dir / "manifest.json"
    context = module.CommandContext(
        root_dir=repo_dir,
        env={"PULUMI_PLAN_NOW_EPOCH": "1000", "PULUMI_EXPECTED_SHA": "sha-a"},
        pulumi_dir=pulumi_dir,
        policy_pack_dir=policy_dir,
        plan_dir=plan_dir,
        preview_artifact_dir=preview_dir,
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
    )
    valid_entry = {
        "stack": "test",
        "planFile": ".artifacts/pulumi-plan/test.plan",
        "planSha256": hashlib.sha256(b"plan").hexdigest(),
        **preview_binding(repo_dir),
    }
    valid_manifest = {
        "schemaVersion": 1,
        "createdAtEpoch": 1000,
        "commitSha": "sha-a",
        "backendUrl": "file:///tmp/backend",
        "pulumiDir": "pulumi",
        "policyPackDir": "policy",
        "stacks": [valid_entry],
    }

    manifest_file.write_text("{", encoding="utf-8")
    assert module._load_plan_manifest(context) is None  # nosec B101
    manifest_file.write_text("[]", encoding="utf-8")
    assert module._load_plan_manifest(context) is None  # nosec B101

    malformed_manifests = [
        {**valid_manifest, "createdAtEpoch": "not-an-int"},
        {**valid_manifest, "createdAtEpoch": 1001},
        {**valid_manifest, "stacks": {"stack": "test"}},
        {**valid_manifest, "stacks": ["test"]},
        {**valid_manifest, "stacks": [{**valid_entry, "planFile": None}]},
        {**valid_manifest, "stacks": [{**valid_entry, "planFile": 123}]},
        {**valid_manifest, "stacks": [{**valid_entry, "planFile": ""}]},
        {**valid_manifest, "stacks": [{**valid_entry, "planFile": str(plan_file)}]},
        {
            **valid_manifest,
            "stacks": [
                {
                    **valid_entry,
                    "planFile": "../repo/.artifacts/pulumi-plan/test.plan",
                }
            ],
        },
        {**valid_manifest, "stacks": [{**valid_entry, "planFile": "outside-link/x"}]},
        {**valid_manifest, "stacks": [{**valid_entry, "planSha256": None}]},
        {**valid_manifest, "stacks": [{**valid_entry, "planSha256": ""}]},
    ]
    for manifest in malformed_manifests:
        assert (  # nosec B101
            module._validate_plan_manifest(context, manifest, "test", plan_file) == 1
        )

    context.env["PULUMI_PLAN_MAX_AGE_SECONDS"] = "not-an-int"
    assert (  # nosec B101
        module._validate_plan_manifest(context, valid_manifest, "test", plan_file) == 1
    )
    assert "Pulumi plan manifest" in capsys.readouterr().err  # nosec B101


def test_run_pulumi_command_requires_manifest_before_saved_plan_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A saved plan cannot be applied without its manifest."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    plan_dir = repo_dir / ".artifacts" / "pulumi-plan"
    plan_dir.mkdir(parents=True)
    plan_file = plan_dir / f"{module._safe_artifact_stem('test')}.plan"
    plan_file.write_text("plan", encoding="utf-8")
    context = module.CommandContext(
        root_dir=repo_dir,
        env={},
        pulumi_dir=repo_dir / "pulumi",
        policy_pack_dir=repo_dir / "policy",
        plan_dir=plan_dir,
        preview_artifact_dir=repo_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    assert module._run_up_plan_command(context, ["test"]) == 1  # nosec B101
    assert "manifest not found" in capsys.readouterr().err  # nosec B101

    (plan_dir / "manifest.json").write_text(
        json.dumps({"schemaVersion": 2, "stacks": []}),
        encoding="utf-8",
    )
    assert module._run_up_plan_command(context, ["test"]) == 1  # nosec B101
    assert "unsupported" in capsys.readouterr().err  # nosec B101


def test_run_pulumi_command_reuses_manifest_for_multiple_plan_applications(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Multi-stack apply should load one manifest and validate every plan."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    plan_dir = repo_dir / ".artifacts" / "pulumi-plan"
    plan_dir.mkdir(parents=True)
    context = module.CommandContext(
        root_dir=repo_dir,
        env={"PULUMI_PLAN_NOW_EPOCH": "1000", "PULUMI_EXPECTED_SHA": "sha-a"},
        pulumi_dir=repo_dir / "pulumi",
        policy_pack_dir=repo_dir / "policy",
        plan_dir=plan_dir,
        preview_artifact_dir=repo_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )
    stacks = ["test", "prod"]
    entries = []
    for stack in stacks:
        plan_file = module._plan_file(plan_dir, stack)
        plan_file.write_text(f"plan-{stack}", encoding="utf-8")
        entries.append(
            {
                "stack": stack,
                "planFile": f".artifacts/pulumi-plan/{plan_file.name}",
                "planSha256": hashlib.sha256(f"plan-{stack}".encode()).hexdigest(),
                **preview_binding(repo_dir, stack),
            }
        )
    (plan_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "createdAtEpoch": 1000,
                "commitSha": "sha-a",
                "backendUrl": "file:///tmp/backend",
                "pulumiDir": "pulumi",
                "policyPackDir": "policy",
                "stacks": entries,
            }
        ),
        encoding="utf-8",
    )

    assert module._run_up_plan_command(context, stacks) == 0  # nosec B101


def test_run_pulumi_command_plan_fails_when_saved_plan_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The plan command must not publish a manifest without a real saved plan."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    context = module.CommandContext(
        root_dir=repo_dir,
        env={},
        pulumi_dir=pulumi_dir,
        policy_pack_dir=policy_dir,
        plan_dir=repo_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=repo_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    assert module._run_plan_command(context, ["test"]) == 1  # nosec B101
    assert "plan file not created" in capsys.readouterr().err  # nosec B101


def test_select_or_init_stack_requires_file_backend_secrets_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """File-backed stack initialization should fail before init without a provider."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    pulumi_dir.mkdir(parents=True)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stderr="missing stack\n")

    context = module.CommandContext(
        root_dir=repo_dir,
        env={},
        pulumi_dir=pulumi_dir,
        policy_pack_dir=repo_dir / "policy",
        plan_dir=repo_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=repo_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="",
        runner=fake_run,
    )

    assert module._select_or_init_stack(context, "test") == 1  # nosec B101
    assert "set PULUMI_SECRETS_PROVIDER" in capsys.readouterr().err  # nosec B101


def test_run_pulumi_command_plan_handles_multiple_configured_stacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A configured stack list should create one saved plan per stack."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    output_file = repo_dir / "github-output.txt"
    preview_dir = repo_dir / ".artifacts" / "pulumi-preview"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    preview_dir.mkdir(parents=True)
    (preview_dir / "stale.json").write_text("{}", encoding="utf-8")
    (preview_dir / "summary.md").write_text("old summary\n", encoding="utf-8")
    monkeypatch.setattr(module, "repo_root", lambda _: repo_dir)
    monkeypatch.setenv("PULUMI_STACK", "default")
    monkeypatch.setenv("PULUMI_PREVIEW_STACKS", "test prod/eu")
    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER",
        "awskms://alias/bootstrap-preview?region=eu-central-1",
    )
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    calls: list[list[str]] = []

    def preview_response(
        command: list[str], stdout: object
    ) -> subprocess.CompletedProcess:
        if stdout is not None:
            stdout.write('{"changeSummary": {"create": 1}, "steps": []}')
        if "--save-plan" in command:
            plan_path = Path(command[command.index("--save-plan") + 1])
            plan_path.write_text(
                f"plan for {command[command.index('--stack') + 1]}",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0)

    def fake_run(command, **kwargs):
        calls.append(command)
        missing_stack_errors = {"test": "missing test\n", "prod/eu": "missing prod\n"}
        selected_stack = (
            command[5]
            if command[0] == "pulumi"
            and command[3:5]
            == [
                "stack",
                "select",
            ]
            else ""
        )
        if selected_stack in missing_stack_errors:
            return subprocess.CompletedProcess(
                command, 1, stderr=missing_stack_errors[selected_stack]
            )
        if command[0] == "pulumi" and command[3] == "preview":
            return preview_response(command, kwargs.get("stdout"))
        if command[:3] == ["uv", "--project", str(repo_dir)]:
            return subprocess.CompletedProcess(
                command, 0, stdout=f"summary for {Path(command[-1]).stem}\n"
            )
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", fake_run)
    assert module.main(["plan"]) == 0  # nosec B101

    test_stem = module._safe_artifact_stem("test")
    prod_stem = module._safe_artifact_stem("prod/eu")
    output = capsys.readouterr().out
    output_values = output_file.read_text(encoding="utf-8")
    assert f"summary for {test_stem}" in output  # nosec B101
    assert f"summary for {prod_stem}" in output  # nosec B101
    assert f"{test_stem}.plan" in output_values  # nosec B101
    assert f"{prod_stem}.plan" in output_values  # nosec B101
    assert "plan_manifest=" in output_values  # nosec B101
    assert "old summary" not in output  # nosec B101
    assert not (preview_dir / "stale.json").exists()  # nosec B101
    manifest = json.loads(
        (repo_dir / ".artifacts/pulumi-plan/manifest.json").read_text()
    )
    assert manifest["schemaVersion"] == 1  # nosec B101
    assert manifest["backendUrl"].startswith("file://")  # nosec B101
    assert [entry["stack"] for entry in manifest["stacks"]] == [  # nosec B101
        "test",
        "prod/eu",
    ]
    initialized_prod = any(
        command[3:10]
        == [
            "stack",
            "init",
            "prod/eu",
            "--non-interactive",
            "--secrets-provider",
            "awskms://alias/bootstrap-preview?region=eu-central-1",
        ]
        for command in calls
    )
    assert initialized_prod  # nosec B101


def test_run_pulumi_command_plan_does_not_preemptively_cancel_stack_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CI plan commands should not cancel a possibly active update."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    monkeypatch.setattr(module, "repo_root", lambda _: repo_dir)
    monkeypatch.setenv("PULUMI_STACK", "prod")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("PULUMI_COMMIT_SHA", "d" * 40)
    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER",
        "awskms://alias/bootstrap-preview?region=eu-central-1",
    )

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "pulumi" and command[3] == "cancel":
            return subprocess.CompletedProcess(command, 0, stdout="")
        if command[0] == "pulumi" and command[3] == "preview":
            if stdout := kwargs.get("stdout"):
                stdout.write('{"changeSummary": {"same": 1}, "steps": []}')
            plan_path = Path(command[command.index("--save-plan") + 1])
            plan_path.write_text("plan", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="")
        if command[:3] == ["uv", "--project", str(repo_dir)]:
            return subprocess.CompletedProcess(command, 0, stdout="summary\n")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", fake_run)
    assert module.main(["plan"]) == 0  # nosec B101
    assert not any(  # nosec B101
        len(command) > 3 and command[3] == "cancel" for command in calls
    )
    assert any(  # nosec B101
        len(command) > 3 and command[3] == "preview" for command in calls
    )


def test_run_pulumi_command_handles_error_paths_and_plan_application(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cover stack-safety failures and saved-plan application."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    plan_dir = repo_dir / ".artifacts" / "pulumi-plan"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    plan_dir.mkdir(parents=True)
    monkeypatch.setattr(module, "repo_root", lambda _: repo_dir)

    monkeypatch.setenv("PULUMI_SECRETS_PROVIDER", "local")
    assert module.main(["preview"]) == 1  # nosec B101
    assert "awskms://" in capsys.readouterr().err  # nosec B101

    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER", "awskms://alias/example?region=eu-central-1"
    )
    monkeypatch.setattr(module, "discover_stacks", lambda *args: [])
    assert module.main(["preview"]) == 1  # nosec B101
    assert "set PULUMI_STACK" in capsys.readouterr().err  # nosec B101

    def shared_run(command, **kwargs):
        if command[0] == "pulumi" and command[3:6] == ["stack", "select", "test"]:
            return subprocess.CompletedProcess(command, 255, stderr="missing\n")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "discover_stacks", lambda *args: ["test"])
    monkeypatch.setattr(module, "run", shared_run)
    monkeypatch.setenv("PULUMI_BACKEND_URL", "s3://shared-state")
    assert module.main(["refresh"]) == 255  # nosec B101
    assert "shared backend stack test does not exist" in capsys.readouterr().err  # nosec B101

    def missing_provider_run(command, **kwargs):
        if command[0] == "pulumi" and command[3:6] == ["stack", "select", "test"]:
            return subprocess.CompletedProcess(command, 1, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", missing_provider_run)
    monkeypatch.setenv("PULUMI_BACKEND_URL", "file:///tmp/backend")
    monkeypatch.delenv("PULUMI_SECRETS_PROVIDER", raising=False)
    module._emit_stderr("")
    assert module.main(["refresh"]) == 1  # nosec B101
    assert "PULUMI_SECRETS_PROVIDER must be set" in capsys.readouterr().err  # nosec B101

    def init_failure_run(command, **kwargs):
        if command[0] == "pulumi" and command[3:6] == ["stack", "select", "test"]:
            return subprocess.CompletedProcess(command, 1, stderr="")
        if command[0] == "pulumi" and command[3:6] == ["stack", "init", "test"]:
            return subprocess.CompletedProcess(command, 42, stderr="kms denied\n")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", init_failure_run)
    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER", "awskms://alias/example?region=eu-central-1"
    )
    assert module.main(["refresh"]) == 42  # nosec B101
    assert "kms denied" in capsys.readouterr().err  # nosec B101

    def ok_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", ok_run)
    monkeypatch.setenv("PULUMI_BACKEND_URL", "file:///tmp/backend")
    monkeypatch.setenv("PULUMI_PLAN_FILE", str(plan_dir / "single.plan"))
    monkeypatch.setattr(module, "discover_stacks", lambda *args: ["test", "prod"])
    assert module.main(["up-plan"]) == 1  # nosec B101
    assert "single selected stack" in capsys.readouterr().err  # nosec B101

    monkeypatch.setattr(module, "discover_stacks", lambda *args: ["test"])
    assert module.main(["up-plan"]) == 1  # nosec B101
    assert "Pulumi plan file not found" in capsys.readouterr().err  # nosec B101

    selected_plan = plan_dir / "single.plan"
    selected_plan.write_text("plan", encoding="utf-8")
    monkeypatch.setenv("PULUMI_EXPECTED_SHA", "sha-a")
    monkeypatch.setenv("PULUMI_PLAN_NOW_EPOCH", "1000")
    (plan_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "createdAtEpoch": 1000,
                "commitSha": "sha-a",
                "backendUrl": "file:///tmp/backend",
                "pulumiDir": "pulumi",
                "policyPackDir": "policy",
                "stacks": [
                    {
                        "stack": "test",
                        "planFile": ".artifacts/pulumi-plan/single.plan",
                        "planSha256": hashlib.sha256(b"plan").hexdigest(),
                        **preview_binding(repo_dir),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    applied: list[list[str]] = []

    def apply_run(command, **kwargs):
        applied.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", apply_run)
    assert module.main(["up-plan"]) == 0  # nosec B101
    applied_selected_plan = any(
        "--plan" in command and str(selected_plan) in command for command in applied
    )
    assert applied_selected_plan  # nosec B101

    single_output = repo_dir / "single-output.txt"
    module._write_plan_outputs(
        str(single_output), [selected_plan], plan_dir, plan_dir / "manifest.json"
    )
    assert f"plan_file={selected_plan}" in single_output.read_text(encoding="utf-8")  # nosec B101


def test_run_up_plan_stack_uses_saved_prod_plan_by_default_in_ci(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Production CI applies should remain constrained to the saved plan."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"
    applied: list[list[str]] = []

    def fake_runner(command, **kwargs):
        applied.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="")

    context = module.CommandContext(
        root_dir=context_dir,
        env={"GITHUB_ACTIONS": "true", "PULUMI_EXPECTED_SHA": "a" * 40},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=fake_runner,
    )

    assert module._run_up_plan_stack(context, "prod", tmp_path / "prod.plan") is None
    assert capsys.readouterr().err == ""  # nosec B101
    assert any(  # nosec B101
        len(command) > 3 and command[3] == "up" and "--plan" in command
        for command in applied
    )
    assert not any(  # nosec B101
        len(command) > 3 and command[3] == "up" and "--plan" not in command
        for command in applied
    )


@pytest.mark.parametrize("stack", ["test", "prod", "service/test"])
@pytest.mark.parametrize(
    "error,code",
    [
        ("decrypting secret value: cipher: message authentication failed", 255),
        ("the stack is currently locked", 42),
        ("provider denied", 17),
    ],
)
def test_run_up_plan_stack_fails_closed_without_apply_or_lock_recovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stack: str,
    error: str,
    code: int,
) -> None:
    """No saved-plan failure authorizes direct apply or lock cancellation."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    applied: list[list[str]] = []

    def fake_runner(command, **kwargs):
        applied.append(command)
        return subprocess.CompletedProcess(command, code, stdout="", stderr=error)

    context = module.CommandContext(
        root_dir=tmp_path,
        env={"GITHUB_ACTIONS": "true", "PULUMI_EXPECTED_SHA": "a" * 40},
        pulumi_dir=tmp_path / "pulumi",
        policy_pack_dir=tmp_path / "policy",
        plan_dir=tmp_path / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=tmp_path / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=fake_runner,
    )
    plan = tmp_path / "reviewed.plan"
    assert module._run_up_plan_stack(context, stack, plan) == code
    assert error in capsys.readouterr().err
    assert len(applied) == 1
    assert applied[0][3] == "up"
    assert applied[0][applied[0].index("--plan") + 1] == str(plan)
    assert "cancel" not in applied[0]


def test_run_up_stack_does_not_retry_after_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Direct applies should not auto-cancel stack locks and retry."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"
    applied: list[list[str]] = []
    up_attempts = 0

    def fake_runner(command, **kwargs):
        nonlocal up_attempts
        applied.append(command)
        if len(command) > 3 and command[3] == "up":
            up_attempts += 1
            if up_attempts == 1:
                return subprocess.CompletedProcess(
                    command,
                    255,
                    stdout="",
                    stderr=module.STACK_LOCK_ERROR,
                )
        return subprocess.CompletedProcess(command, 0, stdout="")

    context = module.CommandContext(
        root_dir=context_dir,
        env={},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=fake_runner,
    )

    assert module._run_up_stack(context, "test") == 255
    assert not any(  # nosec B101
        len(command) > 3 and command[3] == "cancel" for command in applied
    )
    assert up_attempts == 1  # nosec B101


def test_run_up_stack_rejects_direct_apply_in_github_actions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """GitHub applies must use a reviewed saved plan."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"
    calls: list[list[str]] = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="")

    context = module.CommandContext(
        root_dir=context_dir,
        env={"GITHUB_ACTIONS": "true", "PULUMI_EXPECTED_SHA": "b" * 40},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=fake_runner,
    )

    monkeypatch.setattr(module, "_context_from_environment", lambda: context)

    def forbidden_preparation(*args, **kwargs):
        raise AssertionError("Direct CI up must fail before any metadata preparation")

    for name in (
        "_validate_secrets_provider",
        "_configured_stack_names",
        "_dispatch_command",
    ):
        monkeypatch.setattr(module, name, forbidden_preparation)
    assert module.main(["up"]) == 1
    assert "pulumi-up-plan" in capsys.readouterr().err
    assert module.main(["destroy"]) == 1
    destroy_message = capsys.readouterr().err
    assert "separately authorized local operation" in destroy_message
    assert "pulumi-up-plan" not in destroy_message
    assert module._run_up_stack(context, "test") == 1  # nosec B101
    assert "direct Pulumi up is disabled in GitHub Actions" in (  # nosec B101
        capsys.readouterr().err
    )
    assert calls == []  # nosec B101


def test_run_pulumi_command_observable_output_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Observable command execution should stream and capture subprocess output."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            7,
            stdout="captured stdout\n",
            stderr="captured stderr\n",
        )

    fake_context = module.CommandContext(
        root_dir=context_dir,
        env={},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="",
        runner=fake_runner,
    )
    result = module._run_with_observable_output(fake_context, ["pulumi", "version"])
    captured = capsys.readouterr()
    assert result.returncode == 7  # nosec B101
    assert "captured stdout" in captured.out  # nosec B101
    assert "captured stderr" in captured.err  # nosec B101

    popen_calls: list[list[str]] = []

    class FakeProcess:
        stdout = io.StringIO("line one\nline two\n")

        def wait(self) -> int:
            return 3

    def fake_popen(command, **kwargs):
        popen_calls.append(command)
        return FakeProcess()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    default_context = module.CommandContext(
        root_dir=context_dir,
        env={"EXAMPLE": "1"},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="",
        runner=module.DEFAULT_RUNNER,
    )
    streamed = module._run_with_observable_output(default_context, ["pulumi", "about"])
    assert streamed.returncode == 3  # nosec B101
    assert streamed.stdout == "line one\nline two\n"  # nosec B101
    assert popen_calls == [["pulumi", "about"]]  # nosec B101
    assert "line one" in capsys.readouterr().out  # nosec B101

    class FakeProcessWithoutStdout:
        stdout = None

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda command, **kwargs: FakeProcessWithoutStdout(),
    )
    no_stdout = module._run_with_observable_output(
        default_context, ["pulumi", "whoami"]
    )
    assert no_stdout.returncode == 0  # nosec B101
    assert no_stdout.stdout == ""  # nosec B101


def test_run_pulumi_command_unhandled_apply_failures_return_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unhandled Pulumi apply failures should propagate their return codes."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"

    def plan_failure_runner(command, **kwargs):
        if len(command) > 3 and command[3] == "up" and "--plan" in command:
            return subprocess.CompletedProcess(command, 42, stdout="", stderr="boom")
        return subprocess.CompletedProcess(command, 0, stdout="")

    prod_context = module.CommandContext(
        root_dir=context_dir,
        env={
            "GITHUB_ACTIONS": "true",
            "PULUMI_EXPECTED_SHA": "e" * 40,
        },
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=plan_failure_runner,
    )
    assert (  # nosec B101
        module._run_up_plan_stack(prod_context, "prod", tmp_path / "prod.plan") == 42
    )

    direct_calls: list[list[str]] = []

    def direct_runner(command, **kwargs):
        direct_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="")

    direct_context = module.CommandContext(
        root_dir=context_dir,
        env={},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="",
        runner=direct_runner,
    )
    assert module._run_up_stack(direct_context, "test") is None
    assert any(  # nosec B101
        len(command) > 3 and command[3] == "up" for command in direct_calls
    )

    ci_success_calls: list[list[str]] = []

    def ci_success_runner(command, **kwargs):
        ci_success_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="")

    ci_success_context = module.CommandContext(
        root_dir=context_dir,
        env={"GITHUB_ACTIONS": "true", "PULUMI_EXPECTED_SHA": "g" * 40},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=ci_success_runner,
    )
    assert module._run_up_stack(ci_success_context, "test") == 1  # nosec B101
    assert ci_success_calls == []  # nosec B101

    def direct_failure_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 17, stdout="", stderr="boom")

    failed_context = module.CommandContext(
        root_dir=context_dir,
        env={},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=context_dir / ".artifacts" / "pulumi-plan",
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="awskms://alias/example?region=eu-central-1",
        runner=direct_failure_runner,
    )
    assert module._run_up_stack(failed_context, "test") == 17  # nosec B101


def test_run_pulumi_command_dispatch_propagates_apply_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Command dispatch should return failed up-plan and up statuses."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"
    plan_dir = context_dir / ".artifacts" / "pulumi-plan"
    plan_dir.mkdir(parents=True)
    plan_file = plan_dir / f"{module._safe_artifact_stem('test')}.plan"
    plan_file.write_text("plan", encoding="utf-8")
    (plan_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "createdAtEpoch": 1000,
                "commitSha": "sha-a",
                "backendUrl": "file:///tmp/backend",
                "pulumiDir": "pulumi",
                "policyPackDir": "policy",
                "stacks": [
                    {
                        "stack": "test",
                        "planFile": f".artifacts/pulumi-plan/{plan_file.name}",
                        "planSha256": hashlib.sha256(b"plan").hexdigest(),
                        **preview_binding(context_dir),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    context = module.CommandContext(
        root_dir=context_dir,
        env={"PULUMI_PLAN_NOW_EPOCH": "1000", "PULUMI_EXPECTED_SHA": "sha-a"},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=plan_dir,
        preview_artifact_dir=context_dir / ".artifacts" / "pulumi-preview",
        backend_url="file:///tmp/backend",
        secrets_provider="",
        runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    monkeypatch.setattr(module, "_select_or_init_stack", lambda *args: None)
    monkeypatch.setattr(module, "_run_up_plan_stack", lambda *args: 13)
    assert module._run_up_plan_command(context, ["test"]) == 13  # nosec B101

    seen_up_stacks: list[str] = []

    def fake_up_stack(_context, stack):
        seen_up_stacks.append(stack)
        return None if stack == "first" else 11

    monkeypatch.setattr(module, "_run_up_stack", fake_up_stack)
    assert module._run_regular_command("up", context, ["first", "second"]) == 11
    assert seen_up_stacks == ["first", "second"]  # nosec B101


def test_run_plan_command_does_not_cancel_before_preview(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Plan creation should not cancel a possibly active update before preview."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    context_dir = tmp_path / "repo"
    plan_dir = context_dir / ".artifacts" / "pulumi-plan"
    preview_dir = context_dir / ".artifacts" / "pulumi-preview"
    calls: list[list[str]] = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        if len(command) > 3 and command[3] == "preview":
            plan_path = Path(command[command.index("--save-plan") + 1])
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text("plan", encoding="utf-8")
            stdout = kwargs.get("stdout")
            if stdout is not None:
                stdout.write('{"steps": []}')
        return subprocess.CompletedProcess(command, 0, stdout="")

    context = module.CommandContext(
        root_dir=context_dir,
        env={"GITHUB_ACTIONS": "true", "PULUMI_COMMIT_SHA": "a" * 40},
        pulumi_dir=context_dir / "pulumi",
        policy_pack_dir=context_dir / "policy",
        plan_dir=plan_dir,
        preview_artifact_dir=preview_dir,
        backend_url="file:///tmp/backend",
        secrets_provider="",
        runner=fake_runner,
    )

    def fake_write_preview_summary(_root_dir, _preview_file, summary_file, **_kwargs):
        summary_file.write_text("summary\n", encoding="utf-8")

    monkeypatch.setattr(module, "_select_or_init_stack", lambda *args: None)
    monkeypatch.setattr(module, "_write_preview_summary", fake_write_preview_summary)
    assert module._run_plan_command(context, ["test"]) == 0  # nosec B101
    assert not any(  # nosec B101
        len(command) > 3 and command[3] == "cancel" for command in calls
    )


def test_run_pulumi_command_runs_generic_and_plan_without_github_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cover non-plan command dispatch and plan summaries without GitHub outputs."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    repo_dir = tmp_path / "repo"
    pulumi_dir = repo_dir / "pulumi"
    policy_dir = repo_dir / "policy"
    pulumi_dir.mkdir(parents=True)
    policy_dir.mkdir()
    monkeypatch.setattr(module, "repo_root", lambda _: repo_dir)
    monkeypatch.setenv("PULUMI_STACK", "test")
    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER", "awskms://alias/example?region=eu-central-1"
    )
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "pulumi" and command[3] == "preview":
            stdout = kwargs.get("stdout")
            if stdout is not None:
                stdout.write('{"changeSummary": {}, "steps": []}')
            if "--save-plan" in command:
                plan_path = Path(command[command.index("--save-plan") + 1])
                plan_path.write_text("plan", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0)
        if command[:3] == ["uv", "--project", str(repo_dir)]:
            return subprocess.CompletedProcess(command, 0, stdout="summary\n")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(module, "run", fake_run)
    assert module.main(["preview"]) == 0  # nosec B101
    preview_called = any(
        len(command) > 3 and command[3] == "preview" for command in calls
    )
    assert preview_called  # nosec B101

    calls.clear()
    assert module.main(["plan"]) == 0  # nosec B101
    assert "summary" in capsys.readouterr().out  # nosec B101
    assert all("plan_files<<EOF" not in str(command) for command in calls)  # nosec B101


@pytest.mark.parametrize(
    "command_name, action, plan_flag",
    [
        ("plan", "preview", "--save-plan"),
        ("up-plan", "up", "--plan"),
    ],
)
def test_saved_plan_commands_refresh_cloud_state_without_separate_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command_name, action, plan_flag
):
    """Both plan phases reconcile drift; preview never writes a checkpoint."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    calls = []
    context = module.CommandContext(
        root_dir=tmp_path,
        env={},
        pulumi_dir=tmp_path / "pulumi",
        policy_pack_dir=tmp_path / "policy",
        plan_dir=tmp_path / "plans",
        preview_artifact_dir=tmp_path / "preview",
        backend_url="s3://state/test",
        secrets_provider="awskms://alias/test",
        runner=lambda command, **kwargs: calls.append(command),
    )
    plan = tmp_path / "plans/reviewed.plan"
    module._run_stack_command(
        context,
        module.StackCommand(command_name, "test", plan_path=plan),
    )
    assert len(calls) == 1
    command = calls[0]
    assert command[3] == action
    assert command.count("--refresh") == 1
    assert command[command.index(plan_flag) + 1] == str(plan)
    assert command[command.index("--policy-pack") + 1] == str(tmp_path / "policy")
    assert not {"--target", "--replace", "--force"}.intersection(command)


def test_saved_plan_replay_prepares_mandatory_policy_pack(monkeypatch, tmp_path):
    """Gated replay validates policy even when the preview pack ran elsewhere."""
    module = load_script_module(monkeypatch, "run_pulumi_command")
    prepared = []
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module, "_prepare_policy_pack", lambda root, env: prepared.append(root)
    )
    context = module.CommandContext(
        root_dir=tmp_path,
        env={},
        pulumi_dir=tmp_path / "pulumi",
        policy_pack_dir=tmp_path / "policy",
        plan_dir=tmp_path / "plans",
        preview_artifact_dir=tmp_path / "preview",
        backend_url="s3://state/test",
        secrets_provider="awskms://alias/test",
        runner=lambda *args, **kwargs: None,
    )
    module._login_and_prepare("up-plan", context)
    assert prepared == [tmp_path]
