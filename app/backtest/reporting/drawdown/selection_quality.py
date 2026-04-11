#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/selection_quality.py — 선택 품질 분석

P209-STEP9A drawdown 분석의 선택 품질 단계. 각 리밸런스에서 선택된 종목의
forward return 과 "선택하지 않은 상위 후보" 와의 gap 을 계산한다.

단일 책임: trades + rebalance_trace + close_by_code → selection events list,
그리고 events list → summary + verdict
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

import pandas as pd


def _price_at(s: pd.Series, ts: pd.Timestamp) -> Optional[float]:
    """close series에서 ts 시점 이하의 가장 가까운 종가를 반환.

    R5 (fallback 정책): 이 함수는 lookup helper 이므로 None 반환은 허용된
    explicit 시그널이다 ('해당 시점에 가격이 없음'). 호출자는 반드시 명시적
    으로 None 을 분기 처리해야 하며, 0.0 fallback 으로 처리하면 안 된다.

    None 반환 케이스:
    - s 가 None 또는 empty (ticker 가격 데이터 자체가 없음)
    - asof 가 NaT 반환 (ts 이전에 거래된 적 없음)
    - loc 으로 가격 조회 실패 (인덱스 불일치)
    - 가격이 <= 0 (비정상 가격)

    모든 호출자는 `if price is None: continue` 형태로 명시 분기한다.
    """
    if s is None or s.empty:
        return None
    try:
        idx = s.index.asof(ts)
    except (KeyError, TypeError):
        return None
    if idx is None or (hasattr(pd, "NaT") and idx is pd.NaT):
        return None
    try:
        px = float(s.loc[idx])
    except (KeyError, TypeError, ValueError):
        return None
    return px if px > 0 else None


