"""Preserve existing S3 stack encryption without publishing checkpoint values."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Iterator
from urllib.parse import SplitResult, parse_qs, unquote, urlsplit

import yaml
from yaml.constructor import ConstructorError

if TYPE_CHECKING:
    from _pulumi_command_support import CommandContext


class StackConfigError(ValueError):
    """A stack configuration could not be verified without replacing its key."""


# This is deliberately the exact public projection returned by
# poc_workload_phase_entrypoint.workload_configuration.  It is closed so a
# caller cannot smuggle provider, backend, or secret settings through the
# workload path.
WORKLOAD_CONFIG_KEYS = frozenset(
    {
        "user-service-infrastructure:deploymentMode",
        "user-service-infrastructure:webRepositoryName",
        "user-service-infrastructure:workerRepositoryName",
        "user-service-infrastructure:webImage",
        "user-service-infrastructure:workerImage",
        "user-service-infrastructure:imageTagMutability",
        "user-service-infrastructure:executionRoleArn",
        "user-service-infrastructure:taskRoleArn",
        "user-service-infrastructure:appEnv",
        "user-service-infrastructure:appDebug",
        "user-service-infrastructure:apiBaseUrl",
        "user-service-infrastructure:apiUrl",
        "user-service-infrastructure:corsAllowOrigin",
        "user-service-infrastructure:certificateArn",
        "user-service-infrastructure:mailSender",
        "user-service-infrastructure:healthCheckPath",
        "user-service-infrastructure:healthCheckQueueName",
        "user-service-infrastructure:awsSqsEndpointBase",
        "user-service-infrastructure:awsSqsPort",
    }
)
MAX_WORKLOAD_CONFIG_VALUE_BYTES = 4096


class _StackConfigLoader(yaml.SafeLoader):
    """Do not let duplicate YAML keys hide an explicit unsafe provider setting."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        self.flatten_mapping(node)
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise ConstructorError(
                None, None, "Duplicate configuration keys", node.start_mark
            )
        return mapping


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise StackConfigError(message)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _read_json(context: CommandContext, command: list[str]) -> dict[str, Any]:
    result = context.runner(
        command,
        env={**context.env, "PULUMI_BACKEND_URL": context.backend_url},
        check=False,
        capture_output=True,
    )
    _require(result.returncode == 0, "Stack configuration metadata read failed.")
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise StackConfigError(
            "Invalid stack configuration metadata response."
        ) from None
    _require(isinstance(value, dict), "Invalid stack configuration metadata shape.")
    return value


def _yaml_document(path: Path) -> dict[str, Any]:
    _require(not path.is_symlink(), "Stack configuration symlinks are not allowed.")
    try:
        # This SafeLoader subclass only adds duplicate-key rejection.
        loader = _StackConfigLoader(path.read_text())
        try:
            value = loader.get_single_data()
        finally:
            loader.dispose()
    except (OSError, yaml.YAMLError):
        raise StackConfigError("Unable to read stack configuration YAML.") from None
    _require(isinstance(value, dict), "Stack configuration must be a YAML mapping.")
    return value


def _validate_backend(backend: SplitResult) -> None:
    _require(
        backend.scheme == "s3"
        and re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", backend.netloc)
        and not backend.query
        and not backend.fragment
        and all(
            p not in {".", "..", ""}
            for p in backend.path.removeprefix("/").split("/")
            if backend.path.removeprefix("/")
        ),
        "An exact S3 backend is required for shared stack configuration.",
    )


def _split_uri(value: str) -> SplitResult:
    """Convert malformed URI syntax into the guarded configuration error."""
    try:
        return urlsplit(value)
    except ValueError:
        raise StackConfigError(
            "Invalid stack backend or secrets provider URI."
        ) from None


def _region(context: CommandContext) -> str:
    """Require one unambiguous region from the trusted cloud configuration."""
    region = context.env.get("AWS_REGION") or context.env.get("AWS_DEFAULT_REGION", "")
    _require(
        re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", region)
        and all(
            not context.env.get(key) or context.env[key] == region
            for key in ("AWS_REGION", "AWS_DEFAULT_REGION")
        ),
        "AWS region configuration must pin one unambiguous region.",
    )
    return region


