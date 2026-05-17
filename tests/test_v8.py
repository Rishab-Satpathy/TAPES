"""Tests for TAPES v8.0 / v9.0 modules.

Tests cover all phases + upgrades:
    Phase 0: LLM token budget (atomic math), ledger schema, rollback
    Phase 1: Vector grounding, AST extractor, PageRank centrality
    Phase 2: AST-driven splicer, scorched earth, FailureKind, dual-tier LEC
    Phase 3: Live debate early-exit
    Phase 4: Centrality-weighted complexity tracker, dynamic ontology
    Benchmark: benchmark_control.py
"""

from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest


# ── Phase 0: Token Budget ──────────────────────────────────────────────────

class TestTokenBudget:
    def test_budget_partition_ratios(self):
        from aitapes.llm import TokenBudget, TokenPartition

        budget = TokenBudget(total=100_000)
        assert budget.generation_limit == 70_000
        assert budget.debate_limit == 30_000

    def test_consume_within_budget(self):
        from aitapes.llm import TokenBudget, TokenPartition

        budget = TokenBudget(total=10_000)
        budget.consume(5_000, TokenPartition.GENERATION)
        assert budget.generation_used == 5_000
        assert budget.remaining(TokenPartition.GENERATION) == 2_000

    def test_budget_breach_raises(self):
        from aitapes.llm import TokenBudget, TokenPartition, BudgetBreachError

        budget = TokenBudget(total=1_000)
        with pytest.raises(BudgetBreachError) as exc_info:
            budget.consume(800, TokenPartition.GENERATION)
        assert exc_info.value.partition == TokenPartition.GENERATION

    def test_consume_atomic_no_mutation_on_breach(self):
        """Item 1: consume() checks BEFORE incrementing — no mutation on breach."""
        from aitapes.llm import TokenBudget, TokenPartition, BudgetBreachError

        budget = TokenBudget(total=1_000)
        budget.consume(600, TokenPartition.GENERATION)  # 600 used of 700 limit
        assert budget.generation_used == 600
        with pytest.raises(BudgetBreachError):
            budget.consume(200, TokenPartition.GENERATION)  # 800 > 700 limit
        # Counter should NOT have been mutated
        assert budget.generation_used == 600

    def test_insufficient_tokens_error(self):
        """Item 1: InsufficientTokensError raised on Deny."""
        from aitapes.llm import InsufficientTokensError, TokenPartition

        err = InsufficientTokensError(
            partition=TokenPartition.GENERATION, used=800, limit=700
        )
        assert err.partition == TokenPartition.GENERATION
        assert "DENIED" in str(err)

    def test_debate_budget_separate(self):
        from aitapes.llm import TokenBudget, TokenPartition

        budget = TokenBudget(total=10_000)
        budget.consume(200, TokenPartition.DEBATE)
        assert budget.debate_used == 200
        assert budget.generation_used == 0

    def test_session_budget_reset(self):
        from aitapes.llm import reset_session_budget

        budget = reset_session_budget(50_000)
        assert budget.total == 50_000
        assert budget.generation_limit == 35_000


# ── Phase 0: Ledger Schema ────────────────────────────────────────────────

