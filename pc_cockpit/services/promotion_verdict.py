"""승격 판정 계산 (cockpit 로컬 버전)."""

from datetime import datetime

from pc_cockpit.services.config import KST, BASE_DIR, LATEST_PATH
from pc_cockpit.services.json_io import load_json, save_json


def _promotion_verdict_paths():
    tuning_dir = BASE_DIR / "reports" / "tuning"
    return {
        "json": tuning_dir / "promotion_verdict.json",
        "md": tuning_dir / "promotion_verdict.md",
        "backtest": BASE_DIR
        / "reports"
        / "backtest"
        / "latest"
        / "backtest_result.json",
    }


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _same_number(left, right, tolerance=1e-12):
    return abs(_safe_float(left) - _safe_float(right)) <= tolerance


def _extract_ssot_axes(params_data):
    params = (params_data or {}).get("params", {})
    return {
        "momentum_period": params.get("lookbacks", {}).get("momentum_period"),
        "volatility_period": params.get("lookbacks", {}).get("volatility_period"),
        "entry_threshold": params.get("decision_params", {}).get("entry_threshold"),
        "stop_loss": params.get("decision_params", {}).get("exit_threshold"),
        "max_positions": params.get("position_limits", {}).get("max_positions"),
    }


def _extract_backtest_axes(backtest_data):
    params_used = (backtest_data or {}).get("meta", {}).get("params_used", {})
    return {
        "momentum_period": params_used.get("momentum_period"),
        "volatility_period": params_used.get("volatility_period"),
        "entry_threshold": params_used.get("entry_threshold"),
        "stop_loss": params_used.get("stop_loss"),
        "max_positions": params_used.get("max_positions"),
    }


def _build_axis_compare(best_params, current_axes):
    compare = {
        "momentum_period": {
            "best": best_params.get("momentum_period"),
            "current": current_axes.get("momentum_period"),
            "match": current_axes.get("momentum_period")
            == best_params.get("momentum_period"),
        },
        "volatility_period": {
            "best": best_params.get("volatility_period"),
            "current": current_axes.get("volatility_period"),
            "match": current_axes.get("volatility_period")
            == best_params.get("volatility_period"),
        },
        "entry_threshold": {
            "best": _safe_float(best_params.get("entry_threshold")),
            "current": _safe_float(current_axes.get("entry_threshold")),
            "match": _same_number(
                current_axes.get("entry_threshold"),
                best_params.get("entry_threshold"),
            ),
        },
        "stop_loss": {
            "best": _safe_float(best_params.get("stop_loss")),
            "current": _safe_float(current_axes.get("stop_loss")),
            "match": _same_number(
                current_axes.get("stop_loss"), best_params.get("stop_loss")
            ),
        },
        "max_positions": {
            "best": best_params.get("max_positions"),
            "current": current_axes.get("max_positions"),
            "match": current_axes.get("max_positions")
            == best_params.get("max_positions"),
        },
    }
    return compare


