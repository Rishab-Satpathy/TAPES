from __future__ import annotations

import re
from typing import Any

from ..semantics import contains_any_token, has_high_stakes, has_medium_stakes, has_vagueness, score_ambiguity
from ..semantics.ontology import SemanticCategory, get_words
from .models import MutationType, Stakes, TaskContract, TaskType


# Classification precedence is documented here.
# ORDER MATTERS: first match wins. Patch is checked before bug because
# "patch the crash" is an exact-match mutation, not a general bug fix.
# If precedence needs to change, update this comment and the tests.
CLASSIFICATION_PRECEDENCE: tuple[SemanticCategory, TaskType] = (
    (SemanticCategory.PATCH_INTENT, TaskType.PATCH),
    (SemanticCategory.BUG_INTENT, TaskType.BUG_FIX),
    (SemanticCategory.TEST_INTENT, TaskType.TEST),
    (SemanticCategory.REFACTOR_INTENT, TaskType.REFACTOR),
    (SemanticCategory.FEATURE_INTENT, TaskType.FEATURE),
    (SemanticCategory.EXPLAIN_INTENT, TaskType.EXPLAIN),
)


def parse_task_contract(value: str | dict[str, Any]) -> TaskContract:
    """Build a cognition anchor that reduces guessing before generation."""
    data = _normalize_input(value)
    raw_intent = data["raw_intent"].strip()
    if not raw_intent:
        raise ValueError("Task intent cannot be empty.")

    constraints = tuple(_as_list(data.get("explicit_constraints") or data.get("constraints")))
    success = tuple(_as_list(data.get("success_criteria")))
    target = data.get("target_artifact") or _detect_target(raw_intent)
    task_type = _coerce_task_type(data.get("task_type")) or classify_task_type(raw_intent)
    mutation = _coerce_mutation(data.get("allowed_mutation")) or infer_mutation_type(raw_intent, task_type)
    stakes = _coerce_stakes(data.get("stakes")) or infer_stakes(raw_intent)

    preliminary = TaskContract(
        raw_intent=raw_intent,
        target_artifact=target,
        task_type=task_type,
        allowed_mutation=mutation,
        explicit_constraints=constraints,
        missing_information=(),
        forbidden_assumptions=tuple(_as_list(data.get("forbidden_assumptions"))),
        success_criteria=success,
        stakes=stakes,
    )
    missing = tuple(detect_missing_information(preliminary))
    forbidden = tuple(sorted(set(preliminary.forbidden_assumptions + tuple(default_forbidden_assumptions(preliminary)))))

    return TaskContract(
        raw_intent=preliminary.raw_intent,
        target_artifact=preliminary.target_artifact,
        task_type=preliminary.task_type,
        allowed_mutation=preliminary.allowed_mutation,
        explicit_constraints=preliminary.explicit_constraints,
        missing_information=missing,
        forbidden_assumptions=forbidden,
        success_criteria=preliminary.success_criteria,
        stakes=preliminary.stakes,
    )


def detect_missing_information(contract: TaskContract) -> list[str]:
    missing: list[str] = []
    text = contract.raw_intent.lower()
    if not contract.target_artifact and contract.task_type in {TaskType.BUG_FIX, TaskType.PATCH, TaskType.REFACTOR, TaskType.TEST}:
        missing.append("target_artifact")
    if not contract.explicit_constraints:
        missing.append("explicit_constraints")
    if not contract.success_criteria and contract.task_type != TaskType.EXPLAIN:
        missing.append("success_criteria")
    if has_vagueness(text):
        missing.append("vague_terms_need_clarification")
    if contract.allowed_mutation == MutationType.BROAD_REWRITE:
        missing.append("explicit_broad_rewrite_authorization")
    return missing


def list_forbidden_assumptions(contract: TaskContract) -> list[str]:
    return list(contract.forbidden_assumptions)


