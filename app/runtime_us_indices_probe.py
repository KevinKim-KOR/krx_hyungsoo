"""POC2 3-PUSH Runtime Package PC 검증 — 미국 지수 runtime probe (2026-06-13).

지시문 §8.2 / Q1 — Nasdaq / S&P 500 / Philadelphia Semiconductor Index 3종을
Yahoo Finance chart endpoint 로 조회. 신규 dependency 0건 (urllib + json 만).

본 모듈은 source 호출만 책임지고 cache / package 빌더와 분리된다.

원칙:
- HTTP 3초 timeout 개별 / 전체 3종 합산 9초 이내.
- 실패 시 fake 값 0건 — status="failed" + errors 명시.
- 부분 성공 시 status="partial".
- HTML scrape 0건 — JSON endpoint 만 사용.
"""

from __future__ import annotations

import http.cookiejar
import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

YAHOO_HOME_URL = "https://finance.yahoo.com/"
YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
)
YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}
HTTP_TIMEOUT_SECONDS = 3

# Yahoo 는 처음 chart endpoint 호출 전 finance.yahoo.com 의 cookie 가 필요하다.
# 모듈 전역에서 단일 opener 를 재사용 (process-local). thread-safe.
_OPENER_LOCK = threading.Lock()
_OPENER: Optional[urllib.request.OpenerDirector] = None
_HOME_PRIMED = False


def _get_opener() -> urllib.request.OpenerDirector:
    """Cookie jar 가 붙은 opener 1개를 process-local 로 캐시. finance.yahoo.com
    홈을 한 번 방문해 cookie 를 받아둔다 (rate-limit 회피).
    """
    global _OPENER, _HOME_PRIMED
    with _OPENER_LOCK:
        if _OPENER is None:
            cj = http.cookiejar.CookieJar()
            _OPENER = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cj)
            )
        if not _HOME_PRIMED:
            try:
                req = urllib.request.Request(YAHOO_HOME_URL, headers=YAHOO_HEADERS)
                _OPENER.open(req, timeout=HTTP_TIMEOUT_SECONDS)
                _HOME_PRIMED = True
            except Exception as e:  # noqa: BLE001 — best-effort priming
                logger.debug("yahoo finance 홈 priming 실패: %s", e)
        return _OPENER


US_INDICES_SPEC: tuple[tuple[str, str, str], ...] = (
    ("NASDAQ", "Nasdaq Composite", "^IXIC"),
    ("SPX", "S&P 500", "^GSPC"),
    ("SOX", "Philadelphia Semiconductor Index", "^SOX"),
)


def _probe_single(symbol_display: str, name: str, yahoo_symbol: str) -> dict[str, Any]:
    """단일 지수 조회. 실패 시 status="failed" 항목 반환 (예외 흡수)."""
    encoded = urllib.request.quote(yahoo_symbol, safe="")
    url = YAHOO_CHART_URL.format(symbol=encoded)
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    opener = _get_opener()
    try:
        with opener.open(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        meta = data["chart"]["result"][0]["meta"]
        close = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose")
        if not isinstance(close, (int, float)) or not isinstance(prev, (int, float)):
            raise ValueError("regularMarketPrice / chartPreviousClose 누락")
        if prev == 0:
            raise ValueError("chartPreviousClose=0 — 등락률 계산 불가")
        change_pct = (float(close) - float(prev)) / float(prev) * 100.0
        return {
            "symbol": symbol_display,
            "name": name,
            "close": float(close),
            "change_pct": round(change_pct, 4),
            "status": "ok",
        }
    except (urllib.error.URLError, TimeoutError) as e:
        logger.warning(
            "us_indices probe 네트워크 실패: symbol=%s reason=%s", symbol_display, e
        )
        return {
            "symbol": symbol_display,
            "name": name,
            "close": None,
            "change_pct": None,
            "status": "failed",
            "error": f"network: {e}",
        }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning(
            "us_indices probe 파싱 실패: symbol=%s reason=%s", symbol_display, e
        )
        return {
            "symbol": symbol_display,
            "name": name,
            "close": None,
            "change_pct": None,
            "status": "failed",
            "error": f"parse: {e}",
        }


def probe_us_indices() -> dict[str, Any]:
    """3종 미국 지수 probe. snapshot dict 반환 (계약 §8.2 형식).

    반환 구조:
    {
      "captured_at": "<iso>",
      "indices": [{symbol, name, close, change_pct, status, error?}, ...],
      "status": "ok | partial | failed",
      "warnings": [...],
      "errors": [...],
    }
    """
    captured = datetime.now(timezone.utc).isoformat()
    indices: list[dict[str, Any]] = []
    errors: list[str] = []
    for sym, name, yh in US_INDICES_SPEC:
        item = _probe_single(sym, name, yh)
        indices.append(item)
        if item["status"] != "ok":
            errors.append(f"{sym}: {item.get('error', 'unknown')}")
    ok_count = sum(1 for it in indices if it["status"] == "ok")
    if ok_count == len(indices):
        status = "ok"
    elif ok_count == 0:
        status = "failed"
    else:
        status = "partial"
    return {
        "captured_at": captured,
        "indices": indices,
        "status": status,
        "warnings": [],
        "errors": errors,
    }


def empty_unavailable_snapshot(reason: Optional[str] = None) -> dict[str, Any]:
    """probe 미수행 시 사용 — fake 값 없음, 명시 status."""
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "indices": [],
        "status": "unavailable",
        "warnings": [],
        "errors": [reason] if reason else [],
    }
