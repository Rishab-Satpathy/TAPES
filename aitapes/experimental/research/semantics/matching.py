"""Unified text matching for TAPES cognition pressure systems.

Provides doctrine-level matching primitives that prevent ontology drift
across modules. All text matching in the TAPES pipeline should flow
through this module to maintain semantic consistency.

Matching tiers:
    EXACT: full string equality
    TOKEN: word-boundary regex (default for most pressure scoring)
    PHRASE: multi-word substring matching
    STEMMED: basic suffix stripping for morphological variants
"""

from __future__ import annotations

import re
from enum import StrEnum


class MatchTier(StrEnum):
    EXACT = "exact"
    TOKEN = "token"
    PHRASE = "phrase"
    STEMMED = "stemmed"


# Compiled token pattern cache to avoid recompilation on hot paths
_token_cache: dict[str, re.Pattern[str]] = {}


def _compile_token_pattern(word: str) -> re.Pattern[str]:
    if word not in _token_cache:
        _token_cache[word] = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    return _token_cache[word]


def contains_token(text: str, word: str) -> bool:
    """Word-boundary regex match. Use for pressure scoring and classification."""
    return bool(_compile_token_pattern(word).search(text))


def contains_any_token(text: str, words: tuple[str, ...]) -> bool:
    """Word-boundary match against multiple tokens. Default for most TAPES matching."""
    return any(contains_token(text, w) for w in words)


def count_tokens(text: str, words: tuple[str, ...]) -> int:
    """Count how many distinct tokens from the set appear in text."""
    return sum(1 for w in words if contains_token(text, w))


def contains_phrase(text: str, phrase: str) -> bool:
    """Substring match for multi-word phrases like 'crash log' or 'data flow'."""
    return phrase.lower() in text.lower()


def contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    """Substring match against multiple phrases."""
    return any(contains_phrase(text, p) for p in phrases)


def contains_stem(text: str, stem: str) -> bool:
    """Basic stemmed match. Handles common English suffixes.
    Use sparingly — prefer TOKEN for pressure scoring."""
    lowered = text.lower()
    stem_lower = stem.lower()
    if stem_lower in lowered:
        return True
    for suffix in ("ing", "ed", "tion", "ment", "ness", "ity", "ous", "ive", "able"):
        if lowered.endswith(suffix) and stem_lower + suffix[:-2] in lowered:
            return True
    return False


def match_tier(text: str, words: tuple[str, ...], tier: MatchTier = MatchTier.TOKEN) -> bool:
    """Dispatch matching to the specified tier."""
    if tier == MatchTier.EXACT:
        return text.lower().strip() in {w.lower() for w in words}
    if tier == MatchTier.TOKEN:
        return contains_any_token(text, words)
    if tier == MatchTier.PHRASE:
        return contains_any_phrase(text, words)
    if tier == MatchTier.STEMMED:
        return any(contains_stem(text, w) for w in words)
    return False
