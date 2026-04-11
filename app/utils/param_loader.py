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


_ALLOWED_ALLOC_MODES = {
    "dynamic_equal_weight",
    "risk_aware_equal_weight_v1",
    "inverse_volatility_v1",
}

# P208-STEP8A: holding_structure_experiments 에서 허용되는 allocation mode
# (inverse_volatility_v1 재도입 금지 — 대표 2개만 사용)
_ALLOWED_HOLDING_ALLOC_MODES = {
    "dynamic_equal_weight",
    "risk_aware_equal_weight_v1",
}


def _validate_experiments(experiments):
    """allocation_experiments 스키마 검증.

    None이면 None 반환. 리스트이면 각 항목의 필수 키를 검증.
    """
    if experiments is None:
        return None
    if not isinstance(experiments, list):
        raise TypeError(
            f"allocation_experiments는 리스트여야 합니다:" f" {type(experiments)}"
        )
    for i, exp in enumerate(experiments):
        ctx = f"allocation_experiments[{i}]"
        if "experiment_id" not in exp:
            raise KeyError(f"{ctx}: experiment_id 누락")
        alloc = exp.get("allocation")
        if not alloc or not isinstance(alloc, dict):
            raise KeyError(f"{ctx}: allocation 블록 누락")
        if "mode" not in alloc:
            raise KeyError(f"{ctx}.allocation: mode 누락")
        if alloc["mode"] not in _ALLOWED_ALLOC_MODES:
            raise ValueError(
                f"{ctx}.allocation.mode={alloc['mode']!r}"
                f" 허용: {_ALLOWED_ALLOC_MODES}"
            )
        if "fallback_mode" not in alloc:
            raise KeyError(f"{ctx}.allocation: fallback_mode 누락")
    return experiments


def _validate_holding_structure_experiments(experiments):
    """holding_structure_experiments 스키마 검증 (P208-STEP8A).

    None이면 None 반환. 리스트이면 각 항목의 필수 키(name, max_positions,
    allocation_mode)를 검증하고 중복 name 금지.
    """
    if experiments is None:
        return None
    if not isinstance(experiments, list):
        raise TypeError(
            "holding_structure_experiments는 리스트여야 합니다:" f" {type(experiments)}"
        )
    _seen_names = set()
    for i, exp in enumerate(experiments):
        ctx = f"holding_structure_experiments[{i}]"
        if not isinstance(exp, dict):
            raise TypeError(f"{ctx}: dict 형태여야 합니다: {type(exp)}")
        if "name" not in exp:
            raise KeyError(f"{ctx}: name 누락")
        if "max_positions" not in exp:
            raise KeyError(f"{ctx}: max_positions 누락")
        if "allocation_mode" not in exp:
            raise KeyError(f"{ctx}: allocation_mode 누락")

        _nm = exp["name"]
        if not isinstance(_nm, str) or not _nm:
            raise ValueError(f"{ctx}.name은 비어있지 않은 문자열이어야 합니다")
        if _nm in _seen_names:
            raise ValueError(f"{ctx}.name={_nm!r} 중복")
        _seen_names.add(_nm)

        _mp = exp["max_positions"]
        if not isinstance(_mp, int) or isinstance(_mp, bool) or _mp <= 0:
            raise ValueError(f"{ctx}.max_positions는 양의 정수여야 합니다: {_mp!r}")

        _am = exp["allocation_mode"]
        if _am not in _ALLOWED_HOLDING_ALLOC_MODES:
            raise ValueError(
                f"{ctx}.allocation_mode={_am!r}"
                f" 허용: {_ALLOWED_HOLDING_ALLOC_MODES}"
            )
    return experiments


