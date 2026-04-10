#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown_contribution.py — P209-STEP9A

개별 종목 / bucket / 리밸런스 / 구간별 drawdown 기여 분석 모듈.

이번 단계는 분석 챕터이며, 필터나 ML을 실제 매매 로직에 적용하지 않는다.
산출물은 Step9B(Track A 규칙기반) / Track B(ML classifier) 설계의 근거다.

핵심 분석:
1. MDD window (peak/trough) 식별
2. 종목별 drawdown 기여 (daily return attribution)
3. 리밸런스별 선택 품질 (선택 종목의 forward return)
4. bucket/group 수준 위험 요약
5. Selection Quality Verdict (HEALTHY / MIXED / DEGRADED)
"""

from __future__ import annotations

import csv as _csv
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ─── 1. MDD window 식별 ────────────────────────────────────────────────
def find_mdd_window(nav_history: List[Tuple[Any, float]]) -> Optional[Dict[str, Any]]:
    """nav_history에서 최대낙폭 구간(peak/trough)을 찾는다.

    nav_history: [(date_like, nav_float), ...]
    """
    if not nav_history or len(nav_history) < 2:
        return None

    peak_idx = 0
    trough_idx = 0
    cur_peak_nav = float(nav_history[0][1])
    cur_peak_idx = 0
    max_dd = 0.0

    for i, (_d, nav) in enumerate(nav_history):
        nv = float(nav)
        if nv > cur_peak_nav:
            cur_peak_nav = nv
            cur_peak_idx = i
        if cur_peak_nav > 0:
            dd = (nv - cur_peak_nav) / cur_peak_nav
            if dd < max_dd:
                max_dd = dd
                peak_idx = cur_peak_idx
                trough_idx = i

    return {
        "peak_date": str(nav_history[peak_idx][0]),
        "peak_nav": round(float(nav_history[peak_idx][1]), 2),
        "trough_date": str(nav_history[trough_idx][0]),
        "trough_nav": round(float(nav_history[trough_idx][1]), 2),
        "mdd_pct": round(abs(max_dd) * 100, 4),
        "window_length_days": int(trough_idx - peak_idx),
    }


# ─── 2. daily per-ticker position 복원 ────────────────────────────────
def _build_close_series(price_data) -> Dict[str, pd.Series]:
    """MultiIndex(code, date) price_data에서 ticker별 close 시리즈 추출."""
    out: Dict[str, pd.Series] = {}
    if not isinstance(price_data.index, pd.MultiIndex):
        return out
    for code in price_data.index.get_level_values("code").unique():
        df = price_data.xs(code, level="code")
        col = None
        if "close" in df.columns:
            col = "close"
        elif "Close" in df.columns:
            col = "Close"
        if col is None:
            continue
        s = df[col].astype(float)
        if not isinstance(s.index, pd.DatetimeIndex):
            s.index = pd.to_datetime(s.index)
        out[code] = s.sort_index()
    return out


def reconstruct_daily_positions(
    trades: List[Any],
    nav_history: List[Tuple[Any, float]],
    close_by_code: Dict[str, pd.Series],
) -> List[Dict[str, Any]]:
    """trades를 replay하여 각 영업일별 per-ticker 수량/시가총액/현금흐름을 복원.

    반환: [{"date": str, "value": {code: float}, "cash_flow": {code: float}}, ...]
    - value: end-of-day mark-to-market (기존 + 신규 포지션 모두 포함)
    - cash_flow: 당일 매매로 인한 ticker별 현금 유출입
        (양수=순매수 cost, 음수=순매도 proceeds).
        return attribution 시 이 값을 P&L에서 차감해야 순수 mark-to-market
        수익 기여만 남는다.
    """
    if not nav_history:
        return []

    events_by_date: Dict[str, List[Any]] = defaultdict(list)
    for t in trades:
        events_by_date[str(t.date)].append(t)

    qtys: Dict[str, int] = defaultdict(int)
    daily: List[Dict[str, Any]] = []

    for d, _nav in nav_history:
        d_str = str(d)
        ts = pd.Timestamp(d_str)

        cash_flow: Dict[str, float] = defaultdict(float)
        # 거래 적용 (BUY 가산, SELL 차감) + ticker별 cash flow 누적
        for t in events_by_date.get(d_str, []):
            q = int(getattr(t, "quantity", 0))
            p = float(getattr(t, "price", 0.0))
            if t.action == "BUY":
                qtys[t.symbol] += q
                cash_flow[t.symbol] += q * p  # 순매수 cost (양수)
            elif t.action == "SELL":
                qtys[t.symbol] -= q
                if qtys[t.symbol] < 0:
                    qtys[t.symbol] = 0
                cash_flow[t.symbol] -= q * p  # 매도 proceeds (음수)

        # Mark-to-market
        vals: Dict[str, float] = {}
        for code, q in qtys.items():
            if q <= 0:
                continue
            s = close_by_code.get(code)
            if s is None or s.empty:
                continue
            try:
                idx = s.index.asof(ts)
            except (KeyError, TypeError):
                idx = None
            if idx is None or (hasattr(pd, "NaT") and idx is pd.NaT):
                continue
            try:
                price = float(s.loc[idx])
            except (KeyError, TypeError, ValueError):
                continue
            if price > 0:
                vals[code] = q * price

        daily.append(
            {
                "date": d_str,
                "value": vals,
                "cash_flow": dict(cash_flow),
            }
        )

    return daily


# ─── 3. 종목별 MDD 기여 ────────────────────────────────────────────────
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
        prev_nav = nav_map.get(prev["date"], 0.0)
        if prev_nav <= 0:
            continue
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


# ─── 4. 리밸런스별 선택 품질 ───────────────────────────────────────────
def _price_at(s: pd.Series, ts: pd.Timestamp) -> Optional[float]:
    """close series에서 ts 시점 이하의 가장 가까운 종가를 반환."""
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
    """
    if not rebalance_trace:
        return []

    buys_by_date: Dict[str, List[Any]] = defaultdict(list)
    for t in trades:
        if t.action == "BUY":
            buys_by_date[str(t.date)].append(t)

    # 다음 리밸런스 날짜 룩업용
    rebal_dates_list = [
        r.get("rebalance_date") for r in rebalance_trace if r.get("rebalance_date")
    ]

    events: List[Dict[str, Any]] = []
    for r_trace in rebalance_trace:
        rd = r_trace.get("rebalance_date")
        if not rd:
            continue
        bought_here = buys_by_date.get(rd, [])
        if not bought_here:
            continue

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
                continue
            s = close_by_code.get(code)
            if exit_ts is not None:
                exit_price = _price_at(s, exit_ts)
            else:
                exit_price = (
                    float(s.iloc[-1]) if s is not None and not s.empty else None
                )
            if exit_price is None or exit_price <= 0:
                continue
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
            continue

        selected_codes = {r["ticker"] for r in per_ticker_sel}
        avg_sel = sum(r["return_pct"] for r in per_ticker_sel) / len(per_ticker_sel)
        worst_sel = min(per_ticker_sel, key=lambda x: x["return_pct"])
        best_sel = max(per_ticker_sel, key=lambda x: x["return_pct"])

        # ── 선택되지 않은 상위 후보 forward return ──
        # entry = 해당 리밸런스일 close (trade price가 아님 — 실제 매매가
        # 없었으므로 close로 근사)
        candidates_ranked = r_trace.get("top_candidates_ranked") or []
        per_ticker_unsel: List[Dict[str, Any]] = []
        for c in candidates_ranked:
            code = c.get("code")
            if not code or code in selected_codes:
                continue
            s = close_by_code.get(code)
            entry_price = _price_at(s, entry_ts)
            if entry_price is None:
                continue
            if exit_ts is not None:
                exit_price = _price_at(s, exit_ts)
            else:
                exit_price = (
                    float(s.iloc[-1]) if s is not None and not s.empty else None
                )
            if exit_price is None or exit_price <= 0:
                continue
            ret = (exit_price / entry_price - 1.0) * 100
            per_ticker_unsel.append(
                {
                    "ticker": code,
                    "rank": c.get("rank"),
                    "score": c.get("score"),
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


# ─── 5. bucket / group 수준 위험 집계 ──────────────────────────────────
def compute_bucket_risk(
    ticker_contribs: List[Dict[str, Any]],
    buckets: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """종목별 기여를 bucket 멤버십 기준으로 집계.

    dynamic_etf_market 모드에서는 실제 거래 종목이 buckets universe에 없을 수
    있으므로, 매칭 안 되는 종목은 'dynamic_pool'로 분류한다.
    """
    tk_to_bucket: Dict[str, str] = {}
    for b in buckets or []:
        name = b.get("name", "unknown")
        for tk in b.get("universe", []) or []:
            tk_to_bucket[tk] = name

    agg: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "ticker_count": 0,
            "total_contribution_pct": 0.0,
            "avg_weight_sum": 0.0,
            "days_held_sum": 0,
        }
    )

    for row in ticker_contribs:
        code = row.get("ticker")
        bucket = tk_to_bucket.get(code, "dynamic_pool")
        a = agg[bucket]
        a["ticker_count"] += 1
        a["total_contribution_pct"] += float(row.get("contribution_to_nav_pct", 0.0))
        a["avg_weight_sum"] += float(row.get("avg_weight", 0.0))
        a["days_held_sum"] += int(row.get("days_in_portfolio", 0))

    out: Dict[str, Dict[str, Any]] = {}
    for bucket, a in agg.items():
        cnt = a["ticker_count"]
        out[bucket] = {
            "ticker_count": int(cnt),
            "total_contribution_pct": round(a["total_contribution_pct"], 4),
            "avg_weight": round(a["avg_weight_sum"] / cnt, 4) if cnt else 0.0,
            "avg_days_held": round(a["days_held_sum"] / cnt, 2) if cnt else 0.0,
        }
    return out


# ─── 6. Selection Quality Summary / Verdict ────────────────────────────
def _summarize_selection_quality(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not events:
        return {
            "rebalance_count": 0,
            "positive_forward_ratio": 0.0,
            "avg_forward_return_pct": 0.0,
            "best_forward_return_pct": 0.0,
            "worst_forward_return_pct": 0.0,
            "avg_selection_gap_pct": None,
            "events_with_unselected_data": 0,
            "events_with_better_unselected": 0,
        }
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


def _selection_quality_verdict(summary: Dict[str, Any]) -> str:
    """P209-STEP9A verdict:

    - HEALTHY: positive_ratio > 0.5 AND avg > 0 AND gap <= +1%p
      (선택이 비선택보다 크게 뒤지지 않음)
    - MIXED: positive_ratio > 0.3 또는 gap이 0~+2%p 범위
    - DEGRADED: positive_ratio < 0.3 또는 gap이 +2%p 초과
      (비선택이 일관되게 더 나은 구조적 선택 오류)
    """
    pr = summary.get("positive_forward_ratio", 0.0)
    ar = summary.get("avg_forward_return_pct", 0.0)
    gap = summary.get("avg_selection_gap_pct")

    # gap이 유의미하게 나쁘면 DEGRADED 우선
    if gap is not None and gap > 2.0:
        return "DEGRADED"

    if pr > 0.5 and ar > 0 and (gap is None or gap <= 1.0):
        return "HEALTHY"
    if pr > 0.3:
        return "MIXED"
    return "DEGRADED"


# ─── 7. 단일 variant 분석 orchestrator ────────────────────────────────
def analyze_variant(
    *,
    label: str,
    role: str,
    max_positions: int,
    allocation_mode: str,
    raw_result: Dict[str, Any],
    price_data,
    buckets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """단일 백테스트 결과에 대한 전체 drawdown 기여 분석."""
    nav_history = raw_result.get("nav_history", []) or []
    trades = raw_result.get("trades", []) or []
    rebalance_trace = raw_result.get("_rebalance_trace", []) or []

    close_by_code = _build_close_series(price_data)
    window = find_mdd_window(nav_history)

    if window is None:
        return {
            "label": label,
            "role": role,
            "max_positions": max_positions,
            "allocation_mode": allocation_mode,
            "mdd_window": None,
            "top_ticker_contributors_to_mdd": [],
            "all_ticker_contributions": [],
            "selection_quality_summary": _summarize_selection_quality([]),
            "selection_quality_verdict": "NO_DATA",
            "worst_selection_events": [],
            "bucket_risk_summary": {},
        }

    daily_pos = reconstruct_daily_positions(trades, nav_history, close_by_code)
    contribs = compute_ticker_contributions(
        daily_pos, nav_history, window["peak_date"], window["trough_date"]
    )
    sel_events = compute_selection_quality(trades, rebalance_trace, close_by_code)
    bucket_risk = compute_bucket_risk(contribs, buckets)
    summary = _summarize_selection_quality(sel_events)
    verdict = _selection_quality_verdict(summary)

    # 상위 toxic = 기여도가 가장 음수인 5개
    top_toxic = [c for c in contribs if c["contribution_to_nav_pct"] < 0][:5]
    # 최악 선택 이벤트 top 5 (worst ticker 기준 가장 큰 손실)
    worst_events = sorted(sel_events, key=lambda e: e.get("worst_return_pct", 0.0))[:5]

    return {
        "label": label,
        "role": role,
        "max_positions": max_positions,
        "allocation_mode": allocation_mode,
        "mdd_window": window,
        "top_ticker_contributors_to_mdd": top_toxic,
        "all_ticker_contributions": contribs,
        "selection_quality_summary": summary,
        "selection_quality_verdict": verdict,
        "worst_selection_events": worst_events,
        "bucket_risk_summary": bucket_risk,
    }


# ─── 8. 2-variant pipeline (A + B) ─────────────────────────────────────
_RAEW_DEFAULTS = {
    "mode": "risk_aware_equal_weight_v1",
    "risky_sleeve_only": True,
    "volatility_lookback": 20,
    "volatility_floor": 0.05,
    "volatility_cap": 0.6,
    "weight_floor": 0.35,
    "weight_cap": 0.65,
    "fallback_mode": "dynamic_equal_weight",
}
_EQW_DEFAULTS = {
    "mode": "dynamic_equal_weight",
    "fallback_mode": "dynamic_equal_weight",
}


def _build_allocation_block(mode: str) -> Dict[str, Any]:
    if mode == "dynamic_equal_weight":
        return dict(_EQW_DEFAULTS)
    if mode == "risk_aware_equal_weight_v1":
        return dict(_RAEW_DEFAULTS)
    raise ValueError(f"P209-STEP9A 지원 mode 아님: {mode!r}")


def _matches_main(
    main_params: Dict[str, Any], max_positions: int, allocation_mode: str
) -> bool:
    if main_params.get("max_positions") != max_positions:
        return False
    alloc = main_params.get("allocation") or {}
    return alloc.get("mode") == allocation_mode


def run_analysis_pipeline(
    *,
    main_params: Dict[str, Any],
    main_raw_result: Dict[str, Any],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    project_root: Path,
    a_spec: Tuple[str, int, str] = (
        "g2_pos2_raew",
        2,
        "risk_aware_equal_weight_v1",
    ),
    b_spec: Tuple[str, int, str] = (
        "g5_pos4_eq",
        4,
        "dynamic_equal_weight",
    ),
) -> Dict[str, Any]:
    """A (operational) + B (research) 2-variant 분석 파이프라인.

    - A가 현재 main SSOT와 일치하면 main_raw_result를 재사용
    - 그렇지 않으면 A를 별도 실행
    - B는 항상 별도 실행 (pos4 + eq)
    - 결과를 joint report로 저장하고 A 요약 dict을 main meta에 주입할 수 있게 반환
    """
    a_label, a_pos, a_mode = a_spec
    b_label, b_pos, b_mode = b_spec
    buckets = main_params.get("buckets") or []

    logger.info(
        f"[P209-STEP9A] drawdown 기여 분석 파이프라인 시작"
        f" A={a_label}(pos{a_pos},{a_mode})"
        f" B={b_label}(pos{b_pos},{b_mode})"
    )

    # ── A 결과 확보 ──
    if _matches_main(main_params, a_pos, a_mode):
        a_raw = main_raw_result
        logger.info(f"[P209-STEP9A] A={a_label} main 결과 재사용")
    else:
        a_params = dict(main_params)
        a_params["max_positions"] = a_pos
        a_params["allocation"] = _build_allocation_block(a_mode)
        a_params["holding_structure_experiments"] = None
        a_params["allocation_experiments"] = None
        a_params["holding_structure_experiment_name"] = a_label
        a_raw = run_backtest_fn(
            price_data,
            a_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
        )

    # ── B 결과 확보 ──
    if _matches_main(main_params, b_pos, b_mode):
        b_raw = main_raw_result
        logger.info(f"[P209-STEP9A] B={b_label} main 결과 재사용")
    else:
        b_params = dict(main_params)
        b_params["max_positions"] = b_pos
        b_params["allocation"] = _build_allocation_block(b_mode)
        b_params["holding_structure_experiments"] = None
        b_params["allocation_experiments"] = None
        b_params["holding_structure_experiment_name"] = b_label
        b_raw = run_backtest_fn(
            price_data,
            b_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
        )

    a_analysis = analyze_variant(
        label=a_label,
        role="operational_baseline",
        max_positions=a_pos,
        allocation_mode=a_mode,
        raw_result=a_raw,
        price_data=price_data,
        buckets=buckets,
    )
    b_analysis = analyze_variant(
        label=b_label,
        role="research_baseline",
        max_positions=b_pos,
        allocation_mode=b_mode,
        raw_result=b_raw,
        price_data=price_data,
        buckets=buckets,
    )

    analyses = [a_analysis, b_analysis]
    out_dir = project_root / "reports" / "tuning"
    paths = write_drawdown_contribution_report(analyses, out_dir)

    main_inject = _build_main_meta_injection(a_analysis, b_analysis)
    return {
        "analyses": analyses,
        "report_paths": {k: str(v) for k, v in paths.items()},
        "main_meta_injection": main_inject,
    }


# ─── 9. main meta 주입용 요약 dict 구성 ────────────────────────────────
def _build_main_meta_injection(
    a_analysis: Dict[str, Any],
    b_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """A 분석의 핵심 필드 + A/B 비교 요약을 main result meta에 주입할 형태로 반환."""
    a_w = a_analysis.get("mdd_window") or {}
    b_w = b_analysis.get("mdd_window") or {}
    a_qs = a_analysis.get("selection_quality_summary") or {}
    b_qs = b_analysis.get("selection_quality_summary") or {}
    return {
        "drawdown_peak_date": a_w.get("peak_date"),
        "drawdown_trough_date": a_w.get("trough_date"),
        "mdd_window_length": a_w.get("window_length_days"),
        "top_ticker_contributors_to_mdd": a_analysis.get(
            "top_ticker_contributors_to_mdd", []
        ),
        "selection_quality_summary": a_qs,
        "selection_quality_verdict": a_analysis.get("selection_quality_verdict", "N/A"),
        "worst_selection_events": a_analysis.get("worst_selection_events", []),
        "bucket_risk_summary": a_analysis.get("bucket_risk_summary", {}),
        "drawdown_analysis_comparison": {
            "operational_baseline_label": a_analysis.get("label"),
            "operational_baseline_verdict": a_analysis.get("selection_quality_verdict"),
            "operational_avg_selection_gap_pct": a_qs.get("avg_selection_gap_pct"),
            "operational_mdd_pct": a_w.get("mdd_pct"),
            "operational_positive_forward_ratio": a_qs.get("positive_forward_ratio"),
            "operational_avg_forward_return_pct": a_qs.get("avg_forward_return_pct"),
            "operational_events_with_better_unselected": a_qs.get(
                "events_with_better_unselected"
            ),
            "research_baseline_label": b_analysis.get("label"),
            "research_baseline_verdict": b_analysis.get("selection_quality_verdict"),
            "research_avg_selection_gap_pct": b_qs.get("avg_selection_gap_pct"),
            "research_mdd_pct": b_w.get("mdd_pct"),
            "research_positive_forward_ratio": b_qs.get("positive_forward_ratio"),
            "research_avg_forward_return_pct": b_qs.get("avg_forward_return_pct"),
            "research_events_with_better_unselected": b_qs.get(
                "events_with_better_unselected"
            ),
            # B군 요약 — UI side-by-side 표시용
            "research_top_toxic_tickers": b_analysis.get(
                "top_ticker_contributors_to_mdd", []
            ),
            "research_worst_selection_events": b_analysis.get(
                "worst_selection_events", []
            ),
            "research_bucket_risk_summary": b_analysis.get("bucket_risk_summary", {}),
        },
    }


# ─── 10. 산출물 생성 ──────────────────────────────────────────────────
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
    lines: List[str] = [
        "# Drawdown Contribution Analysis (P209-STEP9A)",
        "",
        f"- generated_at: {generated_at}",
        "- scope: **analysis_only** — 필터/ML은 실제 매매 로직에 적용되지 않음",
        "- verdict 기준 유지: `CAGR > 15` AND `MDD < 10`",
        "- 기여 계산: daily return attribution"
        " (prev-day position value × day return) / prev NAV",
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

    # Collect toxic across all variants
    toxic_sets: Dict[str, set] = {}
    for a in analyses:
        top3 = [
            r.get("ticker")
            for r in (a.get("top_ticker_contributors_to_mdd") or [])[:3]
            if r.get("ticker")
        ]
        toxic_sets[a["label"]] = set(top3)

    all_toxic = set()
    for s in toxic_sets.values():
        all_toxic |= s
    common_toxic = set.intersection(*toxic_sets.values()) if toxic_sets else set()

    if all_toxic:
        lines.append(f"- 모든 실험군 상위 3 Toxic 후보 합집합: {sorted(all_toxic)}")
    if common_toxic:
        lines.append(f"- 비교군 공통 Toxic 후보: {sorted(common_toxic)}")

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
