# AgroVision Raspberry Pi Client

**Physical voice assistant hardware client for the AgroVision agriculture platform.**

The Raspberry Pi acts as a physical field assistant that talks to the AgroVision backend over HTTP/SSE — the same backend used by the mobile app and website. All three always see the same data.

```
                         AGROVISION BACKEND
                       /          |           \
                      ↓           ↓            ↓
               MOBILE APP      WEBSITE    RASPBERRY PI
                                              |
                      ┌───────────────────────┼────────────────────┐
                      ↓                       ↓                    ↓
                    OLED                 MICROPHONE            SPEAKER
                                              |
                                          CAMERA
```

---

## Hardware

| Component | Interface | Notes |
|-----------|-----------|-------|
| Raspberry Pi 3B+ | — | Main compute |
| SSD1306 OLED (128x64) | I2C (0x3C) | Status display |
| USB Microphone | USB / ALSA | Voice input |
| Speaker / 3.5mm | ALSA | TTS output |
| Camera Module / USB Webcam | CSI / V4L2 | Photo + video |
| Wi-Fi | wlan0 | Backend connectivity |

All hardware components have **graceful fallbacks**:
- No OLED → console ASCII display
- No microphone → text-mode input
- No speaker → console output
- No camera → simulated field imagery driver

---

## Project Structure

```
raspberry_pi/
├── main.py                     # Entry point — all CLI modes
├── requirements.txt
├── .env.example                # Copy to .env and configure
├── .gitignore
│
├── config/
│   ├── settings.py             # Environment-based configuration
│   ├── device_config.json      # Persisted device credentials (gitignored)
│   └── config.example.yaml    # Full configuration reference
│
├── hardware/                   # Hardware Abstraction Layer (HAL)
│   ├── base.py                 # Abstract driver interfaces
│   ├── oled.py                 # SSD1306 I2C + Console fallback
│   ├── microphone.py           # ALSA/PyAudio + TextMode fallback
│   ├── speaker.py              # pyttsx3 TTS + Console fallback
│   └── camera.py               # libcamera / V4L2 / Simulated drivers
│
├── services/                   # Backend & system services
│   ├── agrovision_api.py       # AgroVision backend REST API client
│   ├── auth_service.py         # Device credentials & pairing state
│   ├── sync_service.py         # SSE realtime event listener
│   ├── heartbeat_service.py    # Periodic device heartbeat
│   ├── network_service.py      # Network connectivity checks
│   ├── voice_service.py        # Voice pipeline (mic → AI → speaker)
│   └── camera_service.py       # Photo/video capture & upload workflow
│
├── models/
│   ├── device.py               # DeviceConfig dataclass
│   ├── response.py             # AssistantResponse dataclass
│   ├── command.py              # VoiceCommand dataclass
│   ├── task.py                 # Task dataclass
│   ├── observation.py          # Observation dataclass
│   └── media.py                # MediaRecord dataclass
│
├── ui/
│   ├── display_manager.py      # All OLED state methods
│   └── states.py               # UIState enum
│
├── utils/
│   ├── logger.py               # Structured logger
│   └── retry.py                # Exponential backoff decorator
│
├── scripts/
│   ├── deploy.sh               # SSH deployment from dev machine
│   ├── install.sh              # OS dependency installer (run on Pi)
│   ├── install_service.sh      # Install systemd service only
│   ├── uninstall.sh            # Remove service + optionally app
│   ├── test_hardware.sh        # Run all hardware tests
│   ├── test_backend.sh         # Run backend integration tests
│   ├── diagnose_pi.sh          # Shell hardware inspection
│   └── hardware_diagnostics.py # Python hardware diagnostics
│
├── systemd/
│   ├── agrovision-pi.service   # Production systemd unit (uses venv)
│   └── agrovision.service      # Legacy basic service
│
└── tests/
    └── (test files)
```

---

## Quick Start (Development)

### 1. Clone and set up

```bash
cd raspberry_pi/
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set BACKEND_URL=http://your-backend-host:5000
```

### 2. Start the AgroVision Backend (SIH_26_01)

```bash
cd ../SIH_26_01
node server/server.js
```

### 3. Run in text mode (no hardware needed)

```bash
cd raspberry_pi/
python main.py --text-mode
```

Type any voice command:
```
[AgroVision] > what are my tasks today
[AgroVision] > take a picture
[AgroVision] > remind me to check irrigation tomorrow
[AgroVision] > what is the weather
[AgroVision] > good morning briefing
```

---

## CLI Reference

```bash
python main.py                      # Full hardware mode (normal operation)
python main.py --text-mode          # Interactive text console (no hardware needed)
python main.py --command "..."      # Execute one command and exit
python main.py --health             # Full diagnostic health check

# Hardware tests
python main.py --test-display       # Cycle through all OLED states
python main.py --test-microphone    # Capture and transcribe audio
python main.py --test-speaker       # Play TTS test phrase
python main.py --test-camera        # Capture → upload → create DB record
python main.py --test-network       # Show IP, internet, backend status
python main.py --test-backend       # Test all backend API endpoints
python main.py --test-realtime      # Listen to SSE for 10 seconds
python main.py --test-device        # Show device identity and pairing status
```

---

## SSH Deployment to Raspberry Pi

### One-command deployment

