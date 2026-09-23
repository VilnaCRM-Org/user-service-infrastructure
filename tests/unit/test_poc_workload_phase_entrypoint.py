"""Pure projections and isolated mock graphs, never native admission evidence."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_phase_entrypoint as module  # noqa: E402
from test_poc_registry_phase_entrypoint import source
from test_poc_workload_images import evidence
from test_poc_workload_phase import graph


def fixture():
    contract, document, *_ = evidence()
    central = contract["workload"]["central"]
    prefix = "arn:aws:iam::891377212104:role/user-service-infrastructure-test"
    central["execution_role_arn"] = prefix + "-EcsExecution"
    central["task_role_arn"] = prefix + "-EcsTask"
    for kind in ("web", "worker"):
        contract["registries"][kind]["logical_name"] = f"user-service-{kind}-repository"
    images = {
        kind: {
            "uri": row["repository_uri"] + "@" + row["digest"],
            "platform": contract["workload"]["release"]["platform"],
            "manifest_media_type": document["mediaType"],
            "config_digest": document["config"]["digest"],
            "config_size": document["config"]["size"],
        }
        for kind, row in contract["workload"]["release"].items()
        if kind in ("web", "worker")
    }
    return contract, images


def test_projection_binds_release_settings_without_mutating_source_or_provider():
    contract, images = fixture()
    before = copy.deepcopy((contract, images))
    projected = module.project_workload_phase(source(contract), contract, images)
    values = module.workload_configuration(projected)
    assert (contract, images) == before
    assert values["user-service-infrastructure:webImage"] == images["web"]["uri"]
    assert values["user-service-infrastructure:workerImage"] == images["worker"]["uri"]
    assert (
        values["user-service-infrastructure:apiUrl"] == "https://user.vilnacrmtest.com"
    )
    assert values["user-service-infrastructure:mailSender"] == "sender@poc.example"
    assert values["user-service-infrastructure:deploymentMode"] == "managed"
    assert all(key.startswith("user-service-infrastructure:") for key in values)
    assert not any(
        key.endswith(
            (
                "owner",
                "environment",
                "costCenter",
                "secretsProvider",
                "accessLogsBucketName",
            )
        )
        for key in values
    )
    contract["workload"]["secret_lifecycle"]["references"].clear()
    images.clear()
    assert module.workload_configuration(projected) == values


@pytest.mark.parametrize(
    "fault",
    [
        "source-type",
        "contract-type",
        "source-digest",
        "phase",
        "role",
        "registry",
        "images-type",
        "images-missing",
        "images-extra",
        "row-type",
        "row-extra",
        "uri",
        "platform",
        "unsupported-platform",
        "media-type",
        "media",
        "size-type",
        "size-bool",
        "size-zero",
        "size-max",
        "digest-type",
        "digest",
    ],
)
def test_incompatible_facts_rejected_before_settings_or_resources(fault):
    contract, images = fixture()
    facts = source(contract)
    row = images["web"]
    changes = {
        "uri": ("uri", "foreign"),
        "platform": ("platform", "linux/arm64"),
        "media-type": ("manifest_media_type", []),
        "media": ("manifest_media_type", "foreign"),
        "size-type": ("config_size", "100"),
        "size-bool": ("config_size", True),
        "size-zero": ("config_size", 0),
        "size-max": ("config_size", module.MAX_CONFIG_BYTES + 1),
        "digest-type": ("config_digest", None),
        "digest": ("config_digest", "sha256:foreign"),
    }
    if fault in changes:
        key, value = changes[fault]
        row[key] = value
    elif fault == "source-type":
        facts = None
    elif fault == "contract-type":
        contract = []
    elif fault == "source-digest":
        facts = source({})
    elif fault == "phase":
        contract = json.loads(
            (
                Path(__file__).parents[1]
                / "fixtures/poc-contract/registry.synthetic.json"
            ).read_text()
        )
        facts = source(contract)
    elif fault == "role":
        contract["workload"]["central"]["execution_role_arn"] += "-foreign"
        facts = source(contract)
    elif fault == "registry":
        contract["registries"]["web"]["logical_name"] = "foreign"
        facts = source(contract)
    elif fault == "unsupported-platform":
        contract["workload"]["release"]["platform"] = "linux/arm64"
        facts = source(contract)
    else:
        images = _mutate_images(images, fault)
    with pytest.raises(ValueError):
        module.project_workload_phase(facts, contract, images)


def _mutate_images(images, fault):
    row = images["web"]
    if fault == "images-type":
        images = []
    elif fault == "images-missing":
        del images["worker"]
    elif fault == "images-extra":
        images["extra"] = row
    elif fault == "row-type":
        images["web"] = []
    elif fault == "row-extra":
        row["token"] = "synthetic-no-pass"
    return images


def test_projection_type_and_mutable_nested_data_are_revalidated():
    contract, images = fixture()
    projection = module.project_workload_phase(source(contract), contract, images)
    with pytest.raises(ValueError, match="workload-projection"):
        module.workload_configuration(projection.__dict__)
    projection.images["web"]["uri"] = "foreign"
    with pytest.raises(ValueError, match="workload-image-binding"):
        module.workload_configuration(projection)


def test_real_child_bridge_preserves_registry_graph_and_uses_exact_images(tmp_path):
    before, after = graph(tmp_path, "registry"), graph(tmp_path, "bridge")
    assert before["error"] is after["error"] is None
    baseline, workload = before["registrations"], after["registrations"]
    assert {name: workload[name] for name in baseline} == baseline
    assert {urn: after["outputs"][urn] for urn in before["outputs"]} == before[
        "outputs"
    ]
    assert after["aws_config"] == before["aws_config"]
    definitions = [
        row
        for row in workload.values()
        if row["type"] == "aws:ecs/taskDefinition:TaskDefinition"
    ]
    assert len(definitions) == 2
    for definition in definitions:
        container = json.loads(definition["inputs"]["containerDefinitions"])[0]
        kind = "worker" if container["name"].endswith("worker") else "web"
        digest = ("b" if kind == "worker" else "a") * 64
        assert container["image"] == (
            "891377212104.dkr.ecr.eu-central-1.amazonaws.com/"
            f"user-service-test-{kind}@sha256:{digest}"
        )
        assert len(container["secrets"]) == 9
        assert all(
            "valueFrom" in item and "value" not in item for item in container["secrets"]
        )
    assert not any(row["type"].startswith("aws:iam/") for row in workload.values())


def test_child_rejects_changed_protected_release_config_before_aws(tmp_path):
    after = graph(tmp_path, "bridge", "config")
    assert after["error"] == "workload-config-binding"
    assert not any(
        row["type"].startswith("aws:") for row in after["registrations"].values()
    )
