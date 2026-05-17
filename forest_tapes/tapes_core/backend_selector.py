from __future__ import annotations

from typing import Any

from .models import BackendChoice, BackendKind, BoundaryAction, BoundaryDecision, InstabilityEstimate, ScopeAllocation

# Threshold provenance: temperature values are empirical pressure-shaping constants.
# Lower temperature = more deterministic output. Higher temperature = more exploration.
# HEURISTIC: 0.0 (fully deterministic, no generation)
# LOCAL_MODEL low instability: 0.1 (minimal exploration)
# API_MODEL high instability: 0.05 (more deterministic under pressure)
# API_MODEL moderate instability: 0.15 (slight exploration)
TEMPERATURE_HEURISTIC = 0.0
TEMPERATURE_LOCAL_LOW = 0.1
TEMPERATURE_API_HIGH = 0.05
TEMPERATURE_API_MODERATE = 0.15

# Instability thresholds for backend selection
INSTABILITY_LOW = 0.2   # Below this, heuristic is sufficient
INSTABILITY_MEDIUM = 0.6 # Below this, local model is sufficient


def select_backend(
    instability: InstabilityEstimate,
    scope: ScopeAllocation,
    boundary: BoundaryDecision,
    environment: dict[str, Any] | None = None,
) -> BackendChoice:
    """Use the smallest sufficient cognition backend."""
    env = environment or {}
    local_models = _safe_model_list(env.get("local_models"))
    api_models = _safe_model_list(env.get("api_models"))
    high_models = _safe_model_list(env.get("high_capability_api_models"))

    if boundary.action == BoundaryAction.ESCALATE_BACKEND and high_models:
        return BackendChoice(
            kind=BackendKind.HIGH_CAPABILITY_API,
            name=str(high_models[0]),
            temperature=TEMPERATURE_API_HIGH,
            rationale="Escalation allowed only after instability pressure remains high.",
        )
    if instability.score < INSTABILITY_LOW:
        return BackendChoice(
            kind=BackendKind.HEURISTIC,
            name="local_heuristic",
            temperature=TEMPERATURE_HEURISTIC,
            rationale="Task is stable enough for deterministic local handling.",
        )
    if instability.score < INSTABILITY_MEDIUM and local_models:
        return BackendChoice(
            kind=BackendKind.LOCAL_MODEL,
            name=str(local_models[0]),
            temperature=TEMPERATURE_LOCAL_LOW,
            rationale="Local model is sufficient under bounded scope.",
        )
    if api_models:
        return BackendChoice(
            kind=BackendKind.API_MODEL,
            name=str(api_models[0]),
            temperature=TEMPERATURE_API_HIGH if instability.score >= INSTABILITY_MEDIUM else TEMPERATURE_API_MODERATE,
            rationale="API model selected because local cognition may be insufficient.",
        )
    if local_models:
        return BackendChoice(
            kind=BackendKind.LOCAL_MODEL,
            name=str(local_models[0]),
            temperature=TEMPERATURE_HEURISTIC,
            rationale="No API backend available; local model selected under degraded mode.",
            degraded=True,
        )
    return BackendChoice(
        kind=BackendKind.HEURISTIC,
        name="local_heuristic",
        temperature=TEMPERATURE_HEURISTIC,
        rationale="No model backend available; falling back to deterministic constraints.",
        degraded=True,
    )


def _safe_model_list(value: Any) -> list[str]:
    """Safely convert environment value to list of model names."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return []
