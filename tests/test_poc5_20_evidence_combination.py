"""POC5-20 — 가격 · 거래량 · 변동성 근거 조합의 과거 사례 대조(읽기 전용 연구 산출).

설계 docs/ai_design/POC5/POC5-20_OBSERVED_EVIDENCE_COMBINATION_REVIEW_DESIGN_V1.md §3 · §4 · §5 · §6-2
PLAN docs/ai_plan/POC5/POC5-20_OBSERVED_EVIDENCE_COMBINATION_REVIEW_PLAN_V1.md §2 · §5(판정 반영)
모두 tmp 시장 DB · tmp 캘린더 · tmp 보유 파일 — 라이브 자료를 열지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pytest

from app import pc_price_basis
from app.evidence_combo import observations as obs
from app.evidence_combo import report as rep
from app.evidence_combo import tables as tab
from app.evidence_combo.render import render_md
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.pc_price_volatility import build_price_volatility
from app.stored_volume_evidence import build_stored_volume_evidence

HOLIDAY = "2026-03-02"
CAL = [
    d.isoformat()
    for d in (date(2026, 1, 2) + timedelta(days=i) for i in range(363))
    if d.weekday() < 5 and d.isoformat() != HOLIDAY and d.year == 2026
]
KST = timezone(timedelta(hours=9))


def _env(tmp_path: Path, holdings: list[dict[str, Any]]) -> dict[str, Path]:
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    (cal_dir / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(CAL) + "\n", encoding="utf-8"
    )
    hp = tmp_path / "holdings_latest.json"
    hp.write_text(
        json.dumps({"holdings": holdings}, ensure_ascii=False), encoding="utf-8"
    )
    return {"db": tmp_path / "m.sqlite", "cal": cal_dir, "holdings": hp}


def _h(ticker: str, account: str = "일반") -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": ticker + "명",
        "account_group": account,
        "quantity": 7,
        "avg_buy_price": 12345,
    }


def _master(db: Path, *tickers: str) -> None:
    upsert_etf_master(
        [EtfMasterRow(t, t, None, None, None, None) for t in tickers],
        source="test",
        db_path=db,
    )


def _prices(
    db: Path,
    ticker: str,
    dates: list[str],
    closes: list[Optional[float]],
    volumes: list[Optional[float]],
    *,
    bad_change_at: Optional[str] = None,
) -> None:
    """저장 change = 직전 저장 행 대비 변화(FDR 연결 판정과 맞음) · bad_change_at 은 일부러 어긋나게."""
    rows, prev = [], None
    for d, c, v in zip(dates, closes, volumes):
        ch = 0.0 if (prev is None or c is None) else c / prev - 1.0
        if d == bad_change_at:
            ch += 0.05
        rows.append(EtfDailyPriceRow(ticker, d, c, c, c, c, v, ch))
        if c is not None:
            prev = c
    upsert_daily_prices(rows, source="FinanceDataReader", db_path=db)


def _wave(n: int, base: float = 100.0) -> list[float]:
    return [round(base + 2.0 * math.sin(i * 0.7) + 0.3 * i, 4) for i in range(n)]


def _load(env: dict[str, Path], end: str) -> rep.InputCopy:
    return rep.load_inputs(
        end, db_path=env["db"], holdings_path=env["holdings"], calendar_dir=env["cal"]
    )


# ── 정의 대조 · t 이하 입력만 ───────────────────────────────────────────────────
def test_same_as_existing_pc_definitions_on_latest_date(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111", "069500")
    days = [d for d in CAL if d <= "2026-06-30"][-80:]
    closes = _wave(80)
    closes[-21], closes[-1] = 100.0, 94.0  # 20저장일 −6% → 5~8% 하락
    vols = [1000 + 37 * (i % 9) for i in range(80)]
    _prices(env["db"], "AAA111", days, closes, vols)
    _prices(env["db"], "069500", days, _wave(80, 300.0), vols)
    d = days[-1]
    inp = _load(env, d)
    reason, got = obs.observe(inp.series["AAA111"], d)
    assert reason is None
    rows = pc_price_basis.load_recent_price_rows(["AAA111"], db_path=env["db"])
    flow = pc_price_basis._flow_from_rows(rows["AAA111"], rows["069500"])
    band = pc_price_basis._decline_band(flow, pc_price_basis.COMPARISON_OK)
    assert (got["band"], got["return_20d_pct_1dp"]) == (
        band["state"],
        band["return_20d_pct_1dp"],
    )
    assert got["band"] == "D5_8"
    assert (
        got["volume_ratio"]
        == build_stored_volume_evidence("AAA111", db_path=env["db"]).ratio
    )
    pv = build_price_volatility(
        [{"ticker": "AAA111", "price_dates": {"end_date": d}}],
        reference_date=d,
        db_path=env["db"],
    )["AAA111"]
    assert got["volatility_comparison"] == pv.comparison


def test_inputs_after_t_do_not_change_observations(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-07-31"][-100:]
    _prices(env["db"], "AAA111", days, _wave(100), [1000 + i for i in range(100)])
    t = days[60]
    before = obs.observe(_load(env, days[-1]).series["AAA111"], t)
    later = days[61:]
    _prices(env["db"], "AAA111", later, [999.0] * len(later), [9_999_999] * len(later))
    after = obs.observe(_load(env, days[-1]).series["AAA111"], t)
    assert before == after and before[0] is None


# ── 거래량 경계(판정 Q1 (b)) · 0 · 결측 ───────────────────────────────────────────
def test_volume_boundary_uses_raw_ratio() -> None:
    assert [obs.volume_above(r) for r in (0.996, 1.000, 1.004)] == [False, False, True]


@pytest.mark.parametrize(
    "t_volume, window_volume, expect",
    [
        (1004, 1000, ("ok", True)),
        (1000, 1000, ("ok", False)),
        (996, 1000, ("ok", False)),
        (0, 1000, ("ok", False)),  # 저장된 0 은 유효 → 평균 이하
        (None, 1000, ("volume_missing", None)),
        (500, 0, ("avg_zero", None)),
    ],
)
def test_volume_classification_and_reasons(
    tmp_path: Path, t_volume: Any, window_volume: Any, expect: tuple
) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-06-30"][-60:]
    vols: list[Any] = [window_volume] * 60
    vols[-1] = t_volume
    _prices(env["db"], "AAA111", days, _wave(60), vols)
    reason, got = obs.observe(_load(env, days[-1]).series["AAA111"], days[-1])
    if expect[0] == "ok":
        assert reason is None and got["volume_above"] is expect[1]
    else:
        assert reason == expect[0]


def test_missing_volume_in_window_is_avg_insufficient(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-06-30"][-60:]
    vols: list[Any] = [1000] * 60
    vols[-5] = None
    _prices(env["db"], "AAA111", days, _wave(60), vols)
    assert (
        obs.observe(_load(env, days[-1]).series["AAA111"], days[-1])[0]
        == "avg_insufficient"
    )


# ── 이후 20거래일: 캘린더 · 휴장 · 결측 · 연결 · 미도래 ───────────────────────────────
def test_outcome_counts_calendar_days_skips_holiday_and_values(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-04-30"]
    closes = [100.0 + i for i in range(len(days))]
    t = "2026-02-20"
    k = days.index(t)
    closes[k + 3] = closes[k] * 0.95  # 경로 중 −5% 하락
    _prices(env["db"], "AAA111", days, closes, [1000] * len(days))
    inp = _load(env, "2026-04-30")
    reason, out = obs.outcome(inp.series["AAA111"], t, inp.calendar, inp.end)
    assert reason is None
    fut = [d for d in CAL if d > t][:20]
    assert HOLIDAY not in fut and fut[-1] == days[k + 20]  # 휴장일은 캘린더에서 건너뜀
    assert out["end_change_pct"] == pytest.approx(
        (closes[k + 20] / closes[k] - 1) * 100
    )
    assert out["min_change_pct"] == pytest.approx(-5.0)
    # 경로가 모두 기준일 종가보다 높으면 최저 종가 변화는 0(min(0, …)) · 끝점은 양수.
    t2 = days[k + 5]
    reason2, out2 = obs.outcome(inp.series["AAA111"], t2, inp.calendar, inp.end)
    assert (
        reason2 is None and out2["min_change_pct"] == 0.0 and out2["end_change_pct"] > 0
    )


def test_outcome_missing_day_is_not_filled_and_basis_and_not_matured(
    tmp_path: Path,
) -> None:
    env = _env(tmp_path, [_h("AAA111"), _h("BBB222")])
    _master(env["db"], "AAA111", "BBB222")
    days = [d for d in CAL if d <= "2026-04-30"]
    t = "2026-02-20"
    k = days.index(t)
    gap = days[k + 7]
    _prices(
        env["db"],
        "AAA111",
        [d for d in days if d != gap],
        [100.0 + i for i in range(len(days) - 1)],
        [1000] * (len(days) - 1),
    )
    _prices(
        env["db"],
        "BBB222",
        days,
        [100.0 + i for i in range(len(days))],
        [1000] * len(days),
        bad_change_at=days[k + 4],
    )
    inp = _load(env, "2026-04-30")
    assert (
        obs.outcome(inp.series["AAA111"], t, inp.calendar, inp.end)[0] == "path_missing"
    )
    assert (
        obs.outcome(inp.series["BBB222"], t, inp.calendar, inp.end)[0] == "path_basis"
    )
    assert (
        obs.outcome(inp.series["BBB222"], days[-5], inp.calendar, inp.end)[0]
        == "not_matured"
    )


# ── 대상 · 사유 순서 · 공통 표본 분모 ─────────────────────────────────────────────
def test_holdings_dedup_non_etf_and_reason_order(tmp_path: Path) -> None:
    env = _env(
        tmp_path, [_h("AAA111"), _h("AAA111", "ISA"), _h("STK999"), _h("NEW333")]
    )
    _master(env["db"], "AAA111", "NEW333")
    days = [d for d in CAL if d <= "2026-08-31"]
    _prices(
        env["db"],
        "AAA111",
        days,
        _wave(len(days)),
        [1000 + (i % 7) for i in range(len(days))],
    )
    late = [d for d in days if d >= "2026-04-01"]
    closes: list[Any] = _wave(len(late))
    closes[10] = None  # 그날 종가 없음(행은 있음)
    _prices(env["db"], "NEW333", late, closes, [1000] * len(late))
    inp = _load(env, "2026-08-31")
    assert inp.held_tickers == ("AAA111", "NEW333", "STK999")
    assert inp.etf_targets == ("AAA111", "NEW333") and inp.non_etf == ("STK999",)
    r = rep.build_report(inp, input_hash="x", generated_at="g")
    ex = {e["code"]: e["count"] for e in r["exclusions"]}
    assert r["universe"]["pairs"] == 2 * len(inp.base_dates)
    assert sum(ex.values()) + r["common_sample"] == r["universe"]["pairs"]
    assert ex["before_first_stored"] == sum(
        1 for d in inp.base_dates if d < "2026-04-01"
    )
    assert ex["no_close_on_t"] == 1
    assert ex["decline_short"] > 0  # NEW333 상장 직후
    for table in r["tables"].values():
        for row in table:
            parts = [c["n"] for c in row["combos"].values()]
            assert row["all"]["n"] == sum(parts)  # 같은 표본 · 같은 분모
    assert sum(row["all"]["n"] for row in r["tables"]["all"]) == r["common_sample"]
    assert (
        sum(row["all"]["n"] for row in r["tables"]["front"])
        + sum(row["all"]["n"] for row in r["tables"]["back"])
        == r["common_sample"]
    )


# ── 알려진 작은 표 ───────────────────────────────────────────────────────────────
def _rec(
    t: str, d: str, end: float, mn: float, up: bool, vup: bool, band: str = "D5_8"
) -> obs.Record:
    return obs.Record(
        t,
        d,
        band,
        -6.0,
        1.5 if up else 0.8,
        up,
        "higher" if vup else "lower",
        vup,
        end,
        mn,
    )


def test_small_table_statistics_and_empty_cell() -> None:
    recs = [
        _rec("A", "2026-03-02", -4.0, -6.0, True, True),
        _rec("B", "2026-03-02", -2.0, -3.0, True, True),
        _rec("A", "2026-03-03", 0.0, -1.0, True, True),
        _rec("C", "2026-03-04", 2.0, 0.0, True, True),
        _rec("C", "2026-03-05", 10.0, 0.0, True, True),
    ]
    c = tab.cell(recs)
    assert (c["n"], c["tickers"], c["dates"]) == (5, 3, 4)
    e = c["end_change_pct"]
    assert (e["median"], e["p25"], e["p75"]) == (0.0, -2.0, 2.0)
    # 날짜별 중앙값: 03-02 = −3 · 03-03 = 0 · 03-04 = 2 · 03-05 = 10 → 중앙값 1.0
    assert e["date_median_of_medians"] == 1.0
    table = tab.band_table(recs)
    row = next(x for x in table if x["band"] == "D5_8")
    assert row["combos"]["vol_above__vola_up"]["n"] == 5
    assert row["combos"]["vol_below__vola_not_up"] == {
        "n": 0,
        "tickers": 0,
        "dates": 0,
        "empty": True,
    }
    assert next(x for x in table if x["band"] == "D10_PLUS")["all"]["empty"] is True


def test_split_halves_front_is_longer_when_odd() -> None:
    days = [f"d{i:03d}" for i in range(159)]
    front, back = tab.split_halves(days)
    assert (len(front), len(back)) == (80, 79) and front[-1] < back[0]
    assert tab.split_halves(["a"]) == (["a"], [])


# ── 실행 · 결정성 · 개인 정보 · 쓰기 0 · 종료일 ─────────────────────────────────────
def test_run_is_deterministic_private_free_and_read_only(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111"), _h("AAA111", "ISA")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-08-31"]
    _prices(
        env["db"],
        "AAA111",
        days,
        _wave(len(days)),
        [1000 + (i % 11) * 13 for i in range(len(days))],
    )
    digest = hashlib.sha256(env["db"].read_bytes()).hexdigest()
    kw = dict(
        db_path=env["db"],
        holdings_path=env["holdings"],
        calendar_dir=env["cal"],
        root=tmp_path / "out",
    )
    a = rep.run("2026-08-31", now=datetime(2026, 10, 17, 9, 0, 0, tzinfo=KST), **kw)
    b = rep.run("2026-08-31", now=datetime(2026, 10, 17, 9, 0, 1, tzinfo=KST), **kw)
    assert a != b and a.name.startswith("2026-08-31_")
    ra, rb = (
        json.loads((x / "report.json").read_text(encoding="utf-8")) for x in (a, b)
    )
    assert ra["body_hash"] == rb["body_hash"] and ra["input_hash"] == rb["input_hash"]
    assert ra["generated_at"] != rb["generated_at"]
    assert ra["common_sample"] > 0
    for f in ("report.md", "report.json", "input_snapshot.json"):
        text = (a / f).read_text(encoding="utf-8")
        for private in (
            "quantity",
            "avg_buy_price",
            "account_group",
            "12345",
            "ISA",
            "일반",
        ):
            assert private not in text
    assert hashlib.sha256(env["db"].read_bytes()).hexdigest() == digest  # DB 쓰기 0
    md = (a / "report.md").read_text(encoding="utf-8")
    assert "표본 없음" in md and "거래량은 표시 반올림 전 배수 기준" in md
    assert not list((tmp_path / "out").glob(".*.partial"))


@pytest.mark.parametrize(
    "end", ["2026-8-31", "2026-02-18", "2026-12-31", "2027-01-04", "2026-02-30"]
)
def test_end_date_is_checked(tmp_path: Path, end: str) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    with pytest.raises(rep.EndDateError):
        _load(env, end)


def test_missing_calendar_is_refused(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    (env["cal"] / "krx_trading_days_2026.csv").unlink()
    with pytest.raises(rep.EndDateError):
        _load(env, "2026-08-31")


def test_render_md_lists_question_exclusions_and_tables() -> None:
    recs = [_rec("A", "2026-03-03", 1.0, -1.0, True, False)]
    body = {
        "generated_at": "g",
        "end": "2026-10-14",
        "input_hash": "0" * 64,
        "body_hash": "1" * 64,
        "question": rep.QUESTION,
        "universe": {
            "held_tickers": 2,
            "etf_targets": ["A"],
            "non_etf_excluded": ["S"],
            "pairs": 3,
            "base_dates": {"first": "2026-02-19", "last": "2026-10-14", "days": 159},
            "front": {"first": "a", "last": "b", "days": 80},
            "back": {"first": "c", "last": "d", "days": 79},
            "common_sample_dates": {
                "first": "2026-04-03",
                "last": "2026-09-10",
                "days": 109,
            },
            "front_sample_dates": {"days": 0},
            "back_sample_dates": {"first": "c", "last": "d", "days": 1},
            "db_latest": "2026-10-14",
        },
        "exclusions": [{"code": c, "label": lab, "count": 1} for c, lab in obs.REASONS],
        "common_sample": 1,
        "definitions": rep.DEFINITIONS,
        "notes": list(rep.NOTES),
        "tables": {k: tab.band_table(recs) for k in ("all", "front", "back")},
    }
    md = render_md(body)
    assert (
        rep.QUESTION in md
        and "이후 경로 저장 결측" in md
        and "부록 A" in md
        and "부록 B" in md
    )
    assert "+1.00%" in md and "표본 없음" in md
    # 검토 L3 — 실제 자료 기간(공통 표본 기준일) · DB 최신 저장일 · 머리 줄
    assert "실제 자료 기간(공통 표본의 기준일): 2026-04-03 ~ 2026-09-10 · 109일" in md
    assert "시장 DB 최신 저장일 2026-10-14" in md
    assert "실제 자료 기간(이 기간 공통 표본의 기준일): 표본 없음" in md
    assert "\n입력 식별 `" in md and "\n· 입력 식별" not in md


# ── 독립 검토 반영(L1 · L2 · L3) ─────────────────────────────────────────────────
def test_volatility_same_is_not_up(tmp_path: Path) -> None:
    """흔들림 'same'(두 구간 표시값이 같음)은 '커지지 않음'(설계 §4)."""
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-06-30"][-60:]
    closes = [
        100.0 if i % 2 == 0 else 101.0 for i in range(60)
    ]  # 두 구간 같은 수익률 묶음
    _prices(env["db"], "AAA111", days, closes, [1000] * 60)
    reason, got = obs.observe(_load(env, days[-1]).series["AAA111"], days[-1])
    assert reason is None
    assert got["volatility_comparison"] == "same" and got["volatility_up"] is False


def test_outcome_checks_first_link_t_to_t_plus_1(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-04-30"]
    t = "2026-02-20"
    k = days.index(t)
    _prices(
        env["db"],
        "AAA111",
        days,
        [100.0 + i for i in range(len(days))],
        [1000] * len(days),
        bad_change_at=days[k + 1],
    )
    inp = _load(env, "2026-04-30")
    assert (
        obs.outcome(inp.series["AAA111"], t, inp.calendar, inp.end)[0] == "path_basis"
    )


def test_volatility_uses_unfiltered_rows(tmp_path: Path) -> None:
    """흔들림은 원본 행(거르지 않음) — t 앞 최근 구간에 종가 없는 행이 있으면 그 구간은 계산하지 않는다."""
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-06-30"][-60:]
    closes: list[Any] = _wave(60)
    closes[-5] = None
    _prices(env["db"], "AAA111", days, closes, [1000] * 60)
    reason, _ = obs.observe(_load(env, days[-1]).series["AAA111"], days[-1])
    assert (
        reason == "volatility_previous_only"
    )  # 최근 구간만 막힘(하락 구간 · 거래량은 거른 행으로 계산됨)


def test_end_after_db_latest_is_refused(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-06-30"]
    _prices(env["db"], "AAA111", days, _wave(len(days)), [1000] * len(days))
    assert _load(env, days[-1]).db_latest == days[-1]
    with pytest.raises(rep.EndDateError):
        _load(env, "2026-07-10")  # DB 최신 저장일(06-30) 뒤


def test_report_states_actual_sample_dates(tmp_path: Path) -> None:
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d <= "2026-08-31"]
    _prices(
        env["db"],
        "AAA111",
        days,
        _wave(len(days)),
        [1000 + (i % 7) for i in range(len(days))],
    )
    inp = _load(env, "2026-08-31")
    r = rep.build_report(inp, input_hash="x", generated_at="g")
    u = r["universe"]
    assert (
        u["common_sample_dates"]["days"] == r["common_sample"]
    )  # 종목 1개 → 기준일 수 = 건수
    assert (
        u["front_sample_dates"]["days"] + u["back_sample_dates"]["days"]
        == r["common_sample"]
    )
    assert u["db_latest"] == "2026-08-31"


def test_end_beyond_2026_calendar_is_refused_even_if_db_has_rows(
    tmp_path: Path,
) -> None:
    """DB 에 2027 자료가 있어도 종료일은 2026 거래일 캘린더 마지막 날 이하(연구는 평일 대체 축을 쓰지 않음)."""
    env = _env(tmp_path, [_h("AAA111")])
    _master(env["db"], "AAA111")
    days = [d for d in CAL if d >= "2026-11-02"] + ["2027-01-04", "2027-01-05"]
    _prices(env["db"], "AAA111", days, _wave(len(days)), [1000] * len(days))
    assert _load(env, CAL[-1]).end == CAL[-1]
    with pytest.raises(rep.EndDateError, match="캘린더"):
        _load(env, "2027-01-04")


# ── 검증자 r1 P2: DB 최신 저장일은 종료일로 자르지 않은 실제 값 ─────────────────────────
@pytest.mark.parametrize("drop_end_row", [True, False])
def test_db_latest_is_actual_latest_not_cut_at_end(
    tmp_path: Path, drop_end_row: bool
) -> None:
    """DB 가 08-31 까지 있고 종료일 08-20 행이 없어도(또는 있어도) 실행되고, 최신 저장일은 08-31."""
    env = _env(tmp_path, [_h("AAA111"), _h("BBB222")])
    _master(env["db"], "AAA111", "BBB222")
    days = [d for d in CAL if d <= "2026-08-31"]
    end = "2026-08-20"
    assert end in days
    for t in ("AAA111", "BBB222"):
        keep = [d for d in days if not (drop_end_row and d == end)]
        _prices(env["db"], t, keep, _wave(len(keep)), [1000] * len(keep))
    inp = _load(env, end)
    assert inp.db_latest == "2026-08-31"
    assert inp.end == end
    assert all(
        r.date <= end for s in inp.series.values() for r in s.raw
    )  # 계산 입력은 종료일까지
    r = rep.build_report(inp, input_hash="x", generated_at="g")
    assert r["universe"]["db_latest"] == "2026-08-31"
    ex = {e["code"]: e["count"] for e in r["exclusions"]}
    assert ex["no_close_on_t"] == (
        2 if drop_end_row else 0
    )  # 종료일 행이 없는 날은 그 기준일만 '종가 없음'
