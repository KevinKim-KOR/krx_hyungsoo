#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/holding_structure/report_writer.py — 산출물 렌더러

P208-STEP8A holding_structure_compare.md / .csv / .json 생성 전담.

단일 책임: sorted rows + errors → md/csv/json 3종 산출물
R3 단계에서 holding_structure_compare.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

import csv as _csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.backtest.reporting.holding_structure.diagnostic import _diagnostic_summary

logger = logging.getLogger(__name__)


def _write_outputs(
    rows: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    out_dir: Path,
) -> None:
    """holding_structure_compare.md / .csv / .json 생성."""
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # JSON
    json_path = out_dir / "holding_structure_compare.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "experiments": rows,
                "errors": errors,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # CSV (flat)
    if rows:
        csv_path = out_dir / "holding_structure_compare.csv"
        _csv_rows = []
        for r in rows:
            rr = dict(r)
            rr["blocked_reason_totals"] = json.dumps(
                rr.get("blocked_reason_totals", {}),
                ensure_ascii=False,
            )
            _csv_rows.append(rr)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(_csv_rows[0].keys()))
            w.writeheader()
            w.writerows(_csv_rows)

    # Markdown
    lines: List[str] = [
        "# Holding Structure Compare (P208-STEP8A)",
        "",
        f"- generated_at: {generated_at}",
        f"- experiments: {len(rows)}",
        "- scope: holding_structure_only (max_positions × allocation_mode)",
        "- shared: same dynamic scanner / hybrid B+D / safe asset / verdict",
        "- verdict: CAGR > 15 AND MDD < 10",
        "- 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순",
        "",
        "## 비교표",
        "",
        (
            "| Rank | Variant | Max Positions | Allocation"
            " | CAGR | MDD | Sharpe | Avg Held"
            " | Blocked MaxPos | Verdict |"
        ),
        "|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        cagr = r.get("cagr")
        mdd = r.get("mdd")
        sharpe = r.get("sharpe")
        lines.append(
            f"| {r.get('rank', '-')}"
            f" | {r.get('variant', '-')}"
            f" | {r.get('max_positions', '-')}"
            f" | {r.get('allocation_mode', '-')}"
            f" | {cagr if cagr is not None else 'ERR'}%"
            f" | {mdd if mdd is not None else 'ERR'}%"
            f" | {sharpe if sharpe is not None else '-'}"
            f" | {r.get('avg_held_positions', '-')}"
            f" | {r.get('blocked_max_positions', 0)}"
            f" | {r.get('verdict', '-')} |"
        )

    if errors:
        lines += ["", "## 오류"]
        for e in errors:
            lines.append(
                f"- {e.get('variant')}"
                f" (pos={e.get('max_positions')}, mode={e.get('allocation_mode')})"
                f": {e.get('error')}"
            )

    # 진단 요약 (지시문의 4가지 질문)
    lines += _diagnostic_summary(rows)

    md_path = out_dir / "holding_structure_compare.md"
    md_path.write_text("\n".join(lines), encoding="utf-8-sig")
    logger.info(f"[P208-SWEEP] 비교 산출물 생성: {len(rows)} 실험군 → {md_path}")
