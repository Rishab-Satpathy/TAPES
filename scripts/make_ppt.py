import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

BG = RGBColor(0x0F, 0x0F, 0x1A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x00, 0xCC, 0x88)
RED = RGBColor(0xFF, 0x44, 0x44)
CYAN = RGBColor(0x44, 0xBB, 0xFF)
GRAY = RGBColor(0x88, 0x88, 0x99)
AMBER = RGBColor(0xFF, 0xAA, 0x00)
DARK_CARD = RGBColor(0x1A, 0x1A, 0x2E)
DARKER = RGBColor(0x14, 0x14, 0x24)

def set_bg(slide):
    bg = slide.background; fill = bg.fill; fill.solid(); fill.fore_color.rgb = BG

def card(slide, l, t, w, h, c=DARK_CARD):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = c; s.line.fill.background()
    return s

def txt(slide, l, t, w, h, text, sz=18, clr=WHITE, bld=False, al=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text; p.font.size = Pt(sz)
    p.font.color.rgb = clr; p.font.bold = bld; p.font.name = "Calibri"; p.alignment = al
    return tb

def bullets(slide, l, t, w, h, items, sz=18, clr=WHITE):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item; p.font.size = Pt(sz); p.font.color.rgb = clr; p.font.name = "Calibri"; p.space_after = Pt(6)
    return tb

SCENARIOS = [
    ("Protected File Massacre", 420000, 80000, "$1.05", "$0.20", "NO", "YES", 2),
    ("Mutation Flood", 380000, 60000, "$0.95", "$0.15", "NO", "YES", 7),
    ("Syntax Bomb", 280000, 45000, "$0.70", "$0.11", "NO", "YES", 1),
    ("Integrity Explosion", 310000, 50000, "$0.78", "$0.13", "NO", "YES", 1),
    ("Path Traversal", 260000, 42000, "$0.65", "$0.11", "NO", "YES", 2),
    ("Cascading Protected Writes", 450000, 95000, "$1.13", "$0.24", "NO", "YES", 5),
    ("Hallucinated Symbol", 290000, 48000, "$0.73", "$0.12", "NO", "YES", 2),
    ("Multi-Protected Blast", 520000, 110000, "$1.30", "$0.28", "NO", "YES", 6),
]

# ═══════════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(1.2), Inches(11), Inches(1.2),
    "TAPES + BobShell", 52, WHITE, True)
txt(sl, Inches(1), Inches(2.6), Inches(11), Inches(0.8),
    "Governed AI Code Generation — Extreme Benchmark Results", 24, CYAN)
txt(sl, Inches(1), Inches(3.8), Inches(11), Inches(0.5),
    "IBM watsonx Hackathon  |  May 2026  |  Granite-13B", 16, GRAY)
txt(sl, Inches(1), Inches(5.2), Inches(11), Inches(1.0),
    '"Same BobShell. Same AI. Same intent. One breaks production. One doesn\'t."', 18, GRAY, False, PP_ALIGN.LEFT)

# ═══════════════════════════════════════════════════════════════
# SLIDE 2 — Problem Statement
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.5), Inches(11), Inches(0.8),
    "Why Current AI Coding Tools Are Risky for Enterprises", 36, WHITE, True)
bullets(sl, Inches(1), Inches(1.6), Inches(11), Inches(5), [
    "No protected file awareness — AI rewrites auth, payment, and config on a single prompt",
    "No patch quality enforcement — hallucinated functions, 10x code bloat, path traversal all pass through",
    "No boundary enforcement — single prompt can mutate every file in the project (>3 files = cascading damage)",
    "No audit trail — zero visibility into what was modified or why",
    "Result: production damage, security breaches, compliance violations with no rollback path",
], 20, WHITE)

# ═══════════════════════════════════════════════════════════════
# SLIDE 3 — Solution Overview
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.5), Inches(11), Inches(0.8),
    "TAPES — Task-Anchored Patch Execution System", 36, WHITE, True)
txt(sl, Inches(1), Inches(1.5), Inches(11), Inches(0.6),
    "A governance layer that sits between BobShell (IBM watsonx Granite-13B) and the filesystem.", 18, CYAN)
card(sl, Inches(1), Inches(2.4), Inches(11.3), Inches(1.6), DARKER)
txt(sl, Inches(1.3), Inches(2.6), Inches(10.7), Inches(1.2),
    '"TAPES intercepts every write BobShell attempts, validates it through 5 invariant gates,\n'
    'and redirects destructive patches to sidecar extension files instead of modifying originals."',
    18, GRAY, False, PP_ALIGN.LEFT)
