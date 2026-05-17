"""Prompt templates for AITAPES commands.

Each template is designed to:
1. Reduce ambiguity (TAPES pressure)
2. Force structured output (not free-form text)
3. Include forbidden assumptions (anti-hallucination)
4. Specify mutation boundaries (patch discipline)
"""

from __future__ import annotations

from pathlib import Path
from .contract import Contract


SYSTEM_PLAN = """You are a requirement stabilization engine.
Your job is to convert vague user intent into a precise, locked contract.

RULES:
1. Do NOT guess. If information is missing, mark it in missing_information.
2. Do NOT broaden scope. Keep constraints tight.
3. Every success criterion must be testable.
4. Every forbidden assumption must be explicit.
5. Respond with VALID JSON only. No markdown."""

SYSTEM_BUILD = """You are a bounded implementation engine.
Your job is to produce SEARCH/REPLACE patches that implement the contract.

RULES:
1. Output ONLY SEARCH/REPLACE patches in the specified format.
2. Each SEARCH string must be EXACT text from the source file.
3. Do NOT guess file contents. If you haven't seen the file, say so.
4. Do NOT rewrite entire files. Use targeted patches.
5. Each patch must include reasoning.
6. Respond with VALID JSON only. No markdown."""

SYSTEM_CHECK = """You are a validation engine.
Your job is to compare code against a contract and find violations.

RULES:
1. Check every success criterion against the actual code.
2. Check for hallucinated APIs, functions, or imports.
3. Check mutation locality (did the code change more than necessary?).
4. Respond with VALID JSON only. No markdown."""


def build_plan_prompt(user_input: str) -> str:
    """Build the prompt for tapes plan."""
    return f"""Convert this user intent into a stabilized contract.

USER INPUT:
{user_input}

OUTPUT FORMAT (JSON):
{{
    "intent": "one-sentence clear intent",
    "constraints": ["constraint 1", "constraint 2"],
    "forbidden_assumptions": ["assumption 1", "assumption 2"],
    "success_criteria": ["testable criterion 1", "testable criterion 2"],
    "missing_information": ["info 1", "info 2"],
    "stakes": "low|medium|high",
    "mutation_boundary": "none|exact_patch|local_edit|refactor|broad_rewrite",
    "target_files": ["file1.py", "file2.py"]
}}

IMPORTANT:
- If the user input is vague, put the vagueness in missing_information.
- If the user input mentions specific files, put them in target_files.
- Default stakes to "low" unless security/production/payment mentioned.
- Default mutation_boundary to "local_edit" unless explicitly broader.
- Add forbidden assumptions about not inventing things not in evidence."""


