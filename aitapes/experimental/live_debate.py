"""Live LLM Debate for TAPES v8.0.

Wires debate.py to trigger two parallel API calls via ThreadPoolExecutor.
Alpha receives AST subgraph context; Omega receives Data Flow context.
Both calls draw from the 30% debate token partition.

Asymmetric Seepage Protocol:
    - MAX_ROUNDS = 3 loop in run_debate
    - Early-exit: break on Round 1 ACCEPT consensus (saves tokens)
    - Tie = one ACCEPT and one REJECT
    - On tie after round 2, merge Alpha+Omega contexts → Judge for consensus
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

try:
    from forest_tapes.tapes_core.models import (
        DebateAgent, DebateDomain, DebateResult, DebateVote, DebateVoteRecord, RiskAssessment, RiskTier,
    )
except ImportError:
    DebateAgent = DebateDomain = DebateResult = DebateVote = DebateVoteRecord = RiskAssessment = RiskTier = None

logger = logging.getLogger(__name__)

MAX_ROUNDS = 3


# ── Debate prompts ─────────────────────────────────────────────────────────

ALPHA_SYSTEM = """You are Alpha, the architecture debate agent.
Your domain: architectural soundness, logic errors, correctness.
You receive the AST subgraph context for the target symbol.

Analyze the proposal and vote:
- ACCEPT if architecturally sound
- REJECT if you find logic errors, incorrect assumptions, or architectural flaws

You MUST enforce Red-Green-Refactor (Adversarial TDD). 
Alongside your consensus, provide a 'RequiredTests' JSON array detailing 
specific test cases that must fail before implementation is allowed.

You MUST also output an 'ExecutionQueue', which is a JSON array of sequential steps 
instead of a monolithic patch plan. 
Format structure: [{"step": 1, "target": "models.py", "depends_on": []}, {"step": 2, "target": "api.py", "depends_on": ["models.py"]}]

Respond with JSON:
{
    "vote": "accept" or "reject",
    "confidence": 0.0-1.0,
    "findings": ["finding 1", "finding 2"],
    "rationale": "explanation",
    "RequiredTests": ["def test_foo(): ..."],
    "ExecutionQueue": [{"step": 1, "target": "file.py", "depends_on": []}]
}"""

OMEGA_SYSTEM = """You are Omega, the security debate agent.
Your domain: security vulnerabilities, race conditions, edge cases.
You receive the Data Flow context derived from the target symbol.

Analyze the proposal and vote:
- ACCEPT if secure and robust
- REJECT if you find security issues, race conditions, or edge cases

You MUST enforce Red-Green-Refactor (Adversarial TDD). 
Alongside your consensus, provide a 'RequiredTests' JSON array detailing 
specific test cases that must fail before implementation is allowed.

You MUST also output an 'ExecutionQueue', which is a JSON array of sequential steps 
instead of a monolithic patch plan. 
Format structure: [{"step": 1, "target": "models.py", "depends_on": []}, {"step": 2, "target": "api.py", "depends_on": ["models.py"]}]

Respond with JSON:
{
    "vote": "accept" or "reject",
    "confidence": 0.0-1.0,
    "findings": ["finding 1", "finding 2"],
    "rationale": "explanation",
    "RequiredTests": ["def test_edge_case(): ..."],
    "ExecutionQueue": [{"step": 1, "target": "file.py", "depends_on": []}]
}"""

JUDGE_SYSTEM = """You are the Judge agent, resolving a debate tie.
Alpha (architecture) and Omega (security) disagreed.
You receive BOTH their contexts and findings.

Synthesize a consensus. Your vote is FINAL.

