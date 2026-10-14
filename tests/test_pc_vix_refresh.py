"""POC5-11 — PC 수동 갱신의 VIX(시장 불안 지표) 단계 (PLAN §1 · §6 · 설계자 판정 Q2 · Q3 · §3 · §4).

격리 DB(tmp) · 가짜 수집기(`sys.modules['FinanceDataReader']` 교체)만 쓴다. 외부 호출 0.
conftest 의 기본 stub(`market_refresh_service.refresh_pc_vix` → 성공 · 문구 없음)은 서비스 시험에서
진짜 `app.pc_vix_refresh.refresh_pc_vix` 로 되돌려 놓는다 — 기본 stub 이 이 경계 시험을 가리지 않게.
"""

from __future__ import annotations

import sqlite3
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
import requests

from app import market_benchmark_batch, market_refresh_service, pc_vix_refresh
from app.market_benchmark_store import (
    fetch_existing_benchmark_close_map,
    latest_benchmark_date,
    upsert_benchmark_prices,
)
from app.market_data_store import latest_refresh_log
from app.market_refresh_service import (
    get_state_snapshot,
    reset_state_for_testing,
    start_refresh_job,
)
from app.pc_vix_refresh import (
    VIX_STEP_FAILED_TEXT,
    last_settled_us_date,
    refresh_pc_vix,
)
from scripts._market_refresh import vix_ingest

# 한국 시각 2026-10-14(수) 03:00 = 미국 동부 10-13(화) 14:00 — 미국 10-13 장중.
NIGHT_KST_UTC = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)
# 한국 시각 2026-10-14(수) 07:00 = 미국 동부 10-13(화) 18:00 — 10-13 마감 뒤.
MORNING_KST_UTC = datetime(2026, 10, 13, 22, 0, tzinfo=timezone.utc)


class FakeVixReader:
    """가짜 `fdr.DataReader('VIX', start, end)`.

    Yahoo 범위 규칙 일부를 흉내 낸다: 끝 날짜(로컬 자정)보다 앞선 평일 행만 돌려준다
    (FDR 의 '시작 = 끝이면 끝을 하루 늘림' 규칙은 흉내 내지 않음).
    `closes` 에 날짜별 값을 주면 그 값을 쓰고(진행 중 세션 · 확정 값 구분), 없으면 20.0.
    """

    def __init__(
        self, closes: dict[str, float] | None = None, raises: Exception | None = None
    ):
        self.closes = closes or {}
        self.raises = raises
        self.calls: list[tuple[str, date, date]] = []

    def __call__(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        if self.raises is not None:
            raise self.raises
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        days = [d for d in days if d.weekday() < 5]
        idx = pd.to_datetime([d.isoformat() for d in days])
        return pd.DataFrame(
            {"Close": [self.closes.get(d.isoformat(), 20.0) for d in days]}, index=idx
        )


@pytest.fixture
def fake_fdr(monkeypatch: pytest.MonkeyPatch):
    holder: dict = {}

    def install(reader: FakeVixReader) -> FakeVixReader:
        monkeypatch.setitem(
            sys.modules, "FinanceDataReader", types.SimpleNamespace(DataReader=reader)
        )
        holder["reader"] = reader
        return reader

    return install


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch):
    """`run_vix_ingest` 의 `date.today()`(PC 로컬 날짜)를 고정한다."""

    def install(d: date) -> None:
        class _D(date):
            @classmethod
            def today(cls):  # noqa: D401
                return d

        monkeypatch.setattr(vix_ingest, "date", _D)

    return install


def _seed_vix(db: Path, through: date, n: int = 5, value: float = 18.0) -> None:
    rows = []
    d = through
    while len(rows) < n:
        if d.weekday() < 5:
            rows.append((d.isoformat(), value))
        d -= timedelta(days=1)
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=rows,
        source="FDR_VIX",
        db_path=db,
    )


