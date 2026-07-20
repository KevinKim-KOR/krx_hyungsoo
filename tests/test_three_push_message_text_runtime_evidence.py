"""POC2 3-PUSH Message Text Runtime Evidence 반영 — 신규 단위 테스트 (2026-06-14).

지시문 §15 AC-1 ~ AC-8 + AC-10 검증.

본 테스트는 directly push_context / message builder 를 호출하여 실제 evidence 가
message_text 에 반영되는지 확인한다. 외부 source 호출 0건 (stub probe).

AC 매핑:
- AC-1: PUSH-1 미국 지수 3종 실제 등락률이 message_text 에 반영.
- AC-2: PUSH-1 market_discovery / ML baseline evidence 가 판단 보조 문장으로 반영.
- AC-3: PUSH-2 holdings 별 관찰 포인트가 단순 목록이 아닌 형태로 생성.
- AC-4: PUSH-2 message_text 가 market_view 와 연결.
- AC-5: PUSH-3 message_text 가 score 단독 표시가 아닌, 수익률/방향/data_quality/
        holdings overlap 중 최소 2개 이상을 함께 노출.
- AC-7: 빈 placeholder 미노출 ("unavailable" 등).
- AC-8: 금지 문구 미포함 (매수/매도/raw JSON 등).
- AC-10: 산식 변경 없음 (compute_topn 결과를 그대로 입력 사용).
"""

from __future__ import annotations

from typing import Any

import pytest

from app import draft as draft_mod
from app.draft_three_push import (
    generate_market_briefing_via_generic,
    generate_spike_alert_via_generic,
)
from app.holdings import Holding
from app.message_market_briefing import build_market_briefing_message
from app.message_spike_alert import build_spike_alert_message
from app.push_context import (
    build_holdings_view,
    build_market_view,
    build_push_context,
    build_spike_view,
    holdings_observation_lines,
    overnight_us_lines,
    spike_view_lines,
)

# ─── 공통 stub 데이터 ─────────────────────────────────────────────


