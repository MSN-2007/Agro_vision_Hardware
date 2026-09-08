import os
import requests
from config.settings import settings
from utils.logger import logger
from models.response import AssistantResponse
from typing import Optional, Dict, Any, List

class AgroVisionApiService:
    """
    AgroVision Backend REST API client for the Raspberry Pi.

    All communication flows through this service.
    The Pi NEVER directly accesses the database.
    All AI processing is handled server-side — this service only sends/receives HTTP.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.BACKEND_URL).rstrip("/")
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self, user_id: Optional[str] = None) -> None:
        """Update session headers. Call after loading device config."""
        self.session.headers.update({
            "Content-Type": "application/json",
            "x-user-id": user_id or settings.DEFAULT_USER_ID,
            "x-source": "raspberry_pi",
            "x-device-id": settings.DEVICE_ID,
        })

    # ------------------------------------------------------------------
    # Health & Connectivity
    # ------------------------------------------------------------------

    def check_health(self) -> bool:
        """Returns True if AgroVision backend is reachable and healthy."""
        try:
            resp = self.session.get(f"{self.base_url}/api/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Device Registration & Heartbeat
    # ------------------------------------------------------------------

    def register_device(self, farm_id: str, field_id: str) -> Optional[Dict[str, Any]]:
        """Register or re-register this device with the backend."""
        try:
            url = f"{self.base_url}/api/devices/register"
            payload = {
                "deviceId": settings.DEVICE_ID,
                "name": settings.DEVICE_NAME,
                "deviceType": "raspberry_pi",
                "farmId": farm_id,
                "fieldId": field_id,
                "firmwareVersion": settings.SOFTWARE_VERSION,
                "status": "online",
            }
            resp = self.session.post(url, json=payload, timeout=5)
            if resp.status_code in (200, 201):
                logger.info(f"[API] Device registered: {settings.DEVICE_ID}")
                return resp.json().get("device")
        except Exception as e:
            logger.error(f"[API] Register device error: {e}")
        return None

    def send_heartbeat(self, battery_level: int = 100) -> bool:
        """Send periodic heartbeat so the backend knows the Pi is online."""
        try:
            url = f"{self.base_url}/api/devices/{settings.DEVICE_ID}/heartbeat"
            payload = {
                "status": "online",
                "batteryLevel": battery_level,
                "softwareVersion": settings.SOFTWARE_VERSION,
                "deviceType": "raspberry_pi",
            }
            resp = self.session.post(url, json=payload, timeout=4)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[API] Heartbeat failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Device Pairing
    # ------------------------------------------------------------------

    def request_pairing_code(self) -> Optional[str]:
        """Ask backend to generate a pairing code for this device."""
        try:
            url = f"{self.base_url}/api/devices/pairing/code"
            resp = self.session.post(url, json={"deviceId": settings.DEVICE_ID}, timeout=5)
            if resp.status_code == 200:
                code = resp.json().get("pairingCode")
                logger.info(f"[API] Pairing code received: {code}")
                return code
        except Exception as e:
            logger.error(f"[API] Pairing code request error: {e}")
        return None

    def check_pairing_status(self, code: str) -> Dict[str, Any]:
        """Poll backend to see if the pairing code has been claimed by the user."""
        try:
            url = f"{self.base_url}/api/devices/pairing/status/{code}"
            resp = self.session.get(url, timeout=4)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {"status": "pending"}

    # ------------------------------------------------------------------
    # AI / Voice Conversation (all intent processing is server-side)
    # ------------------------------------------------------------------

    def converse(self, text: str, farm_id: Optional[str] = None, field_id: Optional[str] = None) -> AssistantResponse:
        """
        Send user's transcribed speech to the AgroVision backend AI dispatcher.
        The backend handles ALL intent parsing and database operations.
        Returns a structured response with intent, TTS text, and OLED text.
        """
        url = f"{self.base_url}/api/ai/converse"
        payload = {
            "text": text,
            "deviceId": settings.DEVICE_ID,
            "farmId": farm_id or settings.DEFAULT_FARM_ID,
            "fieldId": field_id or settings.DEFAULT_FIELD_ID,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=12)
            if resp.status_code in (200, 201):
                data = resp.json()
                return AssistantResponse(
                    success=data.get("success", True),
                    intent=data.get("intent", "GENERAL_CONVERSATION"),
                    text=data.get("text", "I received your request."),
                    oledText=data.get("oledText", "REQUEST OK"),
                    speak=data.get("speak", True),
                    data=data.get("data"),
                )
            else:
                logger.error(f"[API] Converse returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[API] Converse request error: {e}")

        return AssistantResponse(
            success=False,
            intent="ERROR",
            text="AgroVision server is currently unavailable.",
            oledText="ERROR\nServer offline",
            speak=True,
        )

    # ------------------------------------------------------------------
    # Farms & Fields
    # ------------------------------------------------------------------

    def get_farms(self) -> List[Dict[str, Any]]:
        """Retrieve all farms for the current user."""
        try:
            resp = self.session.get(f"{self.base_url}/api/farms", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_farms failed: {e}")
        return []

    def get_fields(self, farm_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all fields, optionally filtered by farm."""
        try:
            url = f"{self.base_url}/api/fields"
            if farm_id:
                url += f"?farmId={farm_id}"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_fields failed: {e}")
        return []

    def get_field(self, field_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single field by ID."""
        try:
            resp = self.session.get(f"{self.base_url}/api/fields/{field_id}", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_field failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def get_tasks(self, field_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve tasks, optionally filtered by field or status."""
        try:
            url = f"{self.base_url}/api/tasks"
            params = []
            if field_id:
                params.append(f"fieldId={field_id}")
            if status:
                params.append(f"status={status}")
            if params:
                url += "?" + "&".join(params)
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_tasks failed: {e}")
        return []

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Convenience: get only pending tasks."""
        return self.get_tasks(status="Pending")

    def complete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Mark a task as completed on the backend."""
        try:
            url = f"{self.base_url}/api/tasks/{task_id}"
            resp = self.session.patch(url, json={
                "status": "Completed",
                "source": "raspberry_pi",
                "deviceId": settings.DEVICE_ID,
            }, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("task")
        except Exception as e:
            logger.error(f"[API] complete_task failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------

    def get_reminders(self) -> List[Dict[str, Any]]:
        """Retrieve all reminders."""
        try:
            resp = self.session.get(f"{self.base_url}/api/reminders", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_reminders failed: {e}")
        return []

    # ------------------------------------------------------------------
    # Observations
    # ------------------------------------------------------------------

    def get_observations(self, field_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve field observations."""
        try:
            url = f"{self.base_url}/api/observations"
            if field_id:
                url += f"?fieldId={field_id}"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_observations failed: {e}")
        return []

    def create_observation(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a field observation. Always sets source=raspberry_pi and deviceId.
        GPS coordinates should be None unless GPS is available — do NOT fabricate.
        """
        try:
            payload.setdefault("source", "raspberry_pi")
            payload.setdefault("deviceId", settings.DEVICE_ID)
            payload.setdefault("latitude", None)
            payload.setdefault("longitude", None)
            resp = self.session.post(
                f"{self.base_url}/api/observations",
                json=payload,
                timeout=8,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("observation")
            else:
                logger.error(f"[API] create_observation failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[API] create_observation exception: {e}")
        return None

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------

    def get_weather(self, field_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cached weather data for a field from the backend."""
        fid = field_id or settings.DEFAULT_FIELD_ID
        try:
            resp = self.session.get(f"{self.base_url}/api/weather/{fid}", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_weather failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Media (Photos & Videos)
    # ------------------------------------------------------------------

    def upload_media(self, file_path: str, media_type: str = "photo") -> Optional[Dict[str, Any]]:
        """
        Upload a file to the AgroVision backend storage as base64.
        Returns the upload result including the server-side URL.
        """
        import base64
        try:
            with open(file_path, "rb") as f:
                data_b64 = base64.b64encode(f.read()).decode("utf-8")

            filename = os.path.basename(file_path)
            url = f"{self.base_url}/api/media/upload"
            resp = self.session.post(url, json={
                "filename": filename,
                "dataBase64": data_b64,
                "mediaType": media_type,
            }, timeout=30)

            if resp.status_code in (200, 201):
                logger.info(f"[API] Media uploaded: {filename} ({media_type})")
                return resp.json()
            else:
                logger.error(f"[API] Media upload failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[API] Media upload exception: {e}")
        return None

    def create_media(self, media_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a media database record on the backend after upload.
        Always includes source=raspberry_pi and deviceId.
        GPS coordinates should be None when not available.
        """
        try:
            media_payload.setdefault("source", "raspberry_pi")
            media_payload.setdefault("deviceId", settings.DEVICE_ID)
            media_payload.setdefault("latitude", None)
            media_payload.setdefault("longitude", None)
            url = f"{self.base_url}/api/media"
            resp = self.session.post(url, json=media_payload, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json().get("media")
            else:
                logger.error(f"[API] Create media record failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[API] Create media record exception: {e}")
        return None

    def get_media(self, field_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all media records, optionally filtered by field."""
        try:
            url = f"{self.base_url}/api/media"
            if field_id:
                url += f"?fieldId={field_id}"
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_media failed: {e}")
        return []

    # ------------------------------------------------------------------
    # Activity Log
    # ------------------------------------------------------------------

    def get_activity(self) -> List[Dict[str, Any]]:
        """Retrieve recent activity log from the backend."""
        try:
            resp = self.session.get(f"{self.base_url}/api/activity", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[API] get_activity failed: {e}")
        return []
