import json
from config.settings import settings
from models.device import DeviceConfig
from utils.logger import logger

class AuthService:
    def __init__(self):
        self.config_path = settings.CONFIG_FILE_PATH
        self.device_config = self.load_config()

    def load_config(self) -> DeviceConfig:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return DeviceConfig(
                        deviceId=data.get("deviceId", settings.DEVICE_ID),
                        name=data.get("name", settings.DEVICE_NAME),
                        deviceType=data.get("deviceType", "raspberry_pi"),
                        userId=data.get("userId", "user-ravi-01"),
                        farmId=data.get("farmId", settings.DEFAULT_FARM_ID),
                        fieldId=data.get("fieldId", settings.DEFAULT_FIELD_ID),
                        paired=data.get("paired", True),
                        authToken=data.get("authToken", "token-agro-pi-001")
                    )
            except Exception as e:
                logger.error(f"[AUTH] Error reading config file: {e}")

        return DeviceConfig(
            deviceId=settings.DEVICE_ID,
            name=settings.DEVICE_NAME,
            deviceType="raspberry_pi",
            userId="user-ravi-01",
            farmId=settings.DEFAULT_FARM_ID,
            fieldId=settings.DEFAULT_FIELD_ID,
            paired=True,
            authToken="token-agro-pi-001"
        )

    def save_config(self, cfg: DeviceConfig) -> None:
        self.device_config = cfg
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "deviceId": cfg.deviceId,
                    "name": cfg.name,
                    "deviceType": cfg.deviceType,
                    "userId": cfg.userId,
                    "farmId": cfg.farmId,
                    "fieldId": cfg.fieldId,
                    "paired": cfg.paired,
                    "authToken": cfg.authToken
                }, f, indent=2)
            logger.info(f"[AUTH] Persistent device config saved for {cfg.deviceId}")
        except Exception as e:
            logger.error(f"[AUTH] Failed to write device config: {e}")

    def is_paired(self) -> bool:
        return self.device_config.paired and bool(self.device_config.authToken)
