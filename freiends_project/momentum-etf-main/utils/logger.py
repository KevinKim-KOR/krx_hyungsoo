"""프로젝트 전역에서 사용 가능한 로거 설정 모듈."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

load_dotenv()

APP_VERSION = "2026-03-30-13"
APP_LABEL = os.environ.get("APP_TYPE", f"APP-{APP_VERSION}")

LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO").upper()
DEBUG_ENABLED = LOG_LEVEL == "DEBUG"


_LOGGER: logging.Logger | None = None


def get_app_logger() -> logging.Logger:
    """기본 애플리케이션 로거를 반환한다."""

    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("momentum_etf")
    if not logger.handlers:
        # 포매터 설정
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 파일 핸들러 (logs/YYYY-MM-DD.log)
        project_root = Path(__file__).resolve().parents[1]
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        if ZoneInfo is not None:
            try:
                now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
            except Exception:
                now_kst = datetime.now()
        else:
            now_kst = datetime.now()

        log_path = log_dir / f"{now_kst.strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.setLevel(LOG_LEVEL if LOG_LEVEL in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO")
        logger.propagate = False

    _LOGGER = logger
    return logger


def is_debug_enabled() -> bool:
    """DEBUG 로그 출력 여부를 반환한다."""

    return DEBUG_ENABLED


__all__ = ["get_app_logger", "is_debug_enabled"]
