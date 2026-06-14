"""POC2 3-PUSH Runtime Package PC 검증 — runtime probe cache (2026-06-13).

지시문 Q5 — `/runs/generate` 호출 시 cache read → miss/TTL 만료 시 1회 probe.
TTL 30분. 별도 scheduler / refresh endpoint 없음.

cache 위치: state/runtime/three_push_runtime_probe_latest.json (gitignored).
**두 snapshot 모두 failed/unavailable** 인 경우만 cache 저장을 건너뛴다 — 다음
호출이 즉시 재시도. 한 쪽이라도 ok/partial 이면 cache 저장 (다음 호출이 그대로
사용). 이 정책은 일시적 네트워크 실패 후 즉시 재호출이 가능하도록 한다.

본 모듈은 cache I/O 만 책임지고 probe / package 빌더와 분리된다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.runtime_kr_quote_probe import probe_kr_quotes
from app.runtime_us_indices_probe import probe_us_indices

logger = logging.getLogger(__name__)

CACHE_DIR = Path("state/runtime")
CACHE_FILE = CACHE_DIR / "three_push_runtime_probe_latest.json"

TTL_MINUTES = 30


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(captured_at: Optional[str]) -> bool:
    if not isinstance(captured_at, str) or not captured_at.strip():
        return False
    try:
        ts = datetime.fromisoformat(captured_at)
    except ValueError:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return _now_utc() - ts < timedelta(minutes=TTL_MINUTES)


def _read_cache() -> Optional[dict[str, Any]]:
    if not CACHE_FILE.exists():
        return None
    try:
        text = CACHE_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("runtime probe cache 손상 — 무시하고 재조회: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_cache(snapshot: dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        logger.warning("runtime probe cache 저장 실패: %s", e)


def _cache_is_fresh(cache: dict[str, Any]) -> bool:
    """cache 의 두 snapshot 모두 fresh 한지 확인."""
    kr = cache.get("kr_realtime_price_snapshot")
    us = cache.get("overnight_us_market_snapshot")
    if not isinstance(kr, dict) or not isinstance(us, dict):
        return False
    return _is_fresh(kr.get("captured_at")) and _is_fresh(us.get("captured_at"))


def get_runtime_probe_snapshot(
    *,
    kr_tickers: list[str],
    force_refresh: bool = False,
) -> dict[str, Any]:
    """runtime probe snapshot 반환. cache hit 시 cache 사용, miss 시 새 probe.

    반환 구조:
    {
      "captured_at": "<iso>",
      "kr_realtime_price_snapshot": {...},
      "overnight_us_market_snapshot": {...},
      "cache_status": "hit | miss | bypassed",
    }

    실패한 항목도 명시 status 로 반영. fake 값 0건.
    """
    if not force_refresh:
        cache = _read_cache()
        if isinstance(cache, dict) and _cache_is_fresh(cache):
            snap = {
                "captured_at": cache.get("captured_at"),
                "kr_realtime_price_snapshot": cache.get("kr_realtime_price_snapshot"),
                "overnight_us_market_snapshot": cache.get(
                    "overnight_us_market_snapshot"
                ),
                "cache_status": "hit",
            }
            return snap

    kr_snap = probe_kr_quotes(kr_tickers)
    us_snap = probe_us_indices()
    snapshot = {
        "captured_at": _now_utc().isoformat(),
        "kr_realtime_price_snapshot": kr_snap,
        "overnight_us_market_snapshot": us_snap,
        "cache_status": "bypassed" if force_refresh else "miss",
    }
    if _both_failed(kr_snap, us_snap):
        logger.info(
            "runtime probe 두 snapshot 모두 실패 — cache 저장 건너뜀 (다음 호출이 재시도)"
        )
    else:
        _write_cache(snapshot)
    return snapshot


def _both_failed(kr_snap: dict[str, Any], us_snap: dict[str, Any]) -> bool:
    bad = {"failed", "unavailable"}
    kr_bad = isinstance(kr_snap, dict) and kr_snap.get("status") in bad
    us_bad = isinstance(us_snap, dict) and us_snap.get("status") in bad
    return kr_bad and us_bad
