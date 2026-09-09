import os
import sys
import time
import platform
import shutil
from typing import Dict, Any, Optional
from config.settings import settings
from utils.logger import logger
from hardware.capabilities import hardware_manager, HardwareState


class TerminalUI:
    """
    Terminal-first interface for AgroVision Raspberry Pi.
    Provides structured banners, status reports, diagnostic checks,
    and an interactive command prompt (AgroVision > ).
    """

    BANNER_WIDTH = 40

    @classmethod
    def print_startup_banner(
        cls,
        device_id: str,
        network_status: str = "CONNECTING",
        backend_status: str = "CONNECTING",
        realtime_status: str = "CONNECTING",
        hw_states: Optional[Dict[str, str]] = None,
    ):
        hw = hw_states or hardware_manager.format_banner_dict()
        print("\n" + "=" * cls.BANNER_WIDTH)
        print("          AGROVISION PI AGENT          ")
        print("=" * cls.BANNER_WIDTH)
        print()
        print(f"Device       : {device_id}")
        print(f"Status       : STARTING")
        print(f"Network      : {network_status}")
        print(f"Backend      : {backend_status}")
        print(f"Realtime     : {realtime_status}")
        print()
        print("Hardware:")
        print(f"  OLED       : {hw.get('oled', 'NOT DETECTED')}")
        print(f"  Microphone : {hw.get('microphone', 'DISABLED')}")
        print(f"  Camera     : {hw.get('camera', 'DISABLED')}")
        print(f"  Speaker    : {hw.get('speaker', 'NOT CONFIGURED')}")
        print()
        print("=" * cls.BANNER_WIDTH + "\n")

    @classmethod
    def print_ready_banner(
        cls,
        device_id: str,
        status: str = "ONLINE",
        backend_status: str = "CONNECTED",
        realtime_status: str = "CONNECTED",
        hw_states: Optional[Dict[str, str]] = None,
    ):
        hw = hw_states or hardware_manager.format_banner_dict()
        print("\n" + "=" * cls.BANNER_WIDTH)
        print("          AGROVISION PI AGENT          ")
        print("=" * cls.BANNER_WIDTH)
        print()
        print(f"Device       : {device_id}")
        print(f"Status       : {status}")
        print(f"Backend      : {backend_status}")
        print(f"Realtime     : {realtime_status}")
        print()
        print(f"OLED         : {hw.get('oled', 'NOT DETECTED')}")
        print(f"Microphone   : {hw.get('microphone', 'DISABLED')}")
        print(f"Camera       : {hw.get('camera', 'DISABLED')}")
        print()
        print("=" * cls.BANNER_WIDTH + "\n")

    @classmethod
    def print_help(cls):
        print("\n" + "=" * 48)
        print("📖 AGROVISION TERMINAL COMMANDS")
        print("=" * 48)
        print("  help         : Show this list of commands")
        print("  status       : View overall system status")
        print("  hardware     : View hardware peripheral status")
        print("  health       : Run system & connectivity health check")
        print("  tasks        : List field tasks for today")
        print("  reminders    : List active reminders")
        print("  weather      : Show current weather for assigned field")
        print("  farm         : Show current farm & field details")
        print("  memory       : Show Raspberry Pi RAM, CPU & disk usage")
        print("  sync         : Test realtime event stream & sync")
        print("  clear        : Clear terminal screen")
        print("  exit / quit  : Shut down the AgroVision Pi client")
        print()
        print("Natural Language Commands (processed by AI):")
        print("  show today's tasks")
        print("  what is the weather?")
        print("  create task: water tomato field")
        print("  show reminders")
        print("  take photo")
        print("=" * 48 + "\n")

    @classmethod
    def print_status(cls, api, auth, net, sync):
        print("\n" + "=" * 48)
        print("📊 AGROVISION SYSTEM STATUS")
        print("=" * 48)
        backend_ok = api.check_health()
        ip_addr = net.get_ip_address()
        online = net.is_connected()
        paired = auth.is_paired()
        hw = hardware_manager.format_banner_dict()

        print(f"  Device ID:          {auth.device_config.deviceId}")
        print(f"  Device Name:        {auth.device_config.name}")
        print(f"  Firmware Version:   {settings.SOFTWARE_VERSION}")
        print(f"  Network IP:         {ip_addr}")
        print(f"  Internet:           {'CONNECTED' if online else 'OFFLINE'}")
        print(f"  Backend:            {api.base_url} [{'REACHABLE' if backend_ok else 'UNREACHABLE'}]")
        print(f"  Paired Status:      {'PAIRED' if paired else 'NOT PAIRED'}")
        print(f"  Assigned Farm:      {auth.device_config.farmId}")
        print(f"  Assigned Field:     {auth.device_config.fieldId}")
        print(f"  Realtime SSE:       {'LISTENING' if getattr(sync, 'running', False) else 'STOPPED'}")
        print()
        print("  Hardware Peripherals:")
        print(f"    - OLED:           {hw.get('oled')}")
        print(f"    - Microphone:     {hw.get('microphone')}")
        print(f"    - Camera:         {hw.get('camera')}")
        print(f"    - Speaker:        {hw.get('speaker')}")
        print("=" * 48 + "\n")

    @classmethod
    def print_hardware(cls):
        print("\n" + "=" * 52)
        print("🔧 HARDWARE CAPABILITY INSPECTION")
        print("=" * 52)
        # Attempt auto-detection of OLED if not yet connected
        if not hardware_manager.is_available("oled"):
            hardware_manager.check_oled()

        hw_states = hardware_manager.check_all()
        for dev, state in hw_states.items():
            details = hardware_manager.get_details(dev)
            tag = f"[{state.value}]"
            print(f"  {dev.upper():<12} : {tag:<16} {details}")

        print()
        print("  I2C Bus      : Bus 1 (/dev/i2c-1)")
        print("  Plug & Play  : Connecting OLED to I2C will be detected.")
        print("=" * 52 + "\n")

    @classmethod
    def print_health(cls, api, net, auth, sync, heartbeat):
        print("\n" + "=" * 54)
        print("🏥 AGROVISION SYSTEM & HARDWARE HEALTH CHECK")
        print("=" * 54)

        # Core checks
        python_ok = sys.version_info >= (3, 9)
        net_ok = net.is_connected()
        backend_ok = api.check_health()
        auth_ok = auth.is_paired()
        sync_ok = getattr(sync, "running", False)
        hb_ok = getattr(heartbeat, "running", False)

        core_checks = {
            "Raspberry Pi System": True,
            "Python Environment": python_ok,
            "Wi-Fi / Network": net_ok,
            "Backend Reachable": backend_ok,
            "Device Authentication": auth_ok,
            "Realtime Connection": sync_ok,
            "Heartbeat Service": hb_ok,
        }

        print("\n--- CRITICAL CORE SUBSYSTEMS ---")
        for name, status in core_checks.items():
            icon = "✅" if status else "❌"
            tag = "PASS" if status else "FAIL"
            print(f"  {icon} {name:<24} [{tag}]")

        # Optional hardware checks
        hw_states = hardware_manager.check_all()
        print("\n--- OPTIONAL HARDWARE PERIPHERALS ---")
        for dev, state in hw_states.items():
            if state == HardwareState.AVAILABLE:
                icon, desc = "✅", "AVAILABLE"
            elif state == HardwareState.DISABLED:
                icon, desc = "⚪", "DISABLED (Headless Mode)"
            elif state == HardwareState.NOT_CONFIGURED:
                icon, desc = "⚪", "NOT CONFIGURED"
            else:
                icon, desc = "ℹ️ ", "NOT DETECTED (Optional)"
            print(f"  {icon} {dev.capitalize():<24} [{desc}]")

        print("\n" + "-" * 54)
        core_healthy = all(core_checks.values())
        if core_healthy:
            print("🟢 OVERALL HEALTH: HEALTHY (Core operational)")
            print("   Note: Optional peripherals absent; terminal mode active.")
        else:
            failed = [k for k, v in core_checks.items() if not v]
            print(f"🔴 OVERALL HEALTH: DEGRADED (Core issues: {', '.join(failed)})")
        print("=" * 54 + "\n")

    @classmethod
    def print_tasks(cls, api, auth):
        print("\n📋 Fetching tasks from AgroVision backend...")
        tasks = api.get_tasks(field_id=auth.device_config.fieldId)
        if not tasks:
            print("  No tasks currently scheduled for this field.\n")
            return

        print(f"\nFound {len(tasks)} task(s):")
        for i, t in enumerate(tasks, 1):
            title = t.get("title", "Untitled Task")
            status = t.get("status", "Pending")
            priority = t.get("priority", "Normal")
            due = t.get("dueDate", "")
            due_str = f" (Due: {due[:10]})" if due else ""
            print(f"  {i}. [{status.upper()}] {title} [Priority: {priority}]{due_str}")
        print()

    @classmethod
    def print_reminders(cls, api):
        print("\n⏰ Fetching reminders from AgroVision backend...")
        reminders = api.get_reminders()
        if not reminders:
            print("  No active reminders.\n")
            return

        print(f"\nFound {len(reminders)} reminder(s):")
        for i, r in enumerate(reminders, 1):
            title = r.get("title", "Reminder")
            rem_time = r.get("reminderTime", "")
            time_str = f" at {rem_time}" if rem_time else ""
            print(f"  {i}. {title}{time_str}")
        print()

    @classmethod
    def print_weather(cls, api, auth):
        print("\n🌤️  Fetching weather data from AgroVision backend...")
        weather = api.get_weather(field_id=auth.device_config.fieldId)
        if not weather:
            print("  No weather data currently cached for assigned field.\n")
            return

        current = weather.get("current", {})
        temp = current.get("temperature", "N/A")
        humidity = current.get("humidity", "N/A")
        condition = current.get("condition", "N/A")
        wind = current.get("windSpeed", "N/A")

        print("\n" + "-" * 38)
        print(f"  Condition   : {condition}")
        print(f"  Temperature : {temp}°C")
        print(f"  Humidity    : {humidity}%")
        print(f"  Wind Speed  : {wind} km/h")
        print("-" * 38 + "\n")

    @classmethod
    def print_farm(cls, api, auth):
        print("\n🚜 Current Farm & Field Information:")
        farms = api.get_farms()
        fields = api.get_fields(auth.device_config.farmId)

        farm_name = "Green Valley Farm"
        for f in farms:
            if f.get("id") == auth.device_config.farmId:
                farm_name = f.get("name", farm_name)
                break

        field_name = "Assigned Field"
        crop_type = "Not specified"
        for f in fields:
            if f.get("id") == auth.device_config.fieldId:
                field_name = f.get("name", field_name)
                crop_type = f.get("cropType", crop_type)
                break

        print(f"  Farm ID    : {auth.device_config.farmId} ({farm_name})")
        print(f"  Field ID   : {auth.device_config.fieldId} ({field_name})")
        print(f"  Crop Type  : {crop_type}")
        print(f"  User ID    : {auth.device_config.userId}")
        print()

    @classmethod
    def print_memory(cls):
        print("\n💻 Raspberry Pi System Metrics:")
        # Platform info
        print(f"  OS / Kernel : {platform.system()} {platform.release()} ({platform.machine()})")
        print(f"  Python      : {sys.version.split()[0]}")

        # Memory & disk check
        try:
            total, used, free = shutil.disk_usage("/")
            print(f"  Disk Space  : {used // (2**30)} GB used / {total // (2**30)} GB total ({free // (2**30)} GB free)")
        except Exception:
            pass

        if platform.system().lower() == "linux":
            try:
                with open("/proc/meminfo", "r") as f:
                    mem_total = mem_avail = 0
                    for line in f:
                        if "MemTotal" in line:
                            mem_total = int(line.split()[1]) // 1024
                        elif "MemAvailable" in line:
                            mem_avail = int(line.split()[1]) // 1024
                    if mem_total:
                        print(f"  RAM Memory  : {mem_total - mem_avail} MB used / {mem_total} MB total ({mem_avail} MB available)")
            except Exception:
                pass
        print()

    @classmethod
    def print_sync(cls, api, sync):
        print("\n🔄 Realtime SSE Sync Status:")
        is_running = getattr(sync, "running", False)
        print(f"  Status       : {'ACTIVE' if is_running else 'STOPPED'}")
        print(f"  Stream URL   : {api.base_url}/api/sync/events")
        print("  Event types  : TASK_CREATED, TASK_UPDATED, REMINDER_CREATED, WEATHER_UPDATED, etc.")
        print()

    @classmethod
    def execute_command(
        cls,
        cmd: str,
        api,
        auth,
        net,
        sync,
        heartbeat,
        voice,
        camera_service,
        display,
    ) -> bool:
        """
        Executes a single terminal command or routes to AI backend.
        Returns False if the command was 'exit' or 'quit', True otherwise.
        """
        cmd_clean = cmd.strip()
        if not cmd_clean:
            return True

        lower = cmd_clean.lower()

        # Exit
        if lower in ("exit", "quit", "q"):
            print("\nShutting down AgroVision Pi. Goodbye!")
            return False

        # Clear
        if lower == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            return True

        # Help
        if lower in ("help", "?"):
            cls.print_help()
            return True

        # Status
        if lower == "status":
            cls.print_status(api, auth, net, sync)
            return True

        # Hardware
        if lower == "hardware":
            cls.print_hardware()
            return True

        # Health
        if lower == "health":
            cls.print_health(api, net, auth, sync, heartbeat)
            return True

        # Tasks
        if lower == "tasks":
            cls.print_tasks(api, auth)
            return True

        # Reminders
        if lower == "reminders":
            cls.print_reminders(api)
            return True

        # Weather
        if lower == "weather":
            cls.print_weather(api, auth)
            return True

        # Farm
        if lower == "farm":
            cls.print_farm(api, auth)
            return True

        # Memory
        if lower == "memory":
            cls.print_memory()
            return True

        # Sync
        if lower == "sync":
            cls.print_sync(api, sync)
            return True

        # Explicit camera check for 'take photo' command
        if lower in ("take photo", "take picture", "capture photo", "snap photo"):
            if not hardware_manager.is_available("camera"):
                print("\n📷 Camera is currently unavailable.")
                print("   Connect a supported camera to enable photo capture.\n")
                display.show_camera_error("Camera unavailable")
                return True
            else:
                if camera_service:
                    camera_service.capture_photo()
                return True

        # Route natural language command through existing voice/backend AI architecture
        print(f"\n[Processing command with AgroVision AI: '{cmd_clean}']")
        display.show_thinking()
        farm_id = auth.device_config.farmId
        field_id = auth.device_config.fieldId
        response = api.converse(cmd_clean, farm_id=farm_id, field_id=field_id)

        # Handle Camera Intents from AI
        if response.intent in ("TAKE_PHOTO", "START_VIDEO", "STOP_VIDEO"):
            if not hardware_manager.is_available("camera"):
                print("\n📷 Camera is currently unavailable.")
                print("   Connect a supported camera to enable photo capture.\n")
                display.show_camera_error("Camera unavailable")
                return True
            elif response.intent == "TAKE_PHOTO" and camera_service:
                camera_service.capture_photo(farm_id=farm_id, field_id=field_id)
                return True

        # Display AI Response in terminal & OLED
        display.show_speaking(response.oledText)
        print("\n" + "-" * 48)
        print(f"🤖 AgroVision AI Response:")
        print(f"   {response.text}")
        if response.oledText and response.oledText != response.text:
            print(f"   Display: {response.oledText.replace(chr(10), ' | ')}")
        print("-" * 48 + "\n")

        return True
