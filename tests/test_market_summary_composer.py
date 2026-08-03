"""POC3-06 §6 공통 판단 요약 composer 단위 테스트.

핵심 계약:
- select_top_holdings 가 프론트 `lowestFiveDayRows` 와 **동일 규칙**(동일 fixture →
  동일 순서·건수). 화면 간 정합(§6.1·AC-2·Q2 전환 테스트).
- KOSPI 관찰값(일간·1년·52주 고점 대비)·국면 지속일 helper 계약(§6.2·Q1·Q4).
"""

from __future__ import annotations

from app.market_regime import (
    compute_kospi_position_metrics,
    compute_regime_streak,
)
from app.market_summary_composer import (
    select_top_holdings,
    summarize_holdings,
    compose_judgment_summary,
)


def _ev_item(
    ticker: str,
    *,
    status: str = "ok",
    r5=None,
    r20=1.0,
    ex20=0.5,
    eval_amount=1000.0,
    pnl=1.0,
) -> dict:
    return {
        "ticker": ticker,
        "name": f"ETF {ticker}",
        "holding": {"evaluation_amount": eval_amount, "pnl_rate_pct": pnl},
        "short_term_momentum": {
            "status": status,
            "return_5d_pct": r5,
            "return_20d_pct": r20,
            "excess_vs_kodex200_20d_pctp": ex20,
        },
    }


# ── select_top_holdings = 프론트 lowestFiveDayRows 동일 규칙 (Q2 전환 테스트) ──


def test_top_holdings_matches_frontend_rule():
    # 프론트 helpers.test.ts 와 동일 fixture:
    #   [-5(A1), -1(A2), -5(A3), unavailable(A4)] → ["A00001","A00003","A00002"]
    holdings = [
        _ev_item("A00001", r5=-5.0),
        _ev_item("A00002", r5=-1.0),
        _ev_item("A00003", r5=-5.0),  # 동률 → ticker 오름차순
        _ev_item("A00004", status="unavailable", r5=None),  # 제외
    ]
    top = select_top_holdings(holdings, limit=3)
    assert [h["ticker"] for h in top] == ["A00001", "A00003", "A00002"]
    assert "A00004" not in [h["ticker"] for h in top]


def test_top_holdings_empty_when_no_valid_five_day():
    holdings = [_ev_item("069500", status="unavailable", r5=None)]
    assert select_top_holdings(holdings, limit=3) == []


def test_top_holdings_dedup_ticker():
    holdings = [_ev_item("A00001", r5=-3.0), _ev_item("A00001", r5=-9.0)]
    top = select_top_holdings(holdings, limit=3)
    assert [h["ticker"] for h in top] == ["A00001"]  # 첫 등장만


def test_summarize_holdings_coverage_counts_need_check():
    holdings = [
        _ev_item("A00001", r5=-1.0),  # ok
        _ev_item("A00002", status="partial", r5=-2.0),  # need_check
        _ev_item("A00003", r5=None),  # 5일 null → need_check
    ]
    s = summarize_holdings(holdings)
    assert s["coverage"]["total"] == 3
    assert s["coverage"]["need_check"] == 2
    assert s["coverage"]["ok"] == 1


# ── KOSPI 관찰값 (§6.2 · Q1) ────────────────────────────────────────────


def test_kospi_position_daily_return():
    hist = [("2026-07-23", 2650.0), ("2026-07-24", 2600.0)]
    m = compute_kospi_position_metrics(hist)
    assert m["as_of_date"] == "2026-07-24"
    # (2600/2650 - 1)*100 = -1.89%
    assert m["daily_return_pct"] == -1.89


def test_kospi_position_one_year_and_high_gap():
    # 1년치 이상: 2025-07-24 ~ 2026-07-24. 고점 2700, 최신 2600.
    hist = []
    hist.append(("2025-07-24", 2500.0))  # 1년 전 기준
    hist.append(("2026-01-15", 2700.0))  # 최근 1년 고점
    hist.append(("2026-07-23", 2650.0))
    hist.append(("2026-07-24", 2600.0))  # 최신
    m = compute_kospi_position_metrics(hist)
    # 1년 수익률: (2600/2500 - 1)*100 = +4.0%
    assert m["return_1y_pct"] == 4.0
    # 고점 대비: (2600/2700 - 1)*100 = -3.70% (음수, 고점 아님)
    assert m["high_52w_gap_pct"] == -3.70


