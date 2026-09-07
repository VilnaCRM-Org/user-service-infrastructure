"""Preserve the reviewed shared administration CLI boundary in the scaffold."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def load_script_module(monkeypatch, name):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    importlib.invalidate_caches()
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def test_configure_github_repository_controls_payloads(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Build the GitHub admin-control payloads without applying them."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")
    existing_pull_request_rule = {
        "type": "pull_request",
        "parameters": {"required_approving_review_count": 2},
    }
    existing_code_quality_rule = {
        "type": "code_quality",
        "parameters": {"severity": "errors"},
    }
    existing_code_scanning_rule = {
        "type": "code_scanning",
        "parameters": {
            "code_scanning_tools": [
                {
                    "alerts_threshold": "errors",
                    "security_alerts_threshold": "high_or_higher",
                    "tool": "CodeQL",
                }
            ]
        },
    }

    payload = module.ruleset_payload(
        [
            existing_pull_request_rule,
            existing_code_quality_rule,
            existing_code_scanning_rule,
            {"type": "ignored_rule"},
        ],
        promotion_app_id=12345,
    )
    rules = {rule["type"]: rule for rule in payload["rules"]}
    contexts = [
        check["context"]
        for check in rules["required_status_checks"]["parameters"][
            "required_status_checks"
        ]
    ]

    assert contexts == list(module.REQUIRED_STATUS_CHECKS)  # nosec B101
    review_parameters = rules["pull_request"]["parameters"]
    assert review_parameters["required_approving_review_count"] == 2
    assert review_parameters["dismiss_stale_reviews_on_push"] is True
    assert review_parameters["require_code_owner_review"] is True
    assert review_parameters["require_last_push_approval"] is True
    assert rules["code_quality"] == existing_code_quality_rule  # nosec B101
    assert rules["code_scanning"] == existing_code_scanning_rule  # nosec B101
    assert module.prod_environment_payload(9444106) == {  # nosec B101
        "wait_timer": 0,
        "prevent_self_review": True,
        "reviewers": [{"type": "User", "id": 9444106}],
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
        "can_admins_bypass": False,
    }
    assert module.operations_alert_reconcile_environment_payload(  # nosec B101
        9444106
    ) == module.prod_environment_payload(9444106)

    monkeypatch.setattr(module, "_main_ruleset", lambda _repo: None)
    monkeypatch.setattr(module, "_github_user_id", lambda _reviewer: 9444106)
    assert (  # nosec B101
        module.main(
            [
                "--promotion-app-id",
                "12345",
                "--repo",
                "VilnaCRM-Org/bootstrap-infrastructure",
            ]
        )
        == 0
    )
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["prodEnvironment"]["reviewers"][0]["id"] == 9444106  # nosec B101
    assert rendered["operationsAlertReconcileEnvironment"]["reviewers"][0]["id"] == (  # nosec B101
        9444106
    )
    assert rendered["prodEnvironmentReviewerLogin"] == "Kravalg"  # nosec B101
    assert rendered["operationsAlertReconcileEnvironmentReviewerLogin"] == (  # nosec B101
        "Kravalg"
    )

    assert (  # nosec B101
        module.main(
            [
                "--promotion-app-id",
                "12345",
                "--repo",
                "VilnaCRM-Org/bootstrap-infrastructure",
                "--dry-run",
            ]
        )
        == 0
    )
    dry_run_rendered = json.loads(capsys.readouterr().out)
    assert (  # nosec B101
        dry_run_rendered["prodEnvironment"]["reviewers"][0]["id"] == 9444106
    )
    assert (  # nosec B101
        dry_run_rendered["operationsAlertReconcileEnvironment"]["reviewers"][0]["id"]
        == 9444106
    )
    assert dry_run_rendered["prodEnvironmentReviewerLogin"] == "Kravalg"  # nosec B101
    assert dry_run_rendered["operationsAlertReconcileEnvironmentReviewerLogin"] == (  # nosec B101
        "Kravalg"
    )

    with pytest.raises(SystemExit):
        module.main(
            [
                "--promotion-app-id",
                "12345",
                "--repo",
                "example/repo",
                "--apply",
                "--dry-run",
            ]
        )
    with pytest.raises(SystemExit):
        module.main(
            [
                "--promotion-app-id",
                "12345",
                "--repo",
                "example/repo",
                "--apply",
                "--verify-only",
            ]
        )
    with pytest.raises(SystemExit):
        module.main(
            [
                "--promotion-app-id",
                "12345",
                "--repo",
                "example/repo",
                "--dry-run",
                "--verify-only",
            ]
        )
    with pytest.raises(SystemExit) as help_exit:
        module.main(["--promotion-app-id", "12345", "--help"])
    assert help_exit.value.code == 0  # nosec B101
    help_text = capsys.readouterr().out
    assert "protected environment payloads" in help_text  # nosec B101
    assert "protected environment controls" in help_text  # nosec B101


def test_configure_github_repository_controls_verification_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify applied GitHub controls before reporting admin success."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")
    ruleset = module.ruleset_payload(promotion_app_id=12345)
    monkeypatch.setattr(module, "_evidence_environment_blockers", lambda repo: [])
    environment = {
        "prevent_self_review": True,
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
        "can_admins_bypass": False,
        "deployment_branch_policies": [{"name": "main", "type": "branch"}],
        "protection_rules": [
            {
                "type": "required_reviewers",
                "reviewers": [
                    {
                        "type": "User",
                        "reviewer": {"type": "User", "id": 9444106, "login": "Kravalg"},
                    }
                ],
            }
        ],
    }

    assert module._ruleset_verification_blockers(ruleset, promotion_app_id=12345) == []  # noqa: SLF001  # nosec B101
    assert (
        module._prod_environment_verification_blockers(  # noqa: SLF001  # nosec B101
            environment, 9444106
        )
        == []
    )
    assert (  # noqa: SLF001  # nosec B101
        module._operations_alert_reconcile_environment_verification_blockers(
            environment, 9444106
        )
        == []
    )
    missing_self_review_environment = {
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
        "can_admins_bypass": False,
        "deployment_branch_policies": [{"name": "main", "type": "branch"}],
        "reviewers": [{"type": "User", "id": 9444106}],
    }
    assert module._prod_environment_verification_blockers(  # noqa: SLF001
        missing_self_review_environment, 9444106
    ) == ["Production environment does not prevent self-review."]  # nosec B101
    nested_self_review_environment = {
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
        "can_admins_bypass": False,
        "deployment_branch_policies": [{"name": "main", "type": "branch"}],
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [
                    {
                        "type": "User",
                        "reviewer": {"type": "User", "id": 9444106, "login": "Kravalg"},
                    }
                ],
            },
            {"type": "branch_policy"},
        ],
    }
    assert (
        module._prod_environment_verification_blockers(  # noqa: SLF001  # nosec B101
            nested_self_review_environment, 9444106
        )
        == []
    )
    assert module._environment_reviewer_ids(  # noqa: SLF001  # nosec B101
        {"reviewers": [{"type": "User", "id": 9444106}]}
    ) == {9444106}
    assert (
        module._environment_reviewer_ids(  # noqa: SLF001  # nosec B101
            {
                "reviewers": ["invalid", {"type": "Team", "id": 1}],
                "protection_rules": [
                    "invalid",
                    {"reviewers": "invalid"},
                    {"reviewers": [{"type": "User", "reviewer": {"login": "missing"}}]},
                ],
            }
        )
        == set()
    )
    assert module._required_status_contexts({"rules": "invalid"}) == set()  # noqa: SLF001  # nosec B101
    assert module._required_status_contexts(  # noqa: SLF001  # nosec B101
        {
            "rules": [
                "invalid",
                {"type": "required_status_checks", "parameters": "invalid"},
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": "invalid"},
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": ["invalid", {}, {"name": "Unit"}]
                    },
                },
            ]
        }
    ) == {"Unit"}
    assert not module._ruleset_has_pull_request_reviews(  # noqa: SLF001  # nosec B101
        {"rules": "invalid"}
    )
    assert not module._ruleset_has_pull_request_reviews(  # noqa: SLF001  # nosec B101
        {"rules": [{"type": "pull_request", "parameters": "invalid"}]}
    )

    bad_ruleset = {"rules": [{"type": "deletion"}]}
    ruleset_blockers = module._ruleset_verification_blockers(  # noqa: SLF001
        bad_ruleset, promotion_app_id=12345
    )
    assert "missing required status checks" in ruleset_blockers[0]  # nosec B101
    assert "pull request reviews" in " ".join(ruleset_blockers)  # nosec B101
    environment_blockers = module._prod_environment_verification_blockers(  # noqa: SLF001
        {
            "prevent_self_review": False,
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
            "protection_rules": [],
        },
        9444106,
    )
    assert "prevent self-review" in environment_blockers[0]  # nosec B101
    assert "main branch" in environment_blockers[1]  # nosec B101
    assert "configured reviewer" in " ".join(environment_blockers)  # nosec B101
    missing_policy_blockers = module._prod_environment_verification_blockers(  # noqa: SLF001
        {"prevent_self_review": True, "protection_rules": []},
        9444106,
    )
    assert "main branch" in missing_policy_blockers[0]  # nosec B101
    assert module._ruleset_verification_blockers(None, promotion_app_id=12345) == [  # noqa: SLF001  # nosec B101
        "Active main branch ruleset was not found after apply."
    ]
    assert module._prod_environment_verification_blockers(  # noqa: SLF001  # nosec B101
        None, 9444106
    ) == ["Production environment was not readable after apply."]
    assert module._operations_alert_reconcile_environment_verification_blockers(  # noqa: SLF001  # nosec B101
        None, 9444106
    ) == ["Operations alert reconcile environment was not readable after apply."]

    monkeypatch.setattr(module, "_main_ruleset", lambda _repo: ruleset)
    monkeypatch.setattr(
        module,
        "_run_gh_api",
        lambda _args, **_kwargs: (
            {"total_count": 1, "branch_policies": [{"name": "main", "type": "branch"}]}
            if _args[0].endswith("/deployment-branch-policies")
            else environment
        ),
    )
    assert module._verify_applied_controls(  # noqa: SLF001  # nosec B101
        "example/repo", 9444106, promotion_app_id=12345
    ) == {
        "requiredStatusChecks": sorted(module.REQUIRED_STATUS_CHECKS),
        "prodReviewerId": 9444106,
        "prodEnvironment": "prod",
        "operationsAlertReconcileReviewerId": 9444106,
        "operationsAlertReconcileEnvironment": "operations-alert-reconcile",
        "governanceReviewerId": 9444106,
        "governanceEnvironment": "governance",
    }

    monkeypatch.setattr(module, "_main_ruleset", lambda _repo: bad_ruleset)
    with pytest.raises(RuntimeError, match="missing required status checks"):
        module._verify_applied_controls("example/repo", 9444106, promotion_app_id=12345)  # noqa: SLF001

    def fail_environment_read(_args, **_kwargs):
        raise RuntimeError("gh: Not Found")

    monkeypatch.setattr(module, "_run_gh_api", fail_environment_read)
    with pytest.raises(RuntimeError) as exc_info:
        module._verify_applied_controls("example/repo", 9444106, promotion_app_id=12345)  # noqa: SLF001
    combined_error = str(exc_info.value)
    assert "missing required status checks" in combined_error  # nosec B101
    assert "prod environment was not readable" in combined_error  # nosec B101
    assert (  # nosec B101
        "operations-alert-reconcile environment was not readable" in combined_error
    )
    assert "gh: Not Found" in combined_error  # nosec B101

    monkeypatch.setattr(module, "_main_ruleset", lambda _repo: ruleset)
    monkeypatch.setattr(module, "_run_gh_api", lambda _args, **_kwargs: [])
    with pytest.raises(RuntimeError, match="not readable"):
        module._verify_applied_controls("example/repo", 9444106, promotion_app_id=12345)  # noqa: SLF001


def test_configure_github_repository_controls_verify_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify existing GitHub controls without applying writes or requiring admin."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")
    verifications: list[tuple[str, int]] = []

    monkeypatch.setattr(module, "_github_user_id", lambda _reviewer: 9444106)
    monkeypatch.setattr(
        module,
        "_repo_admin_allowed",
        lambda _repo: (_ for _ in ()).throw(AssertionError("admin checked")),
    )
    monkeypatch.setattr(
        module,
        "_main_ruleset",
        lambda _repo: (_ for _ in ()).throw(AssertionError("ruleset read")),
    )
    monkeypatch.setattr(
        module,
        "_verify_applied_controls",
        lambda repo, reviewer_id, **kwargs: (
            verifications.append((repo, reviewer_id))
            or {
                "prodEnvironment": "prod",
                "prodReviewerId": reviewer_id,
                "operationsAlertReconcileEnvironment": "operations-alert-reconcile",
                "operationsAlertReconcileReviewerId": reviewer_id,
            }
        ),
    )

    module.configure(
        "example/repo", "Kravalg", apply=False, verify_only=True, promotion_app_id=12345
    )
    rendered = json.loads(capsys.readouterr().out)
    assert rendered == {  # nosec B101
        "verification": {
            "prodEnvironment": "prod",
            "prodReviewerId": 9444106,
            "operationsAlertReconcileEnvironment": "operations-alert-reconcile",
            "operationsAlertReconcileReviewerId": 9444106,
        }
    }

    assert (  # nosec B101
        module.main(
            ["--promotion-app-id", "12345", "--repo", "example/repo", "--verify-only"]
        )
        == 0
    )
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["verification"]["prodReviewerId"] == 9444106  # nosec B101
    assert verifications == [  # nosec B101
        ("example/repo", 9444106),
        ("example/repo", 9444106),
    ]


def test_configure_github_repository_controls_api_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover gh api parsing, ruleset lookup, and reviewer resolution paths."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")
    calls: list[tuple[list[str], str | None]] = []
    responses = [
        '{"ok": true}',
        "",
        '"scalar"',
        '[{"name":"other"},{"name":"main","target":"branch","id":123}]',
        '{"id":123,"rules":[{"type":"deletion"}]}',
        '{"not":"a-list"}',
        '["invalid", {"name":"main","target":"branch","id":"not-int"}]',
        '{"id":9444106}',
        "{}",
        "[]",
        '{"permissions":{"admin":true}}',
        '{"permissions":{"admin":false}}',
        '{"permissions":{}}',
    ]

    def fake_run(command, input=None, check=None, capture_output=None, text=None):
        calls.append((command, input))
        return subprocess.CompletedProcess(command, 0, stdout=responses.pop(0))

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._run_gh_api(["repos/example/repo"]) == {"ok": True}  # nosec B101
    assert (  # nosec B101
        module._run_gh_api(["repos/example/repo"], input_payload={"x": 1}) == {}
    )
    assert module._run_gh_api(["repos/example/repo"]) == {}  # nosec B101
    assert module._main_ruleset("example/repo") == {  # nosec B101
        "id": 123,
        "rules": [{"type": "deletion"}],
    }
    assert module._main_ruleset("example/repo") is None  # nosec B101
    assert module._main_ruleset("example/repo") is None  # nosec B101
    assert module._github_user_id("Kravalg") == 9444106  # nosec B101
    with pytest.raises(ValueError, match="Could not resolve"):
        module._github_user_id("missing")
    assert module._repo_admin_allowed("example/repo") is False  # nosec B101  # noqa: SLF001
    assert module._repo_admin_allowed("example/repo") is True  # nosec B101  # noqa: SLF001
    assert module._repo_admin_allowed("example/repo") is False  # nosec B101  # noqa: SLF001
    assert module._repo_admin_allowed("example/repo") is False  # nosec B101  # noqa: SLF001
    assert calls[1][1] == '{"x": 1}'  # nosec B101

    def failing_run(command, input=None, check=None, capture_output=None, text=None):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="denied")

    monkeypatch.setattr(module.subprocess, "run", failing_run)
    with pytest.raises(RuntimeError, match="denied"):
        module._run_gh_api(["repos/example/repo"])


def test_configure_github_repository_controls_apply_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Apply existing and new ruleset paths through gh api wrappers."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")
    calls: list[tuple[list[str], dict]] = []
    verifications: list[tuple[str, int]] = []
    existing = {"id": 123, "rules": "invalid"}

    monkeypatch.setattr(module, "_repo_admin_allowed", lambda _repo: True)
    monkeypatch.setattr(module, "_github_user_id", lambda _reviewer: 9444106)
    monkeypatch.setattr(
        module,
        "_verify_applied_controls",
        lambda repo, reviewer_id, **kwargs: (
            verifications.append((repo, reviewer_id)) or {"verified": True}
        ),
    )
    monkeypatch.setattr(
        module,
        "prod_environment_payload",
        lambda reviewer_id: {"environment": "prod", "reviewerId": reviewer_id},
    )
    monkeypatch.setattr(
        module,
        "operations_alert_reconcile_environment_payload",
        lambda reviewer_id: {
            "environment": "operations-alert-reconcile",
            "reviewerId": reviewer_id,
        },
    )

    def fake_run_gh_api(args, *, input_payload=None):
        calls.append((list(args), dict(input_payload or {})))
        return {"total_count": 0, "branch_policies": []} if len(args) == 1 else {}

    monkeypatch.setattr(module, "_run_gh_api", fake_run_gh_api)
    monkeypatch.setattr(module, "_main_ruleset", lambda _repo: existing)

    module.configure("example/repo", "Kravalg", apply=True, promotion_app_id=12345)
    assert calls[0][0] == [  # nosec B101
        "repos/example/repo/rulesets/123",
        "--method",
        "PUT",
    ]
    assert calls[1][0] == [  # nosec B101
        "repos/example/repo/environments/prod",
        "--method",
        "PUT",
    ]
    assert calls[2][0] == [  # nosec B101
        "repos/example/repo/environments/operations-alert-reconcile",
        "--method",
        "PUT",
    ]
    assert calls[1][1] == {"environment": "prod", "reviewerId": 9444106}  # nosec B101
    assert calls[2][1] == {  # nosec B101
        "environment": "operations-alert-reconcile",
        "reviewerId": 9444106,
    }
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["prodEnvironment"]["environment"] == "prod"  # nosec B101
    assert rendered["operationsAlertReconcileEnvironment"]["environment"] == (  # nosec B101
        "operations-alert-reconcile"
    )
    assert rendered["verification"] == {"verified": True}  # nosec B101
    assert verifications == [("example/repo", 9444106)]  # nosec B101

    calls.clear()
    verifications.clear()
    monkeypatch.setattr(module, "_main_ruleset", lambda _repo: None)
    module.configure("example/repo", "Kravalg", apply=True, promotion_app_id=12345)
    assert calls[0][0] == ["repos/example/repo/rulesets", "--method", "POST"]  # nosec B101
    assert calls[1][0] == [  # nosec B101
        "repos/example/repo/environments/prod",
        "--method",
        "PUT",
    ]
    assert calls[2][0] == [  # nosec B101
        "repos/example/repo/environments/operations-alert-reconcile",
        "--method",
        "PUT",
    ]
    assert calls[1][1] == {"environment": "prod", "reviewerId": 9444106}  # nosec B101
    assert calls[2][1] == {  # nosec B101
        "environment": "operations-alert-reconcile",
        "reviewerId": 9444106,
    }
    assert verifications == [("example/repo", 9444106)]  # nosec B101


def test_configure_github_repository_controls_apply_requires_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail before mutating repository controls when the token is not an admin."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")
    calls: list[list[str]] = []

    monkeypatch.setattr(module, "_repo_admin_allowed", lambda _repo: False)
    monkeypatch.setattr(
        module,
        "_main_ruleset",
        lambda _repo: (_ for _ in ()).throw(AssertionError("ruleset read")),
    )
    monkeypatch.setattr(
        module,
        "_github_user_id",
        lambda _reviewer: (_ for _ in ()).throw(AssertionError("reviewer read")),
    )

    def fake_run_gh_api(args, *, input_payload=None):
        calls.append(list(args))
        return {}

    monkeypatch.setattr(module, "_run_gh_api", fake_run_gh_api)

    with pytest.raises(RuntimeError, match="repository admin rights"):
        module.configure("example/repo", "Kravalg", apply=True, promotion_app_id=12345)
    assert calls == []  # nosec B101


def test_configure_github_repository_controls_main_reports_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Return a non-zero exit when GitHub rejects the admin update."""
    module = load_script_module(monkeypatch, "configure_github_repository_controls")

    def fail_configure(*_args, **_kwargs):
        raise RuntimeError("admin required")

    monkeypatch.setattr(module, "configure", fail_configure)

    assert (
        module.main(
            ["--promotion-app-id", "12345", "--repo", "example/repo", "--apply"]
        )
        == 1
    )  # nosec B101
    assert "error:" in capsys.readouterr().err  # nosec B101


