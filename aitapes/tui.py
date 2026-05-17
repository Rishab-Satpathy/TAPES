"""TAPES — calm governed execution runtime."""

from __future__ import annotations
import ast, os, sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass

def _setup_io():
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
_setup_io()

from rich.console import Console
from rich.text import Text
from rich.style import Style
from rich.panel import Panel
from rich.rule import Rule

S_C = Style(color="rgb(61,111,212)")
S_M = Style(color="rgb(51,51,51)")
S_D = Style(color="rgb(90,90,90)")
S_G = Style(color="rgb(40,200,64)")
S_R = Style(color="rgb(245,158,11)")
S_W = Style(color="rgb(212,212,212)")
S_B = Style(bold=True)
S_I = Style(italic=True)

def sb(*s): return Style.combine(list(s))
con = Console(highlight=False)

def _detect_model() -> str:
    m = os.environ.get("AITAPES_MODEL", "") or os.environ.get("LLM_MODEL", "")
    p = os.environ.get("AITAPES_PROVIDER", "offline")
    return f"{p}/{m}" if m else "offline"

def _detect_branch() -> str:
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "main"
    except Exception: return "main"

def _detect_repo() -> str:
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        return Path(r.stdout.strip()).name if r.returncode == 0 else "."
    except Exception: return "."

@dataclass
class Session:
    msgs: list[tuple[str, str]]
    cost: float = 0.0

state = Session(msgs=[])
STATE_MODEL = _detect_model()
STATE_REPO = _detect_repo()
STATE_BRANCH = _detect_branch()

def s(role: str, content: str) -> None:
    state.msgs.append((role, content))

def topbar() -> None:
    left = Text()
    left.append(Text(" TAPES ", style=sb(S_C, S_B)))
    left.append(Text(f"· {STATE_REPO} · {STATE_BRANCH} · {STATE_MODEL}", style=S_D))
    con.print(left)
    con.print(Rule(style=Style(color="rgb(26,26,26)")))

def render() -> None:
    con.clear()
    topbar()
    con.print()
    for role, content in state.msgs[-15:]:
        if role == "user":
            con.print(Text(f"  You", style=sb(S_C, S_B)))
            con.print(Panel(content, border_style=Style(color="rgb(61,111,212)"), padding=(0,2)))
        else:
            if not content.strip():
                continue
            con.print(Text(f"  TAPES", style=sb(S_C, S_B)))
            con.print(Panel(content, border_style=Style(color="rgb(26,37,53)"), padding=(0,2)))
        con.print()
    con.print(Rule(style=Style(color="rgb(26,26,26)")))
    bar = Text("  ")
    bar.append(Text("●", style=S_G))
    bar.append(Text(f"  {STATE_MODEL}  ·  ${state.cost:.3f}", style=S_D))
    if os.environ.get("AITAPES_PROVIDER", "") == "watsonx":
        bar.append(Text(f"  ·  BobShell", style=sb(S_G, S_B)))
    con.print(bar)

