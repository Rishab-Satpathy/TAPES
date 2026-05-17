from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PatchOperation(StrEnum):
    """Explicit operation types for mutation clarity.
    DELETE: remove matched text with no replacement.
    REPLACE: substitute matched text with replacement.
    INSERT: add text at a position (search must be empty, replace is the insertion)."""
    DELETE = "delete"
    REPLACE = "replace"
    INSERT = "insert"


class PatchDisciplineError(ValueError):
    """Raised when a patch violates TAPES mutation locality."""


@dataclass(frozen=True)
class ExactPatch:
    target_id: str
    search: str
    replace: str
    reasoning: str
    operation: PatchOperation = PatchOperation.REPLACE


@dataclass(frozen=True)
class PatchResult:
    target_id: str
    before: str
    after: str
    changed: bool
    operation: PatchOperation


def apply_exact_patch(source: str, patch: ExactPatch) -> PatchResult:
    """Apply one exact patch, rejecting zero-match and multi-match mutation ambiguity.
    Calls validate_patch internally before applying."""
    validate_patch(patch)

    if patch.operation == PatchOperation.INSERT:
        return PatchResult(
            target_id=patch.target_id,
            before=source,
            after=source + patch.replace,
            changed=bool(patch.replace),
            operation=patch.operation,
        )

    if patch.operation == PatchOperation.DELETE:
        matches = source.count(patch.search)
        if matches == 0:
            raise PatchDisciplineError("Patch rejected: search block matched zero times.")
        if matches > 1:
            raise PatchDisciplineError("Patch rejected: search block matched more than once.")
        after = source.replace(patch.search, "", 1)
        return PatchResult(
            target_id=patch.target_id,
            before=source,
            after=after,
            changed=after != source,
            operation=patch.operation,
        )

    # REPLACE (default)
    matches = source.count(patch.search)
    if matches == 0:
        raise PatchDisciplineError("Patch rejected: search block matched zero times.")
    if matches > 1:
        raise PatchDisciplineError("Patch rejected: search block matched more than once.")
    after = source.replace(patch.search, patch.replace, 1)
    return PatchResult(
        target_id=patch.target_id,
        before=source,
        after=after,
        changed=after != source,
        operation=patch.operation,
    )


def validate_patch(patch: ExactPatch) -> None:
    """Validate patch structure. Called by apply_exact_patch before mutation.
    Raises PatchDisciplineError if the patch violates TAPES mutation locality."""
    if not patch.target_id.strip():
        raise PatchDisciplineError("Patch target is required.")
    if not patch.search and patch.operation != PatchOperation.INSERT:
        raise PatchDisciplineError("Patch search block is required for non-INSERT operations.")
    if not patch.replace and patch.operation == PatchOperation.REPLACE:
        raise PatchDisciplineError("Patch replace block is required for REPLACE operation.")
    if not patch.reasoning.strip():
        raise PatchDisciplineError("Patch reasoning is required.")
