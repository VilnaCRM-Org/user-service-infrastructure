"""Owned TEST SES Easy DKIM prerequisite, shared by both PoC phases."""

import re

import pulumi_aws as aws

import pulumi

DOMAIN = "user.vilnacrmtest.com"
ZONE = "Z04999481RZ4UQK2NANVH"


def _tokens(attributes):
    """Reject malformed or BYODKIM outputs before deriving DNS record values."""
    tokens = attributes.tokens
    if (
        tokens is None
        or len(tokens) != 3
        or len(set(tokens)) != 3
        or any(re.fullmatch(r"[a-z0-9]{32}", token) is None for token in tokens)
    ):
        raise ValueError("SES Easy DKIM tokens differ")
    return sorted(tokens)


def create_mail_identity(*, parent, tags):
    """Create one fixed domain identity and its three provider-derived CNAMEs."""
    if (pulumi.get_project(), pulumi.get_stack()) != (
        "user-service-infrastructure",
        "test",
    ):
        raise ValueError("SES prerequisite requires the TEST service stack")
    identity = aws.sesv2.EmailIdentity(
        "user-service-mail-identity",
        email_identity=DOMAIN,
        dkim_signing_attributes={"next_signing_key_length": "RSA_2048_BIT"},
        tags=tags,
        opts=pulumi.ResourceOptions(parent=parent),
    )
    # The provider marks its unused empty BYODKIM field secret, tainting the
    # containing output. Only the validated public DNS tokens are declassified.
    tokens = pulumi.Output.unsecret(identity.dkim_signing_attributes.apply(_tokens))
    records = [
        aws.route53.Record(
            f"user-service-mail-dkim-{index}",
            zone_id=ZONE,
            name=tokens.apply(
                lambda values, i=index: f"{values[i]}._domainkey.{DOMAIN}"
            ),
            type="CNAME",
            ttl=300,
            records=tokens.apply(
                lambda values, i=index: [f"{values[i]}.dkim.amazonses.com"]
            ),
            allow_overwrite=False,
            opts=pulumi.ResourceOptions(parent=parent),
        )
        for index in range(3)
    ]
    return identity, records
