"""Synthetic dispatch API and credential boundaries; no remote write is performed."""

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
module = importlib.import_module("poc_publisher_dispatch")
SHA = "a" * 40
REPO = {
    "id": module.REPOSITORY_ID,
    "full_name": module.REPOSITORY,
    "owner": {"id": module.artifacts.admission.OWNER_ID},
    "default_branch": "main",
}
ACTOR = {"id": module.BOT_ID, "login": module.APP_SLUG + "[bot]", "type": "Bot"}


REVIEW_PARAMETERS = {
    "require_code_owner_review": True,
    "require_last_push_approval": True,
    "dismiss_stale_reviews_on_push": True,
    "required_review_thread_resolution": True,
    "required_approving_review_count": 1,
}


def protection_responses():
    return {
        module.API + "/environments/poc-test-images": {
            "can_admins_bypass": False,
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "prevent_self_review": True,
                    "reviewers": [{"type": "User", "reviewer": {"id": 9444106}}],
                }
            ],
        },
        module.API
        + "/environments/poc-test-images/deployment-branch-policies?per_page=100": {
            "total_count": 1,
            "branch_policies": [{"name": "main", "type": "branch"}],
        },
        "users/Kravalg": {"login": "Kravalg", "type": "User", "id": 9444106},
        module.API + "/rules/branches/main?per_page=100": [
            {
                "type": "pull_request",
                "parameters": copy.deepcopy(REVIEW_PARAMETERS),
                "ruleset_id": 601,
                "ruleset_source_type": "Repository",
                "ruleset_source": module.REPOSITORY,
            }
        ],
        module.API + "/rulesets/601": {
            "id": 601,
            "target": "branch",
            "source_type": "Repository",
            "source": module.REPOSITORY,
            "enforcement": "active",
            "rules": [
                {"type": "pull_request", "parameters": copy.deepcopy(REVIEW_PARAMETERS)}
            ],
        },
    }


@pytest.fixture
def state(monkeypatch):
    environment = {
        "GITHUB_JOB": "test_registry_dispatch",
        "POC_REGISTRY_RECEIPT_ID": "301",
        "POC_PUBLISHER_WORKFLOW_SHA": SHA,
    }
    proof = {
        "observation": {
            "run_id": 101,
            "workflow_sha": "b" * 40,
            "observed_at": "observed",
            "source": {"contract_sha256": "c" * 64},
            "checkpoint": {"version": "v1"},
        },
        "observation_artifact": {"artifact_id": 201},
    }
    values = {
        **protection_responses(),
        f"apps/{module.APP_SLUG}": {
            "id": module.APP_ID,
            "slug": module.APP_SLUG,
            "permissions": {"actions": "write"},
        },
        module.API: copy.deepcopy(REPO),
        module.API + "/git/ref/heads/main": {"object": {"sha": SHA, "type": "commit"}},
        module.ENDPOINT: {"id": 401, "path": module.WORKFLOW, "state": "active"},
        module.artifacts.API + "/actions/artifacts/201": {"created_at": "uploaded"},
    }
    calls = []
    monkeypatch.setattr(module.completion, "prepare", lambda env: proof)
    monkeypatch.setattr(
        module.completion, "_jobs", lambda *a, **kw: calls.append(("jobs", kw))
    )
    monkeypatch.setattr(
        module.completion, "_deployment", lambda *a: calls.append(("proof", a[1:]))
    )
    monkeypatch.setattr(
        module.completion.runtime.preflight, "gh", lambda endpoint: values[endpoint]
    )
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    return environment, values, calls


def test_prepare_reuses_proof_readback_and_completed_jobs(state):
    request, workflow = module.prepare()
    assert workflow == 401
    assert request == {
        "source_sha": SHA,
        "platform": "linux/amd64",
        "registry_phase_receipt_id": 301,
        "registry_contract_sha256": "c" * 64,
        "registry_checkpoint_version": "v1",
    }
    assert state[2][0][1]["completed"] is True
    assert state[2][1][0] == "proof"
    assert state[2][1][1][0] == 301
    assert state[2][1][1][-2:] == (module.APP_ID, module.APP_SLUG)


@pytest.mark.parametrize(
    "case",
    [
        "grant",
        "workflow",
        "inactive",
        "source",
        "pin",
        "job",
        "receipt",
        "owner",
        "app",
        "id",
    ],
)
def test_preflight_rejects_missing_grant_workflow_and_source_mismatch(state, case):
    env, values, _ = state
    if case == "grant":
        values[f"apps/{module.APP_SLUG}"]["permissions"]["actions"] = "read"
    elif case == "workflow":
        del values[module.ENDPOINT]
    elif case == "inactive":
        values[module.ENDPOINT]["state"] = "disabled_manually"
    elif case == "source":
        values[module.API + "/git/ref/heads/main"]["object"]["sha"] = "d" * 40
    elif case in {"pin", "job", "receipt"}:
        env[
            {
                "pin": "POC_PUBLISHER_WORKFLOW_SHA",
                "job": "GITHUB_JOB",
                "receipt": "POC_REGISTRY_RECEIPT_ID",
            }[case]
        ] = ""
    elif case == "owner":
        values[module.API]["owner"]["id"] += 1
    elif case == "app":
        values[f"apps/{module.APP_SLUG}"]["id"] += 1
    else:
        values[module.ENDPOINT]["id"] = True
    with pytest.raises((ValueError, KeyError)):
        module.prepare(env, gh=lambda endpoint: values[endpoint])


