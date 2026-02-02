"""
Upload scheduler and YouTube upload management (OAuth-based).
"""
import logging
import random
import uuid
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Optional, List

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import Config
from database import DatabaseManager
from models import UploadJob, Job

logger = logging.getLogger(__name__)


class UploadScheduler:
    """Manages upload scheduling and execution."""

    MIN_DELAY_MINUTES = 15
    MAX_DELAY_MINUTES = 25

    def __init__(self, db: DatabaseManager, orchestrator):
        self.db = db
        self.orchestrator = orchestrator
        self.video_dir = Config.PROJECT_ROOT / "video"

        # 🔑 first upload only if NO uploads exist in DB
        self.first_upload = self._is_first_upload()

        # 🚫 DAILY QUOTA HARD STOP FLAG
        self.quota_exceeded = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_first_upload(self) -> bool:
        uploads = self.db.get_all_uploads()
        return len(uploads) == 0

    def _random_delay(self) -> timedelta:
        return timedelta(
            minutes=random.randint(
                self.MIN_DELAY_MINUTES,
                self.MAX_DELAY_MINUTES
            )
        )

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def schedule_upload(self, job: Job) -> Optional[UploadJob]:
        if not job.video_path or not Path(job.video_path).exists():
            logger.error(f"Invalid video path: {job.video_path}")
            return None

        now = datetime.now(UTC)

        if self.first_upload:
            scheduled_time = now
            self.first_upload = False
            logger.info("First upload → scheduled immediately")
        else:
            scheduled_time = now + self._random_delay()

        upload_job = UploadJob(
            upload_id=str(uuid.uuid4())[:8],
            video_path=job.video_path,
            video_type=job.idea.video_type,
            series_id=job.idea.series_id,
            is_compilation=job.is_compilation,
            scheduled_time=scheduled_time,
            status="pending"
        )

        if not self.db.save_upload_job(upload_job):
            logger.error("Failed to persist upload job")
            return None

        logger.info(
            f"Upload scheduled [{upload_job.upload_id}] at "
            f"{scheduled_time.isoformat()}"
        )
        return upload_job

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_pending_uploads(self) -> List[UploadJob]:
        """
        Returns uploads ready to execute:
        - pending
        - failed (retry)
        """
        if self.quota_exceeded:
            logger.warning("Uploads blocked — daily quota exceeded")
            return []

        now = datetime.now(UTC)
        uploads = self.db.get_all_uploads()

        due = [
            u for u in uploads
            if u.status in ("pending", "failed")
            and u.scheduled_time <= now
        ]

        logger.info(f"{len(due)} uploads ready for execution")
        return due

    # ------------------------------------------------------------------
    # Upload execution
    # ------------------------------------------------------------------

    def execute_upload(self, upload_job: UploadJob) -> bool:
        if self.quota_exceeded:
            logger.warning(
                f"Skipping upload [{upload_job.upload_id}] — quota exceeded"
            )
            return False

        logger.info(f"Executing upload [{upload_job.upload_id}]")

        video_path = Path(upload_job.video_path)
        if not video_path.exists():
            return self._mark_failed(upload_job, "Video file missing")

        job = self.db.get_job_by_video_path(upload_job.video_path)
        if not job or not job.idea:
            return self._mark_failed(upload_job, "Missing job or idea metadata")

        if not job.idea.title or not job.idea.caption:
            return self._mark_failed(upload_job, "Empty title or caption")

        # 🔒 Lock upload
        upload_job.status = "uploading"
        self.db.save_upload_job(upload_job)

        try:
            youtube = self._build_youtube_client()

            if upload_job.is_compilation:
                title = job.idea.title
                description = job.idea.caption
            else:
                title = job.idea.title[:100]
                description = f"{job.idea.caption}\n\n#shorts"

            request = youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": description,
                        "categoryId": "22"
                    },
                    "status": {"privacyStatus": "public"}
                },
                media_body=MediaFileUpload(
                    str(video_path),
                    mimetype="video/mp4",
                    resumable=True
                )
            )

            response = request.execute()

            logger.info(
                f"Upload successful [{upload_job.upload_id}] "
                f"videoId={response.get('id')}"
            )

            return self._mark_uploaded(upload_job)

        except Exception as e:
            logger.exception("Upload failed")
            return self._mark_failed(upload_job, str(e))

    # ------------------------------------------------------------------
    # OAuth / YouTube
    # ------------------------------------------------------------------

    def _build_youtube_client(self):
        if not (
            Config.YOUTUBE_CLIENT_ID
            and Config.YOUTUBE_CLIENT_SECRET
            and Config.YOUTUBE_REFRESH_TOKEN
        ):
            raise RuntimeError("YouTube OAuth credentials not configured")

        return build(
            "youtube",
            "v3",
            credentials=Credentials(
                token=None,
                refresh_token=Config.YOUTUBE_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=Config.YOUTUBE_CLIENT_ID,
                client_secret=Config.YOUTUBE_CLIENT_SECRET,
                scopes=["https://www.googleapis.com/auth/youtube.upload"]
            )
        )

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def _mark_uploaded(self, upload_job: UploadJob) -> bool:
        upload_job.status = "uploaded"
        upload_job.uploaded_at = datetime.now(UTC)

        self.db.save_upload_job(upload_job)
        logger.info(f"Upload marked as uploaded [{upload_job.upload_id}]")

        if not upload_job.is_compilation:
            self.orchestrator.check_and_create_compilation(
                upload_job.series_id
            )

        return True

    def _mark_failed(self, upload_job: UploadJob, error: str) -> bool:
        # 🚫 HARD STOP ON QUOTA
        if "quotaExceeded" in error:
            logger.critical(
                "🚫 YOUTUBE DAILY QUOTA EXCEEDED — SYSTEM HALTED"
            )
            self.quota_exceeded = True

            upload_job.status = "failed"
            upload_job.error_message = "quotaExceeded"
            upload_job.uploaded_at = datetime.now(UTC)

            self.db.save_upload_job(upload_job)
            return False

        upload_job.status = "failed"
        upload_job.error_message = error

        # 🔁 retry later
        upload_job.scheduled_time = (
            datetime.now(UTC) + self._random_delay()
        )

        logger.error(
            f"Upload failed [{upload_job.upload_id}]: {error} "
            f"(retry scheduled)"
        )
        return self.db.save_upload_job(upload_job)

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def get_upload_status(self) -> dict:
        uploads = self.db.get_all_uploads()

        return {
            "total_pending": len([u for u in uploads if u.status == "pending"]),
            "total_uploaded": len([u for u in uploads if u.status == "uploaded"]),
            "total_failed": len([u for u in uploads if u.status == "failed"]),
            "next_upload": min(
                (u.scheduled_time for u in uploads if u.status in ("pending", "failed")),
                default=None
            ),
            "quota_exceeded": self.quota_exceeded
        }
