# -*- coding: utf-8 -*-
"""
scanner.py
- '급등 + 추세 + 강도 + 섹터' 다중 조건으로 BUY 후보를 선별하고
- 보유 종목에 대해 SELL(청산) 신호를 점검하는 모듈

외부 의존:
- DB: Security, PriceDaily, Position (db.py)
- 설정: config.yaml (yaml 로딩)
- 섹터: sectors_map.csv
- 지표: indicators.py
- 레짐: S&P500 (069500.KS) 200일선 (yfinance)

사용 예시 (추후 app.py에 CLI 추가 예정):
    from scanner import recommend_buy_sell, load_config_yaml
    cfg = load_config_yaml("config.yaml")
    buy_df, sell_df, meta = recommend_buy_sell(asof="2025-09-12", cfg=cfg)
"""

from __future__ import annotations
import os
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import yaml
import yfinance as yf
from krx_helpers import get_ohlcv_safe
from sqlalchemy import select
from db import SessionLocal, Security, PriceDaily, Position
from indicators import (
    sma, pct_change_n, slope, adx, mfi,
    turnover_stats, sector_score
)
from adaptive import get_effective_cfg
from pathlib import Path
# from providers.ohlcv_bridge import get_ohlcv_df as get_ohlcv  # 미사용


# -----------------------------
# 설정 / 섹터 맵 로더
# -----------------------------
def load_config_yaml(path: str = None):
    """
    설정 파일 탐색 우선순위:
      1) 인자로 들어온 path (있다면)
      2) config/config.yaml
      3) config.yaml
    둘 다 없으면 FileNotFoundError
    """
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates += [Path("config/config.yaml"), Path("config.yaml")]

    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

    raise FileNotFoundError(
        "No config file found (tried: given path, config/config.yaml, config.yaml)"
    )

def load_sectors_map(path: str = "sectors_map.csv") -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    # 필수 컬럼: code, sector
    if "code" not in df.columns or "sector" not in df.columns:
        raise ValueError("sectors_map.csv 는 최소한 'code,sector' 컬럼을 포함해야 합니다.")
    return dict(zip(df["code"].astype(str), df["sector"].astype(str)))


# -----------------------------
# 유니버스 / 가격 조회
# -----------------------------
def _exclude_by_keywords(name: str, keywords: List[str]) -> bool:
    n = (name or "").lower()
    return any(k.lower() in n for k in keywords)

def get_universe_codes(session: SessionLocal, cfg: dict) -> List[str]:
    """
    국내 ETF + 제외 키워드 + 유동성(거래대금) 필터까지 적용한 code 리스트
    """
    q = select(Security).where(Security.type == cfg["universe"]["type"])
    if cfg["universe"].get("market"):
        q = q.where(Security.market == cfg["universe"]["market"])
    secs = session.execute(q).scalars().all()
    keywords = cfg["universe"]["exclude_keywords"]
    codes = []
    for s in secs:
        if _exclude_by_keywords(s.name, keywords):
            continue
        codes.append(s.code)
    codes = sorted(set(codes))
    # 유동성 필터는 가격 로딩 후 turnover 기준으로 걸러냅니다 (아래에서 수행).
    return codes

def load_prices(session: SessionLocal, codes: List[str],
                end_date: pd.Timestamp, lookback_days: int = 280) -> pd.DataFrame:
    """
    OHLCV 중 close/volume(ADX,MFI 위해 OHLC 필요)까지 포함해서 불러옵니다.
    """
    start_date = (pd.to_datetime(end_date) - pd.Timedelta(days=lookback_days)).date()
    q = select(PriceDaily).where(PriceDaily.date >= start_date).where(PriceDaily.date <= end_date.date())
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


# -----------------------------
# 레짐 체크 (S&P500 200일선)
# -----------------------------
def regime_ok(asof: pd.Timestamp, cfg: dict) -> bool:
    days = int(cfg["regime"]["sma_days"])
    spx = cfg["regime"]["spx_ticker"]
    start = (asof - pd.Timedelta(days=days * 3)).date()
    data = get_ohlcv_safe(spx, start, asof.date())
    if data is None or data.empty:
        return False
    close = data["Close"].dropna()
    if len(close) < days:
        return False
    s200 = close.rolling(days).mean()
    return float(close.iloc[-1]) >= float(s200.iloc[-1])

