# TAPES — Final Hackathon Video Plan (≈ 4:00)

> **Source data:** bob-session-report.md
> (8 scenarios · ibm/granite-13b-chat-v2 via watsonx · 2026-05-16)

---

## Recording Setup

| Item | Value |
|------|-------|
| Tool | OBS Studio (or any screen recorder) |
| Resolution | 1920 × 1080, 60 fps |
| Terminal | Windows Terminal, dark theme, **22 pt** font |
| Color scheme | Green / cyan on black (hacker aesthetic) |
| Mic | Lapel or condenser, pop filter, quiet room |
| Slides | **None** — everything lives in the terminal + overlays |

### Environment (run before hitting record)

```powershell
$env:AITAPES_PROVIDER = "watsonx"
$env:IBM_BOB_PROJECT_ID = "bob-prod"
$env:IBM_BOB_API_KEY = "<key>"
cd "C:\Users\bhara\Downloads\TAPES IBM BOB"
```

---

## Scene Breakdown

---

### SCENE 1 — COLD OPEN HOOK (0:00 – 0:10)

**On screen:** Black background. Single stat fades in, large white text:

```
81% fewer tokens.
$5.95 saved per session.
Zero production damage.
```

**Narration (V/O):**

> *"What if every AI code change was governed, sandboxed, and audited — automatically?"*

**Post-production:**
- Fade-in animation on text (0.5s per line, staggered)
- Subtle ambient synth pad under the voiceover

---

### SCENE 2 — THE PROBLEM (0:10 – 0:35)

**On screen:** Terminal. Run a pre-recorded `git diff` scrolling over multiple files — red deletions in `legacy_auth.py`, `payment.py`, `config.py`.

**Narration:**

> *"You give an AI one instruction. It rewrites six files — your auth core, your payment handler, your config. You spend more tokens fixing what it broke than building what you wanted."*

*[Pause — highlight a red deletion in legacy_auth.py]*

> *"The AI isn't wrong. It's unconstrained. No scope limits. No governance. In production, one bad AI patch is a compliance incident."*

*[Terminal clears. Title card overlay for 2 seconds:]*

```
TAPES — Token-Aware Programming Engineering System
IBM BobShell · Governance Pipeline · Hackathon 2026
```

**B-roll / overlay notes:**
- Yellow highlight box around `legacy_auth.py` deletions
- Title card: centered, bold serif font, subtle slide-up animation

---

### SCENE 3 — WHAT IS TAPES (0:35 – 1:00)

**On screen:** Terminal. Type out the pipeline diagram live (or paste quickly):

```
Your Intent
  → Plan    (bounded contract — lock scope, files, symbols)
  → Prepare (retrieval shaping — skeletons, not full files)
  → Build   (IBM BobShell generates SEARCH/REPLACE patches)
  → Bouncer (intercepts protected files, redirects or blocks)
  → Sandbox (apply in isolation → run tests → verify)
  → Commit  (atomic write — only if ALL gates pass)
  → Ledger  (every operation logged in JSONL audit trail)
```

**Narration:**

> *"TAPES. Seven gates between AI intent and production code."*
>
> *"IBM BobShell generates the code. TAPES governs what BobShell sees, validates what BobShell produces, tests it in a sandbox, and only commits verified patches."*
>
> *"Contract locks the scope. Bouncer intercepts protected files. Sandbox rejects broken patches. Ledger records everything. Seven gates — every patch must clear all seven."*

**B-roll / overlay notes:**
- Each pipeline stage highlights in sequence (green glow) as narrator mentions it
- Keep the diagram on screen for the full 25 seconds

---

### SCENE 4 — RAW BOBSHELL DEMO (1:00 – 1:45)

**On screen:** Terminal. Run Phase 1 of `video_benchmark.py`.

```powershell
python scripts/video_benchmark.py
```

*Phase 1 runs automatically — Raw BobShell, no governance.*

**Narration (while Phase 1 runs):**

> *"Same intent. Same project. First — Raw BobShell. No TAPES. No governance. Bob decides its own fate."*

*[Wait for output. Point at key lines:]*

> *"There. legacy_auth.py — modified. Protected authentication code. Bob didn't know it was protected. Bob didn't care."*

*[Highlight the results:]*

```
Protected file modified?   YES (BAD!)
```

