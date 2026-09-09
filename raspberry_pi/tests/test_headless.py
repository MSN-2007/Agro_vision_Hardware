import unittest
import os
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

from config.settings import settings
from hardware.capabilities import HardwareCapabilityManager, HardwareState
from hardware.oled import LumaOledDriver, ConsoleOledDriver
from hardware.camera import UnavailableCameraDriver, get_camera_driver
from hardware.microphone import DisabledAudioDriver, get_audio_input_driver
from hardware.speaker import ConsoleSpeakerDriver
from ui.display_manager import DisplayManager
from ui.terminal_ui import TerminalUI
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from services.camera_service import CameraService
from services.voice_service import VoiceService
from models.response import AssistantResponse


class TestHeadlessArchitecture(unittest.TestCase):

    def setUp(self):
        self.hw_mgr = HardwareCapabilityManager()

    # --------------------------------------------------------------------------
    # 1. Hardware Capability Detection & States
    # --------------------------------------------------------------------------

    def test_hardware_capability_states_headless(self):
        """Verify initial capabilities in headless mode without peripherals."""
        self.hw_mgr.initialize_all()
        states = self.hw_mgr.check_all()

        self.assertIn("oled", states)
        self.assertIn("microphone", states)
        self.assertIn("camera", states)
        self.assertIn("speaker", states)

        # In headless development, mic and camera are disabled, OLED is unavailable
        self.assertIn(states["oled"], [HardwareState.UNAVAILABLE, HardwareState.DISABLED])
        self.assertEqual(states["microphone"], HardwareState.DISABLED)
        self.assertEqual(states["camera"], HardwareState.DISABLED)

    def test_oled_dynamic_detection(self):
        """Verify OLED detection method returns boolean without throwing exceptions."""
        result = self.hw_mgr.detect_oled()
        self.assertIsInstance(result, bool)

    # --------------------------------------------------------------------------
    # 2. OLED-Unavailable Behavior
    # --------------------------------------------------------------------------

    def test_luma_oled_missing_hardware(self):
        """Ensure LumaOledDriver handles absent hardware safely without throwing exceptions."""
        driver = LumaOledDriver(port=1, address=0x3C, enable_fallback=False)
        self.assertFalse(driver.is_available)
        init_result = driver.initialize()
        self.assertFalse(init_result)
        self.assertFalse(driver.is_available)

        # Drawing text when OLED is unavailable must not crash
        try:
            driver.show_text(["Test Line 1", "Test Line 2"], title="TEST")
            driver.clear()
        except Exception as e:
            self.fail(f"show_text crashed on unavailable OLED: {e}")

    # --------------------------------------------------------------------------
    # 3. Camera-Unavailable Behavior
    # --------------------------------------------------------------------------

    def test_unavailable_camera_driver(self):
        """Verify UnavailableCameraDriver cleanly signals unavailability without fake images."""
        driver = UnavailableCameraDriver(reason="DISABLED")
        self.assertFalse(driver.is_available)
        self.assertFalse(driver.initialize())

        info = driver.check_camera()
        self.assertFalse(info.get("detected"))

        # Photo capture must return None and not create files
        result = driver.capture_photo("test_photo.jpg")
        self.assertIsNone(result)
        self.assertFalse(os.path.exists("test_photo.jpg"))

        # Video start must return False
        vid_result = driver.start_video("test_video.mp4")
        self.assertFalse(vid_result)

    def test_camera_service_unavailable_guard(self):
        """Verify CameraService guards against unavailable camera."""
        driver = UnavailableCameraDriver(reason="UNAVAILABLE")
        display = DisplayManager(enable_terminal_output=False)
        cam_service = CameraService(driver=driver, display=display)

        res = cam_service.capture_photo()
        self.assertIsNone(res)

        vid_res = cam_service.start_video()
        self.assertFalse(vid_res)

    # --------------------------------------------------------------------------
    # 4. Microphone-Disabled Behavior
    # --------------------------------------------------------------------------

    def test_disabled_audio_driver(self):
        """Verify DisabledAudioDriver does not block on input and returns None immediately."""
        driver = DisabledAudioDriver()
        self.assertFalse(driver.is_available)
        self.assertFalse(driver.initialize())

        # Calling listen_and_transcribe must return None without blocking
        result = driver.listen_and_transcribe("Test prompt")
        self.assertIsNone(result)

    # --------------------------------------------------------------------------
    # 5. UI & DisplayManager Dual-Destination Abstraction
    # --------------------------------------------------------------------------

    def test_display_manager_dual_output(self):
        """Verify DisplayManager logs/terminal output works even when OLED is None/unavailable."""
        dm = DisplayManager(driver=None, enable_terminal_output=True)
        self.assertFalse(dm.is_oled_available())

        # Test state transitions without OLED
        dm.show_boot()
        dm.show_connecting()
        dm.show_ready("Green Valley", "Field 1")
        dm.show_speaking("TEST RESPONSE")
        dm.show_camera_error("No camera")
        dm.show_error("Test Error")

    def test_display_manager_dynamic_oled_attach(self):
        """Verify DisplayManager can attach OLED driver dynamically."""
        dm = DisplayManager(driver=None)
        self.assertFalse(dm.is_oled_available())

        mock_oled = MagicMock()
        mock_oled.is_available = True
        dm.set_oled_driver(mock_oled)
        self.assertTrue(dm.is_oled_available())

        dm.show_speaking("TEST OLED ATTACH")
        mock_oled.show_text.assert_called_once()

    # --------------------------------------------------------------------------
    # 6. Terminal UI Banners & Commands
    # --------------------------------------------------------------------------

    def test_terminal_banners_render(self):
        """Verify startup and ready banners render without errors."""
        captured = StringIO()
        with patch('sys.stdout', captured):
            TerminalUI.print_startup_banner(
                device_id="TEST_PI_001",
                network_status="CONNECTED",
                backend_status="CONNECTED",
                realtime_status="CONNECTED",
            )
            TerminalUI.print_ready_banner(
                device_id="TEST_PI_001",
                status="ONLINE",
            )

        output = captured.getvalue()
        self.assertIn("AGROVISION PI AGENT", output)
        self.assertIn("TEST_PI_001", output)
        self.assertIn("ONLINE", output)

    def test_terminal_command_take_photo_unavailable(self):
        """Verify 'take photo' returns clean unavailable message when camera is absent."""
        mock_api = MagicMock()
        mock_auth = MagicMock()
        mock_auth.device_config.farmId = "f-1"
        mock_auth.device_config.fieldId = "fld-1"
        display = DisplayManager(enable_terminal_output=False)

        captured = StringIO()
        with patch('sys.stdout', captured):
            keep_going = TerminalUI.execute_command(
                cmd="take photo",
                api=mock_api,
                auth=mock_auth,
                net=MagicMock(),
                sync=MagicMock(),
                heartbeat=MagicMock(),
                voice=MagicMock(),
                camera_service=None,
                display=display,
            )

        self.assertTrue(keep_going)
        output = captured.getvalue()
        self.assertIn("Camera is currently unavailable", output)
        self.assertIn("Connect a supported camera", output)

    def test_terminal_command_help_and_exit(self):
        """Verify help command prints documentation and exit returns False."""
        captured = StringIO()
        with patch('sys.stdout', captured):
            TerminalUI.print_help()
        self.assertIn("AGROVISION TERMINAL COMMANDS", captured.getvalue())

        # Exit command
        keep_going = TerminalUI.execute_command(
            cmd="exit",
            api=MagicMock(),
            auth=MagicMock(),
            net=MagicMock(),
            sync=MagicMock(),
            heartbeat=MagicMock(),
            voice=MagicMock(),
            camera_service=None,
            display=MagicMock(),
        )
        self.assertFalse(keep_going)

    # --------------------------------------------------------------------------
    # 7. Health Check: Critical Core vs Optional Hardware
    # --------------------------------------------------------------------------

    def test_health_check_separation(self):
        """Verify health check marks system HEALTHY when core passes, even if peripherals absent."""
        mock_api = MagicMock()
        mock_api.check_health.return_value = True

        mock_net = MagicMock()
        mock_net.is_connected.return_value = True

        mock_auth = MagicMock()
        mock_auth.is_paired.return_value = True

        mock_sync = MagicMock()
        mock_sync.running = True

        mock_hb = MagicMock()
        mock_hb.running = True

        captured = StringIO()
        with patch('sys.stdout', captured):
            TerminalUI.print_health(
                api=mock_api,
                net=mock_net,
                auth=mock_auth,
                sync=mock_sync,
                heartbeat=mock_hb
            )

        output = captured.getvalue()
        self.assertIn("CRITICAL CORE SUBSYSTEMS", output)
        self.assertIn("OPTIONAL HARDWARE PERIPHERALS", output)
        self.assertIn("HEALTHY", output)

    # --------------------------------------------------------------------------
    # 8. VoiceService Command Fallback
    # --------------------------------------------------------------------------

    def test_voice_service_camera_intent_when_camera_unavailable(self):
        """Verify VoiceService handles TAKE_PHOTO intent cleanly when camera is unavailable."""
        mock_api = MagicMock()
        mock_api.converse.return_value = AssistantResponse(
            success=True,
            intent="TAKE_PHOTO",
            text="Taking a photo for your observation.",
            oledText="TAKE PHOTO",
            speak=False,
        )
        mock_auth = MagicMock()
        mock_auth.device_config.farmId = "f-1"
        mock_auth.device_config.fieldId = "fld-1"
        display = DisplayManager(enable_terminal_output=False)
        speaker = ConsoleSpeakerDriver()

        voice = VoiceService(
            mic=DisabledAudioDriver(),
            speaker=speaker,
            display=display,
            api=mock_api,
            auth=mock_auth,
            camera_service=None,
        )

        captured = StringIO()
        with patch('sys.stdout', captured):
            result = voice.run_interaction_cycle(text_input="take photo")

        self.assertTrue(result)
        self.assertIn("Camera is currently unavailable", captured.getvalue())


if __name__ == '__main__':
    unittest.main()
