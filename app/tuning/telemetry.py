# -*- coding: utf-8 -*-
"""
app/tuning/telemetry.py — P167-R 구조화 이벤트 로그 (JSONL)

각 튜닝 실행에 대해 이벤트를 JSONL 파일에 기록한다.
경로: reports/tune/telemetry/tune_{timestamp}.jsonl

레거시 참조: _archive/legacy_20260102/extensions/tuning/telemetry.py
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

TELEMETRY_DIR = Path("reports/tune/telemetry")


class TuneLogger:
    """JSONL 텔레메트리 로거"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        self.filepath = TELEMETRY_DIR / f"tune_{ts}.jsonl"
        self._events: list = []

    def emit(
        self,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """이벤트를 JSONL 파일에 추가"""
        entry = {
            "ts": datetime.now(KST).isoformat(),
            "run_id": self.run_id,
            "event": event,
            "payload": payload or {},
        }
        self._events.append(entry)
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[TELEMETRY] Write failed: {e}")

    def emit_tune_start(self, config: Dict[str, Any]) -> None:
        self.emit("TUNE_START", config)

    def emit_trial_end(
        self,
        trial_number: int,
        params: Dict[str, Any],
        score: float,
        pruned: bool = False,
        prune_reason: str = "",
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.emit("TRIAL_END", {
            "trial": trial_number,
            "params": params,
            "score": round(score, 6),
            "pruned": pruned,
            "prune_reason": prune_reason,
            "metrics": metrics or {},
        })

    def emit_tune_end(self, summary: Dict[str, Any]) -> None:
        self.emit("TUNE_END", summary)

    @property
    def event_count(self) -> int:
        return len(self._events)