@pytest.fixture
def dispatch_api(state, monkeypatch):
    run = {
        "id": 501,
        "workflow_id": 401,
        "run_attempt": 1,
        "head_branch": "main",
        "head_sha": SHA,
        "event": "workflow_dispatch",
        "path": module.WORKFLOW,
        "repository": copy.deepcopy(REPO),
        "head_repository": copy.deepcopy(REPO),
        "actor": copy.deepcopy(ACTOR),
        "triggering_actor": copy.deepcopy(ACTOR),
    }
    values = {
        "installation/repositories?per_page=100": {
            "total_count": 1,
            "repositories": [copy.deepcopy(REPO)],
        },
        module.ENDPOINT + "/dispatches": {
            "workflow_run_id": 501,
            "run_url": f"https://api.github.com/{module.API}/actions/runs/501",
            "html_url": f"https://github.com/{module.REPOSITORY}/actions/runs/501",
        },
        module.API + "/actions/runs/501": run,
    }
    calls = []

    def api(endpoint, payload=None):
        calls.append((endpoint, payload))
        return values[endpoint]

    monkeypatch.setattr(module, "app_api", api)
    return values, calls


def test_dispatch_posts_once_and_reads_returned_run(dispatch_api):
    assert module.dispatch() == 501
    calls = dispatch_api[1]
    assert calls[1][0] == module.ENDPOINT + "/dispatches"
    assert calls[1][1]["ref"] == "main"
    assert json.loads(calls[1][1]["inputs"]["request"])["source_sha"] == SHA
    assert calls[-1][0] == module.API + "/actions/runs/501"
    assert len([payload for _, payload in calls if payload is not None]) == 1


@pytest.mark.parametrize(
    "endpoint,path,value",
    [
        ("/rules/branches/main?per_page=100", (), []),
        ("/rules/branches/main?per_page=100", (), [None]),
        ("/rules/branches/main?per_page=100", (), [{"type": "creation"}] * 100),
        ("/rules/branches/main?per_page=100", (0, "type"), "creation"),
        ("/rules/branches/main?per_page=100", (0, "ruleset_id"), True),
        ("/rules/branches/main?per_page=100", (0, "ruleset_source"), "Other/repo"),
        (
            "/rules/branches/main?per_page=100",
            (0, "ruleset_source_type"),
            "Organization",
        ),
        *[
            ("/rules/branches/main?per_page=100", (0, "parameters", field), False)
            for field in REVIEW_PARAMETERS
            if field != "required_approving_review_count"
        ],
        (
            "/rules/branches/main?per_page=100",
            (0, "parameters", "required_approving_review_count"),
            0,
        ),
        (
            "/rules/branches/main?per_page=100",
            (0, "parameters", "required_approving_review_count"),
            True,
        ),
        ("/rulesets/601", ("enforcement",), "evaluate"),
        ("/rulesets/601", ("enforcement",), "disabled"),
        ("/rulesets/601", ("target",), "tag"),
        ("/rulesets/601", ("source",), "Other/repo"),
        ("/rulesets/601", ("rules",), []),
        ("/environments/poc-test-images", ("can_admins_bypass",), True),
        ("/environments/poc-test-images", ("deployment_branch_policy",), None),
        (
            "/environments/poc-test-images",
            ("deployment_branch_policy",),
            {"protected_branches": True, "custom_branch_policies": False},
        ),
        ("/environments/poc-test-images", ("protection_rules",), []),
        (
            "/environments/poc-test-images",
            ("protection_rules", 0, "prevent_self_review"),
            False,
        ),
        ("/environments/poc-test-images", ("protection_rules", 0, "reviewers"), []),
        (
            "/environments/poc-test-images",
            ("protection_rules", 0, "reviewers", 0, "type"),
            "Team",
        ),
        (
            "/environments/poc-test-images",
            ("protection_rules", 0, "reviewers", 0, "reviewer", "id"),
            99,
        ),
        (
            "/environments/poc-test-images/deployment-branch-policies?per_page=100",
            ("total_count",),
            2,
        ),
        (
            "/environments/poc-test-images/deployment-branch-policies?per_page=100",
            ("branch_policies", 0, "name"),
            "*",
        ),
        (
            "/environments/poc-test-images/deployment-branch-policies?per_page=100",
            ("branch_policies", 0, "type"),
            "tag",
        ),
    ],
)
def test_weak_or_partial_protections_reject_before_post(
    state, dispatch_api, endpoint, path, value
):
    values = state[1]
    if path:
        target = values[module.API + endpoint]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    else:
        values[module.API + endpoint] = value
    with pytest.raises(ValueError):
        module.dispatch()
    assert all(payload is None for _, payload in dispatch_api[1])


