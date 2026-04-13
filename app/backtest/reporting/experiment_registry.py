#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/experiment_registry.py — P210-STEP10Z

P206~P210A-2 전체 실험을 분류하고 현재 기준선을 고정하는 registry/state/ledger
산출물을 생성한다.

단일 책임: 실험 분류 + 3개 문서 생성 (registry.md/json, strategy_state.md,
decision_ledger.md). 새 실험 추가나 성능 개선 시도 없음.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ─── 현재 기준선 고정 ─────────────────────────────────────────────────
CURRENT_MAIN_RUN = "g2_pos2_raew"
CURRENT_OPERATIONAL_CONTROL = "A0_operational_no_ml"
CURRENT_RESEARCH_CANDIDATE = "B1_pos3_raew_pre_entry_guard"
LATEST_TRACKB_RESULT = "ML activated (mts=100: soft_gate 5회) but MDD 미개선"
LAST_COMPLETED_CHAPTER = "P210-STEP10A-2"
NEXT_PLANNED_CHAPTER = "P210-STEP10B 또는 Track B 한계 판정 후 종료"


# ─── Registry 데이터 ─────────────────────────────────────────────────
def _build_registry_rows() -> List[Dict[str, Any]]:
    """전체 실험 registry 행 생성. 하드코딩 — 실험 결과는 이미 확정된 과거."""
    return [
        # P206~P208 기반
        {
            "chapter": "P206",
            "variant_or_profile": "g2_pos2_raew",
            "purpose": "운영 baseline (pos2, risk_aware_equal_weight_v1)",
            "run_type": "Main Run",
            "status_tag": "CURRENT_MAIN",
            "cagr": 12.4111,
            "mdd": 12.7446,
            "sharpe": 1.1035,
            "verdict": "REJECT",
            "decision": "운영 기준선 유지. CAGR>15 AND MDD<10 미달.",
            "source_artifact": "backtest_result.json",
            "last_validated_at": "2026-04-13",
        },
        {
            "chapter": "P207/P208",
            "variant_or_profile": "g4_pos3_raew",
            "purpose": "연구 baseline (pos3, risk_aware_equal_weight_v1)",
            "run_type": "Compare Run",
            "status_tag": "CURRENT_RESEARCH_CANDIDATE",
            "cagr": 16.682,
            "mdd": 11.028,
            "sharpe": 1.4817,
            "verdict": "REJECT",
            "decision": "CAGR>15 통과, MDD<10 미달 (1.03%p). 연구 후보 유지.",
            "source_artifact": "holding_structure_compare.md",
            "last_validated_at": "2026-04-13",
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
        # P209B: static toxic filter
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
            "decision": "정적 drop 은 MDD 악화 (11.03→13.02). Track A 기각.",
            "source_artifact": "toxic_filter_compare.md",
            "last_validated_at": "2026-04-12",
        },
        # P209C: contextual guard
        {
            "chapter": "P209C",
            "variant_or_profile": "B1_pos3_raew_pre_entry_guard",
            "purpose": "사전 진입 가드 (pre-entry crash context)",
            "run_type": "Compare Run",
            "status_tag": "CURRENT_RESEARCH_CANDIDATE",
            "cagr": 16.682,
            "mdd": 11.028,
            "sharpe": 1.4817,
            "verdict": "REJECT",
            "decision": "pre-entry guard 만 부분 유효. 연구 후보 유지.",
            "source_artifact": "contextual_guard_compare.md",
            "last_validated_at": "2026-04-12",
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
            "source_artifact": "contextual_guard_compare.md",
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
            "source_artifact": "contextual_guard_compare.md",
            "last_validated_at": "2026-04-12",
        },
        # P210A: ML pipeline (no-op)
        {
            "chapter": "P210A",
            "variant_or_profile": "B0_research_no_ml",
            "purpose": "ML 미적용 연구 baseline (= B1 pre_entry_guard)",
            "run_type": "Compare Run",
            "status_tag": "HISTORICAL_REFERENCE",
            "cagr": 16.682,
            "mdd": 11.028,
            "sharpe": 1.4817,
            "verdict": "REJECT",
            "decision": "ML 미적용 기준선. mts=200 으로 인해 no-op.",
            "source_artifact": "predictive_risk_compare.md",
            "last_validated_at": "2026-04-13",
        },
        # P210A-2: ML activation
        {
            "chapter": "P210A-2",
            "variant_or_profile": "B3_research_soft_gate_lr_mts100",
            "purpose": "ML soft_gate (mts=100, LR, 최적 후보)",
            "run_type": "Compare Run",
            "status_tag": "HISTORICAL_REFERENCE",
            "cagr": 15.932,
            "mdd": 11.028,
            "sharpe": 1.4358,
            "verdict": "REJECT",
            "decision": (
                "ML 활성화 성공 (soft_gate 5회). CAGR −0.75%p 허용 가능하나"
                " MDD 미개선. Track B 데이터 규모 한계."
            ),
            "source_artifact": "predictive_risk_compare.md",
            "last_validated_at": "2026-04-13",
        },
        {
            "chapter": "P210A-2",
            "variant_or_profile": "B2_research_soft_gate_lr_mts75",
            "purpose": "ML soft_gate (mts=75, 과도한 개입)",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": 10.37,
            "mdd": 11.028,
            "sharpe": 1.0248,
            "verdict": "REJECT",
            "decision": "CAGR −6.31%p 과도한 훼손. 기각.",
            "source_artifact": "predictive_risk_compare.md",
            "last_validated_at": "2026-04-13",
        },
        {
            "chapter": "P210A-2",
            "variant_or_profile": "B1_research_soft_gate_lr_mts50",
            "purpose": "ML soft_gate (mts=50, 과도한 개입)",
            "run_type": "Compare Run",
            "status_tag": "REJECTED",
            "cagr": 10.82,
            "mdd": 11.028,
            "sharpe": 1.1845,
            "verdict": "REJECT",
            "decision": "CAGR −5.86%p 과도한 훼손. 기각.",
            "source_artifact": "predictive_risk_compare.md",
            "last_validated_at": "2026-04-13",
        },
    ]


