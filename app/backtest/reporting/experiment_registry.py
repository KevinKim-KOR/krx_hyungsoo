#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/experiment_registry.py — P210-STEP10Z / 10Z-3

P206~P210B 전체 실험을 분류하고 현재 기준선을 고정하는 registry/state/ledger
산출물을 생성한다.

P210-STEP10Z-3: Main Run / Research Candidate / Track B Latest 등 metric 은
이상 모듈 상수가 아니라 canonical evidence/compare json 에서 동적으로 읽어와
fail-loud 로 채운다. stale 하드코딩 금지.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ─── 현재 기준선 식별자 (이름만) ─────────────────────────────────────
CURRENT_MAIN_RUN = "g2_pos2_raew"
CURRENT_OPERATIONAL_CONTROL = "A0_operational_no_ml"
CURRENT_RESEARCH_CANDIDATE = "B1_pos3_raew_pre_entry_guard"
TRACK_B_LATEST_VARIANT = "B2_research_L1_softgate"
LAST_COMPLETED_CHAPTER = "P210-STEP10B"
NEXT_PLANNED_CHAPTER = "Step10C 승격 검토 또는 Track B label/action 한계 판정"

# ─── canonical source paths (project_root 기준 상대) ─────────────────
_EVIDENCE_MD_REL = Path("reports/tuning/dynamic_evidence_latest.md")
_PREDICTIVE_COMPARE_REL = Path("reports/tuning/predictive_risk_compare.json")
_GUARD_COMPARE_REL = Path("reports/tuning/contextual_guard_compare.json")


# ─── canonical loader (fail-loud) ────────────────────────────────────
def _extract_perf_pct(text: str, label: str) -> float:
    """dynamic_evidence_latest.md 의 Performance 표에서 `| label | 12.32% |`."""
    m = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([0-9]+\.[0-9]+)%\s*\|", text)
    if not m:
        raise RuntimeError(
            f"[P210-STEP10Z-3] evidence Performance row missing: {label}"
        )
    return float(m.group(1))


def _extract_perf_sharpe(text: str) -> float:
    """`| Sharpe | 1.1216 |` 형태 (% 없음)."""
    m = re.search(r"\|\s*Sharpe\s*\|\s*([0-9]+\.[0-9]+)\s*\|", text)
    if not m:
        raise RuntimeError("[P210-STEP10Z-3] evidence Performance row missing: Sharpe")
    return float(m.group(1))


def _load_evidence_meta(project_root: Path) -> Dict[str, Any]:
    md_path = project_root / _EVIDENCE_MD_REL
    if not md_path.exists():
        raise RuntimeError(
            f"[P210-STEP10Z-3] canonical evidence missing: {md_path}"
            " — analysis-only sync 전 evidence 가 먼저 존재해야 함"
        )
    text = md_path.read_text(encoding="utf-8")

    m = re.search(r"^- generated_at:\s*(\S+)", text, re.MULTILINE)
    if not m:
        raise RuntimeError(
            f"[P210-STEP10Z-3] evidence generated_at parse 실패: {md_path}"
        )
    return {
        "generated_at": m.group(1),
        "performance": {
            "cagr_pct": _extract_perf_pct(text, "CAGR"),
            "mdd_pct": _extract_perf_pct(text, "MDD"),
            "sharpe": _extract_perf_sharpe(text),
        },
    }


