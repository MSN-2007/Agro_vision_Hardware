from hardware.base import AudioInputDriver, AudioOutputDriver
from ui.display_manager import DisplayManager
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from utils.logger import logger
from typing import Optional

class VoiceService:
    def __init__(
        self,
        mic: AudioInputDriver,
        speaker: AudioOutputDriver,
        display: DisplayManager,
        api: AgroVisionApiService,
        auth: AuthService,
        camera_service = None
    ):
        self.mic = mic
        self.speaker = speaker
        self.display = display
        self.api = api
        self.auth = auth
        self.camera_service = camera_service

    def run_interaction_cycle(self, text_input: str = None) -> bool:
        if text_input is None:
            self.display.show_listening()
            spoken_text = self.mic.listen_and_transcribe("Speak your command")
            if not spoken_text:
                return False
        else:
            spoken_text = text_input.strip()
            if not spoken_text:
                return False

        logger.info(f"[VOICE] Command input: '{spoken_text}'")
        self.display.show_thinking()

        farm_id = self.auth.device_config.farmId
        field_id = self.auth.device_config.fieldId
        response = self.api.converse(spoken_text, farm_id=farm_id, field_id=field_id)

        # Handle Camera Intents
        from hardware.capabilities import hardware_manager
        if response.intent in ("TAKE_PHOTO", "START_VIDEO", "STOP_VIDEO"):
            if not hardware_manager.is_available("camera"):
                print("\n📷 Camera is currently unavailable.")
                print("   Connect a supported camera to enable photo capture.\n")
                self.display.show_camera_error("Camera unavailable")
                return True

            if response.intent == "TAKE_PHOTO":
                if self.camera_service:
                    self.camera_service.capture_photo(farm_id=farm_id, field_id=field_id)
                return True
            elif response.intent == "START_VIDEO":
                if self.camera_service:
                    self.camera_service.start_video(farm_id=farm_id, field_id=field_id)
                return True
            elif response.intent == "STOP_VIDEO":
                if self.camera_service:
                    self.camera_service.stop_video()
                return True

        # Standard voice/AI response
        self.display.show_speaking(response.oledText)
        if response.speak and response.text:
            self.speaker.speak(response.text)

        return True

