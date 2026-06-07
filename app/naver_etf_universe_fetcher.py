"""Naver ETF Universe NAV / 시장가격 fetcher (POC2 — 2026-06-08).

지시문 §4 / §5 — Naver ETF universe endpoint 1회 호출로 전체 ETF universe 의
NAV / 시장가격 / 변동률 / 3M 수익률을 가져온다.

Endpoint:
    GET https://finance.naver.com/api/sise/etfItemList.nhn

응답 구조 (실측 기준):
    { "result": { "etfItemList": [
        { "itemcode": "069500", "itemname": "KODEX 200",
          "nav": "33,520", "nowVal": "33,535", "changeRate": "0.04",
          "threeMonthEarnRate": "5.12",
          "openVal": "...", "highVal": "...", "lowVal": "...", "quant": "..." },
        ...
    ] } }

본 모듈 정책:
- TTL 30 초 모듈-전역 단일 캐시 (`_UNIVERSE_CACHE`).
- 호출 실패 시 stale cache 가 있으면 그대로 재사용 (status=partial,
  message="stale cache reused").
- raw response 전문 저장 X — 필요 필드만 정규화한 dict 반환.
- 응답 자체에 명시적 asof 키가 없으므로 asof 결정은 호출자(service)에서 수행한다.
- 인증 / 새 라이브러리 추가 0건. urllib + socket timeout 만 사용.

본 모듈은 fetcher 만 책임지고 store / service / API 와 분리된다.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# 2026-06-08 FIX (검증자 A-1 / B-6): 괴리율 계산은 기존 helper 재사용 — 산식 중복 X.
from app.etf_nav_fetcher import compute_discount_rate_pct

NAVER_UNIVERSE_URL = "https://finance.naver.com/api/sise/etfItemList.nhn"
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/sise/etfList.nhn",
    "Accept": "application/json, text/plain, */*",
}
HTTP_TIMEOUT_SECONDS = 8
SOCKET_TIMEOUT_SECONDS = 15

TTL_SECONDS = 30

SOURCE_LABEL = "naver_etf_item_list"


@dataclass
class NaverUniverseItem:
    """단일 ETF 정규화 결과 (status=ok|unavailable)."""

    ticker: str
    name: Optional[str]
    nav: Optional[float]
    market_price: Optional[float]
    discount_rate_pct: Optional[float]
    change_rate_pct: Optional[float]
    three_month_return_pct: Optional[float]
    status: str
    message: Optional[str] = None


@dataclass
class NaverUniverseSnapshot:
    """fetch 결과 전체."""

    status: str  # ok | partial | unavailable
    fetched_at: str  # ISO UTC
    items: dict[str, NaverUniverseItem] = field(default_factory=dict)
    cache_hit: bool = False
    stale_cache_used: bool = False
    message: Optional[str] = None


# ─── 모듈-전역 캐시 ──────────────────────────────────────────────


_UNIVERSE_CACHE: dict[str, Any] = {
    "data": None,  # NaverUniverseSnapshot
    "expires_at": None,  # datetime (UTC)
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_number(value: Any) -> Optional[float]:
    """쉼표 / 공백 / 빈 문자열 / None 안전 처리."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized or normalized == "-":
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _normalize_ticker(value: Any) -> Optional[str]:
    text = str(value or "").strip().upper()
    return text or None


def _build_item(raw: dict) -> Optional[NaverUniverseItem]:
    """응답 1개를 NaverUniverseItem 으로 변환. 필수 필드 없으면 None."""
    ticker = _normalize_ticker(raw.get("itemcode"))
    if not ticker:
        return None

    name = str(raw.get("itemname") or "").strip() or None
    nav = _parse_number(raw.get("nav"))
    market_price = _parse_number(raw.get("nowVal"))
    change_rate = _parse_number(raw.get("changeRate"))
    three_month = _parse_number(raw.get("threeMonthEarnRate"))

    # 2026-06-08 FIX (검증자 A-1 / B-6): 산식 중복 제거 — 기존 helper 사용.
    # helper 는 (nav is None or nav <= 0) 또는 market_price is None 이면 None 반환.
    discount_rate_pct = compute_discount_rate_pct(nav, market_price)
    if discount_rate_pct is None:
        return NaverUniverseItem(
            ticker=ticker,
            name=name,
            nav=nav,
            market_price=market_price,
            discount_rate_pct=None,
            change_rate_pct=change_rate,
            three_month_return_pct=three_month,
            status="unavailable",
            message="nav or market_price missing",
        )

    return NaverUniverseItem(
        ticker=ticker,
        name=name,
        nav=nav,
        market_price=market_price,
        discount_rate_pct=discount_rate_pct,
        change_rate_pct=change_rate,
        three_month_return_pct=three_month,
        status="ok",
    )


