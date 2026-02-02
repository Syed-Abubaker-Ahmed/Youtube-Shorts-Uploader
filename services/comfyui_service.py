"""
ComfyUI image generation service (production-safe).
Uses a pre-exported, validated workflow JSON.
"""
import json
import logging
import time
import uuid
import requests
from pathlib import Path
from typing import Optional

from config import Config
from utils import FileUtils, PathUtils

logger = logging.getLogger(__name__)


class ComfyUIService:
    """ComfyUI integration for image generation using a fixed workflow."""

    def __init__(self, endpoint: str = None):
        self.endpoint = endpoint or Config.COMFYUI_ENDPOINT
        self.output_path = PathUtils.ensure_absolute_path(
            Config.COMFYUI_OUTPUT_PATH, "ComfyUI output"
        )

        # 🔒 HARD-LOCKED WORKFLOW
        self.workflow_path = Path("/home/creation/ComfyUI/workflows/sd15_basic.json")


        if not self.workflow_path.exists():
            raise FileNotFoundError(
                f"ComfyUI workflow not found: {self.workflow_path}"
            )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            r = requests.get(self.endpoint.replace("/prompt", ""), timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str,
        seed: Optional[int] = None
    ) -> Optional[Path]:

        workflow = self._load_workflow()

        # ✅ Inject prompts (LOCKED NODE IDS)
        workflow["2"]["inputs"]["text"] = positive_prompt
        workflow["3"]["inputs"]["text"] = negative_prompt

        # ✅ Seed control
        if seed is None:
            seed = uuid.uuid4().int & 0xFFFFFFFF
        workflow["5"]["inputs"]["seed"] = seed

        # ✅ Deterministic filename
        filename_prefix = f"job_{uuid.uuid4().hex[:8]}"
        workflow["7"]["inputs"]["filename_prefix"] = filename_prefix

        payload = {
            "prompt": workflow,
            "client_id": str(uuid.uuid4())
        }

        logger.info("Submitting image job to ComfyUI")

        try:
            r = requests.post(self.endpoint, json=payload, timeout=30)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"ComfyUI request failed: {e}")
            return None

        # 🔁 Wait for output file
        return self._wait_for_image(filename_prefix)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_workflow(self) -> dict:
        with open(self.workflow_path, "r") as f:
            return json.load(f)

    def _wait_for_image(
        self,
        filename_prefix: str,
        timeout: int = 300,
        poll_interval: int = 1
    ) -> Optional[Path]:

        start = time.time()

        while time.time() - start < timeout:
            for img in self.output_path.glob(f"{filename_prefix}*.png"):
                if FileUtils.file_exists_and_readable(img):
                    logger.info(f"Image generated: {img}")
                    return img
            time.sleep(poll_interval)

        logger.error("Timed out waiting for ComfyUI image")
        return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_image(self, image_path: Path) -> bool:
        return FileUtils.safe_delete_file(image_path)
