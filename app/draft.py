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

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app import draft_message, sample_draft, store
from app.factors import build_factor_signals
from app.holdings import HOLDINGS_FILE, Holding
from app.holdings_enrich import enrich_holdings, to_recommendation_dict
from app.holdings_market_evidence import (
    build_holdings_market_evidence,
    get_holdings_file_mtime_iso,
)
from app.market_cache import MarketQuote
from app.market_data_store import DEFAULT_DB_PATH as MARKET_DB_PATH
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER, compute_topn
from app.message_holdings_market_evidence_bullet import (
    build_holdings_market_evidence_factor_signal,
)
from app.ml_baseline_evidence import (
    build_ml_baseline_evidence_factor_signal,
    build_ml_baseline_evidence_snapshot,
)
from app.models import Run
from app.momentum import LATEST_ARTIFACT_FILE as UNIVERSE_LATEST_FILE
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

    # POC2 Step 6 (Fix 라운드 2026-05-11): universe_momentum_latest.json 의 top_candidate 를
    # [판단 사유] 의 "외부 후보 점검" bullet 로 병합하되, draft_payload 키를 신설하지 않고
    # 기존 factor_signals 안에 scope="universe" signal 1건으로 추가한다 (사용자 결정).
    # GenerateDraft 는 pykrx 를 직접 호출하지 않고 이미 저장된 latest artifact 만 읽는다
    # (AC-20). artifact 부재 시 signal 자체를 추가하지 않는다 — pre-refresh 상태에서는
    # [판단 사유] 에 universe bullet 미표시.
    universe_signal = _build_universe_factor_signal(asof_iso=asof_iso)
    if universe_signal is not None:
        factor_signals = list(factor_signals) + [universe_signal]

    # POC2 Step 7C (2026-05-12): universe_momentum_latest.json 의 falling_candidate 를
    # [판단 사유] 의 "급락 ETF 주의 신호" bullet 로 병합. PUSH 2 와 동일하게 새로운
    # factor_signal entry 1건 (scope="universe_falling") 추가 — draft_payload 키 신설 없음.
    # falling_candidate 가 None 이면 signal 자체를 추가하지 않는다 — 신호 없음 시 Telegram
    # 에 "신호 없음" 문구도 추가되지 않게 한다 (KS-5 알림 과다 방지).
    falling_signal = _build_falling_etf_factor_signal(asof_iso=asof_iso)
    if falling_signal is not None:
        factor_signals = list(factor_signals) + [falling_signal]

    # POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) —
    # GET /holdings/market-evidence/latest 와 동일한 builder 를 재사용 (지시문 §5.10).
    # 외부 fetch X (compute_topn 은 SQLite read only). 결과는:
    #  · draft_payload.holdings_market_evidence_snapshot 신규 키 — snapshot 저장.
    #  · factor_signals 에 scope="holdings_market_evidence" signal 1건 — [판단 사유] 1줄.
    # holdings 비어있는 흐름은 본 함수에 도달 전 차단되어 있어 빈 응답 보호 불필요.
    market_evidence_snapshot = build_holdings_market_evidence(
        holdings=holdings,
        topn_payload=compute_topn(
            n=DEFAULT_N,
            db_path=MARKET_DB_PATH,
            basis=DEFAULT_BASIS,
            order=DEFAULT_ORDER,
        ),
        market_quotes=quotes,
        db_path=MARKET_DB_PATH,
        holdings_asof=get_holdings_file_mtime_iso(HOLDINGS_FILE),
    )
    holdings_market_evidence_signal = build_holdings_market_evidence_factor_signal(
        market_evidence_snapshot, asof_iso=asof_iso
    )
    if holdings_market_evidence_signal is not None:
        factor_signals = list(factor_signals) + [holdings_market_evidence_signal]

    # POC2 — ML Baseline Evidence Draft Integration (2026-06-11). 저장된
    # ML baseline v0 룩백 report 를 보조 evidence 로 읽어 draft 에 연결.
    # 재계산 / feature 재생성 / 외부 호출 / ML 학습 0건 (지시문 §4.1).
    # report 부재 / 손상 / stale 도 draft 생성을 실패시키지 않는다 (지시문 §4.7).
    ml_baseline_evidence_snapshot = build_ml_baseline_evidence_snapshot()
    ml_baseline_evidence_signal = build_ml_baseline_evidence_factor_signal(
        ml_baseline_evidence_snapshot, asof_iso=asof_iso
    )
    if ml_baseline_evidence_signal is not None:
        factor_signals = list(factor_signals) + [ml_baseline_evidence_signal]

    return {
        "title": f"보유 종목 기반 초안 ({asof_date})",
        "asof": asof_iso,
        "note": note,
        "recommendations": recommendations,
        "factor_signals": factor_signals,
        "momentum_result": momentum_result,
        # 저장 시점 evidence snapshot — 이후 시장 데이터가 바뀌어도 본 키의 의미가
        # 변하지 않는다 (지시문 §5.11 / AC-9).
        "holdings_market_evidence_snapshot": market_evidence_snapshot,
        # ML baseline 룩백 evidence snapshot — 본 draft 가 어떤 baseline 근거로
        # 생성되었는지 추적 가능 (지시문 §4.2).
        "ml_baseline_evidence_snapshot": ml_baseline_evidence_snapshot,
    }


