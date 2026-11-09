"""POC6-27 — `GET /market/flow-context` 구조 칸(관측값 · 비교 기준값 · 20 · 60거래일 창 · 자료 코드).

계약 출처: POC6-27 PLAN V1 쟁점 1 · 설계자 PLAN 판정 §4(실제 종가와 비교 저점을 관측값 · 기준값 · 기준일로 나눔 ·
기존 문장 그대로 · 새 칸이 실제 GET 응답에 실림). 11/5 · 11/6 사례 = 저장 KOSPI 종가(시장 자료 · 개인 값 아님).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_supply_fx_oil
from app import supply_fx_oil_store as st
from app.market_benchmark_store import upsert_benchmark_prices
from app.supply_fx_oil_context import build_market_flow_context
from app.supply_fx_oil_fields import windows_fields

E8 = 100_000_000
# 11/9 대조의 저장 KOSPI 종가(09-28 ~ 11-06 · 실제 거래일).
REAL = [
    ("2026-09-28", 6889.74),
    ("2026-09-29", 6870.81),
    ("2026-09-30", 6838.04),
    ("2026-10-01", 6971.35),
    ("2026-10-02", 7003.74),
    ("2026-10-06", 6941.39),
    ("2026-10-07", 6803.9),
    ("2026-10-08", 6625.93),
    ("2026-10-12", 6384.24),
    ("2026-10-13", 6035.35),
    ("2026-10-14", 6008.81),
    ("2026-10-15", 5554.22),
    ("2026-10-16", 5668.05),
    ("2026-10-19", 5768.01),
    ("2026-10-20", 5552.74),
    ("2026-10-21", 5735.66),
    ("2026-10-22", 5533.77),
    ("2026-10-23", 5550.3),
    ("2026-10-26", 5469.47),
    ("2026-10-27", 5638.34),
    ("2026-10-28", 6012.44),
    ("2026-10-29", 5937.66),
    ("2026-10-30", 5730.74),
    ("2026-11-02", 5859.08),
    ("2026-11-03", 5648.79),
    ("2026-11-04", 5683.8),
    ("2026-11-05", 5383.8),
    ("2026-11-06", 5059.69),
]
NOW = datetime(2026, 11, 9, 1, 0, tzinfo=timezone.utc)  # 11/9 10:00 KST


def _early_days(n: int, end_before: str) -> list[str]:
    """`end_before` 이전 평일 n 개(오름차순 · 앞쪽 합성 구간)."""
    d, out = date.fromisoformat(end_before) - timedelta(days=1), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return sorted(out)


def _seed_case(db: Path, *, flows: bool = True) -> list[str]:
    early = _early_days(130, REAL[0][0])
    # 앞쪽은 평탄(6,900 ± 소폭) — 실제 마지막 28개 구간의 사건만 남게 한다.
    rows = [(d, 6900.0 + (i % 3)) for i, d in enumerate(early)] + REAL
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="코스피",
        rows=rows,
        source="TEST",
        db_path=db,
    )
    kdays = [d for d, _ in rows]
    if flows:
        out = []
        recent = set(kdays[-21:-1])  # D(11/5)까지 최근 20거래일
        for d in kdays[:-1]:  # 마지막(11/6) 수급 아직 없음 → D = 11/5
            v = -11000 * E8 if d in recent else -12000 * E8
            out += [
                (d, "foreign", v),
                (d, "individual", 9000 * E8),
                (d, "institution", 500 * E8),
                (d, "other_corp", 500 * E8),
            ]
        st.upsert_investor_flows(rows=out, db_path=db)
    for sid, base in ((st.USDKRW, 1340.0), (st.WTI, 90.0)):
        u, p, b = st.MACRO_SERIES[sid]
        st.upsert_macro_daily(
            series_id=sid,
            rows=[(d, base) for d in kdays[:-1]],  # 평탄 · 마지막 = 11/5
            unit=u,
            provider=p,
            basis=b,
            db_path=db,
        )
    return kdays


@pytest.fixture
def case(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed_case(db)
    return db, build_market_flow_context(db_path=db, now=NOW)


def _line(out, key):
    return next(r for r in out["short_lines"] if r["key"] == key)


def test_kospi_obs_separates_close_and_comparison_bound(case):
    _db, out = case
    row = _line(out, "kospi")
    # 기존 문장 그대로(11/9 실제 응답과 같은 글자)
    assert row["text"] == (
        "코스피 11/6 · 직전 대비 -324.11pt(-6.02%) · 5개 관측 -671.05pt(-11.71% · 10/30부터)"
    )
    assert row["flags"] == ["직전 20개 관측 범위 아래"]
    obs = row["obs"]
    assert (obs["date"], obs["value"], obs["unit"]) == ("2026-11-06", 5059.69, "pt")
    assert obs["d1"]["from_date"] == "2026-11-05"
    assert obs["d1"]["diff"] == pytest.approx(-324.11)
    assert obs["d1"]["pct"] == pytest.approx(-6.0199, abs=1e-3)
    assert obs["d5"]["from_date"] == "2026-10-30"
    # 비교 기준값 = 직전 20개 저장 종가 최저(11/5) — 그날 종가(5,059.69)가 아니다.
    assert obs["range"] == {"dir": "아래", "bound": 5383.8, "bound_date": "2026-11-05"}
    assert obs["value"] != obs["range"]["bound"]


def test_range_events_carry_value_bound_and_key(case):
    _db, out = case
    ev = [e for e in out["events"] if e["key"] == "kospi" and e["kind"] == "range"]
    assert [e["text"] for e in ev] == [
        "11/6 코스피 직전 20개 관측 범위 아래(5,383.80 · 11/5 밑)",
        "11/5 코스피 직전 20개 관측 범위 아래(5,469.47 · 10/26 밑)",
    ]
    e6, e5 = ev
    assert (e6["date"], e6["value"], e6["bound"], e6["bound_date"], e6["dir"]) == (
        "2026-11-06",
        5059.69,
        5383.8,
        "2026-11-05",
        "아래",
    )
    assert (e5["value"], e5["bound"], e5["bound_date"], e5["unit"]) == (
        5383.8,
        5469.47,
        "2026-10-26",
        "pt",
    )
    assert e6["series"] == "코스피"  # 기존 칸 그대로


def test_expansion_event_fields():
    from app.supply_fx_oil_calc import price_events

    pts = [(f"2026-01-{i + 1:02d}", 100.0 + (i % 2)) for i in range(25)]
    pts.append(("2026-01-26", pts[-1][1] - 10.0))  # 평균 변화 1 의 10배
    ev = [e for e in price_events(pts, "WTI", "달러") if e["kind"] == "expansion"]
    assert len(ev) == 1
    e = ev[0]
    assert (e["delta"], e["ratio"], e["zero_base"], e["unit"]) == (
        -10.0,
        pytest.approx(10.0),
        False,
        "달러",
    )
    assert (e["base_from"], e["base_to"], e["value"]) == (
        "2026-01-05",
        "2026-01-25",
        pts[-1][1],
    )
    zero = [("2026-02-%02d" % (i + 1), 50.0) for i in range(23)] + [
        ("2026-02-24", 51.0)
    ]
    z = [e for e in price_events(zero, "WTI", "달러") if e["kind"] == "expansion"][0]
    assert z["zero_base"] is True and z["ratio"] is None and z["delta"] == 1.0


def test_flow_rows_and_windows(case):
    _db, out = case
    f = _line(out, "foreign")
    assert f["text"] == "외국인 11/5 순매도 -1.1조원"
    assert f["obs"]["date"] == "2026-11-05" and f["obs"]["unit"] == "원"
    assert f["obs"]["value"] == -11000 * E8
    w = out["windows"]
    assert w["lines"][0] == (
        "외국인 최근 20거래일 -22.0조원(일평균 -1.1조원) · 직전 20거래일 -24.0조원(일평균 -1.2조원)"
    )
    assert w["lines"][1] == "직전 20거래일보다 일평균 매도 감소"
    rec, prev = w["foreign20"]["recent"], w["foreign20"]["previous"]
    # 하루 -1.1조(최근 20) · -1.2조(직전 20) → 합 -22.0조 · -24.0조
    assert (rec["sum"], rec["avg"], rec["to"]) == (
        -220000 * E8,
        -11000 * E8,
        "2026-11-05",
    )
    assert (prev["sum"], prev["avg"]) == (-240000 * E8, -12000 * E8)
    assert rec["from"] > prev["to"]
    r60 = w["r60"]
    assert set(r60) == {"foreign", "individual", "institution"}
    assert r60["foreign"]["to"] == "2026-11-05" and "avg" not in r60["foreign"]
    assert r60["individual"]["sum"] == 9000 * E8 * 60


def test_no_flows_windows_null_and_flow_rows_keyed(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed_case(db, flows=False)
    out = build_market_flow_context(db_path=db, now=NOW)
    assert out["windows"]["foreign20"] is None and out["windows"]["r60"] is None
    rows = {r["key"]: r for r in out["short_lines"]}
    assert rows["foreign"]["obs"] is None and rows["institution"]["obs"] is None
    assert rows["foreign"]["text"] == "외국인 수급 자료 없음"


def test_incomplete_window_gives_null_foreign20():
    w = {
        "foreign": {"r20": {"sum": -1, "avg": -0.05, "from": "a", "to": "b"}},
        "individual": {"r60": None},
        "institution": {"r60": None},
    }
    w["foreign"]["p20"] = None
    w["foreign"]["r60"] = None
    got = windows_fields(w)
    assert got["foreign20"] is None
    assert got["r60"] == {"foreign": None, "individual": None, "institution": None}


def test_price_row_without_data_is_keyed_with_null_obs(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed_case(db)
    with __import__("sqlite3").connect(db) as con:
        con.execute("DELETE FROM market_macro_daily WHERE series_id = ?", (st.WTI,))
    out = build_market_flow_context(db_path=db, now=NOW)
    row = _line(out, "wti")
    assert row["text"] == "WTI 자료 없음" and row["obs"] is None


def test_every_event_and_line_has_key(case):
    _db, out = case
    keys = {"kospi", "usdkrw", "wti", "foreign", "institution"}
    assert {r["key"] for r in out["short_lines"]} == keys
    assert all(e["key"] in keys for e in out["events"])


def test_get_response_keeps_new_fields(tmp_path, monkeypatch):
    db = tmp_path / "m.sqlite"
    _seed_case(db)
    monkeypatch.setattr(api_supply_fx_oil, "_DB_PATH", db)
    from app.api import app

    body = TestClient(app).get("/market/flow-context").json()
    k = next(r for r in body["short_lines"] if r["key"] == "kospi")
    assert k["obs"]["range"]["bound"] == 5383.8 and k["obs"]["value"] == 5059.69
    ev = next(e for e in body["events"] if e["date"] == "2026-11-06")
    assert (ev["key"], ev["bound"], ev["bound_date"]) == (
        "kospi",
        5383.8,
        "2026-11-05",
    )
    assert body["windows"]["foreign20"]["recent"]["avg"] == -11000 * E8
    assert body["windows"]["r60"]["foreign"]["to"] == "2026-11-05"
    fr = body["freshness"]
    assert set(fr) == {"today_kst", "expected_kr", "expected_kr_basis", "items"}
    assert [i["key"] for i in fr["items"]] == ["flows", "usdkrw", "wti"]
