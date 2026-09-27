"""Exercise sealed plumbing with synthetic observations; no admission is granted."""

import copy
import importlib
from contextlib import contextmanager
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
import test_poc_registry_runner as registry_tests
from test_poc_registry_phase_entrypoint import source as source_facts
from test_poc_workload_materializer import protected as protected
from test_poc_workload_phase_entrypoint import parameter_fixture

module = importlib.import_module("poc_workload_runner")


@pytest.fixture
def driver(protected, monkeypatch):
    area, projection, baseline = protected
    contract, images, certificate = parameter_fixture()
    projection = module.bridge.project_workload_phase(
        source_facts(contract), contract, images, certificate
    )
    source = {
        "source": asdict(projection.source),
        "request": {"target_environment": "test", "command": "up"},
    }
    calls = []
    transport = module.ServiceTransport.__new__(module.ServiceTransport)
    transport.repo = area
    transport.environment = {"PULUMI_PYTHON_CMD": "installed-python"}
    transport.before_program = lambda: calls.append("before-program")
    monkeypatch.setattr(
        module.ServiceTransport,
        "bind",
        lambda self, context: replace(context, runner=self),
    )
    monkeypatch.setenv("GITHUB_SHA", projection.source.base_sha)
    monkeypatch.setattr(module.registry, "_trusted_root", lambda: calls.append("root"))
    monkeypatch.setattr(
        module.registry.artifact,
        "load_verified_contract",
        lambda **_: (source, projection.contract),
    )
    monkeypatch.setattr(module.registry, "_review", lambda _: calls.append("review"))
    monkeypatch.setattr(
        module.admission, "authority_from_environment", lambda _: "installed-authority"
    )
    capture = SimpleNamespace(summary=registry_tests.summary(), resources=[])
    observation = module.admission.WorkloadObservation(
        module.admission.RegistryAnchor(None, {}, module._checkpoint(capture)),
        copy.deepcopy(projection.images),
        copy.deepcopy(projection.certificate),
    )
    monkeypatch.setattr(
        module.admission, "observe_workload", lambda *_: copy.deepcopy(observation)
    )
    monkeypatch.setattr(module.registry, "_capture", lambda *_: capture)
    monkeypatch.setattr(
        module.registry.preflight,
        "revalidate_requester",
        lambda _: calls.append("actor"),
    )

    @contextmanager
    def config(context, stack, *, workload_config):
        assert stack == "test"
        assert workload_config == module.bridge.workload_configuration(projection)
        path = area / "baseline.json"
        path.write_bytes(baseline)
        yield replace(context, config_file=path)

    monkeypatch.setattr(module.configuration, "prepared_stack_configuration", config)
    return SimpleNamespace(
        area=area,
        projection=projection,
        source=source,
        capture=capture,
        observation=observation,
        transport=transport,
        calls=calls,
    )


def execute(driver, command="plan"):
    return module.execute(
        command,
        artifact_id="123",
        archive_sha256="a" * 64,
        source_sha256="b" * 64,
        transport=driver.transport,
    )


def dispatch(driver, monkeypatch, *, gate=True):
    def run(command, context, stacks):
        assert command in ("plan", "up-plan") and stacks == ["test"]
        assert context.pulumi_dir == driver.area / "workload"
        assert driver.transport.environment["PULUMI_PYTHON_CMD"] == str(
            context.pulumi_dir / "python"
        )
        assert context.execution_identity["kind"] == "poc-workload-execution/v1"
        assert len(context.execution_identity["generatedFilesSha256"]) == 64
        assert context.config_file is None and context.provider_identity is None
        driver.transport.before_program()
        plan, preview = driver.area / "plan", driver.area / "preview"
        plan.write_text("{}")
        preview.write_text("{}")
        driver.calls.append(context)
        if gate:
            context.registry_plan_gate(
                replace(context, provider_identity=registry_tests.identity()),
                "test",
                plan,
                preview,
            )
        return 0

    monkeypatch.setattr(module.registry.runner, "_dispatch_command", run)


