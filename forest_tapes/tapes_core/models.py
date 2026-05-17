from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TaskType(StrEnum):
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    EXPLAIN = "explain"
    PATCH = "patch"
    UNKNOWN = "unknown"


class MutationType(StrEnum):
    NONE = "none"
    EXACT_PATCH = "exact_patch"
    LOCAL_EDIT = "local_edit"
    REFACTOR = "refactor"
    BROAD_REWRITE = "broad_rewrite"


class Stakes(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Representation(StrEnum):
    DIRECT = "direct"
    STRUCTURED_CONTRACT = "structured_contract"
    AST_SOURCE_WINDOW = "ast_source_window"
    TOPOLOGY_GRAPH = "topology_graph"
    EXECUTION_TRACE = "execution_trace"
    TYPED_INTERFACE_GRAPH = "typed_interface_graph"
    COMPONENT_HIERARCHY = "component_hierarchy"
    DATA_FLOW_GRAPH = "data_flow_graph"
    SCAFFOLDED_REASONING = "scaffolded_reasoning"


class BoundaryAction(StrEnum):
    NONE = "none"
    CLARIFY_INTENT = "clarify_intent"
    FETCH_EVIDENCE = "fetch_evidence"
    WIDEN_TOPOLOGY = "widen_topology"
    INCREASE_VALIDATION = "increase_validation"
    ESCALATE_BACKEND = "escalate_backend"


class BackendKind(StrEnum):
    HEURISTIC = "heuristic"
    LOCAL_MODEL = "local_model"
    API_MODEL = "api_model"
    HIGH_CAPABILITY_API = "high_capability_api"


class ValidationLevel(StrEnum):
    NONE = "none"
    SPOT_CHECK = "spot_check"
    FULL_VERIFY = "full_verify"
    ADVERSARIAL_CHECK = "adversarial_check"


class DebateVote(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"


class DebateDomain(StrEnum):
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    CORRECTNESS = "correctness"


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TaskContract:
    raw_intent: str
    target_artifact: str | None
    task_type: TaskType
    allowed_mutation: MutationType
    explicit_constraints: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    forbidden_assumptions: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    stakes: Stakes = Stakes.LOW


@dataclass(frozen=True)
class InstabilityEstimate:
    score: float
    sources: tuple[str, ...] = ()
    hallucination_pressure: float = 0.0
    reasoning_spread_risk: float = 0.0
    missing_information_risk: float = 0.0
    mutation_instability: float = 0.0


@dataclass(frozen=True)
class ScopeAllocation:
    source_window_lines: int
    topology_radius: int
    memory_items: int
    allowed_assumptions: int
    max_subtasks: int
    mutation_surface: MutationType
    token_budget: int


@dataclass(frozen=True)
class BoundaryDecision:
    action: BoundaryAction
    rationale: str


@dataclass(frozen=True)
class BackendChoice:
    kind: BackendKind
    name: str
    temperature: float
    rationale: str
    degraded: bool = False


@dataclass(frozen=True)
class ValidationSpec:
    level: ValidationLevel
    checks: tuple[str, ...] = ()
    retry_budget: int = 0


@dataclass(frozen=True)
class AllocationResult:
    contract: TaskContract
    instability: InstabilityEstimate
    representation: Representation
    scope: ScopeAllocation
    boundary: BoundaryDecision
    backend: BackendChoice
    validation: ValidationSpec
    rationale: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DebateAgent:
    name: str
    domain: DebateDomain
    temperature: float
    rationale: str


@dataclass(frozen=True)
class DebateVoteRecord:
    agent: str
    domain: DebateDomain
    vote: DebateVote
    confidence: float
    findings: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class DebateResult:
    votes: tuple[DebateVoteRecord, ...]
    verdict: DebateVote
    rounds: int
    risk_tier: RiskTier
    summary: str
    required_tests: tuple[str, ...] = ()
    execution_queue: tuple[dict, ...] = ()


@dataclass(frozen=True)
class RiskAssessment:
    tier: RiskTier
    score: float
    factors: tuple[str, ...] = ()
    debate_rounds: int = 0
    requires_formal_verification: bool = False


@dataclass(frozen=True)
class UncertaintyTag:
    claim: str
    confidence: float
    evidence: str
    alternative: str = ""


@dataclass(frozen=True)
class LedgerCheckpoint:
    index: int
    hash: str
    record_count: int
    timestamp: str