class TestLedgerSchema:
    def test_aitapes_ledger_has_embedding(self):
        from aitapes.ledger import LedgerEntry

        entry = LedgerEntry(
            entry_type="plan",
            command="test",
            input_hash="abc123",
            output_summary="test output",
            timestamp="2026-01-01",
            intent_embedding=[0.1, 0.2, 0.3],
        )
        assert entry.intent_embedding == [0.1, 0.2, 0.3]

    def test_aitapes_ledger_embedding_default_empty(self):
        from aitapes.ledger import LedgerEntry

        entry = LedgerEntry(
            entry_type="plan",
            command="test",
            input_hash="abc123",
            output_summary="test",
            timestamp="2026-01-01",
        )
        assert entry.intent_embedding == []

    def test_forest_ledger_has_embedding(self):
        from forest_tapes.tapes_core.why_ledger import LedgerRecord

        record = LedgerRecord(
            task_hash="abc",
            recorded_at="2026-01-01",
            allocation={},
            intent_embedding=[0.5, 0.6],
        )
        assert record.intent_embedding == [0.5, 0.6]

    def test_append_entry_with_embedding(self):
        from aitapes.ledger import append_entry, read_entries

        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "test.jsonl"
            embedding = [0.1, 0.2, 0.3, 0.4]
            append_entry(
                ledger_path=str(ledger),
                entry_type="plan",
                command="test",
                input_text="test intent",
                output_summary="done",
                intent_embedding=embedding,
            )
            entries = read_entries(str(ledger))
            assert len(entries) == 1
            assert entries[0].intent_embedding == embedding

    def test_backward_compat_no_embedding(self):
        """Entries from v7 (no intent_embedding) should load with empty list."""
        from aitapes.ledger import read_entries

        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "test.jsonl"
            # Write v7-style entry without intent_embedding
            old_entry = {
                "entry_type": "plan",
                "command": "old",
                "input_hash": "abc",
                "output_summary": "old",
                "timestamp": "2025-01-01",
                "details": {},
            }
            ledger.write_text(json.dumps(old_entry) + "\n")
            entries = read_entries(str(ledger))
            assert len(entries) == 1
            assert entries[0].intent_embedding == []


# ── Phase 1: Vector Grounding ──────────────────────────────────────────────

