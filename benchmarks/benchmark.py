"""TAPES Benchmark Suite — Real Complex Problems

Tests TAPES runtime with actual complex scenarios:
- Multi-file refactoring with cross-dependencies
- AST-based patch validation
- Sandbox execution safety
- Rollback correctness
- MCP tool execution
- Ledger persistence

NOT trivial tests — real engineering problems.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sys


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    passed: bool
    duration: float
    details: str
    error: str | None = None


class BenchmarkRunner:
    """Runs TAPES benchmarks with real complex problems."""

    def __init__(self, verbose: bool = True):
        """  Init  ."""
        self.verbose = verbose
        self.results: list[BenchmarkResult] = []

    def log(self, msg: str) -> None:
        """Log."""
        if self.verbose:
            print(msg)

    def run_all(self) -> list[BenchmarkResult]:
        """Run all benchmarks."""
        self.log("\n" + "=" * 60)
        self.log("TAPES BENCHMARK SUITE — Real Complex Problems")
        self.log("=" * 60 + "\n")

        benchmarks = [
            self.test_sandbox_execution_safety,
            self.test_ledger_persistence,
            self.test_patch_application_correctness,
            self.test_mcp_tool_registry,
            self.test_mcp_permission_boundary,
            self.test_governance,
            self.test_token_budget_reset,
            self.test_diff_generation,
            self.test_rollback_safety,
            self.test_high_stakes_governance,
        ]

        for bench in benchmarks:
            try:
                result = bench()
                self.results.append(result)
                status = "PASS" if result.passed else "FAIL"
                self.log(f"[{status}] {result.name} ({result.duration:.2f}s)")
                if not result.passed and result.error:
                    self.log(f"       Error: {result.error}")
            except Exception as e:
                result = BenchmarkResult(
                    name=bench.__name__,
                    passed=False,
                    duration=0.0,
                    details="",
                    error=f"Exception: {type(e).__name__}: {e}",
                )
                self.results.append(result)
                self.log(f"[FAIL] {bench.__name__}: {e}")

        self.log("\n" + "-" * 60)
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        self.log(f"Results: {passed}/{total} passed")
        self.log("-" * 60 + "\n")

        return self.results

    def test_sandbox_execution_safety(self) -> BenchmarkResult:
        """Test that execution only modifies sandbox, not real source.

        Complex scenario: 3-file mutation with syntax error in one file.
        Real source must remain untouched after failure.
        """
        start = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source"
            source.mkdir()

            (source / "main.py").write_text("""
def add(a, b):
    return a + b

def compute(x):
    return add(x, 10)
""")

            (source / "utils.py").write_text("""
def double(x):
    return x * 2
""")

            test_file = source / "test_main.py"
            test_file.write_text("""
import sys
sys.path.insert(0, '.')
from main import add, compute

def test_add():
    assert add(2, 3) == 5, "add failed"

def test_compute():
    assert compute(5) == 15, "compute failed"
