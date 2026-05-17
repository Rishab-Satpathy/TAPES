# TAPES

**T**oken-**A**ware **P**rogramming **E**ngineering **S**ystem

Bob generates the code. TAPES controls what Bob sees, validates what Bob changes, tests it safely in a sandbox, and only commits verified patches.

---

## Architecture

```
Your Intent
  → Plan (bounded contract)
  → Prepare (retrieval shaping + skeletons)
  → Build (IBM BobShell patch generation)
  → Validate (bouncer gates + AST anchor check)
  → Execute (sandbox → test → atomic commit)
  → Result (unified diff shown)
```

*Deterministic local transforms are used as fallback when BobShell is unavailable.*

## How It Works

### 1. Bounded Execution
Before any code generation, TAPES narrows: allowed files, allowed symbols, mutation scope, operation type. TAPES minimizes repository exposure through bounded retrieval shaping.

### 2. Retrieval Shaping
Instead of dumping entire files, TAPES converts unrelated code into hollow skeletons (signatures only) and expands only the target function being modified. This is the largest token reduction.

### 3. Patch Governance
All changes are SEARCH/REPLACE patches — never full file rewrites. Every patch is validated against the actual AST before touching the filesystem.

### 4. Bouncer
Protected files (e.g., `legacy_auth.py`) cannot be modified. When the AI targets a protected file, the Bouncer intercepts and redirects the patch to a safe extension file. A mutation boundary gate also blocks patches that touch too many files at once.

### 5. Sandbox Validation
Patches are applied to a sandbox copy first. Tests run against the sandbox. Only if everything passes does TAPES commit the changes atomically. On failure, the sandbox is destroyed and the real repo is untouched.

### 6. Deterministic Transforms
Many operations (add docstrings, inject validation, extract constants) use AST parsing and codemods — zero LLM calls, zero hallucination risk.

---

## Quick Start

```bash
# Install
pip install -e .
pip install pytest    # for running tests

# Run the demo
tapes "add validation to login"
python scripts/demo.py

# Run tests
pytest tests/test_benchmarks.py -q
# Expected: 63 passed
```

## Commands

| What | How |
|------|-----|
| One-shot pipeline | `tapes "add validation to login"` |
| With explicit intent flag | `tapes --intent "add docstrings"` |
| Dry run (analyze only) | `tapes --intent "refactor auth" --dry-run` |
| Interactive shell | `tapes` |
| Full demo | `python scripts/demo.py` |
| Run tests | `pytest tests/test_benchmarks.py -q` |

## IBM Bob Integration

IBM BobShell (`bob.cmd`) provides adaptive patch generation. TAPES constrains what BobShell sees, validates what BobShell produces, tests it in a sandbox, and commits only verified patches.

```bash
# Set env vars (BobShell active when AITAPES_PROVIDER=watsonx):
export AITAPES_PROVIDER=watsonx
export IBM_BOB_API_KEY="your-key"
export IBM_BOB_PROJECT_ID="your-project-id"

# BobShell now powers generation:
tapes "add validation to login"
# Shows: [BobShell] Session: bob-...  [BobShell] Model: ibm/granite-13b-chat-v2
```

BobShell receives only the bounded contract and prepared context — never the whole repository. When BobShell is unavailable, deterministic local transforms are used as fallback ("Deterministic transformer active" shown in terminal).

## Demo Script

```bash
# Success path:
tapes "add None validation to login handlers"
# Shows: Planning → Building → Testing → Executing → diff → safe commit

# Rollback path (validation failure):
python scripts/demo.py
# Shows: invalid patch caught, sandbox destroyed, repo untouched

# Check BobShell is active:
# Look for "[BobShell] Session:" in build output, or "Deterministic transformer active" for fallback
```

## Provider Support

IBM watsonx is the primary provider (via BobShell). A provider abstraction layer supports additional backends for development and testing.

## Benchmark

```
Token compression:    64%
Patches applied:      34/34 (100%)
Production scenarios: 6/6 passed
Tests:                63 passing
```

## Project Structure

```
aitapes/           → Production runtime (plan, prepare, build, patches, bouncer, tui)
forest_tapes/      → Internal heuristics (retrieval, allocation, pressure kernel)
_demo_project/     → Demo project (legacy_auth, auth_routes, config)
benchmarks/        → Benchmark scripts
tests/             → 63 tests
```