# -----------------------------
# 후보 생성 / 점수화
# -----------------------------
def _last_valid(series: pd.Series) -> Optional[float]:
    if series is None or series.empty:
        return None
    return float(series.dropna().iloc[-1]) if not series.dropna().empty else None

def build_candidate_table(df: pd.DataFrame, asof: pd.Timestamp, cfg: dict) -> pd.DataFrame:
    """
    df: DataFrame[date, code, open, high, low, close, volume]
    asof 기준으로 모든 지표/점수/필터 컬럼을 만든 테이블을 반환
    """
    if df.empty:
        return pd.DataFrame()

    # 피벗 편의
    df = df.copy()
    df = df[df["date"] <= asof].copy()
    if df.empty:
        return pd.DataFrame()

    # 일별 등락률 계산을 위해 전일 대비 필요
    # code별로 최신 2일 추출해서 1일 수익률
    df = df.sort_values(["code", "date"])
    last_by_code = df.groupby("code").tail(2).copy()
    # 1일 수익률
    last_by_code["ret1"] = last_by_code.groupby("code")["close"].pct_change(1)
    r1 = last_by_code.groupby("code").tail(1)[["code", "ret1"]].set_index("code")["ret1"]

    # 20/60일 수익률, SMA, ADX/MFI, 거래대금 Z 등 계산
    rows = []
    need_turnover_mean = float(cfg["universe"].get("min_avg_turnover", 0))
    adx_n = int(cfg["scanner"]["adx_window"])
    mfi_n = int(cfg["scanner"]["mfi_window"])
    volz_n = int(cfg["scanner"]["vol_z_window"])

    for code, g in df.groupby("code"):
        g = g.sort_values("date").set_index("date")
        close = g["close"].astype(float)
        high  = g["high"].astype(float) if "high" in g else close
        low   = g["low"].astype(float) if "low" in g else close
        vol   = g["volume"].astype(float) if "volume" in g else pd.Series(index=close.index, data=np.nan)

        # 추세 지표
        s20 = sma(close, 20)
        s50 = sma(close, 50)
        s200 = sma(close, 200)
        slope20 = slope(s20, 20)

        # 모멘텀
        ret20 = pct_change_n(close, 20)
        ret60 = pct_change_n(close, 60)

        # 강도/자금유입
        adx14 = adx(high, low, close, n=adx_n)
        mfi14 = mfi(high, low, close, vol, n=mfi_n)

        # 거래대금 Z-score
        mean_to, std_to, z_to = turnover_stats(close, vol, n=volz_n)

        # 유동성 필터(20일 평균 거래대금)
        to_mean_last = _last_valid(mean_to)
        if need_turnover_mean and (to_mean_last is None or to_mean_last < need_turnover_mean):
            # 유동성 미달 → 후보 제외, 하지만 이유 기록
            pass

        rows.append({
            "code": code,
            "ret1": _last_valid(r1.reindex([code])) if code in r1.index else None,
            "ret20": _last_valid(ret20),
            "ret60": _last_valid(ret60),
            "sma20": _last_valid(s20),
            "sma50": _last_valid(s50),
            "sma200": _last_valid(s200),
            "slope20": _last_valid(slope20),
            "adx": _last_valid(adx14),
            "mfi": _last_valid(mfi14),
            "volz": _last_valid(z_to),
            "turnover_mean20": to_mean_last,
            "close": _last_valid(close),
        })

    out = pd.DataFrame(rows).dropna(subset=["close"])
    if out.empty:
        return out

    # 필터 적용
    #th = float(cfg["scanner"]["daily_jump_threshold"]) / 100.0
    # --- thresholds from config (with sane defaults) ---
    _scn = (cfg.get("scanner", {}) or {})
    _thr = (_scn.get("thresholds", {}) or {})
    adx_min = float(_thr.get("adx_min", 20.0))
    mfi_min = float(_thr.get("mfi_min", 50.0))
    mfi_max = float(_thr.get("mfi_max", 80.0))
    volz_min = float(_thr.get("volz_min", 1.0))
    jump_pct = float(_thr.get("daily_jump_pct", _scn.get("daily_jump_threshold", 2.0))) / 100.0
