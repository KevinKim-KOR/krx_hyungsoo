"""POC6-29 보완 — 빠른 시세(네이버 · 코스피 · 코스닥 지수 · KODEX 200)(PLAN §9-2 ⓪ · 보완 판정 Q-R1 · 확인 1).

- 받는 때: [최신 자료 갱신] 묶음 작업(`POST /refresh/all`)의 맨 앞 단계에서만(`refresh_quick_quotes`). 6시간 대기와
  무관하다. 화면 진입 · [요약 다시 읽기]는 저장값만 읽는다(`GET /market/quick-quotes` — 외부 조회 없음).
- 원천: 지수 = `m.stock.naver.com/api/index/{KOSPI|KOSDAQ}/basic`(판정 Q-R1 로 새로 쓰는 경로) · KODEX 200 =
  `market_naver` 와 같은 종목 경로(`/api/stock/069500/basic`). HTTP 규약(httpx · 5초 · 머리글)은
  `market_naver` 그대로.
- 저장: `state/market_cache/quick_quotes_latest.json` 한 파일(임시 파일 → 교체). 항목마다 마지막 성공(`last_success`)과
  마지막 시도(`last_attempt`)를 둔다. 실패한 항목은 이전 성공 값을 그대로 둔다(성공 이력이 없으면 null = '시세 미확인').
- 시도 상태(확인 1): 이전 성공이 있고 거래일 · 값 · 등락 · 등락률 · 장 상태가 모두 같으면 `unchanged` — 원천 표기 시각만
  다른 경우다(네이버 지수는 마감 뒤에도 시각이 바뀐다 · 실측 코스피 15:36 → 15:58 값 같음). 이때 마지막 성공은 그대로
  두어 화면이 '원천 시각 그대로(새 시세 없음)'를 보인다(PLAN §9-2 표). 그 밖의 성공 = `updated`(첫 성공 · 새 거래일 ·
  장 상태 변화 · 값 변화).
- 시장 국면 · 순위 · 판단 근거에는 쓰지 않는다(위쪽 세 칸 전용 · 판정 §2-3).
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from fastapi import APIRouter

from app import market_naver
from app.market_cache import coerce_day_return

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quick-quotes"])

KST = timezone(timedelta(hours=9))
STORE_FILE = Path("state/market_cache/quick_quotes_latest.json")
NAVER_INDEX_URL = "https://m.stock.naver.com/api/index/{code}/basic"

Fetcher = Callable[[str], object]  # 주소 → 응답 JSON(해석한 값) · 실패는 예외
Clock = Callable[[], datetime]

REASON_TIMEOUT = "timeout"
REASON_HTTP = "http_error"
REASON_BAD_VALUE = "bad_value"
REASON_MISSING_TIME = "missing_time"
REASON_STORE = "store_error"  # 받았지만 저장하지 못함(그 항목은 저장되지 않았다)

ERROR_TEXT = "빠른 시세를 받는 중 오류가 났습니다."
ALL_FAILED_TEXT = (
    "빠른 시세를 하나도 받지 못했습니다. 마지막으로 받은 값을 그대로 둡니다."
)
STORE_FAILED_TEXT = (
    "빠른 시세를 저장하지 못했습니다. 화면에는 이전에 저장한 값이 보입니다."
)
PREVIOUS_INVALID_TEXT = "이전 빠른 시세 저장 파일을 읽지 못해 새로 저장했습니다."
INVALID_TEXT = "빠른 시세 저장 파일을 읽지 못했습니다."

_ATTEMPT_STATUSES = ("updated", "unchanged", "failed")
# 같은 시세인지 보는 칸 — 원천 표기 시각(source_time)은 넣지 않는다(확인 1).
_SAME_KEYS = ("trade_date", "value", "change", "change_pct", "market_status")
_QUOTE_KEYS = (
    "value",
    "change",
    "change_pct",
    "source_time",
    "trade_date",
    "market_status",
    "fetched_at",
)


@dataclass(frozen=True)
class QuickItem:
    code: str
    name: str
    kind: str  # index · stock


ITEMS = (
    QuickItem("KOSPI", "코스피", "index"),
    QuickItem("KOSDAQ", "코스닥", "index"),
    QuickItem("069500", "KODEX 200", "stock"),
)

_lock = threading.Lock()


class QuickFetchError(Exception):
    """조회 실패 — 사유(reason)를 그대로 시도 기록에 적는다."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _now_kst() -> datetime:
    return datetime.now(KST)


