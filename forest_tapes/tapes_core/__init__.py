"""TAPES cognition pressure core.

This package exists to force the same model into more stable reasoning behavior
by constraining intent, representation, scope, mutation, and validation.

v8.0 additions:
    - ASTExtractor: call graph and reverse dependency extraction
    - vector_grounding: intent embedding and novelty detection
"""

from .allocator import allocate_cognition
from .ast_extractor import ASTExtractor, SubgraphContext, SymbolInfo
from .debate import assess_risk, run_debate
from .models import (
    AllocationResult,
    DebateResult,
    DebateVote,
    InstabilityEstimate,
    LedgerCheckpoint,
    RiskAssessment,
    RiskTier,
    ScopeAllocation,
    TaskContract,
    UncertaintyTag,
    ValidationSpec,
)
from .pressure_kernel import PressureAction, PressureAxis, RuntimeSignals
from .patch_discipline import ExactPatch, PatchDisciplineError, PatchOperation, PatchResult
from .runtime_observer import RuntimeObserver
from .scope_enforcement import enforce_scope, EnforcedContent
from .uncertainty import parse_uncertainty_tags
from .vector_grounding import NoveltyResult, detect_novelty, ground_intent, cosine_similarity
from .why_ledger import LedgerReadResult, LedgerRecord

__all__ = [
    "ASTExtractor",
    "AllocationResult",
    "DebateResult",
    "DebateVote",
    "EnforcedContent",
    "ExactPatch",
    "InstabilityEstimate",
    "LedgerCheckpoint",
    "LedgerReadResult",
    "LedgerRecord",
    "NoveltyResult",
    "PatchDisciplineError",
    "PatchOperation",
    "PatchResult",
    "PressureAction",
    "PressureAxis",
    "RiskAssessment",
    "RiskTier",
    "RuntimeObserver",
    "RuntimeSignals",
    "ScopeAllocation",
    "SubgraphContext",
    "SymbolInfo",
    "TaskContract",
    "UncertaintyTag",
    "ValidationSpec",
    "allocate_cognition",
    "assess_risk",
    "cosine_similarity",
    "detect_novelty",
    "enforce_scope",
    "ground_intent",
    "parse_uncertainty_tags",
    "run_debate",
]
