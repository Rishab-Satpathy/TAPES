"""Continuous Ontology Evolution (Self-Tuning Prompts) for TAPES v8.0/v9.0.

Implements the Meta-Prompt Compiler.
"""
from __future__ import annotations

import json
from pathlib import Path
from aitapes.ledger import get_entries_by_type

STATE_FILE = "tapes-meta-state.json"

def _get_counter(source_dir: str) -> int:
    state_path = Path(source_dir) / STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text()).get("meta_prompt_counter", 0)
        except Exception:
            return 0
    return 0

def _set_counter(source_dir: str, value: int) -> None:
    state_path = Path(source_dir) / STATE_FILE
    state_path.write_text(json.dumps({"meta_prompt_counter": value}))

def update_meta_prompt_counter(
    source_dir: str, 
    ledger_path: str,
    centrality: float, 
    is_greenfield: bool
) -> None:
    """Increment counter based on centrality/greenfield and trigger compilation if >= 50."""
    counter = _get_counter(source_dir)
    
    if is_greenfield or centrality >= 0.85:
        counter += 5
    elif centrality > 0.10:
        counter += 3
    else:
        counter += 1
        
    if counter >= 50:
        print("  [META-PROMPT COMPILER] Counter >= 50. Triggering ontology evolution...")
        _compile_meta_prompt(source_dir, ledger_path)
        counter = 0
        
    _set_counter(source_dir, counter)

def _compile_meta_prompt(source_dir: str, ledger_path: str) -> None:
    """Fetch recent failures, summarize mitigations, and append to Surgeon prompt."""
    from aitapes.llm import call_llm_json, LLMConfig
    
    # Fetch failure logs (we look for "execution" or "check" failures in ledger)
    entries = get_entries_by_type(ledger_path, "execution")
    recent_failures = []
    # Just take last 50 execution entries
    for e in entries[-50:]:
        if e.details and "failure_kind" in e.details:
            recent_failures.append({
                "kind": e.details["failure_kind"],
                "error": e.details.get("error", "")
            })
            
    if not recent_failures:
        print("  [META-PROMPT COMPILER] No failures found. Skipping.")
        return
        
    print(f"  [META-PROMPT COMPILER] Analyzing {len(recent_failures)} recent failures...")
    
    prompt = "Analyze these recent failures and provide 3 brief mitigations to prevent them in the future:\n"
    prompt += json.dumps(recent_failures, indent=2)
    
    system = "You are the TAPES Meta-Prompt Compiler. Extract 3 frequent systemic errors and their mitigations. Respond with JSON: {'mitigations': ['mitigation 1', ...]}"
    
    try:
        raw = call_llm_json(prompt, system=system)
        mitigations = raw.get("mitigations", [])
        if mitigations:
            _append_to_prompts(ledger_path, mitigations)
            print("  [META-PROMPT COMPILER] Successfully appended new rules to ledger.")
    except Exception as e:
        print(f"  [META-PROMPT COMPILER] Compilation failed: {e}")

def _append_to_prompts(ledger_path: str, mitigations: list[str]) -> None:
    """Append mitigations to the strictly typed JSON schema in the B-Tree Ledger."""
    from aitapes.ledger import append_entry
    append_entry(
        ledger_path,
        entry_type="meta_prompt",
        command="compiler",
        input_text="",
        output_summary="Evolved new prompt mitigations",
        details={"mitigations": mitigations}
    )