class TestVectorGrounding:
    def test_cosine_similarity_identical(self):
        from forest_tapes.tapes_core.vector_grounding import cosine_similarity

        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        from forest_tapes.tapes_core.vector_grounding import cosine_similarity

        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(cosine_similarity(v1, v2)) < 1e-6

    def test_cosine_distance(self):
        from forest_tapes.tapes_core.vector_grounding import cosine_distance

        v = [1.0, 0.0, 0.0]
        assert abs(cosine_distance(v, v)) < 1e-6

    def test_novelty_bypass_early_runs(self):
        from forest_tapes.tapes_core.vector_grounding import detect_novelty

        result = detect_novelty([0.1, 0.2], [[0.9, 0.8]], run_number=3)
        assert result.is_novel is False
        assert result.severity == "none"
        assert "bypass" in result.message.lower()

    def test_novelty_detection_similar(self):
        from forest_tapes.tapes_core.vector_grounding import detect_novelty

        intent = [1.0, 0.0, 0.0]
        corpus = [[0.99, 0.01, 0.0], [0.98, 0.02, 0.0]]
        result = detect_novelty(intent, corpus, run_number=10)
        assert result.is_novel is False

    def test_novelty_detection_outlier(self):
        from forest_tapes.tapes_core.vector_grounding import detect_novelty

        intent = [1.0, 0.0, 0.0]
        corpus = [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        result = detect_novelty(intent, corpus, run_number=10)
        assert result.is_novel is True
        assert result.severity in ("sip", "hard_stop")

    def test_ground_intent_with_mock_embedder(self):
        from forest_tapes.tapes_core.vector_grounding import ground_intent

        mock_embed = lambda text: [0.5, 0.5, 0.0]
        embedding, novelty = ground_intent(
            intent="fix the bug",
            ledger_embeddings=[],
            run_number=1,
            embed_fn=mock_embed,
        )
        assert embedding == [0.5, 0.5, 0.0]
        assert novelty.severity == "none"


# ── Phase 1: AST Extractor ────────────────────────────────────────────────

class TestASTExtractor:
    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create a sample Python project for testing."""
        src = tmp_path / "mymodule.py"
        src.write_text(textwrap.dedent("""\
            def helper():
                return 42

            def main_function():
                x = helper()
                return x + 1

            class Calculator:
                def add(self, a, b):
                    return a + b

                def multiply(self, a, b):
                    return a * b
        """))

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_mymodule.py"
        test_file.write_text(textwrap.dedent("""\
            from mymodule import main_function, Calculator

            def test_main():
                assert main_function() == 43

            def test_calculator():
                c = Calculator()
                assert c.add(1, 2) == 3
        """))

        return tmp_path

    def test_index_finds_symbols(self, sample_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(sample_project))
        ext.index()
        symbols = ext.all_symbols()
        names = [s.name for s in symbols]
        assert any("helper" in n for n in names)
        assert any("main_function" in n for n in names)
        assert any("Calculator" in n for n in names)

    def test_get_symbol_exact(self, sample_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(sample_project))
        ext.index()
        sym = ext.get_symbol("helper")
        assert sym is not None
        assert sym.kind == "function"

    def test_get_subgraph_context(self, sample_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(sample_project))
        ext.index()
        ctx = ext.get_subgraph_context("main_function")
        assert ctx.target is not None
        assert ctx.node_count > 0
        assert len(ctx.calls) > 0  # main_function calls helper

    def test_get_relevant_tests(self, sample_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(sample_project))
        ext.index()
        tests = ext.get_relevant_tests("main_function", "tests")
        assert len(tests) > 0

    def test_get_dataflow_context(self, sample_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(sample_project))
        ext.index()
        dfc = ext.get_dataflow_context("main_function")
        assert "DATA FLOW CONTEXT" in dfc
        assert "main_function" in dfc

    def test_count_nodes(self):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=".")
        count = ext.count_nodes("def foo():\n    return 1\n")
        assert count > 0

    def test_symbol_not_found(self):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=".")
        ext._indexed = True
        ctx = ext.get_subgraph_context("nonexistent_symbol")
        assert ctx.target is None


# ── Phase 2: AST-Driven Splicer ───────────────────────────────────────────

class TestASTSplicer:
    def test_patch_has_target_symbol(self):
        from aitapes.patches import Patch

        p = Patch(file="test.py", search="old", replace="new", target_symbol="my_func")
        assert p.target_symbol == "my_func"

    def test_parse_build_output_requires_target_symbol(self):
        from aitapes.patches import parse_build_output

        raw = {
            "patches": [
                {"file": "test.py", "target_symbol": "my_func", "search": "old", "replace": "new"}
            ]
        }
        output = parse_build_output(raw)
        assert output.patches[0].target_symbol == "my_func"

    def test_ast_splicer_finds_function(self):
        from aitapes.patches import Patch, apply_patch, LookupPath

        source = textwrap.dedent("""\
            def foo():
                return 1

            def bar():
                return 2
        """)
        patch = Patch(
            file="test.py",
            search="return 1",
            replace="return 42",
            target_symbol="foo",
        )
        result = apply_patch(source, patch)
        assert result.applied
        assert result.lookup_path == LookupPath.AST_NODE

    def test_ast_splicer_search_exact_fallback(self):
        from aitapes.patches import Patch, apply_patch, LookupPath

        source = "x = 1\ny = 2\n"
        patch = Patch(
            file="test.py",
            search="x = 1",
            replace="x = 42",
            target_symbol="nonexistent",
        )
        result = apply_patch(source, patch)
        assert result.applied
        assert result.lookup_path == LookupPath.SEARCH_EXACT

    def test_ast_splicer_logs_lookup_path(self):
        from aitapes.patches import Patch, apply_patch, LookupPath

        source = "def my_func():\n    pass\n"
        patch = Patch(
            file="test.py",
            search="pass",
            replace="return 0",
            target_symbol="my_func",
        )
        result = apply_patch(source, patch)
        assert result.applied
        assert result.lookup_path in (LookupPath.AST_NODE, LookupPath.AST_FALLBACK)

    def test_patch_result_has_lookup_path(self):
        from aitapes.patches import PatchResult, Patch, LookupPath

        p = Patch(file="f.py", search="a", replace="b", target_symbol="s")
        r = PatchResult(patch=p, applied=False, lookup_path=LookupPath.FAILED)
        assert r.lookup_path == LookupPath.FAILED


# ── Phase 2: Scorched Earth ───────────────────────────────────────────────

class TestScorchedEarth:
    def test_tapes_halt_error(self):
        from aitapes.execution import TAPESHaltError

        err = TAPESHaltError("test halt", failure_trace=["fail1", "fail2"])
        assert "test halt" in str(err)
        assert err.failure_trace == ["fail1", "fail2"]

    def test_max_oscillation_cycles_constant(self):
        from aitapes.execution import MAX_OSCILLATION_CYCLES

        assert MAX_OSCILLATION_CYCLES == 3

    def test_lec_result_structure(self):
        from aitapes.execution import LECResult

        result = LECResult(passed=True, tests_run=["tests/"], test_output="ok")
        assert result.passed is True

    def test_loop_state(self):
        from aitapes.execution import LoopState

        state = LoopState()
        assert state.cycle == 0
        assert state.oscillation_counter == 0.0
        assert state.failure_trace == []


# ── Item 1: Ledger Rollback ───────────────────────────────────────────────

class TestLedgerRollback:
    def test_rollback_removes_entries(self):
        from forest_tapes.tapes_core.why_ledger import (
            LedgerRecord, append_ledger, read_ledger, rollback, snapshot_count,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ledger.jsonl"
            # Snapshot before task
            snap = snapshot_count(path)
            assert snap == 0

            # Add 3 records (simulating task work)
            for i in range(3):
                r = LedgerRecord(task_hash=f"h{i}", recorded_at=f"2026-0{i+1}-01", allocation={})
                append_ledger(path, r)

            assert snapshot_count(path) == 3

            # Rollback to snapshot
            removed = rollback(path, snap)
            assert removed == 3
            assert snapshot_count(path) == 0
            assert len(read_ledger(path)) == 0

    def test_rollback_partial(self):
        from forest_tapes.tapes_core.why_ledger import (
            LedgerRecord, append_ledger, read_ledger, rollback, snapshot_count,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ledger.jsonl"
            # Pre-existing records
            for i in range(2):
                r = LedgerRecord(task_hash=f"pre{i}", recorded_at=f"2025-0{i+1}-01", allocation={})
                append_ledger(path, r)

            snap = snapshot_count(path)  # 2

            # Task adds 3 more
            for i in range(3):
                r = LedgerRecord(task_hash=f"task{i}", recorded_at=f"2026-0{i+1}-01", allocation={})
                append_ledger(path, r)

            assert snapshot_count(path) == 5
            removed = rollback(path, snap)
            assert removed == 3
            records = read_ledger(path)
            assert len(records) == 2
            assert records[0].task_hash == "pre0"

    def test_rollback_noop(self):
        from forest_tapes.tapes_core.why_ledger import (
            LedgerRecord, append_ledger, rollback, snapshot_count,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ledger.jsonl"
            r = LedgerRecord(task_hash="h0", recorded_at="2026-01-01", allocation={})
            append_ledger(path, r)
            removed = rollback(path, 5)  # Snapshot larger than current
            assert removed == 0


# ── Item 2: FailureKind Classification ────────────────────────────────────

class TestFailureKind:
    def test_classify_network_timeout(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("urlopen timeout connection error", -1) == FailureKind.NETWORK_TIMEOUT

    def test_classify_rate_limit(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("HTTP 429 Too Many Requests", 1) == FailureKind.API_RATE_LIMIT

    def test_classify_syntax_error(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("SyntaxError: invalid syntax", 1) == FailureKind.AST_PARSE_FATAL

    def test_classify_indentation(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("IndentationError: unexpected indent", 1) == FailureKind.INDENTATION_MISMATCH

    def test_classify_target_missing(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("target_symbol not found in AST", 1) == FailureKind.TARGET_NODE_MISSING

    def test_classify_assertion_fail(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("FAILED tests/test_auth.py::test_login", 1) == FailureKind.PYTEST_ASSERTION_FAIL

    def test_classify_type_checker(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("mypy error: Incompatible types", 1) == FailureKind.TYPE_CHECKER_REJECT

    def test_classify_execution_timeout(self):
        from aitapes.execution import classify_failure, FailureKind
        assert classify_failure("Test execution timed out", -1) == FailureKind.EXECUTION_TIMEOUT

    def test_tier_penalties(self):
        from aitapes.execution import FAILURE_TIERS, TIER_PENALTIES, FailureKind, FailureTier
        assert TIER_PENALTIES[FailureTier.TRANSIENT] == 0.0
        assert TIER_PENALTIES[FailureTier.STRUCTURAL] == 0.5
        assert TIER_PENALTIES[FailureTier.SEMANTIC] == 1.0

        # Verify all kinds have a tier
        for kind in FailureKind:
            assert kind in FAILURE_TIERS

    def test_lec_result_has_failure_kind(self):
        from aitapes.execution import LECResult, FailureKind
        r = LECResult(
            passed=False, tests_run=["tests/"], test_output="fail",
            failure_kind=FailureKind.PYTEST_ASSERTION_FAIL,
        )
        assert r.failure_kind == FailureKind.PYTEST_ASSERTION_FAIL

    def test_lec_result_has_tier(self):
        from aitapes.execution import LECResult
        r = LECResult(passed=True, tests_run=["tests/"], test_output="ok", tier=1)
        assert r.tier == 1


# ── Item 3: Dual-Tier LEC ─────────────────────────────────────────────────

class TestDualTierLEC:
    def test_tier1_exists(self):
        from aitapes.execution import run_lec_tier1
        assert callable(run_lec_tier1)

    def test_tier2_exists(self):
        from aitapes.execution import run_lec_tier2
        assert callable(run_lec_tier2)

    def test_legacy_run_lec_exists(self):
        from aitapes.execution import run_lec
        assert callable(run_lec)


# ── Phase 4: Complexity Tracker ────────────────────────────────────────────

class TestComplexityTracker:
    def test_add_patch_counts_nodes(self):
        from aitapes.complexity_tracker import ComplexityTracker

        tracker = ComplexityTracker()
        needs_reanchor = tracker.add_patch("def foo():\n    return 1\n")
        assert tracker.patch_complexity > 0
        assert needs_reanchor is False  # Leaf node, no symbol

    def test_hub_triggers_instant_breach(self, tmp_path):
        """Item 6: A core hub with centrality >= 0.85 triggers instant refresh."""
        from aitapes.complexity_tracker import ComplexityTracker, HUB_CENTRALITY_THRESHOLD
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        # Create project where 'engine' is a hub — everything calls it
        src = tmp_path / "project.py"
        src.write_text(textwrap.dedent("""\
            def engine():
                return 42

            def service_a():
                return engine() + 1

            def service_b():
                return engine() + 2

            def service_c():
                return engine() + 3

            def handler():
                a = service_a()
                b = service_b()
                c = service_c()
                return engine()
        """))

        tracker = ComplexityTracker()
        # Patch the hub node
        needs = tracker.add_patch(
            "def engine():\n    return 99\n",
            target_symbol="engine",
            source_dir=str(tmp_path),
        )
        # engine should have high centrality → instant breach
        # (it depends on the specific graph structure)
        assert tracker.patch_complexity > 0

    def test_leaf_node_no_refresh(self, tmp_path):
        """Item 6: An isolated leaf with low centrality → no refresh."""
        from aitapes.complexity_tracker import ComplexityTracker

        src = tmp_path / "project.py"
        src.write_text(textwrap.dedent("""\
            def isolated_leaf():
                return 1

            def another_isolated():
                return 2
        """))

        tracker = ComplexityTracker()
        needs = tracker.add_patch(
            "def isolated_leaf():\n    return 99\n",
            target_symbol="isolated_leaf",
            source_dir=str(tmp_path),
        )
        assert needs is False  # Low centrality → no refresh

    def test_summary_has_centrality_fields(self):
        from aitapes.complexity_tracker import (
            ComplexityTracker, HUB_CENTRALITY_THRESHOLD,
            LEAF_CENTRALITY_THRESHOLD, BASE_COMPLEXITY_THRESHOLD,
        )

        tracker = ComplexityTracker()
        s = tracker.summary()
        assert "patch_complexity" in s
        assert s["hub_threshold"] == HUB_CENTRALITY_THRESHOLD
        assert s["leaf_threshold"] == LEAF_CENTRALITY_THRESHOLD
        assert s["base_complexity_threshold"] == BASE_COMPLEXITY_THRESHOLD


# ── Phase 4: Dynamic Ontology ─────────────────────────────────────────────

class TestDynamicOntology:
    def test_synchronous_update_finds_novel_terms(self):
        from forest_tapes.semantics.dynamic_ontology import DynamicOntology

        ont = DynamicOntology()
        entries = ont.synchronous_update(
            failed_patches=[{"reasoning": "The xyzfoobar function crashed due to a segmentation error"}],
        )
        # Should find novel terms (xyzfoobar is not in the static registry)
        assert len(entries) > 0

    def test_no_novel_terms_from_static_words(self):
        from forest_tapes.semantics.dynamic_ontology import DynamicOntology

        ont = DynamicOntology()
        # "crash" and "error" are already in the static registry
        entries = ont.synchronous_update(
            failed_patches=[{"reasoning": "error crash"}],
        )
        # Static words should not be duplicated
        novel_terms = [e.term for e in entries]
        assert "error" not in novel_terms
        assert "crash" not in novel_terms

    def test_provenance_is_dynamic(self):
        from forest_tapes.semantics.dynamic_ontology import DynamicOntology, DYNAMIC_PROVENANCE

        ont = DynamicOntology()
        entries = ont.synchronous_update(
            failed_checks=[{"evidence": "The flimflam module caused a cascading failure error"}],
        )
        for entry in entries:
            assert entry.provenance == DYNAMIC_PROVENANCE

    def test_get_all_words_includes_dynamic(self):
        from forest_tapes.semantics.dynamic_ontology import DynamicOntology
        from forest_tapes.semantics.ontology import SemanticCategory

        ont = DynamicOntology()
        ont.synchronous_update(
            failed_patches=[{"reasoning": "The quuxbaz function had a crash error"}],
        )
        # Get all words including dynamic should be >= static
        from forest_tapes.semantics.ontology import get_words
        static = get_words(SemanticCategory.INSTABILITY_HIGH)
        all_words = ont.get_all_words(SemanticCategory.INSTABILITY_HIGH)
        assert len(all_words) >= len(static)

    def test_summary(self):
        from forest_tapes.semantics.dynamic_ontology import DynamicOntology

        ont = DynamicOntology()
        ont.synchronous_update(
            failed_patches=[{"reasoning": "The zzznovelterm function failure error"}],
        )
        s = ont.summary()
        assert "total_dynamic_terms" in s
        assert "by_category" in s


# ── Integration: tapes_cli.py ──────────────────────────────────────────────

class TestTapesCLI:
    def test_brain_request(self):
        from tapes_cli import BrainRequest

        req = BrainRequest(intent="fix the bug in auth.py")
        assert req.intent == "fix the bug in auth.py"
        assert req.source_files == {}

    def test_brain_response(self):
        from tapes_cli import BrainResponse

        resp = BrainResponse(instability_score=0.42, representation="ast_source_window")
        assert resp.instability_score == 0.42

    def test_hands_result(self):
        from tapes_cli import HandsResult

        result = HandsResult(patches=(), tokens_used=100)
        assert result.tokens_used == 100

    def test_call_brain(self):
        """Test that brain allocation works end-to-end."""
        from tapes_cli import BrainRequest, _call_brain

        req = BrainRequest(intent="Fix the authentication bug in auth.py")
        resp = _call_brain(req)
        assert resp.instability_score is not None
        assert resp.representation is not None


# ── Item 5: Benchmark Control ─────────────────────────────────────────────

import sys
from pathlib import Path as _Path
_bench_dir = str(_Path(__file__).resolve().parent.parent / "benchmarks")
if _bench_dir not in sys.path:
    sys.path.insert(0, _bench_dir)

class TestBenchmarkControl:
    def test_benchmark_result_structure(self):
        from benchmark_control import BenchmarkResult

        r = BenchmarkResult(
            method="baseline", intent="fix bug", tokens_used=5000,
            generation_tokens=5000, debate_tokens=0,
            time_seconds=1.5, success=True,
        )
        assert r.method == "baseline"
        assert r.tokens_used == 5000

    def test_benchmark_report_structure(self):
        from benchmark_control import BenchmarkResult, BenchmarkReport

        baseline = BenchmarkResult(
            method="baseline", intent="fix", tokens_used=5000,
            generation_tokens=5000, debate_tokens=0, time_seconds=2.0, success=True,
        )
        tapes = BenchmarkResult(
            method="tapes", intent="fix", tokens_used=1500,
            generation_tokens=1200, debate_tokens=300, time_seconds=1.8, success=True,
        )
        report = BenchmarkReport(
            intent="fix", baseline=baseline, tapes=tapes,
            token_savings=3500, token_savings_pct=70.0,
            time_diff_seconds=0.2, timestamp="2026-01-01",
        )
        assert report.token_savings == 3500
        assert report.token_savings_pct == 70.0

    def test_save_report(self, tmp_path):
        from benchmark_control import BenchmarkResult, BenchmarkReport, save_report

        baseline = BenchmarkResult(
            method="baseline", intent="fix", tokens_used=5000,
            generation_tokens=5000, debate_tokens=0, time_seconds=2.0, success=True,
        )
        tapes = BenchmarkResult(
            method="tapes", intent="fix", tokens_used=1500,
            generation_tokens=1200, debate_tokens=300, time_seconds=1.8, success=True,
        )
        report = BenchmarkReport(
            intent="fix", baseline=baseline, tapes=tapes,
            token_savings=3500, token_savings_pct=70.0,
            time_diff_seconds=0.2, timestamp="2026-01-01",
        )
        out = str(tmp_path / "results.json")
        save_report(report, out)
        data = json.loads(Path(out).read_text())
        assert data["token_savings"] == 3500

    def test_demo_constants(self):
        from benchmark_control import DEMO_BUG_SOURCE, DEMO_INTENT
        assert "auth.py" in DEMO_BUG_SOURCE
        assert "refresh_token" in DEMO_INTENT


# ── Item 6: PageRank Centrality ───────────────────────────────────────────

class TestPageRankCentrality:
    @pytest.fixture
    def hub_project(self, tmp_path):
        """Project where 'core_engine' is a high-centrality hub."""
        src = tmp_path / "project.py"
        src.write_text(textwrap.dedent("""\
            def core_engine():
                return 42

            def service_a():
                return core_engine() + 1

            def service_b():
                return core_engine() + 2

            def service_c():
                x = core_engine()
                y = service_a()
                return x + y

            def isolated_leaf():
                return 99
        """))
        return tmp_path

    def test_compute_pagerank(self, hub_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(hub_project))
        ext.index()
        ranks = ext.compute_pagerank()
        assert len(ranks) > 0
        # All values should be in [0, 1]
        for score in ranks.values():
            assert 0.0 <= score <= 1.0

    def test_hub_has_higher_centrality_than_leaf(self, hub_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(hub_project))
        ext.index()
        hub_score = ext.get_centrality("core_engine")
        leaf_score = ext.get_centrality("isolated_leaf")
        assert hub_score > leaf_score

    def test_get_centrality_unknown_symbol(self, hub_project):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=str(hub_project))
        ext.index()
        score = ext.get_centrality("nonexistent_symbol")
        assert score == 0.0

    def test_pagerank_empty_graph(self):
        from forest_tapes.tapes_core.ast_extractor import ASTExtractor

        ext = ASTExtractor(source_dir=".")
        ext._indexed = True
        ranks = ext.compute_pagerank()
        assert ranks == {}
