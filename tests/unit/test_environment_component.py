"""Unit tests for the user-service Pulumi configuration and stack components."""

import asyncio
import re
import runpy
import sys
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
from app.compute import ComputePlane
from app.environment import (
    EnvironmentSettings,
    NetworkSettings,
    _default_tags_from_parts,
    _get_int,
    _normalize_choice,
    _normalize_csv,
    _secret_value,
    _stack_metadata_from_outputs,
    _stack_tag_from_parts,
    _validate_parallel_lengths,
    build_resource_name,
    has_aws_credentials,
    resolve_config_value,
    resolve_deployment_mode,
    resolve_stack_settings,
)
from app.stack import UserServiceStack
from pulumi.runtime import mocks, settings, stack

import pulumi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PULUMI_MAIN = PROJECT_ROOT / "pulumi" / "__main__.py"
_PENDING_OUTPUT_ASSERTIONS: list[Callable[[], None]] = []


def _resource_mock_outputs(
    args: mocks.MockResourceArgs,
    outputs: dict[str, object],
    *,
    resource_id: str,
) -> tuple[str, dict[str, object]]:
    """Inject computed provider outputs needed by the managed stack tests."""
    resource_id, outputs = _apply_data_plane_outputs(
        args,
        outputs,
        resource_id=resource_id,
    )
    resource_id, outputs = _apply_identity_outputs(
        args,
        outputs,
        resource_id=resource_id,
    )
    resource_id, outputs = _apply_edge_outputs(
        args,
        outputs,
        resource_id=resource_id,
    )
    outputs.setdefault("id", resource_id)
    return resource_id, outputs


def _apply_data_plane_outputs(
    args: mocks.MockResourceArgs,
    outputs: dict[str, object],
    *,
    resource_id: str,
) -> tuple[str, dict[str, object]]:
    """Provide computed outputs for data-plane resources."""
    if args.typ.endswith("logGroup:LogGroup"):
        outputs["arn"] = f"arn:aws:logs:eu-central-1:123456789012:log-group:{args.name}"
    elif args.typ.endswith("cluster:Cluster") and "/docdb/" in args.typ:
        outputs["arn"] = f"arn:aws:rds:eu-central-1:123456789012:cluster:{args.name}"
        outputs["clusterIdentifier"] = args.inputs.get("clusterIdentifier", args.name)
        outputs["endpoint"] = f"{args.name}.cluster.local"
    elif args.typ.endswith("subnetGroup:SubnetGroup") and "/docdb/" in args.typ:
        outputs["name"] = f"{args.name}-subnets"
    elif args.typ.endswith("replicationGroup:ReplicationGroup"):
        outputs["arn"] = (
            "arn:aws:elasticache:eu-central-1:123456789012:replicationgroup:"
            f"{args.name}"
        )
        outputs["primaryEndpointAddress"] = f"{args.name}.cache.local"
    elif args.typ.endswith("subnetGroup:SubnetGroup") and "/elasticache/" in args.typ:
        outputs["name"] = f"{args.name}-subnets"
    return resource_id, outputs


def _apply_identity_outputs(
    args: mocks.MockResourceArgs,
    outputs: dict[str, object],
    *,
    resource_id: str,
) -> tuple[str, dict[str, object]]:
    """Provide computed outputs for IAM, ECS, ECR, and Secrets Manager."""
    if args.typ.endswith("cluster:Cluster") and "/ecs/" in args.typ:
        outputs["arn"] = f"arn:aws:ecs:eu-central-1:123456789012:cluster/{args.name}"
    elif args.typ.endswith("service:Service"):
        outputs["arn"] = f"arn:aws:ecs:eu-central-1:123456789012:service/{args.name}"
    elif args.typ.endswith("taskDefinition:TaskDefinition"):
        outputs["arn"] = (
            f"arn:aws:ecs:eu-central-1:123456789012:task-definition/{args.name}:1"
        )
    elif args.typ.endswith("repository:Repository"):
        outputs["arn"] = (
            f"arn:aws:ecr:eu-central-1:123456789012:repository/{outputs['name']}"
        )
        outputs["repositoryUrl"] = (
            f"123456789012.dkr.ecr.eu-central-1.amazonaws.com/{outputs['name']}"
        )
    elif args.typ.endswith("accessKey:AccessKey"):
        outputs["secret"] = pulumi.Output.secret("mock-secret-access-key")
    elif args.typ.endswith("role:Role"):
        outputs["arn"] = f"arn:aws:iam::123456789012:role/{outputs['name']}"
    elif args.typ.endswith("user:User"):
        outputs["arn"] = f"arn:aws:iam::123456789012:user/{outputs['name']}"
    elif args.typ.endswith("secret:Secret"):
        outputs["arn"] = (
            f"arn:aws:secretsmanager:eu-central-1:123456789012:secret:{args.name}"
        )
    return resource_id, outputs


