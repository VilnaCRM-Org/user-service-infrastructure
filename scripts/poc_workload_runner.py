"""Sealed first-workload plan and first-apply adapter; later releases stay closed.

Authenticated registry, release, image and native prerequisite observations feed
only the installed generated program. The exact first-workload topology admits
the saved plan. A successful first apply must pass private checkpoint and native
secret-metadata readback; it issues no cross-run receipt. Drift and subsequent
releases require an authenticated accepted-workload receipt.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone

import _pulumi_stack_config as configuration
import poc_contract
import poc_registry_runner as registry
import poc_workload_admission as admission
import poc_workload_materializer as materializer
import poc_workload_phase_entrypoint as bridge
import poc_workload_secret_result as secret_result
import poc_workload_topology as topology
from poc_phase_admission import CONTRACT_PATH, SourceAdmission
from poc_registry_phase_entrypoint import RegistryPhaseProjection
from service_execution_process import require
from service_execution_transport import ServiceTransport

# FR-24 (N-04) gate-2 bounds, each 300 s below its limit: the 3300 s apply
# process bound and the 3600 s default STS session.
PROCESS_BUDGET_SECONDS = 3000
CREDENTIAL_WINDOW_SECONDS = 3300
TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"

# self-deploy.yml: the only job that ever reaches _oidc_issued_at (test_apply /
# "up-plan") and the OIDC credential step inside it, matched by exact name.
OIDC_JOB_KEY = "test_apply"
OIDC_JOB_NAME = "Test Apply"
OIDC_STEP_NAME = "Configure AWS apply credentials via OIDC"


def _now():
    return datetime.now(timezone.utc).strftime(TIMESTAMP)


def _fail():
    """Close every OIDC-issuance gate below onto one caught exception type."""
    raise RuntimeError


def _oidc_run_jobs():
    """Fetch this run attempt's complete Jobs API listing (own repo, paginated)."""
    run_id = os.environ["GITHUB_RUN_ID"]
    attempt = os.environ["GITHUB_RUN_ATTEMPT"]
    if not (
        re.fullmatch(r"[1-9][0-9]*", run_id) and re.fullmatch(r"[1-9][0-9]*", attempt)
    ):
        _fail()
    endpoint = (
        f"{admission.artifacts.API}/actions/runs/{run_id}"
        f"/attempts/{attempt}/jobs?per_page=100"
    )
    pages = admission._github(endpoint, "--paginate", "--slurp")
    rows = [job for page in pages for job in page["jobs"]]
    # Every page reports the attempt's total; a short listing is incomplete.
    if {page["total_count"] for page in pages} != {len(rows)}:
        _fail()
    return rows


def _oidc_matching_job(rows):
    """Require exactly one ``Test Apply`` job row, from this very run attempt."""
    matches = [job for job in rows if job.get("name") == OIDC_JOB_NAME]
    if len(matches) != 1:
        _fail()
    job = matches[0]
    run = (str(job.get("run_id")), str(job.get("run_attempt")))
    if run != (os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]):
        _fail()
    return job


def _oidc_credential_step(job):
    """Require exactly one completed, successful OIDC credential step."""
    steps = job["steps"]
    if type(steps) is not list:
        _fail()
    found = [step for step in steps if step.get("name") == OIDC_STEP_NAME]
    if len(found) != 1:
        _fail()
    step = found[0]
    if not (step.get("status") == "completed" and step.get("conclusion") == "success"):
        _fail()
    return step


def _oidc_step_started_at(step):
    """Normalize the step's own ``started_at`` (never ``completed_at``) to UTC."""
    started = step["started_at"]
    if type(started) is not str:
        _fail()
    parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        _fail()
    return parsed.astimezone(timezone.utc).strftime(TIMESTAMP)


def _oidc_issued_at():
    """Read the OIDC apply-credential step's own ``started_at`` (FR-24 gate 2).

    The source is this run attempt's own Jobs API
    (``GET .../actions/runs/{id}/attempts/{n}/jobs``), fetched with the GitHub
    token and run identifiers the host already forwards into the worker, using
    the same paginated ``gh api --paginate --slurp`` idiom
    ``poc_workload_admission._publisher_jobs`` uses for the publisher run. The
    ``Test Apply`` job (``GITHUB_JOB == "test_apply"``, the only job that ever
    calls this) must appear exactly once in a complete listing, carry this
    run's id and attempt, and its
    ``Configure AWS apply credentials via OIDC`` step (self-deploy.yml) must
    appear exactly once, completed successfully. ``started_at`` is used, not
    ``completed_at``, as a conservative lower bound on credential issuance.

    Any failure -- the API call failing, incomplete pagination, a missing or
    ambiguous job or step, a step that has not completed successfully, or an
    unparseable timestamp -- fails closed with one stable reason before any
    mutation; this runs before the Pulumi dispatch in ``execute``.
    """
    try:
        if os.environ.get("GITHUB_JOB") != OIDC_JOB_KEY:
            _fail()
        rows = _oidc_run_jobs()
        job = _oidc_matching_job(rows)
        step = _oidc_credential_step(job)
        return _oidc_step_started_at(step)
    except Exception:
        raise ValueError("timing-oidc-issuance") from None