def test_kospi_position_high_gap_zero_at_peak():
    hist = [("2025-08-01", 2000.0), ("2026-08-03", 3000.0)]  # 최신이 고점
    m = compute_kospi_position_metrics(hist)
    assert m["high_52w_gap_pct"] == 0.0  # 고점이면 0%


def test_kospi_position_insufficient_history_none():
    m = compute_kospi_position_metrics([])
    assert m["daily_return_pct"] is None
    assert m["return_1y_pct"] is None
    assert m["high_52w_gap_pct"] is None


def test_kospi_position_sub_one_year_no_high_gap():
    # 검증자 REJECTED 재현: 1년 미만(23일) 이력이면 고점 대비·1년 수익률 모두 None.
    # 23일 중 최고를 52주 고점으로 오인하면 안 된다(§6.2 "1년 이력 부족 시 계산 불가").
    hist = [(f"2026-07-{i:02d}", 2600.0 - i * 10) for i in range(1, 24)]
    m = compute_kospi_position_metrics(hist)
    assert m["daily_return_pct"] is not None  # 일간은 이력 무관하게 계산
    assert m["return_1y_pct"] is None
    assert m["high_52w_gap_pct"] is None


def test_top_holdings_includes_eval_weight_and_pnl():
    # §4.4·AC-7 — 평가 비중(전체 대비)·평가손익 포함.
    holdings = [
        _ev_item("A00001", r5=-5.0, eval_amount=3000.0, pnl=-2.0),
        _ev_item("A00002", r5=-1.0, eval_amount=1000.0, pnl=1.5),
    ]
    top = select_top_holdings(holdings, limit=3)
    a1 = next(h for h in top if h["ticker"] == "A00001")
    # 비중 = 3000 / 4000 = 75.0%
    assert a1["market_weight_pct"] == 75.0
    assert a1["pnl_rate_pct"] == -2.0
    assert a1["eval_amount"] == 3000.0


# ── 국면 지속 거래일 수 (§6.2 · Q4) ──────────────────────────────────────


def test_regime_streak_none_when_insufficient():
    # 60일 미만 → 최신 라벨 계산 불가 → 자료 없음(None).
    hist = [(f"2026-01-{i:02d}", 100.0 + i) for i in range(1, 10)]
    s = compute_regime_streak(hist)
    assert s["regime_code"] is None
    assert s["streak_days"] is None


def test_regime_streak_at_least_when_all_same_from_start():
    # 강한 단조 상승 → 전 구간 bull. 이력 시작점까지 같은 라벨 → at_least.
    hist = [
        (f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}", 100.0 + i * 2.0)
        for i in range(80)
    ]
    s = compute_regime_streak(hist)
    assert s["regime_code"] == "bull"
    assert s["streak_days"] is not None and s["streak_days"] >= 1
    assert s["at_least"] is True


# ── compose_judgment_summary 통합 (§6.1 단일 결과) ───────────────────────


def test_compose_judgment_summary_shape():
    mc = {
        "status": "ok",
        "asof": "2026-07-24",
        "regime_label": "상승장",
        "regime_code": "bull",
        "kodex200": {"status": "ok"},
        "kospi": {"status": "ok"},
    }
    out = compose_judgment_summary(
        market_context=mc,
        kospi_position={
            "daily_return_pct": -1.0,
            "return_1y_pct": 4.0,
            "high_52w_gap_pct": -3.7,
            "as_of_date": "2026-07-24",
        },
        regime_streak={"regime_code": "bull", "streak_days": 5, "at_least": False},
        evidence_holdings=[_ev_item("A00001", r5=-1.0)],
        market_risk={"vix": {"availability": "available", "as_of_date": "2026-07-03"}},
        evidence_asof={"holdings_asof": "2026-07-24", "market_asof": "2026-07-24"},
    )
    assert out["market_position"]["regime_label"] == "상승장"
    assert out["market_position"]["regime_streak_days"] == 5
    assert out["market_position"]["kospi"]["high_52w_gap_pct"] == -3.7
    assert len(out["holdings"]["top_holdings"]) == 1
    assert out["data_status"]["vix_availability"] == "available"
    assert out["data_status"]["vix_asof"] == "2026-07-03"
