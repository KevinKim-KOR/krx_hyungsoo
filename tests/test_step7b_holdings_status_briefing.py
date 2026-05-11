"""POC2 Step 7B — 보유 종목 상태 브리핑 최소 정리 회귀 테스트.

테스트 범위 (Step7B §9):
- message_text [판단 사유] 에 "보유 종목 상태 브리핑" 1줄 포함.
- 별도 "- 보유 비중 영향:" / "- 모멘텀 점검:" bullet 잔존 0건.
- 보유 비중 영향 핵심 정보 (가장 비중 큰 종목 라벨) 가 브리핑 본문에 포함.
- holdings momentum 핵심 정보 (점검값 가장 높은 종목 라벨) 가 브리핑 본문에 포함.
- 사용자 노출 message_text 에 "placeholder" 단어 0건.
- 매수/매도 권유 문구 (BUY / SELL / 매수 추천 / 매도 추천) 0건.
- "매수/매도 의견이 아닙니다" 중립 안내 포함.
- "신규 ETF 관찰 후보" bullet 유지 (Step7A 회귀).
- [판단 사유] 헤더 1회만 (헤더 중복 금지).
- Telegram payload = Run.message_text 단일 소스.
"""

from __future__ import annotations

from datetime import date

from tests._helpers import _put_holdings_for_momentum, _seed_payload, _write_seed

# ─── 1. 통합 bullet 라벨 / 구조 ──────────────────────────────────────


def test_briefing_bullet_present_in_message_text(client, _isolated_universe):
    """message_text 에 '- 보유 종목 상태 브리핑:' 1줄이 정확히 존재."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg: str = body["message_text"]
    assert "- 보유 종목 상태 브리핑:" in msg
    briefing_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    ]
    assert len(briefing_lines) == 1


def test_legacy_factor_and_momentum_bullets_not_separate(client, _isolated_universe):
    """별도 '- 보유 비중 영향:' / '- 모멘텀 점검:' bullet 잔존 0건 (Step7B 통합)."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "- 보유 비중 영향:" not in msg
    assert "- 모멘텀 점검:" not in msg


# ─── 2. 두 데이터 소스 통합 ───────────────────────────────────────


def test_briefing_includes_portfolio_concentration_info(client, _isolated_universe):
    """portfolio reason 의 핵심 ("비중이 가장 큽니다") 이 브리핑 본문에 포함."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "- 보유 종목 상태 브리핑:" in msg
    briefing_line = next(
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    )
    assert "비중이 가장 큽니다" in briefing_line


def test_briefing_includes_holdings_momentum_info(client, _isolated_universe):
    """holdings momentum top_candidate 핵심 ("점검값이 가장 높습니다") 이 브리핑 본문에 포함."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    briefing_line = next(
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    )
    assert "점검값이 가장 높습니다" in briefing_line


# ─── 3. placeholder 사용자 노출 제거 ──────────────────────────────


def test_message_text_does_not_contain_placeholder_word(client, _isolated_universe):
    """사용자 노출 message_text 에 'placeholder' 단어 0건 (Step7B §3.2)."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "placeholder" not in msg


# ─── 4. 매수/매도 의견 아님 중립 안내 ────────────────────────────


def test_message_text_no_buy_sell_recommendation(client, _isolated_universe):
    """사용자 노출 message_text 에 매수/매도 권유 문구 0건."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    forbidden_phrases = [
        "매수 추천",
        "매도 추천",
        "매수 권유",
        "매도 권유",
        "BUY",
        "SELL",
        "리밸런싱",
        "비중 조정 권유",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in msg, f"Forbidden phrase found in message_text: {phrase}"


def test_briefing_contains_neutral_not_buy_sell_note(client, _isolated_universe):
    """브리핑 bullet 에 '매수/매도 의견이 아닙니다' 중립 안내 포함."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    briefing_line = next(
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    )
    assert "매수/매도 의견이 아닙니다" in briefing_line


# ─── 5. Step7A 회귀 ───────────────────────────────────────────────


def test_new_etf_watch_candidate_bullet_preserved(client, _isolated_universe):
    """Step7A '신규 ETF 관찰 후보' bullet 이 유지된다."""
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert "- 신규 ETF 관찰 후보:" in msg


def test_bullet_order_briefing_then_new_etf(client, _isolated_universe):
    """bullet 순서: 보유 종목 상태 브리핑 → 신규 ETF 관찰 후보."""
    _write_seed(
        _isolated_universe["seed_file"], _seed_payload(date.today().isoformat())
    )
    client.post("/universe/momentum/refresh")
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    briefing_idx = msg.find("- 보유 종목 상태 브리핑:")
    new_etf_idx = msg.find("- 신규 ETF 관찰 후보:")
    assert briefing_idx > 0 and new_etf_idx > 0
    assert briefing_idx < new_etf_idx


# ─── 6. 헤더 중복 금지 + 단일 소스 ───────────────────────────────


def test_judgment_header_once_step7b(client, _isolated_universe):
    """[판단 사유] 헤더 1회만 (Step7B 회귀)."""
    _put_holdings_for_momentum(client)
    msg: str = client.post("/runs/generate-from-holdings").json()["message_text"]
    assert msg.count("[판단 사유]") == 1


def test_telegram_uses_run_message_text_single_source(client, _isolated_universe):
    """Run.message_text 가 판단 사유 부분의 단일 소스 — preview API 응답과 일치."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    run_id = body["run_id"]
    # 같은 run 을 GET 으로 조회 — message_text 동일해야 함
    fetched = client.get(f"/runs/{run_id}").json()
    assert fetched["message_text"] == body["message_text"]
    # 브리핑 bullet 동일
    assert "- 보유 종목 상태 브리핑:" in fetched["message_text"]


# ─── 7. legacy payload (momentum_result 없음) — Step7B 호환 ────────


def test_briefing_bullet_when_no_momentum_result():
    """draft_payload 에 momentum_result 가 없어도 portfolio reason 만으로 브리핑 생성."""
    from app import draft_message

    legacy = {
        "title": "legacy",
        "asof": "2026-04-01T00:00:00+00:00",
        "note": "legacy",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 3,
                "avg_buy_price": 84190,
                "invested_amount": 252570,
                "buy_weight_pct": 100.0,
                "action": "HOLD",
                "reason": "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)",
            }
        ],
        "factor_signals": [
            {
                "factor_id": "portfolio_concentration_v1",
                "factor_name": "보유 비중 영향",
                "scope": "portfolio",
                "is_available": True,
                "value": 100.0,
                "unit": "%",
                "reason_text": "평가 계산 가능 보유분 중 KODEX 200의 비중이 가장 큽니다.",
                "fallback_text": None,
            }
        ],
        # momentum_result 키 없음
    }
    msg = draft_message.build_message_text("run_legacy_7b", legacy)
    assert "- 보유 종목 상태 브리핑:" in msg
    assert "비중이 가장 큽니다" in msg
    assert "매수/매도 의견이 아닙니다" in msg
    assert "- 보유 비중 영향:" not in msg
    assert "- 모멘텀 점검:" not in msg
