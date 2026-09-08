from dataclasses import dataclass
from typing import Optional


@dataclass
class Observation:
    """Represents a field observation — mirrors the backend observations collection schema."""
    id: str
    title: str
    content: str
    userId: str
    farmId: str
    fieldId: str
    source: str = "raspberry_pi"         # raspberry_pi | mobile | website
    cropId: Optional[str] = None
    crop: Optional[str] = None
    notes: Optional[str] = None
    latitude: Optional[float] = None     # null when no GPS — do NOT fabricate
    longitude: Optional[float] = None    # null when no GPS — do NOT fabricate
    timestamp: Optional[str] = None
    status: str = "Needs Attention"
    photoUrl: Optional[str] = None
    aiDiagnosis: Optional[str] = None
    deviceId: Optional[str] = None
    createdAt: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Observation":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", data.get("content", "Field Observation")),
            content=data.get("content", data.get("notes", "")),
            userId=data.get("userId", ""),
            farmId=data.get("farmId", ""),
            fieldId=data.get("fieldId", ""),
            source=data.get("source", "raspberry_pi"),
            cropId=data.get("cropId"),
            crop=data.get("crop"),
            notes=data.get("notes"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            timestamp=data.get("timestamp"),
            status=data.get("status", "Needs Attention"),
            photoUrl=data.get("photoUrl"),
            aiDiagnosis=data.get("aiDiagnosis"),
            deviceId=data.get("deviceId"),
            createdAt=data.get("createdAt"),
        )
