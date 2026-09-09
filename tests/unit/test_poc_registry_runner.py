"""Trusted registry driver exercises real graph gates with synthetic native facts."""

import copy
import importlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, replace

import pytest
import test_poc_registry_phase_entrypoint as phase_tests
import test_poc_registry_plan as graph_tests

module = importlib.import_module("poc_registry_runner")


def summary():
    return {
        "state": {
            "kind": "observed_checkpoint",
            "VersionId": "original",
            "ETag": '"etag"',
            "sha256": "a" * 64,
        },
        "kms_key_arn": f"arn:aws:kms:eu-central-1:{module.backend.ACCOUNT}:key/"
        + "1" * 36,
    }


def identity():
    return {
        "accountId": module.backend.ACCOUNT,
        "backendUrl": f"s3://{module.backend.BUCKET}",
        "project": module.backend.PROJECT,
        "stack": "test",
        "kmsKeyArn": summary()["kms_key_arn"],
        "checkpointVersionId": "original",
        "checkpointETag": '"etag"',
    }


def repository(name):
    return {
        "repositoryName": name,
        "registryId": module.backend.ACCOUNT,
        "repositoryArn": (
            f"arn:aws:ecr:eu-central-1:{module.backend.ACCOUNT}:repository/{name}"
        ),
        "repositoryUri": (
            f"{module.backend.ACCOUNT}.dkr.ecr.eu-central-1.amazonaws.com/{name}"
        ),
        "imageTagMutability": "IMMUTABLE",
        "imageScanningConfiguration": {"scanOnPush": True},
    }


@pytest.fixture
def driver(tmp_path, monkeypatch):
    contract = phase_tests.contract()
    source = {
        "source": asdict(phase_tests.source(contract)),
        "request": {
            "command": "up",
            "target_environment": "test",
            "pull_request_number": "19",
        },
    }
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        module.providers, "verify_runtime", module.providers.plugin_home
    )
    monkeypatch.setenv("GITHUB_SHA", source["source"]["base_sha"])
    monkeypatch.setenv("GH_TOKEN", "PRIVATE_SENTINEL")
    monkeypatch.setenv("PYTHONPATH", "/hostile/pr")
    monkeypatch.setenv("PULUMI_PLAN_FILE", "/hostile/plan")
    monkeypatch.setattr(module, "_trusted_root", lambda: "b" * 40)
    monkeypatch.setattr(
        module.artifact, "load_verified_contract", lambda **_: (source, contract)
    )
    monkeypatch.setattr(module, "_git", lambda *args: b"config: {}\n")
    calls = []
    monkeypatch.setattr(
        module.preflight, "revalidate_requester", lambda request: None, raising=False
    )
    monkeypatch.setattr(module, "_review", lambda source: calls.append("review"))
    data = graph_tests.case("baseline")

    def capture(source, operation):
        calls.append(operation)
        rows = (
            list(graph_tests.states().values())
            if "accepted" in calls
            else copy.deepcopy(data["prior_resources"])
        )
        return module.backend.PrivateBackendCapture(
            summary=summary(),
            resources=rows,
        )

    monkeypatch.setattr(module.backend, "capture_backend", capture)
    monkeypatch.setattr(
        module,
        "ecr_read",
        lambda name: repository(name) if "accepted" in calls else None,
    )

    def dispatch(command, context, stacks):
        calls.append("dispatch")
        assert stacks == ["test"] and command in ("plan", "up-plan")
        assert context.pulumi_dir == tmp_path / ".poc-registry/pulumi"
        assert (context.pulumi_dir / "Pulumi.test.yaml").read_text() == "config: {}\n"
        program = (context.pulumi_dir / "__main__.py").read_text()
        assert "run_registry_phase" in program and "UserServiceStack" not in program
        assert "PRIVATE_SENTINEL" not in json.dumps(context.env)
        assert "PYTHONPATH" not in context.env and "PULUMI_PLAN_FILE" not in context.env
        assert context.env["PULUMI_PYTHON_CMD"] == str(tmp_path / ".venv/bin/python")
        assert context.env["UV_NO_SYNC"] == "true"
        assert context.env["PULUMI_HOME"] == str(tmp_path / ".poc-provider-runtime")
        assert context.env["PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION"] == "true"
        assert context.env["PULUMI_IGNORE_AMBIENT_PLUGINS"] == "true"
        context.plan_dir.mkdir(parents=True, exist_ok=True)
        context.preview_artifact_dir.mkdir(parents=True, exist_ok=True)
        plan = context.plan_dir / "test.plan"
        preview = context.preview_artifact_dir / "test.json"
        plan.write_text(json.dumps(data["saved_plan"]))
        preview.write_text(json.dumps(data["preview"]))
        context.registry_plan_gate(
            replace(context, provider_identity=identity()), "test", plan, preview
        )
        calls.append("accepted")
        return 0

    monkeypatch.setattr(module.runner, "_dispatch_command", dispatch)
    return {
        "source": source,
        "contract": contract,
        "data": data,
        "calls": calls,
        "root": tmp_path,
        "capture": capture,
    }


