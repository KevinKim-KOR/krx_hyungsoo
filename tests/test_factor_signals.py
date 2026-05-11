"""POC2 Step 5D Cleanup — Step 3 보유 비중 영향 factor 회귀 테스트.

분리 출처: tests/test_poc1_loop.py (Step 5D 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

from app import market_cache

from tests._helpers import _enriched_for_factor


def test_step3_factor_signals_normal_case():
    """평가 계산 가능 row 가 1+ 일 때 portfolio 1개 + holding_row 1개(=max_weight) 반환."""
    from app.factors import build_factor_signals, FACTOR_ID

    enriched = _enriched_for_factor(
        [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "current_price": 40000,
                "eval_amount": 400000,
                "pnl_amount": 15000,
                "pnl_rate_pct": 3.9,
                "account_group": "일반",
            },
            {
                "ticker": "0013P0",
                "name": "RISE 미국은행TOP10",
                "quantity": 5,
                "avg_buy_price": 10050,
                "invested_amount": 50250,
                "current_price": 10100,
                "eval_amount": 50500,
                "pnl_amount": 250,
                "pnl_rate_pct": 0.5,
                "account_group": "ISA",
            },
        ]
    )
    sigs = build_factor_signals(enriched)
    assert len(sigs) == 2
    assert sigs[0]["scope"] == "portfolio"
    assert sigs[0]["is_available"] is True
    assert sigs[0]["factor_id"] == FACTOR_ID
    assert sigs[0]["unit"] == "%"
    # 069500 이 평가금액 400,000 > 50,500 으로 최대
    assert "KODEX 200" in sigs[0]["reason_text"]
    assert sigs[0]["fallback_text"] is None

    assert sigs[1]["scope"] == "holding_row"
    assert sigs[1]["ticker"] == "069500"
    assert sigs[1]["account_group"] == "일반"
    assert sigs[1]["source_index"] == 0
    assert sigs[1]["avg_buy_price"] == 38500.0
    assert sigs[1]["is_available"] is True


def test_step3_factor_signals_only_one_holding_row_signal_max_weight():
    """평가 계산 가능 row 가 3+ 여도 holding_row scope signal 은 1개 (max_weight) 만."""
    from app.factors import build_factor_signals

    enriched = _enriched_for_factor(
        [
            {
                "ticker": "AAA",
                "quantity": 1,
                "avg_buy_price": 100,
                "invested_amount": 100,
                "current_price": 100,
                "eval_amount": 100,
            },
            {
                "ticker": "BBB",
                "quantity": 1,
                "avg_buy_price": 100,
                "invested_amount": 100,
                "current_price": 200,
                "eval_amount": 200,
            },
            {
                "ticker": "CCC",
                "quantity": 1,
                "avg_buy_price": 100,
                "invested_amount": 100,
                "current_price": 50,
                "eval_amount": 50,
            },
        ]
    )
    sigs = build_factor_signals(enriched)
    holding_row_sigs = [s for s in sigs if s["scope"] == "holding_row"]
    assert len(holding_row_sigs) == 1
    assert holding_row_sigs[0]["ticker"] == "BBB"


def test_step3_factor_signals_excludes_unpriced_rows():
    """현재가 누락 row 는 분모/분자 모두에서 제외된다."""
    from app.factors import build_factor_signals

    enriched = _enriched_for_factor(
        [
            {
                "ticker": "AAA",
                "quantity": 1,
                "avg_buy_price": 100,
                "invested_amount": 100,
                "current_price": 100,
                "eval_amount": 100,
            },
            {
                # 시세 미확인 — 제외
                "ticker": "BBB",
                "quantity": 1,
                "avg_buy_price": 200,
                "invested_amount": 200,
                "current_price": None,
                "eval_amount": None,
                "price_missing": True,
                "calc_missing": True,
            },
        ]
    )
    sigs = build_factor_signals(enriched)
    assert sigs[0]["is_available"] is True
    assert sigs[0]["input_basis"]["calc_available_count"] == 1
    assert sigs[0]["input_basis"]["excluded_count"] == 1
    # max_weight_row 는 AAA 100% (1/1)
    assert sigs[0]["value"] == 100.0
    assert sigs[1]["ticker"] == "AAA"


def test_step3_factor_signals_all_unpriced_returns_fallback_only():
    """평가 계산 가능 row 가 0개면 portfolio fallback 1개만 반환 (run 실패 아님)."""
    from app.factors import build_factor_signals

    enriched = _enriched_for_factor(
        [
            {
                "ticker": "AAA",
                "quantity": 1,
                "avg_buy_price": 100,
                "invested_amount": 100,
                "current_price": None,
                "price_missing": True,
                "calc_missing": True,
            },
            {
                "ticker": "BBB",
                "quantity": 1,
                "avg_buy_price": 100,
                "invested_amount": 100,
                "current_price": None,
                "price_missing": True,
                "calc_missing": True,
            },
        ]
    )
    sigs = build_factor_signals(enriched)
    assert len(sigs) == 1
    assert sigs[0]["scope"] == "portfolio"
    assert sigs[0]["is_available"] is False
    assert sigs[0]["fallback_text"] == "데이터 부족으로 factor 판단 제외"
    assert sigs[0]["value"] is None
    assert sigs[0]["reason_text"] is None


def test_step3_factor_signals_empty_holdings_returns_fallback():
    """빈 holdings → portfolio fallback 1개."""
    from app.factors import build_factor_signals

    sigs = build_factor_signals([])
    assert len(sigs) == 1
    assert sigs[0]["scope"] == "portfolio"
    assert sigs[0]["is_available"] is False


def test_step3_factor_signals_same_ticker_same_account_different_avg_price_mapping():
    """동일 ticker + 동일 account_group + 다른 avg_buy_price 분할매수 row 가 있을 때
    factor 결과가 잘못된 row 에 매핑되지 않는다 — source_index 기반 매핑 보장."""
    from app.factors import build_factor_signals

    enriched = _enriched_for_factor(
        [
            {
                "ticker": "005930",
                "quantity": 5,
                "avg_buy_price": 70000,
                "invested_amount": 350000,
                "current_price": 80000,
                "eval_amount": 400000,
                "account_group": "일반",
            },
            {
                "ticker": "005930",
                "quantity": 10,
                "avg_buy_price": 75000,
                "invested_amount": 750000,
                "current_price": 80000,
                "eval_amount": 800000,
                "account_group": "일반",
            },
        ]
    )
    sigs = build_factor_signals(enriched)
    holding_row = [s for s in sigs if s["scope"] == "holding_row"][0]
    # 두 번째 row(idx=1, eval=800000) 가 max
    assert holding_row["source_index"] == 1
    assert holding_row["avg_buy_price"] == 75000.0
    # 첫 번째 row 는 holding_row signal 에 등장하지 않는다
    assert sigs[0]["input_basis"]["max_weight_source_index"] == 1


def test_step3_message_text_includes_portfolio_judgment_one_line(client):
    """generate-from-holdings 응답의 message_text 에 [판단 사유] 1줄 + factor name 포함."""
    client.put(
        "/holdings",
        json={
            "holdings": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    "quantity": 3,
                    "avg_buy_price": 84190,
                    "account_group": "일반",
                },
                {
                    "ticker": "0013P0",
                    "name": "RISE 미국은행TOP10",
                    "quantity": 5,
                    "avg_buy_price": 10050,
                    "account_group": "ISA",
                },
            ]
        },
    )
    # 시세 캐시 직접 주입 (외부 fetch 트리거 금지)
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker="069500",
                name="KODEX 200",
                current_price=100000.0,
                price_asof=None,
                price_source="naver",
            ),
            market_cache.MarketQuote(
                ticker="0013P0",
                name="RISE 미국은행TOP10",
                current_price=11000.0,
                price_asof=None,
                price_source="naver",
            ),
        ]
    )
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    body = r.json()
    msg = body["message_text"]
    assert "[판단 사유]" in msg
    # Step7B 명칭 정렬: portfolio reason 은 "보유 종목 상태 브리핑" bullet 안에 통합.
    assert "- 보유 종목 상태 브리핑:" in msg
    # portfolio reason 의 핵심 (max_weight ticker 의 라벨) 이 본문에 포함.
    assert "KODEX 200" in msg
    # Step7B: 별도 "- 보유 비중 영향:" bullet 은 사용자 노출에서 사라짐.
    legacy_factor_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 보유 비중 영향:")
    ]
    assert len(legacy_factor_lines) == 0
    # "보유 종목 상태 브리핑" bullet 은 정확히 1줄.
    briefing_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    ]
    assert len(briefing_lines) == 1


def test_step3_message_text_does_not_list_all_holdings_factor_reasons(client):
    """모든 종목의 factor 사유가 message_text 에 나열되면 안 된다."""
    client.put(
        "/holdings",
        json={
            "holdings": [
                {
                    "ticker": "AAA",
                    "name": "AAA Corp",
                    "quantity": 1,
                    "avg_buy_price": 100,
                    "account_group": "일반",
                },
                {
                    "ticker": "BBB",
                    "name": "BBB Corp",
                    "quantity": 1,
                    "avg_buy_price": 100,
                    "account_group": "ISA",
                },
                {
                    "ticker": "CCC",
                    "name": "CCC Corp",
                    "quantity": 1,
                    "avg_buy_price": 100,
                    "account_group": "연금",
                },
            ]
        },
    )
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker=t,
                name=f"{t} Corp",
                current_price=100.0,
                price_asof=None,
                price_source="naver",
            )
            for t in ("AAA", "BBB", "CCC")
        ]
    )
    r = client.post("/runs/generate-from-holdings")
    msg = r.json()["message_text"]
    # holding_row scope reason ("이 종목은 ... 가장 큰 항목입니다") 은 메시지에 들어가지 않는다
    assert "이 종목은 평가 계산 가능 보유분 중 비중이 가장 큰 항목입니다." not in msg
    # Step7B: portfolio reason 은 "보유 종목 상태 브리핑" 1줄 안에 통합. 별도 "- 보유 비중 영향:" 줄 0건.
    legacy_factor_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 보유 비중 영향:")
    ]
    assert len(legacy_factor_lines) == 0
    briefing_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    ]
    assert len(briefing_lines) == 1


def test_step3_message_text_uses_fallback_when_factor_unavailable(client):
    """전 종목 시세 미확인이면 message_text 에 fallback_text 1줄이 포함된다."""
    client.put(
        "/holdings",
        json={
            "holdings": [
                {
                    "ticker": "ZZZ",
                    "name": "ZZZ",
                    "quantity": 1,
                    "avg_buy_price": 100,
                    "account_group": "일반",
                }
            ]
        },
    )
    # market_cache 비움 (이미 fixture 가 reset 함)
    r = client.post("/runs/generate-from-holdings")
    msg = r.json()["message_text"]
    assert "[판단 사유]" in msg
    assert "데이터 부족으로 factor 판단 제외" in msg


def test_step3_draft_payload_factor_signals_persisted_in_run(client):
    """draft_payload.factor_signals 가 Run 에 저장되고 GET 응답에도 포함된다."""
    client.put(
        "/holdings",
        json={
            "holdings": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    "quantity": 3,
                    "avg_buy_price": 84190,
                    "account_group": "일반",
                }
            ]
        },
    )
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker="069500",
                name="KODEX 200",
                current_price=100000.0,
                price_asof=None,
                price_source="naver",
            ),
        ]
    )
    r = client.post("/runs/generate-from-holdings")
    rid = r.json()["run_id"]
    body = r.json()
    fs = body["draft_payload"].get("factor_signals")
    assert isinstance(fs, list) and len(fs) >= 1
    assert fs[0]["scope"] == "portfolio"
    assert fs[0]["factor_id"] == "portfolio_concentration_v1"

    # GET 응답에도 동일하게 포함
    r2 = client.get(f"/runs/{rid}").json()
    fs2 = r2["draft_payload"].get("factor_signals")
    assert fs2 == fs


def test_step3_legacy_draft_payload_without_factor_signals_renders(client):
    """과거 draft_payload (factor_signals 없음) 도 message_text 빌드가 깨지지 않는다 —
    [판단 사유] 섹션이 없을 뿐, run 자체는 정상 동작."""
    from app import draft_message

    legacy_payload = {
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
        # factor_signals 키 없음
    }
    msg = draft_message.build_message_text("run_legacy_step3", legacy_payload)
    assert isinstance(msg, str)
    assert len(msg) > 0
    assert "[판단 사유]" not in msg  # 누락 키는 섹션 자체 생략
    # 기본 헤더/요약은 그대로 빌드
    assert "POC2 holdings 승인 처리" in msg
