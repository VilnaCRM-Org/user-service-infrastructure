"""Offline graph checks for the internal authenticated registry phase."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from coverage import Coverage, CoverageData

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

entrypoint = importlib.import_module("poc_registry_phase_entrypoint")
admission = importlib.import_module("poc_phase_admission")
FIXTURE = Path(__file__).parents[1] / "fixtures/poc-contract/registry.synthetic.json"


def contract() -> dict:
    """Return the phase contract projected onto the stable TEST repositories."""
    document = json.loads(FIXTURE.read_text())
    for kind, logical_name, name in (
        ("web", "user-service-web-repository", "user-service-test-web"),
        ("worker", "user-service-worker-repository", "user-service-test-worker"),
    ):
        registry = document["registries"][kind]
        registry.update(
            {
                "logical_name": logical_name,
                "name": name,
                "arn": f"arn:aws:ecr:eu-central-1:891377212104:repository/{name}",
                "uri": f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{name}",
            }
        )
    return document


def source(document: dict) -> admission.SourceAdmission:
    """Build synthetic typed facts; production facts come only from the adapter."""
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return admission.SourceAdmission(
        contract_sha256=digest,
        head_sha="a" * 40,
        base_sha="b" * 40,
        path=admission.CONTRACT_PATH,
        blob_sha="c" * 40,
        schema_sha256="d" * 64,
        validator_sha256="e" * 64,
    )


def graph_receipt(tmp_path: Path) -> dict:
    """Run the actual graph in a fresh interpreter and return its monitor receipt."""
    program = Path(__file__).parents[1] / "fixtures/poc-registry/graph_probe.py"
    root = Path(__file__).resolve().parents[2]
    coverage_data = tmp_path / "registry.coverage"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(program),
            str(root),
            str(FIXTURE),
            str(coverage_data),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(Path(str(coverage_data) + ".json").read_text())
    assert any(name.endswith("app/registry_phase.py") for name in report["files"])
    active = Coverage.current()
    if active is not None:
        child = CoverageData(basename=str(coverage_data))
        child.read()
        active.get_data().update(child)
    return json.loads(result.stdout)


def test_registry_entrypoint_owns_only_the_stable_two_repository_graph(
    tmp_path: Path,
) -> None:
    """The phase has the future workload's root/child URNs without workload planes."""
    receipt = graph_receipt(tmp_path)
    custom = [item for item in receipt["resources"] if item["custom"]]
    parents = receipt["parents"]
    assert parents["registries"] == receipt["urns"]["user-service"]
    for name in ("user-service-web-repository", "user-service-worker-repository"):
        assert parents[name] == receipt["urns"]["registries"]
    components = {
        item["name"]: item["type"]
        for item in receipt["resources"]
        if not item["custom"]
    }
    assert components["user-service"] == "user-service-infrastructure:stack:UserService"
    assert components["registries"] == "user-service-infrastructure:registry:Plane"
    assert {item["type"] for item in custom} == {"aws:ecr/repository:Repository"}
    assert {item["name"] for item in custom} == {
        "user-service-web-repository",
        "user-service-worker-repository",
    }
    assert {item["inputs"]["name"] for item in custom} == {
        "user-service-test-web",
        "user-service-test-worker",
    }
    assert len(custom) == 2
    assert components["environment-settings"] == (
        "user-service-infrastructure:core:EnvironmentSettings"
    )
    assert (
        parents["environment-settings"]
        == receipt["urns"]["user-service-infrastructure-test"]
    )
    # Mock new_resource omits the root and implicit provider. Parent receipts
    # separately establish the root; the saved-plan tests bind the provider.
    assert len(receipt["resources"]) == 5
    assert len(receipt["urns"]) == 6
    import poc_registry_plan as graph

    assert receipt["policy_failures"] == []
    assert receipt["root_outputs"] == graph.ROOT_OUTPUTS
    for row in custom:
        assert row["inputs"]["tags"] == graph.DEFAULT_TAGS


@pytest.mark.parametrize("change", ["phase", "name", "logical_name", "digest"])
def test_registry_entrypoint_rejects_unbound_or_nonstable_phase_inputs(
    change: str,
) -> None:
    """No untrusted contract field can select a registry graph."""
    document = contract()
    facts = source(document)
    if change == "phase":
        document["phase"] = "workload"
    elif change == "digest":
        facts = source({**document, "status": "proposed-not-installed"})
        facts = admission.SourceAdmission(
            **{**facts.__dict__, "contract_sha256": "0" * 64}
        )
    else:
        document["registries"]["web"][change] = "other"
    with pytest.raises(ValueError):
        entrypoint.project_registry_phase(facts, document)


def test_registry_entrypoint_rejects_absent_or_forged_typed_source() -> None:
    """Only the exact source-fact type reaches graph construction."""
    document = contract()
    with pytest.raises(ValueError, match="Typed source facts required"):
        entrypoint.project_registry_phase(None, document)
    projection = entrypoint.project_registry_phase(source(document), document)
    with pytest.raises(ValueError, match="Registry projection required"):
        entrypoint.run_registry_phase(copy.deepcopy(projection).__dict__)


def test_registry_entrypoint_revalidates_mutable_projection_before_graph() -> None:
    """A projection's public nested mapping cannot add repository authority."""
    document = contract()
    projection = entrypoint.project_registry_phase(source(document), document)
    projection.registries["web"]["name"] = "foreign-repository"
    with pytest.raises(ValueError, match="Registry ownership differs"):
        entrypoint.run_registry_phase(projection)
