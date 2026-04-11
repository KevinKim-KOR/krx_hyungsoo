#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/report_writer.py — drawdown 산출물 렌더러

P209-STEP9A drawdown 분석 결과를 markdown / json / csv 로 출력한다.

단일 책임: analyses (List[Dict]) → drawdown_contribution_report.md/.json/.csv
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.

## R5v2 fallback 정책 — 모듈 레벨 whitelist

이 모듈은 **display rendering 전담** 이다. 모든 `.get(k, default)` 호출은
아래 2가지 카테고리 중 하나로 whitelist 된다:

1. **CSV row 구성**: analyses 의 필드 (role, ticker, contribution_to_nav_pct,
   days_in_portfolio 등) 는 analyze_variant 에서 대부분 설정되지만, optional
   하위 필드는 display 용 `'N/A'`/`'-'`/`0` 기본값 허용.

2. **Markdown 렌더링**: `| {w.get('mdd_pct', 'N/A')}%` 등은 NO_DATA 경로
   (mdd_window=None → {}) 에서 'N/A' 로 표시하기 위한 display fallback.
   이는 silent bug 은닉이 아니라 "데이터 없음" 의 시각적 표현.

필수 필드 (analyses 리스트의 각 분석 dict 에서 `label`, `max_positions`,
`allocation_mode` 등 핵심 식별자) 는 직접 subscript 로 접근한다. 누락 시
KeyError 로 즉시 실패.
"""

from __future__ import annotations

import csv as _csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def write_drawdown_contribution_report(
    analyses: List[Dict[str, Any]],
    out_dir: Path,
) -> Dict[str, Path]:
    """drawdown_contribution_report.md / .json / .csv 작성."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # JSON
    json_path = out_dir / "drawdown_contribution_report.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "scope": "analysis_only",
                "analyses": analyses,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # CSV (flat, top toxic ticker rows)
    csv_path = out_dir / "drawdown_contribution_report.csv"
    csv_rows: List[Dict[str, Any]] = []
    for a in analyses:
        for r in a.get("top_ticker_contributors_to_mdd", []):
            csv_rows.append(
                {
                    "label": a["label"],
                    "role": a.get("role", ""),
                    "max_positions": a["max_positions"],
                    "allocation_mode": a["allocation_mode"],
                    "rank": r.get("contribution_rank"),
                    "ticker": r.get("ticker"),
                    "contribution_to_nav_pct": r.get("contribution_to_nav_pct"),
                    "share_of_mdd_pct": r.get("share_of_mdd_pct"),
                    "days_in_portfolio": r.get("days_in_portfolio"),
                    "avg_weight": r.get("avg_weight"),
                }
            )
    if csv_rows:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)

    # Markdown
    md_path = out_dir / "drawdown_contribution_report.md"
    md_path.write_text(_render_markdown(analyses, generated_at), encoding="utf-8-sig")

    logger.info(f"[P209-STEP9A] drawdown_contribution report 생성 → {md_path}")
    return {"md": md_path, "json": json_path, "csv": csv_path}


def _render_markdown(
    analyses: List[Dict[str, Any]],
    generated_at: str,
) -> str:
    # Baseline realignment (P209-STEP9A, 2026-04-11):
    # 연구 baseline 은 최신 UI 기준으로 재고정 (기존 g5_pos4_eq → g4_pos3_raew).
    # Step9A 는 분석 챕터이며 SSOT 승격 아님.
    a_label = analyses[0]["label"] if len(analyses) > 0 else "-"
    b_label = analyses[1]["label"] if len(analyses) > 1 else "-"
    shadow_label = None
    for _a in analyses[2:]:
        if _a.get("role") == "shadow_reference":
            shadow_label = _a["label"]
            break

    lines: List[str] = [
        "# Drawdown Contribution Analysis (P209-STEP9A)",
        "",
        f"- generated_at: {generated_at}",
        "- scope: **analysis_only** — 필터/ML은 실제 매매 로직에 적용되지 않음",
        "- verdict 기준 유지: `CAGR > 15` AND `MDD < 10`",
        "- 기여 계산: daily return attribution"
        " (prev-day position value × day return) / prev NAV",
        "",
        "## Baseline Realignment (P209-STEP9A, 2026-04-11)",
        "",
        "최신 UI 기준 연구 baseline 을 `g4_pos3_raew` 로 재고정한다."
        " Step9A 는 분석 챕터이며 SSOT 승격 아님.",
        "",
        f"- **A (operational baseline)**: `{a_label}` — 운영 SSOT 유지",
        f"- **B (research baseline)**: `{b_label}` — 최신 UI 기준 연구 baseline",
    ]
    if shadow_label:
        lines.append(
            f"- **C (shadow reference)**: `{shadow_label}` — 보조 참고용 (정식 baseline 아님)"
        )
    lines += [
        "",
        "## 분석 대상 비교군",
        "",
        "| Label | Role | Max Positions | Allocation Mode | MDD % | Verdict |",
        "|---|---|---:|---|---:|---|",
    ]
    for a in analyses:
        w = a.get("mdd_window") or {}
        lines.append(
            f"| {a['label']}"
            f" | {a.get('role', '-')}"
            f" | {a['max_positions']}"
            f" | {a['allocation_mode']}"
            f" | {w.get('mdd_pct', 'N/A')}%"
            f" | {a.get('selection_quality_verdict', 'N/A')} |"
        )

    for a in analyses:
        lines += _render_one_analysis(a)

    lines += _render_filter_proposal(analyses)
    lines += [
        "",
        "## Notes",
        "- 기여 합은 총 MDD return과 근사로 일치 (단일 리밸런스 내"
        " buy/sell에서 cash flow가 value 변화로 잡히는 부분은 근사)",
        "- buckets가 dynamic_etf_market 모드에서 바이패스되므로 실제 거래 종목은"
        " `dynamic_pool`로 분류될 수 있음",
        "- 본 리포트는 분석 산출물이며 SSOT/실거래에 영향 없음 (Step9A=분석 챕터)",
    ]
    return "\n".join(lines)


