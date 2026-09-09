"""Fail-closed lifecycle guards complement the native provider preview."""

import json
import sys
from pathlib import Path

import pytest
from app.runtime_secrets import RuntimeSecrets, RuntimeSecretsDescriptor
from app.workload_phase import _merge_tags

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def test_registry_contract_cannot_authorize_secret_component():
    contract = json.loads((PROJECT_ROOT / "specs/poc/poc-test.json").read_text())
    with pytest.raises(ValueError, match="workload declaration"):
        RuntimeSecretsDescriptor(contract)


def test_partial_or_duplicate_endpoint_secret_inventory_cannot_be_completed():
    # Exercise closure validation without issuing provider registrations: a caller
    # cannot publish outputs or overwrite a purpose before endpoint composition.
    partial = object.__new__(RuntimeSecrets)
    partial.references = {"redis_url": {}, "document_db_url": {}}
    partial.secret_arns = {"redis_url": "synthetic-reference"}
    with pytest.raises(ValueError, match="inventory is incomplete"):
        partial.complete()
    for purpose in ("redis_url", "foreign-purpose"):
        with pytest.raises(ValueError, match="invalid or duplicated"):
            partial.persist_url(purpose, "synthetic-url")


def test_workload_tag_composition_preserves_explicit_tags_without_owner_override():
    baseline = {"Owner": "team-user-service", "Environment": "test"}
    explicit = {"Name": "synthetic", "Owner": "team-user-service"}
    assert _merge_tags(explicit, baseline) == {**baseline, "Name": "synthetic"}
    assert explicit == {"Name": "synthetic", "Owner": "team-user-service"}
    for forbidden in ({"Owner": "foreign"}, "invalid-shape"):
        with pytest.raises(ValueError, match="preserved baseline tags"):
            _merge_tags(forbidden, baseline)
