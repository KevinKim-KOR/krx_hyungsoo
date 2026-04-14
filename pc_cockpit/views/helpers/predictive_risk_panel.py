#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_cockpit/views/helpers/predictive_risk_panel.py — P210-STEP10A UI helper

Track B Predictive Risk Classifier 관련 Streamlit 렌더러 4개.
workflow.py / parameter_editor.py 에서 호출.

R6 원칙: 순수 view 함수. 데이터 변환 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st


def render_predictive_risk_panel_for_parameters(p: Dict[str, Any]) -> None:
    """Parameters 탭의 Track B Predictive Risk Classifier 섹션.

    표시: baseline_profile / ml_mode / model_family / thresholds / 실험군 목록.
    """
    st.subheader("Track B Predictive Risk Classifier (P210-STEP10A)")

    config = p.get("trackb_predictive_risk_classifier")
    if config is None:
        st.info("trackb_predictive_risk_classifier 설정 없음 (비활성)")
        return

    # REQUIRED: param_loader 가 이미 검증했으므로 직접 subscript
    c1, c2, c3 = st.columns(3)
    c1.metric("Label Horizon", f"{config['label_horizon_days']}일")
    c2.metric("Soft Threshold", f"{config['probability_threshold_soft']}")
    c3.metric("Hard Threshold", f"{config['probability_threshold_hard']}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Training Scheme", config["training_scheme"])
    c5.metric("Min Train Samples", config["min_train_samples"])
    c6.metric("Decision Policy", config["decision_policy"])

    st.caption(
        f"Crash DD: {config['label_crash_drawdown_threshold']}"
        f" | Crash Return: {config['label_crash_return_threshold']}"
        f" | Top-K Block: {config['top_k_block_limit']}"
        f" | Feature Set: {config['feature_set_version']}"
    )

    experiments = p.get("trackb_predictive_risk_classifier_experiments")
    if experiments:
        import pandas as _pd

        exp_rows = [
            {
                "variant": e["name"],
                "baseline_profile": e["baseline_profile"],
                "label_profile": e.get("label_profile", "-"),
                "action_policy": e.get("action_policy", "-"),
                "ml_mode": e["ml_mode"],
                "model_family": e["model_family"],
                "min_train_samples_override": e.get("min_train_samples_override"),
            }
            for e in experiments
        ]
        st.caption(
            f"등록된 실험군: {len(experiments)}개"
            f" (A0~A3 = operational, B0~B3 = research)"
        )
        st.dataframe(_pd.DataFrame(exp_rows), use_container_width=True)
    else:
        st.caption("실험군 미등록")


def render_predictive_risk_compare_expander(base_dir: Path) -> None:
    """Backtest 탭의 Predictive Risk Classifier Compare expander."""
    _cmp_path = base_dir / "reports" / "tuning" / "predictive_risk_compare.csv"
    if not _cmp_path.exists():
        return

    import pandas as _pd

    with st.expander(
        "Predictive Risk Classifier Compare (P210-STEP10A)",
        expanded=True,
    ):
        _df = _pd.read_csv(_cmp_path)
        st.dataframe(_df, use_container_width=True)
        st.caption(
            "정렬: MDD 오름차순 -> CAGR 내림차순."
            " verdict 기준: CAGR > 15 AND MDD < 10."
            " 상세 진단(Q1~Q4) 은 predictive_risk_compare.md 참조."
        )