def _record_timing(started, oidc_issued_at):
    """Print the runner's first-create timestamps to the job log (AD-17).

    ``runner_started_at`` to ``observation_ended_at`` is the measured process
    time; ``oidc_issued_at`` (the apply credentials' own OIDC step
    ``started_at``, read by ``_oidc_issued_at`` before any mutation) is the
    start of the credential window. ``timing_within_budget`` checks the record.
    """
    record = {
        "kind": "poc-workload-timing/v1",
        "oidc_issued_at": oidc_issued_at,
        "runner_started_at": started,
        "observation_ended_at": _now(),
    }
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    os.write(2, f"Trusted worker timing: {line}\n".encode())


def _seconds(evidence, key):
    value = evidence.get(key)
    require(type(value) is str, "timing-evidence-field")
    try:
        parsed = datetime.strptime(value, TIMESTAMP)
    except ValueError:
        raise ValueError("timing-evidence-field") from None
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def timing_within_budget(evidence):
    """FR-24 gate-2 check for one measured first-create step.

    Process time runs from the runner start to the result observation; the
    credential window runs from the OIDC issuance to the same observation.
    Gate 2 needs process <= 3000 s and window <= 3300 s, else S5.6 lands first.
    """
    issued = _seconds(evidence, "oidc_issued_at")
    started = _seconds(evidence, "runner_started_at")
    observed = _seconds(evidence, "observation_ended_at")
    require(issued <= started <= observed, "timing-evidence-order")
    return (
        observed - started <= PROCESS_BUDGET_SECONDS
        and observed - issued <= CREDENTIAL_WINDOW_SECONDS
    )


def _installed_admission(stack, command):
    """Runtime guard (FR-23, #57): only installed ``main`` admits an environment.

    The PR-head contract never decides. The guard reads ``admission.<stack>``
    from the contract at the authenticated ``main`` commit of this run; a
    missing, unreadable or non-admitting value refuses ``plan`` and ``up-plan``.
    ``"preview"`` admits only a PROD ``plan`` (gate 2a); ``true`` admits both.
    """
    try:
        raw = registry._git("show", f"{os.environ['GITHUB_SHA']}:{CONTRACT_PATH}")
        require(0 < len(raw) <= poc_contract.MAX_BYTES, "workload-runtime-admission")
        contract = json.loads(
            raw,
            object_pairs_hook=poc_contract._pairs,
            parse_constant=poc_contract._reject_nonfinite,
        )
        value = contract["admission"][stack]
    except Exception:
        raise ValueError("workload-runtime-admission") from None
    require(
        value is True or (stack == "prod" and value == "preview" and command == "plan"),
        "workload-runtime-admission",
    )


def _checkpoint(capture):
    state = capture.summary["state"]
    return {
        "version": state["VersionId"],
        "etag": state["ETag"],
        "sha256": state["sha256"],
    }


def _capture(source, command, observation):
    capture = registry._capture(
        source, command, RegistryPhaseProjection(registry.graph.REGISTRIES)
    )
    require(
        _checkpoint(capture) == observation.anchor.checkpoint,
        "workload-checkpoint-binding",
    )
    return capture


def _gate(source, contract, authority, command, projection, initial):
    def validate(context, stack, plan_path, preview_path):
        require(stack == "test", "workload-stack")
        registry._review(source)
        current = admission.observe_workload(source, contract, authority, command)
        require(current == initial, "workload-observations-changed")
        capture = _capture(source, command, current)
        registry._binding(context, capture)
        plan_raw, plan = registry._read_plan(plan_path)
        preview_raw, preview = registry._read_plan(preview_path)
        topology.admit_first_workload_plan(
            preview,
            saved_plan=plan,
            prior_resources=capture.resources,
            projection=projection,
        )
        require(
            plan_path.read_bytes() == plan_raw
            and preview_path.read_bytes() == preview_raw,
            "workload-plan-bytes-changed",
        )
        registry.preflight.revalidate_requester(source["request"])
        require(command in ("plan", "up-plan"), "workload-first-command")

    return validate


@contextmanager
def _prepared_workload(context, transport, projection):
    """Bind provider state before generation, then recheck it inside plan/replay."""
    with configuration.prepared_stack_configuration(
        context, "test", workload_config=bridge.workload_configuration(projection)
    ) as prepared:
        if prepared.config_file is None:
            raise ValueError("workload-protected-config-required")
        document = configuration.yaml.load(
            prepared.config_file.read_bytes(), Loader=configuration._StackConfigLoader
        )
        baseline = materializer._canonical(document)
        generated = materializer.materialize_workload(
            transport.repo, projection, baseline
        )
        identity = {
            "kind": "poc-workload-execution/v1",
            "projectionSha256": generated.projection_sha256,
            "baselineConfigSha256": generated.baseline_sha256,
            "generatedFilesSha256": hashlib.sha256(
                json.dumps(generated.files, separators=(",", ":")).encode()
            ).hexdigest(),
        }
        previous_python = transport.environment["PULUMI_PYTHON_CMD"]
        previous_admission = transport.before_program

        def before_program():
            previous_admission()
            materializer.verify_materialized_workload(generated, projection, baseline)

        transport.environment["PULUMI_PYTHON_CMD"] = str(generated.python_command)
        transport.before_program = before_program
        try:
            materializer.verify_materialized_workload(generated, projection, baseline)
            yield replace(
                context,
                pulumi_dir=generated.directory,
                config_file=None,
                provider_identity=None,
                execution_identity=identity,
            )
        finally:
            transport.environment["PULUMI_PYTHON_CMD"] = previous_python
            transport.before_program = previous_admission