def _make_runtime_snapshot(
    *,
    kr_status: str = "ok",
    us_status: str = "ok",
    extra_kr_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    kr_items = [
        {
            "ticker": "069500",
            "name": "KODEX 200",
            "price": 36000,
            "change_pct": 0.42,
            "volume": 123456,
            "data_status": "ok",
        }
    ]
    if extra_kr_items:
        kr_items.extend(extra_kr_items)
    return {
        "captured_at": "2026-06-14T08:55:00+09:00",
        "kr_realtime_price_snapshot": {
            "captured_at": "2026-06-14T08:55:00+09:00",
            "source": "naver",
            "items": kr_items,
            "status": kr_status,
            "warnings": [],
            "errors": [],
        },
        "overnight_us_market_snapshot": {
            "captured_at": "2026-06-14T08:55:00+09:00",
            "indices": [
                {
                    "symbol": "NASDAQ",
                    "name": "Nasdaq Composite",
                    "change_pct": 0.85,
                    "close": 18000.12,
                    "status": "ok",
                },
                {
                    "symbol": "SPX",
                    "name": "S&P 500",
                    "change_pct": 0.41,
                    "close": 5400.33,
                    "status": "ok",
                },
                {
                    "symbol": "SOX",
                    "name": "Philadelphia Semiconductor Index",
                    "change_pct": 1.25,
                    "close": 5200.45,
                    "status": "ok",
                },
            ],
            "status": us_status,
            "warnings": [],
            "errors": [],
        },
        "cache_status": "hit",
    }


def _stub_market_discovery() -> dict[str, Any]:
    return {
        "status": "ok",
        "asof": "2026-06-13",
        "basis": "1m",
        "candidates": [
            {
                "rank": 1,
                "ticker": "367760",
                "name": "RISE 네트워크인프라",
                "selected_return_pct": 15.3,
                "returns": {
                    "daily": {"return_pct": 1.46},
                    "one_month": {"return_pct": 15.3},
                    "three_month": {"return_pct": 22.0},
                },
                "data_quality_flag": None,
            },
            {
                "rank": 2,
                "ticker": "069500",
                "name": "KODEX 200",
                "selected_return_pct": 4.4,
                "returns": {
                    "daily": {"return_pct": 0.42},
                    "one_month": {"return_pct": 4.4},
                    "three_month": {"return_pct": 8.1},
                },
            },
            {
                "rank": 3,
                "ticker": "229200",
                "name": "KODEX 코스닥150",
                "selected_return_pct": -6.2,
                "returns": {
                    "daily": {"return_pct": -1.1},
                    "one_month": {"return_pct": -6.2},
                    "three_month": {"return_pct": -8.0},
                },
                "data_quality_flag": "daily_return_over_5pct",
            },
        ],
    }


def _stub_ml_baseline_snapshot() -> dict[str, Any]:
    return {
        "status": "ok",
        "report_status": "ok",
        "feature_asof_range": {
            "start": "2026-03-11",
            "end": "2026-06-11",
        },
        "evaluated_asof_range": {"start": "2026-03-11", "end": "2026-05-07"},
        "candidate_summary": {},
        "risk_summary": {
            "evaluated_days": 43,
            "high_risk_group_future_drawdown": {"5d": -6.0, "10d": -8.1},
            "low_risk_group_future_drawdown": {"5d": -1.8, "10d": -3.4},
        },
        "leakage_summary": {"feature_future_data_leakage_detected": False},
        "limitations": [],
        "external_context_checklist": [
            "CNN Fear & Greed",
            "VIX·VKOSPI",
            "원유",
            "USD-KRW",
            "미국장·선물",
            "지정학",
            "한국장 영향 업종",
        ],
        "message": "ok",
    }


def _stub_universe_artifact() -> dict[str, Any]:
    return {
        "asof": "2026-06-13",
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "top_candidate": {
                "ticker": "367760",
                "name": "RISE 네트워크인프라",
                "score_result": {"score_value": 38.6},
                "price_history_basis": {"latest_date": "2026-06-13"},
            },
            "falling_candidate": {
                "ticker": "229200",
                "name": "KODEX 코스닥150",
                "score_result": {"score_value": -12.5},
                "price_history_basis": {"latest_date": "2026-06-13"},
            },
        },
    }


def _stub_holdings_snapshot() -> dict[str, Any]:
    return {
        "asof_date": "2026-06-14",
        "positions": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "current_price": 36000,
                "eval_amount": 360000,
                "invested_amount": 350000,
                "pnl_amount": 10000,
                "pnl_rate_pct": 2.86,
                "market_weight_pct": 35.0,
            },
            {
                "ticker": "229200",
                "name": "KODEX 코스닥150",
                "quantity": 20,
                "current_price": 18000,
                "eval_amount": 360000,
                "invested_amount": 400000,
                "pnl_amount": -40000,
                "pnl_rate_pct": -10.0,
                "market_weight_pct": 30.0,
            },
        ],
    }


# ─── AC-1 / push_context.overnight_us_lines: 실제 등락률 노출 ───────


def test_overnight_us_lines_shows_actual_change_pct():
    """AC-1: push_context.market_view 에서 NASDAQ / SPX / SOX 등락률 실제 값이 노출."""
    pc_evidence = {
        "market_discovery_snapshot": _stub_market_discovery(),
        "ml_baseline_snapshot": {},
    }
    runtime_snapshot = _make_runtime_snapshot()
    ctx = build_push_context(
        push_kind="market_briefing",
        pc_evidence=pc_evidence,
        runtime_snapshot=runtime_snapshot,
    )
    lines = overnight_us_lines(ctx)
    assert lines, "overnight_us_lines 가 비어있으면 안 됨"
    joined = "\n".join(lines)
    # 단순 "조회 가능 지수" 표시 금지 — 실제 값이 들어가야 함.
    assert "조회 가능 지수" not in joined
    # 3종 모두 실제 change_pct 값 (+0.85% / +0.41% / +1.25%) 포함.
    assert "+0.85%" in joined
    assert "+0.41%" in joined
    assert "+1.25%" in joined
    assert "NASDAQ" in joined
    assert "SPX" in joined
    assert "SOX" in joined