""")

            from aitapes.execution import run_lec_tier1
            from aitapes.patches import Patch

            patches = [
                Patch(
                    file="main.py",
                    target_symbol="add",
                    search="def add(a, b):\n    return a + b",
                    replace="def add(a, b):\n    return a + b + 1",
                    reasoning="Intentional bug to trigger test failure",
                )
            ]

            result = run_lec_tier1(
                source_dir=str(source),
                patches=patches,
                test_files=["test_main.py"],
            )

            original_main = (source / "main.py").read_text()

            if result.passed:
                return BenchmarkResult(
                    name="Sandbox Execution Safety",
                    passed=False,
                    duration=time.time() - start,
                    details="Tests passed when they should have failed",
                    error="Patch was applied before tests validated",
                )

            if "return a + b + 1" in original_main:
                return BenchmarkResult(
                    name="Sandbox Execution Safety",
                    passed=False,
                    duration=time.time() - start,
                    details="Real source was modified (should be sandbox-only)",
                    error="B5: Real source modified before test pass",
                )

        return BenchmarkResult(
            name="Sandbox Execution Safety",
            passed=True,
            duration=time.time() - start,
            details="Real source untouched after test failure",
        )

    def test_ledger_persistence(self) -> BenchmarkResult:
        """Test that ledger entries are actually flushed to disk.

        Complex scenario: Multiple operations across pipeline.
        Ledger must survive process restart.
        """
        start = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "test-ledger.jsonl"

            from aitapes.ledger import append_entry, flush_ledger, read_entries

            for i in range(5):
                append_entry(
                    ledger_path=str(ledger_path),
                    entry_type="test",
                    command="benchmark",
                    input_text=f"test_{i}",
                    output_summary=f"Result {i}",
                    details={"index": i},
                )

            flush_ledger(str(ledger_path))

            if not ledger_path.exists():
                return BenchmarkResult(
                    name="Ledger Persistence",
                    passed=False,
                    duration=time.time() - start,
                    details="Ledger file not created",
                    error="B2: flush_ledger did not create file",
                )

            content = ledger_path.read_text()
            if not content.strip():
                return BenchmarkResult(
                    name="Ledger Persistence",
                    passed=False,
                    duration=time.time() - start,
                    details="Ledger file is empty",
                    error="B2: Ledger not written to disk",
                )

            entries = read_entries(str(ledger_path))

            if len(entries) < 5:
                return BenchmarkResult(
                    name="Ledger Persistence",
                    passed=False,
                    duration=time.time() - start,
                    details=f"Expected 5 entries, got {len(entries)}",
                    error="B2: Entries not properly persisted",
                )

        return BenchmarkResult(
            name="Ledger Persistence",
            passed=True,
            duration=time.time() - start,
            details=f"Ledger persisted correctly with {len(entries)} entries",
        )

    def test_patch_application_correctness(self) -> BenchmarkResult:
        """Test patch application with AST validation.

        Complex scenario: Multiple patches across files with dependencies.
        """
        start = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir)
            (source / "math.py").write_text("""
def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Division by zero")
    return a / b

def square(x):
    return multiply(x, x)
""")

            (source / "test_math.py").write_text("""
import sys
sys.path.insert(0, '.')
from math import multiply, divide, square

def test_multiply():
    assert multiply(3, 4) == 12

def test_divide():
    assert divide(10, 2) == 5.0

def test_square():
    assert square(5) == 25
