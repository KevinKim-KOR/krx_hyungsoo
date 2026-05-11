"""POC2 Step 5D Cleanup — Step 5B holdings mode momentum_result 회귀 테스트.

분리 출처: tests/test_poc1_loop.py (Step 5D 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

from tests._helpers import _put_holdings_for_momentum


def test_step5b_holdings_mode_momentum_result_built():
    """holdings mode momentum_result 가 빌드되고 6 키를 모두 갖는다."""
    from app.momentum import build_holdings_momentum_result, ENGINE_ID, ENGINE_VERSION
    from app.holdings_enrich import EnrichedHolding

    enriched = [
        EnrichedHolding(
            ticker="005930",
            name="삼성전자",
            quantity=5,
            avg_buy_price=70000,
            invested_amount=350000,
            current_price=80000,
            price_asof=None,
            price_source="naver",
            eval_amount=400000,
            pnl_amount=50000,
            pnl_rate_pct=14.29,
            buy_weight_pct=None,
            market_weight_pct=None,
            price_missing=False,
            calc_missing=False,
            account_group="일반",
            source_index=0,
        ),
    ]
    mr = build_holdings_momentum_result(enriched, asof="2026-04-30T00:00:00+00:00")
    assert mr["engine_id"] == ENGINE_ID
    assert mr["engine_version"] == ENGINE_VERSION
    assert mr["mode"] == "holdings"
    assert mr["asof"] == "2026-04-30T00:00:00+00:00"
    assert "summary" in mr
    assert "candidates" in mr


def test_step5b_draft_payload_momentum_result_persisted(client):
    """generate-from-holdings 응답의 draft_payload 에 momentum_result 6번째 키
    (factor_signals 5번째 다음) 가 포함되고 GET 응답에서도 동일하게 조회된다."""
    _put_holdings_for_momentum(client)
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    body = r.json()
    payload = body["draft_payload"]
    assert "momentum_result" in payload
    mr = payload["momentum_result"]
    assert mr["mode"] == "holdings"
    assert mr["engine_id"] == "momentum_engine_placeholder_v1"

    # GET /runs/{id} 에서도 동일 momentum_result 조회됨
    rid = body["run_id"]
    r2 = client.get(f"/runs/{rid}").json()
    assert r2["draft_payload"]["momentum_result"] == mr


def test_step5b_candidate_includes_row_mapping_fields(client):
    """holdings mode candidate 에 source_index, ticker, account_group, avg_buy_price
    4 키가 모두 포함된다 (row 매핑 깨짐 방지)."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    cands = body["draft_payload"]["momentum_result"]["candidates"]
    assert len(cands) == 3
    for c in cands:
        assert "source_index" in c
        assert "ticker" in c
        assert "account_group" in c
        assert "avg_buy_price" in c


def test_step5b_same_ticker_different_account_or_avg_mapping_correct(client):
    """동일 ticker(005930) 가 다른 avg_buy_price 두 row 로 존재해도 candidate 가
    잘못된 row 에 매핑되지 않는다 — source_index 가 1:1 보존."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    cands = body["draft_payload"]["momentum_result"]["candidates"]
    samsung = [c for c in cands if c["ticker"] == "005930"]
    assert len(samsung) == 2
    # source_index 0/1 두 row 가 모두 존재하고 avg 다름
    indices = sorted(c["source_index"] for c in samsung)
    assert indices == [0, 1]
    avgs = sorted(c["avg_buy_price"] for c in samsung)
    assert avgs == [70000.0, 75000.0]
    # candidate_id 에도 avg 가 들어가 두 row 가 구분된다
    ids = {c["candidate_id"] for c in samsung}
    assert len(ids) == 2


def test_step5b_pnl_rate_present_yields_scored(client):
    """pnl_rate 가 있는 후보는 score_result.is_scored=True + score_value 가 부여된다."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    cands = body["draft_payload"]["momentum_result"]["candidates"]
    for c in cands:
        sr = c["score_result"]
        assert sr["is_scored"] is True
        assert isinstance(sr["score_value"], (int, float))
        assert sr["score_unit"] == "%"
        assert sr["ranking_basis"] == "pnl_rate"
        # Step7B (2026-05-12): score_basis_text 의 "placeholder" 단어 제거 — 사용자
        # 노출 안전 차원. 현재 표현: "현재 보유 종목 점검 기준 (평가수익률)".
        assert "평가수익률" in sr["score_basis_text"]
        assert "placeholder" not in sr["score_basis_text"]


def test_step5b_pnl_rate_missing_yields_excluded():
    """시세 미확인/계산 정보 부족 후보는 is_available=False + is_scored=False +
    exclusion_reason. run 실패 처리 안 함."""
    from app.momentum import build_holdings_momentum_result
    from app.holdings_enrich import EnrichedHolding

    enriched = [
        EnrichedHolding(
            ticker="ZZZ",
            name="ZZZ",
            quantity=1,
            avg_buy_price=100,
            invested_amount=100,
            current_price=None,
            price_asof=None,
            price_source=None,
            eval_amount=None,
            pnl_amount=None,
            pnl_rate_pct=None,
            buy_weight_pct=None,
            market_weight_pct=None,
            price_missing=True,
            calc_missing=True,
            account_group="일반",
            source_index=0,
        ),
    ]
    mr = build_holdings_momentum_result(enriched)
    assert mr["summary"]["scored_candidates"] == 0
    assert mr["summary"]["excluded_candidates"] == 1
    c = mr["candidates"][0]
    assert c["is_available"] is False
    assert c["score_result"]["is_scored"] is False
    assert "exclusion_reason" in c
    assert "데이터 부족" in c["reason_text"]
    assert "rank" not in c


