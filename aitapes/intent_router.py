"""Two-Track Intent Router for TAPES v8.0/v9.0.

Feature 5: Calculates computational scope via Track 1 (Physics) and Track 2 (Style).
Uses idiom_matrix.json for dynamic budget multipliers.
"""

import json
from pathlib import Path
from dataclasses import dataclass

IDIOM_MATRIX_PATH = Path(__file__).parent.parent / "forest_tapes" / "tapes_core" / "idiom_matrix.json"

@dataclass
class RoutingResult:
    base_budget: int
    blast_radius: str
    lexical_directives: list[str]
    multiplier: float

def ensure_idiom_matrix():
    if not IDIOM_MATRIX_PATH.exists():
        default_matrix = {
            "python": 1.0,
            "rust": 2.5,
            "c++": 2.0,
            "typescript": 1.5,
            "javascript": 1.2
        }
        IDIOM_MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
        IDIOM_MATRIX_PATH.write_text(json.dumps(default_matrix, indent=2))

def analyze_intent(intent: str, subgraph_ctx) -> RoutingResult:
    """Run Track 1 (Physics) and Track 2 (Style)."""
    matrix = {}
    try:
        ensure_idiom_matrix()
        matrix = json.loads(IDIOM_MATRIX_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        matrix = {"python": 1.0, "rust": 2.5, "c++": 2.0, "typescript": 1.5, "javascript": 1.2}
    
    # Track 1: Physics [Depth, Dependencies, Dependents]
    depth = subgraph_ctx.node_count if subgraph_ctx else 0
    dependencies = len(subgraph_ctx.calls) if subgraph_ctx else 0
    dependents = len(subgraph_ctx.callers) if subgraph_ctx else 0
    
    # Base Budget
    base_budget = 1000 + (depth * 2) + (dependencies * 50) + (dependents * 50)
    
    # Blast Radius
    blast_radius = "local"
    if dependents > 10:
        blast_radius = "broad"
    elif dependents > 3:
        blast_radius = "moderate"
        
    # Track 2: Style (NLP pass)
    lexical_directives = []
    lower_intent = intent.lower()
    if "fast" in lower_intent or "perform" in lower_intent:
        lexical_directives.append("Prioritize performance and execution speed.")
    if "secure" in lower_intent or "safe" in lower_intent:
        lexical_directives.append("Prioritize security and validate all inputs.")
    if "clean" in lower_intent or "readabl" in lower_intent:
        lexical_directives.append("Prioritize readability and clean code principles.")
        
    # The Matrix multiplier
    multiplier = matrix.get("python", 1.0) # Assume python for now
    if "rust" in lower_intent:
        multiplier = matrix.get("rust", 2.5)
        
    final_budget = int(base_budget * multiplier)
    
    return RoutingResult(
        base_budget=final_budget,
        blast_radius=blast_radius,
        lexical_directives=lexical_directives,
        multiplier=multiplier
    )

def daemon_update_idiom_matrix(ledger_path: str | Path):
    """Background daemon to update multipliers every 100 runs based on persistent ledger."""
    try:
        from .ledger import get_entries_by_type
        build_entries = get_entries_by_type(ledger_path, "build")
        run_count = len(build_entries)
    except Exception:
        return
        
    if run_count > 0 and run_count % 100 == 0:
        # Calculate failure rate over the last 100 runs
        recent = build_entries[-100:]
        failed = sum(1 for e in recent if getattr(e, "details", {}).get("failed", 0) > 0)
        failure_rate = failed / 100.0
        
        ensure_idiom_matrix()
        matrix = json.loads(IDIOM_MATRIX_PATH.read_text())
        
        # If failure rate is high (>0.3), increase multiplier for python to give more budget
        if failure_rate > 0.3:
            matrix["python"] = round(matrix.get("python", 1.0) * 1.1, 2)
        elif failure_rate < 0.1:
            matrix["python"] = round(matrix.get("python", 1.0) * 0.95, 2)
            
        IDIOM_MATRIX_PATH.write_text(json.dumps(matrix, indent=2))