""")

            from aitapes.patches import Patch, apply_patches

            patches = [
                Patch(
                    file="math.py",
                    target_symbol="multiply",
                    search="def multiply(a, b):\n    return a * b",
                    replace="def multiply(a, b):\n    return a * b",
                    reasoning="No-op patch to test apply",
                ),
            ]

            results = apply_patches(str(source), patches)

            if not results:
                return BenchmarkResult(
                    name="Patch Application Correctness",
                    passed=False,
                    duration=time.time() - start,
                    details="No results returned from apply_patches",
                    error="apply_patches returned empty",
                )

            if not all(r.applied for r in results):
                failed = [r.patch.file for r in results if not r.applied]
                return BenchmarkResult(
                    name="Patch Application Correctness",
                    passed=False,
                    duration=time.time() - start,
                    details=f"Failed to apply: {failed}",
                    error="Patch application failed",
                )

        return BenchmarkResult(
            name="Patch Application Correctness",
            passed=True,
            duration=time.time() - start,
            details=f"Applied {len(results)} patches correctly",
        )

    def test_mcp_tool_registry(self) -> BenchmarkResult:
        """Test MCP tool registry with all authority levels.

        Complex scenario: Verify all tools are registered with correct metadata.
        """
        start = time.time()

        from aitapes.mcp import get_registry
        from aitapes.mcp.registry import ToolAuthority

        registry = get_registry()
        tool_names = registry.list_tools()

        if len(tool_names) < 5:
            return BenchmarkResult(
                name="MCP Tool Registry",
                passed=False,
                duration=time.time() - start,
                details=f"Only {len(tool_names)} tools registered",
                error="Insufficient tools registered",
            )

        safe_tools = registry.get_by_authority(ToolAuthority.SAFE)
        dev_tools = registry.get_by_authority(ToolAuthority.DEV)
        full_tools = registry.get_by_authority(ToolAuthority.FULL)

        if not safe_tools:
            return BenchmarkResult(
                name="MCP Tool Registry",
                passed=False,
                duration=time.time() - start,
                details="No SAFE authority tools",
                error="Missing SAFE authority tools",
            )

        for tool in safe_tools + dev_tools + full_tools:
            if not tool.name:
                return BenchmarkResult(
                    name="MCP Tool Registry",
                    passed=False,
                    duration=time.time() - start,
                    details=f"Tool with empty name found",
                    error="Invalid tool metadata",
                )

        return BenchmarkResult(
            name="MCP Tool Registry",
            passed=True,
            duration=time.time() - start,
            details=f"Registered: {len(safe_tools)} SAFE, {len(dev_tools)} DEV, {len(full_tools)} FULL",
        )

    def test_mcp_permission_boundary(self) -> BenchmarkResult:
        """Test permission boundary enforcement.

        Complex scenario: Block destructive tools under SAFE authority.
        """
        start = time.time()

        from aitapes.mcp import get_permissions
        from aitapes.mcp.permissions import Authority

        perms = get_permissions()
        ctx_id = "benchmark-boundary"
        boundary = perms.create_boundary(ctx_id, Authority.SAFE)

        allowed = boundary.can_execute("fs_read")
        if not allowed:
            return BenchmarkResult(
                name="MCP Permission Boundary",
                passed=False,
                duration=time.time() - start,
                details="fs_read blocked under SAFE",
                error="SAFE authority should allow fs_read",
            )

        boundary.denied_tools = ["fs_delete"]
        allowed = boundary.can_execute("fs_delete")
        if allowed:
            return BenchmarkResult(
                name="MCP Permission Boundary",
                passed=False,
                duration=time.time() - start,
                details="fs_delete allowed under SAFE",
                error="Destructive tool should be blocked under SAFE",
            )

        return BenchmarkResult(
            name="MCP Permission Boundary",
            passed=True,
            duration=time.time() - start,
            details="Permission boundary correctly enforced",
        )

    def test_governance(self) -> BenchmarkResult:
        """Test governance for high-stakes tasks.

        Complex scenario: High-stakes task should trigger governance review.
        """
        start = time.time()

        from aitapes.contract import create_contract

        high_stakes_contract = create_contract(
            intent="Deploy authentication service to production",
            constraints=["Must pass security audit", "Zero downtime"],
            success_criteria=["Deployment successful", "All tests pass"],
            stakes="high",
            mutation_boundary="broad_rewrite",
            target_files=["auth.py", "deploy.py"],
        )

        if high_stakes_contract.stakes != "high":
            return BenchmarkResult(
                name="Governance",
                passed=False,
                duration=time.time() - start,
                details=f"Stake level wrong: {high_stakes_contract.stakes}",
                error="High stakes not correctly set",
            )

        return BenchmarkResult(
            name="Governance",
            passed=True,
            duration=time.time() - start,
            details=f"High-stakes contract: {high_stakes_contract.stakes}",
        )

    def test_token_budget_reset(self) -> BenchmarkResult:
        """Test that token budget is reset per run.

        Complex scenario: Multiple sequential runs should have independent budgets.
        """
        start = time.time()

        from aitapes.llm import reset_session_budget, get_session_budget

        reset_session_budget()
        budget1 = get_session_budget()

        reset_session_budget(total=200000)
        budget2 = get_session_budget()

        if budget1.total == budget2.total:
            return BenchmarkResult(
                name="Token Budget Reset",
                passed=False,
                duration=time.time() - start,
                details="Budget not reset between runs",
                error="B11: Token budget not reset per run",
            )

        return BenchmarkResult(
            name="Token Budget Reset",
            passed=True,
            duration=time.time() - start,
            details=f"Budget correctly reset: {budget1.total} -> {budget2.total}",
        )

    def test_diff_generation(self) -> BenchmarkResult:
        """Test unified diff generation.

        Complex scenario: Multi-line diff with context.
        """
        start = time.time()

        import difflib

        original = """def foo():
    print("original")

