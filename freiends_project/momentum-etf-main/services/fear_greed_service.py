"""CNN Fear & Greed Index 서비스.

CNN의 실시간 공포탐욕지수 데이터를 가져오고 파싱합니다.
백엔드 캐싱(5분)을 적용하여 외부 사이트 부하를 줄입니다.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import requests

from utils.logger import get_app_logger

logger = get_app_logger()

_CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://edition.cnn.com",
    "Referer": "https://edition.cnn.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# 메모리 캐시 (5분)
_CACHE_TTL = 300
_cache: dict[str, Any] = {
    "data": None,
    "expires_at": 0.0,
}

def get_fear_greed_summary() -> dict[str, Any] | None:
    """공포탐욕지수 요약을 반환합니다 (캐시 적용)."""
    now = time.time()

    if _cache["data"] and now < _cache["expires_at"]:
        return _cache["data"]

    data = _fetch_from_cnn()
    if data:
        _cache["data"] = data
        _cache["expires_at"] = now + _CACHE_TTL

    return data

def _fetch_from_cnn() -> dict[str, Any] | None:
    """CNN에서 데이터를 직접 가져와 파싱합니다."""
    try:
        response = requests.get(_CNN_URL, headers=_HEADERS, timeout=10)
        response.raise_for_status()
        payload = response.json()

        # 기본 필드 추출 (fear_and_greed 노드)
        fng = payload.get("fear_and_greed", {})
        score = fng.get("score")
        label = fng.get("rating") or fng.get("label")
        timestamp = fng.get("timestamp")

        # 전일 종가 지수 (fear_and_greed_historical 내의 previous_close)
        historical = payload.get("fear_and_greed_historical", {})
        previous_close = historical.get("previous_close")

        if score is None or not label:
            logger.error("CNN 데이터 파싱 실패: 필수 필드 누락")
            return None

        return {
            "score": round(float(score), 1),
            "label": label.strip(),
            "previous_close_score": round(float(previous_close), 1) if previous_close is not None else None,
            "updated_at": _to_iso_timestamp(timestamp),
        }
    except Exception as e:
        logger.error(f"CNN Fear & Greed 조회 오류: {e}")
        return None

def _to_iso_timestamp(ts: Any) -> str | None:
    """타임스탬프를 ISO 문자열로 변환합니다."""
    if not ts:
        return None
    try:
        # 초 단위인 경우 밀리초로 변환
        val = float(ts)
        if val < 10_000_000_000:
            val = val
        else:
            val = val / 1000
        return datetime.fromtimestamp(val).isoformat()
    except:
        return str(ts)
