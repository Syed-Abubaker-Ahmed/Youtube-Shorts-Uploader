"""
Main orchestration engine for video generation pipeline.
Handles short generation AND triggers compilation after 20 uploads.
"""
import logging
import uuid
from pathlib import Path
from datetime import UTC, datetime
from typing import Optional, List

from config import Config
from database import DatabaseManager
from models import Job, JobStatus
from services import GroqService, ComfyUIService, XTTSService, FFmpegService
from utils import FileUtils, PathUtils

logger = logging.getLogger(__name__)


class VideoOrchestrator:
    """Main orchestration engine."""

    SERIES_TARGET_COUNT = 20  # shorts per compilation

    def __init__(self):
        self.db = DatabaseManager()
        self.groq = GroqService()
        self.comfyui = ComfyUIService()
        self.xtts = XTTSService()
        self.ffmpeg = FFmpegService()
        self.last_idea_fetch: Optional[datetime] = None

    # ---------------------------------------------------------
    # Health & ideas
    # ---------------------------------------------------------

    def health_check(self) -> dict:
        status = {
            "comfyui": self.comfyui.is_available(),
            "xtts": self.xtts.is_available(),
            "ffmpeg": self.ffmpeg.is_available(),
        }
        logger.info(f"Health check: {status}")
        return status

    def ensure_ideas_available(self, min_ideas: int = 5) -> bool:
        count = self.db.get_ideas_count()
        logger.info(f"Current ideas in database: {count}")

        if count < min_ideas:
            return self.fetch_ideas_from_groq()

        return True

    def fetch_ideas_from_groq(self) -> bool:
        try:
            ideas = self.groq.generate_videos()
            if not ideas:
                logger.error("Groq returned no ideas")
                return False

            if not self.db.save_ideas_batch(ideas):
                logger.error("Failed to save Groq ideas")
                return False

            self.last_idea_fetch = datetime.now(UTC)
            logger.info(f"Saved {len(ideas)} new ideas")
            return True

        except Exception:
            logger.exception("Failed to fetch ideas from Groq")
            return False

    # ---------------------------------------------------------
    # Main pipeline (SHORTS)
    # ---------------------------------------------------------

    def process_next_video(self) -> Optional[Job]:
        logger.info("Starting next video processing")

        # 🔒 ADDITION: HARD GENERATION GATE (NO REMOVALS)
        ideas_available = self.db.get_ideas_count()
        ready_videos = len(self.get_ready_videos())

        logger.info(
            f"Generation gate → ideas={ideas_available}, ready_videos={ready_videos}"
        )

        # ❌ If no ideas but uploads pending → WAIT
        if ideas_available == 0 and ready_videos > 0:
            logger.info(
                "Waiting for pending uploads before generating new videos"
            )
            return None

        # ❌ Fetch ideas ONLY when both are zero
        if ideas_available == 0 and ready_videos == 0:
            logger.info("No ideas and no ready videos → fetching new ideas")
            if not self.fetch_ideas_from_groq():
                return None

        # ---------------------------------------------
        # EXISTING LOGIC BELOW (UNCHANGED)
        # ---------------------------------------------

        # ⚠️ DO NOT allow ensure_ideas_available to trigger Groq
        # Generation rules are handled strictly by the gate above
        if self.db.get_ideas_count() == 0:
            return None


        idea = self.db.get_unused_idea()
        if not idea:
            logger.warning("No unused ideas available")
            return None

        job = Job(
            job_id=str(uuid.uuid4())[:8],
            idea=idea,
            status=JobStatus.CREATED
        )

        try:
            if not self._generate_images(job):
                return self._fail_job(job, "Image generation failed")

            if not self._generate_audio(job):
                return self._fail_job(job, "Audio generation failed")

            if not self._assemble_video(job):
                return self._fail_job(job, "Video assembly failed")

            job.status = JobStatus.READY_FOR_UPLOAD
            self.db.save_job(job)

            # ✅ Mark idea used (DO NOT DELETE)
            self.db.mark_idea_used(job.idea.id)

            # ✅ Cleanup temp files ONLY (images + wav)
            self._cleanup_job_files(job)

            logger.info(
                f"Job {job.job_id} ready for upload → {job.video_path}"
            )
            return job

        except Exception as e:
            logger.exception(f"Unexpected error for job {job.job_id}")
            return self._fail_job(job, str(e))

    # ---------------------------------------------------------
    # Compilation trigger (CALLED AFTER UPLOAD)
    # ---------------------------------------------------------

    def check_and_create_compilation(self, series_id: str) -> Optional[Job]:
        uploaded = self.db.get_uploaded_jobs_by_series(series_id)

        if len(uploaded) < self.SERIES_TARGET_COUNT:
            return None

        if self.db.compilation_exists(series_id):
            logger.info(f"Compilation already exists for series {series_id}")
            return None

        logger.info(f"Creating compilation for series {series_id}")

        video_paths = [Path(j.video_path) for j in uploaded]

        output_path = (
            Config.PROJECT_ROOT / "video" / f"compilation_{series_id}.mp4"
        )

        if not self.ffmpeg.combine_videos(video_paths, output_path):
            logger.error("Compilation ffmpeg failed")
            return None

        series_idea = self.db.get_series_idea(series_id)

        job = Job(
            job_id=str(uuid.uuid4())[:8],
            idea=series_idea,
            video_path=str(output_path.resolve()),
            status=JobStatus.READY_FOR_UPLOAD,
            is_compilation=True
        )

        self.db.save_job(job)
        logger.info(f"Compilation ready → {job.video_path}")
        return job

    # ---------------------------------------------------------
    # Steps
    # ---------------------------------------------------------

    def _generate_images(self, job: Job) -> bool:
        logger.info(f"Generating images for job {job.job_id}")

        image_paths: List[Path] = []

        try:
            questions = job.idea.narration_script.splitlines()
            positives = job.idea.get_positive_prompts()
            negatives = job.idea.get_negative_prompts()

            if not questions:
                logger.error("No narration scenarios found")
                return False

            for idx, _ in enumerate(questions):
                pos = positives[idx % len(positives)]
                neg = negatives[idx % len(negatives)]

                # 🔑 TWO images per scenario
                for _ in range(2):
                    img = self.comfyui.generate_image(
                        positive_prompt=pos,
                        negative_prompt=neg
                    )
                    if not img:
                        return False

                    image_paths.append(img.resolve())

            job.image_paths = [str(p) for p in image_paths]
            job.status = JobStatus.IMAGE_GENERATED
            self.db.save_job(job)
            return True

        except Exception:
            logger.exception("Image generation error")
            return False

    def _generate_audio(self, job: Job) -> bool:
        try:
            name = Path(PathUtils.generate_temp_audio_name(job.job_id)).stem

            audio = self.xtts.generate_speech(
                text=job.idea.narration_script,
                output_name=name,
                language=Config.XTTS_LANGUAGE
            )

            if not audio:
                return False

            job.audio_path = str(audio.resolve())
            job.status = JobStatus.AUDIO_GENERATED
            self.db.save_job(job)
            return True

        except Exception:
            logger.exception("Audio generation error")
            return False

    def _assemble_video(self, job: Job) -> bool:
        try:
            output = (
                Config.PROJECT_ROOT / "video" /
                PathUtils.generate_video_filename(
                    job.idea.video_type.value,
                    job.job_id
                )
            )

            if not self.ffmpeg.assemble_video(
                image_paths=[Path(p) for p in job.image_paths],
                audio_path=Path(job.audio_path),
                output_path=output
            ):
                return False

            job.video_path = str(output.resolve())
            job.status = JobStatus.VIDEO_ASSEMBLED
            self.db.save_job(job)
            return True

        except Exception:
            logger.exception("Video assembly error")
            return False

    # ---------------------------------------------------------
    # Cleanup & helpers
    # ---------------------------------------------------------

    def _cleanup_job_files(self, job: Job) -> None:
        files = [Path(p) for p in job.image_paths or []]
        if job.audio_path:
            files.append(Path(job.audio_path))

        FileUtils.safe_delete_files(files)

    def _fail_job(self, job: Job, reason: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = reason
        self.db.save_job(job)

        self._cleanup_job_files(job)

        logger.error(f"Job {job.job_id} failed: {reason}")
        return None

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def get_ready_videos(self) -> list:
        return self.db.get_jobs_by_status(JobStatus.READY_FOR_UPLOAD)

    def get_system_status(self) -> dict:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "health_check": self.health_check(),
            "ideas_available": self.db.get_ideas_count(),
            "ready_videos": len(self.get_ready_videos()),
            "last_idea_fetch": (
                self.last_idea_fetch.isoformat()
                if self.last_idea_fetch else None
            ),
        }
