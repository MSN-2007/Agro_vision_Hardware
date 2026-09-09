import sys
import os
import time
import argparse
from config.settings import settings
from utils.logger import logger
from hardware.capabilities import hardware_manager, HardwareState
from hardware.oled import LumaOledDriver, ConsoleOledDriver
from hardware.microphone import get_audio_input_driver, TextModeAudioDriver
from hardware.speaker import TtsSpeakerDriver, ConsoleSpeakerDriver
from hardware.camera import get_camera_driver
from ui.display_manager import DisplayManager
from ui.terminal_ui import TerminalUI
from services.agrovision_api import AgroVisionApiService
from services.auth_service import AuthService
from services.sync_service import RealtimeSyncService
from services.heartbeat_service import HeartbeatService
from services.network_service import NetworkService
from services.voice_service import VoiceService
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

    title = data.get("title", data.get("name", data.get("caption", "")))

    if event_type == "TASK_CREATED":
        display.show_speaking(f"NEW TASK\n{title[:18]}")
        if speaker:
            speaker.speak(f"New field task received: {title}")
        print(f"\n🔔 [REALTIME] New Task Created: '{title}'\nAgroVision > ", end="", flush=True)

    elif event_type == "TASK_UPDATED":
        status = data.get("status", "Updated")
        display.show_speaking(f"TASK {status.upper()}\n{title[:18]}")
        print(f"\n🔔 [REALTIME] Task Updated: '{title}' [{status}]\nAgroVision > ", end="", flush=True)

    elif event_type == "TASK_DELETED":
        display.show_speaking("TASK DELETED\nSync'd with cloud")
        print(f"\n🔔 [REALTIME] Task Deleted from cloud\nAgroVision > ", end="", flush=True)

    elif event_type == "OBSERVATION_CREATED":
        src = data.get("source", "")
        if src != "raspberry_pi":
            display.show_speaking(f"NEW NOTE\n{title[:18]}")
            print(f"\n🔔 [REALTIME] Field Note Created: '{title}'\nAgroVision > ", end="", flush=True)

    elif event_type == "REMINDER_CREATED":
        display.show_speaking(f"REMINDER\n{title[:18]}")
        if speaker:
            speaker.speak(f"New reminder: {title}")
        print(f"\n🔔 [REALTIME] Reminder: '{title}'\nAgroVision > ", end="", flush=True)

    elif event_type in ("PHOTO_CREATED", "VIDEO_CREATED"):
        src = data.get("source", "")
        m_type = "PHOTO" if event_type == "PHOTO_CREATED" else "VIDEO"
        if src != "raspberry_pi":
            display.show_speaking(f"NEW {m_type}\n{title[:18]}")
            print(f"\n🔔 [REALTIME] New {m_type}: '{title}'\nAgroVision > ", end="", flush=True)

    elif event_type == "WEATHER_UPDATED":
        display.show_speaking("WEATHER\nUpdated by server")
        print("\n🔔 [REALTIME] Field weather data refreshed by server\nAgroVision > ", end="", flush=True)

    elif event_type == "DEVICE_STATUS_CHANGED":
        device_id = data.get("deviceId", "")
        if device_id == settings.DEVICE_ID:
            status = data.get("status", "")
            logger.info(f"[REALTIME] Device status changed: {status}")

    elif event_type == "FIELD_UPDATED":
        display.show_speaking(f"FIELD UPDATED\n{title[:18]}")
        print(f"\n🔔 [REALTIME] Field updated: '{title}'\nAgroVision > ", end="", flush=True)


# ==============================================================================
# Pairing Flow
# ==============================================================================

