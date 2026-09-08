import sys
import os
import time
import argparse
from config.settings import settings
from utils.logger import logger
from hardware.oled import LumaOledDriver, ConsoleOledDriver
from hardware.microphone import AlsaAudioDriver, TextModeAudioDriver
from hardware.speaker import TtsSpeakerDriver, ConsoleSpeakerDriver
from ui.display_manager import DisplayManager
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from services.sync_service import RealtimeSyncService
from services.heartbeat_service import HeartbeatService
from services.network_service import NetworkService
from services.voice_service import VoiceService
from hardware.camera import get_camera_driver
from services.camera_service import CameraService


# ==============================================================================
# Realtime SSE Event Handler
# ==============================================================================

def handle_sync_event(event_type: str, data: dict, display: DisplayManager, speaker):
    """
    Handles realtime events pushed from the AgroVision backend via SSE.
    When the mobile app or website creates/updates data, the Pi is notified here.
    """
    logger.info(f"[REALTIME EVENT] '{event_type}': {data}")

    if event_type == "TASK_CREATED":
        title = data.get("title", "New Task")
        display.show_speaking(f"NEW TASK\n{title[:18]}")
        speaker.speak(f"New field task received: {title}")

    elif event_type == "TASK_UPDATED":
        title = data.get("title", "Task")
        status = data.get("status", "Updated")
        display.show_speaking(f"TASK {status.upper()}\n{title[:18]}")

    elif event_type == "TASK_DELETED":
        display.show_speaking("TASK DELETED\nSync'd with cloud")

    elif event_type == "OBSERVATION_CREATED":
        title = data.get("title", data.get("content", "Observation"))
        src = data.get("source", "")
        # Only announce observations from OTHER sources (not ones we created)
        if src != "raspberry_pi":
            display.show_speaking(f"NEW NOTE\n{title[:18]}")

    elif event_type == "REMINDER_CREATED":
        title = data.get("title", "Reminder")
        display.show_speaking(f"REMINDER\n{title[:18]}")
        speaker.speak(f"New reminder: {title}")

    elif event_type in ("PHOTO_CREATED", "VIDEO_CREATED"):
        caption = data.get("caption", "Field Media")
        src = data.get("source", "")
        m_type = "PHOTO" if event_type == "PHOTO_CREATED" else "VIDEO"
        # Only announce media from OTHER sources (not ones we just uploaded)
        if src != "raspberry_pi":
            display.show_speaking(f"NEW {m_type}\n{caption[:18]}")

    elif event_type == "WEATHER_UPDATED":
        field_id = data.get("fieldId", "")
        display.show_speaking("WEATHER\nUpdated by server")

    elif event_type == "DEVICE_STATUS_CHANGED":
        device_id = data.get("deviceId", "")
        if device_id == settings.DEVICE_ID:
            status = data.get("status", "")
            logger.info(f"[REALTIME] Device status changed: {status}")

    elif event_type == "FIELD_UPDATED":
        name = data.get("name", "Field")
        display.show_speaking(f"FIELD UPDATED\n{name[:18]}")


# ==============================================================================
# Pairing Flow
# ==============================================================================

