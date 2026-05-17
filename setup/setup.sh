#!/usr/bin/env bash
# TAPES Setup — Mac / Linux
# Usage: bash setup.sh
# Or:    chmod +x setup.sh && ./setup.sh

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
GREEN="\033[92m"; YELLOW="\033[93m"; RED="\033[91m"; CYAN="\033[96m"

ok()   { echo -e "${GREEN}  ✓  $*${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠  $*${RESET}"; }
fail() { echo -e "${RED}  ✗  $*${RESET}"; }
info() { echo -e "${DIM}     $*${RESET}"; }
step() { echo -e "\n${BOLD}[$1/$TOTAL] $2${RESET}"; }
abort(){ fail "$1"; echo; exit 1; }

banner() {
echo -e "${CYAN}"
cat << 'EOF'
╔══════════════════════════════════════════════════╗
║         TAPES v8.0  —  Mac / Linux Setup        ║
║   Cognition Pressure Architecture + IBM Bob      ║
╚══════════════════════════════════════════════════╝
EOF
echo -e "${RESET}"
}

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"
PY="$VENV/bin/python"
TAPES_BIN="$VENV/bin/tapes"
PYTEST_BIN="$VENV/bin/pytest"
ENV_FILE="$HERE/.env"
TOTAL=7

banner

# ── Step 1: Python ────────────────────────────────────────────────────────────
step 1 $TOTAL "Checking Python version"

# Try python3.12, python3, python in that order
PY_CMD=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PY_CMD="$cmd"
            ok "Found: $cmd ($ver)"
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    fail "Python 3.12+ not found."
    info "Mac:   brew install python@3.12"
    info "Linux: sudo apt install python3.12  (or use pyenv)"
    abort "Install Python 3.12+ and re-run."
fi

# ── Step 2: Virtual environment ───────────────────────────────────────────────
step 2 $TOTAL "Creating virtual environment"

if [ -d "$VENV" ]; then
    warn ".venv already exists — skipping creation"
    info "Delete .venv and re-run for a clean install."
else
    "$PY_CMD" -m venv "$VENV"
    ok "Created .venv at $VENV"
fi

# ── Step 3: Install TAPES ─────────────────────────────────────────────────────
step 3 $TOTAL "Installing TAPES and dependencies"
info "This may take 30-60 seconds on first run..."

"$PY" -m pip install --upgrade pip --quiet

if "$PY" -m pip install -e ".[dev]" --quiet 2>/dev/null; then
    ok "TAPES installed (editable + dev extras)"
else
    warn "Dev extras failed — installing without [dev]..."
    "$PY" -m pip install -e . --quiet || abort "pip install failed. Check output above."
fi

[ -f "$TAPES_BIN" ] || abort "\`tapes\` binary not found at $TAPES_BIN — install failed."
ok "\`tapes\` binary at $TAPES_BIN"

# ── Step 4: API keys ──────────────────────────────────────────────────────────
step 4 $TOTAL "Configuring API keys"

# Load existing .env
declare -A EXISTING=()
if [ -f "$ENV_FILE" ]; then
    info "Found existing .env — pre-filling known keys."
    while IFS='=' read -r key val; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        EXISTING["$key"]="$val"
    done < <(grep -v '^\s*#' "$ENV_FILE" | grep '=')
fi

get_key() {
    local env_name="$1" label="$2" hint="$3" required="$4"
    local current="${!env_name:-${EXISTING[$env_name]:-}}"

    if [ -n "$current" ]; then
        local masked
        if [ ${#current} -gt 12 ]; then
            masked="${current:0:6}...${current: -4}"
        else
            masked="***"
        fi
        echo ""
        echo -e "  ${BOLD}$label${RESET}"
        info "Already configured: $masked"
        read -rp "$(echo -e "  Change it? [y/N] ")" change
        if [ "$change" != "y" ]; then
            echo "$current"
            return
        fi
    fi

    echo ""
    echo -e "  ${BOLD}$label${RESET}"
    info "$hint"

    while true; do
        read -rsp "$(echo -e "  ${CYAN}Enter $env_name: ${RESET}")" value
        echo ""
        if [ -n "$value" ]; then
            echo "$value"
            return
        elif [ "$required" = "false" ]; then
            info "Skipped."
            echo ""
            return
        else
            warn "This key is required. Try again."
        fi
    done
}

WATSONX_KEY=$(get_key  "WATSONX_API_KEY"    "IBM watsonx / Bob API key"      "From console.ng.bluemix.net → Manage → Access → API Keys" "true")
WATSONX_PID=$(get_key  "WATSONX_PROJECT_ID" "IBM watsonx Project ID"          "From your watsonx.ai project settings page"               "true")
OPENAI_KEY=$(get_key   "OPENAI_API_KEY"     "OpenAI API key (optional)"       "From platform.openai.com/api-keys — press Enter to skip"  "false")

[ -n "$WATSONX_KEY" ]  && ok "WATSONX_API_KEY saved"
[ -n "$WATSONX_PID" ]  && ok "WATSONX_PROJECT_ID saved"
[ -n "$OPENAI_KEY" ]   && ok "OPENAI_API_KEY saved"

# Write .env
{
    echo "# TAPES environment — auto-generated by setup.sh"
    echo "# Do NOT commit this file to git."
    echo ""
    [ -n "$WATSONX_KEY" ] && echo "WATSONX_API_KEY=$WATSONX_KEY"
    [ -n "$WATSONX_PID" ] && echo "WATSONX_PROJECT_ID=$WATSONX_PID"
    [ -n "$OPENAI_KEY"  ] && echo "OPENAI_API_KEY=$OPENAI_KEY"
} > "$ENV_FILE"
ok ".env written to $ENV_FILE"

# Warn if .gitignore missing .env
if [ -f "$HERE/.gitignore" ]; then
    grep -q '\.env' "$HERE/.gitignore" || warn ".env is NOT in .gitignore — add it before pushing."
else
    warn "No .gitignore found — create one and add .env."
fi

# ── Step 5: Add to PATH ───────────────────────────────────────────────────────
step 5 $TOTAL "Adding \`tapes\` to PATH"

VENV_BIN="$VENV/bin"
SHELL_NAME="$(basename "${SHELL:-bash}")"

case "$SHELL_NAME" in
    zsh)  RC_FILES=("$HOME/.zshrc") ;;
    fish) RC_FILES=("$HOME/.config/fish/config.fish") ;;
    *)    RC_FILES=("$HOME/.bashrc" "$HOME/.bash_profile") ;;
