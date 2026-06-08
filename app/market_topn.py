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
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.market_benchmark_store import fetch_benchmark_history
from app.market_data_store import (
    DEFAULT_DB_PATH,
    fetch_price_history,
    get_etf_name,
    latest_refresh_log,
    list_etf_tickers,
)
from app.market_regime import (
    KODEX200_TICKER,
    KOSPI_ID,
    compute_candidate_excess_return,
    compute_market_context,
)

REQUIRED_TABLES = ("etf_master", "etf_daily_price", "market_refresh_log")


def _missing_required_tables(db_path: Path) -> list[str]:
    """raw sqlite3 로 필수 테이블 존재 여부 확인 — init_db 자동 호출 회피.

    init_db 를 거치면 모든 테이블이 자동 생성되어 invalid 분기를 진입할 수 없다.
    본 함수는 sqlite_master 만 조회한다 (sqlite3.connect 는 빈 파일을 만들 수 있지만
    compute_topn 진입 직전에 path.exists() 가 이미 통과한 상태라 안전).
    """
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN (?, ?, ?)",
            REQUIRED_TABLES,
        )
        present = {row[0] for row in cur.fetchall()}
    return [t for t in REQUIRED_TABLES if t not in present]


DEFAULT_N = 10
DAILY_LOOKBACK_DAYS = 1
ONE_MONTH_LOOKBACK_DAYS = 30
THREE_MONTH_LOOKBACK_DAYS = 90
# 2026-06-08 — UI 요청 (6m/12m/1y/3y 컬럼 추가). 시계열이 없으면 None 으로
# 정직 표시. 1m=30 패턴 유지 (영업일 기준 아니라 캘린더 일수).
SIX_MONTH_LOOKBACK_DAYS = 180
TWELVE_MONTH_LOOKBACK_DAYS = 365
THREE_YEAR_LOOKBACK_DAYS = 365 * 3

# 2026-05-18 통합 후보 테이블 1차 — 조회 기준 (basis).
# 신규 6m/12m/3y 는 표시 전용 — 정렬 기준에서 제외 (사용자 정렬 요청 없음).
ALLOWED_BASIS = ("daily", "one_month", "three_month")
DEFAULT_BASIS = "one_month"

# 2026-05-19 Grid 사용성 FIX — 정렬 방향 (order).
# desc 가 기본 (전체 후보 기준 TOP N), asc 는 전체 후보 기준 BOTTOM N.
# 둘 다 SQLite 산출 가능 후보 전체에 대한 정렬이며, 프론트 로컬 reverse 가 아니다.
ALLOWED_ORDER = ("desc", "asc")
DEFAULT_ORDER = "desc"

EXCLUSION_REASONS = (
    "missing_latest_price",
    "missing_base_price",
    "insufficient_history",
    "invalid_price",
    "stale_price",
)

# 2026-05-18 Market Discovery 후보 정제 1차:
# ETF 이름 기반 1차 태깅 — 인버스 / 레버리지 / 합성 / 선물형.
# 한 ETF 에 여러 태그가 붙을 수 있다 (예: "차이나전기차레버리지(합성)" → leveraged + synthetic).
PRODUCT_TAG_TYPES = ("inverse", "leveraged", "synthetic", "futures")


def classify_etf_tags(name: Optional[str]) -> list[str]:
    """ETF 이름에서 1차 상품 태그를 추출 (지시문 §4).

    - "인버스" → inverse
    - "레버리지" / "2X" / "2배" → leveraged
    - "합성" → synthetic
    - "선물" → futures
    이름이 비어있으면 빈 리스트.
    금현물 / 배당 / 반도체 / AI / 조선 / 방산 / 원자재 등은 이 단계에서 분류하지 않는다.
    """
    if not name:
        return []
    tags: list[str] = []
    if "인버스" in name:
        tags.append("inverse")
    # leveraged: "레버리지" 또는 "2X" (대/소문자 무시) 또는 "2배"
    name_upper = name.upper()
    if ("레버리지" in name) or ("2X" in name_upper) or ("2배" in name):
        tags.append("leveraged")
    if "합성" in name:
        tags.append("synthetic")
    if "선물" in name:
        tags.append("futures")
    return tags


def _empty_filter_exclusion_buckets() -> dict[str, dict[str, int]]:
    return {
        "daily": {k: 0 for k in PRODUCT_TAG_TYPES},
        "one_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "three_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        # 2026-06-08 — 신규 기간 (표시 전용, 정렬 X). dict 동기화.
        "six_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "twelve_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "three_year": {k: 0 for k in PRODUCT_TAG_TYPES},
    }


@dataclass
class TopNEntry:
    rank: int
    ticker: str
    name: Optional[str]
    return_pct: float
    basis_start_date: str
    basis_end_date: str

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "ticker": self.ticker,
            "name": self.name,
            "return_pct": round(self.return_pct, 4),
            "basis_start_date": self.basis_start_date,
            "basis_end_date": self.basis_end_date,
        }


@dataclass
class _PeriodResult:
    return_pct: Optional[float]
    base_date: Optional[str]
    exclusion_reason: Optional[str]  # None if success


