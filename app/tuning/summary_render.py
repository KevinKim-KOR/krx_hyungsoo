"""Tuning validation summary markdown renderer."""

from __future__ import annotations

from typing import Any, Dict, List

from app.tuning.exports import _to_float


def _build_validation_summary_md(
    *,
    asof: str,
    study_name: str,
    mode: str,
    start_date: str,
    end_date: str,
    best_trial_number: int,
    best_params: Dict[str, Any],
    full_metrics: Dict[str, Any],
    worst_segment: str,
    overfit_penalty: float,
    top_rows: List[Dict[str, Any]],
) -> str:
    top5_rows = top_rows[:5]
    lines = [
        "# 튜닝 검산 요약",
        "",
        f"- 실행 시각(asof): {asof}",
        f"- study_name: {study_name}",
        f"- mode: {mode}",
        f"- 기간: {start_date} ~ {end_date}",
        f"- best trial 번호: {best_trial_number}",
        (
            "- best params: "
            f"momentum_period={best_params.get('momentum_period')}, "
            f"volatility_period={best_params.get('volatility_period')}, "
            f"entry_threshold={best_params.get('entry_threshold')}, "
            f"stop_loss={best_params.get('stop_loss')}, "
            f"max_positions={best_params.get('max_positions')}"
        ),
        "",
        "## Full Period 요약",
        f"- CAGR: {_to_float(full_metrics.get('cagr')):.4f}%",
        f"- MDD: {_to_float(full_metrics.get('mdd')):.4f}%",
        f"- Sharpe: {_to_float(full_metrics.get('sharpe')):.4f}",
        "",
        "## 구간 리스크 요약",
        f"- 최악 구간: {worst_segment}",
        f"- 과최적화 벌점: {overfit_penalty:.4f}",
        "",
        "## 상위 5개 후보 비교 요약",
        "| 순위 | Trial | Score | momentum_period | volatility_period | entry_threshold | stop_loss | max_positions | worst_segment |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in top5_rows:
        lines.append(
            f"| {row['rank']} | {row['trial']} | {row['score']:.6f} | "
            f"{row['momentum_period']} | {row['volatility_period']} | "
            f"{row['entry_threshold']:.2f} | {row['stop_loss']:.4f} | "
            f"{row['max_positions']} | {row['worst_segment']} |"
        )
    lines.extend(
        [
            "",
            "## 현재 단계 해석",
            "이 결과는 후보 탐색용이며, Full Backtest 검증 후에만 승격 판단이 가능합니다.",
            "",
        ]
    )
    return "\n".join(lines)