# ── 미국 마감 기준일 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("now_utc", "expected"),
    [
        (NIGHT_KST_UTC, date(2026, 10, 12)),  # 미국 10-13 장중 → 전날까지
        (MORNING_KST_UTC, date(2026, 10, 13)),  # 미국 10-13 마감 뒤
        (
            datetime(2026, 10, 13, 20, 29, tzinfo=timezone.utc),
            date(2026, 10, 12),
        ),  # 16:29 EDT
        (
            datetime(2026, 10, 13, 20, 30, tzinfo=timezone.utc),
            date(2026, 10, 13),
        ),  # 16:30 EDT
        (
            datetime(2026, 12, 15, 21, 29, tzinfo=timezone.utc),
            date(2026, 12, 14),
        ),  # 16:29 EST
        (
            datetime(2026, 12, 15, 21, 30, tzinfo=timezone.utc),
            date(2026, 12, 15),
        ),  # 16:30 EST
    ],
)
def test_last_settled_us_date(now_utc: datetime, expected: date) -> None:
    assert last_settled_us_date(now_utc) == expected


# ── 판정 §3 — 미확정 자료 저장 가능성(기본 경로) · PC 경로 보완 ─────────────────
def test_default_path_stores_in_progress_session_and_never_fixes_it(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    """기본(max_date 없음 · CLI · OCI) 경로의 실제 가능성 확인 — 한국 새벽 갱신이면 진행 중인
    미국 세션 값이 저장되고, 다음 증분은 그 다음 날부터라 그 값은 다시 고쳐지지 않는다."""
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 12))
    fixed_today(
        date(2026, 10, 14)
    )  # 한국 10-14 새벽 → 조회 끝 10-14(로컬 자정) → 10-13 행 포함
    fake_fdr(FakeVixReader({"2026-10-13": 30.0}))  # 10-13 은 장중 값
    assert vix_ingest.run_vix_ingest(db) == 0
    assert fetch_existing_benchmark_close_map("VIX", db_path=db)["2026-10-13"] == 30.0
    # 다음 날 확정 값(31.5)을 주는 원천이어도 10-14 부터만 받는다.
    fixed_today(date(2026, 10, 15))
    fake_fdr(FakeVixReader({"2026-10-13": 31.5}))
    assert vix_ingest.run_vix_ingest(db) == 0
    assert fetch_existing_benchmark_close_map("VIX", db_path=db)["2026-10-13"] == 30.0


def test_pc_path_skips_unsettled_session_then_takes_settled_value(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 12))
    fixed_today(date(2026, 10, 14))
    fake_fdr(FakeVixReader({"2026-10-13": 30.0}))
    assert (
        refresh_pc_vix(db_path=db, now_utc=NIGHT_KST_UTC) is None
    )  # 저장할 확정 행 없음 = 정상
    assert "2026-10-13" not in fetch_existing_benchmark_close_map("VIX", db_path=db)
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-12"
    # 미국 마감 뒤(한국 아침) — 확정 값으로 받는다.
    fake_fdr(FakeVixReader({"2026-10-13": 31.5}))
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) is None
    assert fetch_existing_benchmark_close_map("VIX", db_path=db)["2026-10-13"] == 31.5


def test_pc_path_stores_settled_rows_but_drops_the_in_progress_one(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    """마지막 저장일이 오래돼 받은 행이 기준일을 넘어설 때 — 확정 날짜까지만 저장한다."""
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 8))
    fixed_today(date(2026, 10, 14))
    fake_fdr(FakeVixReader({"2026-10-13": 30.0}))  # 10-09 ~ 10-13(장중) 을 돌려줌
    assert refresh_pc_vix(db_path=db, now_utc=NIGHT_KST_UTC) is None
    stored = fetch_existing_benchmark_close_map("VIX", db_path=db)
    assert "2026-10-12" in stored and "2026-10-09" in stored
    assert "2026-10-13" not in stored
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-12"


# ── 성공 · 이미 최신 · 충돌 · 조회 예외 · timeout ─────────────────────────────
def test_success_adds_rows_without_message(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 9, 11))
    fixed_today(date(2026, 10, 14))
    fake_fdr(FakeVixReader())
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) is None
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-13"


