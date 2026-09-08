#!/usr/bin/env bash
# ==============================================================================
# AgroVision Raspberry Pi — Hardware Test Runner
# ==============================================================================
# Runs all hardware diagnostic tests sequentially and reports PASS/FAIL.
#
# Usage (from raspberry_pi/ directory):
#   ./scripts/test_hardware.sh
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Find Python — prefer venv
PYTHON="${APP_DIR}/venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON="python3"
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

run_test() {
    local name="$1"
    local args="$2"
    echo -e "\n${YELLOW}--- Testing: ${name} ---${NC}"
    if cd "${APP_DIR}" && ${PYTHON} main.py ${args}; then
        echo -e "${GREEN}[PASS] ${name}${NC}"
        ((PASS++))
    else
        echo -e "${RED}[FAIL] ${name}${NC}"
        ((FAIL++))
    fi
}

echo ""
echo "=============================================="
echo "  AgroVision Pi — Hardware Test Suite"
echo "=============================================="
echo "Python: $(${PYTHON} --version 2>&1)"
echo ""

run_test "OLED Display"        "--test-display"
run_test "Microphone"          "--test-microphone"
run_test "Speaker / TTS"       "--test-speaker"
run_test "Camera"              "--test-camera"
run_test "Network / Backend"   "--test-network"
run_test "Backend API"         "--test-backend"
run_test "Device Identity"     "--test-device"
run_test "Realtime SSE"        "--test-realtime"
run_test "Health Check"        "--health"

echo ""
echo "=============================================="
echo -e "  PASSED: ${GREEN}${PASS}${NC}  FAILED: ${RED}${FAIL}${NC}"
echo "=============================================="

[[ ${FAIL} -eq 0 ]] && exit 0 || exit 1