def _load_universe_latest_artifact() -> Optional[dict[str, Any]]:
    """state/universe/universe_momentum_latest.json 을 읽어 raw dict 를 반환.

    파일 부재 / JSON 파싱 실패 / 비-dict 응답 모두 None 반환 (안전 격리).
    Step5C 시점 결과 (refresh_status 키 없음) 도 None 반환 — Step6 외부 후보 점검 대상 외.
    """
    if not UNIVERSE_LATEST_FILE.exists():
        return None
    try:
        text = UNIVERSE_LATEST_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"universe latest artifact 읽기 실패: {e}")
        return None
    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return None
    refresh_status = summary.get("refresh_status")
    if refresh_status not in ("ok", "partial", "failed"):
        return None
    return data


def _build_universe_factor_signal(asof_iso: str) -> Optional[dict[str, Any]]:
    """universe_momentum_latest.json → factor_signals 리스트에 추가할 signal 1건.

    포맷 (기존 portfolio factor signal 과 동일한 구조):
    {
      "factor_id": "universe_one_month_return",
      "factor_name": "신규 ETF 관찰 후보",  # Step7A 정렬: 사용자 노출 공식 PUSH 2 명칭
      "scope": "universe",
      "is_available": True | False,
      "value": float | None,        # top_candidate.score_result.score_value (성공)
      "unit": "%",
      "reason_text": <성공 시 1줄> | None,
      "fallback_text": <실패 시 1줄> | None,
      "input_basis": {              # universe asof / 기준일 / scored / total
        "asof": str,
        "basis_date": str,
        "scored": int,
        "total": int,
        "refresh_status": str,
      },
      "computed_at": <iso>,
    }

    refresh_status:
    - "ok" / "partial" + top_candidate 존재 → is_available=True, reason_text 채움.
    - "failed" 또는 top_candidate 부재 → is_available=False, fallback_text 채움.
    artifact 부재 / 형식 오류 → None 반환 (signal 미추가).
    """
    from app.message_universe_bullet import build_universe_signal_texts

    data = _load_universe_latest_artifact()
    if data is None:
        return None
    summary = data["summary"]
    asof = data.get("asof") or ""
    refresh_status = summary.get("refresh_status")
    top = (
        summary.get("top_candidate")
        if isinstance(summary.get("top_candidate"), dict)
        else None
    )

    # 기준일 결정 (Step6 §13 우선순위).
    basis_date = "기준일 확인 불가"
    if top is not None:
        phb = top.get("price_history_basis")
        if isinstance(phb, dict):
            ld = phb.get("latest_date")
            if isinstance(ld, str) and ld.strip():
                basis_date = ld
    if basis_date == "기준일 확인 불가" and isinstance(asof, str) and asof.strip():
        basis_date = asof

    scored = int(summary.get("scored_candidates") or 0)
    total = int(summary.get("total_candidates") or 0)

    reason_text, fallback_text, value = build_universe_signal_texts(
        refresh_status=refresh_status,
        top_candidate=top,
        scored=scored,
        total=total,
        basis_date=basis_date,
    )

    is_available = reason_text is not None
    return {
        "factor_id": "universe_one_month_return",
        "factor_name": "신규 ETF 관찰 후보",
        "scope": "universe",
        "is_available": is_available,
        "value": value,
        "unit": "%",
        "reason_text": reason_text,
        "fallback_text": fallback_text,
        "input_basis": {
            "asof": asof,
            "basis_date": basis_date,
            "scored": scored,
            "total": total,
            "refresh_status": refresh_status,
        },
        "computed_at": asof_iso,
    }