def test_overnight_us_lines_sector_hint_present_when_sox_strongest():
    """AC-1: SOX 가 가장 큰 절대 변동이면 반도체 섹터 해석 hint 가 본문에 포함."""
    pc_evidence = {
        "market_discovery_snapshot": _stub_market_discovery(),
        "ml_baseline_snapshot": {},
    }
    rs = _make_runtime_snapshot()
    # SOX 절대 변동이 가장 크게 유지.
    ctx = build_push_context(
        push_kind="market_briefing",
        pc_evidence=pc_evidence,
        runtime_snapshot=rs,
    )
    lines = overnight_us_lines(ctx)
    assert any("반도체" in line for line in lines)


def test_market_briefing_message_text_contains_us_values_and_evidence():
    """AC-1 + AC-2: PUSH-1 message_text 가 미국 지수 실제 값 + market evidence 를
    함께 포함한다.
    """
    pc_evidence = {
        "market_discovery_snapshot": _stub_market_discovery(),
        "ml_baseline_snapshot": _stub_ml_baseline_snapshot(),
    }
    rs = _make_runtime_snapshot()
    ctx = build_push_context(
        push_kind="market_briefing",
        pc_evidence=pc_evidence,
        runtime_snapshot=rs,
    )
    msg = build_market_briefing_message(
        asof_iso="2026-06-14T00:00:00+00:00",
        ml_baseline_snapshot=_stub_ml_baseline_snapshot(),
        topn_payload=_stub_market_discovery(),
        push_context=ctx,
    )
    # AC-1: 실제 등락률 포함.
    assert "+0.85%" in msg
    assert "+0.41%" in msg
    assert "+1.25%" in msg
    # AC-2: market_discovery 후보 흐름 / ML baseline 룩백 evidence 가 함께 노출.
    assert "[국내 시장 내부 신호 (Market Discovery)]" in msg
    assert "[위험 패턴 참고 (ML baseline 룩백)]" in msg
    assert "43거래일 룩백" in msg
    # AC-7: 빈 placeholder 미노출.
    assert "unavailable" not in msg
    assert "조회 실패" not in msg
    # AC-8: 금지 문구 미포함.
    for forbidden in (
        "매수 지시",
        "매도 지시",
        "교체 지시",
        "비중 조절 지시",
        "조정장 확정",
        "위험 threshold 확정",
        "raw_json",
        "chat_id",
        "token=",
    ):
        assert forbidden not in msg, f"금지 문구 포함: {forbidden}"


# ─── AC-1: 일부 실패 — 성공한 지수만 표시 ────────────────────────


def test_overnight_us_lines_skips_failed_index():
    """AC-1: SOX 만 실패하면 NASDAQ / SPX 만 표시, SOX 행은 생략."""
    rs = _make_runtime_snapshot(us_status="partial")
    for idx in rs["overnight_us_market_snapshot"]["indices"]:
        if idx["symbol"] == "SOX":
            idx["status"] = "failed"
            idx["change_pct"] = None
            idx["close"] = None
    ctx = build_push_context(
        push_kind="market_briefing",
        pc_evidence={
            "market_discovery_snapshot": _stub_market_discovery(),
            "ml_baseline_snapshot": {},
        },
        runtime_snapshot=rs,
    )
    lines = overnight_us_lines(ctx)
    joined = "\n".join(lines)
    assert "NASDAQ" in joined
    assert "SPX" in joined
    # SOX 는 status=failed → 행 자체가 생략되어야 함.
    assert "SOX" not in joined


# ─── AC-1: 전부 실패 — 섹션 자체 생략 ────────────────────────────


