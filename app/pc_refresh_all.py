"""POC6-29 — [최신 자료 갱신] 묶음 작업(PC · PLAN §3-6 · 판정 Q7 기본안).

- POST /refresh/all        : 시작. 이미 도는 중이면 새로 시작하지 않고 그 작업 상태(`status = "running"`).
  묶음 작업은 시장 갱신을 시작한 뒤 끝나지만, 그 시장 갱신이 아직 돌면 역시 그 작업 상태로 연결한다(보유 현재가를
  다시 받지 않음 · 판정 Q7 '처리 중 다른 탭에서 누르면 실행 중인 작업으로 연결').
- GET  /refresh/all/status : 단계별 상태.

순서 = ⓪ 빠른 시세(`pc_quick_quotes.refresh_quick_quotes` — 네이버 코스피 · 코스닥 지수 · KODEX 200 · 6시간 대기와
무관 · 보완 PLAN §9-2 · 판정 Q-R1 · Q-R2) → ① 보유 현재가(`holdings_quote_refresh` — 「보유 현황」 [시세 갱신 (Naver)]과
같은 한 번에 하나 경로 · 도는 중이면 그 결과를 받음) → ② 기존 시장 갱신 **시작**(`POST /market/refresh` 와 같은 함수 ·
기본 범위 · 한 번에 하나 · 6시간 간격 그대로). 시장 갱신이 끝나기를 기다리지 않는다 — 화면은 기존
`GET /market/refresh/status` 로 따라간다. 빠른 시세가 실패해도(일부 · 전부 · 예외) 그 결과를 ⓪에 적고 ①로 넘어간다.
보유가 비었거나 손상이어도(기존 422 · 500) 그 결과를 ①에 적고 ②로 넘어간다. 시장이 대기 중이면 남은 초와
가능 시각(`next_available_at`)을 적는다.
→ ③ 전일 자료 보충(`pc_prevday_fill.run_prevday_fill` · 보완 2차 PLAN §10-4 · S 판정 Q-S2) = ② 가 6시간 대기로
건너뛰었을 때만 같은 작업에서 모자란 코스피 공식 종가 · 수급 · VIX · 원/달러 · WTI 를 기존 경로로 받는다. ② 가 시작 ·
진행 중이면 같은 수집을 공유하므로 돌지 않는다(`skipped` · 사유).

상태 = {state: idle · running · done, job_id, started_at, finished_at(UTC 'Z'),
steps: {quick, holdings, market, prevday}}.
- quick = pending · running 또는 `refresh_quick_quotes` 결과 그대로({status: done · partial · failed,
  fetched_at(KST), items: {코드: {status: updated · unchanged · failed, reason}}, message}) ·
  예외 = failed(items 비움 · 안내 문장).
- holdings.status = pending · running · done(1종목 이상 성공 · 일부 실패는 fail_count) · failed ·
  skipped(보유 없음) · reason = holdings_empty · holdings_invalid · all_failed · error.
- market.status = pending 또는 기존 시작 결과(accepted · running · skipped_cooldown · vix_retry_running ·
  prevday_running) · 시작 중 예외 = failed_to_start.
- prevday.status = pending · running · done(항목별 결과 `items`) · skipped(사유 `reason`) ·
  failed(예외 · 안내 문장).

외부 호출 = 기존 네이버 종목 경로 · 기존 시장 갱신 + 빠른 시세의 네이버 지수 경로(판정 Q-R1 · 이 묶음 작업에서만).
연타 · 다른 탭은 도는 작업을 이어 보므로 빠른 시세도 그 작업에서 한 번만 받는다. 상태는 이 프로세스 메모리에만
둔다(서버를 다시 켜면 idle).
"""

from __future__ import annotations

import logging
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from fastapi import APIRouter

from app import api_market_topn
from app import holdings as holdings_module
from app import market_cache, pc_prevday_fill, pc_quick_quotes
from app.holdings import HoldingsValidationError
from app.holdings_quote_refresh import (
    HoldingsRefreshRejected,
    QuoteRefreshResult,
    refresh_holdings_quotes_shared,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["refresh-all"])

