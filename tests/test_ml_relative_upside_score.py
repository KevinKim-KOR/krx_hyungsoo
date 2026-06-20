"""tests for app.ml_relative_upside_score + api 통합.

검증 대상 (지시문 §17):
  - reasons 사람 언어 (모델 내부 식별자 / loss / epoch / device 노출 0건).
  - snapshot 부재 시 API 응답이 unavailable 로 통과 (후보 자체 실패시키지 않음).
  - 점수 미생성 시 candidate.relative_upside_score = null.
"""

from __future__ import annotations

from app.ml_relative_upside_features import CandidateFeatureRow
from app.ml_relative_upside_score import (
    USER_NOTICE,
    build_reasons,
    build_score_snapshot,
)


def _make_row(
    ticker: str = "A",
    excess: tuple[float, float, float] = (0.01, 0.01, 0.01),
    drawdown: float = -0.01,
) -> CandidateFeatureRow:
    return CandidateFeatureRow(
        ticker=ticker,
        asof_index=0,
        asof_date="2026-06-19",
        close=100.0,
        return_5d=0.01,
        return_10d=0.02,
        return_20d=0.03,
        excess_return_5d=excess[0],
        excess_return_10d=excess[1],
        excess_return_20d=excess[2],
        drawdown_20d=drawdown,
        future_excess_return_20d=None,
    )


def test_reasons_max_3():
    row = _make_row(excess=(0.01, 0.01, 0.01), drawdown=-0.01)
    reasons = build_reasons(row)
    assert len(reasons) <= 3


def test_reasons_user_language_no_internal_identifiers():
    """모델 내부 식별자 / loss / epoch / device 노출 0건 (지시문 AC-10)."""
    row = _make_row()
    reasons = build_reasons(row)
    forbidden = (
        "loss",
        "epoch",
        "device",
        "cuda",
        "tensor",
        "feature_vector",
        "param_id",
        "drawdown_20d",  # 내부 feature 명 그대로 X (UI 라벨은 "고점 대비").
        "return_5d",
        "excess_return_5d",
    )
    for reason in reasons:
        for f in forbidden:
            assert f not in reason, f"reason 에 내부 식별자 노출: {f!r}"


def test_reasons_strong_outperform():
    """5/10/20일 모두 우위 → 우위 reason."""
    row = _make_row(excess=(0.05, 0.05, 0.05), drawdown=-0.005)
    reasons = build_reasons(row)
    assert any("우위" in r for r in reasons)


def test_reasons_strong_underperform():
    """5/10/20일 모두 약세 → 약세 reason."""
    row = _make_row(excess=(-0.05, -0.05, -0.05), drawdown=-0.005)
    reasons = build_reasons(row)
    assert any("약세" in r for r in reasons)


def test_reasons_drawdown_large():
    """drawdown 큼 → '확인하세요' 메시지."""
    row = _make_row(excess=(0.01, 0.01, 0.01), drawdown=-0.20)
    reasons = build_reasons(row)
    assert any("하락폭" in r for r in reasons)


def test_snapshot_contains_user_notice():
    """snapshot 에 USER_NOTICE 가 포함된다 (지시문 §9 끝)."""
    snapshot = build_score_snapshot(
        asof_date="2026-06-19",
        generated_at="2026-06-19T00:00:00+00:00",
        status="ok",
        display_scores={"A": 75.0},
        raw_scores={"A": 0.05},
        feature_rows=[_make_row("A")],
        simple_excess_return_ranking=[("A", 0.015)],
    )
    assert snapshot["user_notice"] == USER_NOTICE
    assert snapshot["schema_version"] == "relative_upside_score.v0"
    assert snapshot["status"] == "ok"


def test_snapshot_candidates_include_all_fields():
    """snapshot.candidates 가 점수 + drawdown + reasons + simple excess return 포함."""
    snapshot = build_score_snapshot(
        asof_date="2026-06-19",
        generated_at="2026-06-19T00:00:00+00:00",
        status="ok",
        display_scores={"A": 75.0},
        raw_scores={"A": 0.05},
        feature_rows=[_make_row("A")],
        simple_excess_return_ranking=[("A", 0.015)],
    )
    cand = snapshot["candidates"][0]
    assert cand["ticker"] == "A"
    assert cand["relative_upside_score"] == 75.0
    assert cand["relative_upside_raw_prediction"] == 0.05
    assert cand["drawdown_20d"] is not None
    assert isinstance(cand["relative_upside_reasons"], list)


def test_snapshot_includes_simple_vs_ml_comparison():
    """지시문 AC-5 — simple 20일 초과수익 순위 vs ML 점수 순위 비교 기록."""
    snapshot = build_score_snapshot(
        asof_date="2026-06-19",
        generated_at="2026-06-19T00:00:00+00:00",
        status="ok",
        display_scores={"A": 100.0, "B": 50.0, "C": 0.0},
        raw_scores={"A": 0.05, "B": 0.0, "C": -0.05},
        feature_rows=[_make_row("A"), _make_row("B"), _make_row("C")],
        simple_excess_return_ranking=[("A", 0.03), ("B", 0.01), ("C", -0.02)],
    )
    comparison = snapshot["simple_vs_ml_rank_comparison"]
    assert len(comparison) == 3
    a_entry = next(c for c in comparison if c["ticker"] == "A")
    assert a_entry["simple_excess_return_20d_rank"] == 1
    assert a_entry["ml_relative_upside_score_rank"] == 1


# ─── API 통합 — snapshot 부재 / status 분기 ────────────────────────────


def test_api_response_unavailable_when_snapshot_missing(monkeypatch):
    """snapshot 부재 시 API 응답이 status=unavailable + candidate score=null."""
    from app import api_market_topn

    # snapshot 부재 시뮬레이션.
    monkeypatch.setattr(
        "app.ml_relative_upside_score.load_score_snapshot", lambda: None
    )
    # candidate 1건만 mock 으로 머지 함수 직접 호출.
    cand = api_market_topn.MarketCandidate(ticker="069500", name="KODEX 200")
    merged, meta = api_market_topn._merge_relative_upside_score([cand])
    assert meta["relative_upside_score_status"] == "unavailable"
    assert merged[0].relative_upside_score is None
    assert merged[0].relative_upside_reasons == []


def test_api_response_failed_when_snapshot_status_not_ok(monkeypatch):
    """snapshot status != 'ok' 면 candidate score 머지 안 함."""
    from app import api_market_topn

    fake_snapshot = {
        "status": "failed",
        "asof_date": "2026-06-19",
        "generated_at": "2026-06-19T00:00:00+00:00",
        "candidates": [
            {"ticker": "069500", "relative_upside_score": 50.0, "drawdown_20d": -0.01}
        ],
    }
    monkeypatch.setattr(
        "app.ml_relative_upside_score.load_score_snapshot", lambda: fake_snapshot
    )
    cand = api_market_topn.MarketCandidate(ticker="069500", name="KODEX 200")
    merged, meta = api_market_topn._merge_relative_upside_score([cand])
    assert meta["relative_upside_score_status"] == "failed"
    assert merged[0].relative_upside_score is None