Respond with JSON:
{
    "vote": "accept" or "reject",
    "confidence": 0.0-1.0,
    "findings": ["synthesized finding 1"],
    "rationale": "why this resolution"
}"""


# ── Live debate call ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class DebateCallResult:
    """Result from a single LLM debate call."""
    agent: str
    vote: DebateVote
    confidence: float
    findings: tuple[str, ...]
    rationale: str
    raw_response: dict[str, Any] | None = None


def _call_debate_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    config: Any = None,
) -> DebateCallResult:
    """Call a single debate agent via LLM API.

    Uses the DEBATE partition (30% of token budget).
    """
    from aitapes.llm import call_llm_json, TokenPartition

    try:
        raw = call_llm_json(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            system=system_prompt,
            config=config,
            partition=TokenPartition.DEBATE,
        )
        vote_str = raw.get("vote", "reject").lower()
        vote = DebateVote.ACCEPT if vote_str == "accept" else DebateVote.REJECT
        return DebateCallResult(
            agent=agent_name,
            vote=vote,
            confidence=float(raw.get("confidence", 0.5)),
            findings=tuple(raw.get("findings", [])),
            rationale=raw.get("rationale", ""),
            raw_response=raw,
        )
    except Exception as e:
        logger.warning("Debate agent %s failed: %s", agent_name, e)
        return DebateCallResult(
            agent=agent_name,
            vote=DebateVote.REJECT,
            confidence=0.3,
            findings=(f"Agent error: {e}",),
            rationale=f"Agent {agent_name} failed with error; defaulting to REJECT.",
        )


def run_live_debate(
    contract: TaskContract,
    proposal: str,
    risk: RiskAssessment,
    ast_subgraph_context: str = "",
    dataflow_context: str = "",
    is_greenfield: bool = False,
    config: Any = None,
) -> DebateResult:
    """Run live LLM debate with Asymmetric Seepage Protocol.

    1. Parallel Alpha + Omega calls via ThreadPoolExecutor
    2. If tie after round, escalate with merged context
    3. MAX_ROUNDS = 3 loop
    4. On tie after round 2, Judge agent synthesizes consensus
    """
    all_votes: list[DebateVoteRecord] = []
    round_num = 0

    alpha_prompt = (
        f"PROPOSAL:\n{proposal}\n\n"
        f"INTENT:\n{contract.intent}\n\n"
        f"AST SUBGRAPH CONTEXT:\n{ast_subgraph_context or 'No AST context available'}\n"
    )
    omega_prompt = (
        f"PROPOSAL:\n{proposal}\n\n"
        f"INTENT:\n{contract.intent}\n\n"
        f"DATA FLOW CONTEXT:\n{dataflow_context or 'No data flow context available'}\n"
    )

    if is_greenfield:
        sip_injection = "\n[SIP ACTIVE] Greenfield topology detected. Ensure strict specification compliance before proceeding.\n"
        alpha_prompt += sip_injection
        omega_prompt += sip_injection

    alpha_result: DebateCallResult | None = None
    omega_result: DebateCallResult | None = None

    for round_num in range(1, MAX_ROUNDS + 1):
        logger.info("Debate round %d/%d", round_num, MAX_ROUNDS)
        print(f"    Debate round {round_num}/{MAX_ROUNDS}...")

        if round_num <= 2:
            # Rounds 1-2: Parallel Alpha + Omega calls
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(
                        _call_debate_agent, "Alpha", ALPHA_SYSTEM, alpha_prompt, config
                    ): "Alpha",
                    executor.submit(
                        _call_debate_agent, "Omega", OMEGA_SYSTEM, omega_prompt, config
                    ): "Omega",
                }
                for future in as_completed(futures):
                    agent_name = futures[future]
                    result = future.result()
                    if agent_name == "Alpha":
                        alpha_result = result
                    else:
                        omega_result = result

            # Record votes
            all_votes.append(DebateVoteRecord(
                agent="Alpha",
                domain=DebateDomain.ARCHITECTURE,
                vote=alpha_result.vote,
                confidence=alpha_result.confidence,
                findings=alpha_result.findings,
                rationale=alpha_result.rationale,
            ))
            all_votes.append(DebateVoteRecord(
                agent="Omega",
                domain=DebateDomain.SECURITY,
                vote=omega_result.vote,
                confidence=omega_result.confidence,
                findings=omega_result.findings,
                rationale=omega_result.rationale,
            ))

            # Check for consensus
            if alpha_result.vote == omega_result.vote:
                verdict = alpha_result.vote
                print(f"    Consensus: {verdict.value}")

                execution_queue = []
                if alpha_result and alpha_result.raw_response:
                    execution_queue = alpha_result.raw_response.get("ExecutionQueue", [])
                
                # Feature 8: Pre-Execution Graph Check
                import graphlib
                if execution_queue:
                    sorter = graphlib.TopologicalSorter()
                    for step in execution_queue:
                        node = step.get("target")
                        deps = step.get("depends_on", [])
                        if node:
                            sorter.add(node, *deps)
                    try:
                        list(sorter.static_order())
                    except graphlib.CycleError as e:
                        print(f"    [GRAPH REJECT] Circular Dependency Detected in ExecutionQueue: {e}")
                        # Force a reject to re-order
                        verdict = DebateVote.REJECT
                        alpha_prompt += f"\n\n[GRAPH REJECT] Circular Dependency in your ExecutionQueue: {e}. Re-order dependencies.\n"
                        omega_prompt += f"\n\n[GRAPH REJECT] Circular Dependency in your ExecutionQueue: {e}. Re-order dependencies.\n"
                        continue

                # Early-exit: if Round 1 yields ACCEPT, break immediately.
                # No need to compute AST/Data-Flow context mutations for
                # a Round 2 that is no longer needed.
                required_tests = set()
                if alpha_result and alpha_result.raw_response:
                    required_tests.update(alpha_result.raw_response.get("RequiredTests", []))
                if omega_result and omega_result.raw_response:
                    required_tests.update(omega_result.raw_response.get("RequiredTests", []))
                return DebateResult(
                    votes=tuple(all_votes),
                    verdict=verdict,
                    rounds=round_num,
                    risk_tier=risk.tier,
                    summary=_build_summary(all_votes, verdict, round_num),
                    required_tests=tuple(required_tests),
                    execution_queue=tuple(execution_queue),
                )

            # Tie: one ACCEPT, one REJECT
            print(f"    Tie: Alpha={alpha_result.vote.value}, Omega={omega_result.vote.value}")

            if round_num == 2:
                # After round 2 tie, proceed to Judge
                continue

            # Seepage: feed each agent the other's findings for round 2
            alpha_prompt += f"\n\nOmega's findings from round {round_num}:\n" + "\n".join(f"- {f}" for f in omega_result.findings)
            omega_prompt += f"\n\nAlpha's findings from round {round_num}:\n" + "\n".join(f"- {f}" for f in alpha_result.findings)

        else:
            # Round 3: Judge agent with merged context
            judge_prompt = (
                f"PROPOSAL:\n{proposal}\n\n"
                f"INTENT:\n{contract.intent}\n\n"
                f"ALPHA CONTEXT (Architecture):\n{ast_subgraph_context}\n\n"
                f"OMEGA CONTEXT (Security):\n{dataflow_context}\n\n"
                f"ALPHA FINDINGS:\n" + "\n".join(f"- {f}" for f in (alpha_result.findings if alpha_result else ())) + "\n\n"
                f"OMEGA FINDINGS:\n" + "\n".join(f"- {f}" for f in (omega_result.findings if omega_result else ())) + "\n"
            )

            judge_result = _call_debate_agent("Judge", JUDGE_SYSTEM, judge_prompt, config)

            all_votes.append(DebateVoteRecord(
                agent="Judge",
                domain=DebateDomain.CORRECTNESS,
                vote=judge_result.vote,
                confidence=judge_result.confidence,
                findings=judge_result.findings,
                rationale=judge_result.rationale,
            ))

            verdict = judge_result.vote
            print(f"    Judge verdict: {verdict.value}")
            required_tests = set()
            if alpha_result and alpha_result.raw_response:
                required_tests.update(alpha_result.raw_response.get("RequiredTests", []))
            if omega_result and omega_result.raw_response:
                required_tests.update(omega_result.raw_response.get("RequiredTests", []))
            execution_queue = []
            if judge_result and judge_result.raw_response:
                execution_queue = judge_result.raw_response.get("ExecutionQueue", [])
            elif alpha_result and alpha_result.raw_response:
                execution_queue = alpha_result.raw_response.get("ExecutionQueue", [])
                
            return DebateResult(
                votes=tuple(all_votes),
                verdict=verdict,
                rounds=round_num,
                risk_tier=risk.tier,
                summary=_build_summary(all_votes, verdict, round_num),
                required_tests=tuple(required_tests),
                execution_queue=tuple(execution_queue),
            )

    # Should not reach here (all loop paths return), but default to REJECT
    # Use MAX_ROUNDS since loop always returns before this point
    required_tests = set()
    if alpha_result and alpha_result.raw_response:
        required_tests.update(alpha_result.raw_response.get("RequiredTests", []))
    if omega_result and omega_result.raw_response:
        required_tests.update(omega_result.raw_response.get("RequiredTests", []))
        
    execution_queue = []
    if alpha_result and alpha_result.raw_response:
        execution_queue = alpha_result.raw_response.get("ExecutionQueue", [])
        
    return DebateResult(
        votes=tuple(all_votes),
        verdict=DebateVote.REJECT,
        rounds=MAX_ROUNDS,  # loop exhausts all rounds without consensus
        risk_tier=risk.tier,
        summary=_build_summary(all_votes, DebateVote.REJECT, MAX_ROUNDS),
        required_tests=tuple(required_tests),
        execution_queue=tuple(execution_queue),
    )


def _build_summary(votes: list[DebateVoteRecord], verdict: DebateVote, rounds: int) -> str:
    """Generate human-readable debate summary."""
    parts = [f"Live debate verdict: {verdict.value} (after {rounds} round{'s' if rounds > 1 else ''})"]
    for v in votes:
        parts.append(f"  {v.agent} ({v.domain.value}): {v.vote.value} ({v.confidence:.2f})")
        if v.findings:
            for f in v.findings:
                parts.append(f"    - {f}")
    return "\n".join(parts)
