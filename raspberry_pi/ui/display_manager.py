from typing import Optional, List
from hardware.base import DisplayDriver
from hardware.capabilities import hardware_manager
from ui.states import UIState
from utils.logger import logger


class DisplayManager:
    """
    Unified UI Display Manager.
    Directs output to:
    1. Terminal output (always enabled)
    2. Physical OLED output (only if hardware is available)
    """

    def __init__(self, driver: Optional[DisplayDriver] = None, enable_terminal_output: bool = True):
        self.driver = driver
        self.enable_terminal_output = enable_terminal_output
        self.current_state = UIState.BOOT

    def set_oled_driver(self, driver: Optional[DisplayDriver]):
        self.driver = driver

    def is_oled_available(self) -> bool:
        if self.driver is not None:
            if hasattr(self.driver, "is_available"):
                return bool(self.driver.is_available)
            return True
        return hardware_manager.is_available("oled")

    def _render(self, lines: List[str], title: Optional[str] = None):
        # 1. Output to OLED if available
        if self.is_oled_available() and self.driver:
            try:
                self.driver.show_text(lines, title=title)
            except Exception as e:
                logger.warning(f"[UI] OLED render error: {e}")

        # 2. Terminal log/feedback
        if self.enable_terminal_output:
            clean_lines = [l.strip() for l in lines if l.strip()]
            header = f"[{title}] " if title else ""
            msg = " • ".join(clean_lines) if clean_lines else ""
            logger.debug(f"[UI] {header}{msg}")

    def show(self, message: str, title: Optional[str] = None):
        lines = message.split("\n")
        self._render(lines, title=title)

    def show_boot(self):
        self.current_state = UIState.BOOT
        self._render([
            "AgroVision",
            "Physical Hub",
            "Starting up..."
        ], title="BOOT")

    def show_pairing(self, code: str):
        self.current_state = UIState.PAIRING
        self._render([
            "PAIR DEVICE:",
            f"Code: {code}",
            "Enter in Mobile App",
            "or AgroVision Web"
        ], title="PAIRING")

    def show_connecting(self):
        self.current_state = UIState.CONNECTING
        self._render([
            "Connecting to",
            "AgroVision Backend...",
            "Please wait"
        ], title="NETWORK")

    def show_ready(self, farm_name: str, field_name: str):
        self.current_state = UIState.READY
        self._render([
            f"Farm: {farm_name[:18]}",
            f"Field: {field_name[:18]}",
            "",
            "ONLINE • READY",
            "Say 'Hey Vision'"
        ], title="AGROVISION")

    def show_listening(self):
        self.current_state = UIState.LISTENING
        self._render([
            "Listening...",
            "",
            "Speak your command",
            "or observation..."
        ], title="MIC ACTIVE")

    def show_thinking(self):
        self.current_state = UIState.THINKING
        self._render([
            "Thinking...",
            "Processing Intent",
            "with AgroVision AI"
        ], title="AI BRAIN")

    def show_speaking(self, oled_text: str):
        self.current_state = UIState.SPEAKING
        lines = oled_text.split("\n")
        self._render(lines, title="RESPONSE")

    def show_offline(self):
        self.current_state = UIState.OFFLINE
        self._render([
            "OFFLINE MODE",
            "Backend Unreachable",
            "Retrying Wi-Fi...",
            "Local cache active"
        ], title="OFFLINE")

    def show_error(self, message: str):
        self.current_state = UIState.ERROR
        self._render([
            "ERROR:",
            message[:40]
        ], title="ALERT")

    def show_camera_ready(self):
        self.current_state = UIState.CAMERA_READY
        self._render([
            "Camera Ready",
            "Say 'Take a picture'",
            "or 'Start recording'"
        ], title="CAMERA")

    def show_taking_photo(self):
        self.current_state = UIState.CAMERA_TAKING_PHOTO
        self._render([
            "Taking Photo...",
            "Please hold still",
            "Capturing frame..."
        ], title="CAMERA")

    def show_photo_saved(self, details: str = "Photo Saved"):
        self.current_state = UIState.CAMERA_PHOTO_SAVED
        self._render([
            "Photo Saved",
            details[:20],
            "Synced with Cloud"
        ], title="MEDIA OK")

    def show_recording(self):
        self.current_state = UIState.CAMERA_RECORDING
        self._render([
            "Recording...",
            "Video capturing",
            "Say 'Stop recording'"
        ], title="REC VIDEO")

    def show_uploading(self, media_type: str = "Media"):
        self.current_state = UIState.CAMERA_UPLOADING
        self._render([
            f"Uploading {media_type}...",
            "Connecting to Cloud",
            "Please wait"
        ], title="UPLOADING")

    def show_video_saved(self):
        self.current_state = UIState.CAMERA_VIDEO_SAVED
        self._render([
            "Video Saved",
            "Uploaded to Cloud",
            "Available on App"
        ], title="MEDIA OK")

    def show_camera_error(self, message: str = "Camera Error"):
        self.current_state = UIState.CAMERA_ERROR
        self._render([
            "Camera Error",
            message[:24],
            "Check connection"
        ], title="CAM ERROR")

    def show_upload_failed(self):
        self.current_state = UIState.CAMERA_UPLOAD_FAILED
        self._render([
            "Upload Failed",
            "Saved locally",
            "Will retry sync"
        ], title="SYNC WARN")


