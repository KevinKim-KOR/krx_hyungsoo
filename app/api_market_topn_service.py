"""Market Discovery API — 변환 헬퍼 + evidence 보강 + score 머지 + context 변환."""

from __future__ import annotations

from typing import Optional

from app.api_market_topn_models import (
    DataQualityPayload,
    DailyReturnCheckPayload,
    MarketCandidate,
    MarketCandidateExcessReturn,
    MarketContextKodex200,
    MarketContextKospi,
    MarketContextResponse,
    MarketPeriodReturn,
    MarketReturns,
    MarketTopNEntry,
    NavDiscountPayload,
    ShortTermMomentumPayload,
    ShortTermMomentumStartDates,
)
from pathlib import Path

from app.etf_nav_fetcher import classify_discount_flag
from app.etf_nav_store import fetch_latest_nav
from app.short_term_momentum import (
    compute_daily_return_check,
    compute_short_term_momentum_batch,
)


def entry_to_model(raw: dict) -> MarketTopNEntry:
    return MarketTopNEntry(
        rank=raw.get("rank"),
        ticker=raw.get("ticker"),
        name=raw.get("name"),
        return_pct=raw.get("return_pct"),
        basis_start_date=raw.get("basis_start_date"),
        basis_end_date=raw.get("basis_end_date"),
        tags=list(raw.get("tags") or []),
    )


def period_to_model(raw: Optional[dict]) -> Optional[MarketPeriodReturn]:
    if raw is None:
        return None
    return MarketPeriodReturn(
        return_pct=raw.get("return_pct"),
        basis_start_date=raw.get("basis_start_date"),
        basis_end_date=raw.get("basis_end_date"),
    )


def candidate_to_model(raw: dict) -> MarketCandidate:
    returns_raw = raw.get("returns") or {}
    excess_raw = raw.get("excess_return") or None
    return MarketCandidate(
        rank=raw.get("rank"),
        ticker=raw.get("ticker"),
        name=raw.get("name"),
        tags=list(raw.get("tags") or []),
        selected_return_pct=raw.get("selected_return_pct"),
        selected_basis_start_date=raw.get("selected_basis_start_date"),
        selected_basis_end_date=raw.get("selected_basis_end_date"),
        returns=MarketReturns(
            daily=period_to_model(returns_raw.get("daily")),
            one_month=period_to_model(returns_raw.get("one_month")),
            three_month=period_to_model(returns_raw.get("three_month")),
            # 2026-06-08 — 표시 전용 신규 기간.
            six_month=period_to_model(returns_raw.get("six_month")),
            twelve_month=period_to_model(returns_raw.get("twelve_month")),
            three_year=period_to_model(returns_raw.get("three_year")),
        ),
        excess_return=(
            MarketCandidateExcessReturn(**excess_raw) if excess_raw else None
        ),
    )


def build_nav_discount_payload(ticker: str, db_path: Path) -> NavDiscountPayload:
    """store 에서 최신 NAV row 를 읽어 응답 payload 생성 (지시문 §10.2).

    store 에 row 없으면 status=unavailable + message.
    """
    row = fetch_latest_nav(etf_ticker=ticker, db_path=db_path)
    if row is None:
        return NavDiscountPayload(
            status="unavailable",
            message="NAV / discount source unavailable",
        )
    return NavDiscountPayload(
        status=row.status,
        asof=row.asof,
        nav=row.nav,
        market_price=row.market_price,
        discount_rate_pct=row.discount_rate_pct,
        flag=classify_discount_flag(row.discount_rate_pct),
        source=row.source,
        message=row.message,
    )


def merge_relative_upside_score(
    candidates: list[MarketCandidate],
) -> tuple[list[MarketCandidate], dict[str, Optional[str]]]:
    """후보별 ML score / drawdown / reasons 머지 (지시문 §10).

    snapshot 부재 / 손상 / status != "ok" 면 후보는 그대로 두고 top-level 상태만
    채워서 반환. 후보 응답 자체는 절대 실패시키지 않는다 (지시문 §10 끝).

    반환: (수정된 후보 리스트, top-level 메타 dict)
    """
    from app.ml_relative_upside_score import (
        USER_NOTICE as ML_USER_NOTICE,
        load_score_snapshot,
    )

    snapshot = load_score_snapshot()
    if not snapshot:
        return candidates, {
            "relative_upside_score_status": "unavailable",
            "relative_upside_score_asof_date": None,
            "relative_upside_score_generated_at": None,
            "relative_upside_score_user_notice": ML_USER_NOTICE,
        }

    snapshot_status = snapshot.get("status")
    asof = snapshot.get("asof_date")
    generated = snapshot.get("generated_at")
    if snapshot_status != "ok":
        return candidates, {
            "relative_upside_score_status": (
                snapshot_status if isinstance(snapshot_status, str) else "failed"
            ),
            "relative_upside_score_asof_date": asof,
            "relative_upside_score_generated_at": generated,
            "relative_upside_score_user_notice": ML_USER_NOTICE,
        }

    by_ticker: dict[str, dict[str, object]] = {}
    for c in snapshot.get("candidates") or []:
        if not isinstance(c, dict):
            continue
        ticker = c.get("ticker")
        if not isinstance(ticker, str):
            continue
        by_ticker[ticker] = c

    merged: list[MarketCandidate] = []
    for cand in candidates:
        if not cand.ticker:
            merged.append(cand)
            continue
        score_row = by_ticker.get(cand.ticker)
        if score_row is None:
            merged.append(cand)
            continue
        score = score_row.get("relative_upside_score")
        cand.relative_upside_score = score  # type: ignore[assignment]
        cand.drawdown_20d = score_row.get("drawdown_20d")  # type: ignore[assignment]
        reasons = score_row.get("relative_upside_reasons") or []
        cand.relative_upside_reasons = [r for r in reasons if isinstance(r, str)]
        merged.append(cand)

    return merged, {
        "relative_upside_score_status": "ok",
        "relative_upside_score_asof_date": asof,
        "relative_upside_score_generated_at": generated,
        "relative_upside_score_user_notice": ML_USER_NOTICE,
    }


