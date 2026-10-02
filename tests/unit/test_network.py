"""Managed VPC default security group (S3.2, FR-16).

FR-16: the VPC default security group is managed and has zero ingress and
zero egress rules. The hardened TEST graph declares exactly one
``DefaultSecurityGroup`` on the workload VPC with both rule lists empty; any
rule fails the hardened guard on the SDK and the engine path (N), and a
re-added rule in a rendered graph fails the composition (N). Boundary B: the
adoption and destroy semantics are written down in ``docs/sre-operations.md``.
"""

import re
from pathlib import Path

import pytest
from app.network import NetworkPlane
from app.workload_phase import _reject_secret_material
from test_poc_workload_phase import graph
from test_runtime_secrets import _transform_args

import pulumi

ROOT = Path(__file__).parents[2]
DEFAULT_SG = "aws:ec2/defaultSecurityGroup:DefaultSecurityGroup"
INGRESS_RULE = {"protocol": "-1", "fromPort": 0, "toPort": 0, "self": True}
EGRESS_RULE = {
    "protocol": "-1",
    "fromPort": 0,
    "toPort": 0,
    "cidrBlocks": ["0.0.0.0/0"],
}


@pytest.fixture(scope="module")
def hardened(tmp_path_factory):
    receipt = graph(tmp_path_factory.mktemp("default-sg"), "hardened")
    assert receipt["error"] is None
    return receipt


def test_the_hardened_graph_manages_one_default_sg_with_no_rules(hardened):
    rows = hardened["registrations"]
    groups = {name: row for name, row in rows.items() if row["type"] == DEFAULT_SG}
    assert list(groups) == ["user-service-default-sg"]
    inputs = groups["user-service-default-sg"]["inputs"]
    assert inputs["vpcId"] == rows["user-service-vpc"]["id"]
    assert inputs["ingress"] == []
    assert inputs["egress"] == []


def test_the_pre_hardening_graph_does_not_manage_the_default_sg(tmp_path):
    """AD-25: the bridge graph is unchanged until its own story."""
    rows = graph(tmp_path, "bridge")["registrations"].values()
    assert DEFAULT_SG not in {row["type"] for row in rows}


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize(
    "props",
    [
        {"ingress": [], "egress": []},
        {"vpcId": "vpc-fixture"},
    ],
)
def test_a_default_sg_without_rules_passes_the_guard(engine, props):
    assert _reject_secret_material(_transform_args(engine, DEFAULT_SG, props)) is None


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize(
    "props",
    [
        {"ingress": [INGRESS_RULE], "egress": []},
        {"ingress": [], "egress": [EGRESS_RULE]},
        {"ingress": [INGRESS_RULE]},
        {"egress": [EGRESS_RULE]},
        {"ingress": "opaque", "egress": []},
    ],
)
def test_a_default_sg_with_any_rule_fails_the_guard(engine, props):
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_transform_args(engine, DEFAULT_SG, props))


def test_an_unresolved_rule_list_fails_closed():
    """An SDK ``Output`` cannot be read, so it cannot be shown to be empty."""
    props = {"ingress": object.__new__(pulumi.Output), "egress": []}
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_transform_args(False, DEFAULT_SG, props))


@pytest.mark.parametrize("owner", ["root", "stack"])
@pytest.mark.parametrize("kind", ["default-sg-ingress", "default-sg-egress"])
def test_a_rendered_default_sg_rule_fails_the_composition(tmp_path, owner, kind):
    receipt = graph(tmp_path, "hardened", f"{owner}:{kind}")
    assert "unreviewed property" in receipt["error"]
    assert not [
        name for name in receipt["registrations"] if name.startswith("fixture-")
    ]


def test_the_ops_guide_documents_adoption_and_destroy():
    """B (FR-16): the adoption and destroy semantics are written down."""
    text = " ".join((ROOT / "docs/sre-operations.md").read_text().split())
    section = text[text.index("### Managed default security group (S3.2, FR-16)") :]
    section = section[: section.index("## CI Troubleshooting")]
    for marker in (
        "`aws:ec2/defaultSecurityGroup:DefaultSecurityGroup`",
        "empty `ingress` and empty `egress`",
        "adopts the existing default group and removes every ingress and egress rule",
        "only stops Pulumi managing the group",
        "The group stays in the VPC",
        "the bridge graph does not manage the default group",
    ):
        assert marker in section, marker


def test_the_default_sg_docstring_cites_the_ops_guide_section():
    """S32-F1: the docstring cites the file that holds the adoption section."""
    doc = " ".join(NetworkPlane._default_security_group.__doc__.split())
    citation = re.search(r'\((docs/[^,)]+)(?:, "([^"]+)")?\)', doc)
    assert citation.groups() == (
        "docs/sre-operations.md",
        "Managed default security group (S3.2, FR-16)",
    )
    assert "### Managed default security group (S3.2, FR-16)" in (
        (ROOT / "docs/sre-operations.md").read_text()
    )
