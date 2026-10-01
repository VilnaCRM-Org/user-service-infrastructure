"""S1.10 (FR-29, AD-22): the legacy managed path fails closed for test and prod.

The legacy path is ``UserServiceStack`` (and ``DataPlane``/``ComputePlane``)
composed without ``RuntimeSecrets``. It writes config-supplied secret material,
including the social-login client secrets, into ``SecretVersion``s. Shared
stacks compose ``WorkloadPhaseStack`` with ``RuntimeSecrets`` instead; its
pre-hardening branch is S4.10's (AD-25) and is not touched here.
"""

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import app.environment as environment_module
import pytest
from app.compute import ComputePlane
from app.data import DataPlane
from app.stack import UserServiceStack
from test_environment_component import (
    MANAGED_STACK_CONFIG,
    RecordingMocks,
    _assert_output_value,
    _run_pulumi_program,
    mocked_pulumi_context,
)

ROOT = Path(__file__).resolve().parents[2]
REFUSAL = "Legacy managed path is closed for shared stacks"
SECRET_VERSION = "aws:secretsmanager/secretVersion:SecretVersion"
SECRET = "aws:secretsmanager/secret:Secret"
ACCOUNT = {"region": "eu-central-1", "allowedAccountIds": ["123456789012"]}
SOCIAL_SECRETS = {
    "githubClientId": "github-id",
    "githubClientSecret": "github-secret",
    "googleClientId": "google-id",
    "googleClientSecret": "google-secret",
    "facebookClientId": "facebook-id",
    "facebookClientSecret": "facebook-secret",
    "twitterClientId": "twitter-id",
    "twitterClientSecret": "twitter-secret",
}
# The legacy writers: eleven runtime secrets plus the two connection URLs.
LEGACY_SECRET_NAMES = {
    *(
        f"user-service-{key}"
        for key in (
            "app-secret",
            "mailer-dsn",
            "oauth-encryption-key",
            "oauth-passphrase",
            "twofactor-encryption-key",
            "oauth-private-key",
            "oauth-public-key",
            "github-client-secret",
            "google-client-secret",
            "facebook-client-secret",
            "twitter-client-secret",
        )
    ),
    "user-service-documentdb-url",
    "user-service-redis-url",
}


def _config(environment: str, **overrides: object) -> dict[str, object]:
    """Managed legacy config whose central roles match ``environment``."""
    role = f"arn:aws:iam::123456789012:role/user-service-infrastructure-{environment}"
    return {
        **MANAGED_STACK_CONFIG,
        **SOCIAL_SECRETS,
        "environment": environment,
        "executionRoleArn": f"{role}-EcsExecution",
        "taskRoleArn": f"{role}-EcsTask",
        **overrides,
    }


def _shared(settings, environment: str):
    """The dev settings retargeted at a shared environment, roles included."""
    role = f"arn:aws:iam::123456789012:role/user-service-infrastructure-{environment}"
    runtime = replace(
        settings.runtime,
        execution_role_arn=f"{role}-EcsExecution",
        task_role_arn=f"{role}-EcsTask",
    )
    return replace(settings, environment=environment, runtime=runtime)


def _types(recorder: RecordingMocks) -> list[str]:
    return [str(row["type"]) for row in recorder.resources]


def test_shared_environments_are_exactly_test_and_prod():
    """The refusal set is closed and cannot be widened at runtime."""
    shared = environment_module.SHARED_ENVIRONMENTS
    assert shared == frozenset({"test", "prod"})
    assert type(shared) is frozenset


