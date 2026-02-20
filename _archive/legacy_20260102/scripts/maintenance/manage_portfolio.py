#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/maintenance/manage_portfolio.py
포트폴리오(holdings.json) 관리 도구

기능:
1. list: 현재 보유 종목 목록 출력
2. remove: 특정 종목(코드) 삭제
3. clear_sold: 수량(quantity)이 0 이하인 종목 일괄 삭제

사용법:
python manage_portfolio.py list
python manage_portfolio.py remove 005930 000660
python manage_portfolio.py clear_sold
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.portfolio_loader import PortfolioLoader

HOLDINGS_FILE = PROJECT_ROOT / "data" / "portfolio" / "holdings.json"

def load_json():
    if not HOLDINGS_FILE.exists():
        print(f"❌ 파일이 없습니다: {HOLDINGS_FILE}")
        sys.exit(1)
    
    with open(HOLDINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data):
    # 백업 생성
    backup_path = HOLDINGS_FILE.with_suffix(f".json.bak.{datetime.now(KST).strftime('%Y%m%d%H%M%S')}")
    import shutil
    shutil.copy2(HOLDINGS_FILE, backup_path)
    print(f"📦 백업 생성됨: {backup_path.name}")
    
    data['last_updated'] = datetime.now(KST).isoformat()
    
    with open(HOLDINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ holdings.json 업데이트 완료")

def list_holdings(args):
    data = load_json()
    holdings = data.get('holdings', [])
    
    print(f"\n📊 현재 포트폴리오 ({len(holdings)}개 종목)")
    print("-" * 60)
    print(f"{'코드':<8} {'수량':<8} {'평가손익':<15} {'종목명'}")
    print("-" * 60)
    
    for h in holdings:
        code = h.get('code', 'N/A')
        name = h.get('name', 'N/A')
        qty = h.get('quantity', 0)
        ret_pct = h.get('return_pct', 0)
        
        print(f"{code:<8} {qty:<8} {ret_pct:+.2f}%{'':<8} {name}")
    print("-" * 60)

def remove_holdings(args):
    codes_to_remove = args.codes
    data = load_json()
    holdings = data.get('holdings', [])
    
    new_holdings = []
    removed_count = 0
    
    for h in holdings:
        if h.get('code') in codes_to_remove:
            print(f"🗑️ 삭제 대상: {h.get('name')} ({h.get('code')})")
            removed_count += 1
        else:
            new_holdings.append(h)
    
    if removed_count == 0:
        print("⚠️ 삭제할 종목을 찾지 못했습니다.")
        return
    
    data['holdings'] = new_holdings
    save_json(data)
    print(f"총 {removed_count}개 종목이 삭제되었습니다.")

def clear_sold(args):
    data = load_json()
    holdings = data.get('holdings', [])
    
    new_holdings = []
    removed_count = 0
    
    for h in holdings:
        qty = h.get('quantity', 0)
        if qty <= 0:
            print(f"🗑️ 삭제 대상 (수량 0): {h.get('name')} ({h.get('code')})")
            removed_count += 1
        else:
            new_holdings.append(h)
    
    if removed_count == 0:
        print("⚠️ 수량이 0인 종목이 없습니다.")
        return
    
    data['holdings'] = new_holdings
    save_json(data)
    print(f"총 {removed_count}개 종목이 삭제되었습니다.")

def main():
    parser = argparse.ArgumentParser(description="포트폴리오 관리 도구")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # list 명령
    subparsers.add_parser('list', help='보유 종목 목록 출력')
    
    # remove 명령
    remove_parser = subparsers.add_parser('remove', help='특정 종목 삭제')
    remove_parser.add_argument('codes', nargs='+', help='삭제할 종목 코드들')
    
    # clear_sold 명령
    subparsers.add_parser('clear_sold', help='수량 0인 종목 일괄 삭제')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_holdings(args)
    elif args.command == 'remove':
        remove_holdings(args)
    elif args.command == 'clear_sold':
        clear_sold(args)

if __name__ == "__main__":
    main()
