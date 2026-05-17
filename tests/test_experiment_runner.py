from forest_tapes.tapes_core.experiment_runner import build_same_model_experiment_prompt


def test_same_model_experiment_prompt_contains_raw_and_tapes_versions() -> None:
    pair = build_same_model_experiment_prompt(
        {
            "task": "Patch auth.py without broad rewrite",
            "explicit_constraints": ["exact patch only"],
            "success_criteria": ["file is not rewritten"],
        }
    )
    assert pair.raw_prompt == "Patch auth.py without broad rewrite"
    assert "TAPES COGNITION ANCHOR" in pair.tapes_prompt
    assert "exact patch only" in pair.tapes_prompt
    assert "Same model" in pair.stabilization_claim