def test_already_up_to_date_does_not_fetch(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 13))
    fixed_today(date(2026, 10, 14))
    reader = fake_fdr(FakeVixReader())
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) is None
    assert reader.calls == []


def test_conflict_does_not_overwrite_and_returns_message(
    tmp_path: Path, fake_fdr, fixed_today, monkeypatch, caplog
) -> None:
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 9), value=18.0)
    fixed_today(date(2026, 10, 14))

    class Overlap(FakeVixReader):
        def __call__(self, symbol, start, end):
            # 이미 저장된 10-09 를 다른 값으로 함께 돌려주는 원천.
            return super().__call__(symbol, date(2026, 10, 9), end)

    fake_fdr(Overlap({"2026-10-09": 99.0}))
    caplog.set_level("WARNING", logger="app.pc_vix_refresh")
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) == VIX_STEP_FAILED_TEXT
    assert fetch_existing_benchmark_close_map("VIX", db_path=db)["2026-10-09"] == 18.0
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-09"
    # error 가 없어도(rc 2 · error=None) 실패로 남기고 exit_code 를 로그에 둔다.
    assert "status=failed exit_code=2" in caplog.text


def test_fetch_exception_returns_message(tmp_path: Path, fake_fdr, fixed_today) -> None:
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 9))
    fixed_today(date(2026, 10, 14))
    fake_fdr(FakeVixReader(raises=RuntimeError("boom")))
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) == VIX_STEP_FAILED_TEXT
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-09"


def test_timeout_is_applied_to_vix_request_and_restored(
    tmp_path: Path, fake_fdr, fixed_today, monkeypatch
) -> None:
    """판정 Q2 — VIX 조회의 `requests` 호출에 20초 timeout 이 들어가고, timeout 이 나도 블록을 빠져나오면
    원래 함수로 되돌아간다. 실제 20초를 기다리지 않는다(가짜 전송이 바로 Timeout 을 낸다)."""
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 9))
    fixed_today(date(2026, 10, 14))
    seen: list = []

    def transport(self, method, url, *args, **kwargs):
        seen.append(kwargs.get("timeout"))
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr(requests.Session, "request", transport)

    def reader(symbol, start, end):
        requests.get("https://example.invalid/vix")  # FDR Yahoo 와 같은 호출 형태
        raise AssertionError("unreachable")

    fake_fdr(reader)
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) == VIX_STEP_FAILED_TEXT
    assert seen == [20.0]
    assert requests.Session.request is transport  # 블록 밖 = 원래 함수


def test_timeout_wrapper_restored_after_success_too(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    original = requests.Session.request
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 9))
    fixed_today(date(2026, 10, 14))
    inside: list = []

    def reader(symbol, start, end):
        inside.append(requests.Session.request is not original)
        return FakeVixReader()(symbol, start, end)

    fake_fdr(reader)
    assert refresh_pc_vix(db_path=db, now_utc=MORNING_KST_UTC) is None
    assert inside == [True]
    assert requests.Session.request is original


# ── 공유 함수 기본 경로 불변(OCI) · DB 경로 전달 ──────────────────────────────
def test_refresh_vix_default_call_is_unchanged(monkeypatch, tmp_path: Path) -> None:
    calls: list = []
    monkeypatch.setattr(
        vix_ingest, "run_vix_ingest", lambda *a, **k: calls.append((a, k)) or 0
    )
    market_benchmark_batch.refresh_vix(db_path=tmp_path / "x.sqlite")
    assert calls == [((tmp_path / "x.sqlite",), {})]  # OCI 배치와 같은 호출(인자 하나)


def test_pc_step_passes_db_path_and_settled_date(monkeypatch, tmp_path: Path) -> None:
    got: list = []

    def spy(**kw):
        got.append(kw)
        return {
            "status": "ok",
            "as_of_date": "2026-10-13",
            "exit_code": 0,
            "error": None,
        }

    monkeypatch.setattr(pc_vix_refresh, "refresh_vix", spy)
    assert refresh_pc_vix(db_path=tmp_path / "pc.sqlite", now_utc=NIGHT_KST_UTC) is None
    assert got == [{"db_path": tmp_path / "pc.sqlite", "max_date": date(2026, 10, 12)}]