def execute(command="plan"):
    return module.execute(
        command, artifact_id="123", archive_sha256="a" * 64, source_sha256="b" * 64
    )


@pytest.mark.parametrize("command", ["plan", "up-plan"])
def test_real_driver_project_and_gate_path(driver, command):
    assert execute(command) == 0
    expected = ["review", command, "dispatch", "review", command, "accepted"]
    if command == "up-plan":
        expected.append(command)
    assert driver["calls"] == expected
    assert not (driver["root"] / ".poc-registry").exists()


def test_initial_provider_and_repeated_registry(driver, monkeypatch):
    driver["data"].update(graph_tests.case("new"))
    assert execute() == 0
    driver["calls"].clear()
    driver["data"].update(graph_tests.case("repeat"))
    monkeypatch.setattr(module, "ecr_read", repository)
    assert execute() == 0


@pytest.mark.parametrize(
    "field,value", [("command", "plan"), ("target_environment", "prod")]
)
def test_source_request_is_authority_not_cli(driver, field, value):
    driver["source"]["request"][field] = value
    with pytest.raises(ValueError):
        execute("up-plan")
    assert driver["calls"] == []


def test_foreign_runtime_base_and_unknown_command(driver):
    driver["source"]["source"]["base_sha"] = "c" * 40
    with pytest.raises(ValueError):
        execute()
    with pytest.raises(ValueError):
        execute("destroy")
    assert driver["calls"] == []


def test_no_checkpoint_is_not_initial_authority(driver, monkeypatch):
    monkeypatch.setattr(
        module.backend,
        "capture_backend",
        lambda *a, **k: module.backend.PrivateBackendCapture(
            summary={"state": {"kind": "observed_absence"}}, resources=[]
        ),
    )
    with pytest.raises(ValueError):
        execute()
    assert "dispatch" not in driver["calls"]


def test_existing_foreign_repository_cannot_be_adopted(driver, monkeypatch):
    monkeypatch.setattr(module, "ecr_read", repository)
    with pytest.raises(ValueError):
        execute()
    assert "dispatch" not in driver["calls"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("registryId", "933245420672"),
        ("imageTagMutability", "MUTABLE"),
        ("imageScanningConfiguration", {"scanOnPush": False}),
    ],
)
def test_repeat_requires_actual_registry_identity_and_controls(
    driver, monkeypatch, field, value
):
    driver["data"].update(graph_tests.case("repeat"))
    monkeypatch.setattr(
        module, "ecr_read", lambda name: {**repository(name), field: value}
    )
    with pytest.raises(ValueError):
        execute()


