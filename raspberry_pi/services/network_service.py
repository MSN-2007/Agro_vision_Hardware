import socket
import urllib.request
from services.agrovision_api import AgroVisionApiService
from utils.logger import logger


class NetworkService:
    """
    Network connectivity checks for the Raspberry Pi.
    Checks both internet connectivity and AgroVision backend reachability.
    """

    def __init__(self, api: AgroVisionApiService):
        self.api = api

    def is_connected(self) -> bool:
        """
        Returns True if the Pi has internet/network access.
        First tries a quick DNS socket to 8.8.8.8, then falls back
        to checking the backend health endpoint.
        """
        # Fast internet connectivity check
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            pass

        # Fallback: try to reach the AgroVision backend
        return self.api.check_health()

    def is_backend_reachable(self) -> bool:
        """Returns True if the AgroVision backend responds to /api/health."""
        return self.api.check_health()

    def get_ip_address(self) -> str:
        """
        Returns the Pi's local IP address on the active network interface.
        Uses a UDP trick (no actual packet sent) to determine the outbound interface.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1 (loopback)"

    def wait_for_backend(self, timeout_sec: int = 60, interval_sec: int = 5) -> bool:
        """
        Blocks until the backend is reachable or timeout expires.
        Used during boot to wait for network to come up before continuing.
        Returns True if backend became reachable within the timeout.
        """
        import time
        elapsed = 0
        while elapsed < timeout_sec:
            if self.api.check_health():
                logger.info(f"[NETWORK] Backend reachable after {elapsed}s.")
                return True
            logger.debug(f"[NETWORK] Backend not yet reachable ({elapsed}s elapsed)...")
            time.sleep(interval_sec)
            elapsed += interval_sec
        logger.warning(f"[NETWORK] Backend not reachable after {timeout_sec}s timeout.")
        return False
