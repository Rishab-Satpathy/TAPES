"""Tests for build command."""

import json
from pathlib import Path

from aitapes.build import run_build
from aitapes.contract import create_contract


def test_build_offline(tmp_path: Path) -> None:
    # Create contract
    contract = create_contract(
        intent="Fix bug",
        success_criteria=["bug fixed"],
    )
    contract_path = tmp_path / "contract.json"
    contract.save(contract_path)

    # Create source file
    source = tmp_path / "test.py"
    source.write_text("def hello():\n    pass\n")

    output = tmp_path / "patches.json"
    ledger = tmp_path / "ledger.jsonl"

    result = run_build(
        contract_path=str(contract_path),
        source_dir=str(tmp_path),
        output_path=str(output),
        ledger_path=str(ledger),
        offline=True,
    )
    assert len(result.patches) == 0  # Offline returns empty
    assert output.exists()
