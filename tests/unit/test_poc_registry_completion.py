"""Synthetic native/API boundaries; no AWS, App token or deployment is used."""

import copy
import importlib
import os
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import test_poc_registry_phase_entrypoint as phase
import test_poc_registry_plan as graph
import test_poc_registry_runner as driver
from test_poc_source_artifact import prepared as prepared
from test_poc_source_artifact import zip_bytes

module = importlib.import_module("poc_registry_completion")


def encoded(value):
    return module._canonical(value) + b"\n"


def set_references(monkeypatch, references):
    for kind, reference in references.items():
        for field, value in reference.items():
            monkeypatch.setenv(f"POC_{kind}_{field.upper()}", str(value))


@pytest.fixture
def evidence(prepared, monkeypatch):
    source = prepared["source"]
    contract = phase.contract()
    sha = prepared["environment"]["GITHUB_SHA"]
    source["request"]["command"] = "up"
    source["source"]["base_sha"] = source["review"]["base_sha"] = sha
    source["source"]["contract_sha256"] = module._digest(module._canonical(contract))
    source_raw = encoded(source)
    source_zip = zip_bytes(source_raw)
    reference = module._reference(
        "102", module._digest(source_zip), module._digest(source_raw)
    )
    now = datetime.now(timezone.utc) - timedelta(minutes=2)
    observed = {
        "kind": module.OBSERVATION_KIND,
        "run_id": 101,
        "run_attempt": 1,
        "workflow_sha": sha,
        "source": source["source"],
        "source_artifact": reference,
        "observed_at": (now + timedelta(seconds=25)).isoformat(),
        "checkpoint": {
            "version": "version/+==",
            "etag": '"' + "e" * 32 + '"',
            "sha256": "f" * 64,
        },
        "registry_controls_sha256": module._digest(
            module._canonical(
                {
                    "registries": module.runtime.graph.REGISTRIES,
                    "mail_identity": module.runtime.graph.mail.DECLARATION,
                    "tags": module.runtime.graph.DEFAULT_TAGS,
                }
            )
        ),
    }
    raw = encoded(observed)
    archive = zip_bytes(raw, "observation.json")
    observation_reference = module._reference(
        "103", module._digest(archive), module._digest(raw)
    )
    metadata = {}
    for identifier, name, content in (
        (102, "poc-phase-source-101-1", source_zip),
        (103, "poc-registry-observation-101-1", archive),
    ):
        metadata[identifier] = {
            **prepared["metadata"],
            "id": identifier,
            "name": name,
            "digest": "sha256:" + module._digest(content),
            "size_in_bytes": len(content),
        }
    metadata[103]["created_at"] = (now + timedelta(seconds=27)).isoformat()
    jobs = [
        {
            "id": 200 + index,
            "name": name,
            "run_id": 101,
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
            "started_at": (now + timedelta(seconds=index * 10)).isoformat(),
            "completed_at": (now + timedelta(seconds=index * 10 + 9)).isoformat(),
        }
        for index, name in enumerate((*module.JOBS, module.PROOF_JOB))
    ]
    issuer = {
        "performed_via_github_app": {"id": 1234, "slug": "promotion-app"},
        "creator": {"login": "promotion-app[bot]", "type": "Bot"},
    }
    proof = {
        "kind": module.KIND,
        "repository": module.source_api.REPOSITORY,
        "observation_artifact": observation_reference,
        "observation": observed,
        "jobs": {job["name"]: job["id"] for job in jobs[:3]},
    }
    deployment = {
        "id": 301,
        "sha": source["source"]["head_sha"],
        "environment": module.ENVIRONMENT,
        "task": module.TASK,
        "production_environment": False,
        "transient_environment": False,
        "payload": proof,
        **copy.deepcopy(issuer),
    }
    status = {
        "state": "success",
        "environment": module.ENVIRONMENT,
        "log_url": f"https://github.com/{module.source_api.REPOSITORY}/actions/runs/101",
        **copy.deepcopy(issuer),
    }
    record = {
        "source": source,
        "contract": contract,
        "source_reference": reference,
        "observation": observed,
        "reference": observation_reference,
        "metadata": metadata,
        "archives": {"102": source_zip, "103": archive},
        "jobs": jobs,
        "proof": proof,
        "deployment": deployment,
        "statuses": [[status]],
        "run": prepared["run"],
        "calls": [],
    }

    def gh(endpoint, *arguments):
        record["calls"].append(endpoint)
        if "/actions/artifacts/" in endpoint:
            return metadata[int(endpoint.rsplit("/", 1)[1])]
        if endpoint.endswith("/actions/runs/101"):
            return record["run"]
        if "/attempts/1/jobs" in endpoint:
            assert arguments == ("--paginate", "--slurp")
            return [{"total_count": len(record["jobs"]), "jobs": record["jobs"]}]
        if endpoint.endswith("/deployment-branch-policies"):
            return {
                "total_count": 1,
                "branch_policies": [{"name": "main", "type": "branch"}],
            }
        if "/environments/" in endpoint:
            return module.boundary.payload()
        if "/statuses?" in endpoint:
            assert arguments == ("--paginate", "--slurp")
            return record["statuses"]
        assert endpoint.endswith("/deployments/301"), endpoint
        return record["deployment"]

    record["gh"] = gh
    monkeypatch.setattr(module.runtime.preflight, "gh", gh)
    monkeypatch.setattr(
        module.source_api,
        "_download_zip",
        lambda identifier: record["archives"][identifier],
    )
    monkeypatch.setattr(
        module.source_api, "load_verified_contract", lambda **_: (source, contract)
    )
    monkeypatch.setattr(module.runtime, "_trusted_root", lambda: sha)
    monkeypatch.setattr(
        module.runtime, "_review", lambda _: record["calls"].append("review")
    )
    monkeypatch.setenv("GITHUB_JOB", "test_registry_proof")
    set_references(
        monkeypatch, {"SOURCE": reference, "OBSERVATION": observation_reference}
    )
    return record


