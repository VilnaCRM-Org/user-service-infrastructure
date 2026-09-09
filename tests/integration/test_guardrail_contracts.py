"""Integration-level guardrail contracts for Pulumi environment metadata."""

from __future__ import annotations

import asyncio
import re
import runpy
from collections.abc import Callable
from pathlib import Path

import pytest
from app.environment import EnvironmentSettings
from pulumi.runtime import config, mocks, settings, stack

from pulumi import Output


class _IntegrationMocks(mocks.Mocks):
    """Pulumi mocks that keep component construction local to the test process."""

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        """Echo inputs so component registration can complete under test."""
        return f"{args.name}_id", args.inputs

    def call(self, args: mocks.MockCallArgs) -> dict:
        """Return invoke inputs unchanged for deterministic tests."""
        return args.inputs


def _run_with_mocks(
    program: Callable[[], None],
    *,
    stack_name: str = "integration",
    test_mocks: mocks.Mocks | None = None,
) -> None:
    """Execute a Pulumi program inside the integration suite process."""
    try:
        previous_loop = asyncio.get_event_loop()
    except RuntimeError:
        previous_loop = None

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        test_mocks = test_mocks or _IntegrationMocks()
        monitor = mocks.MockMonitor(test_mocks)
        mocks.set_mocks(
            test_mocks,
            project="user-service-infrastructure",
            stack=stack_name,
            monitor=monitor,
        )
        loop.run_until_complete(stack.run_pulumi_func(program))
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        settings.reset_options(project=None, stack=None)
        loop.close()
        if previous_loop is not None and not previous_loop.is_closed():
            asyncio.set_event_loop(previous_loop)
        else:
            asyncio.set_event_loop(None)


def test_environment_settings_support_default_resolution_under_pulumi_mocks() -> None:
    """Exercise the component path that falls back to committed defaults."""

    def program() -> None:
        EnvironmentSettings("integration-settings")

    _run_with_mocks(program)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"environment": 1, "service_name": "billing"},  # type: ignore[dict-item]
            "environment must be a string",
        ),
        (
            {"environment": "", "service_name": "billing"},
            "environment must not be empty",
        ),
        (
            {"environment": " qa ", "service_name": "billing"},
            "environment must not contain surrounding whitespace",
        ),
        (
            {"environment": "dev", "service_name": "Billing_API"},
            "service name must use lowercase letters, digits, and hyphens only",
        ),
    ],
)
def test_environment_settings_reject_invalid_identifier_inputs(
    kwargs: dict[str, object], message: str
) -> None:
    """Exercise identifier validation through the Pulumi component path."""

    def program() -> None:
        EnvironmentSettings("integration-settings", **kwargs)

    with pytest.raises(ValueError, match=rf"^{re.escape(message)}\.$"):
        _run_with_mocks(program)


class _SharedEntrypointMocks(_IntegrationMocks):
    """Model the real AWS invoke protocol without creating a provider process."""

    def __init__(self, account: str) -> None:
        self.account = account
        self.invocations: list[str] = []
        self.resources: list[str] = []

    def call(self, args: mocks.MockCallArgs) -> dict:
        self.invocations.append(args.token)
        assert args.token == "aws:index/getCallerIdentity:getCallerIdentity"
        return {
            "accountId": self.account,
            "arn": f"arn:aws:iam::{self.account}:root",
            "userId": "local-sdk-mock",
        }

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        self.resources.append(args.typ)
        return super().new_resource(args)


@pytest.mark.parametrize(
    "environment,account", [("test", "891377212104"), ("prod", "933245420672")]
)
@pytest.mark.parametrize("case", ["matching", "wrong-caller", "mismatched-environment"])
def test_shared_entrypoint_integrates_config_provider_and_exports(
    environment: str, account: str, case: str
) -> None:
    """Run the actual entrypoint and SDK config/invoke/export path offline."""
    program = Path(__file__).resolve().parents[2] / "pulumi/__main__.py"
    backend = f"s3://pulumi-user-service-infrastructure-{environment}-state"
    provider = f"awskms://alias/pulumi-user-service-infrastructure-{environment}-secrets?region=eu-central-1"
    values = {
        "environment": "dev" if case == "mismatched-environment" else environment,
        "awsAccountId": account,
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": backend,
        "pulumiSecretsProvider": provider,
    }
    previous_config = dict(config.CONFIG.get())
    config.set_all_config(
        {f"user-service-infrastructure:{key}": value for key, value in values.items()}
    )
    observed = _SharedEntrypointMocks(
        "000000000000" if case == "wrong-caller" else account
    )
    exports: list[dict] = []

    def execute_program():
        runpy.run_path(str(program))
        Output.all(**stack.get_root_resource().outputs).apply(exports.append)

    try:
        if case == "matching":
            _run_with_mocks(
                execute_program,
                stack_name=environment,
                test_mocks=observed,
            )
            exported = next(row for row in exports if "repoSlug" in row)
            assert exported["environment"] == environment
            assert exported["repoSlug"] == "user-service-infrastructure"
            assert exported["pulumiBackendUrl"] == backend
            assert exported["pulumiSecretsProvider"] == provider
            assert observed.resources == [
                "user-service-infrastructure:core:EnvironmentSettings"
            ]
        else:
            message = (
                "AWS caller account differs"
                if case == "wrong-caller"
                else "Configured environment differs"
            )
            with pytest.raises(ValueError, match=message):
                _run_with_mocks(
                    execute_program,
                    stack_name=environment,
                    test_mocks=observed,
                )
            assert observed.resources == []
            assert not any("repoSlug" in row for row in exports)
        assert observed.invocations == (
            []
            if case == "mismatched-environment"
            else ["aws:index/getCallerIdentity:getCallerIdentity"]
        )
    finally:
        config.set_all_config(previous_config)
