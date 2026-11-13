"""POC6-29 — [최신 자료 갱신] 묶음 작업 · 보유 현재가 한 번에 하나(PLAN §3-6 · 판정 Q7 · 완료 확인 4).

- 보유 현재가: 겹친 호출(연타 · 다른 탭 · 「보유 현황」 · 묶음 작업)은 네이버 조회 1번 · 같은 결과.
- 묶음 작업: 빠른 시세 → 보유 현재가 → 시장 갱신 시작(순서 · 보완 PLAN §9-2 ⓪) · 도는 중 두 번째 시작 = 그 작업
  상태(빠른 시세 · 보유 현재가 다시 받지 않음) · 시장 대기(가능 시각) · 빠른 시세 실패 · 예외 · 보유 없음 · 손상 ·
  일부 실패 · 시작 실패를 단계 결과로 적고 다음 단계로 넘어감.
- 재진입 검토 창의 이동 메뉴 = 「오늘의 투자 점검」(판정 Q14 · PLAN §1-7).
네이버 · 실제 시장 갱신은 부르지 않는다(가짜 함수 주입 · conftest 격리 보유 · 캐시). 빠른 시세 기본 조회 함수 =
네이버 응답 사본(`tests/fixtures/poc6_29_quick_quotes/`) · 저장 파일 = 임시 폴더 · 실제 HTTP 전송은 시도만 해도 실패.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import httpx
import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, market_cache, market_naver, pc_quick_quotes
from app import pc_prevday_fill, pc_refresh_all
from app import holdings_quote_refresh as hq
from app.reentry_review import models as reentry_models
from tests._helpers import _VALID_HOLDINGS

TICKERS = [h["ticker"] for h in _VALID_HOLDINGS]
QUICK_DIR = Path(__file__).parent / "fixtures" / "poc6_29_quick_quotes"
QUICK_COPIES = {  # 주소 → 네이버 공개 응답 사본(README.txt)
    "https://m.stock.naver.com/api/index/KOSPI/basic": "kospi_1536.json",
    "https://m.stock.naver.com/api/index/KOSDAQ/basic": "kosdaq_1536.json",
    "https://m.stock.naver.com/api/stock/069500/basic": "kodex200_1535.json",
}


@pytest.fixture(autouse=True)
def _reset_job() -> Any:
    pc_refresh_all.reset_for_testing()
    yield
    pc_refresh_all.reset_for_testing()


@pytest.fixture(autouse=True)
def quick_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """빠른 시세 저장 = 임시 폴더 · 기본 조회 = 응답 사본(부른 주소 기록) · 실제 HTTP 전송 시도 = 실패."""
    monkeypatch.setattr(
        pc_quick_quotes, "STORE_FILE", tmp_path / "quick" / "quick_quotes_latest.json"
    )
    calls: list[str] = []
    attempts: list[str] = []

    def copy_fetch(url: str) -> object:
        calls.append(url)
        return json.loads((QUICK_DIR / QUICK_COPIES[url]).read_text(encoding="utf-8"))

    def blocked(self: Any, request: httpx.Request) -> Any:
        attempts.append(str(request.url))
        raise RuntimeError("실제 HTTP 전송 금지(시험)")

    monkeypatch.setattr(pc_quick_quotes, "http_fetch", copy_fetch)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    yield calls
    assert attempts == [], f"실제 HTTP 전송 시도: {attempts}"


@pytest.fixture
def client() -> TestClient:
    c = TestClient(api_module.app)
    assert c.put("/holdings", json={"holdings": _VALID_HOLDINGS}).status_code == 200
    return c


def _quote(t: str, asof: Optional[str]) -> market_cache.MarketQuote:
    return market_cache.MarketQuote(
        ticker=t, name=f"n{t}", current_price=1000.0, price_asof=asof
    )


def _results(
    tickers: list[str], asofs: Optional[dict[str, str]] = None, fail: tuple = ()
) -> list[market_naver.FetchResult]:
    out = []
    for t in tickers:
        if t in fail:
            out.append(market_naver.FetchResult(ticker=t, quote=None, reason="timeout"))
        else:
            asof = (asofs or {}).get(t, "2026-11-12T10:00:00+09:00")
            out.append(
                market_naver.FetchResult(ticker=t, quote=_quote(t, asof), reason=None)
            )
    return out


# ── 보유 현재가 한 번에 하나 ───────────────────────────────────────────────


def test_overlapping_callers_share_one_naver_fetch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """먼저 시작한 호출이 조회 중일 때 들어온 함수 호출 · 「보유 현황」 경로가 같은 결과를 받는다."""
    joined = threading.Semaphore(0)
    entered = threading.Event()
    calls: list[list[str]] = []

    class SpyEvent(threading.Event):
        def wait(self, timeout: Optional[float] = None) -> bool:
            joined.release()  # 붙은 호출이 기다리기 시작함
            return super().wait(timeout)

    class SpyFlight(hq._Flight):
        def __init__(self) -> None:
            super().__init__()
            self.done = SpyEvent()

    def fake_fetch(tickers: list[str], **_: Any) -> list[market_naver.FetchResult]:
        calls.append(list(tickers))
        entered.set()
        assert joined.acquire(timeout=5) and joined.acquire(timeout=5)
        return _results(tickers)

    monkeypatch.setattr(hq, "_Flight", SpyFlight)
    monkeypatch.setattr(market_naver, "fetch_many", fake_fetch)
    out: dict[str, Any] = {}

    def run(name: str, fn: Callable[[], Any]) -> threading.Thread:
        t = threading.Thread(target=lambda: out.__setitem__(name, fn()))
        t.start()
        return t

    leader = run("leader", hq.refresh_holdings_quotes_shared)
    assert entered.wait(timeout=5)
    others = [
        run("joiner", hq.refresh_holdings_quotes_shared),
        run("http", lambda: client.post("/holdings/market/refresh")),
    ]
    for t in [leader, *others]:
        t.join(timeout=10)
        assert not t.is_alive()
    assert calls == [TICKERS]  # 네이버 조회 1번
    assert out["leader"][1] is False and out["joiner"][1] is True
    assert out["joiner"][0] is out["leader"][0]
    res = out["http"]
    assert res.status_code == 200
    assert res.json()["ok_count"] == 2 and res.json()["fail_count"] == 0
    assert hq._inflight is None


def test_sequential_calls_fetch_again_and_failure_clears(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def fake(tickers: list[str], **_: Any) -> list[market_naver.FetchResult]:
        calls.append(1)
        return _results(tickers)

    monkeypatch.setattr(market_naver, "fetch_many", fake)
    hq.refresh_holdings_quotes()
    hq.refresh_holdings_quotes()
    assert len(calls) == 2  # 끝난 실행의 결과를 계속 돌려주지 않는다

    def boom(tickers: list[str], **_: Any) -> list[market_naver.FetchResult]:
        raise ValueError("network")

    monkeypatch.setattr(market_naver, "fetch_many", boom)
    with pytest.raises(ValueError):
        hq.refresh_holdings_quotes()
    assert hq._inflight is None
    monkeypatch.setattr(market_naver, "fetch_many", fake)
    assert hq.refresh_holdings_quotes().ok_count == 2


def test_endpoint_rejections_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    c = TestClient(api_module.app)
    assert c.post("/holdings/market/refresh").status_code == 422  # 보유 없음
    with pytest.raises(hq.HoldingsRefreshRejected) as e:
        hq.refresh_holdings_quotes()
    assert e.value.status_code == 422 and e.value.detail == hq.EMPTY_DETAIL

    def corrupt() -> list:
        raise hq.HoldingsValidationError("bad")

    monkeypatch.setattr(hq.holdings_module, "load", corrupt)
    res = c.post("/holdings/market/refresh")
    assert res.status_code == 500 and "holdings 저장 파일 손상" in res.json()["detail"]


# ── 묶음 작업 ─────────────────────────────────────────────────────────────


def _market(status: str = "accepted", cd: int = 0) -> Callable[[], Any]:
    return lambda: SimpleNamespace(
        status=status,
        refresh_id="market_refresh_x",
        message="m",
        cooldown_remaining_seconds=cd,
    )


def _sync(fn: Callable[[], None]) -> None:
    fn()


PREVDAY_STUB = {"status": "done", "reason": None, "id": "prevday_stub", "items": {}}


@pytest.fixture(autouse=True)
def _stub_prevday(monkeypatch: pytest.MonkeyPatch) -> None:
    """보완 2차 — ② 가 대기인 시험에서 ③ 기본 실행(실제 시장 DB · KRX · OCI)을 부르지 않게(③ 자체는 별도 시험)."""
    monkeypatch.setattr(pc_prevday_fill, "run_prevday_fill", lambda: dict(PREVDAY_STUB))


def test_job_runs_holdings_then_market_and_records_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    market_cache.upsert_many([_quote(TICKERS[0], "2026-11-11T15:00:00+09:00")])

    def fake(tickers: list[str], **_: Any) -> list[market_naver.FetchResult]:
        order.append("holdings")
        return _results(
            tickers,
            {TICKERS[0]: "2026-11-12T09:59:00+09:00"},
            fail=(TICKERS[1],),
        )

    def market() -> Any:
        order.append("market")
        return _market()()

    monkeypatch.setattr(market_naver, "fetch_many", fake)
    started = pc_refresh_all.start_refresh_all(
        market_starter=market, thread_runner=_sync
    )
    assert started["status"] == "accepted" and started["job_id"]
    snap = pc_refresh_all.snapshot()
    assert order == ["holdings", "market"]
    assert snap["steps"]["quick"]["status"] == "done"  # 기본 빠른 시세(응답 사본)
    assert snap["state"] == "done" and snap["job_id"] == started["job_id"]
    assert snap["finished_at"] and snap["started_at"]
    h = snap["steps"]["holdings"]
    assert (h["status"], h["ok_count"], h["fail_count"]) == ("done", 1, 1)
    assert h["failures"] == [{"ticker": TICKERS[1], "reason": "timeout"}]
    assert h["price_asof_before"] == "2026-11-11T15:00:00+09:00"
    assert h["price_asof_max"] == "2026-11-12T09:59:00+09:00"
    assert h["shared"] is False
    m = snap["steps"]["market"]
    assert m == {
        "status": "accepted",
        "refresh_id": "market_refresh_x",
        "message": "m",
        "cooldown_remaining_seconds": 0,
        "next_available_at": None,
    }


def test_second_start_while_running_returns_running_job(client: TestClient) -> None:
    pending: list[Callable[[], None]] = []
    calls: list[str] = []

    def refresher() -> Any:
        calls.append("h")
        return hq.QuoteRefreshResult(1, 0, [_quote("069500", None)], []), False

    def quick() -> dict[str, Any]:
        calls.append("q")
        return {"status": "done", "fetched_at": "t", "items": {}, "message": None}

    first = pc_refresh_all.start_refresh_all(
        quick_refresher=quick,
        holdings_refresher=refresher,
        market_starter=_market(),
        thread_runner=pending.append,
    )
    second = pc_refresh_all.start_refresh_all(
        quick_refresher=quick,
        holdings_refresher=refresher,
        market_starter=_market(),
        thread_runner=pending.append,
    )
    assert first["status"] == "accepted" and second["status"] == "running"
    assert second["job_id"] == first["job_id"] and len(pending) == 1
    assert second["steps"]["quick"] == {"status": "pending"}
    assert second["steps"]["holdings"] == {"status": "pending"}
    pending[0]()
    assert calls == ["q", "h"] and pc_refresh_all.snapshot()["state"] == "done"
    third = pc_refresh_all.start_refresh_all(
        holdings_refresher=refresher,
        market_starter=_market(),
        thread_runner=_sync,
        market_running=lambda _rid: False,
    )
    assert third["status"] == "accepted" and third["job_id"] != first["job_id"]


def test_start_while_job_market_refresh_still_running_joins_that_job(
    client: TestClient, quick_calls: list[str]
) -> None:
    """검토 지적 — 묶음 작업은 시장 갱신 시작 직후 끝난다. 그 시장 갱신이 도는 동안 다른 탭이 누르면 새 작업 ·
    보유 현재가 재조회 없이 그 작업으로 연결(판정 Q7). 시장 갱신이 끝나면 새 작업."""
    calls: list[str] = []
    seen: list[Optional[str]] = []

    def refresher() -> Any:
        calls.append("h")
        return hq.QuoteRefreshResult(1, 0, [], []), False

    first = pc_refresh_all.start_refresh_all(
        holdings_refresher=refresher, market_starter=_market(), thread_runner=_sync
    )
    assert len(quick_calls) == 3  # 기본 빠른 시세 = 세 주소 한 번씩
    running = {"v": True}

    def still(rid: Optional[str]) -> bool:
        seen.append(rid)
        return running["v"]

    second = pc_refresh_all.start_refresh_all(
        holdings_refresher=refresher,
        market_starter=_market(),
        thread_runner=_sync,
        market_running=still,
    )
    assert second["status"] == "running" and second["job_id"] == first["job_id"]
    assert second["steps"]["market"]["refresh_id"] == "market_refresh_x"
    assert calls == ["h"] and seen == ["market_refresh_x"]
    assert len(quick_calls) == 3  # 이어 보기 = 빠른 시세도 다시 받지 않음
    running["v"] = False
    third = pc_refresh_all.start_refresh_all(
        holdings_refresher=refresher,
        market_starter=_market(),
        thread_runner=_sync,
        market_running=still,
    )
    assert third["status"] == "accepted" and third["job_id"] != first["job_id"]
    assert calls == ["h", "h"] and len(quick_calls) == 6


def test_cooldown_or_failed_market_step_does_not_join_previous_job(
    client: TestClient,
) -> None:
    """시장 단계가 대기 · 시작 실패였으면 도는 시장 갱신이 없다 — 상태를 묻지 않고 새 작업."""
    asked: list[Optional[str]] = []
    for status in ("skipped_cooldown", "vix_retry_running"):
        pc_refresh_all.reset_for_testing()
        pc_refresh_all.start_refresh_all(
            holdings_refresher=lambda: (hq.QuoteRefreshResult(1, 0, [], []), False),
            market_starter=_market(status, 600),
            thread_runner=_sync,
        )
        again = pc_refresh_all.start_refresh_all(
            holdings_refresher=lambda: (hq.QuoteRefreshResult(1, 0, [], []), False),
            market_starter=_market(status, 600),
            thread_runner=_sync,
            market_running=lambda rid: asked.append(rid) or True,
        )
        assert again["status"] == "accepted"
    assert asked == []


def test_unreadable_previous_quote_cache_does_not_stop_the_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """검토 지적 — 갱신 전 시세 시각(표시용)을 못 읽어도 보유 · 시장 단계는 그대로."""

    def broken() -> Any:
        raise AttributeError("'list' object has no attribute 'items'")

    monkeypatch.setattr(market_cache, "get_all", broken)
    market_calls: list[int] = []

    def market() -> Any:
        market_calls.append(1)
        return _market()()

    pc_refresh_all.start_refresh_all(
        holdings_refresher=lambda: (hq.QuoteRefreshResult(2, 0, [], []), False),
        market_starter=market,
        thread_runner=_sync,
    )
    snap = pc_refresh_all.snapshot()
    h = snap["steps"]["holdings"]
    assert (h["status"], h["ok_count"], h["price_asof_before"]) == ("done", 2, None)
    assert market_calls == [1] and snap["steps"]["market"]["status"] == "accepted"
    assert snap["state"] == "done"


def test_crash_inside_holdings_step_is_recorded_and_market_still_starts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(_refresher: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(pc_refresh_all, "_holdings_step", crash)
    market_calls: list[int] = []

    def market() -> Any:
        market_calls.append(1)
        return _market()()

    pc_refresh_all.start_refresh_all(market_starter=market, thread_runner=_sync)
    snap = pc_refresh_all.snapshot()
    h = snap["steps"]["holdings"]
    assert (h["status"], h["reason"]) == ("failed", "error")
    assert h["message"] == pc_refresh_all.HOLDINGS_ERROR_TEXT
    assert market_calls == [1] and snap["steps"]["market"]["status"] == "accepted"


def test_market_cooldown_records_next_available_time(client: TestClient) -> None:
    before = datetime.now(timezone.utc)
    pc_refresh_all.start_refresh_all(
        holdings_refresher=lambda: (hq.QuoteRefreshResult(1, 0, [], []), True),
        market_starter=_market("skipped_cooldown", 3600),
        thread_runner=_sync,
    )
    snap = pc_refresh_all.snapshot()
    assert snap["steps"]["holdings"]["shared"] is True
    m = snap["steps"]["market"]
    assert m["status"] == "skipped_cooldown" and m["cooldown_remaining_seconds"] == 3600
    assert (
        snap["steps"]["prevday"] == PREVDAY_STUB
    )  # 보완 2차 — 대기면 ③ 을 같은 작업에서 돌린다
    nxt = datetime.strptime(m["next_available_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    assert (
        before + timedelta(seconds=3590)
        <= nxt
        <= datetime.now(timezone.utc) + timedelta(seconds=3601)
    )


@pytest.mark.parametrize(
    "error, status, reason",
    [
        (hq.HoldingsRefreshRejected(422, hq.EMPTY_DETAIL), "skipped", "holdings_empty"),
        (hq.HoldingsRefreshRejected(500, "손상"), "failed", "holdings_invalid"),
        (RuntimeError("x"), "failed", "error"),
    ],
)
def test_holdings_problem_is_recorded_and_market_still_starts(
    error: Exception, status: str, reason: str
) -> None:
    market_calls: list[int] = []

    def refresher() -> Any:
        raise error

    def market() -> Any:
        market_calls.append(1)
        return _market()()

    pc_refresh_all.start_refresh_all(
        holdings_refresher=refresher, market_starter=market, thread_runner=_sync
    )
    snap = pc_refresh_all.snapshot()
    h = snap["steps"]["holdings"]
    assert (h["status"], h["reason"]) == (status, reason)
    assert h["ok_count"] is None and h["message"]
    assert market_calls == [1] and snap["steps"]["market"]["status"] == "accepted"
    assert snap["state"] == "done"


def test_all_failed_and_market_start_failure(client: TestClient) -> None:
    def market() -> Any:
        raise RuntimeError("cannot start")

    pc_refresh_all.start_refresh_all(
        holdings_refresher=lambda: (
            hq.QuoteRefreshResult(0, 2, [], [{"ticker": "a", "reason": "x"}]),
            False,
        ),
        market_starter=market,
        thread_runner=_sync,
    )
    snap = pc_refresh_all.snapshot()
    h = snap["steps"]["holdings"]
    assert (h["status"], h["reason"], h["ok_count"], h["fail_count"]) == (
        "failed",
        "all_failed",
        0,
        2,
    )
    assert snap["steps"]["market"]["status"] == "failed_to_start"
    assert snap["state"] == "done"


def test_endpoints_use_single_flight_quotes_and_market_starter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, quick_calls: list[str]
) -> None:
    """기본 경로 = 보유 현재가 한 번에 하나 함수 + `POST /market/refresh` 와 같은 함수(가짜로 바꿈)."""
    monkeypatch.setattr(
        market_naver, "fetch_many", lambda tickers, **_: _results(tickers)
    )
    starts: list[Optional[str]] = []

    def fake_start(scope: Optional[str] = None) -> Any:
        starts.append(scope)
        return _market("running")()

    monkeypatch.setattr(api_market_topn, "post_market_refresh", fake_start)
    assert client.get("/refresh/all/status").json() == {
        "state": "idle",
        "job_id": None,
        "started_at": None,
        "finished_at": None,
        "steps": {"quick": None, "holdings": None, "market": None, "prevday": None},
    }
    res = client.post("/refresh/all")
    assert res.status_code == 200 and res.json()["status"] in ("accepted", "running")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        body = client.get("/refresh/all/status").json()
        if body["state"] == "done":
            break
        time.sleep(0.02)
    assert body["state"] == "done" and starts == [None]
    assert body["steps"]["holdings"]["ok_count"] == 2
    assert body["steps"]["market"]["status"] == "running"
    assert body["steps"]["prevday"]["status"] == "skipped"  # ② 진행 중 = 같은 수집 공유
    q = body["steps"]["quick"]  # 기본 = pc_quick_quotes.refresh_quick_quotes(응답 사본)
    assert quick_calls == list(QUICK_COPIES)
    assert (q["status"], q["message"]) == ("done", None) and q["fetched_at"]
    assert q["items"] == {
        c: {"status": "updated", "reason": None} for c in ("KOSPI", "KOSDAQ", "069500")
    }
    quotes = client.get("/market/quick-quotes").json()
    assert [i["quote"]["value"] for i in quotes["items"]] == [5342.73, 696.53, 84240.0]


# ── ⓪ 빠른 시세(보완 PLAN §9-2 · 확인 1) ─────────────────────────────────


def test_quick_runs_first_then_holdings_then_market(client: TestClient) -> None:
    order: list[str] = []
    seen: dict[str, Any] = {}
    result = {"status": "done", "fetched_at": "t", "items": {}, "message": None}

    def quick() -> dict[str, Any]:
        order.append("quick")
        seen["during_quick"] = pc_refresh_all.snapshot()["steps"]
        return result

    def refresher() -> Any:
        order.append("holdings")
        seen["during_holdings"] = pc_refresh_all.snapshot()["steps"]
        return hq.QuoteRefreshResult(1, 0, [], []), False

    def market() -> Any:
        order.append("market")
        return _market()()

    pc_refresh_all.start_refresh_all(
        quick_refresher=quick,
        holdings_refresher=refresher,
        market_starter=market,
        thread_runner=_sync,
    )
    assert order == ["quick", "holdings", "market"]
    assert seen["during_quick"] == {
        "quick": {"status": "running"},
        "holdings": {"status": "pending"},
        "market": {"status": "pending"},
        "prevday": {"status": "pending"},
    }
    assert seen["during_holdings"]["quick"] == result
    assert seen["during_holdings"]["holdings"] == {"status": "running"}
    assert pc_refresh_all.snapshot()["steps"]["quick"] == result


def _raise() -> Any:
    raise RuntimeError("boom")


@pytest.mark.parametrize("kind", ["all_failed", "partial", "raises", "not_dict"])
def test_quick_problem_does_not_stop_holdings_or_market(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    quick: Optional[Callable[[], Any]] = None
    if kind in (
        "all_failed",
        "partial",
    ):  # 기본 경로(실제 refresh_quick_quotes) · 조회 실패

        def fetch(url: str) -> object:
            if kind == "all_failed" or "KOSDAQ" in url:
                raise httpx.ConnectError("down")
            return json.loads((QUICK_DIR / QUICK_COPIES[url]).read_text("utf-8"))

        monkeypatch.setattr(pc_quick_quotes, "http_fetch", fetch)
    else:
        quick = _raise if kind == "raises" else (lambda: None)
    market_calls: list[int] = []

    def market() -> Any:
        market_calls.append(1)
        return _market()()

    pc_refresh_all.start_refresh_all(
        quick_refresher=quick,
        holdings_refresher=lambda: (hq.QuoteRefreshResult(2, 0, [], []), False),
        market_starter=market,
        thread_runner=_sync,
    )
    snap = pc_refresh_all.snapshot()
    q = snap["steps"]["quick"]
    if kind == "all_failed":
        assert (
            q["status"] == "failed" and q["message"] == pc_quick_quotes.ALL_FAILED_TEXT
        )
        assert {v["reason"] for v in q["items"].values()} == {"http_error"}
    elif kind == "partial":
        assert q["status"] == "partial"
        assert q["items"]["KOSDAQ"] == {"status": "failed", "reason": "http_error"}
    else:
        assert set(q) == {"status", "fetched_at", "items", "message"}
        assert (q["status"], q["items"], q["message"]) == (
            "failed",
            {},
            pc_refresh_all.QUICK_ERROR_TEXT,
        )
        assert q["fetched_at"].endswith("+09:00")
    assert snap["steps"]["holdings"]["status"] == "done"
    assert market_calls == [1] and snap["steps"]["market"]["status"] == "accepted"
    assert snap["state"] == "done"


# ── 재진입 검토 창 이동 메뉴(판정 Q14) ────────────────────────────────────


def test_reentry_navigation_points_to_today_check() -> None:
    first = reentry_models.NAVIGATION[0]
    assert first["menu"] == "today_check"
    assert first["label"] == "오늘의 투자 점검 — [최신 자료 갱신]"
    assert "6시간 간격" in first["note"]
    assert all(n["menu"] != "market_discovery" for n in reentry_models.NAVIGATION)