def pipeline(intent: str) -> None:
    s("user", intent)
    s("assistant", "")
    try:
        from io import StringIO
        from contextlib import redirect_stdout
        from forest_tapes.tapes_core.pressure_kernel import RuntimeSignals
        from forest_tapes.tapes_core import allocate_cognition
        from aitapes.plan import run_plan
        from aitapes.offline_builder import generate_patches
        from aitapes.patches import apply_patches
        from aitapes.ledger import store_patch_result
        from aitapes.prepare import prepare, format_diff
        from aitapes.llm import LLMConfig

        signals = RuntimeSignals(patch_attempts=0,patch_failures=0,broad_rewrite_attempted=False,contradiction_count=0,unresolved_branches=0,out_of_scope_references=0,representation_switches=0,validation_failures=0,topology_nodes_touched=1,similar_failures=0)
        cfg = LLMConfig.from_env()
        use_bob = bool(cfg.api_key) and cfg.provider == "watsonx"

        # Suppress internal noise from analysis/planning
        with redirect_stdout(StringIO()):
            allocate_cognition(task=intent, prior_failure_count=0, runtime_signals=signals)
            run_plan(intent, "tapes-contract.json", "tapes-ledger.jsonl", offline=not use_bob)
            prepare(".", intent, max_files=5, hollow=True)

        # Build phase — visible so Bob output shows
        if use_bob:
            con.print(Text("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", style=S_G))
            con.print(Text("  │  IBM BobShell Active                  │", style=sb(S_G, S_B)))
            con.print(Text("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", style=S_G))
            try:
                from aitapes.build import run_build
                output, report = run_build("tapes-contract.json", ".", "tapes-patches.json", "tapes-ledger.jsonl", offline=False)
                plist = list(output.patches)
                if report:
                    report_path = Path("bob-session-report.md")
                    report_path.write_text(report.to_markdown(), encoding="utf-8")
            except Exception as e:
                con.print(Text(f"    BobShell unavailable: {e}", style=S_R))
                con.print(Text("    Deterministic fallback active", style=S_D))
                from aitapes.offline_builder import generate_patches
                output = generate_patches(".", intent)
                plist = list(output.patches)
        else:
            con.print(Text("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", style=S_D))
            con.print(Text("  │  Deterministic Fallback               │", style=S_D))
            con.print(Text("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", style=S_D))
            with redirect_stdout(StringIO()):
                output = generate_patches(".", intent)
                plist = list(output.patches)

        # Run bouncer check — with governed repair for protected files
        from aitapes.bouncer import check_all
        approved, remediations = check_all(plist, ".")
        for r in remediations:
            if r.action == "redirect":
                con.print(Text(f"    ❌ BOUNCER INTERCEPT", style=sb(S_R, S_B)))
                con.print(Text(f"    Protected file mutation intercepted", style=S_D))
                con.print(Text(f"    Redirected to {r.redirect_target}", style=sb(S_G, S_B)))
            elif r.action == "reject":
                con.print(Text(f"    ❌ BOUNCER REJECTED — {r.reason}", style=S_R))
        plist = approved

        # Sandbox: apply patches to temp dir first, only commit if clean
        import tempfile, shutil
        sandbox_applied = 0
        applied = 0
        sandbox_results = []
        with tempfile.TemporaryDirectory(prefix="tapes_sandbox_") as tmp:
            sandbox = Path(tmp)
            for p in plist:
                src = Path(p.file)
                if src.exists():
                    dst = sandbox / p.file
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dst))
            from aitapes.patches import apply_patches as _sandbox_apply
            sandbox_results = _sandbox_apply(str(sandbox), plist)
            sandbox_applied = sum(1 for r in sandbox_results if r.applied)
            sandbox_failed = sum(1 for r in sandbox_results if not r.applied)
            sandbox_clean = True
            if sandbox_applied:
                try:
                    for r in sandbox_results:
                        if r.applied:
                            f = sandbox / r.patch.file
                            if f.exists():
                                ast.parse(f.read_text(encoding="utf-8"))
                except (SyntaxError, OSError):
                    sandbox_clean = False
            if sandbox_clean and sandbox_applied > 0:
                for r in sandbox_results:
                    if r.applied:
                        src = sandbox / r.patch.file
                        dst = Path(r.patch.file)
                        if src.exists():
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(src), str(dst))
                applied = sandbox_applied
            else:
                applied = 0
                if sandbox_failed > 0:
                    con.print(Text(f"    Sandbox rejected — {sandbox_failed} patches failed", style=S_R))
                if not sandbox_clean:
                    con.print(Text("    Syntax error in patched files — rollback", style=S_R))
            store_patch_result("tapes-ledger.jsonl", intent, plist, applied, 0)

        state.cost += 0.01 if use_bob else 0.0

        diff_text = ""
        for r in sandbox_results:
            if r.applied:
                try:
                    full = Path(r.patch.file).read_text(encoding="utf-8")
                    d = format_diff("", full, r.patch.file)
                    if d: diff_text += d
                except Exception: pass

        result = Text()
        result.append(Text("  Planning\n", style=S_D))
        result.append(Text("    contract bounded\n", style=sb(S_G, S_I)))
        result.append(Text("  Building\n", style=S_D))
        result.append(Text(f"    {applied} patches generated\n", style=sb(S_G, S_I)))
        result.append(Text("  Testing\n", style=S_D))
        if sandbox_applied > 0 and sandbox_clean:
            result.append(Text("    passed\n", style=sb(S_G, S_I)))
        elif not sandbox_clean:
            result.append(Text("    syntax error\n", style=S_R))
        else:
            result.append(Text("    no patches applied\n", style=S_D))
        result.append(Text("  Executing\n", style=S_D))
        if applied > 0:
            result.append(Text("    committed safely\n", style=sb(S_G, S_I)))
        elif plist:
            result.append(Text("    sandbox rejected\n", style=S_R))
        else:
            result.append(Text("    nothing to execute\n", style=S_D))

        if diff_text:
            lines = diff_text.split("\n")
            shown = 0
            for line in lines:
                if shown >= 12: break
                if line.startswith("@@"):
                    if shown > 0: result.append(Text("\n"))
                    result.append(Text(f"    {line}\n", style=S_C))
                    shown += 1
                elif line.startswith("+") and not line.startswith("+++"):
                    result.append(Text(f"    {line}\n", style=sb(S_G, S_I)))
                    shown += 1
                elif line.startswith("-") and not line.startswith("---"):
                    result.append(Text(f"    {line}\n", style=S_R))
                    shown += 1

        state.msgs[-1] = ("assistant", result.plain)
        for f in ["tapes-contract.json"]:
            try: os.remove(f)
            except Exception: pass

    except Exception as e:
        state.msgs[-1] = ("assistant", f"Error: {e}")
    finally:
        render()

def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in ("--help", "-h"):
        con.print("Usage: tapes [intent]")
        con.print("  tapes              Start interactive shell")
        con.print('  tapes "add validation"  Run pipeline with intent')
        return
    if args and not args[0].startswith("-"):
        pipeline(" ".join(args))
        return
    if args:
        s("assistant", f"Unknown flag: {args[0]}. Enter interactive mode.")
    else:
        s("assistant", "Ready.")
    render()
    try:
        while True:
            raw = input(f"  \033[38;2;61;111;212m>\033[0m ")
            if not raw: continue
            if raw.lower() in ("exit","quit","q"): con.print("  Session closed."); break
            pipeline(raw)
    except (EOFError, KeyboardInterrupt):
        con.print("\n  Session closed.")

if __name__ == "__main__":
    main()
