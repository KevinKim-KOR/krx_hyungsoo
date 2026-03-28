"""Tune 결과 카드 (render_workflow_p170 내부에서 호출)."""

import time

import pandas as pd
import streamlit as st

from pc_cockpit.services.config import BASE_DIR, format_file_mtime
from pc_cockpit.services.json_io import load_json, apply_tune_best_params_to_ssot
from pc_cockpit.services.promotion_verdict import refresh_promotion_verdict_local


def render_tune_results_card(params_data):
    """🏆 최신 Optuna 튜닝 결과 카드."""
    st.markdown("##### 🏆 최신 Optuna 튜닝 결과")
    TUNE_RESULT_PATH = BASE_DIR / "reports" / "tuning" / "tuning_results.json"
    try:
        if not TUNE_RESULT_PATH.exists():
            st.info("ℹ️ 아직 튜닝 결과 없음 — 먼저 ▶️ Run Tune을 실행하세요.")
        else:
            tune_data = load_json(TUNE_RESULT_PATH)
            if not tune_data:
                st.warning("⚠️ 튜닝 결과 파일 파싱 실패")
            else:
                tune_meta = tune_data.get("meta", {})
                bp = tune_data.get("best_params", {})
                bs = tune_data.get("best_summary", {})
                st.success("✅ 최근 실행 성공")
                c1, c2, c3 = st.columns(3)
                c1.metric("Best Score", f"{tune_data.get('best_score', 0):.4f}")
                c2.metric("Best Trial", f"#{tune_meta.get('best_trial_number', '?')}")
                c3.metric("총 Trials", tune_meta.get("n_trials_total", "?"))
                c4, c5, c6 = st.columns(3)
                c4.metric("Sharpe", f"{bs.get('sharpe', 0):.4f}")
                c5.metric("MDD", f"{bs.get('mdd_pct', 0):.2f}%")
                c6.metric("CAGR", f"{bs.get('cagr', 0):.4f}")
                st.caption(
                    f"Study: {tune_meta.get('study_name', '?')} | Resume: {'✅' if tune_meta.get('resume_enabled') else '❌'} | asof: {tune_meta.get('asof', '?')}"
                )
                with st.expander("최적 파라미터", expanded=False):
                    st.json(bp)

                apply_col1, apply_col2 = st.columns([2, 3])
                if apply_col1.button(
                    "🚀 1등 파라미터 SSOT 자동 적용",
                    key="auto_apply_tune_best_params",
                    use_container_width=True,
                ):
                    try:
                        applied_params = apply_tune_best_params_to_ssot(bp)
                        st.success(
                            "1등 후보 5축을 현재 파라미터(SSOT)에 자동 적용했습니다."
                        )
                        st.caption(
                            "적용 값: "
                            f"momentum_period={applied_params['params']['lookbacks']['momentum_period']}, "
                            f"volatility_period={applied_params['params']['lookbacks']['volatility_period']}, "
                            f"entry_threshold={applied_params['params']['decision_params']['entry_threshold']}, "
                            f"exit_threshold={applied_params['params']['decision_params']['exit_threshold']}, "
                            f"max_positions={applied_params['params']['position_limits']['max_positions']}"
                        )
                        time.sleep(1.0)
                        st.rerun()
                    except Exception as e:
                        st.error(f"SSOT 자동 적용 실패: {e}")
                apply_col2.caption(
                    "튜닝 1등 후보의 momentum_period / volatility_period / "
                    "entry_threshold / stop_loss(exit_threshold) / max_positions을 현재 SSOT에 덮어씁니다."
                )
                objective_version = tune_data.get(
                    "objective_version",
                    tune_meta.get("objective_version", "N/A"),
                )
                worst_segment = tune_data.get("worst_segment", "N/A")
                metric_scale_norm = tune_data.get(
                    "metric_scale_normalized",
                    tune_meta.get("metric_scale_normalized", "decimal"),
                )
                metric_scale_source = tune_data.get(
                    "metric_scale_source",
                    tune_meta.get("metric_scale_source", "unknown"),
                )
                try:
                    overfit_penalty = float(
                        tune_data.get("overfit_penalty", 0.0) or 0.0
                    )
                    cagr_agg = float(tune_data.get("cagr_agg", 0.0) or 0.0)
                    mdd_agg = float(tune_data.get("mdd_agg", 0.0) or 0.0)
                    sharpe_agg = float(tune_data.get("sharpe_agg", 0.0) or 0.0)
                except (TypeError, ValueError):
                    overfit_penalty = 0.0
                    cagr_agg = 0.0
                    mdd_agg = 0.0
                    sharpe_agg = 0.0

                o1, o2 = st.columns(2)
                o1.caption("목적함수 버전")
                o1.write(objective_version)
                o2.caption("최악 구간")
                o2.write(worst_segment)

                o3, o4 = st.columns(2)
                o3.caption("과최적화 벌점")
                o3.write(f"{overfit_penalty:.4f}")
                o4.caption("지표 스케일")
                o4.write(f"{metric_scale_norm} ({metric_scale_source})")

                st.caption(
                    "최종 점수 분해: "
                    f"CAGR_agg={cagr_agg:.4f} / MDD_agg={mdd_agg:.4f} / "
                    f"Sharpe_agg={sharpe_agg:.4f} / Penalty={overfit_penalty:.4f}"
                )

                # Segment evaluation display
                seg_enabled = tune_data.get("segment_evaluation_enabled", False)
                seg_ready = tune_data.get("segment_eval_ready", False)
                seg_status = tune_data.get("segment_status", "")
                seg_m = tune_data.get("segment_metrics", {})
                has_seg_data = bool(
                    seg_m
                    and seg_m.get("SEG_1")
                    and seg_m.get("SEG_2")
                    and seg_m.get("SEG_3")
                )

                if has_seg_data:
                    seg_scheme = tune_data.get("segment_scheme", "equal_3way")
                    full_m = tune_data.get("full_period_metrics", {})
                    rows = [
                        {
                            "구간": "Full",
                            "CAGR": f"{full_m.get('cagr', 0):.2f}%",
                            "MDD": f"{full_m.get('mdd', 0):.2f}%",
                            "Sharpe": f"{full_m.get('sharpe', 0):.4f}",
                            "일수": full_m.get("days", "?"),
                        }
                    ]
                    for key in ["SEG_1", "SEG_2", "SEG_3"]:
                        sm = seg_m.get(key, {})
                        rows.append(
                            {
                                "구간": key,
                                "CAGR": f"{sm.get('cagr', 0):.2f}%",
                                "MDD": f"{sm.get('mdd', 0):.2f}%",
                                "Sharpe": f"{sm.get('sharpe', 0):.4f}",
                                "일수": sm.get("days", "?"),
                            }
                        )
                    st.markdown(f"**📐 구간 평가** (`{seg_scheme}`)")
                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                elif seg_enabled and not seg_ready:
                    st.warning(f"⚠️ 세그먼트 평가 불가 ({seg_status})")
                else:
                    st.info("ℹ️ 세그먼트 평가 없음 — Run Tune을 다시 실행하세요.")

                promotion_verdict = refresh_promotion_verdict_local(tune_data)
                validation_pack = tune_data.get("validation_pack", {})
                validation_files = validation_pack.get("files", {})
                validation_file_rows = []
                for filename in [
                    "trials_top20.csv",
                    "best_trial_segments.csv",
                    "tuning_summary.md",
                    "promotion_verdict.json",
                    "promotion_verdict.md",
                ]:
                    file_meta = validation_files.get(filename, {})
                    file_path = BASE_DIR / "reports" / "tuning" / filename
                    validation_file_rows.append(
                        {
                            "검산 파일": filename,
                            "생성 여부": (
                                "예"
                                if file_meta.get("exists", file_path.exists())
                                else "아니오"
                            ),
                            "최신 시각": file_meta.get("updated_at")
                            or format_file_mtime(file_path),
                        }
                    )
                st.markdown("**검산 파일**")
                st.dataframe(
                    pd.DataFrame(validation_file_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                verdict_color = {
                    "PROMOTE_CANDIDATE": "success",
                    "REVIEW_REQUIRED": "warning",
                    "REJECT": "error",
                }.get(promotion_verdict.get("verdict"), "warning")
                verdict_label = {
                    "PROMOTE_CANDIDATE": "승격 후보",
                    "REVIEW_REQUIRED": "재검토 필요",
                    "REJECT": "기각",
                }.get(promotion_verdict.get("verdict"), "기각")
                verdict_text = (
                    f"현재 판정: {verdict_label} | "
                    f"SSOT 반영: {'예' if promotion_verdict.get('candidate_applied_to_ssot') else '아니오'} | "
                    f"CAGR > 15: {'예' if promotion_verdict.get('criteria_check', {}).get('cagr_gt_15') else '아니오'} | "
                    f"MDD < 10: {'예' if promotion_verdict.get('criteria_check', {}).get('mdd_lt_10') else '아니오'}"
                )
                st.markdown("**승격 판정**")
                if verdict_color == "success":
                    st.success(verdict_text)
                elif verdict_color == "warning":
                    st.warning(verdict_text)
                else:
                    st.error(verdict_text)

                verdict_reason_rows = [
                    {"판정 사유": reason}
                    for reason in promotion_verdict.get("reasons", [])
                ]
                if verdict_reason_rows:
                    st.dataframe(
                        pd.DataFrame(verdict_reason_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                ssot_compare = promotion_verdict.get("ssot_vs_best_params", {})
                if ssot_compare:
                    compare_rows = []
                    axis_labels = {
                        "momentum_period": "모멘텀 기간",
                        "volatility_period": "변동성 기간",
                        "entry_threshold": "진입 임계치",
                        "stop_loss": "손절값",
                        "max_positions": "최대 보유수",
                    }
                    for key in [
                        "momentum_period",
                        "volatility_period",
                        "entry_threshold",
                        "stop_loss",
                        "max_positions",
                    ]:
                        item = ssot_compare.get(key, {})
                        compare_rows.append(
                            {
                                "항목": axis_labels.get(key, key),
                                "튜닝 1등": item.get("best", "-"),
                                "현재 SSOT": item.get("current", "-"),
                                "일치": "예" if item.get("match") else "아니오",
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(compare_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                st.info(f"다음 조치: {promotion_verdict.get('next_action', '-')}")
                top5_rows = (
                    validation_pack.get("top5_comparison")
                    or tune_data.get("trials_top20", [])[:5]
                )
                if top5_rows:
                    top5_display = pd.DataFrame(
                        [
                            {
                                "순위": row.get("rank", "?"),
                                "Trial": row.get("trial", "?"),
                                "점수": f"{float(row.get('score', 0.0)):.4f}",
                                "모멘텀 기간": row.get("momentum_period", "?"),
                                "변동성 기간": row.get("volatility_period", "?"),
                                "진입 임계치": row.get("entry_threshold", "?"),
                                "손절값": row.get("stop_loss", "?"),
                                "최대 보유수": row.get("max_positions", "?"),
                                "최악 구간": row.get("worst_segment", "N/A"),
                            }
                            for row in top5_rows
                        ]
                    )
                    st.markdown("**상위 후보 비교 (Top 5)**")
                    st.dataframe(
                        top5_display,
                        use_container_width=True,
                        hide_index=True,
                    )
            # --- 감도 보정 결과 섹션 ---
            sensitivity_md_path = (
                BASE_DIR / "reports" / "tuning" / "sensitivity_summary.md"
            )
            if sensitivity_md_path.exists():
                with st.expander("감도 보정 결과", expanded=False):
                    try:
                        md_text = sensitivity_md_path.read_text(encoding="utf-8")
                        # 범위 추출
                        vol_range = "—"
                        et_range = "—"
                        vol_low = False
                        et_low = False
                        for line in md_text.split("\n"):
                            if "최종 범위: 기존 유지 (12~24)" in line:
                                vol_range = "12~24 (기존 유지)"
                                vol_low = True
                            elif (
                                "최종 채택 범위:" in line
                                and "volatility" not in line.lower()
                            ):
                                pass
                            if "최종 범위: 기존 유지 (0.01~0.05)" in line:
                                et_range = "0.01~0.05 (기존 유지)"
                                et_low = True
                            if "최종 채택 범위:" in line:
                                if vol_range == "—":
                                    vol_range = line.split(":")[-1].strip()
                                elif et_range == "—":
                                    et_range = line.split(":")[-1].strip()

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("변동성 기간 범위", vol_range)
                            if vol_low:
                                st.caption("⚠️ LOW_SENSITIVITY")
                        with col2:
                            st.metric("진입 임계치 범위", et_range)
                            if et_low:
                                st.caption("⚠️ LOW_SENSITIVITY")

                        st.markdown("**검산 파일**")
                        st.caption(
                            "sensitivity_volatility_period.csv / "
                            "sensitivity_entry_threshold.csv / "
                            "sensitivity_summary.md"
                        )
                    except Exception as se:
                        st.warning(f"감도 보정 결과 로드 실패: {se}")

    except Exception as e:
        st.error(f"튜닝 결과 표시 중 오류: {e}")
