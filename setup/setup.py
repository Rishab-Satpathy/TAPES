#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TAPES Setup Installer
────────────────────
Cross-platform setup: Windows, Mac, Linux.
User just runs: python setup.py

What it does:
  1. Checks Python version (>=3.12)
  2. Creates .venv inside the project
  3. Installs TAPES + all dependencies
  4. Collects API keys interactively
  5. Writes .env file
  6. Adds `tapes` to PATH permanently
  7. Runs a live demo to confirm everything works
"""

from __future__ import annotations

import os
import sys
import subprocess
import platform
import shutil
import getpass
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Colour helpers (no deps) ──────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"

def c(text: str, colour: str) -> str:
    """C."""
    if platform.system() == "Windows" and not os.environ.get("WT_SESSION"):
        return text          # plain cmd.exe — skip colour codes
    return f"{colour}{text}{RESET}"

# ── Build mode detection ────────────────────────────────────────────────────
# Skip interactive setup when pip uses setup.py as a build backend
_BUILD_MODE = (
    "SETUPTOOLS_EXT_MODULE" in os.environ
    or bool(os.environ.get("PIP_REQ_TRACKER"))
    or bool(os.environ.get("PIP_BUILD_TRACKER"))
)

def banner() -> None:
    """Banner."""
    if _BUILD_MODE:
        return
    print()
    print(c("╔══════════════════════════════════════════════════╗", CYAN))
    print(c("║         TAPES v8.0  —  Setup Installer          ║", CYAN))
    print(c("║   Cognition Pressure Architecture + IBM Bob      ║", CYAN))
    print(c("╚══════════════════════════════════════════════════╝", CYAN))
    print()

def step(n: int, total: int, msg: str) -> None:
    """Step."""
    if _BUILD_MODE:
        return
    print(c(f"\n[{n}/{total}] {msg}", BOLD))

def ok(msg: str) -> None:
    """Ok."""
    if _BUILD_MODE:
        return
    print(c(f"  ✓  {msg}", GREEN))

def warn(msg: str) -> None:
    """Warn."""
    if _BUILD_MODE:
        return
    print(c(f"  ⚠  {msg}", YELLOW))

def fail(msg: str) -> None:
    """Fail."""
    if _BUILD_MODE:
        return
    print(c(f"  ✗  {msg}", RED))
    print()

def info(msg: str) -> None:
    """Info."""
    if _BUILD_MODE:
        return
    print(c(f"     {msg}", DIM))

def abort(msg: str) -> None:
    """Abort."""
    if _BUILD_MODE:
        sys.exit(1)
    fail(msg)
    sys.exit(1)

# ── Platform detection ────────────────────────────────────────────────────────

SYSTEM   = platform.system()          # Windows / Darwin / Linux
IS_WIN   = SYSTEM == "Windows"
IS_MAC   = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"

# ── Paths ─────────────────────────────────────────────────────────────────────

HERE     = Path(__file__).parent.resolve()
VENV_DIR = HERE / ".venv"
OUTER_VENV = HERE.parent / ".venv"

# Detect if we're running inside the outer .venv at project root
_in_outer_venv = (
    OUTER_VENV.exists()
    and str(Path(sys.prefix)).replace("\\", "/").lower()
       == str(OUTER_VENV.resolve()).replace("\\", "/").lower()
)

# Use outer venv's python if available, otherwise use nested .venv
if _in_outer_venv:
    PY = Path(sys.executable)
    SCRIPTS = Path(sys.prefix) / ("Scripts" if IS_WIN else "bin")
else:
    PY = VENV_DIR / ("Scripts" if IS_WIN else "bin") / ("python.exe" if IS_WIN else "python")
    SCRIPTS = VENV_DIR / ("Scripts" if IS_WIN else "bin")

TAPES_EXE = SCRIPTS / ("tapes.exe" if IS_WIN else "tapes")
ENV_FILE = HERE / ".env"

TOTAL_STEPS = 7

# ── Step 1: Python version ────────────────────────────────────────────────────

def check_python() -> None:
    """Check Python."""
    if _BUILD_MODE:
        return
    step(1, TOTAL_STEPS, "Checking Python version")
    v = sys.version_info
    if v < (3, 12):
        fail(f"Python 3.12+ required. You have {v.major}.{v.minor}.{v.micro}")
        info("Download from https://python.org/downloads")
        abort("Upgrade Python and re-run setup.")
    ok(f"Python {v.major}.{v.minor}.{v.micro}")

# ── Step 2: Virtual environment ───────────────────────────────────────────────

def create_venv() -> None:
    """Create Venv."""
    if _BUILD_MODE:
        return
    step(2, TOTAL_STEPS, "Creating virtual environment")
    if _in_outer_venv:
        ok(f"Using existing venv: {PY.parent.parent}")
        return
    if VENV_DIR.exists():
        warn(".venv already exists — skipping creation")
        info("Delete .venv and re-run if you want a clean install.")
    else:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True, capture_output=True
        )
        ok(f"Created .venv at {VENV_DIR}")

# ── Step 3: Install TAPES ─────────────────────────────────────────────────────

def install_tapes() -> None:
    """Install Tapes."""
    if _BUILD_MODE:
        return
    step(3, TOTAL_STEPS, "Installing TAPES and dependencies")
    info("This may take 30-60 seconds on first run...")

    if not _in_outer_venv and not VENV_DIR.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True, capture_output=True)
    if not _in_outer_venv:
        subprocess.run([str(PY), "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)

    install_result = subprocess.run(
        [str(PY), "-m", "pip", "install", "-e", ".[dev]", "--quiet"],
        cwd=str(HERE),
        capture_output=True, text=True
    )
    if install_result.returncode != 0:
        # Fallback: install without dev extras
        result2 = subprocess.run(
            [str(PY), "-m", "pip", "install", "-e", ".", "--quiet"],
            cwd=str(HERE),
            capture_output=True, text=True
        )
        if result2.returncode != 0:
            fail("pip install failed.")
            print(result2.stderr[-2000:])
            abort("Fix the error above and re-run setup.")
        warn("Installed without [dev] extras (pytest, ruff, mypy).")
    else:
        ok("TAPES installed (editable mode + dev extras)")

    if not TAPES_EXE.exists():
        abort(f"`tapes` executable not found at {TAPES_EXE}. Installation failed.")
    ok(f"`tapes` binary created at {TAPES_EXE}")

# ── Step 4: API keys ──────────────────────────────────────────────────────────

KEYS = [
    {
        "env":     "WATSONX_API_KEY",
        "label":   "IBM watsonx / Bob API key",
        "hint":    "From console.ng.bluemix.net → Manage → Access → API Keys",
        "required": True,
    },
    {
        "env":     "WATSONX_PROJECT_ID",
        "label":   "IBM watsonx Project ID",
        "hint":    "From your watsonx.ai project settings page",
        "required": True,
    },
    {
        "env":     "IBM_BOB_API_KEY",
        "label":   "IBM watsonx API key (optional — for benchmarks)",
        "hint":    "From IBM Cloud API keys page — press Enter to skip",
        "required": False,
    },
]

def collect_api_keys() -> dict[str, str]:
    """Collect Api Keys."""
    step(4, TOTAL_STEPS, "Configuring API keys")

    # Load existing .env if present
    existing: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
        info(f"Found existing .env — pre-filling known keys.")

    collected: dict[str, str] = {}

    for key_def in KEYS:
        env_name  = key_def["env"]
        label     = key_def["label"]
        hint      = key_def["hint"]
        required  = key_def["required"]

        # Already in environment or .env?
        current = os.environ.get(env_name) or existing.get(env_name, "")

        if current:
            masked = current[:6] + "..." + current[-4:] if len(current) > 12 else "***"
            print(f"\n  {c(label, BOLD)}")
            info(f"Already configured: {masked}")
            change = input(c("  Change it? [y/N] ", DIM)).strip().lower()
            if change != "y":
                collected[env_name] = current
                ok(f"{env_name} kept")
                continue

        print(f"\n  {c(label, BOLD)}")
        info(hint)

        while True:
            value = getpass.getpass(c(f"  Enter {env_name}: ", CYAN)).strip()
            if value:
                collected[env_name] = value
                ok(f"{env_name} saved")
                break
            elif not required:
                info("Skipped.")
                break
            else:
                warn("This key is required. Try again or press Ctrl+C to abort.")

    return collected

def write_env(keys: dict[str, str]) -> None:
    """Write Env."""
    lines = [
        "# TAPES environment — auto-generated by setup.py",
        "# Do NOT commit this file to git.\n",
    ]
    for k, v in keys.items():
        if v:
            lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ok(f".env written to {ENV_FILE}")

    # Warn if .gitignore doesn't cover .env
    gitignore = HERE / ".gitignore"
    if gitignore.exists():
        if ".env" not in gitignore.read_text():
            warn(".env is NOT in .gitignore — add it before pushing to GitHub.")
    else:
        warn("No .gitignore found — create one and add .env before pushing.")

# ── Step 5: Add `tapes` to PATH ───────────────────────────────────────────────

def add_to_path() -> None:
    """Add To Path."""
    step(5, TOTAL_STEPS, "Adding `tapes` to PATH")
    scripts_str = str(SCRIPTS)

    if IS_WIN:
        _add_to_path_windows(scripts_str)
    else:
        _add_to_path_unix(scripts_str)

def _add_to_path_windows(scripts_str: str) -> None:
    """ Add To Path Windows."""
    import winreg  # type: ignore[import]
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE
        )
        current_path, _ = winreg.QueryValueEx(key, "Path")
        if scripts_str.lower() in current_path.lower():
            ok("Already in PATH (no change needed)")
        else:
            new_path = scripts_str + ";" + current_path
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            ok(f"Added to user PATH: {scripts_str}")
            warn("Open a NEW terminal window for PATH changes to take effect.")
        winreg.CloseKey(key)
    except Exception as e:
        warn(f"Could not update PATH automatically: {e}")
        info(f"Add this manually to your PATH: {scripts_str}")

def _add_to_path_unix(scripts_str: str) -> None:
    """ Add To Path Unix."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        rc_files = [Path.home() / ".zshrc"]
    elif "fish" in shell:
        rc_files = [Path.home() / ".config" / "fish" / "config.fish"]
    else:
        rc_files = [Path.home() / ".bashrc", Path.home() / ".bash_profile"]

    export_line = f'\nexport PATH="{scripts_str}:$PATH"  # Added by TAPES setup\n'

    for rc in rc_files:
        if rc.exists() and scripts_str in rc.read_text():
            ok(f"Already in {rc.name} (no change needed)")
            return

    target = rc_files[0]
    with open(target, "a") as f:
        f.write(export_line)
    ok(f"Added to {target}")
    warn(f"Run: source {target}  (or open a new terminal)")

