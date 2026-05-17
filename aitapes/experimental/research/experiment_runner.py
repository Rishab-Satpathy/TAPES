from __future__ import annotations

from dataclasses import dataclass

from typing import Any

from .allocator import allocate_cognition
from .task_contract import contract_to_prompt_anchor


@dataclass(frozen=True)
class ExperimentPromptPair:
    raw_prompt: str
    tapes_prompt: str
    stabilization_claim: str


def build_same_model_experiment_prompt(task: str | dict[str, Any]) -> ExperimentPromptPair:
    """Create raw-vs-TAPES prompts for the central same-model experiment."""
    allocation = allocate_cognition(task)
    raw_prompt = allocation.contract.raw_intent
    tapes_prompt = "\n\n".join(
        (
            contract_to_prompt_anchor(allocation.contract),
            f"Required representation: {allocation.representation.value}",
            f"Reasoning scope: {allocation.scope}",
            f"Validation level: {allocation.validation.level.value}",
            "Produce output only inside this bounded reasoning surface.",
        )
    )
    return ExperimentPromptPair(
        raw_prompt=raw_prompt,
        tapes_prompt=tapes_prompt,
        stabilization_claim="Same model, structured reasoning pressure, expected lower hallucination and mutation spread.",
    )
