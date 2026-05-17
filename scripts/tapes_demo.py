from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forest_tapes.tapes_core import allocate_cognition
from forest_tapes.tapes_core.experiment_runner import build_same_model_experiment_prompt
from forest_tapes.tapes_core.pressure_kernel import RuntimeSignals


def main() -> None:
    task = "Patch auth.py token refresh bug with exact search replace, do not rewrite the file."
    task_input = {
        "task": task,
        "explicit_constraints": ["exact patch only", "do not broaden scope"],
        "success_criteria": ["stale token is cleared"],
    }
    result = allocate_cognition(
        task_input,
        environment={"local_models": ["llama.cpp/local"], "api_models": ["ibm/granite-13b-chat-v2"]},
    )
    pair = build_same_model_experiment_prompt(task_input)
    print("TAPES allocation")
    print(f"representation={result.representation.value}")
    print(f"instability={result.instability.score}")
    print(f"boundary={result.boundary.action.value}")
    print(f"backend={result.backend.kind.value}:{result.backend.name}")
    print(f"validation={result.validation.level.value}")
    print()
    print("Same-model experiment prompts")
    print(f"raw_prompt={pair.raw_prompt}")
    print("tapes_prompt_start=")
    print(pair.tapes_prompt[:800])
    print()
    print("Pressure enforcement demo")
    pressured = allocate_cognition(
        "full rewrite auth.py",
        runtime_signals=RuntimeSignals(broad_rewrite_attempted=True, patch_attempts=3, patch_failures=2),
    )
    print(f"mutation_surface={pressured.scope.mutation_surface.value}")
    print(f"allowed_assumptions={pressured.scope.allowed_assumptions}")
    print(f"validation={pressured.validation.level.value}")


if __name__ == "__main__":
    main()
