from dataclasses import dataclass
from typing import Optional


@dataclass
class MediaRecord:
    """Represents a photo or video record — mirrors the backend photos/videos schema."""
    id: str
    type: str                            # photo | video
    url: str                             # path on backend storage, e.g. /uploads/media_xxx.jpg
    userId: str
    farmId: str
    fieldId: str
    source: str = "raspberry_pi"         # raspberry_pi | mobile | website
    cropId: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    caption: Optional[str] = None
    latitude: Optional[float] = None     # null — GPS not available on standard Pi setup
    longitude: Optional[float] = None    # null — GPS not available on standard Pi setup
    durationSeconds: Optional[float] = None  # for videos only
    deviceId: Optional[str] = None
    timestamp: Optional[str] = None
    createdAt: Optional[str] = None

    @property
    def is_photo(self) -> bool:
        return self.type == "photo"

    @property
    def is_video(self) -> bool:
        return self.type == "video"

    @classmethod
    def from_dict(cls, data: dict) -> "MediaRecord":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "photo"),
            url=data.get("url", ""),
            userId=data.get("userId", ""),
            farmId=data.get("farmId", ""),
            fieldId=data.get("fieldId", ""),
            source=data.get("source", "raspberry_pi"),
            cropId=data.get("cropId"),
            thumbnailUrl=data.get("thumbnailUrl"),
            caption=data.get("caption"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            durationSeconds=data.get("durationSeconds"),
            deviceId=data.get("deviceId"),
            timestamp=data.get("timestamp"),
            createdAt=data.get("createdAt"),
        )