def _event_logged(transport):
    """Give every preview/up child a private engine event log (FR-20).

    The log lands in the transport's root-owned output area, which the
    isolated UID can write, and only the worker's allow-listed diagnostics
    read it. It never reaches ``/public`` or the job output.
    """
    sequence = itertools.count(1)

    def runner(command, **kwargs):
        if command[0] == "pulumi" and command[3:4] in (["preview"], ["up"]):
            path = transport.outputs / f"events-{next(sequence):04d}.jsonl"
            command = [*command, "--event-log", str(path)]
        return transport(command, **kwargs)

    return runner


def _inspect_first_result(source, contract, prior, projection):
    """Require a complete stable first-create checkpoint and native secret metadata.

    Resolved task definitions are validated here because admission sees them as
    unknown; a hardening deviation fails the run after apply, never before it.
    This is same-run TEST apply evidence, not a receipt for later release or drift.
    Native application behavior and resolved gateway relationships still require
    live acceptance before the PoC is considered deployed.
    """
    os.write(2, b"Trusted worker stage: workload result observation\n")
    final = registry.backend.capture_backend(source, operation="up-plan")
    require(
        final.summary["state"]["kind"] == "observed_checkpoint"
        and _checkpoint(final) != _checkpoint(prior),
        "workload-first-result-checkpoint",
    )
    secrets = secret_result.inspect_first_secret_history(
        contract, prior.resources, final.resources
    )
    topology.inspect_first_task_definitions(final.resources, projection, secrets)
    repeat = registry.backend.capture_backend(source, operation="up-plan")
    require(
        repeat.summary["state"] == final.summary["state"]
        and repeat.resources == final.resources,
        "workload-first-result-moved",
    )
    registry._review(source)
    registry.preflight.revalidate_requester(source["request"])


def execute(command, *, artifact_id, archive_sha256, source_sha256, transport):
    """Authenticate and materialize the fixed TEST graph; never accept PR code."""
    require(command in ("plan", "up-plan", "drift"), "workload-command")
    require(command != "drift", "workload-accepted-state-receipt-required")
    started = _now()
    require(type(transport) is ServiceTransport, "workload-isolated-transport-required")
    materializer._worker()
    registry._trusted_root()
    _installed_admission("test", command)
    source, contract = registry.artifact.load_verified_contract(
        artifact_id=artifact_id,
        archive_sha256=archive_sha256,
        source_sha256=source_sha256,
    )
    require(
        source["request"]["target_environment"] == "test"
        and source["source"]["base_sha"] == os.environ["GITHUB_SHA"]
        and (command == "plan" or source["request"]["command"] == "up"),
        "workload-request-binding",
    )
    registry._review(source)
    domain = contract["workload"]["external"]["domain"]
    require(
        domain.get("certificate_parameter_name")
        == admission.capabilities.CERTIFICATE_PARAMETER_NAME
        and "certificate_arn" not in domain,
        "workload-certificate-parameter-required",
    )
    authority = admission.authority_from_environment(os.environ)
    initial = admission.observe_workload(source, contract, authority, command)
    projection = bridge.project_workload_phase(
        SourceAdmission(**source["source"]),
        contract,
        initial.images,
        initial.certificate,
    )
    prior = _capture(source, command, initial)
    root = transport.repo
    context = registry.runner.CommandContext(
        root_dir=root,
        env={"PULUMI_COMMIT_SHA": source["source"]["head_sha"]},
        pulumi_dir=registry.ROOT / "pulumi",
        policy_pack_dir=registry.ROOT / "policy",
        plan_dir=root / ".artifacts/pulumi-plan",
        preview_artifact_dir=root / ".artifacts/pulumi-preview",
        backend_url=f"s3://{registry.backend.BUCKET}",
        secrets_provider=registry.backend.PROVIDER,
        registry_plan_gate=_gate(
            source, contract, authority, command, projection, initial
        ),
    )
    context = transport.bind(context)
    context = replace(context, runner=_event_logged(transport))
    # Read before any mutation: the real apply happens in the dispatch below.
    oidc_issued_at = _oidc_issued_at() if command == "up-plan" else None
    with _prepared_workload(context, transport, projection) as prepared:
        status = registry.runner._dispatch_command(command, prepared, ["test"])
        if status == 0 and command == "up-plan":
            _inspect_first_result(source, contract, prior, projection)
            _record_timing(started, oidc_issued_at)
        return status
