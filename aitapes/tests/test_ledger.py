"""Tests for ledger system."""

import json
from pathlib import Path

from aitapes.ledger import (
    append_entry,
    format_entries,
    get_entries_by_type,
    get_failure_patterns,
    read_entries,
)


def test_append_and_read(tmp_path: Path) -> None:
    ledger = tmp_path / "test.jsonl"
    append_entry(ledger, "plan", "tapes plan", "test input", "test output")
    entries = read_entries(ledger)
    assert len(entries) == 1
    assert entries[0].entry_type == "plan"
    assert entries[0].command == "tapes plan"


def test_multiple_entries(tmp_path: Path) -> None:
    ledger = tmp_path / "test.jsonl"
    append_entry(ledger, "plan", "tapes plan", "input1", "output1")
    append_entry(ledger, "build", "tapes build", "input2", "output2")
    append_entry(ledger, "check", "tapes check", "input3", "output3")
    entries = read_entries(ledger)
    assert len(entries) == 3


def test_filter_by_type(tmp_path: Path) -> None:
    ledger = tmp_path / "test.jsonl"
    append_entry(ledger, "plan", "tapes plan", "input1", "output1")
    append_entry(ledger, "build", "tapes build", "input2", "output2")
    append_entry(ledger, "plan", "tapes plan", "input3", "output3")
    plan_entries = get_entries_by_type(ledger, "plan")
    assert len(plan_entries) == 2


def test_format_entries(tmp_path: Path) -> None:
    ledger = tmp_path / "test.jsonl"
    append_entry(ledger, "plan", "tapes plan", "input", "output")
    entries = read_entries(ledger)
    text = format_entries(entries)
    assert "plan" in text
    assert "output" in text


def test_empty_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "nonexistent.jsonl"
    entries = read_entries(ledger)
    assert len(entries) == 0


def test_failure_patterns(tmp_path: Path) -> None:
    ledger = tmp_path / "test.jsonl"
    append_entry(ledger, "check", "tapes check", "input", "fail reason", {"overall": "fail"})
    append_entry(ledger, "check", "tapes check", "input", "fail reason", {"overall": "fail"})
    append_entry(ledger, "check", "tapes check", "input", "pass", {"overall": "pass"})
    patterns = get_failure_patterns(ledger)
    assert len(patterns) > 0
