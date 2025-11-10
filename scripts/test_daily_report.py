# -*- coding: utf-8 -*-
"""
scripts/test_daily_report.py
일일 리포트 테스트 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from extensions.automation.daily_report import DailyReport
from datetime import date

def main():
    """일일 리포트 테스트"""
    print("=" * 60)
    print("일일 리포트 테스트")
    print("=" * 60)
    print()
    
    # 일일 리포트 생성 (텔레그램 비활성화)
    reporter = DailyReport(telegram_enabled=False)
    
    # 리포트 생성
    report = reporter.generate_report(target_date=date.today())
    
    # 출력
    print(report)
    print()
    print("=" * 60)
    print("테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