def _apply_edge_outputs(
    args: mocks.MockResourceArgs,
    outputs: dict[str, object],
    *,
    resource_id: str,
) -> tuple[str, dict[str, object]]:
    """Provide computed outputs for network edge resources and queues."""
    if args.typ.endswith("securityGroup:SecurityGroup"):
        outputs["arn"] = (
            f"arn:aws:ec2:eu-central-1:123456789012:security-group/{args.name}"
        )
    elif args.typ.endswith("listener:Listener"):
        outputs["arn"] = (
            "arn:aws:elasticloadbalancing:eu-central-1:123456789012:listener/"
            f"{args.name}"
        )
    elif args.typ.endswith("loadBalancer:LoadBalancer"):
        outputs["arn"] = (
            "arn:aws:elasticloadbalancing:eu-central-1:123456789012:"
            f"loadbalancer/app/{args.name}/123"
        )
        outputs["dnsName"] = f"{args.name}.elb.amazonaws.com"
        outputs["zoneId"] = "ZTEST123"
    elif args.typ.endswith("targetGroup:TargetGroup"):
        outputs["arn"] = (
            "arn:aws:elasticloadbalancing:eu-central-1:123456789012:"
            f"targetgroup/{args.name}/123"
        )
    elif args.typ.endswith("queue:Queue"):
        resource_id = (
            f"https://sqs.eu-central-1.amazonaws.com/123456789012/{outputs['name']}"
        )
        outputs["arn"] = f"arn:aws:sqs:eu-central-1:123456789012:{outputs['name']}"
    return resource_id, outputs


class SimpleMocks(mocks.Mocks):
    """Pulumi mocks that echo inputs for unit testing."""

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        """Return synthetic outputs for the resource types used in the stack."""
        resource_id = f"{args.name}_id"
        outputs = dict(args.inputs)
        outputs.setdefault("name", args.inputs.get("name", args.name))
        return _resource_mock_outputs(args, outputs, resource_id=resource_id)

    def call(self, args: mocks.MockCallArgs) -> dict:
        """Return inputs directly for mocked invoke calls."""
        return args.inputs


class RecordingMocks(SimpleMocks):
    """Pulumi mocks that retain resource inputs for focused assertions."""

    def __init__(self) -> None:
        """Initialize the in-memory resource call log."""
        self.resources: list[dict[str, object]] = []

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        """Record resource inputs before delegating to the default mock outputs."""
        self.resources.append(
            {
                "name": args.name,
                "type": args.typ,
                "inputs": dict(args.inputs),
            }
        )
        return super().new_resource(args)


