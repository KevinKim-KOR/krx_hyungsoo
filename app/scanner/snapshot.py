# -*- coding: utf-8 -*-
"""
app/scanner/snapshot.py — Snapshot Identity + Churn Control (P205-STEP5B)

불변조건 1: snapshot_id / snapshot_sha256 생성
불변조건 2: Churn 제어 (overlap_ratio, new_entries_count)
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def compute_snapshot_sha256(
    scanner_mode: str,
    scanner_version: str,
    candidate_pool_source: str,
    active_features: List[Dict[str, Any]],
    pre_filters: Dict[str, Any],
    hard_exclusions: Dict[str, bool],
    eligible_tickers: List[str],
) -> str:
    """
    Deterministic snapshot hash 생성.

    같은 입력이면 같은 sha256이 나온다.
    """
    canonical = {
        "scanner_mode": scanner_mode,
        "scanner_version": scanner_version,
        "candidate_pool_source": candidate_pool_source,
        "active_features": [
            {
                "key": f["key"],
                "weight": f["weight"],
                "lookback": f["lookback"],
            }
            for f in sorted(active_features, key=lambda x: x["key"])
        ],
        "pre_filters": pre_filters,
        "hard_exclusions": hard_exclusions,
        "eligible_tickers": sorted(eligible_tickers),
    }

    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_churn_metrics(
    current_tickers: List[str],
    previous_snapshot_path: Optional[Path],
    min_overlap_ratio: float,
    max_new_entries: int,
) -> Dict[str, Any]:
    """
    이전 snapshot 대비 Churn 지표를 계산한다.

    Returns:
        {
            "previous_snapshot_exists": bool,
            "previous_snapshot_id": str or null,
            "overlap_ratio": float or null,
            "new_entries_count": int or null,
            "removed_entries_count": int or null,
            "churn_check_status": "pass" | "warn" | "first_snapshot",
        }
    """
    result: Dict[str, Any] = {
        "previous_snapshot_exists": False,
        "previous_snapshot_id": None,
        "overlap_ratio": None,
        "new_entries_count": None,
        "removed_entries_count": None,
        "churn_check_status": "first_snapshot",
    }

    if (
        previous_snapshot_path is None
        or not previous_snapshot_path.exists()
    ):
        return result

    try:
        with open(previous_snapshot_path, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
    except Exception as e:
        logger.warning(f"[CHURN] 이전 snapshot 로드 실패: {e}")
        return result

    prev_tickers = prev_data.get("eligible_tickers", [])
    if not prev_tickers:
        return result

    result["previous_snapshot_exists"] = True
    result["previous_snapshot_id"] = prev_data.get("snapshot_id")

    current_set = set(current_tickers)
    prev_set = set(prev_tickers)

    overlap = current_set & prev_set
    new_entries = current_set - prev_set
    removed = prev_set - current_set

    if prev_set:
        overlap_ratio = len(overlap) / len(prev_set)
    else:
        overlap_ratio = 1.0

    result["overlap_ratio"] = round(overlap_ratio, 4)
    result["new_entries_count"] = len(new_entries)
    result["removed_entries_count"] = len(removed)

    # Churn 판정
    warnings = []
    if overlap_ratio < min_overlap_ratio:
        warnings.append(
            f"overlap_ratio({overlap_ratio:.2f}) < "
            f"min({min_overlap_ratio})"
        )
    if len(new_entries) > max_new_entries:
        warnings.append(
            f"new_entries({len(new_entries)}) > "
            f"max({max_new_entries})"
        )

    if warnings:
        result["churn_check_status"] = "warn"
        logger.warning(
            f"[CHURN] 경고: {'; '.join(warnings)}"
        )
    else:
        result["churn_check_status"] = "pass"

    return result


def build_snapshot(
    eligible_tickers: List[str],
    excluded_with_reasons: List[Dict[str, Any]],
    candidate_pool_size: int,
    pre_filter_passed: int,
    hard_exclusion_removed: int,
    active_features: List[Dict[str, Any]],
    disabled_features: List[str],
    config: Dict[str, Any],
    previous_snapshot_path: Optional[Path] = None,
    min_overlap_ratio: float = 0.60,
    max_new_entries: int = 5,
    refresh_frequency: str = "weekly",
) -> Dict[str, Any]:
    """
    완전한 snapshot 딕셔너리를 생성한다.

    불변조건 1: snapshot_id, snapshot_sha256
    불변조건 2: Churn 제어
    불변조건 3: 레버리지/인버스 정책
    """
    now = datetime.now(KST)

    snapshot_sha = compute_snapshot_sha256(
        scanner_mode=config.get("source", "krx_etf_list"),
        scanner_version="v1",
        candidate_pool_source=config.get("source", "krx_etf_list"),
        active_features=active_features,
        pre_filters={
            "min_listing_days": config.get("min_listing_days", 180),
            "min_avg_volume_20d": config.get(
                "min_avg_volume_20d", 50000
            ),
            "min_price": config.get("min_price", 1000),
        },
        hard_exclusions={
            "exclude_inverse": config.get("exclude_inverse", True),
            "exclude_leveraged": config.get(
                "exclude_leveraged", True
            ),
            "exclude_synthetic": config.get(
                "exclude_synthetic", True
            ),
        },
        eligible_tickers=eligible_tickers,
    )

    snapshot_id = (
        f"snap_{now.strftime('%Y%m%d_%H%M%S')}_"
        f"{snapshot_sha[:8]}"
    )

    churn = compute_churn_metrics(
        current_tickers=eligible_tickers,
        previous_snapshot_path=previous_snapshot_path,
        min_overlap_ratio=min_overlap_ratio,
        max_new_entries=max_new_entries,
    )

    feature_weights = {
        f["key"]: f["weight"]
        for f in active_features
        if f["enabled"]
    }

    return {
        "asof": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "scanner_mode": "dynamic_etf_market",
        "scanner_version": "v1",
        "candidate_pool_source": config.get(
            "source", "krx_etf_list"
        ),
        "candidate_pool_size": candidate_pool_size,
        "pre_filter_passed": pre_filter_passed,
        "hard_exclusion_removed": hard_exclusion_removed,
        "scoring_eligible": len(eligible_tickers),
        "eligible_tickers": sorted(eligible_tickers),
        "excluded_tickers_with_reasons": excluded_with_reasons[:50],
        "feature_weights_used": feature_weights,
        "disabled_features": disabled_features,
        "snapshot_id": snapshot_id,
        "snapshot_sha256": snapshot_sha,
        # 불변조건 2: Churn 제어
        "previous_snapshot_exists": churn["previous_snapshot_exists"],
        "previous_snapshot_id": churn["previous_snapshot_id"],
        "overlap_ratio": churn["overlap_ratio"],
        "new_entries_count": churn["new_entries_count"],
        "removed_entries_count": churn.get(
            "removed_entries_count"
        ),
        "min_overlap_ratio": min_overlap_ratio,
        "max_new_entries_per_refresh": max_new_entries,
        "refresh_frequency": refresh_frequency,
        "churn_check_status": churn["churn_check_status"],
        # 불변조건 3: 레버리지/인버스 정책
        "exclude_inverse": config.get("exclude_inverse", True),
        "exclude_leveraged": config.get(
            "exclude_leveraged", True
        ),
        "exclude_synthetic": config.get(
            "exclude_synthetic", True
        ),
    }
