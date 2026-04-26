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

from app import sample_draft, store
from app.holdings import Holding
from app.models import Run

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
        run = Run(
            run_id=run_id,
            asof=asof,
            status="PENDING_APPROVAL",
            draft_payload=payload,
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


def _build_holdings_payload(holdings: list[Holding]) -> dict[str, Any]:
    """holdings 기반 draft_payload 빌더 (POC2 Step 1).

    설계자 결정:
    - title / asof / note / recommendations 4 키 유지 (기존 계약과 호환)
    - recommendations 항목 필드: ticker / name / quantity / avg_buy_price /
      invested_amount / buy_weight_pct / action / reason
    - score 필드 만들지 않음
    - action 은 모두 'HOLD' (이번 단계 추천 로직 확장 금지)
    - 매입금액(invested_amount) = quantity * avg_buy_price
    - 매입금액 기준 비중(buy_weight_pct) = invested_amount / sum(invested_amount) * 100
    """
    asof_dt = datetime.now(timezone.utc)
    asof_iso = asof_dt.isoformat()
    asof_date = asof_dt.strftime("%Y-%m-%d")

    invested_list = [h.invested_amount() for h in holdings]
    total_invested = sum(invested_list)

    recommendations: list[dict[str, Any]] = []
    for h, invested in zip(holdings, invested_list):
        weight_pct = (
            round(invested / total_invested * 100.0, 2) if total_invested > 0 else 0.0
        )
        recommendations.append(
            {
                "ticker": h.ticker,
                "name": h.display_name(),
                "quantity": h.quantity,
                "avg_buy_price": h.avg_buy_price,
                "invested_amount": round(invested, 2),
                "buy_weight_pct": weight_pct,
                "action": "HOLD",
                "reason": "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)",
            }
        )

    return {
        "title": f"보유 종목 기반 초안 ({asof_date})",
        "asof": asof_iso,
        "note": (
            f"holdings 항목 {len(holdings)}건 기준 자동 생성. "
            "이번 단계는 보유 현황 기반 초안이며 추천 판단(매수/매도 등)은 포함하지 않습니다."
        ),
        "recommendations": recommendations,
    }


def generate_draft_from_holdings(holdings: list[Holding]) -> Run:
    """holdings 리스트로 PENDING_APPROVAL run 생성 (POC2 Step 1 운영 진입점).

    - 입력 검증은 호출 전 단계(api 레이어)에서 끝나야 한다.
    - 빈 리스트는 호출자가 미리 차단해야 한다 (이 함수는 받지 않는다).
    - 기존 store.save 를 그대로 사용 → 기존 승인 루프와 동일하게 흐른다.
    """
    if not holdings:
        # 호출자가 차단했어야 함. 도달 시 명시 에러.
        raise ValueError(
            "generate_draft_from_holdings: 빈 holdings 는 호출 전 차단되어야 합니다."
        )

    run_id = _new_run_id()
    asof = datetime.now(timezone.utc).isoformat()
    payload = _build_holdings_payload(holdings)
    run = Run(
        run_id=run_id,
        asof=asof,
        status="PENDING_APPROVAL",
        draft_payload=payload,
    )
    store.save(run)
    return run