def _render_promotion_verdict_md_local(verdict_payload):
    verdict_label = {
        "PROMOTE_CANDIDATE": "승격 후보",
        "REVIEW_REQUIRED": "재검토 필요",
        "REJECT": "기각",
    }.get(verdict_payload.get("verdict"), "기각")
    metrics = verdict_payload.get("full_backtest_metrics", {})
    tune_snapshot = verdict_payload.get("tune_snapshot", {})
    reasons = verdict_payload.get("reasons", [])
    lines = [
        "# 승격 판정",
        "",
        f"- 현재 판정: {verdict_label}",
        f"- SSOT 반영 여부: {'예' if verdict_payload.get('candidate_applied_to_ssot') else '아니오'}",
        "",
        "## Full Backtest 핵심 수치",
        f"- CAGR: {_safe_float(metrics.get('cagr')):.4f}%",
        f"- MDD: {_safe_float(metrics.get('mdd')):.4f}%",
        f"- Sharpe: {_safe_float(metrics.get('sharpe')):.4f}",
        "",
        "## Tune 핵심 수치",
        f"- Best Trial: {tune_snapshot.get('best_trial', 'N/A')}",
        f"- Best Score: {_safe_float(tune_snapshot.get('best_score')):.4f}",
        f"- 최악 구간: {tune_snapshot.get('worst_segment', 'N/A')}",
        f"- 과최적화 벌점: {_safe_float(tune_snapshot.get('overfit_penalty')):.4f}",
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


def refresh_promotion_verdict_local(tune_data):
    paths = _promotion_verdict_paths()
    backtest_data = load_json(paths["backtest"]) or {}
    params_data = load_json(LATEST_PATH) or {}
    best_params = (tune_data or {}).get("best_params", {})
    ssot_vs_best_params = _build_axis_compare(
        best_params, _extract_ssot_axes(params_data)
    )
    candidate_applied_to_ssot = all(
        item.get("match", False) for item in ssot_vs_best_params.values()
    ) and bool(best_params)
    backtest_vs_best = _build_axis_compare(
        best_params, _extract_backtest_axes(backtest_data)
    )
    backtest_matches_candidate = all(
        item.get("match", False) for item in backtest_vs_best.values()
    ) and bool(best_params)

    backtest_summary = backtest_data.get("summary", {})
    cagr_value = _safe_float(backtest_summary.get("cagr"))
    mdd_value = _safe_float(
        backtest_summary.get("mdd", backtest_summary.get("mdd_pct"))
    )
    sharpe_value = _safe_float(backtest_summary.get("sharpe"))
    criteria_check = {
        "cagr_gt_15": cagr_value > 15.0,
        "mdd_lt_10": mdd_value < 10.0,
        "sharpe_reference": sharpe_value,
        "backtest_matches_candidate": backtest_matches_candidate,
    }
    tune_snapshot = {
        "best_trial": (tune_data or {}).get("meta", {}).get("best_trial_number", "N/A"),
        "best_score": _safe_float((tune_data or {}).get("best_score")),
        "worst_segment": (tune_data or {}).get("worst_segment", "N/A"),
        "overfit_penalty": _safe_float((tune_data or {}).get("overfit_penalty")),
    }
    reasons = []
    if not candidate_applied_to_ssot:
        reasons.append("현재 SSOT 5축이 튜닝 1등 후보와 일치하지 않습니다.")
    if not criteria_check["cagr_gt_15"]:
        reasons.append("Full Backtest CAGR이 15% 초과 기준을 만족하지 못합니다.")
    if not criteria_check["mdd_lt_10"]:
        reasons.append("Full Backtest MDD가 10% 미만 기준을 만족하지 못합니다.")
    if candidate_applied_to_ssot and not backtest_matches_candidate:
        reasons.append("최신 Full Backtest 결과가 현재 1등 후보 기준과 다릅니다.")
    if tune_snapshot["worst_segment"] == "SEG_1":
        reasons.append("최악 구간이 SEG_1이므로 초기 구간 일관성 재검토가 필요합니다.")
    if tune_snapshot["overfit_penalty"] >= 5.0:
        reasons.append("과최적화 벌점이 높아 추가 검산이 필요합니다.")
    if tune_snapshot["best_score"] < 0:
        reasons.append("튜닝 점수가 음수이므로 해석 경고가 필요합니다.")

    if (
        candidate_applied_to_ssot
        and criteria_check["cagr_gt_15"]
        and criteria_check["mdd_lt_10"]
        and backtest_matches_candidate
        and tune_snapshot["worst_segment"] != "SEG_1"
        and tune_snapshot["overfit_penalty"] < 5.0
        and tune_snapshot["best_score"] >= 0
    ):
        verdict = "PROMOTE_CANDIDATE"
    elif (
        candidate_applied_to_ssot
        and criteria_check["cagr_gt_15"]
        and criteria_check["mdd_lt_10"]
    ):
        verdict = "REVIEW_REQUIRED"
    else:
        verdict = "REJECT"

    next_action = {
        "PROMOTE_CANDIDATE": "현재 후보를 승격 후보로 유지하고 OCI 반영 전 마지막 검토를 수행합니다.",
        "REVIEW_REQUIRED": "현재 후보는 재검토 필요 상태이므로 다음 Tune 후보와 비교 검증합니다.",
        "REJECT": "현재 후보는 기각 상태이므로 SSOT와 Full Backtest를 다시 맞춘 뒤 재평가합니다.",
    }[verdict]
    verdict_payload = {
        "asof": datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "verdict": verdict,
        "candidate_applied_to_ssot": candidate_applied_to_ssot,
        "ssot_vs_best_params": ssot_vs_best_params,
        "full_backtest_metrics": {
            "cagr": cagr_value,
            "mdd": mdd_value,
            "sharpe": sharpe_value,
        },
        "tune_snapshot": tune_snapshot,
        "criteria_check": criteria_check,
        "reasons": reasons[:6],
        "next_action": next_action,
    }
    save_json(paths["json"], verdict_payload)
    paths["md"].write_text(
        _render_promotion_verdict_md_local(verdict_payload), encoding="utf-8"
    )
    return verdict_payload
