#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/predictive_risk_compare.py — P210-STEP10A Track B sweep

Track B predictive risk classifier 실험군(A0~A2, B0~B2)을 sweep 실행하고
비교 요약 산출물 + training report 를 생성한다.

단일 책임: experiments list → ML 학습 → rows (backtest + ML meta) → 산출물 생성
패턴: contextual_guard_compare.py 와 동일한 아키텍처

핵심 원칙:
- ML 은 연구/검증 전용. 운영 SSOT 에 자동 승격 금지.
- Main Run 은 변경하지 않음. Compare Run 전용.
- baseline_profile 에 따라 guard 적용 여부가 결정됨:
  - operational_control_a0 = g2_pos2_raew, guard 없음
  - research_candidate_b1 = g4_pos3_raew, pre_entry_guard 적용
- ML overlay 는 guard 이후 결과 위에서만 동작 (guard 탈락 후보 부활 금지).
"""

from __future__ import annotations

import csv as _csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Baseline profile → 실제 파라미터 매핑 ────────────────────────────
_PROFILE_MAP = {
    "operational_control_a0": {
        "holding_label": "g2_pos2_raew",
        "guard_mode": None,
    },
    "research_candidate_b1": {
        "holding_label": "g4_pos3_raew",
        "guard_mode": "pre_entry_guard",
    },
}


def _verdict(cagr: Optional[float], mdd: Optional[float]) -> str:
    if cagr is None or mdd is None:
        return "NO_DATA"
    if cagr > 15 and mdd < 10:
        return "PROMOTE"
    return "REJECT"


def _build_allocation_block(allocation_mode: str) -> Dict[str, Any]:
    if allocation_mode == "dynamic_equal_weight":
        return {
            "mode": "dynamic_equal_weight",
            "fallback_mode": "dynamic_equal_weight",
        }
    if allocation_mode == "risk_aware_equal_weight_v1":
        return {
            "mode": "risk_aware_equal_weight_v1",
            "volatility_lookback": 20,
            "volatility_floor": 0.05,
            "volatility_cap": 0.6,
            "weight_floor": 0.35,
            "weight_cap": 0.65,
            "fallback_mode": "dynamic_equal_weight",
        }
    raise ValueError(f"P210-STEP10A 허용되지 않은 allocation_mode: {allocation_mode!r}")


def _require_raw(raw: Dict[str, Any], key: str, variant: str) -> Any:
    if key not in raw:
        raise KeyError(
            f"P210-STEP10A: {variant} raw result 에 '{key}' 누락."
            f" BacktestRunner.run 이 REQUIRED 필드를 반환하지 않았음."
        )
    return raw[key]


# ─── Sweep ────────────────────────────────────────────────────────────
def run_predictive_risk_sweep(
    experiments: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    holding_experiments: List[Dict[str, Any]],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    format_result_fn: Callable,
    project_root: Path,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Track B 실험군을 sweep 실행.

    Returns:
        rows: 비교표 행 리스트
        all_training_logs: 전체 실험군의 training log 합산
    """
    from app.backtest.ml import build_predictions_for_sweep, format_training_report

    logger.info(
        f"[P210-STEP10A] predictive_risk_compare" f" 실험군 {len(experiments)}개 실행"
    )

    hs_by_name = {e["name"]: e for e in holding_experiments}
    ml_config = base_params["trackb_predictive_risk_classifier"]

    # REQUIRED: research_candidate_b1 은 pre_entry_guard 가 핵심 계약.
    # tracka_contextual_guard 블록이 없으면 B1 baseline 의미가 깨지므로
    # 즉시 실패해야 한다. operational_control_a0 는 guard 미사용이므로
    # 이 블록이 없어도 A0 자체는 동작하지만, Step10A 실험군에 B1 이
    # 포함되어 있으므로 전체적으로 REQUIRED.
    guard_params = base_params.get("tracka_contextual_guard")
    has_b1_profile = any(
        e["baseline_profile"] == "research_candidate_b1" for e in experiments
    )
    if has_b1_profile and guard_params is None:
        raise KeyError(
            "P210-STEP10A: research_candidate_b1 baseline 은"
            " tracka_contextual_guard 블록이 필수입니다."
            " SSOT 에 tracka_contextual_guard 가 없으면"
            " B1 pre_entry_guard 계약이 깨집니다."
        )

    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    all_training_logs: List[Dict[str, Any]] = []
    all_training_reports: List[Dict[str, Any]] = []
    # cache: profile 별 predictions 는 한번만 생성
    _pred_cache: Dict[str, Tuple[Dict, List, Any]] = {}

    for exp in experiments:
        name = exp["name"]
        profile = exp["baseline_profile"]
        ml_mode = exp["ml_mode"]
        model_family = exp["model_family"]
        # P210-STEP10A-2: per-experiment min_train_samples override
        mts_override = exp.get("min_train_samples_override")  # OPTIONAL: None for no_ml

        if profile not in _PROFILE_MAP:
            raise ValueError(
                f"P210-STEP10A: baseline_profile={profile!r}"
                f" 허용: {sorted(_PROFILE_MAP.keys())}"
            )
        pmap = _PROFILE_MAP[profile]
        holding_label = pmap["holding_label"]
        profile_guard_mode = pmap["guard_mode"]

        if holding_label not in hs_by_name:
            raise KeyError(
                f"P210-STEP10A: holding_label={holding_label!r}"
                f" 가 holding_structure_experiments 에 없음"
            )
        hs_spec = hs_by_name[holding_label]
        max_pos = hs_spec["max_positions"]
        alloc_mode = hs_spec["allocation_mode"]

        # ML predictions 구축 (profile + model_family + mts_override 단위 캐시)
        cache_key = f"{profile}__{model_family}__{mts_override}"
        if ml_mode != "none" and cache_key not in _pred_cache:
            # baseline 으로 한번 backtest 실행하여 rebalance_trace 확보
            _base_params = dict(base_params)
            _base_params["max_positions"] = max_pos
            _base_params["allocation"] = _build_allocation_block(alloc_mode)
            _base_params["holding_structure_experiments"] = None
            _base_params["allocation_experiments"] = None
            _base_params["tracka_contextual_guard_experiments"] = None
            _base_params["trackb_predictive_risk_classifier_experiments"] = None

            _base_raw = run_backtest_fn(
                price_data,
                _base_params,
                start,
                end,
                enable_regime=True,
                skip_baselines=True,
                contextual_guard_params=(guard_params if profile_guard_mode else None),
                tracka_guard_mode=profile_guard_mode,
            )
            _trace = _require_raw(_base_raw, "_rebalance_trace", f"{name}_base")

            predictions, training_log, dataset = build_predictions_for_sweep(
                price_data=price_data,
                rebalance_trace=_trace,
                config=ml_config,
                model_family=model_family,
                min_train_samples_override=mts_override,
            )
            _pred_cache[cache_key] = (predictions, training_log, dataset)

            report = format_training_report(
                training_log=training_log,
                dataset=dataset,
                config=ml_config,
                model_family=model_family,
            )
            all_training_reports.append(
                {
                    "profile": profile,
                    "model_family": model_family,
                    "min_train_samples_override": mts_override,
                    "report": report,
                }
            )
            all_training_logs.extend(training_log)

        # 실험 backtest 실행
        exp_params = dict(base_params)
        exp_params["max_positions"] = max_pos
        exp_params["allocation"] = _build_allocation_block(alloc_mode)
        exp_params["holding_structure_experiment_name"] = name
        exp_params["holding_structure_experiments"] = None
        exp_params["allocation_experiments"] = None
        exp_params["tracka_contextual_guard_experiments"] = None
        exp_params["trackb_predictive_risk_classifier_experiments"] = None

        # ML predictions 주입
        ml_preds = None
        if ml_mode != "none" and cache_key in _pred_cache:
            ml_preds = _pred_cache[cache_key][0]

        raw = run_backtest_fn(
            price_data,
            exp_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
            contextual_guard_params=(guard_params if profile_guard_mode else None),
            tracka_guard_mode=profile_guard_mode,
            ml_crash_predictions=ml_preds,
            ml_mode=ml_mode if ml_mode != "none" else None,
            ml_probability_threshold_soft=ml_config["probability_threshold_soft"],
            ml_probability_threshold_hard=ml_config["probability_threshold_hard"],
            ml_top_k_block_limit=ml_config["top_k_block_limit"],
            trackb_ml_experiment_name=name,
            trackb_baseline_profile=profile,
            trackb_model_family=model_family,
            trackb_label_horizon_days=ml_config["label_horizon_days"],
            trackb_label_crash_drawdown_threshold=ml_config[
                "label_crash_drawdown_threshold"
            ],
        )
        formatted = format_result_fn(
            raw,
            exp_params,
            start,
            end,
            price_data=price_data,
            run_mode="predictive_risk_experiment",
        )
        summary = formatted["summary"]
        meta = formatted["meta"]

        if "cagr" not in summary or "mdd" not in summary or "sharpe" not in summary:
            raise KeyError(f"P210-STEP10A: {name} summary 에 cagr/mdd/sharpe 누락")
        cagr = summary["cagr"]
        mdd = summary["mdd"]
        sharpe = summary["sharpe"]

        # P210-STEP10A-2: training log 에서 predicted/burnin dates 추출
        _cached_log = _pred_cache[cache_key][1] if cache_key in _pred_cache else []
        _predicted_dates = len(
            [e for e in _cached_log if e.get("status") == "PREDICTED"]
        )
        _burnin_dates = len([e for e in _cached_log if e.get("status") == "BURN_IN"])
        _total_labeled = 0
        if cache_key in _pred_cache:
            _ds = _pred_cache[cache_key][2]
            _total_labeled = int(_ds[_ds["label"].notna()].shape[0])

        rows.append(
            {
                "variant": name,
                "baseline_profile": profile,
                "ml_mode": ml_mode,
                "model_family": model_family,
                "min_train_samples": (
                    mts_override if mts_override is not None else "-"
                ),
                "total_labeled_samples": _total_labeled,
                "predicted_dates": _predicted_dates,
                "burnin_dates": _burnin_dates,
                "cagr": round(cagr, 4) if cagr is not None else None,
                "mdd": round(mdd, 4) if mdd is not None else None,
                "sharpe": round(sharpe, 4) if sharpe is not None else None,
                "total_trades": _require_raw(meta, "total_trades", name),
                "avg_held_positions": _require_raw(raw, "avg_held_positions", name),
                "predicted_positive_count": _require_raw(
                    raw, "trackb_predicted_positive_count", name
                ),
                "soft_gate_hits_total": _require_raw(
                    raw, "trackb_soft_gate_hits_total", name
                ),
                "hard_gate_hits_total": _require_raw(
                    raw, "trackb_hard_gate_hits_total", name
                ),
                "rerank_changes_total": _require_raw(
                    raw, "trackb_rerank_changes_total", name
                ),
                "ml_burnin_count": _require_raw(
                    raw, "trackb_ml_burnin_rebalance_count", name
                ),
                "verdict": _verdict(cagr, mdd),
            }
        )
        logger.info(
            f"[P210-STEP10A] {name}: profile={profile}"
            f" ml_mode={ml_mode} mts={mts_override}"
            f" CAGR={cagr} MDD={mdd}"
            f" predicted_dates={_predicted_dates}"
            f" soft_gate={raw['trackb_soft_gate_hits_total']}"
            f" burnin={raw['trackb_ml_burnin_rebalance_count']}"
        )

    # P210-STEP10A-2 정렬:
    # 1차 Predicted Dates 내림차순 (ML 개입 여부가 1차 관심)
    # 2차 MDD 오름차순
    # 3차 CAGR 내림차순
    def _sort_key(r: Dict[str, Any]):
        pd_v = r.get("predicted_dates", 0)
        mdd_v = r["mdd"]
        cagr_v = r["cagr"]
        return (
            -(pd_v if isinstance(pd_v, int) else 0),
            mdd_v if mdd_v is not None else 9999.0,
            -(cagr_v if cagr_v is not None else -9999.0),
        )

    rows.sort(key=_sort_key)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    _write_compare_outputs(rows, out_dir)
    _write_training_report(all_training_reports, out_dir)

    return rows, all_training_logs


