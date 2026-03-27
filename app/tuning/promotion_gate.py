"""Promotion verdict logic for tuning pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.tuning.exports import _to_float
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


def _is_same_number(left: Any, right: Any, tolerance: float = 1e-12) -> bool:
    return abs(_to_float(left) - _to_float(right)) <= tolerance


def _extract_ssot_candidate_axes(params_data: Dict[str, Any]) -> Dict[str, Any]:
    params = params_data.get("params", {})
    return {
        "momentum_period": params.get("lookbacks", {}).get("momentum_period"),
        "volatility_period": params.get("lookbacks", {}).get("volatility_period"),
        "entry_threshold": params.get("decision_params", {}).get("entry_threshold"),
        "stop_loss": params.get("decision_params", {}).get("exit_threshold"),
        "max_positions": params.get("position_limits", {}).get("max_positions"),
    }


def _extract_backtest_candidate_axes(
    backtest_data: Dict[str, Any],
) -> Dict[str, Any]:
    params_used = backtest_data.get("meta", {}).get("params_used", {})
    return {
        "momentum_period": params_used.get("momentum_period"),
        "volatility_period": params_used.get("volatility_period"),
        "entry_threshold": params_used.get("entry_threshold"),
        "stop_loss": params_used.get("stop_loss"),
        "max_positions": params_used.get("max_positions"),
    }


def _build_axis_comparison(
    *,
    best_params: Dict[str, Any],
    current_params: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    return {
        "momentum_period": {
            "best": best_params.get("momentum_period"),
            "current": current_params.get("momentum_period"),
            "match": current_params.get("momentum_period")
            == best_params.get("momentum_period"),
        },
        "volatility_period": {
            "best": best_params.get("volatility_period"),
            "current": current_params.get("volatility_period"),
            "match": current_params.get("volatility_period")
            == best_params.get("volatility_period"),
        },
        "entry_threshold": {
            "best": _to_float(best_params.get("entry_threshold")),
            "current": _to_float(current_params.get("entry_threshold")),
            "match": _is_same_number(
                current_params.get("entry_threshold"),
                best_params.get("entry_threshold"),
            ),
        },
        "stop_loss": {
            "best": _to_float(best_params.get("stop_loss")),
            "current": _to_float(current_params.get("stop_loss")),
            "match": _is_same_number(
                current_params.get("stop_loss"),
                best_params.get("stop_loss"),
            ),
        },
        "max_positions": {
            "best": best_params.get("max_positions"),
            "current": current_params.get("max_positions"),
            "match": current_params.get("max_positions")
            == best_params.get("max_positions"),
        },
    }


def _all_match(comparison: Dict[str, Dict[str, Any]]) -> bool:
    return all(item.get("match", False) for item in comparison.values())


def _render_promotion_verdict_md(verdict_payload: Dict[str, Any]) -> str:
    verdict_label_map = {
        "PROMOTE_CANDIDATE": "승격 후보",
        "REVIEW_REQUIRED": "재검토 필요",
        "REJECT": "기각",
    }
    metrics = verdict_payload.get("full_backtest_metrics", {})
    tune_snapshot = verdict_payload.get("tune_snapshot", {})
    reasons = verdict_payload.get("reasons", [])
    lines = [
        "# 승격 판정",
        "",
        f"- 현재 판정: {verdict_label_map.get(verdict_payload.get('verdict'), '기각')}",
        (
            "- SSOT 반영 여부: "
            f"{'예' if verdict_payload.get('candidate_applied_to_ssot') else '아니오'}"
        ),
        "",
        "## Full Backtest 핵심 수치",
        f"- CAGR: {_to_float(metrics.get('cagr')):.4f}%",
        f"- MDD: {_to_float(metrics.get('mdd')):.4f}%",
        f"- Sharpe: {_to_float(metrics.get('sharpe')):.4f}",
        "",
        "## Tune 핵심 수치",
        f"- Best Trial: {tune_snapshot.get('best_trial', 'N/A')}",
        f"- Best Score: {_to_float(tune_snapshot.get('best_score')):.4f}",
        f"- 최악 구간: {tune_snapshot.get('worst_segment', 'N/A')}",
        f"- 과최적화 벌점: {_to_float(tune_snapshot.get('overfit_penalty')):.4f}",
        "",
        "## 판정 사유",
    ]
    for reason in reasons[:4]:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## 다음 행동",
            f"- {verdict_payload.get('next_action', '-')}",
            "",
        ]
    )
    return "\n".join(lines)


def refresh_promotion_verdict(
    *,
    tune_data_override: Dict[str, Any] | None = None,
    backtest_data_override: Dict[str, Any] | None = None,
    params_data_override: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    asof = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    reasons: List[str] = []
    verdict = "REJECT"
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

    best_params = (tune_data or {}).get("best_params", {})
    current_axes = _extract_ssot_candidate_axes(params_data or {})
    ssot_vs_best_params = _build_axis_comparison(
        best_params=best_params,
        current_params=current_axes,
    )
    candidate_applied_to_ssot = bool(best_params) and _all_match(ssot_vs_best_params)

    backtest_axes = _extract_backtest_candidate_axes(backtest_data or {})
    backtest_matches_candidate = bool(best_params) and _all_match(
        _build_axis_comparison(
            best_params=best_params,
            current_params=backtest_axes,
        )
    )

    summary = (backtest_data or {}).get("summary", {})
    mdd_value = _to_float(summary.get("mdd", summary.get("mdd_pct", 0.0)))
    cagr_value = _to_float(summary.get("cagr", 0.0))
    sharpe_value = _to_float(summary.get("sharpe", 0.0))

    criteria_check = {
        "cagr_gt_15": cagr_value > 15.0,
        "mdd_lt_10": mdd_value < 10.0,
        "sharpe_reference": sharpe_value,
        "backtest_matches_candidate": backtest_matches_candidate,
    }

    tune_snapshot = {
        "best_trial": (tune_data or {}).get("meta", {}).get("best_trial_number", "N/A"),
        "best_score": _to_float((tune_data or {}).get("best_score")),
        "worst_segment": (tune_data or {}).get("worst_segment", "N/A"),
        "overfit_penalty": _to_float((tune_data or {}).get("overfit_penalty")),
    }

    full_backtest_metrics = {
        "cagr": cagr_value,
        "mdd": mdd_value,
        "sharpe": sharpe_value,
    }

    if not candidate_applied_to_ssot:
        reasons.append("현재 SSOT 5축 값이 튜닝 1등 후보와 일치하지 않습니다.")

    if tune_data and backtest_data:
        if not criteria_check["cagr_gt_15"]:
            reasons.append("Full Backtest CAGR이 15% 초과 기준을 만족하지 못합니다.")
        if not criteria_check["mdd_lt_10"]:
            reasons.append("Full Backtest MDD가 10% 미만 기준을 만족하지 못합니다.")
        if candidate_applied_to_ssot and not backtest_matches_candidate:
            reasons.append(
                "최신 Full Backtest 결과가 현재 1등 후보 기준으로 다시 계산되지 않았습니다."
            )
        if tune_snapshot["worst_segment"] == "SEG_1":
            reasons.append(
                "최악 구간이 SEG_1이므로 초기 구간 일관성 재검토가 필요합니다."
            )
        if tune_snapshot["overfit_penalty"] >= 5.0:
            reasons.append("과최적화 벌점이 높아 추가 검산이 필요합니다.")
        if tune_snapshot["best_score"] < 0:
            reasons.append("튜닝 점수가 음수이므로 해석 경고가 필요합니다.")

    if (
        tune_data
        and backtest_data
        and params_data
        and candidate_applied_to_ssot
        and criteria_check["cagr_gt_15"]
        and criteria_check["mdd_lt_10"]
        and backtest_matches_candidate
        and tune_snapshot["worst_segment"] != "SEG_1"
        and tune_snapshot["overfit_penalty"] < 5.0
        and tune_snapshot["best_score"] >= 0
    ):
        verdict = "PROMOTE_CANDIDATE"
    elif (
        tune_data
        and backtest_data
        and params_data
        and candidate_applied_to_ssot
        and criteria_check["cagr_gt_15"]
        and criteria_check["mdd_lt_10"]
    ):
        verdict = "REVIEW_REQUIRED"
    else:
        verdict = "REJECT"

    next_action_map = {
        "PROMOTE_CANDIDATE": (
            "현재 후보를 승격 후보로 유지하고 OCI 반영 전 마지막 검토를 수행합니다."
        ),
        "REVIEW_REQUIRED": (
            "현재 후보는 재검토 필요 상태이므로 다음 Tune 후보와 비교 검증합니다."
        ),
        "REJECT": (
            "현재 후보는 기각 상태이므로 SSOT와 Full Backtest를 다시 맞춘 뒤 재평가합니다."
        ),
    }

    verdict_payload = {
        "asof": asof,
        "verdict": verdict,
        "candidate_applied_to_ssot": candidate_applied_to_ssot,
        "ssot_vs_best_params": ssot_vs_best_params,
        "full_backtest_metrics": full_backtest_metrics,
        "tune_snapshot": tune_snapshot,
        "criteria_check": criteria_check,
        "reasons": reasons[:6],
        "next_action": next_action_map[verdict],
    }
    atomic_write_text(
        PROMOTION_VERDICT_JSON,
        json.dumps(verdict_payload, indent=2, ensure_ascii=False),
    )
    atomic_write_text(
        PROMOTION_VERDICT_MD, _render_promotion_verdict_md(verdict_payload)
    )
    return verdict_payload