def compute_selection_quality(
    trades: List[Any],
    rebalance_trace: List[Dict[str, Any]],
    close_by_code: Dict[str, pd.Series],
    unselected_topk: int = 5,
) -> List[Dict[str, Any]]:
    """리밸런스 날짜별 선택 품질 분석 (선택 vs 비선택 상위 후보 비교).

    각 리밸런스에서:
      1. 선택된(BUY) 종목의 forward return (trade price → next rebal close)
      2. cap 이전 상위 후보 중 '선택되지 않은' top-K의 forward return
         (entry = 해당 리밸런스일 close, exit = 다음 리밸런스 close)
      3. selection_gap_pct = avg_unselected - avg_selected
         (양수 = 비선택이 더 좋았다 = selection miss)

    R5v2 fallback 정책:
    - REQUIRED: r_trace 의 `rebalance_date`, `top_candidates_ranked` 는
      backtest_runner.py 가 P209-STEP9A 이후 항상 설정 → 누락 시 KeyError raise
    - WHITELIST: 내부 `continue` 문들은 "특정 ticker 의 가격 데이터 없음 /
      매매가 없음 / 후보 없음" 같은 legitimate skip 패턴. 전체 분석을
      중단시키지 않고 해당 ticker/event 만 건너뛴다.
    """
    if not rebalance_trace:
        return []

    buys_by_date: Dict[str, List[Any]] = defaultdict(list)
    for t in trades:
        if t.action == "BUY":
            buys_by_date[str(t.date)].append(t)

    # REQUIRED: rebalance_date 는 모든 trace entry 에 반드시 존재
    for r_trace in rebalance_trace:
        if "rebalance_date" not in r_trace:
            raise KeyError(
                "compute_selection_quality: rebalance_trace entry 에"
                " 'rebalance_date' 누락"
            )
    rebal_dates_list = [r["rebalance_date"] for r in rebalance_trace]

    events: List[Dict[str, Any]] = []
    for r_trace in rebalance_trace:
        rd = r_trace["rebalance_date"]
        bought_here = buys_by_date.get(rd, [])  # R5 whitelist: 매수 없는 리밸런스
        if not bought_here:
            continue  # R5 whitelist: 매수 없음 → skip (legitimate)

        # next rebalance date
        try:
            my_idx = rebal_dates_list.index(rd)
            next_rd = (
                rebal_dates_list[my_idx + 1]
                if my_idx + 1 < len(rebal_dates_list)
                else None
            )
        except ValueError:
            next_rd = None

        entry_ts = pd.Timestamp(rd)
        exit_ts = pd.Timestamp(next_rd) if next_rd else None

        # ── 선택된 종목 forward return (trade price 기준) ──
        per_ticker_sel: List[Dict[str, Any]] = []
        for t in bought_here:
            code = t.symbol
            entry_price = float(t.price)
            if entry_price <= 0:
                continue  # R5 whitelist: 비정상 entry price skip
            s = close_by_code.get(code)  # R5 whitelist: 가격 없는 ticker 는 None
            if exit_ts is not None:
                exit_price = _price_at(s, exit_ts)
            else:
                exit_price = (
                    float(s.iloc[-1]) if s is not None and not s.empty else None
                )
            if exit_price is None or exit_price <= 0:
                continue  # R5 whitelist: exit price 없음 → skip (lookup miss)
            ret = (exit_price / entry_price - 1.0) * 100
            per_ticker_sel.append(
                {
                    "ticker": code,
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "return_pct": round(ret, 4),
                }
            )

        if not per_ticker_sel:
            continue  # R5 whitelist: 계산 가능한 선택 종목 없음 → skip

        selected_codes = {r["ticker"] for r in per_ticker_sel}
        avg_sel = sum(r["return_pct"] for r in per_ticker_sel) / len(per_ticker_sel)
        worst_sel = min(per_ticker_sel, key=lambda x: x["return_pct"])
        best_sel = max(per_ticker_sel, key=lambda x: x["return_pct"])

        # ── 선택되지 않은 상위 후보 forward return ──
        # REQUIRED: top_candidates_ranked 는 P209-STEP9A 이후 backtest_runner 가
        # 항상 설정 (빈 list 도 legitimate, 단 키는 존재해야 함).
        if "top_candidates_ranked" not in r_trace:
            raise KeyError(
                "compute_selection_quality: rebalance_trace entry 에"
                f" 'top_candidates_ranked' 누락 (rd={rd})"
            )
        candidates_ranked = r_trace["top_candidates_ranked"]
        per_ticker_unsel: List[Dict[str, Any]] = []
        for c in candidates_ranked:
            # REQUIRED: candidate dict 는 code/rank/score 를 backtest_runner 가
            # 항상 설정 (P209-STEP9A)
            if "code" not in c:
                raise KeyError(
                    "compute_selection_quality: candidate 에 'code' 누락" f" (rd={rd})"
                )
            code = c["code"]
            if code in selected_codes:
                continue  # R5 whitelist: 이미 선택된 종목 제외
            s = close_by_code.get(code)  # R5 whitelist: 가격 없는 ticker → None
            entry_price = _price_at(s, entry_ts)
            if entry_price is None:
                continue  # R5 whitelist: entry price 없음 → skip
            if exit_ts is not None:
                exit_price = _price_at(s, exit_ts)
            else:
                exit_price = (
                    float(s.iloc[-1]) if s is not None and not s.empty else None
                )
            if exit_price is None or exit_price <= 0:
                continue  # R5 whitelist: exit price 없음 → skip
            ret = (exit_price / entry_price - 1.0) * 100
            per_ticker_unsel.append(
                {
                    "ticker": code,
                    # rank/score 는 backtest_runner 가 항상 설정 (P209-STEP9A)
                    "rank": c["rank"],
                    "score": c["score"],
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "return_pct": round(ret, 4),
                }
            )
            if len(per_ticker_unsel) >= unselected_topk:
                break

        if per_ticker_unsel:
            avg_unsel = sum(r["return_pct"] for r in per_ticker_unsel) / len(
                per_ticker_unsel
            )
            gap_pct = round(avg_unsel - avg_sel, 4)
            best_unsel = max(per_ticker_unsel, key=lambda x: x["return_pct"])
        else:
            avg_unsel = None
            gap_pct = None
            best_unsel = None

        events.append(
            {
                "rebalance_date": rd,
                "next_rebalance_date": next_rd,
                "selected_tickers": [r["ticker"] for r in per_ticker_sel],
                "per_ticker": per_ticker_sel,
                "avg_forward_return_pct": round(avg_sel, 4),
                "best_selected_ticker": best_sel["ticker"],
                "best_selected_return_pct": best_sel["return_pct"],
                "worst_ticker": worst_sel["ticker"],
                "worst_return_pct": worst_sel["return_pct"],
                # P209-STEP9A: 비선택 상위 후보 비교
                "unselected_top_candidates": per_ticker_unsel,
                "avg_unselected_forward_return_pct": (
                    round(avg_unsel, 4) if avg_unsel is not None else None
                ),
                "selection_gap_pct": gap_pct,
                "best_unselected_ticker": (
                    best_unsel.get("ticker") if best_unsel else None
                ),
                "best_unselected_return_pct": (
                    best_unsel.get("return_pct") if best_unsel else None
                ),
            }
        )
    return events


