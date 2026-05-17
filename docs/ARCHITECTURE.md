# TAPES Architecture

## Pipeline

```
┌───────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  ANALYZE  │ → │  PLAN   │ → │  BUILD  │ → │  APPLY  │
│           │    │         │    │         │    │         │
│ execution │    │ contract│    │ patches │    │ validate│
│ analysis  │    │ create  │    │ generate│    │ & write │
└───────────┘    └─────────┘    └─────────┘    └─────────┘
```

## Stage 1: Analyze

Analyzes the intent to determine scope and risk:

- **Complexity Estimate** (0.0–1.0): How complex/risky is this task?
- **Context Strategy**: What retrieval strategy best fits? (AST window, data flow, etc.)
- **Rationale**: Why this strategy was chosen

## Stage 2: Plan

Converts vague intent into a locked Contract:

- **Intent**: One-sentence clear statement
- **Constraints**: Tight, specific rules
- **Success Criteria**: Testable outcomes
- **Mutation Boundary**: exact_patch / local_edit / refactor / broad_rewrite
- **Target Files**: Specific files to modify

## Stage 3: Build

Generates SEARCH/REPLACE patches:

- **Online**: IBM watsonx.ai (Granite models) via Bob integration
- **Offline**: AST-based code transformation (no API keys needed)

Patches are precise — they target specific AST nodes, not full file rewrites.

## Stage 4: Apply

- Validates search strings exist in target files
- Splices replacements using AST node positions
- Creates `.bak` backups before modifying
- Reports applied/failed per patch

## Terminal UI

The `tapes` command opens a Claude Code-style terminal interface:

```
 TAPES · repo · main · offline
─────────────────────────────────
  You
╭───────────────────────────────╮
│ add validation to login       │
╰───────────────────────────────╯
  TAPES
╭───────────────────────────────╮
│  Planning                     │
│    contract bounded           │
│  Building                     │
│    2 patches generated        │
│  Testing                      │
│    passed                     │
│  Executing                    │
│    committed safely           │
╰───────────────────────────────╯
─────────────────────────────────
  ● offline  ·  $0.010
```

## Key Design Decisions

| Decision | Why |
|----------|-----|
| AST-based splicing | Precise, verifiable code changes |
| SEARCH/REPLACE format | Human-readable, LLM-friendly |
| Backup before write | Always reversible |
| Offline fallback | Demo-ready without API keys |
| Sandbox testing | Prevents unsafe patches from reaching filesystem |
