"""초안(draft) 생성.

성공: status=PENDING_APPROVAL, draft_payload=dict
실패: status=FAILED, draft_payload=None

같은 날 재시도도 허용되지만 반드시 새 run_id 를 발급한다.
draft_payload 는 화면에서도 보고 외부 전달 body 로도 사용되는 단일 본문이다.

테스트 시나리오(draft 생성 실패, 외부 전달 실패) 는 payload 내부 플래그로
표현하지 않는다. 테스트는 이 모듈의 함수를 monkeypatch 하여 실패를 주입한다.
운영 payload 에는 테스트 제어 메타데이터가 절대 섞이지 않는다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app import draft_message, sample_draft, store
from app.factors import build_factor_signals
from app.holdings import Holding
from app.holdings_enrich import enrich_holdings, to_recommendation_dict
from app.market_cache import MarketQuote
from app.models import Run
from app.momentum import build_holdings_momentum_result

logger = logging.getLogger(__name__)


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run_{stamp}_{uuid4().hex[:8]}"


def generate_draft(input_data: dict[str, Any]) -> Run:
    """샘플 초안 생성 엔트리 (개발/테스트용 — 운영 입력 아님).

    POC2 Step 1 부터는 운영 흐름이 generate_draft_from_holdings() 로 바뀌었다.
    이 함수는 샘플 입력 폼(접힘 섹션)에서만 사용된다.

    계약 불만족(빈 dict 포함, 필수 키 누락) 시 SampleDraftInputError 가
    발생하며 이 함수는 status=FAILED, draft_payload=None 인 Run 을 저장하고
    반환한다. "GenerateDraft 실패 → FAILED 단일 규칙" (POC1) 유지.
    """
    run_id = _new_run_id()
    asof = datetime.now(timezone.utc).isoformat()

    try:
        payload = sample_draft.build_sample_payload(input_data)
        # Step 2D: 생성 시점에 message_text 를 미리 빌드해 Run 에 저장.
        # 비-holdings(샘플) payload 는 build_message_text 가 빈 문자열을 돌려주며
        # 그 경우 Run.message_text 는 None 으로 둔다 (UI 가 정적 fallback 표시).
        msg = draft_message.build_message_text(run_id, payload)
        run = Run(
            run_id=run_id,
            asof=asof,
            status="PENDING_APPROVAL",
            draft_payload=payload,
            message_text=msg if msg else None,
        )
    except sample_draft.SampleDraftInputError as e:
        logger.error(f"draft 생성 실패 run_id={run_id}: {e}")
        run = Run(
            run_id=run_id,
            asof=asof,
            status="FAILED",
            draft_payload=None,
        )

    store.save(run)
    return run


def _build_holdings_payload(
    holdings: list[Holding],
    market_quotes: dict[str, MarketQuote] | None = None,
) -> dict[str, Any]:
    """holdings 기반 draft_payload 빌더 (POC2 Step 1 + Step 2 enrich 호환).

    설계자 결정:
    - title / asof / note / recommendations 4 키 유지 (기존 계약과 호환)
    - score 필드 만들지 않음
    - action 은 모두 'HOLD' (이번 단계 추천 로직 확장 금지)
    - market_quotes=None 또는 빈 dict 면 Step 1 호환 동작 (시세 필드 없음)
    - market_quotes 가 주어지면 holdings_enrich 가 시세/평가/손익/시장비중 추가
    - 시세 fetch 는 절대 트리거하지 않는다. 호출자가 캐시에서 미리 조회해 넘긴다.
    """
    asof_dt = datetime.now(timezone.utc)
    asof_iso = asof_dt.isoformat()
    asof_date = asof_dt.strftime("%Y-%m-%d")

    quotes = market_quotes or {}
    enriched = enrich_holdings(holdings, quotes)
    recommendations: list[dict[str, Any]] = [
        to_recommendation_dict(item) for item in enriched
    ]

    note = (
        f"holdings 항목 {len(holdings)}건 기준 자동 생성. "
        "이번 단계는 보유 현황 기반 초안이며 추천 판단(매수/매도 등)은 포함하지 않습니다."
    )

    # POC2 Step 3: 첫 factor signal 통합. 설계자 명시 승인 — Step3 한정으로
    # draft_payload 5번째 키 factor_signals 를 추가한다 (Run top-level 확장은 안 함).
    # 다른 draft_payload 메타 flag 추가나 일반 확장 허용으로 해석 금지.
    factor_signals = build_factor_signals(enriched)

    # POC2 Step 5B: Momentum Engine holdings mode placeholder 산식 1회 실행.
    # 설계자 명시 승인 — Step5B 한정으로 draft_payload 6번째 키 momentum_result 를
    # 추가한다 (Run top-level 확장 / 별도 artifact / DB 모두 도입 안 함).
    # placeholder 산식(pnl_rate) 은 최종 투자 판단 산식이 아니다.
    momentum_result = build_holdings_momentum_result(enriched, asof=asof_iso)

    return {
        "title": f"보유 종목 기반 초안 ({asof_date})",
        "asof": asof_iso,
        "note": note,
        "recommendations": recommendations,
        "factor_signals": factor_signals,
        "momentum_result": momentum_result,
    }


def generate_draft_from_holdings(
    holdings: list[Holding],
    market_quotes: dict[str, MarketQuote] | None = None,
) -> Run:
    """holdings 리스트로 PENDING_APPROVAL run 생성 (POC2 Step 1 운영 진입점).

    POC2 Step 2 부터 market_quotes 를 외부에서 주입받을 수 있다 (옵셔널).
    - 입력 검증은 호출 전 단계(api 레이어)에서 끝나야 한다.
    - 빈 리스트는 호출자가 미리 차단해야 한다 (이 함수는 받지 않는다).
    - market_quotes 미주입 = 시세 없는 Step 1 호환 동작.
    - 기존 store.save 를 그대로 사용 → 기존 승인 루프와 동일하게 흐른다.
    - 이 함수는 절대 외부 fetch 를 트리거하지 않는다 (호출자 책임).
    """
    if not holdings:
        # 호출자가 차단했어야 함. 도달 시 명시 에러.
        raise ValueError(
            "generate_draft_from_holdings: 빈 holdings 는 호출 전 차단되어야 합니다."
        )

    run_id = _new_run_id()
    asof = datetime.now(timezone.utc).isoformat()
    payload = _build_holdings_payload(holdings, market_quotes=market_quotes)
    # Step 2D: 생성 시점에 message_text 를 미리 빌드해 Run 에 저장.
    # 같은 문자열을 GET /runs/{id} 응답(preview), Telegram 발송, OCI handoff
    # 모두에서 재사용한다 → preview ↔ 실제 발송문 단일 소스 보장.
    msg = draft_message.build_message_text(run_id, payload)
    run = Run(
        run_id=run_id,
        asof=asof,
        status="PENDING_APPROVAL",
        draft_payload=payload,
        message_text=msg if msg else None,
    )
    store.save(run)
    return run
