"""Internal workload settings bridge; no CLI, admission or execution permission.

The trusted caller must authenticate source, images, capabilities and prior state.
The existing worker remains disabled until native plan/replay gates are connected.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import poc_contract
from poc_phase_admission import SourceAdmission
from poc_registry_phase_entrypoint import _stable_registries
from poc_workload_images import MAX_CONFIG_BYTES, MEDIA
from service_execution_process import require


@dataclass(frozen=True)
class WorkloadPhaseProjection:
    """Detached nonsecret data, never a capability or native-observation receipt."""

    source: SourceAdmission
    contract: dict[str, Any]
    images: dict[str, Any]


def _images(contract, observed):
    """Retain only both closed native config projections bound to the release."""
    require(
        type(observed) is dict and set(observed) == {"web", "worker"},
        "workload-image-set",
    )
    release = contract["workload"]["release"]
    require(release["platform"] == "linux/amd64", "workload-supported-platform")
    for kind, row in observed.items():
        require(
            type(row) is dict
            and set(row)
            == {
                "uri",
                "manifest_media_type",
                "config_digest",
                "config_size",
                "platform",
            },
            "workload-image-fields",
        )
        expected = release[kind]
        require(
            row["uri"] == expected["repository_uri"] + "@" + expected["digest"]
            and row["platform"] == release["platform"],
            "workload-image-binding",
        )
        require(
            type(row["manifest_media_type"]) is str
            and row["manifest_media_type"] in MEDIA,
            "workload-image-media",
        )
        require(
            type(row["config_size"]) is int
            and 0 < row["config_size"] <= MAX_CONFIG_BYTES,
            "workload-config-size",
        )
        require(
            type(row["config_digest"]) is str
            and re.fullmatch(r"sha256:[0-9a-f]{64}", row["config_digest"]),
            "workload-config-digest",
        )


def project_workload_phase(source, contract, images):
    """Bind already-authenticated facts without contacting AWS or resolving secrets."""
    require(type(source) is SourceAdmission, "workload-source-facts")
    require(type(contract) is dict, "workload-contract-object")
    document = copy.deepcopy(contract)
    poc_contract._validate_document(document)
    require(document["phase"] == "workload", "workload-phase-required")
    require(
        poc_contract._digest(document) == source.contract_sha256,
        "workload-source-binding",
    )
    _stable_registries(document["registries"])
    central = document["workload"]["central"]
    prefix = (
        f"arn:aws:iam::{document['account_id']}:role/"
        f"{document['backend']['project']}-test"
    )
    require(
        central["execution_role_arn"] == prefix + "-EcsExecution"
        and central["task_role_arn"] == prefix + "-EcsTask",
        "workload-role-binding",
    )
    observed = copy.deepcopy(images)
    _images(document, observed)
    return WorkloadPhaseProjection(source, document, observed)


def _checked(projection):
    require(type(projection) is WorkloadPhaseProjection, "workload-projection")
    return project_workload_phase(
        projection.source, projection.contract, projection.images
    )


def workload_configuration(projection):
    """Return only generated application settings for protected config assembly.

    Merge these into the authenticated baseline before the existing canonical
    provider preparation. No metadata, provider or secrets-provider field changes.
    Generated workload composition owns ALB log storage; no external bucket input.
    """
    checked = _checked(projection)
    workload = checked.contract["workload"]
    domain = workload["external"]["domain"]
    base_url = "https://" + domain["fqdn"]
    values = {
        "deploymentMode": "managed",
        "webRepositoryName": checked.contract["registries"]["web"]["name"],
        "workerRepositoryName": checked.contract["registries"]["worker"]["name"],
        "webImage": checked.images["web"]["uri"],
        "workerImage": checked.images["worker"]["uri"],
        "imageTagMutability": "IMMUTABLE",
        "executionRoleArn": workload["central"]["execution_role_arn"],
        "taskRoleArn": workload["central"]["task_role_arn"],
        "appEnv": "prod",
        "appDebug": "0",
        "apiBaseUrl": base_url,
        "apiUrl": base_url,
        "corsAllowOrigin": "^" + re.escape(base_url) + "$",
        "certificateArn": domain["certificate_arn"],
        "mailSender": workload["external"]["mail"]["sender"],
        "healthCheckPath": workload["runtime"]["health_path"],
        "healthCheckQueueName": "health-check-queue",
        "awsSqsEndpointBase": f"https://sqs.{checked.contract['region']}.amazonaws.com",
        "awsSqsPort": "443",
    }
    return {
        "user-service-infrastructure:" + key: value for key, value in values.items()
    }


def resolve_workload_inputs(projection):
    """Resolve existing generated-secret settings inside the isolated Pulumi child.

    Protected current config must contain the exact projected release settings.
    This creates no resources and never invokes the legacy manual-secret loader.
    """
    from app.environment import (
        DEFAULT_COST_CENTER,
        DEFAULT_OWNER,
        EnvironmentSettings,
        _normalize_tag_value,
        resolve_config_value,
        resolve_stack_settings,
    )
    from app.runtime_secrets import RuntimeSecretsDescriptor

    import pulumi

    checked = _checked(projection)
    config = pulumi.Config()
    for key, value in workload_configuration(checked).items():
        require(config.get(key.split(":", 1)[1]) == value, "workload-config-binding")
    metadata = SimpleNamespace(
        environment_name=resolve_config_value(
            None, config.get("environment"), default="dev"
        ),
        service_name_value=resolve_config_value(
            None, config.get("serviceName"), default=pulumi.get_project()
        ),
        owner=_normalize_tag_value(config.get("owner") or "", default=DEFAULT_OWNER),
        cost_center=_normalize_tag_value(
            config.get("costCenter") or "", default=DEFAULT_COST_CENTER
        ),
    )
    descriptor = RuntimeSecretsDescriptor(checked.contract)
    descriptor.validate_context()
    settings = resolve_stack_settings(
        cast(EnvironmentSettings, metadata), generated_secrets=True
    )
    descriptor.validate_target(settings)
    return settings, _stable_registries(checked.contract["registries"]), descriptor


def run_workload_phase(projection):
    """Register the existing composition only when an internal caller invokes it."""
    from app.workload_phase import WorkloadPhaseStack

    settings, registries, descriptor = resolve_workload_inputs(projection)
    return WorkloadPhaseStack(
        settings=settings, registries=registries, secrets=descriptor
    )
