"""An installed registry gate must run inside sealing and replay boundaries."""

from dataclasses import replace

import pytest
from test_saved_plan_destructive_gate import preview, seal_existing, setup_command


@pytest.mark.parametrize("command", ["plan", "up-plan", "preview"])
@pytest.mark.parametrize("registry", [False, True])
def test_show_sames_is_required_only_for_registry_plan(
    monkeypatch, tmp_path, command, registry
):
    module, context, _ = setup_command(monkeypatch, tmp_path, preview())
    if registry:
        context = replace(context, registry_plan_gate=lambda *_: None)
    invocation = module._pulumi_command(
        context, module.StackCommand(command, "test", plan_path=tmp_path / "test.plan")
    )
    assert ("--show-sames" in invocation) is (registry and command == "plan")


def test_isolated_policy_and_summary_hooks_preserve_legacy_plan_gates(
    monkeypatch, tmp_path
):
    module, context, commands = setup_command(monkeypatch, tmp_path, preview())
    calls = []

    def forbidden(*_a, **_k):
        raise AssertionError("Legacy preparation must not import PR policy as root")

    def summary(source, destination):
        assert source.read_text() == preview()
        destination.write_text("trusted summary\n")
        calls.append("summary")

    context = replace(
        context,
        prepare_policy_pack=lambda prepared: calls.append("policy"),
        summarize_preview=summary,
    )
    monkeypatch.setattr(module, "_prepare_policy_pack", forbidden)
    monkeypatch.setattr(module, "_write_preview_summary", forbidden)
    module._login_and_prepare("plan", context)
    assert "login" in commands[0]
    assert module._run_plan_command(context, ["test"]) == 0
    assert calls == ["policy", "summary"]
    assert module._plan_manifest_file(context).is_file()


@pytest.mark.parametrize("operation", ["plan", "up-plan"])
def test_rejected_registry_graph_never_seals_or_applies(
    monkeypatch, tmp_path, operation
):
    module, context, commands = setup_command(monkeypatch, tmp_path, preview())
    seen = []

    def reject(prepared, stack, plan, original_preview):
        seen.append(stack)
        assert prepared.registry_plan_gate is reject
        assert plan.read_text() == "sealed plan"
        assert original_preview.read_text() == preview()
        if operation == "plan":
            assert not module._plan_manifest_file(context).exists()
        raise ValueError("Registry graph rejected")

    context = replace(context, registry_plan_gate=reject)
    if operation == "up-plan":
        seal_existing(module, context, "test", preview())
    run = (
        module._run_plan_command if operation == "plan" else module._run_up_plan_command
    )
    with pytest.raises(ValueError, match="Registry graph rejected"):
        run(context, ["test"])
    assert seen == ["test"]
    assert not any("--plan" in command for command in commands)
    if operation == "plan":
        assert not module._plan_manifest_file(context).exists()


def test_registry_gate_runs_after_provider_binding_and_before_apply(
    monkeypatch, tmp_path
):
    module, context, _ = setup_command(monkeypatch, tmp_path, preview())
    order = []

    def gate(_prepared, stack, _plan, original_preview):
        assert stack == "test" and original_preview.read_text() == preview()
        order.append("graph")

    context = replace(context, registry_plan_gate=gate)
    seal_existing(module, context, "test", preview())
    monkeypatch.setattr(
        module, "verify_provider_identity", lambda *_: order.append("provider")
    )
    monkeypatch.setattr(module, "_run_up_plan_stack", lambda *_: order.append("apply"))
    assert module._run_up_plan_command(context, ["test"]) == 0
    assert order == ["provider", "graph", "apply"]


def test_corrupt_preview_cannot_reach_registry_gate(monkeypatch, tmp_path):
    module, context, commands = setup_command(monkeypatch, tmp_path, preview())

    def forbidden(*_):
        raise AssertionError("Registry gate must follow manifest byte verification")

    context = replace(context, registry_plan_gate=forbidden)
    path, _ = seal_existing(module, context, "test", preview())
    path.write_text("tampered")
    assert module._run_up_plan_command(context, ["test"]) == 1
    assert commands == []


def test_replay_rechecks_preview_binding_after_provider_verification(
    monkeypatch, tmp_path
):
    """A preview binding lost after manifest validation cannot reach gate or apply."""
    module, context, commands = setup_command(monkeypatch, tmp_path, preview())
    seen = []

    def forbidden(*_):
        raise AssertionError("Missing preview must prevent graph validation")

    def invalidate_preview(_prepared, entry):
        seen.append("provider")
        entry.pop("previewFile")

    context = replace(context, registry_plan_gate=forbidden)
    seal_existing(module, context, "test", preview())
    monkeypatch.setattr(module, "verify_provider_identity", invalidate_preview)
    assert module._run_up_plan_command(context, ["test"]) == 1
    assert seen == ["provider"]
    assert any(command[3:5] == ["stack", "select"] for command in commands)
    assert not any("--plan" in command for command in commands)
