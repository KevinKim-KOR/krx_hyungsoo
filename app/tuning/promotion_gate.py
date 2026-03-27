"""Promotion verdict logic for tuning pipeline (I/O wrapper)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.tuning.promotion_verdict_core import (
    compute_promotion_verdict,
    render_promotion_verdict_md,
)
from app.tuning.results_io import atomic_write_text

KST = timezone(timedelta(hours=9))

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULT_LATEST = PROJECT_ROOT / "reports" / "tuning" / "tuning_results.json"
PARAMS_SSOT_PATH = (
    PROJECT_ROOT / "state" / "params" / "latest" / "strategy_params_latest.json"
)
BACKTEST_RESULT_LATEST = (
    PROJECT_ROOT / "reports" / "backtest" / "latest" / "backtest_result.json"
)
PROMOTION_VERDICT_JSON = PROJECT_ROOT / "reports" / "tuning" / "promotion_verdict.json"
PROMOTION_VERDICT_MD = PROJECT_ROOT / "reports" / "tuning" / "promotion_verdict.md"


def _load_json_or_none(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def refresh_promotion_verdict(
    *,
    tune_data_override: Dict[str, Any] | None = None,
    backtest_data_override: Dict[str, Any] | None = None,
    params_data_override: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    reasons: List[str] = []
    tune_data = None
    backtest_data = None
    params_data = None

    if tune_data_override is not None:
        tune_data = tune_data_override
    else:
        try:
            tune_data = _load_json_or_none(RESULT_LATEST)
            if not tune_data:
                reasons.append("최신 튜닝 결과를 읽지 못했습니다.")
        except Exception as error:
            reasons.append(f"튜닝 결과 파싱 실패: {error}")

    if backtest_data_override is not None:
        backtest_data = backtest_data_override
    else:
        try:
            backtest_data = _load_json_or_none(BACKTEST_RESULT_LATEST)
            if not backtest_data:
                reasons.append("최신 Full Backtest 결과를 읽지 못했습니다.")
        except Exception as error:
            reasons.append(f"백테스트 결과 파싱 실패: {error}")

    if params_data_override is not None:
        params_data = params_data_override
    else:
        try:
            params_data = _load_json_or_none(PARAMS_SSOT_PATH)
            if not params_data:
                reasons.append("현재 SSOT 파라미터를 읽지 못했습니다.")
        except Exception as error:
            reasons.append(f"SSOT 파라미터 파싱 실패: {error}")

    verdict_payload = compute_promotion_verdict(
        tune_data=tune_data,
        backtest_data=backtest_data,
        params_data=params_data,
        extra_reasons=reasons,
    )

    asof = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    verdict_payload["asof"] = asof

    atomic_write_text(
        PROMOTION_VERDICT_JSON,
        json.dumps(verdict_payload, indent=2, ensure_ascii=False),
    )
    atomic_write_text(
        PROMOTION_VERDICT_MD, render_promotion_verdict_md(verdict_payload)
    )
    return verdict_payload
