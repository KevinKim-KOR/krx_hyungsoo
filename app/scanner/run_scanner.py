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

    errors = []
    smoke = {
        "result": "FAIL",
        "candidate_pool_built": False,
        "feature_matrix_built": False,
        "snapshot_written": False,
        "eligible_count": 0,
        "feature_columns_complete": False,
        "errors": errors,
    }

    # ── 1. Candidate Pool ──
    from app.scanner.config import (
        CANDIDATE_POOL_CONFIG,
        EXCLUDE_INVERSE,
        EXCLUDE_LEVERAGED,
        EXCLUDE_SYNTHETIC,
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

    try:
        etf_list = fetch_krx_etf_list()
        total_pool_size = len(etf_list)
    except Exception as e:
        errors.append(f"ETF 목록 수집 실패: {e}")
        total_pool_size = 0

    try:
        eligible, excluded = build_candidate_pool(
            CANDIDATE_POOL_CONFIG
        )
        smoke["candidate_pool_built"] = True
        smoke["eligible_count"] = len(eligible)
        logger.info(
            f"[POOL] 적격 후보: {len(eligible)}, "
            f"제외: {len(excluded)}"
        )
    except Exception as e:
        errors.append(f"Candidate pool 생성 실패: {e}")
        traceback.print_exc()
        _atomic_write_json(SMOKE_RESULT_PATH, smoke)
        return smoke

    if not eligible:
        errors.append("적격 후보 0건 — 스캐너 중단")
        _atomic_write_json(SMOKE_RESULT_PATH, smoke)
        return smoke

    # ── 2. OHLCV 데이터 수집 (종목별 타임아웃 10초) ──
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    from app.backtest.infra.data_loader import load_ohlcv_cached

    TICKER_TIMEOUT_SEC = 10

    today = date.today()
    lookback_start = today - timedelta(days=180)
    lookback_end = today - timedelta(days=1)

    ohlcv_cache = {}
    data_failed = []

    def _fetch_one(t):
        return load_ohlcv_cached(t, lookback_start, lookback_end, data_source="fdr")

    with ThreadPoolExecutor(max_workers=1) as pool:
        for i, ticker in enumerate(eligible, 1):
            try:
                future = pool.submit(_fetch_one, ticker)
                df = future.result(timeout=TICKER_TIMEOUT_SEC)
                if df is not None and not df.empty:
                    if isinstance(df.index, pd.MultiIndex):
                        df = df.xs(ticker, level="code", drop_level=True)
                    ohlcv_cache[ticker] = df
                else:
                    data_failed.append(ticker)
            except FuturesTimeout:
                logger.warning(f"[DATA] {ticker} 타임아웃 ({TICKER_TIMEOUT_SEC}s)")
                data_failed.append(ticker)
            except Exception as e:
                logger.warning(f"[DATA] {ticker} 데이터 실패: {e}")
                data_failed.append(ticker)

            if i % 20 == 0:
                logger.info(
                    f"[DATA] 진행 {i}/{len(eligible)} "
                    f"(성공={len(ohlcv_cache)}, 실패={len(data_failed)})"
                )

    logger.info(
        f"[DATA] 완료: 성공={len(ohlcv_cache)}, "
        f"실패={len(data_failed)}"
    )

    # 실패 종목을 excluded에 추가
    for t in data_failed:
        excluded.append(
            {"ticker": t, "reason": "ohlcv_data_fetch_failed"}
        )

    # eligible 에서 데이터 실패 제거
    eligible_with_data = [t for t in eligible if t in ohlcv_cache]

    # ── 3. Feature Matrix 계산 ──
    from app.scanner.feature_provider import compute_feature_matrix

    active_features = get_active_features()
    disabled_keys = get_disabled_features()

    try:
        fm = compute_feature_matrix(
            tickers=eligible_with_data,
            ohlcv_cache=ohlcv_cache,
            features=active_features,
        )
        smoke["feature_matrix_built"] = True

        # feature 컬럼 완전성 체크
        expected_cols = {f["key"] for f in active_features}
        actual_cols = set(fm.columns) if not fm.empty else set()
        smoke["feature_columns_complete"] = expected_cols.issubset(
            actual_cols
        )

        logger.info(
            f"[FEATURE] Matrix 생성: "
            f"{len(fm)}행 × {len(fm.columns)}열"
        )
    except Exception as e:
        errors.append(f"Feature matrix 계산 실패: {e}")
        traceback.print_exc()
        fm = pd.DataFrame()

    # ── 4. Pre-filter (Volume/Price) ──
    # Candidate Pool에서 이미 이름 기반 필터는 완료.
    # 여기서 실제 데이터 기반 pre-filter 적용.
    min_vol = CANDIDATE_POOL_CONFIG.get("min_avg_volume_20d", 50000)
    min_price = CANDIDATE_POOL_CONFIG.get("min_price", 1000)

    pre_filter_removed = 0
    if not fm.empty and "liquidity_20d" in fm.columns:
        before = len(fm)
        vol_mask = fm["liquidity_20d"].fillna(0) >= min_vol
        price_fail = []
        for ticker in fm["ticker"]:
            ohlcv = ohlcv_cache.get(ticker)
            if ohlcv is not None and "close" in ohlcv.columns:
                last_price = ohlcv["close"].iloc[-1]
                if last_price < min_price:
                    price_fail.append(ticker)
                    excluded.append(
                        {
                            "ticker": ticker,
                            "reason": f"price({last_price}) < {min_price}",
                        }
                    )

        if price_fail:
            fm = fm[~fm["ticker"].isin(price_fail)]

        pre_filter_removed = before - len(fm)

    # ── 5. Snapshot 생성 ──
    from app.scanner.snapshot import build_snapshot

    hard_excl_count = len(
        [
            e
            for e in excluded
            if e.get("reason", "") in (
                "is_inverse", "is_leveraged", "is_synthetic"
            )
        ]
    )

    previous_snap = SNAPSHOT_PATH if SNAPSHOT_PATH.exists() else None

    try:
        snapshot = build_snapshot(
            eligible_tickers=eligible_with_data,
            excluded_with_reasons=excluded,
            candidate_pool_size=total_pool_size,
            pre_filter_passed=len(eligible),
            hard_exclusion_removed=hard_excl_count,
            active_features=active_features,
            disabled_features=disabled_keys,
            config=CANDIDATE_POOL_CONFIG,
            previous_snapshot_path=previous_snap,
            min_overlap_ratio=MIN_OVERLAP_RATIO,
            max_new_entries=MAX_NEW_ENTRIES_PER_REFRESH,
            refresh_frequency=REFRESH_FREQUENCY,
        )
        _atomic_write_json(SNAPSHOT_PATH, snapshot)
        smoke["snapshot_written"] = True
        logger.info(
            f"[SNAPSHOT] 생성 완료: "
            f"id={snapshot['snapshot_id']}, "
            f"sha={snapshot['snapshot_sha256'][:12]}..."
        )
    except Exception as e:
        errors.append(f"Snapshot 생성 실패: {e}")
        traceback.print_exc()

    # ── 6. Feature Matrix CSV 저장 ──
    if not fm.empty:
        try:
            fm.to_csv(
                FEATURE_MATRIX_PATH, index=False, encoding="utf-8-sig"
            )
            logger.info(
                f"[MATRIX] CSV 저장: {FEATURE_MATRIX_PATH.name}"
            )
        except Exception as e:
            errors.append(f"Feature matrix CSV 저장 실패: {e}")

    # ── 7. Smoke Result ──
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