def run_pairing_flow(api: AgroVisionApiService, auth: AuthService, display: DisplayManager, speaker) -> bool:
    """
    Executes the full device pairing flow when the Pi is not yet paired.

    Flow:
      1. Request a pairing code from the backend
      2. Display it on the OLED (and print to console)
      3. Poll the backend until the user claims the code via mobile/web
      4. Save the returned credentials to device_config.json
      5. Return True if paired successfully, False on timeout

    The .env or device_config.json stores these credentials persistently.
    """
    logger.info("[PAIRING] Device not paired. Starting pairing flow...")
    speaker.speak("AgroVision is not paired. Requesting pairing code.")

    # Step 1: Get pairing code from backend
    pairing_code = api.request_pairing_code()
    if not pairing_code:
        display.show_error("Pairing failed")
        speaker.speak("Could not get pairing code from the backend. Check network connection.")
        return False

    # Step 2: Display on OLED
    logger.info(f"[PAIRING] Pairing code: {pairing_code}")
    display.show_pairing(pairing_code)
    speaker.speak(
        f"Pairing code: {' '.join(pairing_code)}. "
        "Enter this code in the AgroVision mobile app or website to connect this device."
    )

    print("\n" + "=" * 50)
    print("🔗 AGROVISION DEVICE PAIRING")
    print("=" * 50)
    print(f"  Pairing Code: {pairing_code}")
    print(f"  Expires in:   {settings.PAIRING_TIMEOUT_SEC // 60} minutes")
    print()
    print("  Open the AgroVision App or Website and enter this code.")
    print("=" * 50 + "\n")

    # Step 3: Poll for pairing completion
    timeout = settings.PAIRING_TIMEOUT_SEC
    elapsed = 0

    while elapsed < timeout:
        time.sleep(settings.PAIRING_POLL_INTERVAL_SEC)
        elapsed += settings.PAIRING_POLL_INTERVAL_SEC

        status_data = api.check_pairing_status(pairing_code)
        status = status_data.get("status", "pending")

        logger.debug(f"[PAIRING] Poll {elapsed}s: status={status}")

        if status == "claimed":
            # Step 4: Extract and save credentials
            token = status_data.get("token")
            farm_id = status_data.get("farmId", settings.DEFAULT_FARM_ID)
            field_id = status_data.get("fieldId", settings.DEFAULT_FIELD_ID)
            user_id = status_data.get("device", {}).get("userId", settings.DEFAULT_USER_ID)
            device_name = status_data.get("device", {}).get("name", settings.DEVICE_NAME)

            from models.device import DeviceConfig
            cfg = DeviceConfig(
                deviceId=settings.DEVICE_ID,
                name=device_name,
                deviceType="raspberry_pi",
                userId=user_id,
                farmId=farm_id,
                fieldId=field_id,
                paired=True,
                authToken=token,
            )
            auth.save_config(cfg)

            # Update API headers with new user ID
            api._update_headers(user_id=user_id)

            logger.info(f"[PAIRING] Paired successfully. Farm={farm_id}, Field={field_id}, User={user_id}")
            display.show_speaking(f"PAIRED!\nFarm: {farm_id[:16]}\nField: {field_id[:16]}")
            speaker.speak("Device paired successfully! AgroVision is now connected to your farm.")
            time.sleep(2)
            return True

        elif status == "expired":
            logger.warning("[PAIRING] Pairing code expired.")
            break

        # Show countdown on OLED every 30s
        if elapsed % 30 == 0:
            remaining = timeout - elapsed
            display.show_pairing(f"{pairing_code}\n{remaining}s left")

    # Pairing timed out
    display.show_error("Pairing timeout")
    speaker.speak("Pairing timed out. Restarting...")
    logger.warning("[PAIRING] Pairing timed out after {} seconds".format(timeout))
    return False


# ==============================================================================
# Health Check
# ==============================================================================

