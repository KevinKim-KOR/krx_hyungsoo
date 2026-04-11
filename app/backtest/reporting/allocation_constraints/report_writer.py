#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/allocation_constraints/report_writer.py — P207 산출물 렌더러

P207-STEP7C allocation_constraint_compare.md / .csv 생성 전담.

단일 책임: experiment results list → md/csv 2종 산출물
R4 단계에서 run_backtest.py inline 블록에서 분리된 모듈.

## R5v2 fallback 정책 — 모듈 레벨 whitelist

이 모듈은 **display rendering 전담** 이다. sweep.py 가 구성한 row dict 를
markdown 테이블 / CSV 로 출력하며, 각 실험군별로 optional 필드
(weight_floor, weight_cap 등 — equal_weight 모드에선 없음) 가 존재한다.
모든 `.get(k, '-')` / `.get(k, 'ERR')` 등의 호출은 display placeholder 이며,
silent bug 은닉이 아니라 "해당 실험군에서는 이 필드가 의미 없음" 의 시각적
표현이다.
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
    # R5 whitelist: display fallback — sweep.py 에서 구성된 row 는 experiment
    # 별로 mode/weight_floor/weight_cap 가 있을 수도/없을 수도 있으며 (equal_weight
    # 는 floor/cap 없음), CAGR/MDD/Sharpe 가 None 일 수 있다 (계산 실패).
    # '-' / '?' / 'ERR' 기호는 사용자 display 를 위한 명시적 placeholder.
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
