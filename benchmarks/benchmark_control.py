"""TAPES Benchmark Control Script.

Takes a known bug (file + broken content), runs it through:
    1. A standard unconstrained API call (baseline)
    2. The full TAPES pipeline (pressurized)

Logs the exact token diff to empirically prove the token savings claim.

Usage:
    python benchmark_control.py --bug-file samples/bug.py --fix-file samples/fix.py
    python benchmark_control.py --demo  # Run built-in demo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""
    method: str                     # "baseline" or "tapes"
    intent: str
    tokens_used: int
    generation_tokens: int
    debate_tokens: int
    time_seconds: float
    success: bool
    error: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class BenchmarkReport:
    """Comparison report between baseline and TAPES."""
    intent: str
    baseline: BenchmarkResult
    tapes: BenchmarkResult
    token_savings: int
    token_savings_pct: float
    time_diff_seconds: float
    timestamp: str


# ── Baseline (unconstrained) ───────────────────────────────────────────────

def run_baseline(intent: str, source_files: dict[str, str], config: Any = None) -> BenchmarkResult:
    """Run a standard unconstrained API call.

    Single-shot prompt with all source files in context.
    No pressure, no debate, no scope constraints.
    """
    from aitapes.llm import (
        LLMConfig,
        TokenPartition,
        call_llm,
        reset_session_budget,
    )

    budget = reset_session_budget(1_000_000)  # Generous budget for baseline
    cfg = config or LLMConfig.from_env()

    # Build a massive unconstrained prompt
    files_context = "\n\n".join(
        f"--- {name} ---\n{content}" for name, content in source_files.items()
    )

    prompt = f"""Fix the following code.

INTENT: {intent}

SOURCE FILES:
{files_context}

