#!/usr/bin/env bash
# ==============================================================================
# AgroVision Raspberry Pi — SSH Deployment Script
# ==============================================================================
# Deploys the AgroVision Pi client from your development machine to a
# Raspberry Pi over SSH. Run this from the raspberry_pi/ directory.
#
# Usage:
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh pi@192.168.1.100
#   ./scripts/deploy.sh pi@192.168.1.100 /home/pi/agrovision-pi
#
# Requirements (on developer machine):
#   - ssh client
#   - rsync
#   - SSH key auth set up (recommended: ssh-copy-id pi@<PI_IP>)
#
# What this script does:
#   1. Verify SSH connection
#   2. Create application directory on Pi
#   3. rsync project files (excludes .env, __pycache__, venv, temp_media, .git)
#   4. Run install.sh on Pi (installs OS deps + Python venv)
#   5. Install systemd service
#   6. Reload, enable, and restart service
#   7. Show service status
#   8. Run health check
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Arguments
# ------------------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <user@pi-host> [remote-app-dir]"
    echo "Example: $0 pi@192.168.1.100"
    echo "Example: $0 pi@192.168.1.100 /home/pi/agrovision-pi"
    exit 1
fi

PI_HOST="$1"
REMOTE_DIR="${2:-/home/pi/agrovision-pi}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="agrovision-pi"
SERVICE_FILE="agrovision-pi.service"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[DEPLOY]${NC} $*"; }
log_error()   { echo -e "${RED}[DEPLOY ERROR]${NC} $*"; }
log_section() { echo -e "\n${BOLD}── $* ──────────────────────────────────────────${NC}"; }

# ------------------------------------------------------------------------------
# Step 1: Verify SSH connection
# ------------------------------------------------------------------------------
log_section "Step 1: Verifying SSH connection to ${PI_HOST}"

if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "${PI_HOST}" "echo 'SSH OK'" &>/dev/null; then
    log_error "Cannot connect to ${PI_HOST} via SSH."
    echo ""
    echo "Troubleshooting:"
    echo "  1. Ensure the Pi is powered on and connected to the same network."
    echo "  2. Verify the IP address: nmap -sn 192.168.1.0/24 | grep -i raspberry"
    echo "  3. Set up SSH key auth:  ssh-copy-id ${PI_HOST}"
    echo "  4. Try manual connection: ssh ${PI_HOST}"
    exit 1
fi
log_info "SSH connection to ${PI_HOST} verified ✓"