# ── 서비스 통합(가짜 ETF 수집 · 진짜 VIX 단계 · 가짜 VIX 원천) ────────────────
def _universe_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": "069500",
                "Category": 1,
                "Name": "KODEX 200",
                "Price": 1.0,
                "Volume": 1,
                "MarCap": 1.0,
            }
        ]
    )


def _price_fetcher(ticker, start, end):
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    idx = pd.to_datetime([d.isoformat() for d in days])
    n = len(days)
    return pd.DataFrame(
        {
            "Open": [1.0] * n,
            "High": [1.0] * n,
            "Low": [1.0] * n,
            "Close": [1.0] * n,
            "Volume": [1] * n,
            "Change": [0.0] * n,
        },
        index=idx,
    )


@pytest.fixture
def service_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr("app.market_data_store.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr("app.market_refresh_service.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr(
        "app.market_briefing.calendar.CALENDAR_DIR", tmp_path / "no_cal"
    )
    monkeypatch.setattr(
        market_refresh_service, "_regenerate_intraday_config", lambda db_path: None
    )
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_kospi_benchmark",
        lambda **kw: {"status": "ok", "error": None},
    )
    monkeypatch.setattr(
        market_refresh_service, "refresh_nav_universe", lambda **kw: None
    )
    monkeypatch.setattr(
        market_refresh_service, "_write_nav_refresh_summary", lambda s: None
    )
    monkeypatch.setattr(
        market_refresh_service, "refresh_holdings_equity_prices", lambda **kw: None
    )
    # conftest 기본 stub 대신 진짜 VIX 단계(가짜 원천은 시험마다).
    monkeypatch.setattr(market_refresh_service, "refresh_pc_vix", refresh_pc_vix)
    monkeypatch.setattr(market_refresh_service, "_utcnow", lambda: MORNING_KST_UTC)
    reset_state_for_testing(db_path=db)
    return db


def _run(db: Path, cooldown: int = 6):
    return start_refresh_job(
        db_path=db,
        cooldown_hours=cooldown,
        universe_fetcher=_universe_df,
        price_fetcher=_price_fetcher,
        end_date_for_prices=date(2026, 10, 13),
        thread_runner=lambda runner: runner(),
    )


def _log_rows(db: Path) -> list[tuple]:
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT run_id, source, error_summary FROM market_refresh_log ORDER BY rowid"
        ).fetchall()
    finally:
        con.close()


def test_service_success_writes_vix_to_pc_db_and_keeps_records(
    service_db: Path, fake_fdr, fixed_today
) -> None:
    _seed_vix(service_db, date(2026, 9, 11))
    fixed_today(date(2026, 10, 14))
    fake_fdr(FakeVixReader())
    _run(service_db)
    snap = get_state_snapshot(db_path=service_db)
    assert snap.status == "completed"
    assert snap.error_summary is None
    assert latest_benchmark_date("VIX", db_path=service_db) == "2026-10-13"
    # 기록 행은 ETF 목록 · 가격 · KOSPI 세 줄 그대로(VIX 행 없음) · '마지막 전체 갱신'은 예전과 같은 KOSPI 행.
    rows = _log_rows(service_db)
    assert [r[1] for r in rows] == [
        "FinanceDataReader/universe",
        "FinanceDataReader/prices",
        "KRX_OPEN_API/idx_kospi_dd_trd",
    ]
    assert all("vix" not in (r[0] + r[1]).lower() for r in rows)
    assert latest_refresh_log(db_path=service_db)["run_id"].startswith(
        "kospi-benchmark-"
    )


