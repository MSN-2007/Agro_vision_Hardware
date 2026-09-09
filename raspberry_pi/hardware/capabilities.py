import os
import sys
import shutil
import subprocess
import platform
from enum import Enum
from typing import Dict, Any, Optional
from config.settings import settings
from utils.logger import logger


class HardwareState(Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class HardwareCapabilityManager:
    """
    Centralized Hardware Capability Manager.
    Tracks and probes states of OLED, microphone, camera, and speaker.
    Allows dynamic re-detection for plug-and-play peripherals without restarting.
    """

    def __init__(self):
        self._states: Dict[str, HardwareState] = {
            "oled": HardwareState.UNAVAILABLE,
            "microphone": HardwareState.DISABLED,
            "camera": HardwareState.DISABLED,
            "speaker": HardwareState.NOT_CONFIGURED,
        }
        self._details: Dict[str, str] = {}
        self._oled_driver = None
        self._camera_driver = None
        self._mic_driver = None
        self._speaker_driver = None

    def initialize_all(self):
        """Perform initial safe hardware detection at startup."""
        logger.info("[CAPABILITIES] Probing hardware capabilities...")
        self.check_oled()
        self.check_microphone()
        self.check_camera()
        self.check_speaker()
        logger.info(
            f"[CAPABILITIES] Initial status: OLED={self._states['oled'].value}, "
            f"Mic={self._states['microphone'].value}, "
            f"Camera={self._states['camera'].value}, "
            f"Speaker={self._states['speaker'].value}"
        )

    def get_status(self, device: str) -> HardwareState:
        return self._states.get(device.lower(), HardwareState.UNAVAILABLE)

    def is_available(self, device: str) -> bool:
        return self.get_status(device) == HardwareState.AVAILABLE

    def get_details(self, device: str) -> str:
        return self._details.get(device.lower(), "")

    def check_all(self) -> Dict[str, HardwareState]:
        return dict(self._states)

    def format_banner_dict(self) -> Dict[str, str]:
        """Formats hardware states for terminal startup banner."""
        display_map = {
            HardwareState.AVAILABLE: "READY",
            HardwareState.UNAVAILABLE: "NOT DETECTED",
            HardwareState.DISABLED: "DISABLED",
            HardwareState.ERROR: "ERROR",
            HardwareState.NOT_CONFIGURED: "NOT CONFIGURED",
        }
        return {
            "oled": display_map.get(self._states["oled"], "NOT DETECTED"),
            "microphone": display_map.get(self._states["microphone"], "DISABLED"),
            "camera": display_map.get(self._states["camera"], "DISABLED"),
            "speaker": display_map.get(self._states["speaker"], "NOT CONFIGURED"),
        }

    # --------------------------------------------------------------------------
    # OLED Capability & Detection
    # --------------------------------------------------------------------------

    def check_oled(self) -> HardwareState:
        oled_config = str(settings.OLED_ENABLED).lower()
        if oled_config in ("false", "0", "disabled"):
            self._states["oled"] = HardwareState.DISABLED
            self._details["oled"] = "Disabled by configuration (OLED_ENABLED=false)"
            return HardwareState.DISABLED

        # Probe I2C bus and device presence safely
        is_linux = platform.system().lower() == "linux"
        bus_num = settings.OLED_I2C_BUS
        i2c_dev = f"/dev/i2c-{bus_num}"

        if is_linux and not os.path.exists(i2c_dev):
            self._states["oled"] = HardwareState.UNAVAILABLE
            self._details["oled"] = f"I2C interface {i2c_dev} not found"
            return HardwareState.UNAVAILABLE

        detected_addr = self._probe_i2c_oled()
        if detected_addr is not None:
            try:
                from hardware.oled import LumaOledDriver
                driver = LumaOledDriver(port=bus_num, address=detected_addr)
                if driver.initialize():
                    self._oled_driver = driver
                    self._states["oled"] = HardwareState.AVAILABLE
                    self._details["oled"] = f"SSD1306 OLED ready on bus {bus_num} @ 0x{detected_addr:02X}"
                    logger.info(f"[OLED] Detected and initialized OLED @ 0x{detected_addr:02X}")
                    return HardwareState.AVAILABLE
            except Exception as e:
                self._states["oled"] = HardwareState.ERROR
                self._details["oled"] = f"OLED initialization error: {e}"
                return HardwareState.ERROR

        self._states["oled"] = HardwareState.UNAVAILABLE
        self._details["oled"] = "No OLED display responded on I2C bus"
        return HardwareState.UNAVAILABLE

    def _probe_i2c_oled(self) -> Optional[int]:
        """
        Safely tests if an OLED device acknowledges on common addresses (0x3C, 0x3D).
        Does not crash if I2C tools or bus are absent.
        """
        candidate_addresses = [settings.OLED_I2C_ADDRESS]
        for alt in [0x3C, 0x3D]:
            if alt not in candidate_addresses:
                candidate_addresses.append(alt)

        # 1. Try smbus2 / smbus if installed
        for module_name in ["smbus2", "smbus"]:
            try:
                smbus_mod = __import__(module_name)
                bus = smbus_mod.SMBus(settings.OLED_I2C_BUS)
                for addr in candidate_addresses:
                    try:
                        # Attempt a quick 1-byte read or write to test ACK
                        bus.read_byte(addr)
                        bus.close()
                        return addr
                    except Exception:
                        continue
                bus.close()
            except Exception:
                pass

        # 2. Try i2cdetect if on Linux
        if shutil.which("i2cdetect"):
            try:
                res = subprocess.run(
                    ["i2cdetect", "-y", str(settings.OLED_I2C_BUS)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    for addr in candidate_addresses:
                        hex_str = f"{addr:02x}"
                        # Look for hex address in i2cdetect grid
                        if hex_str in res.stdout.lower():
                            return addr
            except Exception:
                pass

        return None

    def detect_oled(self) -> bool:
        """Dynamic plug-and-play detection for OLED at runtime."""
        state = self.check_oled()
        return state == HardwareState.AVAILABLE

    def get_oled_driver(self):
        return self._oled_driver

    # --------------------------------------------------------------------------
    # Microphone Capability & Detection
    # --------------------------------------------------------------------------

    def check_microphone(self) -> HardwareState:
        if not settings.MICROPHONE_ENABLED:
            self._states["microphone"] = HardwareState.DISABLED
            self._details["microphone"] = "Disabled by configuration (MICROPHONE_ENABLED=false)"
            return HardwareState.DISABLED

        # Check ALSA recording devices if enabled
        if platform.system().lower() == "linux" and shutil.which("arecord"):
            try:
                res = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=2)
                if res.returncode != 0 or "no soundcards found" in res.stderr.lower() or not res.stdout.strip():
                    self._states["microphone"] = HardwareState.UNAVAILABLE
                    self._details["microphone"] = "No audio capture hardware detected (arecord -l empty)"
                    return HardwareState.UNAVAILABLE
            except Exception as e:
                self._states["microphone"] = HardwareState.ERROR
                self._details["microphone"] = f"Microphone probe error: {e}"
                return HardwareState.ERROR

        self._states["microphone"] = HardwareState.AVAILABLE
        self._details["microphone"] = "Audio capture hardware detected"
        return HardwareState.AVAILABLE

    # --------------------------------------------------------------------------
    # Camera Capability & Detection
    # --------------------------------------------------------------------------

    def check_camera(self) -> HardwareState:
        if not settings.CAMERA_ENABLED:
            self._states["camera"] = HardwareState.DISABLED
            self._details["camera"] = "Disabled by configuration (CAMERA_ENABLED=false)"
            return HardwareState.DISABLED

        # Probe camera hardware explicitly:
        # 1. Raspberry Pi CSI camera via libcamera / rpicam
        for cmd in ["rpicam-hello", "libcamera-hello", "rpicam-still", "libcamera-still"]:
            if shutil.which(cmd):
                try:
                    res = subprocess.run([cmd, "--list-cameras"], capture_output=True, text=True, timeout=3)
                    if res.returncode == 0 and "No cameras available" not in res.stdout and "Available cameras" in res.stdout:
                        self._states["camera"] = HardwareState.AVAILABLE
                        self._details["camera"] = f"Pi CSI camera detected via {cmd}"
                        return HardwareState.AVAILABLE
                except Exception:
                    pass

        # 2. USB Camera: Must NOT assume /dev/video* is a camera. Check via v4l2-ctl.
        if shutil.which("v4l2-ctl"):
            try:
                res = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and "bcm2835" not in res.stdout.lower() and "camera" in res.stdout.lower():
                    self._states["camera"] = HardwareState.AVAILABLE
                    self._details["camera"] = "V4L2 video capture device detected"
                    return HardwareState.AVAILABLE
            except Exception:
                pass

        self._states["camera"] = HardwareState.UNAVAILABLE
        self._details["camera"] = "No physical camera detected"
        return HardwareState.UNAVAILABLE

    # --------------------------------------------------------------------------
    # Speaker Capability & Detection
    # --------------------------------------------------------------------------

    def check_speaker(self) -> HardwareState:
        if not settings.SPEAKER_ENABLED:
            self._states["speaker"] = HardwareState.NOT_CONFIGURED
            self._details["speaker"] = "Audio output not configured (SPEAKER_ENABLED=false)"
            return HardwareState.NOT_CONFIGURED

        if platform.system().lower() == "linux" and shutil.which("aplay"):
            try:
                res = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=2)
                if res.returncode != 0 or "no soundcards found" in res.stderr.lower():
                    self._states["speaker"] = HardwareState.UNAVAILABLE
                    self._details["speaker"] = "No playback device detected"
                    return HardwareState.UNAVAILABLE
            except Exception:
                pass

        self._states["speaker"] = HardwareState.AVAILABLE
        self._details["speaker"] = "Audio playback device ready"
        return HardwareState.AVAILABLE


# Global capability manager instance
hardware_manager = HardwareCapabilityManager()
