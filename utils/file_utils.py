"""
File and path utilities.
"""
import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FileUtils:
    """File operation utilities."""
    
    @staticmethod
    def ensure_dir_exists(path: Path) -> None:
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ensured: {path}")
    
    @staticmethod
    def safe_delete_file(path: Path) -> bool:
        """Safely delete a file with error handling."""
        try:
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {path}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return False
        return True
    
    @staticmethod
    def safe_delete_files(paths: List[Path]) -> bool:
        """Safely delete multiple files."""
        all_deleted = True
        for path in paths:
            if not FileUtils.safe_delete_file(path):
                all_deleted = False
        return all_deleted
    
    @staticmethod
    def copy_file(src: Path, dst: Path) -> bool:
        """Safely copy a file."""
        try:
            FileUtils.ensure_dir_exists(dst.parent)
            shutil.copy2(src, dst)
            logger.info(f"Copied {src} to {dst}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy {src} to {dst}: {e}")
            return False
    
    @staticmethod
    def get_files_in_directory(
        directory: Path,
        extension: Optional[str] = None
    ) -> List[Path]:
        """Get all files in directory, optionally filtered by extension."""
        try:
            if extension:
                files = list(directory.glob(f"*{extension}"))
            else:
                files = list(directory.glob("*"))
            files = [f for f in files if f.is_file()]
            return sorted(files)
        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []
    
    @staticmethod
    def get_file_size(path: Path) -> int:
        """Get file size in bytes."""
        try:
            return path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to get size of {path}: {e}")
            return 0
    
    @staticmethod
    def file_exists_and_readable(path: Path) -> bool:
        """Check if file exists and is readable."""
        return path.exists() and path.is_file() and os.access(path, os.R_OK)
    
    @staticmethod
    def wait_for_file(
        path: Path,
        timeout: int = 60,
        poll_interval: int = 1
    ) -> bool:
        """Wait for a file to appear."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if path.exists() and path.is_file():
                logger.info(f"File appeared: {path}")
                return True
            time.sleep(poll_interval)
        logger.warning(f"Timeout waiting for file: {path}")
        return False
