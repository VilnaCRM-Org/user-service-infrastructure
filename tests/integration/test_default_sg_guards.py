"""Fail-closed guard of the S3.2 default security group in the integration suite.

The integration coverage gate includes ``pulumi/app``. The hardened graph
renders only the reviewed default security group with zero rules, so these
cases drive the refusal directly: any ingress or egress rule, or an opaque
rule list, fails the hardened guard (FR-16).
"""

import pytest
from app.workload_phase import _reject_secret_material

import pulumi

DEFAULT_SG = "aws:ec2/defaultSecurityGroup:DefaultSecurityGroup"
RULE = {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}


def _args(props):
    return pulumi.ResourceTransformationArgs(
        resource=None, type_=DEFAULT_SG, name="probe", props=props, opts=None
    )


@pytest.mark.parametrize(
    "props",
    [
        {"ingress": [RULE], "egress": []},
        {"ingress": [], "egress": [RULE]},
        {"ingress": "opaque"},
    ],
)
def test_a_default_sg_rule_fails_the_hardened_guard(props):
    with pytest.raises(ValueError, match="unreviewed property"):
        _reject_secret_material(_args(props))


@pytest.mark.parametrize("props", [{"ingress": [], "egress": []}, {}])
def test_a_default_sg_without_rules_passes_the_hardened_guard(props):
    assert _reject_secret_material(_args(props)) is None
