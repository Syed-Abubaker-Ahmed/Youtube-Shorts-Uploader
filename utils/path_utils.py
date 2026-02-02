"""
Path utilities with absolute path guarantees.
"""
import os
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


class PathUtils:
    """Path utilities ensuring absolute paths."""
    
    @staticmethod
    def absolute_path(path: Union[str, Path]) -> Path:
        """Convert to absolute path."""
        p = Path(path).expanduser().resolve()
        if not p.is_absolute():
            p = Path.cwd() / p
        return p
    
    @staticmethod
    def generate_video_filename(
        video_type: str,
        job_id: str
    ) -> str:
        """Generate deterministic video filename."""
        return f"{video_type}_{job_id}_final.mp4"
    
    @staticmethod
    def generate_temp_image_name(job_id: str, index: int = 0) -> str:
        """Generate temporary image name for job."""
        return f"temp_{job_id}_image_{index}.png"
    
    @staticmethod
    def generate_temp_audio_name(job_id: str) -> str:
        """Generate temporary audio name for job."""
        return f"temp_{job_id}_narration.wav"
    
    @staticmethod
    def generate_compilation_filename(batch_id: str) -> str:
        """Generate compilation video filename."""
        return f"compilation_{batch_id}.mp4"
    
    @staticmethod
    def ensure_absolute_path(path: Path, context: str = "") -> Path:
        """Ensure path is absolute and log."""
        abs_path = PathUtils.absolute_path(path)
        if not abs_path.is_absolute():
            raise ValueError(f"Failed to make absolute path: {path} (context: {context})")
        logger.debug(f"Path made absolute ({context}): {abs_path}")
        return abs_path
    
    @staticmethod
    def get_relative_name(full_path: Path, base_path: Path) -> str:
        """Get relative name of file."""
        try:
            return str(full_path.relative_to(base_path))
        except ValueError:
            return str(full_path.name)