# ── Step 6: Verify ────────────────────────────────────────────────────────────

def verify_install() -> None:
    """Verify Install."""
    step(6, TOTAL_STEPS, "Verifying installation")

    # Run `tapes --help` via the venv binary directly (PATH may not be updated yet)
    result = subprocess.run(
        [str(TAPES_EXE), "--help"],
        capture_output=True, text=True
    )
    if result.returncode != 0 and "usage" not in result.stdout.lower():
        warn("`tapes --help` returned an error — check manually after setup.")
        info(result.stderr[:500])
    else:
        ok("`tapes --help` responds correctly")

    # Run tests if pytest available
    pytest_exe = SCRIPTS / ("pytest.exe" if IS_WIN else "pytest")
    if pytest_exe.exists():
        info("Running test suite (no API calls)...")
        t = subprocess.run(
            [str(pytest_exe), "tests/", "-q", "--tb=no", "--no-header"],
            cwd=str(HERE),
            capture_output=True, text=True
        )
        lines = t.stdout.strip().splitlines()
        summary = next((l for l in reversed(lines) if "passed" in l or "failed" in l), "")
        if summary:
            if "failed" in summary:
                warn(f"Tests: {summary}")
            else:
                ok(f"Tests: {summary}")
    else:
        info("pytest not found — skipping tests (install with: pip install pytest)")

