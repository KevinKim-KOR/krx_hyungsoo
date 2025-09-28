# signals/service.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Optional, Tuple
from utils.config import get_report_cfg_defaults, get_signals_cfg_defaults
from reporting_eod import _load_watchlist  # 재사용 (없어도 동작)
from .queries import (
    recent_trading_dates_kr, load_universe_from_json,
    load_prices_for_dates, load_names,
)

def compute_daily_signals(codes: Optional[List[str]] = None) -> Dict[str, object]:
    """
    멀티-모멘텀 기반 점수 산출:
      - windows (기본 1/5/20일) 수익률 * weights → score
      - mode = 'score_abs' => score ≥ +thr -> BUY, ≤ -thr -> SELL
      - mode = 'rank'      => score 상위 top_k BUY, 하위 bottom_k SELL
    룰:
      - 휴장일/데이터 부족은 생성 안 함 또는 제외
      - etf.json의 is_active=false 제외
      - 병렬 처리 금지(순차)
    """
    cfg = get_signals_cfg_defaults()
    top_n, min_abs = get_report_cfg_defaults()  # 참고 표시에만 사용
    dates = recent_trading_dates_kr(limit=max(cfg["windows"]) + 60)
    if not dates:
        return {"date": None, "signals": [], "mode": cfg["mode"], "windows": cfg["windows"]}

    d0 = dates[-1]
    # 필요한 기준일(당일 + 각 윈도우 이전일)
    need_dates: List[str] = [d0]
    for w in cfg["windows"]:
        idx = len(dates) - 1 - w
        if idx >= 0:
            need_dates.append(dates[idx])
    need_dates = sorted(set(need_dates))

    # 유니버스 결정
    if codes is None:
        codes = []
        if cfg["use_watchlist"]:
            try:
                codes = _load_watchlist() or []
            except Exception:
                codes = []
        if not codes:
            codes = load_universe_from_json()
    names = load_names(codes)
    px = load_prices_for_dates(codes, need_dates)

    rows: List[Dict] = []
    insufficient = 0
    for code in codes:
        m = px.get(code, {})
        p0 = m.get(d0)
        if p0 is None:
            insufficient += 1
            continue

        rets: List[float] = []
        ok = True
        for w in cfg["windows"]:
            idx = len(dates) - 1 - w
            if idx < 0:
                ok = False
                break
            d_prev = dates[idx]
            p1 = m.get(d_prev)
            if p1 is None or p1 == 0:
                ok = False
                break
            rets.append((p0 - p1) / p1)
        if not ok:
            insufficient += 1
            continue

        # 점수
        score = 0.0
        for r, w in zip(rets, cfg["weights"]):
            score += r * float(w)

        # 기본은 HOLD, 모드별로 결정
        signal = "HOLD"
        if cfg["mode"] == "score_abs":
            thr = float(cfg["score_threshold"])
            if score >= +thr:
                signal = "BUY"
            elif score <= -thr:
                signal = "SELL"

        rows.append({
            "code": code,
            "name": names.get(code, code),
            "date": d0,
            "r1": rets[0] if len(rets) > 0 else None,
            "r5": rets[1] if len(rets) > 1 else None,
            "r20": rets[2] if len(rets) > 2 else None,
            "score": score,
            "signal": signal,
        })

    # rank 모드면 여기서 최종 라벨링
    if cfg["mode"] == "rank":
        rows = sorted(rows, key=lambda x: x["score"], reverse=True)
        for i, row in enumerate(rows):
            if i < int(cfg["top_k"]):
                row["signal"] = "BUY"
            elif i >= max(0, len(rows) - int(cfg["bottom_k"])):
                row["signal"] = "SELL"
            else:
                row["signal"] = "HOLD"
    else:
        # score_abs 모드는 점수 절대값 큰 순으로 보여주기
        rows = sorted(rows, key=lambda x: abs(x["score"]), reverse=True)

    return {
        "date": d0,
        "signals": rows,
        "mode": cfg["mode"],
        "windows": cfg["windows"],
        "weights": cfg["weights"],
        "score_threshold": float(cfg["score_threshold"]),
        "top_k": int(cfg["top_k"]),
        "bottom_k": int(cfg["bottom_k"]),
        "use_watchlist": bool(cfg["use_watchlist"]),
        "insufficient_count": insufficient,
        "min_abs": min_abs,
    }
