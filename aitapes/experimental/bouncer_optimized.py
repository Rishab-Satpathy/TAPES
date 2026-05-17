"""Bouncer Optimized for TAPES v8.0.

Cherry-picked from NovelIdeaEdition's bouncer module.
Risk-based validation gate with retry logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

__all__ = ["Bouncer", "RiskScore", "RetryDecision", "classify_failure"]

logger = logging.getLogger(__name__)


class RetryDecision(Enum):
    """Decision for retry strategy after validation failure."""
    RETRY = auto()
    FALLBACK = auto()
    REJECT = auto()


@dataclass
class RiskScore:
    """Risk score for a validation decision."""
    total: float
    factors: tuple[str, ...]
    tier: str  # "low", "medium", "high", "critical"


class Bouncer:
    """Risk-based validation gate with retry logic."""

    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = threshold
        self._history: list[RiskScore] = []

    def assess(self, context: dict[str, Any]) -> RiskScore:
        """Assess risk for a given context."""
        score = 0.0
        factors: list[str] = []

        stakes = context.get("stakes", "low")
        if stakes == "high":
            score += 0.4
            factors.append("high_stakes")
        elif stakes == "medium":
            score += 0.2
            factors.append("medium_stakes")

        complexity = context.get("complexity", 0)
        if complexity > 100:
            score += 0.3
            factors.append("high_complexity")
        elif complexity > 50:
            score += 0.15
            factors.append("medium_complexity")

        mutation = context.get("mutation_boundary", "local_edit")
        if mutation == "broad_rewrite":
            score += 0.2
            factors.append("broad_mutation")
        elif mutation == "refactor":
            score += 0.1
            factors.append("refactor_mutation")

        tier = "low"
        if score >= 0.7:
            tier = "critical"
        elif score >= 0.5:
            tier = "high"
        elif score >= 0.3:
            tier = "medium"

        risk = RiskScore(total=score, factors=tuple(factors), tier=tier)
        self._history.append(risk)
        return risk

    def should_allow(self, context: dict[str, Any]) -> bool:
        """Check if operation should be allowed based on risk assessment."""
        risk = self.assess(context)
        return risk.total < self._threshold

    def retry_decision(self, failure_count: int, risk: RiskScore) -> RetryDecision:
        """Determine retry strategy based on failure count and risk."""
        if failure_count >= 3:
            return RetryDecision.REJECT

        if risk.tier == "critical":
            return RetryDecision.REJECT

        if risk.tier == "high":
            if failure_count >= 2:
                return RetryDecision.FALLBACK
            return RetryDecision.RETRY

        if failure_count >= 1:
            return RetryDecision.FALLBACK

        return RetryDecision.RETRY

    def summary(self) -> dict[str, Any]:
        return {
            "threshold": self._threshold,
            "decisions": len(self._history),
            "avg_risk": sum(r.total for r in self._history) / max(len(self._history), 1),
        }


def classify_failure(error_output: str, return_code: int) -> str:
    """Classify failure type from error output.

    B8 fix: require both "assert " AND "assertion" to avoid false positives.
    """
    lower = error_output.lower()

    if "syntaxerror" in lower or "syntax error" in lower:
        return "ast_parse_fatal"
    if "indentationerror" in lower or "unexpected indent" in lower:
        return "indentation_mismatch"
    if "assert " in lower and "assertion" in lower:
        return "pytest_assertion_fail"
    if "typeerror" in lower or "type error" in lower:
        return "type_checker_reject"
    if return_code == -1 and "timed out" in lower:
        return "execution_timeout"

    return "unknown"