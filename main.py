"""
YouTube Automation System - Main Entry Point
"""
import sys
import logging
import time
import signal
from pathlib import Path
from datetime import datetime, UTC

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from logging_config import setup_logging
from orchestrator import VideoOrchestrator
from uploader import UploadScheduler
from database import DatabaseManager

logger = logging.getLogger(__name__)

running = True


# --------------------------------------------------
# Signal handling
# --------------------------------------------------

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received. Stopping gracefully.")
    running = False


# --------------------------------------------------
# Initialization
# --------------------------------------------------

def initialize_system():
    logger.info("Initializing YouTube Automation System")

    if not Config.validate():
        raise RuntimeError("Configuration validation failed")

    # 🔑 SINGLE shared database instance
    db = DatabaseManager()

    orchestrator = VideoOrchestrator()
    orchestrator.db = db  # ensure shared DB

    upload_scheduler = UploadScheduler(
        db=db,
        orchestrator=orchestrator
    )

    health = orchestrator.health_check()
    for service, ok in health.items():
        logger.info(f"{service}: {'OK' if ok else 'UNAVAILABLE'}")

    return orchestrator, upload_scheduler


# --------------------------------------------------
# Status output
# --------------------------------------------------

def print_status(orchestrator, upload_scheduler):
    status = orchestrator.get_system_status()
    upload_status = upload_scheduler.get_upload_status()

    logger.info("=" * 60)
    logger.info("MODE: PRODUCTION")
    logger.info(f"TIME: {datetime.now(UTC).isoformat()}")

    logger.info(f"Ideas available     : {status['ideas_available']}")
    logger.info(f"Videos ready       : {status['ready_videos']}")

    logger.info(f"Uploads pending    : {upload_status['total_pending']}")
    logger.info(f"Uploads uploaded   : {upload_status['total_uploaded']}")
    logger.info(f"Uploads failed     : {upload_status['total_failed']}")

    next_upload = upload_status.get("next_upload")
    if next_upload:
        logger.info(f"Next upload at     : {next_upload}")
    else:
        logger.info("Next upload at     : none")

    logger.info("=" * 60)


# --------------------------------------------------
# Processing steps
# --------------------------------------------------

def process_generation(orchestrator, upload_scheduler):
    status = orchestrator.get_system_status()

    # 🧠 WAIT if no ideas but videos still pending upload
    if status["ideas_available"] == 0 and status["ready_videos"] > 0:
        logger.info("Generation paused — waiting for uploads to complete")
        return

    job = orchestrator.process_next_video()
    if not job:
        logger.info("No video generated this cycle")
        return

    logger.info(f"Video generated: {job.video_path}")

    upload_job = upload_scheduler.schedule_upload(job)
    if upload_job:
        logger.info(f"Upload scheduled: {upload_job.upload_id}")


def process_uploads(upload_scheduler):
    # 🛑 HARD BLOCK uploads after quota exceeded
    if upload_scheduler.quota_exceeded:
        logger.critical("Daily YouTube upload limit reached — uploads halted")
        return

    pending = upload_scheduler.get_pending_uploads()
    if not pending:
        return

    logger.info(f"Processing {len(pending)} pending uploads")

    for upload in pending:
        upload_scheduler.execute_upload(upload)


# --------------------------------------------------
# Main loop
# --------------------------------------------------

def run():
    orchestrator, upload_scheduler = initialize_system()

    interval = 60
    logger.info("Running in PRODUCTION mode")

    while running:
        try:
            process_generation(orchestrator, upload_scheduler)
            process_uploads(upload_scheduler)
            print_status(orchestrator, upload_scheduler)

            # 🛑 FINAL STOP CONDITION
            status = orchestrator.get_system_status()
            if (
                upload_scheduler.quota_exceeded
                and status["ideas_available"] == 0
            ):
                logger.critical(
                    "🛑 DAILY LIMIT REACHED & NO IDEAS LEFT — SYSTEM STOPPED"
                )
                break

            logger.info(f"Sleeping for {interval} seconds")
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except Exception:
            logger.error("Unexpected error in main loop", exc_info=True)
            time.sleep(30)

    logger.info("System stopped")


# --------------------------------------------------
# Entry point
# --------------------------------------------------

def main():
    setup_logging()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    run()


if __name__ == "__main__":
    sys.exit(main())