def _coordinates(context: CommandContext, stack: str) -> dict[str, str]:
    _require(
        not re.search(r"[%\\\x00-\x20]", context.backend_url),
        "An exact S3 backend cannot contain escapes or control characters.",
    )
    backend = _split_uri(context.backend_url)
    _validate_backend(backend)
    _require(
        context.env.get("PULUMI_BACKEND_URL", context.backend_url)
        == context.backend_url
        and not context.env.get("PULUMI_CLOUD_SECRET_OVERRIDE"),
        "Backend or cloud secrets override differs from the requested stack.",
    )
    account = context.env.get("AWS_ACCOUNT_ID", "")
    _require(
        re.fullmatch(r"[0-9]{12}", account),
        "AWS_ACCOUNT_ID must pin the stack account.",
    )
    project = _yaml_document(context.pulumi_dir / "Pulumi.yaml").get("name")
    _require(
        isinstance(project, str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+", project)
        and re.fullmatch(r"[A-Za-z0-9_.-]+", stack),
        "Exact project and unqualified stack names are required.",
    )
    prefix = backend.path.strip("/")
    key = f".pulumi/stacks/{project}/{stack}.json"
    return {
        "accountId": account,
        "region": _region(context),
        "project": str(project),
        "stack": stack,
        "backendUrl": context.backend_url,
        "bucket": backend.netloc,
        "key": f"{prefix}/{key}" if prefix else key,
    }


def _checkpoint_version(
    context: CommandContext, target: dict[str, str]
) -> dict[str, str]:
    metadata = _read_json(
        context,
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            target["bucket"],
            "--key",
            target["key"],
            "--expected-bucket-owner",
            target["accountId"],
            "--output",
            "json",
        ],
    )
    _require(
        isinstance(metadata.get("VersionId"), str)
        and metadata["VersionId"] not in {"", "null"}
        and isinstance(metadata.get("ETag"), str)
        and metadata["ETag"],
        "A versioned existing stack checkpoint is required.",
    )
    return {
        "checkpointVersionId": metadata["VersionId"],
        "checkpointETag": metadata["ETag"],
    }


def _validate_deployment(deployment: Any, target: dict[str, str]) -> None:
    _require(isinstance(deployment, dict), "Invalid stack deployment metadata.")
    prefix = f"urn:pulumi:{target['stack']}::{target['project']}::"
    resources = deployment.get("resources", [])
    # Official stack init stores provider state before the first root resource.
    # Existing nonempty inventories must still identify this exact stack.
    _require(
        isinstance(resources, list)
        and all(
            isinstance(r, dict) and str(r.get("urn", "")).startswith(prefix)
            for r in resources
        )
        and (
            not resources
            or any(
                r.get("urn")
                == f"{prefix}pulumi:pulumi:Stack::{target['project']}-{target['stack']}"
                for r in resources
            )
        )
        and not deployment.get("pending_operations"),
        "Checkpoint project, stack or pending operation precondition failed.",
    )


def _provider_state(context: CommandContext, target: dict[str, str]) -> dict[str, Any]:
    checkpoint = _read_json(
        context,
        [
            "pulumi",
            "-C",
            str(context.pulumi_dir),
            "stack",
            "export",
            "--stack",
            target["stack"],
            "--non-interactive",
        ],
    )
    deployment = checkpoint.get("deployment", {})
    _validate_deployment(deployment, target)
    provider = deployment.get("secrets_providers", {})
    _require(
        isinstance(provider, dict)
        and provider.get("type") == "cloud"
        and isinstance(provider.get("state"), dict),
        "Existing cloud secrets-provider state is required.",
    )
    state = provider["state"]
    _require(
        state.get("url") == context.secrets_provider,
        "Checkpoint secrets provider differs from requested provider.",
    )
    try:
        valid_key = bool(base64.b64decode(state.get("encryptedkey", ""), validate=True))
    except (ValueError, TypeError, binascii.Error):
        valid_key = False
    _require(
        valid_key,
        "Existing encrypted data key is required; key generation is forbidden.",
    )
    return provider


def _key_identity(context: CommandContext, account: str, region: str) -> str:
    provider = _split_uri(context.secrets_provider)
    _require(
        provider.scheme == "awskms"
        and not provider.fragment
        and region
        and parse_qs(provider.query, keep_blank_values=True) == {"region": [region]},
        "Secrets provider must use the pinned AWS region.",
    )
    identifier = unquote(provider.netloc + provider.path)
    _require(bool(identifier), "An existing KMS key identifier is required.")
    metadata = _read_json(
        context,
        [
            "aws",
            "kms",
            "describe-key",
            "--key-id",
            identifier,
            "--region",
            region,
            "--output",
            "json",
        ],
    ).get("KeyMetadata", {})
    return _validate_key_metadata(metadata, account, region)


def _validate_key_metadata(metadata: Any, account: str, region: str) -> str:
    arn = metadata.get("Arn", "") if isinstance(metadata, dict) else ""
    pieces = arn.split(":") if isinstance(arn, str) else []
    _require(
        len(pieces) == 6
        and pieces[0] == "arn"
        and pieces[2] == "kms"
        and pieces[3] == region
        and pieces[4] == account
        and pieces[5].startswith("key/")
        and metadata.get("KeyState") == "Enabled",
        "Secrets-provider KMS key account, region or state differs.",
    )
    return arn


