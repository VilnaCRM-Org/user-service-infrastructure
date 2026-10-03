"""Exercise sealed plumbing with synthetic observations; no admission is granted."""

import copy
import importlib
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_poc_registry_runner as registry_tests
import yaml
from test_poc_registry_phase_entrypoint import source as source_facts
from test_poc_workload_materializer import protected as protected
from test_poc_workload_phase_entrypoint import parameter_fixture

module = importlib.import_module("poc_workload_runner")
ROOT = Path(__file__).resolve().parents[2]


# FR-31 gate-1 admission record, as committed on the installed ``main``.
ADMITTED_MAIN = b'{"phase": "workload", "admission": {"test": true, "prod": false}}'


def installed_main(monkeypatch, sha, raw):
    """Serve ``git show <main sha>:specs/poc/poc-test.json`` from fixed bytes."""

    def git(*arguments):
        assert arguments == ("show", f"{sha}:specs/poc/poc-test.json")
        if raw is None:
            raise ValueError("Registry execution precondition failed")
        return raw

    monkeypatch.setattr(module.registry, "_git", git)


# S4.5 F1 (FR-24 / AD-17): synthetic Jobs-API fixtures for ``_oidc_issued_at``.
OIDC_RUN_ID = "555"
OIDC_RUN_ATTEMPT = "1"
OIDC_STARTED_AT = "2026-10-01T10:00:00Z"


def oidc_env(monkeypatch):
    """Set the run identifiers ``_oidc_issued_at`` reads from the environment."""
    monkeypatch.setenv("GITHUB_JOB", module.OIDC_JOB_KEY)
    monkeypatch.setenv("GITHUB_RUN_ID", OIDC_RUN_ID)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", OIDC_RUN_ATTEMPT)


def oidc_step(**overrides):
    step = {
        "name": module.OIDC_STEP_NAME,
        "status": "completed",
        "conclusion": "success",
        "started_at": OIDC_STARTED_AT,
    }
    step.update(overrides)
    return step


def oidc_job(steps, *, name=None, run_id=555, run_attempt=1):
    return {
        "name": name or module.OIDC_JOB_NAME,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "steps": steps,
    }


