"""Uncertainty tag handling for TAPES.

Structured way for models to say "I don't know."
Converts hallucination into a typed signal the orchestrator can handle.

Format in model output:
    <uncertainty>
        <claim>What the model is uncertain about</claim>
        <confidence>0.0-1.0</confidence>
        <evidence>What evidence exists</evidence>
        <alternative>What else might be true</alternative>
    </uncertainty>
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import UncertaintyTag


# Threshold provenance:
# LOW_CONFIDENCE = 0.3: Below this, the claim is unreliable
# MEDIUM_CONFIDENCE = 0.6: Below this, needs verification
# HIGH_CONFIDENCE = 0.8: Above this, generally trustworthy
LOW_CONFIDENCE = 0.3
MEDIUM_CONFIDENCE = 0.6
HIGH_CONFIDENCE = 0.8


def parse_uncertainty_tags(text: str) -> list[UncertaintyTag]:
    """Parse <uncertainty> tags from model output."""
    tags: list[UncertaintyTag] = []
    pattern = re.compile(
        r"<uncertainty>\s*"
        r"<claim>(.*?)</claim>\s*"
        r"<confidence>([\d.]+)</confidence>\s*"
        r"<evidence>(.*?)</evidence>\s*"
        r"(?:<alternative>(.*?)</alternative>\s*)?"
        r"</uncertainty>",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        claim = match.group(1).strip()
        try:
            confidence = float(match.group(2))
        except ValueError:
            confidence = 0.0
        evidence = match.group(3).strip()
        alternative = (match.group(4) or "").strip()
        tags.append(UncertaintyTag(
            claim=claim,
            confidence=confidence,
            evidence=evidence,
            alternative=alternative,
        ))
    return tags


def has_uncertainty(text: str) -> bool:
    """Check if model output contains uncertainty tags."""
    return "<uncertainty>" in text


def filter_reliable_claims(tags: list[UncertaintyTag]) -> list[UncertaintyTag]:
    """Filter tags to only those above the reliability threshold."""
    return [t for t in tags if t.confidence >= MEDIUM_CONFIDENCE]


def filter_unreliable_claims(tags: list[UncertaintyTag]) -> list[UncertaintyTag]:
    """Filter tags to only those below the reliability threshold."""
    return [t for t in tags if t.confidence < MEDIUM_CONFIDENCE]


def summarize_uncertainty(tags: list[UncertaintyTag]) -> str:
    """Generate a summary of uncertainty tags for the orchestrator."""
    if not tags:
        return "No uncertainty tags found."

    reliable = filter_reliable_claims(tags)
    unreliable = filter_unreliable_claims(tags)

    parts = [f"Uncertainty summary: {len(tags)} total, {len(reliable)} reliable, {len(unreliable)} unreliable"]
    for tag in unreliable:
        parts.append(f"  UNRELIABLE ({tag.confidence:.2f}): {tag.claim}")
        if tag.alternative:
            parts.append(f"    Alternative: {tag.alternative}")
    for tag in reliable:
        parts.append(f"  RELIABLE ({tag.confidence:.2f}): {tag.claim}")

    return "\n".join(parts)


def uncertainty_to_risk_factors(tags: list[UncertaintyTag]) -> tuple[str, ...]:
    """Convert uncertainty tags to risk factors for the pressure system."""
    factors: list[str] = []
    for tag in filter_unreliable_claims(tags):
        if tag.confidence < LOW_CONFIDENCE:
            factors.append(f"high_uncertainty: {tag.claim[:50]}")
        else:
            factors.append(f"moderate_uncertainty: {tag.claim[:50]}")
    return tuple(factors)