def test_service_vix_failure_appends_text_and_next_run_is_possible(
    service_db: Path, fake_fdr, fixed_today
) -> None:
    _seed_vix(service_db, date(2026, 10, 9))
    fixed_today(date(2026, 10, 14))
    fake_fdr(FakeVixReader(raises=RuntimeError("boom")))
    _run(service_db)
    snap = get_state_snapshot(db_path=service_db)
    assert snap.status == "completed"  # ETF 결과로 판정 · VIX 실패가 지우지 않음
    assert snap.error_summary == VIX_STEP_FAILED_TEXT
    assert latest_benchmark_date("VIX", db_path=service_db) == "2026-10-09"
    con = sqlite3.connect(str(service_db))
    try:
        assert con.execute("SELECT COUNT(*) FROM etf_daily_price").fetchone()[0] > 0
    finally:
        con.close()
    # running 에 남지 않아 다음 수동 갱신이 돈다(쿨다운 0 으로 즉시 재실행).
    fake_fdr(FakeVixReader())
    res = _run(service_db, cooldown=0)
    assert res.status == "accepted"
    assert get_state_snapshot(db_path=service_db).error_summary is None
    assert latest_benchmark_date("VIX", db_path=service_db) == "2026-10-13"


def test_service_vix_step_exception_is_isolated(service_db: Path, monkeypatch) -> None:
    def boom(**kw):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(market_refresh_service, "refresh_pc_vix", boom)
    _run(service_db)
    snap = get_state_snapshot(db_path=service_db)
    assert snap.status == "completed"
    assert snap.error_summary == VIX_STEP_FAILED_TEXT


@pytest.mark.parametrize(
    ("equity_msg", "vix_fail", "expected"),
    [
        (None, False, None),
        (
            "보유 개별주 가격 갱신 실패(1종목)",
            False,
            "보유 개별주 가격 갱신 실패(1종목)",
        ),
        (None, True, VIX_STEP_FAILED_TEXT),
        (
            "보유 개별주 가격 갱신 실패(1종목)",
            True,
            "보유 개별주 가격 갱신 실패(1종목) · " + VIX_STEP_FAILED_TEXT,
        ),
    ],
)
def test_service_message_order(
    service_db: Path, monkeypatch, equity_msg, vix_fail, expected
) -> None:
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_holdings_equity_prices",
        lambda **kw: equity_msg,
    )
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_pc_vix",
        lambda **kw: VIX_STEP_FAILED_TEXT if vix_fail else None,
    )
    _run(service_db)
    assert get_state_snapshot(db_path=service_db).error_summary == expected


# ── 검토 반영(2026-10-14) — 주말 · 단계 순서 · 쿨다운 · 다른 단계 실패와 겹침 ───────────
class MustNotFetch(FakeVixReader):
    def __call__(self, symbol, start, end):
        raise AssertionError(f"주말만 남았는데 조회했다: {start} ~ {end}")


@pytest.mark.parametrize(
    "now_utc",
    [
        datetime(
            2026, 10, 10, 1, 0, tzinfo=timezone.utc
        ),  # 한국 일 10:00 = 미국 금 21:00
        datetime(
            2026, 10, 11, 22, 0, tzinfo=timezone.utc
        ),  # 한국 월 07:00 = 미국 일 18:00
        datetime(
            2026, 10, 12, 7, 0, tzinfo=timezone.utc
        ),  # 한국 월 16:00 = 미국 월 03:00
    ],
)
def test_weekend_only_range_is_up_to_date_not_failure(
    tmp_path: Path, fake_fdr, fixed_today, now_utc
) -> None:
    """금요일 값이 저장된 뒤 주말 · 월요일 장 전 갱신 — 새 미국 거래일이 없으니 실패 문구를 내지 않는다."""
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 9))  # 금
    fixed_today(date(2026, 10, 12))
    fake_fdr(MustNotFetch())
    assert refresh_pc_vix(db_path=db, now_utc=now_utc) is None
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-09"


