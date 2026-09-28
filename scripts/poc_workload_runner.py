"""Sealed first-workload plan and first-apply adapter; later releases stay closed.

Authenticated registry, release, image and native prerequisite observations feed
only the installed generated program. The exact first-workload topology admits
the saved plan. A successful first apply must pass private checkpoint and native
secret-metadata readback; it issues no cross-run receipt. Drift and subsequent
releases require an authenticated accepted-workload receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import replace

import _pulumi_stack_config as configuration
import poc_registry_runner as registry
import poc_workload_admission as admission
import poc_workload_materializer as materializer
import poc_workload_phase_entrypoint as bridge
import poc_workload_secret_result as secret_result
import poc_workload_topology as topology
from poc_phase_admission import SourceAdmission
from poc_registry_phase_entrypoint import RegistryPhaseProjection
from service_execution_process import require
from service_execution_transport import ServiceTransport


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


def _inspect_first_result(source, contract, prior):
    """Require a complete stable first-create checkpoint and native secret metadata.

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
    secret_result.inspect_first_secret_history(
        contract, prior.resources, final.resources
    )
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
    require(type(transport) is ServiceTransport, "workload-isolated-transport-required")
    materializer._worker()
    registry._trusted_root()
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
    with _prepared_workload(context, transport, projection) as prepared:
        status = registry.runner._dispatch_command(command, prepared, ["test"])
        if status == 0 and command == "up-plan":
            _inspect_first_result(source, contract, prior)
        return status
