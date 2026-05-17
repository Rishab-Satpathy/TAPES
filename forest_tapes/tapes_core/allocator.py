from __future__ import annotations

from typing import Any

from .backend_selector import select_backend
from .boundary_widener import decide_boundary
from .debate import assess_risk, create_alpha_agent, create_omega_agent, run_debate
from .instability_estimator import estimate_instability
from .models import AllocationResult, DebateResult, DebateVote, RiskAssessment, ValidationLevel, ValidationSpec
from .pressure_kernel import RuntimeSignals, PressurizedAllocation, pressurize_allocation
from .representation_router import representation_prompt_rule, route_representation_with_trace
from .scope_allocator import allocate_scope
from .task_contract import contract_to_prompt_anchor, parse_task_contract
from .uncertainty import parse_uncertainty_tags, uncertainty_to_risk_factors
from .validation_intensity import select_validation


def allocate_cognition(
    task: str | dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
    prior_failure_count: int = 0,
    runtime_signals: RuntimeSignals | None = None,
    debate_findings: dict[str, Any] | None = None,
) -> AllocationResult:
    """Run the TAPES cognition-pressure allocation pipeline.

    debate_findings is a dict with keys:
        alpha_findings: tuple[str, ...]
        alpha_votes: tuple[DebateVote, ...]
        alpha_confidences: tuple[float, ...]
        omega_findings: tuple[str, ...]
        omega_votes: tuple[DebateVote, ...]
        omega_confidences: tuple[float, ...]
        proposal: str

    In production, these come from LLM calls. In testing, pass directly.
    """
    contract = parse_task_contract(task)
    instability = estimate_instability(contract, prior_failure_count=prior_failure_count)

    # Risk assessment
    risk = assess_risk(contract, instability.score)

    # Run debate if findings provided
    debate: DebateResult | None = None
    if debate_findings is not None:
        debate = run_debate(
            contract=contract,
            proposal=debate_findings.get("proposal", contract.raw_intent),
            risk=risk,
            alpha_findings=debate_findings.get("alpha_findings", ()),
            alpha_votes=debate_findings.get("alpha_votes", ()),
            alpha_confidences=debate_findings.get("alpha_confidences", ()),
            omega_findings=debate_findings.get("omega_findings", ()),
            omega_votes=debate_findings.get("omega_votes", ()),
            omega_confidences=debate_findings.get("omega_confidences", ()),
        )

    # Route with explainability trace
    routed = route_representation_with_trace(contract, instability)
    representation = routed.representation

    # Compute pre-pressure allocation
    pre_scope = allocate_scope(contract, instability, representation)
    pre_boundary = decide_boundary(contract, instability, representation, pre_scope)
    pre_validation = select_validation(contract, instability, pre_scope)

    # Apply pressure kernel
    pressure = pressurize_allocation(contract, instability, representation, pre_scope, pre_boundary, pre_validation, runtime_signals)

    # Select backend using post-pressure state
    backend = select_backend(instability, pressure.scope, pressure.boundary, environment=environment)

    # Build rationale
    rationale_parts = [
        "Task contract created as cognition anchor.",
        f"Representation rule: {representation_prompt_rule(representation)}",
        f"Routing confidence: {routed.confidence:.2f}",
        f"Routing reason: {routed.reason}",
        f"Risk tier: {risk.tier.value} (score: {risk.score:.2f})",
        f"Debate rounds: {risk.debate_rounds}",
        f"Pressure decision: {pressure.decision.action.value} ({pressure.decision.rationale})",
        f"Boundary decision: {pressure.boundary.rationale}",
        f"Backend decision: {backend.rationale}",
        f"Prompt anchor:\n{contract_to_prompt_anchor(contract)}",
    ]

    if debate is not None:
        rationale_parts.insert(5, f"Debate verdict: {debate.verdict.value}")
        rationale_parts.insert(6, f"Debate summary:\n{debate.summary}")

        # If debate rejected, force higher validation
        if debate.verdict == DebateVote.REJECT:
            from dataclasses import replace
            pressure = PressurizedAllocation(
                scope=pressure.scope,
                boundary=pressure.boundary,
                validation=replace(
                    pressure.validation,
                    level=ValidationLevel.ADVERSARIAL_CHECK,
                    retry_budget=max(pressure.validation.retry_budget, 3),
                ),
                decision=pressure.decision,
                reading=pressure.reading,
            )

    return AllocationResult(
        contract=contract,
        instability=instability,
        representation=representation,
        scope=pressure.scope,
        boundary=pressure.boundary,
        backend=backend,
        validation=pressure.validation,
        rationale=tuple(rationale_parts),
    )
