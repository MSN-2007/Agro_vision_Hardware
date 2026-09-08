#!/usr/bin/env bash
# ==============================================================================
# AgroVision Raspberry Pi — OS Dependency Installer
# ==============================================================================
# Run this ONCE on the Raspberry Pi to install all OS-level dependencies,
# enable hardware interfaces (I2C, camera), and set up the Python virtual env.
#
# Usage:
#   chmod +x scripts/install.sh
#   ./scripts/install.sh
#
# Safe to run multiple times (idempotent).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_section() { echo -e "\n${BOLD}==============================${NC}"; echo -e "${BOLD}$*${NC}"; echo -e "${BOLD}==============================${NC}"; }

# ------------------------------------------------------------------------------
# 0. Sanity checks
# ------------------------------------------------------------------------------
log_section "AgroVision Pi Installer Starting"

if [[ "$EUID" -ne 0 ]]; then
    log_error "This script must be run with sudo or as root."
    echo "Usage: sudo ./scripts/install.sh"
    exit 1
fi

# Detect OS
if [[ ! -f /etc/os-release ]]; then
    log_error "Cannot detect OS (/etc/os-release missing). Is this a Raspberry Pi?"
    exit 1
fi
source /etc/os-release
log_info "Detected OS: ${PRETTY_NAME:-Unknown}"

# Detect architecture
ARCH=$(uname -m)
log_info "Architecture: ${ARCH}"

if [[ ! "$ARCH" =~ ^(armv7l|aarch64|armv6l)$ ]]; then
    log_warn "Architecture '${ARCH}' is not a typical Raspberry Pi architecture."
    log_warn "Continuing anyway (some hardware packages may not be available)."
fi

# ------------------------------------------------------------------------------
# 1. System update (optional but recommended)
# ------------------------------------------------------------------------------
log_section "1. Updating Package Lists"
apt-get update -qq || log_warn "apt-get update had warnings (may be network or mirror issue)"

# ------------------------------------------------------------------------------
# 2. Core system packages
# ------------------------------------------------------------------------------
log_section "2. Installing Core System Dependencies"

PACKAGES=(
    # Python runtime
    python3
    python3-pip
    python3-venv
    python3-dev

    # I2C tools (OLED display via I2C)
    i2c-tools
    python3-smbus

    # Audio dependencies (microphone + speaker)
    portaudio19-dev
    python3-pyaudio
    alsa-utils
    espeak-ng
    libespeak-ng1

    # Camera utilities
    v4l-utils
    ffmpeg

    # Network utilities
    curl
    wget
    rsync

    # System utilities
    git
)

log_info "Installing: ${PACKAGES[*]}"
apt-get install -y --no-install-recommends "${PACKAGES[@]}" || {
    log_warn "Some packages failed to install. Continuing..."
}

# ------------------------------------------------------------------------------
# 3. Enable I2C interface (for OLED display)
# ------------------------------------------------------------------------------
log_section "3. Enabling I2C Interface"

if command -v raspi-config &> /dev/null; then
    raspi-config nonint do_i2c 0
    log_info "I2C interface enabled via raspi-config"
else
    # Fallback: manually enable I2C in config
    if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null && \
       ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
        CONFIG_FILE="/boot/config.txt"
        [[ -f "/boot/firmware/config.txt" ]] && CONFIG_FILE="/boot/firmware/config.txt"
        echo "dtparam=i2c_arm=on" >> "${CONFIG_FILE}"
        log_info "I2C enabled in ${CONFIG_FILE} (reboot required)"
    else
        log_info "I2C already enabled in boot config"
    fi
fi

# Load I2C kernel module now
modprobe i2c-dev 2>/dev/null || log_warn "Could not modprobe i2c-dev (will be available after reboot)"

# Add pi user to i2c group
if id -u pi &>/dev/null; then
    usermod -aG i2c,gpio,video,audio pi || true
    log_info "User 'pi' added to hardware groups: i2c, gpio, video, audio"
fi

# ------------------------------------------------------------------------------
# 4. Enable camera (for Pi CSI camera module)
# ------------------------------------------------------------------------------
log_section "4. Checking Camera Configuration"

if command -v raspi-config &> /dev/null; then
    # On Bookworm/newer: libcamera is default, no separate enable needed
    log_info "Camera check: raspi-config available. libcamera is auto-enabled on Pi OS Bookworm+"
else
    log_warn "raspi-config not found. Ensure camera is enabled manually if using CSI camera."
fi

# Check if libcamera or rpicam is available
if command -v libcamera-still &>/dev/null; then
    log_info "libcamera-still found: $(which libcamera-still)"
elif command -v rpicam-still &>/dev/null; then
    log_info "rpicam-still found: $(which rpicam-still)"
else
    log_warn "libcamera-still / rpicam-still not found. Install with:"
    log_warn "  sudo apt-get install -y libcamera-apps"
fi

# ------------------------------------------------------------------------------
# 5. Python virtual environment
# ------------------------------------------------------------------------------
log_section "5. Setting Up Python Virtual Environment"

VENV_DIR="${APP_DIR}/venv"

if [[ -d "${VENV_DIR}" ]]; then
    log_info "Virtual environment already exists at ${VENV_DIR}"
else
    log_info "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    log_info "Virtual environment created"
fi

