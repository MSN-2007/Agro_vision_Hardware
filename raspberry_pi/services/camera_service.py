import os
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from utils.logger import logger
from hardware.camera import CameraDriver, get_camera_driver
from ui.display_manager import DisplayManager
from hardware.base import AudioOutputDriver
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from config.settings import settings

class CameraService:
    def __init__(
        self,
        driver: Optional[CameraDriver] = None,
        display: Optional[DisplayManager] = None,
        speaker: Optional[AudioOutputDriver] = None,
        api: Optional[AgroVisionApiService] = None,
        auth: Optional[AuthService] = None,
        max_video_duration: int = 30
    ):
        self.driver = driver or get_camera_driver()
        self.display = display
        self.speaker = speaker
        self.api = api or AgroVisionApiService()
        self.auth = auth or AuthService()
        self.max_video_duration = max_video_duration

        self.temp_dir = os.path.join(str(settings.BASE_DIR), "temp_media")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.state_file = os.path.join(self.temp_dir, "recording_state.json")

        self.is_recording = False
        self.recording_thread = None
        self.active_farm_id = None
        self.active_field_id = None
        self.video_output_path = None

    def initialize(self) -> bool:
        return self.driver.initialize()

    def check_camera(self) -> Dict[str, Any]:
        return self.driver.check_camera()

    def capture_photo(
        self,
        farm_id: Optional[str] = None,
        field_id: Optional[str] = None,
        caption: str = "Field camera capture"
    ) -> Optional[Dict[str, Any]]:
        """
        Executes complete photo workflow:
        Capture -> Upload to backend -> Create Media DB Record -> Update OLED -> Speak TTS
        """
        f_id = farm_id or self.auth.device_config.farmId
        fld_id = field_id or self.auth.device_config.fieldId

        # Guard: Check camera capability
        if hasattr(self.driver, "is_available") and not self.driver.is_available:
            logger.info("[CAMERA] Photo capture skipped: camera is currently unavailable.")
            if self.display:
                self.display.show_camera_error("Camera unavailable")
            return None

        logger.info(f"[CAMERA] Starting photo capture for farm={f_id}, field={fld_id}")
        if self.display:
            self.display.show_taking_photo()

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        temp_photo_path = os.path.join(self.temp_dir, f"photo_{timestamp_str}.jpg")

        # 1. Capture photo via hardware HAL
        result = self.driver.capture_photo(temp_photo_path)
        if not result or not os.path.exists(temp_photo_path):
            logger.error("[CAMERA] Failed to capture photo from hardware.")
            if self.display:
                self.display.show_camera_error("Capture failed")
            if self.speaker:
                self.speaker.speak("Camera capture failed. Please check camera connection.")
            return None

        size_kb = os.path.getsize(temp_photo_path) / 1024
        resolution = result.get("resolution", "1280x720")
        logger.info(f"[CAMERA] Photo captured successfully: {temp_photo_path} ({resolution}, {size_kb:.1f} KB)")

        # 2. Upload photo to AgroVision backend
        if self.display:
            self.display.show_uploading("Photo")

        upload_res = self.api.upload_media(temp_photo_path, media_type="photo")
        if not upload_res or not upload_res.get("url"):
            logger.error("[CAMERA] Photo upload to backend storage failed.")
            if self.display:
                self.display.show_upload_failed()
            if self.speaker:
                self.speaker.speak("Photo captured, but cloud upload failed. Saved locally.")
            return None

        # 3. Create Media Database Record (Single Source of Truth)
        # IMPORTANT: Do not fabricate GPS coordinates. Latitude/longitude remain None.
        media_payload = {
            "userId": self.auth.device_config.userId,
            "farmId": f_id,
            "fieldId": fld_id,
            "cropId": None,
            "type": "photo",
            "url": upload_res["url"],
            "thumbnailUrl": upload_res["url"],
            "caption": caption,
            "latitude": None,
            "longitude": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "raspberry_pi",
            "deviceId": self.auth.device_config.deviceId
        }

        created_media = self.api.create_media(media_payload)
        logger.info(f"[CAMERA] Media record created on backend: {created_media}")

        # Resolve field name for UI
        field_name = "Assigned Field"
        try:
            fields = self.api.get_fields(f_id)
            for f in fields:
                if f.get("id") == fld_id:
                    field_name = f.get("name", field_name)
                    break
        except Exception:
            pass

        # 4. Confirmation on OLED & Speaker
        if self.display:
            self.display.show_photo_saved(field_name)
        if self.speaker:
            self.speaker.speak(f"Photo captured and saved to {field_name}.")

        return {
            "success": True,
            "filePath": temp_photo_path,
            "url": upload_res["url"],
            "resolution": resolution,
            "sizeBytes": result.get("sizeBytes", 0),
            "media": created_media
        }

    def start_video(self, farm_id: Optional[str] = None, field_id: Optional[str] = None) -> bool:
        """Starts video recording with auto-stop watchdog thread."""
        if hasattr(self.driver, "is_available") and not self.driver.is_available:
            logger.info("[CAMERA] Video recording skipped: camera is currently unavailable.")
            if self.display:
                self.display.show_camera_error("Camera unavailable")
            return False

        if self.is_recording:
            logger.warning("[CAMERA] Video recording is already in progress.")
            if self.speaker:
                self.speaker.speak("Video is already recording.")
            return False

        self.active_farm_id = farm_id or self.auth.device_config.farmId
        self.active_field_id = field_id or self.auth.device_config.fieldId

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.video_output_path = os.path.join(self.temp_dir, f"video_{timestamp_str}.mp4")

        started = self.driver.start_video(self.video_output_path)
        if not started:
            logger.error("[CAMERA] Failed to start video recording.")
            if self.display:
                self.display.show_camera_error("Video error")
            if self.speaker:
                self.speaker.speak("Could not start video recording.")
            return False

        self.is_recording = True
        logger.info(f"[CAMERA] Video recording started: {self.video_output_path} (Max: {self.max_video_duration}s)")
        
        # Save recording state to file
        import json
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "is_recording": True,
                    "video_output_path": self.video_output_path,
                    "active_farm_id": self.active_farm_id,
                    "active_field_id": self.active_field_id,
                    "start_time": time.time()
                }, f)
        except Exception as e:
            logger.warning(f"[CAMERA] Could not write recording state file: {e}")

        if self.display:
            self.display.show_recording()
        if self.speaker:
            self.speaker.speak("Recording started. Say 'Stop recording' to finish.")

        # Watchdog thread to enforce max duration
        def auto_stop_timer():
            time.sleep(self.max_video_duration)
            if self.is_recording or os.path.exists(self.state_file):
                logger.info(f"[CAMERA] Max recording duration ({self.max_video_duration}s) reached. Auto-stopping.")
                self.stop_video()

        self.recording_thread = threading.Thread(target=auto_stop_timer, daemon=True)
        self.recording_thread.start()
        return True

    def stop_video(self) -> Optional[Dict[str, Any]]:
        """Stops video recording and uploads to AgroVision cloud."""
        import json
        # Restore state from file if this is a new process
        if not self.is_recording and os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.video_output_path = data.get("video_output_path")
                    self.active_farm_id = data.get("active_farm_id")
                    self.active_field_id = data.get("active_field_id")
                    self.is_recording = True
            except Exception as e:
                logger.error(f"[CAMERA] Error reading state file: {e}")

        if not self.is_recording:
            logger.warning("[CAMERA] Stop video called but no recording active.")
            if self.speaker:
                self.speaker.speak("No active video recording to stop.")
            return None

        self.is_recording = False
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        except Exception:
            pass

        if hasattr(self.driver, "current_video_path"):
            self.driver.current_video_path = self.video_output_path

        res = self.driver.stop_video()
        if not res or not self.video_output_path or not os.path.exists(self.video_output_path):
            logger.error("[CAMERA] Video stopping failed or output missing.")
            if self.display:
                self.display.show_camera_error("Video save failed")
            return None

        duration = res.get("durationSeconds", 5.0)
        logger.info(f"[CAMERA] Video captured: {self.video_output_path} ({duration}s)")

        # Upload video
        if self.display:
            self.display.show_uploading("Video")

        upload_res = self.api.upload_media(self.video_output_path, media_type="video")
        if not upload_res or not upload_res.get("url"):
            logger.error("[CAMERA] Video upload failed.")
            if self.display:
                self.display.show_upload_failed()
            if self.speaker:
                self.speaker.speak("Video saved locally, but cloud upload failed.")
            return None

        # Create media record
        media_payload = {
            "userId": self.auth.device_config.userId,
            "farmId": self.active_farm_id,
            "fieldId": self.active_field_id,
            "cropId": None,
            "type": "video",
            "url": upload_res["url"],
            "thumbnailUrl": upload_res["url"],
            "caption": f"Field video capture ({duration:.0f}s)",
            "durationSeconds": duration,
            "latitude": None,
            "longitude": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "raspberry_pi",
            "deviceId": self.auth.device_config.deviceId
        }

        created_media = self.api.create_media(media_payload)
        logger.info(f"[CAMERA] Video media record created: {created_media}")

        if self.display:
            self.display.show_video_saved()
        if self.speaker:
            self.speaker.speak("Recording stopped and video saved to AgroVision.")

        return {
            "success": True,
            "filePath": self.video_output_path,
            "url": upload_res["url"],
            "durationSeconds": duration,
            "media": created_media
        }

    def release(self):
        if self.is_recording:
            self.stop_video()
        self.driver.release()
