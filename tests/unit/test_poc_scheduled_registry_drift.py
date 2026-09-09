"""Scheduled native provenance and the actual saved-preview gate, without AWS."""

import copy
import importlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
import test_poc_registry_plan as graph_tests
import test_poc_registry_runner as runner_tests

module = importlib.import_module("poc_scheduled_registry_drift")
runtime = module.runtime
SHA = "b" * 40


@pytest.fixture
def scheduled(tmp_path, monkeypatch):
    """Use native-shaped API responses and the real checkout/provenance validator."""
    contract = (Path(module.__file__).parents[1] / module.CONTRACT_PATH).read_bytes()
    repository = {
        "id": module.REPOSITORY_ID,
        "full_name": module.REPOSITORY,
        "owner": {"id": module.OWNER_ID},
        "default_branch": "main",
    }
    run = {
        "id": 101,
        "run_attempt": 1,
        "event": "schedule",
        "path": module.WORKFLOW,
        "head_branch": "main",
        "head_sha": SHA,
        "status": "in_progress",
        "conclusion": None,
        "repository": copy.deepcopy(repository),
        "head_repository": copy.deepcopy(repository),
    }
    ref = {"ref": "refs/heads/main", "object": {"type": "commit", "sha": SHA}}
    environment = {
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": module.REPOSITORY,
        "GITHUB_REPOSITORY_ID": str(module.REPOSITORY_ID),
        "GITHUB_REPOSITORY_OWNER_ID": str(module.OWNER_ID),
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": "101",
        "GITHUB_SHA": SHA,
        "GITHUB_WORKFLOW_SHA": SHA,
        "GITHUB_WORKFLOW_REF": f"{module.REPOSITORY}/{module.WORKFLOW}@refs/heads/main",
        "GH_TOKEN": "PRIVATE_SENTINEL",
        "PYTHONPATH": "/hostile/pr",
        "PULUMI_PLAN_FILE": "/hostile/plan",
        "UV_NO_SYNC": "false",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    monkeypatch.setattr(runtime.sys, "prefix", str(tmp_path / ".venv"))
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").touch()
    calls = []
    data = {"contract": contract, "dirty": b""}

    def git(*args):
        calls.append(("git", args))
        if args == ("rev-parse", "--show-toplevel"):
            return str(tmp_path).encode()
        if args == ("rev-parse", "HEAD"):
            return SHA.encode()
        if args == ("remote", "get-url", "origin"):
            return f"https://github.com/{module.REPOSITORY}.git".encode()
        if args[0] in ("diff", "ls-files"):
            assert all(path in args for path in module.EXTRA_PATHS)
            return data["dirty"] if args[0] == "ls-files" else b""
        assert args[0] == "show"
        if args[1] == f"{SHA}:{module.CONTRACT_PATH}":
            return data["contract"]
        assert args[1] == f"{SHA}:pulumi/Pulumi.test.yaml"
        return b"config: {}\n"

    def gh(path):
        calls.append(("gh", path))
        return copy.deepcopy(
            {
                module.API: repository,
                f"{module.API}/actions/runs/101": run,
                f"{module.API}/git/ref/heads/main": ref,
            }[path]
        )

    monkeypatch.setattr(runtime, "_git", git)
    monkeypatch.setattr(module, "gh", gh)
    return {
        "root": tmp_path,
        "repository": repository,
        "run": run,
        "ref": ref,
        "calls": calls,
        "data": data,
    }


@pytest.fixture
def diagnostic(scheduled, monkeypatch):
    """Run real dispatch, plan generation and manifest sealing with fake CLI I/O."""
    data = graph_tests.case("repeat")
    captures = []
    operations = []

    def capture(digest):
        assert len(digest) == 64
        captures.append(digest)
        return runtime.backend.PrivateBackendCapture(
            summary=runner_tests.summary(),
            resources=copy.deepcopy(data["prior_resources"]),
        )

    @contextmanager
    def prepare(context, stack):
        assert stack == "test"
        yield replace(context, provider_identity=runner_tests.identity())

    def emit(context, request):
        operations.append(request.command)
        assert request.command == "plan" and request.stack == "test"
        assert context.env["UV_NO_SYNC"] == "true"
        assert context.env["UV_FROZEN"] == "true"
        assert context.env["PULUMI_COMMIT_SHA"] == SHA
        assert "PRIVATE_SENTINEL" not in json.dumps(context.env)
        assert "PYTHONPATH" not in context.env
        assert "PULUMI_PLAN_FILE" not in context.env
        program = (context.pulumi_dir / "__main__.py").read_text()
        assert "run_registry_phase" in program and "UserServiceStack" not in program
        request.plan_path.write_text(json.dumps(data["saved_plan"]))
        request.stdout.write(json.dumps(data["preview"]))

    def select(context, stack):
        assert stack == "test"
        operations.append("select")
        return None

    def login(command, context):
        assert command == "plan"
        operations.append("login")

    monkeypatch.setattr(runtime.backend, "capture_scheduled_backend", capture)
    monkeypatch.setattr(runtime, "ecr_read", runner_tests.repository)
    monkeypatch.setattr(runtime.runner, "_login_and_prepare", login)
    monkeypatch.setattr(runtime.runner, "_select_or_init_stack", select)
    monkeypatch.setattr(runtime.runner, "prepared_stack_configuration", prepare)
    monkeypatch.setattr(runtime.runner, "_run_stack_command", emit)
    monkeypatch.setattr(
        runtime.runner,
        "_write_preview_summary",
        lambda root, preview, summary, **kw: summary.write_text("diagnostic\n"),
    )
    return {**scheduled, "plan": data, "captures": captures, "operations": operations}


def test_native_provenance_and_installed_contract_precredential(scheduled, monkeypatch):
    monkeypatch.setattr(
        runtime.backend,
        "capture_scheduled_backend",
        lambda *args: pytest.fail("Verification must not access AWS"),
    )
    assert module.verify_provenance() == module.ScheduledProvenance("101", SHA)
    assert module.main(["verify"]) == 0
    assert {call[1] for call in scheduled["calls"] if call[0] == "gh"} == {
        module.API,
        f"{module.API}/actions/runs/101",
        f"{module.API}/git/ref/heads/main",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_EVENT_NAME", "repository_dispatch"),
        ("GITHUB_EVENT_NAME", "workflow_dispatch"),
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("GITHUB_REPOSITORY_ID", "123"),
        ("GITHUB_REPOSITORY_OWNER_ID", "123"),
        ("GITHUB_REPOSITORY", "other/repository"),
        ("GITHUB_WORKFLOW_REF", "foreign/workflow@refs/heads/main"),
        ("GITHUB_WORKFLOW_SHA", "a" * 40),
        ("GITHUB_RUN_ID", "../101"),
        ("GITHUB_SHA", ""),
    ],
)
def test_wrong_context_rejected_before_api(scheduled, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        module.verify_provenance()
    assert scheduled["calls"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", True),
        ("run_attempt", 2),
        ("event", "workflow_dispatch"),
        ("path", ".github/workflows/self-deploy.yml"),
        ("head_branch", "feature"),
        ("head_sha", "a" * 40),
        ("status", "completed"),
        ("conclusion", "success"),
    ],
)
def test_native_run_fields_cannot_be_forged_by_environment(scheduled, field, value):
    scheduled["run"][field] = value
    with pytest.raises(ValueError):
        module.verify_provenance()


