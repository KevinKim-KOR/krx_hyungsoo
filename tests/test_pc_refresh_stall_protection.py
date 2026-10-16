"""POC5-17 — PC 수동 갱신(POST /market/refresh)의 멈춤 보호(`DEF-FDR-TIMEOUT` 잔여).

PLAN docs/ai_plan/POC5/POC5-17_PC_MARKET_REFRESH_STALL_PROTECTION_PLAN_V1.md §2 · §3 · §5
판정 docs/ai_design/POC5/POC5-17_PC_MARKET_REFRESH_STALL_PROTECTION_PLAN_DECISION_2026-10-16.md
  §4 · §5 · §7
tmp DB · 가짜 fetcher · 연결만 받고 응답하지 않는 로컬 소켓 서버. 외부 조회 · 라이브 DB 0.
"""

from __future__ import annotations

import functools
import socket
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import requests
import urllib3

from app import market_data_fdr, market_refresh_service
from app.market_data_fdr import refresh_price_history
from app.market_refresh_service import (
    PRICE_TIMEOUT_STOP_STREAK,
    PRICE_TIMEOUT_STOP_TEXT,
    get_state_snapshot,
    start_refresh_job,
)
from app.three_push_runtime.market_data_batch import fdr_request_timeout
from tests.test_market_vix_retry import _price_fetcher, _universe_df, svc  # noqa: F401

END = date(2026, 10, 13)
TICKERS = [f"1000{i:02d}" for i in range(1, 13)]  # 12종목 · 이 순서로 조회
ORIGINAL_REQUEST = requests.Session.request


def _ok(ticker, start, end):
    return _price_fetcher(ticker, start, end)


def _scripted(outcomes: dict, default="timeout"):
    """종목별 결과: 'ok' · 'empty' · 예외 객체 · 'timeout'(ReadTimeout). 호출 순서를 기록한다."""
    calls: list[str] = []

    def fetch(tk, start, end):
        calls.append(tk)
        out = outcomes.get(tk, default)
        if out == "ok":
            return _ok(tk, start, end)
        if out == "empty":
            return pd.DataFrame()
        if out == "timeout":
            raise requests.exceptions.ReadTimeout("read timed out")
        raise out

    return fetch, calls


def _log(db: Path, source: str = "FinanceDataReader/prices") -> tuple:
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT attempted_count, success_count, fail_count, error_summary "
            "FROM market_refresh_log WHERE source = ? ORDER BY rowid DESC LIMIT 1",
            (source,),
        ).fetchone()
    finally:
        con.close()


# ── 공유 함수(선택 인자) ──────────────────────────────────────────────────────
def test_stops_after_exactly_five_consecutive_timeouts(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    fetch, calls = _scripted({})
    r = refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=db,
        stop_after_consecutive_timeouts=5,
    )
    assert (
        calls == TICKERS[:5]
    )  # 다섯 번째 시간 초과를 처리한 뒤 남은 종목은 조회하지 않는다
    assert (r.not_started, r.stopped_on_timeouts) == (7, True)
    # 기존 기록 의미(대상 · 대상 - 성공)는 그대로 · 조회하지 않은 수는 사유에 따로.
    assert (r.attempted, r.success, r.fail) == (12, 0, 12)
    attempted, success, fail, summary = _log(db)
    assert (attempted, success, fail) == (12, 0, 12)
    assert summary.startswith(
        "stopped_after_consecutive_timeouts=5 queried=5 not_started=7; "
    )


@pytest.mark.parametrize(
    "breaker",
    [
        "ok",
        "empty",
        ValueError("parse"),
        requests.exceptions.HTTPError("500"),
        requests.exceptions.ConnectionError("refused"),
    ],
    ids=["성공", "빈 자료", "파싱 오류", "HTTP 오류", "연결 거부"],
)
def test_streak_resets_on_any_non_timeout_result(tmp_path: Path, breaker) -> None:
    fetch, calls = _scripted(
        {TICKERS[4]: breaker}
    )  # 4번 시간 초과 · 끊김 · 그 뒤 시간 초과
    r = refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=tmp_path / "m.sqlite",
        stop_after_consecutive_timeouts=5,
    )
    assert calls == TICKERS[:10]  # 끊긴 뒤 다시 다섯 번째에서 멈춤
    assert r.not_started == 2


def test_store_failure_also_resets_streak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = market_data_fdr.upsert_daily_prices

    def upsert(rows, **kw):
        if rows and rows[0].ticker == TICKERS[4]:
            raise sqlite3.OperationalError("locked")
        return real(rows, **kw)

    monkeypatch.setattr(market_data_fdr, "upsert_daily_prices", upsert)
    fetch, calls = _scripted({TICKERS[4]: "ok"})
    refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=tmp_path / "m.sqlite",
        stop_after_consecutive_timeouts=5,
    )
    assert calls == TICKERS[:10]


