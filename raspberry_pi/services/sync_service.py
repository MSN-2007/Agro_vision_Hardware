import json
import threading
import time
import urllib.request
from config.settings import settings
from utils.logger import logger
from typing import Callable

class RealtimeSyncService:
    def __init__(self, on_event_callback: Callable[[str, dict], None]):
        self.on_event = on_event_callback
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._sse_listen_loop, daemon=True)
        self.thread.start()
        logger.info("[REALTIME] SSE Synchronizer listener started in background")

    def stop(self):
        self.running = False

    def _sse_listen_loop(self):
        sse_url = f"{settings.BACKEND_URL}/api/sync/events"
        backoff = 2.0

        while self.running:
            try:
                req = urllib.request.Request(sse_url, headers={
                    "Accept": "text/event-stream",
                    "x-device-id": settings.DEVICE_ID
                })
                with urllib.request.urlopen(req, timeout=30) as response:
                    logger.info("[REALTIME] Connected to AgroVision SSE stream")
                    backoff = 2.0
                    event_type = "message"

                    for raw_line in response:
                        if not self.running:
                            break
                        line = raw_line.decode('utf-8').strip()
                        if not line:
                            continue
                        if line.startswith("event:"):
                            event_type = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data_str = line.split(":", 1)[1].strip()
                            try:
                                data = json.loads(data_str)
                                self.on_event(event_type, data)
                            except Exception:
                                pass
            except Exception as e:
                if self.running:
                    logger.warning(f"[REALTIME] SSE connection dropped ({e}). Reconnecting in {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 1.5, 30.0)