@pytest.mark.parametrize("existing", [False, True])
def test_configure_converges_main_only_policy(monkeypatch, existing):
    controls = load_script_module(monkeypatch, "configure_github_repository_controls")
    boundary = load_script_module(monkeypatch, "_github_evidence_environment")
    calls = []
    policies = [{"name": "*", "type": "branch", "id": 1}]
    if existing:
        policies.append({"name": "main", "type": "branch", "id": 2})

    def api(args, **kwargs):
        calls.append((args, kwargs))
        return {
            "total_count": len(policies) if isinstance(policies, list) else 0,
            "branch_policies": policies,
        }

    monkeypatch.setattr(controls, "_run_gh_api", api)
    controls._configure_evidence_environment("org/repo")
    assert calls[0][1]["input_payload"] == boundary.payload()
    assert any(args[-1] == "DELETE" and args[0].endswith("/1") for args, _ in calls)
    assert sum(args[-1] == "POST" for args, _ in calls) == (0 if existing else 1)


def test_configure_rejects_malformed_policy_metadata(monkeypatch):
    controls = load_script_module(monkeypatch, "configure_github_repository_controls")
    monkeypatch.setattr(controls, "_run_gh_api", lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="object"):
        controls._configure_evidence_environment("org/repo")


def test_verification_reads_environment_and_branch_policies(monkeypatch):
    controls = load_script_module(monkeypatch, "configure_github_repository_controls")
    boundary = load_script_module(monkeypatch, "_github_evidence_environment")

    def api(args):
        return (
            {"total_count": 1, "branch_policies": [{"name": "main", "type": "branch"}]}
            if args[0].endswith("deployment-branch-policies")
            else boundary.payload()
        )

    monkeypatch.setattr(controls, "_run_gh_api", api)
    assert controls._evidence_environment_blockers("org/repo") == []
    monkeypatch.setattr(controls, "_run_gh_api", lambda *args: [])
    assert "JSON objects" in controls._evidence_environment_blockers("org/repo")[0]

    def failure(*args):
        raise RuntimeError("Not Found")

    monkeypatch.setattr(controls, "_run_gh_api", failure)
    assert "not readable" in controls._evidence_environment_blockers("org/repo")[0]
