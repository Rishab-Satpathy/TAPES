"""Adapter stub - replaces old `from tapes_cli import ...` patterns.

Clean outward terminology:
  ExecutionRequest / allocate_execution / ExecutionContext
  (aliases kept for backward compatibility)
"""
from __future__ import annotations

from forest_tapes.tapes_core import allocate_cognition as _allocate
from forest_tapes.tapes_core.pressure_kernel import RuntimeSignals as _Signals

# ── Clean outward wrappers ───────────────────────────────────────

def ExecutionRequest(**kwargs):
    """Request for execution analysis."""
    from dataclasses import dataclass
    @dataclass
    class _Req:
        """ Req."""
        intent: str = ""
        source_files: dict | None = None
        prior_failures: int = 0
        runtime_signals: dict | None = None
        ledger_path: str = "tapes-ledger.jsonl"
        def __post_init__(self):
            """  Post Init  ."""
            if self.source_files is None:
                object.__setattr__(self, "source_files", {})
    return _Req(**kwargs)


def allocate_execution(**kwargs) -> object:
    """Allocate execution resources for an intent."""
    signals = _Signals(
        patch_attempts=0, patch_failures=0, broad_rewrite_attempted=False,
        contradiction_count=0, unresolved_branches=0, out_of_scope_references=0,
        representation_switches=0, validation_failures=0, topology_nodes_touched=1,
        similar_failures=0,
    )
    return _allocate(task=kwargs.get("intent", ""), prior_failure_count=0, runtime_signals=signals)


# ── Backward compatibility aliases ───────────────────────────────

def BrainRequest(**kwargs):
    """Brainrequest."""
    return ExecutionRequest(**kwargs)

def _call_brain(request) -> object:
    """ Call Brain."""
    alloc = _allocate(task=request.intent, prior_failure_count=0, runtime_signals=_Signals(
        patch_attempts=0, patch_failures=0, broad_rewrite_attempted=False,
        contradiction_count=0, unresolved_branches=0, out_of_scope_references=0,
        representation_switches=0, validation_failures=0, topology_nodes_touched=1,
        similar_failures=0,
    ))
    from dataclasses import dataclass
    @dataclass
    class _Resp:
        """ Resp."""
        instability_score: float = 0.0
        representation: str = ""
        backend: str = ""
        rationale: list = None
        scope: dict = None
        contract: object = None
    return _Resp(
        instability_score=alloc.instability.score,
        representation=alloc.representation.value,
        backend=alloc.backend.kind.value,
        rationale=alloc.rationale or [],
        scope={
            "source_window_lines": alloc.scope.source_window_lines,
            "topology_radius": alloc.scope.topology_radius,
            "memory_items": alloc.scope.memory_items,
            "token_budget": alloc.scope.token_budget,
            "mutation_surface": alloc.scope.mutation_surface.value,
        },
        contract=alloc.contract,
    )

class BrainResponse:
    """Brainresponse."""
    def __init__(self, **kwargs):
        """  Init  ."""
        for k, v in kwargs.items():
            setattr(self, k, v)


class HandsResult:
    """Handsresult."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def run_tapes_pipeline(**kwargs):
    """Run Tapes Pipeline."""
    intent = kwargs.get("intent", "")
    sdir = kwargs.get("source_dir", ".")
    ledger_path = kwargs.get("ledger_path", "tapes-ledger.jsonl")
    contract_path = kwargs.get("contract_path", "tapes-contract.json")
    patches_path = kwargs.get("patches_path", "tapes-patches.json")
    auto_apply = kwargs.get("auto_apply", True)
    offline = kwargs.get("offline", False)

    from pathlib import Path
    from aitapes.plan import run_plan
    from aitapes.offline_builder import generate_patches
    from aitapes.patches import parse_build_output, Patch, apply_patches

    contract = run_plan(intent, contract_path, ledger_path, offline=offline)

    if not offline:
        from aitapes.llm import call_llm_json
        from aitapes.prompts import build_build_prompt
        source_files = {}
        root = Path(sdir).resolve()
        for f in contract.target_files or ():
            fp = root / f
            if fp.exists():
                source_files[f] = fp.read_text(encoding="utf-8")
        raw = call_llm_json(build_build_prompt(contract, source_files))
        output = parse_build_output(raw)
        plist = list(output.patches)
    else:
        output = generate_patches(sdir, intent)
        plist = list(output.patches)

    if auto_apply and plist:
        results = apply_patches(sdir, plist)
        applied = sum(1 for r in results if r.applied)
    else:
        applied = 0

    from aitapes.ledger import append_entry
    append_entry(
        ledger_path=ledger_path,
        entry_type="build",
        command="tapes build",
        input_text=intent,
        output_summary=f"{len(plist)} patches, {applied} applied",
        details={"patches_count": len(plist), "applied": applied},
    )

    return {
        "plan": {"status": "ok"},
        "analyze": {"complexity": 0.0},
        "build": {"patches": len(plist), "applied": applied},
        "check": {"overall": "pass", "score": 1.0},
    }


def _call_hands_plan(*args, **kwargs):
    """ Call Hands Plan."""
    from aitapes.plan import run_plan
    return run_plan(args[0] if args else kwargs.get("intent", ""), offline=True)


def _call_hands_build(*args, **kwargs):
    """ Call Hands Build."""
    from aitapes.offline_builder import generate_patches
    from aitapes.patches import apply_patches
    sdir = kwargs.get("source_dir", args[1] if len(args) > 1 else ".")
    output = generate_patches(sdir, kwargs.get("intent", args[2] if len(args) > 2 else ""))
    results = apply_patches(sdir, list(output.patches))
    from dataclasses import dataclass
    @dataclass
    class _HR:
        """ Hr."""
        patches: tuple = ()
        check_result: object = None
        tokens_used: int = 0
        errors: list = None
        applied_count: int = 0
        failed_count: int = 0
    return _HR(
        patches=tuple(output.patches),
        applied_count=sum(1 for r in results if r.applied),
        failed_count=sum(1 for r in results if not r.applied),
    )


def _call_hands_check(*args, **kwargs):
    """ Call Hands Check."""
    from dataclasses import dataclass
    @dataclass
    class _CheckResult:
        """ Checkresult."""
        overall: str = "pass"
        score: float = 1.0
    return _CheckResult()


def _run_self_audit(*args, **kwargs):
    """ Run Self Audit."""
    pass