@pytest.mark.parametrize(
    "exc",
    [
        requests.exceptions.ConnectTimeout("connect"),
        requests.exceptions.ReadTimeout("read"),
        TimeoutError("socket"),
        requests.exceptions.ConnectionError(
            urllib3.exceptions.ReadTimeoutError(None, "/x", "read timed out")
        ),
    ],
    ids=["연결 시간 초과", "읽기 시간 초과", "소켓 시간 초과", "본문 읽기 시간 초과"],
)
def test_timeout_kinds_are_counted(tmp_path: Path, exc) -> None:
    fetch, calls = _scripted({}, default=exc)
    r = refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=tmp_path / "m.sqlite",
        stop_after_consecutive_timeouts=5,
    )
    assert len(calls) == 5 and r.stopped_on_timeouts


def test_message_text_alone_is_not_a_timeout(tmp_path: Path) -> None:
    fetch, calls = _scripted({}, default=RuntimeError("read timed out"))
    r = refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=tmp_path / "m.sqlite",
        stop_after_consecutive_timeouts=5,
    )
    assert len(calls) == 12 and not r.stopped_on_timeouts


def test_without_argument_behaviour_is_unchanged(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    fetch, calls = _scripted({})
    r = refresh_price_history(TICKERS, end_date=END, price_fetcher=fetch, db_path=db)
    assert calls == TICKERS  # OCI 배치 경로 — 끝까지 조회
    assert (r.attempted, r.success, r.fail) == (12, 0, 12)
    assert (r.not_started, r.stopped_on_timeouts) == (0, False)
    summary = _log(db)[3]
    assert summary == "; ".join(f"{t}:ReadTimeout: read timed out" for t in TICKERS[:5])


def test_last_five_timeouts_with_nothing_left_is_not_a_stop(tmp_path: Path) -> None:
    fetch, calls = _scripted({t: "ok" for t in TICKERS[:7]})  # 마지막 5종목 시간 초과
    r = refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=tmp_path / "m.sqlite",
        stop_after_consecutive_timeouts=5,
    )
    assert calls == TICKERS and (r.not_started, r.stopped_on_timeouts) == (0, False)


def test_saved_rows_kept_and_unqueried_rows_untouched(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    old = "2026-01-02"
    from app.market_data_store import EtfDailyPriceRow, upsert_daily_prices

    upsert_daily_prices(
        [EtfDailyPriceRow(t, old, 9, 9, 9, 9, 9, 0) for t in TICKERS],
        source="FinanceDataReader",
        db_path=db,
    )
    fetch, _ = _scripted({TICKERS[0]: "ok", TICKERS[1]: "ok"})
    refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=db,
        stop_after_consecutive_timeouts=5,
    )
    con = sqlite3.connect(str(db))
    try:
        rows = dict(
            ((t, d), c)
            for t, d, c in con.execute(
                "SELECT ticker, date, close FROM etf_daily_price"
            )
        )
    finally:
        con.close()
    assert rows[(TICKERS[0], "2026-10-13")] == 1.0  # 받은 자료 저장
    for t in TICKERS:
        assert rows[(t, old)] == 9.0  # 실패 · 미조회 종목의 기존 자료 그대로
    assert (TICKERS[7], "2026-10-13") not in rows


# ── 서비스 경계 ────────────────────────────────────────────────────────────────
def _run(rig: dict, prices, universe=None):
    return start_refresh_job(
        db_path=rig["db"],
        cooldown_hours=6,
        universe_fetcher=universe or (lambda: _universe_df(tuple(TICKERS[:8]))),
        price_fetcher=prices,
        end_date_for_prices=END,
        thread_runner=lambda runner: runner(),
    )


def test_stop_ends_job_failed_and_rerun_is_accepted(svc: dict) -> None:  # noqa: F811
    fetch, calls = _scripted({TICKERS[0]: "ok", TICKERS[1]: "ok"})
    assert _run(svc, fetch).status == "accepted"
    assert calls == TICKERS[:7]
    snap = get_state_snapshot(db_path=svc["db"])
    assert snap.status == "failed"  # 뒤 단계(KOSPI · VIX · NAV)가 성공해도 failed
    assert "kospi" in svc["calls"] and "nav" in svc["calls"]
    assert snap.error_summary == PRICE_TIMEOUT_STOP_TEXT.format(n=1)
    assert (
        snap.cooldown_remaining_seconds == 0
    )  # 성공 시각을 만들지 않음 · 대기 시작 안 함
    assert _run(svc, _ok).status == "accepted"  # running 이 남지 않고 바로 다시 실행
    assert get_state_snapshot(db_path=svc["db"]).status == "completed"


