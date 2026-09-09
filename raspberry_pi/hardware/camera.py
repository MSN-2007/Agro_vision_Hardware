import os
import sys
import time
import subprocess
import platform
import shutil
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from config.settings import settings
from utils.logger import logger

class CameraDriver(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def check_camera(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def capture_photo(self, output_path: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def start_video(self, output_path: str) -> bool:
        pass

    @abstractmethod
    def stop_video(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def release(self) -> None:
        pass


class LibcameraDriver(CameraDriver):
    """Driver for Raspberry Pi CSI Camera via libcamera-still / rpicam-still and libcamera-vid."""
    def __init__(self):
        self.cmd_still = "libcamera-still"
        self.cmd_vid = "libcamera-vid"
        self.video_proc = None
        self.current_video_path = None
        self.video_start_time = None

    def initialize(self) -> bool:
        for cmd in ["rpicam-still", "libcamera-still"]:
            if shutil.which(cmd):
                self.cmd_still = cmd
                self.cmd_vid = cmd.replace("-still", "-vid")
                logger.info(f"[CAMERA] CSI Camera binary detected: {self.cmd_still}")
                return True
        return False

    def check_camera(self) -> Dict[str, Any]:
        try:
            res = subprocess.run([self.cmd_still, "--list-cameras"], capture_output=True, text=True, timeout=3)
            detected = res.returncode == 0 and "No cameras available" not in res.stdout
            return {
                "type": "CSI (Raspberry Pi Camera Module)",
                "driver": self.cmd_still,
                "detected": detected,
                "details": res.stdout.strip() or res.stderr.strip()
            }
        except Exception as e:
            return {"type": "CSI", "detected": False, "error": str(e)}

    def capture_photo(self, output_path: str) -> Optional[Dict[str, Any]]:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            # Capture with 1 second preview/warmup
            cmd = [self.cmd_still, "-n", "-t", "1000", "--width", "1920", "--height", "1080", "-o", output_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path)
                return {
                    "filePath": output_path,
                    "resolution": "1920x1080",
                    "sizeBytes": size,
                    "mediaType": "photo"
                }
            logger.error(f"[CAMERA] CSI capture failed: {proc.stderr}")
        except Exception as e:
            logger.error(f"[CAMERA] CSI capture exception: {e}")
        return None

    def start_video(self, output_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            self.current_video_path = output_path
            self.video_start_time = time.time()
            # libcamera-vid running indefinitely until killed
            cmd = [self.cmd_vid, "-n", "-t", "0", "--width", "1280", "--height", "720", "-o", output_path]
            self.video_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"[CAMERA] CSI start_video error: {e}")
            return False

    def stop_video(self) -> Optional[Dict[str, Any]]:
        if not self.video_proc:
            return None
        try:
            self.video_proc.terminate()
            self.video_proc.wait(timeout=4)
        except Exception:
            self.video_proc.kill()
        self.video_proc = None
        duration = round(time.time() - (self.video_start_time or time.time()), 1)
        if self.current_video_path and os.path.exists(self.current_video_path):
            size = os.path.getsize(self.current_video_path)
            return {
                "filePath": self.current_video_path,
                "durationSeconds": duration,
                "sizeBytes": size,
                "mediaType": "video"
            }
        return None

    def release(self) -> None:
        if self.video_proc:
            try:
                self.video_proc.terminate()
            except Exception:
                pass


class V4L2CameraDriver(CameraDriver):
    """Driver for USB webcams via V4L2 and ffmpeg/fswebcam."""
    def __init__(self, device: str = "/dev/video0"):
        self.device = device
        self.video_proc = None
        self.current_video_path = None
        self.video_start_time = None

    def initialize(self) -> bool:
        if os.path.exists(self.device):
            logger.info(f"[CAMERA] V4L2 USB camera detected at {self.device}")
            return True
        return False

    def check_camera(self) -> Dict[str, Any]:
        detected = os.path.exists(self.device)
        return {
            "type": "USB (V4L2)",
            "device": self.device,
            "detected": detected,
            "status": "Connected" if detected else "Device not found"
        }

    def capture_photo(self, output_path: str) -> Optional[Dict[str, Any]]:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            if shutil.which("ffmpeg"):
                cmd = ["ffmpeg", "-y", "-f", "v4l2", "-i", self.device, "-frames:v", "1", output_path]
                res = subprocess.run(cmd, capture_output=True, timeout=8)
                if res.returncode == 0 and os.path.exists(output_path):
                    return {
                        "filePath": output_path,
                        "resolution": "1280x720",
                        "sizeBytes": os.path.getsize(output_path),
                        "mediaType": "photo"
                    }
            elif shutil.which("fswebcam"):
                cmd = ["fswebcam", "-d", self.device, "-r", "1280x720", "--no-banner", output_path]
                res = subprocess.run(cmd, capture_output=True, timeout=8)
                if res.returncode == 0 and os.path.exists(output_path):
                    return {
                        "filePath": output_path,
                        "resolution": "1280x720",
                        "sizeBytes": os.path.getsize(output_path),
                        "mediaType": "photo"
                    }
        except Exception as e:
            logger.error(f"[CAMERA] V4L2 capture error: {e}")
        return None

    def start_video(self, output_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            self.current_video_path = output_path
            self.video_start_time = time.time()
            cmd = ["ffmpeg", "-y", "-f", "v4l2", "-i", self.device, "-c:v", "libx264", output_path]
            self.video_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"[CAMERA] V4L2 start_video error: {e}")
            return False

    def stop_video(self) -> Optional[Dict[str, Any]]:
        if not self.video_proc:
            return None
        try:
            self.video_proc.terminate()
            self.video_proc.wait(timeout=4)
        except Exception:
            self.video_proc.kill()
        self.video_proc = None
        duration = round(time.time() - (self.video_start_time or time.time()), 1)
        if self.current_video_path and os.path.exists(self.current_video_path):
            return {
                "filePath": self.current_video_path,
                "durationSeconds": duration,
                "sizeBytes": os.path.getsize(self.current_video_path),
                "mediaType": "video"
            }
        return None

    def release(self) -> None:
        if self.video_proc:
            try:
                self.video_proc.terminate()
            except Exception:
                pass


class SimulatedCameraDriver(CameraDriver):
    """
    High-fidelity simulated camera driver.
    Generates realistic field imagery using Pillow with agricultural textures and overlays.
    Used for unit testing, non-Linux development environments, or when physical camera is offline.
    Guarantees the application never crashes when hardware camera is detached.
    """
    def __init__(self):
        self.current_video_path = None
        self.video_start_time = None
        self.is_recording = False

    def initialize(self) -> bool:
        logger.info("[CAMERA] Simulated Camera Driver active (Field Imagery Simulator)")
        return True

    def check_camera(self) -> Dict[str, Any]:
        return {
            "type": "Simulated Field Camera (PIL Driver)",
            "detected": True,
            "resolution": "1280x720",
            "status": "Ready (Field Imagery Emulation Active)"
        }

    def capture_photo(self, output_path: str) -> Optional[Dict[str, Any]]:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            from PIL import Image, ImageDraw

            width, height = 1280, 720
            # Generate agricultural field gradient (Sky -> Field -> Crops)
            img = Image.new("RGB", (width, height), color=(135, 206, 235)) # Sky
            draw = ImageDraw.Draw(img)

            # Ground / Soil
            draw.rectangle([0, 300, width, height], fill=(92, 64, 51))

            # Crop rows (lush green)
            for x in range(0, width, 80):
                draw.rectangle([x, 380, x + 50, height], fill=(34, 139, 34))
                # Crop highlights
                draw.ellipse([x + 10, 360, x + 40, 420], fill=(50, 205, 50))

            # Sun
            draw.ellipse([width - 200, 40, width - 100, 140], fill=(255, 215, 0))

            # AgroVision Watermark / Metadata HUD
            draw.rectangle([20, 20, 450, 120], fill=(0, 0, 0, 180))
            ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            draw.text((35, 30), "AGROVISION FIELD CAMERA 3B+", fill=(0, 255, 128))
            draw.text((35, 55), f"TIMESTAMP: {ts}", fill=(255, 255, 255))
            draw.text((35, 80), "STATUS: OPTIMAL CROP CANOPY • NORMAL", fill=(255, 220, 100))

            img.save(output_path, "JPEG", quality=90)
            size = os.path.getsize(output_path)
            return {
                "filePath": output_path,
                "resolution": f"{width}x{height}",
                "sizeBytes": size,
                "mediaType": "photo"
            }
        except Exception as e:
            logger.error(f"[CAMERA] Simulated capture error: {e}")
            # Minimal JPEG fallback if Pillow fails
            try:
                with open(output_path, "wb") as f:
                    f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9')
                return {
                    "filePath": output_path,
                    "resolution": "1x1",
                    "sizeBytes": os.path.getsize(output_path),
                    "mediaType": "photo"
                }
            except Exception:
                return None

    def start_video(self, output_path: str) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self.current_video_path = output_path
        self.video_start_time = time.time()
        self.is_recording = True
        try:
            with open(output_path, "wb") as f:
                f.write(b'\x00\x00\x00 ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free')
        except Exception:
            pass
        logger.info(f"[CAMERA] Simulated video recording started: {output_path}")
        return True

    def stop_video(self) -> Optional[Dict[str, Any]]:
        if not self.is_recording and not (self.current_video_path and os.path.exists(self.current_video_path)):
            return None
        self.is_recording = False
        duration = round(time.time() - (self.video_start_time or (time.time() - 3.0)), 1)
        if duration < 1.0:
            duration = 1.0

        # Finalize valid MP4 placeholder
        try:
            if self.current_video_path:
                with open(self.current_video_path, "ab") as f:
                    f.write(b'\x00\x00\x00\x10mdatAgroVisionVid')
                size = os.path.getsize(self.current_video_path)
                return {
                    "filePath": self.current_video_path,
                    "durationSeconds": duration,
                    "sizeBytes": size,
                    "mediaType": "video"
                }
        except Exception as e:
            logger.error(f"[CAMERA] Error saving simulated video: {e}")
            return None

    def release(self) -> None:
        self.is_recording = False


class UnavailableCameraDriver(CameraDriver):
    """Driver representing unavailable, detached, or disabled camera hardware."""
    def __init__(self, reason: str = "UNAVAILABLE"):
        self.reason = reason

    @property
    def is_available(self) -> bool:
        return False

    def initialize(self) -> bool:
        logger.info(f"[CAMERA] Camera is {self.reason.lower()} for current hardware configuration.")
        return False

    def check_camera(self) -> Dict[str, Any]:
        return {
            "type": "None",
            "detected": False,
            "status": f"Camera {self.reason}"
        }

    def capture_photo(self, output_path: str) -> Optional[Dict[str, Any]]:
        logger.warning(f"[CAMERA] Photo capture attempted while camera is {self.reason}.")
        return None

    def start_video(self, output_path: str) -> bool:
        logger.warning(f"[CAMERA] Video recording attempted while camera is {self.reason}.")
        return False

    def stop_video(self) -> Optional[Dict[str, Any]]:
        return None

    def release(self) -> None:
        pass


def get_camera_driver(force_simulated: bool = False) -> CameraDriver:
    """
    Hardware inspection factory.
    Returns:
    1. SimulatedCameraDriver if explicitly requested (e.g. test fixtures)
    2. UnavailableCameraDriver if camera is disabled in settings
    3. LibcameraDriver if Raspberry Pi CSI camera detected
    4. V4L2CameraDriver if USB webcam verified
    5. UnavailableCameraDriver if no physical camera detected
    """
    if force_simulated:
        return SimulatedCameraDriver()

    if not settings.CAMERA_ENABLED:
        logger.info("[CAMERA] Camera disabled by configuration (CAMERA_ENABLED=false).")
        return UnavailableCameraDriver(reason="DISABLED")

    # 1. Check for Raspberry Pi CSI camera
    for cmd in ["rpicam-hello", "libcamera-hello", "rpicam-still", "libcamera-still"]:
        if shutil.which(cmd):
            try:
                res = subprocess.run([cmd, "--list-cameras"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and "No cameras available" not in res.stdout and "Available cameras" in res.stdout:
                    logger.info(f"[CAMERA] Raspberry Pi CSI camera detected using {cmd}")
                    return LibcameraDriver()
            except Exception:
                pass

    # 2. Check for V4L2 USB cameras (must verify via v4l2-ctl; do NOT assume /dev/video* alone)
    if shutil.which("v4l2-ctl"):
        try:
            res = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and "bcm2835" not in res.stdout.lower() and "camera" in res.stdout.lower():
                dev = "/dev/video0" if os.path.exists("/dev/video0") else "/dev/video1"
                logger.info(f"[CAMERA] USB V4L2 camera verified at {dev}")
                return V4L2CameraDriver(dev)
        except Exception:
            pass

    logger.info("[CAMERA] Physical camera not detected.")
    return UnavailableCameraDriver(reason="UNAVAILABLE")