def verify(evidence, **changes):
    evidence["run"].update(status="completed", conclusion="success")
    return module.verify_completion(
        301,
        **{
            "app_id": 1234,
            "app_slug": "promotion-app",
            "trusted_workflow_sha": "a" * 40,
            "registry_contract": evidence["contract"],
            "gh": evidence["gh"],
            "download": lambda identifier: evidence["archives"][identifier],
            **changes,
        },
    )


def test_actual_artifact_codec_prepare_and_historical_verifier(evidence):
    assert module.prepare() == evidence["proof"]
    evidence["calls"].clear()
    result = verify(evidence)
    assert result == module.contract_api.RegistryReleaseBinding(
        301, evidence["source"]["source"]["contract_sha256"], "version/+=="
    )
    assert not any("/pulls/" in path or "review" == path for path in evidence["calls"])
    assert any("/artifacts/102" in path for path in evidence["calls"])
    assert any("/artifacts/103" in path for path in evidence["calls"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_JOB", "test_apply"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_REF", "refs/pull/19/merge"),
        ("GITHUB_RUN_ATTEMPT", "2"),
    ],
)
def test_wrong_producer_context_fails_before_bulk_reads(
    evidence, monkeypatch, field, value
):
    monkeypatch.setenv(field, value)
    with pytest.raises(ValueError):
        module.prepare()
    assert not evidence["calls"]


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("request", "command", "plan"),
        ("request", "target_environment", "prod"),
        ("source", "base_sha", "f" * 40),
    ],
)
def test_current_source_admission_cannot_be_bypassed(evidence, target, field, value):
    evidence["source"][target][field] = value
    with pytest.raises(ValueError):
        module.prepare()


@pytest.mark.parametrize(
    "index,field,value",
    [
        (0, "conclusion", "failure"),
        (1, "status", "in_progress"),
        (2, "head_sha", "f" * 40),
        (2, "run_id", 999),
        (2, "id", True),
        (2, "started_at", "2999-01-01T00:00:00Z"),
        (3, "conclusion", "failure"),
    ],
)
def test_original_jobs_must_be_successful_ordered_and_same_run(
    evidence, index, field, value
):
    evidence["jobs"][index][field] = value
    with pytest.raises(ValueError):
        verify(evidence)


@pytest.mark.parametrize(
    "kind", ["missing", "duplicate", "order", "outside-observation", "pagination"]
)
def test_job_inventory_and_observation_window_are_complete(evidence, kind):
    if kind == "missing":
        evidence["jobs"].pop(1)
    elif kind == "duplicate":
        evidence["jobs"].append(copy.deepcopy(evidence["jobs"][1]))
    elif kind == "order":
        evidence["jobs"][1]["started_at"] = evidence["jobs"][0]["started_at"]
    elif kind == "outside-observation":
        evidence["jobs"][2]["completed_at"] = evidence["jobs"][2]["started_at"]
    else:
        gh = evidence["gh"]

        def incomplete(endpoint, *args):
            value = gh(endpoint, *args)
            if "/jobs?" in endpoint:
                value[0]["total_count"] += 1
            return value

        evidence["gh"] = incomplete
    with pytest.raises(ValueError):
        verify(evidence)