def test_partial_timeouts_complete_and_keep_existing_cooldown(
    svc: dict,  # noqa: F811
) -> None:
    fetch, calls = _scripted(
        {t: "ok" for t in TICKERS[:8]} | {TICKERS[1]: "timeout", TICKERS[5]: "timeout"}
    )
    _run(svc, fetch)
    snap = get_state_snapshot(db_path=svc["db"])
    assert (snap.status, snap.error_summary) == (
        "completed",
        "price_partial_failure: fail=2",
    )
    assert snap.cooldown_remaining_seconds > 0
    assert _run(svc, _ok).status == "skipped_cooldown"


def test_three_fdr_stages_are_wrapped_and_restored(
    svc: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    seen: dict[str, bool] = {}

    def universe():
        seen["universe"] = requests.Session.request is not ORIGINAL_REQUEST
        return _universe_df(tuple(TICKERS[:2]))

    def prices(tk, start, end):
        seen["prices"] = requests.Session.request is not ORIGINAL_REQUEST
        return _ok(tk, start, end)

    def equity(**kw):
        seen["equity"] = requests.Session.request is not ORIGINAL_REQUEST
        return None

    def vix(**kw):
        seen["vix_outside"] = requests.Session.request is ORIGINAL_REQUEST
        return None

    monkeypatch.setattr(
        market_refresh_service, "refresh_holdings_equity_prices", equity
    )
    monkeypatch.setattr(market_refresh_service, "refresh_pc_vix", vix)
    _run(svc, prices, universe=universe)
    assert seen == {
        "universe": True,
        "prices": True,
        "equity": True,
        "vix_outside": True,
    }
    assert requests.Session.request is ORIGINAL_REQUEST


@pytest.mark.parametrize("stage", ["price", "equity"])
def test_function_restored_when_exception_leaves_the_block(
    svc: dict, monkeypatch: pytest.MonkeyPatch, stage: str  # noqa: F811
) -> None:
    # 감싼 블록 밖으로 예외가 실제로 빠져나가는 경로(안에서 잡히는 fetcher 예외가 아님).
    def boom(*a, **kw):
        assert requests.Session.request is not ORIGINAL_REQUEST
        raise RuntimeError("boom")

    target = (
        "list_etf_tickers" if stage == "price" else "refresh_holdings_equity_prices"
    )
    monkeypatch.setattr(market_refresh_service, target, boom)
    _run(svc, _ok)
    assert requests.Session.request is ORIGINAL_REQUEST
    snap = get_state_snapshot(db_path=svc["db"])
    assert snap.status != "running"
    if stage == "price":
        # POC5-18 — 예상 밖 오류 회차는 failed(예전 completed 고정 기대값을 정정).
        assert snap.status == "failed"
        assert snap.error_summary.startswith("refresh_unexpected: RuntimeError")


# ── 실제 요청 대기 상한(로컬 소켓 · 응답 없음) ──────────────────────────────────
@pytest.fixture
def silent_server():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(64)
    held: list = []
    stop = threading.Event()

    def accept():
        srv.settimeout(0.2)
        while not stop.is_set():
            try:
                held.append(srv.accept())
            except OSError:
                continue

    th = threading.Thread(target=accept, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}/"
    stop.set()
    th.join(timeout=2)
    for conn, _ in held:
        conn.close()
    srv.close()


def test_real_request_timeout_ends_the_job(
    svc: dict, monkeypatch: pytest.MonkeyPatch, silent_server: str  # noqa: F811
) -> None:
    # 시험에서만 상한을 0.3초로 줄인다(같은 함수 · 운영 값 20초).
    monkeypatch.setattr(
        market_refresh_service,
        "fdr_request_timeout",
        functools.partial(fdr_request_timeout, 0.3),
    )
    calls: list[str] = []

    def prices(tk, start, end):
        calls.append(tk)
        requests.get(silent_server + tk)  # FDR 과 같은 방식(timeout 없이 requests.get)
        raise AssertionError("응답이 오지 않아야 한다")

    t0 = time.monotonic()
    _run(svc, prices)
    assert time.monotonic() - t0 < 10
    assert calls == TICKERS[:PRICE_TIMEOUT_STOP_STREAK]
    snap = get_state_snapshot(db_path=svc["db"])
    assert (snap.status, snap.error_summary) == (
        "failed",
        PRICE_TIMEOUT_STOP_TEXT.format(n=3),
    )
    assert requests.Session.request is ORIGINAL_REQUEST
    assert _log(svc["db"])[3].startswith(
        "stopped_after_consecutive_timeouts=5 queried=5 not_started=3; "
        f"{TICKERS[0]}:ReadTimeout"
    )


@pytest.fixture
def stalled_body_server():
    """헤더와 본문 일부만 보내고 멈추는 로컬 서버(본문 읽기 시간 초과)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(64)
    held: list = []
    stop = threading.Event()

    def serve():
        srv.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            held.append(conn)
            conn.recv(4096)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n"
                b"Content-Type: text/plain\r\n\r\npartial"
            )

    th = threading.Thread(target=serve, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.getsockname()[1]}/"
    stop.set()
    th.join(timeout=2)
    for conn in held:
        conn.close()
    srv.close()


def test_real_body_read_timeout_counts_toward_the_stop(
    svc: dict, monkeypatch: pytest.MonkeyPatch, stalled_body_server: str  # noqa: F811
) -> None:
    monkeypatch.setattr(
        market_refresh_service,
        "fdr_request_timeout",
        functools.partial(fdr_request_timeout, 0.3),
    )
    calls: list[str] = []

    def prices(tk, start, end):
        calls.append(tk)
        requests.get(stalled_body_server + tk)
        raise AssertionError("본문이 끝까지 오지 않아야 한다")

    _run(svc, prices)
    assert calls == TICKERS[:PRICE_TIMEOUT_STOP_STREAK]
    snap = get_state_snapshot(db_path=svc["db"])
    assert (snap.status, snap.error_summary) == (
        "failed",
        PRICE_TIMEOUT_STOP_TEXT.format(n=3),
    )


def test_real_timeout_on_universe_fails_and_clears_running(
    svc: dict, monkeypatch: pytest.MonkeyPatch, silent_server: str  # noqa: F811
) -> None:
    monkeypatch.setattr(
        market_refresh_service,
        "fdr_request_timeout",
        functools.partial(fdr_request_timeout, 0.3),
    )

    def universe():
        requests.get(silent_server + "etf")
        raise AssertionError("응답이 오지 않아야 한다")

    _run(svc, _ok, universe=universe)
    snap = get_state_snapshot(db_path=svc["db"])
    assert snap.status == "failed"
    assert snap.error_summary.startswith("universe_fetch_failed: ReadTimeout")
    assert _run(svc, _ok).status == "accepted"


# ── 검증자 r1 P2 — 중단 뒤 가격 기록 쓰기가 실패해도 중단은 failed ──────────────────
def _block_price_log(db: Path) -> None:
    """tmp DB 의 가격 기록 행 INSERT 만 막는다(SQLite 쓰기 경로 그대로 · 시험 전용 트리거)."""
    from app.market_data_store import init_db

    init_db(db)
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TRIGGER block_price_log BEFORE INSERT ON market_refresh_log "
            "WHEN NEW.source = 'FinanceDataReader/prices' "
            "BEGIN SELECT RAISE(ABORT, 'price log blocked'); END"
        )
        con.commit()
    finally:
        con.close()


def test_stop_survives_price_log_failure(svc: dict) -> None:  # noqa: F811
    _block_price_log(svc["db"])
    fetch, calls = _scripted({TICKERS[0]: "ok", TICKERS[1]: "ok"})
    _run(svc, fetch)
    assert calls == TICKERS[:7]  # 2 성공 · 5 시간 초과 · 1 미조회
    snap = get_state_snapshot(db_path=svc["db"])
    assert snap.status == "failed"
    stop_text = PRICE_TIMEOUT_STOP_TEXT.format(n=1)
    assert snap.error_summary.startswith(f"{stop_text} · refresh_unexpected: ")
    assert "price log blocked" in snap.error_summary
    assert snap.cooldown_remaining_seconds == 0
    assert _run(svc, _ok).status == "accepted"


def test_on_stop_is_called_before_the_price_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    real = market_data_fdr.log_refresh

    def log(**kw):
        order.append("log")
        return real(**kw)

    monkeypatch.setattr(market_data_fdr, "log_refresh", log)
    fetch, _ = _scripted({})
    refresh_price_history(
        TICKERS,
        end_date=END,
        price_fetcher=fetch,
        db_path=tmp_path / "m.sqlite",
        stop_after_consecutive_timeouts=5,
        on_stop=lambda n: order.append(f"stop:{n}"),
    )
    assert order == ["stop:7", "log"]
