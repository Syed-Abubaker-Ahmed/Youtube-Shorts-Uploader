"""
Groq LLM API service for generating 20 Would You Rather videos
using llama-3.3-70b-versatile.
STRICT JSON. ABSOLUTELY NO HUMANS.
"""
import logging
import json
import uuid
from typing import List
from datetime import datetime, UTC
import requests

from config import Config
from models import VideoIdea, VideoType

logger = logging.getLogger(__name__)


class GroqService:
    BASE_URL = "https://api.groq.com/openai/v1"
    MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or Config.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def generate_videos(self) -> List[VideoIdea]:
        """
        Generates EXACTLY 20 Would You Rather videos
        sharing ONE series_id.
        """
        series_id = f"wyr_{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"

        prompt = self._build_prompt(
            video_count=20,
            scenarios_per_video=5
        )

        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You generate automated short-form video content. "
                                "Respond with STRICTLY valid JSON only. "
                                "No markdown. No explanations."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.6,
                    "max_tokens": 9000,
                },
                timeout=120,
            )

            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]

            if not raw or not raw.strip():
                logger.error("Groq returned empty content")
                return []

            # 🔧 STRIP MARKDOWN CODE FENCES IF PRESENT
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```", 2)[1].strip()

            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error("Groq returned invalid JSON")
                logger.error("RAW GROQ OUTPUT ↓↓↓")
                logger.error(raw)
                return []

            # --------------------------------------------------
            # Series-level metadata (for compilation)
            # --------------------------------------------------

            series_title = parsed["series"]["full_video_title"].strip()
            series_caption = parsed["series"]["full_video_caption"].strip()

            videos: List[VideoIdea] = []

            for video in parsed["videos"]:
                idea = VideoIdea(
                    id=str(uuid.uuid4()),
                    video_type=VideoType.WOULD_YOU_RATHER,
                    series_id=series_id,
                    title=video["title"].strip(),
                    caption=video["caption"].strip(),
                    positive_prompt=json.dumps(video["positive_prompts"]),
                    negative_prompt=json.dumps(video["negative_prompts"]),
                    narration_script=video["narration_script"].strip(),
                    created_at=datetime.now(UTC),
                )
                videos.append(idea)

            logger.info(
                f"Generated {len(videos)} videos for series {series_id}"
            )

            # Persist series metadata for compilation upload
            self._persist_series_metadata(
                series_id,
                series_title,
                series_caption
            )

            return videos

        except Exception:
            logger.error("Groq generation failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Series metadata persistence hook
    # ------------------------------------------------------------------

    def _persist_series_metadata(
        self,
        series_id: str,
        title: str,
        caption: str
    ) -> None:
        try:
            from database import DatabaseManager
            db = DatabaseManager()
            db.save_series_metadata(
                series_id=series_id,
                title=title,
                caption=caption
            )
        except Exception:
            logger.warning(
                "Failed to persist series metadata",
                exc_info=True
            )

    # ------------------------------------------------------------------
    # Prompt Builder
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        video_count: int,
        scenarios_per_video: int
    ) -> str:

        return f"""
You are an AI system that generates AUTOMATED VIDEO CONTENT.

ABSOLUTE RULES:
- Output STRICTLY valid JSON
- No markdown
- No explanations
- Generate EXACTLY {video_count} IDEAS
- Generate EXACTLY {video_count} VIDEOS
- NEVER include humans in image prompts

PHASE 1 — IDEAS:
Generate EXACTLY {video_count} unique video ideas.
Each idea = 5–8 word theme.

PHASE 2 — VIDEOS:
For EACH idea, generate ONE video with EXACTLY {scenarios_per_video} scenarios.

EACH SCENARIO:
- Format ONLY as a question:
  "Would you rather A or B?"
- No commentary
- No jokes
- No filler

NARRATION RULES:
- Narration script must ONLY contain the questions
- One question per line
- No extra text

IMAGE PROMPT RULES:
- Stable Diffusion 1.5
- Vertical 9:16
- Cinematic lighting
- Ultra-detailed
- Objects, environments, fantasy, abstract ONLY
- NO HUMANS
- NO PEOPLE
- NO FACES
- NO BODY PARTS
- NO HUMANOIDS
- NO SILHOUETTES
- NO TEXT IN IMAGE

PER VIDEO METADATA:
- title: 3–6 words
- caption: 4–8 words

GLOBAL METADATA:
- One title for the combined 10-minute video
- One caption for the combined 10-minute video

STRICT JSON OUTPUT FORMAT:
{{
  "series": {{
    "full_video_title": "",
    "full_video_caption": ""
  }},
  "ideas": [],
  "videos": [
    {{
      "idea": "",
      "title": "",
      "caption": "",
      "positive_prompts": [],
      "negative_prompts": [],
      "narration_script": ""
    }}
  ]
}}
"""
