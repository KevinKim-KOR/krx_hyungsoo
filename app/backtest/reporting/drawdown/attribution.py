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
        # R5v2: cash_flow 는 reconstruct_daily_positions 가 항상 설정 (빈 dict 가능)
        if "cash_flow" not in cur:
            raise KeyError(
                "compute_ticker_contributions: daily position entry 에"
                f" 'cash_flow' 누락 (date={cur['date']!r})"
            )
        cash_flow = cur["cash_flow"]
        all_codes = (
            set(prev["value"].keys()) | set(cur["value"].keys()) | set(cash_flow.keys())
        )
        for code in all_codes:
            # R5 whitelist: 수학적 semantic fallback
            # ─ code 가 prev["value"] 에 없음 = 전날 보유하지 않음 = pv 0.0 (정확)
            # ─ code 가 cur["value"] 에 없음 = 당일 보유하지 않음 = cv 0.0 (정확)
            # ─ code 가 cash_flow 에 없음 = 당일 매매 없음 = cf 0.0 (정확)
            # 이 0.0 은 "값을 모름" 이 아니라 "값이 정확히 0 이다" 이므로 silent
            # fallback 이 아닌 수학적 정의. `.get(k, 0.0)` 유지.
            pv = prev["value"].get(code, 0.0)
            cv = cur["value"].get(code, 0.0)
            cf = cash_flow.get(code, 0.0)
            # 순수 mark-to-market P&L = 가치 변화 - 매매로 인한 현금 유출입
            pnl = (cv - pv) - cf
            contribs[code] += pnl / prev_nav

        # R5v2: cur["date"] 는 window 내 날짜 → nav_map 에 반드시 존재
        if cur["date"] not in nav_map:
            raise ValueError(
                f"compute_ticker_contributions: nav_map 에"
                f" cur date={cur['date']!r} 누락 (데이터 정합성 오류)"
            )
        cur_nav = nav_map[cur["date"]]
        for code, cv in cur["value"].items():
            if cv > 0:
                days_held[code] += 1
                if cur_nav > 0:
                    weight_sum[code] += cv / cur_nav

    # R5v2: peak_date/trough_date 는 find_mdd_window 가 nav_history 에서 추출한
    # 날짜이므로 nav_map 에 반드시 존재. 누락 = 데이터 정합성 오류.
    if peak_date not in nav_map:
        raise ValueError(
            f"compute_ticker_contributions: nav_map 에 peak_date={peak_date!r}"
            " 누락 (find_mdd_window 와 nav_history 불일치)"
        )
    if trough_date not in nav_map:
        raise ValueError(
            f"compute_ticker_contributions: nav_map 에 trough_date={trough_date!r}"
            " 누락 (find_mdd_window 와 nav_history 불일치)"
        )
    peak_nav = nav_map[peak_date]
    trough_nav = nav_map[trough_date]
    if peak_nav <= 0:
        raise ValueError(
            f"compute_ticker_contributions: peak_nav <= 0"
            f" (peak_date={peak_date}, nav={peak_nav})"
        )
    total_return = (trough_nav - peak_nav) / peak_nav

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
