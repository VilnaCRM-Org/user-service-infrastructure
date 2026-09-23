"""The saved-plan config path accepts only generated workload settings."""

import base64
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("_pulumi_stack_config")


@pytest.fixture
def stack(tmp_path):
    pulumi_dir = tmp_path / "pulumi"
    pulumi_dir.mkdir()
    (pulumi_dir / "Pulumi.test.yaml").write_text(
        yaml.safe_dump({"config": {"example:value": "safe"}})
    )
    return SimpleNamespace(pulumi_dir=pulumi_dir)


@pytest.fixture
def overlay():
    return {
        "user-service-infrastructure:deploymentMode": "managed",
        "user-service-infrastructure:webRepositoryName": "user-service-test-web",
        "user-service-infrastructure:workerRepositoryName": "user-service-test-worker",
        "user-service-infrastructure:webImage": (
            "891377212104.dkr.ecr.eu-central-1.amazonaws.com/"
            "user-service-test-web@sha256:" + "a" * 64
        ),
        "user-service-infrastructure:workerImage": (
            "891377212104.dkr.ecr.eu-central-1.amazonaws.com/"
            "user-service-test-worker@sha256:" + "b" * 64
        ),
        "user-service-infrastructure:imageTagMutability": "IMMUTABLE",
        "user-service-infrastructure:executionRoleArn": (
            "arn:aws:iam::891377212104:role/user-service-test-EcsExecution"
        ),
        "user-service-infrastructure:taskRoleArn": (
            "arn:aws:iam::891377212104:role/user-service-test-EcsTask"
        ),
        "user-service-infrastructure:appEnv": "prod",
        "user-service-infrastructure:appDebug": "0",
        "user-service-infrastructure:apiBaseUrl": "https://user.vilnacrmtest.com",
        "user-service-infrastructure:apiUrl": "https://user.vilnacrmtest.com",
        "user-service-infrastructure:corsAllowOrigin": "^https://user\\.vilnacrmtest\\.com$",
        "user-service-infrastructure:certificateArn": (
            "arn:aws:acm:eu-central-1:891377212104:certificate/"
            "00000000-0000-0000-0000-000000000000"
        ),
        "user-service-infrastructure:mailSender": "sender@poc.example",
        "user-service-infrastructure:healthCheckPath": "/health",
        "user-service-infrastructure:healthCheckQueueName": "health-check-queue",
        "user-service-infrastructure:awsSqsEndpointBase": (
            "https://sqs.eu-central-1.amazonaws.com"
        ),
        "user-service-infrastructure:awsSqsPort": "443",
    }


def _configuration(module, stack, overlay=None):
    return module._configuration(
        stack,
        "test",
        {
            "state": {
                "url": "awskms://alias/example?region=eu-central-1",
                "encryptedkey": base64.b64encode(b"existing-ciphertext").decode(),
            }
        },
        {"accountId": "891377212104", "region": "eu-central-1"},
        overlay,
    )


def test_materializes_closed_workload_projection_before_config_digest(
    module, stack, overlay
):
    config = _configuration(module, stack, overlay)

    assert config["config"].items() >= overlay.items()
    assert config["config"]["example:value"] == "safe"
    assert config["secretsprovider"] == "awskms://alias/example?region=eu-central-1"
    assert config["encryptedkey"]
    assert module._digest(config) != module._digest(_configuration(module, stack))


def test_default_configuration_does_not_add_workload_settings(module, stack):
    config = _configuration(module, stack)

    assert not (set(config["config"]) & module.WORKLOAD_CONFIG_KEYS)
    assert config["config"]["aws:region"] == "eu-central-1"


@pytest.mark.parametrize(
    "change",
    [
        lambda values: [],
        lambda values: {
            key: value for key, value in values.items() if key.endswith("appEnv")
        },
        lambda values: {**values, "aws:region": "eu-central-1"},
        lambda values: {**values, "user-service-infrastructure:appDebug": 0},
        lambda values: {**values, "user-service-infrastructure:appDebug": "\n"},
        lambda values: {
            **values,
            "user-service-infrastructure:webImage": "foreign-image",
        },
        lambda values: {
            **values,
            "user-service-infrastructure:appDebug": "x" * 4097,
        },
    ],
)
def test_rejects_arbitrary_or_nonpublic_workload_overlay(
    module, stack, overlay, change
):
    with pytest.raises(module.StackConfigError, match="configuration"):
        _configuration(module, stack, change(overlay))


def test_rejects_committed_workload_setting_that_differs_from_projection(
    module, stack, overlay
):
    (stack.pulumi_dir / "Pulumi.test.yaml").write_text(
        yaml.safe_dump(
            {
                "config": {
                    "user-service-infrastructure:appDebug": "1",
                }
            }
        )
    )

    with pytest.raises(module.StackConfigError, match="protected projection"):
        _configuration(module, stack, overlay)