QuickRefresher = Callable[[], dict[str, Any]]  # `refresh_quick_quotes` 결과
HoldingsRefresher = Callable[[], tuple[QuoteRefreshResult, bool]]
MarketRunning = Callable[
    [Optional[str]], bool
]  # 이 refresh_id 의 시장 갱신이 아직 도는가
MarketStarter = Callable[
    [], Any
]  # status · refresh_id · message · cooldown_remaining_seconds 속성
PrevdayFiller = Callable[[], dict[str, Any]]  # `run_prevday_fill` 결과
ThreadRunner = Callable[[Callable[[], None]], None]

REASON_EMPTY = "holdings_empty"
REASON_INVALID = "holdings_invalid"
REASON_ALL_FAILED = "all_failed"
REASON_ERROR = "error"
HOLDINGS_ERROR_TEXT = "보유 현재가 갱신 중 오류가 났습니다."
MARKET_ERROR_TEXT = "시장 자료 갱신을 시작하지 못했습니다."
QUICK_ERROR_TEXT = "빠른 시세를 받는 중 오류가 났습니다."
PREVDAY_ERROR_TEXT = "전일 자료를 보충하는 중 오류가 났습니다."
PREVDAY_SKIP_TEXT = {
    "accepted": "시장 전체 갱신을 시작했습니다 — 같은 수집에서 받습니다",
    "running": "시장 전체 갱신이 진행 중입니다 — 같은 수집에서 받습니다",
    "vix_retry_running": "VIX 다시 받기가 진행 중입니다",
    "prevday_running": "전일 자료 보충이 이미 진행 중입니다",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")  # 시장 갱신 상태와 같은 모양(UTC)


def _idle() -> dict[str, Any]:
    return {
        "state": "idle",
        "job_id": None,
        "started_at": None,
        "finished_at": None,
        "steps": {"quick": None, "holdings": None, "market": None, "prevday": None},
    }


_lock = threading.Lock()
_job: dict[str, Any] = _idle()


def reset_for_testing() -> None:
    global _job
    with _lock:
        _job = _idle()


def snapshot() -> dict[str, Any]:
    with _lock:
        return deepcopy(_job)


def _set_step(name: str, value: dict[str, Any]) -> None:
    with _lock:
        _job["steps"][name] = value


def _latest_asof(values: list[Optional[str]]) -> Optional[str]:
    """시세 시각 중 가장 늦은 것(시간대가 섞여도 시각으로 비교 · 읽을 수 없는 값은 뺀다)."""
    best: Optional[tuple[datetime, str]] = None
    for v in values:
        if not isinstance(v, str) or not v.strip():
            continue
        try:
            t = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            continue
        if best is None or t > best[0]:
            best = (t, v)
    return best[1] if best else None


def _asof_before() -> Optional[str]:
    """갱신 전 캐시의 보유 종목 시세 시각(이전 → 이번 표시용 · 보유 · 캐시를 못 읽으면 None).

    표시용 값이라 어떤 읽기 오류도 갱신을 막지 않는다(형식이 어긋난 캐시 파일 포함 · 검토 지적).
    """
    try:
        loaded = holdings_module.load()
    except (HoldingsValidationError, OSError, ValueError):
        return None
    try:
        cache = market_cache.get_all()
        return _latest_asof(
            [cache[h.ticker].price_asof for h in loaded if h.ticker in cache]
        )
    except Exception:  # noqa: BLE001 — 표시용 이전 시각만 비운다
        logger.exception("refresh-all: previous quote time unreadable")
        return None


def _holdings_step(refresher: HoldingsRefresher) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "failed",
        "reason": None,
        "ok_count": None,
        "fail_count": None,
        "price_asof_before": _asof_before(),
        "price_asof_max": None,
        "failures": [],
        "shared": False,
        "message": None,
    }
    try:
        result, shared = refresher()
    except HoldingsRefreshRejected as e:
        empty = e.status_code == 422
        base.update(
            status="skipped" if empty else "failed",
            reason=REASON_EMPTY if empty else REASON_INVALID,
            message=e.detail,
        )
        return base
    except Exception:  # noqa: BLE001 — 이 단계만 실패로 적고 시장 단계로 넘어간다
        logger.exception("refresh-all: holdings step failed")
        base.update(reason=REASON_ERROR, message=HOLDINGS_ERROR_TEXT)
        return base
    base.update(
        status="done" if result.ok_count > 0 else "failed",
        reason=None if result.ok_count > 0 else REASON_ALL_FAILED,
        ok_count=result.ok_count,
        fail_count=result.fail_count,
        price_asof_max=_latest_asof([q.price_asof for q in result.quotes]),
        failures=list(result.failures),
        shared=shared,
    )
    return base


