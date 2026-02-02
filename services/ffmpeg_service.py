"""
FFmpeg video assembly service.
"""
import logging
import subprocess
import random
from pathlib import Path
from typing import List, Optional, Union

from config import Config
from utils import FileUtils, PathUtils

logger = logging.getLogger(__name__)


class FFmpegService:
    """FFmpeg video assembly."""

    def __init__(self):
        self.video_width = Config.VIDEO_WIDTH
        self.video_height = Config.VIDEO_HEIGHT
        self.output_dir = PathUtils.ensure_absolute_path(
            Config.PROJECT_ROOT / "video",
            "Video output"
        )

    # ---------------------------------------------------------
    # Availability
    # ---------------------------------------------------------

    def is_available(self) -> bool:
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5,
                check=True
            )
            return True
        except Exception as e:
            logger.warning(f"FFmpeg not available: {e}")
            return False

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def assemble_video(
        self,
        image_paths: Union[Path, List[Path]],
        audio_path: Path,
        output_path: Path,
        duration: Optional[float] = None
    ) -> bool:
        """
        Assemble a video from ONE or MANY images + one audio track.
        """

        if isinstance(image_paths, Path):
            image_paths = [image_paths]

        if not image_paths:
            logger.error("No images provided for video assembly")
            return False

        for img in image_paths:
            if not FileUtils.file_exists_and_readable(img):
                logger.error(f"Image not readable: {img}")
                return False

        if not FileUtils.file_exists_and_readable(audio_path):
            logger.error(f"Audio not readable: {audio_path}")
            return False

        FileUtils.ensure_dir_exists(output_path.parent)

        try:
            if duration is None:
                duration = self._get_media_duration(audio_path)

            if not duration or duration <= 0:
                logger.error("Invalid or missing audio duration")
                return False

            image_count = len(image_paths)
            per_image_duration = duration / image_count

            logger.info(
                f"Assembling video with {image_count} images "
                f"(audio {duration:.2f}s, per-image {per_image_duration:.2f}s)"
            )

            # -------------------------------------------------
            # Build FFmpeg command
            # -------------------------------------------------

            cmd = ["ffmpeg", "-y"]

            # Inputs: loop each image for its duration
            for img in image_paths:
                cmd += [
                    "-loop", "1",
                    "-t", f"{per_image_duration}",
                    "-i", str(img)
                ]

            # Audio input
            cmd += ["-i", str(audio_path)]

            # -------------------------------------------------
            # Build filter_complex
            # -------------------------------------------------

            scale_pad = (
                f"scale={self.video_width}:{self.video_height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.video_width}:{self.video_height}:"
                f"(ow-iw)/2:(oh-ih)/2"
            )

            filter_parts = []
            for i in range(image_count):
                filter_parts.append(f"[{i}:v]{scale_pad}[v{i}]")

            concat_inputs = "".join(f"[v{i}]" for i in range(image_count))
            filter_parts.append(
                f"{concat_inputs}concat=n={image_count}:v=1:a=0,format=yuv420p[v]"
            )

            filter_complex = ";".join(filter_parts)

            cmd += [
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", f"{image_count}:a",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                str(output_path)
            ]

            logger.debug("FFmpeg command:\n" + " ".join(cmd))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                logger.info(f"Video assembled successfully: {output_path}")
                return True

            logger.error(f"FFmpeg failed:\n{result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg video assembly timed out")
            return False
        except Exception:
            logger.exception("Video assembly failed")
            return False

    # ---------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------

    def _get_media_duration(self, media_path: Path) -> Optional[float]:
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(media_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"ffprobe failed:\n{result.stderr}")
                return None

            return float(result.stdout.strip())

        except Exception as e:
            logger.error(f"Failed to read duration: {e}")
            return None

    def create_compilation(
        self,
        video_paths: List[Path],
        output_path: Path
    ) -> bool:

        if not video_paths:
            logger.error("No videos provided for compilation")
            return False

        FileUtils.ensure_dir_exists(output_path.parent)
        concat_file = output_path.parent / f".concat_{random.randint(10000,99999)}.txt"

        try:
            self._create_concat_demux(video_paths, concat_file)

            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-y",
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                logger.info(f"Compilation created: {output_path}")
                return True

            logger.error(f"FFmpeg compilation failed:\n{result.stderr}")
            return False

        except Exception:
            logger.exception("Compilation failed")
            return False
        finally:
            FileUtils.safe_delete_file(concat_file)

    def _create_concat_demux(
        self,
        video_paths: List[Path],
        output_file: Path
    ) -> None:
        with open(output_file, "w", encoding="utf-8") as f:
            for path in video_paths:
                f.write(f"file '{path.resolve()}'\n")

    def get_video_duration(self, video_path: Path) -> Optional[float]:
        return self._get_media_duration(video_path)