def _render_one_analysis(a: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["", f"## {a['label']} — {a.get('role', '')}"]
    w = a.get("mdd_window") or {}
    lines += [
        "",
        "### MDD Window",
        f"- peak_date: {w.get('peak_date', 'N/A')}",
        f"- peak_nav: {w.get('peak_nav', 'N/A')}",
        f"- trough_date: {w.get('trough_date', 'N/A')}",
        f"- trough_nav: {w.get('trough_nav', 'N/A')}",
        f"- mdd_pct: {w.get('mdd_pct', 'N/A')}%",
        f"- window_length_days: {w.get('window_length_days', 'N/A')}",
    ]

    # Top toxic tickers
    lines += ["", "### Top Toxic Tickers (MDD 구간 손실 기여 상위)"]
    top = a.get("top_ticker_contributors_to_mdd") or []
    if top:
        lines += [
            "",
            "| Rank | Ticker | Contribution to NAV %"
            " | Share of MDD % | Days in Port. | Avg Weight |",
            "|---:|---|---:|---:|---:|---:|",
        ]
        for r in top:
            lines.append(
                f"| {r.get('contribution_rank', '-')}"
                f" | {r.get('ticker', '-')}"
                f" | {r.get('contribution_to_nav_pct', 0)}%"
                f" | {r.get('share_of_mdd_pct', 0)}%"
                f" | {r.get('days_in_portfolio', 0)}"
                f" | {r.get('avg_weight', 0)} |"
            )
    else:
        lines.append("- 기여 데이터 없음 (드로우다운 미발생 or window 내 포지션 없음)")

    # Worst selection events + 선택-비선택 gap
    lines += ["", "### Worst Selection Events (top 5)"]
    ws = a.get("worst_selection_events") or []
    if ws:
        lines += [
            "",
            "| Rebal Date | Selected | Worst Ticker"
            " | Worst Ret % | Avg Sel % | Avg Unsel %"
            " | Gap (Unsel−Sel) %p | Best Unsel |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
        for e in ws:
            sel = ",".join(e.get("selected_tickers", []) or [])
            _avg_us = e.get("avg_unselected_forward_return_pct")
            _gap = e.get("selection_gap_pct")
            _best_us = e.get("best_unselected_ticker")
            _best_us_ret = e.get("best_unselected_return_pct")
            _best_us_str = (
                f"{_best_us}({_best_us_ret}%)" if _best_us is not None else "-"
            )
            lines.append(
                f"| {e.get('rebalance_date', '-')}"
                f" | {sel or '-'}"
                f" | {e.get('worst_ticker', '-')}"
                f" | {e.get('worst_return_pct', 0)}%"
                f" | {e.get('avg_forward_return_pct', 0)}%"
                f" | {_avg_us if _avg_us is not None else '-'}%"
                f" | {_gap if _gap is not None else '-'}"
                f" | {_best_us_str} |"
            )
    else:
        lines.append("- 선택 이벤트 없음")

    # Bucket risk
    lines += ["", "### Bucket / Group Risk Summary"]
    br = a.get("bucket_risk_summary") or {}
    if br:
        lines += [
            "",
            "| Bucket | Ticker Count | Total Contrib %"
            " | Avg Weight | Avg Days Held |",
            "|---|---:|---:|---:|---:|",
        ]
        for name, v in sorted(
            br.items(), key=lambda x: x[1].get("total_contribution_pct", 0.0)
        ):
            lines.append(
                f"| {name}"
                f" | {v.get('ticker_count', 0)}"
                f" | {v.get('total_contribution_pct', 0)}%"
                f" | {v.get('avg_weight', 0)}"
                f" | {v.get('avg_days_held', 0)} |"
            )
    else:
        lines.append("- bucket 매칭 결과 없음")

    # Selection quality summary
    qs = a.get("selection_quality_summary") or {}
    _gap_val = qs.get("avg_selection_gap_pct")
    _gap_str = f"{_gap_val}%p" if _gap_val is not None else "N/A"
    lines += [
        "",
        "### Selection Quality Summary",
        f"- rebalance_count: {qs.get('rebalance_count', 0)}",
        f"- positive_forward_ratio: {qs.get('positive_forward_ratio', 0)}",
        f"- avg_forward_return_pct: {qs.get('avg_forward_return_pct', 0)}%",
        f"- best_forward_return_pct: {qs.get('best_forward_return_pct', 0)}%",
        f"- worst_forward_return_pct: {qs.get('worst_forward_return_pct', 0)}%",
        f"- **avg_selection_gap_pct**: {_gap_str}"
        "  _(양수=비선택이 더 좋았음=selection miss)_",
        f"- events_with_unselected_data:"
        f" {qs.get('events_with_unselected_data', 0)}",
        f"- events_with_better_unselected:"
        f" {qs.get('events_with_better_unselected', 0)}",
        f"- **verdict**: {a.get('selection_quality_verdict', 'N/A')}",
    ]
    return lines


def _render_filter_proposal(analyses: List[Dict[str, Any]]) -> List[str]:
    """다음 단계 필터 후보 규칙 초안 — Step9A는 분석만, 적용 금지."""
    lines: List[str] = [
        "",
        "## 다음 단계 필터 후보 규칙 제안 (초안)",
        "",
        "이번 단계(Step9A)는 분석 챕터이므로 필터를 실제 적용하지 않는다."
        " 아래는 Step9B(Track A 규칙기반) / Track B(ML classifier) 설계의 근거 초안이다.",
        "",
    ]

    # P209-STEP9A FIX: 공통 toxic 계산은 공유 함수 compute_common_toxic_primary
    # 로 통일 (evidence_writer 와 동일한 결과 보장). shadow 는 교집합에서 제외.
    from app.backtest.reporting.drawdown.toxic_summary import (
        DEFAULT_COMMON_TOXIC_TOP_N,
        compute_common_toxic_primary,
    )

    all_toxic = set()
    for a in analyses:
        top3 = [
            r["ticker"]
            for r in (a.get("top_ticker_contributors_to_mdd") or [])[
                :DEFAULT_COMMON_TOXIC_TOP_N
            ]
            if "ticker" in r
        ]
        all_toxic |= set(top3)

    common_toxic = compute_common_toxic_primary(analyses)

    if all_toxic:
        lines.append(
            f"- 모든 실험군 상위 {DEFAULT_COMMON_TOXIC_TOP_N}"
            f" Toxic 후보 합집합 (shadow 포함): {sorted(all_toxic)}"
        )
    if common_toxic:
        lines.append(
            f"- 정식 baseline 공통 Toxic 후보"
            f" (top {DEFAULT_COMMON_TOXIC_TOP_N} 교집합, shadow 제외):"
            f" {common_toxic}"
        )

    for a in analyses:
        qs = a.get("selection_quality_summary") or {}
        _v = a.get("selection_quality_verdict", "N/A")
        lines.append(
            f"- {a['label']} quality: verdict={_v},"
            f" positive_ratio={qs.get('positive_forward_ratio', 0)},"
            f" avg_fwd={qs.get('avg_forward_return_pct', 0)}%"
        )

    lines += [
        "",
        "### 제안 규칙 초안 (Step9B에서 검증 대상)",
        "- R1: 상위 toxic ticker를 리밸런스 선택 시 배제 (toxic asset drop)",
        "- R2: 리밸런스 직후 N영업일 내 -X% 이상 하락 종목 강제 청산"
        " (momentum crash filter)",
        "- R3: 특정 bucket/그룹의 총 노출을 상한으로 제한 (bucket exposure cap)",
        "- R4: 종목별 개별 stop (현재 stop_loss 대비 더 타이트하게)",
        "",
        "### 분석 질문 답변",
        "- Q1 스캐너 상위권 중 반복 MDD 유발자:"
        " 상기 Top Toxic Tickers 섹션의 rank 상위가 해당",
        "- Q2 선택 직후 급락 패턴: Worst Selection Events 상위가 반복 종목 포함 여부를 확인",
        "- Q3 toxic asset 성격군: Bucket/Group Risk Summary의"
        " `dynamic_pool` vs 기존 bucket 비교로 확인",
    ]
    return lines
