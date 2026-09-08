#!/usr/bin/env python3
"""
AgroVision Raspberry Pi Hardware Diagnostic Utility
Inspects connected hardware, audio, I2C devices, throttling, and network.
"""
import subprocess
import platform
import os
import sys

def run_cmd(cmd, desc):
    print(f"\n--- {desc} [{cmd}] ---")
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        out = proc.stdout.strip() or proc.stderr.strip()
        print(out if out else "(No output)")
        return proc.returncode == 0
    except Exception as e:
        print(f"Unavailable or error: {e}")
        return False

def main():
    print("=" * 60)
    print("🍓 AGROVISION RASPBERRY PI 3B+ HARDWARE DIAGNOSTICS")
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python:   {sys.version.split()[0]}")
    print("=" * 60)

    is_linux = platform.system().lower() == "linux"

    if is_linux:
        run_cmd("cat /proc/cpuinfo | grep -E 'Model|Hardware|Revision'", "CPU / Board Model")
        run_cmd("cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION_ID'", "OS Release")
        run_cmd("ip addr | grep -E 'inet |state UP'", "Network Interfaces & IP")
        run_cmd("i2cdetect -y 1", "I2C Bus Scan (OLED check on 0x3C/0x3D)")
        run_cmd("aplay -l", "Audio Playback Devices (Speaker check)")
        run_cmd("arecord -l", "Audio Recording Devices (Microphone check)")
        run_cmd("lsusb", "Connected USB Peripherals")
        run_cmd("vcgencmd get_throttled", "Power & Thermal Throttling Status")
        run_cmd("libcamera-still --list-cameras 2>/dev/null || rpicam-still --list-cameras 2>/dev/null", "Pi CSI Camera Detection")
        run_cmd("v4l2-ctl --list-devices 2>/dev/null || ls -la /dev/video* 2>/dev/null", "V4L2 Video & USB Devices")
    else:
        print("\n[NOTE] Running in simulated / non-Linux development environment.")
        print("Emulated diagnostics:")
        print("  - OLED: Fallback to ConsoleOledDriver (ASCII 128x64 display buffer)")
        print("  - Audio Input: Fallback to TextModeAudioDriver (interactive console)")
        print("  - Audio Output: Fallback to ConsoleSpeakerDriver")
        print("  - Camera: SimulatedCameraDriver (Field Imagery Emulation) active")
        print("  - Network: IP socket resolution active")
        print("  - On Linux Raspberry Pi, hardware drivers use luma.oled (I2C 0x3C), pyaudio/speech_recognition, and libcamera/v4l2")

    print("\n" + "=" * 60)
    print("AgroVision Hardware Diagnostic Complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
