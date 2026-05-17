from forest_tapes.tapes_core.allocator import allocate_cognition
from forest_tapes.tapes_core.models import DebateVote, ValidationLevel


def test_allocator_with_debate_accept() -> None:
    result = allocate_cognition(
        "Fix auth bug",
        debate_findings={
            "proposal": "Fix the auth bug by updating the token validation",
            "alpha_findings": ("Architecture is sound",),
            "alpha_votes": (DebateVote.ACCEPT,),
            "alpha_confidences": (0.9,),
            "omega_findings": ("No security issues",),
            "omega_votes": (DebateVote.ACCEPT,),
            "omega_confidences": (0.85,),
        },
    )

    assert "Debate verdict: accept" in " ".join(result.rationale)
    assert any("Debate summary" in line for line in result.rationale)


def test_allocator_with_debate_reject() -> None:
    result = allocate_cognition(
        "Fix auth bug",
        debate_findings={
            "proposal": "Fix the auth bug",
            "alpha_findings": ("Logic issue",),
            "alpha_votes": (DebateVote.ACCEPT,),
            "alpha_confidences": (0.7,),
            "omega_findings": ("SQL injection vulnerability",),
            "omega_votes": (DebateVote.REJECT,),
            "omega_confidences": (0.95,),
        },
    )

    assert "Debate verdict: reject" in " ".join(result.rationale)
    assert result.validation.level == ValidationLevel.ADVERSARIAL_CHECK


def test_allocator_without_debate() -> None:
    result = allocate_cognition("Fix auth bug")
    assert not any("Debate verdict" in line for line in result.rationale)