def _compute_period(
    history: list[tuple[str, float]],
    asof_iso: str,
    lookback_days: int,
) -> _PeriodResult:
    """단일 ticker 의 시계열에서 한 기간 수익률 산출.

    결측은 0% 로 보정하지 않고 exclusion_reason 으로 분류한다.
    """
    if not history:
        return _PeriodResult(None, None, "missing_latest_price")
    if len(history) < 2:
        return _PeriodResult(None, None, "insufficient_history")

    latest_idx = len(history) - 1
    _latest_date, latest_close = history[latest_idx]
    if latest_close <= 0:
        return _PeriodResult(None, None, "invalid_price")

    if lookback_days == DAILY_LOOKBACK_DAYS:
        base_idx: Optional[int] = latest_idx - 1
    else:
        try:
            asof_d = date.fromisoformat(asof_iso)
        except ValueError:
            return _PeriodResult(None, None, "invalid_price")
        target = asof_d - timedelta(days=lookback_days)
        target_iso = target.isoformat()
        base_idx = None
        for i, (d_iso, _close) in enumerate(history):
            if d_iso >= target_iso:
                base_idx = i
                break
        if base_idx is None:
            return _PeriodResult(None, None, "missing_base_price")
        if base_idx == latest_idx:
            return _PeriodResult(None, None, "insufficient_history")

    base_date, base_close = history[base_idx]
    if base_close <= 0:
        return _PeriodResult(None, None, "invalid_price")
    ret_pct = (latest_close / base_close - 1.0) * 100.0
    return _PeriodResult(return_pct=ret_pct, base_date=base_date, exclusion_reason=None)


def _latest_date_in_db(db_path: Path) -> Optional[str]:
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute("SELECT MAX(date) FROM etf_daily_price")
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def _empty_exclusion_buckets() -> dict[str, dict[str, int]]:
    return {
        "daily": {k: 0 for k in EXCLUSION_REASONS},
        "one_month": {k: 0 for k in EXCLUSION_REASONS},
        "three_month": {k: 0 for k in EXCLUSION_REASONS},
        # 2026-06-08 — 신규 기간 (표시 전용, 정렬 X). dict 동기화.
        "six_month": {k: 0 for k in EXCLUSION_REASONS},
        "twelve_month": {k: 0 for k in EXCLUSION_REASONS},
        "three_year": {k: 0 for k in EXCLUSION_REASONS},
    }


def _latest_refresh_payload(db_path: Path) -> Optional[dict]:
    log = latest_refresh_log(db_path=db_path)
    if not log:
        return None
    return {
        "refresh_id": log["run_id"],
        "source": log["source"],
        "asof": log["asof"],
        "attempted_count": log["attempted_count"],
        "success_count": log["success_count"],
        "fail_count": log["fail_count"],
        "runtime_seconds": log["runtime_seconds"],
        "error_summary": log["error_summary"],
        "created_at": log["created_at"],
    }


def _build_filters_dict(
    exclude_inverse: bool,
    exclude_leveraged: bool,
    exclude_synthetic: bool,
    exclude_futures: bool,
) -> dict[str, bool]:
    return {
        "exclude_inverse": exclude_inverse,
        "exclude_leveraged": exclude_leveraged,
        "exclude_synthetic": exclude_synthetic,
        "exclude_futures": exclude_futures,
    }


def _build_empty_payload(
    *,
    status: str,
    n: int,
    elapsed: float,
    basis: str = DEFAULT_BASIS,
    order: str = DEFAULT_ORDER,
    error: Optional[str] = None,
    db_path: Optional[Path] = None,
    filters: Optional[dict[str, bool]] = None,
) -> dict:
    latest_refresh = None
    if db_path is not None and status in ("ok", "empty"):
        try:
            latest_refresh = _latest_refresh_payload(db_path)
        except sqlite3.Error:
            latest_refresh = None
    return {
        "status": status,
        "error": error,
        "asof": None,
        "source": "SQLite (FinanceDataReader 수집)",
        "n": n,
        "basis": basis,
        "order": order,
        "universe_count": 0,
        "price_success_count": 0,
        "price_fail_count": 0,
        "latest_refresh": latest_refresh,
        "runtime_seconds": round(elapsed, 3),
        "candidates": [],
        "daily_topn": [],
        "one_month_topn": [],
        "three_month_topn": [],
        "period_exclusions": _empty_exclusion_buckets(),
        "filter_exclusions": _empty_filter_exclusion_buckets(),
        "filters": filters or _build_filters_dict(True, True, True, True),
        "topn_caveat": (
            "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능 (query parameter `n`)."
        ),
        "market_context": None,
    }


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
) -> dict:
    """SQLite etf_daily_price 기준 일간 / 1개월 / 3개월 TOP N 산출.

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
    per_ticker_tags: dict[str, list[str]] = {}
    exclusions = _empty_exclusion_buckets()

    # ticker 별 이름 캐싱 — get_etf_name 반복 호출 회피.
    name_cache: dict[str, Optional[str]] = {}

    def _name_of(tk: str) -> Optional[str]:
        if tk not in name_cache:
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
            per_ticker_returns[tk][label] = {
                "return_pct": round(r.return_pct, 4),
                "basis_start_date": r.base_date,
                "basis_end_date": asof_iso,
            }

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
        asof=asof_iso,
        kodex200_history=kodex200_history,
        kospi_history=kospi_history if kospi_history else None,
    )
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