# ── Step 7: Live demo ─────────────────────────────────────────────────────────

def run_demo(keys: dict[str, str]) -> None:
    """Run Demo."""
    step(7, TOTAL_STEPS, "Running live demo")

    # Skip if no API key provided
    if not keys.get("WATSONX_API_KEY") and not keys.get("OPENAI_API_KEY"):
        warn("No API key provided — skipping live demo.")
        info("Run it later: tapes --intent \"add hello function to models.py\"")
        return

    # Load .env into current environment for the subprocess
    env = os.environ.copy()
    for k, v in keys.items():
        if v:
            env[k] = v

    demo_script = HERE / "scripts" / "tapes_demo.py"
    if demo_script.exists():
        info("Running scripts/tapes_demo.py ...")
        result = subprocess.run(
            [str(PY), str(demo_script)],
            env=env, cwd=str(HERE),
            timeout=120
        )
        if result.returncode == 0:
            ok("Demo completed successfully")
        else:
            warn("Demo exited with an error — check output above.")
    else:
        # Fallback: run tapes --intent directly
        info("Running: tapes --intent \"add hello() to demo\"")
        demo_dir = HERE / "_setup_demo"
        demo_dir.mkdir(exist_ok=True)
        (demo_dir / "demo.py").write_text("# TAPES demo file\n\ndef goodbye():\n    return 'bye'\n")

        result = subprocess.run(
            [str(TAPES_EXE), "--intent", "add a hello() function that returns 'hello world'",
             "--source", str(demo_dir)],
            env=env, cwd=str(HERE),
            timeout=120
        )
        if result.returncode == 0:
            ok("Demo completed — check _setup_demo/demo.py to see the patch applied.")
        else:
            warn("Demo had an error — but TAPES is installed. Run manually when ready.")

