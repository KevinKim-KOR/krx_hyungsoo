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


def _resolve_next_action(
    verdict: str,
    candidate_applied_to_ssot: bool,
    used_params_match_ssot,
    criteria_check: Dict[str, Any],
) -> str:
    """사유별 next_action 문구 분기 (P205-STEP3B)."""
    # Case 4: PROMOTE
    if verdict == "PROMOTE_CANDIDATE":
        return "현재 후보는 승격 후보입니다. " "OCI 반영 전 최종 점검만 수행합니다."

    # Case 1: SSOT / Backtest 불일치
    if not candidate_applied_to_ssot or used_params_match_ssot is False:
        return (
            "현재 후보는 SSOT 또는 Backtest 기준이 "
            "일치하지 않으므로, 파라미터를 다시 맞춘 뒤 "
            "재평가합니다."
        )

    # Case 3: REVIEW_REQUIRED + 정합성 충족
    if verdict == "REVIEW_REQUIRED":
        return (
            "현재 후보는 기준 정합성은 충족했지만 "
            "추가 검토가 필요합니다. "
            "상위 후보와 비교 후 재평가합니다."
        )

    # Case 2: REJECT + 정합성 충족 + 성능 미달
    return (
        "현재 후보는 기준 정합성은 충족했지만 "
        "Full Backtest 성능 기준을 만족하지 못해 "
        "기각합니다. 다음 후보를 검토하거나 "
        "유니버스/탐색범위를 재검토합니다."
    )


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

    # P205-STEP5D: 유니버스 일치 검사
    # (mode + ticker list + snapshot identity + SSOT)
    tune_meta = (tune_data or {}).get("meta", {})
    tune_um = tune_meta.get("universe_mode")
    bt_um = bt_meta.get("universe_mode")
    ssot_um = (params_data or {}).get("universe_mode")

    bt_universe = sorted(bt_meta.get("universe", []))
    tune_universe = sorted(tune_meta.get("universe", []))
    # SSOT universe: dynamic_etf_market은 루트 universe_tickers
    _pd = params_data or {}
    if ssot_um == "dynamic_etf_market":
        ssot_universe = sorted(_pd.get("universe_tickers", []))
    else:
        ssot_universe = sorted(_pd.get("params", {}).get("universe", []))

    bt_universe_size = bt_meta.get("universe_size")
    tune_universe_size = tune_meta.get("universe_size")

    if tune_um and bt_um:
        mode_match = tune_um == bt_um
        # SSOT mode 일치
        ssot_mode_match = ssot_um == bt_um if ssot_um else True

        # ticker list 직접 비교
        if bt_universe and tune_universe:
            ticker_match = bt_universe == tune_universe
        else:
            ticker_match = (
                bt_universe_size == tune_universe_size
                if bt_universe_size and tune_universe_size
                else True
            )

        # SSOT ticker list 일치
        if bt_universe and ssot_universe:
            ssot_ticker_match = bt_universe == ssot_universe
        else:
            ssot_ticker_match = True

        # snapshot identity
        tune_snap = tune_meta.get("used_universe_snapshot_id")
        bt_snap = bt_meta.get("used_universe_snapshot_id")
        tune_sha = tune_meta.get("used_universe_snapshot_sha256")
        bt_sha = bt_meta.get("used_universe_snapshot_sha256")

        snap_match = True
        if tune_snap and bt_snap:
            snap_match = tune_snap == bt_snap
        if tune_sha and bt_sha:
            snap_match = snap_match and (tune_sha == bt_sha)

        # dynamic 모드: Tune과 Backtest 모두 dynamic_execution 필요
        bt_dynamic = bt_meta.get("dynamic_execution", False)
        tune_dynamic = tune_meta.get("dynamic_execution", False)

        if bt_um == "dynamic_etf_market":
            # Backtest + Tune 양쪽 schedule evidence 검증
            bt_sched = bt_meta.get("dynamic_schedule_path")
            bt_first = bt_meta.get("first_rebalance_snapshot_id")
            bt_sched_valid = bool(bt_sched) and bool(bt_first)

            tune_sched = tune_meta.get("dynamic_schedule_path")
            tune_first = tune_meta.get("first_rebalance_snapshot_id")
            tune_sched_valid = bool(tune_sched) and bool(tune_first)

            schedule_valid = bt_sched_valid and tune_sched_valid

            used_universe_match = (
                mode_match
                and ssot_mode_match
                and bt_dynamic
                and tune_dynamic
                and snap_match
                and schedule_valid
            )
            if not bt_sched_valid:
                reasons.append("Backtest dynamic schedule 증거가 " "불완전합니다.")
            if not tune_sched_valid:
                reasons.append("Tune dynamic schedule 증거가 " "불완전합니다.")
        else:
            used_universe_match = (
                mode_match
                and ssot_mode_match
                and ticker_match
                and ssot_ticker_match
                and snap_match
            )
    else:
        used_universe_match = None

    if used_universe_match is False:
        reasons.append("Tune과 Backtest의 유니버스가 다릅니다.")
        if verdict == "PROMOTE_CANDIDATE":
            verdict = "REVIEW_REQUIRED"

    return {
        "verdict": verdict,
        "candidate_applied_to_ssot": candidate_applied_to_ssot,
        "used_params_match_ssot": used_params_match_ssot,
        "used_universe_match": used_universe_match,
        "universe_mode": bt_um or tune_um,
        "universe_size": bt_universe_size or tune_universe_size,
        "used_universe_snapshot_id": bt_meta.get("used_universe_snapshot_id"),
        "used_universe_snapshot_sha256": bt_meta.get("used_universe_snapshot_sha256"),
        "ssot_vs_best_params": ssot_vs_best,
        "full_backtest_metrics": full_backtest_metrics,
        "tune_snapshot": tune_snapshot,
        "criteria_check": criteria_check,
        "reasons": reasons[:6],
        "next_action": _resolve_next_action(
            verdict,
            candidate_applied_to_ssot,
            used_params_match_ssot,
            criteria_check,
        ),
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
        "- 유니버스 일치: "
        + (
            "예"
            if verdict_payload.get("used_universe_match")
            else (
                "아니오"
                if verdict_payload.get("used_universe_match") is False
                else "N/A"
            )
        ),
        f"- universe_snapshot_id: "
        f"{verdict_payload.get('used_universe_snapshot_id', 'N/A')}",
        f"- universe_mode: " f"{verdict_payload.get('universe_mode', 'N/A')}",
        f"- universe_size: " f"{verdict_payload.get('universe_size', 'N/A')}",
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