> *"Protected file modified. Auth module compromised. This is what ships without governance — no audit trail, no rollback, no safety net."*

**B-roll / overlay notes:**
- Red pulsing border around "YES (BAD!)" line
- Optional: brief cutaway showing the actual diff in `legacy_auth.py`

---

### SCENE 5 — TAPES + BOBSHELL DEMO (1:45 – 2:30)

**On screen:** Terminal. Phase 2 runs automatically after Phase 1.

**Narration:**

> *"Same intent. Same AI. Now — TAPES plus BobShell."*

*[BobShell session ID appears]*

> *"Session ID — real IBM BobShell, ibm/granite-13b-chat-v2 on watsonx. Bob is running — inside TAPES."*

*[BOUNCER INTERCEPT fires]*

> *"BOUNCER INTERCEPT. Bob tried to modify legacy_auth.py — same as before. Same AI, same instinct. TAPES caught it. File is byte-identical. Untouched."*

*[Tests pass. Results table prints.]*

> *"Tests pass. Protected file safe. Same Bob. Same intent. One breaks production. One doesn't."*

**B-roll / overlay notes:**
- Green pulsing border around "NO (PROTECTED)" line
- Green checkmark overlay on "Tests passing: True"
- Split-screen moment (optional): Raw result left, TAPES result right

---

### SCENE 6 — FULL BENCHMARK TABLE (2:30 – 3:05)

**On screen:** Hold the final results table from the session report (or show as overlay graphic):

```
                        Raw BobShell      TAPES + BobShell     Savings
─────────────────────── ────────────────  ──────────────────  ──────────
Total tokens consumed    2,910,000         530,000             81%
Total cost               $7.29             $1.34               $5.95
Protected files modified 8/8               0/8                 100% safe
Bouncer intercepts       —                 26                  —
Bad patches blocked      —                 20                  —
Patches redirected       —                 6                   —
Legitimate patches OK    —                 6                   —
```

**Narration:**

> *"Eight adversarial scenarios. Protected file massacre. Mutation flood. Syntax bomb. Path traversal. Multi-protected blast. Every scenario designed to break production."*

*[Pause 2 seconds on table]*

> *"Raw BobShell modified protected files in eight out of eight scenarios. TAPES blocked every single violation — 26 bouncer intercepts, 20 blocked, 6 safely redirected to sidecar extension files."*

> *"81% token reduction. $5.95 saved. And six legitimate patches still flowed through — security doesn't mean blocking everything."*

**B-roll / overlay notes:**
- Animate rows appearing one at a time (0.3s each)
- Flash the "81%" and "$5.95" in gold/highlight color
- Hold the full table for at least 4 seconds so judges can read it

---

### SCENE 7 — HOW IT WORKS (TECHNICAL) (3:05 – 3:35)

**On screen:** Terminal. Quick walkthrough of the pipeline internals.

**Option A — Show the code structure:**
```powershell
tree aitapes /F
```

**Option B — Show a bouncer intercept log:**
```powershell
cat .bob/tapes-audit-ledger.jsonl | Select-String "BOUNCER"
```

**Narration:**

> *"Under the hood: the Bouncer scans every patch against a protected-files map. Any patch touching legacy_auth, payment, or config is intercepted — blocked or redirected to a safe extension file."*

> *"The Sandbox applies patches in isolation first. Tests run against the sandbox copy. Only when everything passes does TAPES commit atomically. On failure — sandbox destroyed, real repo untouched."*

> *"Every operation — plan, build, bouncer, sandbox, apply — is recorded in a JSONL audit ledger. Full replayability from a single file."*

**B-roll / overlay notes:**
- Highlight `bouncer.py`, `execution.py`, `ledger.py` in the tree output
- Show 2–3 ledger entries scrolling by (fast)

---

### SCENE 8 — THE CLOSE (3:35 – 4:00)

**On screen:** Black background. White text, one line at a time.

**Narration (slow, deliberate delivery):**

> *"The AI will keep getting more powerful."*

*[Pause 1s]*

> *"Codebases will keep getting more complex."*

*[Pause 1s]*

> *"The stakes will keep getting higher."*

*[Pause 2s]*

> *"The question was never whether AI can write code."*

*[Pause 1s]*

> *"The question was whether you can trust it."*

