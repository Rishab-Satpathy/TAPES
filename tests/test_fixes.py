import re
from forest_tapes.tapes_core.task_contract import parse_task_contract
from forest_tapes.tapes_core.instability_estimator import estimate_instability

def test_vague_word_boundary_fix():
    # "awesome" contains "some", but "some" is a vague word.
    # Before fix, this would trigger vague_terms_need_clarification.
    # After fix, it should NOT.
    contract = parse_task_contract("Make this awesome")
    assert "vague_terms_need_clarification" not in contract.missing_information

    # "This some task" should trigger it.
    contract2 = parse_task_contract("This some task")
    assert "vague_terms_need_clarification" in contract2.missing_information

def test_instability_marker_boundary_fix():
    # "awesome" should not trigger ambiguity_pressure score increase
    # (missing_information_pressure is expected due to no constraints/criteria)
    contract = parse_task_contract("Make this awesome")
    estimate = estimate_instability(contract)
    assert "ambiguity_pressure" not in estimate.sources  # No ambiguity detected

    # "maybe this" should trigger ambiguity
    contract2 = parse_task_contract("maybe this")
    estimate2 = estimate_instability(contract2)
    assert estimate2.hallucination_pressure > 0.0