def _iso(dt: datetime) -> str:
    return dt.astimezone(KST).isoformat(timespec="seconds")


def now_iso() -> str:
    """지금 시각(KST ISO · 초 단위) — 묶음 작업의 예외 결과에도 같은 모양을 쓴다."""
    return _iso(_now_kst())


def source_url(item: QuickItem) -> str:
    if item.kind == "index":
        return NAVER_INDEX_URL.format(code=item.code)
    return market_naver.NAVER_BASIC_URL.format(ticker=item.code)


def http_fetch(url: str, *, client: Optional[httpx.Client] = None) -> object:
    """네이버 한 건 조회(`market_naver.fetch_one` 과 같은 시간 제한 · 머리글). 200 이 아니면 `QuickFetchError`."""
    if client is not None:
        resp = client.get(
            url,
            timeout=market_naver.DEFAULT_TIMEOUT_SEC,
            headers=market_naver.DEFAULT_HEADERS,
        )
    else:
        with httpx.Client(
            timeout=market_naver.DEFAULT_TIMEOUT_SEC,
            headers=market_naver.DEFAULT_HEADERS,
        ) as c:
            resp = c.get(url)
    if resp.status_code != 200:
        raise QuickFetchError(REASON_HTTP)
    return resp.json()  # 해석 실패 = ValueError → bad_value


# ── 응답 해석 ─────────────────────────────────────────────────────────────


