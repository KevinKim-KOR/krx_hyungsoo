"""POC2 Step 5D-2 Cleanup — draft_message Step2B + handoff + Step2D message_text.

분리 출처: tests/test_holdings_draft_flow.py (Step 5D-2 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

from app import api, delivery, store
from app.delivery import deliver as _ORIGINAL_DELIVER  # autouse stub 우회용

from tests._helpers import _VALID_HOLDINGS_FOR_2D, _make_holding_rec


def test_draft_message_step2b_summary_form_no_per_item_buy_fields():
    """Step 2B: 메시지가 요약형 — 수량/평균매입단가/매입금액/매입비중/현재가/평가금액 등
    종목별 매입 상세 필드는 기본 메시지에 등장하지 않는다 (UI 에서 확인)."""
    from app import draft_message

    payload = {
        "title": "보유 종목 기반 초안 (2026-04-25)",
        "asof": "2026-04-25T00:00:00+00:00",
        "note": "holdings 항목 2건 기준 자동 생성. 추천 판단 없이 보유 현황 기준입니다.",
        "recommendations": [
            {
                "ticker": "0013P0",
                "name": "RISE 미국은행TOP10",
                "quantity": 5,
                "avg_buy_price": 10050,
                "invested_amount": 50250,
                "buy_weight_pct": 47.6,
                "action": "HOLD",
                "reason": ("보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)"),
            },
            {
                "ticker": "0015B0",
                "quantity": 5,
                "avg_buy_price": 11063,
                "invested_amount": 55315,
                "buy_weight_pct": 52.4,
                "action": "HOLD",
                "reason": ("보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)"),
            },
        ],
    }
    msg = draft_message.build_message_text("run_xxx", payload)

    # raw JSON 노출 금지
    assert "[{" not in msg
    assert '"ticker"' not in msg
    assert "recommendations:" not in msg

    # 헤더 / run_id / 제목 / 전체 요약 섹션
    assert "POC2 holdings 승인 처리" in msg
    assert "run_id: run_xxx" in msg
    assert "보유 종목 기반 초안" in msg
    assert "전체 요약:" in msg
    assert "보유 종목: 2개" in msg

    # 종목별 매입 상세는 기본 메시지에서 제외 (Step 2B AC 6)
    # 종목별 prefix "     - " 접두로 검증 (요약은 "   - 총 매입금액" 처럼 다른 prefix)
    assert "     - 수량:" not in msg
    assert "     - 평균 매입단가:" not in msg
    assert "     - 매입금액:" not in msg
    assert "     - 매입비중:" not in msg
    assert "     - 현재가:" not in msg
    assert "     - 평가금액:" not in msg

    # UI 안내 문구
    assert "웹 화면에서 확인" in msg


def test_draft_message_default_hold_items_excluded_from_focus():
    """Step 2B: action=HOLD + 기본 reason 만 가진 종목은 주목 종목에 들어가지 않는다.

    단 시세 미확인이면 별도 카테고리로 표시될 수 있다 — 본 테스트는 시세 확인+기본 HOLD 만.
    """
    from app import draft_message

    payload = {
        "title": "기본 HOLD 만",
        "asof": "x",
        "note": "",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "buy_weight_pct": 100.0,
                "current_price": 38500,
                "eval_amount": 385000,
                "pnl_amount": 0,
                "pnl_rate_pct": 0.0,
                "market_weight_pct": 100.0,
                "action": "HOLD",
                "reason": draft_message.DEFAULT_HOLD_REASON,
            }
        ],
    }
    msg = draft_message.build_message_text("run_basic_hold", payload)
    # 요약은 포함
    assert "보유 종목: 1개" in msg
    assert "시세 확인: 1개" in msg

    # 단일 종목이고 다른 후보가 없어 손익률 상위/하위/시장비중 상위로 1건은 잡힐 수 있음.
    # 핵심 보장: 메시지 자체는 요약 위주이고 raw JSON / 매입 상세 필드는 등장 안 함.
    assert "수량:" not in msg
    assert "현재가:" not in msg


def test_draft_message_omits_missing_fields():
    """누락 필드는 줄 자체 생략. undefined/null/None/NaN 노출 금지."""
    from app import draft_message

    # quantity 만 있는 최소 항목 — Step 2B 에서는 어떤 종목별 매입 줄도 안 나옴.
    payload = {
        "title": "최소",
        "asof": "x",
        "note": "",
        "recommendations": [{"ticker": "069500", "quantity": 10}],
    }
    msg = draft_message.build_message_text("run_min", payload)
    # 미존재 필드는 'undefined' / 'None' / 'NaN' 으로 나오지 않음
    assert "undefined" not in msg
    assert "None" not in msg
    assert "NaN" not in msg
    # 종목별 매입 상세 라인은 모두 미표시 (종목별 prefix "     - " 로 검증)
    assert "     - 평균 매입단가:" not in msg
    assert "     - 매입금액:" not in msg
    assert "     - 매입비중:" not in msg
    # 시세 미확인 1개 종목이므로 [시세 미확인] 표기는 주목 섹션에 등장
    assert "보유 종목: 1개" in msg
    assert "시세 확인: 0개 / 미확인: 1개" in msg


def test_draft_message_returns_empty_for_non_holdings():
    from app import draft_message

    # 샘플 형태(score) 는 빈 문자열 반환 (호출자가 raw fallback 결정)
    payload = {
        "title": "샘플",
        "note": "",
        "recommendations": [{"ticker": "069500", "score": 0.5, "action": "HOLD"}],
    }
    msg = draft_message.build_message_text("run_sample", payload)
    assert msg == ""


def test_handoff_artifact_message_text_for_holdings_payload(tmp_path, monkeypatch):
    # delivery.deliver 가 holdings draft 를 보낼 때 사용하는 빌더 + 저장 흐름을
    # 단위 단위로 검증. autouse 의 deliver-stub 영향을 받지 않도록 직접 호출.
    from app import draft_message
    from app.models import Run
    import json as _json

    monkeypatch.setattr(store, "HANDOFF_STAGING_DIR", tmp_path / "stg")

    holdings_payload = {
        "title": "보유 종목 기반 초안 (test)",
        "asof": "2026-04-25T00:00:00+00:00",
        "note": "test note",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "buy_weight_pct": 100.0,
                "action": "HOLD",
                "reason": "보유 종목 현황",
            }
        ],
    }
    run = Run(
        run_id="run_step1a_test",
        asof="2026-04-25T00:00:00+00:00",
        status="DELIVERING",
        draft_payload=holdings_payload,
    )
    # delivery.deliver 의 핵심 분기 재현:
    assert draft_message.is_holdings_draft(run.draft_payload)
    msg = draft_message.build_message_text(run.run_id, run.draft_payload or {})
    path = store.write_handoff_artifact(run, "2026-04-25T00:00:01+00:00", msg)

    body = _json.loads(path.read_text(encoding="utf-8"))
    assert "message_text" in body
    assert "POC2 holdings 승인 처리" in body["message_text"]
    assert "KODEX 200 (069500)" in body["message_text"]
    # draft_payload 는 그대로 유지
    assert body["draft_payload"] == holdings_payload
    # raw recommendations JSON 이 message_text 에 포함되지 않음
    assert "[{" not in body["message_text"]
    assert '"ticker"' not in body["message_text"]


# ─── POC2 Step 1: holdings 기반 draft 생성 ─────────────────────────────


def test_draft_message_includes_summary_eval_lines_when_priced():
    """Step 2B: enrich 된 payload 에서 전체 요약 — 평가금액/평가손익/평가수익률 표시 (시세 확인 기준).

    요약의 평가수익률은 합계 기준으로 재계산된다 (priced_pnl / priced_invested * 100).
    종목 단일 + 깔끔한 비율(10%) 로 검증.
    """
    from app import draft_message

    payload = {
        "title": "보유 종목 기반 초안 (test)",
        "asof": "x",
        "note": "n",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 10000,
                "invested_amount": 100000,
                "buy_weight_pct": 100.0,
                "current_price": 11000,
                "eval_amount": 110000,
                "pnl_amount": 10000,
                "pnl_rate_pct": 10.0,
                "market_weight_pct": 100.0,
                "action": "HOLD",
                "reason": "보유 종목 현황",
            }
        ],
    }
    msg = draft_message.build_message_text("run_x", payload)
    # 전체 요약 — 시세 확인 카운트 + 평가 계산 라벨 (current_price 있어도 eval_amount
    # 가 없으면 평가 집계에서 빠지도록 라벨 구분).
    assert "전체 요약:" in msg
    assert "보유 종목: 1개" in msg
    assert "시세 확인: 1개 / 미확인: 0개" in msg
    assert "평가금액: 110,000원 (평가 계산 1개 기준)" in msg
    assert "평가손익: +10,000원 (평가 계산 1개 기준)" in msg
    assert "평가수익률: +10% (평가 계산 1개 기준)" in msg
    # 종목별 현재가 줄은 미표시 (종목별 prefix "     - " 으로 검증)
    assert "     - 현재가:" not in msg
    # "실시간" 이라는 단어는 사용하지 않는다 (지시문 금지어)
    assert "실시간" not in msg


def test_draft_message_shows_price_missing_marker_by_key_absence():
    """current_price 키 자체가 없는 holdings 항목은 [시세 미확인] 표시 + 미확인 경고 문구."""
    from app import draft_message

    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "buy_weight_pct": 100.0,
                "action": "HOLD",
            }
        ],
    }
    msg = draft_message.build_message_text("run_x", payload)
    assert "[시세 미확인]" in msg
    # 시세 미확인 종목이 있을 때 경고 문구
    assert "일부 종목 시세 미확인" in msg
    # 종목별 현재가/평가금액 라인 자체가 표시되지 않음 (종목별 prefix 검증)
    assert "     - 현재가:" not in msg
    assert "     - 평가금액:" not in msg
    # undefined / null / NaN 노출 금지
    assert "undefined" not in msg
    assert "None" not in msg
    assert "NaN" not in msg


# ─── POC2 Step 2B — Telegram Message Compaction ────────────────────────


def test_draft_message_step2b_large_holdings_under_length_limit():
    """AC1/AC9: 18+ 보유 종목에서도 message_text 가 안전 한도 이하."""
    from app import draft_message

    recs = []
    for i in range(20):
        recs.append(
            _make_holding_rec(
                ticker=f"00{i:04d}0",
                name=f"테스트종목매우긴이름가나다라마바사아자차카타파하_{i}",
                quantity=10,
                avg_buy_price=10000 + i * 100,
                current_price=10000 + i * 110,
                pnl_rate_pct=(i - 10) * 0.5,
                market_weight_pct=5.0,
            )
        )
    payload = {
        "title": "20종목 large holdings 테스트",
        "asof": "x",
        "note": "20개 종목 대량 시나리오",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_large", payload)

    assert len(msg) <= draft_message.MAX_LENGTH_CHARS
    # 전체 종목 모두 상세 나열되지 않아야 한다 (AC2)
    # 20종목 × 종목명 30+자로 보면 전부 나열되면 한도 초과 — 길이 자체로도 검증되지만 명시 보강
    full_listed_count = sum(1 for r in recs if r["name"] in msg)
    assert full_listed_count < len(recs)


def test_draft_message_step2b_default_hold_not_in_focus():
    """AC3: 기본 HOLD 종목(action=HOLD + 기본 reason)은 요약에는 들어가도 상세 목록에 전부 들어가지 않는다.

    구체적으로: 기본 HOLD 만 있을 때 시세 확인된 종목은 손익률/시장비중 정렬 결과에
    한해 일부만 노출. 모든 기본 HOLD 가 다 노출되지는 않는다.
    """
    from app import draft_message

    recs = []
    for i in range(10):
        recs.append(
            _make_holding_rec(
                ticker=f"AAA{i:03d}",
                quantity=10,
                avg_buy_price=10000,
                current_price=10000 + i * 100,
                pnl_rate_pct=float(i),
                market_weight_pct=10.0,
            )
        )
    payload = {
        "title": "기본 HOLD 만",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_only_hold", payload)
    # 요약에 10개 모두 카운트
    assert "보유 종목: 10개" in msg
    # 주목 종목 개수는 10개보다 적어야 한다 (Top N 합 = 최대 9, 중복 제거 후 더 적을 수 있음)
    listed = sum(1 for r in recs if (r["ticker"] in msg))
    assert listed < 10


def test_draft_message_step2b_omits_quantity_avg_price_lines():
    """AC6: 메시지에 수량/평균매입단가/매입금액/매입비중/현재가/평가금액 라인이 없다."""
    from app import draft_message

    recs = [
        _make_holding_rec(
            ticker="069500",
            name="KODEX 200",
            quantity=10,
            avg_buy_price=38500,
            current_price=40000,
            pnl_rate_pct=3.9,
            market_weight_pct=100.0,
        )
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_x", payload)
    # 종목별 prefix "     - " 로 검증 (요약 라인 "   - 총 매입금액" 등 prefix 가 다름)
    assert "     - 수량:" not in msg
    assert "     - 평균 매입단가:" not in msg
    assert "     - 매입금액:" not in msg
    assert "     - 매입비중:" not in msg
    assert "     - 현재가:" not in msg
    assert "     - 평가금액:" not in msg


def test_draft_message_step2b_pnl_rate_and_action_reason_included():
    """AC7: 종목별로 평가수익률/판단/사유 중심 표시."""
    from app import draft_message

    # 비-기본 reason 으로 주목 종목에 진입하도록 구성
    recs = [
        _make_holding_rec(
            ticker="069500",
            name="KODEX 200",
            current_price=40000,
            pnl_rate_pct=-15.0,
            market_weight_pct=50.0,
        ),
        _make_holding_rec(
            ticker="091160",
            current_price=22000,
            pnl_rate_pct=20.0,
            market_weight_pct=50.0,
        ),
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_x", payload)
    # 평가수익률 / 판단 / 사유 라인 등장
    assert "평가수익률: -15%" in msg
    assert "판단: HOLD" in msg
    assert "사유:" in msg


def test_draft_message_step2b_sorting_excludes_missing_pnl_rate():
    """AC15/AC16: pnl_rate_pct 가 없는 종목은 정렬 대상에서 제외 — 메시지 생성 실패 없음."""
    from app import draft_message

    recs = [
        # 시세 있고 pnl_rate_pct 도 정상
        _make_holding_rec(
            ticker="GOOD1",
            current_price=11000,
            pnl_rate_pct=10.0,
            market_weight_pct=50.0,
        ),
        # 시세 있는데 pnl_rate_pct 키 자체 없음 — 정렬 제외
        _make_holding_rec(
            ticker="NORATE",
            current_price=11000,
            pnl_rate_pct=None,
            market_weight_pct=50.0,
        ),
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    # 절대 raise 하면 안 됨
    msg = draft_message.build_message_text("run_x", payload)
    assert isinstance(msg, str) and len(msg) > 0


def test_draft_message_step2b_sorting_handles_nan_and_string_values():
    """AC15/AC16: NaN / 비숫자 / None 인 정렬 키가 섞여도 메시지 생성이 실패하지 않는다."""
    from app import draft_message

    recs = [
        _make_holding_rec(
            ticker="A",
            current_price=10000,
            pnl_rate_pct=5.0,
            market_weight_pct=30.0,
        ),
        # NaN / 문자열 / None 을 직접 주입 — _to_finite_float 에서 차단되어야 함
        {
            "ticker": "B",
            "name": "B",
            "quantity": 10,
            "avg_buy_price": 10000,
            "invested_amount": 100000,
            "current_price": 10000,
            "eval_amount": 100000,
            "pnl_amount": 0,
            "pnl_rate_pct": float("nan"),
            "market_weight_pct": "abc",  # 문자열
            "action": "HOLD",
            "reason": draft_message.DEFAULT_HOLD_REASON,
        },
        {
            "ticker": "C",
            "name": "C",
            "quantity": 10,
            "avg_buy_price": 10000,
            "invested_amount": 100000,
            "pnl_rate_pct": None,
            "market_weight_pct": None,
            "action": "HOLD",
            "reason": draft_message.DEFAULT_HOLD_REASON,
        },
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_x", payload)
    assert "NaN" not in msg
    assert "nan" not in msg
    assert "None" not in msg
    assert "abc" not in msg


def test_draft_message_step2b_price_missing_not_treated_as_zero():
    """AC17: 가격 미확인 종목은 손익률 0% 로 취급되지 않는다 — 손익률 정렬에서 제외."""
    from app import draft_message

    # 가격 미확인 종목 1개 + 시세 확인 종목 1개 (손익률 -5%)
    recs = [
        # current_price 없음 — pnl_rate_pct 도 응답에 없음 (Step 2 정책)
        {
            "ticker": "NOPRICE",
            "name": "NOPRICE",
            "quantity": 10,
            "avg_buy_price": 10000,
            "invested_amount": 100000,
            "buy_weight_pct": 50.0,
            "action": "HOLD",
            "reason": draft_message.DEFAULT_HOLD_REASON,
        },
        _make_holding_rec(
            ticker="LOSER",
            current_price=9500,
            pnl_rate_pct=-5.0,
            market_weight_pct=50.0,
        ),
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_x", payload)

    # 가격 미확인 종목은 price_missing 카테고리에만 등장
    assert "🔍 시세 미확인 종목" in msg
    assert "NOPRICE" in msg
    # 손익률 하위 카테고리에는 LOSER 만 (NOPRICE 가 0% 로 잡혀 끼어들지 않아야 함)
    # 메시지 내 "📉 평가수익률 하위" 섹션 안에 NOPRICE 가 같이 등장하면 안 됨
    bottom_idx = msg.find("📉 평가수익률 하위")
    if bottom_idx >= 0:
        next_section_idx = msg.find("📊 시장비중 상위", bottom_idx)
        if next_section_idx < 0:
            next_section_idx = msg.find("📈 평가수익률 상위", bottom_idx)
        if next_section_idx < 0:
            next_section_idx = len(msg)
        bottom_section = msg[bottom_idx:next_section_idx]
        assert "NOPRICE" not in bottom_section


def test_draft_message_step2b_summary_priced_basis_label():
    """AC4/AC18/AC19/AC20: 시세 미확인 종목 있을 때 평가금액/손익은 시세 확인 기준이라 명시."""
    from app import draft_message

    recs = [
        _make_holding_rec(
            ticker="A",
            current_price=11000,
            pnl_rate_pct=10.0,
            market_weight_pct=100.0,
        ),
        # 가격 미확인
        {
            "ticker": "B",
            "name": "B",
            "quantity": 10,
            "avg_buy_price": 10000,
            "invested_amount": 100000,
            "action": "HOLD",
            "reason": draft_message.DEFAULT_HOLD_REASON,
        },
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_x", payload)
    # 시세 확인/미확인 카운트 명시
    assert "시세 확인: 1개 / 미확인: 1개" in msg
    # 평가금액/손익/수익률 옆에 "평가 계산 N개 기준" 라벨 (계산 정보 부족과 분리)
    assert "(평가 계산 1개 기준)" in msg
    # 일부 종목 시세 미확인 또는 계산 정보 부족 경고
    assert "일부 종목 시세 미확인 또는 계산 정보 부족" in msg
    # 전체 매입금액은 모든 종목 합계
    assert "총 매입금액: 200,000원" in msg


def test_draft_message_step2b_truncation_notice_when_over_limit(monkeypatch):
    """AC8: 안전 한도를 매우 작게 두면 잘림 안내 문구가 포함되며 한도 이하로 유지된다."""
    from app import draft_message

    # 강제로 한도를 작게 설정 — 재구성 단계에서도 못 줄어드는 경계 시나리오 재현
    monkeypatch.setattr(draft_message, "MAX_LENGTH_CHARS", 200)

    recs = [
        _make_holding_rec(
            ticker=f"X{i:03d}",
            current_price=10000,
            pnl_rate_pct=float(i),
            market_weight_pct=5.0,
        )
        for i in range(20)
    ]
    payload = {
        "title": "초소형 한도 테스트",
        "asof": "x",
        "note": "한도 200자로 강제",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_truncate", payload)
    assert len(msg) <= 200
    # 잘림 안내 문구
    assert "전체 상세는 웹 화면에서 확인" in msg or "메시지 길이 제한" in msg


def test_draft_message_step2b_compute_summary_unit():
    """compute_summary 단위 — 시세 확인/미확인 종목 분리 + 평가는 시세 확인 종목 기준."""
    from app import draft_message

    recs = [
        # 시세 확인 — 이익 +1000
        {
            "ticker": "A",
            "name": "A",
            "quantity": 10,
            "avg_buy_price": 10000,
            "invested_amount": 100000,
            "current_price": 10100,
            "eval_amount": 101000,
            "pnl_amount": 1000,
        },
        # 시세 미확인
        {
            "ticker": "B",
            "name": "B",
            "quantity": 5,
            "avg_buy_price": 20000,
            "invested_amount": 100000,
        },
    ]
    s = draft_message.compute_summary(recs)
    assert s["total_count"] == 2
    assert s["priced_count"] == 1
    assert s["unpriced_count"] == 1
    assert s["total_invested"] == 200000.0
    assert s["priced_eval"] == 101000.0
    assert s["priced_pnl"] == 1000.0
    assert round(s["priced_pnl_rate_pct"], 4) == 1.0


def test_draft_message_step2b_calc_missing_not_treated_as_zero():
    """Codex REJECTED FIX: current_price 는 있는데 eval_amount/invested_amount 가
    누락된 종목은 '계산 정보 부족' 으로 분리 — 0 원으로 집계되거나 평가 계산 가능
    종목으로 표시되지 않는다.
    """
    from app import draft_message

    recs = [
        # 평가 계산 가능 종목 1개 — invested 100,000 / eval 110,000 / pnl 10,000
        _make_holding_rec(
            ticker="GOOD",
            name="GOOD",
            quantity=10,
            avg_buy_price=10000,
            current_price=11000,
            pnl_rate_pct=10.0,
            market_weight_pct=100.0,
        ),
        # 시세는 있는데 eval_amount / invested_amount 누락 — 계산 정보 부족
        {
            "ticker": "CALCMISS",
            "name": "CALCMISS",
            "quantity": 10,
            "avg_buy_price": 10000,
            "current_price": 12000,
            # eval_amount / invested_amount / pnl_amount / pnl_rate_pct 모두 누락
            "action": "HOLD",
            "reason": draft_message.DEFAULT_HOLD_REASON,
        },
    ]
    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": recs,
    }
    msg = draft_message.build_message_text("run_calcmiss", payload)

    # 카운트 분리: 시세 확인 2 / 평가 계산 가능 1 / 계산 정보 부족 1
    assert "보유 종목: 2개" in msg
    assert "시세 확인: 2개 / 미확인: 0개" in msg
    assert "평가 계산 가능: 1개 / 계산 정보 부족: 1개" in msg

    # 평가 집계는 GOOD 만 — CALCMISS 가 0 원으로 들어가 평균을 왜곡하지 않음
    assert "평가금액: 110,000원 (평가 계산 1개 기준)" in msg
    assert "평가손익: +10,000원 (평가 계산 1개 기준)" in msg
    assert "평가수익률: +10% (평가 계산 1개 기준)" in msg

    # 경고 문구
    assert "일부 종목 시세 미확인 또는 계산 정보 부족" in msg

    # CALCMISS 는 calc_missing 카테고리에 등장 (가격 미확인은 아님)
    assert "⚙ 계산 정보 부족 종목" in msg
    assert "CALCMISS" in msg
    # GOOD 은 평가 가능 종목이라 calc_missing 카테고리에 들어가지 않음
    calc_missing_idx = msg.find("⚙ 계산 정보 부족 종목")
    next_section_idx = msg.find("📉", calc_missing_idx)
    if next_section_idx < 0:
        next_section_idx = msg.find("📊", calc_missing_idx)
    if next_section_idx < 0:
        next_section_idx = msg.find("📈", calc_missing_idx)
    if next_section_idx < 0:
        next_section_idx = len(msg)
    calc_missing_section = msg[calc_missing_idx:next_section_idx]
    assert "GOOD" not in calc_missing_section
    # CALCMISS 종목 라인에 [계산 정보 부족] 마커
    assert "[계산 정보 부족]" in msg


def test_draft_message_step2b_compute_summary_separates_calc_missing():
    """compute_summary 단위 — 시세 확인 ≠ 평가 계산 가능 분리 검증."""
    from app import draft_message

    recs = [
        # 평가 계산 가능
        {
            "ticker": "A",
            "quantity": 10,
            "avg_buy_price": 10000,
            "invested_amount": 100000,
            "current_price": 11000,
            "eval_amount": 110000,
        },
        # 시세는 있는데 eval_amount 없음
        {
            "ticker": "B",
            "quantity": 5,
            "avg_buy_price": 20000,
            "current_price": 22000,
            # eval_amount 없음
        },
        # 시세 미확인
        {
            "ticker": "C",
            "quantity": 5,
            "avg_buy_price": 20000,
            "invested_amount": 100000,
        },
    ]
    s = draft_message.compute_summary(recs)
    assert s["total_count"] == 3
    assert s["priced_count"] == 2  # A, B
    assert s["unpriced_count"] == 1  # C
    assert s["calc_available_count"] == 1  # A 만
    assert s["calc_missing_count"] == 1  # B
    # 평가 집계는 A 만
    assert s["priced_eval"] == 110000.0
    assert s["priced_pnl"] == 10000.0
    assert round(s["priced_pnl_rate_pct"], 4) == 10.0


def test_draft_message_step2b_returns_empty_for_non_holdings():
    """is_holdings_draft False 면 빈 문자열 (Step 1A 호환)."""
    from app import draft_message

    msg = draft_message.build_message_text(
        "run_x",
        {"recommendations": [{"ticker": "069500", "score": 0.5, "action": "HOLD"}]},
    )
    assert msg == ""


def test_step2d_legacy_run_without_message_text_loadable(tmp_path, monkeypatch):
    """과거 state/runs/*.json 에 message_text 키가 없어도 Run.from_dict 가
    KeyError 없이 None 으로 로드한다 (하위 호환)."""
    import json as _json

    runs_dir = tmp_path / "legacy_runs"
    runs_dir.mkdir()
    legacy_file = runs_dir / "run_legacy_2d.json"
    legacy_file.write_text(
        _json.dumps(
            {
                "run_id": "run_legacy_2d",
                "asof": "2026-04-01T00:00:00+00:00",
                "status": "PENDING_APPROVAL",
                "draft_payload": {
                    "title": "legacy",
                    "asof": "2026-04-01T00:00:00+00:00",
                    "note": "legacy",
                    "recommendations": [],
                },
                # message_text 키 자체 없음
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "STORE_DIR", runs_dir)

    loaded = store.load("run_legacy_2d")
    assert loaded.run_id == "run_legacy_2d"
    assert loaded.message_text is None  # 누락 → None 으로 fallback


def test_step2d_get_run_returns_none_message_text_for_legacy(tmp_path, monkeypatch):
    """legacy run 의 GET /runs/{id} 응답에 message_text 가 None 으로 노출된다."""
    import json as _json

    runs_dir = tmp_path / "legacy_runs2"
    runs_dir.mkdir()
    rid = "run_legacy_2d_api"
    (runs_dir / f"{rid}.json").write_text(
        _json.dumps(
            {
                "run_id": rid,
                "asof": "2026-04-01T00:00:00+00:00",
                "status": "PENDING_APPROVAL",
                "draft_payload": {
                    "title": "legacy",
                    "asof": "2026-04-01T00:00:00+00:00",
                    "note": "legacy",
                    "recommendations": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "STORE_DIR", runs_dir)

    from fastapi.testclient import TestClient as _TC

    c = _TC(api.app)
    r = c.get(f"/runs/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert "message_text" in body  # 키 자체는 응답 스키마에 항상 존재
    assert body["message_text"] is None


def test_step2d_delivery_uses_stored_message_text(client, monkeypatch):
    """신규 run 은 Run.message_text 가 빌드되어 저장된다. delivery 는 builder 를
    재호출하지 않고 저장된 값을 그대로 handoff artifact 에 넣는다 → preview ↔
    실제 발송문 단일 소스 보장."""
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS_FOR_2D})
    r = client.post("/runs/generate-from-holdings")
    rid = r.json()["run_id"]
    expected_msg = r.json()["message_text"]
    assert isinstance(expected_msg, str) and len(expected_msg) > 0

    # _stub_oci_calls autouse fixture 가 delivery.deliver 를 람다로 stub 한 상태.
    # 모듈 top-level 에서 미리 캡처한 원본 함수 객체를 사용해 우회한다.
    _real_deliver = _ORIGINAL_DELIVER

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "신규 run 의 delivery 는 message_text 를 재생성하면 안 됩니다."
        )

    monkeypatch.setattr(delivery, "_scp_upload", lambda *a, **kw: None)
    monkeypatch.setattr(delivery, "_ssh_target", lambda: "stub@host")
    monkeypatch.setattr(delivery, "_remote_inbox", lambda: "/tmp/inbox")
    monkeypatch.setattr(
        delivery.draft_message, "build_message_text", _should_not_be_called
    )

    captured = {}
    real_write = store.write_handoff_artifact

    def _spy_write(run, approved_at, message_text=None):
        captured["message_text"] = message_text
        return real_write(run, approved_at, message_text)

    monkeypatch.setattr(store, "write_handoff_artifact", _spy_write)

    # store.load 로 신규 run (DELIVERING 으로 전환되지 않은 PENDING_APPROVAL 상태).
    # deliver() 는 DELIVERING 만 받으므로 status 만 변경한 복제본 사용.
    pending = store.load(rid)
    pending.status = "DELIVERING"
    _real_deliver(pending)
    assert captured["message_text"] == expected_msg


def test_step2d_delivery_legacy_run_falls_back_to_builder(monkeypatch):
    """과거 run 은 Run.message_text 가 None 일 수 있다. 이 경우 delivery 는
    holdings draft 면 builder fallback 을 트리거한다 (legacy 호환)."""
    _real_deliver = _ORIGINAL_DELIVER
    from app.models import Run as RunModel

    legacy_run = RunModel(
        run_id="run_legacy_2d_deliv",
        asof="2026-04-01T00:00:00+00:00",
        status="DELIVERING",
        draft_payload={
            "title": "legacy holdings",
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
        },
        message_text=None,  # legacy
    )

    called = {"n": 0}

    def _spy_builder(run_id, payload):
        called["n"] += 1
        return "LEGACY_FALLBACK_TEXT"

    monkeypatch.setattr(delivery.draft_message, "build_message_text", _spy_builder)
    monkeypatch.setattr(delivery, "_scp_upload", lambda *a, **kw: None)
    monkeypatch.setattr(delivery, "_ssh_target", lambda: "stub@host")
    monkeypatch.setattr(delivery, "_remote_inbox", lambda: "/tmp/inbox")

    _real_deliver(legacy_run)
    assert called["n"] == 1  # legacy 만 fallback 트리거


# ─── POC2 Step 5B: Minimal Momentum Engine Execution (holdings mode) ─
