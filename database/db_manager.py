"""
Database management using SQLite.

FEATURES:
- series_id support
- series metadata table
- shorts vs compilation aware
- upload scheduling support
- status queries for orchestrator
- SOFT-delete ideas (used flag only)
"""
import sqlite3
import logging
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime, UTC

from config import Config
from models import VideoIdea, Job, UploadJob, VideoType, JobStatus

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite database manager."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS series_metadata (
                    series_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS video_ideas (
                    id TEXT PRIMARY KEY,
                    video_type TEXT NOT NULL,
                    series_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    positive_prompt TEXT NOT NULL,
                    negative_prompt TEXT NOT NULL,
                    narration_script TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    idea_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_compilation INTEGER DEFAULT 0,

                    image_paths TEXT,
                    audio_path TEXT,
                    video_path TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,

                    FOREIGN KEY (idea_id) REFERENCES video_ideas(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS upload_jobs (
                    upload_id TEXT PRIMARY KEY,
                    video_path TEXT NOT NULL,
                    video_type TEXT NOT NULL,
                    series_id TEXT NOT NULL,
                    is_compilation INTEGER DEFAULT 0,
                    scheduled_time TEXT NOT NULL,
                    uploaded_at TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
            """)

            conn.commit()
            logger.info(f"Database initialized: {self.db_path}")

        finally:
            conn.close()
    # ------------------------------------------------------------------
    # Series metadata  ✅ ADD HERE
    # ------------------------------------------------------------------

    def save_series_metadata(self, series_id: str, title: str, caption: str) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO series_metadata
                (series_id, title, caption, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                series_id,
                title,
                caption,
                datetime.now(UTC).isoformat()
            ))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Video Ideas (SOFT DELETE)
    # ------------------------------------------------------------------

    def save_ideas_batch(self, ideas: List[VideoIdea]) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            for idea in ideas:
                cur.execute("""
                    INSERT OR REPLACE INTO video_ideas
                    (id, video_type, series_id, title, caption,
                     positive_prompt, negative_prompt, narration_script,
                     created_at, used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    idea.id,
                    idea.video_type.value,
                    idea.series_id,
                    idea.title,
                    idea.caption,
                    idea.positive_prompt,
                    idea.negative_prompt,
                    idea.narration_script,
                    idea.created_at.isoformat()
                ))

            conn.commit()
            return True
        except Exception:
            logger.exception("Failed to save ideas batch")
            return False
        finally:
            conn.close()

    def get_unused_idea(self) -> Optional[VideoIdea]:
        conn = self._get_connection()
        row = conn.execute("""
            SELECT * FROM video_ideas
            WHERE used = 0
            ORDER BY created_at ASC
            LIMIT 1
        """).fetchone()
        conn.close()
        return self._row_to_idea(row) if row else None

    def mark_idea_used(self, idea_id: str) -> None:
        conn = self._get_connection()
        conn.execute("UPDATE video_ideas SET used = 1 WHERE id = ?", (idea_id,))
        conn.commit()
        conn.close()

    def get_ideas_count(self) -> int:
        conn = self._get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM video_ideas WHERE used = 0"
        ).fetchone()[0]
        conn.close()
        return count

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def save_job(self, job: Job) -> bool:
        try:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO jobs
                (job_id, idea_id, status, is_compilation,
                 image_paths, audio_path, video_path,
                 created_at, updated_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id,
                job.idea.id,
                job.status.value,
                int(job.is_compilation),
                json.dumps(job.image_paths),
                job.audio_path,
                job.video_path,
                job.created_at.isoformat(),
                datetime.now(UTC).isoformat(),
                job.error_message
            ))
            conn.commit()
            return True
        except Exception:
            logger.exception("Failed to save job")
            return False
        finally:
            conn.close()

    def get_job_by_video_path(self, video_path: str) -> Optional[Job]:
        conn = self._get_connection()
        row = conn.execute("""
            SELECT j.*, i.*
            FROM jobs j
            JOIN video_ideas i ON j.idea_id = i.id
            WHERE j.video_path = ?
            LIMIT 1
        """, (video_path,)).fetchone()
        conn.close()
        return self._row_to_job(row) if row else None

    # ------------------------------------------------------------------
    # Upload Jobs
    # ------------------------------------------------------------------

    def save_upload_job(self, upload: UploadJob) -> bool:
        try:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO upload_jobs
                (upload_id, video_path, video_type, series_id,
                 is_compilation, scheduled_time, uploaded_at,
                 status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                upload.upload_id,
                upload.video_path,
                upload.video_type.value,
                upload.series_id,
                int(upload.is_compilation),
                upload.scheduled_time.isoformat(),
                upload.uploaded_at.isoformat() if upload.uploaded_at != datetime.max else None,
                upload.status,
                upload.error_message
            ))
            conn.commit()
            return True
        except Exception:
            logger.exception("Failed to save upload job")
            return False
        finally:
            conn.close()

    def get_pending_uploads(self) -> List[UploadJob]:
        conn = self._get_connection()
        rows = conn.execute("""
            SELECT * FROM upload_jobs
            WHERE status = 'pending'
            ORDER BY scheduled_time ASC
        """).fetchall()
        conn.close()
        return [self._row_to_upload_job(r) for r in rows]

    def get_all_uploads(self) -> List[UploadJob]:
        conn = self._get_connection()
        rows = conn.execute("SELECT * FROM upload_jobs").fetchall()
        conn.close()
        return [self._row_to_upload_job(r) for r in rows]

    # ------------------------------------------------------------------
    # 🔑 COMPILATION SUPPORT (FIX)
    # ------------------------------------------------------------------

    def get_uploaded_jobs_by_series(self, series_id: str) -> List[Job]:
        conn = self._get_connection()
        rows = conn.execute("""
            SELECT j.*, i.*
            FROM jobs j
            JOIN video_ideas i ON j.idea_id = i.id
            JOIN upload_jobs u ON u.video_path = j.video_path
            WHERE u.series_id = ?
              AND u.status = 'uploaded'
              AND u.is_compilation = 0
            ORDER BY u.uploaded_at ASC
        """, (series_id,)).fetchall()
        conn.close()
        return [self._row_to_job(r) for r in rows]

    def compilation_exists(self, series_id: str) -> bool:
        conn = self._get_connection()
        row = conn.execute("""
            SELECT 1 FROM upload_jobs
            WHERE series_id = ?
              AND is_compilation = 1
              AND status = 'uploaded'
            LIMIT 1
        """, (series_id,)).fetchone()
        conn.close()
        return row is not None

    def get_series_idea(self, series_id: str) -> VideoIdea:
        conn = self._get_connection()
        row = conn.execute("""
            SELECT * FROM video_ideas
            WHERE series_id = ?
            ORDER BY created_at ASC
            LIMIT 1
        """, (series_id,)).fetchone()
        conn.close()

        if not row:
            raise RuntimeError(f"No idea found for series {series_id}")

        return self._row_to_idea(row)

    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        conn = self._get_connection()
        rows = conn.execute("""
            SELECT j.*, i.*
            FROM jobs j
            JOIN video_ideas i ON j.idea_id = i.id
            WHERE j.status = ?
            ORDER BY j.created_at ASC
        """, (status.value,)).fetchall()
        conn.close()
        return [self._row_to_job(r) for r in rows]

    # ------------------------------------------------------------------
    # Row mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_idea(row: sqlite3.Row) -> VideoIdea:
        return VideoIdea(
            id=row["id"],
            video_type=VideoType(row["video_type"]),
            series_id=row["series_id"],
            title=row["title"],
            caption=row["caption"],
            positive_prompt=row["positive_prompt"],
            negative_prompt=row["negative_prompt"],
            narration_script=row["narration_script"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            job_id=row["job_id"],
            idea=DatabaseManager._row_to_idea(row),
            status=JobStatus(row["status"]),
            is_compilation=bool(row["is_compilation"]),
            image_paths=json.loads(row["image_paths"] or "[]"),
            audio_path=row["audio_path"] or "",
            video_path=row["video_path"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error_message=row["error_message"] or "",
        )

    @staticmethod
    def _row_to_upload_job(row: sqlite3.Row) -> UploadJob:
        uploaded_at = (
            datetime.fromisoformat(row["uploaded_at"])
            if row["uploaded_at"]
            else datetime.max
        )

        return UploadJob(
            upload_id=row["upload_id"],
            video_path=row["video_path"],
            video_type=VideoType(row["video_type"]),
            series_id=row["series_id"],
            is_compilation=bool(row["is_compilation"]),
            scheduled_time=datetime.fromisoformat(row["scheduled_time"]),
            uploaded_at=uploaded_at,
            status=row["status"],
            error_message=row["error_message"] or "",
        )
