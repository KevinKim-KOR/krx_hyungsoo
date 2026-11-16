"""ETF 구성종목 API — Constituents & Overlap 1차 (POC2 — 2026-05-27).

엔드포인트 (지시문 §8):
- POST /market/constituents/refresh     : 후보 tickers 만 외부 수집 + 캐시.
- GET  /market/constituents/analysis    : 구성종목 + 집중도 + 중복률 + repeated.
- GET  /market/constituents/holdings-status : 보유 ETF 구성 상태(저장 자료만 · POC6-31 STEP 2 · C11).
- POST /market/constituents/collect      : 후보 목록 수집 작업 시작(서버 작업 · POC6-31 STEP 3 · C15 · 판정 Q6 (b)).
- GET  /market/constituents/collect/status : 후보 수집 작업 상태(읽기만 · 읽기로 수집이 시작되지 않음 ·
  tickers 를 주면 같은 목록의 작업이 없을 때 저장 기록으로 ETF별 상태).
- GET  /market/constituents/cross-family : 여러 지수 계열이 함께 담은 주식(읽기 전용 · POC6-31 STEP 3).
- GET  /market/constituents/pair-exposure : 보유와 후보의 구성종목 비교(읽기 전용 · 금액 없음 · POC6-31 STEP 4 · C21).

본 router 는 매매 자동화 / Telegram / OCI PUSH / AI API 와 무관 — 외부 KRX
데이터 수집 (cap/cache/delay/budget 가드) + 로컬 SQLite 분석만.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import (
    etf_constituents_store,
)  # lookup-style attribute access (monkeypatch 친화).
from app.etf_constituents_analysis import (
    DEFAULT_TOP_K_FOR_OVERLAP,
    compute_analysis,
)
from app.etf_constituents_service import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    refresh_constituents,
)
from app.collect_target_date import collect_target_date
from app.etf_constituents_batch import COLLECTOR, KIND_CANDIDATES
from app.holdings_constituents_refresh import holdings_constituents_status
from app.constituents_cross_family import (
    cross_family,
    etf_meta,
    read_confirmed_rows,
)
from app import (
    constituents_pair_exposure,
    constituents_pair_exposure_io,
    constituents_pair_exposure_text,
)
from app.etf_constituents_batch import CANDIDATES_MAX, Collector
from app.etf_constituents_status import (
    CANDIDATES_ACTION,
    read_analysis_rows,
    stored_status,
)
from app.market_briefing.official_csv import resolve_official_csv

router = APIRouter()

ANALYSIS_MAX_TICKERS = (
    CANDIDATES_MAX  # 넘겨받는 후보 목록 상한(30) — 외부 호출 없는 읽기
)
META_DIR = Path("state/market_meta")


class RefreshConstituentsRequest(BaseModel):
    asof: str = Field(..., min_length=1)
    tickers: list[str] = Field(..., min_length=1)
    top_k: int = DEFAULT_TOP_K
    force: bool = False


class RefreshConstituentsItem(BaseModel):
    ticker: str
    status: str
    source: Optional[str] = None
    constituent_count: int = 0
    from_cache: bool = False
    message: Optional[str] = None


class RefreshConstituentsResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    message: Optional[str] = None
    asof: Optional[str] = None
    requested_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    cached_count: int = 0
    fetched_count: int = 0
    skipped_count: int = 0
    source: Optional[str] = None
    items: list[RefreshConstituentsItem] = []


@router.post("/market/constituents/refresh", response_model=RefreshConstituentsResponse)
def post_constituents_refresh(
    req: RefreshConstituentsRequest,
) -> RefreshConstituentsResponse:
    if not req.tickers:
        raise HTTPException(status_code=422, detail="tickers must not be empty.")
    if req.top_k is not None and req.top_k > MAX_TOP_K:
        raise HTTPException(
            status_code=422,
            detail=f"top_k must be <= {MAX_TOP_K}.",
        )
    # db_path 는 호출 시점 module attribute lookup — 테스트 monkeypatch 반영.
    result = refresh_constituents(
        asof=req.asof,
        tickers=list(req.tickers),
        top_k=req.top_k or DEFAULT_TOP_K,
        force=req.force,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
    )
    return RefreshConstituentsResponse(
        status=result.status,
        reason=result.reason,
        message=result.message,
        asof=result.asof,
        requested_count=result.requested_count,
        success_count=result.success_count,
        fail_count=result.fail_count,
        cached_count=result.cached_count,
        fetched_count=result.fetched_count,
        skipped_count=result.skipped_count,
        source=result.source,
        items=[
            RefreshConstituentsItem(
                ticker=i.ticker,
                status=i.status,
                source=i.source,
                constituent_count=i.constituent_count,
                from_cache=i.from_cache,
                message=i.message,
            )
            for i in result.items
        ],
    )


# ─── GET /market/constituents/analysis ────────────────────────────────


class TopHolding(BaseModel):
    rank: int
    ticker: Optional[str] = None
    name: Optional[str] = None
    weight_pct: Optional[float] = None
    # 2026-05-31 — Naver 통합. 해외형 종목은 ticker=null, 아래 식별자가 채워짐.
    constituent_isin: Optional[str] = None
    constituent_reuters_code: Optional[str] = None
    market_type: Optional[str] = None


class Concentration(BaseModel):
    top1_weight_pct: Optional[float] = None
    top3_weight_pct: Optional[float] = None
    top5_weight_pct: Optional[float] = None
    top10_weight_pct: Optional[float] = None


class ConstituentItem(BaseModel):
    etf_ticker: str
    etf_name: Optional[str] = None
    status: str
    source: Optional[str] = None
    asof: str
    # POC6-31 — 이 ETF 구성일이 원천이 준 날짜로 확인됐나(None = 자료 없음)
    asof_confirmed: Optional[bool] = None
    top_holdings: list[TopHolding] = []
    concentration: Concentration = Concentration()


class OverlapCommonHolding(BaseModel):
    ticker: Optional[str] = None
    name: Optional[str] = None
    left_weight_pct: Optional[float] = None
    right_weight_pct: Optional[float] = None


class OverlapPair(BaseModel):
    left_ticker: str
    right_ticker: str
    common_count_top10: int = 0
    weighted_overlap_pct: Optional[float] = None
    common_holdings: list[OverlapCommonHolding] = []
    # POC6-31(판정 Q7) — 양쪽 구성일 · 같은 날짜 쌍인가(다른 날짜 쌍은 참고)
    left_asof: Optional[str] = None
    right_asof: Optional[str] = None
    same_date: Optional[bool] = None
    # same_date(양쪽 원천일 확인 · 같은 날짜) · unconfirmed · different_date · no_data(한쪽 자료 없음)
    pair_scope: Optional[str] = None


class RepeatedCoreItem(BaseModel):
    etf_ticker: str
    weight_pct: Optional[float] = None


class RepeatedCoreHolding(BaseModel):
    ticker: Optional[str] = None
    name: Optional[str] = None
    appears_in_etf_count: int = 0
    items: list[RepeatedCoreItem] = []


class AnalysisCoverage(BaseModel):
    requested_count: int
    available_count: int
    unavailable_count: int


class ConstituentsAnalysisResponse(BaseModel):
    status: str
    asof: str
    # 표시 깊이 (구성종목 탭). 2026-08-19 설계 확정으로 최대 30.
    top_k: int
    # 중복률·반복 등장 계산 기준 깊이. **표시 깊이와 무관하게 항상 10** —
    # 화면의 `Top 10 기준` 문구가 계속 사실이어야 한다.
    overlap_top_k: int = DEFAULT_TOP_K_FOR_OVERLAP
    coverage: AnalysisCoverage
    constituents: list[ConstituentItem] = []
    overlap_matrix: list[OverlapPair] = []
    repeated_core_holdings: list[RepeatedCoreHolding] = []


def _parse_tickers_csv(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


@router.get(
    "/market/constituents/analysis", response_model=ConstituentsAnalysisResponse
)
def get_constituents_analysis(
    tickers: str = Query(..., description="콤마 구분 ETF tickers"),
    # 2026-05-27 FIX (검증자 B-6 NOTE 반영) — 지시문 §8.2 예시는 asof 없이 호출.
    # asof 누락 시 ticker 별 latest_constituent_asof 중 MAX 를 사용 (서버가
    # 가장 최근 수집 시점 자동 선택).
    asof: Optional[str] = Query(default=None),
    top_k: int = Query(default=DEFAULT_TOP_K_FOR_OVERLAP, ge=1, le=MAX_TOP_K),
) -> ConstituentsAnalysisResponse:
    ticker_list = _parse_tickers_csv(tickers)
    if not ticker_list:
        raise HTTPException(status_code=422, detail="tickers must not be empty.")
    # POC6-31(판정 Q7) — 외부 호출 없는 DB 읽기라 넘겨받는 후보 목록 상한(30)까지 읽는다.
    if len(ticker_list) > ANALYSIS_MAX_TICKERS:
        raise HTTPException(
            status_code=422,
            detail=f"tickers count > {ANALYSIS_MAX_TICKERS}.",
        )

    # 읽기 전용 · 원천일 확인은 날짜를 지정해도 · 비워도 같은 기준(검증자 r1 F2 · r2 F6 — 지정일의 기록). 날짜 · 행 · 확인
    # 지문을 한 읽기 트랜잭션에서 읽어 그 행의 지문으로 판정한다(검증자 r2 F5 · r3 F8).
    db = etf_constituents_store.DEFAULT_DB_PATH
    asof_by_ticker, preloaded = read_analysis_rows(ticker_list, asof=asof, db_path=db)
    # 데이터 1건도 없으면 today 로 fallback (compute_analysis 가 모두 unavailable 로 결과 반환).
    effective_asof = asof or (
        max(asof_by_ticker.values())
        if asof_by_ticker
        else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )

    payload = compute_analysis(
        tickers=ticker_list,
        asof=effective_asof,
        top_k=top_k,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
        asof_by_ticker=asof_by_ticker,
        preloaded=preloaded,
    )
    return ConstituentsAnalysisResponse(**payload)


# ---- POC6-31 — 보유 구성 상태 · 후보 수집 작업 ----


@router.get("/market/constituents/holdings-status")
def get_holdings_constituents_status() -> dict:
    """보유 ETF 별 구성 상태(저장 자료만 · 읽기 전용) — 화면 진입 · [요약 다시 읽기] · 할 일 개수."""
    return holdings_constituents_status(db_path=etf_constituents_store.DEFAULT_DB_PATH)


class CollectRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1)


def _collect_idle() -> dict:
    return {"state": "idle", "job_id": None, "items": []}


@router.post("/market/constituents/collect")
def post_constituents_collect(req: CollectRequest) -> dict:
    """후보 목록 수집 작업 시작. 이미 도는 중이면 그 작업을 돌려준다(새로 만들지 않음 · 판정 §1 둘째)."""
    target = collect_target_date(datetime.now(timezone.utc))
    if target is None:
        raise HTTPException(
            status_code=503, detail="수집 목표일을 정하지 못했습니다(달력)."
        )
    return COLLECTOR.start(
        KIND_CANDIDATES,
        list(req.tickers),
        target_date=target,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
    )


@router.get("/market/constituents/collect/status")
def get_constituents_collect_status(
    tickers: Optional[str] = Query(
        default=None, description="콤마 구분 후보 tickers(이 목록의 상태)"
    ),
) -> dict:
    """후보 수집 작업 상태 — 읽기만(수집을 시작하지 않음 · 판정 Q6).

    `tickers` 를 주면 그 목록의 상태를 돌려준다:
    - 같은 목록 · 같은 목표일의 작업(진행 중 · 끝남)이 있으면 그 작업.
    - 없으면 저장 기록으로 ETF별 상태(`stored=True` · 서버를 다시 켜도 같은 상태 · 판정 §1 셋째 · 넷째).
      다른 목록의 작업이 돌고 있으면 `other_job` 에 그 범위를 싣는다(이 목록의 수집처럼 보이지 않게).
    """
    job = COLLECTOR.current(KIND_CANDIDATES)
    if tickers is None:
        return job or _collect_idle()
    ticker_list = Collector.normalize(KIND_CANDIDATES, _parse_tickers_csv(tickers))
    if not ticker_list:
        raise HTTPException(status_code=422, detail="tickers must not be empty.")
    target = collect_target_date(datetime.now(timezone.utc))
    if target is None:
        raise HTTPException(
            status_code=503, detail="수집 목표일을 정하지 못했습니다(달력)."
        )
    if (
        job
        and set(job["tickers"]) == set(ticker_list)
        and (job["state"] == "running" or job["target_date"] == target)
    ):
        return {**job, "other_list": False, "stored": False}
    st = stored_status(
        ticker_list,
        target_date=target,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
        action=CANDIDATES_ACTION,
    )
    running_other = job if job and job["state"] == "running" else None
    return {
        "state": "idle",
        "job_id": None,
        "stored": True,
        "other_list": False,
        "stored_status": st["status"],
        "reason": st["reason"],
        "target_date": target,
        "total": st["total"],
        "needs_check": st["needs_check"],
        "counts": st["counts"],
        "items": st["items"],
        "other_job": (
            {
                "total": running_other["total"],
                "done": running_other["done"],
                "started_at": running_other["started_at"],
            }
            if running_other
            else None
        ),
    }


@router.get("/market/constituents/cross-family")
def get_constituents_cross_family(
    tickers: str = Query(..., description="콤마 구분 ETF tickers(선정 순서)"),
) -> dict:
    """여러 지수 계열이 함께 담은 주식(POC6-31 STEP 3 · 판정 §2 첫째) — 읽기 전용 · 외부 호출 0."""
    ticker_list = list(dict.fromkeys(_parse_tickers_csv(tickers)))
    if not ticker_list:
        raise HTTPException(status_code=422, detail="tickers must not be empty.")
    if len(ticker_list) > ANALYSIS_MAX_TICKERS:
        raise HTTPException(
            status_code=422, detail=f"tickers count > {ANALYSIS_MAX_TICKERS}."
        )
    db = etf_constituents_store.DEFAULT_DB_PATH
    sel = resolve_official_csv(META_DIR)
    official = (
        {
            (r.get("단축코드") or "").strip(): r
            for r in sel.records
            if (r.get("단축코드") or "").strip()
        }
        if sel.ok
        else {}
    )
    names, etf_tickers = _etf_master(db)
    latest = read_confirmed_rows(ticker_list, db_path=db)
    out = cross_family(etf_meta(ticker_list, official, names), latest, etf_tickers)
    out["official_csv"] = sel.name if sel.ok else None
    return out


def _etf_master(db_path) -> tuple[dict[str, Optional[str]], set[str]]:
    # 못 읽으면 빈 목록(계열 비교 · 기존 동작) — 짝 비교는 None 으로 '확인 불가'를 따로 낸다.
    return constituents_pair_exposure_io.read_etf_master(Path(db_path)) or ({}, set())


@router.get("/market/constituents/pair-exposure")
def get_constituents_pair_exposure(
    candidate: str = Query(..., min_length=1, description="고른 후보 ETF"),
    holding: Optional[str] = Query(None, description="고른 보유(ETF 또는 개별 주식)"),
    screen: Optional[str] = None,
    basis: Optional[str] = None,
    side: Optional[str] = None,
    rank: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exclude_inverse: bool = Query(...),
    exclude_leveraged: bool = Query(...),
    exclude_synthetic: bool = Query(...),
    exclude_futures: bool = Query(...),
) -> dict:
    """보유와 후보의 구성종목 비교(POC6-31 STEP 4 · PLAN C21 · 판정 §2 둘째 · 셋째) — 읽기 전용 · 외부 호출 0.

    응답에 금액은 없다(%만 · POC6-24). `fingerprint` = 판단 근거 미리보기가 같은 함수로 다시 계산해 대조하는 근거 지문.
    """
    cand = candidate.strip()
    if not cand:
        raise HTTPException(status_code=422, detail="candidate must not be empty.")
    condition = constituents_pair_exposure.condition_of(
        screen=screen,
        basis=basis,
        side=side,
        rank=rank,
        start_date=start_date,
        end_date=end_date,
        filters={
            "exclude_inverse": exclude_inverse,
            "exclude_leveraged": exclude_leveraged,
            "exclude_synthetic": exclude_synthetic,
            "exclude_futures": exclude_futures,
        },
    )
    body = constituents_pair_exposure_io.load(
        cand,
        (holding or "").strip() or None,
        condition,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
    )
    # 기준일 줄 = 미리보기 원문과 같은 서버 글(화면이 따로 만들지 않음 · 검증자 STEP 4~5 r1 B-6 · F12) · 지문 밖 덧붙임.
    return {
        **body,
        "date_line": constituents_pair_exposure_text.date_line(body),
        "pair_dates_differ": constituents_pair_exposure_text.pair_dates_differ(body),
        # 주식별 합계에서 빠진 ETF 사유 글(미리보기 원문과 같은 글 · 검증자 STEP 4~5 r2 F14 · 없으면 null)
        "stock_notes": {
            s["key"]: constituents_pair_exposure_text.unknown_note(s["exposure"])
            for s in body["stocks"]
        },
    }