# ─── 산출물 생성 ─────────────────────────────────────────────────────
def generate_experiment_registry(project_root: Path) -> None:
    """experiment_registry.md/.json + current_strategy_state.md +
    decision_ledger.md 를 생성한다."""
    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    rows = _build_registry_rows()

    # JSON
    payload = {"generated_at": generated_at, "rows": rows}
    (out_dir / "experiment_registry.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Markdown — registry
    (out_dir / "experiment_registry.md").write_text(
        "\n".join(_render_registry_md(rows, generated_at)),
        encoding="utf-8",
    )

    # current_strategy_state.md
    (out_dir / "current_strategy_state.md").write_text(
        "\n".join(_render_strategy_state(generated_at)),
        encoding="utf-8",
    )

    # decision_ledger.md
    (out_dir / "decision_ledger.md").write_text(
        "\n".join(_render_decision_ledger(generated_at)),
        encoding="utf-8",
    )

    logger.info(
        "[P210-STEP10Z] experiment registry + strategy state"
        " + decision ledger 생성 완료"
    )


def get_strategy_summary() -> Dict[str, str]:
    """evidence / UI 상단 요약 블록용."""
    return {
        "current_main_run": CURRENT_MAIN_RUN,
        "current_research_candidate": CURRENT_RESEARCH_CANDIDATE,
        "last_completed_chapter": LAST_COMPLETED_CHAPTER,
        "last_rejected_axis": "Track B ML soft_gate (MDD 미개선)",
        "next_planned_chapter": NEXT_PLANNED_CHAPTER,
    }


# ─── Registry Markdown ───────────────────────────────────────────────
def _render_registry_md(rows: List[Dict[str, Any]], generated_at: str) -> List[str]:
    lines = [
        "# Experiment Registry (P210-STEP10Z)",
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
        "- `CURRENT_RESEARCH_CANDIDATE`: 승격 검토 중인 연구 후보",
        "- `REJECTED`: 검증 후 기각된 실험",
        "- `ANALYSIS_ONLY`: 분석/참고용 (정식 실험 아님)",
        "- `HISTORICAL_REFERENCE`: 과거 비교 참조용 (현재 활성 아님)",
    ]
    return lines


# ─── Current Strategy State ──────────────────────────────────────────
def _render_strategy_state(generated_at: str) -> List[str]:
    return [
        "# Current Strategy State (P210-STEP10Z)",
        "",
        f"- generated_at: {generated_at}",
        "",
        "## 현재 기준선",
        "",
        "| 역할 | 식별자 | 성능 | 상태 |",
        "|---|---|---|---|",
        f"| **Main Run** | `{CURRENT_MAIN_RUN}`"
        " | CAGR 12.41% / MDD 12.74% | REJECT (운영 유지) |",
        f"| **Operational Control** | `{CURRENT_OPERATIONAL_CONTROL}`"
        " | = Main Run | ML 미적용 control |",
        f"| **Research Candidate** | `{CURRENT_RESEARCH_CANDIDATE}`"
        " | CAGR 16.68% / MDD 11.03% | REJECT (MDD<10 미달) |",
        "| **Track B Latest** | `B3_soft_gate_lr_mts100`"
        " | CAGR 15.93% / MDD 11.03% | ML 활성화 OK / 성과 NG |",
        "",
        "## 기각된 축 (Do Not Promote)",
        "",
        "- P209B 정적 blacklist drop → MDD 악화",
        "- P209C early_stop / combined guard → CAGR 과도 훼손",
        "- P210A-2 ML soft_gate mts=50/75 → CAGR 5~6%p 훼손",
        "",
        "## 다음 단계",
        "",
        f"- 마지막 완료 챕터: `{LAST_COMPLETED_CHAPTER}`",
        f"- 다음 예정: `{NEXT_PLANNED_CHAPTER}`",
        "- 전제: closeout 이후에만 새 실험 진입 허용",
    ]


# ─── Decision Ledger ─────────────────────────────────────────────────
def _render_decision_ledger(generated_at: str) -> List[str]:
    return [
        "# Decision Ledger (P210-STEP10Z)",
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
        " CAGR −0.75%p 허용 가능하나 MDD 미개선 (11.03% 유지)",
        "- 다음 단계로 무엇이 넘어왔는가:"
        " Track B 한계 확인. Step10B label/action 재설계 또는 종료 판정",
    ]
