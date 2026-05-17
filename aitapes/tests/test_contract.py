"""Tests for contract system."""

import json
import tempfile
from pathlib import Path

from aitapes.contract import Contract, create_contract, validate_contract


def test_contract_creation() -> None:
    contract = create_contract(
        intent="Fix auth bug",
        constraints=["exact patch only"],
        success_criteria=["bug is fixed"],
    )
    assert contract.intent == "Fix auth bug"
    assert "exact patch only" in contract.constraints
    assert "bug is fixed" in contract.success_criteria
    assert contract.stakes == "low"
    assert contract.mutation_boundary == "local_edit"


def test_contract_json_roundtrip() -> None:
    contract = create_contract(
        intent="Test roundtrip",
        constraints=["c1", "c2"],
        success_criteria=["s1"],
    )
    json_str = contract.to_json()
    restored = Contract.from_json(json_str)
    assert restored.intent == contract.intent
    assert restored.constraints == contract.constraints
    assert restored.success_criteria == contract.success_criteria


def test_contract_save_load(tmp_path: Path) -> None:
    contract = create_contract(intent="Save test", success_criteria=["works"])
    path = tmp_path / "contract.json"
    contract.save(path)
    loaded = Contract.load(path)
    assert loaded.intent == "Save test"


def test_validate_contract_valid() -> None:
    contract = create_contract(
        intent="Valid contract",
        success_criteria=["criterion 1"],
    )
    issues = validate_contract(contract)
    assert len(issues) == 0


def test_validate_contract_empty_intent() -> None:
    contract = Contract(intent="", success_criteria=["c1"])
    issues = validate_contract(contract)
    assert any("intent" in i.lower() for i in issues)


def test_validate_contract_no_criteria() -> None:
    contract = Contract(intent="Test")
    issues = validate_contract(contract)
    assert any("success" in i.lower() for i in issues)


def test_validate_contract_invalid_stakes() -> None:
    contract = Contract(intent="Test", stakes="invalid")
    issues = validate_contract(contract)
    assert any("stakes" in i.lower() for i in issues)


def test_contract_forbidden_assumptions() -> None:
    contract = create_contract(intent="Test")
    assert any("invent" in a.lower() for a in contract.forbidden_assumptions)
    assert any("broad" in a.lower() for a in contract.forbidden_assumptions)