@pytest.mark.parametrize("identifier", [True, 0, module.BOT_ID])
def test_reviewer_identity_rejects_invalid_or_app_identity(
    state, dispatch_api, identifier
):
    state[1]["users/Kravalg"]["id"] = identifier
    with pytest.raises(ValueError):
        module.dispatch()
    assert all(payload is None for _, payload in dispatch_api[1])


@pytest.mark.parametrize(
    "endpoint",
    [
        "/rules/branches/main?per_page=100",
        "/rulesets/601",
        "/environments/poc-test-images",
        "/environments/poc-test-images/deployment-branch-policies?per_page=100",
    ],
)
def test_unavailable_protection_metadata_never_dispatches(
    state, dispatch_api, endpoint
):
    del state[1][module.API + endpoint]
    with pytest.raises(KeyError):
        module.dispatch()
    assert all(payload is None for _, payload in dispatch_api[1])


def test_observable_rules_accept_redacted_bypass_list_with_independent_environment_gate(
    state,
):
    assert "bypass_actors" not in state[1][module.API + "/rulesets/601"]
    assert module.prepare()[1] == 401


@pytest.mark.parametrize(
    "case",
    ["scope", "rows", "empty", "id", "url", "source", "actor", "attempt", "repo"],
)
def test_dispatch_fails_closed_without_retry(dispatch_api, case):
    values, calls = dispatch_api
    result = values[module.ENDPOINT + "/dispatches"]
    run = values[module.API + "/actions/runs/501"]
    if case == "scope":
        values["installation/repositories?per_page=100"]["total_count"] = 2
    elif case == "rows":
        values["installation/repositories?per_page=100"]["repositories"] = []
    elif case == "empty":
        result.clear()
    elif case == "id":
        result["workflow_run_id"] = True
    elif case == "url":
        result["run_url"] = "https://example.invalid/run"
    elif case == "source":
        run["head_sha"] = "d" * 40
    elif case == "actor":
        run["triggering_actor"]["id"] += 1
    elif case == "attempt":
        run["run_attempt"] = 2
    else:
        run["head_repository"]["id"] += 1
    with pytest.raises((ValueError, KeyError)):
        module.dispatch()
    assert len([payload for _, payload in calls if payload is not None]) <= 1


@pytest.mark.parametrize("payload", [None, {"ref": "main"}])
def test_api_uses_only_separate_token_and_explicit_version(monkeypatch, payload):
    monkeypatch.setenv("PUBLISHER_DISPATCH_APP_TOKEN", "synthetic-dispatch")
    monkeypatch.setenv("REGISTRY_PROOF_APP_TOKEN", "synthetic-proof")

    def run(arguments, **kwargs):
        assert arguments[:5] == [
            "/usr/bin/gh",
            "api",
            "--hostname",
            "github.com",
            "endpoint",
        ]
        assert "X-GitHub-Api-Version: 2026-03-10" in arguments
        assert kwargs["env"] == {
            "PATH": "/usr/bin:/bin",
            "HOME": module.os.environ["HOME"],
            "GH_TOKEN": "synthetic-dispatch",
            "GH_PROMPT_DISABLED": "1",
        }
        assert kwargs["timeout"] == 60
        assert kwargs["input"] == (None if payload is None else b'{"ref":"main"}')
        return SimpleNamespace(returncode=0, stdout=b'{"ok":true}')

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.app_api("endpoint", payload) == {"ok": True}


@pytest.mark.parametrize(
    "code,body", [(1, b"private"), (0, b""), (0, b"x" * (1024 * 1024 + 1))]
)
def test_api_rejects_denial_empty_response_and_oversized_response(
    monkeypatch, code, body
):
    monkeypatch.setenv("PUBLISHER_DISPATCH_APP_TOKEN", "synthetic")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=code, stdout=body),
    )
    with pytest.raises(ValueError):
        module.app_api("endpoint")


@pytest.mark.parametrize("mode", ["prepare", "dispatch"])
def test_cli_success(monkeypatch, capsys, mode):
    monkeypatch.setattr(module, "prepare", lambda: None)
    monkeypatch.setattr(module, "dispatch", lambda: 501)
    assert module.main([mode]) == 0
    assert "501" in capsys.readouterr().out if mode == "dispatch" else True


def test_cli_sanitizes_failures(monkeypatch, capsys):
    def fail():
        raise subprocess.SubprocessError("private")

    monkeypatch.setattr(module, "dispatch", fail)
    assert module.main(["dispatch"]) == 1
    assert "private" not in capsys.readouterr().err
