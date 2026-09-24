"""Completion helpers must not restore routes closed by the installed controller."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def jobs():
    return yaml.safe_load((ROOT / ".github/workflows/self-deploy.yml").read_text())[
        "jobs"
    ]


@pytest.mark.parametrize(
    "name",
    ["test_registry_observation", "test_registry_proof", "test_registry_dispatch"],
)
def test_unvalidated_completion_route_is_not_installed(name):
    graph = jobs()
    assert name not in graph
    assert all(name not in job.get("needs", []) for job in graph.values())
    assert name not in str(graph["comment_result"])


def test_completion_helpers_cannot_issue_credentials_from_workflow():
    graph = jobs()
    assert "exit 1" in graph["preflight"]["steps"][-1]["run"]
    for job in graph.values():
        assert job.get("environment") != "governance-evidence"
        assert "deployments" not in job.get("permissions", {})
        for step in job["steps"]:
            assert "actions/create-github-app-token@" not in step.get("uses", "")
            assert "poc_registry_completion.py" not in step.get("run", "")
            assert "poc_publisher_dispatch.py" not in step.get("run", "")
