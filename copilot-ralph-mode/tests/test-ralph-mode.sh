#!/bin/bash

# Test suite for Copilot Ralph Mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RALPH_SCRIPT="$SCRIPT_DIR/../ralph-mode.sh"
TEST_DIR=$(mktemp -d)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0

# Cleanup on exit
cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# Test helper
test_case() {
  local name="$1"
  echo -n "Testing: $name... "
}

pass() {
  echo -e "${GREEN}PASS${NC}"
  ((PASSED++))
}

fail() {
  echo -e "${RED}FAIL${NC}"
  echo "  Error: $1"
  ((FAILED++))
}

# Setup
cd "$TEST_DIR"
chmod +x "$RALPH_SCRIPT"

echo ""
echo "🔄 Copilot Ralph Mode Test Suite"
echo "================================"
echo ""

# Test 1: Enable Ralph mode
test_case "Enable Ralph mode"
if "$RALPH_SCRIPT" enable "Test task" --max-iterations 10 --completion-promise "DONE" > /dev/null 2>&1; then
  if [[ -f ".ralph-mode/state.md" ]] && [[ -f ".ralph-mode/INSTRUCTIONS.md" ]]; then
    pass
  else
    fail "State files not created"
  fi
else
  fail "Command failed"
fi

# Test 2: Check status
test_case "Status command"
if "$RALPH_SCRIPT" status | grep -q "ACTIVE"; then
  pass
else
  fail "Status not showing active"
fi

# Test 3: Get prompt
test_case "Prompt command"
if "$RALPH_SCRIPT" prompt | grep -q "Test task"; then
  pass
else
  fail "Prompt not returned correctly"
fi

# Test 4: Iterate
test_case "Iterate command"
"$RALPH_SCRIPT" iterate > /dev/null
if grep -q "iteration: 2" ".ralph-mode/state.md"; then
  pass
else
  fail "Iteration not incremented"
fi

# Test 5: Max iterations check
test_case "Max iterations limit"
for i in {3..10}; do
  "$RALPH_SCRIPT" iterate > /dev/null 2>&1 || true
done
# After 10 iterations, should be disabled
if [[ ! -f ".ralph-mode/state.md" ]]; then
  pass
else
  fail "Should have stopped at max iterations"
fi

# Test 6: Re-enable for more tests
"$RALPH_SCRIPT" enable "Another task" > /dev/null 2>&1

# Test 7: Disable
test_case "Disable command"
if "$RALPH_SCRIPT" disable | grep -q "disabled"; then
  if [[ ! -d ".ralph-mode" ]]; then
    pass
  else
    fail "Directory not removed"
  fi
else
  fail "Disable message not shown"
fi

# Test 8: Enable without options
test_case "Enable with minimal options"
if "$RALPH_SCRIPT" enable "Simple task" > /dev/null 2>&1; then
  if [[ -f ".ralph-mode/state.md" ]]; then
    pass
  else
    fail "State file not created"
  fi
else
  fail "Command failed"
fi

# Cleanup
"$RALPH_SCRIPT" disable > /dev/null 2>&1 || true

# Test 9: Enable without prompt should fail
test_case "Enable without prompt fails"
if ! "$RALPH_SCRIPT" enable 2>&1 | grep -q "No prompt"; then
  fail "Should require prompt"
else
  pass
fi

# Summary
echo ""
echo "================================"
echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo ""

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

echo "✅ All tests passed!"