# Upgrade pip inside venv
log_info "Upgrading pip in virtual environment..."
"${VENV_DIR}/bin/pip" install --upgrade pip --quiet

# ------------------------------------------------------------------------------
# 6. Install Python dependencies
# ------------------------------------------------------------------------------
log_section "6. Installing Python Dependencies"

REQUIREMENTS="${APP_DIR}/requirements.txt"

if [[ ! -f "${REQUIREMENTS}" ]]; then
    log_error "requirements.txt not found at ${REQUIREMENTS}"
    exit 1
fi

log_info "Installing core requirements..."
"${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS}" --quiet

# Hardware-specific: install luma.oled for OLED display (may fail on non-Pi)
log_info "Attempting to install hardware-specific packages..."
"${VENV_DIR}/bin/pip" install luma.oled>=3.13.0 --quiet 2>/dev/null && \
    log_info "luma.oled installed (OLED display driver)" || \
    log_warn "luma.oled installation failed — will use console OLED fallback"

# pyttsx3 for TTS
"${VENV_DIR}/bin/pip" install pyttsx3>=2.90 --quiet 2>/dev/null && \
    log_info "pyttsx3 installed (text-to-speech)" || \
    log_warn "pyttsx3 installation failed — will use console speaker fallback"

# SpeechRecognition for microphone input
"${VENV_DIR}/bin/pip" install SpeechRecognition>=3.10.0 PyAudio>=0.2.14 --quiet 2>/dev/null && \
    log_info "SpeechRecognition + PyAudio installed (microphone input)" || \
    log_warn "SpeechRecognition/PyAudio failed — will use text-mode input"

# ------------------------------------------------------------------------------
# 7. Set up environment file
# ------------------------------------------------------------------------------
log_section "7. Setting Up Environment Configuration"

ENV_FILE="${APP_DIR}/.env"
ENV_EXAMPLE="${APP_DIR}/.env.example"

if [[ -f "${ENV_FILE}" ]]; then
    log_info ".env file already exists — not overwriting"
else
    if [[ -f "${ENV_EXAMPLE}" ]]; then
        cp "${ENV_EXAMPLE}" "${ENV_FILE}"
        log_warn "Copied .env.example to .env"
        log_warn "*** EDIT ${ENV_FILE} and set BACKEND_URL to your AgroVision server address! ***"
    else
        log_warn ".env.example not found. Creating minimal .env"
        cat > "${ENV_FILE}" << 'EOF'
BACKEND_URL=http://localhost:5000
DEVICE_ID=AGRO_PI_001
DEVICE_NAME=AgroVision Field Hub
DEFAULT_FARM_ID=farm-gv-01
DEFAULT_FIELD_ID=field-mango-01
DEFAULT_USER_ID=user-ravi-01
LOG_LEVEL=INFO
USE_CONSOLE_OLED=false
AGROVISION_ENVIRONMENT=production
EOF
    fi
fi

# Secure the .env file
chmod 600 "${ENV_FILE}" 2>/dev/null || true

# ------------------------------------------------------------------------------
# 8. Create required directories
# ------------------------------------------------------------------------------
log_section "8. Creating Application Directories"

mkdir -p "${APP_DIR}/temp_media"
mkdir -p "${APP_DIR}/logs"
chown -R pi:pi "${APP_DIR}" 2>/dev/null || true
log_info "Directories created: temp_media/, logs/"

# ------------------------------------------------------------------------------
# 9. Verify installation
# ------------------------------------------------------------------------------
log_section "9. Verifying Installation"

echo ""
echo "Python:         $(${VENV_DIR}/bin/python --version 2>&1)"
echo "pip:            $(${VENV_DIR}/bin/pip --version 2>&1 | cut -d' ' -f1-2)"
echo "requests:       $(${VENV_DIR}/bin/python -c 'import requests; print(requests.__version__)' 2>/dev/null || echo 'NOT INSTALLED')"
echo "Pillow:         $(${VENV_DIR}/bin/python -c 'from PIL import Image; print("OK")' 2>/dev/null || echo 'NOT INSTALLED')"
echo "luma.oled:      $(${VENV_DIR}/bin/python -c 'import luma.oled; print("OK")' 2>/dev/null || echo 'Not installed (fallback active)')"
echo "pyttsx3:        $(${VENV_DIR}/bin/python -c 'import pyttsx3; print("OK")' 2>/dev/null || echo 'Not installed (fallback active)')"
echo "SpeechRecog:    $(${VENV_DIR}/bin/python -c 'import speech_recognition; print("OK")' 2>/dev/null || echo 'Not installed (text-mode active)')"
echo "I2C tools:      $(command -v i2cdetect &>/dev/null && echo 'OK' || echo 'NOT FOUND')"
echo ""

# ------------------------------------------------------------------------------
# Done
# ------------------------------------------------------------------------------
log_section "Installation Complete"

echo -e "${GREEN}AgroVision Pi installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit ${ENV_FILE} and set BACKEND_URL"
echo "  2. Run diagnostics: cd ${APP_DIR} && venv/bin/python scripts/hardware_diagnostics.py"
echo "  3. Test in text mode: venv/bin/python main.py --text-mode"
echo "  4. Install systemd service: sudo ./scripts/install_service.sh"
echo ""
echo "Or use deploy.sh from your developer machine to do all of this remotely."