def oidc_pages(jobs):
    """One Jobs-API page, in the ``admission._github(..., "--slurp")`` page shape."""
    return [{"total_count": len(jobs), "jobs": jobs}]


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
    # S4.5 F1: a default working OIDC-issuance evidence source for every
    # up-plan-reaching test that does not itself exercise that evidence.
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job([oidc_step()])]),
    )
    monkeypatch.setattr(module.registry, "_trusted_root", lambda: calls.append("root"))
    installed_main(monkeypatch, projection.source.base_sha, ADMITTED_MAIN)
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
def test_first_saved_plan_gate_runs_and_apply_checks_result(
    driver, monkeypatch, command
):
    observed = []
    monkeypatch.setattr(
        module,
        "_inspect_first_result",
        lambda source, contract, prior, projection: observed.append(
            (source, contract, prior, projection)
        ),
    )
    monkeypatch.setattr(
        module.topology, "validate_first_workload_topology", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    assert execute(driver, command) == 0
    assert len(observed) == (1 if command == "up-plan" else 0)
    if observed:
        assert observed[0][2] is driver.capture
        assert observed[0][3] == driver.projection
    assert driver.transport.environment["PULUMI_PYTHON_CMD"] == "installed-python"


def test_failed_result_observation_stops_first_apply_success(driver, monkeypatch):
    def reject(*_):
        raise ValueError("workload-result-invalid")

    monkeypatch.setattr(module, "_inspect_first_result", reject)
    monkeypatch.setattr(
        module.topology, "admit_first_workload_plan", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    with pytest.raises(ValueError, match="workload-result-invalid"):
        execute(driver, "up-plan")


def test_first_result_binds_changed_stable_checkpoint_and_secret_readback(
    driver, monkeypatch
):
    final = copy.deepcopy(driver.capture)
    final.summary["state"]["VersionId"] = "new-version"
    final.resources = [{"urn": "synthetic-workload"}]
    reads = iter((final, copy.deepcopy(final)))
    monkeypatch.setattr(
        module.registry.backend,
        "capture_backend",
        lambda *_a, **_k: next(reads),
    )
    observed = []
    monkeypatch.setattr(
        module.secret_result,
        "inspect_first_secret_history",
        lambda contract, before, after: (
            observed.append((contract, before, after)) or "secret-metadata"
        ),
    )
    monkeypatch.setattr(
        module.topology,
        "inspect_first_task_definitions",
        lambda *args: observed.append(args),
    )
    module._inspect_first_result(
        driver.source, driver.projection.contract, driver.capture, driver.projection
    )
    assert observed == [
        (driver.projection.contract, driver.capture.resources, final.resources),
        (final.resources, driver.projection, "secret-metadata"),
    ]
    assert driver.calls[-2:] == ["review", "actor"]


@pytest.mark.parametrize("fault", ["unchanged", "moved", "secret", "containers"])
def test_first_result_rejects_missing_or_unstable_evidence(driver, monkeypatch, fault):
    final = copy.deepcopy(driver.capture)
    final.summary["state"]["VersionId"] = "new-version"
    repeated = copy.deepcopy(final)
    if fault == "unchanged":
        final.summary["state"]["VersionId"] = "original"
    if fault == "moved":
        repeated.summary["state"]["VersionId"] = "other-version"
    reads = iter((final, repeated))
    monkeypatch.setattr(
        module.registry.backend,
        "capture_backend",
        lambda *_a, **_k: next(reads),
    )

    def secrets(*_):
        if fault == "secret":
            raise ValueError("workload-secret-result")

    def containers(*_):
        if fault == "containers":
            raise ValueError("workload-task-container-runtime")

    monkeypatch.setattr(module.secret_result, "inspect_first_secret_history", secrets)
    monkeypatch.setattr(module.topology, "inspect_first_task_definitions", containers)
    with pytest.raises(ValueError, match="workload-"):
        module._inspect_first_result(
            driver.source, driver.projection.contract, driver.capture, driver.projection
        )


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


def test_preview_and_up_children_get_a_private_event_log(tmp_path):
    """FR-20: only engine runs write an event log, into the private output area."""
    calls = []

    class Transport:
        outputs = tmp_path

        def __call__(self, command, **kwargs):
            calls.append((command, kwargs))
            return "result"

    runner = module._event_logged(Transport())
    for verb in ("preview", "up", "stack"):
        assert runner(["pulumi", "-C", "/p", verb], env={}) == "result"
    assert runner(["aws", "sts", "get-caller-identity"], env={}) == "result"
    assert calls == [
        (
            [
                "pulumi",
                "-C",
                "/p",
                "preview",
                "--event-log",
                str(tmp_path / "events-0001.jsonl"),
            ],
            {"env": {}},
        ),
        (
            [
                "pulumi",
                "-C",
                "/p",
                "up",
                "--event-log",
                str(tmp_path / "events-0002.jsonl"),
            ],
            {"env": {}},
        ),
        (["pulumi", "-C", "/p", "stack"], {"env": {}}),
        (["aws", "sts", "get-caller-identity"], {"env": {}}),
    ]


def test_installed_main_admission_allows_workload_execution(driver, monkeypatch):
    """FR-23 P: installed main admits TEST, so the saved-plan dispatch runs."""
    monkeypatch.setattr(
        module.topology, "admit_first_workload_plan", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    assert execute(driver, "plan") == 0
    assert driver.calls[:2] == ["root", "review"]


@pytest.mark.parametrize(
    "main",
    [
        b'{"phase": "workload", "admission": {"test": false, "prod": false}}',
        b'{"phase": "registry"}',
        b'{"phase": "workload", "admission": {"test": "true", "prod": false}}',
        b'{"phase": "workload", "admission": ["test"]}',
        b"not json",
        b"",
    ],
)
@pytest.mark.parametrize("command", ["plan", "up-plan"])
def test_pr_head_admission_without_main_admission_is_refused(
    driver, monkeypatch, main, command
):
    """FR-23 N: the PR head admits TEST, installed main does not: refused."""
    head = {**driver.projection.contract, "admission": {"test": True, "prod": True}}
    monkeypatch.setattr(
        module.registry.artifact,
        "load_verified_contract",
        lambda **_: (driver.source, head),
    )
    installed_main(monkeypatch, driver.projection.source.base_sha, main)
    monkeypatch.setattr(
        module.admission,
        "observe_workload",
        lambda *_: pytest.fail("observed after a refused runtime admission"),
    )
    with pytest.raises(ValueError, match="^workload-runtime-admission$"):
        execute(driver, command)
    assert driver.calls == ["root"]


def test_missing_installed_contract_is_refused(driver, monkeypatch):
    """FR-23 B: no contract at the installed main commit refuses execution."""
    installed_main(monkeypatch, driver.projection.source.base_sha, None)
    with pytest.raises(ValueError, match="^workload-runtime-admission$"):
        execute(driver, "plan")
    monkeypatch.delenv("GITHUB_SHA")
    with pytest.raises(ValueError, match="^workload-runtime-admission$"):
        module._installed_admission("test", "plan")


@pytest.mark.parametrize(
    ("value", "command", "admitted"),
    [
        (True, "plan", True),
        (True, "up-plan", True),
        ("preview", "plan", True),
        ("preview", "up-plan", False),
        (False, "plan", False),
    ],
)
def test_prod_preview_admits_only_plan(monkeypatch, value, command, admitted):
    """FR-31 gate 2a: ``admission.prod: "preview"`` admits only the PROD plan."""
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    raw = module.json.dumps({"admission": {"test": True, "prod": value}}).encode()
    installed_main(monkeypatch, "c" * 40, raw)
    if admitted:
        module._installed_admission("prod", command)
    else:
        with pytest.raises(ValueError, match="^workload-runtime-admission$"):
            module._installed_admission("prod", command)


def test_preview_value_never_admits_test(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    installed_main(
        monkeypatch, "c" * 40, b'{"admission": {"test": "preview", "prod": false}}'
    )
    with pytest.raises(ValueError, match="^workload-runtime-admission$"):
        module._installed_admission("test", "plan")


@pytest.mark.parametrize("command", ["plan", "up-plan"])
def test_first_create_apply_records_runner_timing(driver, monkeypatch, capfd, command):
    """FR-24 / AD-17: an observed first create prints its runner timestamps."""
    stamps = iter(("2026-10-01T10:05:00Z", "2026-10-01T10:45:00Z"))
    monkeypatch.setattr(module, "_now", lambda: next(stamps))
    monkeypatch.setattr(module, "_inspect_first_result", lambda *_: None)
    monkeypatch.setattr(
        module.topology, "admit_first_workload_plan", lambda *a, **k: None
    )
    dispatch(driver, monkeypatch)
    assert execute(driver, command) == 0
    timing = (
        "Trusted worker timing: "
        '{"kind":"poc-workload-timing/v1",'
        '"observation_ended_at":"2026-10-01T10:45:00Z",'
        '"oidc_issued_at":"2026-10-01T10:00:00Z",'
        '"runner_started_at":"2026-10-01T10:05:00Z"}\n'
    )
    output = capfd.readouterr().err
    assert (timing in output) == (command == "up-plan")
    if command == "up-plan":
        # (a) the emitted record, fed straight in, passes the FR-24 gate-2 check.
        record = module.json.loads(timing.removeprefix("Trusted worker timing: "))
        assert module.timing_within_budget(record) is True


def test_runner_clock_is_utc_seconds():
    import re

    assert re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", module._now())


def test_oidc_issuance_uses_step_started_at_not_completed_at(monkeypatch):
    """(c) ``oidc_issued_at`` comes from the step's ``started_at``, not its end."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages(
            [
                oidc_job(
                    [
                        oidc_step(
                            started_at="2026-10-01T09:50:00Z",
                            completed_at="2026-10-01T10:30:00Z",
                        )
                    ]
                )
            ]
        ),
    )
    assert module._oidc_issued_at() == "2026-10-01T09:50:00Z"


def test_oidc_issuance_reads_this_run_attempt_jobs_endpoint(monkeypatch):
    """F-03: the exact own-repo, per-attempt, paginated Jobs API call."""
    oidc_env(monkeypatch)
    calls = []
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *args: calls.append(args) or oidc_pages([oidc_job([oidc_step()])]),
    )
    assert module._oidc_issued_at() == "2026-10-01T10:00:00Z"
    assert calls == [
        (
            "repos/VilnaCRM-Org/user-service-infrastructure/actions/runs/555"
            "/attempts/1/jobs?per_page=100",
            "--paginate",
            "--slurp",
        )
    ]


@pytest.mark.parametrize("run", [{"run_id": 556}, {"run_attempt": 2}, {"run_id": None}])
def test_oidc_issuance_rejects_a_job_row_from_another_run(monkeypatch, run):
    """F-04: the job row must carry this run's id and attempt."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job([oidc_step()], **run)]),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_names_bind_to_the_self_deploy_workflow():
    """F-03: the job, its ``actions: read`` and the one OIDC step exist as named."""
    workflow = yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())
    job = workflow["jobs"][module.OIDC_JOB_KEY]
    assert job["name"] == "Test Apply" == module.OIDC_JOB_NAME
    assert job["permissions"]["actions"] == "read"
    names = [step.get("name") for step in job["steps"]]
    assert names.count("Configure AWS apply credentials via OIDC") == 1
    assert module.OIDC_STEP_NAME == "Configure AWS apply credentials via OIDC"
    oidc = names.index(module.OIDC_STEP_NAME)
    assert job["steps"][oidc]["uses"].startswith(
        "aws-actions/configure-aws-credentials@"
    )
    assert oidc < names.index("Apply saved test plan")


def test_oidc_issuance_rejects_job_key_mismatch(monkeypatch):
    oidc_env(monkeypatch)
    monkeypatch.setenv("GITHUB_JOB", "test_preview")
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


@pytest.mark.parametrize(
    ("run_id", "attempt"),
    [("0", "1"), ("01", "1"), ("abc", "1"), ("1", "0"), ("1", "abc"), ("1", "")],
)
def test_oidc_issuance_rejects_non_positive_integer_run_identifiers(
    monkeypatch, run_id, attempt
):
    oidc_env(monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ID", run_id)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", attempt)
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_missing_job(monkeypatch):
    """(b) the job is missing from the listing: refuse before any mutation."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(module.admission, "_github", lambda *_a, **_k: oidc_pages([]))
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_duplicate_job(monkeypatch):
    """(b) an ambiguous (duplicated) job in the listing refuses."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages(
            [oidc_job([oidc_step()]), oidc_job([oidc_step()])]
        ),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_non_list_steps(monkeypatch):
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job("not-a-list")]),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_missing_step(monkeypatch):
    """(b) the OIDC step is missing from the job: refuse before any mutation."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission, "_github", lambda *_a, **_k: oidc_pages([oidc_job([])])
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_duplicate_step(monkeypatch):
    """(b) a duplicated OIDC step in the job refuses."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job([oidc_step(), oidc_step()])]),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "in_progress", "conclusion": None},
        {"status": "completed", "conclusion": "failure"},
    ],
    ids=["unfinished-step", "failed-step"],
)
def test_oidc_issuance_rejects_step_not_successfully_completed(monkeypatch, overrides):
    """(b) an unfinished (or failed) OIDC step refuses before any mutation."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job([oidc_step(**overrides)])]),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_non_string_started_at(monkeypatch):
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job([oidc_step(started_at=None)])]),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


@pytest.mark.parametrize(
    "started_at",
    ["not-a-timestamp", "2026-10-01T10:00:00"],
    ids=["unparseable", "no-timezone"],
)
def test_oidc_issuance_rejects_unparseable_or_naive_started_at(monkeypatch, started_at):
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: oidc_pages([oidc_job([oidc_step(started_at=started_at)])]),
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_github_api_failure(monkeypatch):
    """(b) the GitHub API call itself failing refuses with the stable reason."""
    oidc_env(monkeypatch)

    def boom(*_a, **_k):
        raise ValueError("private-process-failed")

    monkeypatch.setattr(module.admission, "_github_bytes", boom)
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_incomplete_pagination(monkeypatch):
    """(b) an empty/incomplete paginated response refuses with the stable reason."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(module.admission, "_github_bytes", lambda *_a, **_k: b"")
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_rejects_a_short_page_listing(monkeypatch):
    """(b) a listing with fewer jobs than the reported total refuses."""
    oidc_env(monkeypatch)
    monkeypatch.setattr(
        module.admission,
        "_github",
        lambda *_a, **_k: [{"total_count": 2, "jobs": [oidc_job([oidc_step()])]}],
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        module._oidc_issued_at()


def test_oidc_issuance_failure_stops_up_plan_before_any_dispatch(driver, monkeypatch):
    """(b) a bad OIDC evidence refuses before the saved-plan mutation runs."""
    monkeypatch.setattr(module.admission, "_github", lambda *_a, **_k: oidc_pages([]))
    calls = []
    monkeypatch.setattr(
        module.registry.runner,
        "_dispatch_command",
        lambda *_a, **_k: calls.append(1) or 0,
    )
    with pytest.raises(ValueError, match="^timing-oidc-issuance$"):
        execute(driver, "up-plan")
    assert calls == []


def test_execute_gives_engine_children_the_private_event_log(driver, monkeypatch):
    """FR-20: production ``execute`` wires the event log into every engine run."""
    seen = []
    outputs = driver.area / "outputs"
    driver.transport.outputs = outputs
    monkeypatch.setattr(
        module.ServiceTransport,
        "__call__",
        lambda self, command, **kwargs: seen.append(command),
    )

    def run(command, context, stacks):
        context.runner(["pulumi", "-C", str(context.pulumi_dir), "preview"], env={})
        return 1

    monkeypatch.setattr(module.registry.runner, "_dispatch_command", run)
    assert execute(driver) == 1
    assert seen == [
        [
            "pulumi",
            "-C",
            str(driver.area / "workload"),
            "preview",
            "--event-log",
            str(outputs / "events-0001.jsonl"),
        ]
    ]