@pytest.mark.parametrize(
    "where,field,value",
    [
        ("deployment", "task", "deploy"),
        ("deployment", "environment", "test"),
        ("deployment", "production_environment", True),
        ("deployment", "sha", "f" * 40),
        ("status", "state", "failure"),
        ("status", "log_url", "https://foreign.invalid"),
    ],
)
def test_distinct_deployment_and_latest_status_binding(evidence, where, field, value):
    row = (
        evidence["deployment"] if where == "deployment" else evidence["statuses"][0][0]
    )
    row[field] = value
    with pytest.raises(ValueError):
        verify(evidence)


@pytest.mark.parametrize("where", ["deployment", "status"])
@pytest.mark.parametrize(
    "field,value", [("id", 15368), ("id", True), ("slug", "foreign")]
)
def test_wrong_or_ambiguous_app_identity(evidence, where, field, value):
    row = (
        evidence["deployment"] if where == "deployment" else evidence["statuses"][0][0]
    )
    row["performed_via_github_app"][field] = value
    with pytest.raises(ValueError):
        verify(evidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_attempt", 2),
        ("event", "pull_request"),
        ("head_sha", "f" * 40),
        ("head_branch", "foreign"),
        ("path", "foreign.yml"),
    ],
)
def test_historical_run_cannot_be_substituted(evidence, field, value):
    evidence["run"][field] = value
    with pytest.raises(ValueError):
        verify(evidence)


@pytest.mark.parametrize(
    "identifier,field,value",
    [
        (102, "expired", True),
        (103, "expired", True),
        (103, "name", "foreign"),
        (103, "id", True),
        (103, "digest", "sha256:" + "f" * 64),
    ],
)
def test_original_artifacts_must_still_be_authentic_and_available(
    evidence, identifier, field, value
):
    evidence["metadata"][identifier][field] = value
    with pytest.raises(ValueError):
        verify(evidence)


def test_corrupt_archive_or_member_is_never_extracted(evidence):
    evidence["archives"]["103"] = b"bad-private-value"
    with pytest.raises(ValueError, match="completion"):
        verify(evidence)


def test_wrong_registry_or_controller_authority(evidence):
    with pytest.raises(ValueError):
        verify(evidence, trusted_workflow_sha="f" * 40)
    changed = copy.deepcopy(evidence["contract"])
    changed["registries"]["web"]["logical_name"] = "other-repository"
    with pytest.raises(ValueError):
        verify(evidence, registry_contract=changed)


def test_fresh_observer_uses_real_graph_without_dispatch(evidence, monkeypatch):
    monkeypatch.setenv("GITHUB_JOB", "test_registry_observation")
    state = {
        "kind": "observed_checkpoint",
        "VersionId": "version/+==",
        "ETag": '"' + "e" * 32 + '"',
        "sha256": "f" * 64,
    }
    capture = module.runtime.backend.PrivateBackendCapture(
        summary={"state": state, "observed_at": evidence["observation"]["observed_at"]},
        resources=list(graph.states().values()),
    )
    monkeypatch.setattr(
        module.runtime.backend, "capture_backend", lambda *a, **k: capture
    )
    monkeypatch.setattr(module.runtime, "ecr_read", driver.repository)
    monkeypatch.setattr(
        module,
        "_tags",
        lambda _: {
            "tags": [
                {"Key": key, "Value": value}
                for key, value in module.runtime.graph.DEFAULT_TAGS.items()
            ]
        },
    )
    monkeypatch.setattr(
        module.runtime.runner,
        "_dispatch_command",
        lambda *a, **k: pytest.fail("observer must never start Pulumi"),
    )
    assert module.observe(evidence["source_reference"]) == evidence["observation"]
    capture.resources.pop()
    with pytest.raises(ValueError):
        module.observe(evidence["source_reference"])


@pytest.mark.parametrize(
    "tags",
    [
        [],
        [{"Key": "foreign", "Value": "value"}],
        [{"Key": "Owner", "Value": "foreign"}] * 7,
        None,
    ],
)
def test_native_tags_must_be_complete_exact_and_unique(monkeypatch, tags):
    monkeypatch.setattr(module, "_tags", lambda _: {"tags": tags})
    with pytest.raises(ValueError):
        module._native_tags()