# ----------------------------------------------------

    # sanitize numeric cols to avoid NoneType comparison
    for _c in ["close","sma50","sma200","slope20"]:
        out[_c] = pd.to_numeric(out[_c], errors="coerce")
    out = out.dropna(subset=["close","sma50","sma200","slope20"])

    # 필터 적용
    out["trend_ok"] = (out["close"] > out["sma50"]) & (out["close"] > out["sma200"]) & (out["slope20"] > 0)
    out["jump_ok"] = (out["ret1"] >= jump_pct)
    out["strength_ok"] = (out["adx"] >= adx_min) & (out["mfi"].between(mfi_min, mfi_max, inclusive="both")) & (out["volz"] >= volz_min)
# 유동성 필터는 기존 그대로

    # 유동성 필터
    if need_turnover_mean > 0:
        out["liquidity_ok"] = out["turnover_mean20"] >= need_turnover_mean
    else:
        out["liquidity_ok"] = True

    out["all_ok"] = out["trend_ok"] & out["jump_ok"] & out["strength_ok"] & out["liquidity_ok"]
    return out


def rank_composite(cands: pd.DataFrame, prices_df: pd.DataFrame,
                   sectors_map: Dict[str, str], cfg: dict, asof: pd.Timestamp) -> pd.DataFrame:
    """
    섹터 스코어 상위 K개로 제한 후, 종목을 컴포지트 점수로 랭크
    """
    if cands.empty:
        return cands

    # 섹터 부여
    cands = cands.copy()
    cands["sector"] = cands["code"].map(sectors_map).fillna("Unknown")

    # 섹터 스코어 (20/60일)
    sec_sc = sector_score(
        prices_df[prices_df["date"] <= asof][["date", "code", "close"]],
        sectors_map, win_short=20, win_long=60, weights=(0.5, 0.5)
    )
    top_k = int(cfg["scanner"]["sector_top_k"])
    keep_secs = set(sec_sc["sector"].head(top_k).tolist())
    cands = cands[cands["sector"].isin(keep_secs)].copy()

    if cands.empty:
        return cands

    # 컴포지트 점수: (ret1, ret20, ret60, adx, mfi, volz, 20/60일 돌파율 비슷한 대용으로 ret20/ret60 사용)
    # 각 항목을 순위화(rank, 높은 것이 좋음), 동률 평균
    def _rank(s: pd.Series) -> pd.Series:
        return s.rank(method="average", na_option="keep")

    rank_cols = ["ret1", "ret20", "ret60", "adx", "mfi", "volz"]
    for col in rank_cols:
        cands[f"r_{col}"] = _rank(cands[col])

    # 합산 점수(동일 가중). 필요시 config에 가중치 테이블 추가 가능.
    cands["score"] = cands[[f"r_{c}" for c in rank_cols]].sum(axis=1)

    # 섹터당 최대 보유 개수 제한
    per_sector_cap = int(cfg["scanner"]["per_sector_cap"])
    cands = cands.sort_values(["score"], ascending=False)
    capped_rows = []
    cnt = {}
    for _, row in cands.iterrows():
        s = row["sector"]
        if cnt.get(s, 0) < per_sector_cap:
            capped_rows.append(row)
            cnt[s] = cnt.get(s, 0) + 1
    cands2 = pd.DataFrame(capped_rows)

    # 최종 TOP N
    top_n = int(cfg["scanner"]["top_n"])
    return cands2.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)