def _decode_body(body: bytes, content_type: Optional[str]) -> str:
    """Naver universe endpoint 는 EUC-KR / cp949 응답을 줄 수 있다.

    Content-Type 의 charset 우선, 없거나 실패하면 utf-8 → cp949 순으로 시도.
    """
    charset = None
    if content_type:
        for part in content_type.split(";"):
            part = part.strip().lower()
            if part.startswith("charset="):
                charset = part.split("=", 1)[1].strip().strip('"')
                break
    if charset:
        try:
            return body.decode(charset, errors="strict")
        except (LookupError, UnicodeDecodeError):
            pass
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            return body.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _http_get_json(url: str) -> tuple[Optional[int], Optional[dict], Optional[str]]:
    """단순 GET → (http_status, parsed_json, error_text)."""
    req = urllib.request.Request(url, headers=NAVER_HEADERS)
    # socket-level timeout 도 명시 (urllib 내부 socket 에 적용).
    prev_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(SOCKET_TIMEOUT_SECONDS)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type")
            text = _decode_body(body, content_type)
            try:
                payload = json.loads(text)
            except Exception as e:  # noqa: BLE001
                return (resp.status, None, f"json_decode_failed: {e}")
            if not isinstance(payload, dict):
                return (resp.status, None, "payload_not_dict")
            return (resp.status, payload, None)
    except urllib.error.HTTPError as e:
        return (e.code, None, f"HTTPError {e.code}: {e}")
    except urllib.error.URLError as e:
        return (None, None, f"URLError: {e}")
    except Exception as e:  # noqa: BLE001
        return (None, None, f"{type(e).__name__}: {e}")
    finally:
        socket.setdefaulttimeout(prev_timeout)


def _build_snapshot_from_payload(
    payload: dict, fetched_at: datetime
) -> NaverUniverseSnapshot:
    items: dict[str, NaverUniverseItem] = {}
    raw_items = (payload.get("result") or {}).get("etfItemList") or []
    if not isinstance(raw_items, list):
        return NaverUniverseSnapshot(
            status="unavailable",
            fetched_at=_utc_iso(fetched_at),
            message="result.etfItemList not a list",
        )
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        built = _build_item(raw)
        if built is not None:
            items[built.ticker] = built
    if not items:
        return NaverUniverseSnapshot(
            status="unavailable",
            fetched_at=_utc_iso(fetched_at),
            message="empty etfItemList",
        )
    return NaverUniverseSnapshot(
        status="ok", fetched_at=_utc_iso(fetched_at), items=items
    )


def _clone_as_stale(
    snap: NaverUniverseSnapshot, fetched_at: datetime
) -> NaverUniverseSnapshot:
    return NaverUniverseSnapshot(
        status="partial",
        fetched_at=_utc_iso(fetched_at),
        items=dict(snap.items),
        cache_hit=False,
        stale_cache_used=True,
        message="stale cache reused",
    )


def fetch_universe_snapshot(
    *,
    force: bool = False,
    http_getter: Optional[Any] = None,
) -> NaverUniverseSnapshot:
    """Naver ETF universe 1회 호출 (TTL 30s + stale 재사용).

    Args:
        force: True 이면 TTL 무시하고 외부 호출.
        http_getter: 테스트용 주입. (url) -> (status, payload_dict, err).

    Returns:
        NaverUniverseSnapshot — status ∈ {ok, partial, unavailable}.
    """
    now = _now_utc()
    cached = _UNIVERSE_CACHE.get("data")
    expires_at = _UNIVERSE_CACHE.get("expires_at")

    if (
        not force
        and isinstance(cached, NaverUniverseSnapshot)
        and isinstance(expires_at, datetime)
        and now < expires_at
    ):
        return NaverUniverseSnapshot(
            status=cached.status,
            fetched_at=cached.fetched_at,
            items=dict(cached.items),
            cache_hit=True,
            stale_cache_used=cached.stale_cache_used,
            message=cached.message,
        )

    getter = http_getter or _http_get_json
    status_code, payload, err = getter(NAVER_UNIVERSE_URL)
    if payload is None:
        if isinstance(cached, NaverUniverseSnapshot) and cached.items:
            return _clone_as_stale(cached, now)
        return NaverUniverseSnapshot(
            status="unavailable",
            fetched_at=_utc_iso(now),
            message=f"call_failed: {err or 'unknown'} (http={status_code})",
        )

    snapshot = _build_snapshot_from_payload(payload, now)
    if snapshot.status != "ok":
        # 응답은 받았지만 비정상 — stale 있으면 stale 우선.
        if isinstance(cached, NaverUniverseSnapshot) and cached.items:
            return _clone_as_stale(cached, now)
        return snapshot

    _UNIVERSE_CACHE["data"] = snapshot
    _UNIVERSE_CACHE["expires_at"] = now + timedelta(seconds=TTL_SECONDS)
    return snapshot


def reset_cache_for_tests() -> None:
    """테스트 전용 — 모듈 캐시 초기화."""
    _UNIVERSE_CACHE["data"] = None
    _UNIVERSE_CACHE["expires_at"] = None
