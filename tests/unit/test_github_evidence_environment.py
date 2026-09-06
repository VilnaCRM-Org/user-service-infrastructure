"""The isolated App key must be inaccessible to feature-branch workflow jobs."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
boundary = importlib.import_module("_github_evidence_environment")
promotion = importlib.import_module("governance_promotion")


def test_valid_boundary_has_no_all_pr_review_bottleneck():
    environment = boundary.payload()
    assert environment["reviewers"] == []
    assert (
        boundary.verification_blockers(
            environment,
            {
                "branch_policies": [{"name": "main", "type": "branch"}],
            },
        )
        == []
    )


@pytest.mark.parametrize(
    "policies",
    [
        None,
        1,
        "main",
        {},
        [None],
        ["main"],
        [{}],
        [],
        [{"name": "*", "type": "branch"}],
        [{"name": "main", "type": "tag"}],
        [{"name": "main", "type": "branch"}, {"name": "feature", "type": "branch"}],
    ],
)
def test_wildcards_tags_other_branches_and_missing_policy_rejected(policies):
    assert boundary.verification_blockers(
        boundary.payload(), {"branch_policies": policies}
    )


def test_admin_bypass_and_missing_branch_restrictions_rejected():
    assert len(boundary.verification_blockers({}, {})) == 3


def test_reporter_rechecks_boundary_before_using_app_key(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setattr(
        promotion,
        "gh",
        lambda path: (
            {"branch_policies": [{"name": "main", "type": "branch"}]}
            if path.endswith("deployment-branch-policies")
            else boundary.payload()
        ),
    )
    assert promotion.main(["verify-environment"]) == 0
    monkeypatch.setattr(promotion, "gh", lambda *args: {})
    with pytest.raises(ValueError, match="main branch"):
        promotion.main(["verify-environment"])