def enrich_candidates_with_evidence(
    candidates: list[MarketCandidate],
    db_path: Path,
) -> list[MarketCandidate]:
    """단기 흐름 + data_quality 채우기 (지시문 §10).

    KODEX200 시계열은 1회만 fetch. NAV 는 store read only.
    """
    tickers = [c.ticker for c in candidates if c.ticker]
    momentum_map = compute_short_term_momentum_batch(tickers, db_path=db_path)
    enriched: list[MarketCandidate] = []
    for c in candidates:
        if not c.ticker:
            enriched.append(c)
            continue
        m = momentum_map.get(c.ticker)
        momentum_payload = (
            ShortTermMomentumPayload(
                status=m.status,
                return_5d_pct=m.return_5d_pct,
                return_10d_pct=m.return_10d_pct,
                return_20d_pct=m.return_20d_pct,
                excess_vs_kodex200_5d_pctp=m.excess_vs_kodex200_5d_pctp,
                excess_vs_kodex200_10d_pctp=m.excess_vs_kodex200_10d_pctp,
                excess_vs_kodex200_20d_pctp=m.excess_vs_kodex200_20d_pctp,
                start_dates=(
                    ShortTermMomentumStartDates(
                        five_d=m.start_date_5d,
                        ten_d=m.start_date_10d,
                        twenty_d=m.start_date_20d,
                    )
                    if m.status == "ok"
                    else None
                ),
                end_date=m.end_date,
                message=m.message,
            )
            if m is not None
            else None
        )

        d = compute_daily_return_check(c.ticker, db_path=db_path)
        daily_payload = DailyReturnCheckPayload(
            status=d.status,
            daily_return_pct=d.daily_return_pct,
            flag=d.flag,
            threshold_pct=d.threshold_pct,
            message=d.message,
        )
        nav_payload = build_nav_discount_payload(c.ticker, db_path=db_path)

        warnings: list[str] = []
        if daily_payload.flag:
            warnings.append(daily_payload.flag)
        if nav_payload.flag:
            warnings.append(nav_payload.flag)

        # data_quality 전체 status — daily 또는 nav 중 warning 이 있으면 warning.
        if daily_payload.status == "warning" or nav_payload.flag is not None:
            overall_status = "warning"
        elif (
            daily_payload.status == "unavailable"
            and nav_payload.status == "unavailable"
        ):
            overall_status = "unavailable"
        else:
            overall_status = "ok"

        dq_payload = DataQualityPayload(
            status=overall_status,
            daily_return_check=daily_payload,
            nav_discount=nav_payload,
            warnings=warnings,
        )
        enriched.append(
            c.model_copy(
                update={
                    "short_term_momentum": momentum_payload,
                    "data_quality": dq_payload,
                }
            )
        )
    return enriched


def market_context_to_model(raw: Optional[dict]) -> Optional[MarketContextResponse]:
    if not raw:
        return None
    kodex_raw = raw.get("kodex200") or {"status": "unavailable"}
    kospi_raw = raw.get("kospi") or {"status": "unavailable"}
    return MarketContextResponse(
        status=raw.get("status") or "unavailable",
        asof=raw.get("asof"),
        primary_benchmark=raw.get("primary_benchmark") or "KODEX200",
        regime_label=raw.get("regime_label") or "판정불가",
        regime_code=raw.get("regime_code") or "unavailable",
        regime_score=raw.get("regime_score"),
        regime_reasons=list(raw.get("regime_reasons") or []),
        kodex200=MarketContextKodex200(**kodex_raw),
        kospi=MarketContextKospi(**kospi_raw),
        warnings=list(raw.get("warnings") or []),
    )
