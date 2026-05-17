from forest_tapes.tapes_core.debate import (
    create_alpha_agent,
    create_judge_agent,
    create_omega_agent,
    assess_risk,
    run_debate,
)
from forest_tapes.tapes_core.models import (
    DebateDomain,
    DebateVote,
    MutationType,
    RiskTier,
    Stakes,
    TaskType,
)
from forest_tapes.tapes_core.task_contract import parse_task_contract


def test_alpha_and_omega_have_different_domains() -> None:
    alpha = create_alpha_agent()
    omega = create_omega_agent()
    assert alpha.domain == DebateDomain.ARCHITECTURE
    assert omega.domain == DebateDomain.SECURITY
    assert alpha.domain != omega.domain


def test_assess_risk_low_stakes() -> None:
    contract = parse_task_contract("explain this function")
    risk = assess_risk(contract, instability_score=0.1)
    assert risk.tier == RiskTier.LOW
    assert risk.debate_rounds == 1
    assert not risk.requires_formal_verification


def test_assess_risk_high_stakes() -> None:
    contract = parse_task_contract(
        "Fix critical production security bug in auth payment system"
    )
    risk = assess_risk(contract, instability_score=0.8)
    assert risk.tier == RiskTier.CRITICAL
    assert risk.debate_rounds == 3
    assert risk.requires_formal_verification


def test_debate_both_accept() -> None:
    contract = parse_task_contract("Fix auth bug")
    risk = assess_risk(contract, 0.2)

    result = run_debate(
        contract=contract,
        proposal="Fix the auth bug",
        risk=risk,
        alpha_findings=("Architecture looks sound",),
        alpha_votes=(DebateVote.ACCEPT,),
        alpha_confidences=(0.9,),
        omega_findings=("No security issues found",),
        omega_votes=(DebateVote.ACCEPT,),
        omega_confidences=(0.85,),
    )

    assert result.verdict == DebateVote.ACCEPT
    assert len(result.votes) == 2


def test_debate_omega_rejects() -> None:
    contract = parse_task_contract("Fix auth bug")
    risk = assess_risk(contract, 0.2)

    result = run_debate(
        contract=contract,
        proposal="Fix the auth bug",
        risk=risk,
        alpha_findings=("Architecture looks sound",),
        alpha_votes=(DebateVote.ACCEPT,),
        alpha_confidences=(0.9,),
        omega_findings=("SQL injection vulnerability detected",),
        omega_votes=(DebateVote.REJECT,),
        omega_confidences=(0.95,),
    )

    assert result.verdict == DebateVote.REJECT


def test_debate_empty_votes_default_to_reject() -> None:
    contract = parse_task_contract("Fix auth bug")
    risk = assess_risk(contract, 0.2)

    result = run_debate(
        contract=contract,
        proposal="Fix the auth bug",
        risk=risk,
    )

    assert result.verdict == DebateVote.REJECT


def test_debate_summary_contains_all_agents() -> None:
    contract = parse_task_contract("Fix auth bug")
    risk = assess_risk(contract, 0.2)

    result = run_debate(
        contract=contract,
        proposal="Fix the auth bug",
        risk=risk,
        alpha_findings=("Logic issue",),
        alpha_votes=(DebateVote.REJECT,),
        alpha_confidences=(0.7,),
        omega_findings=("Security issue",),
        omega_votes=(DebateVote.REJECT,),
        omega_confidences=(0.8,),
    )

    assert "Alpha" in result.summary
    assert "Omega" in result.summary
    assert "reject" in result.summary