def test_step5b_rank_omitted_when_only_one_scorable():
    """비교 가능한 후보가 1개 뿐이면 rank 는 생략된다 (Step5A §5.5)."""
    from app.momentum import build_holdings_momentum_result
    from app.holdings_enrich import EnrichedHolding

    enriched = [
        EnrichedHolding(
            ticker="AAA",
            name="AAA",
            quantity=1,
            avg_buy_price=100,
            invested_amount=100,
            current_price=110,
            price_asof=None,
            price_source=None,
            eval_amount=110,
            pnl_amount=10,
            pnl_rate_pct=10.0,
            buy_weight_pct=None,
            market_weight_pct=None,
            price_missing=False,
            calc_missing=False,
            account_group="일반",
            source_index=0,
        ),
    ]
    mr = build_holdings_momentum_result(enriched)
    c = mr["candidates"][0]
    assert c["score_result"]["is_scored"] is True
    assert "rank" not in c


def test_step5b_rank_assigned_when_two_or_more_scorable(client):
    """비교 가능한 후보가 2개 이상이면 rank 가 부여되고 score 내림차순."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    cands = body["draft_payload"]["momentum_result"]["candidates"]
    # 모두 scorable 한 케이스 (시세 cache 모두 채움)
    for c in cands:
        assert "rank" in c
    # rank 1 = 최고 score_value
    by_rank = sorted(cands, key=lambda c: c["rank"])
    scores = [c["score_result"]["score_value"] for c in by_rank]
    assert scores == sorted(scores, reverse=True)


def test_step5b_message_text_judgment_header_appears_once(client):
    """[판단 사유] 헤더는 message_text 에 정확히 1번만 등장한다."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg = body["message_text"]
    assert msg.count("[판단 사유]") == 1


def test_step5b_message_text_contains_both_factor_and_momentum_bullets(client):
    """Step7B 통합: 별도 "- 보유 비중 영향:" / "- 모멘텀 점검:" bullet 은 사라지고
    "- 보유 종목 상태 브리핑:" 1줄 안에 두 정보가 모두 들어간다.

    portfolio reason 의 핵심 (가장 비중이 큰 종목 라벨) + holdings momentum 의 핵심
    (점검값 가장 높은 종목 라벨) 이 같은 1줄에 통합되어야 한다.
    """
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg = body["message_text"]
    assert "[판단 사유]" in msg
    assert "- 보유 종목 상태 브리핑:" in msg
    # 별도 bullet 형태로는 더 이상 등장하지 않음
    assert "- 보유 비중 영향:" not in msg
    assert "- 모멘텀 점검:" not in msg
    # 보유 비중 영향 핵심 표현이 본문에 통합 포함
    assert "비중이 가장 큽니다" in msg
    # holdings momentum 핵심 표현이 본문에 통합 포함
    assert "점검값이 가장 높습니다" in msg


def test_step5b_message_text_no_separate_momentum_header(client):
    """별도 [모멘텀 점검] 헤더는 message_text 에 만들지 않는다 (Step5B AC-15)."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg = body["message_text"]
    assert "[모멘텀 점검]" not in msg


def test_step5b_existing_factor_signals_preserved(client):
    """Step3 의 보유 비중 영향 factor 가 깨지지 않는다 — factor_signals 그대로."""
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    payload = body["draft_payload"]
    assert "factor_signals" in payload
    fs = payload["factor_signals"]
    assert isinstance(fs, list) and len(fs) >= 1
    portfolio = [s for s in fs if s.get("scope") == "portfolio"]
    assert len(portfolio) == 1
    assert portfolio[0]["factor_id"] == "portfolio_concentration_v1"


def test_step5b_message_text_does_not_list_all_candidate_ranks(client):
    """전체 후보 순위는 Telegram 에 나열되지 않는다 (Top N 정책 금지).

    Step7B: 모멘텀 정보는 "- 보유 종목 상태 브리핑:" 1줄 안에 통합되며 candidate 별
    상세 reason_text 는 노출되지 않는다.
    """
    _put_holdings_for_momentum(client)
    body = client.post("/runs/generate-from-holdings").json()
    msg = body["message_text"]
    # candidate 별 상세 reason_text 가 메시지에 들어가지 않음 (Step7B 후 표현 정정 반영)
    assert "현재 평가수익률 기준 보유 종목 점검값이 계산되었습니다" not in msg
    # 보유 종목 상태 브리핑 라인은 정확히 1줄
    briefing_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 보유 종목 상태 브리핑:")
    ]
    assert len(briefing_lines) == 1
    # 별도 "- 모멘텀 점검:" bullet 0건
    legacy_momentum_lines = [
        ln for ln in msg.split("\n") if ln.startswith("- 모멘텀 점검:")
    ]
    assert len(legacy_momentum_lines) == 0


def test_step5b_legacy_payload_without_momentum_result_renders():
    """과거 draft_payload (momentum_result 없음) 도 build_message_text 가 깨지지 않는다.
    factor bullet 만 있고 momentum bullet 은 자연 생략."""
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
                "reason_text": "test reason",
                "fallback_text": None,
            }
        ],
        # momentum_result 키 없음
    }
    msg = draft_message.build_message_text("run_legacy_5b", legacy)
    assert "[판단 사유]" in msg
    assert msg.count("[판단 사유]") == 1
    # Step7B 통합: legacy payload (momentum_result 없음) 라도 portfolio reason 만으로
    # "보유 종목 상태 브리핑" bullet 이 생성된다. 별도 "- 보유 비중 영향:" 줄은 없다.
    assert "- 보유 종목 상태 브리핑:" in msg
    assert "- 보유 비중 영향:" not in msg
    assert "- 모멘텀 점검:" not in msg


# ─── POC2 Step 5C: Universe Mode Minimal Candidate Source ───────────