def test_after_monday_close_fetches_monday(
    tmp_path: Path, fake_fdr, fixed_today
) -> None:
    db = tmp_path / "m.sqlite"
    _seed_vix(db, date(2026, 10, 9))
    fixed_today(date(2026, 10, 13))
    fake_fdr(FakeVixReader())
    now = datetime(
        2026, 10, 12, 22, 0, tzinfo=timezone.utc
    )  # 한국 화 07:00 = 미국 월 18:00
    assert refresh_pc_vix(db_path=db, now_utc=now) is None
    assert latest_benchmark_date("VIX", db_path=db) == "2026-10-12"


@pytest.mark.parametrize("vix_mode", ["ok", "fail", "raise"])
def test_service_step_order_and_nav_runs_after_vix(
    service_db: Path, monkeypatch, vix_mode
) -> None:
    calls: list[str] = []

    def rec(name, ret=None):
        def f(**kw):
            calls.append(name)
            return ret

        return f

    def vix(**kw):
        calls.append("vix")
        if vix_mode == "raise":
            raise RuntimeError("boom")
        return VIX_STEP_FAILED_TEXT if vix_mode == "fail" else None

    monkeypatch.setattr(
        market_refresh_service, "refresh_holdings_equity_prices", rec("equity")
    )
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_kospi_benchmark",
        rec("kospi", {"status": "ok", "error": None}),
    )
    monkeypatch.setattr(market_refresh_service, "refresh_pc_vix", vix)
    monkeypatch.setattr(market_refresh_service, "refresh_nav_universe", rec("nav"))
    _run(service_db)
    assert calls == ["equity", "kospi", "vix", "nav"]
    snap = get_state_snapshot(db_path=service_db)
    assert snap.status == "completed"
    assert snap.error_summary == (None if vix_mode == "ok" else VIX_STEP_FAILED_TEXT)


def test_vix_only_failure_keeps_existing_six_hour_cooldown(
    service_db: Path, monkeypatch
) -> None:
    """VIX 만 실패하면 갱신은 completed(ETF 성공)라 기존 6시간 쿨다운이 걸린다(기존 규칙 · 이번 무변경)."""
    monkeypatch.setattr(
        market_refresh_service, "refresh_pc_vix", lambda **kw: VIX_STEP_FAILED_TEXT
    )
    _run(service_db)
    assert get_state_snapshot(db_path=service_db).status == "completed"
    again = _run(service_db, cooldown=6)
    assert again.status == "skipped_cooldown"


@pytest.mark.parametrize(
    ("etf_fail", "kospi_fail", "expected_head"),
    [
        (True, False, "price_partial_failure: fail=1"),
        (False, True, "kospi_benchmark_unavailable: down"),
        (
            True,
            True,
            "price_partial_failure: fail=1",
        ),  # KOSPI 문구는 앞 사유가 없을 때만(기존 규칙)
    ],
)
def test_vix_text_follows_existing_etf_and_kospi_reasons(
    service_db: Path, monkeypatch, etf_fail, kospi_fail, expected_head
) -> None:
    def universe():
        return pd.DataFrame(
            [
                {
                    "Symbol": t,
                    "Category": 1,
                    "Name": t,
                    "Price": 1.0,
                    "Volume": 1,
                    "MarCap": 1.0,
                }
                for t in ("069500", "111111")
            ]
        )

    def prices(ticker, start, end):
        if etf_fail and ticker == "111111":
            raise RuntimeError("boom")
        return _price_fetcher(ticker, start, end)

    if kospi_fail:
        monkeypatch.setattr(
            market_refresh_service,
            "refresh_kospi_benchmark",
            lambda **kw: {"status": "failed", "error": "down"},
        )
    monkeypatch.setattr(
        market_refresh_service, "refresh_pc_vix", lambda **kw: VIX_STEP_FAILED_TEXT
    )
    start_refresh_job(
        db_path=service_db,
        cooldown_hours=6,
        universe_fetcher=universe,
        price_fetcher=prices,
        end_date_for_prices=date(2026, 10, 13),
        thread_runner=lambda runner: runner(),
    )
    snap = get_state_snapshot(db_path=service_db)
    assert snap.error_summary == f"{expected_head} · {VIX_STEP_FAILED_TEXT}"
