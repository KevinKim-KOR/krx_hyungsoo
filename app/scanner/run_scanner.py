#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/scanner/run_scanner.py — 다이나믹 유니버스 스캐너 실행기 (P205-STEP5B)

실행:
  python -m app.scanner.run_scanner

산출물:
  reports/tuning/universe_snapshot_latest.json
  reports/tuning/universe_feature_matrix_latest.csv
  reports/tuning/dynamic_scanner_smoke_result.json

기존 Tune/Backtest/UI/Objective/Promotion 에 영향 없음.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeout,
)
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.scanner")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 산출물 경로
OUTPUT_DIR = PROJECT_ROOT / "reports" / "tuning"
SNAPSHOT_PATH = OUTPUT_DIR / "universe_snapshot_latest.json"
FEATURE_MATRIX_PATH = OUTPUT_DIR / "universe_feature_matrix_latest.csv"
SMOKE_RESULT_PATH = OUTPUT_DIR / "dynamic_scanner_smoke_result.json"

# 6개월 feature(lookback=120)를 안정 산출하려면
# 달력 365일 이상의 OHLCV가 필요 (거래일 ~245일)
OHLCV_CALENDAR_DAYS = 365

# 종목별 데이터 수집 타임아웃 (초)
TICKER_TIMEOUT_SEC = 10