def _load_compare(
    project_root: Path, rel_path: Path
) -> Tuple[str, List[Dict[str, Any]]]:
    p = project_root / rel_path
    if not p.exists():
        raise RuntimeError(f"[P210-STEP10Z-3] canonical compare missing: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if "generated_at" not in data or "rows" not in data:
        raise RuntimeError(
            f"[P210-STEP10Z-3] compare json schema invalid (need generated_at+rows):"
            f" {p}"
        )
    return data["generated_at"], data["rows"]


def _find_row(
    rows: List[Dict[str, Any]], key: str, value: str, source_label: str
) -> Dict[str, Any]:
    for r in rows:
        if r.get(key) == value:
            return r
    raise RuntimeError(f"[P210-STEP10Z-3] {source_label}: row missing {key}={value!r}")


def load_canonical_metrics(project_root: Path) -> Dict[str, Any]:
    """모든 canonical source 를 한 번 읽고 metric 묶음 반환.

    누락 시 즉시 RuntimeError.
    """
    evidence = _load_evidence_meta(project_root)
    pred_gen, pred_rows = _load_compare(project_root, _PREDICTIVE_COMPARE_REL)
    guard_gen, guard_rows = _load_compare(project_root, _GUARD_COMPARE_REL)

    research_row = _find_row(
        guard_rows,
        "variant",
        CURRENT_RESEARCH_CANDIDATE,
        "contextual_guard_compare",
    )
    g4_row = _find_row(
        guard_rows, "variant", "B0_pos3_raew_no_guard", "contextual_guard_compare"
    )
    b0_row = _find_row(
        pred_rows, "variant", "B0_research_no_ml", "predictive_risk_compare"
    )
    trackb_row = _find_row(
        pred_rows, "variant", TRACK_B_LATEST_VARIANT, "predictive_risk_compare"
    )

    return {
        "evidence_generated_at": evidence["generated_at"],
        "predictive_compare_generated_at": pred_gen,
        "contextual_guard_compare_generated_at": guard_gen,
        "main_run_metrics": {
            "cagr_pct": evidence["performance"]["cagr_pct"],
            "mdd_pct": evidence["performance"]["mdd_pct"],
            "sharpe": evidence["performance"]["sharpe"],
        },
        "research_candidate_metrics": {
            "cagr_pct": research_row["cagr"],
            "mdd_pct": research_row["mdd"],
            "sharpe": research_row["sharpe"],
        },
        "g4_baseline_metrics": {
            "cagr_pct": g4_row["cagr"],
            "mdd_pct": g4_row["mdd"],
            "sharpe": g4_row["sharpe"],
        },
        "p210a_b0_metrics": {
            "cagr_pct": b0_row["cagr"],
            "mdd_pct": b0_row["mdd"],
            "sharpe": b0_row["sharpe"],
        },
        "track_b_latest": {
            "variant": trackb_row["variant"],
            "label_profile": trackb_row["label_profile"],
            "action_policy": trackb_row["action_policy"],
            "min_train_samples": trackb_row["min_train_samples"],
            "label_positive_ratio_pct": (
                float(trackb_row["label_positive_ratio"]) * 100.0
            ),
            "predicted_dates": trackb_row["predicted_dates"],
            "soft_gate_hits": trackb_row["soft_gate_hits_total"],
            "cagr_pct": trackb_row["cagr"],
            "mdd_pct": trackb_row["mdd"],
            "sharpe": trackb_row["sharpe"],
        },
    }


def _evidence_date(metrics: Dict[str, Any]) -> str:
    """evidence_generated_at ('2026-04-14T23:38:00+09:00') → '2026-04-14'."""
    return metrics["evidence_generated_at"].split("T", 1)[0]


def _format_latest_trackb_summary(metrics: Dict[str, Any]) -> str:
    tb = metrics["track_b_latest"]
    return (
        f"Step10B label/action 재설계: {tb['variant']}"
        f" (label={tb['label_profile']}, action={tb['action_policy']})."
        f" CAGR {tb['cagr_pct']:.2f}% / MDD {tb['mdd_pct']:.2f}% / Sharpe"
        f" {tb['sharpe']:.4f}."
        f" MDD 전 구간 {tb['mdd_pct']:.2f}% 불변 → Track B 구조적 한계 확인"
    )


def _format_last_rejected_axis(metrics: Dict[str, Any]) -> str:
    tb_mdd = metrics["track_b_latest"]["mdd_pct"]
    return (
        "Track B label/action 재설계로도 MDD 개선 실패"
        f" (L0/L1/L2 × softgate/rerank 전 구간 MDD {tb_mdd:.2f}% 불변)"
    )


# ─── Registry 데이터 ─────────────────────────────────────────────────
def _build_registry_rows(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """전체 실험 registry 행 생성.

    P210-STEP10Z-3: CURRENT_* / 최신 비교 대상 4행은 canonical metrics 로 채움.
    historical 행은 그대로 (당시 검증 시점 stale 가능, status_tag 로 구분).
    """
    ev_date = _evidence_date(metrics)
    main = metrics["main_run_metrics"]
    research = metrics["research_candidate_metrics"]
    g4 = metrics["g4_baseline_metrics"]
    b0 = metrics["p210a_b0_metrics"]
    tb = metrics["track_b_latest"]

    return [
        {
            "chapter": "P206",
            "variant_or_profile": CURRENT_MAIN_RUN,
            "purpose": "운영 baseline (pos2, risk_aware_equal_weight_v1)",
            "run_type": "Main Run",
            "status_tag": "CURRENT_MAIN",
            "cagr": main["cagr_pct"],
            "mdd": main["mdd_pct"],
            "sharpe": main["sharpe"],
            "verdict": "REJECT",
            "decision": "운영 기준선 유지. CAGR>15 AND MDD<10 미달.",
            "source_artifact": "dynamic_evidence_latest.md",
            "last_validated_at": ev_date,
        },
        {
            "chapter": "P207/P208",
            "variant_or_profile": "g4_pos3_raew",
            "purpose": "연구 baseline (pos3, risk_aware_equal_weight_v1)",
            "run_type": "Compare Run",
            "status_tag": "CURRENT_RESEARCH_BASELINE",
            "cagr": g4["cagr_pct"],
            "mdd": g4["mdd_pct"],
            "sharpe": g4["sharpe"],
            "verdict": "REJECT",
            "decision": "no-guard 기준 연구 baseline. CAGR>15 미달.",
            "source_artifact": "contextual_guard_compare.json",
            "last_validated_at": ev_date,
        },
        {
            "chapter": "P209A",
            "variant_or_profile": "g3_pos3_eq (shadow)",
            "purpose": "shadow reference (pos3, equal_weight)",
            "run_type": "analysis_only",
            "status_tag": "ANALYSIS_ONLY",
            "cagr": None,
            "mdd": None,
            "sharpe": None,
            "verdict": "N/A",
            "decision": "drawdown 분석 참고용. 정식 baseline 아님.",
            "source_artifact": "drawdown_contribution_report.md",
            "last_validated_at": "2026-04-12",
        },
        {
            "chapter": "P209B",
            "variant_or_profile": "B1_pos3_raew_primary_drop",
            "purpose": "정적 blacklist drop (102110, 102970)",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": 15.26,
            "mdd": 13.02,
            "sharpe": 1.5035,
            "verdict": "REJECT",
            "decision": "정적 drop 은 MDD 악화. Track A 기각 (historical).",
            "source_artifact": "toxic_filter_compare.md",
            "last_validated_at": "2026-04-12",
        },
        {
            "chapter": "P209C",
            "variant_or_profile": CURRENT_RESEARCH_CANDIDATE,
            "purpose": "사전 진입 가드 (pre-entry crash context)",
            "run_type": "Compare Run",
            "status_tag": "CURRENT_RESEARCH_CANDIDATE",
            "cagr": research["cagr_pct"],
            "mdd": research["mdd_pct"],
            "sharpe": research["sharpe"],
            "verdict": "REJECT",
            "decision": "pre-entry guard 만 부분 유효. CAGR<15 미달.",
            "source_artifact": "contextual_guard_compare.json",
            "last_validated_at": ev_date,
        },
        {
            "chapter": "P209C",
            "variant_or_profile": "B2_pos3_raew_early_stop_guard",
            "purpose": "초기 보유 타이트 스탑 (early-stop)",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": None,
            "mdd": None,
            "sharpe": None,
            "verdict": "REJECT",
            "decision": "early_stop 은 CAGR 대폭 훼손. 기각.",
            "source_artifact": "contextual_guard_compare.json",
            "last_validated_at": "2026-04-12",
        },
        {
            "chapter": "P209C",
            "variant_or_profile": "B3_pos3_raew_combined_guard",
            "purpose": "복합 가드 (pre-entry + early-stop)",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": None,
            "mdd": None,
            "sharpe": None,
            "verdict": "REJECT",
            "decision": "combined 은 과잉 방어. 기각.",
            "source_artifact": "contextual_guard_compare.json",
            "last_validated_at": "2026-04-12",
        },
        {
            "chapter": "P210A",
            "variant_or_profile": "B0_research_no_ml",
            "purpose": "ML 미적용 연구 baseline (= research_candidate_b1 base)",
            "run_type": "Compare Run",
            "status_tag": "HISTORICAL_REFERENCE",
            "cagr": b0["cagr_pct"],
            "mdd": b0["mdd_pct"],
            "sharpe": b0["sharpe"],
            "verdict": "REJECT",
            "decision": "ML 미적용 기준선. mts=200 으로 인해 no-op (P210A).",
            "source_artifact": "predictive_risk_compare.json",
            "last_validated_at": ev_date,
        },
        {
            "chapter": "P210A-2",
            "variant_or_profile": "B3_research_soft_gate_lr_mts100",
            "purpose": "ML soft_gate (mts=100, LR, 최적 후보) — historical",
            "run_type": "Compare Run",
            "status_tag": "HISTORICAL_REFERENCE",
            "cagr": 15.932,
            "mdd": 11.028,
            "sharpe": 1.4358,
            "verdict": "REJECT",
            "decision": (
                "ML 활성화 성공 (당시 soft_gate 5회). MDD 미개선."
                " Track B 데이터 규모 한계 확인 (snapshot)."
            ),
            "source_artifact": "predictive_risk_compare.md (P210A-2 snapshot)",
            "last_validated_at": "2026-04-13",
        },
        {
            "chapter": "P210A-2",
            "variant_or_profile": "B2_research_soft_gate_lr_mts75",
            "purpose": "ML soft_gate (mts=75, 과도한 개입) — historical",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": 10.37,
            "mdd": 11.028,
            "sharpe": 1.0248,
            "verdict": "REJECT",
            "decision": "CAGR 과도한 훼손. 기각 (snapshot).",
            "source_artifact": "predictive_risk_compare.md (P210A-2 snapshot)",
            "last_validated_at": "2026-04-13",
        },
        {
            "chapter": "P210A-2",
            "variant_or_profile": "B1_research_soft_gate_lr_mts50",
            "purpose": "ML soft_gate (mts=50, 과도한 개입) — historical",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": 10.82,
            "mdd": 11.028,
            "sharpe": 1.1845,
            "verdict": "REJECT",
            "decision": "CAGR 과도한 훼손. 기각 (snapshot).",
            "source_artifact": "predictive_risk_compare.md (P210A-2 snapshot)",
            "last_validated_at": "2026-04-13",
        },
        {
            "chapter": "P210B",
            "variant_or_profile": TRACK_B_LATEST_VARIANT,
            "purpose": (
                "Track B label/action 재설계 최상위 활성 실험군"
                f" (label={tb['label_profile']}, action={tb['action_policy']})"
            ),
            "run_type": "Compare Run",
            "status_tag": "CURRENT_TRACK_B_LATEST",
            "cagr": tb["cagr_pct"],
            "mdd": tb["mdd_pct"],
            "sharpe": tb["sharpe"],
            "verdict": "REJECT",
            "decision": (
                "L1 severe label 로 positive_ratio 축소,"
                " CAGR 훼손 최소. MDD 미개선 → Track B 구조적 한계."
            ),
            "source_artifact": "predictive_risk_compare.json",
            "last_validated_at": ev_date,
        },
    ]


# ─── 산출물 생성 ─────────────────────────────────────────────────────
def _build_strategy_state_payload(
    generated_at: str, metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """current_strategy_state canonical JSON payload (dynamic from metrics)."""
    main = metrics["main_run_metrics"]
    research = metrics["research_candidate_metrics"]
    tb = metrics["track_b_latest"]

    return {
        "generated_at": generated_at,
        "canonical_sources": {
            "evidence_generated_at": metrics["evidence_generated_at"],
            "predictive_compare_generated_at": (
                metrics["predictive_compare_generated_at"]
            ),
            "contextual_guard_compare_generated_at": (
                metrics["contextual_guard_compare_generated_at"]
            ),
        },
        "current_main_run": {
            "identifier": CURRENT_MAIN_RUN,
            "cagr_pct": main["cagr_pct"],
            "mdd_pct": main["mdd_pct"],
            "sharpe": main["sharpe"],
            "verdict": "REJECT",
            "note": "운영 기준선 유지. CAGR>15 AND MDD<10 미달.",
        },
        "current_operational_control": {
            "identifier": CURRENT_OPERATIONAL_CONTROL,
            "note": "ML 미적용 control. = Main Run.",
        },
        "current_research_candidate": {
            "identifier": CURRENT_RESEARCH_CANDIDATE,
            "cagr_pct": research["cagr_pct"],
            "mdd_pct": research["mdd_pct"],
            "sharpe": research["sharpe"],
            "verdict": "REJECT",
            "note": "pre-entry guard 만 부분 유효. 두 기준 동시 충족 미달.",
        },
        "track_b_latest": {
            "identifier": tb["variant"],
            "label_profile": tb["label_profile"],
            "action_policy": tb["action_policy"],
            "min_train_samples": tb["min_train_samples"],
            "label_positive_ratio_pct": tb["label_positive_ratio_pct"],
            "predicted_dates": tb["predicted_dates"],
            "soft_gate_hits": tb["soft_gate_hits"],
            "cagr_pct": tb["cagr_pct"],
            "mdd_pct": tb["mdd_pct"],
            "sharpe": tb["sharpe"],
            "verdict": "REJECT",
            "note": _format_latest_trackb_summary(metrics),
        },
        "rejected_axes": [
            "P209B 정적 blacklist drop → MDD 악화",
            "P209C early_stop / combined guard → CAGR 과도 훼손",
            "P210A-2 ML soft_gate mts=50/75 → CAGR 과도 훼손",
            "P210B L0 broad / L2 fast — softgate/rerank 전 구간 MDD 불변",
        ],
        "last_completed_chapter": LAST_COMPLETED_CHAPTER,
        "last_rejected_axis": _format_last_rejected_axis(metrics),
        "next_planned_chapter": NEXT_PLANNED_CHAPTER,
        "latest_trackb_result_summary": _format_latest_trackb_summary(metrics),
    }


def _build_decision_ledger_payload(
    generated_at: str, metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """decision_ledger canonical JSON payload."""
    tb = metrics["track_b_latest"]
    chapters = [
        {
            "chapter": "P206",
            "title": "Timing / Hybrid 방어 엔진",
            "validated": "VIX + domestic shock + hybrid regime + safe asset",
            "conclusion": "엔지니어링 완성, 정책 성능 실패 (MDD<10 미달)",
            "handoff": "타이밍 미세조정 포기 → 포트폴리오 구성으로",
        },
        {
            "chapter": "P207",
            "title": "Allocation 엔지니어링",
            "validated": "risk_aware_equal_weight, inverse_vol",
            "conclusion": "배분만으로 두 기준 동시 충족 불가",
            "handoff": "보유 구조 검증 (P208)",
        },
        {
            "chapter": "P208",
            "title": "Holding Structure",
            "validated": "max_positions 2/3/4/5 × allocation 2종",
            "conclusion": "보유 확장만으로 MDD<10 불가. pos4 CAGR 최고",
            "handoff": "종목 선정 품질 분석 (P209A)",
        },
        {
            "chapter": "P209A",
            "title": "Drawdown Attribution 분석",
            "validated": "MDD window 내 종목별 기여, 선택 품질",
            "conclusion": "102110/102970 반복 toxic. 선택 품질만으로 부족",
            "handoff": "toxic 필터 설계 (P209B)",
        },
        {
            "chapter": "P209B",
            "title": "Static Blacklist (Track A)",
            "validated": "정적 ticker drop (primary 2개 / extended 4개)",
            "conclusion": "drop 은 MDD 악화 + CAGR 훼손. 가설 기각",
            "handoff": "문맥형 가드 (P209C)",
        },
        {
            "chapter": "P209C",
            "title": "Contextual Crash Guard (Track A)",
            "validated": "pre-entry guard / early-stop / combined",
            "conclusion": "pre-entry 만 부분 유효. early_stop/combined 기각",
            "handoff": "ML classifier (P210A)",
        },
        {
            "chapter": "P210A",
            "title": "ML Pipeline 구축",
            "validated": "walk-forward LR classifier + soft_gate",
            "conclusion": "구현 PASS / mts=200 > labeled=183 → no-op",
            "handoff": "mts 하향 실험 (P210A-2)",
        },
        {
            "chapter": "P210A-2",
            "title": "min_train_samples Relaxation",
            "validated": "mts=50/75/100 으로 ML 활성화 여부",
            "conclusion": (
                "ML 활성화 성공 (mts=100). CAGR 일부 훼손 허용 가능."
                " MDD 미개선 (snapshot 11.03% / 현 14.92%)"
            ),
            "handoff": "Track B 한계 확인. Step10B 재설계 또는 종료 판정",
        },
        {
            "chapter": "P210B",
            "title": "Label + Action Redesign",
            "validated": (
                "label_profile (L0 broad / L1 severe / L2 fast) ×"
                " action_policy (softgate / rerank), mts=100 / LR 고정"
            ),
            "conclusion": (
                f"label_positive_ratio 71% → {tb['label_positive_ratio_pct']:.1f}%"
                f" 까지 축소 성공."
                f" L1 severe softgate ({tb['variant']}) 가 CAGR 훼손 최소"
                f" (CAGR {tb['cagr_pct']:.2f}% / MDD {tb['mdd_pct']:.2f}%)."
                " MDD 전 구간 동일 baseline 값 불변"
                " → Track B label/action 재설계로도 MDD<10 달성 불가."
            ),
            "handoff": (
                "Step10C 승격 검토 (threshold 튜닝 등 별도 축) 또는"
                " Track B 구조적 한계 확정 후 P210 종료 선언"
            ),
        },
        {
            "chapter": "P210-STEP10Z-3",
            "title": "Canonical State / Registry Realign",
            "validated": (
                "stale 하드코딩 metric 제거,"
                " evidence/compare json 우선 로더 도입,"
                " handoff freshness 검증 추가"
            ),
            "conclusion": (
                "current_strategy_state / experiment_registry / decision_ledger /"
                " handoff mirror 가 모두 최신 canonical evidence 기준으로 sync"
            ),
            "handoff": ("P210-STEP10C-TRACKB-LIMIT-VERDICT-AND-CLOSEOUT 로 진입 가능"),
        },
    ]
    return {"generated_at": generated_at, "chapters": chapters}


def generate_experiment_registry(project_root: Path) -> None:
    """experiment_registry.md/.json + current_strategy_state.md/.json +
    decision_ledger.md/.json 를 생성한다.

    P210-STEP10Z-3: canonical evidence/compare 를 dynamic loader 로 읽어 채움.
    누락 시 즉시 RuntimeError. 하드코딩 metric 미사용.
    """
    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    metrics = load_canonical_metrics(project_root)
    rows = _build_registry_rows(metrics)

    # registry JSON + MD
    payload = {"generated_at": generated_at, "rows": rows}
    (out_dir / "experiment_registry.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "experiment_registry.md").write_text(
        "\n".join(_render_registry_md(rows, generated_at)),
        encoding="utf-8",
    )

    # current_strategy_state MD + canonical JSON sibling
    state_payload = _build_strategy_state_payload(generated_at, metrics)
    (out_dir / "current_strategy_state.md").write_text(
        "\n".join(_render_strategy_state(generated_at, metrics)),
        encoding="utf-8",
    )
    (out_dir / "current_strategy_state.json").write_text(
        json.dumps(state_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # decision_ledger MD + canonical JSON sibling
    ledger_payload = _build_decision_ledger_payload(generated_at, metrics)
    (out_dir / "decision_ledger.md").write_text(
        "\n".join(_render_decision_ledger(generated_at, metrics)),
        encoding="utf-8",
    )
    (out_dir / "decision_ledger.json").write_text(
        json.dumps(ledger_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(
        "[P210-STEP10Z-3] experiment registry + strategy state + decision ledger"
        " 생성 완료 (canonical-sync mode)"
    )


def get_strategy_summary() -> Dict[str, str]:
    """evidence / UI 상단 요약 블록용.

    P210-STEP10Z-3: canonical metrics 를 직접 읽어 dynamic 텍스트 반환.
    project_root 는 cwd 기준 (호출자 어디서든 동일 절대 경로 산출물 사용).
    """
    project_root = Path.cwd()
    metrics = load_canonical_metrics(project_root)
    return {
        "current_main_run": CURRENT_MAIN_RUN,
        "current_research_candidate": CURRENT_RESEARCH_CANDIDATE,
        "last_completed_chapter": LAST_COMPLETED_CHAPTER,
        "last_rejected_axis": _format_last_rejected_axis(metrics),
        "next_planned_chapter": NEXT_PLANNED_CHAPTER,
    }


def patch_evidence_summary_block(project_root: Path) -> None:
    """dynamic_evidence_latest.md 의 Current Strategy Position 블록을
    최신 canonical summary (get_strategy_summary) 와 동기화한다.

    sync-only mode 에서는 evidence_writer 를 재호출하지 않으므로 해당 블록이
    stale 로 남는 것을 막기 위한 최소 침습 in-place patch.

    - Performance / Hybrid Regime / Allocation 등 backtest 데이터 블록은 건드리지 않음
    - evidence MD 의 `- generated_at:` 헤더도 건드리지 않음
      (logical timestamp 유지 → state.generated_at >= evidence.generated_at 보장)
    - 블록 미발견 시 fail-loud (RuntimeError)
    """
    md_path = project_root / _EVIDENCE_MD_REL
    if not md_path.exists():
        raise RuntimeError(
            f"[P210-STEP10Z-3] evidence missing for summary patch: {md_path}"
        )

    summary = get_strategy_summary()
    new_block_lines = [
        "## Current Strategy Position",
        f"- **Current Main Run**: `{summary['current_main_run']}`",
        (
            "- **Current Research Candidate**:"
            f" `{summary['current_research_candidate']}`"
        ),
        f"- **Last Completed Chapter**: `{summary['last_completed_chapter']}`",
        f"- **Last Rejected Axis**: {summary['last_rejected_axis']}",
        f"- **Next Planned Chapter**: {summary['next_planned_chapter']}",
    ]
    new_block = "\n".join(new_block_lines) + "\n"

    text = md_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^## Current Strategy Position\n(?:- \*\*[^\n]+\*\*:[^\n]*\n)+",
        re.MULTILINE,
    )
    if not pattern.search(text):
        raise RuntimeError(
            "[P210-STEP10Z-3] evidence 의 'Current Strategy Position' 블록 미발견"
            f" — evidence_writer 포맷 변경 가능성. path={md_path}"
        )
    patched = pattern.sub(new_block, text, count=1)
    if patched == text:
        # 이미 동기화된 상태 — no-op
        logger.info("[P210-STEP10Z-3] evidence summary 블록 이미 동기화 상태 (no-op)")
        return
    md_path.write_text(patched, encoding="utf-8")
    logger.info("[P210-STEP10Z-3] evidence summary 블록 patch 완료")


# ─── Registry Markdown ───────────────────────────────────────────────
def _render_registry_md(rows: List[Dict[str, Any]], generated_at: str) -> List[str]:
    lines = [
        "# Experiment Registry (P210-STEP10Z-3)",
        "",
        f"- generated_at: {generated_at}",
        f"- total_entries: {len(rows)}",
        "",
        "## 실험 분류표",
        "",
        "| Chapter | Variant/Profile | Purpose | Run Type"
        " | Status | CAGR | MDD | Sharpe"
        " | Verdict | Decision | Source Artifact | Validated |",
        "|---|---|---|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for r in rows:
        cagr_s = f"{r['cagr']:.2f}%" if r["cagr"] is not None else "-"
        mdd_s = f"{r['mdd']:.2f}%" if r["mdd"] is not None else "-"
        sharpe_s = f"{r['sharpe']:.4f}" if r["sharpe"] is not None else "-"
        lines.append(
            f"| {r['chapter']}"
            f" | {r['variant_or_profile']}"
            f" | {r['purpose']}"
            f" | {r['run_type']}"
            f" | **{r['status_tag']}**"
            f" | {cagr_s}"
            f" | {mdd_s}"
            f" | {sharpe_s}"
            f" | {r['verdict']}"
            f" | {r['decision']}"
            f" | {r['source_artifact']}"
            f" | {r['last_validated_at']} |"
        )

    lines += [
        "",
        "## Status Tag 범례",
        "- `CURRENT_MAIN`: 현재 운영 기준선",
        "- `CURRENT_RESEARCH_BASELINE`: pos3 raw baseline (no guard)",
        "- `CURRENT_RESEARCH_CANDIDATE`: 승격 검토 중인 연구 후보",
        "- `CURRENT_TRACK_B_LATEST`: Step10B 최상위 활성 ML 실험군",
        "- `REJECTED`: 검증 후 기각된 실험",
        "- `ANALYSIS_ONLY`: 분석/참고용 (정식 실험 아님)",
        "- `HISTORICAL_REFERENCE`: 과거 비교 참조용 (현재 활성 아님)",
    ]
    return lines


# ─── Current Strategy State ──────────────────────────────────────────
def _render_strategy_state(generated_at: str, metrics: Dict[str, Any]) -> List[str]:
    main = metrics["main_run_metrics"]
    research = metrics["research_candidate_metrics"]
    tb = metrics["track_b_latest"]
    return [
        "# Current Strategy State (P210-STEP10Z-3)",
        "",
        f"- generated_at: {generated_at}",
        f"- evidence_generated_at: {metrics['evidence_generated_at']}",
        (
            "- predictive_compare_generated_at:"
            f" {metrics['predictive_compare_generated_at']}"
        ),
        (
            "- contextual_guard_compare_generated_at:"
            f" {metrics['contextual_guard_compare_generated_at']}"
        ),
        "",
        "## 현재 기준선",
        "",
        "| 역할 | 식별자 | 성능 | 상태 |",
        "|---|---|---|---|",
        (
            f"| **Main Run** | `{CURRENT_MAIN_RUN}` |"
            f" CAGR {main['cagr_pct']:.2f}% / MDD {main['mdd_pct']:.2f}% /"
            f" Sharpe {main['sharpe']:.4f} | REJECT (운영 유지) |"
        ),
        (
            f"| **Operational Control** | `{CURRENT_OPERATIONAL_CONTROL}` |"
            " = Main Run | ML 미적용 control |"
        ),
        (
            f"| **Research Candidate** | `{CURRENT_RESEARCH_CANDIDATE}` |"
            f" CAGR {research['cagr_pct']:.2f}% / MDD {research['mdd_pct']:.2f}% /"
            f" Sharpe {research['sharpe']:.4f} | REJECT (CAGR<15) |"
        ),
        (
            f"| **Track B Latest** | `{tb['variant']}` |"
            f" CAGR {tb['cagr_pct']:.2f}% / MDD {tb['mdd_pct']:.2f}% /"
            f" Sharpe {tb['sharpe']:.4f} | Step10B 최상위 활성 실험군 |"
        ),
        "",
        "## 기각된 축 (Do Not Promote)",
        "",
        "- P209B 정적 blacklist drop → MDD 악화",
        "- P209C early_stop / combined guard → CAGR 과도 훼손",
        "- P210A-2 ML soft_gate mts=50/75 → CAGR 과도 훼손",
        "- P210B L0 broad / L2 fast — softgate/rerank 전 구간 MDD 불변",
        "",
        "## 다음 단계",
        "",
        f"- 마지막 완료 챕터: `{LAST_COMPLETED_CHAPTER}`",
        f"- 다음 예정: `{NEXT_PLANNED_CHAPTER}`",
        f"- 최근 기각 축: {_format_last_rejected_axis(metrics)}",
        "- 전제: closeout 이후에만 새 실험 진입 허용",
    ]


# ─── Decision Ledger ─────────────────────────────────────────────────
def _render_decision_ledger(generated_at: str, metrics: Dict[str, Any]) -> List[str]:
    tb = metrics["track_b_latest"]
    return [
        "# Decision Ledger (P210-STEP10Z-3)",
        "",
        f"- generated_at: {generated_at}",
        "",
        "## P206: Timing / Hybrid 방어 엔진",
        "- 무엇을 검증했는가: VIX + domestic shock + hybrid regime + safe asset",
        "- 무슨 결론이 났는가: 엔지니어링 완성, 정책 성능 실패 (MDD<10 미달)",
        "- 다음 단계로 무엇이 넘어왔는가: 타이밍 미세조정 포기 → 포트폴리오 구성으로",
        "",
        "## P207: Allocation 엔지니어링",
        "- 무엇을 검증했는가: risk_aware_equal_weight, inverse_vol",
        "- 무슨 결론이 났는가: 배분만으로 두 기준 동시 충족 불가",
        "- 다음 단계로 무엇이 넘어왔는가: 보유 구조 검증 (P208)",
        "",
        "## P208: Holding Structure",
        "- 무엇을 검증했는가: max_positions 2/3/4/5 × allocation 2종",
        "- 무슨 결론이 났는가: 보유 확장만으로 MDD<10 불가. pos4 CAGR 최고",
        "- 다음 단계로 무엇이 넘어왔는가: 종목 선정 품질 분석 (P209A)",
        "",
        "## P209A: Drawdown Attribution 분석",
        "- 무엇을 검증했는가: MDD window 내 종목별 기여, 선택 품질",
        "- 무슨 결론이 났는가: 102110/102970 반복 toxic. 선택 품질만으로 부족",
        "- 다음 단계로 무엇이 넘어왔는가: toxic 필터 설계 (P209B)",
        "",
        "## P209B: Static Blacklist (Track A)",
        "- 무엇을 검증했는가: 정적 ticker drop (primary 2개 / extended 4개)",
        "- 무슨 결론이 났는가: drop 은 MDD 악화 + CAGR 훼손. 가설 기각",
        "- 다음 단계로 무엇이 넘어왔는가: 문맥형 가드 (P209C)",
        "",
        "## P209C: Contextual Crash Guard (Track A)",
        "- 무엇을 검증했는가: pre-entry guard / early-stop / combined",
        "- 무슨 결론이 났는가: pre-entry 만 부분 유효. early_stop/combined 기각",
        "- 다음 단계로 무엇이 넘어왔는가: ML classifier (P210A)",
        "",
        "## P210A: ML Pipeline 구축",
        "- 무엇을 검증했는가: walk-forward LR classifier + soft_gate",
        "- 무슨 결론이 났는가: 구현 PASS / mts=200 > labeled=183 → no-op",
        "- 다음 단계로 무엇이 넘어왔는가: mts 하향 실험 (P210A-2)",
        "",
        "## P210A-2: min_train_samples Relaxation",
        "- 무엇을 검증했는가: mts=50/75/100 으로 ML 활성화 여부",
        "- 무슨 결론이 났는가:"
        " ML 활성화 성공 (mts=100: soft_gate 5회)."
        " CAGR 일부 훼손 허용 가능. MDD 미개선 (snapshot 11.03% / 현 14.92%)",
        "- 다음 단계로 무엇이 넘어왔는가:"
        " Track B 한계 확인. Step10B label/action 재설계 또는 종료 판정",
        "",
        "## P210B: Label + Action Redesign",
        "- 무엇을 검증했는가:"
        " label_profile (L0 broad / L1 severe / L2 fast) ×"
        " action_policy (softgate / rerank), mts=100 / LR 고정",
        "- 무슨 결론이 났는가:"
        f" label_positive_ratio 71% → {tb['label_positive_ratio_pct']:.1f}%"
        f" 까지 축소 성공."
        f" L1 severe softgate ({tb['variant']}) 가 CAGR 훼손 최소"
        f" (CAGR {tb['cagr_pct']:.2f}% / MDD {tb['mdd_pct']:.2f}%)."
        " MDD 전 구간 동일 baseline 값 불변"
        " → Track B label/action 재설계로도 MDD<10 불가",
        "- 다음 단계로 무엇이 넘어왔는가:"
        " Step10C 승격 검토 또는 Track B 구조적 한계 확정 후 P210 종료 선언",
        "",
        "## P210-STEP10Z-3: Canonical State / Registry Realign",
        "- 무엇을 검증했는가:"
        " stale 하드코딩 metric 제거,"
        " evidence/compare json 우선 로더 도입,"
        " handoff freshness 검증 추가",
        "- 무슨 결론이 났는가:"
        " current_strategy_state / experiment_registry / decision_ledger /"
        " handoff mirror 가 모두 최신 canonical evidence 기준으로 sync",
        "- 다음 단계로 무엇이 넘어왔는가:"
        " P210-STEP10C-TRACKB-LIMIT-VERDICT-AND-CLOSEOUT 진입 가능",
    ]
