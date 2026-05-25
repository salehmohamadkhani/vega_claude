#!/usr/bin/env bash
# Test Network Resilience Feature
# This script simulates network disconnection to test the resilience feature

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
DISCONNECT_DURATION=${1:-15}  # Seconds to simulate disconnection
RALPH_DIR=".ralph-mode"
MOCK_FILE="$RALPH_DIR/mock_network_down"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}🧪 NETWORK RESILIENCE TEST${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}This test will:${NC}"
echo "  1. Create a mock file that simulates network being DOWN"
echo "  2. Wait $DISCONNECT_DURATION seconds (simulating outage)"
echo "  3. Remove the mock file (simulating network restored)"
echo ""

# Create ralph-mode directory if needed
mkdir -p "$RALPH_DIR"

# Function to check if mock network is down
test_mock_network_down() {
    [[ -f "$MOCK_FILE" ]]
}

echo -e "${GREEN}📋 Test Plan:${NC}"
echo "─────────────────────────────────────────────────────────────────"
echo ""

# Step 1: Verify real network is up
echo -e "${BLUE}[Step 1] Verifying real network connection...${NC}"
if ping -c 1 -W 3 "1.1.1.1" &>/dev/null; then
    echo -e "  ${GREEN}✅ Real network is UP${NC}"
else
    echo -e "  ${YELLOW}⚠️ Real network appears down - test may not work correctly${NC}"
fi
echo ""

# Step 2: Create mock disconnect
echo -e "${BLUE}[Step 2] Simulating network DISCONNECT...${NC}"
echo "Network simulated down at $(date '+%Y-%m-%d %H:%M:%S')" > "$MOCK_FILE"
echo -e "  ${YELLOW}📁 Created mock file: $MOCK_FILE${NC}"
echo -e "  ${RED}🔌 Network status: SIMULATED DOWN${NC}"
echo ""

# Step 3: Test the detection
echo -e "${BLUE}[Step 3] Testing detection (should show DOWN)...${NC}"
if test_mock_network_down; then
    echo -e "  ${GREEN}✅ Mock network correctly detected as DOWN${NC}"
else
    echo -e "  ${RED}❌ Mock detection failed!${NC}"
fi
echo ""

# Step 4: Countdown
echo -e "${BLUE}[Step 4] Simulating outage for $DISCONNECT_DURATION seconds...${NC}"
echo ""

for ((i=DISCONNECT_DURATION; i>0; i--)); do
    elapsed=$((DISCONNECT_DURATION - i))
    progress=$((elapsed * 100 / DISCONNECT_DURATION))
    bar_filled=$((progress / 5))
    bar_empty=$((20 - bar_filled))
    
    printf "\r  ${MAGENTA}⏳ Network DOWN: %2d seconds remaining... [%s%s] %d%%${NC}" \
        "$i" \
        "$(printf '#%.0s' $(seq 1 $bar_filled 2>/dev/null) 2>/dev/null)" \
        "$(printf '.%.0s' $(seq 1 $bar_empty 2>/dev/null) 2>/dev/null)" \
        "$progress"
    
    sleep 1
done
echo ""
echo ""

# Step 5: Restore network
echo -e "${BLUE}[Step 5] Simulating network RESTORE...${NC}"
rm -f "$MOCK_FILE"
echo -e "  ${GREEN}📁 Removed mock file${NC}"
echo -e "  ${GREEN}🌐 Network status: RESTORED${NC}"
echo ""

# Step 6: Verify restore
echo -e "${BLUE}[Step 6] Testing detection (should show UP)...${NC}"
if ! test_mock_network_down; then
    echo -e "  ${GREEN}✅ Network correctly detected as UP${NC}"
else
    echo -e "  ${RED}❌ Network still showing as down!${NC}"
fi
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ NETWORK RESILIENCE TEST COMPLETE${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}To test with actual Ralph Mode:${NC}"
echo ""
echo -e "  ${WHITE}1. In Terminal 1, start Ralph:${NC}"
echo -e "     ${MAGENTA}python ralph_mode.py enable 'Test task' --max-iterations 10${NC}"
echo -e "     ${MAGENTA}./ralph-loop.sh run${NC}"
echo ""
echo -e "  ${WHITE}2. In Terminal 2, simulate disconnect:${NC}"
echo -e "     ${MAGENTA}echo 'down' > .ralph-mode/mock_network_down${NC}"
echo ""
echo -e "  ${WHITE}3. Watch Ralph wait for network...${NC}"
echo ""
echo -e "  ${WHITE}4. Restore network:${NC}"
echo -e "     ${MAGENTA}rm .ralph-mode/mock_network_down${NC}"
echo ""
