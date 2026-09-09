import unittest
import os
import shutil
from unittest.mock import patch
from hardware.camera import SimulatedCameraDriver, get_camera_driver
from services.camera_service import CameraService
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from config.settings import settings

class TestCameraSubsystem(unittest.TestCase):
    def setUp(self):
        self.driver = SimulatedCameraDriver()
        self.api = AgroVisionApiService(base_url="http://localhost:5000")
        self.auth = AuthService()
        self.service = CameraService(
            driver=self.driver,
            api=self.api,
            auth=self.auth
        )
        self.test_dir = os.path.join(str(settings.BASE_DIR), "temp_test_camera")
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_camera_driver_detection_and_init(self):
        self.assertTrue(self.driver.initialize())
        info = self.driver.check_camera()
        self.assertTrue(info.get("detected"))
        self.assertIn("Simulated", info.get("type"))

    def test_camera_driver_photo_capture(self):
        out_path = os.path.join(self.test_dir, "test_crop.jpg")
        result = self.driver.capture_photo(out_path)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 1000)
        self.assertEqual(result.get("resolution"), "1280x720")

    def test_camera_driver_video_recording(self):
        out_path = os.path.join(self.test_dir, "test_clip.mp4")
        started = self.driver.start_video(out_path)
        self.assertTrue(started)
        res = self.driver.stop_video()
        self.assertIsNotNone(res)
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(res.get("durationSeconds", 0), 0)

    def test_camera_service_photo_workflow(self):
        # Capture, upload to backend, and verify media record created with null GPS
        with patch.object(self.api, 'upload_media', return_value={"url": "http://mock-cloud.com/photo.jpg"}), \
             patch.object(self.api, 'create_media', return_value={
                 "source": "raspberry_pi", "type": "photo", "latitude": None, "longitude": None
             }):
            photo_res = self.service.capture_photo(caption="Unit test field photo")
            self.assertIsNotNone(photo_res)
            self.assertTrue(photo_res.get("success"))
            media = photo_res.get("media")
            self.assertIsNotNone(media)
            self.assertEqual(media.get("source"), "raspberry_pi")
            self.assertEqual(media.get("type"), "photo")
            # Mandated rule: Pi without GPS must have null latitude and longitude
            self.assertIsNone(media.get("latitude"))
            self.assertIsNone(media.get("longitude"))

    def test_camera_service_video_workflow(self):
        # Start and stop video via service
        with patch.object(self.api, 'upload_media', return_value={"url": "http://mock-cloud.com/video.mp4"}), \
             patch.object(self.api, 'create_media', return_value={
                 "source": "raspberry_pi", "type": "video", "latitude": None, "longitude": None
             }):
            started = self.service.start_video()
            self.assertTrue(started)
            video_res = self.service.stop_video()
            self.assertIsNotNone(video_res)
            self.assertTrue(video_res.get("success"))
            media = video_res.get("media")
            self.assertIsNotNone(media)
            self.assertEqual(media.get("source"), "raspberry_pi")
            self.assertEqual(media.get("type"), "video")
            self.assertIsNone(media.get("latitude"))
            self.assertIsNone(media.get("longitude"))


    def test_camera_factory_fallback_safety(self):
        # Verify get_camera_driver never returns None
        driver = get_camera_driver()
        self.assertIsNotNone(driver)
        # When simulated is requested, initialize must succeed
        sim_driver = get_camera_driver(force_simulated=True)
        self.assertIsNotNone(sim_driver)
        self.assertTrue(sim_driver.initialize())


if __name__ == '__main__':
    unittest.main()