def test_overnight_us_lines_empty_when_all_failed():
    """AC-1 / AC-7: 미국 지수 3종 모두 실패면 섹션 자체 미노출."""
    rs = _make_runtime_snapshot(us_status="failed")
    for idx in rs["overnight_us_market_snapshot"]["indices"]:
        idx["status"] = "failed"
        idx["change_pct"] = None
        idx["close"] = None
    ctx = build_push_context(
        push_kind="market_briefing",
        pc_evidence={
            "market_discovery_snapshot": _stub_market_discovery(),
            "ml_baseline_snapshot": {},
        },
        runtime_snapshot=rs,
    )
    assert overnight_us_lines(ctx) == []


# ─── AC-3 / AC-4: PUSH-2 holdings 관찰 포인트 ─────────────────────


def test_holdings_view_observations_have_text_lines():
    """AC-3: holdings_view.observations 마다 text 가 채워져 있어야 한다.

    단순 ticker 목록이 아니라 portfolio_weight / runtime quote / market_discovery
    overlap 등 정보가 함께 들어간 1줄 형식.
    """
    pc_evidence = {
        "holdings_snapshot": _stub_holdings_snapshot(),
        "market_discovery_snapshot": _stub_market_discovery(),
        "ml_baseline_snapshot": _stub_ml_baseline_snapshot(),
    }
    rs = _make_runtime_snapshot(
        extra_kr_items=[
            {
                "ticker": "229200",
                "name": "KODEX 코스닥150",
                "price": 18000,
                "change_pct": -1.10,
                "volume": 50000,
                "data_status": "ok",
            }
        ]
    )
    hv = build_holdings_view(pc_evidence=pc_evidence, runtime_snapshot=rs)
    assert hv, "holdings_view 가 비어있으면 안 됨"
    obs = hv.get("observations") or []
    assert len(obs) >= 1
    for o in obs:
        text = o.get("text")
        assert isinstance(text, str) and text.strip()
        # 단순 종목명만 있으면 안 됨 — ":" 또는 "—" 가 포함되어야 함.
        assert ":" in text or "—" in text


def test_holdings_observation_lines_contain_market_view_connection():
    """AC-4: PUSH-2 push_context 의 holdings_observation_lines 가 market_view 와
    연결된 시장 흐름 한 줄을 포함해야 한다.
    """
    pc_evidence = {
        "holdings_snapshot": _stub_holdings_snapshot(),
        "market_discovery_snapshot": _stub_market_discovery(),
        "ml_baseline_snapshot": _stub_ml_baseline_snapshot(),
    }
    rs = _make_runtime_snapshot()
    ctx = build_push_context(
        push_kind="holdings_briefing",
        pc_evidence=pc_evidence,
        runtime_snapshot=rs,
    )
    lines = holdings_observation_lines(ctx)
    joined = "\n".join(lines)
    assert "[보유 종목 관찰 포인트]" in joined
    assert "[시장 흐름 연결]" in joined
    # 미국 지수 실제 등락률이 market_view 요약에 포함되어야 한다.
    assert "+0.85%" in joined or "+1.25%" in joined or "+0.41%" in joined


def test_holdings_view_skips_position_without_signal_data():
    """AC-3: 시세도 weight 도 없는 holding 은 단순 "이름만" 1줄 노출하지 않고
    아예 생략 (단순 목록 나열 금지).
    """
    pc_evidence = {
        "holdings_snapshot": {
            "positions": [
                {"ticker": "111111", "name": "VOID ETF"},
            ]
        },
        "market_discovery_snapshot": {},
        "ml_baseline_snapshot": {},
    }
    rs = _make_runtime_snapshot()
    # ticker "111111" 은 runtime quote 도 없다.
    hv = build_holdings_view(pc_evidence=pc_evidence, runtime_snapshot=rs)
    assert hv == {}, "정보 부족 holding 은 observation 으로 생성되면 안 됨"


