import pytest

from forest_tapes.tapes_core.models import MutationType, TaskType
from forest_tapes.tapes_core.task_contract import contract_to_prompt_anchor, parse_task_contract


def test_empty_task_rejected() -> None:
    with pytest.raises(ValueError):
        parse_task_contract("")


def test_vague_task_produces_missing_information() -> None:
    contract = parse_task_contract("Fix some appropriate thing in auth.py etc")
    assert "vague_terms_need_clarification" in contract.missing_information
    assert "explicit_constraints" in contract.missing_information


def test_constraints_preserved_and_anchor_blocks_guessing() -> None:
    contract = parse_task_contract(
        {
            "task": "Patch auth.py token refresh bug",
            "explicit_constraints": ["only change refresh_token", "do not rewrite the file"],
            "success_criteria": ["stale token is cleared"],
        }
    )
    anchor = contract_to_prompt_anchor(contract)
    assert "only change refresh_token" in anchor
    assert "Do not perform broad rewrites" in anchor
    assert "Do not fill gaps with plausible guesses" in anchor


@pytest.mark.parametrize(
    ("text", "task_type"),
    [
        ("fix crash in auth.py", TaskType.BUG_FIX),
        ("build login feature", TaskType.FEATURE),
        ("refactor session manager", TaskType.REFACTOR),
        ("add pytest for auth", TaskType.TEST),
        ("explain this module", TaskType.EXPLAIN),
        ("search replace this block", TaskType.PATCH),
        ("do something vague", TaskType.UNKNOWN),
    ],
)
def test_task_type_classification(text: str, task_type: TaskType) -> None:
    assert parse_task_contract(text).task_type == task_type


def test_broad_rewrite_requires_missing_authorization() -> None:
    contract = parse_task_contract("full rewrite auth.py")
    assert contract.allowed_mutation == MutationType.BROAD_REWRITE
    assert "explicit_broad_rewrite_authorization" in contract.missing_information


def test_as_list_handles_non_iterable_types() -> None:
    contract = parse_task_contract(
        {
            "task": "Fix auth bug",
            "explicit_constraints": 42,
            "success_criteria": True,
        }
    )
    assert contract.explicit_constraints == ("42",)
    assert contract.success_criteria == ("True",)