def _run_pulumi_program(
    program: Callable[[], None],
    *,
    test_mocks: mocks.Mocks | None = None,
) -> None:
    """Execute a Pulumi program with mocks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        test_mocks = test_mocks or SimpleMocks()
        monitor = mocks.MockMonitor(test_mocks)
        mocks.set_mocks(
            test_mocks,
            project="user-service-infrastructure",
            stack="unit",
            monitor=monitor,
        )
        loop.run_until_complete(stack.run_pulumi_func(program))
        loop.run_until_complete(asyncio.sleep(0))
        for assertion in _PENDING_OUTPUT_ASSERTIONS:
            assertion()
    finally:
        _PENDING_OUTPUT_ASSERTIONS.clear()
        settings.reset_options(project=None, stack=None)
        loop.close()
        asyncio.set_event_loop(None)


def _assert_output_value(output: pulumi.Output, expected: object) -> None:
    """Assert a Pulumi Output resolves to the expected value."""
    called = False

    def check(value: object) -> None:
        nonlocal called
        called = True
        assert value == expected, f"Expected {expected!r}, got {value!r}"

    def verify_called() -> None:
        assert called, "Expected Output.apply callback to run under Pulumi mocks"

    output.apply(check)
    _PENDING_OUTPUT_ASSERTIONS.append(verify_called)


@contextmanager
def mocked_pulumi_context(
    config_values: dict[str, object] | None = None,
    *,
    aws_config_values: dict[str, object] | None = None,
    credentials_present: bool = False,
    project_name: str | None = None,
) -> Iterator[Mock]:
    """Patch Pulumi config/project helpers for deterministic tests."""
    config_values = config_values or {}
    aws_config_values = aws_config_values or {}

    def config_methods(values: dict[str, object]) -> Mock:
        config_mock = Mock()
        config_mock.get.side_effect = lambda key, default=None: values.get(key, default)
        config_mock.get_int.side_effect = lambda key: values.get(key)
        config_mock.get_secret.side_effect = lambda key: (
            pulumi.Output.secret(values[key]) if key in values else None
        )
        return config_mock

    with ExitStack() as stack:
        config_patch = stack.enter_context(patch("app.environment.pulumi.Config"))
        config_instances = {
            "": config_methods(config_values),
            "aws": config_methods(aws_config_values),
        }
        config_patch.side_effect = lambda namespace="": config_instances[namespace]
        stack.enter_context(
            patch(
                "app.environment.has_aws_credentials",
                return_value=credentials_present,
            )
        )

        if project_name is not None:
            stack.enter_context(
                patch("app.environment.pulumi.get_project", return_value=project_name)
            )

        yield config_instances[""]


def test_stack_tag_combines_service_and_environment() -> None:
    """Combine explicit service/environment into a stack tag."""

    def program() -> None:
        """Export the derived stack tag for assertion."""
        env_settings = EnvironmentSettings(
            "unit", environment="staging", service_name="billing"
        )
        pulumi.export("stackTag", env_settings.stack_tag)
        _assert_output_value(env_settings.stack_tag, "billing-staging")

    _run_pulumi_program(program)


def test_default_tags_use_service_and_environment() -> None:
    """Build default tags from explicit service/environment values."""

    def program() -> None:
        """Export default tags for explicit values."""
        env_settings = EnvironmentSettings(
            "unit", environment="production", service_name="edge"
        )
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "edge",
                "Environment": "production",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )

    _run_pulumi_program(program)


def test_environment_falls_back_to_config_value() -> None:
    """Use the config value when environment is not passed."""

    def program() -> None:
        """Export resolved fields for config-based environment."""
        env_settings = EnvironmentSettings("unit")
        pulumi.export("environment", env_settings.environment)
        pulumi.export("serviceName", env_settings.service_name)
        pulumi.export("stackTag", env_settings.stack_tag)
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(env_settings.environment, "qa")
        _assert_output_value(env_settings.service_name, "user-service-infrastructure")
        _assert_output_value(env_settings.stack_tag, "user-service-infrastructure-qa")
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "user-service-infrastructure",
                "Environment": "qa",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )

    with mocked_pulumi_context({"environment": "qa"}) as config_instance:
        _run_pulumi_program(program)

    assert config_instance.get.call_args_list == [
        call("environment"),
        call("serviceName"),
        call("owner"),
        call("costCenter"),
    ]


def test_environment_defaults_to_dev_when_unset() -> None:
    """Default environment to dev when no config is set."""

    def program() -> None:
        """Export resolved fields for default environment."""
        env_settings = EnvironmentSettings("unit")
        pulumi.export("environment", env_settings.environment)
        pulumi.export("serviceName", env_settings.service_name)
        pulumi.export("stackTag", env_settings.stack_tag)
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(env_settings.environment, "dev")
        _assert_output_value(env_settings.service_name, "user-service-infrastructure")
        _assert_output_value(env_settings.stack_tag, "user-service-infrastructure-dev")
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "user-service-infrastructure",
                "Environment": "dev",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )

    with mocked_pulumi_context():
        _run_pulumi_program(program)


def test_service_name_falls_back_to_config_value() -> None:
    """Use the config value when service name is not passed."""

    def program() -> None:
        """Export resolved fields for config-based service name."""
        env_settings = EnvironmentSettings("unit", environment="qa")
        pulumi.export("serviceName", env_settings.service_name)
        pulumi.export("stackTag", env_settings.stack_tag)
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(env_settings.service_name, "billing")
        _assert_output_value(env_settings.stack_tag, "billing-qa")
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "billing",
                "Environment": "qa",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )

    with mocked_pulumi_context({"serviceName": "billing"}):
        _run_pulumi_program(program)


def test_service_name_defaults_to_project_name() -> None:
    """Default service name to the Pulumi project name."""

    def program() -> None:
        """Export resolved fields for project-name fallback."""
        env_settings = EnvironmentSettings("unit", environment="qa")
        pulumi.export("serviceName", env_settings.service_name)
        pulumi.export("stackTag", env_settings.stack_tag)
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(env_settings.service_name, "project-fallback")
        _assert_output_value(env_settings.stack_tag, "project-fallback-qa")
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "project-fallback",
                "Environment": "qa",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )

    with mocked_pulumi_context(project_name="project-fallback"):
        _run_pulumi_program(program)


def test_default_tags_allow_owner_and_cost_center_overrides() -> None:
    """Let stack config override the template defaults for shared tags."""

    def program() -> None:
        """Export default tags for owner and cost-center overrides."""
        env_settings = EnvironmentSettings("unit", environment="qa")
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "user-service-infrastructure",
                "Environment": "qa",
                "Owner": "team-platform",
                "CostCenter": "cost-123",
            },
        )

    with mocked_pulumi_context({"owner": "team-platform", "costCenter": "cost-123"}):
        _run_pulumi_program(program)


def test_default_tags_trim_owner_and_cost_center_config_values() -> None:
    """Normalize padded config values before exporting shared tags."""

    def program() -> None:
        """Export normalized tags from config-backed owner values."""
        env_settings = EnvironmentSettings("unit", environment="qa")
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "user-service-infrastructure",
                "Environment": "qa",
                "Owner": "team-platform",
                "CostCenter": "cost-123",
            },
        )

    with mocked_pulumi_context(
        {"owner": " team-platform ", "costCenter": " cost-123 "}
    ):
        _run_pulumi_program(program)


def test_default_tags_fall_back_when_owner_and_cost_center_are_blank() -> None:
    """Replace blank owner metadata with the documented template defaults."""

    def program() -> None:
        """Export default tags for blank config values."""
        env_settings = EnvironmentSettings("unit", environment="qa")
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "user-service-infrastructure",
                "Environment": "qa",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )

    with mocked_pulumi_context({"owner": "   ", "costCenter": ""}):
        _run_pulumi_program(program)


def test_default_tags_allow_explicit_owner_and_cost_center_overrides() -> None:
    """Honor explicit owner and cost-center overrides before config defaults."""

    def program() -> None:
        """Export default tags for explicit tag overrides."""
        env_settings = EnvironmentSettings(
            "unit",
            environment="qa",
            service_name="billing",
            owner="payments",
            cost_center="finops",
        )
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "billing",
                "Environment": "qa",
                "Owner": "payments",
                "CostCenter": "finops",
            },
        )

    _run_pulumi_program(program)


def test_default_tags_trim_explicit_owner_and_cost_center_overrides() -> None:
    """Normalize explicit owner overrides before exporting default tags."""

    def program() -> None:
        """Export default tags for explicit padded tag overrides."""
        env_settings = EnvironmentSettings(
            "unit",
            environment="qa",
            service_name="billing",
            owner=" payments ",
            cost_center=" finops ",
        )
        pulumi.export("defaultTags", env_settings.default_tags)
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "billing",
                "Environment": "qa",
                "Owner": "payments",
                "CostCenter": "finops",
            },
        )

    _run_pulumi_program(program)


def test_resolve_config_value_preserves_explicit_configured_and_default_paths() -> None:
    """Keep resolution semantics stable for explicit, configured, and default values."""
    assert resolve_config_value("prod", "staging", default="dev") == "prod"
    assert resolve_config_value(None, "staging", default="dev") == "staging"
    assert resolve_config_value(None, None, default="dev") == "dev"


def test_stack_metadata_helpers_keep_the_four_field_layout() -> None:
    """Map service, environment, owner, and cost center without index drift."""
    metadata = _stack_metadata_from_outputs(
        ["billing", "qa", "team-platform", "cost-123"]
    )

    assert metadata == ("billing", "qa", "team-platform", "cost-123")
    assert _stack_tag_from_parts(metadata) == "billing-qa"
    assert _default_tags_from_parts(metadata) == {
        "Project": "billing",
        "Environment": "qa",
        "Owner": "team-platform",
        "CostCenter": "cost-123",
    }


def _assert_config_error(config_values: dict[str, object], message: str) -> None:
    """Assert invalid config is rejected inside the mocked Pulumi runtime."""

    def program() -> None:
        """Instantiate the component to trigger config validation."""
        EnvironmentSettings("unit")

    with mocked_pulumi_context(config_values):
        with pytest.raises(ValueError, match=rf"^{re.escape(message)}\.$"):
            _run_pulumi_program(program)


def test_environment_rejects_blank_config_value() -> None:
    """Reject empty environment config instead of silently defaulting."""
    _assert_config_error({"environment": ""}, "environment must not be empty")


def test_environment_rejects_padded_config_value() -> None:
    """Reject padded environment config to keep exported identifiers stable."""
    _assert_config_error(
        {"environment": " qa "},
        "environment must not contain surrounding whitespace",
    )


def test_service_name_rejects_invalid_config_value() -> None:
    """Reject service config that would produce invalid stack metadata."""
    _assert_config_error(
        {"serviceName": "Billing_API"},
        "service name must use lowercase letters, digits, and hyphens only",
    )


def test_component_registers_expected_type_token() -> None:
    """Pass the expected type token into the public ComponentResource API."""
    captured: dict[str, tuple[str, str]] = {}
    original_init = pulumi.ComponentResource.__init__

    def tracked_init(
        self: pulumi.ComponentResource,
        type_token: str,
        name: str,
        props: object = None,
        opts: object = None,
        *args: object,
        **kwargs: object,
    ) -> None:
        if isinstance(self, EnvironmentSettings):
            captured["component"] = (type_token, name)
        original_init(self, type_token, name, props, opts, *args, **kwargs)

    def program() -> None:
        """Capture the component instance for type checks."""
        env_settings = EnvironmentSettings("unit")
        pulumi.export("environment", env_settings.environment)

    with patch.object(pulumi.ComponentResource, "__init__", new=tracked_init):
        _run_pulumi_program(program)

    assert captured.get("component") == (
        "user-service-infrastructure:core:EnvironmentSettings",
        "unit",
    )


def test_build_resource_name_hashes_when_length_limit_is_applied() -> None:
    """Keep AWS-length truncation deterministic for resource naming."""
    short_name = build_resource_name("user-service-dev", "alb", max_length=32)
    tiny_name = build_resource_name(
        "user-service-with-a-very-long-environment-name",
        "load-balancer",
        max_length=6,
    )

    assert short_name.startswith("user-service-dev-alb")
    assert len(tiny_name) == 6
    assert build_resource_name(
        "user-service-with-a-very-long-environment-name",
        "load-balancer",
        max_length=32,
    ) == build_resource_name(
        "user-service-with-a-very-long-environment-name",
        "load-balancer",
        max_length=32,
    )
    assert (
        len(
            build_resource_name(
                "user-service-with-a-very-long-environment-name",
                "load-balancer",
                max_length=32,
            )
        )
        <= 32
    )


def test_resolve_deployment_mode_handles_auto_and_explicit_modes() -> None:
    """Keep deployment mode resolution stable for preview and managed paths."""
    assert resolve_deployment_mode("auto", credentials_present=False) == "preview"
    assert resolve_deployment_mode("auto", credentials_present=True) == "managed"
    assert resolve_deployment_mode("preview", credentials_present=True) == "preview"
    assert resolve_deployment_mode("managed", credentials_present=False) == "managed"


def test_normalize_choice_rejects_unknown_values() -> None:
    """Reject invalid enumerated config values with a clear error."""
    with pytest.raises(
        ValueError,
        match=r"^deployment mode must be one of: managed, preview\.$",
    ):
        _normalize_choice(
            "invalid",
            allowed={"managed", "preview"},
            label="deployment mode",
        )


def test_normalize_csv_ignores_empty_entries_and_falls_back_to_default() -> None:
    """Trim CSV segments and preserve defaults when no concrete values remain."""
    assert _normalize_csv(" one, ,two ", default=("default",)) == ("one", "two")
    assert _normalize_csv(" , ", default=("default",)) == ("default",)


def test_get_int_preserves_explicit_zero_and_defaults_missing_values() -> None:
    """Return configured zero values instead of replacing them with defaults."""
    config = Mock()
    config.get_int.side_effect = lambda key: {"zero": 0}.get(key)

    assert _get_int(config, "zero", default=42) == 0
    assert _get_int(config, "missing", default=42) == 42


def test_secret_value_supports_preview_plaintext_and_rejects_managed_plaintext() -> (
    None
):
    """Allow preview-only plaintext while rejecting managed plain-text secrets."""
    config_with_plaintext = Mock()
    config_with_plaintext.get_secret.return_value = None
    config_with_plaintext.get.return_value = "plaintext-secret"

    with patch(
        "app.environment.pulumi.Output.secret",
        side_effect=lambda value: f"secret:{value}",
    ):
        plaintext_secret = _secret_value(
            config_with_plaintext,
            "appSecret",
            managed=False,
            preview_default="preview-secret",
        )
    assert plaintext_secret == "secret:plaintext-secret"

    with pytest.raises(
        ValueError,
        match=(
            r"^appSecret is configured as plain text; re-set it with "
            r"`pulumi config set --secret appSecret <value>` for managed "
            r"deployments\.$"
        ),
    ):
        _secret_value(
            config_with_plaintext,
            "appSecret",
            managed=True,
            preview_default="preview-secret",
        )


def test_secret_value_rejects_missing_managed_apply() -> None:
    """Fail fast when managed deployments omit required secret inputs."""
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


def test_validate_parallel_lengths_rejects_misaligned_subnet_sets() -> None:
    """Reject network config where AZs and subnet partitions drift apart."""
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


def test_has_aws_credentials_detects_supported_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detect both static-key and profile-based AWS credential contexts."""
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    assert has_aws_credentials() is False

    monkeypatch.setenv("AWS_PROFILE", "default")
    assert has_aws_credentials() is True