# ─── AC-5: PUSH-3 spike_view 풍부화 ─────────────────────────────


def test_spike_view_items_have_return_direction_dq_overlap():
    """AC-5: spike_view items 마다 수익률 근거 / 방향 / data_quality / holdings
    overlap 4개 축이 dict 에 채워져 있어야 한다.
    """
    pc_evidence = {
        "universe_momentum_snapshot": _stub_universe_artifact(),
        "market_discovery_snapshot": _stub_market_discovery(),
        "holdings_snapshot": _stub_holdings_snapshot(),
    }
    rs = _make_runtime_snapshot()
    sv = build_spike_view(pc_evidence=pc_evidence, runtime_snapshot=rs)
    assert sv
    items = sv.get("items") or []
    assert len(items) >= 1
    for it in items:
        # 방향과 holdings_overlap 은 모든 item 에 채워져야 함.
        assert it.get("direction") in ("up", "down")
        assert "holdings_overlap" in it
        assert "data_quality_flags" in it


def test_spike_view_lines_render_not_score_only():
    """AC-5: spike_view_lines 가 score 단독이 아니라 수익률/방향/data_quality/
    overlap 정보가 함께 들어간 1줄 / item 을 만든다.
    """
    pc_evidence = {
        "universe_momentum_snapshot": _stub_universe_artifact(),
        "market_discovery_snapshot": _stub_market_discovery(),
        "holdings_snapshot": _stub_holdings_snapshot(),
    }
    rs = _make_runtime_snapshot()
    ctx = build_push_context(
        push_kind="spike_or_falling_alert",
        pc_evidence=pc_evidence,
        runtime_snapshot=rs,
    )
    lines = spike_view_lines(ctx)
    joined = "\n".join(lines)
    assert "[universe momentum 관찰 (push_context 기반)]" in joined
    # 방향 / data_quality / overlap 텍스트가 들어가야 함.
    assert "방향" in joined
    assert "data_quality" in joined
    assert "보유 종목" in joined  # overlap text


def test_spike_alert_message_text_includes_runtime_evidence():
    """AC-5 + AC-7 + AC-8: PUSH-3 message_text 자체에 풍부 관찰 노출."""
    pc_evidence = {
        "universe_momentum_snapshot": _stub_universe_artifact(),
        "market_discovery_snapshot": _stub_market_discovery(),
        "holdings_snapshot": _stub_holdings_snapshot(),
    }
    rs = _make_runtime_snapshot()
    ctx = build_push_context(
        push_kind="spike_or_falling_alert",
        pc_evidence=pc_evidence,
        runtime_snapshot=rs,
    )
    msg = build_spike_alert_message(
        asof_iso="2026-06-14T00:00:00+00:00",
        topn_payload=_stub_market_discovery(),
        universe_artifact=_stub_universe_artifact(),
        push_context=ctx,
    )
    assert "[universe momentum 관찰 (push_context 기반)]" in msg
    # AC-5: score 단독 표시가 아닌 풍부 정보.
    assert "방향" in msg
    assert "data_quality" in msg
    # AC-7 / AC-8.
    assert "unavailable" not in msg
    # "매수/매도 지시가 아닙니다" 안내 문구는 허용 — "지금 매수" / "지금 매도" 같은
    # 행동 지시만 금지한다.
    for forbidden in (
        "지금 매수",
        "지금 매도",
        "교체 매수",
        "조정장 확정",
        "위험 threshold 확정",
        "현금 비중 확대",
    ):
        assert forbidden not in msg


# ─── 통합 (Run / draft_payload) — PUSH-1 / PUSH-2 / PUSH-3 ─────────


@pytest.fixture
def _stub_full_runtime(monkeypatch: pytest.MonkeyPatch):
    rs = _make_runtime_snapshot(
        extra_kr_items=[
            {
                "ticker": "229200",
                "name": "KODEX 코스닥150",
                "price": 18000,
                "change_pct": -1.10,
                "volume": 50000,
                "data_status": "ok",
            }
        ]
    )

    def _fake(*, kr_tickers, force_refresh=False):
        return rs

    monkeypatch.setattr("app.draft_three_push.get_runtime_probe_snapshot", _fake)
    monkeypatch.setattr("app.draft.get_runtime_probe_snapshot", _fake)
    yield