# -----------------------------
# SELL(보유) 체크
# -----------------------------
def check_sell_rules(positions: pd.DataFrame, price_panel: pd.DataFrame, cfg: dict, asof: pd.Timestamp) -> pd.DataFrame:
    """
    positions: DataFrame[code, weight] (현재 보유)
    price_panel: DataFrame[date, code, open, high, low, close, volume] (asof 포함)
    반환: SELL 추천 테이블 [code, reason, close, sma50, sma200, adx, mfi, volz]
    """
    if positions is None or positions.empty:
        return pd.DataFrame(columns=["code", "reason"])

    df = price_panel.copy()
    df = df[df["date"] <= asof].copy()
    out_rows = []

    for code, g in df.groupby("code"):
        g = g.sort_values("date").set_index("date")
        close = g["close"].astype(float)
        high  = g["high"].astype(float) if "high" in g else close
        low   = g["low"].astype(float) if "low" in g else close
        vol   = g["volume"].astype(float) if "volume" in g else pd.Series(index=close.index, data=np.nan)

        s50 = sma(close, 50)
        s200 = sma(close, 200)
        adx14 = adx(high, low, close, n=int(cfg["scanner"]["adx_window"]))
        mfi14 = mfi(high, low, close, vol, n=int(cfg["scanner"]["mfi_window"]))
        _, _, volz = turnover_stats(close, vol, n=int(cfg["scanner"]["vol_z_window"]))

        last = {
            "code": code,
            "close": _last_valid(close),
            "sma50": _last_valid(s50),
            "sma200": _last_valid(s200),
            "adx": _last_valid(adx14),
            "mfi": _last_valid(mfi14),
            "volz": _last_valid(volz),
        }

        reasons = []
        # 하드 이탈
        if cfg["sell_rules"]["hard_exit_under_sma200"] and last["close"] is not None and last["sma200"] is not None:
            if last["close"] < last["sma200"]:
                reasons.append("close<sma200")

        # 소프트 조건: sma50 아래 & 약세신호 중 1개 이상
        soft_hit = []
        if cfg["sell_rules"]["soft_exit_under_sma50"] and last["close"] is not None and last["sma50"] is not None:
            if last["close"] < last["sma50"]:
                # 약세 조건들
                # 최근 20일 수익률 < 0
                ret20 = _last_valid(pct_change_n(close, 20))
                if ret20 is not None and ret20 < 0:
                    soft_hit.append("ret20<0")
                if last["adx"] is not None and last["adx"] < float(cfg["sell_rules"]["adx_soft_threshold"]):
                    soft_hit.append("adx<soft")
                if last["mfi"] is not None and last["mfi"] < float(cfg["sell_rules"]["mfi_soft_threshold"]):
                    soft_hit.append("mfi<soft")
                if last["volz"] is not None and last["volz"] <= float(cfg["sell_rules"]["vol_z_soft_threshold"]):
                    soft_hit.append("volz<=soft")
                if soft_hit:
                    reasons.append("sma50↓+" + ",".join(soft_hit))

        if reasons:
            last["reason"] = ";".join(reasons)
            out_rows.append(last)

    return pd.DataFrame(out_rows).sort_values("code")


# -----------------------------
# 메인: BUY/SELL 추천
# -----------------------------
def recommend_buy_sell(asof: str | pd.Timestamp, cfg: dict
                       ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    """
    반환:
      buy_df:  BUY 추천 상위 N (columns: code, sector, score, ret1, ret20, ret60, adx, mfi, volz, close)
      sell_df: SELL 추천(보유 중 규칙 위반)
      meta:    {"regime_ok": bool, "asof": Timestamp, "universe_size": int, "after_filters": int}
    """
    cfg = get_effective_cfg(pd.to_datetime(asof), cfg)

    asof_ts = pd.to_datetime(asof)

    # 1) 레짐 체크
    regime = regime_ok(asof_ts, cfg)

    with SessionLocal() as s:
        # 2) 유니버스
        codes = get_universe_codes(s, cfg)

        # 3) 가격/거래량 로드
        panel = load_prices(s, codes, asof_ts, lookback_days=300)

        # 유동성 기준 때문에 최종 후보 계산 전에 panel 필요
        cands = build_candidate_table(panel, asof_ts, cfg)

        # 레짐 OFF면 BUY는 빈 리스트로 (단, SELL 체크는 진행)
        if not regime or cands.empty:
            buy_df = pd.DataFrame(columns=["code","sector","score","ret1","ret20","ret60","adx","mfi","volz","close"])
        else:
            # 4) 섹터/컴포지트 점수 기반 랭크 → TOP N
            sectors = load_sectors_map("sectors_map.csv")
            buy_df = rank_composite(cands[cands["all_ok"] == True], panel, sectors, cfg, asof_ts)

        # 5) SELL 체크: 현재 포지션 읽기
        poss = s.execute(select(Position)).scalars().all()
        pos_df = pd.DataFrame([{"code": p.code, "weight": float(p.weight)} for p in poss]) if poss else pd.DataFrame(columns=["code","weight"])
        sell_df = check_sell_rules(pos_df, panel, cfg, asof_ts)

    meta = {
    "regime_ok": bool(regime),
    "asof": asof_ts,
    "universe_size": int(len(set(panel["code"])) if not panel.empty else 0),
    "after_filters": (len(buy_df) if (buy_df is not None and not buy_df.empty) else 0),
    "adaptive_state": (cfg.get("meta", {}) or {}).get("adaptive_state", ""),
    }

    return buy_df, sell_df, meta