def _market_step(starter: MarketStarter) -> dict[str, Any]:
    try:
        r = starter()
    except Exception:  # noqa: BLE001 — 시작 실패를 결과로 적는다
        logger.exception("refresh-all: market start failed")
        return {
            "status": "failed_to_start",
            "refresh_id": None,
            "message": MARKET_ERROR_TEXT,
            "cooldown_remaining_seconds": None,
            "next_available_at": None,
        }
    cd = getattr(r, "cooldown_remaining_seconds", None)
    status = getattr(r, "status", None)
    return {
        "status": status,
        "refresh_id": getattr(r, "refresh_id", None),
        "message": getattr(r, "message", None),
        "cooldown_remaining_seconds": cd,
        "next_available_at": (
            _iso(_now() + timedelta(seconds=cd))
            if status == "skipped_cooldown" and isinstance(cd, int)
            else None
        ),
    }


def _quick_step(refresher: QuickRefresher) -> dict[str, Any]:
    """⓪ 빠른 시세 — 결과 사전을 그대로 적는다. 어떻게 실패해도 보유 · 시장 단계로 넘어간다."""
    try:
        result = refresher()
        if not isinstance(result, dict):
            raise TypeError(f"quick quotes result is {type(result).__name__}")
        return result
    except Exception:  # noqa: BLE001 — 이 단계만 실패로 적는다
        logger.exception("refresh-all: quick quotes step failed")
        return {
            "status": "failed",
            "fetched_at": pc_quick_quotes.now_iso(),
            "items": {},
            "message": QUICK_ERROR_TEXT,
        }


def _prevday_step(filler: PrevdayFiller, market: dict[str, Any]) -> dict[str, Any]:
    """③ — ② 가 대기로 건너뛴 경우에만 실행. 그 밖에는 사유와 함께 skipped(같은 수집 공유 · 시작 실패 등)."""
    status = market.get("status")
    if status != "skipped_cooldown":
        return {
            "status": "skipped",
            "reason": PREVDAY_SKIP_TEXT.get(
                status, "시장 갱신을 시작하지 못해 전일 자료 보충도 하지 않았습니다"
            ),
            "id": None,
            "items": {},
        }
    try:
        result = filler()
        if not isinstance(result, dict):
            raise TypeError(f"prevday result is {type(result).__name__}")
        return result
    except Exception:  # noqa: BLE001 — 이 단계만 실패로 적는다
        logger.exception("refresh-all: prevday step failed")
        return {
            "status": "failed",
            "reason": PREVDAY_ERROR_TEXT,
            "id": None,
            "items": {},
        }


def _default_prevday_filler() -> dict[str, Any]:
    # 부를 때 모듈 속성으로 찾는다(시험이 바꿔 끼운다).
    return pc_prevday_fill.run_prevday_fill()


def _default_quick_refresher() -> dict[str, Any]:
    # 부를 때 모듈 속성으로 찾는다(시험이 네이버 조회 함수를 바꿔 끼운다).
    return pc_quick_quotes.refresh_quick_quotes()


def _default_market_starter() -> Any:
    # `POST /market/refresh`(기본 범위)가 부르는 그 함수 그대로(한 번에 하나 · 6시간 간격 · VIX 재시도 중 거절).
    return api_market_topn.post_market_refresh(scope=None)