def test_checkpoint_race_and_provider_binding_block_before_acceptance(
    driver, monkeypatch
):
    original = driver["capture"]

    def raced(source, operation):
        capture = original(source, operation)
        if "dispatch" in driver["calls"]:
            capture.summary["state"]["VersionId"] = "changed"
        return capture

    monkeypatch.setattr(module.backend, "capture_backend", raced)
    with pytest.raises(ValueError):
        execute()
    assert "accepted" not in driver["calls"]
    assert not (driver["root"] / ".poc-registry").exists()
    context = type("Context", (), {"provider_identity": None})()
    with pytest.raises(ValueError):
        module._binding(context, original({}, "plan"))
    context.provider_identity = {**identity(), "checkpointETag": '"changed"'}
    with pytest.raises(ValueError):
        module._binding(context, original({}, "plan"))


def test_actual_graph_rejects_foreign_change_before_acceptance(driver):
    graph_tests.ecr_step(driver["data"])["op"] = "update"
    with pytest.raises(ValueError):
        execute()
    assert "accepted" not in driver["calls"]


def test_fixed_project_does_not_reuse_existing_directory(driver):
    directory = driver["root"] / ".poc-registry"
    directory.mkdir()
    marker = directory / "keep"
    marker.write_text("untouched")
    with pytest.raises(FileExistsError):
        execute()
    assert marker.read_text() == "untouched"


@pytest.mark.parametrize("raw", [b'{"steps":[],"steps":[]}', b'{"x": NaN}', b"[]"])
def test_original_plan_decoder_rejects_ambiguity(tmp_path, raw):
    path = tmp_path / "plan"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        module._read_plan(path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        module._read_plan(link)


def test_native_ecr_transport_and_exact_missing_code(monkeypatch):
    name = "user-service-test-web"
    responses = [
        subprocess.CompletedProcess(
            [], 0, json.dumps({"repositories": [repository(name)]}).encode(), b""
        ),
        subprocess.CompletedProcess(
            [],
            254,
            b"",
            b"An error occurred (RepositoryNotFoundException) "
            b"when calling the DescribeRepositories operation: absent",
        ),
        subprocess.CompletedProcess(
            [],
            254,
            b"",
            b"An error occurred (AccessDeniedException) "
            b"when calling the DescribeRepositories operation: PRIVATE",
        ),
        subprocess.CompletedProcess([], 0, b'{"repositories":[]}', b""),
    ]

    def run(command, **kwargs):
        assert command[:3] == ["aws", "ecr", "describe-repositories"]
        assert command[command.index("--registry-id") + 1] == module.backend.ACCOUNT
        assert command[command.index("--repository-names") + 1] == name
        assert kwargs["env"]["AWS_MAX_ATTEMPTS"] == "1"
        return responses.pop(0)

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.ecr_read(name) == repository(name)
    assert module.ecr_read(name) is None
    with pytest.raises(ValueError):
        module.ecr_read(name)
    with pytest.raises(ValueError):
        module.ecr_read(name)
    with pytest.raises(ValueError):
        module.ecr_read("foreign")


def test_git_binding_checks_return_code(monkeypatch):
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, b"PRIVATE", b"PRIVATE"),
    )
    with pytest.raises(ValueError, match="Registry execution precondition failed"):
        module._git("rev-parse", "HEAD")


def test_installed_revision_remote_and_venv_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.artifact, "_context", lambda env: ("101", "b" * 40))
    monkeypatch.setattr(module.sys, "prefix", str(tmp_path / ".venv"))
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").touch()
    replies = {
        "--show-toplevel": str(tmp_path).encode(),
        "HEAD": b"b" * 40,
        "origin": f"https://github.com/{module.artifact.REPOSITORY}.git".encode(),
    }
    monkeypatch.setattr(module, "_git", lambda *a: replies.get(a[-1], b""))
    assert module._trusted_root() == "b" * 40
    replies["HEAD"] = b"c" * 40
    with pytest.raises(ValueError):
        module._trusted_root()
    replies["HEAD"] = b"b" * 40
    replies["origin"] = b"https://github.com/foreign/repository.git"
    with pytest.raises(ValueError):
        module._trusted_root()


