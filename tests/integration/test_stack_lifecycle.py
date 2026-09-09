"""Pulumi Automation API integration tests for stack lifecycle."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pulumi.automation as auto
import pytest
from app.compute import ComputePlane
from app.environment import (
    NetworkSettings,
    _normalize_choice,
    _normalize_csv,
    _required_managed_string,
    _secret_value,
    _validate_parallel_lengths,
    build_resource_name,
    resolve_deployment_mode,
)
from pulumi.automation.errors import RuntimeError as AutomationRuntimeError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PULUMI_WORKDIR = PROJECT_ROOT / "pulumi"

pytestmark = pytest.mark.skipif(
    shutil.which("pulumi") is None, reason="Pulumi CLI binary is not available in PATH."
)


def _stack_name() -> str:
    """Return a unique stack name for the test run."""
    return f"it-{uuid.uuid4().hex[:8]}"


def _copy_workdir(tmp_path: Path, *, name: str) -> Path:
    """Copy the Pulumi program into an isolated temporary work directory."""
    work_dir = tmp_path / name
    shutil.copytree(
        PULUMI_WORKDIR,
        work_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache"),
    )
    return work_dir


def _workspace_options(work_dir: Path) -> auto.LocalWorkspaceOptions:
    """Pass the prepared Pulumi environment through Automation API workspaces."""
    env_vars = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("PULUMI_")
        or key in {"COVERAGE_FILE", "COVERAGE_PROCESS_START"}
    }
    return auto.LocalWorkspaceOptions(
        work_dir=str(work_dir),
        pulumi_home=env_vars.get("PULUMI_HOME"),
        env_vars=env_vars,
    )


def _configure_managed_stack(
    stack: auto.Stack,
    *,
    plain_overrides: dict[str, str] | None = None,
    secret_overrides: dict[str, str] | None = None,
) -> None:
    """Apply the baseline managed-stack config used by Automation API tests."""
    plain_config = {
        "environment": "integration",
        "serviceName": "user-service",
        "deploymentMode": "managed",
        "executionRoleArn": (
            "arn:aws:iam::123456789012:role/"
            "user-service-infrastructure-integration-EcsExecution"
        ),
        "taskRoleArn": (
            "arn:aws:iam::123456789012:role/"
            "user-service-infrastructure-integration-EcsTask"
        ),
        "accessLogsBucketName": "shared-alb-access-logs",
        "apiBaseUrl": "https://users.example.com",
        "apiUrl": "https://users.example.com",
        "corsAllowOrigin": "^https://users\\.example\\.com$",
        "certificateArn": (
            "arn:aws:acm:eu-central-1:123456789012:certificate/user-service"
        ),
        "webImage": "123456789012.dkr.ecr.eu-central-1.amazonaws.com/user-service:sha",
        "workerImage": (
            "123456789012.dkr.ecr.eu-central-1.amazonaws.com/user-service-worker:sha"
        ),
    }
    stack.set_config(
        "aws:allowedAccountIds", auto.ConfigValue(value='["123456789012"]')
    )
    secret_config = {
        "documentDbPassword": "mongo-secret",
        "redisAuthToken": "redis-secret-token-1234",
        "appSecret": "app-secret",
        "mailerDsn": "smtp://mail.example.com:587",
        "oauthEncryptionKey": "oauth-encryption-key",
        "oauthPassphrase": "oauth-passphrase",
        "twoFactorEncryptionKey": "two-factor-key",
        "oauthPrivateKeyPem": "private-key",
        "oauthPublicKeyPem": "public-key",
        "githubClientSecret": "github-secret",
        "googleClientSecret": "google-secret",
        "facebookClientSecret": "facebook-secret",
        "twitterClientSecret": "twitter-secret",
    }
    if plain_overrides:
        plain_config.update(plain_overrides)
    if secret_overrides:
        secret_config.update(secret_overrides)
    for key, value in plain_config.items():
        stack.set_config(key, auto.ConfigValue(value=value))
    for key, value in secret_config.items():
        stack.set_config(key, auto.ConfigValue(value=value, secret=True))


def test_pulumi_stack_preview_and_up_cycle(tmp_path: Path) -> None:
    """Validate preview/up/destroy behavior for the credential-free preview stack."""
    work_dir = _copy_workdir(tmp_path, name="pulumi-program")

    stack = auto.create_or_select_stack(
        stack_name=_stack_name(),
        work_dir=str(work_dir),
        opts=_workspace_options(work_dir),
    )
    stack.set_config("environment", auto.ConfigValue(value="integration"))
    stack.set_config("serviceName", auto.ConfigValue(value="integration-test"))
    stack.set_config("deploymentMode", auto.ConfigValue(value="preview"))

    try:
        preview_result = stack.preview()
        assert preview_result.change_summary is not None

        up_result = stack.up()

        assert up_result.outputs["deploymentMode"].value == "preview"
        assert up_result.outputs["stackTag"].value == "integration-test-integration"
        assert up_result.outputs["serviceName"].value == "integration-test"
        assert up_result.outputs["environment"].value == "integration"
        assert up_result.outputs["region"].value == "eu-central-1"
        assert up_result.outputs["defaultTags"].value == {
            "Project": "integration-test",
            "Environment": "integration",
            "Owner": "platform",
            "CostCenter": "engineering",
            "DataClassification": "internal",
            "Criticality": "high",
            "RetentionClass": "standard",
        }
        assert (
            up_result.outputs["serviceUrl"].value
            == "https://integration-test.integration.internal"
        )
        assert (
            up_result.outputs["loadBalancerDnsName"].value
            == "integration-test-integration-alb.elb.amazonaws.com"
        )
        assert (
            up_result.outputs["clusterName"].value == "integration-test-integration-ecs"
        )
        assert up_result.outputs["queueUrls"].value["healthCheck"] == (
            "https://sqs.eu-central-1.amazonaws.com/preview/health-check-queue"
        )
    finally:
        try:
            stack.destroy(on_output=None)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"Pulumi destroy failed: {exc}")
        try:
            stack.workspace.remove_stack(stack.name)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"Pulumi stack removal failed: {exc}")


def test_pulumi_stack_managed_preview_cycle_without_host_credentials(
    tmp_path: Path,
) -> None:
    """Preview the managed stack even when the workspace has no real AWS creds."""
    work_dir = _copy_workdir(tmp_path, name="pulumi-managed-preview")

    stack = auto.create_or_select_stack(
        stack_name=_stack_name(),
        work_dir=str(work_dir),
        opts=_workspace_options(work_dir),
    )
    _configure_managed_stack(stack)

    try:
        preview_result = stack.preview()
        assert preview_result.change_summary is not None
        assert preview_result.change_summary
    finally:
        try:
            stack.workspace.remove_stack(stack.name)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"Pulumi stack removal failed: {exc}")


def test_pulumi_stack_rejects_zero_documentdb_instances_in_managed_mode(
    tmp_path: Path,
) -> None:
    """Fail the managed preview when DocumentDB would publish no instances."""
    work_dir = _copy_workdir(tmp_path, name="pulumi-managed-preview")

    stack = auto.create_or_select_stack(
        stack_name=_stack_name(),
        work_dir=str(work_dir),
        opts=_workspace_options(work_dir),
    )
    _configure_managed_stack(
        stack,
        plain_overrides={"documentDbInstanceCount": "0"},
    )

    try:
        with pytest.raises(AutomationRuntimeError) as exc_info:
            stack.preview()
        assert (
            "documentDbInstanceCount must be at least 1 for managed deployments."
            in str(exc_info.value)
        ), str(exc_info.value)
    finally:
        try:
            stack.workspace.remove_stack(stack.name)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"Pulumi stack removal failed: {exc}")


def test_environment_helpers_cover_managed_validation_paths() -> None:
    """Cover the config-validation helpers used by managed stack previews."""
    assert resolve_deployment_mode("auto", credentials_present=True) == "managed"
    assert _normalize_csv(" one, ,two ", default=("default",)) == ("one", "two")
    assert _normalize_csv(" , ", default=("default",)) == ("default",)
    assert len(build_resource_name("x" * 40, "suffix", max_length=24)) <= 24
    assert len(build_resource_name("x" * 40, "suffix", max_length=6)) == 6

    with pytest.raises(
        ValueError,
        match=r"^deployment mode must be one of: managed, preview\.$",
    ):
        _normalize_choice(
            "invalid",
            allowed={"managed", "preview"},
            label="deployment mode",
        )

    config_with_value = Mock()
    config_with_value.get.return_value = "configured"
    assert (
        _required_managed_string(
            config_with_value,
            "accessLogsBucketName",
            managed=True,
            preview_default="preview-value",
        )
        == "configured"
    )

    config_with_secret = Mock()
    config_with_secret.get_secret.return_value = Mock()
    config_with_secret.get.return_value = None
    assert (
        _secret_value(
            config_with_secret,
            "appSecret",
            managed=True,
            preview_default="preview-secret",
        )
        is config_with_secret.get_secret.return_value
    )

    config_with_plaintext = Mock()
    config_with_plaintext.get_secret.return_value = None
    config_with_plaintext.get.return_value = "plaintext-secret"
    with pytest.raises(
        ValueError,
        match=(
            r"^appSecret is configured as plain text; re-set it with "
            r"`pulumi -C pulumi config set --secret appSecret <value>` for "
            r"managed "
            r"deployments\.$"
        ),
    ):
        _secret_value(
            config_with_plaintext,
            "appSecret",
            managed=True,
            preview_default="preview-secret",
        )

    with patch(
        "app.environment.pulumi.Output.secret",
        side_effect=lambda value: f"secret:{value}",
    ):
        assert (
            _secret_value(
                config_with_plaintext,
                "appSecret",
                managed=False,
                preview_default="preview-secret",
            )
            == "secret:plaintext-secret"
        )

    config_without_value = Mock()
    config_without_value.get.return_value = None
    with patch("app.environment.pulumi.runtime.is_dry_run", return_value=False):
        with pytest.raises(
            ValueError,
            match=(
                "^accessLogsBucketName must be configured for managed deployments\\.$"
            ),
        ):
            _required_managed_string(
                config_without_value,
                "accessLogsBucketName",
                managed=True,
                preview_default="preview-value",
            )

    config_without_secret = Mock()
    config_without_secret.get_secret.return_value = None
    config_without_secret.get.return_value = None
    with patch("app.environment.pulumi.runtime.is_dry_run", return_value=False):
        with pytest.raises(
            ValueError,
            match=(
                r"^appSecret must be configured as a secret for managed "
                r"deployments\.$"
            ),
        ):
            _secret_value(
                config_without_secret,
                "appSecret",
                managed=True,
                preview_default="preview-secret",
            )

    with pytest.raises(
        ValueError,
        match=(
            "^availability zones, public subnets, app subnets, and data subnets "
            "must have the same number of entries\\.$"
        ),
    ):
        _validate_parallel_lengths(
            NetworkSettings(
                vpc_cidr="10.42.0.0/16",
                availability_zones=("eu-central-1a", "eu-central-1b"),
                public_subnet_cidrs=("10.42.0.0/24",),
                app_subnet_cidrs=("10.42.10.0/24", "10.42.11.0/24"),
                data_subnet_cidrs=("10.42.20.0/24", "10.42.21.0/24"),
            )
        )


def test_component_helpers_cover_listener_and_policy_paths() -> None:
    """Cover helper branches that the Automation API path does not assert directly."""
    # These checks bypass full constructors on purpose so coverage reaches helper
    # branches that the public stack lifecycle does not expose directly.
    compute = object.__new__(ComputePlane)

    with pytest.raises(
        ValueError, match="^Managed compute requires caller-owned registry outputs$"
    ):
        compute._build_managed_outputs(Mock(), Mock(), Mock(), Mock(), None)

    fake_output = Mock()
    fake_output.apply.side_effect = lambda callback: callback("repo-url")
    with patch("app.compute.pulumi.Output.from_input", return_value=fake_output):
        assert (
            compute._resolve_image_uri(
                repository_url="ignored",
                image_tag="2026.04.12",
                override=None,
            )
            == "repo-url:2026.04.12"
        )

    settings = Mock()
    settings.runtime.certificate_arn = None
    load_balancer = Mock(arn="alb-arn")
    target_group = Mock(arn="tg-arn")
    with patch(
        "app.compute.aws.lb.Listener",
        side_effect=lambda name, **kwargs: kwargs,
    ):
        listener = compute._create_http_listener(
            settings,
            load_balancer,
            target_group,
        )
    assert listener["protocol"] == "HTTP"
    assert listener["default_actions"][0].type == "forward"


@pytest.mark.parametrize(
    ("config_key", "config_value", "message"),
    [
        ("environment", "", "environment must not be empty"),
        (
            "environment",
            " qa ",
            "environment must not contain surrounding whitespace",
        ),
        (
            "serviceName",
            "Billing_API",
            "service name must use lowercase letters, digits, and hyphens only",
        ),
    ],
)
def test_invalid_stack_config_fails_preview(
    tmp_path: Path,
    config_key: str,
    config_value: str,
    message: str,
) -> None:
    """Reject invalid environment metadata during a real Pulumi preview."""
    work_dir = _copy_workdir(tmp_path, name=f"pulumi-invalid-{config_key}")
    stack = auto.create_or_select_stack(
        stack_name=_stack_name(),
        work_dir=str(work_dir),
        opts=_workspace_options(work_dir),
    )
    baseline = {
        "environment": "integration",
        "serviceName": "integration-test",
        "deploymentMode": "preview",
    }
    for key, value in baseline.items():
        stack.set_config(key, auto.ConfigValue(value=value))
    stack.set_config(config_key, auto.ConfigValue(value=config_value))

    try:
        with pytest.raises(AutomationRuntimeError) as exc_info:
            stack.preview()
        assert message in str(exc_info.value), str(exc_info.value)
    finally:
        try:
            stack.workspace.remove_stack(stack.name)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"Pulumi stack removal failed: {exc}")
