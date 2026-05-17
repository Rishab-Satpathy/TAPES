import json

from forest_tapes.tapes_core.allocator import allocate_cognition
from forest_tapes.tapes_core.why_ledger import (
    _record_count,
    append_ledger,
    build_ledger_record,
    read_ledger,
    read_ledger_with_recovery,
    verify_checkpoint,
    deduplicate_ledger,
    merge_quarantine,
)


def test_ledger_checkpoint_written(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"
    checkpoint_path = tmp_path / "why.checkpoint.jsonl"

    # Write records to trigger checkpoint
    for i in range(15):
        result = allocate_cognition(f"Task checkpoint {i}")
        record = build_ledger_record(result)
        append_ledger(ledger_path, record)

    assert checkpoint_path.exists()
    with checkpoint_path.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    assert len(lines) >= 1


def test_ledger_checkpoint_verify(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"

    for i in range(15):
        result = allocate_cognition(f"Task verify {i}")
        record = build_ledger_record(result)
        append_ledger(ledger_path, record)

    assert verify_checkpoint(ledger_path) is True


def test_ledger_deduplication(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"

    result = allocate_cognition("Same task")
    record1 = build_ledger_record(result, outcome="failure")
    record2 = build_ledger_record(result, outcome="success")

    append_ledger(ledger_path, record1)
    append_ledger(ledger_path, record2)

    assert len(read_ledger(ledger_path)) == 2

    removed = deduplicate_ledger(ledger_path)
    assert removed == 1
    assert len(read_ledger(ledger_path)) == 1


def test_ledger_merge_quarantine(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"
    quarantine_path = tmp_path / "why.corrupt.jsonl"

    # Write a valid record then a corrupt one
    result = allocate_cognition("Valid task")
    record = build_ledger_record(result)
    append_ledger(ledger_path, record)

    # Write corrupt data
    with quarantine_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"raw_content": '{"task_hash": "abc", "recorded_at": "2026-01-01", "allocation": {}}', "error": "test"}) + "\n")

    recovered = merge_quarantine(ledger_path)
    assert recovered == 1
    assert not quarantine_path.exists()


def test_ledger_read_with_recovery_returns_checkpoints(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"

    for i in range(15):
        result = allocate_cognition(f"Task recovery {i}")
        record = build_ledger_record(result)
        append_ledger(ledger_path, record)

    read_result = read_ledger_with_recovery(ledger_path)
    assert len(read_result.checkpoints) >= 1
    assert read_result.checkpoints[0].record_count >= 1