def _atomic_write_json(path: Path, data: dict) -> None:
    """Atomic JSON write."""
    tmp = path.parent / f"{path.name}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def run_scanner() -> dict:
    """
    다이나믹 유니버스 스캐너를 실행하고 산출물을 생성한다.

    Returns:
        smoke_result dict
    """
    logger.info("=" * 60)
    logger.info("P205-STEP5B 다이나믹 유니버스 스캐너 실행")
    logger.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    errors: list = []
    smoke = {
        "result": "FAIL",
        "candidate_pool_built": False,
        "feature_matrix_built": False,
        "snapshot_written": False,
        "eligible_count": 0,
        "feature_columns_complete": False,
        "errors": errors,
    }

    # ── 1. Config & Imports ──
    from app.scanner.config import (
        CANDIDATE_POOL_CONFIG,
        MAX_NEW_ENTRIES_PER_REFRESH,
        MIN_OVERLAP_RATIO,
        REFRESH_FREQUENCY,
        SCANNER_MODE,
        SCANNER_VERSION,
        get_active_features,
        get_disabled_features,
    )
    from app.scanner.candidate_pool import (
        build_candidate_pool,
        fetch_krx_etf_list,
    )

    # ── 2. ETF 원본 목록 크기 ──
    try:
        etf_list = fetch_krx_etf_list()
        total_pool_size = len(etf_list)
    except Exception as exc:
        errors.append(f"ETF 목록 수집 실패: {exc}")
        total_pool_size = 0

    # ── 3. Candidate Pool (이름 필터 + listing_days) ──
    try:
        eligible, ticker_name_map, excluded = build_candidate_pool(
            CANDIDATE_POOL_CONFIG
        )
        smoke["candidate_pool_built"] = True
        smoke["eligible_count"] = len(eligible)
        logger.info(f"[POOL] 적격 후보: {len(eligible)}, " f"제외: {len(excluded)}")
    except Exception as exc:
        errors.append(f"Candidate pool 생성 실패: {exc}")
        traceback.print_exc()
        _atomic_write_json(SMOKE_RESULT_PATH, smoke)
        return smoke

    if not eligible:
        errors.append("적격 후보 0건 — 스캐너 중단")
        _atomic_write_json(SMOKE_RESULT_PATH, smoke)
        return smoke

    # ── 4. OHLCV 데이터 수집 ──
    from app.backtest.infra.data_loader import (
        load_ohlcv_cached,
    )

    today = date.today()
    lookback_start = today - timedelta(days=OHLCV_CALENDAR_DAYS)
    lookback_end = today - timedelta(days=1)

    ohlcv_cache: dict = {}
    data_failed: list = []

    def _fetch_one(t: str):
        return load_ohlcv_cached(
            t,
            lookback_start,
            lookback_end,
            data_source="fdr",
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        for i, ticker in enumerate(eligible, 1):
            try:
                future = pool.submit(_fetch_one, ticker)
                df = future.result(timeout=TICKER_TIMEOUT_SEC)
                if df is not None and not df.empty:
                    if isinstance(df.index, pd.MultiIndex):
                        df = df.xs(
                            ticker,
                            level="code",
                            drop_level=True,
                        )
                    ohlcv_cache[ticker] = df
                else:
                    data_failed.append(ticker)
            except FuturesTimeout:
                logger.warning(f"[DATA] {ticker} 타임아웃 " f"({TICKER_TIMEOUT_SEC}s)")
                data_failed.append(ticker)
            except Exception as exc:
                logger.warning(f"[DATA] {ticker} 데이터 실패: {exc}")
                data_failed.append(ticker)

            if i % 20 == 0:
                logger.info(
                    f"[DATA] 진행 {i}/{len(eligible)} "
                    f"(성공={len(ohlcv_cache)}, "
                    f"실패={len(data_failed)})"
                )

    logger.info(f"[DATA] 완료: 성공={len(ohlcv_cache)}, " f"실패={len(data_failed)}")

    for t in data_failed:
        excluded.append({"ticker": t, "reason": "ohlcv_data_fetch_failed"})

    # ── 5. 데이터 기반 Pre-filter (volume, price, suspended) ──
    min_avg_vol = CANDIDATE_POOL_CONFIG.get("min_avg_volume_20d", 50000)
    min_price = CANDIDATE_POOL_CONFIG.get("min_price", 1000)

    eligible_filtered: list = []
    for ticker in eligible:
        if ticker not in ohlcv_cache:
            continue
        ohlcv = ohlcv_cache[ticker]

        # 거래정지(suspended) 판별: 최근 5거래일 거래량 = 0
        if "volume" in ohlcv.columns:
            recent_vol = ohlcv["volume"].tail(5)
            if (recent_vol == 0).all():
                excluded.append(
                    {
                        "ticker": ticker,
                        "name": ticker_name_map.get(ticker, ""),
                        "reason": "is_suspended",
                    }
                )
                continue

        # min_avg_volume_20d (거래량 기준)
        if "volume" in ohlcv.columns:
            avg_vol_20 = ohlcv["volume"].tail(20).mean()
            if avg_vol_20 < min_avg_vol:
                excluded.append(
                    {
                        "ticker": ticker,
                        "name": ticker_name_map.get(ticker, ""),
                        "reason": (
                            f"avg_volume_20d" f"({avg_vol_20:.0f}) " f"< {min_avg_vol}"
                        ),
                    }
                )
                continue

        # min_price
        if "close" in ohlcv.columns:
            last_price = ohlcv["close"].iloc[-1]
            if last_price < min_price:
                excluded.append(
                    {
                        "ticker": ticker,
                        "name": ticker_name_map.get(ticker, ""),
                        "reason": (f"price({last_price}) " f"< {min_price}"),
                    }
                )
                continue

        eligible_filtered.append(ticker)

    logger.info(
        f"[PRE-FILTER] 데이터 기반 필터 후: "
        f"{len(eligible_filtered)}종목 "
        f"(제거: {len(eligible) - len(eligible_filtered) - len(data_failed)})"
    )

    # smoke eligible_count를 최종 필터 후 값으로 갱신
    smoke["eligible_count"] = len(eligible_filtered)

    # ── 6. Feature Matrix 계산 ──
    from app.scanner.feature_provider import (
        compute_feature_matrix,
    )

    active_features = get_active_features()
    disabled_keys = get_disabled_features()

    try:
        fm = compute_feature_matrix(
            tickers=eligible_filtered,
            ohlcv_cache=ohlcv_cache,
            features=active_features,
            ticker_name_map=ticker_name_map,
        )
        smoke["feature_matrix_built"] = True

        expected_cols = {f["key"] for f in active_features}
        actual_cols = set(fm.columns) if not fm.empty else set()
        smoke["feature_columns_complete"] = expected_cols.issubset(actual_cols)

        logger.info(f"[FEATURE] Matrix 생성: " f"{len(fm)}행 x {len(fm.columns)}열")
    except Exception as exc:
        errors.append(f"Feature matrix 계산 실패: {exc}")
        traceback.print_exc()
        fm = pd.DataFrame()

    # ── 7. Snapshot 생성 ──
    from app.scanner.snapshot import build_snapshot

    hard_excl_count = len(
        [
            e
            for e in excluded
            if e.get("reason", "") in ("is_inverse", "is_leveraged", "is_synthetic")
        ]
    )

    prev_snap = SNAPSHOT_PATH if SNAPSHOT_PATH.exists() else None

    try:
        snapshot = build_snapshot(
            eligible_tickers=eligible_filtered,
            excluded_with_reasons=excluded,
            candidate_pool_size=total_pool_size,
            pre_filter_passed=len(eligible_filtered),
            hard_exclusion_removed=hard_excl_count,
            active_features=active_features,
            disabled_features=disabled_keys,
            config=CANDIDATE_POOL_CONFIG,
            scanner_mode=SCANNER_MODE,
            scanner_version=SCANNER_VERSION,
            previous_snapshot_path=prev_snap,
            min_overlap_ratio=MIN_OVERLAP_RATIO,
            max_new_entries=MAX_NEW_ENTRIES_PER_REFRESH,
            refresh_frequency=REFRESH_FREQUENCY,
        )
        _atomic_write_json(SNAPSHOT_PATH, snapshot)
        smoke["snapshot_written"] = True
        logger.info(
            "[SNAPSHOT] 생성 완료: "
            f"id={snapshot['snapshot_id']}, "
            f"sha={snapshot['snapshot_sha256'][:12]}..."
        )
    except Exception as exc:
        errors.append(f"Snapshot 생성 실패: {exc}")
        traceback.print_exc()

    # ── 8. Feature Matrix CSV 저장 ──
    if not fm.empty:
        try:
            fm.to_csv(
                FEATURE_MATRIX_PATH,
                index=False,
                encoding="utf-8-sig",
            )
            logger.info("[MATRIX] CSV 저장: " f"{FEATURE_MATRIX_PATH.name}")
        except Exception as exc:
            errors.append(f"Feature matrix CSV 저장 실패: {exc}")

    # ── 9. Smoke Result ──
    if (
        smoke["candidate_pool_built"]
        and smoke["feature_matrix_built"]
        and smoke["snapshot_written"]
        and not errors
    ):
        smoke["result"] = "OK"

    _atomic_write_json(SMOKE_RESULT_PATH, smoke)

    logger.info("=" * 60)
    logger.info(
        f"[SCANNER] 결과: {smoke['result']} | "
        f"적격={smoke['eligible_count']} | "
        f"오류={len(errors)}"
    )
    logger.info("=" * 60)

    return smoke


if __name__ == "__main__":
    result = run_scanner()
    if result["result"] != "OK":
        sys.exit(1)
