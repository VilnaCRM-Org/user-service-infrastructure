"""Exercise native-shaped evidence through real registry and release verifiers."""

import base64
import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_admission as module  # noqa: E402
import pytest
import test_poc_registry_plan as graph
from test_poc_contract import fixture
from test_poc_registry_completion import evidence as evidence
from test_poc_source_artifact import prepared as prepared
from test_poc_source_artifact import zip_bytes
from test_service_execution_transport import installed as installed


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


AUTHORITY = module.Authority(1234, "promotion-app", "a" * 40, "b" * 40)


@pytest.fixture
def registry_evidence(evidence, monkeypatch):
    evidence["run"].update(status="completed", conclusion="success")
    raw = encoded(evidence["contract"])
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    evidence["source"]["source"]["blob_sha"] = blob
    # Re-encode the historical source artifact after binding its real Git blob.
    source_raw = encoded(evidence["source"])
    source_zip = zip_bytes(source_raw)
    reference = evidence["observation"]["source_artifact"]
    reference.update(archive_sha256=sha(source_zip), file_sha256=sha(source_raw))
    evidence["metadata"][102].update(
        digest="sha256:" + sha(source_zip), size_in_bytes=len(source_zip)
    )
    evidence["archives"]["102"] = source_zip
    observation_raw = encoded(evidence["observation"])
    observation_zip = zip_bytes(observation_raw, "observation.json")
    evidence["reference"].update(
        archive_sha256=sha(observation_zip), file_sha256=sha(observation_raw)
    )
    evidence["metadata"][103].update(
        digest="sha256:" + sha(observation_zip), size_in_bytes=len(observation_zip)
    )
    evidence["archives"]["103"] = observation_zip
    workload = fixture("workload")
    for key in ("account_id", "region", "environment", "backend", "registries"):
        workload[key] = copy.deepcopy(evidence["contract"][key])
    for kind in ("web", "worker"):
        workload["workload"]["release"][kind]["repository_uri"] = workload[
            "registries"
        ][kind]["uri"]
    workload["workload"]["release"].update(
        registry_phase_receipt_id=301,
        registry_contract_digest=module.contract_api._digest(evidence["contract"]),
        registry_checkpoint_version=evidence["observation"]["checkpoint"]["version"],
    )
    original = evidence["gh"]

    def gh(endpoint, *args):
        if "/contents/" in endpoint:
            return {
                "type": "file",
                "path": module.artifacts.admission.CONTRACT_PATH,
                "encoding": "base64",
                "size": len(raw),
                "sha": blob,
                "content": base64.b64encode(raw).decode(),
            }
        return copy.deepcopy(original(endpoint, *args))

    checkpoint = evidence["observation"]["checkpoint"]
    capture = SimpleNamespace(
        resources=list(graph.states().values()),
        summary={
            "state": {
                "kind": "observed_checkpoint",
                "VersionId": checkpoint["version"],
                "ETag": checkpoint["etag"],
                "sha256": checkpoint["sha256"],
            }
        },
    )
    monkeypatch.setattr(
        module.registry.backend, "capture_backend", lambda *_a, **_k: capture
    )
    from test_poc_registry_runner import repository

    monkeypatch.setattr(module.registry, "ecr_read", repository)
    evidence.update(gh=gh, workload=workload, capture=capture)
    return evidence


def inspect_registry(value, command="plan"):
    return module.inspect_registry(
        value["source"],
        value["workload"],
        AUTHORITY,
        command,
        gh=value["gh"],
        download=lambda identifier: value["archives"][identifier],
    )


@pytest.mark.parametrize("command", ["plan", "up-plan", "drift"])
def test_original_registry_verifier_and_actual_graph_are_reused(
    registry_evidence, command
):
    anchor = inspect_registry(registry_evidence, command)
    assert anchor.binding.registry_phase_receipt_id == 301
    assert anchor.checkpoint == registry_evidence["observation"]["checkpoint"]
    assert "checkpoint=" not in repr(anchor)


