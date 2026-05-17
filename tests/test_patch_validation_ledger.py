import json

import pytest

from forest_tapes.tapes_core.allocator import allocate_cognition
from forest_tapes.tapes_core.models import ValidationLevel
from forest_tapes.tapes_core.patch_discipline import ExactPatch, PatchDisciplineError, PatchOperation, apply_exact_patch
from forest_tapes.tapes_core.validation_intensity import select_validation
from forest_tapes.tapes_core.why_ledger import append_failure, append_ledger, build_ledger_record, read_ledger, read_ledger_with_recovery


def test_exact_patch_applies_once() -> None:
    patch = ExactPatch(target_id="auth.refresh", search="return stale", replace="return fresh", reasoning="remove stale token")
    result = apply_exact_patch("function x(){ return stale }", patch)
    assert "return fresh" in result.after
    assert result.operation == PatchOperation.REPLACE


def test_exact_patch_rejects_zero_and_multi_match() -> None:
    patch = ExactPatch(target_id="auth.refresh", search="return stale", replace="return fresh", reasoning="remove stale token")
    with pytest.raises(PatchDisciplineError, match="zero"):
        apply_exact_patch("return other", patch)
    with pytest.raises(PatchDisciplineError, match="more than once"):
        apply_exact_patch("return stale\nreturn stale", patch)


def test_delete_operation_removes_text() -> None:
    patch = ExactPatch(
        target_id="auth.cleanup",
        search="return stale;",
        replace="",
        reasoning="remove stale return",
        operation=PatchOperation.DELETE,
    )
    result = apply_exact_patch("function x(){ return stale; }", patch)
    assert "return stale;" not in result.after
    assert result.operation == PatchOperation.DELETE


def test_insert_operation_appends_text() -> None:
    patch = ExactPatch(
        target_id="auth.add",
        search="",
        replace=" // validated",
        reasoning="add validation comment",
        operation=PatchOperation.INSERT,
    )
    result = apply_exact_patch("function x(){ return fresh; }", patch)
    assert "// validated" in result.after
    assert result.operation == PatchOperation.INSERT


def test_validate_patch_rejects_empty_search_for_replace() -> None:
    patch = ExactPatch(target_id="t", search="", replace="r", reasoning="reason")
    with pytest.raises(PatchDisciplineError, match="search block is required"):
        apply_exact_patch("source", patch)


def test_validate_patch_rejects_empty_replace_for_replace() -> None:
    patch = ExactPatch(target_id="t", search="s", replace="", reasoning="reason")
    with pytest.raises(PatchDisciplineError, match="replace block is required"):
        apply_exact_patch("source with s", patch)


def test_validation_scales_with_high_stakes_mutation() -> None:
    result = allocate_cognition(
        {
            "task": "Fix critical auth.py security bug",
            "explicit_constraints": ["exact patch only"],
            "success_criteria": ["no bypass"],
        }
    )
    validation = select_validation(result.contract, result.instability, result.scope)
    assert validation.level in {ValidationLevel.FULL_VERIFY, ValidationLevel.ADVERSARIAL_CHECK}
    assert "patch_locality_check" in validation.checks


def test_ledger_and_failure_memory_jsonl(tmp_path) -> None:
    result = allocate_cognition("Fix some auth thing")
    record = build_ledger_record(result)
    ledger_path = tmp_path / "why.jsonl"
    failure_path = tmp_path / "failure.jsonl"

    append_ledger(ledger_path, record)
    failure = build_ledger_record(result, outcome="failure", outcome_notes="vague target caused instability")
    append_failure(failure_path, failure)

    assert len(read_ledger(ledger_path)) == 1
    assert len(read_ledger(failure_path)) == 1
    with ledger_path.open("r", encoding="utf-8") as handle:
        json.loads(handle.readline())


def test_ledger_recovery_handles_corrupt_lines(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"
    # Write a valid line followed by a corrupt line
    result = allocate_cognition("Fix auth bug")
    record = build_ledger_record(result)
    append_ledger(ledger_path, record)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write("this is not json\n")
        handle.write('{"valid": true}\n')

    read_result = read_ledger_with_recovery(ledger_path)
    assert len(read_result.records) == 1
    assert len(read_result.corrupted) == 2
    assert read_result.partial is True
    assert read_result.corrupted[0].line_number == 2
    assert read_result.corrupted[1].line_number == 3


def test_ledger_recovery_quarantines_corrupt_lines(tmp_path) -> None:
    ledger_path = tmp_path / "why.jsonl"
    quarantine_path = tmp_path / "why.corrupt.jsonl"
    result = allocate_cognition("Fix auth bug")
    record = build_ledger_record(result)
    append_ledger(ledger_path, record)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write("corrupt data\n")

    read_ledger_with_recovery(ledger_path)
    assert quarantine_path.exists()
    with quarantine_path.open("r", encoding="utf-8") as handle:
        entries = [json.loads(line) for line in handle if line.strip()]
    assert len(entries) == 1
    assert entries[0]["line_number"] == 2
    assert entries[0]["error"] is not None