# ── Final summary ─────────────────────────────────────────────────────────────

def print_summary(success: bool) -> None:
    """Print Summary."""
    print()
    print(c("═" * 52, CYAN))
    if success:
        print(c("  TAPES is ready.", GREEN + BOLD))
    else:
        print(c("  Setup completed with warnings.", YELLOW + BOLD))
    print(c("═" * 52, CYAN))
    print()
    print(c("  Quick start:", BOLD))
    print(f"    tapes --intent \"fix the auth bug in login.py\"")
    print(f"    tapes --intent \"add logging to all API handlers\"")
    print(f"    tapes ledger          — view decision history")
    print(f"    tapes dashboard       — open observability UI")
    print()
    print(c("  Docs:", BOLD))
    print(f"    README.md        — overview + usage")
    print(f"    ARCHITECTURE.md  — full pipeline diagram")
    print(f"    BENCHMARKS.md    — benchmark results")
    print()
    if IS_WIN:
        print(c("  Windows note:", YELLOW))
        print("    Open a NEW terminal window for `tapes` to work in PATH.")
        print()

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Main."""
    if _BUILD_MODE:
        from setuptools import setup
        setup()
        return

    banner()

    check_python()
    create_venv()
    install_tapes()
    keys = collect_api_keys()
    write_env(keys)
    add_to_path()
    verify_install()
    run_demo(keys)
    print_summary(success=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c("\n\n  Aborted by user.", YELLOW))
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        fail(f"Command failed: {e.cmd}")
        sys.exit(1)
