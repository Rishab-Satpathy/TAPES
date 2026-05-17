from forest_tapes.semantics import (
    contains_any_token,
    contains_token,
    count_tokens,
    has_cross_scope,
    has_high_stakes,
    has_medium_stakes,
    has_vagueness,
    score_ambiguity,
    score_subjectivity,
    trace_routing,
)
from forest_tapes.semantics.ontology import SemanticCategory, get_words


def test_contains_token_matches_whole_words_only() -> None:
    assert contains_token("fix the bug", "bug") is True
    assert contains_token("debug the issue", "bug") is False
    assert contains_token("make this awesome", "some") is False


def test_contains_any_token_matches_multiple_words() -> None:
    assert contains_any_token("fix the crash error", ("bug", "crash", "error")) is True
    assert contains_any_token("build a feature", ("bug", "crash", "error")) is False


def test_count_tokens_counts_distinct_matches() -> None:
    assert count_tokens("fix the crash and error", ("crash", "error", "bug")) == 2
    assert count_tokens("no matches here", ("crash", "error")) == 0


def test_score_ambiguity_returns_float() -> None:
    score = score_ambiguity("Fix some appropriate thing")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_score_ambiguity_increases_with_more_vague_terms() -> None:
    low = score_ambiguity("fix bug")
    high = score_ambiguity("fix some appropriate reasonable thing")
    assert high > low


def test_score_subjectivity_detects_subjective_terms() -> None:
    assert score_subjectivity("make it better") > 0.0
    assert score_subjectivity("fix the bug") == 0.0


def test_has_vagueness_detects_vague_terms() -> None:
    assert has_vagueness("fix some thing") is True
    assert has_vagueness("fix the specific bug") is False


def test_has_cross_scope_detects_scope_expansion() -> None:
    assert has_cross_scope("fix across all files") is True
    assert has_cross_scope("fix this function") is False


def test_has_high_stakes_detects_domain_terms() -> None:
    assert has_high_stakes("fix security vulnerability") is True
    assert has_high_stakes("fix the typo") is False


def test_has_medium_stakes_detects_elevated_terms() -> None:
    assert has_medium_stakes("important review") is True
    assert has_medium_stakes("fix the bug") is False


def test_trace_routing_returns_candidates() -> None:
    trace = trace_routing("Fix the runtime stack trace crash")
    assert trace.winner is not None
    assert trace.winner == SemanticCategory.RUNTIME_EVIDENCE
    assert len(trace.candidates) >= 1
    assert trace.total_evidence > 0


def test_trace_routing_returns_none_for_no_match() -> None:
    trace = trace_routing("do something vague")
    assert trace.winner is None
    assert len(trace.candidates) == 0
    assert trace.total_evidence == 0


def test_ontology_has_all_categories() -> None:
    for category in SemanticCategory:
        words = get_words(category)
        assert isinstance(words, tuple)
        assert len(words) > 0
