"""
XTTS v2 text-to-speech service.
"""
import logging
import requests
from pathlib import Path
from typing import Optional

from config import Config
from utils import FileUtils, PathUtils

logger = logging.getLogger(__name__)


class XTTSService:
    """XTTS v2 Text-to-Speech integration."""

    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or Config.XTTS_ENDPOINT
        self.output_path = PathUtils.ensure_absolute_path(
            Config.XTTS_OUTPUT_PATH, "XTTS output"
        )

        # ✅ REQUIRED for XTTS v2
        self.default_speaker_wav = "/home/creation/xtts_api/female_en.wav"

    def is_available(self) -> bool:
        """Check if XTTS is running."""
        try:
            response = requests.get(
                self.endpoint.replace("/tts", "/health"),
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"XTTS not available: {e}")
            return False

    def generate_speech(
        self,
        text: str,
        output_name: str,
        speaker_wav: Optional[str] = None,
        language: Optional[str] = None
    ) -> Optional[Path]:

        if not text.strip():
            logger.error("XTTS text is empty")
            return None

        # 🔥 FIX: strip extension if caller passed .wav
        output_name = Path(output_name).stem

        speaker_wav = speaker_wav or self.default_speaker_wav
        language = language or Config.XTTS_LANGUAGE

        payload = {
            "text": text,
            "output_name": output_name,
            "speaker_wav": speaker_wav,
            "language": language,
        }

        logger.info(f"Generating speech: {output_name}.wav")


        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=180
            )
            response.raise_for_status()

            data = response.json()

            # ✅ CORRECT KEY
            audio_path = data.get("audio_file")
            if not audio_path:
                logger.error(f"XTTS response missing audio_file: {data}")
                return None

            audio_path = Path(audio_path).absolute()

            if FileUtils.wait_for_file(audio_path, timeout=60):
                logger.info(f"Audio generated: {audio_path}")
                return audio_path

            logger.error(f"Audio file not found after timeout: {audio_path}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"XTTS request failed: {e}")
            return None
        except Exception as e:
            logger.exception("XTTS generation failed")
            return None

    def cleanup_audio(self, audio_path: Path) -> bool:
        """Delete generated audio after use."""
        return FileUtils.safe_delete_file(audio_path)