@pytest.mark.parametrize("environment", ["test", "prod"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_managed_shared_stack_without_runtime_secrets_raises(environment, dry_run):
    """P: managed test/prod without RuntimeSecrets raises before any AWS resource."""
    recorder = RecordingMocks()

    def program():
        with pytest.raises(ValueError, match=REFUSAL):
            UserServiceStack("legacy")

    with (
        mocked_pulumi_context(_config(environment), aws_config_values=ACCOUNT),
        patch("app.environment.pulumi.runtime.is_dry_run", return_value=dry_run),
    ):
        _run_pulumi_program(program, test_mocks=recorder)
    # Not even the provider or the registries register: nothing under aws:.
    assert not [kind for kind in _types(recorder) if kind.startswith("aws:")]
    assert "pulumi:providers:aws" not in _types(recorder)


@pytest.mark.parametrize("stack", ["test", "prod"])
def test_a_shared_stack_name_refuses_a_non_shared_environment(stack):
    """P: a ``test``/``prod`` stack refuses the legacy path whatever its config."""
    recorder = RecordingMocks()

    def program():
        with pytest.raises(ValueError, match=REFUSAL):
            UserServiceStack("legacy")

    with (
        mocked_pulumi_context(_config("dev"), aws_config_values=ACCOUNT),
        patch("app.environment.pulumi.get_stack", return_value=stack),
    ):
        _run_pulumi_program(program, test_mocks=recorder)
    assert not [kind for kind in _types(recorder) if kind.startswith("aws:")]


@pytest.mark.parametrize("environment", ["test", "prod"])
@pytest.mark.parametrize("plane", ["data", "compute"])
def test_planes_composed_directly_without_runtime_secrets_raise(environment, plane):
    """P: the planes refuse too, so bypassing UserServiceStack does not reopen it."""
    recorder = RecordingMocks()

    def program():
        stack = UserServiceStack("dev-legacy")
        shared = _shared(stack.settings, environment)
        before = len(recorder.resources)
        with pytest.raises(ValueError, match=REFUSAL):
            if plane == "data":
                DataPlane("direct", settings=shared, network=stack.network)
            else:
                ComputePlane(
                    "direct",
                    settings=shared,
                    network=stack.network,
                    data=stack.data,
                    messaging=stack.messaging,
                    registries=stack.registries.outputs,
                )
        assert recorder.resources[before:] == []

    with mocked_pulumi_context(_config("dev"), aws_config_values=ACCOUNT):
        _run_pulumi_program(program, test_mocks=recorder)


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_legacy_secret_writers_refuse_a_shared_target(environment):
    """N: neither legacy writer can put a SecretVersion into a shared graph."""
    recorder = RecordingMocks()

    def program():
        stack = UserServiceStack("dev-legacy")
        shared = _shared(stack.settings, environment)
        before = len(recorder.resources)
        with pytest.raises(ValueError, match=REFUSAL):
            stack.compute._create_runtime_secrets(shared)
        with pytest.raises(ValueError, match=REFUSAL):
            stack.data._persist_url(shared, "redis_url", "user-service-x", "v")
        assert recorder.resources[before:] == []

    with mocked_pulumi_context(_config("dev"), aws_config_values=ACCOUNT):
        _run_pulumi_program(program, test_mocks=recorder)


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_a_managed_shared_graph_contains_no_secret_version(environment):
    """N: the managed test/prod legacy graph never holds a SecretVersion or Secret."""
    recorder = RecordingMocks()
    refusals: list[str] = []

    def program():
        try:
            UserServiceStack("legacy")
        except ValueError as error:
            refusals.append(str(error))

    with mocked_pulumi_context(_config(environment), aws_config_values=ACCOUNT):
        _run_pulumi_program(program, test_mocks=recorder)
    versions = [
        row["name"] for row in recorder.resources if row["type"] == SECRET_VERSION
    ]
    assert versions == []
    assert SECRET not in _types(recorder)
    assert len(refusals) == 1 and REFUSAL in refusals[0]


def test_dev_managed_legacy_graph_is_unchanged():
    """B: dev keeps the legacy writers, social-login secrets included."""
    recorder = RecordingMocks()

    def program():
        UserServiceStack("legacy")

    with mocked_pulumi_context(_config("dev"), aws_config_values=ACCOUNT):
        _run_pulumi_program(program, test_mocks=recorder)
    secrets = {row["name"] for row in recorder.resources if row["type"] == SECRET}
    versions = {
        row["name"] for row in recorder.resources if row["type"] == SECRET_VERSION
    }
    assert secrets == LEGACY_SECRET_NAMES
    assert versions == {f"{name}-version" for name in LEGACY_SECRET_NAMES}


@pytest.mark.parametrize("environment", ["dev", "test", "prod"])
def test_preview_placeholder_mode_is_unaffected(environment):
    """B: preview placeholders render for every environment, with no AWS resource."""
    recorder = RecordingMocks()

    def program():
        stack = UserServiceStack("legacy")
        assert stack.registries is None
        _assert_output_value(
            stack.compute.outputs.cluster_name, f"user-service-{environment}-ecs"
        )

    with mocked_pulumi_context(
        {
            "deploymentMode": "preview",
            "serviceName": "user-service",
            "environment": environment,
        }
    ):
        _run_pulumi_program(program, test_mocks=recorder)
    assert not [kind for kind in _types(recorder) if kind.startswith("aws:")]


def test_preview_planes_stay_open_on_a_shared_stack_name():
    """B: the stack-name refusal applies to managed mode only."""

    def program():
        UserServiceStack("legacy")

    with (
        mocked_pulumi_context({"deploymentMode": "preview", "environment": "test"}),
        patch("app.environment.pulumi.get_stack", return_value="test"),
    ):
        _run_pulumi_program(program)


def test_the_lifecycle_doc_records_the_legacy_path_and_the_social_login_path():
    """FR-29 (NFR-10): the doc records the refusal and the future social path."""
    text = " ".join((ROOT / "specs/poc/secret-lifecycle.md").read_text().split())
    section = text[text.index("## Legacy managed path fails closed") :]
    for marker in (
        "(S1.10, FR-29, AD-22)",
        "`UserServiceStack`",
        "`ComputePlane._create_runtime_secrets`",
        "`DataPlane._persist_url`",
        "`require_legacy_target`",
        "`SHARED_ENVIRONMENTS`",
        "the selected stack name",
        "before any AWS resource registers",
        "Dev and preview placeholders are unchanged",
        "S4.10",
        "governance secret-write path",
        "outside Pulumi",
        "no `SecretVersion`",
        "`SOCIAL_OAUTH_ENABLED`",
    ):
        assert marker in section, marker