# ─── Compare 산출물 생성 ─────────────────────────────────────────────
def _write_compare_outputs(rows: List[Dict[str, Any]], out_dir: Path) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # JSON
    payload = {"generated_at": generated_at, "rows": rows}
    (out_dir / "predictive_risk_compare.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # CSV
    if rows:
        csv_path = out_dir / "predictive_risk_compare.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Markdown
    md_path = out_dir / "predictive_risk_compare.md"
    md_path.write_text(
        "\n".join(_render_compare_md(rows, generated_at)), encoding="utf-8"
    )
    logger.info("[P210-STEP10A] predictive_risk_compare 산출물 생성 완료")


def _fmt_pct(v: Optional[float]) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def _render_compare_md(rows: List[Dict[str, Any]], generated_at: str) -> List[str]:
    lines = [
        "# P210-STEP10A-2 Track B Predictive Risk Classifier Compare",
        "",
        f"- generated_at: {generated_at}",
        f"- experiments: {len(rows)}",
        "- verdict 기준 유지: `CAGR > 15` AND `MDD < 10`",
        "- 정렬: 1차 Predicted Dates 내림차순," " 2차 MDD 오름차순, 3차 CAGR 내림차순",
        "- 변경축: `min_train_samples` only (50/75/100)",
        "",
        "## 비교표",
        "",
        "| Rank | Variant | Baseline Profile | ML Mode | Model Family"
        " | Min Train Samples | Total Labeled | Predicted Dates | Burnin Dates"
        " | Predicted Positive | SoftGate Hits"
        " | CAGR | MDD | Sharpe | Verdict |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        _sharpe_s = f"{r['sharpe']:.4f}" if r["sharpe"] is not None else "N/A"
        lines.append(
            f"| {r['rank']}"
            f" | {r['variant']}"
            f" | {r['baseline_profile']}"
            f" | {r['ml_mode']}"
            f" | {r['model_family']}"
            f" | {r['min_train_samples']}"
            f" | {r['total_labeled_samples']}"
            f" | {r['predicted_dates']}"
            f" | {r['burnin_dates']}"
            f" | {r['predicted_positive_count']}"
            f" | {r['soft_gate_hits_total']}"
            f" | {_fmt_pct(r['cagr'])}"
            f" | {_fmt_pct(r['mdd'])}"
            f" | {_sharpe_s}"
            f" | {r['verdict']} |"
        )

    # Q1~Q4 진단 (Step10A-2 기준)
    by_variant = {r["variant"]: r for r in rows}
    lines += ["", "## 진단 요약"]

    # Q1: 어떤 min_train_samples 부터 predicted_dates > 0 처음 발생하는가
    lines.append("")
    lines.append(
        "### Q1. 어떤 min_train_samples 부터 predicted_dates > 0 이 발생하는가"
    )
    _ml_rows = [r for r in rows if r["ml_mode"] != "none"]
    _activated = [r for r in _ml_rows if r["predicted_dates"] > 0]
    if _activated:
        _first = min(_activated, key=lambda r: r["min_train_samples"])
        lines.append(
            f"- **최초 활성화**: min_train_samples={_first['min_train_samples']}"
            f" ({_first['variant']})"
            f" → predicted_dates={_first['predicted_dates']}"
        )
    else:
        lines.append("- **활성화 없음**: 50/75/100 전 구간에서 predicted_dates=0")

    # Q2: 연구 baseline 에서 soft_gate 가 MDD 를 줄이는가
    b0 = by_variant.get("B0_research_no_ml")
    lines.append("")
    lines.append("### Q2. 연구 baseline 에서 soft_gate 가 MDD 를 실제로 줄이는가")
    # mts50/75/100 중 best vs B0 비교
    _b_sg = [
        r
        for r in rows
        if r["baseline_profile"] == "research_candidate_b1"
        and r["ml_mode"] == "soft_gate"
        and r["predicted_dates"] > 0
    ]
    if b0 and _b_sg:
        _best_b = min(_b_sg, key=lambda r: r["mdd"] if r["mdd"] is not None else 9999)
        _delta = (
            round(b0["mdd"] - _best_b["mdd"], 4) if _best_b["mdd"] is not None else None
        )
        lines.append(
            f"- B0 (no_ml): MDD {b0['mdd']:.2f}%"
            f" → {_best_b['variant']}: MDD {_best_b['mdd']:.2f}%"
            f" (Δ={_delta:+.2f}%p)"
            if _delta is not None
            else f"- B0 vs {_best_b['variant']}: 데이터 부족"
        )
    elif b0 and not _b_sg:
        lines.append("- soft_gate 실험군 중 predicted_dates > 0 인 것이 없음")
    else:
        lines.append("- 데이터 부족")

    # Q3: CAGR 훼손폭은 허용 가능한가
    lines.append("")
    lines.append("### Q3. CAGR 훼손폭은 허용 가능한가")
    if b0 and _b_sg:
        for _r in sorted(_b_sg, key=lambda x: x["min_train_samples"]):
            _cd = round(b0["cagr"] - _r["cagr"], 4) if _r["cagr"] is not None else None
            if _cd is not None:
                lines.append(
                    f"- {_r['variant']} (mts={_r['min_train_samples']}):"
                    f" CAGR {_r['cagr']:.2f}% (ΔCAGR={-_cd:+.2f}%p vs B0)"
                    f" | soft_gate_hits={_r['soft_gate_hits_total']}"
                )
    else:
        lines.append("- soft_gate 활성 실험군 없음")

    # Q4: Step10B 로 넘길 ML 설정이 존재하는가
    lines.append("")
    lines.append("### Q4. Step10B 로 넘길 ML 설정이 존재하는가")
    promoted = [r["variant"] for r in rows if r["verdict"] == "PROMOTE"]
    if promoted:
        top = rows[0]
        lines.append(f"- **승격 후보 존재**: {', '.join(promoted)}")
        lines.append(
            f"- **최상위**: `{top['variant']}`"
            f" (MDD {_fmt_pct(top['mdd'])}, CAGR {_fmt_pct(top['cagr'])})"
        )
    else:
        # Step10A-2 실패 판정 기준 체크
        any_predicted = any(r["predicted_dates"] > 0 for r in _ml_rows)
        any_hits = any(r["soft_gate_hits_total"] > 0 for r in _ml_rows)
        if not any_predicted:
            lines.append(
                "- **Track B 데이터 규모 한계 확인**:"
                " 50/75/100 전 구간에서 predicted_dates=0."
                " Track B 는 현재 universe/기간에서 한계."
            )
        elif not any_hits:
            lines.append(
                "- **예측은 생겼지만 soft_gate 미발동**:"
                " crash probability 가 threshold 미만."
                " threshold 하향 또는 모델 보강 필요."
            )
        else:
            if rows:
                best = rows[0]
                lines.append("- **승격 후보 없음**: CAGR>15 AND MDD<10 동시 충족 없음")
                lines.append(
                    f"- **차선**: `{best['variant']}`"
                    f" (MDD {_fmt_pct(best['mdd'])},"
                    f" CAGR {_fmt_pct(best['cagr'])})"
                )
            lines.append(
                "- **다음 단계**: Step10B threshold 튜닝" " 또는 Track B 한계 판정"
            )

    lines += [
        "",
        "## Notes",
        "- Step10A 는 연구/검증 전용. 운영 SSOT 에 자동 승격 금지.",
        "- ML 은 walk_forward_expanding 학습. 초기 burn-in 구간 존재.",
        "- soft_gate / rerank 은 guard 이후 결과 위에서만 동작"
        " (guard 탈락 후보 부활 금지).",
    ]
    return lines


# ─── Training Report 산출물 ──────────────────────────────────────────
def _write_training_report(reports: List[Dict[str, Any]], out_dir: Path) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # JSON
    payload = {"generated_at": generated_at, "reports": reports}
    (out_dir / "predictive_risk_training_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Markdown
    md_lines = [
        "# P210-STEP10A Track B Training Report",
        "",
        f"- generated_at: {generated_at}",
        f"- profiles: {len(reports)}",
        "",
    ]
    for entry in reports:
        profile = entry["profile"]
        mf = entry["model_family"]
        report = entry["report"]
        ld = report["label_definition"]
        ci = report["class_imbalance"]
        wf = report["walk_forward_summary"]
        # REQUIRED: format_training_report 가 항상 설정 (빈 dict 포함)
        fi = report["top_feature_importance"]

        md_lines += [
            f"## {profile} / {mf}",
            "",
            "### Label 정의",
            f"- horizon: {ld['horizon_days']}영업일",
            f"- crash_drawdown_threshold: {ld['crash_drawdown_threshold']}",
            f"- crash_return_threshold: {ld['crash_return_threshold']}",
            f"- 양성 의미: {ld['positive_meaning']}",
            "",
            "### Feature Set",
            f"- version: {report['feature_set']['version']}",
            f"- feature 수: {report['feature_set']['count']}",
            f"- benchmark: {report['feature_set']['benchmark_ticker']}",
            "",
            "### Training Scheme",
            f"- scheme: {report['training_scheme']}",
            f"- min_train_samples: {wf['min_train_samples']}",
            "",
            "### Class Imbalance",
            f"- total_labeled_samples: {ci['total_labeled_samples']}",
            f"- positive: {ci['positive_count']}" f" ({ci['positive_ratio']:.1%})",
            f"- negative: {ci['negative_count']}",
            "",
            "### Walk-Forward Summary",
            f"- total rebalance dates: {wf['total_rebalance_dates']}",
            f"- predicted dates: {wf['predicted_dates']}",
            f"- burn-in dates: {wf['burnin_dates']}",
            f"- first predict: {wf['first_predict_date']}",
            f"- last predict: {wf['last_predict_date']}",
            "",
            "### Top Feature Importance",
        ]
        if fi:
            md_lines.append("| Feature | Importance |")
            md_lines.append("|---|---:|")
            for feat, imp in fi.items():
                md_lines.append(f"| {feat} | {imp:.6f} |")
        else:
            md_lines.append("- (데이터 없음)")

        md_lines += [
            "",
            "### Leakage Check",
            f"- passed: {report['leakage_check_passed']}",
            "",
            "### 해석 경고",
            f"- {report['interpretation_warning']}",
            "",
        ]

    md_path = out_dir / "predictive_risk_training_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info("[P210-STEP10A] predictive_risk_training_report 생성 완료")