*[Pause 2s]*

> *"TAPES answers that question."*

*[Pause 1s]*

> *"IBM BobShell as the brain. TAPES as the trust layer."*

*[Pause 2s. Final line — one word at a time, bold:]*

> **"Constrain everything. Guess nothing. Ship once."**

*[Hard cut to black. Hold 3 seconds. End.]*

**Post-production:**
- Each text line fade-in, centered
- Final tagline: larger font, slight zoom effect
- Optional: project URL / team name in bottom corner during final black

---

## Full Timing Map

| Scene | Time | On Screen | Action |
|-------|------|-----------|--------|
| 1 — Cold Open | 0:00 – 0:10 | Black + animated stats | V/O hook |
| 2 — Problem | 0:10 – 0:35 | Terminal: git diff scrolling | V/O + highlight |
| 3 — Architecture | 0:35 – 1:00 | Terminal: pipeline diagram | V/O explainer |
| 4 — Raw BobShell | 1:00 – 1:45 | Terminal: Phase 1 running | Live demo |
| 5 — TAPES + Bob | 1:45 – 2:30 | Terminal: Phase 2 running | Live demo |
| 6 — Benchmark | 2:30 – 3:05 | Results table (overlay/terminal) | V/O + hold |
| 7 — Technical | 3:05 – 3:35 | Terminal: code structure / ledger | V/O walkthrough |
| 8 — Close | 3:35 – 4:00 | Black + text | V/O + tagline |

---

## Commands for Recording

### Scene 4 + 5 (covers both phases automatically)
```powershell
python scripts/video_benchmark.py
```

### Scene 7 — Option A (project structure)
```powershell
tree aitapes /F
```

### Scene 7 — Option B (audit ledger)
```powershell
Get-Content .bob\tapes-audit-ledger.jsonl | Select-String "BOUNCER"
```

### Backup — Run tests standalone
```powershell
pytest tests/test_benchmarks.py -q
```

---

## Three Lines Judges Will Remember

1. *"Same BobShell. Same AI. Same intent. One breaks production. One doesn't."*
2. *"The question was never whether AI can write code. The question was whether you can trust it."*
3. *"Constrain everything. Guess nothing. Ship once."*

---

## Key Numbers to Emphasize

| Stat | Value | When to say it |
|------|-------|----------------|
| Token reduction | **81%** | Scene 1 (hook), Scene 6 (table) |
| Cost saved | **$5.95** per session | Scene 1 (hook), Scene 6 (table) |
| Protected violations blocked | **8/8 → 0/8** | Scene 5 (demo), Scene 6 (table) |
| Bouncer intercepts | **26** | Scene 6 (table) |
| Bad patches blocked | **20** | Scene 6 (table) |
| Patches redirected safely | **6** | Scene 6 (table) |
| Legitimate patches approved | **6** | Scene 6 (table) |

---

## Post-Production Checklist

- [ ] Record terminal sessions (Scenes 2, 4, 5, 7)
- [ ] Record voiceover for all 8 scenes
- [ ] Create title card overlay (Scene 2)
- [ ] Create cold-open stats animation (Scene 1)
- [ ] Create results table overlay or terminal output (Scene 6)
- [ ] Create closing text cards (Scene 8)
- [ ] Add highlight boxes (red for raw failures, green for TAPES protections)
- [ ] Add background music (low ambient synth, duck under narration)
- [ ] Review timing — total should land between 3:45 and 4:15
- [ ] Export: MP4, H.264, 1080p, 60fps
- [ ] Watch once without audio to check visual pacing
- [ ] Watch once without video to check narration flow
- [ ] Final export and upload

---

## Visual Style Guide

| Element | Style |
|---------|-------|
| Terminal background | Pure black (`#000000`) |
| Terminal text | Green (`#00FF41`) or cyan (`#00D4FF`) |
| Highlight — danger | Red border pulse (`#FF3333`) |
| Highlight — safe | Green border pulse (`#33FF57`) |
| Overlay text | White (`#FFFFFF`) on black, Inter or JetBrains Mono |
| Stats callout | Gold (`#FFD700`) |
| Title card | Serif bold, centered, slide-up animation |
| Transitions | Hard cut (no wipes, no fades between scenes — except Scene 1 fade-in) |
