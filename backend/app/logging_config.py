"""Centralized logging via Loguru. No bare print() anywhere in the app."""

import sys
from pathlib import Path

from loguru import logger

from app.config import BASE_DIR, settings


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    log_file = Path(settings.output_dir).parent / "logs" / "dataguard.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )
    logger.info(f"Loguru initialized (level={level})")
