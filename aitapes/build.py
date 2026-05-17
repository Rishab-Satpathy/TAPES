"""tapes build - Bounded Implementation (IBM Bob Integration)

Bob generates patches. TAPES governs execution.

Architecture:
    TAPES plan -> Contract -> Bob generates patches -> TAPES check -> pass/fail
                                    |                           |
                                    +-- rollback on failure ----+

Bob generates code; TAPES validates and rolls back
when Bob produces invalid patches.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .bob import BobConfig, BobSession
from .contract import Contract
from .llm import LLMConfig
from .ledger import append_entry
from .patches import (
    BuildOutput,
    Patch,
    apply_patches,
    format_patches_as_text,
    format_uncertainties,
    parse_build_output,
)
from .prompts import SYSTEM_BUILD, build_build_prompt


def run_build(
    contract_path: str = "tapes-contract.json",
    source_dir: str = ".",
    output_path: str = "tapes-patches.json",
    ledger_path: str = "tapes-ledger.jsonl",
    config: LLMConfig | None = None,
    auto_apply: bool = False,
    offline: bool = False,
    is_greenfield: bool = False,
    mock_db_flag: bool = False,
    speculative: bool = False,
    bob_config: BobConfig | None = None,
) -> tuple[BuildOutput, Any]:
    """Run the build command with IBM Bob as patch generator.

    Args:
        contract_path: Path to the contract JSON.
        source_dir: Directory containing source files.
        output_path: Where to save patches.
        ledger_path: Where to record the decision.
        config: LLM configuration.
        auto_apply: If True, apply patches automatically.
        offline: If True, return empty build output (for testing).
        bob_config: IBM Bob configuration.

    Returns:
        Tuple of (BuildOutput, BobSessionReport).
    """
    # Initialize IBM Bob session
    bob = BobSession(config=bob_config)
    print(f"  [BobShell] Session: {bob.session_id}")
    print(f"  [BobShell] Mode: code")
    print(f"  [BobShell] Model: {bob.config.model_id}")

    # Load contract
    contract = Contract.load(contract_path)
    print(f"  Contract: {contract.intent[:60]}")
    print(f"  Mutation boundary: {contract.mutation_boundary}")

    # Read source files
    source_path = Path(source_dir)
    source_files: dict[str, str] = {}

    if contract.target_files:
        for f in contract.target_files:
            full = source_path / f
            if full.exists():
                source_files[f] = full.read_text(encoding="utf-8")
            else:
                print(f"  [!] Target file not found: {f}")
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
        print("  [offline mode] Returning empty build output...")
        output = BuildOutput(patches=(), uncertainties=(), assumptions=())
        report = bob.end_session(status="offline")
    else:
        # Feature 3: Adversarial TDD via Live Debate (optional, disabled by default)
        use_debate = False
        try:
            from aitapes.experimental.live_debate import run_live_debate
            use_debate = True
        except ImportError:
            run_live_debate = None

        from forest_tapes.tapes_core.ast_extractor import ASTExtractor
        from .execution import run_lec_tier1

        extractor = ASTExtractor(source_dir=source_dir)
        ast_ctx = ""
        df_ctx = ""

        provider = (config or LLMConfig.from_env()).provider
        # Adversarial TDD via Live Debate (optional, disabled by default if experimental import fails or watsonx provider)
        debate_res = None
        if use_debate and provider != "watsonx":
            from forest_tapes.tapes_core.models import RiskAssessment, RiskTier
            from forest_tapes.tapes_core.drift_mapper import extract_expected_nodes
            expected = extract_expected_nodes(contract.intent, extractor)
            target_symbol = list(expected)[0] if expected else ""
            ast_ctx = extractor.get_subgraph_context(target_symbol).summary if target_symbol else ""
            df_ctx = extractor.get_dataflow_context(target_symbol) if target_symbol else ""
            print("  [Adversarial TDD] Running live debate for RequiredTests...")
            try:
                debate_res = run_live_debate(
                    contract=contract,
                    proposal=contract.intent,
                    risk=RiskAssessment(tier=RiskTier.MEDIUM, score=0.5),
                    ast_subgraph_context=ast_ctx,
                    dataflow_context=df_ctx,
                    is_greenfield=is_greenfield,
                    config=config,
                )
            except Exception:
                debate_res = None

        if debate_res and debate_res.required_tests:
            test_content = "\n".join(debate_res.required_tests)
            test_file = source_path / "test_temp.py"
            test_file.write_text(test_content, encoding="utf-8")
            print("  [Adversarial TDD] Executing Tier-1 LEC against RequiredTests...")
            try:
                lec_res = run_lec_tier1(source_dir=source_dir, patches=[], test_files=["test_temp.py"])
                if lec_res.passed:
                    print("  [Adversarial TDD] WARNING: Tests passed unexpectedly. Red-Green-Refactor violated.")
                else:
                    print("  [Adversarial TDD] Confirmed failure. Greenlight for Surgeon.")
            finally:
                if test_file.exists():
                    test_file.unlink()

        # -- Bob generates patches ---------------------------------------------
        system_instructions = SYSTEM_BUILD
        if mock_db_flag:
            system_instructions += "\n\n[DB GUARDIAN] Database mutation detected. Wrap execution in ephemeral rollback transaction."

        print(f"\n  [BobShell] Asking Bob to generate patches...")
        bob_patches = bob.generate_patches(
            contract=contract,
            source_files=source_files,
            system_prompt=system_instructions,
        )

        patches_list = []
        for bp in bob_patches:
            if bp.search is not None and bp.replace is not None and bp.file:
                patches_list.append(Patch(
                    file=bp.file,
                    search=bp.search,
                    replace=bp.replace,
                    target_symbol=bp.target_symbol,
                    reasoning=bp.reasoning,
                ))

        output = BuildOutput(
            patches=tuple(patches_list),
            uncertainties=(),
            assumptions=(),
        )

        for p in output.patches:
            if not p.target_symbol:
                bob.record_rejection(p.file, "Missing target_symbol")
                print(f"    [REJECT] {p.file}: Missing target_symbol")

        report = bob.end_session(status="completed")
        report_path = Path(source_dir) / "bob-session-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        if report:
            report_path.write_text(report.to_markdown(), encoding="utf-8")
            print(f"  [BobShell] Session report saved to: {report_path}")
        else:
            print("  [BobShell] No session report (offline mode)")

    # Print summary
    print(f"\n  Patches: {len(output.patches)}")
    for i, p in enumerate(output.patches, 1):
        print(f"    {i}. {p.file}: {p.reasoning[:50]}")

    if output.uncertainties:
        print(f"\n  Uncertainties: {len(output.uncertainties)}")
        for u in output.uncertainties:
            print(f"    [{u.confidence:.0%}] {u.claim[:50]}")

    if output.assumptions:
        print(f"\n  Assumptions made: {len(output.assumptions)}")

    # Apply patches if requested - use sandbox copy of source dir
    if auto_apply and output.patches:
        print(f"\n  Applying patches...")
        with tempfile.TemporaryDirectory(prefix="tapes_build_") as tmp:
            sandbox = Path(tmp) / "sandbox"
            shutil.copytree(source_dir, sandbox, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", ".git"))
            results = apply_patches(str(sandbox), list(output.patches))
            applied = sum(1 for r in results if r.applied)
            failed = sum(1 for r in results if not r.applied)
            print(f"    Applied: {applied}, Failed: {failed}")
            for r in results:
                if r.applied:
                    bob.record_patch_applied()
                else:
                    print(f"    [FAIL] {r.patch.file}: {r.error}")
                    bob.record_rejection(r.patch.file, r.error or "Patch application failed")
            # Copy patched files back to real source dir
            if applied > 0 and failed == 0:
                for r in results:
                    if r.applied:
                        src = sandbox / r.patch.file
                        dst = Path(source_dir) / r.patch.file
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if src.exists():
                            shutil.copy2(str(src), str(dst))

    # Record in ledger
    append_entry(
        ledger_path=ledger_path,
        entry_type="build",
        command="tapes build (bob)",
        input_text=contract.intent,
        output_summary=f"{len(output.patches)} patches (Bob), {len(output.uncertainties)} uncertainties",
        details={
            "patches_count": len(output.patches),
            "uncertainties_count": len(output.uncertainties),
            "assumptions_count": len(output.assumptions),
            "files_affected": list(set(p.file for p in output.patches)),
            "bob_session_id": report.session_id if report else None,
            "bob_tokens": report.total_tokens if report else 0,
            "bob_invalid_patches": report.invalid_patches_caught if report else 0,
        },
    )

    print()
    return output, report