```bash
# From your developer machine, inside the raspberry_pi/ directory:
./scripts/deploy.sh pi@192.168.1.100
```

This script:
1. Verifies SSH connection
2. rsyncs project files (never copies `.env` or `device_config.json`)
3. Runs `install.sh` on the Pi (OS deps + Python venv)
4. Installs and starts the systemd service
5. Shows live service status
6. Runs health check

### Update after code changes

```bash
git pull
./scripts/deploy.sh pi@192.168.1.100
```

### Manual SSH workflow

```bash
# Connect to Pi
ssh pi@192.168.1.100

# On Pi
cd /home/pi/agrovision-pi
sudo bash scripts/install.sh         # First time only
venv/bin/python main.py --health     # Verify everything works
venv/bin/python main.py --text-mode  # Test interactively
sudo bash scripts/install_service.sh # Install as system service
```

---

## Systemd Service

```bash
# Check status
sudo systemctl status agrovision-pi

# View live logs
sudo journalctl -u agrovision-pi -f

# Restart
sudo systemctl restart agrovision-pi

# Stop
sudo systemctl stop agrovision-pi

# Disable auto-start
sudo systemctl disable agrovision-pi
```

---

## Device Pairing

When the Pi starts for the first time (or after a reset), it runs the pairing flow:

1. Pi requests a pairing code from the backend (`POST /api/devices/pairing/code`)
2. Code is displayed on OLED and spoken via TTS
3. User enters the code in the **AgroVision mobile app** or **website**
4. Backend associates the Pi with the user's farm/field
5. Pi receives credentials and saves them to `config/device_config.json`
6. Pi enters normal operation

The pairing code looks like: **`AGRO-1234`**

---

## Voice Commands

| Say | Action |
|-----|--------|
| "What are my tasks today?" | List pending tasks |
| "Create a task to inspect the tomato field" | Create a new task |
| "Complete the irrigation task" | Mark task as done |
| "What is the weather?" | Current weather |
| "7-day forecast" | Weekly weather |
| "Take a note: leaves are yellowing" | Create field observation |
| "Take a picture" | Capture photo → upload → backend |
| "Start recording" | Start video recording |
| "Stop recording" | Stop + upload video |
| "Good morning briefing" | Weather + task summary |
| "What did I observe last week?" | Retrieve farm memory |
| "Remind me to check irrigation tomorrow" | Create reminder |

---

## Architecture: Backend as Single Source of Truth

```
Voice Input
    ↓
Microphone → Speech-to-Text (Google / ALSA)
    ↓
/api/ai/converse (AgroVision Backend)
    ↓
Intent Detection + Database Operations (server-side)
    ↓
Response (intent + TTS text + OLED text)
    ↓
Pi: OLED display + Speaker TTS

Meanwhile:
Backend → SSE broadcast → Mobile App + Website see same data
```

**What the Pi does NOT do:**
- No direct database access
- No Gemini/AI API keys on the Pi
- No direct communication with mobile app or website
- No fake/generated data

---

## Hardware Setup

### I2C OLED Display

```bash
# Enable I2C on Raspberry Pi
sudo raspi-config → Interface Options → I2C → Enable

# Detect display address
sudo i2cdetect -y 1
# Should show 0x3C or 0x3D
```

### Audio

```bash
# List recording devices
arecord -l

# List playback devices
aplay -l

# Test speaker
aplay /usr/share/sounds/alsa/Front_Center.wav

# Test microphone
arecord -d 3 -f cd test.wav && aplay test.wav
```

### Camera

```bash
# Check CSI camera
libcamera-still --list-cameras
# or
rpicam-still --list-cameras

# Check USB camera
ls -la /dev/video*
```

---

## End-to-End Test Scenarios

### Test 1: Take a photo
```
Say: "Take a picture"
Expected: Camera captures → uploads → backend creates media record → 
          Pi says "Photo saved" → Mobile app & website show the photo
```

### Test 2: Create task
```
Say: "Create a task to inspect this field tomorrow"
Expected: Backend creates task → Pi confirms → Mobile app & website see task
```

### Test 3: Mobile → Pi sync
```
Create a task in the mobile app
Expected: Backend saves → Pi receives SSE TASK_CREATED event → 
          Pi OLED shows "New task" → Pi speaks announcement
```

### Test 4: Offline handling
```
Disconnect internet
Expected: Pi shows "Offline" on OLED → Does NOT falsely report success
Reconnect internet
Expected: Pi reconnects automatically
```

---

## Security Notes

- `.env` is gitignored — never committed
- `config/device_config.json` is gitignored — contains auth tokens
- No database credentials on the Pi
- No Gemini/AI API keys on the Pi
- All AI processing is server-side
- Device uses token-based auth (`x-device-id` + `authToken`)
- Media uploaded as base64 over HTTPS (configure BACKEND_URL with `https://`)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| OLED not working | Check I2C: `i2cdetect -y 1` — should show 0x3C |
| No microphone | Check ALSA: `arecord -l` — Pi falls back to text mode |
| Camera not found | Check: `libcamera-still --list-cameras` or `ls /dev/video*` |
| Backend unreachable | Check BACKEND_URL in .env — ensure backend is running |
| Service won't start | Check logs: `sudo journalctl -u agrovision-pi -n 50` |
| Pairing not working | Ensure backend is running and Pi can reach it |