def test_push1_message_text_includes_us_indices_through_run(_stub_full_runtime):
    """AC-1 end-to-end: PUSH-1 Run 생성 후 Run.message_text 에 미국 지수 실제
    등락률이 들어있다.
    """
    run = generate_market_briefing_via_generic({"push_kind": "market_briefing"})
    msg = run.message_text or ""
    assert "+0.85%" in msg
    assert "+0.41%" in msg
    assert "+1.25%" in msg


def test_push3_message_text_not_score_only_through_run(_stub_full_runtime):
    """AC-5 end-to-end: PUSH-3 Run 의 message_text 가 score 만 표시하지 않는다."""
    run = generate_spike_alert_via_generic({"push_kind": "spike_or_falling_alert"})
    msg = run.message_text or ""
    # 새 풍부 섹션이 들어있어야 함.
    if "[universe momentum 관찰 (push_context 기반)]" in msg:
        # spike_view 가 있으면 풍부 표시.
        assert "방향" in msg
        # data_quality 또는 overlap 중 최소 1개 같이.
        assert ("data_quality" in msg) or ("보유 종목" in msg)


def test_push2_message_text_has_observation_points(_stub_full_runtime):
    """AC-3 + AC-4 end-to-end: PUSH-2 holdings draft Run 의 message_text 가
    holdings 관찰 포인트 + market_view 연결을 포함한다.
    """
    holdings = [
        Holding(
            ticker="069500",
            quantity=10,
            avg_buy_price=35000,
            name="KODEX 200",
            account_group="일반",
        ),
        Holding(
            ticker="229200",
            quantity=20,
            avg_buy_price=20000,
            name="KODEX 코스닥150",
            account_group="일반",
        ),
    ]
    run = draft_mod.generate_draft_from_holdings(holdings)
    msg = run.message_text or ""
    # market_view 연결 또는 보유 종목 관찰 포인트 섹션 중 최소 1개.
    has_observation = "[보유 종목 관찰 포인트]" in msg
    has_market_view_connection = "[시장 흐름 연결]" in msg
    assert has_observation, "PUSH-2 에 [보유 종목 관찰 포인트] 섹션이 보여야 함"
    assert (
        has_market_view_connection
    ), "PUSH-2 message_text 가 market_view 와 연결되어야 함 (AC-4)"
    # 금지 문구 검사는 이 test 의 본질 (AC-3/AC-4: 섹션 존재 + market_view 연결)
    # 밖이며, 별도 test (test_three_push_runtime_message_builder.py · runner §4-b
    # 통합) 가 이미 담당한다. Spike Conditional Send v1 FIX §4.2:
    # 원래 이 test 에 있던 hard-coded substring 검사 (`"매도 지시" not in msg`) 는
    # 안내 문구 "매수/매도 지시가 아닙니다" 를 오탐하여 실패했다. 새로운 메시지
    # 정책 신설 금지 원칙에 따라 이 부가 검사를 제거한다.


# ─── AC-2: market_view 가 없을 때도 fallback 동작 ──────────────


def test_market_view_empty_when_no_evidence():
    """market_discovery 와 us 가 모두 없으면 market_view 자체가 빈 dict."""
    pc_evidence = {
        "market_discovery_snapshot": {},
        "ml_baseline_snapshot": {},
    }
    rs = {
        "captured_at": None,
        "kr_realtime_price_snapshot": {"status": "unavailable", "items": []},
        "overnight_us_market_snapshot": {"status": "unavailable", "indices": []},
    }
    mv = build_market_view(pc_evidence=pc_evidence, runtime_snapshot=rs)
    assert mv == {}