def test_resolve_stack_settings_defaults_to_preview_without_credentials() -> None:
    """Resolve the full stack contract for the repo's no-credential CI path."""
    captured: dict[str, object] = {}

    def program() -> None:
        """Resolve stack settings inside the mocked Pulumi runtime."""
        env_settings = EnvironmentSettings("unit", environment="dev")
        captured["settings"] = resolve_stack_settings(env_settings)

    with mocked_pulumi_context(
        {"apiBaseUrl": "https://user.dev.internal", "serviceName": "user-service"}
    ):
        _run_pulumi_program(program)

    settings_model = captured["settings"]

    assert settings_model is not None
    assert settings_model.deployment_mode == "preview"
    assert settings_model.region == "eu-central-1"
    assert settings_model.runtime.app_env == "prod"
    assert settings_model.runtime.app_debug == "0"
    assert settings_model.runtime.api_base_url == "https://user.dev.internal"
    assert settings_model.runtime.api_url == "https://user.dev.internal"
    assert (
        settings_model.runtime.access_logs_bucket_name == "preview-only-alb-access-logs"
    )
    assert settings_model.queues.health_check == "health-check-queue"
    assert settings_model.network.availability_zones == (
        "eu-central-1a",
        "eu-central-1b",
    )
    assert settings_model.social.github_redirect_uri.endswith(
        "/api/auth/social/github/callback"
    )


