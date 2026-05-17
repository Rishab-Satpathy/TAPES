import json
import pytest
from unittest.mock import patch
from pathlib import Path
from tapes_cli import run_tapes_pipeline
from forest_tapes.tapes_core.models import TaskContract, TaskType, MutationType

@pytest.fixture
def mock_repo(tmp_path):
    source_dir = tmp_path / "mock_repo"
    source_dir.mkdir()
    
    # Create a basic file to patch
    main_py = source_dir / "main.py"
    main_py.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    
    return source_dir

def test_end_to_end_mock_pipeline(mock_repo):
    """
    Feature 1: End-to-End Mock Harness.
    Mocks LLM APIs, executes real file-system, AST math, and state machine.
    """
    ledger_path = mock_repo / "tapes-ledger.jsonl"
    contract_path = mock_repo / "tapes-contract.json"
    patches_path = mock_repo / "tapes-patches.json"
    
    # Mock LLM calls
    def mock_call_llm_json(prompt, *args, **kwargs):
        if "Stabilize requirements" in prompt or "Convert this user intent" in prompt:
            return {
                "intent": "Change hello to return tapes",
                "constraints": [],
                "forbidden_assumptions": [],
                "success_criteria": [],
                "missing_information": [],
                "stakes": "low",
                "mutation_boundary": "exact_patch",
                "target_files": ["main.py"]
            }
        elif "Implement the following contract" in prompt:
            return {
                "patches": [{
                    "file": "main.py",
                    "target_symbol": "main.hello",
                    "search": "return 'world'",
                    "replace": "return 'tapes'",
                    "reasoning": "Requested behavior."
                }],
                "uncertainty": [],
                "assumptions_made": []
            }
        elif "Validate the following code" in prompt:
            return {
                "checks": [{"criterion": "Returns tapes", "status": "pass", "evidence": "Saw return tapes", "file": "main.py"}],
                "hallucinations": [],
                "mutation_locality": {"assessment": "local"},
                "overall": "pass",
                "summary": "Passed."
            }
        elif "You are Alpha" in prompt or "You are Omega" in prompt or "Judge agent" in prompt:
            return {
                "vote": "accept",
                "confidence": 0.9,
                "findings": [],
                "rationale": "Looks good.",
                "RequiredTests": ["def test_hello(): assert hello() == 'tapes'"]
            }
        elif "Analyze these recent failures" in prompt:
            return {"mitigations": ["Be careful."]}
        return {}

    with patch('aitapes.llm.call_llm_json', side_effect=mock_call_llm_json):
        # We also need to mock `call_llm_json` inside forest_tapes if it's there, but actually forest_tapes doesn't call LLM directly for allocation, wait, allocate_cognition might call it? No, allocate_cognition uses heuristics.
        
        # Run pipeline
        result = run_tapes_pipeline(
            intent="Change hello to return tapes in main.py",
            source_dir=str(mock_repo),
            ledger_path=str(ledger_path),
            contract_path=str(contract_path),
            patches_path=str(patches_path),
            auto_apply=True,
            offline=False
        )
        
        # Assert determinism and state
        assert result["plan"]["status"] == "ok"
        assert result["build"]["patches"] == 1
        assert result["check"]["overall"] == "pass"
        
        # Verify file changed
        content = (mock_repo / "main.py").read_text()
        assert "return 'tapes'" in content
        
        # Verify ledger exists
        assert ledger_path.exists()
        
        # In Feature 3, we implemented L1 Hashmap. So verify ledger is written to disk correctly
        ledger_content = ledger_path.read_text().strip()
        assert ledger_content.startswith("[")  # Strict JSON array
        
        data = json.loads(ledger_content)
        assert len(data) > 0
        assert any(e["entry_type"] == "build" for e in data)
