#!/usr/bin/env bash
# ==============================================================================
# AgroVision Service Installation Script for Raspberry Pi
# ==============================================================================
set -e

SERVICE_FILE="/etc/systemd/system/agrovision.service"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing AgroVision service from ${CURRENT_DIR}/systemd/agrovision.service..."

# Create systemd service with current working directory
sudo sed -e "s|/home/pi/AgroVision/raspberry_pi|${CURRENT_DIR}|g" \
    "${CURRENT_DIR}/systemd/agrovision.service" | sudo tee "${SERVICE_FILE}" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable agrovision.service
sudo systemctl start agrovision.service

echo "AgroVision service installed and started successfully!"
echo "Check status with: sudo systemctl status agrovision.service"
echo "View live logs with: sudo journalctl -u agrovision.service -f"
