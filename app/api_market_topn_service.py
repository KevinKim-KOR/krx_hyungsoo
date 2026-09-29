"""Market Discovery API — 변환 헬퍼 + evidence 보강 + score 머지 + context 변환."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.api_market_topn_models import (
    DataQualityPayload,
    DailyReturnCheckPayload,
    MarketCandidate,
    MarketCandidateExcessReturn,
    MarketContextKodex200,
    MarketContextKospi,
    MarketContextRegimeStreak,
    MarketContextResponse,
    MarketPeriodReturn,
    MarketReturns,
    MarketRiskKodex200,
    MarketRiskRecentPoint,
    MarketRiskReference,
    MarketRiskVix,
    MarketTopNEntry,
    NavDiscountPayload,
    ShortTermMomentumPayload,
    ShortTermMomentumStartDates,
)
from pathlib import Path

from app.etf_nav_fetcher import classify_discount_flag
from app.etf_nav_store import fetch_latest_nav
from app.market_benchmark_freshness import MAX_STALE_TRADING_DAYS
from app.market_briefing.calendar import check_trading_day
from app.market_data_store import latest_refresh_log
from app.trading_day_lag import benchmark_lag_trading_days
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


# ─── POC3-02D-OPS-02 3-4 — KOSPI 최신성 화면 상태 (설계자 Q4~Q6 · 2026-09-28) ────
# 기존 응답 `market_context.kospi` 에 **선택 필드 3개**만 더한다(설계자 Q4 — 신규
# 엔드포인트 · 기존 필드 의미 변경 · 외부 호출 0). 이미 가진 DB(KS11 적재 기록)와
# 거래일 캘린더만 읽는다. 운영 판정(`compute_kospi_metrics` · 임계값)은 그대로다.
# 화면 문구는 프론트 `KospiStatusNote` 가 상태 → 설계자 확정 문구로 옮긴다.

KOSPI_REFRESH_SOURCE = "FinanceDataReader/KS11"
_KST = timezone(timedelta(hours=9))


def _kst_today() -> str:
    return datetime.now(_KST).date().isoformat()


def kospi_display_state(
    *,
    status: Optional[str],
    as_of: Optional[str],
    lag: Optional[int],
    last_refresh: Optional[dict],
    today_is_trading_day: Optional[bool],
) -> str:
    """KOSPI 화면 상태 하나. 위에서부터 처음 맞는 줄.

    | 조건 | 상태 |
    |---|---|
    | 저장 KOSPI 없음 · KS11 적재 기록 없음 | `not_evaluated` |
    | 저장 KOSPI 없음 · 마지막 적재가 호출 실패 | `source_failed` |
    | 저장 KOSPI 없음 | `no_result` |
    | 최신 아님(아래) · 마지막 적재가 호출 실패 | `source_failed` |
    | 최신 아님 | `stale` |
    | 최신이지만 수익률 미산출(운영 판정 `ok` 아님) | `no_result` |
    | 오늘이 거래일 아님 | `holiday` |
    | 그 밖 | `ok` |

    - **최신** = 운영 판정이 `stale` 이 아니고, 거래일 지연(`lag`)을 쟀고
      `MAX_STALE_TRADING_DAYS` 이하. 지연을 못 재면 최신으로 보지 않는다(C7 과 같다).
    - **호출 실패** = 마지막 KS11 적재 기록이 실패이고 사유가 `source_stale:` 가
      아님(자료원이 멈춘 것은 `stale`). 자료가 최신이면 그 뒤 호출 실패는 화면 값에
      영향이 없어 보지 않는다.
    """
    fetch_failed = bool(
        last_refresh
        and int(last_refresh.get("fail_count") or 0) > 0
        and not str(last_refresh.get("error_summary") or "").startswith("source_stale:")
    )
    if as_of is None:
        if last_refresh is None:
            return "not_evaluated"
        return "source_failed" if fetch_failed else "no_result"
    fresh = status != "stale" and lag is not None and lag <= MAX_STALE_TRADING_DAYS
    if not fresh:
        return "source_failed" if fetch_failed else "stale"
    if status != "ok":
        return "no_result"
    if today_is_trading_day is False:
        return "holiday"
    return "ok"


def with_kospi_display(
    market_context: Optional[dict],
    *,
    db_path: Path,
    today_kst: Optional[str] = None,
    calendar_dir: Optional[Path] = None,
) -> Optional[dict]:
    """`market_context.kospi` 에 `display_state` · `trading_day_lag` ·
    `today_is_trading_day` 를 더한 **사본**. 입력 dict 는 바꾸지 않는다.

    `trading_day_lag` 는 C7 KOSPI 적재 감지와 **같은 함수**
    (`benchmark_lag_trading_days` — 거래일 캘린더 축, 없으면 평일 fallback)다.
    KODEX200 적재일 축 lag(`freshness.lag_trading_days`)와 섞지 않는다(설계자 Q6).
    읽기가 실패하면 필드를 더하지 않는다 — 화면은 기존 `status` 로 표시한다.
    """
    if not isinstance(market_context, dict):
        return market_context
    kospi = market_context.get("kospi")
    if not isinstance(kospi, dict):
        return market_context
    today = today_kst or _kst_today()
    as_of = kospi.get("as_of_date")
    try:
        last_refresh = latest_refresh_log(source=KOSPI_REFRESH_SOURCE, db_path=db_path)
        lag, _ref = benchmark_lag_trading_days(
            as_of, today_kst=today, calendar_dir=calendar_dir
        )
        trading_today = check_trading_day(today, directory=calendar_dir).ok
    except Exception:  # noqa: BLE001 — 표시 보조 필드가 응답 전체를 깨면 안 된다
        return market_context
    state = kospi_display_state(
        status=kospi.get("status"),
        as_of=as_of,
        lag=lag,
        last_refresh=last_refresh,
        today_is_trading_day=trading_today,
    )
    return {
        **market_context,
        "kospi": {
            **kospi,
            "display_state": state,
            "trading_day_lag": lag,
            "today_is_trading_day": trading_today,
        },
    }


def market_context_to_model(raw: Optional[dict]) -> Optional[MarketContextResponse]:
    if not raw:
        return None
    kodex_raw = raw.get("kodex200") or {"status": "unavailable"}
    kospi_raw = raw.get("kospi") or {"status": "unavailable"}
    streak_raw = raw.get("regime_streak")
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
        regime_streak=(
            MarketContextRegimeStreak(**streak_raw)
            if isinstance(streak_raw, dict)
            else None
        ),
        warnings=list(raw.get("warnings") or []),
    )


# 2026-07-03 Market Risk Reference v1 (지시문 §7).


def build_market_risk_reference_payload(db_path: Path) -> MarketRiskReference:
    """SQLite 만 read 하여 KODEX200 + VIX evidence 를 API 응답 모델로 변환.

    외부 시세 호출 X. 지시문 §7 계약: 최상위 필드로 항상 존재하며 데이터
    부재 시 availability="unavailable".
    """
    from app.market_risk_reference_service import build_market_risk_reference

    evidence = build_market_risk_reference(db_path=db_path)

    def _to_points(series) -> list[MarketRiskRecentPoint]:
        if not series:
            return []
        return [MarketRiskRecentPoint(date=p.date, close=p.close) for p in series]

    return MarketRiskReference(
        kodex200=MarketRiskKodex200(
            availability=evidence.kodex200.availability,
            as_of_date=evidence.kodex200.as_of_date,
            close=evidence.kodex200.close,
            change_1d_pct=evidence.kodex200.change_1d_pct,
            recent_20d_series=_to_points(evidence.kodex200.recent_20d_series),
            series_first_date=evidence.kodex200.series_first_date,
            series_last_date=evidence.kodex200.series_last_date,
        ),
        vix=MarketRiskVix(
            availability=evidence.vix.availability,
            as_of_date=evidence.vix.as_of_date,
            close=evidence.vix.close,
            change_1d_pct=evidence.vix.change_1d_pct,
            change_5d_pct=evidence.vix.change_5d_pct,
            recent_20d_series=_to_points(evidence.vix.recent_20d_series),
            series_first_date=evidence.vix.series_first_date,
            series_last_date=evidence.vix.series_last_date,
        ),
    )
