"""POC 1단계 FastAPI (Step 3 OCI 실연결 구조).

엔드포인트:
- POST /runs/generate        : 새 run_id 로 초안 생성
- GET  /runs                 : 모든 run 조회
- GET  /runs/{run_id}        : 단일 run 조회 + DELIVERING 인 경우
                               OCI outbox 1회 reconciliation 시도
- POST /runs/{run_id}/reject : PENDING_APPROVAL -> REJECTED
- POST /runs/{run_id}/approve: PENDING_APPROVAL -> DELIVERING 즉시 진입 후
                               BackgroundTasks 가 SCP 로 OCI inbox 에 큐잉

상태 결정 책임 분리:
- _execute_delivery (BackgroundTasks):
  · SCP 성공 → status 그대로 DELIVERING 유지 (큐잉만 완료)
  · SCP 실패 / DeliveryConfigError → FAILED 즉시 종결
- _try_reconcile_with_oci_outbox (GET /runs/{run_id} 시점):
  · OCI consumer (poc1_consume_inbox.sh) 가 outbox 에 쓴 결과 파일을
    SSH cat 으로 1회 조회. status 가 COMPLETED / FAILED 이면 store 갱신
  · DeliveryConfigError → FAILED 마킹 (DELIVERING 영구 고정 차단)

즉 동기 응답으로 COMPLETED 까지 가지 않는다. 최종 상태는 OCI 측 처리 +
프론트의 느린 polling(12s) 또는 수동 새로고침을 통해 도달한다.
APPROVED 상태는 존재하지 않는다.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# `app.config` import 자체가 .env 자동 로드를 트리거한다.
# 환경변수에 의존하는 어떤 모듈보다 먼저 import 되어야 한다.
from app import config  # noqa: F401  # side-effect import (load_dotenv)
from app import (
    delivery,
    draft,
    holdings as holdings_module,
    holdings_enrich,
    market_cache,
    market_naver,
    store,
)
from app.api_decision_sessions import router as decision_sessions_router
from app.api_etf_constituents import router as etf_constituents_router
from app.api_holdings_market_evidence import router as holdings_market_evidence_router
from app.api_market_topn import router as market_topn_router
from app.api_ml_baseline import router as ml_baseline_router
from app.api_ml_jobs import router as ml_jobs_router
from app.api_ml_relative_upside import router as ml_relative_upside_router
from app.api_ml_readiness import router as ml_readiness_router
from app.api_ml_sanity import router as ml_sanity_router
from app.api_nav_discount import router as nav_discount_router
from app.api_three_push_param import router as three_push_param_router
from app.api_universe import router as universe_router
from app.holdings import HoldingsValidationError
from app.models import Run
from app.state import InvalidTransition, validate_transition

logger = logging.getLogger(__name__)

app = FastAPI(title="POC 1단계 승인 루프")

# Next.js dev(3000) 프론트에서 직접 호출 허용.
# Next.js API Routes/Proxy 를 거치지 않고 프론트 ↔ FastAPI 분리 연결이
# 이번 단계의 확정 설계. 운영 배포 시 origin 화이트리스트 재정의 대상.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    # POC2 Step 1: PUT /holdings 추가됨. preflight OPTIONS 통과 위해 PUT 허용.
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

# POC2 Step 6 — universe momentum 엔드포인트는 별도 라우터로 분리 (app.api_universe).
# KS-10 근접 해소 + 1개 책임 1개 파일.
app.include_router(universe_router)
app.include_router(market_topn_router)
app.include_router(decision_sessions_router)
app.include_router(etf_constituents_router)
# POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) —
# read-only GET /holdings/market-evidence/latest. 외부 fetch X, 신규 저장 X.
app.include_router(holdings_market_evidence_router)
# POC2 NAV / Discount Display FIX (2026-06-08) —
# read-only GET /market/nav-discount/latest. 저장된 etf_nav_daily 만 read.
app.include_router(nav_discount_router)
# POC2 ML 최소 데이터 레인 (2026-06-08) —
# read-only GET /ml/readiness/latest. etf_ml_feature_daily / market_risk_feature_daily
# row 수 + latest asof 만 read. 외부 source 호출 X.
app.include_router(ml_readiness_router)
# POC2 ML Feature Sanity Check (2026-06-08) — read-only
# GET /ml/feature-sanity/latest. state/ml/ml_feature_sanity_latest.json 만 read.
app.include_router(ml_sanity_router)
# POC2 ML Baseline v0 룩백 검증 (2026-06-11) — read-only
# GET /ml/baseline-v0/latest. state/ml/ml_baseline_v0_report_latest.json 만 read.
app.include_router(ml_baseline_router)
# POC2 UI 안전실행 (2026-06-11) — POST /ml/jobs/evidence-refresh + GET /ml/jobs/latest.
# 3단계 (feature → sanity → baseline) background job runner + read-only status.
app.include_router(ml_jobs_router)
# POC2 ML 축1 — 상대상승 참고점수 실행 UI 연결 (2026-06-21):
# POST /market/relative-upside/run — 사용자가 CLI 없이 화면에서 점수 계산.
# 기존 GET /market/topn/latest 후보 응답 구조 유지. 새 모델 / 새 feature 0건.
app.include_router(ml_relative_upside_router)
# POC2 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 (2026-06-20, Phase B):
# GET /three-push/param/state + POST /three-push/param/apply — CLI 없이 UI 한
# 번으로 현재 운영 기준을 OCI 에 적용. 신규 DB / scheduler 0건.
app.include_router(three_push_param_router)
# POC2 3-PUSH Message Contract 정렬 (2026-06-12, FIX r2 — 설계자 수용):
# 신규 PUSH endpoint 신설 금지선 (§3 / §11) 준수.
# PUSH-1 / PUSH-3 은 기존 POST /runs/generate 의 input_data.push_kind 분기로 통합.
# PUSH-2 (holdings_briefing) 는 기존 POST /runs/generate-from-holdings 재정의.


class GenerateDraftRequest(BaseModel):
    # input_data 는 필수 dict. 빈 dict 또는 sample_draft 필수 키 누락은
    # draft 레이어에서 SampleDraftInputError → FAILED run 으로 귀결된다.
    # 즉 "실패 → FAILED 단일 규칙" 이며 이 단계에서 400 으로 거절하지 않는다.
    input_data: dict[str, Any] = Field(
        ...,
        description=(
            "draft 생성 입력. 필수 dict. 빈 dict / 필수 키 누락 시 FAILED run 으로 저장"
        ),
    )


class RunResponse(BaseModel):
    run_id: str
    asof: str
    status: str
    draft_payload: Optional[dict[str, Any]] = None
    # POC2 Step 2D: 신규 run 은 generate 시점에 백엔드가 빌드한 message_text 를
    # 응답에 그대로 포함한다. 과거 run 은 None.
    # 프론트엔드는 이 값을 opaque string 으로 받아 그대로 렌더링한다 (조립 금지).
    message_text: Optional[str] = None
    # POC2 3-PUSH Message Contract 정렬 (2026-06-11) — 3종 PUSH 구분 식별자.
    # 과거 run 은 None. delivery / OCI consumer 는 본 필드를 읽지 않는다.
    push_kind: Optional[str] = None

    @classmethod
    def from_run(cls, run: Run) -> "RunResponse":
        return cls(
            run_id=run.run_id,
            asof=run.asof,
            status=run.status,
            draft_payload=run.draft_payload,
            message_text=run.message_text,
            push_kind=run.push_kind,
        )


@app.post("/runs/generate", response_model=RunResponse)
def post_generate(req: GenerateDraftRequest) -> RunResponse:
    # 원 지시(POC1): GenerateDraft 실패 → FAILED 단일 규칙.
    # 빈 dict / 필수 키 누락 등 모든 draft 생성 실패는 draft.generate_draft
    # 내부에서 FAILED run 으로 저장되며 200 응답으로 돌려준다.
    # POC2 Step 1 부터 이 엔드포인트는 샘플 입력(개발/테스트용) 전용.
    # 운영 흐름은 POST /runs/generate-from-holdings 사용.
    run = draft.generate_draft(req.input_data)
    return RunResponse.from_run(run)


# ─── POC2 Step 1: holdings ─────────────────────────────────────────────


class HoldingItem(BaseModel):
    ticker: str
    quantity: float
    avg_buy_price: float
    name: Optional[str] = None
    # POC2 Step 2C: 표시/그룹용 라벨. 누락/빈 값은 백엔드에서 "일반" 으로 정규화.
    account_group: Optional[str] = None


class HoldingsPayload(BaseModel):
    holdings: list[HoldingItem]


@app.get("/holdings", response_model=HoldingsPayload)
def get_holdings() -> HoldingsPayload:
    """저장된 holdings 조회. 파일 없으면 빈 리스트 반환."""
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        # 저장된 파일이 손상된 경우. 사용자에게 명시적으로 알림.
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
    return HoldingsPayload(
        holdings=[
            HoldingItem(
                ticker=h.ticker,
                quantity=h.quantity,
                avg_buy_price=h.avg_buy_price,
                name=h.name,
                account_group=h.account_group,
            )
            for h in loaded
        ]
    )


@app.put("/holdings", response_model=HoldingsPayload)
def put_holdings(payload: HoldingsPayload) -> HoldingsPayload:
    """holdings 저장. 검증 실패 시 422 (run 생성 안 함).

    POC2 Step 1 E항: 단순 입력 오류로 run_id 를 만들거나 FAILED run 을
    저장하지 않는다. validation error 는 422 로 즉시 반환.
    """
    raw = [item.model_dump() for item in payload.holdings]
    try:
        validated = holdings_module.validate_holdings(raw)
    except HoldingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    holdings_module.save(validated)
    return HoldingsPayload(
        holdings=[
            HoldingItem(
                ticker=h.ticker,
                quantity=h.quantity,
                avg_buy_price=h.avg_buy_price,
                name=h.name,
                account_group=h.account_group,
            )
            for h in validated
        ]
    )


@app.post("/runs/generate-from-holdings", response_model=RunResponse)
def post_generate_from_holdings() -> RunResponse:
    """저장된 holdings 기반 draft 생성 (POC2 Step 1 운영 진입점).

    holdings 가 비어있거나 손상되면 422 — run 생성 차단 (FAILED run 만들지 않음).
    이후는 기존 승인 루프(PENDING_APPROVAL / Approve / Reject) 가 동일하게 처리.

    POC2 Step 2: 시장데이터 캐시(market_cache)를 조회해 draft 에 주입한다.
    - 캐시는 사용자가 명시적으로 POST /holdings/market/refresh 를 눌렀을 때만 채워진다.
      (2026-05-18: namespace 정정 — 기존 /market/refresh 가 ETF universe SQLite refresh
      엔드포인트로 이동하면서 holdings naver 시세 갱신은 /holdings/market/refresh 로 분리.)
    - 캐시가 비어있거나 일부만 있으면 그 부분은 시세 없이 표시된다 (price_missing).
    - 이 엔드포인트가 자동으로 외부 fetch 를 트리거하지 않는다.
    """
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
    if not loaded:
        raise HTTPException(
            status_code=422,
            detail="holdings 가 비어 있습니다. 먼저 보유 종목을 입력 후 저장해 주세요.",
        )
    # 캐시에서 holdings 종목에 해당하는 시세만 추출 (전체 캐시 노출 방지).
    all_quotes = market_cache.get_all()
    relevant_quotes = {
        h.ticker: all_quotes[h.ticker] for h in loaded if h.ticker in all_quotes
    }
    run = draft.generate_draft_from_holdings(loaded, market_quotes=relevant_quotes)
    return RunResponse.from_run(run)


# POC2 3-PUSH Message Contract (2026-06-12, FIX r2 — 설계자 수용):
# 신규 PUSH endpoint 신설 금지선 (§3 / §11) 준수. PUSH-1 / PUSH-3 은 위의
# POST /runs/generate 가 input_data.push_kind 로 분기 처리한다 (draft.generate_
# draft 가 draft_three_push 모듈로 위임). PUSH-2 (holdings_briefing) 는 위의
# POST /runs/generate-from-holdings 가 재정의되어 동일 계약을 따른다.


# ─── POC2 Step 2: market data ──────────────────────────────────────────


class MarketQuoteResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    price_asof: Optional[str] = None
    price_source: Optional[str] = None


class MarketRefreshResponse(BaseModel):
    ok_count: int
    fail_count: int
    items: list[MarketQuoteResponse]
    failures: list[dict[str, str]]


class EnrichedHoldingResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    quantity: float
    avg_buy_price: float
    invested_amount: float
    current_price: Optional[float] = None
    price_asof: Optional[str] = None
    price_source: Optional[str] = None
    eval_amount: Optional[float] = None
    pnl_amount: Optional[float] = None
    pnl_rate_pct: Optional[float] = None
    buy_weight_pct: Optional[float] = None
    market_weight_pct: Optional[float] = None
    price_missing: bool
    calc_missing: bool
    # POC2 Step 2C: 표시/그룹용 라벨 + UI key 안정성을 위한 행 위치.
    account_group: str = "일반"
    source_index: int = 0


class EnrichedHoldingsResponse(BaseModel):
    items: list[EnrichedHoldingResponse]


@app.post("/holdings/market/refresh", response_model=MarketRefreshResponse)
def post_market_refresh() -> MarketRefreshResponse:
    """저장된 holdings 의 모든 ticker 에 대해 Naver 시세를 조회 + 캐시에 반영.

    POC2 Step 2 설계자 결정:
    - 사용자가 명시적으로 호출했을 때만 외부 fetch 발생 (page load / polling /
      draft 조회 / 새로고침에서는 호출하지 않는다)
    - 1차 소스 Naver 만 사용. pykrx / yfinance fallback 은 POC2-Step2A 로 이연.
    - 단일 종목 실패는 격리 (다른 종목 진행)
    - 결과 요약 + 실패 사유 반환

    2026-05-18 namespace 정정 — 경로 `/market/refresh` 에서 `/holdings/market/refresh`
    로 이동. 이유: Market Discovery SQLite Direct Refresh STEP 의 새 endpoint 가
    ETF universe 전체 갱신용 `/market/refresh` 를 사용. 본 endpoint 는 holdings 시세
    갱신이라 의미 namespace 가 `/holdings/*` 가 맞다 (backward compatibility alias 없음).
    """
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
    if not loaded:
        raise HTTPException(
            status_code=422,
            detail="holdings 가 비어 있습니다. 먼저 보유 종목을 입력 후 저장해 주세요.",
        )

    tickers = [h.ticker for h in loaded]
    results = market_naver.fetch_many(tickers)

    successes = [r for r in results if r.quote is not None]
    failures = [r for r in results if r.quote is None]

    if successes:
        market_cache.upsert_many([r.quote for r in successes])  # type: ignore[misc]

    return MarketRefreshResponse(
        ok_count=len(successes),
        fail_count=len(failures),
        items=[
            MarketQuoteResponse(
                ticker=r.quote.ticker,
                name=r.quote.name,
                current_price=r.quote.current_price,
                price_asof=r.quote.price_asof,
                price_source=r.quote.price_source,
            )
            for r in successes
            if r.quote is not None
        ],
        failures=[
            {"ticker": r.ticker, "reason": r.reason or "unknown"} for r in failures
        ],
    )


@app.get("/holdings/enriched", response_model=EnrichedHoldingsResponse)
def get_holdings_enriched() -> EnrichedHoldingsResponse:
    """holdings × market_cache 조합 결과 조회. 외부 fetch 트리거 없음.

    캐시가 비어있어도 200 으로 holdings 단독 데이터(시세 없는 형태)를 반환한다.
    UI 가 price_missing / calc_missing 플래그를 보고 적절히 표시한다.
    """
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
    all_quotes = market_cache.get_all()
    relevant_quotes = {
        h.ticker: all_quotes[h.ticker] for h in loaded if h.ticker in all_quotes
    }
    enriched = holdings_enrich.enrich_holdings(loaded, relevant_quotes)
    return EnrichedHoldingsResponse(
        items=[
            EnrichedHoldingResponse(
                ticker=e.ticker,
                name=e.name,
                quantity=e.quantity,
                avg_buy_price=e.avg_buy_price,
                invested_amount=e.invested_amount,
                current_price=e.current_price,
                price_asof=e.price_asof,
                price_source=e.price_source,
                eval_amount=e.eval_amount,
                pnl_amount=e.pnl_amount,
                pnl_rate_pct=e.pnl_rate_pct,
                buy_weight_pct=e.buy_weight_pct,
                market_weight_pct=e.market_weight_pct,
                price_missing=e.price_missing,
                calc_missing=e.calc_missing,
                account_group=e.account_group,
                source_index=e.source_index,
            )
            for e in enriched
        ]
    )


@app.get("/runs", response_model=list[RunResponse])
def get_runs() -> list[RunResponse]:
    return [RunResponse.from_run(r) for r in store.list_runs()]


def _try_reconcile_with_oci_outbox(run: Run) -> Run:
    """DELIVERING 상태인 run 에 한해 OCI outbox 결과를 1회 조회하여 갱신.

    설계자 결정: 별도 worker/scheduler 를 만들지 않고, 프론트의 느린 polling
    이 GET /runs/{run_id} 를 호출할 때마다 동기적으로 SSH cat 1회 시도.
    outbox 파일이 있으면 store 갱신, 없으면 DELIVERING 유지.

    outbox 파일 규약(소비자 poc1_consume_inbox.sh 가 작성):
    {
      "run_id": "...",
      "status": "COMPLETED" | "FAILED",
      "processed_at": "ISO-8601",
      "telegram_message_id": "...optional..."
    }
    """
    if run.status != "DELIVERING":
        return run
    try:
        outbox = delivery.fetch_outbox_result(run.run_id)
    except delivery.DeliveryConfigError as e:
        # 환경변수 누락은 silent swallow 금지 (Codex B-1).
        # DELIVERING 영구 고정을 막기 위해 즉시 FAILED 로 종결한다.
        # 사용자가 .env 를 설정하지 않은 상태라면 동일한 누락으로 _execute_delivery
        # 단계에서도 FAILED 가 됐어야 정상이며, 여기 도달했다는 것은 SCP 시점에는
        # 환경변수가 있었으나 이후 사라진 비정상 상태이므로 명시적 실패 처리.
        logger.error(
            f"[reconcile] OCI 환경변수 누락으로 outbox 조회 불가 → FAILED "
            f"run_id={run.run_id}: {e}"
        )
        run.status = "FAILED"
        store.save(run)
        return run
    if not outbox:
        return run
    new_status = outbox.get("status")
    if new_status not in ("COMPLETED", "FAILED"):
        logger.warning(
            f"outbox status 가 비정상: run_id={run.run_id} status={new_status!r}. "
            "DELIVERING 유지."
        )
        return run
    try:
        validate_transition(run.status, new_status)
    except InvalidTransition as e:
        logger.warning(f"outbox 결과 무시 (전이 위반): {e}")
        return run
    run.status = new_status
    store.save(run)
    logger.info(f"[reconcile] OCI outbox 결과 반영 run_id={run.run_id} → {new_status}")
    return run


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    run = _try_reconcile_with_oci_outbox(run)
    return RunResponse.from_run(run)


@app.post("/runs/{run_id}/reject", response_model=RunResponse)
def post_reject(run_id: str) -> RunResponse:
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    try:
        validate_transition(run.status, "REJECTED")
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    run.status = "REJECTED"
    store.save(run)
    return RunResponse.from_run(run)


def _execute_delivery(run_id: str) -> None:
    """BackgroundTasks 에서 실행되는 전달 워커 (POC1 Step 3 OCI 연결 구조).

    deliver() 의 책임은 'OCI inbox 에 SCP 로 artifact 를 큐잉' 까지이며,
    그것만으로는 최종 COMPLETED 가 아니다. 실제 처리(Telegram 발송) 는 OCI
    측 daily_ops.sh → poc1_consume_inbox.sh 가 수행하고 그 결과를 outbox 에
    파일로 남긴다. 로컬 GET /runs/{run_id} 가 그 outbox 를 조회해
    COMPLETED 또는 FAILED 로 reconciliation 한다.

    따라서 이 함수의 분기는:
    - SCP 성공 → status 그대로(DELIVERING). store.save 만 (asof 는 변경 없음)
    - SCP 실패(또는 환경 설정 누락) → status FAILED 로 즉시 종결
    """
    try:
        run = store.load(run_id)
    except KeyError:
        logger.error(f"background delivery: run_id 조회 실패 {run_id}")
        return
    if run.status != "DELIVERING":
        logger.warning(
            f"background delivery: 상태가 DELIVERING 이 아님 "
            f"(run_id={run_id}, status={run.status}). 전달 건너뜀."
        )
        return
    try:
        delivery.deliver(run)
        # SCP 성공 = OCI inbox 에 큐잉 완료. 최종 결과는 outbox reconciliation 에서.
        logger.info(
            f"background delivery: SCP 큐잉 완료 (run_id={run_id}). DELIVERING 유지."
        )
    except delivery.DeliveryError as e:
        logger.error(f"delivery 실패 run_id={run.run_id}: {e}")
        run.status = "FAILED"
        store.save(run)
    except delivery.DeliveryConfigError as e:
        # 환경변수 미설정 — 검증 환경에서는 stub 으로 우회되지만,
        # 실 운영에서 누락되면 즉시 FAILED 로 마킹해야 사용자가 알 수 있음.
        logger.error(f"delivery 환경 설정 누락 run_id={run.run_id}: {e}")
        run.status = "FAILED"
        store.save(run)


@app.post("/runs/{run_id}/approve", response_model=RunResponse)
def post_approve(run_id: str, background_tasks: BackgroundTasks) -> RunResponse:
    """Approve 요청.

    - PENDING_APPROVAL → DELIVERING 상태 저장 후 '즉시' DELIVERING 응답을 반환
    - 실제 외부 전달은 BackgroundTasks 로 위임 (별도 태스크)
    - 클라이언트는 polling 또는 수동 새로고침으로 COMPLETED / FAILED 최종 상태를 확인
    """
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    try:
        validate_transition(run.status, "DELIVERING")
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))

    run.status = "DELIVERING"
    store.save(run)

    # 현 시점 스냅샷을 응답으로 고정 (background 가 언제 실행되든 상관 없음)
    snapshot = RunResponse.from_run(run)

    # 외부 전달은 비동기로 진행. 결과는 store 업데이트.
    background_tasks.add_task(_execute_delivery, run_id)

    return snapshot
