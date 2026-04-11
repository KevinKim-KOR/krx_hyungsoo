#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/attribution.py — 종목별 MDD return attribution

P209-STEP9A drawdown 분석의 기여도 계산 단계. daily per-ticker position +
cash_flow 데이터를 받아 MDD window 내 각 종목의 순수 mark-to-market P&L
기여를 산출한다.

단일 책임: daily positions (with cash_flow) + nav_history + peak/trough
날짜 → 종목별 contribution list
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple


def compute_ticker_contributions(
    daily_positions: List[Dict[str, Any]],
    nav_history: List[Tuple[Any, float]],
    peak_date: str,
    trough_date: str,
) -> List[Dict[str, Any]]:
    """MDD window 내 종목별 return attribution (cash flow 제외).

    순수 mark-to-market P&L 기여:
        P&L_i,t = v_i,t - v_i,(t-1) - cash_flow_i,t
        contribution_i = Σ (P&L_i,t / nav_(t-1))
    - cash_flow(당일 순매수 cost - 매도 proceeds)를 차감해서
      '현금 유입/유출'이 아닌 '보유 중 시가 평가손익'만 기여로 잡는다.
    - 이 기여의 총합은 MDD window 총 수익률과 근사 일치해야 한다
      (약간의 슬리피지/수수료 오차는 남음).
    """
    nav_map = {str(d): float(n) for d, n in nav_history}

    window = [p for p in daily_positions if peak_date <= p["date"] <= trough_date]
    if len(window) < 2:
        return []

    contribs: Dict[str, float] = defaultdict(float)
    days_held: Dict[str, int] = defaultdict(int)
    weight_sum: Dict[str, float] = defaultdict(float)

    for i in range(1, len(window)):
        prev = window[i - 1]
        cur = window[i]
        # R5: nav_map 에 date 가 없으면 데이터 손상 → raise
        # (daily_positions 와 nav_history 가 동일 nav_history 에서 파생되므로
        #  정상 케이스에서 miss 가 발생할 수 없다)
        if prev["date"] not in nav_map:
            raise ValueError(
                f"compute_ticker_contributions: nav_map 에"
                f" prev date={prev['date']!r} 누락 (데이터 정합성 오류)"
            )
        prev_nav = nav_map[prev["date"]]
        if prev_nav <= 0:
            raise ValueError(
                f"compute_ticker_contributions: prev_nav <= 0"
                f" (date={prev['date']}, nav={prev_nav}) — NAV 이상"
            )
        all_codes = (
            set(prev["value"].keys())
            | set(cur["value"].keys())
            | set(cur.get("cash_flow", {}).keys())
        )
        cash_flow = cur.get("cash_flow", {}) or {}
        for code in all_codes:
            pv = prev["value"].get(code, 0.0)
            cv = cur["value"].get(code, 0.0)
            cf = cash_flow.get(code, 0.0)
            # 순수 mark-to-market P&L = 가치 변화 - 매매로 인한 현금 유출입
            pnl = (cv - pv) - cf
            contribs[code] += pnl / prev_nav

        cur_nav = nav_map.get(cur["date"], 0.0)
        for code, cv in cur["value"].items():
            if cv > 0:
                days_held[code] += 1
                if cur_nav > 0:
                    weight_sum[code] += cv / cur_nav

    peak_nav = nav_map.get(peak_date, 0.0)
    trough_nav = nav_map.get(trough_date, 0.0)
    total_return = (trough_nav - peak_nav) / peak_nav if peak_nav > 0 else 0.0

    out: List[Dict[str, Any]] = []
    for code, c in contribs.items():
        share = (c / total_return * 100) if total_return != 0 else 0.0
        avg_w = weight_sum[code] / days_held[code] if days_held[code] > 0 else 0.0
        out.append(
            {
                "ticker": code,
                "contribution_to_nav_pct": round(c * 100, 4),
                "share_of_mdd_pct": round(share, 2),
                "days_in_portfolio": int(days_held[code]),
                "avg_weight": round(avg_w, 4),
            }
        )

    # 손실 기여가 큰 순서(가장 음수)
    out.sort(key=lambda x: x["contribution_to_nav_pct"])
    for rank, row in enumerate(out, start=1):
        row["contribution_rank"] = rank
    return out
