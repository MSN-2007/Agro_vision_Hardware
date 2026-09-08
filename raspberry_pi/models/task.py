from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Task:
    """Represents a farm task — mirrors the backend tasks collection schema."""
    id: str
    title: str
    status: str                          # Pending | InProgress | Completed
    userId: str
    farmId: Optional[str] = None
    fieldId: Optional[str] = None
    description: Optional[str] = None
    dueDate: Optional[str] = None
    voiceCreated: bool = False
    source: str = "raspberry_pi"         # raspberry_pi | mobile | website
    deviceId: Optional[str] = None
    completedAt: Optional[str] = None
    createdAt: Optional[str] = None

    @property
    def is_pending(self) -> bool:
        return self.status.lower() == "pending"

    @property
    def is_completed(self) -> bool:
        return self.status.lower() == "completed"

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", "Untitled Task"),
            status=data.get("status", "Pending"),
            userId=data.get("userId", ""),
            farmId=data.get("farmId"),
            fieldId=data.get("fieldId"),
            description=data.get("description"),
            dueDate=data.get("dueDate"),
            voiceCreated=data.get("voiceCreated", False),
            source=data.get("source", "raspberry_pi"),
            deviceId=data.get("deviceId"),
            completedAt=data.get("completedAt"),
            createdAt=data.get("createdAt"),
        )
