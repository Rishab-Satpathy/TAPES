"""Tests for check command."""

from pathlib import Path

from aitapes.check import run_check
from aitapes.contract import create_contract


def test_check_offline(tmp_path: Path) -> None:
    # Create contract
    contract = create_contract(
        intent="Test check",
        target_files=["test.py"],
        success_criteria=["code exists"],
    )
    contract_path = tmp_path / "contract.json"
    contract.save(contract_path)

    # Create source file
    source = tmp_path / "test.py"
    source.write_text("def hello():\n    pass\n")

    ledger = tmp_path / "ledger.jsonl"

    result = run_check(
        contract_path=str(contract_path),
        source_dir=str(tmp_path),
        ledger_path=str(ledger),
        offline=True,
    )
    assert result.overall in ("pass", "fail")
    assert result.score >= 0.0
    assert result.score <= 1.0