def test_native_tags_transport_is_finite_and_no_retry(monkeypatch):
    calls = []

    def run(argv, **options):
        calls.append((argv, options))
        assert options["timeout"] == 60 and options["env"]["AWS_MAX_ATTEMPTS"] == "1"
        return SimpleNamespace(returncode=0, stdout=b'{"tags":[]}', stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module._tags("user-service-test-web") == {"tags": []}
    assert calls[0][0][:3] == ["aws", "ecr", "list-tags-for-resource"]
    with pytest.raises(ValueError):
        module._tags("foreign")
    assert len(calls) == 1


def test_publish_exact_distinct_record_and_readback(evidence, monkeypatch):
    writes = []

    def write(endpoint, payload):
        writes.append((endpoint, payload))
        return (
            evidence["deployment"]
            if endpoint.endswith("/deployments")
            else evidence["statuses"][0][0]
        )

    monkeypatch.setattr(module, "_write", write)
    assert (
        module.publish(evidence["proof"], app_id=1234, app_slug="promotion-app") == 301
    )
    assert len(writes) == 2
    assert writes[0][1]["task"] == "registry-proof"
    assert writes[0][1]["environment"] == "poc-test-registry"
    assert [endpoint for endpoint, _ in writes] == [
        f"{module.API}/deployments",
        f"{module.API}/deployments/301/statuses",
    ]
    assert writes[1][1]["auto_inactive"] is False


def test_write_uses_only_dedicated_token_and_literal_json(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "READ_SYNTHETIC")
    monkeypatch.setenv("REGISTRY_PROOF_APP_TOKEN", "WRITE_SYNTHETIC")

    def run(argv, **options):
        assert argv == ["gh", "api", "endpoint", "--method", "POST", "--input", "-"]
        assert options["env"]["GH_TOKEN"] == "WRITE_SYNTHETIC"
        assert options["input"] == b'{"literal":"$(not-executed)"}'
        assert options["timeout"] == 60
        return SimpleNamespace(returncode=0, stdout=b'{"id":1}')

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module._write("endpoint", {"literal": "$(not-executed)"}) == {"id": 1}


@pytest.mark.parametrize("mode", ["observe", "prepare", "publish"])
def test_cli_outputs_only_fixed_reference_metadata(
    evidence, monkeypatch, tmp_path, capsys, mode
):
    monkeypatch.setattr(module, "OBSERVATION_PATH", tmp_path / "observation.json")
    monkeypatch.setattr(module, "PROOF_PATH", tmp_path / "proof.json")
    monkeypatch.setattr(module, "observe", lambda _: evidence["observation"])
    monkeypatch.setattr(module, "prepare", lambda: evidence["proof"])
    monkeypatch.setattr(module, "publish", lambda *a, **k: 301)
    monkeypatch.setenv("REGISTRY_PROOF_APP_ID", "1234")
    monkeypatch.setenv("REGISTRY_PROOF_APP_SLUG", "promotion-app")
    if mode == "publish":
        module.PROOF_PATH.write_bytes(encoded(evidence["proof"]))
    assert module.main([mode]) == 0
    assert capsys.readouterr().out.startswith(
        "registry_phase_receipt_id=" if mode == "publish" else "file_sha256="
    )


@pytest.mark.parametrize(
    "failure", [ValueError, EOFError, module.source_api.zipfile.BadZipFile]
)
def test_cli_failure_is_sanitized(monkeypatch, capsys, failure):
    monkeypatch.setattr(
        module, "prepare", lambda: (_ for _ in ()).throw(failure("PRIVATE"))
    )
    assert module.main(["prepare"]) == 1
    assert "PRIVATE" not in str(capsys.readouterr())


def test_cli_admit_has_no_file_or_aws_operation(
    evidence, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("GITHUB_JOB", "test_registry_observation")
    monkeypatch.chdir(tmp_path)
    assert module.main(["admit"]) == 0
    assert (
        capsys.readouterr().out == "VALID: TEST registry observation source admitted\n"
    )
    assert list(tmp_path.iterdir()) == []


def test_real_isolated_cli_fails_before_network(tmp_path):
    result = subprocess.run(
        [os.sys.executable, "-I", module.__file__, "prepare"],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr == "INVALID: TEST registry completion proof failed\n"


@pytest.mark.parametrize(
    "field,value",
    [
        ("app_id", True),
        ("app_id", 0),
        ("app_slug", "foreign/slug"),
        ("trusted_workflow_sha", "main"),
    ],
)
def test_invalid_verifier_authority_fails_before_api(evidence, field, value):
    with pytest.raises(ValueError):
        verify(evidence, **{field: value})
    assert evidence["calls"] == []


def test_stale_prepared_proof_cannot_reach_app_write(evidence, monkeypatch):
    changed = copy.deepcopy(evidence["proof"])
    changed["jobs"][module.JOBS[0]] += 1
    monkeypatch.setattr(
        module, "_write", lambda *a: pytest.fail("stale proof must not publish")
    )
    with pytest.raises(ValueError):
        module.publish(changed, app_id=1234, app_slug="promotion-app")


@pytest.mark.parametrize("case", ["caller", "version", "tags", "review"])
def test_fresh_native_observation_rejects_races_and_revocation(
    evidence, monkeypatch, case
):
    monkeypatch.setenv("GITHUB_JOB", "test_registry_observation")
    state = {
        "kind": "observed_checkpoint",
        "VersionId": "version/+==",
        "ETag": '"' + "e" * 32 + '"',
        "sha256": "f" * 64,
    }
    capture = module.runtime.backend.PrivateBackendCapture(
        summary={"state": state, "observed_at": evidence["observation"]["observed_at"]},
        resources=list(graph.states().values()),
    )
    calls = []

    def read(*args, **kwargs):
        calls.append("capture")
        if case == "caller":
            raise ValueError("wrong native caller")
        result = copy.deepcopy(capture)
        if case == "version" and len(calls) > 1:
            result.summary["state"]["VersionId"] = "changed"
        return result

    monkeypatch.setattr(module.runtime.backend, "capture_backend", read)
    monkeypatch.setattr(module.runtime, "ecr_read", driver.repository)
    monkeypatch.setattr(
        module,
        "_tags",
        lambda _: {
            "tags": [
                {"Key": key, "Value": "changed" if case == "tags" else value}
                for key, value in module.runtime.graph.DEFAULT_TAGS.items()
            ]
        },
    )
    if case == "review":
        monkeypatch.setattr(
            module.runtime,
            "_review",
            lambda _: (_ for _ in ()).throw(ValueError("revoked")),
        )
    with pytest.raises(ValueError):
        module.observe(evidence["source_reference"])


def test_artifact_upload_must_be_inside_actual_observation_job(evidence):
    evidence["metadata"][103]["created_at"] = datetime.now(timezone.utc).isoformat()
    with pytest.raises(ValueError):
        verify(evidence)


def test_wrong_bot_latest_status_and_empty_statuses_are_rejected(evidence):
    evidence["statuses"][0][0]["creator"]["type"] = "User"
    with pytest.raises(ValueError):
        verify(evidence)
    evidence["statuses"] = [[]]
    with pytest.raises(ValueError):
        verify(evidence)


@pytest.mark.parametrize("next_second", [False, True])
def test_observation_containment_uses_github_second_precision(evidence, next_second):
    original = module.source_api._timestamp(
        evidence["observation"]["observed_at"]
    ).replace(microsecond=0)
    captured = original + (
        timedelta(seconds=1) if next_second else timedelta(microseconds=900000)
    )
    evidence["observation"]["observed_at"] = captured.isoformat()
    evidence["metadata"][103]["created_at"] = original.isoformat()
    payload = encoded(evidence["observation"])
    archive = zip_bytes(payload, "observation.json")
    evidence["archives"]["103"] = archive
    evidence["reference"].update(
        archive_sha256=module._digest(archive), file_sha256=module._digest(payload)
    )
    evidence["metadata"][103].update(
        digest="sha256:" + module._digest(archive), size_in_bytes=len(archive)
    )
    if next_second:
        with pytest.raises(ValueError):
            verify(evidence)
    else:
        assert verify(evidence).registry_phase_receipt_id == 301
        assert evidence["observation"]["observed_at"] == captured.isoformat()


@pytest.fixture(autouse=True)
def isolated_mail_metadata(monkeypatch):
    """These driver tests isolate SES/DNS; native bindings have their own suite."""
    import poc_mail_prerequisite as mail

    monkeypatch.setattr(mail, "inspect_inventory", lambda *_: None)
    monkeypatch.setattr(mail, "inspect_identity", lambda **_: None)
