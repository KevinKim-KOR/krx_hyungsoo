"""POC6-01 — 시장 흐름 계산 · 응답 조립 · 조회 API(외부 0 · 쓰기 0).

계약 출처: POC5-28 설계 개정 3 §3 · §3-1 · §4 · PLAN 판정 §4-2(누적 기준점 = 기간 시작 직전) · §4-3(D · E) ·
§7-3(순매수만 · 비율 생략) · POC6-01 판정 §5.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_supply_fx_oil
from app import supply_fx_oil_calc as calc
from app import supply_fx_oil_store as st
from app.market_benchmark_store import upsert_benchmark_prices
from app.supply_fx_oil_context import ai_text, build_market_flow_context

E8 = 100_000_000


def _wd(n, start="2026-04-01"):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# ── 기간 · 누적 ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code, end, boundary",
    [
        ("1M", "2026-10-16", "2026-09-16"),
        ("3M", "2026-05-31", "2026-02-28"),  # 말일 맞춤
        ("6M", "2026-10-16", "2026-04-16"),
        ("1M", "2026-10-31", "2026-09-30"),  # 31일 → 30일 달 말일
        ("YTD", "2026-10-16", "2025-12-31"),
    ],
)
def test_period_boundary(code, end, boundary):
    assert calc.period_boundary(code, end) == boundary


def test_change_over_uses_actual_dates_and_never_interpolates():
    pts = [("2026-04-15", 100.0), ("2026-04-20", 110.0), ("2026-10-15", 121.0)]
    c = calc.change_over(pts, "2026-04-16", "2026-10-16")
    assert (c["from_date"], c["to_date"], round(c["pct"], 6)) == (
        "2026-04-15",
        "2026-10-15",
        21.0,
    )
    assert (
        calc.change_over(pts, "2026-04-14", "2026-10-16") is None
    )  # 경계 이전 값 없음
    assert (
        calc.change_over([("2026-04-15", 100.0)], "2026-04-16", "2026-10-16") is None
    )  # 기간 안 값 없음
    assert (
        calc.change_over(
            [("2026-04-15", -5.0), ("2026-05-01", 1.0)], "2026-04-16", "2026-10-16"
        )["pct"]
        is None
    )


def test_cumulative_includes_first_day_and_flags_partial():
    days = _wd(5)
    pts = [(d, v) for d, v in zip(days, [10, -20, 30, -40, 50])]
    s = calc.period_sum(pts, days, "2026-03-31", days[-1])
    assert s == {
        "sum": 30,
        "days": 5,
        "expected": 5,
        "partial": False,
    }  # 첫날(+10) 포함 · 마지막 = 전 일자 합
    s = calc.period_sum(
        [p for p in pts if p[0] != days[2]], days, "2026-03-31", days[-1]
    )
    assert s == {
        "sum": 0,
        "days": 4,
        "expected": 5,
        "partial": True,
    }  # 빠진 날은 0 채우기 없이 부분 집계


def test_windows_complete_only():
    days = _wd(60)
    pts = [(d, -1.0) for d in days]
    w = calc.window(pts, days, days[-1], 0, 20)
    assert (w["sum"], w["from"], w["to"]) == (-20.0, days[40], days[59])
    assert calc.window(pts, days, days[-1], 20, 20)["to"] == days[39]
    assert calc.window(pts, days, days[-1], 0, 60)["sum"] == -60.0
    assert calc.window(pts[:-1] + [], days, days[-1], 0, 20) is None  # 마지막 날 빠짐
    assert calc.window(pts, days, days[-1], 0, 61) is None


# ── 단기(설계 §3-1) ───────────────────────────────────────────────────────────


def _series(changes, start=100.0):
    v, out = start, [("2026-01-01", start)]
    d = date(2026, 1, 1)
    for c in changes:
        v += c
        d += timedelta(days=1)
        out.append((d.isoformat(), v))
    return out


@pytest.mark.parametrize("last, flag", [(2.99, False), (3.0, True), (-3.0, True)])
def test_expansion_threshold_excludes_current_change(last, flag):
    pts = _series([1, -1] * 10 + [last])  # 기준 20개 평균 |Δ| = 1 · 원본 22개
    e = calc.short_term(pts)["expansion"]
    assert (
        e["flag"] is flag
        and e["base_mean"] == 1
        and round(e["ratio"], 2) == round(abs(last), 2)
    )
    # 기준 창 = 이번 관측 직전까지의 원본 21개(변화 20개) — 첫 값 ~ 직전 값
    assert (e["base_from"], e["base_to"]) == (pts[0][0], pts[-2][0])


def test_expansion_needs_22_values_and_zero_base():
    assert (
        calc.short_term(_series([1] * 20))["expansion"] is None
    )  # 21개 = 비교 자료 부족
    assert calc.short_term(_series([1] * 21))["expansion"] is not None  # 22개
    z = calc.short_term(_series([0] * 20 + [5]))["expansion"]
    assert z["zero_base"] and z["ratio"] is None and z["flag"] is True
    assert calc.short_term(_series([0] * 21))["expansion"]["flag"] is False


def test_d1_d5_and_range_break_with_ties():
    pts = _series([1] * 19 + [-30, 31])  # 마지막 값 = 이전 최고 120 과 같음? → 계산
    st_ = calc.short_term(pts)
    assert st_["d1"]["diff"] == 31 and st_["d5"]["from_date"] == pts[-6][0]
    hi = max(v for _, v in pts[-21:-1])
    tie = pts[:-1] + [(pts[-1][0], hi)]
    assert calc.short_term(tie)["range"] is None  # 같은 값 = 이탈 아님
    above = pts[:-1] + [(pts[-1][0], hi + 0.01)]
    assert calc.short_term(above)["range"]["dir"] == "위"
    below = pts[:-1] + [(pts[-1][0], min(v for _, v in pts[-21:-1]) - 0.01)]
    assert calc.short_term(below)["range"]["dir"] == "아래"


@pytest.mark.parametrize(
    "a, b, want",
    [
        (
            -30,
            -40,
            (
                "직전 20거래일보다 일평균 매도 감소",
                "일평균 매도 감소 (직전 20거래일 대비)",
            ),
        ),
        (
            -50,
            -40,
            (
                "직전 20거래일보다 일평균 매도 증가",
                "일평균 매도 증가 (직전 20거래일 대비)",
            ),
        ),
        (
            -40,
            -40,
            (
                "직전 20거래일과 일평균 매도 같음",
                "일평균 매도 같음 (직전 20거래일 대비)",
            ),
        ),
        (
            30,
            40,
            (
                "직전 20거래일보다 일평균 매수 감소",
                "일평균 매수 감소 (직전 20거래일 대비)",
            ),
        ),
        (10, -40, ("순매도 → 순매수 전환", "순매도 → 순매수 전환")),
        (-10, 40, ("순매수 → 순매도 전환", "순매수 → 순매도 전환")),
        (0, -40, ("한쪽 합이 0 이라 증감 · 전환을 말하지 않음",) * 2),
    ],
)
def test_twenty_day_trend_wording(a, b, want):
    from app.supply_fx_oil_context import _trend

    assert _trend({"sum": a, "avg": a / 20}, {"sum": b, "avg": b / 20}) == want


def test_pct_blank_when_previous_not_positive():
    pts = [("2026-01-01", 0.0), ("2026-01-02", 1.0)]
    assert calc.short_term(pts)["d1"]["pct"] is None


def test_flow_short_ratio_zero_base_and_shortage():
    days = _wd(21)
    base = [(d, (100 if i % 2 else -100) * E8) for i, d in enumerate(days[:20])]
    f = calc.flow_short(base + [(days[20], -300 * E8)], days)
    assert f["flag"] and round(f["ratio"], 6) == 3.0
    assert (f["base_from"], f["base_to"]) == (days[0], days[19])
    assert calc.flow_short(base + [(days[20], -299 * E8)], days)["flag"] is False
    z = calc.flow_short([(d, 0) for d in days[:20]] + [(days[20], 5 * E8)], days)
    assert z["note"] == "직전 20거래일 순매수 0" and z["flag"] is True
    assert calc.flow_short(base[:15], days)["note"] == "비교 자료 부족"
    # 직전 20 거래일 중 하루가 빠지면 목록에 20개가 있어도 비교하지 않는다(건너뛰어 창을 만들지 않음).
    days31 = _wd(31)
    gap = [(d, (100 if i % 2 else -100) * E8) for i, d in enumerate(days31[:30])]
    del gap[25]
    g = calc.flow_short(gap + [(days31[30], -300 * E8)], days31)
    assert g["note"] == "비교 자료 부족" and g["flag"] is False


def test_recent_events_cover_last_five_observations_only():
    pts = _series([1, -1] * 15 + [10, 1, -1, 1, -1, 1])  # 확대가 마지막에서 6번째 관측
    assert not [
        e for e in calc.price_events(pts, "WTI", "달러") if e["kind"] == "expansion"
    ]
    pts = _series([1, -1] * 15 + [10, 1, -1, 1, -1])  # 5번째 관측 = 포함
    ev = [e for e in calc.price_events(pts, "WTI", "달러") if e["kind"] == "expansion"]
    assert len(ev) == 1 and ev[0]["date"] == pts[-5][0] and "10.0배" in ev[0]["text"]


def test_won_format():
    assert calc.won(-157.8 * 10**4 * E8) == "-157.8조원"
    assert (
        calc.won(-1850 * E8) == "-1,850억원"
        and calc.won(0) == "0억원"
        and calc.won(316 * E8) == "+316억원"
    )


# ── 조립 · API ──────────────────────────────────────────────────────────────


def _seed(
    db: Path, *, kdays, flows=True, fx_tail=None, oil=None, vix_up=True, macro=True
):
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="코스피",
        rows=[(d, 3000.0 - i) for i, d in enumerate(kdays)],
        source="TEST",
        db_path=db,
    )
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=[(d, 15.0 + (i if vix_up else -i) * 0.01) for i, d in enumerate(kdays)],
        source="TEST",
        db_path=db,
    )
    if flows:
        rows = []
        for d in kdays[:-1]:  # 마지막 코스피 날짜 = 수급 아직 없음 → D 는 그 전날
            rows += [
                (d, "foreign", -1000 * E8),
                (d, "individual", 900 * E8),
                (d, "institution", 50 * E8),
                (d, "other_corp", 50 * E8),
            ]
        st.upsert_investor_flows(rows=rows, db_path=db)
    if not macro:
        return
    fx_days = kdays + (fx_tail or [])
    u, p, b = st.MACRO_SERIES[st.USDKRW]
    st.upsert_macro_daily(
        series_id=st.USDKRW,
        rows=[(d, 1400.0 + i) for i, d in enumerate(fx_days)],
        unit=u,
        provider=p,
        basis=b,
        db_path=db,
    )
    u, p, b = st.MACRO_SERIES[st.WTI]
    st.upsert_macro_daily(
        series_id=st.WTI,
        rows=oil or [(d, 80.0 - i * 0.1) for i, d in enumerate(kdays)],
        unit=u,
        provider=p,
        basis=b,
        db_path=db,
    )


def test_context_d_is_common_date_and_e_can_be_later(tmp_path):
    db = tmp_path / "m.sqlite"
    kdays = _wd(140, "2026-04-01")
    _seed(db, kdays=kdays, fx_tail=["2026-12-31"])
    out = build_market_flow_context(db_path=db)
    assert out["D"] == kdays[-2] and out["has_flows"]
    assert (
        out["series"]["usdkrw"]["E"] == "2026-12-31"
    )  # 환율이 D 보다 늦어도 단기는 E 로
    fx_line = next(r for r in out["short_lines"] if r["text"].startswith("원/달러"))
    assert "12/31" in fx_line["text"]
    kospi_line = next(r for r in out["short_lines"] if r["text"].startswith("코스피"))
    assert not any(f.startswith("늦음") for f in kospi_line["flags"])
    p = out["periods"]["6M"]
    f = p["investors"]["foreign"]
    assert f["sum"] == -1000 * E8 * f["days"] and not f["partial"]
    assert any(line.startswith("외국인 누적 순매도") for line in p["lines"])
    # 매일 같은 순매도 → 최근 20 · 직전 20 일평균이 같다 = '같음'(증가 · 감소로 쓰지 않음)
    assert out["windows"]["lines"][1] == "직전 20거래일과 일평균 매도 같음"
    assert (
        "최근 20거래일 일평균 매도 같음 (직전 20거래일 대비)" in out["today_lines"][0]
    )


def test_context_interpretation_rows(tmp_path):
    db = tmp_path / "m.sqlite"
    kdays = _wd(140, "2026-04-01")
    _seed(
        db, kdays=kdays
    )  # 코스피 하락 · 외국인 순매도 · 원/달러 상승 · 유가 하락 · VIX 상승
    rows = build_market_flow_context(db_path=db)["interpretation"]["6M"]["rows"]
    assert [r[0] for r in rows] == [
        "코스피 하락 · 외국인 순매도 · 원/달러 상승",
        "유가 하락 · VIX 상승(글로벌 위험 회피)",
    ]
    db2 = tmp_path / "m2.sqlite"
    _seed(
        db2,
        kdays=kdays,
        vix_up=False,
        oil=[(d, 80.0 + i * 0.1) for i, d in enumerate(kdays)],
    )
    rows2 = build_market_flow_context(db_path=db2)["interpretation"]["6M"]["rows"]
    assert [r[0] for r in rows2] == [
        "코스피 하락 · 외국인 순매도 · 원/달러 상승"
    ]  # 유가 상승 = 표에 없는 조합 · 만들지 않음
    db3 = tmp_path / "m3.sqlite"
    _seed(db3, kdays=kdays, vix_up=False)  # 유가 하락 · VIX 하락
    rows3 = build_market_flow_context(db_path=db3)["interpretation"]["6M"]["rows"]
    assert rows3[-1][0] == "유가 하락 · VIX 하락(글로벌 시장 견조)"
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=[(d, 15.0) for d in kdays],
        source="TEST",
        db_path=db3,
    )  # VIX 기간 변화 0 = 상승도 하락도 아님 → 유가 해석 줄 없음
    rows4 = build_market_flow_context(db_path=db3)["interpretation"]["6M"]["rows"]
    assert [r[0] for r in rows4] == ["코스피 하락 · 외국인 순매도 · 원/달러 상승"]


def test_context_without_flows_says_so_and_never_zero_fills(tmp_path):
    db = tmp_path / "m.sqlite"
    kdays = _wd(30, "2026-09-01")
    _seed(db, kdays=kdays, flows=False)
    out = build_market_flow_context(db_path=db)
    assert out["D"] == kdays[-1] and not out["has_flows"]
    assert any(
        "투자자별 수급 자료 없음" in line for line in out["periods"]["1M"]["lines"]
    )
    assert (
        "0억원" not in out["ai_text"]["1M"]
        and "투자자별 수급 자료 없음" in out["today_lines"][0]
    )


def test_context_stale_flag_and_partial(tmp_path):
    db = tmp_path / "m.sqlite"
    kdays = _wd(60, "2026-08-01")
    _seed(db, kdays=kdays, oil=[(d, 80.0) for d in kdays[:30]])
    con = sqlite3.connect(db)
    con.execute(
        "DELETE FROM market_investor_flow_daily WHERE trade_date = ?", (kdays[40],)
    )
    con.commit()
    out = build_market_flow_context(db_path=db)
    wti_line = next(r for r in out["short_lines"] if r["text"].startswith("WTI"))
    assert any(f.startswith("늦음 — 최신") for f in wti_line["flags"])
    assert out["periods"]["1M"]["investors"]["foreign"]["partial"]
    assert (
        "외국인 20거래일 비교 — 자료가 온전하지 않아 표시하지 않음"
        in out["windows"]["lines"]
    )


def test_ai_text_has_same_numbers_and_no_blank_lines(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, kdays=_wd(140, "2026-04-01"))
    out = build_market_flow_context(db_path=db)
    for code in ("1M", "3M", "6M", "YTD"):
        text = out["ai_text"][code]
        assert "\n\n" not in text and text == ai_text(out, code)
        for line in out["periods"][code]["lines"] + out["windows"]["lines"]:
            assert f"- {line}" in text
    assert out["limits"][0] in out["ai_text"]["6M"]


def test_empty_db_context_and_api_never_write(tmp_path, monkeypatch):
    db = tmp_path / "none.sqlite"
    out = build_market_flow_context(db_path=db)
    assert out["D"] is None and set(out["ai_text"]) == {"1M", "3M", "6M", "YTD"}
    assert not db.exists()
    monkeypatch.setattr(api_supply_fx_oil, "_DB_PATH", db)
    from app.api import app

    r = TestClient(app).get("/market/flow-context")
    assert r.status_code == 200 and r.json()["D"] is None and not db.exists()


def test_api_returns_all_periods_and_lines(tmp_path, monkeypatch):
    db = tmp_path / "m.sqlite"
    _seed(db, kdays=_wd(140, "2026-04-01"))
    before = (
        sqlite3.connect(db).execute("SELECT count(*) FROM sqlite_master").fetchone()
    )
    monkeypatch.setattr(api_supply_fx_oil, "_DB_PATH", db)
    from app.api import app

    body = TestClient(app).get("/market/flow-context").json()
    assert set(body["periods"]) == {"1M", "3M", "6M", "YTD"} and body["has_flows"]
    assert set(body["series"]["flows"]["investors"]) == {
        "foreign",
        "individual",
        "institution",
        "other_corp",
    }
    assert (
        body["periods"]["6M"]["lines"]
        == build_market_flow_context(db_path=db)["periods"]["6M"]["lines"]
    )
    assert (
        sqlite3.connect(db).execute("SELECT count(*) FROM sqlite_master").fetchone()
        == before
    )
    # 새 칸이 응답 모델에서 빠지지 않음(검증자 r1 — 사건 확인 범위 · 기간별 해석 모양)
    assert set(body["event_check"]) == {
        "checked",
        "unchecked",
        "unchecked_text",
        "empty_text",
    }
    assert set(body["interpretation"]["6M"]) == {"rows", "notes"}


def test_interpretation_follows_each_period_and_ai_text(tmp_path):
    """해석 = 고른 기간의 변화로(기간 선택은 묶음 전체에 하나) · AI 글 제목 · 수집 시각 · 오늘 줄 D."""
    db = tmp_path / "m.sqlite"
    kdays = _wd(140, "2026-04-01")
    n = len(kdays)
    # 6개월 = 원/달러 상승 · 최근 1개월 = 원/달러 하락
    fx = [(d, 1400.0 + i if i < n - 15 else 1600.0 - i) for i, d in enumerate(kdays)]
    _seed(db, kdays=kdays)
    u, p, b = st.MACRO_SERIES[st.USDKRW]
    st.upsert_macro_daily(
        series_id=st.USDKRW, rows=fx, unit=u, provider=p, basis=b, db_path=db
    )
    out = build_market_flow_context(db_path=db)
    assert (
        out["interpretation"]["6M"]["rows"][0][0]
        == "코스피 하락 · 외국인 순매도 · 원/달러 상승"
    )
    assert (
        out["interpretation"]["1M"]["rows"][0][0]
        == "코스피 하락 · 외국인 순매도 · 원/달러 하락"
    )
    assert "[가능한 해석 — 1개월 기준 · 확정이 아님]" in out["ai_text"]["1M"]
    assert (
        "원/달러 하락" in out["ai_text"]["1M"]
        and "원/달러 상승 →" not in out["ai_text"]["1M"]
    )
    tail = out["ai_text"]["6M"].split("[자료 기준일] ")[1].split("\n")[0]
    assert tail.count("(수집 ") == 4 and " KST)" in tail and "코스피 " in tail
    assert out["status"][0]["collected_at"]  # 코스피 = 최신 저장 행의 저장 시각
    assert out["today_lines"][0].startswith(
        f"시장 흐름 6개월({calc.md(out['D'])}까지): "
    )


def test_kst_stamp():
    from app.supply_fx_oil_context import kst_stamp

    assert kst_stamp("2026-10-20T12:33:40Z") == "10/20 21:33 KST"
    assert kst_stamp(None) == "—" and kst_stamp("x") == "—"


# ── 검증자 r1 정정 — 확인할 수 없는 것을 '없음 · 해당 없음'으로 쓰지 않음 ─────────────────


def _drop(db: Path, sql: str, *args) -> None:
    con = sqlite3.connect(db)
    con.execute(sql, args)
    con.commit()
    con.close()


def _flat(db: Path, benchmark_id: str, days, base: float) -> None:
    """번갈아 오르내리는 값(변화 크기 늘 1 · 범위 이탈 없음) = 큰 변화 없는 계열."""
    upsert_benchmark_prices(
        benchmark_id=benchmark_id,
        benchmark_name=benchmark_id,
        rows=[(d, base + (i % 2)) for i, d in enumerate(days)],
        source="TEST",
        db_path=db,
    )


def _flat_macro(db: Path, days) -> None:
    for sid, base in ((st.USDKRW, 1400.0), (st.WTI, 80.0)):
        u, p, b = st.MACRO_SERIES[sid]
        st.upsert_macro_daily(
            series_id=sid,
            rows=[(d, base + (i % 2)) for i, d in enumerate(days)],
            unit=u,
            provider=p,
            basis=b,
            db_path=db,
        )


def test_today_line_shows_partial_flows_and_unavailable_20day(tmp_path):
    """F1 — 기간 중 하루 수급이 빠지면 오늘 첫 줄 · 기간 줄 · 해석이 모두 부분 집계를 말한다."""
    db = tmp_path / "m.sqlite"
    kdays = _wd(140, "2026-04-01")
    _seed(db, kdays=kdays)
    _drop(db, "DELETE FROM market_investor_flow_daily WHERE trade_date = ?", kdays[-10])
    out = build_market_flow_context(db_path=db)
    f = out["periods"]["6M"]["investors"]["foreign"]
    assert f["partial"] and f["days"] == f["expected"] - 1
    part = f"부분 집계 {f['days']}/{f['expected']}일"
    assert part in out["today_lines"][0]
    assert "최근 20거래일 비교 불가(자료가 온전하지 않음)" in out["today_lines"][0]
    assert any(part in line for line in out["periods"]["6M"]["lines"])
    it = out["interpretation"]["6M"]
    assert [r[0] for r in it["rows"]] == ["유가 하락 · VIX 상승(글로벌 위험 회피)"]
    assert it["notes"][0] == (
        "확인 못 한 조합: 코스피 하락 · 외국인 순매도 · 원/달러 — "
        f"외국인 수급 부분 집계({f['days']}/{f['expected']}일)"
    )
    assert f"- {it['notes'][0]}" in out["ai_text"]["6M"]


def test_uncovered_period_is_partial_not_silent(tmp_path):
    """기간 경계 이전 저장 자료가 없으면 '부분 기간' · 코스피 줄을 빼지 않고 '자료 없음'."""
    db = tmp_path / "m.sqlite"
    kdays = _wd(60, "2026-07-01")
    _seed(db, kdays=kdays)
    out = build_market_flow_context(db_path=db)
    p6 = out["periods"]["6M"]
    assert p6["covered"] is False and out["periods"]["1M"]["covered"] is True
    assert p6["lines"][0].startswith(
        f"부분 기간 — {p6['boundary']} 이전 저장 자료가 없어 {kdays[0]}부터만"
    )
    assert "코스피 자료 없음(기간을 덮는 저장 값이 없음)" in p6["lines"]
    assert any(f"부분 기간({p6['start']}부터)" in line for line in p6["lines"])
    l1 = out["today_lines"][0]
    assert (
        "코스피 자료 없음(기간 시작 전 값 없음)" in l1
        and f"부분 기간({p6['start']}부터)" in l1
    )
    assert "코스피 기간 변화 계산 불가" in out["interpretation"]["6M"]["notes"][0]


def test_events_check_none_partial_and_all(tmp_path):
    """F2 — 최근 큰 변화 '없음'은 모든 자료를 비교했을 때만. 아니면 확인 못 한 자료 · 사유."""
    # (1) 관측 10개 = 아무것도 비교 못 함
    db = tmp_path / "a.sqlite"
    _seed(db, kdays=_wd(10, "2026-09-01"))
    out = build_market_flow_context(db_path=db)
    chk = out["event_check"]
    assert (
        chk["checked"] == []
        and [u["reason"] for u in chk["unchecked"]] == ["비교 자료 부족"] * 5
    )
    assert out["today_lines"][1] == (
        "최근 5개 관측: 큰 변화를 확인하지 못함 — 코스피 비교 자료 부족 · 원/달러 비교 자료 부족 · "
        "WTI 비교 자료 부족 · 외국인 비교 자료 부족 · 기관계 비교 자료 부족"
    )
    assert "큰 변화 없음" not in out["today_lines"][1]
    assert f"- {out['today_lines'][1]}" in out["ai_text"]["6M"]
    # (2) 환율 · WTI 자료 없음 · 나머지는 큰 변화 없음
    db = tmp_path / "b.sqlite"
    kdays = _wd(140, "2026-04-01")
    _seed(db, kdays=kdays, macro=False)
    _flat(db, "KOSPI", kdays, 3000.0)
    out = build_market_flow_context(db_path=db)
    assert out["events"] == []
    assert out["today_lines"][1] == (
        "최근 5개 관측: 확인한 자료(코스피 · 외국인 · 기관계)에서는 표시 기준에 해당하는 큰 변화 없음"
        " · 확인 못 한 자료 — 원/달러 자료 없음 · WTI 자료 없음"
    )
    # (3) 사건이 있어도 확인 못 한 자료는 함께 적는다
    db = tmp_path / "c.sqlite"
    _seed(db, kdays=kdays, macro=False)  # 코스피 매일 하락 = 범위 아래 사건
    out = build_market_flow_context(db_path=db)
    assert out["events"] and out["today_lines"][1].endswith(
        " · 확인 못 한 자료 — 원/달러 자료 없음 · WTI 자료 없음"
    )
    assert (
        "- 확인 못 한 자료 — 원/달러 자료 없음 · WTI 자료 없음" in out["ai_text"]["6M"]
    )
    # (4) 모두 비교했고 해당 없음 = 그때만 '큰 변화 없음'
    db = tmp_path / "d.sqlite"
    _seed(db, kdays=kdays, macro=False)
    _flat(db, "KOSPI", kdays, 3000.0)
    _flat_macro(db, kdays)
    out = build_market_flow_context(db_path=db)
    assert (
        out["event_check"]["unchecked"] == []
        and out["event_check"]["unchecked_text"] is None
    )
    assert out["today_lines"][1] == (
        "최근 5개 관측: 표시 기준(이전 20회 평균 변화의 3배 · 직전 20개 범위)에 해당하는 큰 변화 없음"
        " — 안정이라는 뜻은 아님"
    )
    # (5) 수급 자료 없음 = 단기 줄에도 행이 있고 확인 못 한 자료로 센다
    db = tmp_path / "e.sqlite"
    _seed(db, kdays=kdays, flows=False)
    out = build_market_flow_context(db_path=db)
    texts = [r["text"] for r in out["short_lines"]]
    assert "외국인 수급 자료 없음" in texts and "기관계 수급 자료 없음" in texts
    assert {"label": "외국인", "reason": "자료 없음"} in out["event_check"]["unchecked"]


@pytest.mark.parametrize("n, checked", [(10, 0), (22, 1), (25, 4), (26, 5), (40, 5)])
def test_price_event_coverage_counts_comparable_recent_observations(n, checked):
    assert calc.price_event_coverage(_series([1, -1] * 20)[:n]) == (checked, 5)


def test_flow_event_coverage_and_partial_reason(tmp_path):
    days = _wd(26)
    net = [(d, -100 * E8) for d in days]
    assert calc.flow_event_coverage(net, days) == (5, 5)
    # days[2] 가 빠지면 최근 5개 관측(days[21] ~ days[25]) 중 앞 2개의 직전 20 거래일에 빈 날이 생긴다
    assert calc.flow_event_coverage([p for p in net if p[0] != days[2]], days) == (3, 5)
    # days[10] 은 다섯 관측 모두의 기준 창 안 → 하나도 비교 못 함
    assert calc.flow_event_coverage([p for p in net if p[0] != days[10]], days) == (
        0,
        5,
    )
    db = tmp_path / "m.sqlite"
    kdays = _wd(140, "2026-04-01")
    _seed(db, kdays=kdays)
    _drop(db, "DELETE FROM market_investor_flow_daily WHERE trade_date = ?", kdays[-25])
    reasons = {
        u["label"]: u["reason"]
        for u in build_market_flow_context(db_path=db)["event_check"]["unchecked"]
    }
    assert reasons["외국인"].startswith("비교 자료 부족(최근 5개 관측 중 ")


def test_flow_zero_base_observation_stays_in_recent_events():
    """F3 — 직전 20거래일 순매수 0 뒤 발생한 관측도 최근 5개 사건에 남는다(배수 없이 사실만)."""
    days = _wd(26)
    net = [(d, 0.0) for d in days[:23]] + [
        (days[23], -1 * E8),
        (days[24], 0.0),
        (days[25], 0.0),
    ]
    ev = calc.flow_events(net, "외국인", days)
    assert [e["date"] for e in ev] == [days[23]]
    assert ev[0]["text"] == (
        f"{calc.md(days[23])} 외국인 직전 20거래일 순매수 0, 이번 순매도 -1억원"
    )


def test_interpretation_notes_never_turn_missing_into_not_applicable(tmp_path):
    kdays = _wd(140, "2026-04-01")
    # 유가 하락 · VIX 가 기간을 덮지 않음 → 확인 못 한 조합(규칙 1 은 정상 행)
    db = tmp_path / "a.sqlite"
    _seed(db, kdays=kdays)
    b = build_market_flow_context(db_path=db)["periods"]["6M"]["boundary"]
    _drop(
        db,
        "DELETE FROM market_benchmark_daily_price WHERE benchmark_id = 'VIX' AND date <= ?",
        b,
    )
    it = build_market_flow_context(db_path=db)["interpretation"]["6M"]
    assert [r[0] for r in it["rows"]] == ["코스피 하락 · 외국인 순매도 · 원/달러 상승"]
    assert it["notes"] == [
        "확인 못 한 조합: 유가 하락 · VIX — VIX 기간 변화 계산 불가(기간을 덮는 저장 값 없음)"
    ]
    # 환율 · WTI 자료 없음 → 두 조합 모두 확인 못 함('해당 규칙 없음'을 말하지 않음)
    db = tmp_path / "b.sqlite"
    _seed(db, kdays=kdays, macro=False)
    it = build_market_flow_context(db_path=db)["interpretation"]["6M"]
    assert it["rows"] == [] and it["notes"] == [
        "확인 못 한 조합: 코스피 하락 · 외국인 순매도 · 원/달러 — 원/달러 기간 변화 계산 불가",
        "확인 못 한 조합: 유가 하락 · VIX — WTI 기간 변화 계산 불가",
    ]
    # 하나는 확인 못 함 · 하나는 확인했고 해당 없음
    db = tmp_path / "c.sqlite"
    _seed(db, kdays=kdays, oil=[(d, 80.0 + i * 0.1) for i, d in enumerate(kdays)])
    _drop(db, "DELETE FROM market_macro_daily WHERE series_id = ?", st.USDKRW)
    it = build_market_flow_context(db_path=db)["interpretation"]["6M"]
    assert it["rows"] == [] and it["notes"] == [
        "확인 못 한 조합: 코스피 하락 · 외국인 순매도 · 원/달러 — 원/달러 기간 변화 계산 불가",
        "확인한 조합에는 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)",
    ]
    # 모두 확인했고 해당 없음(코스피 상승 · 유가 상승)
    db = tmp_path / "d.sqlite"
    _seed(db, kdays=kdays, oil=[(d, 80.0 + i * 0.1) for i, d in enumerate(kdays)])
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="코스피",
        rows=[(d, 3000.0 + i) for i, d in enumerate(kdays)],
        source="TEST",
        db_path=db,
    )
    it = build_market_flow_context(db_path=db)["interpretation"]["6M"]
    assert it == {
        "rows": [],
        "notes": ["지금 조합에 해당하는 해석 규칙 없음(설명을 만들어 내지 않음)"],
    }


def test_sixty_day_window_incomplete_is_said(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, kdays=_wd(50, "2026-08-03"))
    lines = build_market_flow_context(db_path=db)["windows"]["lines"]
    assert "외국인 60거래일 — 자료가 온전하지 않아 표시하지 않음" in lines
