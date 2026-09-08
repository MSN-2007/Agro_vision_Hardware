from hardware.base import DisplayDriver
from ui.states import UIState

class DisplayManager:
    def __init__(self, driver: DisplayDriver):
        self.driver = driver
        self.current_state = UIState.BOOT

    def show_boot(self):
        self.current_state = UIState.BOOT
        self.driver.show_text([
            "AgroVision",
            "Physical Hub",
            "Starting up..."
        ], title="BOOT")

    def show_pairing(self, code: str):
        self.current_state = UIState.PAIRING
        self.driver.show_text([
            "PAIR DEVICE:",
            f"Code: {code}",
            "Enter in Mobile App",
            "or AgroVision Web"
        ], title="PAIRING")

    def show_connecting(self):
        self.current_state = UIState.CONNECTING
        self.driver.show_text([
            "Connecting to",
            "AgroVision Backend...",
            "Please wait"
        ], title="NETWORK")

    def show_ready(self, farm_name: str, field_name: str):
        self.current_state = UIState.READY
        self.driver.show_text([
            f"Farm: {farm_name[:18]}",
            f"Field: {field_name[:18]}",
            "",
            "ONLINE • READY",
            "Say 'Hey Vision'"
        ], title="AGROVISION")

    def show_listening(self):
        self.current_state = UIState.LISTENING
        self.driver.show_text([
            "Listening...",
            "",
            "Speak your command",
            "or observation..."
        ], title="MIC ACTIVE")

    def show_thinking(self):
        self.current_state = UIState.THINKING
        self.driver.show_text([
            "Thinking...",
            "Processing Intent",
            "with AgroVision AI"
        ], title="AI BRAIN")

    def show_speaking(self, oled_text: str):
        self.current_state = UIState.SPEAKING
        lines = oled_text.split("\n")
        self.driver.show_text(lines, title="RESPONSE")

    def show_offline(self):
        self.current_state = UIState.OFFLINE
        self.driver.show_text([
            "OFFLINE MODE",
            "Backend Unreachable",
            "Retrying Wi-Fi...",
            "Local cache active"
        ], title="OFFLINE")

    def show_error(self, message: str):
        self.current_state = UIState.ERROR
        self.driver.show_text([
            "ERROR:",
            message[:40]
        ], title="ALERT")

    def show_camera_ready(self):
        self.current_state = UIState.CAMERA_READY
        self.driver.show_text([
            "Camera Ready",
            "Say 'Take a picture'",
            "or 'Start recording'"
        ], title="CAMERA")

    def show_taking_photo(self):
        self.current_state = UIState.CAMERA_TAKING_PHOTO
        self.driver.show_text([
            "Taking Photo...",
            "Please hold still",
            "Capturing frame..."
        ], title="CAMERA")

    def show_photo_saved(self, details: str = "Photo Saved"):
        self.current_state = UIState.CAMERA_PHOTO_SAVED
        self.driver.show_text([
            "Photo Saved",
            details[:20],
            "Synced with Cloud"
        ], title="MEDIA OK")

    def show_recording(self):
        self.current_state = UIState.CAMERA_RECORDING
        self.driver.show_text([
            "Recording...",
            "Video capturing",
            "Say 'Stop recording'"
        ], title="REC VIDEO")

    def show_uploading(self, media_type: str = "Media"):
        self.current_state = UIState.CAMERA_UPLOADING
        self.driver.show_text([
            f"Uploading {media_type}...",
            "Connecting to Cloud",
            "Please wait"
        ], title="UPLOADING")

    def show_video_saved(self):
        self.current_state = UIState.CAMERA_VIDEO_SAVED
        self.driver.show_text([
            "Video Saved",
            "Uploaded to Cloud",
            "Available on App"
        ], title="MEDIA OK")

    def show_camera_error(self, message: str = "Camera Error"):
        self.current_state = UIState.CAMERA_ERROR
        self.driver.show_text([
            "Camera Error",
            message[:24],
            "Check connection"
        ], title="CAM ERROR")

    def show_upload_failed(self):
        self.current_state = UIState.CAMERA_UPLOAD_FAILED
        self.driver.show_text([
            "Upload Failed",
            "Saved locally",
            "Will retry sync"
        ], title="SYNC WARN")

