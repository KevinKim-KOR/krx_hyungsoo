"""POC3-02D-OPS-03 — KOSPI 공식 자료원(KRX `idx/kospi_dd_trd`) · 같은 최신성 함수.

설계자 PLAN 판정(2026-09-29) 확정 계약 9 · 13 · 검증 시나리오 7(KOSPI 만 실패).

- 자료원: 저장 최신일(포함)부터 기대 T-1 까지 날짜당 1회 · 빈 날을 만들지 않는다.
- 09-17 정정: 덮어쓰기 **전에** 기존 값 · source · 행 hash 를 증거 JSON 에 남긴다 ·
  증거를 못 남기면 쓰지 않는다 · 전후 건수 · 값을 기록한다.
- 최신 = `kospi_as_of == expected_previous_trading_day` — 배치 · 계산 · API 가 같은 함수.
- KOSPI 만 실패하면 Telegram 고지 없음(PC 전용).

외부 조회 0건(KRX 대역 fetcher) · 라이브 DB · state · logs 미접근(tmp DB · tmp 캘린더).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, api_market_topn_service, market_benchmark_freshness
from app import market_benchmark_store as store
from app import market_data_store, market_refresh_service, market_regime
from app.api_market_topn_service import kospi_display_state, with_kospi_display
from app.market_benchmark_freshness import kospi_freshness
from app.market_briefing import calendar as _cal
from app.market_briefing import krx_sync
from app.market_regime import compute_kospi_metrics
from tests.test_market_topn_api import (
    _seed_kodex200_long_history,
    _seed_kospi_long_history,
)

KEY = "TEST-KEY-DO-NOT-LOG"
FDR = "FinanceDataReader/KS11"
KRX = store.KOSPI_SOURCE
# 2026-09-24(목) · 25(금) 추석 연휴 — 실제 캘린더와 같은 모양.
HOLIDAYS = {"2026-09-24", "2026-09-25"}
# KRX 공식 종가(PLAN STEP 1-6 실측 · 09-15 ~ 09-17 · 09-28). 나머지는 합성값.
OFFICIAL = {
    "2026-09-15": 6627.26,
    "2026-09-16": 6717.97,
    "2026-09-17": 6715.41,
    "2026-09-18": 6894.23,
    "2026-09-21": 7007.72,
    "2026-09-22": 6950.10,
    "2026-09-23": 6901.55,
    "2026-09-28": 6889.74,
    "2026-09-29": 6912.30,
}


def _write_calendar(dir_: Path) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    d, days = date(2026, 1, 1), []
    while d.year == 2026:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            days.append(d.isoformat())
        d += timedelta(days=1)
    (dir_ / "krx_trading_days_2026.csv").write_text(
        "date,source\n" + "".join(f"{x},TEST\n" for x in days), encoding="utf-8"
    )
    return dir_


class FakeKrx:
    """KRX `idx/kospi_dd_trd` 대역 — 호출을 기록하고 `published` 날짜만 준다."""

    def __init__(self, published=None, *, raise_on=(), override=None):
        self.published = dict(OFFICIAL if published is None else published)
        self.raise_on = set(raise_on)
        self.override = dict(override or {})
        self.calls: list[str] = []

    def __call__(self, bas_dd: str, key: str) -> list[dict]:
        assert key == KEY
        self.calls.append(bas_dd)
        iso = f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:]}"
        if iso in self.raise_on:
            raise ConnectionError("krx down")
        if iso in self.override:
            return self.override[iso]
        if iso not in self.published:
            return []  # 공개 전 · 당일 조회 — 행 0
        return [
            {"BAS_DD": bas_dd, "IDX_NM": "코스피 200", "CLSPRC_IDX": "900.12"},
            {
                "BAS_DD": bas_dd,
                "IDX_NM": "코스피",
                "CLSPRC_IDX": f"{self.published[iso]:,.2f}",
            },
            {"BAS_DD": bas_dd, "IDX_NM": "코스피 100", "CLSPRC_IDX": "3000.00"},
        ]


@pytest.fixture
def cal(tmp_path: Path) -> Path:
    return _write_calendar(tmp_path / "market_meta")


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "market_data.sqlite"
    market_data_store.init_db(p)
    return p


def _seed(db: Path, rows: dict, source: str) -> None:
    store.upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=sorted(rows.items()),
        source=source,
        db_path=db,
    )


def _refresh(db, cal, fake, today="2026-09-30", **kw):
    kw.setdefault("evidence_dir", db.parent / "evidence")
    return store.refresh_kospi_benchmark(
        end_date=date.fromisoformat(today),
        fetcher=fake,
        api_key=KEY,
        db_path=db,
        calendar_dir=cal,
        **kw,
    )


def _pc_shape(db: Path) -> dict:
    """PC · OCI 실측 모양 — FDR KS11 이 09-17 12:22 KST 장중 값에서 멈췄다."""
    rows = {"2026-09-15": 6627.26, "2026-09-16": 6717.97, "2026-09-17": 6724.34}
    _seed(db, rows, FDR)
    return store._kospi_rows(db)


# ── 09-17 정정 절차 (확정 계약 9 ①~④) ────────────────────────────────────────


def test_first_run_corrects_0917_with_evidence_and_fills_to_t1(db, cal) -> None:
    before = _pc_shape(db)
    fake = FakeKrx()
    res = _refresh(db, cal, fake)

    # 저장 최신일(09-17 · 포함)부터 기대 T-1(09-29)까지 거래일마다 1회 · 휴장일 없음.
    assert fake.calls == [
        "20260917",
        "20260918",
        "20260921",
        "20260922",
        "20260923",
        "20260928",
        "20260929",
    ]
    assert res["calls"] == 7 and res["status"] == "ok" and res["error"] is None
    assert (res["as_of_date"], res["expected_as_of_date"]) == ("2026-09-29",) * 2
    assert res["corrections"] == [
        {
            "date": "2026-09-17",
            "old_close": 6724.34,
            "new_close": 6715.41,
            "old_source": FDR,
        }
    ]
    assert res["replaced"] == 1 and res["rows_written"] == 7
    assert res["before"] == {"rows": 3, "as_of": "2026-09-17"}
    assert res["after"] == {"rows": 9, "as_of": "2026-09-29"}

    # ① 기존 값 · source · hash 보존 — 증거 JSON.
    ev = json.loads(Path(res["evidence_path"]).read_text(encoding="utf-8"))
    (change,) = ev["changes"]
    old = before["2026-09-17"]
    expected_hash = hashlib.sha256(
        json.dumps(
            {"benchmark_id": "KOSPI", **old}, sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    assert change["old_close"] == 6724.34 and change["old_source"] == FDR
    assert change["old_created_at"] == old["created_at"]
    assert change["old_row_hash"] == expected_hash
    assert change["new_close"] == 6715.41 and change["value_changed"] is True
    # ④ 전후 건수 · 값 · read-back.
    assert ev["before"] == {"rows": 3, "as_of": "2026-09-17"}
    assert ev["after"] == {"rows": 9, "as_of": "2026-09-29"}
    assert ev["stage"] == "after_write" and ev["readback_ok"] is True
    assert ev["after_rows"][0]["close"] == 6715.41
    assert ev["after_rows"][0]["source"] == KRX
    assert ev["new_dates"] == [
        "2026-09-18",
        "2026-09-21",
        "2026-09-22",
        "2026-09-23",
        "2026-09-28",
        "2026-09-29",
    ]

    # ③ 공식 종가로 정정 · 조회하지 않은 앞 날짜는 그대로(이미 공식값과 일치).
    rows = store._kospi_rows(db)
    assert (rows["2026-09-17"]["close"], rows["2026-09-17"]["source"]) == (
        6715.41,
        KRX,
    )
    assert rows["2026-09-16"] == before["2026-09-16"]
    assert rows["2026-09-15"] == before["2026-09-15"]


def test_evidence_is_written_before_the_overwrite(db, cal, monkeypatch) -> None:
    """저장이 실패해도 증거는 이미 남아 있다 — 순서: 증거 → 덮어쓰기."""
    _pc_shape(db)

    def boom(**kw):
        raise RuntimeError("disk")

    monkeypatch.setattr(store, "upsert_benchmark_prices", boom)
    res = _refresh(db, cal, FakeKrx())
    assert (res["status"], res["error"]) == ("failed", "store:RuntimeError")
    ev = json.loads(Path(res["evidence_path"]).read_text(encoding="utf-8"))
    assert ev["stage"] == "before_write"
    assert ev["changes"][0]["old_close"] == 6724.34
    assert store._kospi_rows(db)["2026-09-17"]["close"] == 6724.34


def test_readback_mismatch_is_failure_even_when_as_of_is_t1(db, cal, monkeypatch):
    """확정 계약 3 ⑤ 와 같은 원칙 — 저장 뒤 날짜별 값 · source 를 다시 읽어 확인한다."""
    _pc_shape(db)
    real = store.upsert_benchmark_prices

    def skewed(*, rows, **kw):
        return real(rows=[(d, c + 1.0) for d, c in rows], **kw)

    monkeypatch.setattr(store, "upsert_benchmark_prices", skewed)
    res = _refresh(db, cal, FakeKrx())
    assert (res["status"], res["error"]) == ("failed", "readback_mismatch:2026-09-17")
    ev = json.loads(Path(res["evidence_path"]).read_text(encoding="utf-8"))
    assert ev["readback_ok"] is False


def test_no_evidence_no_overwrite(db, cal, tmp_path) -> None:
    """증거를 못 남기면 아무것도 쓰지 않는다 — 다음 회차가 같은 날짜부터 다시 한다."""
    before = _pc_shape(db)
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    res = _refresh(db, cal, FakeKrx(), evidence_dir=blocker / "sub")
    assert res["status"] == "failed"
    assert res["error"].startswith("evidence_write_failed:")
    assert res["rows_written"] == 0 and res["evidence_path"] is None
    assert store._kospi_rows(db) == before


def test_default_evidence_dir_is_read_at_call_time(db, cal, tmp_path, monkeypatch):
    _pc_shape(db)
    monkeypatch.setattr(store, "KOSPI_EVIDENCE_DIR", tmp_path / "ev_default")
    res = _refresh(db, cal, FakeKrx(), evidence_dir=None)
    assert Path(res["evidence_path"]).parent == tmp_path / "ev_default"


def test_rerun_same_day_rechecks_t1_once_and_rewrites_nothing(db, cal) -> None:
    _pc_shape(db)
    _refresh(db, cal, FakeKrx())
    fake = FakeKrx()
    res = _refresh(db, cal, fake)
    assert fake.calls == ["20260929"]
    assert (res["status"], res["rows_written"], res["replaced"]) == ("ok", 0, 0)
    assert res["evidence_path"] is None and res["corrections"] == []


# ── 최신성 — T-1 정상 · T-2 는 정상 아님 (C7 lag ≤ 1 폐기) ──────────────────────


def test_t2_only_is_stale_even_though_old_lag_rule_passed(db, cal) -> None:
    """08:10 전(T-1 공개 전) 모양: 저장 09-28 · 09-29 는 0행 → T-2 → 정상 아님."""
    _seed(db, {"2026-09-28": 6889.74}, KRX)
    published = {k: v for k, v in OFFICIAL.items() if k <= "2026-09-28"}
    res = _refresh(db, cal, FakeKrx(published))
    assert res["status"] == "failed"
    assert res["error"] == (
        "source_stale:as_of=2026-09-28,expected=2026-09-29,lag=1,"
        "reason=no_rows@2026-09-29"
    )
    # 화면도 같은 판정 — 옛 규칙(lag 1 ≤ 1)이면 정상이었다.
    k = with_kospi_display(
        {"kospi": {"status": "ok", "as_of_date": "2026-09-28"}},
        db_path=db,
        today_kst="2026-09-30",
        calendar_dir=cal,
    )["kospi"]
    assert (k["display_state"], k["trading_day_lag"]) == ("stale", 1)


@pytest.mark.parametrize(
    "as_of,today,fresh,reason",
    [
        ("2026-09-29", "2026-09-30", True, None),
        ("2026-09-28", "2026-09-30", False, "before_expected"),
        ("2026-09-30", "2026-09-30", False, "after_expected"),  # 당일 장중 행
        ("2026-09-23", "2026-09-28", True, None),  # 추석 연휴 다음 거래일
        ("2026-09-23", "2026-09-27", True, None),  # 휴장일(일요일) 화면
        (None, "2026-09-30", False, "no_data"),
        ("20260929", "2026-09-30", False, "invalid_date"),
    ],
)
def test_kospi_freshness_is_exact_previous_trading_day(
    cal, as_of, today, fresh, reason
):
    got = kospi_freshness(as_of, today_kst=today, calendar_dir=cal)
    assert (got.is_fresh, got.reason) == (fresh, reason)


def test_weekday_fallback_year_uses_weekday_t1(db, tmp_path) -> None:
    """캘린더가 없는 해(2027)는 평일 fallback 으로 기대 T-1 을 정한다."""
    fake = FakeKrx({"2027-03-08": 2800.0, "2027-03-09": 2810.0})
    res = _refresh(db, tmp_path / "no_calendar", fake, today="2027-03-10", max_calls=2)
    assert fake.calls == ["20270308", "20270309"]
    assert (res["status"], res["as_of_date"]) == ("ok", "2027-03-09")


# ── 빈 날을 만들지 않는다 · 호출 수 · 기록 ────────────────────────────────────


def test_missing_new_date_stops_without_creating_a_gap(db, cal) -> None:
    _seed(db, {"2026-09-21": 7007.72}, KRX)
    published = {k: v for k, v in OFFICIAL.items() if k != "2026-09-22"}
    fake = FakeKrx(published)
    res = _refresh(db, cal, fake)
    assert fake.calls == ["20260921", "20260922"]  # 09-22 에서 멈춤 · 09-23 조회 안 함
    assert sorted(store._kospi_rows(db)) == ["2026-09-21"]
    assert res["error"].endswith("reason=no_rows@2026-09-22")


def test_recheck_miss_of_stored_latest_continues(db, cal) -> None:
    """저장 최신일 재확인만 비면 다음 날짜로 간다(이미 있는 행 · 빈 날 없음)."""
    _seed(db, {"2026-09-28": 6889.74}, KRX)
    fake = FakeKrx(override={"2026-09-28": []})
    res = _refresh(db, cal, fake)
    assert fake.calls == ["20260928", "20260929"]
    assert res["status"] == "ok" and res["as_of_date"] == "2026-09-29"


def test_fetch_exception_stops_immediately_and_is_source_failure(db, cal) -> None:
    _seed(db, {"2026-09-22": 6950.10}, KRX)
    fake = FakeKrx(raise_on={"2026-09-23"})
    res = _refresh(db, cal, fake)
    assert fake.calls == ["20260922", "20260923"]
    assert (res["status"], res["error"]) == ("failed", "fetch_failed:ConnectionError")
    assert res["attempts"][-1] == {
        "date": "2026-09-23",
        "result": "fetch_error",
        "error_type": "ConnectionError",
    }
    log = {"fail_count": 1, "error_summary": res["error"]}
    state = kospi_display_state(
        status="stale",
        as_of="2026-09-22",
        is_fresh=False,
        last_refresh=log,
        today_is_trading_day=True,
    )
    assert state == "source_failed"


def test_t1_already_stored_recheck_failure_stays_ok(db, cal) -> None:
    _seed(db, {"2026-09-29": 6912.30}, KRX)
    res = _refresh(db, cal, FakeKrx(raise_on={"2026-09-29"}))
    assert (res["status"], res["error"]) == ("ok", None)
    assert res["note"] == "fetch_failed:ConnectionError"


@pytest.mark.parametrize(
    "rows,why",
    [
        (
            [{"BAS_DD": "20260929", "IDX_NM": "코스피 200", "CLSPRC_IDX": "900"}],
            "kospi_row_missing",
        ),
        (
            [
                {"BAS_DD": "20260929", "IDX_NM": "코스피", "CLSPRC_IDX": "1"},
                {"BAS_DD": "20260929", "IDX_NM": "코스피", "CLSPRC_IDX": "2"},
            ],
            "kospi_row_duplicate",
        ),
        (
            [{"BAS_DD": "20260928", "IDX_NM": "코스피", "CLSPRC_IDX": "6889.74"}],
            "basis_mismatch",
        ),
        (
            [{"BAS_DD": "20260929", "IDX_NM": "코스피", "CLSPRC_IDX": ""}],
            "invalid_close",
        ),
        (
            [{"BAS_DD": "20260929", "IDX_NM": "코스피", "CLSPRC_IDX": "0"}],
            "invalid_close",
        ),
        (
            [{"BAS_DD": "20260929", "IDX_NM": "코스피", "CLSPRC_IDX": "-1"}],
            "invalid_close",
        ),
        (
            [{"BAS_DD": "20260929", "IDX_NM": "코스피", "CLSPRC_IDX": "nan"}],
            "invalid_close",
        ),
    ],
)
def test_bad_response_is_not_stored(db, cal, rows, why) -> None:
    _seed(db, {"2026-09-28": 6889.74}, KRX)
    res = _refresh(db, cal, FakeKrx(override={"2026-09-29": rows}))
    assert res["error"].endswith(f"reason={why}@2026-09-29")
    assert sorted(store._kospi_rows(db)) == ["2026-09-28"]


def test_call_cap_is_oldest_first_and_next_run_continues(db, cal) -> None:
    _seed(db, {"2026-09-15": 6627.26}, KRX)
    first = FakeKrx()
    _refresh(db, cal, first, max_calls=3)
    assert first.calls == ["20260915", "20260916", "20260917"]
    second = FakeKrx()
    res = _refresh(db, cal, second, max_calls=40)
    assert second.calls[0] == "20260917" and second.calls[-1] == "20260929"
    assert res["status"] == "ok"


def test_attempt_log_has_no_key_or_price_values(db, cal) -> None:
    _pc_shape(db)
    res = _refresh(db, cal, FakeKrx())
    text = json.dumps(res["attempts"], ensure_ascii=False)
    assert KEY not in text and "6715" not in text and "CLSPRC" not in text
    assert KEY not in json.dumps(res, ensure_ascii=False)
    assert res["attempts"][0] == {"date": "2026-09-17", "rows": 3, "result": "ok"}


def test_api_key_missing_makes_no_call(db, cal, monkeypatch) -> None:
    monkeypatch.setattr(krx_sync, "read_api_key", lambda env_path=None: None)
    fake = FakeKrx()
    res = store.refresh_kospi_benchmark(
        end_date=date(2026, 9, 30), fetcher=fake, db_path=db, calendar_dir=cal
    )
    assert fake.calls == [] and res["calls"] == 0
    assert (res["status"], res["error"]) == ("failed", "api_key_missing")


def test_conftest_blocks_the_live_kospi_endpoint(db, cal) -> None:
    """`fetcher` 를 안 넘기면 네트워크 경계(`_default_kospi_fetcher`)가 테스트 가드에 막힌다."""
    res = store.refresh_kospi_benchmark(
        end_date=date(2026, 9, 30), api_key=KEY, db_path=db, calendar_dir=cal
    )
    assert res["error"] == "fetch_failed:AssertionError"
    assert res["attempts"][0]["error_type"] == "AssertionError"


# ── 같은 최신성 함수 — 배치 · 계산 · API (확정 계약 9 ⑤) ──────────────────────


def test_all_layers_import_the_same_freshness_function() -> None:
    f = market_benchmark_freshness.kospi_freshness
    assert store.kospi_freshness is f
    assert market_regime.kospi_freshness is f
    assert api_market_topn_service.kospi_freshness is f


def _history_until(last: str) -> list[tuple[str, float]]:
    end = date.fromisoformat(last)
    return [
        ((end - timedelta(days=i)).isoformat(), 2700.0 + (200 - i))
        for i in range(199, -1, -1)
    ]


@pytest.mark.parametrize(
    "last,compute_status,batch_status,display",
    [("2026-09-29", "ok", "ok", "ok"), ("2026-09-28", "stale", "failed", "stale")],
)
def test_batch_compute_and_api_agree(
    db, cal, last, compute_status, batch_status, display
):
    hist = _history_until(last)
    axis = [d for d, _ in _history_until("2026-09-29")]
    got = compute_kospi_metrics(
        hist, trading_days=axis, today_kst="2026-09-30", calendar_dir=cal
    )
    assert got["status"] == compute_status
    _seed(db, dict(hist[-5:]), KRX)
    res = _refresh(db, cal, FakeKrx({k: v for k, v in OFFICIAL.items() if k <= last}))
    assert res["status"] == batch_status
    k = with_kospi_display(
        {"kospi": {"status": got["status"], "as_of_date": got["as_of_date"]}},
        db_path=db,
        today_kst="2026-09-30",
        calendar_dir=cal,
    )["kospi"]
    assert k["display_state"] == display


def test_compute_path_without_today_keeps_legacy_rule() -> None:
    """과거 재현 호출부(ML 화면 등)는 `today_kst` 를 넘기지 않는다 — 예전 판정 그대로."""
    hist = _history_until("2026-09-28")
    axis = [d for d, _ in _history_until("2026-09-29")]
    assert compute_kospi_metrics(hist, trading_days=axis)["status"] == "ok"


def test_compute_path_fresh_but_off_kodex_axis_is_unavailable(cal) -> None:
    hist = _history_until("2026-09-29")
    axis = [d for d, _ in _history_until("2026-09-21")]  # KODEX200 이 멈춘 PC
    got = compute_kospi_metrics(
        hist, trading_days=axis, today_kst="2026-09-30", calendar_dir=cal
    )
    assert (got["status"], got["reason"]) == ("unavailable", "as_of_not_on_axis")


@pytest.fixture
def api_client(monkeypatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "api" / "market_data.sqlite"
    fake_db.parent.mkdir()
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing(db_path=fake_db)
    monkeypatch.setattr(_cal, "CALENDAR_DIR", _write_calendar(tmp_path / "meta"))
    monkeypatch.setattr(api_market_topn_service, "_kst_today", lambda: "2026-09-30")
    return TestClient(api_module.app)


@pytest.mark.parametrize(
    "kospi_last,status", [("2026-09-29", "ok"), ("2026-09-28", "stale")]
)
def test_topn_api_compute_and_display_use_same_today(api_client, kospi_last, status):
    db = api_market_topn.DEFAULT_DB_PATH
    _seed_kodex200_long_history(db, date(2026, 9, 29), n_days=120)
    _seed_kospi_long_history(db, date.fromisoformat(kospi_last), n_days=120)
    k = api_client.get("/market/topn/latest").json()["market_context"]["kospi"]
    assert (k["status"], k["display_state"], k["as_of_date"]) == (
        status,
        status,
        kospi_last,
    )
    if status == "stale":
        assert k["return_1m_pct"] is None  # T-2 수익률은 만들지 않는다


# ── KOSPI 만 실패 — Telegram 고지 없음 (시나리오 7 · 확정 계약 13) ──────────────


def test_kospi_only_failure_is_pc_only_no_telegram_notice(
    monkeypatch, tmp_path
) -> None:
    import app.market_benchmark_batch as bench_mod
    import scripts.run_oci_market_data_batch as batch
    from app.market_briefing import krx_target_sync
    from app.three_push_runtime import market_data_batch as mdb
    from app.three_push_runtime.market_data_batch import RefreshResult
    from app.three_push_runtime.runner_market_briefing import batch_failure_reasons

    today = date(2026, 9, 30)
    state_path = tmp_path / "batch_state.json"
    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", state_path)
    monkeypatch.setattr(mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "re.json")
    monkeypatch.setattr(batch, "_kst_today", lambda: today)
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500"])
    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda tickers, *, end_date, **kw: RefreshResult(
            attempted=1, success=1, fail=0, price_data_as_of="2026-09-29"
        ),
    )
    monkeypatch.setattr(
        batch,
        "_build_universe_artifact",
        lambda *, price_data_as_of: ({"summary": {"refresh_status": "ok"}}, "t", "ok"),
    )
    monkeypatch.setattr(
        "app.universe_bootstrap.artifact_validator.validate_artifact",
        lambda *a, **k: (True, None, {}),
    )
    monkeypatch.setattr(
        batch,
        "evaluate_freshness",
        lambda **kw: type("V", (), {"ok": True, "reason": ""})(),
    )
    monkeypatch.setattr(
        "app.momentum.universe_mode.save_latest_artifact", lambda r: tmp_path / "a.json"
    )
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        lambda **kw: {"status": "ok", "target_date": "2026-09-29", "attempts": []},
    )
    monkeypatch.setattr(_cal, "CALENDAR_DIR", _write_calendar(tmp_path / "meta"))
    # KOSPI 만 실패 — 실제 적재 경로(tmp DB) · KRX 경계만 예외.
    ok = {"status": "ok", "as_of_date": "2026-09-29", "error": None}
    monkeypatch.setattr(bench_mod, "refresh_vix", lambda **kw: ok)
    monkeypatch.setattr(bench_mod, "refresh_us_index", lambda *a, **kw: ok)
    monkeypatch.setattr(krx_sync, "read_api_key", lambda env_path=None: KEY)

    def _krx_down(bas_dd, key):
        raise ConnectionError("krx down")

    monkeypatch.setattr(krx_sync, "_default_kospi_fetcher", _krx_down)
    db = tmp_path / "m.sqlite"
    real = bench_mod.refresh_benchmarks
    monkeypatch.setattr(
        bench_mod, "refresh_benchmarks", lambda **kw: real(db_path=db, **kw)
    )

    rec = batch.run(mode="run")
    saved = json.loads(state_path.read_text(encoding="utf-8"))

    kospi = rec["benchmark_refresh"]["kospi"]
    assert (kospi["status"], kospi["error"]) == (
        "failed",
        "fetch_failed:ConnectionError",
    )
    assert kospi["calls"] == 1 and kospi["source"] == KRX
    assert rec["benchmark_refresh"]["failed"] == ["kospi"]
    assert rec["stage_status"]["fdr_price"] == "ok"
    # 08:30 배치 실패 고지 판정 — KOSPI 실패는 사유가 아니다(PC 전용).
    assert batch_failure_reasons(saved, today.isoformat()) == []
