"""Malformed protection metadata must never be accepted as deployment approval."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import _github_environment_controls as environments
import _github_repository_controls as controls
import pulumi_pr_comment as comments


def test_ruleset_metadata_retains_stronger_rules_and_exact_app_issuer():
    strong = {
        "type": "pull_request",
        "parameters": {
            "required_approving_review_count": 3,
            "required_reviewers": [{"id": 7}],
        },
    }
    ruleset = controls.ruleset_payload(
        [
            strong,
            {"type": "code_quality"},
            {"type": "code_scanning"},
            {"type": "required_deployments"},
            {"type": None},
        ],
        promotion_app_id=12345,
    )
    assert controls.ruleset_verification_blockers(ruleset, promotion_app_id=12345) == []
    assert (
        controls.harden_pull_request_rule(strong)["parameters"][
            "required_approving_review_count"
        ]
        == 3
    )
    assert controls.ruleset_verification_blockers(ruleset, promotion_app_id=54321)
    assert controls.ruleset_verification_blockers(None, promotion_app_id=12345)
    assert len(controls.ruleset_verification_blockers({}, promotion_app_id=12345)) == 3
    assert controls.rulesets_have_pull_request_rule([{}, ruleset])
    assert not controls.rulesets_have_pull_request_rule([{}])
    assert controls.active_branch_ruleset_count([{}, ruleset]) == 1
    assert controls.required_status_contexts_for_rulesets([{}, ruleset]) == set(
        controls.REQUIRED_STATUS_CHECKS
    )
    for invalid in (0, -1, 15368):
        with pytest.raises(ValueError):
            controls.ruleset_payload(promotion_app_id=invalid)


@pytest.mark.parametrize(
    "rule",
    [
        None,
        {},
        {"type": "required_status_checks"},
        {"type": "required_status_checks", "parameters": {}},
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": "bad"},
        },
    ],
)
def test_malformed_status_lists_prove_no_checks(rule):
    assert controls.required_status_check_items(rule) == ()
    assert controls.required_status_contexts({"rules": [rule]}) == set()


@pytest.mark.parametrize(
    "rules",
    [
        None,
        [],
        [None],
        [{"type": "pull_request"}],
        [
            {
                "type": "pull_request",
                "parameters": {"required_approving_review_count": "1"},
            }
        ],
        [
            {
                "type": "pull_request",
                "parameters": {"required_approving_review_count": 0},
            }
        ],
        [
            {
                "type": "pull_request",
                "parameters": {"required_approving_review_count": 1},
            }
        ],
    ],
)
def test_incomplete_review_metadata_is_not_protection(rules):
    assert not controls.ruleset_has_pull_request_reviews({"rules": rules})


def test_status_items_and_nested_reviewers_require_recognized_types():
    assert controls.required_status_contexts(
        {
            "rules": [
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [None, {}, {"name": "fallback"}]
                    },
                }
            ]
        }
    ) == {"fallback"}
    assert controls.status_check_context(None) is None
    assert controls.environment_reviewer_ids(
        {
            "protection_rules": [
                None,
                {
                    "reviewers": [
                        None,
                        {},
                        {"type": "User", "id": 7},
                        {"reviewer": {"id": 8}},
                    ]
                },
            ]
        }
    ) == {7, 8}
    assert controls.environment_reviewer_ids({}) == set()
    assert not comments.author_is_authorized(
        "MEMBER", author_login="Kravalg", action="up"
    )
    assert not environments.environment_is_main_only(
        {"deployment_branch_policies": [None]}
    )


def test_environment_wrappers_reject_missing_or_weakened_protection():
    for payload, verifier in (
        (
            controls.prod_environment_payload,
            controls.prod_environment_verification_blockers,
        ),
        (
            controls.governance_environment_payload,
            controls.governance_environment_verification_blockers,
        ),
        (
            controls.operations_alert_reconcile_environment_payload,
            controls.operations_alert_reconcile_environment_verification_blockers,
        ),
    ):
        environment = payload(7)
        environment["deployment_branch_policies"] = [{"name": "main", "type": "branch"}]
        assert verifier(environment, 7) == []
        assert verifier(None, 7)
        for field, value in (
            ("prevent_self_review", False),
            ("can_admins_bypass", True),
            ("reviewers", []),
            ("deployment_branch_policies", [{"name": "*", "type": "branch"}]),
        ):
            changed = copy.deepcopy(environment)
            changed[field] = value
            assert verifier(changed, 7)


def test_optional_rules_and_missing_nested_reviewer_lists_are_not_inferred():
    assert (
        controls.ruleset_verification_blockers(
            controls.ruleset_payload(promotion_app_id=12345), promotion_app_id=12345
        )
        == []
    )
    assert (
        controls.environment_reviewer_ids(
            {"protection_rules": [{"type": "wait_timer"}]}
        )
        == set()
    )
    assert environments.environment_prevents_self_review(
        {
            "protection_rules": [
                None,
                {"type": "required_reviewers", "prevent_self_review": True},
            ]
        }
    )
    assert not environments.environment_prevents_self_review(
        {
            "protection_rules": [
                {"type": "required_reviewers", "prevent_self_review": False}
            ]
        }
    )
