"""승격 판정 공유 코어 — 순수 로직, I/O 없음."""

from __future__ import annotations

from typing import Any, Dict, List


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def is_same_number(left: Any, right: Any, tolerance: float = 1e-12) -> bool:
    return abs(to_float(left) - to_float(right)) <= tolerance


# ── 축 추출 ──


def extract_ssot_axes(params_data: Dict[str, Any]) -> Dict[str, Any]:
    params = (params_data or {}).get("params", {})
    return {
        "momentum_period": params.get("lookbacks", {}).get("momentum_period"),
        "volatility_period": params.get("lookbacks", {}).get("volatility_period"),
        "entry_threshold": params.get("decision_params", {}).get("entry_threshold"),
        "stop_loss": params.get("decision_params", {}).get("exit_threshold"),
        "max_positions": params.get("position_limits", {}).get("max_positions"),
    }


def extract_backtest_axes(backtest_data: Dict[str, Any]) -> Dict[str, Any]:
    params_used = (backtest_data or {}).get("meta", {}).get("params_used", {})
    return {
        "momentum_period": params_used.get("momentum_period"),
        "volatility_period": params_used.get("volatility_period"),
        "entry_threshold": params_used.get("entry_threshold"),
        "stop_loss": params_used.get("stop_loss"),
        "max_positions": params_used.get("max_positions"),
    }


# ── 축 비교 ──


