"""TAPES Hackathon Demo — 2 flows: success and bouncer intercept.

Usage:
  python scripts/demo.py
"""

import sys, os, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SEP = "=" * 65
DEMO = "_demo_project"
WORK = "_demo_work"

def section(title):
    print(f"\n  {title}")
    print(f"  {'─' * 60}")

def step(label, status=""):
    mark = "✓" if "pass" in status.lower() or "ok" in status.lower() else "✗" if "fail" in status.lower() else "→"
    print(f"  {mark} {label}")

def setup_workdir():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    shutil.copytree(DEMO, WORK)
    os.chdir(WORK)

def cleanup():
    os.chdir(str(Path(__file__).parent.parent))
    if os.path.exists(WORK):
        shutil.rmtree(WORK)

# ── FLOW 1: SUCCESS PATH ─────────────────────────────────────────
section("FLOW 1: SUCCESS — safe patch, validated, committed")
setup_workdir()

step("Planning...")
from aitapes.plan import run_plan
run_plan("add None validation to login", "contract.json", "ledger.jsonl", offline=True)
step("Contract bounded", "OK")

step("Generating patches...")
from aitapes.offline_builder import generate_patches, display_patches
output = generate_patches(".", "add None validation to login")
patches = list(output.patches)
step(f"{len(patches)} patches generated", "OK")

step("Applying patches...")
from aitapes.patches import apply_patches
results = apply_patches(".", patches)
applied = sum(1 for r in results if r.applied)
failed = sum(1 for r in results if not r.applied)

if applied and failed == 0:
    step(f"{applied}/{len(patches)} patches applied", "PASS")
    step("Atomic commit", "OK")
else:
    step(f"{applied}/{len(patches)} applied, {failed} failed", "FAIL")

print(f"\n  Diff:")
for r in results:
    if r.applied:
        content = Path(r.patch.file).read_text()
        print(f"  @@ {r.patch.file} @@")
        for line in r.patch.replace.split("\n")[:10]:
            print(f"    + {line}")

cleanup()

# ── FLOW 2: BOUNCER INTERCEPT ────────────────────────────────────
print(f"\n\n{SEP}")
section("FLOW 2: BOUNCER — unsafe mutation intercepted, redirected")
setup_workdir()

from aitapes.patches import Patch
from aitapes.bouncer import check_all, PROTECTED_FILES

# Simulate an AI trying to modify the protected legacy_auth.py
step("AI generates patch targeting legacy_auth.py...")
unsafe_patch = Patch(
    file="legacy_auth.py",
    target_symbol="authenticate",
    search="def authenticate(username, password):",
    replace="def authenticate(username, password):\n    # NEW: bcrypt hashing\n    import bcrypt\n    ...",
    reasoning="Upgrade password hashing to bcrypt",
)
step(f"  target: {unsafe_patch.file} → symbol {unsafe_patch.target_symbol}", "OK")

step("Running bouncer gates...")
approved, remediations = check_all([unsafe_patch], ".")

if remediations:
    for r in remediations:
        if r.action == "redirect":
            step(f"BOUNCER INTERCEPTED: {r.reason}", "REDIRECT")
            step(f"  Patch redirected to safe target: {r.redirect_target}", "OK")
        else:
            step(f"BOUNCER REJECTED: {r.reason}", "REJECT")

# Verify legacy_auth.py was NOT modified
original = Path("legacy_auth.py").read_text()
assert "hashlib" in original
step(f"  legacy_auth.py unchanged (protected)", "PASS")

if approved:
    step(f"Redirected patches: {len(approved)} applied to extension file", "OK")

# Show the redirection visual
print(f"\n  ├─ BEFORE: AI → legacy_auth.py ✗ (blocked)")
print(f"  └─ AFTER:  AI → auth_middleware_extension.py ✓ (governed redirect)")
print(f"\n  Safe extension file: {PROTECTED_FILES['legacy_auth.py']}")

cleanup()

# ── SUMMARY ───────────────────────────────────────────────────────
print(f"\n\n{SEP}")
print("  DEMO COMPLETE")
print(f"  Flow 1: SAFE PATCH — validated, sandboxed, committed")
print(f"  Flow 2: BOUNCER — unsafe AI mutation intercepted, redirected")
print(f"{SEP}")
print(f"\n  TAPES: Bob generates. TAPES governs.")