# Get Pi info
PI_INFO=$(ssh "${PI_HOST}" "hostname && cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"' && uname -m" 2>/dev/null || echo "Unknown")
log_info "Remote host info: ${PI_INFO//$'\n'/ | }"

# ------------------------------------------------------------------------------
# Step 2: Create application directory
# ------------------------------------------------------------------------------
log_section "Step 2: Creating remote directory ${REMOTE_DIR}"

ssh "${PI_HOST}" "mkdir -p ${REMOTE_DIR}"
log_info "Directory ${REMOTE_DIR} ready ✓"

# ------------------------------------------------------------------------------
# Step 3: Sync project files
# ------------------------------------------------------------------------------
log_section "Step 3: Syncing project files via rsync"

# Build rsync exclude list
EXCLUDES=(
    --exclude='.env'                 # Never copy secrets
    --exclude='config/device_config.json'  # Device-specific, generated on Pi
    --exclude='__pycache__/'
    --exclude='*.pyc'
    --exclude='*.pyo'
    --exclude='*.egg-info/'
    --exclude='.git/'
    --exclude='.gitignore'           # Keep Pi's own gitignore if any
    --exclude='venv/'
    --exclude='.venv/'
    --exclude='temp_media/'
    --exclude='logs/'
    --exclude='*.log'
    --exclude='recording_state.json'
    --exclude='.vscode/'
    --exclude='.DS_Store'
    --exclude='dist/'
    --exclude='build/'
    --exclude='node_modules/'
)

log_info "Syncing ${APP_DIR}/ → ${PI_HOST}:${REMOTE_DIR}/"
rsync -avz --progress "${EXCLUDES[@]}" \
    "${APP_DIR}/" \
    "${PI_HOST}:${REMOTE_DIR}/"

log_info "Files synced ✓"

# ------------------------------------------------------------------------------
# Step 4: Make scripts executable
# ------------------------------------------------------------------------------
log_section "Step 4: Setting script permissions"

ssh "${PI_HOST}" "chmod +x ${REMOTE_DIR}/scripts/*.sh 2>/dev/null || true"
log_info "Script permissions set ✓"

# ------------------------------------------------------------------------------
# Step 5: Run install.sh on Pi
# ------------------------------------------------------------------------------
log_section "Step 5: Running install.sh on Pi (this may take a few minutes)"

log_warn "You may be asked for the sudo password on the Pi."
ssh -t "${PI_HOST}" "cd ${REMOTE_DIR} && sudo bash scripts/install.sh"
log_info "install.sh completed ✓"

# ------------------------------------------------------------------------------
# Step 6: Install systemd service
# ------------------------------------------------------------------------------
log_section "Step 6: Installing systemd service"

# Update the WorkingDirectory path in the service file and copy to systemd
ssh "${PI_HOST}" "
    REMOTE_DIR='${REMOTE_DIR}'
    SERVICE_SRC='${REMOTE_DIR}/systemd/${SERVICE_FILE}'

    if [[ ! -f \"\${SERVICE_SRC}\" ]]; then
        echo '[ERROR] Service file not found: '\${SERVICE_SRC}''
        exit 1
    fi

    # Patch WorkingDirectory and ExecStart with actual remote dir
    sed -e \"s|WorkingDirectory=.*|WorkingDirectory=\${REMOTE_DIR}|g\" \\
        -e \"s|ExecStart=.*|ExecStart=\${REMOTE_DIR}/venv/bin/python main.py|g\" \\
        -e \"s|EnvironmentFile=.*|EnvironmentFile=-\${REMOTE_DIR}/.env|g\" \\
        \"\${SERVICE_SRC}\" | sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null

    echo 'Service file installed to /etc/systemd/system/${SERVICE_NAME}.service'
"
log_info "Systemd service file installed ✓"

# ------------------------------------------------------------------------------
# Step 7: Enable and start service
# ------------------------------------------------------------------------------
log_section "Step 7: Enabling and starting agrovision-pi service"

ssh "${PI_HOST}" "
    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME}.service
    sudo systemctl restart ${SERVICE_NAME}.service
    sleep 3
"
log_info "Service enabled and started ✓"

# ------------------------------------------------------------------------------
# Step 8: Show service status
# ------------------------------------------------------------------------------
log_section "Step 8: Service Status"

echo ""
ssh "${PI_HOST}" "sudo systemctl status ${SERVICE_NAME}.service --no-pager -l" || true

# ------------------------------------------------------------------------------
# Step 9: Run health check
# ------------------------------------------------------------------------------
log_section "Step 9: Running Health Check"

sleep 2
ssh "${PI_HOST}" "
    cd ${REMOTE_DIR}
    echo ''
    echo '--- AgroVision Pi Health Check ---'
    ${REMOTE_DIR}/venv/bin/python main.py --health 2>&1 || echo '[WARN] Health check unavailable right now — service may still be starting'
" || true

# ------------------------------------------------------------------------------
# Done
# ------------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}============================================${NC}"
echo -e "${GREEN}${BOLD}  AgroVision Pi Deployment Complete! ✓${NC}"
echo -e "${GREEN}${BOLD}============================================${NC}"
echo ""
echo "Useful commands on the Pi (ssh ${PI_HOST}):"
echo "  sudo systemctl status ${SERVICE_NAME}          # Check service"
echo "  sudo journalctl -u ${SERVICE_NAME} -f          # Live logs"
echo "  sudo systemctl restart ${SERVICE_NAME}         # Restart"
echo "  cd ${REMOTE_DIR} && venv/bin/python main.py --text-mode   # Interactive test"
echo "  cd ${REMOTE_DIR} && venv/bin/python main.py --health      # Health check"
echo ""
echo "To redeploy after code changes:"
echo "  ./scripts/deploy.sh ${PI_HOST}"
echo ""
