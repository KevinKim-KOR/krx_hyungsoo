"""P205-STEP5E: Dynamic Universe Schedule Builder.

전체 기간의 rebalance date를 미리 추출하고,
각 날짜 기준으로 scanner를 1회씩 실행하여 schedule을 사전 계산한다.
Tune/Backtest는 이 schedule에서 lookup만 한다.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.scanner.config import (
    CANDIDATE_POOL_CONFIG,
    SCANNER_MODE,
    SCANNER_VERSION,
    SELECTOR_CONFIG,
    get_active_features,
)

logger = logging.getLogger("app.scanner.schedule")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEDULE_JSON = (
    PROJECT_ROOT / "reports" / "tuning" / "dynamic_universe_schedule_latest.json"
)
SCHEDULE_CSV = (
    PROJECT_ROOT / "reports" / "tuning" / "dynamic_universe_schedule_latest.csv"
)


def _compute_cache_key(
    start: date,
    end: date,
    rebalance_rule: Dict[str, Any],
) -> str:
    """schedule cache key (deterministic)."""
    raw = json.dumps(
        {
            "scanner_mode": SCANNER_MODE,
            "scanner_version": SCANNER_VERSION,
            "pool_config": CANDIDATE_POOL_CONFIG,
            "active_features": [
                {
                    "key": f["key"],
                    "weight": f["weight"],
                    "lookback": f["lookback"],
                }
                for f in get_active_features()
            ],
            "selector": {
                "top_n": SELECTOR_CONFIG["top_n"],
                "ranking_formula": SELECTOR_CONFIG["ranking_formula"],
            },
            "rebalance_rule": rebalance_rule,
            "start": str(start),
            "end": str(end),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_rebalance_dates(
    trading_days: List[date],
    rebalance_rule: Dict[str, Any],
) -> List[date]:
    """거래일 목록에서 rebalance date를 추출한다."""
    freq = rebalance_rule.get("frequency", "M")
    dates: List[date] = []
    prev_month = None
    prev_week = None

    for i, d in enumerate(trading_days):
        should = False
        if i == 0:
            should = True
        elif freq == "M":
            should = prev_month is not None and d.month != prev_month
        elif freq == "W":
            cur_week = d.isocalendar()[1]
            should = prev_week is not None and cur_week != prev_week
        else:
            should = True

        if should:
            dates.append(d)
        prev_month = d.month
        prev_week = d.isocalendar()[1]

    return dates


def _run_scanner_for_date(
    as_of: date,
    ohlcv_full: Dict[str, pd.DataFrame],
    ticker_name_map: Dict[str, str],
) -> Dict[str, Any]:
    """특정 날짜 기준으로 scanner 로직을 실행한다.

    미래 데이터를 사용하지 않도록 as_of까지만 데이터를 잘라 사용한다.
    """
    from app.scanner.config import get_active_features
    from app.scanner.feature_provider import compute_feature_matrix
    from app.scanner.snapshot import compute_snapshot_sha256

    active_features = get_active_features()
    min_listing = CANDIDATE_POOL_CONFIG.get("min_listing_days", 180)
    min_vol = CANDIDATE_POOL_CONFIG.get("min_avg_volume_20d", 50000)
    min_price = CANDIDATE_POOL_CONFIG.get("min_price", 1000)
    top_n = SELECTOR_CONFIG["top_n"]

    # as_of 기준으로 데이터 자르기
    cutoff = pd.Timestamp(as_of)
    ohlcv_cut: Dict[str, pd.DataFrame] = {}
    for ticker, df in ohlcv_full.items():
        cut = df[df.index <= cutoff]
        if len(cut) >= min_listing:
            ohlcv_cut[ticker] = cut

    # pre-filter
    eligible = []
    for ticker, df in ohlcv_cut.items():
        if len(df) < min_listing:
            continue
        if "volume" in df.columns:
            recent_vol = df["volume"].tail(5)
            if (recent_vol == 0).all():
                continue
            avg_vol = df["volume"].tail(20).mean()
            if avg_vol < min_vol:
                continue
        if "close" in df.columns:
            if df["close"].iloc[-1] < min_price:
                continue
        eligible.append(ticker)

    if not eligible:
        return {
            "rebalance_date": str(as_of),
            "selected_count": 0,
            "selected_tickers": [],
            "snapshot_id": f"sched_{as_of}_empty",
            "snapshot_sha256": "",
            "selection_status": "no_eligible",
            "scoring_eligible": 0,
            "candidate_pool_size": len(ohlcv_cut),
            "fallback_applied": False,
        }

    # feature matrix
    fm = compute_feature_matrix(
        tickers=eligible,
        ohlcv_cache=ohlcv_cut,
        features=active_features,
        ticker_name_map=ticker_name_map,
    )

    if fm.empty:
        return {
            "rebalance_date": str(as_of),
            "selected_count": 0,
            "selected_tickers": [],
            "snapshot_id": f"sched_{as_of}_empty",
            "snapshot_sha256": "",
            "selection_status": "no_features",
            "scoring_eligible": 0,
            "candidate_pool_size": len(ohlcv_cut),
            "fallback_applied": False,
        }

    # scoring
    norm_cols = [f"{f['key']}_norm" for f in active_features]
    weights = [f["weight"] for f in active_features]

    fm["_eligible"] = True
    for nc in norm_cols:
        if nc in fm.columns:
            fm.loc[fm[nc].isna(), "_eligible"] = False

    scored = fm[fm["_eligible"]].copy()
    if scored.empty:
        return {
            "rebalance_date": str(as_of),
            "selected_count": 0,
            "selected_tickers": [],
            "snapshot_id": f"sched_{as_of}_empty",
            "snapshot_sha256": "",
            "selection_status": "no_scorable",
            "scoring_eligible": 0,
            "candidate_pool_size": len(ohlcv_cut),
            "fallback_applied": False,
        }

    scored["_score"] = 0.0
    for nc, w in zip(norm_cols, weights):
        if nc in scored.columns:
            scored["_score"] += w * scored[nc].fillna(0)

    scored = scored.sort_values(["_score", "ticker"], ascending=[False, True])
    selected = scored.head(top_n)["ticker"].tolist()

    snap_sha = compute_snapshot_sha256(
        scanner_mode=SCANNER_MODE,
        scanner_version=SCANNER_VERSION,
        candidate_pool_source=CANDIDATE_POOL_CONFIG.get("source", "krx_etf_list"),
        active_features=active_features,
        pre_filters={
            "min_listing_days": min_listing,
            "min_avg_volume_20d": min_vol,
            "min_price": min_price,
        },
        hard_exclusions={
            "exclude_inverse": True,
            "exclude_leveraged": True,
            "exclude_synthetic": True,
        },
        eligible_tickers=selected,
    )

    return {
        "rebalance_date": str(as_of),
        "selected_count": len(selected),
        "selected_tickers": selected,
        "snapshot_id": f"sched_{as_of}_{snap_sha[:8]}",
        "snapshot_sha256": snap_sha,
        "selection_status": "ok" if len(selected) >= 5 else "insufficient",
        "scoring_eligible": len(scored),
        "candidate_pool_size": len(ohlcv_cut),
        "fallback_applied": False,
    }


def _write_schedule_snapshot(schedule_data: dict) -> str:
    """실행별 고유 schedule snapshot 파일을 생성한다."""
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    from datetime import timezone as _tz

    _kst = _tz(_td(hours=9))
    _ts = _dt.now(_kst).strftime("%Y%m%d_%H%M%S")
    snap_json = SCHEDULE_JSON.parent / f"dynamic_universe_schedule_{_ts}.json"
    snap_json.write_text(
        json.dumps(schedule_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    rel_path = str(snap_json.relative_to(PROJECT_ROOT))
    logger.info(f"[SCHEDULE] snapshot: {snap_json.name}")
    return rel_path


def build_dynamic_schedule(
    start: date,
    end: date,
    rebalance_rule: Dict[str, Any],
    ohlcv_full: Dict[str, pd.DataFrame],
    ticker_name_map: Dict[str, str],
) -> Dict[str, Any]:
    """전체 기간 rebalance schedule을 사전 계산한다.

    Returns:
        schedule dict with cache_key, entries, and lookup table
    """
    cache_key = _compute_cache_key(start, end, rebalance_rule)

    # 캐시 확인
    if SCHEDULE_JSON.exists():
        try:
            cached = json.loads(SCHEDULE_JSON.read_text(encoding="utf-8"))
            if cached.get("cache_key") == cache_key:
                logger.info("[SCHEDULE] 캐시 히트 — 기존 schedule 재사용")
                # cache hit에서도 고유 snapshot 생성
                snap_path = _write_schedule_snapshot(cached)
                return {
                    **cached,
                    "cache_hit": True,
                    "schedule_snapshot_path": snap_path,
                }
        except Exception:
            pass

    logger.info(f"[SCHEDULE] 사전 계산 시작: {start} ~ {end}")

    # 거래일 추출 (모든 ticker의 날짜 합집합)
    all_dates = set()
    for df in ohlcv_full.values():
        for d in df.index:
            if isinstance(d, pd.Timestamp):
                all_dates.add(d.date())
            else:
                all_dates.add(d)

    trading_days = sorted(d for d in all_dates if start <= d <= end)

    rebalance_dates = _extract_rebalance_dates(trading_days, rebalance_rule)

    logger.info(f"[SCHEDULE] rebalance dates: {len(rebalance_dates)}개")

    entries = []
    for i, rd in enumerate(rebalance_dates):
        entry = _run_scanner_for_date(rd, ohlcv_full, ticker_name_map)
        entries.append(entry)
        if (i + 1) % 5 == 0:
            logger.info(f"[SCHEDULE] 진행: {i + 1}/{len(rebalance_dates)}")

    # lookup table: date → selected_tickers
    lookup = {}
    for e in entries:
        lookup[e["rebalance_date"]] = e["selected_tickers"]

    schedule = {
        "cache_key": cache_key,
        "cache_hit": False,
        "scanner_mode": SCANNER_MODE,
        "scanner_version": SCANNER_VERSION,
        "start_date": str(start),
        "end_date": str(end),
        "rebalance_count": len(entries),
        "entries": entries,
    }

    # 저장
    SCHEDULE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_JSON.write_text(
        json.dumps(schedule, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # CSV
    if entries:
        fieldnames = [
            "rebalance_date",
            "selected_count",
            "selected_tickers",
            "snapshot_id",
            "snapshot_sha256",
            "selection_status",
            "scoring_eligible",
            "candidate_pool_size",
            "fallback_applied",
        ]
        with open(SCHEDULE_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for e in entries:
                row = dict(e)
                row["selected_tickers"] = "|".join(e["selected_tickers"])
                writer.writerow(row)

    snap_path = _write_schedule_snapshot(schedule)
    schedule["schedule_snapshot_path"] = snap_path

    logger.info(
        f"[SCHEDULE] 완료: {len(entries)}개 rebalance snapshot" f" (path: {snap_path})"
    )

    return schedule


def make_universe_resolver(
    schedule: Dict[str, Any],
) -> "callable":
    """schedule에서 date → selected_tickers lookup 함수를 생성."""
    lookup: Dict[str, List[str]] = {}
    last_tickers: List[str] = []

    for e in schedule.get("entries", []):
        tickers = e.get("selected_tickers", [])
        if tickers:
            last_tickers = tickers
        lookup[e["rebalance_date"]] = tickers

    def resolver(d: date) -> Optional[List[str]]:
        key = str(d)
        if key in lookup:
            return lookup[key]
        # 가장 가까운 이전 날짜 찾기
        sorted_dates = sorted(lookup.keys())
        for sd in reversed(sorted_dates):
            if sd <= key:
                return lookup[sd]
        return last_tickers or None

    return resolver
