import threading
import time
from services.agrovision_api import AgroVisionApiService
from config.settings import settings
from utils.logger import logger

class HeartbeatService:
    def __init__(self, api: AgroVisionApiService):
        self.api = api
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
        logger.info("[HEARTBEAT] Heartbeat background service started")

    def stop(self):
        self.running = False

    def _heartbeat_loop(self):
        while self.running:
            self.api.send_heartbeat(battery_level=98)
            time.sleep(settings.HEARTBEAT_INTERVAL_SEC)
