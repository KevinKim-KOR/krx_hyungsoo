"""POC6-29 — 행 상세 수치(`GET /market/etf-detail?tickers=…` · PLAN §2-7 · §3-3 · 판정 Q4-1).

1 · 3개월 = 같은 DB · 같은 끝일의 요약(`build_summary`) `criteria` 값과 같음 · 6 · 12개월 시작 행 규칙 ·
계산된 0(ok) · 기간 다름(값 없음 + 실제 날짜) · 자료 없음 · 20구간 KODEX 200 차이(시작 · 끝 둘 다 같을 때만) ·
NAV(ok · 부분 · 없음 · 개별 주식 해당 없음 · 괴리 3 · 5%) · 422 · 읽기 전용(mode=ro).
임시 DB 만 쓴다(라이브 DB 를 열지 않음).
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_etf_compare
from app.etf_nav_store import NavDailyRow, init_nav_db, upsert_nav_rows
from app.market_data_store import init_db
from app.pc_etf_compare_summary import build_summary
from app.pc_etf_row_detail import build_etf_detail
from app.short_term_momentum import _window_return_pct
from tests.test_poc6_28_etf_compare import END, FILTERS, _bdays, _master, _put, _trend

D = _bdays(END, 300)  # 약 14개월 — 12개월 시작 행까지 있다
INTRADAY = "2026-11-10T04:00:00Z"  # 11/10 13:00 KST — 장중 저장
UP, FLAT, STOP, LATE, GAP = "AAA101", "AAA102", "AAA103", "AAA104", "AAA105"
STOCK = "STK001"  # 가짜 개별 주식 코드(ETF 목록에 없음 · 실제 종목 아님)


def _closes(n: int, start: float, end_v: float) -> list[float]:
    return _trend(n, start, end_v)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "market_data.sqlite"
    init_db(p)
    _master(
        p,
        {
            "069500": "KODEX 200",
            UP: "가 상승",
            FLAT: "나 평탄",
            STOP: "다 멈춤",
            LATE: "라 늦은상장",
            GAP: "마 빠진날",
        },
    )
    _put(p, "069500", _closes(300, 120.0, 100.0), days=D)
    _put(p, UP, _closes(300, 100.0, 160.0), days=D, last_fetched=INTRADAY)
    _put(p, FLAT, [100.0] * 300, days=D)  # 계산된 0
    _put(p, STOP, _closes(271, 100.0, 140.0), days=D[:-29])  # 끝일 = D[-30]
    _put(p, LATE, _closes(50, 100.0, 90.0), days=D[-50:])  # 늦은 상장(약 2.5개월)
    gap_days = D[:-10] + D[-9:]  # 최근 20구간 안에서 하루 빠짐
    _put(p, GAP, _closes(299, 100.0, 120.0), days=gap_days)
    # 보유 개별 주식(etf_master 밖) — ETF 끝일 다음 날 행도 있다(보유 현재가 업데이트).
    _put(p, STOCK, _closes(301, 50.0, 70.0), days=D + ["2026-11-11"])
    init_nav_db(p)
    upsert_nav_rows(
        [
            NavDailyRow(UP, END, 100.0, 103.5, 3.5, "naver", "ok", None),
            NavDailyRow(
                FLAT, END, 100.0, 94.8, -5.2, "naver", "partial", "stale cache reused"
            ),
            NavDailyRow(
                LATE, END, None, None, None, "naver", "unavailable", "nav missing"
            ),
        ],
        db_path=p,
    )
    return p


def _run_summary(db: Path, basis: str) -> dict[str, Any]:
    return build_summary(
        db_path=db,
        basis=basis,
        filters=FILTERS,
        official={},
        official_meta={},
        dictionary=None,
        dictionary_meta={},
        held_tickers=None,
        holdings_status="ok",
    )


def _detail(db: Path, *tickers: str) -> dict[str, dict[str, Any]]:
    r = build_etf_detail(db, list(tickers))
    assert r["status"] == "ok" and r["end_date"] == END
    return {it["ticker"]: it for it in r["items"]}


# ── 요약과 같은 값(완료 확인 3 · 판정 Q4-1) ───────────────────────────────


@pytest.mark.parametrize("basis", ["one_month", "three_month", "daily"])
def test_one_three_month_equal_summary_criteria(db: Path, basis: str) -> None:
    s = _run_summary(db, basis)
    assert s["status"] == "ok"
    rows = s["top"] + s["bottom"]
    det = _detail(db, *{r["ticker"] for r in rows})
    assert rows
    for r in rows:
        it = det[r["ticker"]]
        for key, crit in (("m1", "one_month"), ("m3", "three_month")):
            c, p = r["criteria"][crit], it[key]
            assert p["status"] == c["status"], (r["ticker"], key)
            assert (p["start"], p["end"]) == (c["start"], c["end"])
            if c["status"] == "ok":
                assert (
                    p["value"] == c["value"]
                )  # 같은 산식 · 같은 반올림 = 정확히 같은 값
                assert (p["start_close"], p["end_close"]) == (
                    c["start_close"],
                    c["end_close"],
                )
            else:
                assert p["value"] is None  # 기간 다름은 값을 비운다
        same = r["criteria"]["same_kodex_1m"]
        if same["status"] == "ok":
            sk = it["same_kodex"]["one_month"]
            assert sk["status"] == "ok" and sk["value"] == same["value"]
            assert sk["kodex200_return_pct"] == same["kodex200_return_pct"]
        dd, ddc = it["drawdown"], r["criteria"]["drawdown"]
        assert dd["status"] == ddc["status"] and dd["value"] == ddc["value"]
        assert (dd["start"], dd["end"]) == (ddc["start"], ddc["end"])


def test_late_listing_three_month_matches_summary_period_differs(db: Path) -> None:
    s = _run_summary(db, "one_month")
    row = next(r for r in s["top"] + s["bottom"] if r["ticker"] == LATE)
    assert row["criteria"]["three_month"]["status"] == "period_differs"
    it = _detail(db, LATE)[LATE]
    assert it["m1"]["status"] == "ok"
    m3 = it["m3"]
    assert m3["status"] == "period_differs" and m3["value"] is None
    assert m3["reason"] == "start_differs" and m3["start"] == D[-50]
    assert it["m12"]["status"] == "period_differs" and it["m12"]["start"] == D[-50]
    assert it["same_kodex"]["three_month"]["status"] == "period_differs"


# ── 6 · 12개월 · 일간 · 5 · 20구간 규칙 ───────────────────────────────────


def test_six_and_twelve_month_start_row_rule(db: Path) -> None:
    it = _detail(db, UP)[UP]
    closes = dict(zip(D, _closes(300, 100.0, 160.0)))
    for key, days in (("m6", 180), ("m12", 365)):
        target = (date.fromisoformat(END) - timedelta(days=days)).isoformat()
        start = next(d for d in D if d >= target)
        p = it[key]
        assert p["status"] == "ok" and (p["start"], p["end"]) == (start, END)
        assert p["value"] == round((closes[END] / closes[start] - 1.0) * 100.0, 4)


def test_row_windows_use_window_return_pct(db: Path) -> None:
    it = _detail(db, UP)[UP]
    series = list(zip(D, _closes(300, 100.0, 160.0)))
    for key, n in (("daily", 1), ("w5", 5), ("w20", 20)):
        p = it[key]
        assert p["status"] == "ok" and (p["start"], p["end"]) == (D[-(n + 1)], END)
        assert p["value"] == round(_window_return_pct(series, n), 4)


def test_computed_zero_stays_zero_with_ok(db: Path) -> None:
    it = _detail(db, FLAT)[FLAT]
    for key in ("daily", "w5", "w20", "m1", "m3", "m6", "m12"):
        assert it[key]["status"] == "ok" and it[key]["value"] == 0.0, key
        assert it[key]["value"] is not None
    assert it["drawdown"]["status"] == "ok" and it["drawdown"]["value"] == 0.0


def test_stopped_etf_shows_period_differs_with_actual_dates(db: Path) -> None:
    it = _detail(db, STOP)[STOP]
    stop_end = D[-30]
    assert it["last_date"] == stop_end
    for key in ("daily", "w5", "w20", "m1", "m3", "m6", "m12"):
        p = it[key]
        assert p["status"] == "period_differs" and p["value"] is None, key
        assert p["end"] == stop_end and p["reason"] == "end_differs"
        assert p["start"] is not None and p["start_close"] is None
    assert it["excess20"]["status"] == "period_differs"
    assert it["excess20"]["value_pctp"] is None
    assert it["same_kodex"]["one_month"]["status"] == "period_differs"
    assert it["drawdown"]["status"] == "period_differs"
    assert (
        it["drawdown"]["reason"] == "end_differs" and it["drawdown"]["end"] == stop_end
    )


def test_insufficient_and_unknown_ticker_are_missing(db: Path) -> None:
    det = _detail(db, LATE, "ZZZ999")
    late = det[LATE]
    assert late["m1"]["status"] == "ok" and late["w20"]["status"] == "ok"
    none = det["ZZZ999"]
    assert none["is_etf"] is False and none["last_date"] is None
    assert none["end_price"] is None
    for key in ("daily", "w5", "w20", "m1", "m3", "m6", "m12"):
        assert none[key]["status"] == "missing" and none[key]["reason"] == "no_rows"
    assert none["drawdown"]["status"] == "missing"
    assert none["nav"]["status"] == "not_applicable"


# ── 20구간 KODEX 200 차이 ────────────────────────────────────────────────


def test_excess20_only_when_start_and_end_both_match(db: Path) -> None:
    r = build_etf_detail(db, [UP, GAP])
    kw = r["kodex200"]["window20"]
    assert kw["status"] == "ok" and (kw["start"], kw["end"]) == (D[-21], END)
    det = {it["ticker"]: it for it in r["items"]}
    up = det[UP]["excess20"]
    t = _window_return_pct(list(zip(D, _closes(300, 100.0, 160.0))), 20)
    k = _window_return_pct(list(zip(D, _closes(300, 120.0, 100.0))), 20)
    assert up["status"] == "ok" and up["value_pctp"] == round(t - k, 4)
    assert (up["etf_return_pct"], up["kodex200_return_pct"]) == (
        round(t, 4),
        round(k, 4),
    )
    assert (up["start"], up["end"]) == (kw["start"], kw["end"])
    gap = det[GAP]["excess20"]
    assert gap["status"] == "period_differs" and gap["value_pctp"] is None
    assert gap["reason"] == "start_differs"
    assert gap["start"] == D[-22] and gap["kodex200_start"] == D[-21]
    assert gap["end"] == gap["kodex200_end"] == END
    # 20구간 자체(그 종목 행)는 ok · 1개월은 시작 · 끝이 공통 기간과 같아 ok.
    assert det[GAP]["w20"]["status"] == "ok" and det[GAP]["m1"]["status"] == "ok"


# ── 가격 시점 · NAV · 개별 주식 ───────────────────────────────────────────


def test_end_price_state_from_own_last_row(db: Path) -> None:
    det = _detail(db, UP, FLAT)
    assert det[UP]["end_price"]["state"] == "intraday"
    assert det[UP]["end_price"]["fetched_at_kst"] == "2026-11-10T13:00:00+09:00"
    assert det[FLAT]["end_price"]["state"] == "after_close"


def test_nav_states_and_flags(db: Path) -> None:
    det = _detail(db, UP, FLAT, LATE, GAP, STOCK)
    up = det[UP]["nav"]
    assert up["status"] == "ok" and up["flag"] == "discount_check_needed"
    assert (up["nav"], up["market_price"], up["discount_rate_pct"], up["asof"]) == (
        100.0,
        103.5,
        3.5,
        END,
    )
    flat = det[FLAT]["nav"]
    assert flat["status"] == "ok" and flat["flag"] == "discount_warning"
    assert flat["row_status"] == "partial" and flat["message"] == "stale cache reused"
    late = det[LATE]["nav"]
    assert late["status"] == "missing" and late["asof"] == END
    assert late["discount_rate_pct"] is None
    assert det[GAP]["nav"]["status"] == "missing" and det[GAP]["nav"]["asof"] is None
    assert det[STOCK]["nav"]["status"] == "not_applicable"


def test_nav_table_absent_is_missing(tmp_path: Path) -> None:
    p = tmp_path / "m.sqlite"
    init_db(p)
    _master(p, {"069500": "KODEX 200", UP: "가 상승"})
    _put(p, "069500", _closes(40, 120.0, 100.0), days=D[-40:])
    _put(p, UP, _closes(40, 100.0, 110.0), days=D[-40:])
    it = build_etf_detail(p, [UP])["items"][0]
    assert it["nav"]["status"] == "missing"
    with sqlite3.connect(p) as con:  # 읽기 전용 — 표를 만들지 않는다
        assert not con.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'etf_nav_daily'"
        ).fetchone()


def test_stock_uses_own_latest_row_and_no_nav(db: Path) -> None:
    it = _detail(db, STOCK)[STOCK]
    assert it["is_etf"] is False and it["name"] is None
    assert it["last_date"] == "2026-11-11" and it["end_price"]["date"] == "2026-11-11"
    assert it["m1"]["status"] == "period_differs" and it["m1"]["end"] == "2026-11-11"
    assert it["w20"]["status"] == "period_differs"
    assert it["nav"]["status"] == "not_applicable"


def test_status_missing_and_empty(tmp_path: Path) -> None:
    assert build_etf_detail(tmp_path / "none.sqlite", [UP])["status"] == "missing"
    p = tmp_path / "e.sqlite"
    init_db(p)
    r = build_etf_detail(p, [UP])
    assert r["status"] == "empty" and r["items"] == []


# ── 경로 ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client(db: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(api_etf_compare, "MARKET_DB_PATH", db)
    return TestClient(api_module.app)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_endpoint_dedupes_and_reads_only(client: TestClient, db: Path) -> None:
    before = _sha(db)
    res = client.get("/market/etf-detail", params={"tickers": f"{UP}, {UP},{FLAT},"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and [it["ticker"] for it in body["items"]] == [
        UP,
        FLAT,
    ]
    assert body["kodex200"]["window20"]["end"] == END
    assert _sha(db) == before


@pytest.mark.parametrize(
    "tickers",
    ["", " , ", ",".join(f"T{i:05d}" for i in range(31)), "AAA101;DROP", "가나다"],
)
def test_endpoint_rejects_bad_ticker_lists(client: TestClient, tickers: str) -> None:
    assert (
        client.get("/market/etf-detail", params={"tickers": tickers}).status_code == 422
    )


def test_endpoint_accepts_thirty_and_requires_param(client: TestClient) -> None:
    thirty = ",".join(f"T{i:05d}" for i in range(30))
    res = client.get("/market/etf-detail", params={"tickers": thirty})
    assert res.status_code == 200 and len(res.json()["items"]) == 30
    assert client.get("/market/etf-detail").status_code == 422


def test_endpoint_missing_db(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_etf_compare, "MARKET_DB_PATH", tmp_path / "none.sqlite")
    body = client.get("/market/etf-detail", params={"tickers": UP}).json()
    assert body["status"] == "missing" and body["items"] == []
    assert not (tmp_path / "none.sqlite").exists()