def test_generated_projection_and_wrapper_reach_existing_dispatch(driver, monkeypatch):
    # Only this isolated plumbing test replaces the rejecting semantic gate.
    monkeypatch.setattr(
        module.topology, "admit_first_workload_plan", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    assert execute(driver) == 0
    assert driver.transport.environment["PULUMI_PYTHON_CMD"] == "installed-python"
    driver.transport.before_program()
    assert driver.calls[-1] == "before-program"
    assert "actor" in driver.calls


@pytest.mark.parametrize("command", ["plan", "up-plan"])
def test_real_admission_stop_survives_adapter(driver, monkeypatch, command):
    monkeypatch.setattr(
        module.topology, "validate_first_workload_topology", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    with pytest.raises(
        ValueError, match="native-capability-and-input-admission-required"
    ):
        execute(driver, command)
    assert driver.transport.environment["PULUMI_PYTHON_CMD"] == "installed-python"


def test_replay_still_requires_result_observer_if_topology_gate_later_opens(
    driver, monkeypatch
):
    monkeypatch.setattr(
        module.topology, "admit_first_workload_plan", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    with pytest.raises(ValueError, match="workload-result-observer-required"):
        execute(driver, "up-plan")


@pytest.mark.parametrize(
    "mutation",
    ["observations", "certificate", "checkpoint", "plan", "preview", "stack"],
)
def test_gate_rechecks_evidence_and_artifact_bytes(driver, monkeypatch, mutation):
    dispatch(driver, monkeypatch, gate=False)
    assert execute(driver) == 0
    context = driver.calls[-1]
    plan, preview = driver.area / "plan", driver.area / "preview"

    def topology(*args, **kwargs):
        if mutation in ("plan", "preview"):
            (plan if mutation == "plan" else preview).write_text('{"changed":true}')

    monkeypatch.setattr(module.topology, "admit_first_workload_plan", topology)
    if mutation == "observations":
        driver.observation.images["web"]["config_digest"] = "changed"
    if mutation == "certificate":
        driver.observation.certificate["parameter_version"] += 1
    if mutation == "checkpoint":
        driver.capture.summary["state"]["VersionId"] = "changed"
    with pytest.raises(ValueError, match="workload-"):
        context.registry_plan_gate(
            replace(context, provider_identity=registry_tests.identity()),
            "prod" if mutation == "stack" else "test",
            plan,
            preview,
        )


@pytest.mark.parametrize("field", ["target_environment", "base_sha", "command"])
def test_request_binding_rejects_before_materialization(driver, field):
    target = driver.source["source" if field == "base_sha" else "request"]
    target[field] = "foreign"
    with pytest.raises(ValueError, match="workload-request-binding"):
        execute(driver, "up-plan")
    assert not (driver.area / "workload").exists()


@pytest.mark.parametrize(
    "command,error",
    [
        ("destroy", "workload-command"),
        ("drift", "accepted-state-receipt"),
        ("plan", "isolated-transport"),
    ],
)
def test_unsupported_routes_fail_before_any_observation(command, error):
    with pytest.raises(ValueError, match=error):
        module.execute(
            command,
            artifact_id="1",
            archive_sha256="a",
            source_sha256="b",
            transport=None,
        )


def test_generated_identity_is_in_manifest_and_mismatch_stops_replay(
    driver, monkeypatch
):
    dispatch(driver, monkeypatch, gate=False)
    execute(driver)
    context = driver.calls[-1]
    plan, preview = driver.area / "plan", driver.area / "preview"
    entry = module.registry.runner._plan_manifest_entry(context, "test", plan, preview)
    assert entry["executionIdentity"] == context.execution_identity
    for identity in (
        None,
        {**context.execution_identity, "projectionSha256": "changed"},
    ):
        changed = {**entry, "executionIdentity": identity}
        with pytest.raises(ValueError, match="execution identity changed"):
            module.registry.runner._replay_prepared_plan(
                context, {"stacks": [changed]}, "test", plan
            )
    # A workload manifest also cannot be replayed through an ordinary context.
    with pytest.raises(ValueError, match="execution identity changed"):
        module.registry.runner._replay_prepared_plan(
            replace(context, execution_identity=None), {"stacks": [entry]}, "test", plan
        )


def test_missing_protected_config_rejects(driver, monkeypatch):
    @contextmanager
    def missing(context, *_args, **_kwargs):
        yield context

    monkeypatch.setattr(module.configuration, "prepared_stack_configuration", missing)
    with pytest.raises(ValueError, match="protected-config-required"):
        execute(driver)


def test_production_runner_requires_parameter_and_cannot_use_copied_arn(driver):
    domain = driver.projection.contract["workload"]["external"]["domain"]
    domain["certificate_arn"] = driver.projection.certificate["certificate_arn"]
    domain.pop("certificate_parameter_name")
    with pytest.raises(ValueError, match="certificate-parameter-required"):
        execute(driver)


def test_matching_execution_identity_retains_provider_gate_and_replay_order(
    driver, monkeypatch
):
    dispatch(driver, monkeypatch, gate=False)
    execute(driver)
    context = driver.calls[-1]
    plan, preview = driver.area / "plan", driver.area / "preview"
    entry = module.registry.runner._plan_manifest_entry(context, "test", plan, preview)
    calls = []
    monkeypatch.setattr(
        module.registry.runner,
        "verify_provider_identity",
        lambda *_: calls.append("provider"),
    )
    monkeypatch.setattr(
        module.registry.runner,
        "_run_up_plan_stack",
        lambda *_: calls.append("replay"),
    )
    context = replace(context, registry_plan_gate=lambda *_: calls.append("gate"))
    assert (
        module.registry.runner._replay_prepared_plan(
            context, {"stacks": [entry]}, "test", plan
        )
        is None
    )
    assert calls == ["provider", "gate", "replay"]


def test_before_program_rechecks_materialized_bytes_and_restores_transport(
    driver, monkeypatch
):
    def corrupt(_command, context, _stacks):
        path = context.pulumi_dir / "__main__.py"
        path.chmod(0o600)
        path.write_bytes(b"X" * path.stat().st_size)
        path.chmod(0o440)
        driver.transport.before_program()

    monkeypatch.setattr(module.registry.runner, "_dispatch_command", corrupt)
    with pytest.raises(ValueError, match="workload-materializer-readback"):
        execute(driver)
    assert driver.transport.environment["PULUMI_PYTHON_CMD"] == "installed-python"