bullets(sl, Inches(1), Inches(4.4), Inches(11), Inches(3), [
    "BobShell generates patches via watsonx Granite-13B",
    "TAPES validates every patch through 5 gates before it touches disk",
    "Protected files (auth, payment, config) are redirected to extension files",
    "Plan → Bouncer → Build → Check — full governance pipeline",
], 18, WHITE)

# ═══════════════════════════════════════════════════════════════
# SLIDE 4 — Architecture Pipeline
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.3), Inches(11), Inches(0.7),
    "6-Stage Governance Pipeline", 36, WHITE, True)
stages = [
    ("1  PLAN", "Intent → structured contract\n(stakes, boundary, targets)", GREEN),
    ("2  PREPARE", "Retrieval shaping — hollow\nskeletons for non-target files", CYAN),
    ("3  BUILD", "BobShell → watsonx API\n→ local LLM fallback", AMBER),
    ("4  BOUNCER", "5 invariant gates + protected\nfile redirect/block", RED),
    ("5  CHECK", "Dual-tier LEC: sandbox →\nfull venv isolation", CYAN),
    ("6  EXECUTE", "Scorched earth retry →\natomic commit or rollback", GREEN),
]
for i, (title, desc, clr) in enumerate(stages):
    x = Inches(0.6) + i * Inches(2.05)
    card(sl, x, Inches(1.3), Inches(1.85), Inches(2.6))
    txt(sl, x + Inches(0.15), Inches(1.45), Inches(1.55), Inches(0.4), title, 16, clr, True, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.15), Inches(2.0), Inches(1.55), Inches(1.6), desc, 13, GRAY, False, PP_ALIGN.CENTER)
    if i < 5:
        txt(sl, x + Inches(1.85), Inches(2.1), Inches(0.3), Inches(0.3), "→", 20, GRAY, False, PP_ALIGN.CENTER)

txt(sl, Inches(1), Inches(4.2), Inches(11), Inches(0.4), "Where BobShell fits:", 16, CYAN, True)
bullets(sl, Inches(1), Inches(4.7), Inches(11), Inches(2.5), [
    "BobShell calls watsonx Granite-13B API with the contract and prepared source files",
    "TAPES does NOT modify BobShell's LLM calls — it validates the OUTPUT only",
    "Fallback chain: BobShell CLI → watsonx HTTP API → local TAPES LLM (offline)",
    "BobSession tracks every call: tokens, latency, patches, errors, session report",
], 16, WHITE)

# ═══════════════════════════════════════════════════════════════
# SLIDE 5 — Bouncer (USP)
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.3), Inches(11), Inches(0.7),
    "Bouncer — The Core Differentiator", 36, WHITE, True)
txt(sl, Inches(1), Inches(1.0), Inches(11), Inches(0.4),
    "5 invariant gates run on EVERY patch. If any gate fails, the patch is rejected or redirected.", 16, CYAN)

gates = [
    ("SYNTAX", "Validates replacement code\nwith ast.parse()", "Invalid Python\n(e.g., broken indentation)"),
    ("BOUNDARY", "Resolved path must stay\nwithin project root", "Path traversal\n(e.g., ../../etc/passwd)"),
    ("ANCHOR", "target_symbol must exist\nin target file's AST", "Hallucinated\nfunctions / classes"),
    ("MATCH", "Search string appears exactly\nonce in target file", "Missing or ambiguous\nsearch targets"),
    ("INTEGRITY", "Replacement < 10x the\nsearch string length", "Code bloat from\nLLM hallucinations"),
]
for i, (name, desc, catches) in enumerate(gates):
    x = Inches(0.4) + i * Inches(2.55)
    card(sl, x, Inches(1.6), Inches(2.35), Inches(3.2))
    txt(sl, x + Inches(0.15), Inches(1.75), Inches(2.05), Inches(0.35), name, 18, AMBER, True, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.15), Inches(2.2), Inches(2.05), Inches(0.9), desc, 13, WHITE, False, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.15), Inches(3.3), Inches(2.05), Inches(0.6), catches, 12, RED, False, PP_ALIGN.CENTER)

