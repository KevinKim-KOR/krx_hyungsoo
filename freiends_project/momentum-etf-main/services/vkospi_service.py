"""VKOSPI(코스피 200 변동성지수) 실시간 데이터 조회 유틸리티.

인베스팅닷컴(kr.investing.com)에서 실시간 수치를 가져옵니다.
백엔드 캐싱(5분)을 적용하여 과도한 요청을 방지합니다.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import requests

from utils.logger import get_app_logger

logger = get_app_logger()

# 인베스팅닷컴 VKOSPI 페이지 URL
_INVESTING_VKOSPI_URL = "https://kr.investing.com/indices/kospi-volatility"
_INVESTING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 메모리 캐시 (5분)
_CACHE_TTL_SECONDS = 300
_cache: dict[str, Any] = {
    "data": None,
    "expires_at": 0.0,
}


def get_vkospi() -> dict[str, Any] | None:
    """VKOSPI 현재 지수와 등락률을 반환합니다.

    Returns:
        {"price": float, "change_pct": float, "updated_at": str} 또는 None
    """
    now = time.time()

    # 캐시가 유효하면 즉시 반환
    if _cache["data"] is not None and now < _cache["expires_at"]:
        return _cache["data"]

    data = _fetch_from_investing()
    if data:
        _cache["data"] = data
        _cache["expires_at"] = now + _CACHE_TTL_SECONDS

    return data


def _fetch_from_investing() -> dict[str, Any] | None:
    """인베스팅닷컴에서 VKOSPI 현재가/등락률을 파싱합니다."""
    try:
        response = requests.get(
            _INVESTING_VKOSPI_URL,
            headers=_INVESTING_HEADERS,
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()
        html = response.text

        # 현재가: data-test="instrument-price-last">61.48
        price_match = re.search(
            r'instrument-price-last"[^>]*>([0-9.,]+)', html
        )
        # 등락률: data-test="instrument-price-change-percent">(+0.08%)
        pct_match = re.search(
            r'instrument-price-change-percent"[^>]*>\(?([+-]?[0-9.,]+)%?\)?',
            html,
        )

        if not price_match:
            logger.error("인베스팅닷컴 VKOSPI 현재가 파싱 실패")
            return None

        price = float(price_match.group(1).replace(",", ""))
        change_pct = 0.0
        if pct_match:
            change_pct = float(pct_match.group(1).replace(",", ""))

        return {
            "code": "VKOSPI",
            "name": "VKOSPI",
            "price": price,
            "change_pct": change_pct,
            "updated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"인베스팅닷컴 VKOSPI 조회 오류: {e}")
        return None