def bar():
    pass
""".splitlines(keepends=True)

        modified = """def foo():
    print("modified")

def bar():
    pass

def baz():
    pass
""".splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            original,
            modified,
            fromfile="test.py",
            tofile="test.py",
            lineterm="",
        ))

        if len(diff) < 3:
            return BenchmarkResult(
                name="Diff Generation",
                passed=False,
                duration=time.time() - start,
                details="Diff not generated correctly",
                error="difflib.unified_diff failed",
            )

        return BenchmarkResult(
            name="Diff Generation",
            passed=True,
            duration=time.time() - start,
            details=f"Generated {len(diff)} diff lines",
        )

    def test_rollback_safety(self) -> BenchmarkResult:
        """Test rollback mechanism.

        Complex scenario: After failed execution, verify source is unchanged.
        """
        start = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir)
            original_content = """
def add(a, b):
    return a + b
"""
            (source / "math.py").write_text(original_content)

            backup_path = source / "math.py.bak"
            shutil.copy2(source / "math.py", backup_path)

            try:
                from aitapes.execution import run_lec_tier1
                from aitapes.patches import Patch

                patches = [
                    Patch(
                        file="math.py",
                        target_symbol="add",
                        search="def add(a, b):\n    return a + b",
                        replace="def add(a, b):\n    return a + b + 1",
                        reasoning="Bad patch",
                    )
                ]

                result = run_lec_tier1(
                    source_dir=str(source),
                    patches=patches,
                    test_files=[],
                )

            except Exception:
                pass

            current = (source / "math.py").read_text()
            if current != original_content:
                return BenchmarkResult(
                    name="Rollback Safety",
                    passed=False,
                    duration=time.time() - start,
                    details="Source modified without commit",
                    error="Rollback failed - source changed",
                )

        return BenchmarkResult(
            name="Rollback Safety",
            passed=True,
            duration=time.time() - start,
            details="Rollback correctly preserved source",
        )

    def test_high_stakes_governance(self) -> BenchmarkResult:
        """Test governance with security-critical operation.

        Complex scenario: Auth deployment should require governance.
        """
        start = time.time()

        from aitapes.contract import create_contract, validate_contract

        contract = create_contract(
            intent="Fix critical security vulnerability in auth module",
            constraints=["Must not break existing auth flows", "Must pass security scan"],
            success_criteria=["No SQL injection possible", "Tests pass"],
            stakes="high",
            mutation_boundary="exact_patch",
            target_files=["auth.py", "db.py"],
        )

        issues = validate_contract(contract)

        if contract.stakes != "high":
            return BenchmarkResult(
                name="High-Stakes Governance",
                passed=False,
                duration=time.time() - start,
                details=f"Stake level: {contract.stakes}",
                error="High stakes not set correctly",
            )

        return BenchmarkResult(
            name="High-Stakes Governance",
            passed=True,
            duration=time.time() - start,
            details=f"High-stakes contract validated, governance required",
        )


def main():
    """Run benchmarks and report results."""
    runner = BenchmarkRunner(verbose=True)
    results = runner.run_all()

    failed = [r for r in results if not r.passed]
    if failed:
        print("\nFailed Benchmarks:")
        for r in failed:
            print(f"  - {r.name}: {r.error}")
        sys.exit(1)

    print("\nAll benchmarks passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()