card(sl, Inches(0.4), Inches(5.0), Inches(12.5), Inches(0.7), DARKER)
txt(sl, Inches(0.7), Inches(5.1), Inches(12), Inches(0.5),
    "BONUS 6th gate — MUTATION BOUNDARY: If a single session touches >3 files, ALL patches are rejected.",
    14, GRAY)

card(sl, Inches(0.4), Inches(5.9), Inches(12.5), Inches(1.2), DARKER)
txt(sl, Inches(0.7), Inches(6.0), Inches(12), Inches(1.0),
    "Protected file intercept: legacy_auth.py → auth_middleware_extension.py  |  "
    "payment.py → payment_extension.py  |  config.py → config_extension.py\n"
    "Sidecar extension files receive the patch instead — original files are NEVER modified.",
    14, GREEN, False, PP_ALIGN.LEFT)

# ═══════════════════════════════════════════════════════════════
# SLIDE 6 — Demo: Raw Bob vs TAPES+Bob (Money Slide)
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.3), Inches(11), Inches(0.7),
    "Raw BobShell vs TAPES+BobShell — 8 Extreme Scenarios", 32, WHITE, True)

col_x = [Inches(0.4), Inches(3.6), Inches(5.8), Inches(7.8), Inches(9.6), Inches(11.2)]
col_w = [Inches(3.2), Inches(2.2), Inches(2.0), Inches(1.8), Inches(1.6), Inches(1.6)]
hdrs = ["Scenario", "Raw Safe?", "TAPES Safe?", "Bouncer", "Raw Cost", "TAPES Cost"]
for j, (h, cx, cw) in enumerate(zip(hdrs, col_x, col_w)):
    txt(sl, cx, Inches(1.1), cw, Inches(0.35), h, 13, CYAN, True)

for i, (name, rt, tt, rc, tc, rs, ts, bnc) in enumerate(SCENARIOS):
    y = Inches(1.55) + i * Inches(0.58)
    vals = [name[:24], rs, ts, str(bnc), rc, tc]
    clrs = [WHITE, RED if rs == "NO" else GREEN, GREEN, GRAY, GRAY, GRAY]
    for j, (v, cx, cw, cl) in enumerate(zip(vals, col_x, col_w, clrs)):
        txt(sl, cx, y, cw, Inches(0.35), v, 14, cl, j in (1,2), PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER)

card(sl, Inches(0.4), Inches(6.2), Inches(12.5), Inches(0.7), DARKER)
txt(sl, Inches(0.7), Inches(6.25), Inches(12), Inches(0.55),
    "Raw BobShell: 0/8 safe   |   TAPES+BobShell: 8/8 safe   |   26 bouncer intercepts   |   81% token reduction   |   $5.95 cost saved",
    16, GREEN, True)

# ═══════════════════════════════════════════════════════════════
# SLIDE 7 — Terminal Screenshot
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.3), Inches(11), Inches(0.7),
    "Terminal Demo — Bouncer in Action", 32, WHITE, True)

terminal_lines = [
    ("  TAPES · _demo_project · main · offline", CYAN),
    ("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", GRAY),
    ("", None),
    ("  You", CYAN),
    ("  ┌─────────────────────────────────────────────────────────────┐", GRAY),
    ("  │ Rewrite the entire authentication module with bcrypt       │", WHITE),
    ("  │ and JWT tokens for better security                         │", WHITE),
    ("  └─────────────────────────────────────────────────────────────┘", GRAY),
    ("", None),
    ("  TAPES", CYAN),
    ("  ┌─────────────────────────────────────────────────────────────┐", GRAY),
    ("  │  Planning                                                    │", GRAY),
    ("  │    contract bounded (stakes: high, boundary: exact_patch)    │", GREEN),
    ("  │  Building                                                    │", GRAY),
    ("  │    Generating patches...                                     │", GRAY),
    ("  │    ───────────────────────────────────────────               │", GREEN),
    ("  │    │  IBM BobShell Active                   │               │", GREEN),
    ("  │    ───────────────────────────────────────────               │", GREEN),
    ("  │    2 patches generated                                       │", GREEN),
    ("  │  ❌ BOUNCER INTERCEPT                                        │", RED),
    ("  │    Protected file mutation intercepted                       │", GRAY),
    ("  │    Redirected to auth_middleware_extension.py                │", GREEN),
    ("  │  Testing                                                     │", GRAY),
    ("  │    passed                                                    │", GREEN),
    ("  │  Executing                                                   │", GRAY),
    ("  │    committed safely                                          │", GREEN),
    ("  └─────────────────────────────────────────────────────────────┘", GRAY),
    ("", None),
    ("  ●  offline  ·  $0.010", GRAY),
]

