"""
Configuration management for YouTube automation system.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Central configuration manager."""

    # ------------------------------------------------------------------
    # Project paths
    # ------------------------------------------------------------------

    PROJECT_ROOT = Path(__file__).parent.absolute()
    VIDEO_OUTPUT_DIR = PROJECT_ROOT / "video"
    DATABASE_PATH = PROJECT_ROOT / "automation.db"
    LOG_FILE = PROJECT_ROOT / "app.log"

    # ------------------------------------------------------------------
    # External service paths (ABSOLUTE PATHS - DO NOT MODIFY)
    # ------------------------------------------------------------------

    COMFYUI_OUTPUT_PATH = Path("/home/creation/ComfyUI/output/").absolute()
    XTTS_OUTPUT_PATH = Path("/home/creation/xtts_api/output/").absolute()

    # ------------------------------------------------------------------
    # API Endpoints
    # ------------------------------------------------------------------

    COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")
    COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
    COMFYUI_ENDPOINT = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}/prompt"

    XTTS_HOST = os.getenv("XTTS_HOST", "127.0.0.1")
    XTTS_PORT = int(os.getenv("XTTS_PORT", "8000"))
    XTTS_ENDPOINT = f"http://{XTTS_HOST}:{XTTS_PORT}/tts"

    # ------------------------------------------------------------------
    # Groq API
    # ------------------------------------------------------------------

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    # ------------------------------------------------------------------
    # YouTube OAuth (UPLOADS USE OAUTH ONLY)
    # ------------------------------------------------------------------

    YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
    YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

    # ------------------------------------------------------------------
    # Video Settings
    # ------------------------------------------------------------------

    VIDEO_DURATION_MIN = int(os.getenv("VIDEO_DURATION_MIN", "20"))
    VIDEO_DURATION_MAX = int(os.getenv("VIDEO_DURATION_MAX", "30"))
    VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
    VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
    TARGET_COMPILATION_DURATION = int(os.getenv("TARGET_COMPILATION_DURATION", "600"))

    # ------------------------------------------------------------------
    # Upload Settings
    # ------------------------------------------------------------------

    UPLOAD_DELAY_MIN = int(os.getenv("UPLOAD_DELAY_MIN", "900"))   # 15 min
    UPLOAD_DELAY_MAX = int(os.getenv("UPLOAD_DELAY_MAX", "2100"))  # 35 min

    # ------------------------------------------------------------------
    # API Defaults
    # ------------------------------------------------------------------

    IDEAS_PER_BATCH = int(os.getenv("IDEAS_PER_BATCH", "20"))
    XTTS_LANGUAGE = os.getenv("XTTS_LANGUAGE", "en")
    POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "5"))

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # ------------------------------------------------------------------
    # Video Types
    # ------------------------------------------------------------------

    VIDEO_TYPES = [
        "would_you_rather",
        "fantasy_choice",
        "month_choice",
    ]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration for production execution."""
        errors = []

        # Groq
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY environment variable not set")

        # OAuth (uploads depend on this)
        if not cls.YOUTUBE_CLIENT_ID:
            errors.append("YOUTUBE_CLIENT_ID not set")
        if not cls.YOUTUBE_CLIENT_SECRET:
            errors.append("YOUTUBE_CLIENT_SECRET not set")
        if not cls.YOUTUBE_REFRESH_TOKEN:
            errors.append("YOUTUBE_REFRESH_TOKEN not set")

        # External outputs
        if not cls.COMFYUI_OUTPUT_PATH.exists():
            errors.append(f"ComfyUI output path missing: {cls.COMFYUI_OUTPUT_PATH}")

        if not cls.XTTS_OUTPUT_PATH.exists():
            errors.append(f"XTTS output path missing: {cls.XTTS_OUTPUT_PATH}")

        # Ensure local dirs exist
        cls.VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        if errors:
            for error in errors:
                logger.error(error)
            return False

        logger.info("Configuration validated successfully")
        return True

    # ------------------------------------------------------------------
    # Info for logging/debug
    # ------------------------------------------------------------------

    @classmethod
    def get_info(cls) -> dict:
        return {
            "comfyui_endpoint": cls.COMFYUI_ENDPOINT,
            "xtts_endpoint": cls.XTTS_ENDPOINT,
            "comfyui_output": str(cls.COMFYUI_OUTPUT_PATH),
            "xtts_output": str(cls.XTTS_OUTPUT_PATH),
            "project_video_dir": str(cls.VIDEO_OUTPUT_DIR),
            "video_format": f"{cls.VIDEO_WIDTH}x{cls.VIDEO_HEIGHT}",
            "ideas_per_batch": cls.IDEAS_PER_BATCH,
            "upload_delay_range": f"{cls.UPLOAD_DELAY_MIN}-{cls.UPLOAD_DELAY_MAX}s",
        }
