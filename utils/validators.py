"""
Input validators.
"""
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class Validators:
    """Input and data validators."""
    
    @staticmethod
    def validate_video_idea(idea: Dict[str, Any]) -> bool:
        """Validate video idea structure."""
        required_fields = ["positive_prompt", "negative_prompt", "narration_script", "caption"]
        for field in required_fields:
            if field not in idea or not str(idea[field]).strip():
                logger.warning(f"Invalid idea - missing or empty field: {field}")
                return False
        return True
    
    @staticmethod
    def validate_groq_batch(batch: List[Dict[str, Any]]) -> bool:
        """Validate Groq batch response."""
        if not isinstance(batch, list) or len(batch) == 0:
            logger.warning("Invalid batch: not a list or empty")
            return False
        for idea in batch:
            if not Validators.validate_video_idea(idea):
                return False
        return True
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove invalid characters from filename."""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', '_', filename)
        return filename[:255]  # Max filename length
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format."""
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    @staticmethod
    def validate_video_dimensions(width: int, height: int) -> bool:
        """Validate video dimensions."""
        if width < 100 or width > 4096:
            logger.warning(f"Invalid width: {width}")
            return False
        if height < 100 or height > 4096:
            logger.warning(f"Invalid height: {height}")
            return False
        return True
