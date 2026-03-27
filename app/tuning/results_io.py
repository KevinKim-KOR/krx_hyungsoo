"""Atomic file write utilities for tuning results."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("app.run_tune")

KST = timezone(timedelta(hours=9))

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULT_LATEST = PROJECT_ROOT / "reports" / "tuning" / "tuning_results.json"
RESULT_SNAPSHOTS = PROJECT_ROOT / "reports" / "tuning" / "snapshots"


def atomic_write_result(data: Dict[str, Any]) -> None:
    """Atomic write: tmp → rename → snapshot copy"""
    RESULT_LATEST.parent.mkdir(parents=True, exist_ok=True)
    RESULT_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

    content = json.dumps(data, indent=2, ensure_ascii=False)

    tmp_fd = tempfile.NamedTemporaryFile(
        mode="w",
        dir=RESULT_LATEST.parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp_fd.write(content)
        tmp_fd.close()
        tmp_path = Path(tmp_fd.name)
        if RESULT_LATEST.exists():
            RESULT_LATEST.unlink()
        tmp_path.rename(RESULT_LATEST)
        logger.info(f"[WRITE] latest → {RESULT_LATEST}")
    except Exception:
        Path(tmp_fd.name).unlink(missing_ok=True)
        raise

    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    snap_path = RESULT_SNAPSHOTS / f"tune_result_{ts}.json"
    shutil.copy2(RESULT_LATEST, snap_path)
    logger.info(f"[WRITE] snapshot → {snap_path}")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd = tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
        newline="",
    )
    try:
        tmp_fd.write(content)
        tmp_fd.close()
        tmp_path = Path(tmp_fd.name)
        if path.exists():
            path.unlink()
        tmp_path.rename(path)
        logger.info(f"[WRITE] file → {path}")
    except Exception:
        Path(tmp_fd.name).unlink(missing_ok=True)
        raise
