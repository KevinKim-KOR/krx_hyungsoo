#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스캐너 0건 출력 원인 진단 스크립트

실행: python scripts/diagnostics/diagnose_scanner_zero.py
"""

import sys
import pandas as pd
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scanner import load_config_yaml, get_universe_codes, load_prices, regime_ok, build_candidate_table
from db import SessionLocal

def diagnose():
    print("=" * 60)
    print("[DIAGNOSE] Scanner Zero Output Analysis")
    print("=" * 60)
    
    # 1. 설정 로드
    try:
        cfg = load_config_yaml("config.yaml")
        print("[OK] 설정 파일 로드 성공")
    except FileNotFoundError as e:
        print(f"[ERROR] 설정 파일 없음: {e}")
        print("→ config.yaml.example을 config.yaml로 복사하세요")
        return
    
    # 2. 유니버스 크기 확인
    with SessionLocal() as s:
        codes = get_universe_codes(s, cfg)
        print(f"[INFO] 유니버스 크기: {len(codes)}개 종목")
        if len(codes) == 0:
            print("[ERROR] 유니버스가 비어있습니다")
            print("→ python app.py init 실행 후 종목 데이터를 추가하세요")
            return
        print(f"   샘플: {codes[:5]}")
    
    # 3. 가격 데이터 확인
    asof = pd.Timestamp.today().normalize()
    with SessionLocal() as s:
        panel = load_prices(s, codes, asof, lookback_days=300)
        print(f"[INFO] 가격 데이터: {len(panel)} rows")
        if panel.empty:
            print("[ERROR] 가격 데이터가 없습니다")
            print("→ python app.py ingest-eod --date auto 실행하세요")
            return
        
        unique_codes = panel['code'].nunique()
        date_range = f"{panel['date'].min().date()} ~ {panel['date'].max().date()}"
        print(f"   종목 수: {unique_codes}")
        print(f"   기간: {date_range}")
    
    # 4. 레짐 체크
    try:
        regime = regime_ok(asof, cfg)
        print(f"[INFO] 레짐 상태: {'ON (투자 가능)' if regime else 'OFF (현금 전환)'}")
        if not regime:
            print("   → S&P500이 200일선 아래입니다")
            print("   → 레짐 가드를 비활성화하려면:")
            print("      bash scripts/linux/diagnostics/disable_regime_guard.sh")
    except Exception as e:
        print(f"[WARN] 레짐 체크 실패: {e}")
        regime = False
    
    # 5. 후보 필터링 단계별 확인
    with SessionLocal() as s:
        panel = load_prices(s, codes, asof, lookback_days=300)
        cands = build_candidate_table(panel, asof, cfg)
        
        print(f"[INFO] 필터링 단계:")
        print(f"   1) 전체 후보: {len(cands)} 종목")
        
        if not cands.empty:
            trend_ok = cands['trend_ok'].sum()
            jump_ok = cands['jump_ok'].sum()
            strength_ok = cands['strength_ok'].sum()
            liquidity_ok = cands['liquidity_ok'].sum()
            all_ok = cands['all_ok'].sum()
            
            print(f"   2) 추세 조건 통과: {trend_ok} (close > SMA50 & SMA200)")
            print(f"   3) 급등 조건 통과: {jump_ok} (1일 수익률 ≥ 2%)")
            print(f"   4) 강도 조건 통과: {strength_ok} (ADX≥20, MFI 50-80, VolZ≥1)")
            print(f"   5) 유동성 통과: {liquidity_ok}")
            print(f"   6) 최종 통과: {all_ok} 종목")
            
            if all_ok == 0:
                print("[TIP] 권장 조치:")
                if jump_ok == 0:
                    print("   - 급등 임계값을 낮추세요 (2% → 1%)")
                    print("     config.yaml > scanner.thresholds.daily_jump_pct: 1.0")
                if strength_ok < 5:
                    print("   - 강도 조건을 완화하세요")
                    print("     ADX 20 → 15, MFI 범위 확대")
        else:
            print("   [ERROR] 후보 생성 실패 (데이터 부족)")
    
    # 6. 요약
    print("\n" + "=" * 60)
    print("[SUMMARY] 진단 요약")
    print("=" * 60)
    
    issues = []
    if len(codes) == 0:
        issues.append("유니버스 비어있음 → init 실행")
    if panel.empty:
        issues.append("가격 데이터 없음 → ingest-eod 실행")
    if not regime:
        issues.append("레짐 OFF → disable_regime_guard.sh 실행")
    if not cands.empty and cands['all_ok'].sum() == 0:
        issues.append("필터 조건 과다 → config.yaml 완화")
    
    if issues:
        print("[WARN] 발견된 문제:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("[OK] 모든 조건 정상 (신호 생성 가능)")

if __name__ == "__main__":
    diagnose()
