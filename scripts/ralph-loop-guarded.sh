#!/usr/bin/env bash
# Ralph Guarded Loop Wrapper
# Runs the self-verifying guardrail before and after the Ralph SEPCC loop.
# Exits non-zero if guardrail fails at any point.
set -euo pipefail

# ── Paths ───────────────────────────────────────────────────────────────────
WORKTREE="/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1"
GUARDRAIL="$WORKTREE/scripts/ralph_guardrail_check.py"
RALPH_LOOP="/opt/vega-cloud/spc/ralph-mode/ralph-loop-sepcc.sh"
LOG_FILE="/opt/vega-cloud/logs/ralph-guarded-loop.log"
STATE_FILE="$WORKTREE/.ralph-mode/state.json"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

# ── Ensure log dir exists ───────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

echo -e "${CYAN}════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Ralph Guarded Loop Wrapper${NC}"
echo -e "${CYAN}  Workspace: $WORKTREE${NC}"
echo -e "${CYAN}  Guardrail: $GUARDRAIL${NC}"
echo -e "${CYAN}  Log: $LOG_FILE${NC}"
echo -e "${CYAN}════════════════════════════════════════════${NC}"
echo ""

cd "$WORKTREE"

# ── Guardrail pre-check ─────────────────────────────────────────────────────
echo -e "${BLUE}[PRE-CHECK] Running guardrail before loop...${NC}"
echo "---"
if python3 "$GUARDRAIL"; then
    echo -e "\n${GREEN}[PRE-CHECK] Guardrail PASSED — proceeding to loop${NC}\n"
else
    echo -e "\n${RED}[PRE-CHECK] Guardrail FAILED — aborting loop${NC}"
    exit 1
fi

# ── Ralph loop ──────────────────────────────────────────────────────────────
echo -e "${BLUE}[LOOP] Starting Ralph SEPCC loop...${NC}"
echo "---"
LOOP_EXIT=0
if [ -f "$RALPH_LOOP" ]; then
    bash "$RALPH_LOOP" || LOOP_EXIT=$?
else
    echo -e "${RED}ERROR: Ralph loop not found: $RALPH_LOOP${NC}"
    exit 1
fi
echo "---"
echo -e "${BLUE}[LOOP] Ralph loop finished (exit=$LOOP_EXIT)${NC}"
echo ""

# ── Guardrail post-check ────────────────────────────────────────────────────
echo -e "${BLUE}[POST-CHECK] Running guardrail after loop...${NC}"
echo "---"
if python3 "$GUARDRAIL"; then
    echo -e "\n${GREEN}[POST-CHECK] Guardrail PASSED${NC}\n"
else
    echo -e "\n${RED}[POST-CHECK] Guardrail FAILED — loop may have introduced unexpected changes${NC}"
    exit 1
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Guarded loop complete.${NC}"
echo -e "${CYAN}  Loop exit: $LOOP_EXIT${NC}"
echo -e "${CYAN}  Guardrail: PRE=PASS POST=PASS${NC}"
echo -e "${CYAN}  Log: $LOG_FILE${NC}"
echo -e "${CYAN}════════════════════════════════════════════${NC}"

exit $LOOP_EXIT
