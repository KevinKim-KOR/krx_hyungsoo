# -*- coding: utf-8 -*-
"""
DB -> holdings.json 동기화 스크립트
DB의 보유종목 데이터를 holdings.json 파일로 내보냅니다.
Cloud/NAS에서 DB를 사용할 수 없을 때 임시 해결책으로 사용합니다.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.db import SessionLocal, Holdings
import pykrx.stock as stock
import pandas as pd

def get_latest_price(code: str) -> float:
    """최신 가격 조회 (최대 7일 전까지)"""
    today = datetime.now()
    for i in range(7):
        check_date = (today - pd.Timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv_by_date(check_date, check_date, code)
            if not df.empty:
                return float(df.iloc[0]['종가'])
        except:
            continue
    return 0

def sync():
    print("=" * 60)
    print("DB -> holdings.json 동기화")
    print("=" * 60)
    
    session = SessionLocal()
    
    # DB에서 보유종목 조회 (quantity > 0)
    holdings = session.query(Holdings).filter(Holdings.quantity > 0).all()
    print(f"DB에서 {len(holdings)}개 종목 조회")
    
    # 현재가 업데이트 및 JSON 구조 생성
    holdings_list = []
    total_cost = 0
    total_value = 0
    
    for h in holdings:
        # 현재가 조회
        current_price = h.current_price if h.current_price and h.current_price > 0 else get_latest_price(h.code)
        
        # DB에 현재가 업데이트
        if current_price > 0 and h.current_price != current_price:
            h.current_price = current_price
        
        # 계산
        cost = h.avg_price * h.quantity
        value = current_price * h.quantity if current_price > 0 else cost
        return_amount = value - cost
        return_pct = (return_amount / cost * 100) if cost > 0 else 0
        
        total_cost += cost
        total_value += value
        
        item = {
            "code": h.code,
            "name": h.name,
            "quantity": h.quantity,
            "avg_price": h.avg_price,
            "current_price": current_price if current_price > 0 else h.avg_price,
            "total_cost": cost,
            "current_value": value,
            "return_amount": return_amount,
            "return_pct": return_pct,
            "broker": ""
        }
        holdings_list.append(item)
        print(f"  {h.code} {h.name}: {h.quantity}주 @ {h.avg_price:,.0f} -> {current_price:,.0f} ({return_pct:+.2f}%)")
    
    # DB 커밋 (current_price 업데이트)
    try:
        session.commit()
        print("\nDB current_price 업데이트 완료")
    except Exception as e:
        session.rollback()
        print(f"\nDB 업데이트 실패: {e}")
    finally:
        session.close()
    
    # JSON 파일 저장
    output = {
        "last_updated": datetime.now().isoformat(),
        "holdings": holdings_list
    }
    
    json_path = PROJECT_ROOT / "data" / "portfolio" / "holdings.json"
    
    # 백업
    if json_path.exists():
        backup_path = json_path.with_suffix('.json.bak')
        json_path.rename(backup_path)
        print(f"\n기존 파일 백업: {backup_path}")
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ holdings.json 저장 완료: {json_path}")
    print(f"   종목 수: {len(holdings_list)}개")
    print(f"   총 매입액: {total_cost:,.0f}원")
    print(f"   총 평가액: {total_value:,.0f}원")
    print(f"   평가손익: {total_value - total_cost:+,.0f}원 ({(total_value - total_cost) / total_cost * 100 if total_cost > 0 else 0:+.2f}%)")

if __name__ == "__main__":
    sync()