def _finite(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _number(raw: object) -> Optional[float]:
    """'5,342.73' · '-300' 같은 문자열 또는 숫자 → float(쉼표 제거 · 읽을 수 없거나 무한대면 None)."""
    if isinstance(raw, str):
        s = raw.replace(",", "").strip()
        if not s:
            return None
        try:
            n = float(s)
        except ValueError:
            return None
    elif _finite(raw):
        n = float(raw)  # type: ignore[arg-type]
    else:
        return None
    return n if math.isfinite(n) else None


def _parse_time(raw: object) -> Optional[datetime]:
    """시간대가 붙은 ISO 시각만 받는다(시간대 없는 값 · 형식 오류 = None)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        t = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _trade_date(t: datetime) -> str:
    return t.astimezone(KST).date().isoformat()


def parse_quote(
    payload: object, fetched_at: str
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """응답 하나 → (시세, None) 또는 (None, 사유). 값 없음 · 이상 = bad_value · 시각 없음 · 이상 = missing_time."""
    if not isinstance(payload, dict):
        return None, REASON_BAD_VALUE
    value = _number(payload.get("closePrice"))
    if value is None or value <= 0:
        return None, REASON_BAD_VALUE
    source_time = payload.get("localTradedAt")
    when = _parse_time(source_time)
    if when is None:
        return None, REASON_MISSING_TIME
    change = _number(payload.get("compareToPreviousClosePrice"))
    change_pct = coerce_day_return(payload.get("fluctuationsRatio"))
    # 전일 대비 금액은 부호가 빠진 사례가 있었다(`market_naver` 주석 · 466920). 등락률과 부호가 어긋나면
    # 금액을 비운다 — 틀린 부호를 화면에 내지 않는다(등락률은 그대로).
    if change is not None and change_pct is not None and change * change_pct < 0:
        change = None
    status = payload.get("marketStatus")
    return (
        {
            "value": value,
            "change": change,
            "change_pct": change_pct,
            "source_time": source_time,
            "trade_date": _trade_date(when),
            "market_status": status if isinstance(status, str) else None,
            "fetched_at": fetched_at,
        },
        None,
    )


def _fetch_item(
    fetch: Fetcher, item: QuickItem, fetched_at: str
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    url = source_url(item)
    try:
        payload = fetch(url)
    except QuickFetchError as e:
        reason = e.reason
    except httpx.TimeoutException:
        reason = REASON_TIMEOUT
    except httpx.HTTPError:
        reason = REASON_HTTP
    except ValueError:  # JSON 해석 실패
        reason = REASON_BAD_VALUE
    except Exception:  # noqa: BLE001 — 이 항목만 실패로 적는다
        logger.exception("quick-quotes: fetch crashed code=%s", item.code)
        reason = REASON_HTTP
    else:
        quote, reason = parse_quote(payload, fetched_at)
        if quote is not None:
            return quote, None
    logger.warning("quick-quotes: failed code=%s reason=%s", item.code, reason)
    return None, reason


# ── 저장 파일 ─────────────────────────────────────────────────────────────


def _valid_success(d: object) -> bool:
    if not isinstance(d, dict):
        return False
    if not _finite(d.get("value")) or d["value"] <= 0:
        return False
    if any(
        d.get(k) is not None and not _finite(d.get(k)) for k in ("change", "change_pct")
    ):
        return False
    when = _parse_time(d.get("source_time"))
    trade_date = d.get("trade_date")
    if when is None or not isinstance(trade_date, str):
        return False
    try:
        date.fromisoformat(trade_date)
    except ValueError:
        return False
    if trade_date != _trade_date(when):  # 거래일은 원천 시각에서 다시 계산해 맞춰 본다
        return False
    status = d.get("market_status")
    if status is not None and not isinstance(status, str):
        return False
    return _parse_time(d.get("fetched_at")) is not None


def _valid_attempt(d: object) -> bool:
    if not isinstance(d, dict) or _parse_time(d.get("at")) is None:
        return False
    status, reason = d.get("status"), d.get("reason")
    if status not in _ATTEMPT_STATUSES:
        return False
    if status == "failed":
        return isinstance(reason, str) and bool(reason)
    return reason is None


def _load() -> tuple[str, dict[str, dict[str, Any]]]:
    """('ok' | 'empty' | 'invalid', 항목별 {last_success, last_attempt}).

    한 칸이라도 이상하면 파일 전체를 invalid 로 본다.
    """
    try:
        text = STORE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "empty", {}
    except (OSError, ValueError):  # 폴더 · 권한 · 글자 깨짐
        return "invalid", {}
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return "invalid", {}
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, dict):
        return "invalid", {}
    out: dict[str, dict[str, Any]] = {}
    for item in ITEMS:
        raw = items.get(item.code)
        if raw is None:
            continue  # 이 항목은 아직 기록 없음
        if not isinstance(raw, dict):
            return "invalid", {}
        success, attempt = raw.get("last_success"), raw.get("last_attempt")
        if success is not None and not _valid_success(success):
            return "invalid", {}
        if attempt is not None and not _valid_attempt(attempt):
            return "invalid", {}
        if success is None and attempt is not None and attempt["status"] != "failed":
            return "invalid", {}  # 성공 기록 없이 '받음'일 수 없다
        out[item.code] = {"last_success": success, "last_attempt": attempt}
    return "ok", out


def _write(items: dict[str, dict[str, Any]], updated_at: str) -> None:
    """임시 파일에 쓴 뒤 교체(`market_cache._atomic_write` 와 같은 방식 · 실패하면 원래 파일 그대로)."""
    text = json.dumps(
        {"updated_at": updated_at, "items": items}, ensure_ascii=False, indent=2
    )
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".quick_quotes_latest.", suffix=".tmp", dir=str(STORE_FILE.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, STORE_FILE)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── 받기(묶음 작업 ⓪) ─────────────────────────────────────────────────────


def _same_quote(prev: dict[str, Any], new: dict[str, Any]) -> bool:
    return all(prev.get(k) == new.get(k) for k in _SAME_KEYS)


def _refresh(fetch: Fetcher, clock: Clock) -> dict[str, Any]:
    started = _iso(clock())
    with _lock:
        state, previous = _load()
        if state == "invalid":
            logger.warning("quick-quotes: previous store unreadable — rewriting")
        stored: dict[str, dict[str, Any]] = {}
        results: dict[str, dict[str, Any]] = {}
        for item in ITEMS:
            prev = (previous.get(item.code) or {}).get("last_success")
            at = _iso(clock())
            quote, reason = _fetch_item(fetch, item, at)
            if quote is None:
                status, success = "failed", prev
            elif prev is not None and _same_quote(prev, quote):
                status, success = (
                    "unchanged",
                    prev,
                )  # 원천 시각만 바뀜 — 성공 기록 그대로
            else:
                status, success = "updated", quote
            stored[item.code] = {
                "last_success": success,
                "last_attempt": {"at": at, "status": status, "reason": reason},
            }
            results[item.code] = {"status": status, "reason": reason}
        try:
            _write(stored, _iso(clock()))
        except Exception:  # noqa: BLE001 — 저장 실패를 결과로 적는다
            logger.exception("quick-quotes: store write failed")
            for r in results.values():
                if r["status"] != "failed":
                    r.update(status="failed", reason=REASON_STORE)
            return {
                "status": "failed",
                "fetched_at": started,
                "items": results,
                "message": STORE_FAILED_TEXT,
            }
    failed = [i.name for i in ITEMS if results[i.code]["status"] == "failed"]
    messages: list[str] = []
    if len(failed) == len(ITEMS):
        status = "failed"
        messages.append(ALL_FAILED_TEXT)
    elif failed:
        status = "partial"
        messages.append(
            f"{' · '.join(failed)} 시세를 받지 못했습니다. 그 항목은 마지막으로 받은 값을 그대로 둡니다."
        )
    else:
        status = "done"
    if state == "invalid":
        messages.append(PREVIOUS_INVALID_TEXT)
    return {
        "status": status,
        "fetched_at": started,
        "items": results,
        "message": " ".join(messages) or None,
    }


def refresh_quick_quotes(
    fetch: Optional[Fetcher] = None, now: Optional[Clock] = None
) -> dict[str, Any]:
    """세 항목을 순서대로 받아 저장한다. 결과 = {status: done · partial · failed, fetched_at, items, message}.

    예외를 올리지 않는다. 기본 조회 함수는 부를 때 모듈 속성으로 찾는다(시험의 바꿔 끼우기).
    """
    clock = now or _now_kst
    try:
        return _refresh(fetch or http_fetch, clock)
    except Exception:  # noqa: BLE001 — 묶음 작업의 다음 단계를 막지 않는다
        logger.exception("quick-quotes: refresh crashed")
        return {
            "status": "failed",
            "fetched_at": now_iso(),
            "items": {},
            "message": ERROR_TEXT,
        }


# ── 읽기(저장값만 · 외부 조회 없음) ────────────────────────────────────────


def _quote_view(d: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return None if d is None else {k: d.get(k) for k in _QUOTE_KEYS}


def _attempt_view(d: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return None if d is None else {k: d.get(k) for k in ("at", "status", "reason")}


def read_quick_quotes() -> dict[str, Any]:
    """{status: ok · empty(파일 없음) · invalid(읽지 못함), message, items(고정 순서 3개)}."""
    try:
        state, records = _load()
    except Exception:  # noqa: BLE001 — 읽기 실패는 invalid 로 보인다
        logger.exception("quick-quotes: read crashed")
        state, records = "invalid", {}
    items = []
    for item in ITEMS:
        rec = records.get(item.code) or {}
        items.append(
            {
                "code": item.code,
                "name": item.name,
                "kind": item.kind,
                "quote": _quote_view(rec.get("last_success")),
                "last_attempt": _attempt_view(rec.get("last_attempt")),
            }
        )
    return {
        "status": state,
        "message": INVALID_TEXT if state == "invalid" else None,
        "items": items,
    }


@router.get("/market/quick-quotes")
def get_quick_quotes() -> dict[str, Any]:
    return read_quick_quotes()