def render_predictive_risk_training_expander(base_dir: Path) -> None:
    """Backtest 탭의 ML Training Summary expander."""
    _report_path = (
        base_dir / "reports" / "tuning" / "predictive_risk_training_report.json"
    )
    if not _report_path.exists():
        return

    import json

    with st.expander("ML Training Summary (P210-STEP10A)", expanded=False):
        with open(_report_path, encoding="utf-8") as f:
            data = json.load(f)

        reports = data.get("reports")
        if not reports:
            st.caption("Training report 데이터 없음")
            return

        for entry in reports:
            profile = entry["profile"]
            mf = entry["model_family"]
            report = entry["report"]
            ci = report["class_imbalance"]
            wf = report["walk_forward_summary"]

            st.markdown(f"**{profile} / {mf}**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Samples", ci["total_labeled_samples"])
            col2.metric(
                "Positive Ratio",
                f"{ci['positive_ratio']:.1%}",
            )
            col3.metric(
                "Predicted Dates",
                f"{wf['predicted_dates']} / {wf['total_rebalance_dates']}",
            )
            st.caption(
                f"Burn-in: {wf['burnin_dates']}회"
                f" | First predict: {wf['first_predict_date']}"
                f" | Last predict: {wf['last_predict_date']}"
            )

            # Feature importance
            fi = report["top_feature_importance"]
            if fi:
                import pandas as _pd_fi

                fi_df = _pd_fi.DataFrame(
                    [{"feature": k, "importance": v} for k, v in fi.items()]
                )
                st.dataframe(fi_df, use_container_width=True)

            st.caption(f"Leakage check: {report['leakage_check_passed']}")
            st.divider()


def render_predictive_risk_evidence_caption(bt_meta: Dict[str, Any]) -> None:
    """Evidence/Backtest 탭의 Track B 요약 caption.

    rule 6/7: format_result 가 trackb_* 필드를 항상 주입한다.
    필드 존재를 trackb_ml_mode 로 감지. 없으면 구버전 산출물 안내.
    """
    if "trackb_ml_mode" not in bt_meta:
        st.caption("Track B Predictive Risk: (구버전 산출물 — Step10A 메타 없음)")
        return

    # REQUIRED: format_result 가 항상 설정
    ml_mode = bt_meta["trackb_ml_mode"]
    profile = bt_meta["trackb_baseline_profile"]
    model = bt_meta["trackb_model_family"]
    predicted_pos = bt_meta["trackb_predicted_positive_count"]
    soft_hits = bt_meta["trackb_soft_gate_hits_total"]
    burnin = bt_meta["trackb_ml_burnin_rebalance_count"]

    # WHITELIST (display): None baseline/model = main run (ML 미사용)
    profile_str = profile if profile is not None else "-"
    model_str = model if model is not None else "-"

    # Verdict: main run 의 promotion verdict 와 동일 기준 (CAGR>15 AND MDD<10)
    # bt_meta 에서 summary 수준의 cagr/mdd 를 직접 접근할 수 없으므로
    # main run 은 항상 운영 기준 — verdict 는 별도 파일에서 읽거나
    # "main run verdict 는 Promotion Verdict 섹션 참조" 로 안내.
    # Step10A 실험군별 verdict 는 compare 표에서 확인.
    # Main Run verdict 계산: ml_mode 가 "none" 이면 ML 미적용.
    # 실험군별 verdict 는 evidence Track B 비교표에서 확인.
    # Main Run 의 CAGR/MDD 기반 verdict 는 Promotion Verdict 섹션에서 이미
    # 표시되므로, 여기서는 ML 적용 여부만 구분하여 표기.
    if ml_mode == "none" or ml_mode is None:
        verdict_str = "REJECT (Main Run, ML 미적용)"
    else:
        verdict_str = "실험군별 Compare 표 참조"

    # Main run 은 ML 미적용이므로 predicted_dates=0, min_train_samples=N/A.
    # 실험군별 상세는 Compare 표 + Training Summary 에서 확인.
    st.caption(
        f"Track B ML:"
        f" profile=`{profile_str}`"
        f" | mode=`{ml_mode}`"
        f" | model=`{model_str}`"
        f" | min_train_samples=N/A (Main Run)"
        f" | predicted_dates=0 (Main Run)"
        f" | predicted_pos={predicted_pos}"
        f" | soft_gate={soft_hits}"
        f" | burnin={burnin}"
        f" | verdict={verdict_str}"
    )
