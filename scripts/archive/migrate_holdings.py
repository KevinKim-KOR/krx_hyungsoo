#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
기존 holdings.json 데이터를 DB로 마이그레이션
"""
import json
import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.db import SessionLocal, Holdings, init_db


def migrate_holdings():
    """holdings.json → DB 마이그레이션"""
    
    # DB 초기화
    print("DB 초기화...")
    init_db()
    
    # JSON 파일 읽기
    json_path = project_root / "data" / "portfolio" / "holdings.json"
    if not json_path.exists():
        print(f"❌ 파일 없음: {json_path}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    holdings_data = data.get('holdings', [])
    print(f"\n📊 총 {len(holdings_data)}개 종목 발견")
    
    # DB 세션
    session = SessionLocal()
    
    try:
        # 기존 데이터 삭제 (재마이그레이션 대비)
        session.query(Holdings).delete()
        session.commit()
        print("✅ 기존 데이터 삭제 완료")
        
        # 새 데이터 삽입
        added = 0
        for item in holdings_data:
            holding = Holdings(
                code=item['code'],
                name=item['name'],
                quantity=int(item['quantity']),
                avg_price=float(item['avg_price'])
            )
            session.add(holding)
            added += 1
            print(f"  ✓ {item['name']} ({item['code']}): {item['quantity']}주 @ {item['avg_price']:,}원")
        
        session.commit()
        print(f"\n✅ {added}개 종목 마이그레이션 완료!")
        
        # 확인
        total = session.query(Holdings).count()
        print(f"📊 DB 총 종목 수: {total}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 오류 발생: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate_holdings()