esac

EXPORT_LINE="export PATH=\"$VENV_BIN:\$PATH\"  # Added by TAPES setup"
ALREADY_SET=false

for rc in "${RC_FILES[@]}"; do
    if [ -f "$rc" ] && grep -q "$VENV_BIN" "$rc" 2>/dev/null; then
        ok "Already in $rc — no change needed"
        ALREADY_SET=true
        break
    fi
done

if [ "$ALREADY_SET" = false ]; then
    target="${RC_FILES[0]}"
    echo -e "\n$EXPORT_LINE" >> "$target"
    ok "Added to $target"
    warn "Run: source $target  (or open a new terminal)"
fi

# Update current session
export PATH="$VENV_BIN:$PATH"

# ── Step 6: Verify ────────────────────────────────────────────────────────────
step 6 $TOTAL "Verifying installation"

if "$TAPES_BIN" --help 2>&1 | grep -qi "usage\|intent\|tapes"; then
    ok "\`tapes --help\` responds correctly"
else
    warn "\`tapes --help\` returned unexpected output — check manually."
fi

if [ -f "$PYTEST_BIN" ]; then
    info "Running test suite (no API calls)..."
    summary=$("$PYTEST_BIN" tests/ -q --tb=no --no-header 2>&1 | tail -3 | grep -E "passed|failed" || true)
    if echo "$summary" | grep -q "failed"; then
        warn "Tests: $summary"
    elif [ -n "$summary" ]; then
        ok "Tests: $summary"
    fi
fi

# ── Step 7: Demo ──────────────────────────────────────────────────────────────
step 7 $TOTAL "Running live demo"

if [ -z "$WATSONX_KEY" ] && [ -z "$OPENAI_KEY" ]; then
    warn "No API key provided — skipping demo."
    info "Run later: tapes --intent \"add hello function to models.py\""
else
    export WATSONX_API_KEY="$WATSONX_KEY"
    export WATSONX_PROJECT_ID="$WATSONX_PID"
    [ -n "$OPENAI_KEY" ] && export OPENAI_API_KEY="$OPENAI_KEY"

    DEMO_SCRIPT="$HERE/scripts/tapes_demo.py"
    if [ -f "$DEMO_SCRIPT" ]; then
        info "Running scripts/tapes_demo.py ..."
        if "$PY" "$DEMO_SCRIPT"; then
            ok "Demo completed successfully"
        else
            warn "Demo had an error — TAPES is still installed."
        fi
    else
        info "Running quick intent demo..."
        DEMO_DIR="$HERE/_setup_demo"
        mkdir -p "$DEMO_DIR"
        echo -e "# TAPES demo file\n\ndef goodbye():\n    return 'bye'\n" > "$DEMO_DIR/demo.py"
        if "$TAPES_BIN" --intent "add a hello() function that returns 'hello world'" --source "$DEMO_DIR"; then
            ok "Demo completed — check _setup_demo/demo.py"
        else
            warn "Demo had an error — run manually when ready."
        fi
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  TAPES is ready.${RESET}"
echo -e "${CYAN}════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${BOLD}  Quick start:${RESET}"
echo '    tapes --intent "fix the auth bug in login.py"'
echo '    tapes --intent "add logging to all API handlers"'
echo "    tapes ledger       — view decision history"
echo "    tapes dashboard    — open observability UI"
echo ""
echo -e "${BOLD}  Docs:${RESET}"
echo "    README.md        — overview + usage"
echo "    ARCHITECTURE.md  — full pipeline diagram"
echo "    BENCHMARKS.md    — benchmark results"
echo ""