def run_pairing_flow(api: AgroVisionApiService, auth: AuthService, display: DisplayManager, speaker) -> bool:
    """
    Executes the full device pairing flow when the Pi is not yet paired.
    """
    logger.info("[PAIRING] Device not paired. Starting pairing flow...")
    if speaker:
        speaker.speak("AgroVision is not paired. Requesting pairing code.")

    # Step 1: Get pairing code from backend
    pairing_code = api.request_pairing_code()
    if not pairing_code:
        display.show_error("Pairing failed")
        if speaker:
            speaker.speak("Could not get pairing code from the backend. Check network connection.")
        return False

    # Step 2: Display on OLED & terminal
    logger.info(f"[PAIRING] Pairing code: {pairing_code}")
    display.show_pairing(pairing_code)

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
            api._update_headers(user_id=user_id)

            logger.info(f"[PAIRING] Paired successfully. Farm={farm_id}, Field={field_id}, User={user_id}")
            display.show_speaking(f"PAIRED!\nFarm: {farm_id[:16]}\nField: {field_id[:16]}")
            if speaker:
                speaker.speak("Device paired successfully! AgroVision is now connected to your farm.")
            return True

        elif status == "expired":
            logger.warning("[PAIRING] Pairing code expired.")
            break

    display.show_error("Pairing timeout")
    logger.warning(f"[PAIRING] Pairing timed out after {timeout} seconds")
    return False


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AgroVision Raspberry Pi Headless & Physical Hardware Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      # Headless / Terminal-First primary mode
  python main.py --status             # Show system and network status
  python main.py --hardware           # Inspect hardware capabilities (OLED, mic, cam)
  python main.py --health             # Run diagnostic health check
  python main.py --command "weather"  # Run single command and exit
        """
    )

    parser.add_argument("--status",         action="store_true", help="Print system status and exit")
    parser.add_argument("--hardware",       action="store_true", help="Print hardware peripheral statuses and exit")
    parser.add_argument("--health",         action="store_true", help="Run full diagnostic health check and exit")
    parser.add_argument("--text-mode",      action="store_true", help="Force interactive terminal REPL mode")
    parser.add_argument("--test-camera",    action="store_true", help="Test camera detection and capture")
    parser.add_argument("--test-display",   action="store_true", help="Test OLED display states")
    parser.add_argument("--test-backend",   action="store_true", help="Test connection to AgroVision backend")
    parser.add_argument("--test-realtime",  action="store_true", help="Test SSE real-time synchronization")
    parser.add_argument("--command",        type=str,            help="Execute a single command and exit")

    args = parser.parse_args()

    # --------------------------------------------------------------------------
    # 1. Initialize Hardware Capabilities & Drivers
    # --------------------------------------------------------------------------
    hardware_manager.initialize_all()

    # Display / OLED Driver: optional hardware
    if hardware_manager.is_available("oled"):
        oled_driver = hardware_manager.get_oled_driver()
    else:
        # Luma driver without fallback emulator spam
        oled_driver = LumaOledDriver(
            port=settings.OLED_I2C_BUS,
            address=settings.OLED_I2C_ADDRESS,
            enable_fallback=settings.USE_CONSOLE_OLED
        )

    display = DisplayManager(driver=oled_driver, enable_terminal_output=True)

    # Audio input driver: capability-aware
    mic_driver = get_audio_input_driver()

    # Speaker driver: optional
    if settings.SPEAKER_ENABLED:
        speaker_driver = TtsSpeakerDriver()
    else:
        speaker_driver = ConsoleSpeakerDriver()

    # Camera driver: capability-aware (returns UnavailableCameraDriver when absent)
    cam_driver = get_camera_driver()

    # --------------------------------------------------------------------------
    # 2. Initialize Core Services (Network, API, Auth)
    # --------------------------------------------------------------------------
    api = AgroVisionApiService()
    auth = AuthService()
    api._update_headers(user_id=auth.device_config.userId)
    net = NetworkService(api)
    cam_service = CameraService(cam_driver, display, speaker_driver, api, auth)
    voice = VoiceService(mic_driver, speaker_driver, display, api, auth, camera_service=cam_service)

    # --------------------------------------------------------------------------
    # 3. CLI Quick Diagnostic Modes
    # --------------------------------------------------------------------------
    if args.hardware:
        TerminalUI.print_hardware()
        return

    if args.status:
        sync_mock = type('Obj', (), {'running': False})()
        TerminalUI.print_status(api, auth, net, sync_mock)
        return

    if args.health:
        sync_mock = type('Obj', (), {'running': False})()
        hb_mock = type('Obj', (), {'running': False})()
        TerminalUI.print_health(api, net, auth, sync_mock, hb_mock)
        return

    if args.command:
        sync_mock = type('Obj', (), {'running': False})()
        hb_mock = type('Obj', (), {'running': False})()
        TerminalUI.execute_command(
            cmd=args.command,
            api=api,
            auth=auth,
            net=net,
            sync=sync_mock,
            heartbeat=hb_mock,
            voice=voice,
            camera_service=cam_service,
            display=display,
        )
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
        return

    if args.test_camera:
        print("\n" + "=" * 50)
        print("📸 AGROVISION CAMERA DIAGNOSTIC & TEST")
        print("=" * 50)
        cam_info = cam_driver.check_camera()
        print(f"  Camera Type:      {cam_info.get('type')}")
        print(f"  Detected:         {'YES' if cam_info.get('detected') else 'NO'}")
        print(f"  Status:           {cam_info.get('status', 'Unavailable')}")
        if not cam_info.get("detected"):
            print("\n  Camera is currently unavailable.")
            print("  Connect a supported camera to enable photo capture.\n")
        return

    if args.test_display:
        print("\nTesting OLED Display states...")
        display.show_boot();         time.sleep(0.5)
        display.show_connecting();   time.sleep(0.5)
        display.show_ready("Green Valley Farm", "Mango Field"); time.sleep(0.5)
        display.show_speaking("AGROVISION\nTerminal First Mode"); time.sleep(0.5)
        print("Display test complete.\n")
        return

    # --------------------------------------------------------------------------
    # 4. Standard Application Startup (Headless / Terminal-First)
    # --------------------------------------------------------------------------
    # Display Startup Banner
    TerminalUI.print_startup_banner(
        device_id=auth.device_config.deviceId,
        network_status="CONNECTING",
        backend_status="CONNECTING",
        realtime_status="CONNECTING",
    )

    display.show_boot()

    # Network & Backend Reachability Check
    net_connected = net.is_connected()
    backend_connected = api.check_health()

    net_status_str = "CONNECTED" if net_connected else "OFFLINE"
    backend_status_str = "CONNECTED" if backend_connected else "UNREACHABLE"

    if not backend_connected:
        logger.warning("[MAIN] AgroVision backend not reachable. Starting in offline/standalone mode.")
        display.show_offline()
    else:
        logger.info(f"[MAIN] Connected to AgroVision backend at {api.base_url}.")

    # Pairing flow (if device is not yet paired)
    if not auth.is_paired():
        logger.warning("[MAIN] Device not paired. Starting pairing flow...")
        paired = run_pairing_flow(api, auth, display, speaker_driver)
        if not paired:
            logger.warning("[MAIN] Pairing not completed. Continuing in unpaired mode.")

    # Register device with backend
    if backend_connected:
        api.register_device(auth.device_config.farmId, auth.device_config.fieldId)

    # Start Background Core Services (Heartbeat & SSE Realtime)
    heartbeat = HeartbeatService(api)
    heartbeat.start()
    logger.info("[MAIN] Heartbeat service started in background.")

    sync = RealtimeSyncService(
        lambda ev, d: handle_sync_event(ev, d, display, speaker_driver)
    )
    sync.start()
    logger.info("[MAIN] Realtime SSE sync service started in background.")

    realtime_status_str = "CONNECTED"

    # Display Ready Banner
    TerminalUI.print_ready_banner(
        device_id=auth.device_config.deviceId,
        status="ONLINE" if backend_connected else "STANDALONE",
        backend_status=backend_status_str,
        realtime_status=realtime_status_str,
    )

    farms = api.get_farms() if backend_connected else []
    farm_name = farms[0].get("name", "Green Valley Farm") if farms else "Green Valley Farm"
    fields = api.get_fields(auth.device_config.farmId) if backend_connected else []
    field_name = fields[0].get("name", "Farm Field") if fields else "Farm Field"

    display.show_ready(farm_name, field_name)

    # --------------------------------------------------------------------------
    # 5. Interactive Terminal Loop or Headless Daemon Mode
    # --------------------------------------------------------------------------
    is_interactive = sys.stdin.isatty() or args.text_mode

    if is_interactive:
        print("Type 'help' for commands, or type any request for AgroVision AI.")
        print("Type 'exit' or 'quit' to stop.\n")

        try:
            while True:
                try:
                    cmd = input("AgroVision > ").strip()
                    if not cmd:
                        continue
                    keep_running = TerminalUI.execute_command(
                        cmd=cmd,
                        api=api,
                        auth=auth,
                        net=net,
                        sync=sync,
                        heartbeat=heartbeat,
                        voice=voice,
                        camera_service=cam_service,
                        display=display,
                    )
                    if not keep_running:
                        break
                except EOFError:
                    print("\nEOF received. Exiting.")
                    break
        except KeyboardInterrupt:
            print("\nShutdown signal received (Ctrl+C).")
    else:
        # Non-interactive / systemd background service mode
        logger.info("[MAIN] Running in headless background daemon mode. Services active.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("[MAIN] Shutdown signal received.")

    # --------------------------------------------------------------------------
    # 6. Clean Shutdown
    # --------------------------------------------------------------------------
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