@pytest.mark.parametrize(
    "fault",
    [
        "issuer",
        "version",
        "hash",
        "graph",
        "empty",
        "receipt",
        "blob",
        "digest",
        "command",
    ],
)
def test_registry_forgery_and_native_movement_reject(registry_evidence, fault):
    value = registry_evidence
    if fault == "issuer":
        value["deployment"]["creator"]["login"] = "foreign[bot]"
    elif fault in ("version", "hash"):
        value["capture"].summary["state"][
            "VersionId" if fault == "version" else "sha256"
        ] = "different"
    elif fault == "graph":
        value["capture"].resources[-1]["inputs"]["forceDelete"] = True
    elif fault == "empty":
        value["capture"].resources.clear()
    elif fault == "receipt":
        original = value["gh"]
        calls = 0

        def moved(endpoint, *args):
            nonlocal calls
            result = original(endpoint, *args)
            if endpoint.endswith("/deployments/301"):
                calls += 1
                if calls > 1:
                    result["extra"] = True
            return result

        value["gh"] = moved
    elif fault in ("blob", "digest"):
        value["deployment"]["payload"]["observation"]["source"][
            "blob_sha" if fault == "blob" else "contract_sha256"
        ] = "f" * (40 if fault == "blob" else 64)
    with pytest.raises((ValueError, KeyError)):
        inspect_registry(value, "destroy" if fault == "command" else "plan")


