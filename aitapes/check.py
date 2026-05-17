"""tapes check - Validation

Compares code against contract. Measures compliance,
hallucination rate, and mutation locality.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .contract import Contract
from .llm import LLMConfig, call_llm_json
from .ledger import append_entry
from .prompts import SYSTEM_CHECK, build_check_prompt


@dataclass(frozen=True)
class CheckResult:
    """Result of tapes check."""
    overall: str  # "pass" or "fail"
    checks: tuple[dict[str, str], ...]
    hallucinations: tuple[dict[str, str], ...]
    mutation_locality: dict[str, Any]
    summary: str
    score: float  # 0.0 to 1.0


def run_check(
    contract_path: str = "tapes-contract.json",
    source_dir: str = ".",
    ledger_path: str = "tapes-ledger.jsonl",
    config: LLMConfig | None = None,
    offline: bool = False,
) -> CheckResult:
    """Run the check command.

    Args:
        contract_path: Path to the contract JSON.
        source_dir: Directory containing source files.
        ledger_path: Where to record the decision.
        config: LLM configuration.
        offline: If True, do local checks only (no LLM).

    Returns:
        The check result.
    """
    print(f"\n{'='*60}")
    print("  TAPES CHECK - Validation")
    print(f"{'='*60}\n")

    # Load contract
    contract = Contract.load(contract_path)
    print(f"  Contract: {contract.intent[:60]}")

    # Read source files
    source_path = Path(source_dir)
    source_files: dict[str, str] = {}

    if contract.target_files:
        for f in contract.target_files:
            full = source_path / f
            if full.exists():
                source_files[f] = full.read_text(encoding="utf-8")
    else:
        for py_file in source_path.rglob("*.py"):
            rel = str(py_file.relative_to(source_path))
            if ".venv" not in rel and "__pycache__" not in rel:
                try:
                    source_files[rel] = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue

    print(f"  Source files: {len(source_files)}")

    if offline:
        print("  [offline mode] Running local checks...")
        result = _local_check(contract, source_files)
    else:
        print("  Calling LLM for validation...")
        prompt = build_check_prompt(contract, source_files)
        raw = call_llm_json(prompt, config=config, system=SYSTEM_CHECK)
        result = _parse_check_result(raw)

    # Print summary
    status = "[OK] PASS" if result.overall == "pass" else "[FAIL] FAIL"
    print(f"\n  {status}")
    print(f"  Score: {result.score:.0%}")
    print(f"  Summary: {result.summary}")

    if result.checks:
        print(f"\n  Checks:")
        for c in result.checks:
            icon = "[OK]" if c.get("status") == "pass" else "[FAIL]"
            print(f"    {icon} {c.get('criterion', 'unknown')}: {c.get('status', 'unknown')}")

    if result.hallucinations:
        print(f"\n  Hallucinations: {len(result.hallucinations)}")
        for h in result.hallucinations:
            print(f"    [FAIL] {h.get('type', '?')}: {h.get('name', '?')} in {h.get('file', '?')}")

    if result.mutation_locality:
        loc = result.mutation_locality
        print(f"\n  Mutation locality: {loc.get('assessment', 'unknown')}")
        print(f"    Files changed: {loc.get('files_changed', [])}")
        print(f"    Lines changed: {loc.get('total_lines_changed', 0)}")

    # Record in ledger
    append_entry(
        ledger_path=ledger_path,
        entry_type="check",
        command="tapes check",
        input_text=contract.intent,
        output_summary=f"{result.overall} (score: {result.score:.0%})",
        details={
            "overall": result.overall,
            "score": result.score,
            "checks_count": len(result.checks),
            "hallucinations_count": len(result.hallucinations),
            "mutation_assessment": result.mutation_locality.get("assessment", "unknown"),
        },
    )

    print()
    return result


def _parse_check_result(raw: dict[str, Any]) -> CheckResult:
    """Parse LLM JSON output into CheckResult."""
    checks = tuple(raw.get("checks", []))
    hallucinations = tuple(raw.get("hallucinations", []))
    mutation = raw.get("mutation_locality", {})

    # Calculate score
    if checks:
        pass_count = sum(1 for c in checks if c.get("status") == "pass")
        score = pass_count / len(checks)
    else:
        score = 0.0

    # Penalize for hallucinations
    if hallucinations:
        score *= max(0.3, 1.0 - len(hallucinations) * 0.2)

    return CheckResult(
        overall=raw.get("overall", "fail"),
        checks=checks,
        hallucinations=hallucinations,
        mutation_locality=mutation,
        summary=raw.get("summary", "No summary"),
        score=min(1.0, max(0.0, score)),
    )


def _local_check(contract: Contract, source_files: dict[str, str]) -> CheckResult:
    """Perform local checks without LLM."""
    checks: list[dict[str, str]] = []
    hallucinations: list[dict[str, str]] = []

    # Check if target files exist
    for f in contract.target_files:
        if f in source_files:
            checks.append({
                "criterion": f"Target file exists: {f}",
                "status": "pass",
                "evidence": f"File {f} found",
                "file": f,
            })
        else:
            checks.append({
                "criterion": f"Target file exists: {f}",
                "status": "fail",
                "evidence": f"File {f} not found",
                "file": f,
            })

    # Check for common hallucinations in source
    for f in contract.target_files:
        if f in source_files:
            content = source_files[f]
            # Check for TODO/FIXME that might indicate incomplete implementation
            if "TODO" in content or "FIXME" in content:
                checks.append({
                    "criterion": f"No TODO/FIXME in {f}",
                    "status": "fail",
                    "evidence": "Found TODO or FIXME comments",
                    "file": f,
                })

    # Calculate mutation locality
    files_changed = list(source_files.keys())
    total_lines = sum(len(c.splitlines()) for c in source_files.values())

    mutation = {
        "score": 1.0 if len(files_changed) <= 3 else 0.5,
        "files_changed": files_changed,
        "total_lines_changed": total_lines,
        "assessment": "local" if len(files_changed) <= 2 else "moderate" if len(files_changed) <= 5 else "broad",
    }

    # Calculate overall
    if checks:
        pass_count = sum(1 for c in checks if c.get("status") == "pass")
        score = pass_count / len(checks)
    else:
        score = 0.5  # No checks = neutral

    return CheckResult(
        overall="pass" if score >= 0.7 else "fail",
        checks=tuple(checks),
        hallucinations=tuple(hallucinations),
        mutation_locality=mutation,
        summary=f"Local check: {score:.0%} of checks passed",
        score=score,
    )