@pytest.mark.parametrize("repository", ["repository", "head_repository"])
@pytest.mark.parametrize("field", ["id", "full_name", "owner"])
def test_run_repository_and_owner_are_exact(scheduled, repository, field):
    scheduled["run"][repository][field] = None
    with pytest.raises(ValueError):
        module.verify_provenance()


@pytest.mark.parametrize(
    "mutation", ["default", "owner", "ref", "type", "sha", "dirty"]
)
def test_current_main_and_local_schema_integrity_required(scheduled, mutation):
    if mutation == "default":
        scheduled["repository"]["default_branch"] = "other"
    elif mutation == "owner":
        scheduled["repository"]["owner"]["id"] = 1
    elif mutation == "ref":
        scheduled["ref"]["ref"] = "refs/tags/main"
    elif mutation == "dirty":
        scheduled["data"]["dirty"] = b"schemas/untracked.py\n"
    else:
        scheduled["ref"]["object"][mutation] = "foreign"
    with pytest.raises(ValueError):
        module.verify_provenance()


@pytest.mark.parametrize(
    "raw", [b"{}", b'{"a":1,"a":2}', b'{"x":NaN}', b" ", b"x" * 131073]
)
def test_installed_contract_is_strict_and_bounded(scheduled, raw):
    scheduled["data"]["contract"] = raw
    with pytest.raises(ValueError):
        module._installed_contract(module.verify_provenance())


def test_complete_graph_runs_only_fresh_preview_and_seals_diagnostic(diagnostic):
    assert module.main(["check"]) == 0
    assert diagnostic["operations"] == ["login", "select", "plan"]
    assert len(diagnostic["captures"]) == 3
    assert len([c for c in diagnostic["calls"] if c == ("gh", module.API)]) == 6
    assert not (diagnostic["root"] / ".poc-registry").exists()
    manifest = json.loads(
        (
            diagnostic["root"] / ".artifacts/poc-scheduled-registry/plan/manifest.json"
        ).read_text()
    )
    assert manifest["commitSha"] == SHA
    assert manifest["stacks"][0]["stack"] == "test"
    assert not (diagnostic["root"] / ".artifacts/pulumi-plan").exists()


