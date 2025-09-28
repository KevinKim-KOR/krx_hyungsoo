# signals/service.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Optional
from reporting_eod import _load_report_cfg_defaults  # min_abs, topN 재사용
from .queries import (
    latest_trading_date_kr, previous_trading_date,
    load_universe_from_json, load_last_two_closes, load_names
)

def compute_daily_signals(codes: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
    """
    단일 일간 신호:
      ret = (d0 - d1) / d1
      ret >= +min_abs -> BUY, ret <= -min_abs -> SELL, 그 외 HOLD
    룰:
      - 휴장일에는 생성하지 않음(최신 거래일이 없거나 d1 없음)
      - etf.json의 is_active=false는 제외
      - 데이터 부족(둘 중 하나 없음)은 제외
    """
    d0 = latest_trading_date_kr()
    if not d0:
        return {"date": None, "signals": []}  # 휴장일/데이터없음 → 생성 안 함

    d1 = previous_trading_date(d0)
    if not d1:
        return {"date": d0, "signals": []}

    top_n, min_abs = _load_report_cfg_defaults()

    universe = codes if (codes is not None) else load_universe_from_json()
    if not universe:
        return {"date": d0, "signals": []}

    names = load_names(universe)
    px = load_last_two_closes(universe, d0, d1)

    out: List[Dict] = []
    for code in universe:
        p0, p1 = px.get(code, (None, None))
        if p0 is None or p1 is None or p1 == 0:
            # 데이터 부족: 제외(룰)
            continue
        ret = (p0 - p1) / p1
        if ret >= min_abs:
            sig = "BUY"
        elif ret <= -min_abs:
            sig = "SELL"
        else:
            sig = "HOLD"
        out.append({"code": code, "name": names.get(code, code), "ret": ret, "signal": sig})

    # 정렬: 절대값 큰 순
    out = sorted(out, key=lambda x: abs(x["ret"]), reverse=True)
    return {"date": d0, "signals": out, "min_abs": min_abs}
