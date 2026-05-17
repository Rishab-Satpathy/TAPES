"""Execution Layer for TAPES v8.0.

Dual-Tier LEC (Local Execution Check):
    Tier 1 (Fast Sandbox): Copy .py files only, run tests with host Python.
        Guarantees millisecond feedback loops during Scorched Earth cycles.
    Tier 2 (Final Merge Gate): Full venv isolation check before atomic commit.

Scorched Earth Loop with Granular FailureKind:
    TRANSIENT (no penalty, silent retry):
        NETWORK_TIMEOUT, API_RATE_LIMIT
    STRUCTURAL (+0.5 oscillation, fast-path syntax fix):
        AST_PARSE_FATAL, TARGET_NODE_MISSING, INDENTATION_MISMATCH
    SEMANTIC (+1.0 oscillation, full context re-evaluation):
        PYTEST_ASSERTION_FAIL, TYPE_CHECKER_REJECT, EXECUTION_TIMEOUT
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────

MAX_OSCILLATION_CYCLES = 3


# ── FailureKind enum ───────────────────────────────────────────────────────

class FailureTier(StrEnum):
    """High-level failure tier controlling retry policy."""
    TRANSIENT = "transient"        # No penalty, silent retry
    STRUCTURAL = "structural"      # +0.5 oscillation, fast-path syntax fix
    SEMANTIC = "semantic"          # +1.0 oscillation, full context re-evaluation


class FailureKind(StrEnum):
    """Granular failure sub-types for readability."""
    # Transient — no penalty
    NETWORK_TIMEOUT = "network_timeout"
    API_RATE_LIMIT = "api_rate_limit"

    # Structural — +0.5 oscillation
    AST_PARSE_FATAL = "ast_parse_fatal"
    TARGET_NODE_MISSING = "target_node_missing"
    INDENTATION_MISMATCH = "indentation_mismatch"

    # Semantic — +1.0 oscillation
    PYTEST_ASSERTION_FAIL = "pytest_assertion_fail"
    TYPE_CHECKER_REJECT = "type_checker_reject"
    EXECUTION_TIMEOUT = "execution_timeout"

    # Unknown
    UNKNOWN = "unknown"


# Tier mapping
FAILURE_TIERS: dict[FailureKind, FailureTier] = {
    FailureKind.NETWORK_TIMEOUT: FailureTier.TRANSIENT,
    FailureKind.API_RATE_LIMIT: FailureTier.TRANSIENT,
    FailureKind.AST_PARSE_FATAL: FailureTier.STRUCTURAL,
    FailureKind.TARGET_NODE_MISSING: FailureTier.STRUCTURAL,
    FailureKind.INDENTATION_MISMATCH: FailureTier.STRUCTURAL,
    FailureKind.PYTEST_ASSERTION_FAIL: FailureTier.SEMANTIC,
    FailureKind.TYPE_CHECKER_REJECT: FailureTier.SEMANTIC,
    FailureKind.EXECUTION_TIMEOUT: FailureTier.SEMANTIC,
    FailureKind.UNKNOWN: FailureTier.SEMANTIC,
}

# Oscillation penalties per tier
TIER_PENALTIES: dict[FailureTier, float] = {
    FailureTier.TRANSIENT: 0.0,
    FailureTier.STRUCTURAL: 0.5,
    FailureTier.SEMANTIC: 1.0,
}


def classify_failure(error_output: str, return_code: int) -> FailureKind:
    """Parse error output to classify into a specific FailureKind."""
    lower = error_output.lower()

    # Transient
    if "timeout" in lower and ("connection" in lower or "network" in lower or "urlopen" in lower):
        return FailureKind.NETWORK_TIMEOUT
    if "rate limit" in lower or "429" in lower or "too many requests" in lower:
        return FailureKind.API_RATE_LIMIT

    # Structural
    if "syntaxerror" in lower or "syntax error" in lower:
        return FailureKind.AST_PARSE_FATAL
    if "indentationerror" in lower or "unexpected indent" in lower or "unindent" in lower:
        return FailureKind.INDENTATION_MISMATCH
    if "target_symbol" in lower and ("not found" in lower or "missing" in lower):
        return FailureKind.TARGET_NODE_MISSING
    if "ast lookup failed" in lower or "hallucinated" in lower:
        return FailureKind.TARGET_NODE_MISSING

    # Semantic
    if return_code == -1 and "timed out" in lower:
        return FailureKind.EXECUTION_TIMEOUT
    if "assertionerror" in lower or ("assert " in lower and "assertion" in lower) or "FAILED " in error_output:
        return FailureKind.PYTEST_ASSERTION_FAIL
    if "mypy" in lower or "type error" in lower or "typeerror" in lower:
        return FailureKind.TYPE_CHECKER_REJECT

    return FailureKind.UNKNOWN


# ── Exceptions ─────────────────────────────────────────────────────────────

class TAPESHaltError(Exception):
    """Raised when the scorched earth loop breaches MAX_OSCILLATION_CYCLES."""

    def __init__(self, message: str, failure_trace: list[str] | None = None) -> None:
        self.failure_trace = failure_trace or []
        super().__init__(message)


# ── Dual-Tier LEC ──────────────────────────────────────────────────────────

@dataclass
class LECResult:
    """Result of a Local Execution Check."""
    passed: bool
    tests_run: list[str]
    test_output: str
    tier: int = 1  # 1 or 2
    failure_kind: FailureKind = FailureKind.UNKNOWN
    error: str | None = None
    return_code: int = 0


def _find_venv_dir(source_dir: str) -> Path | None:
    """Find the virtual environment directory."""
    source_path = Path(source_dir)
    candidates = [
        source_path / ".venv",
        source_path / "venv",
        source_path / "env",
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "pyvenv.cfg").exists():
            return candidate

    venv_env = os.environ.get("VIRTUAL_ENV")
    if venv_env:
        return Path(venv_env)

    return None


def _clone_venv(venv_dir: Path, temp_dir: Path) -> Path:
    """Clone a venv into a temp directory (fast: system-site-packages only, no pip install)."""
    temp_venv = temp_dir / "venv_clone"

    try:
        python = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        if python.with_suffix(".exe").exists():
            python = python.with_suffix(".exe")

        subprocess.run(
            [str(python), "-m", "venv", str(temp_venv), "--system-site-packages"],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        logger.warning("Venv clone failed; falling back to directory copy")
        if temp_venv.exists():
            shutil.rmtree(temp_venv)
        shutil.copytree(venv_dir, temp_venv)

    return temp_venv


def run_lec_tier1(
    source_dir: str,
    patches: list[Any],
    test_files: list[str] | None = None,
    target_symbol: str | None = None,
    _expansion_depth: int = 0,
) -> LECResult:
    """Tier 1 LEC (Fast Sandbox).

    Does NOT clone the virtual environment.
    Copies only .py source files to a temp directory and runs the
    targeted tests using the host's existing Python process.
    Guarantees millisecond feedback loops during Scorched Earth cycles.
    """
    MAX_EXPANSION_DEPTH = 3
    source_path = Path(source_dir).resolve()

    with tempfile.TemporaryDirectory(prefix="tapes_lec_t1_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        temp_source = temp_dir / "source"

        # Tier 1: copy only .py files — no venv, no cache
        temp_source.mkdir(parents=True, exist_ok=True)
        for py_file in source_path.rglob("*.py"):
            rel = py_file.relative_to(source_path)
            if ".venv" in str(rel) or "__pycache__" in str(rel) or ".git" in str(rel):
                continue
            dest = temp_source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py_file, dest)

        # Also copy non-py config files needed for tests
        for config_file in ("pyproject.toml", "setup.cfg", "setup.py", "pytest.ini", "conftest.py"):
            src = source_path / config_file
            if src.exists():
                shutil.copy2(src, temp_source / config_file)

        # Apply patches in temp directory
        patched_files_contents = {}
        if patches:
            from .patches import apply_patches as _apply
            results = _apply(str(temp_source), patches)
            
            # Feature 11: Pre-Flight Syntax Gate
            syntax_errors = []
            for res in results:
                if res.applied:
                    dest_file = temp_source / res.patch.file
                    if dest_file.exists():
                        patched_files_contents[dest_file] = dest_file.read_text(encoding="utf-8")
                        try:
                            compile(patched_files_contents[dest_file], str(dest_file), "exec")
                        except SyntaxError as e:
                            syntax_errors.append(f"SyntaxError in {res.patch.file}: {e}")
                            
            if syntax_errors:
                return LECResult(
                    passed=False,
                    tests_run=[],
                    test_output="\n".join(syntax_errors),
                    tier=1,
                    failure_kind=FailureKind.AST_PARSE_FATAL,
                    error="Syntax Gate Failed",
                    return_code=1,
                )

        # Determine which tests to run
        if test_files is None and target_symbol:
            from forest_tapes.tapes_core.ast_extractor import ASTExtractor
            extractor = ASTExtractor(source_dir=str(temp_source))
            extractor.index()
            test_files = extractor.get_relevant_tests(target_symbol, "tests")

        if not test_files:
            test_files = ["tests/"]

        # Tier 1: use project venv Python if available, fallback to host
        _find_venv = Path(sys.executable)
        _proj_root = Path(source_path).resolve()
        for _venv in (_proj_root / ".venv", _proj_root.parent / ".venv"):
            _candidate = _venv / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
            if _candidate.exists():
                _find_venv = _candidate
                break
        python_exec = _find_venv
        cmd = [str(python_exec), "-m", "pytest", "-x", "--tb=short", "-q"]
        cmd.extend(test_files)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(temp_source),
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout + result.stderr
            failure_kind = FailureKind.UNKNOWN
            if result.returncode != 0:
                failure_kind = classify_failure(output, result.returncode)

            # Feature 12: Dynamic Expansion Ceiling (max 3 levels)
            if _expansion_depth < MAX_EXPANSION_DEPTH:
                if "ModuleNotFoundError" in output or "ImportError" in output:
                    import re
                    match = re.search(r"No module named '([^']+)'", output)
                    if match:
                        missing_module = match.group(1)
                        print(f"    [EXPANSION] Missing module detected: {missing_module}. Checking expansion ceiling...")
                        parts = missing_module.split('.')
                        candidate_paths = [
                            source_path / Path(*parts).with_suffix('.py'),
                            source_path / Path(*parts) / '__init__.py'
                        ]
                        found_file = next((p for p in candidate_paths if p.exists()), None)
                        if found_file:
                            rel_path = found_file.relative_to(source_path)
                            dest = temp_source / rel_path
                            if not dest.exists():
                                print(f"    [EXPANSION] Dynamically ingesting {rel_path} into sandbox...")
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(found_file, dest)
                                return run_lec_tier1(source_dir, patches, test_files, target_symbol, _expansion_depth + 1)
            return LECResult(
                passed=result.returncode == 0,
                tests_run=test_files,
                test_output=output,
                tier=1,
                failure_kind=failure_kind,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return LECResult(
                passed=False,
                tests_run=test_files,
                test_output="Test execution timed out (120s)",
                tier=1,
                failure_kind=FailureKind.EXECUTION_TIMEOUT,
                error="timeout",
                return_code=-1,
            )
        except subprocess.SubprocessError as e:
            return LECResult(
                passed=False,
                tests_run=test_files,
                test_output=f"Subprocess error: {e}",
                tier=1,
                failure_kind=FailureKind.UNKNOWN,
                error=str(e),
                return_code=-1,
            )
        except FileNotFoundError as e:
            return LECResult(
                passed=False,
                tests_run=test_files,
                test_output=f"pytest not found: {e}",
                tier=1,
                failure_kind=FailureKind.UNKNOWN,
                error=str(e),
                return_code=-1,
            )


def _sandbox_copy(source_path: Path, temp_source: Path, affected_files: list[str] | None = None) -> None:
    """Copy only affected files into sandbox (avoids full repo copy)."""
    if affected_files:
        temp_source.mkdir(parents=True, exist_ok=True)
        for f in affected_files:
            src = source_path / f
            dst = temp_source / f
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
    else:
        shutil.copytree(
            source_path,
            temp_source,
            ignore=shutil.ignore_patterns(".venv", "venv", "env", "__pycache__", "*.pyc", ".git"),
        )


def run_lec_tier2(
    source_dir: str,
    patches: list[Any],
    test_files: list[str] | None = None,
    target_symbol: str | None = None,
) -> LECResult:
    """Tier 2 LEC (Final Merge Gate).

    Full venv isolation check. Only executed once the patch passes Tier 1.
    Clones the virtual environment, applies patches, and runs tests in
    complete isolation before allowing the atomic commit.
    """
    source_path = Path(source_dir).resolve()
    venv_dir = _find_venv_dir(source_dir)

    with tempfile.TemporaryDirectory(prefix="tapes_lec_t2_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        # Full source copy (optimized: only affected files if known)
        temp_source = temp_dir / "source"
        _sandbox_copy(source_path, temp_source, affected_files=None)

        # Clone venv
        if venv_dir:
            temp_venv = _clone_venv(venv_dir, temp_dir)
            python_exec = temp_venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
            if python_exec.with_suffix(".exe").exists():
                python_exec = python_exec.with_suffix(".exe")
        else:
            python_exec = Path(sys.executable)

        # Apply patches
        if patches:
            from .patches import apply_patches as _apply
            _apply(str(temp_source), patches)

        # Determine tests
        if test_files is None and target_symbol:
            from forest_tapes.tapes_core.ast_extractor import ASTExtractor
            extractor = ASTExtractor(source_dir=str(temp_source))
            extractor.index()
            test_files = extractor.get_relevant_tests(target_symbol, "tests")

        if not test_files:
            test_files = ["tests/"]

        cmd = [str(python_exec), "-m", "pytest", "-x", "--tb=short", "-q"]
        cmd.extend(test_files)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(temp_source),
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout + result.stderr
            failure_kind = FailureKind.UNKNOWN
            if result.returncode != 0:
                failure_kind = classify_failure(output, result.returncode)
            return LECResult(
                passed=result.returncode == 0,
                tests_run=test_files,
                test_output=output,
                tier=2,
                failure_kind=failure_kind,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return LECResult(
                passed=False,
                tests_run=test_files,
                test_output="Test execution timed out (120s)",
                tier=2,
                failure_kind=FailureKind.EXECUTION_TIMEOUT,
                error="timeout",
                return_code=-1,
            )
        except subprocess.SubprocessError as e:
            return LECResult(
                passed=False,
                tests_run=test_files,
                test_output=str(e),
                tier=2,
                failure_kind=FailureKind.UNKNOWN,
                error=str(e),
                return_code=-1,
            )


# Legacy compatibility alias
def run_lec(
    source_dir: str,
    patches: list[Any],
    test_files: list[str] | None = None,
    target_symbol: str | None = None,
) -> LECResult:
    """Run the dual-tier LEC: Tier 1 first, then Tier 2 on pass."""
    t1 = run_lec_tier1(source_dir, patches, test_files, target_symbol)
    if not t1.passed:
        return t1
    return run_lec_tier2(source_dir, patches, test_files, target_symbol)


def merge_to_main(temp_source: Path, main_source: Path) -> None:
    """Atomically merge temp directory into the main directory on full pass."""
    for py_file in temp_source.rglob("*.py"):
        rel = py_file.relative_to(temp_source)
        target = main_source / rel
        if ".venv" in str(rel) or "__pycache__" in str(rel):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(py_file, target)
    logger.info("Merged temp source into main at %s", main_source)


# ── Scorched Earth Loop ───────────────────────────────────────────────────

@dataclass
class LoopState:
    """State of the scorched earth loop."""
    cycle: int = 0
    oscillation_counter: float = 0.0
    failure_trace: list[str] | None = None

    def __post_init__(self) -> None:
        if self.failure_trace is None:
            self.failure_trace = []


def scorched_earth_loop(
    intent: str,
    source_dir: str = ".",
    ledger_path: str = "tapes-ledger.jsonl",
    contract_path: str = "tapes-contract.json",
    patches_path: str = "tapes-patches.json",
    offline: bool = False,
    max_cycles: int = MAX_OSCILLATION_CYCLES,
) -> dict[str, Any]:
    """Scorched earth loop with granular FailureKind classification.

    Oscillation penalty varies by failure tier:
        TRANSIENT:  +0.0 (silent retry)
        STRUCTURAL: +0.5 (fast-path syntax fix)
        SEMANTIC:   +1.0 (full context re-evaluation)
    """
    from .ledger import append_entry
    from .plan import run_plan
    from .build import run_build
    from .check import run_check

    state = LoopState()

    print(f"\n{'═'*60}")
    print(f"  TAPES SCORCHED EARTH — Max cycles: {max_cycles}")
    print(f"{'═'*60}\n")

    while state.oscillation_counter < max_cycles:
        state.cycle += 1
        print(f"\n  ╔═══ Cycle {state.cycle} (oscillation: {state.oscillation_counter:.1f}/{max_cycles}) ═══╗")

        try:
            # Plan
            print("  │ [PLAN] Stabilizing intent...")
            contract = run_plan(
                user_input=intent,
                output_path=contract_path,
                ledger_path=ledger_path,
                offline=offline,
            )

            # Build
            print("  │ [BUILD] Generating patches...")
            build_output, _bob_report = run_build(
                contract_path=contract_path,
                source_dir=source_dir,
                output_path=patches_path,
                ledger_path=ledger_path,
                auto_apply=True,
                offline=offline,
            )

            # Check (LEC)
            print("  │ [CHECK] Validating...")
            check_result = run_check(
                contract_path=contract_path,
                source_dir=source_dir,
                ledger_path=ledger_path,
                offline=offline,
            )

            if check_result.overall == "pass":
                print(f"  ╚═══ PASS on cycle {state.cycle} ═══╝")
                return {
                    "status": "pass",
                    "cycles": state.cycle,
                    "oscillation_counter": state.oscillation_counter,
                }

            # Classify the failure
            failure_kind = classify_failure(
                getattr(check_result, "details", "") or "",
                getattr(check_result, "return_code", 1),
            )
            tier = FAILURE_TIERS.get(failure_kind, FailureTier.SEMANTIC)
            penalty = TIER_PENALTIES[tier]

            state.oscillation_counter += penalty
            failure_msg = (
                f"Cycle {state.cycle}: {failure_kind.value} "
                f"[{tier.value}, +{penalty}] "
                f"(score: {check_result.score:.0%})"
            )
            state.failure_trace.append(failure_msg)
            print(f"  │ [{tier.value.upper()}] {failure_kind.value}")
            print(f"  │ Penalty: +{penalty} → oscillation: {state.oscillation_counter:.1f}/{max_cycles}")

            # Log failure to ledger
            append_entry(
                ledger_path=ledger_path,
                entry_type="check",
                command="tapes scorched-earth",
                input_text=intent,
                output_summary=failure_msg,
                details={
                    "overall": check_result.overall,
                    "score": check_result.score,
                    "failure_kind": failure_kind.value,
                    "failure_tier": tier.value,
                    "penalty": penalty,
                    "oscillation_counter": state.oscillation_counter,
                    "cycle": state.cycle,
                },
            )

            # Transient failures: silent retry without logging as failure
            if tier == FailureTier.TRANSIENT:
                print("  │ [TRANSIENT] Silent retry...")
                continue
                
            # Feature 11: Amnesiac Retries
            if failure_kind == FailureKind.PYTEST_ASSERTION_FAIL or failure_kind == FailureKind.AST_PARSE_FATAL:
                print("  │ [AMNESIA] Logic/Syntax failure detected. Wiping Surgeon's memory for Attempt 2.")
                from .ledger import wipe_memory
                wipe_memory(ledger_path)
                
                # Actual Prompt Injection for Attempt 2
                traceback_text = getattr(check_result, "details", "") or "No detailed traceback."
                if "[PRIOR FAILURE TRACEBACK TO AVOID]" not in intent:
                    intent = f"{intent}\n\n[PRIOR FAILURE TRACEBACK TO AVOID]\n{traceback_text}"
                
        except Exception as e:
            # Classify exception-based failures
            error_str = f"{type(e).__name__}: {e}"
            failure_kind = classify_failure(error_str, -1)
            tier = FAILURE_TIERS.get(failure_kind, FailureTier.SEMANTIC)
            penalty = TIER_PENALTIES[tier]

            state.oscillation_counter += penalty
            failure_msg = f"Cycle {state.cycle}: {failure_kind.value} [{tier.value}, +{penalty}] — {error_str}"
            state.failure_trace.append(failure_msg)
            print(f"  │ [ERROR] {failure_kind.value} [{tier.value}]: {error_str}")

    # Breached MAX_OSCILLATION_CYCLES — write <unresolvable> and halt
    print(f"\n  {'!'*50}")
    print(f"  UNRESOLVABLE: oscillation {state.oscillation_counter:.1f} >= {max_cycles}")
    print(f"  {'!'*50}")

    append_entry(
        ledger_path=ledger_path,
        entry_type="check",
        command="tapes scorched-earth",
        input_text=intent,
        output_summary=f"<unresolvable> after {state.cycle} cycles (oscillation: {state.oscillation_counter:.1f})",
        details={
            "overall": "unresolvable",
            "oscillation_counter": state.oscillation_counter,
            "failure_trace": state.failure_trace,
        },
    )

    raise TAPESHaltError(
        f"TAPES Halt: Unresolvable (oscillation {state.oscillation_counter:.1f} >= {max_cycles}).\n"
        f"Failure trace:\n" + "\n".join(f"  {f}" for f in state.failure_trace),
        failure_trace=state.failure_trace,
    )
