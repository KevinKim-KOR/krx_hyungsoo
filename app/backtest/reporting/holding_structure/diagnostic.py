#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/holding_structure/diagnostic.py — Q1~Q4 진단 요약

P208-STEP8A holding structure 비교 실험의 진단 요약. 지시문 4개 질문
(pos2 병목 여부 / 보유수 확대 MDD 효과 / CAGR 훼손폭 / 다음 단계 search
space) 에 대한 답변을 G1~G8 결과 기반으로 생성한다.

단일 책임: sorted rows (G1~G8) → markdown 진단 요약 라인 리스트
R3 단계에서 holding_structure_compare.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _diagnostic_summary(rows: List[Dict[str, Any]]) -> List[str]:
    """지시문이 요구한 4가지 질문에 답하는 요약 섹션."""
    if not rows:
        return ["", "## 진단 요약", "- 실험군 데이터가 없어 진단 불가"]

    pos2_rows = [r for r in rows if r.get("max_positions") == 2]
    pos3_rows = [r for r in rows if r.get("max_positions") == 3]
    pos4_rows = [r for r in rows if r.get("max_positions") == 4]
    pos5_rows = [r for r in rows if r.get("max_positions") == 5]

    def _avg(key: str, subset: List[Dict[str, Any]]):
        vals = [r.get(key) for r in subset if r.get(key) is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)

    def _sum(key: str, subset: List[Dict[str, Any]]):
        return sum(int(r.get(key, 0) or 0) for r in subset)

    pos2_blocked_sum = _sum("blocked_max_positions", pos2_rows)
    pos2_blocked_avg = _avg("blocked_max_positions", pos2_rows)
    pos2_pre_cap_max = max(
        (
            int(r.get("rebalances_with_more_than_2_candidates", 0) or 0)
            for r in pos2_rows
        ),
        default=0,
    )
    pos2_avg_mdd = _avg("mdd", pos2_rows)

    pos_blocks = [
        ("pos2", pos2_rows),
        ("pos3", pos3_rows),
        ("pos4", pos4_rows),
        ("pos5", pos5_rows),
    ]
    avg_mdd_by_pos = {
        label: _avg("mdd", subset) for label, subset in pos_blocks if subset
    }
    avg_cagr_by_pos = {
        label: _avg("cagr", subset) for label, subset in pos_blocks if subset
    }

    # Q1: max_positions=2가 병목이었는가
    # 진짜 병목 판정은 pre-cap 후보 풀이 2개 초과였던 리밸런스 수를 본다.
    # (pos2에서 BLOCKED_MAX_POSITIONS는 candidate 수가 실제로 많았음을 뜻한다)
    _q1_bottleneck = pos2_blocked_sum > 0 or pos2_pre_cap_max > 0
    q1 = (
        "pos2 실험군당 평균 Blocked MaxPos={}회"
        " (실험군 합계 {}회),"
        " pre-cap 후보>2 리밸런스={}회"
        " → 병목 {}"
    ).format(
        pos2_blocked_avg if pos2_blocked_avg is not None else 0,
        pos2_blocked_sum,
        pos2_pre_cap_max,
        "존재 (확대 필요 가능)" if _q1_bottleneck else "미확인",
    )

    # Q2: 보유 수 확대가 MDD를 줄였는가
    def _fmt(v):
        return f"{v:.2f}%" if v is not None else "N/A"

    mdd_str = ", ".join(f"{k}={_fmt(v)}" for k, v in avg_mdd_by_pos.items())
    if pos2_avg_mdd is not None and avg_mdd_by_pos:
        _min_label = min(
            avg_mdd_by_pos,
            key=lambda k: (
                avg_mdd_by_pos[k] if avg_mdd_by_pos[k] is not None else 9999.0
            ),
        )
        q2 = f"평균 MDD [{mdd_str}]" f" → 최저 MDD 구간: {_min_label}"
    else:
        q2 = f"평균 MDD [{mdd_str}]"

    # Q3: CAGR 훼손폭
    cagr_str = ", ".join(f"{k}={_fmt(v)}" for k, v in avg_cagr_by_pos.items())
    q3 = f"평균 CAGR [{cagr_str}]"

    # Q4: 다음 단계 기본 search space
    # MDD<10 만족하는 구간 우선, 없으면 MDD 최소 구간
    def _score(label, subset):
        avg_m = _avg("mdd", subset)
        avg_c = _avg("cagr", subset)
        if avg_m is None:
            return (1, 9999.0, 0.0)
        ok = 0 if (avg_m < 10 and (avg_c or 0) > 15) else 1
        return (ok, avg_m, -(avg_c or 0))

    ranked = sorted(
        [(label, subset) for label, subset in pos_blocks if subset],
        key=lambda x: _score(x[0], x[1]),
    )
    next_space = ranked[0][0] if ranked else "N/A"
    q4 = f"다음 단계 기본 search space 후보: {next_space}"

    return [
        "",
        "## 진단 요약",
        f"- Q1 (pos2가 실제 병목이었는가): {q1}",
        f"- Q2 (보유 수 확대가 MDD를 줄였는가): {q2}",
        f"- Q3 (CAGR 훼손폭): {q3}",
        f"- Q4 (다음 단계 기본 search space): {q4}",
    ]