def run_health_check(api: AgroVisionApiService, net: NetworkService, oled, mic, speaker, cam_driver):
    """Runs a comprehensive hardware + software health check and prints results."""
    print("\n" + "=" * 50)
    print("🌿 AGROVISION HARDWARE & SYSTEM HEALTH CHECK")
    print("=" * 50)

    oled_ok = oled.initialize()
    mic_ok = mic.initialize()
    speaker_ok = speaker.initialize()
    cam_info = cam_driver.check_camera()
    cam_ok = cam_driver.initialize()
    net_ok = net.is_connected()
    backend_ok = api.check_health()
    ip_addr = net.get_ip_address()

    results = {
        "OLED Display":       oled_ok,
        "Microphone":         mic_ok,
        "Speaker / TTS":      speaker_ok,
        "Camera Subsystem":   cam_ok,
        "Wi-Fi / Network":    net_ok,
        "AgroVision Backend": backend_ok,
    }

    for name, status in results.items():
        icon = "✅" if status else "❌"
        state = "PASS" if status else "FAIL"
        print(f"  {icon} {name:<22} [{state}]")

    print()
    print(f"  📸 Camera Type:        {cam_info.get('type', 'Unknown')}")
    print(f"  🌐 IP Address:         {ip_addr}")
    print(f"  🏷️  Device ID:          {settings.DEVICE_ID}")
    print(f"  📡 Backend URL:        {api.base_url}")
    print(f"  🔧 Software Version:   {settings.SOFTWARE_VERSION}")
    print("=" * 50 + "\n")

    all_ok = all(results.values())
    if all_ok:
        print("✅ All systems operational.\n")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"⚠️  Issues detected: {', '.join(failed)}")
        print("   Hardware issues will use fallback modes automatically.\n")

    return all_ok


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AgroVision Raspberry Pi Physical Hardware Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      # Full hardware mode (normal operation)
  python main.py --text-mode          # Interactive text console (no hardware needed)
  python main.py --command "what are my tasks today?"
  python main.py --health             # Full diagnostic health check
  python main.py --test-display       # Test OLED states
  python main.py --test-camera        # Test camera capture + upload
  python main.py --test-backend       # Test backend connectivity
        """
    )

    parser.add_argument("--text-mode",      action="store_true", help="Interactive text console mode (no mic/speaker/OLED needed)")
    parser.add_argument("--test-network",   action="store_true", help="Test network interface and backend connectivity")
    parser.add_argument("--test-device",    action="store_true", help="Test device identity and pairing configuration")
    parser.add_argument("--test-camera",    action="store_true", help="Test camera detection, capture, upload, and cleanup")
    parser.add_argument("--test-display",   action="store_true", help="Test OLED display states")
    parser.add_argument("--test-microphone",action="store_true", help="Test microphone input")
    parser.add_argument("--test-speaker",   action="store_true", help="Test speaker text-to-speech")
    parser.add_argument("--test-backend",   action="store_true", help="Test connection to AgroVision backend")
    parser.add_argument("--test-realtime",  action="store_true", help="Test SSE real-time synchronization")
    parser.add_argument("--health",         action="store_true", help="Run full diagnostic health check")
    parser.add_argument("--command",        type=str,            help="Execute a single voice command string and exit")

    args = parser.parse_args()

    # --------------------------------------------------------------------------
    # Driver selection: hardware vs. console/text mode
    # --------------------------------------------------------------------------
    use_console = (
        args.text_mode
        or settings.USE_CONSOLE_OLED
        or os.environ.get("USE_CONSOLE_OLED") == "true"
    )

    if use_console:
        oled_driver = ConsoleOledDriver()
        mic_driver = TextModeAudioDriver()
        speaker_driver = ConsoleSpeakerDriver()
    else:
        oled_driver = LumaOledDriver()
        mic_driver = AlsaAudioDriver()
        speaker_driver = TtsSpeakerDriver()

    display = DisplayManager(oled_driver)
    api = AgroVisionApiService()
    auth = AuthService()

    # Update API headers with the stored user ID
    api._update_headers(user_id=auth.device_config.userId)

    net = NetworkService(api)
    cam_driver = get_camera_driver()
    cam_service = CameraService(cam_driver, display, speaker_driver, api, auth)

    # --------------------------------------------------------------------------
    # Test / Diagnostic Modes
    # --------------------------------------------------------------------------

    if args.health:
        run_health_check(api, net, oled_driver, mic_driver, speaker_driver, cam_driver)
        return

    if args.test_camera:
        print("\n" + "=" * 50)
        print("📸 AGROVISION CAMERA DIAGNOSTIC & TEST")
        print("=" * 50)
        cam_info = cam_driver.check_camera()
        print("1. Detecting Camera Hardware...")
        print(f"   Camera Interface: {cam_info.get('type')}")
        print(f"   Detected:         {'YES' if cam_info.get('detected') else 'NO'}")
        print(f"   Status:           {cam_info.get('status', 'Ready')}")

        print("\n2. Initializing Camera...")
        cam_ok = cam_driver.initialize()
        print(f"   Driver Init:      [{'OK' if cam_ok else 'FAIL'}]")

        test_dir = os.path.join(str(settings.BASE_DIR), "temp_media")
        os.makedirs(test_dir, exist_ok=True)
        test_path = os.path.join(test_dir, "test_camera_capture.jpg")

        print(f"\n3. Capturing Test Image → {test_path}...")
        oled_driver.initialize()
        display.show_taking_photo()
        capture_res = cam_driver.capture_photo(test_path)
        if capture_res and os.path.exists(test_path):
            size_bytes = os.path.getsize(test_path)
            print(f"   Capture Status:   [OK]")
            print(f"   Resolution:       {capture_res.get('resolution', 'N/A')}")
            print(f"   File Size:        {size_bytes} bytes ({size_bytes / 1024:.1f} KB)")
        else:
            print("   Capture Status:   [FAIL]")
            return

        print("\n4. Uploading to AgroVision Cloud Backend...")
        display.show_uploading("Photo")
        upload_res = api.upload_media(test_path, media_type="photo")
        if upload_res and upload_res.get("url"):
            print(f"   Upload Status:    [OK]")
            print(f"   Cloud URL:        {upload_res.get('url')}")
            media_payload = {
                "userId": auth.device_config.userId,
                "farmId": auth.device_config.farmId,
                "fieldId": auth.device_config.fieldId,
                "type": "photo",
                "url": upload_res["url"],
                "thumbnailUrl": upload_res["url"],
                "caption": "Camera diagnostic test photo",
                "latitude": None,
                "longitude": None,
                "source": "raspberry_pi",
                "deviceId": auth.device_config.deviceId,
            }
            record = api.create_media(media_payload)
            print(f"   Media DB Record:  [{'OK' if record else 'FAIL'}]")
            display.show_photo_saved("Test Complete")
        else:
            print("   Upload Status:    [FAIL]")
            display.show_upload_failed()

        print("\n5. Cleaning Up Temporary Test File...")
        try:
            if os.path.exists(test_path):
                os.remove(test_path)
            print("   Cleanup Status:   [OK]")
        except Exception as e:
            print(f"   Cleanup Note:     {e}")

        print("\n" + "=" * 50)
        print("✅ CAMERA TEST COMPLETE")
        print("=" * 50 + "\n")
        return

    if args.test_network:
        print("\n" + "=" * 45)
        print("🌐 AGROVISION NETWORK DIAGNOSTICS")
        print("=" * 45)
        ip = net.get_ip_address()
        online = net.is_connected()
        backend_ok = api.check_health()
        print(f"  Local IP Address:    {ip}")
        print(f"  Internet Status:     [{'ONLINE' if online else 'OFFLINE'}]")
        print(f"  Backend Server:      {api.base_url} [{'REACHABLE' if backend_ok else 'UNREACHABLE'}]")
        print("=" * 45 + "\n")
        return

    if args.test_device:
        print("\n" + "=" * 45)
        print("🏷️  AGROVISION DEVICE IDENTITY")
        print("=" * 45)
        cfg = auth.device_config
        print(f"  Device ID:           {cfg.deviceId}")
        print(f"  Device Name:         {cfg.name}")
        print(f"  Device Type:         {cfg.deviceType}")
        print(f"  Assigned User ID:    {cfg.userId}")
        print(f"  Assigned Farm ID:    {cfg.farmId}")
        print(f"  Assigned Field ID:   {cfg.fieldId}")
        print(f"  Paired:              {'YES' if cfg.paired else 'NO (run normally to pair)'}")
        print(f"  Auth Token Set:      {'YES' if cfg.authToken else 'NO'}")
        print(f"  Config File:         {auth.config_path}")
        print("=" * 45 + "\n")
        return

    if args.test_display:
        oled_driver.initialize()
        print("\nTesting OLED Display states...")
        display.show_boot();         time.sleep(1.0)
        display.show_pairing("AGRO-8842"); time.sleep(1.0)
        display.show_connecting();   time.sleep(1.0)
        display.show_ready("Green Valley Farm", "Mango Plantation"); time.sleep(1.0)
        display.show_listening();    time.sleep(1.0)
        display.show_thinking();     time.sleep(1.0)
        display.show_speaking("WEATHER\n28°C Partly Cloudy\nRain: 20%"); time.sleep(1.0)
        display.show_speaking("TASKS TODAY\n1. Inspect mango\n2. Check drip"); time.sleep(1.0)
        display.show_taking_photo(); time.sleep(1.0)
        display.show_uploading("Photo"); time.sleep(1.0)
        display.show_photo_saved("Mango Field"); time.sleep(1.0)
        display.show_recording();    time.sleep(1.0)
        display.show_video_saved();  time.sleep(1.0)
        display.show_offline();      time.sleep(1.0)
        display.show_error("Test error message"); time.sleep(1.0)
        display.show_ready("Green Valley Farm", "Mango Plantation")
        print("OLED display test complete.\n")
        return

    if args.test_speaker:
        speaker_driver.initialize()
        test_phrase = "AgroVision hardware speaker test. Audio output is fully operational. The crops are looking healthy today."
        print(f"Testing speaker: '{test_phrase}'")
        speaker_driver.speak(test_phrase)
        return

    if args.test_microphone:
        mic_driver.initialize()
        print("\nMicrophone test — speak a voice command:")
        result = mic_driver.listen_and_transcribe("Testing Microphone. Speak now:")
        print(f"\nTranscription result: '{result}'")
        if result:
            print("✅ Microphone OK")
        else:
            print("⚠️  No transcription captured (timeout or no audio)")
        return

    if args.test_backend:
        print(f"\nTesting AgroVision Backend at {api.base_url}...")
        healthy = api.check_health()
        print(f"  Health Check:        [{'OK' if healthy else 'FAIL'}]")
        if healthy:
            hb = api.send_heartbeat()
            print(f"  Heartbeat Sent:      [{'OK' if hb else 'FAIL'}]")
            farms = api.get_farms()
            print(f"  Retrieved Farms:     {len(farms)} farm(s)")
            tasks = api.get_tasks()
            print(f"  Retrieved Tasks:     {len(tasks)} task(s)")
            weather = api.get_weather()
            print(f"  Weather Data:        [{'OK - temp=' + str(weather.get('current', {}).get('temperature', '?')) + '°C' if weather else 'No weather cached'}]")
        return

    if args.test_realtime:
        print(f"\nConnecting to SSE stream at {api.base_url}/api/sync/events...")
        sync = RealtimeSyncService(lambda ev, d: print(f"  → [EVENT] {ev}: {list(d.keys())}"))
        sync.start()
        print("Listening for 10 seconds...")
        time.sleep(10)
        sync.stop()
        print("Realtime test ended.\n")
        return

    # --------------------------------------------------------------------------
    # Single command mode (useful for shell scripting + automation)
    # --------------------------------------------------------------------------
    if args.command:
        oled_driver.initialize()
        mic_driver.initialize()
        speaker_driver.initialize()
        voice = VoiceService(mic_driver, speaker_driver, display, api, auth, camera_service=cam_service)
        voice.run_interaction_cycle(text_input=args.command)
        return

    # --------------------------------------------------------------------------
    # Text mode: interactive development console
    # --------------------------------------------------------------------------
    if args.text_mode:
        print("\n" + "=" * 55)
        print("🌿 AgroVision Interactive Text Mode")
        print("   Type voice commands. Type 'exit' or 'quit' to stop.")
        print("=" * 55 + "\n")

        oled_driver.initialize()
        mic_driver.initialize()
        speaker_driver.initialize()

        # Pairing check in text mode
        if not auth.is_paired():
            logger.warning("[MAIN] Device not paired. Attempting pairing flow...")
            paired = run_pairing_flow(api, auth, display, speaker_driver)
            if not paired:
                logger.error("[MAIN] Pairing failed. Exiting text mode.")
                return

        api.register_device(auth.device_config.farmId, auth.device_config.fieldId)
        display.show_ready("Green Valley Farm", "Mango Plantation")
        voice = VoiceService(mic_driver, speaker_driver, display, api, auth, camera_service=cam_service)

        while True:
            try:
                cmd = input("\n[AgroVision] > ").strip()
                if not cmd:
                    continue
                if cmd.lower() in ("exit", "quit", "q"):
                    print("Exiting text mode. Goodbye.")
                    break
                voice.run_interaction_cycle(text_input=cmd)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break
        return

    # --------------------------------------------------------------------------
    # NORMAL BOOT — Full hardware mode
    # --------------------------------------------------------------------------
    logger.info("=" * 55)
    logger.info(f"🌿 AgroVision Raspberry Pi Client [{settings.SOFTWARE_VERSION}]")
    logger.info(f"   Device ID:  {auth.device_config.deviceId}")
    logger.info(f"   Backend:    {settings.BACKEND_URL}")
    logger.info(f"   Mode:       {'Console' if use_console else 'Hardware'}")
    logger.info("=" * 55)

    # Initialize hardware
    oled_driver.initialize()
    mic_driver.initialize()
    speaker_driver.initialize()
    display.show_boot()
    time.sleep(1.0)

    # Check network + backend
    display.show_connecting()
    if not api.check_health():
        logger.warning("[MAIN] AgroVision backend not reachable. Starting in offline mode.")
        display.show_offline()
        # Still start heartbeat — it will retry when backend comes back
    else:
        logger.info("[MAIN] Connected to AgroVision backend.")

    # Pairing flow (if device is not yet paired)
    if not auth.is_paired():
        logger.warning("[MAIN] Device not paired. Starting pairing flow...")
        paired = run_pairing_flow(api, auth, display, speaker_driver)
        if not paired:
            logger.error("[MAIN] Pairing failed or timed out. Restarting in 10s (systemd will restart).")
            display.show_error("Pairing failed")
            time.sleep(10)
            sys.exit(1)

    # Register device with backend (also updates last-seen)
    api.register_device(auth.device_config.farmId, auth.device_config.fieldId)

    # Start background services
    heartbeat = HeartbeatService(api)
    heartbeat.start()
    logger.info("[MAIN] Heartbeat service started.")

    sync = RealtimeSyncService(
        lambda ev, d: handle_sync_event(ev, d, display, speaker_driver)
    )
    sync.start()
    logger.info("[MAIN] Realtime SSE sync service started.")

    # Resolve farm + field names for display
    farms = api.get_farms()
    farm_name = farms[0].get("name", "Green Valley Farm") if farms else "Green Valley Farm"
    fields = api.get_fields(auth.device_config.farmId)
    field_name = fields[0].get("name", "Farm Field") if fields else "Farm Field"

    display.show_ready(farm_name, field_name)
    speaker_driver.speak(f"AgroVision ready. Field: {field_name}.")

    # Initialize camera
    cam_driver.initialize()

    # Main voice loop
    voice = VoiceService(mic_driver, speaker_driver, display, api, auth, camera_service=cam_service)
    logger.info("[MAIN] Entering main voice loop. Ready for commands.")

    try:
        while True:
            voice.run_interaction_cycle()
            time.sleep(0.5)
            display.show_ready(farm_name, field_name)
    except KeyboardInterrupt:
        logger.info("[MAIN] Shutdown signal received (Ctrl+C).")
    finally:
        logger.info("[MAIN] Shutting down AgroVision Pi...")
        heartbeat.stop()
        sync.stop()
        cam_service.release()
        try:
            display.driver.clear()
        except Exception:
            pass
        logger.info("[MAIN] Shutdown complete.")


if __name__ == "__main__":
    main()