def _provider_pin_value(field: str, value: Any) -> Any:
    """Accept equivalent Pulumi scalar encodings without accepting coercions."""
    if field == "allowedAccountIds" and isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            raise StackConfigError(
                "Invalid AWS provider account configuration."
            ) from None
    if field.startswith("skip") and value == "false":
        return False
    return value


def _materialize_provider_pins(
    config: dict[str, Any], target: dict[str, str], *, materialize: bool
) -> None:
    """Validate all callers; add provider settings only for admitted PoC execution."""
    pins = {
        "region": target["region"],
        "allowedAccountIds": [target["accountId"]],
        "skipCredentialsValidation": False,
        "skipRegionValidation": False,
        "skipRequestingAccountId": False,
    }
    settings = config.setdefault("config", {})
    _require(isinstance(settings, dict), "Stack config must be a mapping.")
    for key, value in list(settings.items()):
        _require(isinstance(key, str), "Stack config keys must be strings.")
        if key != "aws" and not key.startswith("aws:"):
            continue
        field = key.removeprefix("aws:").removeprefix("config:")
        _require(field in pins, "Unsupported AWS provider configuration.")
        actual = _provider_pin_value(field, value)
        expected = pins[field]
        _require(
            type(actual) is type(expected) and actual == expected,
            "AWS provider configuration differs from the pinned target.",
        )
        if materialize:
            del settings[key]
    if materialize:
        settings.update({f"aws:{field}": value for field, value in pins.items()})


def _workload_image_matches(
    image: str, account: str, region: str, repository: str
) -> bool:
    return bool(
        re.fullmatch(
            re.escape(f"{account}.dkr.ecr.{region}.amazonaws.com/{repository}@sha256:")
            + r"[0-9a-f]{64}",
            image,
        )
    )


def _validate_workload_shape(workload_config: dict[str, str]) -> None:
    _require(
        set(workload_config) == WORKLOAD_CONFIG_KEYS
        and all(type(key) is str for key in workload_config),
        "Workload configuration must contain exactly the generated public settings.",
    )
    _require(
        all(
            type(value) is str
            and 0 < len(value.encode()) <= MAX_WORKLOAD_CONFIG_VALUE_BYTES
            and not any(
                ord(character) < 32 or ord(character) == 127 for character in value
            )
            for value in workload_config.values()
        ),
        "Workload configuration values must be bounded public strings.",
    )


def _validate_workload_images(
    workload_config: dict[str, str], target: dict[str, str]
) -> None:
    account, region = target["accountId"], target["region"]
    web_repository = workload_config["user-service-infrastructure:webRepositoryName"]
    worker_repository = workload_config[
        "user-service-infrastructure:workerRepositoryName"
    ]
    repository_pattern = r"[a-z0-9](?:[a-z0-9._/-]{0,254}[a-z0-9])?"
    _require(
        all(
            re.fullmatch(repository_pattern, repository)
            for repository in (web_repository, worker_repository)
        )
        and _workload_image_matches(
            workload_config["user-service-infrastructure:webImage"],
            account,
            region,
            web_repository,
        )
        and _workload_image_matches(
            workload_config["user-service-infrastructure:workerImage"],
            account,
            region,
            worker_repository,
        ),
        "Workload image configuration differs from the protected target.",
    )


def _validate_workload_projection(
    workload_config: dict[str, str], target: dict[str, str]
) -> None:
    account, region = target["accountId"], target["region"]
    api_base_url = workload_config["user-service-infrastructure:apiBaseUrl"]
    _validate_workload_runtime(workload_config, api_base_url)
    _validate_workload_roles(workload_config, account, region)
    _validate_workload_endpoints(workload_config, region)


def _validate_workload_runtime(
    workload_config: dict[str, str], api_base_url: str
) -> None:
    _require(
        workload_config["user-service-infrastructure:deploymentMode"] == "managed"
        and workload_config["user-service-infrastructure:imageTagMutability"]
        == "IMMUTABLE"
        and workload_config["user-service-infrastructure:appEnv"] == "prod"
        and workload_config["user-service-infrastructure:appDebug"] == "0"
        and workload_config["user-service-infrastructure:apiUrl"] == api_base_url
        and re.fullmatch(r"https://[a-z0-9.-]+", api_base_url)
        and workload_config["user-service-infrastructure:corsAllowOrigin"]
        == "^" + re.escape(api_base_url) + "$",
        "Workload configuration differs from the generated public projection.",
    )