def test_resolve_stack_settings_rejects_managed_apply_without_required_inputs() -> None:
    """Reject incomplete managed configuration outside preview mode."""
    error_pattern = (
        r"^accessLogsBucketName must be configured for managed deployments\.$"
    )

    def program() -> None:
        """Resolve managed settings inside the mocked runtime."""
        env_settings = EnvironmentSettings("unit", environment="prod")
        resolve_stack_settings(env_settings)

    with (
        mocked_pulumi_context({"deploymentMode": "managed"}),
        patch("app.environment.pulumi.runtime.is_dry_run", return_value=False),
    ):
        with pytest.raises(
            ValueError,
            match=error_pattern,
        ):
            _run_pulumi_program(program)


def test_main_exports_expected_outputs() -> None:
    """Execute the Pulumi entrypoint and validate exported outputs."""

    def program() -> None:
        """Run the pulumi __main__ module inside the mocked runtime."""
        sys.path.insert(0, str(PROJECT_ROOT / "pulumi"))
        try:
            module_globals = runpy.run_path(str(PULUMI_MAIN))
        finally:
            sys.path.pop(0)

        stack_component = module_globals["stack"]
        env_settings = stack_component.environment_settings
        _assert_output_value(env_settings.environment, "dev")
        _assert_output_value(env_settings.service_name, "user-service")
        _assert_output_value(env_settings.stack_tag, "user-service-dev")
        _assert_output_value(
            env_settings.default_tags,
            {
                "Project": "user-service",
                "Environment": "dev",
                "Owner": "platform",
                "CostCenter": "engineering",
            },
        )
        _assert_output_value(
            stack_component.compute.outputs.service_url, "https://user.dev.internal"
        )
        _assert_output_value(
            stack_component.compute.outputs.web_repository_url,
            "123456789012.dkr.ecr.eu-central-1.amazonaws.com/user-service",
        )

    with mocked_pulumi_context(
        {
            "deploymentMode": "preview",
            "serviceName": "user-service",
            "apiBaseUrl": "https://user.dev.internal",
        }
    ):
        _run_pulumi_program(program)


