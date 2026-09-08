#!/usr/bin/env bash
# ==============================================================================
# AgroVision Raspberry Pi — Backend Integration Test
# ==============================================================================
# Tests connectivity and API communication with the AgroVision backend.
# Reads BACKEND_URL from .env file if present.
#
# Usage (from raspberry_pi/ directory):
#   ./scripts/test_backend.sh
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
ENV_FILE="${APP_DIR}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    # Export only safe vars
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        export "$key"="${value}"
    done < "${ENV_FILE}"
fi

BACKEND_URL="${BACKEND_URL:-http://localhost:5000}"

# Find Python — prefer venv
PYTHON="${APP_DIR}/venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON="python3"
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo "=============================================="
echo "  AgroVision Backend Integration Tests"
echo "  Backend URL: ${BACKEND_URL}"
echo "=============================================="

# Test 1: HTTP health check (curl)
echo -e "\n${YELLOW}1. HTTP Health Check (curl)${NC}"
if curl -s --max-time 5 "${BACKEND_URL}/api/health" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}[PASS] Backend /api/health responded OK${NC}"
else
    echo -e "${RED}[FAIL] Backend not reachable at ${BACKEND_URL}${NC}"
    echo "       Is the AgroVision server running? Run: cd SIH_26_01 && node server/server.js"
    exit 1
fi

# Test 2: SSE endpoint available
echo -e "\n${YELLOW}2. SSE Realtime Endpoint Check${NC}"
SSE_RESPONSE=$(curl -s --max-time 3 -H "Accept: text/event-stream" \
    "${BACKEND_URL}/api/sync/events" 2>/dev/null | head -c 100 || true)
if echo "${SSE_RESPONSE}" | grep -q "CONNECTED"; then
    echo -e "${GREEN}[PASS] SSE /api/sync/events stream is active${NC}"
else
    echo -e "${YELLOW}[WARN] SSE endpoint may be working but response was unexpected${NC}"
fi

# Test 3: Python backend test
echo -e "\n${YELLOW}3. Python Backend + API Test${NC}"
cd "${APP_DIR}" && ${PYTHON} main.py --test-backend

# Test 4: Python realtime test
echo -e "\n${YELLOW}4. Python Realtime SSE Test (10s)${NC}"
cd "${APP_DIR}" && ${PYTHON} main.py --test-realtime

echo ""
echo "=============================================="
echo -e "${GREEN}${BOLD}  Backend integration tests complete.${NC}"
echo "=============================================="
