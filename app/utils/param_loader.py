#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/utils/param_loader.py — 전략 파라미터 로딩 (SSOT 전용, fallback 금지)

철칙 #7: 필수 설정값이 누락되면 암묵적 default 대신 명확한 에러를 발생시킨다.

사용처:
  - app/run_backtest.py
  - app/run_tune.py
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PARAMS_SSOT_PATH = (
    PROJECT_ROOT / "state" / "params" / "latest" / "strategy_params_latest.json"
)
BUNDLE_PATH = (
    PROJECT_ROOT
    / "state"
    / "strategy_bundle"
    / "latest"
    / "strategy_bundle_latest.json"
)


# ─── 필수 키 정의 ────────────────────────────────────────────────────────
# SSOT params 객체 내 반드시 존재해야 하는 키 목록
_REQUIRED_NESTED_KEYS = {
    "lookbacks": ["momentum_period", "volatility_period"],
    "risk_limits": ["max_position_pct"],
    "position_limits": ["max_positions", "min_cash_pct"],
    "decision_params": ["entry_threshold", "exit_threshold", "adx_filter_min"],
}

_REQUIRED_TOP_KEYS = [
    "portfolio_mode",
    "sell_mode",
    "rebalance",
    "universe",
]


def _get_sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _require_key(data: dict, key: str, context: str) -> Any:
    """dict에서 key를 꺼내되, 없으면 KeyError를 발생시킨다."""
    if key not in data:
        raise KeyError(f"필수 키 누락: '{key}' in {context}")
    return data[key]


def _extract_params_strict(params_raw: dict) -> Dict[str, Any]:
    """
    params 딕셔너리에서 전략 파라미터를 추출한다.
    필수 키가 하나라도 없으면 KeyError를 발생시킨다.
    """
    # 중첩 그룹 검증 및 추출
    lookbacks = _require_key(params_raw, "lookbacks", "params")
    risk_limits = _require_key(params_raw, "risk_limits", "params")
    pos_limits = _require_key(params_raw, "position_limits", "params")
    decision = _require_key(params_raw, "decision_params", "params")

    for group_name, keys in _REQUIRED_NESTED_KEYS.items():
        group = params_raw[group_name]
        for key in keys:
            _require_key(group, key, f"params.{group_name}")

    # 최상위 필수 키 검증
    for key in _REQUIRED_TOP_KEYS:
        _require_key(params_raw, key, "params")

    universe = params_raw["universe"]
    portfolio_mode = params_raw["portfolio_mode"]

    # bucket_portfolio 모드일 때 buckets 필수
    if portfolio_mode == "bucket_portfolio":
        buckets = _require_key(params_raw, "buckets", "params")
        if not buckets:
            raise ValueError(
                "portfolio_mode='bucket_portfolio'이나 buckets가 비어있습니다."
            )
        # bucket에서 universe 합성
        all_tickers = []
        for b in buckets:
            all_tickers.extend(_require_key(b, "universe", "buckets[].universe"))
        all_tickers = list(dict.fromkeys(all_tickers))
        if all_tickers:
            universe = all_tickers
    else:
        buckets = params_raw.get("buckets", [])

    if not universe:
        raise ValueError("universe가 비어있습니다. SSOT 파일을 확인하세요.")

    return {
        "universe": universe,
        "momentum_period": lookbacks["momentum_period"],
        "volatility_period": lookbacks["volatility_period"],
        "max_positions": pos_limits["max_positions"],
        "max_position_pct": risk_limits["max_position_pct"],
        "min_cash_pct": pos_limits["min_cash_pct"],
        "entry_threshold": decision["entry_threshold"],
        "stop_loss": decision["exit_threshold"],
        "adx_filter_min": decision["adx_filter_min"],
        "portfolio_mode": portfolio_mode,
        "sell_mode": params_raw["sell_mode"],
        "rebalance": params_raw["rebalance"],
        "buckets": buckets,
        "data_source": params_raw.get("data_source", "fdr"),
    }


def load_params_strict() -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    SSOT 파라미터 파일에서 전략 파라미터를 로딩한다.

    - SSOT 파일이 없으면 FileNotFoundError
    - 필수 키가 누락되면 KeyError
    - universe가 비어있으면 ValueError

    Returns:
        (params_dict, param_source_meta)
    """
    if not PARAMS_SSOT_PATH.exists():
        raise FileNotFoundError(
            f"SSOT 파라미터 파일이 없습니다: {PARAMS_SSOT_PATH}\n"
            f"state/params/latest/strategy_params_latest.json 을 먼저 생성하세요."
        )

    with open(PARAMS_SSOT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    params_raw = _require_key(data, "params", "strategy_params_latest.json")
    params = _extract_params_strict(params_raw)

    # P205-STEP4: universe_mode 처리
    universe_mode = data.get("universe_mode", "fixed_current")
    params["universe_mode"] = universe_mode

    if universe_mode == "expanded_candidates":
        from app.tuning.universe_config import get_universe_list

        params["universe"] = get_universe_list(universe_mode)

    source = {
        "path": "state/params/latest/strategy_params_latest.json",
        "sha256": _get_sha256(PARAMS_SSOT_PATH),
    }

    logger.info(
        f"[PARAMS] SSOT 로딩 완료: {source['path']} "
        f"(sha256={source['sha256'][:12]}...)"
    )
    return params, source