def test_resolve_stack_settings_preserves_zero_capacity_overrides() -> None:
    """Keep explicit zero-valued numeric config instead of falling back to defaults."""
    captured: dict[str, object] = {}

    def program() -> None:
        """Resolve stack settings with zero-valued capacity and data overrides."""
        env_settings = EnvironmentSettings("unit", environment="dev")
        captured["settings"] = resolve_stack_settings(env_settings)

    with mocked_pulumi_context(
        {
            "serviceName": "user-service",
            "containerPort": 0,
            "webDesiredCount": 0,
            "workerDesiredCount": 0,
            "documentDbInstanceCount": 0,
            "documentDbPort": 0,
            "documentDbBackupRetentionDays": 0,
            "redisReplicasPerNodeGroup": 0,
            "redisPort": 0,
            "redisSnapshotRetentionLimit": 0,
            "appEnv": "staging",
            "appDebug": "1",
        }
    ):
        _run_pulumi_program(program)

    settings_model = captured["settings"]
    assert settings_model is not None
    assert settings_model.capacity.container_port == 0
    assert settings_model.capacity.web_desired_count == 0
    assert settings_model.capacity.worker_desired_count == 0
    assert settings_model.documentdb.instance_count == 0
    assert settings_model.documentdb.port == 0
    assert settings_model.documentdb.backup_retention_days == 0
    assert settings_model.redis.replicas_per_node_group == 0
    assert settings_model.redis.port == 0
    assert settings_model.redis.snapshot_retention_limit == 0
    assert settings_model.runtime.app_env == "staging"
    assert settings_model.runtime.app_debug == "1"


def test_compute_common_environment_uses_runtime_app_flags() -> None:
    """Populate APP_ENV and APP_DEBUG from runtime settings instead of literals."""
    compute = object.__new__(ComputePlane)
    settings_model = Mock()
    settings_model.region = "eu-central-1"
    settings_model.runtime.app_env = "staging"
    settings_model.runtime.app_debug = "1"
    settings_model.runtime.api_base_url = "https://users.example.com"
    settings_model.runtime.api_url = "https://users.example.com"
    settings_model.runtime.cors_allow_origin = "^https://users\\.example\\.com$"
    settings_model.runtime.mail_sender = "noreply@example.com"
    settings_model.runtime.jwt_issuer = "issuer"
    settings_model.runtime.jwt_audience = "audience"
    settings_model.runtime.emf_namespace = "UserService/Test"
    settings_model.runtime.aws_sqs_endpoint_base = (
        "https://sqs.eu-central-1.amazonaws.com"
    )
    settings_model.runtime.aws_sqs_port = "443"
    settings_model.social.github_client_id = "github-client"
    settings_model.social.github_redirect_uri = "https://users.example.com/github"
    settings_model.social.google_client_id = "google-client"
    settings_model.social.google_redirect_uri = "https://users.example.com/google"
    settings_model.social.facebook_client_id = "facebook-client"
    settings_model.social.facebook_redirect_uri = "https://users.example.com/facebook"
    settings_model.social.facebook_graph_api_version = "v19.0"
    settings_model.social.twitter_client_id = "twitter-client"
    settings_model.social.twitter_redirect_uri = "https://users.example.com/twitter"

    messaging = Mock()
    messaging.outputs.health_check_access_key_id = "access-key-id"
    messaging.outputs.queue_urls = {
        "sendEmail": "https://queue/send-email",
        "failedSendEmail": "https://queue/failed-send-email",
        "insertUserBatch": "https://queue/insert-user-batch",
        "domainEvents": "https://queue/domain-events",
        "failedDomainEvents": "https://queue/failed-domain-events",
    }

    with patch.object(
        compute,
        "_queue_dsn",
        side_effect=lambda queue_url, region: f"{region}:{queue_url}",
    ):
        environment = compute._common_environment(
            settings_model,
            messaging,
            include_worker_name=False,
        )
    values = {entry["name"]: entry["value"] for entry in environment}

    assert values["APP_ENV"] == "staging"
    assert values["APP_DEBUG"] == "1"


def test_resolve_stack_settings_requires_social_secrets_for_enabled_providers() -> None:
    """Require managed social-provider secrets only when a provider is enabled."""

    def program() -> None:
        """Resolve managed settings with GitHub OAuth enabled but no secret set."""
        env_settings = EnvironmentSettings("unit", environment="prod")
        resolve_stack_settings(env_settings)

    managed_config = {
        "deploymentMode": "managed",
        "serviceName": "user-service",
        "accessLogsBucketName": "shared-alb-access-logs",
        "githubClientId": "github-client",
        "documentDbPassword": "mongo-secret",
        "redisAuthToken": "redis-secret",
        "appSecret": "app-secret",
        "mailerDsn": "smtp://mail.example.com:587",
        "oauthEncryptionKey": "oauth-encryption-key",
        "oauthPassphrase": "oauth-passphrase",
        "twoFactorEncryptionKey": "two-factor-key",
        "oauthPrivateKeyPem": "private-key",
        "oauthPublicKeyPem": "public-key",
    }

    with (
        mocked_pulumi_context(managed_config),
        patch("app.environment.pulumi.runtime.is_dry_run", return_value=False),
    ):
        with pytest.raises(
            ValueError,
            match=(
                r"^githubClientSecret must be configured as a secret for managed "
                r"deployments\.$"
            ),
        ):
            _run_pulumi_program(program)


