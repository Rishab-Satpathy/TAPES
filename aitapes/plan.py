"""tapes plan - Requirement Stabilization

Converts vague user intent into a locked contract.
Applies TAPES pressure: detects ambiguity, forces clarity.
"""

from __future__ import annotations

from typing import Any

from .contract import Contract, create_contract, validate_contract
from .llm import LLMConfig, call_llm_json
from .ledger import append_entry
from .prompts import SYSTEM_PLAN, build_plan_prompt


def run_plan(
    user_input: str,
    output_path: str = "tapes-contract.json",
    ledger_path: str = "tapes-ledger.jsonl",
    config: LLMConfig | None = None,
    offline: bool = False,
) -> Contract:
    """Run the plan command.

    Args:
        user_input: User's description of what they want.
        output_path: Where to save the contract.
        ledger_path: Where to record the decision.
        config: LLM configuration. If None, reads from environment.
        offline: If True, create contract without LLM (for testing).

    Returns:
        The stabilized contract.
    """
    print(f"\n{'='*60}")
    print("  TAPES PLAN - Requirement Stabilization")
    print(f"{'='*60}\n")

    if offline:
        print("  [offline mode] Creating contract without LLM...")
        contract = _create_offline_contract(user_input)
    else:
        print(f"  Stabilizing intent: {user_input[:80]}...")
        raw = call_llm_json(build_plan_prompt(user_input), config=config, system=SYSTEM_PLAN)
        contract = Contract.from_dict(raw)

    # Validate
    issues = validate_contract(contract)
    if issues:
        print(f"\n  [!] Contract issues:")
        for issue in issues:
            print(f"    - {issue}")

    # Save contract
    contract.save(output_path)
    print(f"\n  [OK] Contract saved to: {output_path}")

    # Record in ledger
    append_entry(
        ledger_path=ledger_path,
        entry_type="plan",
        command="tapes plan",
        input_text=user_input,
        output_summary=f"Contract created: {contract.intent[:60]}",
        details={
            "intent": contract.intent,
            "constraints_count": len(contract.constraints),
            "missing_count": len(contract.missing_information),
            "stakes": contract.stakes,
            "mutation_boundary": contract.mutation_boundary,
        },
    )

    # Print summary
    print(f"\n  Intent: {contract.intent}")
    if contract.constraints:
        print(f"  Constraints: {', '.join(contract.constraints[:3])}")
    if contract.missing_information:
        print(f"  Missing: {', '.join(contract.missing_information)}")
    print(f"  Stakes: {contract.stakes}")
    print(f"  Mutation: {contract.mutation_boundary}")
    if contract.target_files:
        print(f"  Target files: {', '.join(contract.target_files)}")
    print()

    return contract


def _create_offline_contract(user_input: str) -> Contract:
    """Create a contract without LLM (for testing/offline mode)."""
    # Simple heuristic contract creation
    constraints: list[str] = []
    stakes = "low"
    mutation = "local_edit"
    missing: list[str] = []

    text = user_input.lower()

    # Detect stakes
    if any(w in text for w in ("production", "security", "payment", "auth", "legal")):
        stakes = "high"
    elif any(w in text for w in ("important", "review", "release")):
        stakes = "medium"

    # Detect mutation scope
    if any(w in text for w in ("rewrite", "full", "entire", "all files")):
        mutation = "broad_rewrite"
    elif any(w in text for w in ("refactor", "restructure")):
        mutation = "refactor"
    elif any(w in text for w in ("patch", "search", "replace", "exact")):
        mutation = "exact_patch"

    # Detect constraints from input
    if "no " in text:
        # Extract "no X" patterns
        import re
        no_patterns = re.findall(r"no\s+(\w+(?:\s+\w+)?)", text)
        constraints = [f"Do not {p}" for p in no_patterns[:5]]

    if not constraints:
        constraints = ["Follow existing code style"]
        missing.append("explicit_constraints")

    success = []
    if "test" in text:
        success.append("Code passes existing tests")
    if "fix" in text or "bug" in text:
        success.append("Bug is resolved")
    if not success:
        success.append("Implementation matches intent")
        missing.append("success_criteria")

    forbidden = [
        "Do not invent files, APIs, or functions not present in evidence.",
        "Do not broaden mutation scope beyond the declared target.",
    ]
    if mutation != "broad_rewrite":
        forbidden.append("Do not perform broad rewrites.")

    # Detect target files
    import re
    file_matches = re.findall(r"[\w./\\-]+\.(?:py|js|ts|tsx|jsx|java|go|rs)\b", user_input)
    target_files = list(dict.fromkeys(file_matches))  # deduplicate while preserving order

    return Contract(
        intent=user_input.strip(),
        constraints=tuple(constraints),
        forbidden_assumptions=tuple(forbidden),
        success_criteria=tuple(success),
        missing_information=tuple(missing),
        stakes=stakes,
        mutation_boundary=mutation,
        target_files=tuple(target_files),
    )