def _validate_workload_roles(
    workload_config: dict[str, str], account: str, region: str
) -> None:
    _require(
        all(
            re.fullmatch(rf"arn:aws:iam::{account}:role/[A-Za-z0-9+=,.@_/-]+", role)
            for role in (
                workload_config["user-service-infrastructure:executionRoleArn"],
                workload_config["user-service-infrastructure:taskRoleArn"],
            )
        )
        and bool(
            re.fullmatch(
                rf"arn:aws:acm:{region}:{account}:certificate/[0-9a-f-]+",
                workload_config["user-service-infrastructure:certificateArn"],
            )
        )
        and bool(
            re.fullmatch(
                r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+",
                workload_config["user-service-infrastructure:mailSender"],
            )
        ),
        "Workload configuration differs from the generated public projection.",
    )


def _validate_workload_endpoints(workload_config: dict[str, str], region: str) -> None:
    _require(
        bool(
            re.fullmatch(
                r"/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*",
                workload_config["user-service-infrastructure:healthCheckPath"],
            )
        )
        and workload_config["user-service-infrastructure:healthCheckQueueName"]
        == "health-check-queue"
        and workload_config["user-service-infrastructure:awsSqsEndpointBase"]
        == f"https://sqs.{region}.amazonaws.com"
        and workload_config["user-service-infrastructure:awsSqsPort"] == "443",
        "Workload configuration differs from the generated public projection.",
    )


def _materialize_workload_config(
    config: dict[str, Any],
    workload_config: dict[str, str] | None,
    target: dict[str, str],
) -> None:
    """Add only the closed, public workload projection to the config file."""
    if workload_config is None:
        return
    _require(type(workload_config) is dict, "Workload configuration must be a mapping.")
    _validate_workload_shape(workload_config)
    _validate_workload_images(workload_config, target)
    _validate_workload_projection(workload_config, target)
    settings = config.setdefault("config", {})
    _require(isinstance(settings, dict), "Stack config must be a mapping.")
    for key, value in workload_config.items():
        _require(
            key not in settings or settings[key] == value,
            "Committed workload configuration differs from the protected projection.",
        )
    settings.update(workload_config)


def _configuration(
    context: CommandContext,
    stack: str,
    provider: dict[str, Any],
    target: dict[str, str],
    workload_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    config = _yaml_document(context.pulumi_dir / f"Pulumi.{stack}.yaml")
    state = provider["state"]
    _require(
        not config.get("encryptionsalt")
        and config.get("secretsprovider", state["url"]) == state["url"]
        and config.get("encryptedkey", state["encryptedkey"]) == state["encryptedkey"],
        "Committed configuration encryption differs from the existing stack.",
    )
    config.pop("encryptionsalt", None)
    config.update(secretsprovider=state["url"], encryptedkey=state["encryptedkey"])
    # Ordinary shared commands retain their committed desired provider config.
    # Only the admitted PoC path owns the reviewed provider hardening transition.
    _materialize_provider_pins(
        config, target, materialize=context.registry_plan_gate is not None
    )
    _materialize_workload_config(config, workload_config, target)
    return config


@contextmanager
def prepared_stack_configuration(
    context: CommandContext,
    stack: str,
    *,
    workload_config: dict[str, str] | None = None,
) -> Iterator[CommandContext]:
    """Use the existing encrypted key in a private, automatically removed config."""
    if context.backend_url.startswith("file://"):
        _require(
            workload_config is None,
            "Workload configuration requires protected shared stack preparation.",
        )
        yield context
        return
    target = _coordinates(context, stack)
    identity = _read_json(
        context, ["aws", "sts", "get-caller-identity", "--output", "json"]
    )
    _require(
        identity.get("Account") == target["accountId"],
        "AWS caller account differs from the pinned stack account.",
    )
    before = _checkpoint_version(context, target)
    provider = _provider_state(context, target)
    key_arn = _key_identity(context, target["accountId"], target["region"])
    _require(
        before == _checkpoint_version(context, target),
        "Checkpoint changed during configuration preparation.",
    )
    config = _configuration(context, stack, provider, target, workload_config)
    binding = {
        **{k: target[k] for k in ("accountId", "backendUrl", "project", "stack")},
        **before,
        "kmsKeyArn": key_arn,
        "providerStateSha256": _digest(provider),
        "stackConfigSha256": _digest(config),
    }
    with TemporaryDirectory(prefix="pulumi-stack-config-") as directory:
        path = Path(directory) / "config.yaml"
        path.write_text(yaml.safe_dump(config, sort_keys=True))
        path.chmod(0o600)
        yield replace(context, config_file=path, provider_identity=binding)


def verify_provider_identity(context: CommandContext, entry: dict[str, Any]) -> None:
    """Reject missing, rotated or retargeted provider state before saved-plan replay."""
    if context.provider_identity is not None:
        _require(
            entry.get("secretsProviderIdentity") == context.provider_identity,
            "Saved-plan provider, configuration or checkpoint identity changed.",
        )
