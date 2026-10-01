"""POC3-02D-OPS-02 3-4 — KOSPI 최신성 화면 상태 (설계자 Q4~Q6 · 2026-09-28).

`GET /market/topn/latest` 의 `market_context.kospi` 에 선택 필드 3개
(`display_state` · `trading_day_lag` · `today_is_trading_day`)를 더한다.

- 상태표: 저장 자료 · KOSPI 적재 기록 · 최신 여부 · 운영 판정 · 오늘 거래일 여부 → 상태 하나.
- 거래일 지연은 KOSPI 적재 감지와 **같은 함수** — 같은 날 · 같은 자료로 적재 기록의
  `source_stale:…lag=N` 과 화면 lag 가 같다(설계자 Q6).
- POC3-02D-OPS-03 확정 계약 9 — 최신 = 기준일 == 기대 T-1(`kospi_freshness`). C7
  `lag ≤ 1` 폐기(T-2 는 정상 아님) · 적재 기록 source = KRX `idx/kospi_dd_trd`.
- 기존 필드 불변 · 입력 dict 불변 · 읽기 실패 시 필드 없음 · 외부 호출 0.
- 모두 tmp DB · tmp 캘린더(라이브 `state/` 를 열지 않는다).
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, api_market_topn_service, market_data_store
from app import market_refresh_service
from app.api_market_topn_service import kospi_display_state, with_kospi_display
from app.market_benchmark_store import (
    KOSPI_SOURCE,
    refresh_kospi_benchmark,
    upsert_benchmark_prices,
)
from app.market_briefing import calendar as _cal
from app.market_data_store import init_db, log_refresh
from tests.test_market_topn_api import _krx_kospi_until, _seed_kodex200_long_history

# 2026-09-24(목) · 09-25(금) 추석 연휴 — 실제 캘린더와 같은 모양의 tmp 캘린더.
HOLIDAYS = {"2026-09-24", "2026-09-25"}


def _write_calendar(dir_: Path) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    d = date(2026, 1, 1)
    days = []
    while d.year == 2026:
        iso = d.isoformat()
        if d.weekday() < 5 and iso not in HOLIDAYS:
            days.append(iso)
        d += timedelta(days=1)
    (dir_ / "krx_trading_days_2026.csv").write_text(
        "date,source\n" + "".join(f"{x},TEST\n" for x in days), encoding="utf-8"
    )
    return dir_


def _seed_kospi_until(db: Path, last: str, n_days: int = 120) -> None:
    end = date.fromisoformat(last)
    rows = []
    for i in range(n_days):
        d = end - timedelta(days=n_days - 1 - i)
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            rows.append((d.isoformat(), 2700.0 + i))
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=rows,
        source="Test",
        db_path=db,
    )


def _log_ks11(db: Path, *, ok: bool, error: str | None, run: str = "r1") -> None:
    """KOSPI 적재 기록 한 줄(이름은 OPS-02 그대로 · source 는 OPS-03 KRX)."""
    log_refresh(
        run_id=f"kospi-benchmark-{run}",
        source=KOSPI_SOURCE,
        asof="2026-09-22",
        attempted=1,
        success=1 if ok else 0,
        fail=0 if ok else 1,
        runtime_seconds=0.0,
        error_summary=error,
        db_path=db,
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "market_data.sqlite"
    init_db(p)
    return p


@pytest.fixture
def cal(tmp_path: Path) -> Path:
    return _write_calendar(tmp_path / "market_meta")


# ── 상태표 ────────────────────────────────────────────────────────────────────

FAILED = {"fail_count": 1, "error_summary": "ConnectionError: timeout"}
STALE_LOG = {
    "fail_count": 1,
    "error_summary": "source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4",
}
OK_LOG = {"fail_count": 0, "error_summary": None}


@pytest.mark.parametrize(
    "status,as_of,fresh,log,trading,expected",
    [
        # 저장 KOSPI 없음
        ("unavailable", None, False, None, True, "not_evaluated"),
        ("unavailable", None, False, FAILED, True, "source_failed"),
        ("unavailable", None, False, OK_LOG, True, "no_result"),
        ("unavailable", None, False, STALE_LOG, True, "no_result"),
        # 최신 아님
        ("stale", "2026-09-17", False, OK_LOG, True, "stale"),
        ("stale", "2026-09-17", False, STALE_LOG, True, "stale"),
        ("stale", "2026-09-17", False, FAILED, True, "source_failed"),
        # OPS-03 확정 계약 9 — T-2(옛 lag 1)는 더 이상 정상이 아니다.
        ("ok", "2026-09-22", False, OK_LOG, True, "stale"),
        ("stale", "2026-09-23", True, OK_LOG, True, "stale"),  # 운영 판정 stale 존중
        ("stale", "2026-09-17", False, OK_LOG, False, "stale"),  # 휴장일이어도 지연
        # 최신(기준일 == 기대 T-1)
        ("ok", "2026-09-23", True, OK_LOG, True, "ok"),
        ("ok", "2026-09-23", True, FAILED, True, "ok"),  # 최신이면 그 뒤 호출 실패 무관
        ("ok", "2026-09-23", True, None, True, "ok"),
        ("unavailable", "2026-09-23", True, OK_LOG, True, "no_result"),  # 수익률 미산출
        ("ok", "2026-09-23", True, OK_LOG, False, "holiday"),
    ],
)
def test_display_state_table(status, as_of, fresh, log, trading, expected) -> None:
    assert (
        kospi_display_state(
            status=status,
            as_of=as_of,
            is_fresh=fresh,
            last_refresh=log,
            today_is_trading_day=trading,
        )
        == expected
    )


# ── 적재 감지와 같은 lag ──────────────────────────────────────────────────────


def test_lag_is_the_c7_value_for_same_day_and_data(db: Path, cal: Path) -> None:
    """같은 날(09-28) · 같은 자료(09-17 까지 공개)로 적재 기록의 lag 와 화면 lag 가 같다."""
    res = refresh_kospi_benchmark(
        end_date=date(2026, 9, 28),
        fetcher=_krx_kospi_until("2026-09-17"),
        api_key="TEST-KEY",
        db_path=db,
        calendar_dir=cal,
    )
    assert res["status"] == "failed"
    assert res["error"] == (
        "source_stale:as_of=2026-09-17,expected=2026-09-23,lag=4,"
        "reason=no_rows@2026-09-18"
    )

    out = with_kospi_display(
        {"kospi": {"status": "stale", "as_of_date": "2026-09-17"}},
        db_path=db,
        today_kst="2026-09-28",
        calendar_dir=cal,
    )
    assert out["kospi"]["trading_day_lag"] == 4
    assert out["kospi"]["display_state"] == "stale"


# ── 선택 필드 덧붙이기 (tmp DB · tmp 캘린더) ─────────────────────────────────


def _kospi(status: str, as_of: str | None) -> dict:
    return {"status": status, "as_of_date": as_of, "freshness": {"lag_trading_days": 2}}


def test_pc_today_shape_is_stale_with_calendar_lag(db: Path, cal: Path) -> None:
    """PC 실측 모양(2026-09-28): KOSPI 09-17 · 마지막 KS11 적재 09-22 성공(C7 이전 기록)."""
    _log_ks11(db, ok=True, error=None)
    ctx = {
        "status": "partial",
        "warnings": ["w"],
        "kospi": _kospi("stale", "2026-09-17"),
    }
    before = copy.deepcopy(ctx)
    out = with_kospi_display(ctx, db_path=db, today_kst="2026-09-28", calendar_dir=cal)
    assert ctx == before  # 입력 dict 불변
    k = out["kospi"]
    assert (k["display_state"], k["trading_day_lag"], k["today_is_trading_day"]) == (
        "stale",
        4,
        True,
    )
    # 기존 필드 불변 — KODEX200 축 lag(freshness)도 그대로 두되 화면 lag 와 섞지 않는다.
    assert {x: v for x, v in k.items() if x not in _NEW} == before["kospi"]
    assert {x: v for x, v in out.items() if x != "kospi"} == {
        x: v for x, v in before.items() if x != "kospi"
    }


_NEW = {"display_state", "trading_day_lag", "today_is_trading_day"}


@pytest.mark.parametrize(
    "log,expected",
    [
        ((True, "source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4"), "stale"),
        ((False, "source_stale:as_of=2026-09-17,ref=2026-09-23,lag=4"), "stale"),
        ((False, "ConnectionError: timeout"), "source_failed"),
        ((False, "no_data"), "source_failed"),
    ],
)
def test_stale_vs_fetch_failure_from_latest_ks11_log(db, cal, log, expected) -> None:
    _log_ks11(db, ok=True, error=None, run="old")
    _log_ks11(db, ok=log[0], error=log[1], run="new")
    out = with_kospi_display(
        {"kospi": _kospi("stale", "2026-09-17")},
        db_path=db,
        today_kst="2026-09-28",
        calendar_dir=cal,
    )
    assert out["kospi"]["display_state"] == expected


def test_no_data_states(db: Path, cal: Path) -> None:
    base = {"kospi": {"status": "unavailable"}}
    kw = dict(db_path=db, today_kst="2026-09-28", calendar_dir=cal)
    assert with_kospi_display(base, **kw)["kospi"]["display_state"] == "not_evaluated"
    _log_ks11(db, ok=True, error=None, run="a")
    assert with_kospi_display(base, **kw)["kospi"]["display_state"] == "no_result"
    _log_ks11(db, ok=False, error="RuntimeError: boom", run="b")
    k = with_kospi_display(base, **kw)["kospi"]
    assert (k["display_state"], k["trading_day_lag"]) == ("source_failed", None)


def test_holiday_with_previous_trading_day_data_is_not_stale(
    db: Path, cal: Path
) -> None:
    """추석 연휴 중 일요일(09-27) · 직전 거래일(09-23) 자료 → 휴장일 · 지연 0."""
    _log_ks11(db, ok=True, error=None)
    k = with_kospi_display(
        {"kospi": _kospi("ok", "2026-09-23")},
        db_path=db,
        today_kst="2026-09-27",
        calendar_dir=cal,
    )["kospi"]
    assert (k["display_state"], k["trading_day_lag"], k["today_is_trading_day"]) == (
        "holiday",
        0,
        False,
    )
    # 평일 휴장(09-24)도 캘린더로 잡는다.
    k = with_kospi_display(
        {"kospi": _kospi("ok", "2026-09-23")},
        db_path=db,
        today_kst="2026-09-24",
        calendar_dir=cal,
    )["kospi"]
    assert (k["display_state"], k["today_is_trading_day"]) == ("holiday", False)


def test_read_failure_adds_nothing(tmp_path: Path, cal: Path) -> None:
    bad = tmp_path / "is_a_dir"
    bad.mkdir()
    ctx = {"kospi": _kospi("stale", "2026-09-17")}
    out = with_kospi_display(ctx, db_path=bad, today_kst="2026-09-28", calendar_dir=cal)
    assert out == ctx
    assert not (_NEW & set(out["kospi"]))


def test_non_dict_context_passes_through(db: Path) -> None:
    assert with_kospi_display(None, db_path=db) is None
    assert with_kospi_display({"kospi": None}, db_path=db) == {"kospi": None}


# ── GET /market/topn/latest 관통 ─────────────────────────────────────────────


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing(db_path=fake_db)
    monkeypatch.setattr(_cal, "CALENDAR_DIR", _write_calendar(tmp_path / "market_meta"))
    monkeypatch.setattr(api_market_topn_service, "_kst_today", lambda: "2026-09-28")
    return TestClient(api_module.app)


def _no_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import market_data_fdr

    def boom(*a, **k):
        raise AssertionError("외부 호출 금지")

    for name in (
        "refresh_etf_universe",
        "refresh_price_history",
        "_default_price_fetcher",
    ):
        monkeypatch.setattr(market_data_fdr, name, boom)


def test_topn_latest_carries_kospi_display_fields(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PC 실측 모양: KODEX200 09-21 · KOSPI 09-17 · KS11 적재 09-22 성공 → 기준일 지연 · 4거래일."""
    _no_external_calls(monkeypatch)
    db = api_market_topn.DEFAULT_DB_PATH
    _seed_kodex200_long_history(db, date(2026, 9, 21), n_days=120)
    _seed_kospi_until(db, "2026-09-17")
    _log_ks11(db, ok=True, error=None)

    ctx = api_client.get("/market/topn/latest").json()["market_context"]
    k = ctx["kospi"]
    assert k["status"] == "stale"  # 운영 판정 그대로
    assert k["as_of_date"] == "2026-09-17"
    assert (k["display_state"], k["trading_day_lag"], k["today_is_trading_day"]) == (
        "stale",
        4,
        True,
    )
    # 응답의 warnings 는 그대로(화면에서만 숨긴다) — 기존 필드 의미 불변.
    assert any(w.startswith("KOSPI benchmark is stale") for w in ctx["warnings"])


def test_topn_latest_fields_are_optional_when_unreadable(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """표시 보조 읽기가 실패해도 응답은 그대로 나오고 새 필드만 null 이다."""
    db = api_market_topn.DEFAULT_DB_PATH
    _seed_kodex200_long_history(db, date(2026, 9, 21), n_days=120)
    _seed_kospi_until(db, "2026-09-17")

    def boom(*a, **k):
        raise RuntimeError("read failed")

    monkeypatch.setattr(api_market_topn_service, "latest_refresh_log", boom)
    res = api_client.get("/market/topn/latest")
    assert res.status_code == 200
    k = res.json()["market_context"]["kospi"]
    assert k["status"] == "stale"
    assert k["display_state"] is None and k["trading_day_lag"] is None
    assert k["today_is_trading_day"] is None