def contract_to_prompt_anchor(contract: TaskContract) -> str:
    """Render the contract as a model-facing anti-guessing anchor."""
    constraints = _format_items(contract.explicit_constraints, "No explicit constraints supplied.")
    missing = _format_items(contract.missing_information, "No missing information detected.")
    forbidden = _format_items(contract.forbidden_assumptions, "Do not invent unstated facts.")
    success = _format_items(contract.success_criteria, "No success criteria supplied.")
    target = contract.target_artifact or "UNSPECIFIED"
    return (
        "TAPES COGNITION ANCHOR\n"
        "Reason only from the bounded contract below.\n"
        f"Intent: {contract.raw_intent}\n"
        f"Target artifact: {target}\n"
        f"Task type: {contract.task_type.value}\n"
        f"Allowed mutation: {contract.allowed_mutation.value}\n"
        f"Stakes: {contract.stakes.value}\n"
        f"Explicit constraints:\n{constraints}\n"
        f"Success criteria:\n{success}\n"
        f"Missing information:\n{missing}\n"
        f"Forbidden assumptions:\n{forbidden}\n"
        "If missing information is required, ask or mark it unknown. Do not fill gaps with plausible guesses."
    )


def classify_task_type(text: str) -> TaskType:
    """Classify task type using documented precedence from CLASSIFICATION_PRECEDENCE."""
    lowered = text.lower()
    for category, task_type in CLASSIFICATION_PRECEDENCE:
        if contains_any_token(lowered, get_words(category)):
            return task_type
    return TaskType.UNKNOWN


def infer_mutation_type(text: str, task_type: TaskType) -> MutationType:
    """Infer mutation type using ontology-backed detection."""
    from ..semantics import detect_mutation_scope
    lowered = text.lower()

    # Use ontology for mutation scope detection
    scope = detect_mutation_scope(lowered)
    if scope == "broad":
        return MutationType.BROAD_REWRITE
    if scope == "exact" or task_type == TaskType.PATCH:
        return MutationType.EXACT_PATCH
    if task_type == TaskType.REFACTOR:
        return MutationType.REFACTOR
    if task_type in {TaskType.BUG_FIX, TaskType.FEATURE, TaskType.TEST}:
        return MutationType.LOCAL_EDIT
    return MutationType.NONE


def infer_stakes(text: str) -> Stakes:
    if has_high_stakes(text):
        return Stakes.HIGH
    if has_medium_stakes(text):
        return Stakes.MEDIUM
    return Stakes.LOW


def default_forbidden_assumptions(contract: TaskContract) -> list[str]:
    forbidden = [
        "Do not invent files, APIs, functions, tests, or runtime behavior not present in provided evidence.",
        "Do not broaden mutation scope beyond the declared target without a boundary-widening decision.",
    ]
    if contract.target_artifact is None:
        forbidden.append("Do not assume the target artifact.")
    if "explicit_constraints" in contract.missing_information:
        forbidden.append("Do not invent missing constraints.")
    if contract.allowed_mutation != MutationType.BROAD_REWRITE:
        forbidden.append("Do not perform broad rewrites.")
    return forbidden


def _normalize_input(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, str):
        return {"raw_intent": value}
    if not isinstance(value, dict):
        raise TypeError("Task input must be a string or dictionary.")
    raw = value.get("raw_intent") or value.get("task") or value.get("intent")
    if raw is None:
        raise ValueError("Task dictionary requires 'task', 'intent', or 'raw_intent'.")
    return {**value, "raw_intent": str(raw)}


def _detect_target(text: str) -> str | None:
    file_match = re.search(r"\b([\w./\\-]+\.(?:py|js|ts|tsx|jsx|java|kt|go|rs|md|json|yaml|yml|toml))\b", text, re.I)
    if file_match:
        return file_match.group(1)
    return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    return [str(item) for item in value]


def _format_items(items: tuple[str, ...], empty: str) -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def _coerce_task_type(value: Any) -> TaskType | None:
    if value is None:
        return None
    try:
        return TaskType(str(value))
    except ValueError:
        return None


def _coerce_mutation(value: Any) -> MutationType | None:
    if value is None:
        return None
    try:
        return MutationType(str(value))
    except ValueError:
        return None


def _coerce_stakes(value: Any) -> Stakes | None:
    if value is None:
        return None
    try:
        return Stakes(str(value))
    except ValueError:
        return None
