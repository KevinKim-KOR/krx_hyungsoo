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
from typing import Any, Dict

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


def _write_selection_reason_md(
    path: Path,
    sel: Dict[str, Any],
    smoke: dict,
    snapshot: Dict[str, Any],
) -> None:
    """선택 근거 문서를 한국어로 생성한다."""
    lines = [
        "# 유니버스 선택 근거",
        "",
        f"- 실행 시각: {snapshot.get('asof', '?')}",
        f"- scanner_mode: {snapshot.get('scanner_mode', '?')}",
        f"- scanner_version: {snapshot.get('scanner_version', '?')}",
        "",
        "## 후보 풀 요약",
        "",
        f"- 전체 후보: {snapshot.get('candidate_pool_size', '?')}",
        f"- pre-filter 후: {snapshot.get('pre_filter_passed', '?')}",
        f"- hard exclusion 제거: {snapshot.get('hard_exclusion_removed', '?')}",
        f"- scoring eligible: {snapshot.get('scoring_eligible', '?')}",
        "",
        "## 선택 결과",
        "",
        f"- ranking_formula: {sel.get('ranking_formula', '?')}",
        f"- top_n: {sel.get('top_n', '?')}",
        f"- tie_breaker: {sel.get('tie_breaker', '?')}",
        f"- fallback 적용: {'예' if sel.get('fallback_applied') else '아니오'}",
        f"- 최종 선택: {sel.get('selected_count', 0)}종목",
        f"- selection_status: {sel.get('selection_status', '?')}",
        f"- min_candidates_met: {'예' if sel.get('min_candidates_met') else '아니오'}",
        "",
        "## 상위 10개 종목",
        "",
        "| 순위 | 종목코드 | 종목명 | composite_score |",
        "| --- | --- | --- | --- |",
    ]

    for item in sel.get("selected_tickers_with_scores", [])[:10]:
        lines.append(
            f"| {item['rank']} | {item['ticker']} "
            f"| {item.get('name', '')} "
            f"| {item['composite_score']:.6f} |"
        )

    # 제외 사유
    excl = snapshot.get("excluded_tickers_with_reasons", [])
    if excl:
        lines.extend(
            [
                "",
                "## 주요 제외 종목 (상위 10개)",
                "",
                "| 종목코드 | 사유 |",
                "| --- | --- |",
            ]
        )
        for e in excl[:10]:
            lines.append(f"| {e.get('ticker', '?')} | {e.get('reason', '?')} |")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


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
        "selector_ranking_built": False,
        "snapshot_written": False,
        "selection_reason_written": False,
        "eligible_count": 0,
        "selected_count": 0,
        "min_candidates_met": False,
        "selection_status": "not_run",
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

    # ── 7. Selector/Ranking (Step5C) ──
    from app.scanner.config import SELECTOR_CONFIG

    selection_result: Dict[str, Any] = {
        "ranking_formula": SELECTOR_CONFIG["ranking_formula"],
        "top_n": SELECTOR_CONFIG["top_n"],
        "tie_breaker": f"{SELECTOR_CONFIG['tie_breaker_1']}"
        f" → {SELECTOR_CONFIG['tie_breaker_2']}",
        "fallback_applied": False,
        "fallback_steps_used": [],
        "selected_count": 0,
        "selected_tickers": [],
        "selected_tickers_with_scores": [],
        "selection_status": "not_run",
        "min_candidates_met": False,
    }

    if not fm.empty:
        try:
            top_n = SELECTOR_CONFIG["top_n"]
            min_cand = SELECTOR_CONFIG["min_candidates"]
            tb1 = SELECTOR_CONFIG["tie_breaker_1"]
            # composite_score 계산
            norm_cols = [f"{f['key']}_norm" for f in active_features]
            weights = [f["weight"] for f in active_features]

            # scoring_eligible: 모든 활성 feature norm이 NaN이 아닌 행
            fm["scoring_eligible"] = True
            for nc in norm_cols:
                if nc in fm.columns:
                    fm.loc[fm[nc].isna(), "scoring_eligible"] = False

            scored = fm[fm["scoring_eligible"]].copy()

            if not scored.empty:
                scored["composite_score"] = 0.0
                for nc, w in zip(norm_cols, weights):
                    if nc in scored.columns:
                        scored["composite_score"] += w * scored[nc].fillna(0)

                # 정렬: composite_score desc → tie_breaker1 desc → tie_breaker2 asc
                tb1_norm = f"{tb1}_norm"
                sort_cols = ["composite_score"]
                sort_asc = [False]
                if tb1_norm in scored.columns:
                    sort_cols.append(tb1_norm)
                    sort_asc.append(False)
                sort_cols.append("ticker")
                sort_asc.append(True)

                scored = scored.sort_values(sort_cols, ascending=sort_asc)
                scored["rank"] = range(1, len(scored) + 1)

                # top_n 선택
                selected = scored.head(top_n).copy()
                selected["selected"] = "Y"
                selected["selection_reason"] = "selected_top_n"

                # fallback 체크
                if len(selected) < min_cand:
                    for step in SELECTOR_CONFIG["fallback_relaxation"]:
                        # TODO: fallback은 pre-filter를 완화하여 재스캔
                        # 현재는 기존 scored에서 더 뽑는 방식
                        selection_result["fallback_steps_used"].append(step["field"])
                    selection_result["fallback_applied"] = True

                sel_tickers = selected["ticker"].tolist()
                sel_with_scores = []
                for _, row in selected.iterrows():
                    sel_with_scores.append(
                        {
                            "ticker": row["ticker"],
                            "name": row.get("name", ""),
                            "composite_score": round(float(row["composite_score"]), 6),
                            "rank": int(row["rank"]),
                        }
                    )

                selection_result["selected_count"] = len(sel_tickers)
                selection_result["selected_tickers"] = sel_tickers
                selection_result["selected_tickers_with_scores"] = sel_with_scores
                selection_result["min_candidates_met"] = len(sel_tickers) >= min_cand
                if len(sel_tickers) >= min_cand:
                    selection_result["selection_status"] = "ok"
                else:
                    selection_result["selection_status"] = "insufficient_candidates"

                # fm에 결과 병합
                fm["composite_score"] = None
                fm["rank"] = None
                fm["selected"] = "N"
                fm["selection_reason"] = ""
                fm["scoring_eligible"] = fm.get("scoring_eligible", False)
                fm["fallback_stage"] = ""

                for idx in scored.index:
                    fm.loc[idx, "composite_score"] = scored.loc[idx, "composite_score"]
                    fm.loc[idx, "rank"] = scored.loc[idx, "rank"]

                for idx in selected.index:
                    fm.loc[idx, "selected"] = "Y"
                    fm.loc[idx, "selection_reason"] = "selected_top_n"

                # 비선택 사유
                for idx in fm.index:
                    if fm.loc[idx, "selected"] != "Y":
                        if not fm.loc[idx, "scoring_eligible"]:
                            fm.loc[idx, "selection_reason"] = "excluded_missing_feature"
                        elif fm.loc[idx, "rank"] is not None:
                            fm.loc[idx, "selection_reason"] = "excluded_low_score"

                smoke["selector_ranking_built"] = True
                smoke["selected_count"] = len(sel_tickers)
                smoke["min_candidates_met"] = selection_result["min_candidates_met"]
                smoke["selection_status"] = selection_result["selection_status"]

                logger.info(
                    f"[SELECTOR] 선택: {len(sel_tickers)}/{len(scored)}종목"
                    f" (top_n={top_n})"
                )
            else:
                selection_result["selection_status"] = "no_scorable_candidates"
                logger.warning("[SELECTOR] 스코어링 가능 후보 0건")
        except Exception as exc:
            errors.append(f"Selector/Ranking 실패: {exc}")
            traceback.print_exc()

    # ── 8. Snapshot 생성 ──
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
            selection_result=selection_result,
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

    # ── 10. Selection Reason MD 생성 (Step5C) ──
    REASON_MD_PATH = OUTPUT_DIR / "universe_selection_reason_latest.md"
    if selection_result["selected_count"] > 0:
        try:
            _write_selection_reason_md(
                REASON_MD_PATH, selection_result, smoke, snapshot
            )
            smoke["selection_reason_written"] = True
        except Exception as exc:
            errors.append(f"Selection reason MD 생성 실패: {exc}")
            traceback.print_exc()

    # ── 11. Smoke Result ──
    if (
        smoke["candidate_pool_built"]
        and smoke["feature_matrix_built"]
        and smoke["selector_ranking_built"]
        and smoke["snapshot_written"]
        and not errors
    ):
        smoke["result"] = "OK"
    elif smoke["selector_ranking_built"] and not errors:
        if smoke["selection_status"] == "insufficient_candidates":
            smoke["result"] = "WARN"

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