def _validate_drawdown_analysis_baselines(baselines, holding_experiments):
    """drawdown_analysis_baselines 스키마 검증 (P209-STEP9A realignment FIX).

    - None 이면 None 반환. 단 universe_mode == dynamic_etf_market 인 경우
      run_backtest 에서 REQUIRED 로 취급하여 별도 raise 한다 (_require_dd_baselines).
    - dict 이면 operational/research 는 필수, shadow 는 optional
    - 각 값은 문자열이며, holding_structure_experiments 의 name 과 일치해야 함
    - rule 6/7 (암묵 fallback 금지): 기본값 없음. SSOT 에 명시 요구.
    """
    if baselines is None:
        return None
    if not isinstance(baselines, dict):
        raise TypeError(
            "drawdown_analysis_baselines 는 dict 여야 합니다:" f" {type(baselines)}"
        )
    if "operational" not in baselines:
        raise KeyError("drawdown_analysis_baselines: operational 누락")
    if "research" not in baselines:
        raise KeyError("drawdown_analysis_baselines: research 누락")

    known_names = set()
    if holding_experiments:
        known_names = {e["name"] for e in holding_experiments}

    result = {}
    for role in ("operational", "research", "shadow"):
        if role not in baselines:
            continue
        val = baselines[role]
        if not isinstance(val, str) or not val:
            raise ValueError(
                f"drawdown_analysis_baselines.{role}"
                f" 는 비어있지 않은 문자열이어야 합니다: {val!r}"
            )
        if known_names and val not in known_names:
            raise ValueError(
                f"drawdown_analysis_baselines.{role}={val!r}"
                f" 가 holding_structure_experiments 에 없음."
                f" 허용: {sorted(known_names)}"
            )
        result[role] = val
    return result


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
        "allocation": params_raw.get("allocation"),
        "allocation_experiments": _validate_experiments(
            params_raw.get("allocation_experiments")
        ),
        "holding_structure_experiments": _validate_holding_structure_experiments(
            params_raw.get("holding_structure_experiments")
        ),
        "drawdown_analysis_baselines": _validate_drawdown_analysis_baselines(
            params_raw.get("drawdown_analysis_baselines"),
            params_raw.get("holding_structure_experiments"),
        ),
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

    # P205-STEP4/5D: universe_mode 처리
    universe_mode = data.get("universe_mode", "fixed_current")
    params["universe_mode"] = universe_mode
    params["universe_snapshot_id"] = data.get("universe_snapshot_id")
    params["universe_snapshot_sha256"] = data.get("universe_snapshot_sha256")

    if universe_mode == "expanded_candidates":
        from app.tuning.universe_config import get_universe_list

        params["universe"] = get_universe_list(universe_mode)
    elif universe_mode == "dynamic_etf_market":
        # SSOT에 저장된 dynamic tickers 사용
        dyn_tickers = data.get("universe_tickers")
        if dyn_tickers and isinstance(dyn_tickers, list):
            params["universe"] = dyn_tickers
        else:
            raise ValueError(
                "universe_mode=dynamic_etf_market이나 "
                "universe_tickers가 SSOT에 없습니다. "
                "먼저 스캐너 결과를 SSOT에 적용하세요."
            )

        # P209-STEP9A realignment FIX: dynamic_etf_market 모드에서는
        # drawdown_analysis_baselines 가 REQUIRED. 누락 시 즉시 raise.
        # rule 6/7 (암묵 fallback 금지) — 운영 SSOT 에 baseline 을 명시 요구.
        if params.get("drawdown_analysis_baselines") is None:
            raise KeyError(
                "universe_mode=dynamic_etf_market 에서는"
                " params.drawdown_analysis_baselines 가 필수입니다."
                " SSOT 에 operational/research/(optional shadow) 라벨을 명시하세요."
                ' 예: {"operational": "g2_pos2_raew",'
                ' "research": "g4_pos3_raew",'
                ' "shadow": "g3_pos3_eq"}'
            )

    source = {
        "path": "state/params/latest/strategy_params_latest.json",
        "sha256": _get_sha256(PARAMS_SSOT_PATH),
    }

    logger.info(
        f"[PARAMS] SSOT 로딩 완료: {source['path']} "
        f"(sha256={source['sha256'][:12]}...)"
    )
    return params, source
