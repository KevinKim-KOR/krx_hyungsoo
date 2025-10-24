# -*- coding: utf-8 -*-
"""
NAS 전용 경량 스캐너
- 백테스트/ML 의존성 제거
- 핵심 스캐닝 로직만 포함
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from core.db import SessionLocal, Security, PriceDaily
from core.indicators import sma, adx, mfi, pct_change_n
from sqlalchemy import select
import yaml

def load_config():
    """설정 파일 로드"""
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        config_path = "config.yaml"
    
    if not os.path.exists(config_path):
        # 기본 설정 반환
        return {
            "universe": {
                "type": "ETF",
                "exclude_keywords": ["레버리지", "인버스", "채권"]
            },
            "scanner": {
                "thresholds": {
                    "daily_jump_pct": 1.0,
                    "adx_min": 15.0,
                    "mfi_min": 40.0
                }
            }
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_universe_codes(session, cfg):
    """유니버스 종목 코드 조회"""
    q = select(Security).where(Security.type == cfg["universe"]["type"])
    secs = session.execute(q).scalars().all()
    
    exclude_keywords = cfg["universe"]["exclude_keywords"]
    codes = []
    for s in secs:
        name = (s.name or "").lower()
        if any(k.lower() in name for k in exclude_keywords):
            continue
        codes.append(s.code)
    
    return sorted(set(codes))

def run_scanner_nas(asof: pd.Timestamp):
    """NAS 전용 스캐너 실행"""
    cfg = load_config()
    
    with SessionLocal() as session:
        # 유니버스 조회
        codes = get_universe_codes(session, cfg)
        print(f"유니버스 크기: {len(codes)} 종목")
        
        # 가격 데이터 로드
        start_date = (asof - pd.Timedelta(days=300)).date()
        q = select(PriceDaily).where(
            PriceDaily.date >= start_date
        ).where(
            PriceDaily.date <= asof.date()
        )
        rows = session.execute(q).scalars().all()
        
        if not rows:
            print("⚠️ 가격 데이터 없음")
            return
        
        df = pd.DataFrame([{
            "code": r.code, "date": r.date,
            "open": r.open, "high": r.high, "low": r.low,
            "close": r.close, "volume": r.volume
        } for r in rows])
        
        df = df[df["code"].isin(codes)]
        df["date"] = pd.to_datetime(df["date"])
        
        # 필터링
        thresholds = cfg.get("scanner", {}).get("thresholds", {})
        jump_pct = float(thresholds.get("daily_jump_pct", 1.0)) / 100.0
        adx_min = float(thresholds.get("adx_min", 15.0))
        mfi_min = float(thresholds.get("mfi_min", 40.0))
        
        candidates = []
        for code, g in df.groupby("code"):
            g = g.sort_values("date").set_index("date")
            close = g["close"].astype(float)
            high = g["high"].astype(float)
            low = g["low"].astype(float)
            volume = g["volume"].astype(float)
            
            if len(close) < 60:
                continue
            
            # 지표 계산
            ret1 = pct_change_n(close, 1)
            ret20 = pct_change_n(close, 20)
            s50 = sma(close, 50)
            s200 = sma(close, 200)
            adx14 = adx(high, low, close, n=14)
            mfi14 = mfi(high, low, close, volume, n=14)
            
            # 최신값 추출
            try:
                last_ret1 = ret1.iloc[-1]
                last_ret20 = ret20.iloc[-1]
                last_close = close.iloc[-1]
                last_s50 = s50.iloc[-1]
                last_s200 = s200.iloc[-1]
                last_adx = adx14.iloc[-1]
                last_mfi = mfi14.iloc[-1]
            except:
                continue
            
            # 필터 조건
            if pd.isna(last_ret1) or pd.isna(last_ret20):
                continue
            if pd.isna(last_s50) or pd.isna(last_s200):
                continue
            if pd.isna(last_adx) or pd.isna(last_mfi):
                continue
            
            # 조건: 급등 + 추세 + 강도
            if (last_ret1 >= jump_pct and 
                last_close > last_s50 and 
                last_close > last_s200 and
                last_adx >= adx_min and
                last_mfi >= mfi_min):
                
                candidates.append({
                    "code": code,
                    "ret1": last_ret1,
                    "ret20": last_ret20,
                    "close": last_close,
                    "adx": last_adx,
                    "mfi": last_mfi
                })
        
        # 결과 출력
        if candidates:
            print(f"\n✅ BUY 후보: {len(candidates)}건")
            for c in sorted(candidates, key=lambda x: x["ret1"], reverse=True)[:10]:
                print(f"  - {c['code']}: 1일 {c['ret1']*100:.2f}%, 20일 {c['ret20']*100:.2f}%, "
                      f"ADX {c['adx']:.1f}, MFI {c['mfi']:.1f}, 종가 {c['close']:.0f}")
        else:
            print("\n⚠️ BUY 후보 없음 (필터 조건 미충족)")
            print(f"   - 급등 기준: {jump_pct*100:.1f}%")
            print(f"   - ADX 최소: {adx_min:.1f}")
            print(f"   - MFI 최소: {mfi_min:.1f}")

if __name__ == "__main__":
    run_scanner_nas(pd.Timestamp.today())