def test_current_review_uses_authenticated_fact_identities(monkeypatch):
    source = {
        "source": {"head_sha": "a" * 40, "base_sha": "b" * 40},
        "request": {"pull_request_number": "19"},
    }
    calls = []
    monkeypatch.setattr(
        module.preflight, "revalidate_requester", lambda request: None, raising=False
    )
    monkeypatch.setattr(
        module, "verify_reviewed_source", lambda *a, **k: calls.append((a, k))
    )
    module._review(source)
    assert calls[0][0] == (module.artifact.REPOSITORY, "19", "a" * 40, "b" * 40)
    assert calls[0][1]["gh"] is module.preflight.gh


def test_cli_redacts_failures_and_returns_success(monkeypatch, capsys):
    args = [
        "plan",
        "--artifact-id",
        "123",
        "--archive-sha256",
        "a" * 64,
        "--source-sha256",
        "b" * 64,
    ]
    monkeypatch.setattr(module, "execute", lambda **k: 0)
    assert module.main(args) == 0
    monkeypatch.setattr(
        module, "execute", lambda **k: (_ for _ in ()).throw(ValueError("PRIVATE"))
    )
    assert module.main(args) == 1
    assert capsys.readouterr().err == "INVALID: registry execution failed\n"


def test_real_isolated_cli_rejects_untrusted_context(tmp_path):
    (tmp_path / "json.py").write_text("raise RuntimeError('PR IMPORT')")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            module.__file__,
            "plan",
            "--artifact-id",
            "123",
            "--archive-sha256",
            "a" * 64,
            "--source-sha256",
            "b" * 64,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(tmp_path)},
        timeout=30,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "INVALID: registry execution failed\n"


def test_drift_requires_full_registry_and_uses_preview_session(driver, monkeypatch):
    with pytest.raises(ValueError):
        execute("drift")
    assert "dispatch" not in driver["calls"]
    driver["calls"].clear()
    driver["data"].update(graph_tests.case("repeat"))
    monkeypatch.setattr(module, "ecr_read", repository)
    assert execute("drift") == 0
    assert driver["calls"] == [
        "review",
        "plan",
        "dispatch",
        "review",
        "plan",
        "accepted",
    ]


def test_failed_apply_has_no_successful_postcondition(driver, monkeypatch):
    monkeypatch.setattr(module.runner, "_dispatch_command", lambda *args: 2)
    assert execute("up-plan") == 2
    assert driver["calls"] == ["review", "up-plan"]


def test_successful_apply_must_materialize_full_graph(driver, monkeypatch):
    original = driver["capture"]

    def incomplete(source, operation):
        captured = original(source, operation)
        if "accepted" in driver["calls"]:
            return module.backend.PrivateBackendCapture(summary=summary(), resources=[])
        return captured

    monkeypatch.setattr(module.backend, "capture_backend", incomplete)
    monkeypatch.setattr(module, "ecr_read", lambda name: None)
    with pytest.raises(ValueError):
        execute("up-plan")


def test_git_success_uses_fixed_checkout_and_literal_arguments(monkeypatch):
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0, b"public-object-id\n", b"")

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module._git("rev-parse", "HEAD") == b"public-object-id\n"
    assert calls[0][0] == ["git", "-C", str(module.ROOT), "rev-parse", "HEAD"]
    assert calls[0][1]["capture_output"] is True


def test_plan_bytes_cannot_change_during_native_recheck(driver, monkeypatch):
    original = driver["capture"]

    def raced(source, operation):
        capture = original(source, operation)
        if "dispatch" in driver["calls"]:
            path = driver["root"] / ".artifacts/pulumi-plan/test.plan"
            path.write_text(path.read_text() + "\n")
        return capture

    monkeypatch.setattr(module.backend, "capture_backend", raced)
    with pytest.raises(ValueError):
        execute()
    assert "accepted" not in driver["calls"]