def _build_falling_etf_factor_signal(asof_iso: str) -> Optional[dict[str, Any]]:
    """Step 7C — universe_momentum_latest.json 의 falling_candidate → factor signal 1건.

    포맷 (기존 universe scope signal 과 동일한 구조 — scope 값만 다름):
    {
      "factor_id": "universe_falling_one_month_return",
      "factor_name": "급락 ETF 주의 신호",
      "scope": "universe_falling",
      "is_available": True | False,
      "value": float | None,             # falling_candidate.score_result.score_value
      "unit": "%",
      "reason_text": <성공 시 1줄> | None,
      "fallback_text": None,             # 본 signal 은 없음 시 entry 자체 미추가
      "input_basis": {
        "asof": str,
        "basis_date": str,
        "threshold_pct": float,
        "ticker": str,
        "candidate_id": str,
      },
      "computed_at": <iso>,
    }

    artifact 부재 / falling_candidate=None / 형식 오류 → None 반환 (signal 미추가).
    이는 [판단 사유] 에 "급락 ETF 주의 신호" bullet 가 생성되지 않게 한다 — KS-5 알림
    과다 방지 (지시문 §3.4).
    """
    from app.message_falling_etf_bullet import build_falling_etf_signal_text

    data = _load_universe_latest_artifact()
    if data is None:
        return None
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return None
    falling = summary.get("falling_candidate")
    if not isinstance(falling, dict):
        return None  # falling_candidate None → signal 미추가
    threshold_pct = summary.get("falling_threshold_pct")
    if not isinstance(threshold_pct, (int, float)):
        return None
    asof = data.get("asof") or ""

    # 기준일 결정 (Step6 §13 우선순위 + Step7C 동일).
    basis_date = "기준일 확인 불가"
    phb = falling.get("price_history_basis")
    if isinstance(phb, dict):
        ld = phb.get("latest_date")
        if isinstance(ld, str) and ld.strip():
            basis_date = ld
    if basis_date == "기준일 확인 불가" and isinstance(asof, str) and asof.strip():
        basis_date = asof

    score_result = falling.get("score_result") or {}
    score_value = score_result.get("score_value")
    if not isinstance(score_value, (int, float)):
        return None
    name = falling.get("name") or falling.get("ticker") or "(이름 미상)"

    reason_text = build_falling_etf_signal_text(
        name=name,
        score_value=float(score_value),
        threshold_pct=float(threshold_pct),
        basis_date=basis_date,
    )

    return {
        "factor_id": "universe_falling_one_month_return",
        "factor_name": "급락 ETF 주의 신호",
        "scope": "universe_falling",
        "is_available": True,
        "value": float(score_value),
        "unit": "%",
        "reason_text": reason_text,
        "fallback_text": None,
        "input_basis": {
            "asof": asof,
            "basis_date": basis_date,
            "threshold_pct": float(threshold_pct),
            "ticker": falling.get("ticker") or "",
            "candidate_id": falling.get("candidate_id") or "",
        },
        "computed_at": asof_iso,
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