@pytest.mark.parametrize("kind", ["baseline", "new", "unknown", "foreign-provider"])
def test_no_initialization_partial_graph_or_unsafe_provider(diagnostic, kind):
    if kind in ("baseline", "new"):
        diagnostic["plan"]["prior_resources"] = graph_tests.case(kind)[
            "prior_resources"
        ]
    elif kind == "unknown":
        diagnostic["plan"]["prior_resources"][-1]["type"] = "aws:ecs/service:Service"
    else:
        provider = next(
            row
            for row in diagnostic["plan"]["prior_resources"]
            if row["type"] == runtime.graph.PROVIDER
        )
        provider["inputs"]["skipRegionValidation"] = "true"
    with pytest.raises(ValueError):
        module.execute()
    assert diagnostic["operations"] == []


@pytest.mark.parametrize(
    "operation", ["create", "update", "delete", "replace", "import", "refresh"]
)
def test_complete_prior_cannot_hide_any_preview_mutation(diagnostic, operation):
    graph_tests.ecr_step(diagnostic["plan"])["op"] = operation
    with pytest.raises(ValueError):
        module.execute()
    assert not (
        diagnostic["root"] / ".artifacts/poc-scheduled-registry/plan/manifest.json"
    ).exists()


@pytest.mark.parametrize("field", ["steps", "inputDiff", "outputDiff"])
def test_saved_plan_mutation_rejected_even_with_same_preview(diagnostic, field):
    plans = diagnostic["plan"]["saved_plan"]["resourcePlans"]
    record = next(row for urn, row in plans.items() if "ecr/repository" in urn)
    if field == "steps":
        record[field] = ["update"]
    else:
        record["goal"][field] = {"updates": {"imageTagMutability": "MUTABLE"}}
    with pytest.raises(ValueError):
        module.execute()


@pytest.mark.parametrize("when", [2, 3, 4, 5, 6])
def test_main_movement_at_each_recheck_prevents_success(diagnostic, monkeypatch, when):
    original = module.gh
    reads = 0

    def gh(path):
        nonlocal reads
        response = original(path)
        if path.endswith("/git/ref/heads/main"):
            reads += 1
            if reads == when:
                response["object"]["sha"] = "c" * 40
        return response

    monkeypatch.setattr(module, "gh", gh)
    with pytest.raises(ValueError):
        module.execute()


@pytest.mark.parametrize("when", [2, 3])
def test_checkpoint_change_during_or_after_preview_rejected(
    diagnostic, monkeypatch, when
):
    original = runtime.backend.capture_scheduled_backend
    reads = 0

    def capture(digest):
        nonlocal reads
        response = original(digest)
        reads += 1
        if reads == when:
            response.summary["state"]["VersionId"] = "changed"
        return response

    monkeypatch.setattr(runtime.backend, "capture_scheduled_backend", capture)
    with pytest.raises(ValueError):
        module.execute()


def test_failed_preview_cannot_report_success(diagnostic, monkeypatch, capsys):
    monkeypatch.setattr(runtime.runner, "_dispatch_command", lambda *args: 7)
    assert module.main(["check"]) == 7
    assert capsys.readouterr().out == ""


def test_absent_checkpoint_never_reaches_dispatch_or_initialization(
    diagnostic, monkeypatch
):
    monkeypatch.setattr(
        runtime.backend,
        "capture_scheduled_backend",
        lambda digest: runtime.backend.PrivateBackendCapture(
            summary={"state": {"kind": "observed_absence"}}, resources=[]
        ),
    )
    monkeypatch.setattr(
        runtime.runner,
        "_dispatch_command",
        lambda *args: pytest.fail("Absent stack reached Pulumi execution"),
    )
    with pytest.raises(ValueError):
        module.execute()
    assert diagnostic["operations"] == []
    assert not (diagnostic["root"] / ".poc-registry").exists()


def test_diagnostic_success_is_not_phase_acceptance(diagnostic, capsys):
    assert module.main(["check"]) == 0
    output = capsys.readouterr().out
    assert output.endswith(
        "TEST registry matches installed main; diagnostic only, no phase acceptance.\n"
    )
    assert "contract_sha256" not in output
    assert "prior_authority" not in output


def test_cli_redacts_native_api_failures(scheduled, monkeypatch, capsys):
    def denied(path):
        raise subprocess.CalledProcessError(1, ["gh"], stderr="PRIVATE_SENTINEL")

    monkeypatch.setattr(module, "gh", denied)
    assert module.main(["verify"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INVALID: scheduled registry diagnostic failed\n"


@pytest.mark.parametrize("command", ["verify", "check", "up-plan", "initialize"])
def test_real_isolated_cli_rejects_untrusted_context_and_write_commands(
    tmp_path, command
):
    (tmp_path / "json.py").write_text("raise RuntimeError('PR IMPORT')")
    result = subprocess.run(
        [sys.executable, "-I", module.__file__, command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(tmp_path)},
        timeout=30,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "PR IMPORT" not in result.stderr