def test_managed_stack_uses_preview_credential_skips_and_scoped_data_egress() -> None:
    """Keep provider preview skips and managed data-plane networking intentional."""
    managed_config = {
        "deploymentMode": "managed",
        "serviceName": "user-service",
        "accessLogsBucketName": "shared-alb-access-logs",
        "documentDbPassword": "mongo-secret",
        "redisAuthToken": "redis-secret",
        "appSecret": "app-secret",
        "mailerDsn": "smtp://mail.example.com:587",
        "oauthEncryptionKey": "oauth-encryption-key",
        "oauthPassphrase": "oauth-passphrase",
        "twoFactorEncryptionKey": "two-factor-key",
        "oauthPrivateKeyPem": "private-key",
        "oauthPublicKeyPem": "public-key",
    }
    recording_mocks = RecordingMocks()

    def program() -> None:
        """Instantiate a managed stack with a single-node Redis topology."""
        UserServiceStack("managed-stack")

    with mocked_pulumi_context(
        {**managed_config, "redisReplicasPerNodeGroup": 0},
        aws_config_values={"region": "eu-central-1"},
    ):
        _run_pulumi_program(program, test_mocks=recording_mocks)

    provider = next(
        resource
        for resource in recording_mocks.resources
        if resource["name"] == "managed-provider"
    )
    provider_inputs = provider["inputs"]
    assert provider_inputs["skipCredentialsValidation"] == "false"
    assert provider_inputs["skipMetadataApiCheck"] == "false"
    assert provider_inputs["skipRequestingAccountId"] == "false"
    assert provider_inputs["skipRegionValidation"] == "false"

    redis_replication_group = next(
        resource
        for resource in recording_mocks.resources
        if resource["name"] == "user-service-redis"
    )
    redis_inputs = redis_replication_group["inputs"]
    assert redis_inputs["automaticFailoverEnabled"] is False
    assert redis_inputs["multiAzEnabled"] is False
    assert redis_inputs["numCacheClusters"] == 1

    documentdb_security_group = next(
        resource
        for resource in recording_mocks.resources
        if resource["name"] == "user-service-documentdb-sg"
    )
    redis_security_group = next(
        resource
        for resource in recording_mocks.resources
        if resource["name"] == "user-service-redis-sg"
    )
    assert documentdb_security_group["inputs"]["egress"][0]["cidrBlocks"] == [
        "10.42.0.0/16"
    ]
    assert redis_security_group["inputs"]["egress"][0]["cidrBlocks"] == ["10.42.0.0/16"]


def test_managed_stack_requires_at_least_one_documentdb_instance() -> None:
    """Reject a managed DocumentDB cluster that would expose no instances."""
    managed_config = {
        "deploymentMode": "managed",
        "serviceName": "user-service",
        "accessLogsBucketName": "shared-alb-access-logs",
        "documentDbPassword": "mongo-secret",
        "redisAuthToken": "redis-secret",
        "appSecret": "app-secret",
        "mailerDsn": "smtp://mail.example.com:587",
        "oauthEncryptionKey": "oauth-encryption-key",
        "oauthPassphrase": "oauth-passphrase",
        "twoFactorEncryptionKey": "two-factor-key",
        "oauthPrivateKeyPem": "private-key",
        "oauthPublicKeyPem": "public-key",
    }

    def program() -> None:
        """Instantiate a managed stack with an invalid zero-instance topology."""
        UserServiceStack("managed-stack")

    with mocked_pulumi_context(
        {**managed_config, "documentDbInstanceCount": 0},
        aws_config_values={"region": "eu-central-1"},
    ):
        with pytest.raises(
            ValueError,
            match=(
                r"^documentDbInstanceCount must be at least 1 for managed "
                r"deployments\.$"
            ),
        ):
            _run_pulumi_program(program)


def test_managed_stack_percent_encodes_data_plane_connection_urls() -> None:
    """Percent-encode reserved credentials before exporting managed URLs."""
    managed_config = {
        "deploymentMode": "managed",
        "serviceName": "user-service",
        "accessLogsBucketName": "shared-alb-access-logs",
        "documentDbUsername": "user@example.com",
        "documentDbPassword": "mongo:/?#@secret",
        "redisAuthToken": "redis:/?#@token",
        "appSecret": "app-secret",
        "mailerDsn": "smtp://mail.example.com:587",
        "oauthEncryptionKey": "oauth-encryption-key",
        "oauthPassphrase": "oauth-passphrase",
        "twoFactorEncryptionKey": "two-factor-key",
        "oauthPrivateKeyPem": "private-key",
        "oauthPublicKeyPem": "public-key",
    }
    recording_mocks = RecordingMocks()

    def program() -> None:
        """Instantiate a managed stack and record the derived data secrets."""
        UserServiceStack("managed-stack")

    with mocked_pulumi_context(
        managed_config,
        aws_config_values={"region": "eu-central-1"},
    ):
        _run_pulumi_program(program, test_mocks=recording_mocks)

    documentdb_secret_version = next(
        resource
        for resource in recording_mocks.resources
        if resource["name"] == "user-service-documentdb-url-version"
    )
    redis_secret_version = next(
        resource
        for resource in recording_mocks.resources
        if resource["name"] == "user-service-redis-url-version"
    )
    documentdb_secret_string = documentdb_secret_version["inputs"]["secretString"][
        "value"
    ]
    redis_secret_string = redis_secret_version["inputs"]["secretString"]["value"]

    assert documentdb_secret_string.startswith(
        "mongodb://user%40example.com:mongo%3A%2F%3F%23%40secret@"
    )
    assert "user@example.com:mongo:/?#@secret@" not in documentdb_secret_string
    assert redis_secret_string.startswith("rediss://:redis%3A%2F%3F%23%40token@")
    assert ":redis:/?#@token@" not in redis_secret_string