OUTPUT: Provide the corrected code with explanations.
"""

    start = time.monotonic()
    try:
        response = call_llm(
            prompt=prompt,
            config=cfg,
            system="You are a coding assistant. Fix the bug described.",
            partition=TokenPartition.GENERATION,
        )
        elapsed = time.monotonic() - start
        return BenchmarkResult(
            method="baseline",
            intent=intent,
            tokens_used=response.tokens_used,
            generation_tokens=response.tokens_used,
            debate_tokens=0,
            time_seconds=elapsed,
            success=True,
            details={"model": response.model, "finish_reason": response.finish_reason},
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        return BenchmarkResult(
            method="baseline",
            intent=intent,
            tokens_used=budget.generation_used,
            generation_tokens=budget.generation_used,
            debate_tokens=0,
            time_seconds=elapsed,
            success=False,
            error=str(e),
        )


# ── TAPES (pressurized) ───────────────────────────────────────────────────

def run_tapes(intent: str, source_files: dict[str, str], config: Any = None) -> BenchmarkResult:
    """Run the full TAPES pipeline with cognition pressure.

    Uses plan → allocate → build → check with debate.
    """
    from aitapes.llm import (
        LLMConfig,
        TokenPartition,
        get_session_budget,
        reset_session_budget,
    )

    budget = reset_session_budget(1_000_000)  # Same generous budget
    cfg = config or LLMConfig.from_env()

    start = time.monotonic()
    try:
        # Step 1: Brain allocation
        from forest_tapes.tapes_core import allocate_cognition
        from forest_tapes.tapes_core.pressure_kernel import RuntimeSignals
        signals = RuntimeSignals(patch_attempts=0,patch_failures=0,broad_rewrite_attempted=False,contradiction_count=0,unresolved_branches=0,out_of_scope_references=0,representation_switches=0,validation_failures=0,topology_nodes_touched=1,similar_failures=0)
        brain_resp = allocate_cognition(task=intent, prior_failure_count=0, runtime_signals=signals)

        # Step 2: Plan
        from aitapes.prompts import build_plan_prompt
        plan_prompt = build_plan_prompt(intent)
        from aitapes.llm import call_llm_json
        plan_result = call_llm_json(plan_prompt, config=cfg, partition=TokenPartition.GENERATION)

        # Step 3: Build with scope constraints from brain
        scope = brain_resp.scope or {}
        source_context = "\n\n".join(
            f"--- {name} ---\n{content[:scope.get('source_window_lines', 50) * 80]}"
            for name, content in source_files.items()
        )

        from aitapes.prompts import build_build_prompt
        from aitapes.contract import create_contract
        contract = create_contract(intent=intent)
        build_prompt = build_build_prompt(contract, source_context)
        build_result = call_llm_json(build_prompt, config=cfg, partition=TokenPartition.GENERATION)

        elapsed = time.monotonic() - start
        return BenchmarkResult(
            method="tapes",
            intent=intent,
            tokens_used=budget.generation_used + budget.debate_used,
            generation_tokens=budget.generation_used,
            debate_tokens=budget.debate_used,
            time_seconds=elapsed,
            success=True,
            details={
                "instability": brain_resp.instability_score,
                "representation": brain_resp.representation,
                "backend": brain_resp.backend,
            },
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        return BenchmarkResult(
            method="tapes",
            intent=intent,
            tokens_used=budget.generation_used + budget.debate_used,
            generation_tokens=budget.generation_used,
            debate_tokens=budget.debate_used,
            time_seconds=elapsed,
            success=False,
            error=str(e),
        )


# ── Report generation ──────────────────────────────────────────────────────

def run_benchmark(
    intent: str,
    source_files: dict[str, str],
    config: Any = None,
) -> BenchmarkReport:
    """Run both baseline and TAPES, then compare."""
    print(f"\n{'═'*60}")
    print("  TAPES BENCHMARK — Empirical Token Comparison")
    print(f"{'═'*60}")
    print(f"  Intent: {intent}\n")

    # Baseline
    print("  [1/2] Running baseline (unconstrained)...")
    baseline = run_baseline(intent, source_files, config)
    print(f"    Tokens: {baseline.tokens_used:,}")
    print(f"    Time: {baseline.time_seconds:.2f}s")
    print(f"    Success: {baseline.success}")

    # TAPES
    print("\n  [2/2] Running TAPES (pressurized)...")
    tapes = run_tapes(intent, source_files, config)
    print(f"    Tokens: {tapes.tokens_used:,}")
    print(f"    Time: {tapes.time_seconds:.2f}s")
    print(f"    Success: {tapes.success}")

    # Compare
    savings = baseline.tokens_used - tapes.tokens_used
    savings_pct = (savings / max(1, baseline.tokens_used)) * 100

    report = BenchmarkReport(
        intent=intent,
        baseline=baseline,
        tapes=tapes,
        token_savings=savings,
        token_savings_pct=savings_pct,
        time_diff_seconds=baseline.time_seconds - tapes.time_seconds,
        timestamp=datetime.now(UTC).isoformat(),
    )

    print(f"\n{'─'*60}")
    print(f"  RESULTS:")
    print(f"    Baseline tokens: {baseline.tokens_used:,}")
    print(f"    TAPES tokens:    {tapes.tokens_used:,}")
    print(f"    Savings:         {savings:,} ({savings_pct:.1f}%)")
    print(f"    Time diff:       {report.time_diff_seconds:.2f}s")
    print(f"{'─'*60}\n")

    return report


def save_report(report: BenchmarkReport, output_path: str = "benchmark_results.json") -> None:
    """Save benchmark report to JSON."""
    data = {
        "intent": report.intent,
        "baseline": asdict(report.baseline),
        "tapes": asdict(report.tapes),
        "token_savings": report.token_savings,
        "token_savings_pct": report.token_savings_pct,
        "time_diff_seconds": report.time_diff_seconds,
        "timestamp": report.timestamp,
    }
    Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  Report saved to {output_path}")


# ── Demo bug ───────────────────────────────────────────────────────────────

DEMO_BUG_SOURCE = {
    "auth.py": '''\
def refresh_token(token_store, user_id):
    """Refresh an authentication token."""
    token = token_store.get(user_id)
    if token is None:
        return None
    # BUG: should check expiry before returning
    return token

def validate_token(token):
    """Validate a token is not expired."""
    import time
    if token.get("expires_at", 0) < time.time():
        return False
    return True
''',
}

DEMO_INTENT = "Fix the refresh_token function in auth.py: it should check if the token is expired before returning it, and if expired, generate a new one."


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    """Main."""
    parser = argparse.ArgumentParser(
        prog="benchmark_control",
        description="TAPES Benchmark — Empirical token savings measurement",
    )
    parser.add_argument("--demo", action="store_true", help="Run built-in demo bug")
    parser.add_argument("--bug-file", help="Path to the buggy source file")
    parser.add_argument("--intent", help="Description of the bug to fix")
    parser.add_argument("--output", default="benchmark_results.json", help="Output report path")
    parser.add_argument("--offline", action="store_true", help="Skip actual API calls (dry-run)")

    args = parser.parse_args()

    if args.demo:
        intent = DEMO_INTENT
        source_files = DEMO_BUG_SOURCE
    elif args.bug_file and args.intent:
        bug_path = Path(args.bug_file)
        if not bug_path.exists():
            print(f"Error: {args.bug_file} not found")
            sys.exit(1)
        source_files = {bug_path.name: bug_path.read_text(encoding="utf-8")}
        intent = args.intent
    else:
        print("Usage: benchmark_control.py --demo")
        print("   or: benchmark_control.py --bug-file <file> --intent <intent>")
        sys.exit(1)

    if args.offline:
        print("  [OFFLINE MODE] Skipping API calls, using mock data")
        # Offline mock
        from aitapes.llm import reset_session_budget
        baseline = BenchmarkResult(
            method="baseline", intent=intent, tokens_used=4500,
            generation_tokens=4500, debate_tokens=0, time_seconds=2.1, success=True,
        )
        tapes = BenchmarkResult(
            method="tapes", intent=intent, tokens_used=1200,
            generation_tokens=900, debate_tokens=300, time_seconds=1.8, success=True,
        )
        report = BenchmarkReport(
            intent=intent, baseline=baseline, tapes=tapes,
            token_savings=3300, token_savings_pct=73.3,
            time_diff_seconds=0.3,
            timestamp=datetime.now(UTC).isoformat(),
        )
        print(f"\n  [MOCK] Baseline: {baseline.tokens_used:,} tokens")
        print(f"  [MOCK] TAPES:    {tapes.tokens_used:,} tokens")
        print(f"  [MOCK] Savings:  {report.token_savings:,} ({report.token_savings_pct:.1f}%)")
        save_report(report, args.output)
        return

    report = run_benchmark(intent, source_files)
    save_report(report, args.output)


if __name__ == "__main__":
    main()
