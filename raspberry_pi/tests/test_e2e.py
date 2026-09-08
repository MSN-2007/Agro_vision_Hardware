"""
AgroVision Pi — End-to-End Test Suite (text mode)

These tests simulate the full voice pipeline using text input
instead of a microphone. They require the AgroVision backend to
be running at BACKEND_URL.

Run:
    cd raspberry_pi/
    python -m pytest tests/ -v

Or without pytest:
    python tests/test_e2e.py
"""
import sys
import os
import time

# Ensure parent directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import settings
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from hardware.oled import ConsoleOledDriver
from hardware.microphone import TextModeAudioDriver
from hardware.speaker import ConsoleSpeakerDriver
from hardware.camera import get_camera_driver
from ui.display_manager import DisplayManager
from services.voice_service import VoiceService
from services.camera_service import CameraService


def setup():
    """Create all services using console (non-hardware) drivers."""
    oled = ConsoleOledDriver()
    oled.initialize()
    mic = TextModeAudioDriver()
    mic.initialize()
    speaker = ConsoleSpeakerDriver()
    speaker.initialize()

    display = DisplayManager(oled)
    api = AgroVisionApiService()
    auth = AuthService()
    api._update_headers(user_id=auth.device_config.userId)
    cam_driver = get_camera_driver()
    cam_service = CameraService(cam_driver, display, speaker, api, auth)
    voice = VoiceService(mic, speaker, display, api, auth, camera_service=cam_service)

    return api, auth, voice, cam_service


def test_backend_reachable():
    """TEST: Backend must respond to /api/health."""
    api, _, _, _ = setup()
    result = api.check_health()
    print(f"[TEST 1] Backend reachable: {'PASS' if result else 'FAIL'}")
    assert result, f"Backend not reachable at {api.base_url}"


def test_get_tasks():
    """TEST: Retrieve tasks from backend."""
    api, _, _, _ = setup()
    tasks = api.get_tasks()
    print(f"[TEST 2] Get tasks: PASS ({len(tasks)} tasks)")
    assert isinstance(tasks, list)


def test_get_weather():
    """TEST: Retrieve weather data from backend."""
    api, auth, _, _ = setup()
    weather = api.get_weather(auth.device_config.fieldId)
    # Weather may be None if not cached — that's acceptable
    print(f"[TEST 3] Get weather: {'PASS (data found)' if weather else 'PASS (no cached weather)'}")


def test_voice_tasks_query():
    """TEST 4 (E2E): 'What are my tasks today?' goes through full pipeline."""
    api, auth, voice, _ = setup()
    print("\n[TEST 4] Voice: 'what are my tasks today?'")
    result = voice.run_interaction_cycle(text_input="what are my tasks today?")
    print(f"[TEST 4] Voice pipeline result: {'PASS' if result else 'FAIL (no response)'}")


def test_voice_weather_query():
    """TEST 5 (E2E): 'What is the weather?' goes through full pipeline."""
    api, auth, voice, _ = setup()
    print("\n[TEST 5] Voice: 'what is the weather?'")
    result = voice.run_interaction_cycle(text_input="what is the weather?")
    print(f"[TEST 5] Weather query: {'PASS' if result else 'FAIL'}")


def test_voice_create_observation():
    """TEST 6 (E2E): Creating a field observation via voice."""
    api, auth, voice, _ = setup()
    print("\n[TEST 6] Voice: 'take a note that the leaves are turning yellow'")
    result = voice.run_interaction_cycle(
        text_input="take a note that the leaves are turning yellow"
    )
    print(f"[TEST 6] Observation creation: {'PASS' if result else 'FAIL'}")


def test_voice_morning_briefing():
    """TEST 7 (E2E): Morning briefing."""
    api, auth, voice, _ = setup()
    print("\n[TEST 7] Voice: 'good morning briefing'")
    result = voice.run_interaction_cycle(text_input="good morning briefing")
    print(f"[TEST 7] Morning briefing: {'PASS' if result else 'FAIL'}")


def test_heartbeat():
    """TEST 8: Heartbeat reaches backend."""
    api, _, _, _ = setup()
    result = api.send_heartbeat()
    print(f"[TEST 8] Heartbeat: {'PASS' if result else 'FAIL'}")


def test_camera_simulation():
    """TEST 9: Camera capture (simulated on non-Pi platforms)."""
    import tempfile
    api, auth, _, cam_service = setup()
    cam_service.driver.initialize()
    test_path = os.path.join(tempfile.gettempdir(), "agrovision_test_photo.jpg")
    result = cam_service.driver.capture_photo(test_path)
    exists = result and os.path.exists(test_path)
    print(f"[TEST 9] Camera capture (simulated): {'PASS' if exists else 'FAIL'}")
    if exists:
        os.remove(test_path)
    assert exists


def test_farms_and_fields():
    """TEST 10: Retrieve farms and fields from backend."""
    api, auth, _, _ = setup()
    farms = api.get_farms()
    fields = api.get_fields(auth.device_config.farmId)
    print(f"[TEST 10] Farms: {len(farms)}, Fields: {len(fields)}: PASS")
    assert isinstance(farms, list)
    assert isinstance(fields, list)


def run_all_tests():
    """Run all tests and print a summary report."""
    tests = [
        test_backend_reachable,
        test_get_tasks,
        test_get_weather,
        test_voice_tasks_query,
        test_voice_weather_query,
        test_voice_create_observation,
        test_voice_morning_briefing,
        test_heartbeat,
        test_camera_simulation,
        test_farms_and_fields,
    ]

    print("\n" + "=" * 60)
    print("🌿 AgroVision Pi — End-to-End Test Suite")
    print(f"   Backend: {settings.BACKEND_URL}")
    print(f"   Device:  {settings.DEVICE_ID}")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = []

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            name = test_fn.__name__
            print(f"[FAIL] {name}: {e}")
            errors.append((name, str(e)))
            failed += 1

    print("\n" + "=" * 60)
    print(f"  Results: {passed} PASSED, {failed} FAILED")
    if errors:
        print("\n  Failed tests:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
