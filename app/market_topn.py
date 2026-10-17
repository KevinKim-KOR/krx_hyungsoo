"""SQLite 직접 계산 기반 일간 / 1개월 / 3개월 TOP N 산출.

2026-05-18 변경 (Market Discovery SQLite Direct Refresh):
- JSON artifact 출력/저장 폐기 (state/market/ 하위 어떤 .json 파일도 생성하지 않는다).
- 시장 데이터 SSOT 는 state/market/market_data.sqlite 단일.
- API (`GET /market/topn/latest`) 는 본 모듈의 `compute_topn()` 만 호출한다.

응답 status:
- "ok"      : 정상 — universe + 가격 데이터로 TOP N 산출 가능 (빈 결과여도 ok)
- "missing" : SQLite DB 파일 자체 없음
- "empty"   : DB 존재하나 가격 데이터 부족 (etf_daily_price 의 date 없음)
- "invalid" : DB 파일 깨짐 / 필수 테이블 부재 등 구조 이상

결측 처리 (지시문 §6):
- 결측 ETF 를 0% 수익률로 보정하지 않는다.
- period_exclusions 로 기간별 제외 사유를 집계해 반환.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from app.market_benchmark_store import fetch_benchmark_history
from app.market_data_store import (
    DEFAULT_DB_PATH,
    fetch_price_history,
    get_etf_name,
    get_etf_name_map,
    list_etf_tickers,
)
from app.market_regime import (
    KODEX200_TICKER,
    KOSPI_ID,
    compute_candidate_excess_return,
    compute_market_context,
    kodex200_return_dates,
)

# POC5-22 — 동일 기간 KODEX200 비교(순수 계산 · 조회 · 연구 모듈 import 없음).
from app.same_period_kodex200 import PERIOD_KEYS as SAME_PERIOD_KEYS
from app.same_period_kodex200 import close_by_date, compare as same_period_compare

# POC2 Cleanup (2026-06-14) — 보조 helper / 상수 / dataclass 는
# market_topn_helpers.py 로 분리 (KS-10 near 해소). 본 파일은 re-export 로 기존
# import 경로 호환을 유지한다.
from app.market_topn_helpers import (  # noqa: F401
    ALLOWED_BASIS,
    ALLOWED_ORDER,
    DAILY_LOOKBACK_DAYS,
    DEFAULT_BASIS,
    DEFAULT_N,
    DEFAULT_ORDER,
    EXCLUSION_REASONS,
    ONE_MONTH_LOOKBACK_DAYS,
    PRODUCT_TAG_TYPES,
    REQUIRED_TABLES,
    SIX_MONTH_LOOKBACK_DAYS,
    THREE_MONTH_LOOKBACK_DAYS,
    THREE_YEAR_LOOKBACK_DAYS,
    TWELVE_MONTH_LOOKBACK_DAYS,
    TopNEntry,
    _build_empty_payload,
    _build_filters_dict,
    _compute_period,
    _empty_exclusion_buckets,
    _empty_filter_exclusion_buckets,
    _latest_date_in_db,
    _latest_refresh_payload,
    _missing_required_tables,
    _PeriodResult,
    classify_etf_tags,
)


def compute_topn(
    *,
    n: int = DEFAULT_N,
    db_path: Path = DEFAULT_DB_PATH,
    asof: Optional[str] = None,
    basis: str = DEFAULT_BASIS,
    order: str = DEFAULT_ORDER,
    exclude_inverse: bool = True,
    exclude_leveraged: bool = True,
    exclude_synthetic: bool = True,
    exclude_futures: bool = True,
    kospi_today_kst: Optional[str] = None,
    market_asof_from_kodex200: bool = False,
    actual_price_dates: bool = False,
    same_period_kodex200: bool = False,
) -> dict:
    """SQLite etf_daily_price 기준 일간 / 1개월 / 3개월 TOP N 산출.

    `kospi_today_kst` — POC3-02D-OPS-03 확정 계약 9. 화면 API 만 넘긴다(KOSPI 최신성 =
    기대 T-1). 없으면 KOSPI 판정은 예전 그대로다(과거 재현 호출부 무변경).

    `market_asof_from_kodex200` — POC5-11(설계자 판정 Q1). PC 화면 API 만 True 를 넘긴다.
    True 면 `market_context.asof`(계약 ⑤ 'KODEX200 기준일')를 판정 · 지속일 · 기준선과 같은
    읽기의 069500 유효 이력 마지막 날짜로 둔다(이력 없으면 None). 기본 False 는 예전 그대로
    (전체 최신일 `asof_iso`) — 최상위 `asof` · 후보 기간 계산 · 다른 호출자 출력은 늘 그대로다.

    `actual_price_dates` — POC5-21(설계자 PLAN 판정 Q1 · Q3). PC 화면 API 만 True 를 넘긴다.
    True 면 기간 dict 에 그 수익률을 계산한 시작 · 끝 저장 행 날짜(`price_start_date` ·
    `price_end_date`)를, `market_context.kodex200` 에 1M · 3M 수익률의 시작 · 끝 행 날짜를 더한다.
    이미 읽은 행에서만 가져온다(추가 조회 없음). 기본 False 는 출력이 예전 그대로다 —
    `basis_end_date` 는 늘 시장 저장 최신일(`asof_iso`)이다.

    `same_period_kodex200` — POC5-22(설계자 PLAN 판정 2026-10-17). PC 화면 API(시장 · 보유 근거)만
    True 를 넘긴다. True 면 후보마다 1개월 · 3개월의 동일 기간 KODEX200 비교(`same_period_kodex200`)를
    더한다 — 그 수익률이 실제로 쓴 A · B 날짜의 KODEX200 종가 · 반올림 전 값으로 뺀 차이(%p). 시장 판정용으로
    이미 읽은 069500 이력을 한 번 정리해 쓴다(추가 조회 없음). 기존 `excess_return` 은 그대로다.

    DB 부재 시 status="missing". DB 가 있어도 가격 데이터 없음/필수 테이블 부재면
    각각 status="empty"/"invalid". 본 함수는 외부 fetch / write 없음 — SQLite read only.

    필터링 순서 (지시문 §3.1, Market Discovery 후보 정제 1차):
    1. SQLite 산출 가능 후보 전체 → 2. 태깅 → 3. exclude 옵션 적용 →
    4. 정렬 → 5. TOP N 자르기 → 6. rank 재부여.
    SQLite 에서 먼저 TOP N 자른 뒤 필터링하는 방식은 금지 (필터 후 결과가 N 미만이
    되는 케이스가 발생).
    """
    t0 = time.perf_counter()
    if basis not in ALLOWED_BASIS:
        basis = DEFAULT_BASIS  # 호출자(API) 가 Literal 로 1차 막지만 안전 fallback.
    if order not in ALLOWED_ORDER:
        order = DEFAULT_ORDER  # 동일하게 안전 fallback.
    filters = _build_filters_dict(
        exclude_inverse, exclude_leveraged, exclude_synthetic, exclude_futures
    )

    if not db_path.exists():
        return _build_empty_payload(
            status="missing",
            n=n,
            elapsed=time.perf_counter() - t0,
            basis=basis,
            order=order,
            error="SQLite DB 파일이 없습니다. 먼저 시장 데이터 갱신을 실행하세요.",
            filters=filters,
        )

    try:
        missing = _missing_required_tables(db_path)
    except sqlite3.Error as e:
        return _build_empty_payload(
            status="invalid",
            n=n,
            elapsed=time.perf_counter() - t0,
            basis=basis,
            order=order,
            error=f"SQLite 구조 확인 실패: {type(e).__name__}: {e}",
            filters=filters,
        )
    if missing:
        return _build_empty_payload(
            status="invalid",
            n=n,
            elapsed=time.perf_counter() - t0,
            basis=basis,
            order=order,
            error=f"SQLite 의 필수 테이블이 누락되었습니다: {missing}",
            filters=filters,
        )

    try:
        asof_iso = asof or _latest_date_in_db(db_path)
    except sqlite3.Error as e:
        return _build_empty_payload(
            status="invalid",
            n=n,
            elapsed=time.perf_counter() - t0,
            basis=basis,
            order=order,
            error=f"SQLite 조회 실패: {type(e).__name__}: {e}",
            filters=filters,
        )

    tickers = list_etf_tickers(db_path)
    universe_count = len(tickers)

    if not asof_iso:
        payload = _build_empty_payload(
            status="empty",
            n=n,
            elapsed=time.perf_counter() - t0,
            basis=basis,
            order=order,
            error="가격 데이터가 SQLite 에 아직 없습니다. 최신 시장 데이터 갱신을 실행하세요.",
            db_path=db_path,
            filters=filters,
        )
        payload["universe_count"] = universe_count
        return payload

    price_success = 0
    price_fail = 0

    period_specs = [
        ("daily", DAILY_LOOKBACK_DAYS),
        ("one_month", ONE_MONTH_LOOKBACK_DAYS),
        ("three_month", THREE_MONTH_LOOKBACK_DAYS),
        # 2026-06-08 — 표시 전용 신규 기간. 신규 상장 / 시계열 미적재 ETF 는
        # exclusions 에 missing_*** 로 카운트되고 응답에서 None 으로 노출된다.
        ("six_month", SIX_MONTH_LOOKBACK_DAYS),
        ("twelve_month", TWELVE_MONTH_LOOKBACK_DAYS),
        ("three_year", THREE_YEAR_LOOKBACK_DAYS),
    ]
    # 기존 호환용 — 각 기간별 (ticker, return_pct, base_date, tags) 산출 가능 후보.
    buckets: dict[str, list[tuple[str, float, str, list[str]]]] = {
        label: [] for label, _ in period_specs
    }
    # 통합 후보 — ticker 별 3 기간 결과 + 태그. 결측 기간은 None 으로 두고
    # 0% 보정하지 않는다 (지시문 §6).
    per_ticker_returns: dict[str, dict[str, Optional[dict[str, object]]]] = {}
    # POC5-22 — 동일 기간 비교용 반올림 전 수익률 · 실제 A · B(flag 일 때만 · 1개월 · 3개월).
    raw_periods: dict[str, dict[str, _PeriodResult]] = {}
    per_ticker_tags: dict[str, list[str]] = {}
    exclusions = _empty_exclusion_buckets()

    # 2026-06-08 perf — universe 전체 ticker→name 매핑을 1 쿼리로 prefetch
    # (이전: ticker 마다 SQLite 1 호출 = 1000+ 회). row 없는 ticker 는 None.
    name_cache: dict[str, Optional[str]] = get_etf_name_map(db_path=db_path)

    def _name_of(tk: str) -> Optional[str]:
        # fallback: prefetch dict 에 없는 ticker (e.g. master 미등록) 는 단건 조회.
        if tk in name_cache:
            return name_cache[tk]
        name_cache[tk] = get_etf_name(tk, db_path=db_path)
        return name_cache[tk]

    for tk in tickers:
        history = fetch_price_history(tk, db_path=db_path)
        if not history:
            price_fail += 1
            for label, _ in period_specs:
                exclusions[label]["missing_latest_price"] += 1
            continue
        price_success += 1
        tags = classify_etf_tags(_name_of(tk))
        per_ticker_tags[tk] = tags
        per_ticker_returns[tk] = {label: None for label, _ in period_specs}
        for label, lookback in period_specs:
            r = _compute_period(history, asof_iso, lookback)
            if r.exclusion_reason is not None:
                exclusions[label][r.exclusion_reason] = (
                    exclusions[label].get(r.exclusion_reason, 0) + 1
                )
                continue
            assert r.return_pct is not None and r.base_date is not None
            buckets[label].append((tk, r.return_pct, r.base_date, tags))
            period_out: dict[str, object] = {
                "return_pct": round(r.return_pct, 4),
                "basis_start_date": r.base_date,
                "basis_end_date": asof_iso,
            }
            if actual_price_dates:
                period_out["price_start_date"] = r.base_date
                period_out["price_end_date"] = r.end_date
            per_ticker_returns[tk][label] = period_out
            if same_period_kodex200 and label in SAME_PERIOD_KEYS:
                raw_periods.setdefault(tk, {})[label] = r

    # exclude 옵션 → 활성 필터 태그
    exclude_tags: set[str] = set()
    if exclude_inverse:
        exclude_tags.add("inverse")
    if exclude_leveraged:
        exclude_tags.add("leveraged")
    if exclude_synthetic:
        exclude_tags.add("synthetic")
    if exclude_futures:
        exclude_tags.add("futures")

    filter_exclusions = _empty_filter_exclusion_buckets()

    def _topn_with_filter(
        items: list[tuple[str, float, str, list[str]]], period_label: str
    ) -> list[dict]:
        """filter-before-limit (지시문 §3.1) — 필터 → 정렬 → 자르기 → rank 재부여.

        제외된 ETF 는 filter_exclusions[period_label][tag] 에 활성 필터 태그별로 가산.
        한 ETF 가 여러 태그를 갖고 활성 필터가 그 태그 중 둘 이상이면 카운트가 각각 +1.
        """
        kept: list[tuple[str, float, str, list[str]]] = []
        for tk, ret_pct, base_date, tags in items:
            matched = exclude_tags.intersection(tags)
            if matched:
                for t in matched:
                    filter_exclusions[period_label][t] += 1
                continue
            kept.append((tk, ret_pct, base_date, tags))
        kept.sort(key=lambda x: x[1], reverse=True)
        out: list[dict] = []
        for rank, (tk, ret_pct, base_date, tags) in enumerate(kept[:n], start=1):
            entry = TopNEntry(
                rank=rank,
                ticker=tk,
                name=_name_of(tk),
                return_pct=ret_pct,
                basis_start_date=base_date,
                basis_end_date=asof_iso,
            ).to_dict()
            entry["tags"] = list(tags)
            out.append(entry)
        return out

    # ── 통합 후보 테이블 (지시문 §5 / §6) ────────────────────────────────
    # 1. 필터링: ticker 별 태그가 활성 필터와 매치하면 제외 (각 태그별 +1 카운트).
    # 2. selected basis 가 None 인 후보 (선택된 기간 수익률 부재) 제외.
    # 3. selected basis 의 return_pct 내림차순 정렬.
    # 4. TOP N 자르기.
    # 5. rank 1 부터 재부여.
    candidate_filter_exclusions: dict[str, int] = {k: 0 for k in PRODUCT_TAG_TYPES}

    kept_candidates: list[tuple[str, list[str], dict[str, Optional[dict]]]] = []
    for tk, returns in per_ticker_returns.items():
        tags = per_ticker_tags.get(tk, [])
        matched = exclude_tags.intersection(tags)
        if matched:
            for t in matched:
                candidate_filter_exclusions[t] += 1
            continue
        kept_candidates.append((tk, tags, returns))

    def _basis_return_pct(item):
        sel = item[2].get(basis)
        if sel is None:
            return None
        return sel["return_pct"]

    # selected basis 수익률이 없는 후보 제외 (지시문 §6 step 5).
    kept_candidates = [c for c in kept_candidates if _basis_return_pct(c) is not None]
    # 정렬: desc → 내림차순 (TOP N), asc → 오름차순 (BOTTOM N).
    # 전체 SQLite 후보 기준 정렬 — 로컬 reverse 가 아니다 (지시문 §3.2 / AC-13).
    kept_candidates.sort(key=lambda c: _basis_return_pct(c), reverse=(order == "desc"))

    # ── Market Regime & Benchmark Context (지시문 §6~§9, 2026-05-22) ────
    # KODEX200 history 는 etf_daily_price 에서, KOSPI 는 market_benchmark_daily_price
    # 에서. 둘 다 SQLite read-only — 외부 fetch 없음.
    kodex200_history = fetch_price_history(KODEX200_TICKER, db_path=db_path)
    kospi_history = fetch_benchmark_history(KOSPI_ID, db_path=db_path)
    market_context = compute_market_context(
        asof=(
            (kodex200_history[-1][0] if kodex200_history else None)
            if market_asof_from_kodex200
            else asof_iso
        ),
        kodex200_history=kodex200_history,
        kospi_history=kospi_history if kospi_history else None,
        kospi_today_kst=kospi_today_kst,
    )
    # 2026-08-03 POC3-06 §6.2 — KOSPI 관찰값(일간·1년·52주 고점 대비) additive 병합
    # + 국면 지속 거래일 수. 기존 저장 series read 만 사용(신규 source·DB 0).
    from app.market_regime import (
        compute_kospi_position_metrics,
        compute_regime_streak,
    )

    _kospi_ctx = market_context.get("kospi")
    if (
        isinstance(_kospi_ctx, dict)
        and _kospi_ctx.get("status") == "ok"
        and kospi_history
    ):
        _pos = compute_kospi_position_metrics(kospi_history)
        _kospi_ctx["daily_return_pct"] = _pos.get("daily_return_pct")
        _kospi_ctx["return_1y_pct"] = _pos.get("return_1y_pct")
        _kospi_ctx["high_52w_gap_pct"] = _pos.get("high_52w_gap_pct")
        _kospi_ctx["as_of_date"] = _pos.get("as_of_date")
    if isinstance(market_context.get("kodex200"), dict) and (
        market_context["kodex200"].get("status") == "ok"
    ):
        market_context["regime_streak"] = compute_regime_streak(kodex200_history)
        if actual_price_dates:
            # POC5-21 — 같은 069500 이력 · 같은 행 선택(kodex200_return_dates).
            market_context["kodex200"].update(kodex200_return_dates(kodex200_history))
    # 후보 excess_return 계산용 benchmark 수익률 추출 (없으면 None 으로 노출).
    _kodex = market_context.get("kodex200") or {}
    _kospi = market_context.get("kospi") or {}
    bench_kodex_1m = (
        _kodex.get("return_1m_pct") if _kodex.get("status") == "ok" else None
    )
    bench_kodex_3m = (
        _kodex.get("return_3m_pct") if _kodex.get("status") == "ok" else None
    )
    bench_kospi_1m = (
        _kospi.get("return_1m_pct") if _kospi.get("status") == "ok" else None
    )
    bench_kospi_3m = (
        _kospi.get("return_3m_pct") if _kospi.get("status") == "ok" else None
    )

    # POC5-22 — 이미 읽은 069500 이력을 {날짜: 종가}로 한 번 정리(같은 날짜만 · 후보마다 다시 읽지 않음).
    kodex200_close = close_by_date(kodex200_history) if same_period_kodex200 else {}

    candidates_out: list[dict] = []
    for rank, (tk, tags, returns) in enumerate(kept_candidates[:n], start=1):
        sel = returns[basis]
        cand_1m = (returns.get("one_month") or {}).get("return_pct")
        cand_3m = (returns.get("three_month") or {}).get("return_pct")
        candidates_out.append(
            {
                "rank": rank,
                "ticker": tk,
                "name": _name_of(tk),
                "tags": list(tags),
                "selected_return_pct": sel["return_pct"] if sel else None,
                "selected_basis_start_date": (sel["basis_start_date"] if sel else None),
                "selected_basis_end_date": (sel["basis_end_date"] if sel else None),
                "returns": returns,
                "excess_return": compute_candidate_excess_return(
                    candidate_1m_pct=cand_1m,
                    candidate_3m_pct=cand_3m,
                    kodex200_1m_pct=bench_kodex_1m,
                    kodex200_3m_pct=bench_kodex_3m,
                    kospi_1m_pct=bench_kospi_1m,
                    kospi_3m_pct=bench_kospi_3m,
                ),
            }
        )
        if same_period_kodex200:
            raw = raw_periods.get(tk, {})
            candidates_out[-1]["same_period_kodex200"] = {
                label: same_period_compare(
                    raw[label].return_pct if label in raw else None,
                    raw[label].base_date if label in raw else None,
                    raw[label].end_date if label in raw else None,
                    kodex200_close,
                )
                for label in SAME_PERIOD_KEYS
            }

    elapsed = time.perf_counter() - t0
    return {
        "status": "ok",
        "error": None,
        "asof": asof_iso,
        "source": "SQLite (FinanceDataReader 수집)",
        "n": n,
        "basis": basis,
        "order": order,
        "universe_count": universe_count,
        "price_success_count": price_success,
        "price_fail_count": price_fail,
        "latest_refresh": _latest_refresh_payload(db_path),
        "runtime_seconds": round(elapsed, 3),
        # 통합 후보 테이블 (frontend 기본 렌더 소스).
        "candidates": candidates_out,
        # 호환용 — 기존 분리 테이블 응답도 유지.
        "daily_topn": _topn_with_filter(buckets["daily"], "daily"),
        "one_month_topn": _topn_with_filter(buckets["one_month"], "one_month"),
        "three_month_topn": _topn_with_filter(buckets["three_month"], "three_month"),
        "period_exclusions": exclusions,
        "filter_exclusions": filter_exclusions,
        "filters": filters,
        "candidate_filter_exclusions": candidate_filter_exclusions,
        "topn_caveat": (
            "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능 (query parameter `n`)."
        ),
        "market_context": market_context,
    }
