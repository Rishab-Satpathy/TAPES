"""Contract data model for AITAPES.

The contract is the single source of truth that flows between
plan → build → check commands. It carries intent, constraints,
forbidden assumptions, mutation boundaries, and stakes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Contract:
    """Stabilized requirement contract."""
    intent: str
    constraints: tuple[str, ...] = ()
    forbidden_assumptions: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    stakes: str = "low"
    mutation_boundary: str = "local_edit"
    target_files: tuple[str, ...] = ()
    created_at: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert tuples to lists for JSON serialization
        for key in ("constraints", "forbidden_assumptions", "success_criteria",
                     "missing_information", "target_files"):
            d[key] = list(d[key])
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contract:
        # Convert lists back to tuples
        for key in ("constraints", "forbidden_assumptions", "success_criteria",
                     "missing_information", "target_files"):
            if key in data and isinstance(data[key], list):
                data[key] = tuple(data[key])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, text: str) -> Contract:
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: str | Path) -> Contract:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")


def validate_contract(contract: Contract) -> list[str]:
    """Validate a contract. Returns list of issues (empty = valid)."""
    issues: list[str] = []

    if not contract.intent.strip():
        issues.append("Contract intent cannot be empty.")

    if contract.stakes not in ("low", "medium", "high"):
        issues.append(f"Invalid stakes: {contract.stakes}")

    if contract.mutation_boundary not in ("none", "exact_patch", "local_edit", "refactor", "broad_rewrite"):
        issues.append(f"Invalid mutation_boundary: {contract.mutation_boundary}")

    if not contract.success_criteria:
        issues.append("Contract should have at least one success criterion.")

    return issues


def create_contract(
    intent: str,
    constraints: list[str] | None = None,
    success_criteria: list[str] | None = None,
    stakes: str = "low",
    mutation_boundary: str = "local_edit",
    target_files: list[str] | None = None,
) -> Contract:
    """Create a new contract with automatic constraint extraction."""
    forbidden: list[str] = [
        "Do not invent files, APIs, functions, or runtime behavior not present in provided evidence.",
        "Do not broaden mutation scope beyond the declared target.",
    ]

    if mutation_boundary != "broad_rewrite":
        forbidden.append("Do not perform broad rewrites.")

    missing: list[str] = []
    if not constraints:
        missing.append("explicit_constraints")
    if not success_criteria:
        missing.append("success_criteria")

    return Contract(
        intent=intent,
        constraints=tuple(constraints or []),
        forbidden_assumptions=tuple(forbidden),
        success_criteria=tuple(success_criteria or []),
        missing_information=tuple(missing),
        stakes=stakes,
        mutation_boundary=mutation_boundary,
        target_files=tuple(target_files or []),
    )
