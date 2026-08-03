"""POC3-06 D구간 — PUSH preview 와 Dashboard 정합 (§6.1·AC-7·AC-14·AC-15·AC-16).

- holdings_briefing message_text 가 draft_payload.judgment_summary.holdings.top_holdings
  (= Dashboard 와 동일 composer 결과)를 '오늘 먼저 볼 보유 ETF' 로 표시한다.
- market_briefing message_text 가 market_context(= Dashboard 와 동일 저장값 read)의
  KOSPI 관찰값·국면·지속일을 '시장 위치' 로 표시한다.
- 값·순서가 composer 결과와 일치 (화면별 재계산 없음).
"""

from __future__ import annotations

from app.draft_message import build_message_text
from app.message_market_briefing import build_market_briefing_message


def _holdings_payload_with_summary(
    top_holdings: list[dict], *, need_check: int = 0
) -> dict:
    return {
        "title": "보유 종목 기반 초안 (2026-07-24)",
        "asof": "2026-07-24T00:00:00+00:00",
        "note": "",
        "recommendations": [
            {"ticker": "A00001", "quantity": 10, "avg_buy_price": 1000}
        ],
        "judgment_summary": {
            "market_position": {},
            "holdings": {
                "top_holdings": top_holdings,
                "coverage": {
                    "total": len(top_holdings) + need_check,
                    "need_check": need_check,
                    "ok": len(top_holdings),
                },
            },
            "data_status": {
                "holdings_asof": "2026-06-17T14:35:07+00:00",
                "market_evidence_asof": "2026-07-24",
            },
        },
        # runtime_package 없음 → failed 분기 미진입(정상 본문 조립).
    }


def test_holdings_briefing_shows_top_holdings_from_summary():
    top = [
        {
            "ticker": "A00001",
            "name": "ETF 하나",
            "market_weight_pct": 60.0,
            "pnl_rate_pct": -2.0,
            "return_5d_pct": -5.0,
            "return_20d_pct": -3.0,
            "excess_vs_kodex200_20d_pctp": -1.5,
        },
        {
            "ticker": "A00002",
            "name": "ETF 둘",
            "market_weight_pct": 40.0,
            "pnl_rate_pct": 1.5,
            "return_5d_pct": -1.0,
            "return_20d_pct": 2.0,
            "excess_vs_kodex200_20d_pctp": 0.5,
        },
    ]
    payload = _holdings_payload_with_summary(top, need_check=2)
    msg = build_message_text("run_test", payload)
    assert "[오늘 먼저 볼 보유 ETF]" in msg
    # Dashboard 와 동일 순서·ticker.
    assert "ETF 하나 (A00001)" in msg
    assert "ETF 둘 (A00002)" in msg
    # AC-7: 평가 비중·평가손익 표시.
    assert "비중 60.0%" in msg
    assert "손익 -2.00%" in msg
    # 5일 값 표시 (composer 결과 그대로).
    assert "5일 -5.00%" in msg
    assert "20일 -3.00%" in msg
    # AC-15: Holdings/Market 기준일 표시.
    assert "보유 기준일" in msg
    assert "시장 기준일 2026-07-24" in msg
    # 자료 확인 필요 제한 문장 (판정 아님).
    assert "자료 확인 필요 2건" in msg
    assert "매수·매도 판단이 아닙니다" in msg
    # A00001 이 A00002 보다 먼저 (5일 낮은 순).
    assert msg.index("A00001") < msg.index("A00002")


def test_holdings_briefing_omits_section_when_no_top_holdings():
    payload = _holdings_payload_with_summary([])
    msg = build_message_text("run_test", payload)
    # 0건 위장 문구 없이 섹션 자체 생략.
    assert "[오늘 먼저 볼 보유 ETF]" not in msg


def _topn_with_market_context() -> dict:
    return {
        "status": "ok",
        "asof": "2026-07-24",
        "basis": "one_month",
        "candidates": [],
        "market_context": {
            "status": "ok",
            "asof": "2026-07-24",
            "regime_label": "하락장",
            "regime_code": "bear",
            "kospi": {
                "status": "ok",
                "daily_return_pct": -5.72,
                "return_1y_pct": 109.71,
                "high_52w_gap_pct": -26.59,
                "as_of_date": "2026-07-24",
            },
            "regime_streak": {
                "regime_code": "bear",
                "streak_days": 12,
                "at_least": False,
            },
        },
    }


def test_market_briefing_shows_market_position_from_context():
    msg = build_market_briefing_message(
        asof_iso="2026-07-24T00:00:00+00:00",
        topn_payload=_topn_with_market_context(),
    )
    assert "[시장 위치]" in msg
    # Dashboard 와 동일 KOSPI 관찰값(같은 market_context).
    assert "일간 -5.72%" in msg
    assert "1년 +109.71%" in msg
    assert "최근 1년 고점 대비 -26.59%" in msg
    # 기존 국면 + 지속일 (KODEX200 기준 명시).
    assert "하락장" in msg
    assert "12거래일째" in msg
    assert "KODEX200 기준" in msg


def test_market_briefing_omits_position_when_context_unavailable():
    topn = {
        "status": "unavailable",
        "asof": "2026-07-24",
        "candidates": [],
        "market_context": {"status": "unavailable"},
    }
    msg = build_market_briefing_message(
        asof_iso="2026-07-24T00:00:00+00:00", topn_payload=topn
    )
    assert "[시장 위치]" not in msg
