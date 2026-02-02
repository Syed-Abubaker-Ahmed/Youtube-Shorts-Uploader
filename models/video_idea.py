"""
Data models for video automation system.
UPDATED:
- series_id support
- title support (per short + compilation)
- compilation flag
- safe backward compatibility
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List
from enum import Enum
import json


# --------------------------------------------------
# Enums
# --------------------------------------------------

class VideoType(str, Enum):
    WOULD_YOU_RATHER = "would_you_rather"
    FANTASY_CHOICE = "fantasy_choice"
    MONTH_CHOICE = "month_choice"
    COMPILATION = "compilation"


class JobStatus(str, Enum):
    CREATED = "created"
    IMAGE_GENERATED = "image_generated"
    AUDIO_GENERATED = "audio_generated"
    VIDEO_ASSEMBLED = "video_assembled"
    READY_FOR_UPLOAD = "ready_for_upload"
    UPLOADED = "uploaded"
    FAILED = "failed"


# --------------------------------------------------
# Video Idea
# --------------------------------------------------

@dataclass
class VideoIdea:
    """
    A single VIDEO idea.
    - Shorts share the same series_id
    - Compilation uses the same series_id
    """
    id: str
    video_type: VideoType

    # 🔑 NEW
    series_id: str

    # Metadata
    title: str
    caption: str

    # Prompts (JSON-encoded arrays)
    positive_prompt: str          # JSON list[str]
    negative_prompt: str          # JSON list[str]

    narration_script: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    # ---------- Helpers ----------

    def get_positive_prompts(self) -> List[str]:
        try:
            return json.loads(self.positive_prompt)
        except Exception:
            return []

    def get_negative_prompts(self) -> List[str]:
        try:
            return json.loads(self.negative_prompt)
        except Exception:
            return []

    # ---------- Serialization ----------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "video_type": self.video_type.value,
            "series_id": self.series_id,
            "title": self.title,
            "caption": self.caption,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "narration_script": self.narration_script,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoIdea":
        return cls(
            id=data["id"],
            video_type=VideoType(data["video_type"]),
            series_id=data.get("series_id", "legacy"),
            title=data.get("title", ""),
            caption=data.get("caption", ""),
            positive_prompt=data["positive_prompt"],
            negative_prompt=data["negative_prompt"],
            narration_script=data["narration_script"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


# --------------------------------------------------
# Job
# --------------------------------------------------

@dataclass
class Job:
    """Video generation or compilation job."""
    job_id: str
    idea: VideoIdea
    status: JobStatus = JobStatus.CREATED

    # 🔑 NEW
    is_compilation: bool = False

    # Assets
    image_paths: List[str] = field(default_factory=list)
    audio_path: str = ""
    video_path: str = ""

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: str = ""

    # ---------- Serialization ----------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea.to_dict(),
            "status": self.status.value,
            "is_compilation": self.is_compilation,
            "image_paths": self.image_paths,
            "audio_path": self.audio_path,
            "video_path": self.video_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            job_id=data["job_id"],
            idea=VideoIdea.from_dict(data["idea"]),
            status=JobStatus(data["status"]),
            is_compilation=data.get("is_compilation", False),
            image_paths=data.get("image_paths", []),
            audio_path=data.get("audio_path", ""),
            video_path=data.get("video_path", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message", ""),
        )


# --------------------------------------------------
# Upload Job
# --------------------------------------------------

@dataclass
class UploadJob:
    """Video upload job."""
    upload_id: str
    video_path: str
    video_type: VideoType
    series_id: str
    scheduled_time: datetime   # 🔥 moved up

    is_compilation: bool = False
    uploaded_at: datetime = field(default_factory=lambda: datetime.max)
    status: str = "pending"  # pending | uploaded | failed
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "upload_id": self.upload_id,
            "video_path": self.video_path,
            "video_type": self.video_type.value,
            "series_id": self.series_id,
            "is_compilation": self.is_compilation,
            "scheduled_time": self.scheduled_time.isoformat(),
            "uploaded_at": (
                self.uploaded_at.isoformat()
                if self.uploaded_at != datetime.max else ""
            ),
            "status": self.status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UploadJob":
        uploaded_at = (
            datetime.fromisoformat(data["uploaded_at"])
            if data.get("uploaded_at")
            else datetime.max
        )

        return cls(
            upload_id=data["upload_id"],
            video_path=data["video_path"],
            video_type=VideoType(data["video_type"]),
            series_id=data.get("series_id", "legacy"),
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]),
            is_compilation=data.get("is_compilation", False),
            uploaded_at=uploaded_at,
            status=data.get("status", "pending"),
            error_message=data.get("error_message", ""),
        )

