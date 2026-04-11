#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/allocation_constraints/report_writer.py — P207 산출물 렌더러

P207-STEP7C allocation_constraint_compare.md / .csv 생성 전담.

단일 책임: experiment results list → md/csv 2종 산출물
R4 단계에서 run_backtest.py inline 블록에서 분리된 모듈.
"""

from __future__ import annotations

import csv as _csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def write_allocation_constraint_compare(
    sorted_valid: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    total_experiments: int,
    out_dir: Path,
) -> None:
    """allocation_constraint_compare.md / .csv 생성.

    Args:
        sorted_valid: Sharpe 내림차순으로 정렬되고 rank 부여된 유효 실험군 리스트
            (각 dict: experiment_id, mode, weight_floor, weight_cap, CAGR,
             MDD, Sharpe, trades, fallback_used, verdict, rank)
        errors: 실패한 실험군 dict 리스트 (experiment_id, mode, error)
        total_experiments: 전체 실험군 수 (valid + errors)
            md 헤더의 "- experiments: N" 표기용
        out_dir: 출력 디렉토리 (project_root/reports/tuning)

    CSV 는 sorted_valid 의 순서대로 기록되므로 rank 와 파일 순서가 일치한다.
    """
    if total_experiments == 0:
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    if sorted_valid:
        csv_path = out_dir / "allocation_constraint_compare.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(sorted_valid[0].keys()))
            w.writeheader()
            w.writerows(sorted_valid)

    # Markdown
    md_lines: List[str] = [
        "# Allocation Constraint Compare (P207-STEP7C)",
        "",
        f"- generated_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S+09:00')}",
        f"- experiments: {total_experiments}",
        "",
        "## 비교표",
        "",
        "| Rank | Variant | Mode | Floor/Cap | CAGR | MDD | Sharpe | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted_valid:
        fc = f"{r.get('weight_floor', '-')}" f"/{r.get('weight_cap', '-')}"
        md_lines.append(
            f"| {r.get('rank', '-')}"
            f" | {r['experiment_id']}"
            f" | {r.get('mode', '?')}"
            f" | {fc}"
            f" | {r.get('CAGR', 'ERR')}%"
            f" | {r.get('MDD', 'ERR')}%"
            f" | {r.get('Sharpe', '-')}"
            f" | {r.get('verdict', '-')} |"
        )

    # 에러 실험군
    if errors:
        md_lines += ["", "## 오류"]
        for e in errors:
            md_lines.append(f"- {e['experiment_id']}: {e['error']}")

    md_path = out_dir / "allocation_constraint_compare.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8-sig")
    logger.info(f"[P207-SWEEP] 비교 산출물 생성: {len(sorted_valid)} 실험군")
