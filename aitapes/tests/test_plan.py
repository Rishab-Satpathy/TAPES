"""Tests for plan command."""

import json
from pathlib import Path

from aitapes.plan import run_plan


def test_plan_offline(tmp_path: Path) -> None:
    output = tmp_path / "contract.json"
    ledger = tmp_path / "ledger.jsonl"
    contract = run_plan(
        user_input="Fix the auth bug in auth.py",
        output_path=str(output),
        ledger_path=str(ledger),
        offline=True,
    )
    assert contract.intent == "Fix the auth bug in auth.py"
    assert output.exists()
    assert ledger.exists()


def test_plan_offline_detects_scope(tmp_path: Path) -> None:
    output = tmp_path / "contract.json"
    ledger = tmp_path / "ledger.jsonl"
    contract = run_plan(
        user_input="Rewrite the entire auth module from scratch",
        output_path=str(output),
        ledger_path=str(ledger),
        offline=True,
    )
    assert contract.mutation_boundary == "broad_rewrite"


def test_plan_offline_detects_high_stakes(tmp_path: Path) -> None:
    output = tmp_path / "contract.json"
    ledger = tmp_path / "ledger.jsonl"
    contract = run_plan(
        user_input="Fix production security vulnerability in payment system",
        output_path=str(output),
        ledger_path=str(ledger),
        offline=True,
    )
    assert contract.stakes == "high"