def _market_running(refresh_id: Optional[str]) -> bool:
    """기존 시장 갱신 상태(메모리)가 이 refresh_id 로 아직 도는가 — 읽지 못하면 False(새 작업 허용)."""
    try:
        st = api_market_topn.get_market_refresh_status()
    except Exception:  # noqa: BLE001
        logger.exception("refresh-all: market status unreadable")
        return False
    return getattr(st, "status", None) == "running" and (
        refresh_id is None or getattr(st, "refresh_id", None) == refresh_id
    )


def _runner(
    job_id: str,
    quick: QuickRefresher,
    refresher: HoldingsRefresher,
    starter: MarketStarter,
    prevday: PrevdayFiller,
) -> None:
    try:
        _set_step("quick", {"status": "running"})
        _set_step("quick", _quick_step(quick))
        _set_step("holdings", {"status": "running"})
        try:
            holdings = _holdings_step(refresher)
        except (
            Exception
        ):  # noqa: BLE001 — 보유 단계가 어떻게 실패해도 시장 단계로 넘어간다
            logger.exception("refresh-all: holdings step crashed")
            holdings = {
                "status": "failed",
                "reason": REASON_ERROR,
                "ok_count": None,
                "fail_count": None,
                "price_asof_before": None,
                "price_asof_max": None,
                "failures": [],
                "shared": False,
                "message": HOLDINGS_ERROR_TEXT,
            }
        _set_step("holdings", holdings)
        market = _market_step(starter)
        _set_step("market", market)
        if market.get("status") == "skipped_cooldown":
            _set_step("prevday", {"status": "running"})
        _set_step("prevday", _prevday_step(prevday, market))
    finally:
        with _lock:
            if _job["job_id"] == job_id:
                _job["state"] = "done"
                _job["finished_at"] = _iso(_now())


def start_refresh_all(
    *,
    quick_refresher: Optional[QuickRefresher] = None,
    holdings_refresher: Optional[HoldingsRefresher] = None,
    market_starter: Optional[MarketStarter] = None,
    thread_runner: Optional[ThreadRunner] = None,
    market_running: Optional[MarketRunning] = None,
    prevday_filler: Optional[PrevdayFiller] = None,
) -> dict[str, Any]:
    """시작(`status = accepted`) · 이미 도는 중이면 그 작업 상태(`status = running`).

    지난 작업이 시작한 시장 갱신이 아직 돌아도 그 작업 상태를 준다(새로 만들지 않음 · 빠른 시세 · 보유 현재가도
    다시 받지 않음).
    """
    global _job
    still = market_running or _market_running
    with _lock:
        if _job["state"] == "running":
            return {"status": "running", **deepcopy(_job)}
        market = (_job.get("steps") or {}).get("market") or {}
        if (
            _job.get("job_id")
            and market.get("status") in ("accepted", "running")
            and still(market.get("refresh_id"))
        ):
            return {"status": "running", **deepcopy(_job)}
        job_id = (
            f"refresh_all_{_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )
        _job = {
            "state": "running",
            "job_id": job_id,
            "started_at": _iso(_now()),
            "finished_at": None,
            "steps": {
                "quick": {"status": "pending"},
                "holdings": {"status": "pending"},
                "market": {"status": "pending"},
                "prevday": {"status": "pending"},
            },
        }
        started = deepcopy(_job)
    quick = quick_refresher or _default_quick_refresher
    refresher = holdings_refresher or refresh_holdings_quotes_shared
    starter = market_starter or _default_market_starter
    prevday = prevday_filler or _default_prevday_filler

    def run() -> None:
        _runner(job_id, quick, refresher, starter, prevday)

    if thread_runner is not None:
        thread_runner(run)
    else:
        threading.Thread(target=run, name=job_id, daemon=True).start()
    return {"status": "accepted", **started}


@router.post("/refresh/all")
def post_refresh_all() -> dict[str, Any]:
    return start_refresh_all()


@router.get("/refresh/all/status")
def get_refresh_all_status() -> dict[str, Any]:
    return snapshot()