@pytest.fixture
def publisher(registry_evidence):
    contract = copy.deepcopy(registry_evidence["workload"])
    release = contract["workload"]["release"]
    contract["workload"]["central"]["publisher_workflow_path"] = (
        module.PUBLISHER_WORKFLOW
    )
    release["workflow_ref"] = (
        f"{module.APP_REPOSITORY}/{module.PUBLISHER_WORKFLOW}@refs/heads/main"
    )
    run_id = release["publisher_run_id"]
    now = datetime.now(timezone.utc) - timedelta(minutes=5)

    def stamp(seconds):
        return (now + timedelta(seconds=seconds)).isoformat()

    actor = {"id": 77, "login": "promotion-app[bot]", "type": "Bot"}
    repository = {
        "id": module.APP_ID,
        "full_name": module.APP_REPOSITORY,
        "owner": {"id": 114362548},
    }
    run = {
        "id": run_id,
        "run_attempt": 1,
        "event": "workflow_dispatch",
        "path": module.PUBLISHER_WORKFLOW,
        "head_branch": "main",
        "head_sha": AUTHORITY.publisher_workflow_sha,
        "status": "completed",
        "conclusion": "success",
        "repository": repository,
        "head_repository": repository,
        "actor": actor,
        "triggering_actor": actor,
    }
    jobs = [
        {
            "id": 10 + index,
            "name": name,
            "run_id": run_id,
            "head_sha": AUTHORITY.publisher_workflow_sha,
            "status": "completed",
            "conclusion": "success",
            "started_at": stamp(index * 20),
            "completed_at": stamp(index * 20 + 15),
        }
        for index, name in enumerate(module.JOB_NAMES)
    ]
    common = {
        "repository": module.APP_REPOSITORY,
        "source_sha": release["source_sha"],
        "publisher_run_id": run_id,
        "publisher_run_attempt": 1,
        "workflow_sha": AUTHORITY.publisher_workflow_sha,
    }
    build = {"artifact_id": 104, "archive_sha256": "e" * 64, "file_sha256": "f" * 64}
    quality = {
        **common,
        "schema_version": "poc-quality-v1",
        "quality_job_id": 10,
        "command": "make ci",
        "conclusion": "success",
    }
    provenance = {
        **common,
        "schema_version": "poc-build-provenance-v1",
        "platform": release["platform"],
        "build_job_id": 11,
        "build_artifact": build,
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
    metadata, archives = {}, {}

    def put(identifier, prefix, member, value, created=45):
        payload = encoded(value)
        archive = zip_bytes(payload, member)
        archives[str(identifier)] = archive
        metadata[identifier] = {
            "id": identifier,
            "name": f"{prefix}-{run_id}-1",
            "expired": False,
            "digest": "sha256:" + sha(archive),
            "size_in_bytes": len(archive),
            "created_at": stamp(created),
            "expires_at": stamp(10000),
            "workflow_run": {
                "id": run_id,
                "repository_id": module.APP_ID,
                "head_repository_id": module.APP_ID,
                "head_branch": "main",
                "head_sha": AUTHORITY.publisher_workflow_sha,
            },
        }
        return {
            "artifact_id": identifier,
            "archive_sha256": sha(archive),
            "file_sha256": sha(payload),
        }

    release["quality_evidence"] = put(
        101, "poc-quality-evidence", "quality.json", quality
    )
    release["provenance"] = put(
        102, "poc-build-provenance", "provenance.json", provenance
    )
    put(103, "poc-release-manifest", "release-manifest.json", release)
    put(104, "poc-image-build", "build.json", {}, created=25)
    metadata[104]["digest"] = "sha256:" + build["archive_sha256"]
    data = {
        "contract": contract,
        "run": run,
        "jobs": jobs,
        "metadata": metadata,
        "archives": archives,
        "quality": quality,
        "provenance": provenance,
        "actor": actor,
        "put": put,
    }

    def gh(endpoint, *args):
        if endpoint.startswith("apps/"):
            return {"id": AUTHORITY.app_id, "slug": AUTHORITY.app_slug}
        if endpoint.startswith("users/"):
            return copy.deepcopy(data["actor"])
        if "/attempts/1/jobs?" in endpoint:
            assert args == ("--paginate", "--slurp")
            return [{"jobs": copy.deepcopy(data["jobs"])}]
        if "/artifacts?" in endpoint:
            return [{"artifacts": copy.deepcopy(list(metadata.values()))}]
        if "/actions/artifacts/" in endpoint:
            return copy.deepcopy(metadata[int(endpoint.rsplit("/", 1)[1])])
        assert endpoint == f"{module.APP_API}/actions/runs/{run_id}"
        return copy.deepcopy(data["run"])

    data["gh"] = gh
    return data


def inspect_release(value):
    return module.inspect_release(
        value["contract"],
        AUTHORITY,
        gh=value["gh"],
        download=lambda identifier: value["archives"][identifier],
    )


def test_complete_original_release_chain_and_default_private_adapters(
    publisher, monkeypatch
):
    expected = sha(encoded(publisher["contract"]["workload"]["release"]))
    assert inspect_release(publisher) == expected
    monkeypatch.setattr(module, "_github", publisher["gh"])
    monkeypatch.setattr(
        module, "_app_download", lambda identifier: publisher["archives"][identifier]
    )
    assert module.inspect_release(publisher["contract"], AUTHORITY) == expected


@pytest.mark.parametrize(
    "suffix", ["/103", "/104", "/attempts/1/jobs?per_page=100", "/actions/runs/1"]
)
def test_release_metadata_races_fail_closed(publisher, suffix):
    original = publisher["gh"]
    count = 0

    def gh(endpoint, *args):
        nonlocal count
        value = original(endpoint, *args)
        if endpoint.endswith(suffix):
            count += 1
            if count >= 2:
                if isinstance(value, list):
                    value[0]["jobs"][0]["id"] += 100
                else:
                    value["changed"] = True
        return value

    publisher["gh"] = gh
    with pytest.raises(ValueError):
        inspect_release(publisher)


@pytest.mark.parametrize(
    "fault",
    [
        "actor",
        "attempt",
        "workflow",
        "repository",
        "jobs",
        "duplicate-job",
        "job-id",
        "job-time",
        "job-order",
        "manifest-name",
        "expired",
        "wrong-producer",
        "archive",
        "size",
        "created",
        "quality",
        "provenance",
        "manifest",
        "reference",
        "build-digest",
        "build-size",
        "build-time",
    ],
)
def test_release_native_and_byte_substitution_reject(publisher, fault):
    p = publisher
    mutations = {
        "actor": (p["run"], "actor", {"id": 88, "login": "human", "type": "User"}),
        "attempt": (p["run"], "run_attempt", 2),
        "workflow": (p["run"], "head_sha", "c" * 40),
        "repository": (p["run"]["repository"], "id", 1),
        "duplicate-job": (p["jobs"][1], "name", p["jobs"][0]["name"]),
        "job-id": (p["jobs"][0], "id", True),
        "job-time": (p["jobs"][0], "started_at", p["jobs"][2]["started_at"]),
        "job-order": (p["jobs"][0], "completed_at", p["jobs"][2]["completed_at"]),
        "manifest-name": (p["metadata"][103], "name", "foreign"),
        "expired": (p["metadata"][103], "expired", True),
        "wrong-producer": (p["metadata"][103]["workflow_run"], "id", 999999),
        "archive": (p["archives"], "103", b"different"),
        "size": (p["metadata"][103], "size_in_bytes", True),
        "created": (p["metadata"][103], "created_at", p["jobs"][0]["started_at"]),
        "build-digest": (p["metadata"][104], "digest", "sha256:" + "a" * 64),
        "build-size": (p["metadata"][104], "size_in_bytes", 8 * 1024**3),
        "build-time": (p["metadata"][104], "created_at", p["jobs"][2]["started_at"]),
    }
    if fault in mutations:
        target, key, value = mutations[fault]
        target[key] = value
    elif fault == "jobs":
        p["jobs"].pop()
    elif fault in ("quality", "provenance"):
        doc = p[fault]
        doc["source_sha"] = "d" * 40
        field = "quality_evidence" if fault == "quality" else "provenance"
        identifier = 101 if fault == "quality" else 102
        prefix = (
            "poc-quality-evidence" if fault == "quality" else "poc-build-provenance"
        )
        p["contract"]["workload"]["release"][field] = p["put"](
            identifier, prefix, fault + ".json", doc
        )
        p["put"](
            103,
            "poc-release-manifest",
            "release-manifest.json",
            p["contract"]["workload"]["release"],
        )
    elif fault == "manifest":
        p["put"](103, "poc-release-manifest", "release-manifest.json", {})
    elif fault == "reference":
        p["contract"]["workload"]["release"]["provenance"]["file_sha256"] = "a" * 64
        p["put"](
            103,
            "poc-release-manifest",
            "release-manifest.json",
            p["contract"]["workload"]["release"],
        )
    with pytest.raises((ValueError, KeyError)):
        inspect_release(p)


def test_protected_authority_and_fixed_binary_context(monkeypatch):
    environment = {
        "GOVERNANCE_PROMOTION_APP_ID": "1234",
        "GOVERNANCE_PROMOTION_APP_SLUG": "promotion-app",
        "POC_REGISTRY_WORKFLOW_SHA": "a" * 40,
        "POC_PUBLISHER_WORKFLOW_SHA": "b" * 40,
    }
    assert module.authority_from_environment(environment) == AUTHORITY
    for key in environment:
        with pytest.raises(ValueError):
            module.authority_from_environment(
                {k: v for k, v in environment.items() if k != key}
            )
    with pytest.raises(ValueError):
        module._authority({})
    with pytest.raises(ValueError):
        module._authority(module.Authority(True, "app", "a" * 40, "b" * 40))
    monkeypatch.setenv("HOME", "/private/root")
    monkeypatch.setenv("GH_TOKEN", "synthetic")
    monkeypatch.setenv("GH_HOST", "foreign.invalid")
    calls = []
    monkeypatch.setattr(
        module,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or b'{"ok":true}',
    )
    assert module._github("repos/example") == {"ok": True}
    assert module._download("123") == b'{"ok":true}'
    assert module._app_download("123") == b'{"ok":true}'
    assert all(
        c[0][:4] == ["/usr/bin/gh", "api", "--hostname", "api.github.com"]
        for c in calls
    )
    assert all(
        set(c[1]["env"]) == {"PATH", "HOME", "GH_CONFIG_DIR", "GH_TOKEN"}
        and c[1]["cwd"] == Path("/trusted")
        for c in calls
    )


def test_combined_path_stops_before_any_workload_program(monkeypatch):
    calls = []
    monkeypatch.setattr(
        module, "inspect_registry", lambda *_: calls.append("registry") or "same"
    )
    monkeypatch.setattr(module, "inspect_release", lambda *_: calls.append("release"))
    monkeypatch.setattr(
        module.images, "inspect_images", lambda *_: calls.append("images")
    )
    monkeypatch.setattr(
        module.capabilities,
        "inspect_capabilities",
        lambda *_: calls.append("capabilities"),
    )
    with pytest.raises(ValueError, match="native-image-capability-and-plan"):
        module.inspect_workload({}, {}, AUTHORITY, "plan")

    assert calls == ["registry", "release", "images", "capabilities", "registry"]
    values = iter(("old", "changed"))
    monkeypatch.setattr(module, "inspect_registry", lambda *_: next(values))
    with pytest.raises(ValueError, match="prior-changed"):
        module.inspect_workload({}, {}, AUTHORITY, "plan")


def test_worker_reaches_real_receipt_release_and_native_graph_checks(
    publisher, registry_evidence, monkeypatch
):
    import service_execution_worker as worker

    environment = {
        "GOVERNANCE_PROMOTION_APP_ID": "1234",
        "GOVERNANCE_PROMOTION_APP_SLUG": "promotion-app",
        "POC_REGISTRY_WORKFLOW_SHA": "a" * 40,
        "POC_PUBLISHER_WORKFLOW_SHA": "b" * 40,
        "POC_SOURCE_ARTIFACT_ID": "102",
        "POC_SOURCE_ARCHIVE_SHA256": "c" * 64,
        "POC_SOURCE_SHA256": "d" * 64,
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    source = registry_evidence["source"]
    monkeypatch.setenv("GITHUB_SHA", source["source"]["base_sha"])
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (source, publisher["contract"]),
    )
    calls = []

    def gh(endpoint, *args):
        calls.append(endpoint)
        implementation = (
            registry_evidence["gh"]
            if endpoint.startswith(module.artifacts.API + "/")
            else publisher["gh"]
        )
        return implementation(endpoint, *args)

    monkeypatch.setattr(module, "_github", gh)
    monkeypatch.setattr(
        module, "_download", lambda key: registry_evidence["archives"][key]
    )
    monkeypatch.setattr(module, "_app_download", lambda key: publisher["archives"][key])
    monkeypatch.setattr(
        module.images, "inspect_images", lambda *_: calls.append("images")
    )
    monkeypatch.setattr(
        module.capabilities,
        "inspect_capabilities",
        lambda *_: calls.append("capabilities"),
    )
    monkeypatch.setattr(
        worker.registry, "execute", lambda *_a, **_k: pytest.fail("program dispatched")
    )
    with pytest.raises(
        ValueError, match="native-image-capability-and-plan-gates-required"
    ):
        worker._test(None, "plan", source["source"]["head_sha"])
    assert any("/deployments/301" in value for value in calls)
    assert any("/attempts/1/jobs" in value for value in calls)
    assert any(module.APP_API + "/actions/artifacts/" in value for value in calls)
    assert "images" in calls
    assert "capabilities" in calls


def test_native_image_failure_stops_before_state_recheck_and_program(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "inspect_registry", lambda *_: calls.append("registry"))
    monkeypatch.setattr(module, "inspect_release", lambda *_: calls.append("release"))

    def reject(_contract):
        calls.append("images")
        raise ValueError("image-read-failures")

    monkeypatch.setattr(module.images, "inspect_images", reject)
    with pytest.raises(ValueError, match="image-read-failures"):
        module.inspect_workload({}, {}, AUTHORITY, "up-plan")
    assert calls == ["registry", "release", "images"]


def test_native_capability_failure_stops_before_state_recheck(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "inspect_registry", lambda *_: calls.append("registry"))
    monkeypatch.setattr(module, "inspect_release", lambda *_: calls.append("release"))
    monkeypatch.setattr(
        module.images, "inspect_images", lambda *_: calls.append("images")
    )

    def reject(_contract):
        calls.append("capabilities")
        raise ValueError("workload-execution-pull-decision")

    monkeypatch.setattr(module.capabilities, "inspect_capabilities", reject)
    with pytest.raises(ValueError, match="execution-pull-decision"):
        module.inspect_workload({}, {}, AUTHORITY, "plan")
    assert calls == ["registry", "release", "images", "capabilities"]


def test_authority_inputs_are_root_only_and_workflow_protected(installed):
    import service_execution_host as host
    import yaml

    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/self-deploy.yml").read_text())
    keys = (
        "GOVERNANCE_PROMOTION_APP_ID",
        "GOVERNANCE_PROMOTION_APP_SLUG",
        "POC_REGISTRY_WORKFLOW_SHA",
        "POC_PUBLISHER_WORKFLOW_SHA",
    )
    for job in ("test_preview", "test_apply", "test_post_apply_drift"):
        steps = workflow["jobs"][job]["steps"]
        launcher = [
            step for step in steps if "POC_SOURCE_SHA256" in step.get("env", {})
        ]
        assert len(launcher) == 1
        assert all(launcher[0]["env"][key] == "${{ vars." + key + " }}" for key in keys)
    assert all(key in host.FIELDS for key in keys)
    port, _ = installed
    assert all(key not in port.environment for key in keys)


@pytest.fixture(autouse=True)
def isolated_mail_metadata(monkeypatch):
    """These driver tests isolate SES/DNS; native bindings have their own suite."""
    import poc_mail_prerequisite as mail

    monkeypatch.setattr(mail, "inspect_inventory", lambda *_: None)
    monkeypatch.setattr(mail, "inspect_identity", lambda **_: None)
