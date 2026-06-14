"""POC2 3-PUSH Runtime Package PC 검증 — 국내 시세 runtime probe (2026-06-13).

지시문 §8.1 / Q2 — Naver polling realtime quote endpoint 로 단일 종목/ETF
시세를 조회. 기존 `app/naver_etf_universe_fetcher.py` 와 동일 dependency
범위 (urllib + json). 신규 dependency 0건.

본 모듈은 source 호출만 책임지고 cache / package 빌더와 분리된다.

원칙:
- HTTP 3초 timeout 개별.
- 실패 시 fake 값 0건 — item.status="failed".
- 부분 성공 시 snapshot.status="partial".
- 호출자가 ticker 목록을 주입 (holdings / benchmark / spike 후보).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

NAVER_POLLING_URL = (
    "https://polling.finance.naver.com/api/realtime/domestic/stock/{ticker}"
)
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
    "Accept": "application/json, text/plain, */*",
}
HTTP_TIMEOUT_SECONDS = 3
SOURCE_LABEL = "naver"


def _parse_int(value: Any) -> Optional[int]:
    """Naver 응답의 쉼표 포함 문자열 (e.g. "129,270") 을 int 로."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    return None


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _probe_single(ticker: str) -> dict[str, Any]:
    """단일 ticker quote 조회. 예외 흡수 후 status 명시 dict 반환."""
    url = NAVER_POLLING_URL.format(ticker=urllib.request.quote(ticker, safe=""))
    req = urllib.request.Request(url, headers=NAVER_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        items = data.get("datas")
        if not isinstance(items, list) or not items:
            raise ValueError("datas 비어있음")
        d = items[0]
        price = _parse_int(d.get("closePriceRaw") or d.get("closePrice"))
        change_pct = _parse_float(d.get("fluctuationsRatio"))
        volume = _parse_int(d.get("accumulatedTradingVolume"))
        name = d.get("stockName")
        if price is None or change_pct is None:
            raise ValueError("price / change_pct 누락")
        return {
            "ticker": ticker,
            "name": name if isinstance(name, str) else None,
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "data_status": "ok",
        }
    except (urllib.error.URLError, TimeoutError) as e:
        logger.warning("kr quote probe 네트워크 실패: ticker=%s reason=%s", ticker, e)
        return {
            "ticker": ticker,
            "name": None,
            "price": None,
            "change_pct": None,
            "volume": None,
            "data_status": "failed",
            "error": f"network: {e}",
        }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("kr quote probe 파싱 실패: ticker=%s reason=%s", ticker, e)
        return {
            "ticker": ticker,
            "name": None,
            "price": None,
            "change_pct": None,
            "volume": None,
            "data_status": "failed",
            "error": f"parse: {e}",
        }


def probe_kr_quotes(tickers: Iterable[str]) -> dict[str, Any]:
    """주어진 ticker 리스트의 실시간 시세 조회. snapshot dict 반환.

    반환 구조 (계약 §8.1 형식):
    {
      "captured_at": "<iso>",
      "source": "naver",
      "items": [...],
      "status": "ok | partial | failed",
      "warnings": [...],
      "errors": [...],
    }
    """
    captured = datetime.now(timezone.utc).isoformat()
    cleaned = [t for t in tickers if isinstance(t, str) and t.strip()]
    cleaned = list(dict.fromkeys(cleaned))  # 순서 유지 dedup.
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for t in cleaned:
        it = _probe_single(t)
        items.append(it)
        if it["data_status"] != "ok":
            errors.append(f"{t}: {it.get('error', 'unknown')}")
    if not items:
        return {
            "captured_at": captured,
            "source": SOURCE_LABEL,
            "items": [],
            "status": "unavailable",
            "warnings": ["ticker 목록 비어있음"],
            "errors": [],
        }
    ok_count = sum(1 for it in items if it["data_status"] == "ok")
    if ok_count == len(items):
        status = "ok"
    elif ok_count == 0:
        status = "failed"
    else:
        status = "partial"
    return {
        "captured_at": captured,
        "source": SOURCE_LABEL,
        "items": items,
        "status": status,
        "warnings": [],
        "errors": errors,
    }


def empty_unavailable_snapshot(reason: Optional[str] = None) -> dict[str, Any]:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_LABEL,
        "items": [],
        "status": "unavailable",
        "warnings": [],
        "errors": [reason] if reason else [],
    }