def _summarize_selection_quality(
    events: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """선택 품질 이벤트 리스트 → 요약 dict.

    R5 (fallback 제거): 이전에는 events 가 비어있으면 numeric 필드를 0.0 으로
    채운 dict 를 반환했음. 이 silent 0 fallback 은 "0 건" 과 "데이터 없음" 을
    구분하지 못해 금지. 대신 events 가 비면 `None` 반환. 호출자는 반드시
    명시적으로 None 을 분기 처리한다 (analyze_variant 가 verdict='NO_EVENTS'
    로 처리).
    """
    if not events:
        return None
    rets = [e["avg_forward_return_pct"] for e in events]
    positive = sum(1 for r in rets if r > 0)
    total = len(rets)

    # P209-STEP9A: 선택 vs 비선택 gap 집계
    gaps = [
        e.get("selection_gap_pct")
        for e in events
        if e.get("selection_gap_pct") is not None
    ]
    avg_gap = (sum(gaps) / len(gaps)) if gaps else None
    events_with_gap = len(gaps)
    events_miss = sum(1 for g in gaps if g > 0)

    return {
        "rebalance_count": total,
        "positive_forward_ratio": round(positive / total, 4),
        "avg_forward_return_pct": round(sum(rets) / total, 4),
        "best_forward_return_pct": round(max(rets), 4),
        "worst_forward_return_pct": round(min(rets), 4),
        "avg_selection_gap_pct": (round(avg_gap, 4) if avg_gap is not None else None),
        "events_with_unselected_data": events_with_gap,
        "events_with_better_unselected": events_miss,
    }


def _selection_quality_verdict(summary: Optional[Dict[str, Any]]) -> str:
    """P209-STEP9A verdict:

    - NO_EVENTS: summary 가 None (events 가 비어있음, _summarize 가 None 반환)
    - HEALTHY: positive_ratio > 0.5 AND avg > 0 AND gap <= +1%p
      (선택이 비선택보다 크게 뒤지지 않음)
    - MIXED: positive_ratio > 0.3 또는 gap이 0~+2%p 범위
    - DEGRADED: positive_ratio < 0.3 또는 gap이 +2%p 초과
      (비선택이 일관되게 더 나은 구조적 선택 오류)

    R5 (fallback 제거): summary 가 None 인 경우 명시적 NO_EVENTS 반환.
    이전에는 `.get(k, 0.0)` 로 silent 0 fallback 했음.
    """
    if summary is None:
        return "NO_EVENTS"
    # summary 는 _summarize_selection_quality 가 반환한 dict 이며
    # 필수 필드가 모두 존재함을 보장한다 (None 은 위에서 처리).
    pr = summary["positive_forward_ratio"]
    ar = summary["avg_forward_return_pct"]
    gap = summary["avg_selection_gap_pct"]

    # gap이 유의미하게 나쁘면 DEGRADED 우선
    if gap is not None and gap > 2.0:
        return "DEGRADED"

    if pr > 0.5 and ar > 0 and (gap is None or gap <= 1.0):
        return "HEALTHY"
    if pr > 0.3:
        return "MIXED"
    return "DEGRADED"