def test_generated_program_uses_only_installed_module_path(driver, monkeypatch):
    root = driver["root"]
    (root / "scripts").mkdir()
    (root / "pulumi").mkdir()
    trusted = root / "scripts/poc_registry_phase_entrypoint.py"
    trusted.write_text(
        "import json\n"
        "class RegistryPhaseProjection:\n"
        "    def __init__(self, values): self.registries = values\n"
        "def run_registry_phase(projection):\n"
        "    print(json.dumps(projection.registries, sort_keys=True))\n"
    )
    hostile = root / "hostile"
    hostile.mkdir()
    (hostile / "poc_registry_phase_entrypoint.py").write_text(
        "raise RuntimeError('PR source must not execute')\n"
    )
    projection = graph_tests.projection()
    with module._project(projection) as project:
        result = subprocess.run(
            [sys.executable, "-I", str(project / "__main__.py")],
            cwd=hostile,
            env={**os.environ, "PYTHONPATH": str(hostile)},
            capture_output=True,
            text=True,
            timeout=30,
        )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == module.graph.REGISTRIES


def test_native_ecr_new_cli_prefix_is_still_exact_error_code(monkeypatch):
    response = subprocess.CompletedProcess(
        [],
        254,
        b"",
        b"aws: [ERROR]: An error occurred "
        b"(RepositoryNotFoundException) when calling the "
        b"DescribeRepositories operation: absent",
    )
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: response)
    assert module.ecr_read("user-service-test-web") is None
    response.stderr = response.stderr.replace(
        b"RepositoryNotFoundException", b"AccessDeniedException"
    )
    with pytest.raises(ValueError):
        module.ecr_read("user-service-test-web")


def test_requester_revocation_after_graph_validation_blocks_apply(driver, monkeypatch):
    monkeypatch.setattr(
        module.preflight,
        "revalidate_requester",
        lambda request: (_ for _ in ()).throw(ValueError("revoked")),
        raising=False,
    )
    with pytest.raises(ValueError):
        execute("up-plan")
    assert "accepted" not in driver["calls"]


def test_provider_verification_failure_prevents_dispatch(driver, monkeypatch):
    def fail(root):
        assert root == driver["root"]
        raise ValueError("unverified provider")

    monkeypatch.setattr(module.providers, "verify_runtime", fail)
    with pytest.raises(ValueError, match="unverified provider"):
        execute()
    assert "dispatch" not in driver["calls"]
    assert not (driver["root"] / ".poc-registry").exists()


def test_incoming_plugin_environment_cannot_override_fixed_runtime(driver, monkeypatch):
    for key in (
        "PULUMI_HOME",
        "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION",
        "PULUMI_IGNORE_AMBIENT_PLUGINS",
    ):
        monkeypatch.setenv(key, "hostile")
    assert execute() == 0


def test_provider_environment_reaches_actual_pulumi_subprocess(driver, monkeypatch):
    root = driver["root"]
    binaries = root / "bin"
    binaries.mkdir()
    executable = binaries / "pulumi"
    executable.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        'print(json.dumps({"args":sys.argv[1:],"env":dict(os.environ)}))\n'
    )
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(binaries))
    env = module._child_environment(driver["source"])
    context = module.runner.CommandContext(
        root_dir=root,
        env=env,
        pulumi_dir=root / "pulumi",
        policy_pack_dir=root / "policy",
        plan_dir=root / "plans",
        preview_artifact_dir=root / "previews",
        backend_url=env["PULUMI_BACKEND_URL"],
        secrets_provider=env["PULUMI_SECRETS_PROVIDER"],
    )
    output = root / "subprocess.json"
    with output.open("w") as stream:
        module.runner._run_stack_command(
            context,
            module.runner.StackCommand(
                "plan", "test", plan_path=root / "test.plan", stdout=stream
            ),
        )
    observed = json.loads(output.read_text())
    assert observed["args"][2] == "preview"
    assert "--save-plan" in observed["args"]
    assert observed["env"]["PULUMI_HOME"] == str(root / ".poc-provider-runtime")
    assert observed["env"]["PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION"] == "true"
    assert observed["env"]["PULUMI_IGNORE_AMBIENT_PLUGINS"] == "true"
    assert "GH_TOKEN" not in observed["env"] and "PYTHONPATH" not in observed["env"]