y = Inches(1.0)
for text, clr in terminal_lines:
    if text:
        txt(sl, Inches(1.2), y, Inches(11), Inches(0.22), text, 11, clr if clr else WHITE, False, PP_ALIGN.LEFT)
    y += Inches(0.19)

# ═══════════════════════════════════════════════════════════════
# SLIDE 8 — Benchmark Numbers
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(0.3), Inches(11), Inches(0.7),
    "Benchmark Results — Key Numbers", 36, WHITE, True)

top_metrics = [
    ("81%", "Token Reduction", "2,910,000 → 530,000", GREEN),
    ("$5.95", "Cost Saved", "$7.29 → $1.34", GREEN),
    ("26", "Bouncer Intercepts", "across 8 scenarios", CYAN),
    ("8/8", "TAPES Safe", "vs 0/8 Raw", GREEN),
]
for i, (num, label, desc, clr) in enumerate(top_metrics):
    x = Inches(0.5) + i * Inches(3.15)
    card(sl, x, Inches(1.2), Inches(2.95), Inches(1.8))
    txt(sl, x + Inches(0.2), Inches(1.3), Inches(2.55), Inches(0.7), num, 44, clr, True, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.2), Inches(2.0), Inches(2.55), Inches(0.35), label, 16, WHITE, True, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.2), Inches(2.35), Inches(2.55), Inches(0.3), desc, 12, GRAY, False, PP_ALIGN.CENTER)

row_metrics = [
    ("Bad patches blocked", "18", "Purely destructive writes caught"),
    ("Redirected to extension", "8", "Sidecar files instead of overwrite"),
    ("Legitimate patches approved", "8", "Safe changes still flow through"),
    ("Tests passing", "254/254", "Zero regressions"),
    ("TAPES overhead", "~0.2s", "Per scenario — negligible"),
    ("Session cost (all 8)", "$1.34", "vs $7.29 raw"),
]
for i, (label, val, desc) in enumerate(row_metrics):
    row = i // 3
    col = i % 3
    x = Inches(0.5) + col * Inches(4.2)
    y = Inches(3.3) + row * Inches(1.6)
    card(sl, x, y, Inches(3.95), Inches(1.35))
    txt(sl, x + Inches(0.2), y + Inches(0.1), Inches(3.55), Inches(0.35), val, 28, GREEN if "254" in val or "$1.34" in val else CYAN, True, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.2), y + Inches(0.5), Inches(3.55), Inches(0.3), label, 15, WHITE, True, PP_ALIGN.CENTER)
    txt(sl, x + Inches(0.2), y + Inches(0.85), Inches(3.55), Inches(0.3), desc, 12, GRAY, False, PP_ALIGN.CENTER)

# Bug fixes footer
card(sl, Inches(0.5), Inches(6.5), Inches(12.3), Inches(0.6), DARKER)
txt(sl, Inches(0.8), Inches(6.55), Inches(11.7), Inches(0.45),
    "11 bugs fixed during preparation: CLI bouncer bypass, TUI always-shows-passed, silent full-region replace, "
    "BobShell empty target_symbol, double flush, match gate count>1, write-back scope, protected file gaps, more",
    11, GRAY)

# ═══════════════════════════════════════════════════════════════
# SLIDE 9 — Closing
# ═══════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(sl)
txt(sl, Inches(1), Inches(1.5), Inches(11), Inches(1.2),
    "Thank You", 52, WHITE, True, PP_ALIGN.CENTER)
txt(sl, Inches(1), Inches(3.0), Inches(11), Inches(1.0),
    '"Constrain everything. Guess nothing. Ship once."', 22, CYAN, False, PP_ALIGN.CENTER)
txt(sl, Inches(1), Inches(4.2), Inches(11), Inches(0.5),
    "TAPES v8.0 — Governed AI Code Generation", 18, GRAY, False, PP_ALIGN.CENTER)
txt(sl, Inches(1), Inches(4.8), Inches(11), Inches(0.5),
    "IBM watsonx  +  BobShell  +  TAPES Governance Pipeline", 16, GRAY, False, PP_ALIGN.CENTER)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "TAPES_Hackathon_Demo.pptx")
prs.save(out)
print(f"Saved: {out}")
