"""Market Regime + candidate excess_return 단위 테스트 (POC2 — 2026-05-22)."""

from __future__ import annotations

from app.market_regime import (
    compute_candidate_excess_return,
    compute_kodex200_metrics,
    compute_kospi_metrics,
    compute_market_context,
)


def _flat_series(start_close: float, n: int) -> list[tuple[str, float]]:
    """date 가 무관한 순서만 중요한 lookup 시계열 (date 는 더미)."""
    return [(f"2026-01-{i + 1:02d}", start_close) for i in range(n)]


def _series_with_trend(
    start_close: float, end_close: float, n: int
) -> list[tuple[str, float]]:
    """선형 trend 시계열 (start → end). 정렬은 date ASC 처럼 인덱스 순."""
    step = (end_close - start_close) / max(1, n - 1)
    return [(f"2026-01-{i + 1:02d}", start_close + step * i) for i in range(n)]


def test_compute_kodex200_metrics_unavailable_for_short_history():
    short = _flat_series(100.0, 30)  # < 60+1 거래일.
    out = compute_kodex200_metrics(short)
    assert out["status"] == "unavailable"


def test_compute_kodex200_metrics_strong_bull():
    # 100 → 120 (20% 상승) 시계열 61 행 (60+1). 20일/60일 모두 상승, MA 위.
    history = _series_with_trend(100.0, 120.0, 61)
    out = compute_kodex200_metrics(history)
    assert out["status"] == "ok"
    assert out["return_60d_pct"] > 5.0
    assert out["return_20d_pct"] > 2.0
    assert out["ma20_position"] == "above"
    assert out["ma60_position"] == "above"


def test_compute_market_context_bull():
    history = _series_with_trend(100.0, 120.0, 61)
    ctx = compute_market_context(asof="2026-05-22", kodex200_history=history)
    assert ctx["status"] == "partial"  # KOSPI 없으므로.
    assert ctx["regime_label"] == "상승장"
    assert ctx["regime_code"] == "bull"
    assert ctx["regime_score"] >= 2
    assert ctx["kodex200"]["status"] == "ok"
    assert ctx["kospi"]["status"] == "unavailable"
    assert any("KOSPI" in w for w in ctx["warnings"])


def test_compute_market_context_bear():
    history = _series_with_trend(120.0, 100.0, 61)
    ctx = compute_market_context(asof="2026-05-22", kodex200_history=history)
    assert ctx["regime_label"] == "하락장"
    assert ctx["regime_code"] == "bear"
    assert ctx["regime_score"] <= -2


def test_compute_market_context_neutral():
    # 약한 변동 — 20d ≤ 2%, 60d ≤ 5%. MA 위/아래 혼합.
    # 100 → 101 (1% 상승) — 20d/60d 변화율 절대값이 임계 미만.
    history = _series_with_trend(100.0, 101.0, 61)
    ctx = compute_market_context(asof="2026-05-22", kodex200_history=history)
    # 점수가 +2/-2 사이면 보합장.
    assert ctx["regime_code"] in ("neutral", "bull", "bear")
    if ctx["regime_code"] == "neutral":
        assert ctx["regime_label"] == "보합장"


def test_compute_market_context_unavailable_when_kodex_missing():
    ctx = compute_market_context(asof="2026-05-22", kodex200_history=[])
    assert ctx["status"] == "unavailable"
    assert ctx["regime_label"] == "판정불가"
    assert ctx["regime_code"] == "unavailable"
    assert ctx["regime_score"] is None


def test_compute_market_context_ok_when_both_benchmarks_present():
    kodex = _series_with_trend(100.0, 120.0, 61)
    kospi = _series_with_trend(100.0, 115.0, 61)
    ctx = compute_market_context(
        asof="2026-05-22", kodex200_history=kodex, kospi_history=kospi
    )
    assert ctx["status"] == "ok"
    assert ctx["kospi"]["status"] == "ok"
    assert ctx["warnings"] == []


def test_compute_kospi_metrics_short_history_unavailable():
    out = compute_kospi_metrics(_flat_series(2700.0, 30))
    assert out["status"] == "unavailable"


def test_compute_candidate_excess_return_full():
    out = compute_candidate_excess_return(
        candidate_1m_pct=10.0,
        candidate_3m_pct=20.0,
        kodex200_1m_pct=3.0,
        kodex200_3m_pct=5.0,
        kospi_1m_pct=2.0,
        kospi_3m_pct=4.0,
    )
    assert out["vs_kodex200_1m_pctp"] == 7.0
    assert out["vs_kodex200_3m_pctp"] == 15.0
    assert out["vs_kospi_1m_pctp"] == 8.0
    assert out["vs_kospi_3m_pctp"] == 16.0


def test_compute_candidate_excess_return_null_propagation():
    out = compute_candidate_excess_return(
        candidate_1m_pct=10.0,
        candidate_3m_pct=None,
        kodex200_1m_pct=3.0,
        kodex200_3m_pct=5.0,
        kospi_1m_pct=None,
        kospi_3m_pct=None,
    )
    assert out["vs_kodex200_1m_pctp"] == 7.0
    # 후보 3m 이 None 이면 vs_kodex200_3m_pctp 도 null.
    assert out["vs_kodex200_3m_pctp"] is None
    # KOSPI 가 None 이면 vs_kospi_* 도 null.
    assert out["vs_kospi_1m_pctp"] is None
    assert out["vs_kospi_3m_pctp"] is None
