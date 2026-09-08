from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class AssistantResponse:
    success: bool
    intent: str
    text: str
    oledText: str
    speak: bool = True
    data: Optional[Any] = None