def test_register_outputs_maps_component_properties() -> None:
    """Register outputs for component properties consistently."""
    original_register = pulumi.ComponentResource.register_outputs

    def program() -> None:
        """Export component outputs for register_outputs tracking."""
        env_settings = EnvironmentSettings("unit", environment="qa", service_name="svc")
        pulumi.export("stackTag", env_settings.stack_tag)
        pulumi.export("defaultTags", env_settings.default_tags)

    with patch.object(
        pulumi.ComponentResource,
        "register_outputs",
        autospec=True,
        wraps=original_register,
    ) as mock_register:
        _run_pulumi_program(program)

    env_calls = [
        register_call
        for register_call in mock_register.call_args_list
        if isinstance(register_call.args[0], EnvironmentSettings)
    ]
    assert env_calls, "EnvironmentSettings.register_outputs was not invoked"

    resource, outputs = env_calls[0].args
    assert set(outputs.keys()) == {
        "environment",
        "serviceName",
        "stackTag",
        "defaultTags",
    }
    assert outputs["environment"] is resource.environment
    assert outputs["serviceName"] is resource.service_name
    assert outputs["stackTag"] is resource.stack_tag
    assert outputs["defaultTags"] is resource.default_tags


def test_user_service_stack_preview_mode_exports_runtime_contract() -> None:
    """Exercise the preview-only stack path used by local and PR guardrail jobs."""

    def program() -> None:
        """Instantiate the top-level stack in preview mode."""
        stack_component = UserServiceStack("unit-stack")
        _assert_output_value(
            stack_component.compute.outputs.cluster_name, "user-service-dev-ecs"
        )
        _assert_output_value(
            stack_component.compute.outputs.load_balancer_dns_name,
            "user-service-dev-alb.elb.amazonaws.com",
        )
        _assert_output_value(
            stack_component.messaging.outputs.queue_urls["sendEmail"],
            "https://sqs.eu-central-1.amazonaws.com/preview/send-email",
        )
        _assert_output_value(
            stack_component.data.outputs.documentdb_endpoint,
            "user-service-dev-documentdb.local",
        )

    with mocked_pulumi_context(
        {"deploymentMode": "preview", "serviceName": "user-service"}
    ):
        _run_pulumi_program(program)


def test_user_service_stack_managed_mode_builds_managed_outputs_under_mocks() -> None:
    """Exercise the managed resource graph under Pulumi mocks."""

    managed_config = {
        "deploymentMode": "managed",
        "serviceName": "user-service",
        "accessLogsBucketName": "shared-alb-access-logs",
        "documentDbPassword": "mongo-secret",
        "redisAuthToken": "redis-secret",
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

    def program() -> None:
        """Instantiate the managed stack under mocks and assert key outputs."""
        stack_component = UserServiceStack("managed-stack")
        _assert_output_value(
            stack_component.compute.outputs.web_repository_url,
            "123456789012.dkr.ecr.eu-central-1.amazonaws.com/user-service",
        )
        _assert_output_value(
            stack_component.compute.outputs.worker_repository_url,
            "123456789012.dkr.ecr.eu-central-1.amazonaws.com/user-service-workers",
        )
        _assert_output_value(
            stack_component.compute.outputs.load_balancer_dns_name,
            "user-service-alb.elb.amazonaws.com",
        )
        _assert_output_value(
            stack_component.messaging.outputs.queue_urls["domainEvents"],
            "https://sqs.eu-central-1.amazonaws.com/123456789012/domain-events",
        )
        _assert_output_value(
            stack_component.data.outputs.redis_endpoint,
            "user-service-redis.cache.local",
        )

    with mocked_pulumi_context(
        managed_config,
        aws_config_values={"region": "eu-central-1"},
    ):
        _run_pulumi_program(program)


def test_user_service_stack_managed_mode_supports_https_and_image_overrides() -> None:
    """Exercise the HTTPS-listener path and explicit image overrides."""
    managed_config = {
        "deploymentMode": "managed",
        "serviceName": "user-service",
        "accessLogsBucketName": "shared-alb-access-logs",
        "certificateArn": (
            "arn:aws:acm:eu-central-1:123456789012:certificate/user-service"
        ),
        "webImage": "123456789012.dkr.ecr.eu-central-1.amazonaws.com/custom-web:sha",
        "workerImage": (
            "123456789012.dkr.ecr.eu-central-1.amazonaws.com/custom-worker:sha"
        ),
        "documentDbPassword": "mongo-secret",
        "redisAuthToken": "redis-secret",
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

    def program() -> None:
        """Instantiate the managed stack with HTTPS and explicit image URIs."""
        stack_component = UserServiceStack("managed-stack-https")
        _assert_output_value(
            stack_component.compute.outputs.load_balancer_dns_name,
            "user-service-alb.elb.amazonaws.com",
        )
        _assert_output_value(
            stack_component.compute.outputs.web_service_name,
            "user-service-dev-web",
        )

    with mocked_pulumi_context(
        managed_config,
        aws_config_values={"region": "eu-central-1"},
    ):
        _run_pulumi_program(program)
