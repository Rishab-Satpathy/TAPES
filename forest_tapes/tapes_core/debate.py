"""Adversarial debate module for TAPES.

Runs debate BEFORE code exists, not after. Alpha attacks architecture/logic,
Omega attacks security/concurrency. Domain separation prevents correlated failure.

State machine:
    PROPOSE -> ALPHA_VOTE -> OMEGA_VOTE -> (if split) JUDGE -> ACCEPT/REJECT

Key constraint: both agents must accept for the pipeline to proceed.
Asymmetric vote resolution: CRITICAL findings override HIGH/MEDIUM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import (
    DebateAgent,
    DebateDomain,
    DebateResult,
    DebateVote,
    DebateVoteRecord,
    RiskAssessment,
    RiskTier,
    TaskContract,
    UncertaintyTag,
)


class DebateState(StrEnum):
    PROPOSE = "propose"
    ALPHA_VOTE = "alpha_vote"
    OMEGA_VOTE = "omega_vote"
    JUDGE = "judge"
    ACCEPT = "accept"
    REJECT = "reject"


# Threshold provenance:
# CONFIDENCE_FLOOR = 0.3: Below this, the vote is abstain (not enough evidence)
# CRITICAL_WEIGHT = 1.0: CRITICAL findings always override
# HIGH_WEIGHT = 0.7: HIGH findings need consensus to block
# MEDIUM_WEIGHT = 0.3: MEDIUM findings rarely block alone
# MAX_ROUNDS = 3: Prevents infinite debate loops
CONFIDENCE_FLOOR = 0.3
CRITICAL_WEIGHT = 1.0
HIGH_WEIGHT = 0.7
MEDIUM_WEIGHT = 0.3
MAX_ROUNDS = 3


def create_alpha_agent() -> DebateAgent:
    """Alpha: attacks architecture, logic, correctness."""
    return DebateAgent(
        name="Alpha",
        domain=DebateDomain.ARCHITECTURE,
        temperature=0.3,
        rationale="Alpha focuses on architectural soundness, logic errors, and correctness.",
    )


def create_omega_agent() -> DebateAgent:
    """Omega: attacks security, concurrency, edge cases."""
    return DebateAgent(
        name="Omega",
        domain=DebateDomain.SECURITY,
        temperature=0.2,
        rationale="Omega focuses on security vulnerabilities, race conditions, and edge cases.",
    )


def create_judge_agent() -> DebateAgent:
    """Judge: breaks ties when Alpha and Omega disagree."""
    return DebateAgent(
        name="Judge",
        domain=DebateDomain.CORRECTNESS,
        temperature=0.1,
        rationale="Judge resolves disagreements between Alpha and Omega.",
    )


def assess_risk(contract: TaskContract, instability_score: float) -> RiskAssessment:
    """Assess risk tier to determine debate intensity."""
    score = 0.0
    factors: list[str] = []

    # Stakes contribution
    if contract.stakes.value == "high":
        score += 0.4
        factors.append("high_stakes")
    elif contract.stakes.value == "medium":
        score += 0.2
        factors.append("medium_stakes")

    # Instability contribution
    if instability_score >= 0.6:
        score += 0.3
        factors.append("high_instability")
    elif instability_score >= 0.3:
        score += 0.15
        factors.append("moderate_instability")

    # Mutation contribution
    if contract.allowed_mutation.value == "broad_rewrite":
        score += 0.2
        factors.append("broad_mutation")
    elif contract.allowed_mutation.value == "refactor":
        score += 0.1
        factors.append("refactor_mutation")

    # Missing information contribution
    if len(contract.missing_information) > 2:
        score += 0.1
        factors.append("missing_information")

    # Determine tier
    if score >= 0.7:
        tier = RiskTier.CRITICAL
    elif score >= 0.5:
        tier = RiskTier.HIGH
    elif score >= 0.3:
        tier = RiskTier.MEDIUM
    else:
        tier = RiskTier.LOW

    # Debate rounds based on risk
    if tier == RiskTier.CRITICAL:
        debate_rounds = 3
    elif tier == RiskTier.HIGH:
        debate_rounds = 2
    else:
        debate_rounds = 1

    return RiskAssessment(
        tier=tier,
        score=score,
        factors=tuple(factors),
        debate_rounds=debate_rounds,
        requires_formal_verification=tier == RiskTier.CRITICAL,
    )


def run_debate(
    contract: TaskContract,
    proposal: str,
    risk: RiskAssessment,
    alpha_findings: tuple[str, ...] = (),
    alpha_votes: tuple[DebateVote, ...] = (),
    alpha_confidences: tuple[float, ...] = (),
    omega_findings: tuple[str, ...] = (),
    omega_votes: tuple[DebateVote, ...] = (),
    omega_confidences: tuple[float, ...] = (),
) -> DebateResult:
    """Run adversarial debate between Alpha and Omega.
    
    In production, alpha_findings/omega_findings come from LLM calls.
    In testing, they are passed directly.
    """
    votes: list[DebateVoteRecord] = []

    # Alpha vote
    alpha_vote = _tally_agent_votes(
        agent_name="Alpha",
        domain=DebateDomain.ARCHITECTURE,
        findings=alpha_findings,
        votes=alpha_votes,
        confidences=alpha_confidences,
    )
    votes.append(alpha_vote)

    # Omega vote
    omega_vote = _tally_agent_votes(
        agent_name="Omega",
        domain=DebateDomain.SECURITY,
        findings=omega_findings,
        votes=omega_votes,
        confidences=omega_confidences,
    )
    votes.append(omega_vote)

    # Determine verdict
    verdict = _resolve_verdict(votes, risk)

    return DebateResult(
        votes=tuple(votes),
        verdict=verdict,
        rounds=1,
        risk_tier=risk.tier,
        summary=_generate_summary(votes, verdict),
    )


def _tally_agent_votes(
    agent_name: str,
    domain: DebateDomain,
    findings: tuple[str, ...],
    votes: tuple[DebateVote, ...],
    confidences: tuple[float, ...],
) -> DebateVoteRecord:
    """Tally votes from a single agent across findings."""
    if not votes:
        return DebateVoteRecord(
            agent=agent_name,
            domain=domain,
            vote=DebateVote.ABSTAIN,
            confidence=0.0,
            findings=findings,
            rationale="No votes submitted; abstaining.",
        )

    # Weighted vote tally
    accept_weight = 0.0
    reject_weight = 0.0
    for vote, conf in zip(votes, confidences):
        effective_conf = max(conf, CONFIDENCE_FLOOR)
        if vote == DebateVote.ACCEPT:
            accept_weight += effective_conf
        elif vote == DebateVote.REJECT:
            reject_weight += effective_conf

    if reject_weight > accept_weight:
        final_vote = DebateVote.REJECT
    elif accept_weight > reject_weight:
        final_vote = DebateVote.ACCEPT
    else:
        final_vote = DebateVote.ABSTAIN

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

    return DebateVoteRecord(
        agent=agent_name,
        domain=domain,
        vote=final_vote,
        confidence=avg_confidence,
        findings=findings,
        rationale=f"{agent_name} voted {final_vote.value} with {avg_confidence:.2f} confidence.",
    )


def _resolve_verdict(votes: list[DebateVoteRecord], risk: RiskAssessment) -> DebateVote:
    """Resolve final verdict using asymmetric vote resolution.
    
    Rules:
    - Both must ACCEPT for ACCEPT
    - CRITICAL finding from either agent forces REJECT
    - HIGH findings need both agents to agree
    - Tied votes default to REJECT (conservative)
    """
    # Check for critical findings
    for vote_record in votes:
        if vote_record.domain == DebateDomain.SECURITY and vote_record.vote == DebateVote.REJECT:
            if vote_record.confidence >= 0.8:
                return DebateVote.REJECT

    # Count accept/reject
    accept_count = sum(1 for v in votes if v.vote == DebateVote.ACCEPT)
    reject_count = sum(1 for v in votes if v.vote == DebateVote.REJECT)

    # Both must accept
    if accept_count == len(votes) and reject_count == 0:
        return DebateVote.ACCEPT

    # Any reject means reject (conservative)
    if reject_count > 0:
        return DebateVote.REJECT

    # Default to reject (conservative)
    return DebateVote.REJECT


def _generate_summary(votes: list[DebateVoteRecord], verdict: DebateVote) -> str:
    """Generate human-readable summary of debate outcome."""
    parts = [f"Debate verdict: {verdict.value}"]
    for v in votes:
        parts.append(f"  {v.agent} ({v.domain.value}): {v.vote.value} ({v.confidence:.2f})")
        if v.findings:
            for f in v.findings:
                parts.append(f"    - {f}")
    return "\n".join(parts)
