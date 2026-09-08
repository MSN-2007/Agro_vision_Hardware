#!/usr/bin/env bash
# ==============================================================================
# AgroVision Raspberry Pi — Uninstall Script
# ==============================================================================
# Removes the AgroVision systemd service and optionally removes the
# application directory.
#
# Usage:
#   sudo ./scripts/uninstall.sh             # Remove service only
#   sudo ./scripts/uninstall.sh --full      # Remove service + app directory
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="agrovision-pi"

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

FULL_UNINSTALL=false
[[ "${1:-}" == "--full" ]] && FULL_UNINSTALL=true

echo -e "${RED}=== AgroVision Pi Uninstall ===${NC}"

if [[ "$EUID" -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} Run with sudo."
    exit 1
fi

# Stop and disable service
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo -e "${YELLOW}[INFO]${NC} Stopping ${SERVICE_NAME}..."
    systemctl stop "${SERVICE_NAME}"
fi

if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo -e "${YELLOW}[INFO]${NC} Disabling ${SERVICE_NAME}..."
    systemctl disable "${SERVICE_NAME}"
fi

# Remove service file
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
if [[ -f "${SERVICE_FILE}" ]]; then
    rm -f "${SERVICE_FILE}"
    echo -e "${GREEN}[INFO]${NC} Removed ${SERVICE_FILE}"
fi

systemctl daemon-reload
echo -e "${GREEN}[INFO]${NC} Systemd reloaded."

if [[ "${FULL_UNINSTALL}" == true ]]; then
    echo -e "${RED}[WARN]${NC} Removing application directory: ${APP_DIR}"
    read -r -p "Are you sure? (y/N) " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "${APP_DIR}"
        echo -e "${GREEN}[INFO]${NC} Application directory removed."
    else
        echo "Cancelled. Application files kept."
    fi
fi

echo -e "${GREEN}[DONE]${NC} AgroVision Pi service uninstalled."
