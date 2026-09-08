from dataclasses import dataclass
from typing import Optional

@dataclass
class DeviceConfig:
    deviceId: str
    name: str
    deviceType: str
    userId: str
    farmId: Optional[str] = None
    fieldId: Optional[str] = None
    paired: bool = False
    authToken: Optional[str] = None