def build_axis_comparison(
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
            "best": to_float(best_params.get("entry_threshold")),
            "current": to_float(current_params.get("entry_threshold")),
            "match": is_same_number(
                current_params.get("entry_threshold"),
                best_params.get("entry_threshold"),
            ),
        },
        "stop_loss": {
            "best": to_float(best_params.get("stop_loss")),
            "current": to_float(current_params.get("stop_loss")),
            "match": is_same_number(
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


def all_axes_match(comparison: Dict[str, Dict[str, Any]]) -> bool:
    return all(item.get("match", False) for item in comparison.values())


# ── 판정 계산 ──

NEXT_ACTION_MAP = {
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


def compute_promotion_verdict(
    *,
    tune_data: Dict[str, Any] | None,
    backtest_data: Dict[str, Any] | None,
    params_data: Dict[str, Any] | None,
    extra_reasons: List[str] | None = None,
) -> Dict[str, Any]:
    """순수 판정 계산. I/O 없음. asof는 호출자가 추가."""
    reasons: List[str] = list(extra_reasons or [])

    best_params = (tune_data or {}).get("best_params", {})
    ssot_axes = extract_ssot_axes(params_data or {})
    ssot_vs_best = build_axis_comparison(best_params, ssot_axes)
    candidate_applied_to_ssot = bool(best_params) and all_axes_match(ssot_vs_best)

    backtest_axes = extract_backtest_axes(backtest_data or {})
    backtest_vs_best = build_axis_comparison(best_params, backtest_axes)
    backtest_matches_candidate = bool(best_params) and all_axes_match(backtest_vs_best)

    summary = (backtest_data or {}).get("summary", {})
    mdd_value = to_float(summary.get("mdd", summary.get("mdd_pct", 0.0)))
    cagr_value = to_float(summary.get("cagr", 0.0))
    sharpe_value = to_float(summary.get("sharpe", 0.0))

    criteria_check = {
        "cagr_gt_15": cagr_value > 15.0,
        "mdd_lt_10": mdd_value < 10.0,
        "sharpe_reference": sharpe_value,
        "backtest_matches_candidate": backtest_matches_candidate,
    }

    tune_snapshot = {
        "best_trial": (tune_data or {}).get("meta", {}).get("best_trial_number", "N/A"),
        "best_score": to_float((tune_data or {}).get("best_score")),
        "worst_segment": (tune_data or {}).get("worst_segment", "N/A"),
        "overfit_penalty": to_float((tune_data or {}).get("overfit_penalty")),
    }

    full_backtest_metrics = {
        "cagr": cagr_value,
        "mdd": mdd_value,
        "sharpe": sharpe_value,
    }

    # ── 사유 수집 ──
    if not candidate_applied_to_ssot:
        reasons.append("현재 SSOT 5축 값이 튜닝 1등 후보와 일치하지 않습니다.")

    if tune_data and backtest_data:
        if not criteria_check["cagr_gt_15"]:
            reasons.append("Full Backtest CAGR이 15% 초과 기준을 만족하지 못합니다.")
        if not criteria_check["mdd_lt_10"]:
            reasons.append("Full Backtest MDD가 10% 미만 기준을 만족하지 못합니다.")
        if candidate_applied_to_ssot and not backtest_matches_candidate:
            reasons.append(
                "최신 Full Backtest 결과가 현재 1등 후보 기준으로 "
                "다시 계산되지 않았습니다."
            )
        if tune_snapshot["worst_segment"] == "SEG_1":
            reasons.append(
                "최악 구간이 SEG_1이므로 초기 구간 일관성 재검토가 필요합니다."
            )
        if tune_snapshot["overfit_penalty"] >= 5.0:
            reasons.append("과최적화 벌점이 높아 추가 검산이 필요합니다.")
        if tune_snapshot["best_score"] < 0:
            reasons.append("튜닝 점수가 음수이므로 해석 경고가 필요합니다.")

    # ── Backtest 5축 vs SSOT 일치 검사 (P205-STEP3) ──
    bt_meta = (backtest_data or {}).get("meta", {})
    bt_5axes = bt_meta.get("used_params_5axes", {})
    if bt_5axes:
        used_params_match_ssot = (
            bt_5axes.get("momentum_period") == ssot_axes.get("momentum_period")
            and is_same_number(
                bt_5axes.get("exit_threshold"),
                ssot_axes.get("stop_loss"),
            )
            and is_same_number(
                bt_5axes.get("entry_threshold"),
                ssot_axes.get("entry_threshold"),
            )
            and bt_5axes.get("volatility_period") == ssot_axes.get("volatility_period")
            and bt_5axes.get("max_positions") == ssot_axes.get("max_positions")
        )
    else:
        used_params_match_ssot = None

    if used_params_match_ssot is False:
        reasons.append("Backtest에 사용된 5축이 현재 SSOT와 일치하지 않습니다.")

    # ── 판정 결정 ──
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

    # P205-STEP3 강등: Backtest 5축 불일치 시 PROMOTE 금지
    if used_params_match_ssot is False and verdict == "PROMOTE_CANDIDATE":
        verdict = "REVIEW_REQUIRED"

    return {
        "verdict": verdict,
        "candidate_applied_to_ssot": candidate_applied_to_ssot,
        "used_params_match_ssot": used_params_match_ssot,
        "ssot_vs_best_params": ssot_vs_best,
        "full_backtest_metrics": full_backtest_metrics,
        "tune_snapshot": tune_snapshot,
        "criteria_check": criteria_check,
        "reasons": reasons[:6],
        "next_action": NEXT_ACTION_MAP[verdict],
    }


# ── MD 렌더링 ──

_VERDICT_LABEL_MAP = {
    "PROMOTE_CANDIDATE": "승격 후보",
    "REVIEW_REQUIRED": "재검토 필요",
    "REJECT": "기각",
}


def render_promotion_verdict_md(verdict_payload: Dict[str, Any]) -> str:
    metrics = verdict_payload.get("full_backtest_metrics", {})
    tune_snapshot = verdict_payload.get("tune_snapshot", {})
    reasons = verdict_payload.get("reasons", [])
    lines = [
        "# 승격 판정",
        "",
        f"- 현재 판정: "
        f"{_VERDICT_LABEL_MAP.get(verdict_payload.get('verdict'), '기각')}",
        (
            "- SSOT 반영 여부: "
            f"{'예' if verdict_payload.get('candidate_applied_to_ssot') else '아니오'}"
        ),
        "",
        "## Full Backtest 핵심 수치",
        f"- CAGR: {to_float(metrics.get('cagr')):.4f}%",
        f"- MDD: {to_float(metrics.get('mdd')):.4f}%",
        f"- Sharpe: {to_float(metrics.get('sharpe')):.4f}",
        "",
        "## Tune 핵심 수치",
        f"- Best Trial: {tune_snapshot.get('best_trial', 'N/A')}",
        f"- Best Score: {to_float(tune_snapshot.get('best_score')):.4f}",
        f"- 최악 구간: {tune_snapshot.get('worst_segment', 'N/A')}",
        f"- 과최적화 벌점: {to_float(tune_snapshot.get('overfit_penalty')):.4f}",
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
