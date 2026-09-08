from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class VoiceCommand:
    raw_text: str
    deviceId: str
    farmId: Optional[str] = None
    fieldId: Optional[str] = None
    intent: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
