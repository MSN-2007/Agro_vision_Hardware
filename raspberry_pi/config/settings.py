import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


class Settings:
    # Backend connection
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/")

    # Device identity — persists across reboots
    DEVICE_ID: str = os.getenv("DEVICE_ID", "AGRO_PI_001")
    DEVICE_NAME: str = os.getenv("DEVICE_NAME", "AgroVision Field Hub")

    # Default farm / field assigned to this Pi (updated after pairing)
    DEFAULT_FARM_ID: str = os.getenv("DEFAULT_FARM_ID", "farm-gv-01")
    DEFAULT_FIELD_ID: str = os.getenv("DEFAULT_FIELD_ID", "field-mango-01")

    # Default user associated with this Pi (updated after pairing)
    DEFAULT_USER_ID: str = os.getenv("DEFAULT_USER_ID", "user-ravi-01")

    # Application behaviour
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT: str = os.getenv("AGROVISION_ENVIRONMENT", "production")
    USE_CONSOLE_OLED: bool = os.getenv("USE_CONSOLE_OLED", "false").lower() == "true"

    # Versioning & timing
    SOFTWARE_VERSION: str = "v1.3.0"
    HEARTBEAT_INTERVAL_SEC: int = int(os.getenv("HEARTBEAT_INTERVAL_SEC", "30"))
    PAIRING_POLL_INTERVAL_SEC: int = 5
    PAIRING_TIMEOUT_SEC: int = 600  # 10 minutes

    # Paths
    CONFIG_FILE_PATH: Path = CONFIG_DIR / "device_config.json"
    BASE_DIR: Path = BASE_DIR


settings = Settings()
