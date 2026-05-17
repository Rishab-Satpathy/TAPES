from forest_tapes.tapes_core.uncertainty import (
    filter_reliable_claims,
    filter_unreliable_claims,
    has_uncertainty,
    parse_uncertainty_tags,
    summarize_uncertainty,
    uncertainty_to_risk_factors,
)


def test_parse_uncertainty_tags_basic() -> None:
    text = """Here is my answer.
    <uncertainty>
        <claim>The function is pure</claim>
        <confidence>0.8</confidence>
        <evidence>No side effects observed</evidence>
    </uncertainty>
    """
    tags = parse_uncertainty_tags(text)
    assert len(tags) == 1
    assert tags[0].claim == "The function is pure"
    assert tags[0].confidence == 0.8
    assert tags[0].evidence == "No side effects observed"


def test_parse_uncertainty_tags_with_alternative() -> None:
    text = """<uncertainty>
        <claim>Database is PostgreSQL</claim>
        <confidence>0.6</confidence>
        <evidence>Connection string pattern</evidence>
        <alternative>Could be MySQL</alternative>
    </uncertainty>
    """
    tags = parse_uncertainty_tags(text)
    assert len(tags) == 1
    assert tags[0].alternative == "Could be MySQL"


def test_parse_uncertainty_tags_multiple() -> None:
    text = """<uncertainty>
        <claim>Claim 1</claim>
        <confidence>0.9</confidence>
        <evidence>Evidence 1</evidence>
    </uncertainty>
    <uncertainty>
        <claim>Claim 2</claim>
        <confidence>0.2</confidence>
        <evidence>Evidence 2</evidence>
    </uncertainty>
    """
    tags = parse_uncertainty_tags(text)
    assert len(tags) == 2


def test_has_uncertainty() -> None:
    assert has_uncertainty("<uncertainty>test</uncertainty>") is True
    assert has_uncertainty("no tags here") is False


def test_filter_reliable_claims() -> None:
    text = """<uncertainty>
        <claim>Reliable claim</claim>
        <confidence>0.8</confidence>
        <evidence>Strong evidence</evidence>
    </uncertainty>
    <uncertainty>
        <claim>Unreliable claim</claim>
        <confidence>0.2</confidence>
        <evidence>Weak evidence</evidence>
    </uncertainty>
    """
    tags = parse_uncertainty_tags(text)
    reliable = filter_reliable_claims(tags)
    unreliable = filter_unreliable_claims(tags)
    assert len(reliable) == 1
    assert len(unreliable) == 1
    assert reliable[0].claim == "Reliable claim"
    assert unreliable[0].claim == "Unreliable claim"


def test_summarize_uncertainty() -> None:
    text = """<uncertainty>
        <claim>Low confidence</claim>
        <confidence>0.2</confidence>
        <evidence>Weak</evidence>
    </uncertainty>
    """
    tags = parse_uncertainty_tags(text)
    summary = summarize_uncertainty(tags)
    assert "UNRELIABLE" in summary
    assert "Low confidence" in summary


def test_uncertainty_to_risk_factors() -> None:
    text = """<uncertainty>
        <claim>High risk claim</claim>
        <confidence>0.1</confidence>
        <evidence>Very weak</evidence>
    </uncertainty>
    """
    tags = parse_uncertainty_tags(text)
    factors = uncertainty_to_risk_factors(tags)
    assert len(factors) == 1
    assert "high_uncertainty" in factors[0]
