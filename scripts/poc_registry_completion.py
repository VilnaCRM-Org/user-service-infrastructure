#!/usr/bin/env python3
"""Issue a distinct TEST registry proof from a fresh, child-free observation job.

The issuer uses the existing main-only promotion App. No full promotion status,
workload admission, image publishing, or service execution isolation is implied.
Historical readback validates original producer evidence without re-admitting an
old PR. Missing/expired evidence fails; observations are not atomic cloud locks.
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
from datetime import datetime, timezone  # noqa: E402

import _github_evidence_environment as boundary  # noqa: E402
import poc_contract as contract_api  # noqa: E402
import poc_registry_runner as runtime  # noqa: E402
import poc_source_artifact as source_api  # noqa: E402

API = source_api.API
ENVIRONMENT = "poc-test-registry"
TASK = "registry-proof"
KIND = "poc-test-registry-completion/v1"
OBSERVATION_KIND = "poc-test-registry-observation/v1"
OBSERVATION_PATH = Path(".artifacts/poc-registry-observation/observation.json")
PROOF_PATH = Path(".artifacts/poc-registry-proof/proof.json")
JOBS = ("Test Apply", "Test Post-Apply Drift", "Observe TEST Registry Completion")
PROOF_JOB = "Publish TEST Registry Completion Proof"


def _require(condition):
    if not condition:
        raise ValueError("Invalid TEST registry completion evidence")


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _reference(artifact_id, archive_sha256, file_sha256):
    source_api._pattern(artifact_id, r"[1-9][0-9]*")
    for digest in (archive_sha256, file_sha256):
        source_api._pattern(digest, r"[0-9a-f]{64}")
    return {
        "artifact_id": int(artifact_id),
        "archive_sha256": archive_sha256,
        "file_sha256": file_sha256,
    }


def _references(environment):
    return {
        kind: _reference(
            *(
                environment[f"POC_{kind.upper()}_{field}"]
                for field in ("ARTIFACT_ID", "ARCHIVE_SHA256", "FILE_SHA256")
            )
        )
        for kind in ("source", "observation")
    }


def _reference_object(reference):
    _require(
        type(reference) is dict
        and set(reference) == {"artifact_id", "archive_sha256", "file_sha256"}
    )
    _require(type(reference["artifact_id"]) is int and reference["artifact_id"] > 0)
    _require(
        reference
        == _reference(
            str(reference["artifact_id"]),
            reference["archive_sha256"],
            reference["file_sha256"],
        )
    )


def _source(reference):
    _reference_object(reference)
    return source_api.load_verified_contract(
        artifact_id=str(reference["artifact_id"]),
        archive_sha256=reference["archive_sha256"],
        source_sha256=reference["file_sha256"],
    )


def _current_source(reference):
    source, contract = _source(reference)
    _require(source["request"]["target_environment"] == "test")
    _require(source["request"]["command"] == "up")
    _require(source["source"]["base_sha"] == os.environ["GITHUB_SHA"])
    runtime._review(source)
    projection = runtime.project_registry_phase(
        runtime.SourceAdmission(**source["source"]), contract
    )
    return source, projection


def _tags(name):
    _require(name in {row["name"] for row in runtime.graph.REGISTRIES.values()})
    arn = (
        f"arn:aws:ecr:{runtime.backend.REGION}:{runtime.backend.ACCOUNT}:"
        f"repository/{name}"
    )
    result = subprocess.run(  # nosec B603 B607
        [
            "aws",
            "ecr",
            "list-tags-for-resource",
            "--resource-arn",
            arn,
            "--region",
            runtime.backend.REGION,
            "--endpoint-url",
            f"https://api.ecr.{runtime.backend.REGION}.amazonaws.com",
            "--output",
            "json",
            "--no-cli-pager",
        ],
        capture_output=True,
        check=False,
        timeout=60,
        env={**os.environ, "AWS_MAX_ATTEMPTS": "1"},
    )
    _require(
        result.returncode == 0
        and len(result.stdout) <= runtime.backend.MAX_METADATA
        and len(result.stderr) <= 65536
    )
    return runtime.backend._json(result.stdout)


def _native_tags():
    for row in runtime.graph.REGISTRIES.values():
        response = _tags(row["name"])
        tags = response.get("tags")
        _require(type(tags) is list and len(tags) == len(runtime.graph.DEFAULT_TAGS))
        actual = {}
        for tag in tags:
            _require(type(tag) is dict and set(tag) == {"Key", "Value"})
            _require(type(tag["Key"]) is str and tag["Key"] not in actual)
            actual[tag["Key"]] = tag["Value"]
        _require(actual == runtime.graph.DEFAULT_TAGS)


def admit(reference):
    """Authenticate the complete source and requester before AWS credentials."""
    runtime._trusted_root()
    _require(os.environ.get("GITHUB_JOB") == "test_registry_observation")
    return _current_source(reference)


def observe(reference):
    """Run only in a fresh trusted job that never starts a Pulumi/PR child."""
    source, projection = admit(reference)
    first = runtime._capture(source, "plan", projection)
    _require(len(first.resources) == len(runtime.graph._graph(projection)))
    _native_tags()
    second = runtime._capture(source, "plan", projection)
    _require(first.summary["state"] == second.summary["state"])
    _native_tags()
    runtime._review(source)
    runtime._trusted_root()
    run_id, workflow_sha = source_api._context(os.environ)
    state = second.summary["state"]
    return {
        "kind": OBSERVATION_KIND,
        "run_id": int(run_id),
        "run_attempt": 1,
        "workflow_sha": workflow_sha,
        "source": source["source"],
        "source_artifact": reference,
        "observed_at": second.summary["observed_at"],
        "checkpoint": {
            "version": state["VersionId"],
            "etag": state["ETag"],
            "sha256": state["sha256"],
        },
        "registry_controls_sha256": _digest(
            _canonical(
                {
                    "registries": runtime.graph.REGISTRIES,
                    "mail_identity": runtime.graph.mail.DECLARATION,
                    "tags": runtime.graph.DEFAULT_TAGS,
                }
            )
        ),
    }


def _observation(reference, run_id, workflow_sha, *, gh, download):
    _reference_object(reference)
    identifier = str(reference["artifact_id"])
    name = f"poc-registry-observation-{run_id}-1"
    metadata = source_api._artifact(
        gh, identifier, reference["archive_sha256"], run_id, workflow_sha, name=name
    )
    raw = download(identifier)
    _require(_digest(raw) == reference["archive_sha256"])
    payload = source_api._payload(raw, member_name="observation.json")
    _require(_digest(payload) == reference["file_sha256"])
    value = json.loads(
        payload,
        object_pairs_hook=source_api._pairs,
        parse_constant=contract_api._reject_nonfinite,
    )
    _require(
        type(value) is dict
        and set(value)
        == {
            "kind",
            "run_id",
            "run_attempt",
            "workflow_sha",
            "source",
            "source_artifact",
            "observed_at",
            "checkpoint",
            "registry_controls_sha256",
        }
    )
    source_api._matches(
        value,
        {
            "kind": OBSERVATION_KIND,
            "run_id": int(run_id),
            "run_attempt": 1,
            "workflow_sha": workflow_sha,
        },
    )
    _reference_object(value["source_artifact"])
    source_api._fields(
        value["source"],
        {
            "head_sha": r"[0-9a-f]{40}",
            "base_sha": r"[0-9a-f]{40}",
            "contract_sha256": r"[0-9a-f]{64}",
            "blob_sha": r"[0-9a-f]{40}",
            "schema_sha256": r"[0-9a-f]{64}",
            "validator_sha256": r"[0-9a-f]{64}",
            "path": source_api.re.escape(source_api.admission.CONTRACT_PATH),
        },
    )
    _require(value["source"]["base_sha"] == workflow_sha)
    _require(
        type(value["checkpoint"]) is dict
        and set(value["checkpoint"]) == {"version", "etag", "sha256"}
    )
    contract_api._registry_release_fields(
        {
            "registry_phase_receipt_id": 1,
            "registry_contract_digest": value["source"]["contract_sha256"],
            "registry_checkpoint_version": value["checkpoint"]["version"],
        }
    )
    source_api._pattern(value["checkpoint"]["sha256"], r"[0-9a-f]{64}")
    source_api._pattern(value["checkpoint"]["etag"], r'"[0-9a-f]{32}"')
    observed = source_api._timestamp(value["observed_at"]).replace(microsecond=0)
    created = source_api._timestamp(metadata["created_at"])
    _require(observed <= created <= datetime.now(timezone.utc))
    expected_controls = _digest(
        _canonical(
            {
                "registries": runtime.graph.REGISTRIES,
                "mail_identity": runtime.graph.mail.DECLARATION,
                "tags": runtime.graph.DEFAULT_TAGS,
            }
        )
    )
    _require(value["registry_controls_sha256"] == expected_controls)
    source_api._artifact(
        gh, identifier, reference["archive_sha256"], run_id, workflow_sha, name=name
    )
    return value, metadata["created_at"]


def _job_list(gh, run_id):
    pages = gh(
        f"{API}/actions/runs/{run_id}/attempts/1/jobs?per_page=100",
        "--paginate",
        "--slurp",
    )
    _require(type(pages) is list and bool(pages))
    jobs = [job for page in pages for job in page["jobs"]]
    _require(all(page["total_count"] == len(jobs) for page in pages))
    _require(len({job["id"] for job in jobs}) == len(jobs))
    return jobs


def _jobs(gh, run_id, workflow_sha, *, completed=False, observed_at, uploaded_at):
    jobs = _job_list(gh, run_id)
    selected = {}
    previous_end = None
    for name in (*JOBS, PROOF_JOB) if completed else JOBS:
        matches = [job for job in jobs if job.get("name") == name]
        _require(len(matches) == 1)
        job = matches[0]
        source_api._matches(
            job,
            {
                "run_id": int(run_id),
                "head_sha": workflow_sha,
                "status": "completed",
                "conclusion": "success",
            },
        )
        _require(type(job["id"]) is int and job["id"] > 0)
        start, end = (
            source_api._timestamp(job[key]) for key in ("started_at", "completed_at")
        )
        _require(start <= end <= datetime.now(timezone.utc))
        _require(previous_end is None or previous_end <= start)
        if name == JOBS[-1]:
            _require(
                start
                <= source_api._timestamp(observed_at).replace(microsecond=0)
                <= source_api._timestamp(uploaded_at)
                <= end
            )
        previous_end = end
        selected[name] = job["id"]
    return selected


def _historical_source(observed, run_id, workflow_sha, gh, download):
    reference = observed["source_artifact"]
    identifier = str(reference["artifact_id"])
    source_api._artifact(
        gh, identifier, reference["archive_sha256"], run_id, workflow_sha
    )
    raw = download(identifier)
    _require(_digest(raw) == reference["archive_sha256"])
    payload = source_api._payload(raw)
    _require(_digest(payload) == reference["file_sha256"])
    source = json.loads(
        payload,
        object_pairs_hook=source_api._pairs,
        parse_constant=contract_api._reject_nonfinite,
    )
    _require(
        type(source) is dict and set(source) == {"kind", "source", "request", "review"}
    )
    _require(
        source["kind"] == "poc-phase-source/v1"
        and source["source"] == observed["source"]
    )
    source_api._matches(
        source["request"],
        {
            "command": "up",
            "target_environment": "test",
            "head_sha": observed["source"]["head_sha"],
        },
    )
    source_api._matches(
        source["review"],
        {"head_sha": observed["source"]["head_sha"], "base_sha": workflow_sha},
    )
    source_api._artifact(
        gh, identifier, reference["archive_sha256"], run_id, workflow_sha
    )


def _environment(gh):
    endpoint = f"{API}/environments/{boundary.NAME}"
    _require(
        not boundary.verification_blockers(
            gh(endpoint), gh(f"{endpoint}/deployment-branch-policies")
        )
    )


def prepare(environment=None):
    """Authenticate completed job and artifact evidence before App credentials."""
    environment = os.environ if environment is None else environment
    runtime._trusted_root()
    _require(environment.get("GITHUB_JOB") == "test_registry_proof")
    run_id, workflow_sha = source_api._context(environment)
    refs = _references(environment)
    source, _ = _current_source(refs["source"])
    observed, uploaded_at = _observation(
        refs["observation"],
        run_id,
        workflow_sha,
        gh=runtime.preflight.gh,
        download=source_api._download_zip,
    )
    _require(
        observed["source"] == source["source"]
        and observed["source_artifact"] == refs["source"]
    )
    jobs = _jobs(
        runtime.preflight.gh,
        run_id,
        workflow_sha,
        observed_at=observed["observed_at"],
        uploaded_at=uploaded_at,
    )
    _environment(runtime.preflight.gh)
    return {
        "kind": KIND,
        "repository": source_api.REPOSITORY,
        "observation_artifact": refs["observation"],
        "observation": observed,
        "jobs": jobs,
    }


def _write(path, value):
    result = subprocess.run(  # nosec B603 B607
        ["gh", "api", path, "--method", "POST", "--input", "-"],
        input=_canonical(value),
        capture_output=True,
        check=False,
        timeout=60,
        env={**os.environ, "GH_TOKEN": os.environ["REGISTRY_PROOF_APP_TOKEN"]},
    )
    _require(
        result.returncode == 0 and len(result.stdout) <= source_api.MAX_SOURCE_BYTES
    )
    return json.loads(result.stdout, object_pairs_hook=source_api._pairs)


def _issuer(value, app_id, app_slug):
    source_api._matches(
        value.get("performed_via_github_app"), {"id": app_id, "slug": app_slug}
    )
    source_api._matches(
        value.get("creator"), {"login": f"{app_slug}[bot]", "type": "Bot"}
    )


def _deployment(gh, identifier, proof, app_id, app_slug):
    endpoint = f"{API}/deployments/{identifier}"
    deployment = gh(endpoint)
    source_api._matches(
        deployment,
        {
            "id": identifier,
            "sha": proof["observation"]["source"]["head_sha"],
            "environment": ENVIRONMENT,
            "task": TASK,
            "production_environment": False,
            "transient_environment": False,
            "payload": proof,
        },
    )
    _issuer(deployment, app_id, app_slug)
    pages = gh(f"{endpoint}/statuses?per_page=100", "--paginate", "--slurp")
    statuses = [status for page in pages for status in page]
    _require(bool(statuses))
    status = statuses[0]
    source_api._matches(
        status,
        {
            "state": "success",
            "environment": ENVIRONMENT,
            "log_url": f"https://github.com/{source_api.REPOSITORY}/actions/runs/{proof['observation']['run_id']}",
        },
    )
    _issuer(status, app_id, app_slug)
    return deployment


def publish(proof, *, app_id, app_slug):
    """Revalidate immediately, create one distinct record, then read it back."""
    _require(type(app_id) is int and app_id > 0)
    source_api._pattern(app_slug, r"[a-z0-9][a-z0-9-]{0,99}")
    _require(proof == prepare())
    observed = proof["observation"]
    deployment = _write(
        f"{API}/deployments",
        {
            "ref": observed["source"]["head_sha"],
            "environment": ENVIRONMENT,
            "task": TASK,
            "auto_merge": False,
            "required_contexts": [],
            "production_environment": False,
            "transient_environment": False,
            "description": "Verified TEST registry completion only",
            "payload": proof,
        },
    )
    identifier = deployment["id"]
    _require(type(identifier) is int and identifier > 0)
    source_api._matches(deployment, {"sha": observed["source"]["head_sha"]})
    _issuer(deployment, app_id, app_slug)
    _write(
        f"{API}/deployments/{identifier}/statuses",
        {
            "state": "success",
            "environment": ENVIRONMENT,
            "auto_inactive": False,
            "description": "TEST registry observed after apply and drift",
            "log_url": f"https://github.com/{source_api.REPOSITORY}/actions/runs/{observed['run_id']}",
        },
    )
    _deployment(runtime.preflight.gh, identifier, proof, app_id, app_slug)
    return identifier


def _completed_run(gh, run_id, trusted_workflow_sha):
    run = gh(f"{API}/actions/runs/{run_id}")
    source_api._matches(
        run,
        {
            "id": int(run_id),
            "run_attempt": 1,
            "event": "repository_dispatch",
            "path": source_api.WORKFLOW,
            "head_branch": "main",
            "head_sha": trusted_workflow_sha,
            "status": "completed",
            "conclusion": "success",
        },
    )
    for key in ("repository", "head_repository"):
        source_api._matches(
            run.get(key),
            {
                "id": source_api.admission.REPOSITORY_ID,
                "full_name": source_api.REPOSITORY,
            },
        )
        source_api._matches(
            run[key].get("owner"), {"id": source_api.admission.OWNER_ID}
        )
    return run


def _verification_authority(
    identifier, app_id, app_slug, trusted_workflow_sha, registry_contract
):
    _require(
        type(identifier) is int
        and identifier > 0
        and type(app_id) is int
        and app_id > 0
    )
    source_api._pattern(app_slug, r"[a-z0-9][a-z0-9-]{0,99}")
    source_api._pattern(trusted_workflow_sha, r"[0-9a-f]{40}")
    contract_api._shape(registry_contract)
    contract_api._semantics(registry_contract)
    _require(registry_contract["phase"] == "registry")


def verify_completion(
    identifier,
    *,
    app_id,
    app_slug,
    trusted_workflow_sha,
    registry_contract,
    gh=None,
    download=None,
):
    """Authenticate original completed issuance, independent of the old PR head.

    The caller pins trusted issuer/workflow authority and the registry contract;
    neither comes from the receipt. This is not a fresh observation of AWS.
    """
    _verification_authority(
        identifier, app_id, app_slug, trusted_workflow_sha, registry_contract
    )
    gh, download = gh or runtime.preflight.gh, download or source_api._download_zip
    candidate = gh(f"{API}/deployments/{identifier}")
    proof = candidate["payload"]
    _require(
        type(proof) is dict
        and set(proof)
        == {"kind", "repository", "observation_artifact", "observation", "jobs"}
    )
    source_api._matches(proof, {"kind": KIND, "repository": source_api.REPOSITORY})
    _deployment(gh, identifier, proof, app_id, app_slug)
    observed = proof["observation"]
    run_id = str(observed["run_id"])
    source_api._pattern(run_id, r"[1-9][0-9]*")
    _require(observed["workflow_sha"] == trusted_workflow_sha)
    run = _completed_run(gh, run_id, trusted_workflow_sha)
    verified, uploaded_at = _observation(
        proof["observation_artifact"],
        run_id,
        trusted_workflow_sha,
        gh=gh,
        download=download,
    )
    _require(verified == observed)
    _historical_source(observed, run_id, trusted_workflow_sha, gh, download)
    jobs = _jobs(
        gh,
        run_id,
        trusted_workflow_sha,
        completed=True,
        observed_at=observed["observed_at"],
        uploaded_at=uploaded_at,
    )
    _require(type(proof["jobs"]) is dict and set(proof["jobs"]) == set(JOBS))
    _require(
        all(
            type(identifier) is int and identifier > 0
            for identifier in proof["jobs"].values()
        )
    )
    _require(proof["jobs"] == {name: jobs[name] for name in JOBS})
    digest = _digest(_canonical(registry_contract))
    _require(observed["source"]["contract_sha256"] == digest)
    _deployment(gh, identifier, proof, app_id, app_slug)
    _require(gh(f"{API}/actions/runs/{run_id}") == run)
    return contract_api.RegistryReleaseBinding(
        identifier, digest, observed["checkpoint"]["version"]
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("admit", "observe", "prepare", "publish"))
    mode = parser.parse_args(argv).mode
    try:
        if mode in ("admit", "observe"):
            reference = _reference(
                *(
                    os.environ[f"POC_SOURCE_{field}"]
                    for field in ("ARTIFACT_ID", "ARCHIVE_SHA256", "FILE_SHA256")
                )
            )
            if mode == "admit":
                admit(reference)
                print("VALID: TEST registry observation source admitted")
                return 0
            result, path = observe(reference), OBSERVATION_PATH
        elif mode == "prepare":
            result, path = prepare(), PROOF_PATH
        else:
            proof = json.loads(
                PROOF_PATH.read_bytes(), object_pairs_hook=source_api._pairs
            )
            identifier = publish(
                proof,
                app_id=int(os.environ["REGISTRY_PROOF_APP_ID"]),
                app_slug=os.environ["REGISTRY_PROOF_APP_SLUG"],
            )
            print(f"registry_phase_receipt_id={identifier}")
            return 0
        raw = _canonical(result) + b"\n"
        _require(len(raw) <= source_api.MAX_SOURCE_BYTES)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(raw)
        print(f"file_sha256={_digest(raw)}")
        return 0
    except (
        ValueError,
        EOFError,
        source_api.zipfile.BadZipFile,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print("INVALID: TEST registry completion proof failed", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
