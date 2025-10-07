# scripts/ops/cal_cache.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

# 프로젝트 루트 기준으로 PKL 경로 계산
PKL = Path(__file__).resolve().parents[2] / "data" / "cache" / "kr" / "trading_days.pkl"

def trading_days_cached_or_build() -> pd.DatetimeIndex:
    """
    1) 캐시 우선: trading_days.pkl
    2) 없거나 비면 calendar_kr.load_trading_days() 호출 후 캐시 반환
    """
    if PKL.exists():
        idx = pd.read_pickle(PKL)
        if isinstance(idx, pd.DatetimeIndex) and len(idx) > 0:
            return idx

    # 캐시가 없거나 손상 ⇒ calendar_kr로 한 번 빌드 (실운영에서는
    # run_refresh_calendar.sh가 매일 생성하므로 보조 경로)
    from calendar_kr import load_trading_days
    idx = load_trading_days()
    if not isinstance(idx, pd.DatetimeIndex) or len(idx) == 0:
        raise RuntimeError("calendar cache build failed")
    return idx