def build_build_prompt(contract: Contract, source_files: dict[str, str], spatial_neighborhood: str = "", ledger_path: str = "") -> str:
    """Build the prompt for tapes build."""
    files_context = ""
    for path, content in source_files.items():
        # Clip to first 200 lines per file for token efficiency
        lines = content.splitlines()
        if len(lines) > 200:
            clipped = "\n".join(lines[:200])
            files_context += f"\n--- {path} (clipped to 200 lines) ---\n{clipped}\n"
        else:
            files_context += f"\n--- {path} ---\n{content}\n"

    # Evolved Ontology Rules (Feature 5) from Ledger
    mitigations_text = ""
    if ledger_path:
        from .ledger import get_entries_by_type
        try:
            meta_entries = get_entries_by_type(ledger_path, "meta_prompt")
            active_mitigations = []
            for e in meta_entries:
                if e.details and "mitigations" in e.details:
                    active_mitigations.extend(e.details["mitigations"])
            if active_mitigations:
                # Deduplicate while preserving order
                active_mitigations = list(dict.fromkeys(active_mitigations))
                mitigations_text = "\n[EVOLVED ONTOLOGY RULES]\n" + "\n".join(f"- {m}" for m in active_mitigations)
        except Exception:
            pass

    return f"""Implement the following contract by producing SEARCH/REPLACE patches.

CONTRACT:
Intent: {contract.intent}
Constraints: {', '.join(contract.constraints)}
Success Criteria: {', '.join(contract.success_criteria)}
Forbidden Assumptions: {', '.join(contract.forbidden_assumptions)}
Mutation Boundary: {contract.mutation_boundary}
Target Files: {', '.join(contract.target_files) if contract.target_files else 'any affected files'}

SPATIAL NEIGHBORHOOD:
{spatial_neighborhood or 'No spatial map available.'}

SOURCE FILES:
{files_context}

OUTPUT FORMAT (JSON):
{{
    "patches": [
        {{
            "file": "path/to/file.py",
            "target_symbol": "module.ClassName.method_name or module.function_name",
            "search": "exact text to find",
            "replace": "replacement text",
            "reasoning": "why this change implements the contract"
        }}
    ],
    "uncertainty": [
        {{
            "claim": "what you're uncertain about",
            "confidence": 0.0-1.0,
            "evidence": "what evidence exists",
            "alternative": "what else might be true"
        }}
    ],
    "assumptions_made": ["list of assumptions if any were required"]
}}

RULES:
- SEARCH must be EXACT text from the source file.
- target_symbol MUST identify the function, method, or class being patched.
- Do NOT guess file contents. Only patch files you've seen.
- Each patch must be self-contained (one logical change).
- If you need to see more of a file, note it in uncertainty.
- Reject broad rewrites unless mutation_boundary is "broad_rewrite".
{mitigations_text}"""


def build_check_prompt(contract: Contract, source_files: dict[str, str]) -> str:
    """Build the prompt for tapes check."""
    files_context = ""
    for path, content in source_files.items():
        files_context += f"\n--- {path} ---\n{content}\n"

    return f"""Validate the following code against this contract.

CONTRACT:
Intent: {contract.intent}
Constraints: {', '.join(contract.constraints)}
Success Criteria: {', '.join(contract.success_criteria)}
Forbidden Assumptions: {', '.join(contract.forbidden_assumptions)}
Mutation Boundary: {contract.mutation_boundary}

CODE:
{files_context}

OUTPUT FORMAT (JSON):
{{
    "checks": [
        {{
            "criterion": "success criterion being checked",
            "status": "pass|fail|partial",
            "evidence": "what you found in the code",
            "file": "file where evidence was found"
        }}
    ],
    "hallucinations": [
        {{
            "type": "api|function|import|file",
            "name": "what was hallucinated",
            "file": "where it appears",
            "evidence": "why it's hallucinated"
        }}
    ],
    "mutation_locality": {{
        "score": 0.0-1.0,
        "files_changed": ["list of files"],
        "total_lines_changed": 0,
        "assessment": "local|moderate|broad"
    }},
    "overall": "pass|fail",
    "summary": "one-sentence summary of validation result"
}}

RULES:
- Check EVERY success criterion individually.
- Look for imports that don't exist in the source files provided.
- Look for function calls that weren't defined.
- Measure how many files were changed and by how much.
- Be strict: if a criterion isn't clearly met, mark it as fail."""


def build_review_prompt(code: str, contract: Contract) -> str:
    """Build a review prompt for Claude-style code review."""
    return f"""Review this code against the contract. Be critical.

CONTRACT:
Intent: {contract.intent}
Constraints: {', '.join(contract.constraints)}
Success Criteria: {', '.join(contract.success_criteria)}

CODE:
```python
{code}
```

Check for:
1. Logic correctness
2. Design compliance
3. Security issues
4. Edge cases
5. Performance

Output JSON:
{{
    "verdict": "approved|needs_changes|critical_issues",
    "issues": [
        {{
            "severity": "critical|major|minor",
            "category": "logic|design|security|edge_case|performance",
            "description": "what's wrong",
            "fix": "how to fix it"
        }}
    ],
    "score": 0-10
}}"""
