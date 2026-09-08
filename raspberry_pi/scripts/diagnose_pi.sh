#!/usr/bin/env bash
# ==============================================================================
# AgroVision Raspberry Pi 3B+ Hardware Inspection & Diagnostic Script
# ==============================================================================

echo "=========================================================="
echo "🍓 AgroVision Raspberry Pi Hardware & Bus Inspection"
echo "=========================================================="

echo -e "\n--- 1. CPU & Raspberry Pi Board Model ---"
cat /proc/cpuinfo | grep -E 'Model|Hardware|Revision|Processor' || true

echo -e "\n--- 2. OS & Kernel ---"
cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION' || true
uname -a

echo -e "\n--- 3. Python Version ---"
python3 --version || true

echo -e "\n--- 4. I2C Bus Detection (OLED Display: 0x3C or 0x3D) ---"
if command -v i2cdetect >/dev/null 2>&1; then
    i2cdetect -y 1 || true
else
    echo "i2c-tools not installed. Run: sudo apt install -y i2c-tools"
fi

echo -e "\n--- 5. Audio Playback Devices (Speaker / 3.5mm / USB / HDMI) ---"
aplay -l || true

echo -e "\n--- 6. Audio Recording Devices (Microphone / USB Mic) ---"
arecord -l || true

echo -e "\n--- 7. Connected USB Devices ---"
lsusb || true

echo -e "\n--- 8. Network Interfaces & IP Addresses ---"
ip addr || ifconfig || true

echo -e "\n--- 9. Bluetooth Devices ---"
if command -v bluetoothctl >/dev/null 2>&1; then
    bluetoothctl devices || true
fi

echo -e "\n--- 10. Thermal & Under-Voltage Status ---"
if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd get_throttled || true
    vcgencmd measure_temp || true
fi

echo -e "\n--- 11. Camera Hardware Diagnostics ---"
echo "A. Checking Pi CSI Camera (libcamera / rpicam):"
if command -v libcamera-still >/dev/null 2>&1; then
    libcamera-still --list-cameras || true
elif command -v rpicam-still >/dev/null 2>&1; then
    rpicam-still --list-cameras || true
else
    echo "libcamera-still / rpicam-still not found."
fi

echo "B. Checking V4L2 Video Devices:"
ls -la /dev/video* 2>/dev/null || echo "No /dev/video* devices found."
if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices || true
fi

echo -e "\n=========================================================="
echo "Inspection complete."
echo "=========================================================="
