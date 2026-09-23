"""Integration coverage for the TEST SES identity and derived DKIM records."""

import asyncio
from types import SimpleNamespace

import pytest
from app.mail_identity import DOMAIN, ZONE, _tokens, create_mail_identity
from pulumi.runtime import mocks, settings, stack


class MailIdentityMocks(mocks.Mocks):
    """Supply the public Easy DKIM tokens normally returned by the provider."""

    def __init__(self) -> None:
        self.resources: list[mocks.MockResourceArgs] = []

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        self.resources.append(args)
        outputs = dict(args.inputs)
        if args.typ == "aws:sesv2/emailIdentity:EmailIdentity":
            outputs["dkimSigningAttributes"] = {
                "tokens": [letter * 32 for letter in "cba"]
            }
        return f"{args.name}-id", outputs

    def call(self, args: mocks.MockCallArgs) -> dict:
        raise AssertionError(f"Unexpected invoke: {args.token}")


def run_mail_identity(
    program, recorder: MailIdentityMocks, *, stack_name: str = "test"
) -> None:
    """Execute a TEST-stack Pulumi program entirely through local mocks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        monitor = mocks.MockMonitor(recorder)
        mocks.set_mocks(
            recorder,
            project="user-service-infrastructure",
            stack=stack_name,
            monitor=monitor,
        )
        loop.run_until_complete(stack.run_pulumi_func(program))
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        settings.reset_options(project=None, stack=None)
        loop.close()
        asyncio.set_event_loop(None)


@pytest.mark.parametrize(
    "value",
    [
        None,
        ["a" * 32, "b" * 32],
        ["a" * 32] * 3,
        ["a" * 32, "b" * 32, "not-a-token"],
    ],
)
def test_mail_identity_rejects_each_malformed_easy_dkim_token_shape(value) -> None:
    """Invalid provider outputs cannot become public DNS records."""
    with pytest.raises(ValueError, match="Easy DKIM tokens differ"):
        _tokens(SimpleNamespace(tokens=value))


def test_mail_identity_registers_three_public_dkim_cnames() -> None:
    """The TEST identity produces exactly one SES identity and three CNAMEs."""
    recorder = MailIdentityMocks()
    run_mail_identity(
        lambda: create_mail_identity(
            parent=None, tags={"Project": "user-service-infrastructure"}
        ),
        recorder,
    )

    identity, *records = recorder.resources
    assert identity.typ == "aws:sesv2/emailIdentity:EmailIdentity"
    assert identity.inputs["emailIdentity"] == DOMAIN
    assert identity.inputs["dkimSigningAttributes"] == {
        "nextSigningKeyLength": "RSA_2048_BIT"
    }
    assert [record.typ for record in records] == ["aws:route53/record:Record"] * 3
    assert sorted(record.name for record in records) == [
        "user-service-mail-dkim-0",
        "user-service-mail-dkim-1",
        "user-service-mail-dkim-2",
    ]
    assert all(record.inputs["zoneId"] == ZONE for record in records)
    assert all(record.inputs["type"] == "CNAME" for record in records)
    assert all(record.inputs["ttl"] == 300 for record in records)


def test_mail_identity_rejects_a_non_test_stack_before_registration() -> None:
    """Prerequisite resources remain exclusive to the TEST service stack."""
    recorder = MailIdentityMocks()
    with pytest.raises(ValueError, match="TEST service stack"):
        run_mail_identity(
            lambda: create_mail_identity(parent=None, tags={}),
            recorder,
            stack_name="prod",
        )
    assert recorder.resources == []
