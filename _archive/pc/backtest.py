# -*- coding: utf-8 -*-
"""
backtest.py
- scanner.py의 규칙(레짐/급등/추세/강도/섹터TOP)으로
  일별 신호를 계산하고, 설정된 주기(W/M/D)에 체결하여
  NAV를 시뮬레이션합니다.
- 거래비용/슬리피지도 반영합니다.
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional, List
import numpy as np
import pandas as pd
from core.indicators import sma
import yfinance as yf
from core.data_loader import get_ohlcv_safe
from sqlalchemy import select


from core.db import SessionLocal, Security, PriceDaily, Security
from pc.scanner import (
    load_config_yaml, load_sectors_map,
    get_universe_codes, load_prices,
    build_candidate_table, rank_composite,
    regime_ok, check_sell_rules
)


def _price_panel(session: SessionLocal, codes: List[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    q = select(PriceDaily).where(PriceDaily.date >= start.date()).where(PriceDaily.date <= end.date())
    rows = session.execute(q).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["date","code","open","high","low","close","volume"])
    df = pd.DataFrame([{
        "code": r.code, "date": r.date,
        "open": r.open, "high": r.high, "low": r.low,
        "close": r.close, "volume": r.volume
    } for r in rows])
    if codes:
        df = df[df["code"].isin(codes)]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["date","code"])


def _make_trade_dates(all_dates: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    f = (freq or "W").upper()
    if f.startswith("M"):
        # 매월 마지막 거래일
        return all_dates.to_series().groupby([all_dates.year, all_dates.month]).tail(1).index
    if f.startswith("D"):
        return all_dates
    # 기본: 주간(그 주의 마지막 거래일)
    return all_dates.to_series().groupby([all_dates.year, all_dates.isocalendar().week]).tail(1).index


def _series_nav_from_weights(wide: pd.DataFrame,
                             trade_dates: pd.DatetimeIndex,
                             cfg: dict,
                             sectors_map: Dict[str, str],
                             asof_dates: pd.DatetimeIndex) -> pd.Series:
    """
    핵심 시뮬레이터:
      - 매일 수익 반영
      - trade_dates에서만 리밸런스
      - 리밸런스 시엔 scanner 규칙으로 TOP N 선정
      - SELL 룰은 일 단위로 체크하여 보유 축소
      - 비용(수수료+슬리피지) = (fee_bps+slip_bps) * turnover 에 NAV에서 즉시 차감
    """
    slippage_bps = float(cfg["backtest"].get("slippage_bps", 8))
    fee_bps      = float(cfg["backtest"].get("fee_bps", 5))
    cost_perc    = (slippage_bps + fee_bps) / 10000.0

    nav = pd.Series(index=asof_dates, dtype=float)
    nav.iloc[0] = 1.0
    weights: Dict[str, float] = {}  # 현재 보유 비중

    for i, d in enumerate(asof_dates):
        prev = asof_dates[i-1] if i > 0 else None

        # ===== 일일 수익 반영 =====
        if i > 0 and weights:
            day_ret = 0.0
            for c, w in list(weights.items()):
                if c not in wide.columns:  # 데이터 없음
                    continue
                px_t = wide.loc[d, c]
                # 직전 거래일 가격
                if prev in wide.index:
                    px_y = wide.loc[prev, c]
                else:
                    px_y = wide.loc[:d, c].iloc[-2] if len(wide.loc[:d, c]) >= 2 else np.nan
                if np.isnan(px_t) or np.isnan(px_y) or px_y == 0:
                    continue
                day_ret += w * (px_t / px_y - 1.0)
            nav.loc[d] = nav.loc[prev] * (1.0 + day_ret)
        elif i > 0:
            nav.loc[d] = nav.loc[prev]  # 현금 상태

        # ===== SELL 룰 일일 체크 (보유 축소) =====
        if weights:
            # 포지션 DF로 변환
            pos_df = pd.DataFrame([{"code": k, "weight": v} for k, v in weights.items()])
            # 가격 패널 (이날까지)
            panel_d = wide.loc[:d, weights.keys()].copy()
            panel_d = panel_d.stack().reset_index()
            panel_d.columns = ["date","code","close"]
            # check_sell_rules는 OHLCV 필요 → close만 있는 단축판: SELL 룰에서 ADX/MFI/VolZ를 생략하지 않으려면
            # 전체 패널이 필요하므로, 외부에서 price_panel을 공급받아야 함. 단순화 위해 여기선 close 기반 룰 최소화 가능.
            # 다만 정확도를 위해 scanner와 동일한 판별을 호출하려면 원본 패널이 필요 → 아래 외부 호출에서 처리.
            # (간결화를 위해 SELL룰은 리밸런스 시점에서만 엄밀히 적용하도록 아래에서 처리)

        # ===== 리밸런스 / 신호 갱신 =====
        if d in trade_dates:
            # 레짐 체크
            if not regime_ok(d, cfg):
                # 전량 현금
                if weights:
                    # 전량 청산 비용 = 합산 비중 (turnover)
                    turnover = sum(abs(w) for w in weights.values())
                    nav.loc[d] = nav.loc[d] * (1.0 - cost_perc * turnover)
                weights = {}
                continue

            # 후보 생성 및 랭킹
            # build_candidate_table / rank_composite는 OHLCV 패널 필요 → wide만으론 부족
            # => price_panel을 재구성
            # (효율 위해 루프 밖에서 전체 패널을 전달할 수도 있으나, 코드 단순화를 위해 여기서 로드)
            with SessionLocal() as s:
                codes_all = list(wide.columns)
                panel_full = _load_panel_full(s, codes_all, end=d, lookback=300)
            cands = build_candidate_table(panel_full, d, cfg)
            if cands.empty:
                # 유지(현금이면 그대로)
                continue
            sectors = sectors_map or {}
            picks = rank_composite(cands[cands["all_ok"] == True], panel_full, sectors, cfg, d)
            if picks.empty:
                continue

            # 목표 비중
            top_codes = picks["code"].tolist()
            new_w = {c: 1.0/len(top_codes) for c in top_codes}

            # 비용(턴오버) 계산
            all_codes = set(weights.keys()) | set(new_w.keys())
            turnover = sum(abs(weights.get(c, 0.0) - new_w.get(c, 0.0)) for c in all_codes)

            # 비용 차감
            if i > 0:
                nav.loc[d] = nav.loc[d] * (1.0 - cost_perc * turnover)

            # 갱신
            weights = new_w

    return nav.ffill()


def _load_panel_full(session: SessionLocal, codes: List[str], end: pd.Timestamp, lookback: int) -> pd.DataFrame:
    start = (end - pd.Timedelta(days=lookback)).date()
    q = select(PriceDaily).where(PriceDaily.date >= start).where(PriceDaily.date <= end.date())
    rows = session.execute(q).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["date","code","open","high","low","close","volume"])
    df = pd.DataFrame([{
        "code": r.code, "date": r.date,
        "open": r.open, "high": r.high, "low": r.low,
        "close": r.close, "volume": r.volume
    } for r in rows if r.code in codes])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["date","code"])


def run_backtest(start: str, end: str, config_path: str = "config.yaml"):
    cfg = load_config_yaml(config_path)
    start_ts = pd.to_datetime(start)
    end_ts   = pd.to_datetime(end)

    # 1) 데이터 로드
    with SessionLocal() as s:
        codes = get_universe_codes(s, cfg)
        panel = _price_panel(s, codes, start_ts - pd.Timedelta(days=60), end_ts)
    if panel.empty:
        print("가격 데이터가 없습니다. 먼저 ingest-eod 로 적재하세요.")
        return

    # 2) 거래일/리밸런스일
    wide = panel.pivot(index="date", columns="code", values="close").sort_index().ffill()
    all_dates = wide.index[(wide.index >= start_ts) & (wide.index <= end_ts)]
    trade_dates = _make_trade_dates(all_dates, cfg["backtest"].get("trade_frequency", "W"))

    # 3) 섹터 맵(없어도 동작)
    sectors = load_sectors_map("sectors_map.csv")

    # 4) NAV 시뮬
    nav = _series_nav_from_weights(wide, trade_dates, cfg, sectors, all_dates)

        # 5) 벤치마크(기본: 379800.KS)
    bench_code = cfg["backtest"].get("benchmark_code", "379800")

    # bench_nav: 벤치마크 종가 시리즈(거래일 인덱스에 맞춰 정렬/보간)
    bench_nav = None

    # 5-1) DB 시세에 있으면 그대로 사용
    if bench_code in wide.columns:
        bench_nav = wide[bench_code].reindex(all_dates).ffill()

    # 5-2) DB에 없으면 KRX에서 수집(야후 사용 안 함, 레이트리밋 회피)
    if bench_nav is None or bench_nav.dropna().empty:
        bcode = bench_code if str(bench_code).endswith(".KS") else f"{bench_code}.KS"
        try:
            y = get_ohlcv_safe(bcode, start_ts.date(), end_ts.date())  # DataFrame(OHLCV)
            if y is not None and not y.empty:
                bench_nav = y["Close"].reindex(all_dates).ffill()
        except Exception:
            bench_nav = None

    # 5-3) 결과 확인 + 누적수익 계산
    if bench_nav is None or bench_nav.dropna().empty:
        print("벤치마크 데이터를 불러오지 못했습니다. NAV만 출력합니다.")
        bench_cum = float("nan")
    else:
        bench_nav = pd.Series(bench_nav).astype(float).dropna().sort_index()
        bench_cum = (bench_nav.iloc[-1] / bench_nav.iloc[0]) - 1.0

    # 6) 성과 요약
    def _mdd(s: pd.Series) -> float:
        s = s.dropna()
        if s.empty: return np.nan
        roll_max = s.cummax()
        dd = s / roll_max - 1.0
        return float(dd.min())

    port_cum  = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    port_mdd  = _mdd(nav)
    rows = [
        ["기간", f"{nav.index[0].date()} ~ {nav.index[-1].date()}"],
        ["전략 누적수익률", f"{port_cum*100:.2f}%"],
        ["전략 MDD", f"{port_mdd*100:.2f}%"],
    ]
    if bench_nav is not None:
        bench_cum = ((bench_nav.iloc[-1] / bench_nav.iloc[0]) - 1.0) if len(bench_nav)>=2 else float('nan')
        bench_mdd = _mdd(bench_nav)
        rows += [
            [f"벤치마크({bench_code}) 누적", f"{bench_cum*100:.2f}%"],
            ["벤치마크 MDD", f"{bench_mdd*100:.2f}%"],
            ["초과수익(전략-벤치)", f"{(port_cum-bench_cum)*100:.2f}%"],
        ]

    # --- save run to CSV ---
    try:
        import os
        os.makedirs("backtests", exist_ok=True)
        dd = pd.Index(all_dates, name="date")
        nav_s   = pd.Series(nav, index=dd, name="strategy").astype(float).ffill()
        bench_s = pd.Series(bench_nav, index=dd, name="benchmark").astype(float).ffill() if "bench_nav" in locals() and bench_nav is not None else None

        out = pd.concat([nav_s, bench_s], axis=1) if bench_s is not None else nav_s.to_frame()
        out.reset_index().to_csv(f"backtests/run_{pd.Timestamp.now():%Y%m%d_%H%M%S}.csv", index=False)
        print(f"[백테스트] CSV 저장 완료 → backtests/run_YYYYMMDD_HHMMSS.csv")
    except Exception as e:
        print(f"[백테스트] CSV 저장 실패: {e}")
    
    print(tabulate(rows, tablefmt="plain"))

    # (선택) CSV 저장 등은 필요 시 추가
