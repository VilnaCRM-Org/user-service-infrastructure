#!/usr/bin/env python3
"""Diagnose TEST registry drift against installed main; never admit a transition.

This schedule-only path has no PR, artifact, requester, apply or initialization
inputs. A matching graph is diagnostic evidence, not accepted phase provenance.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402  # nosec B404
from dataclasses import dataclass  # noqa: E402

import poc_contract  # noqa: E402
import poc_registry_runner as runtime  # noqa: E402
from poc_phase_admission import CONTRACT_PATH, OWNER_ID, REPOSITORY_ID  # noqa: E402
from poc_registry_phase_entrypoint import (  # noqa: E402
    RegistryPhaseProjection,
    _stable_registries,
)
from poc_source_artifact import API, REPOSITORY, _matches, _pattern  # noqa: E402
from pulumi_command_preflight import gh  # noqa: E402

WORKFLOW = ".github/workflows/scheduled-drift.yml"
EXTRA_PATHS = ("specs", "schemas", WORKFLOW, ".github/actions/setup-poc-runtime")


@dataclass(frozen=True)
class ScheduledProvenance:
    """Native current-main observation authority, never PR source admission."""

    run_id: str
    sha: str


def _require(value):
    if not value:
        raise ValueError("Scheduled registry diagnostic precondition failed")


def _context():
    _matches(
        dict(os.environ),
        {
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(REPOSITORY_ID),
            "GITHUB_REPOSITORY_OWNER_ID": str(OWNER_ID),
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW_REF": f"{REPOSITORY}/{WORKFLOW}@refs/heads/main",
        },
    )
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    sha = os.environ.get("GITHUB_SHA", "")
    _pattern(run_id, r"[1-9][0-9]*")
    _pattern(sha, r"[0-9a-f]{40}")
    _require(os.environ.get("GITHUB_WORKFLOW_SHA") == sha)
    return ScheduledProvenance(run_id, sha)


def _repository(value):
    _matches(value, {"id": REPOSITORY_ID, "full_name": REPOSITORY})
    _matches(value.get("owner"), {"id": OWNER_ID})


def verify_provenance():
    """Authenticate the native run and still-current main before any AWS access."""
    provenance = _context()
    run = gh(f"{API}/actions/runs/{provenance.run_id}")
    _matches(
        run,
        {
            "id": int(provenance.run_id),
            "run_attempt": 1,
            "event": "schedule",
            "path": WORKFLOW,
            "head_branch": "main",
            "head_sha": provenance.sha,
            "status": "in_progress",
            "conclusion": None,
        },
    )
    _repository(run.get("repository"))
    _repository(run.get("head_repository"))
    repository = gh(API)
    _repository(repository)
    _matches(repository, {"default_branch": "main"})
    ref = gh(f"{API}/git/ref/heads/main")
    _matches(ref, {"ref": "refs/heads/main"})
    _matches(ref.get("object"), {"type": "commit", "sha": provenance.sha})
    runtime._verify_checkout(provenance.sha, extra_paths=EXTRA_PATHS)
    return provenance


def _installed_contract(provenance):
    """Project only fixed registry data from the authenticated installed commit."""
    raw = runtime._git("show", f"{provenance.sha}:{CONTRACT_PATH}")
    _require(0 < len(raw) <= poc_contract.MAX_BYTES)
    contract = json.loads(
        raw,
        object_pairs_hook=poc_contract._pairs,
        parse_constant=poc_contract._reject_nonfinite,
    )
    poc_contract._validate_document(contract)
    _require(contract["phase"] == "registry")
    projection = RegistryPhaseProjection(_stable_registries(contract["registries"]))
    canonical = json.dumps(
        contract, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest(), projection


def _capture(digest, projection):
    capture = runtime.backend.capture_scheduled_backend(digest)
    _require(capture.summary["state"]["kind"] == "observed_checkpoint")
    _require(len(capture.resources) == 7)
    runtime.graph._prior(capture.resources, runtime.graph._graph(projection))
    runtime._ecr_inventory(capture.resources)
    return capture


def _recheck(provenance):
    _require(verify_provenance() == provenance)


def _gate(provenance, digest, projection, initial):
    def validate(context, stack, plan_path, preview_path):
        _require(stack == "test")
        _recheck(provenance)
        plan_raw, plan = runtime._read_plan(plan_path)
        preview_raw, preview = runtime._read_plan(preview_path)
        current = _capture(digest, projection)
        _require(current.summary["state"] == initial.summary["state"])
        runtime._binding(context, current)
        # All seven resources already exist. The graph gate therefore permits
        # only same operations and empty input/output diffs, including provider.
        runtime.graph.validate(
            preview,
            saved_plan=plan,
            prior_resources=current.resources,
            projection=projection,
        )
        _require(
            plan_path.read_bytes() == plan_raw
            and preview_path.read_bytes() == preview_raw
        )
        _recheck(provenance)

    return validate


def execute():
    """Run a fresh fixed-program preview with no write or creation alternative."""
    provenance = verify_provenance()
    digest, projection = _installed_contract(provenance)
    initial = _capture(digest, projection)
    with runtime._project(projection) as project:
        context = runtime.runner.CommandContext(
            root_dir=runtime.ROOT,
            env=runtime._runtime_environment(provenance.sha),
            pulumi_dir=project,
            policy_pack_dir=runtime.ROOT / "policy",
            plan_dir=runtime.ROOT / ".artifacts/poc-scheduled-registry/plan",
            preview_artifact_dir=runtime.ROOT
            / ".artifacts/poc-scheduled-registry/preview",
            backend_url=f"s3://{runtime.backend.BUCKET}",
            secrets_provider=runtime.backend.PROVIDER,
            registry_plan_gate=_gate(provenance, digest, projection, initial),
        )
        _recheck(provenance)
        status = runtime.runner._dispatch_command("plan", context, ["test"])
        if status == 0:
            _recheck(provenance)
            final = _capture(digest, projection)
            _require(final.summary["state"] == initial.summary["state"])
            _recheck(provenance)
        return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "check"))
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            _installed_contract(verify_provenance())
            return 0
        status = execute()
        if status == 0:
            print(
                "TEST registry matches installed main; "
                "diagnostic only, no phase acceptance."
            )
        return status
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print("INVALID: scheduled registry diagnostic failed", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
