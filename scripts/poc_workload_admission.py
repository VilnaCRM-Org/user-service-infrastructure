"""Observe authenticated first-workload prerequisites inside the trusted worker.

This module never starts a Pulumi program or grants phase permission. A registry
receipt authenticates historical completion; current checkpoint and publisher
evidence must be checked independently before any future workload execution.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import poc_contract as contract_api
import poc_registry_completion as completion
import poc_registry_runner as registry
import poc_source_artifact as artifacts
import poc_workload_capabilities as capabilities
import poc_workload_images as images
from poc_registry_phase_entrypoint import RegistryPhaseProjection
from service_execution_process import require, run


@dataclass(frozen=True)
class Authority:
    """Protected workflow inputs; no identity is learned from a release receipt."""

    app_id: int
    app_slug: str
    registry_workflow_sha: str
    publisher_workflow_sha: str


def authority_from_environment(environment):
    """Require the existing App identity and explicit trusted workflow revisions."""
    identifier = environment.get("GOVERNANCE_PROMOTION_APP_ID", "")
    artifacts._pattern(identifier, r"[1-9][0-9]*")
    value = Authority(
        int(identifier),
        environment.get("GOVERNANCE_PROMOTION_APP_SLUG", ""),
        environment.get("POC_REGISTRY_WORKFLOW_SHA", ""),
        environment.get("POC_PUBLISHER_WORKFLOW_SHA", ""),
    )
    _authority(value)
    return value


def _authority(value):
    require(type(value) is Authority, "workload-authority-required")
    require(type(value.app_id) is int and value.app_id > 0, "workload-app-identity")
    artifacts._pattern(value.app_slug, r"[a-z0-9][a-z0-9-]{0,99}")
    for sha in (value.registry_workflow_sha, value.publisher_workflow_sha):
        artifacts._pattern(sha, r"[0-9a-f]{40}")


def _github_bytes(endpoint, *arguments):
    """Use the fixed CLI with only the root-private GitHub credential context."""
    return run(
        ["/usr/bin/gh", "api", "--hostname", "api.github.com", endpoint, *arguments],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": os.environ["HOME"],
            "GH_CONFIG_DIR": os.environ["HOME"] + "/gh",
            "GH_TOKEN": os.environ["GH_TOKEN"],
        },
        cwd=Path("/trusted"),
        timeout=120,
    )


def _github(endpoint, *arguments):
    return registry.backend._json(_github_bytes(endpoint, *arguments))


def _download(identifier):
    artifacts._pattern(identifier, r"[1-9][0-9]*")
    return _github_bytes(f"{artifacts.API}/actions/artifacts/{identifier}/zip")


@dataclass(frozen=True)
class RegistryAnchor:
    """Authenticated historical anchor matched to the current first-workload state."""

    binding: contract_api.RegistryReleaseBinding
    contract: dict = field(repr=False)
    checkpoint: dict = field(repr=False)


def _registry_document(candidate, gh):
    source = candidate["payload"]["observation"]["source"]
    artifacts._pattern(source["head_sha"], r"[0-9a-f]{40}")
    blob, raw = artifacts.source_adapter._content_bytes(
        gh(
            f"{artifacts.API}/contents/{artifacts.admission.CONTRACT_PATH}"
            f"?ref={source['head_sha']}"
        )
    )
    require(blob == source["blob_sha"], "workload-registry-blob")
    document = artifacts.admission._decode_contract(raw)
    require(
        contract_api._digest(document) == source["contract_sha256"],
        "workload-registry-contract",
    )
    return document


def inspect_registry(source, contract, authority, command, *, gh=None, download=None):
    """Reuse the complete registry issuer verifier and fresh native graph capture."""
    _authority(authority)
    contract_api._validate_document(contract)
    require(contract["phase"] == "workload", "workload-contract-required")
    require(command in ("plan", "up-plan", "drift"), "workload-command")
    gh, download = gh or _github, download or _download
    identifier = contract["workload"]["release"]["registry_phase_receipt_id"]
    endpoint = f"{artifacts.API}/deployments/{identifier}"
    candidate = gh(endpoint)
    document = _registry_document(candidate, gh)
    binding = completion.verify_completion(
        identifier,
        app_id=authority.app_id,
        app_slug=authority.app_slug,
        trusted_workflow_sha=authority.registry_workflow_sha,
        registry_contract=document,
        gh=gh,
        download=download,
    )
    require(gh(endpoint) == candidate, "workload-registry-receipt-changed")
    contract_api.validate_registry_release_binding(
        contract, registry_contract=document, expected=binding
    )
    projection = RegistryPhaseProjection(
        cast(dict[str, dict[str, str]], registry.graph.REGISTRIES)
    )
    capture = registry._capture(
        source, "up-plan" if command == "up-plan" else "plan", projection
    )
    require(
        len(capture.resources) == len(registry.graph._graph(projection)),
        "workload-completed-registry-required",
    )
    state = capture.summary["state"]
    current = {
        "version": state["VersionId"],
        "etag": state["ETag"],
        "sha256": state["sha256"],
    }
    require(
        current == candidate["payload"]["observation"]["checkpoint"],
        "workload-registry-checkpoint-changed",
    )
    return RegistryAnchor(binding, document, current)


APP_REPOSITORY = "VilnaCRM-Org/user-service"
APP_ID = 646535009
APP_API = f"repos/{APP_REPOSITORY}"
PUBLISHER_WORKFLOW = ".github/workflows/publish-poc-images.yml"
JOB_NAMES = (
    "Validate application release",
    "Build application images",
    "Publish TEST application images",
)


def _app_download(identifier):
    artifacts._pattern(identifier, r"[1-9][0-9]*")
    return _github_bytes(f"{APP_API}/actions/artifacts/{identifier}/zip")


def _publisher(gh, release, authority):
    identifier = release["publisher_run_id"]
    endpoint = f"{APP_API}/actions/runs/{identifier}"
    observed = gh(endpoint)
    artifacts._matches(
        gh(f"apps/{authority.app_slug}"),
        {"id": authority.app_id, "slug": authority.app_slug},
    )
    login = f"{authority.app_slug}[bot]"
    actor = gh(f"users/{login}")
    artifacts._matches(actor, {"login": login, "type": "Bot"})
    require(type(actor["id"]) is int and actor["id"] > 0, "workload-publisher-actor")
    for field_name in ("actor", "triggering_actor"):
        artifacts._matches(
            observed[field_name], {"id": actor["id"], "login": login, "type": "Bot"}
        )
    artifacts._matches(
        observed,
        {
            "id": identifier,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "path": PUBLISHER_WORKFLOW,
            "head_branch": "main",
            "head_sha": authority.publisher_workflow_sha,
            "status": "completed",
            "conclusion": "success",
        },
    )
    for field_name in ("repository", "head_repository"):
        artifacts._matches(
            observed[field_name], {"id": APP_ID, "full_name": APP_REPOSITORY}
        )
        artifacts._matches(observed[field_name]["owner"], {"id": 114362548})
    return observed, _publisher_jobs(gh, identifier, authority)


def _publisher_jobs(gh, identifier, authority):
    """Bind complete successful job identities and ordering to attempt one."""
    endpoint = f"{APP_API}/actions/runs/{identifier}"
    pages = gh(f"{endpoint}/attempts/1/jobs?per_page=100", "--paginate", "--slurp")
    rows = [job for page in pages for job in page["jobs"]]
    require(len(rows) == 3, "workload-publisher-jobs")
    jobs = {job["name"]: job for job in rows}
    require(set(jobs) == set(JOB_NAMES), "workload-publisher-jobs")
    for job in jobs.values():
        require(type(job["id"]) is int and job["id"] > 0, "workload-publisher-job-id")
        artifacts._matches(
            job,
            {
                "run_id": identifier,
                "head_sha": authority.publisher_workflow_sha,
                "status": "completed",
                "conclusion": "success",
            },
        )
        require(
            artifacts._timestamp(job["started_at"])
            <= artifacts._timestamp(job["completed_at"]),
            "workload-publisher-job-time",
        )
    require(len({job["id"] for job in rows}) == 3, "workload-publisher-job-id")
    publish = jobs[JOB_NAMES[2]]
    for name in JOB_NAMES[:2]:
        require(
            artifacts._timestamp(jobs[name]["completed_at"])
            <= artifacts._timestamp(publish["started_at"]),
            "workload-publisher-job-order",
        )
    return jobs


def _artifact_metadata(value, release, authority, *, name):
    identifier = value["id"]
    require(type(identifier) is int and identifier > 0, "workload-artifact-id")
    artifacts._matches(value, {"name": name, "expired": False})
    artifacts._pattern(value["digest"], r"sha256:[0-9a-f]{64}")
    artifacts._matches(
        value["workflow_run"],
        {
            "id": release["publisher_run_id"],
            "repository_id": APP_ID,
            "head_repository_id": APP_ID,
            "head_branch": "main",
            "head_sha": authority.publisher_workflow_sha,
        },
    )
    require(
        artifacts._timestamp(value["created_at"])
        <= datetime.now(timezone.utc)
        < artifacts._timestamp(value["expires_at"]),
        "workload-artifact-expired",
    )


def _published_document(
    gh, download, metadata, release, authority, publish, *, name, member
):
    _artifact_metadata(metadata, release, authority, name=name)
    size = metadata["size_in_bytes"]
    require(
        type(size) is int and 0 < size <= artifacts.MAX_ZIP_BYTES,
        "workload-artifact-size",
    )
    require(
        artifacts._timestamp(publish["started_at"])
        <= artifacts._timestamp(metadata["created_at"])
        <= artifacts._timestamp(publish["completed_at"]),
        "workload-artifact-job-time",
    )
    identifier = str(metadata["id"])
    endpoint = f"{APP_API}/actions/artifacts/{identifier}"
    require(gh(endpoint) == metadata, "workload-artifact-changed")
    raw = download(identifier)
    require(
        "sha256:" + hashlib.sha256(raw).hexdigest() == metadata["digest"],
        "workload-archive-digest",
    )
    payload = artifacts._payload(raw, member_name=member)
    document = registry.backend._json(payload)
    require(gh(endpoint) == metadata, "workload-artifact-changed")
    return document, hashlib.sha256(payload).hexdigest()


def _evidence(gh, download, release, authority, jobs, kind, member):
    reference = release[kind]
    completion._reference_object(reference)
    metadata = gh(f"{APP_API}/actions/artifacts/{reference['artifact_id']}")
    artifacts._matches(metadata, {"id": reference["artifact_id"]})
    prefix = "poc-build-provenance" if kind == "provenance" else "poc-quality-evidence"
    name = f"{prefix}-{release['publisher_run_id']}-1"
    document, digest = _published_document(
        gh,
        download,
        metadata,
        release,
        authority,
        jobs[JOB_NAMES[2]],
        name=name,
        member=member,
    )
    require(
        metadata["digest"] == "sha256:" + reference["archive_sha256"]
        and digest == reference["file_sha256"],
        "workload-evidence-digest",
    )
    return document


def _evidence_values(release, authority, jobs, quality, provenance):
    common = {
        "repository": APP_REPOSITORY,
        "source_sha": release["source_sha"],
        "publisher_run_id": release["publisher_run_id"],
        "publisher_run_attempt": 1,
        "workflow_sha": authority.publisher_workflow_sha,
    }
    expected_quality = {
        **common,
        "schema_version": "poc-quality-v1",
        "quality_job_id": jobs[JOB_NAMES[0]]["id"],
        "command": "make ci",
        "conclusion": "success",
    }
    build_reference = provenance["build_artifact"]
    completion._reference_object(build_reference)
    expected_provenance = {
        **common,
        "schema_version": "poc-build-provenance-v1",
        "platform": release["platform"],
        "build_job_id": jobs[JOB_NAMES[1]]["id"],
        "build_artifact": build_reference,
        "registry": {
            key: release[key]
            for key in (
                "registry_phase_receipt_id",
                "registry_contract_digest",
                "registry_checkpoint_version",
            )
        },
        "web": release["web"],
        "worker": release["worker"],
    }
    # Canonical JSON equality also distinguishes true from integer 1.
    require(
        contract_api._digest(quality) == contract_api._digest(expected_quality),
        "workload-quality-evidence",
    )
    require(
        contract_api._digest(provenance) == contract_api._digest(expected_provenance),
        "workload-build-evidence",
    )


def _build_artifact(gh, release, authority, jobs, reference):
    endpoint = f"{APP_API}/actions/artifacts/{reference['artifact_id']}"
    value = gh(endpoint)
    artifacts._matches(value, {"id": reference["artifact_id"]})
    _artifact_metadata(
        value,
        release,
        authority,
        name=f"poc-image-build-{release['publisher_run_id']}-1",
    )
    require(
        value["digest"] == "sha256:" + reference["archive_sha256"],
        "workload-build-artifact-digest",
    )
    size = value["size_in_bytes"]
    require(
        type(size) is int and 0 < size <= 7 * 1024**3, "workload-build-artifact-size"
    )
    build = jobs[JOB_NAMES[1]]
    require(
        artifacts._timestamp(build["started_at"])
        <= artifacts._timestamp(value["created_at"])
        <= artifacts._timestamp(build["completed_at"]),
        "workload-build-artifact-time",
    )
    require(gh(endpoint) == value, "workload-build-artifact-changed")


def inspect_release(contract, authority, *, gh=None, download=None):
    """Authenticate exact installed publisher run, jobs, manifest and evidence bytes."""
    _authority(authority)
    contract_api._validate_document(contract)
    require(contract["phase"] == "workload", "workload-contract-required")
    gh, download = gh or _github, download or _app_download
    release = contract["workload"]["release"]
    require(
        release["workflow_ref"]
        == f"{APP_REPOSITORY}/{PUBLISHER_WORKFLOW}@refs/heads/main",
        "workload-publisher-workflow-reference",
    )
    observed, jobs = _publisher(gh, release, authority)
    endpoint = f"{APP_API}/actions/runs/{release['publisher_run_id']}"
    pages = gh(f"{endpoint}/artifacts?per_page=100", "--paginate", "--slurp")
    name = f"poc-release-manifest-{release['publisher_run_id']}-1"
    matches = [
        item for page in pages for item in page["artifacts"] if item["name"] == name
    ]
    require(len(matches) == 1, "workload-manifest-artifact")
    manifest, digest = _published_document(
        gh,
        download,
        matches[0],
        release,
        authority,
        jobs[JOB_NAMES[2]],
        name=name,
        member="release-manifest.json",
    )
    require(
        contract_api._digest(manifest) == contract_api._digest(release),
        "workload-manifest-mismatch",
    )
    quality = _evidence(
        gh, download, release, authority, jobs, "quality_evidence", "quality.json"
    )
    provenance = _evidence(
        gh, download, release, authority, jobs, "provenance", "provenance.json"
    )
    _evidence_values(release, authority, jobs, quality, provenance)
    _build_artifact(gh, release, authority, jobs, provenance["build_artifact"])
    current, current_jobs = _publisher(gh, release, authority)
    require(current == observed and current_jobs == jobs, "workload-publisher-changed")
    return digest


def inspect_workload(source, contract, authority, command):
    """Run real authenticated reads; never substitute these for a workload plan gate."""
    anchor = inspect_registry(source, contract, authority, command)
    inspect_release(contract, authority)
    images.inspect_images(contract)
    registry.graph.mail.inspect_identity(ready=True)
    capabilities.inspect_capabilities(contract)
    require(
        inspect_registry(source, contract, authority, command) == anchor,
        "workload-prior-changed",
    )
    raise ValueError("workload-native-image-capability-and-plan-gates-required")
