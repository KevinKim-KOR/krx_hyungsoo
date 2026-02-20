#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주간 실시간 vs 백테스트 비교 리포트
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from datetime import datetime, date, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
import logging
from typing import List, Dict

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyComparison:
    """주간 비교 분석"""
    
    def __init__(self, signal_dir: str = None, output_dir: str = None):
        """
        Args:
            signal_dir: 신호 로그 디렉토리
            output_dir: 리포트 출력 디렉토리
        """
        project_root = Path(__file__).parent.parent.parent
        
        if signal_dir is None:
            signal_dir = project_root / "data" / "monitoring" / "signals"
        if output_dir is None:
            output_dir = project_root / "data" / "monitoring" / "reports"
        
        self.signal_dir = Path(signal_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def get_week_dates(self, end_date: date = None) -> List[date]:
        """
        최근 1주일 날짜 리스트
        
        Args:
            end_date: 종료일 (기본: 오늘)
            
        Returns:
            날짜 리스트
        """
        if end_date is None:
            end_date = date.today()
        
        dates = []
        for i in range(7):
            d = end_date - timedelta(days=i)
            dates.append(d)
        
        return sorted(dates)
    
    def load_daily_signals(self, target_date: date) -> Dict:
        """
        특정 날짜의 신호 로드
        
        Args:
            target_date: 대상 날짜
            
        Returns:
            신호 데이터
        """
        signal_file = self.signal_dir / f"signals_{target_date.strftime('%Y%m%d')}.json"
        
        if not signal_file.exists():
            return {'date': target_date.isoformat(), 'signals': []}
        
        try:
            with open(signal_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"신호 로드 실패 [{target_date}]: {e}")
            return {'date': target_date.isoformat(), 'signals': []}
    
    def analyze_week(self) -> Dict:
        """
        주간 분석
        
        Returns:
            분석 결과
        """
        logger.info("=" * 60)
        logger.info("주간 비교 분석")
        logger.info("=" * 60)
        
        week_dates = self.get_week_dates()
        
        analysis = {
            'period': {
                'start': week_dates[0].isoformat(),
                'end': week_dates[-1].isoformat()
            },
            'daily_summary': [],
            'weekly_stats': {
                'total_buy_signals': 0,
                'total_sell_signals': 0,
                'avg_signals_per_day': 0.0,
                'regime_distribution': {}
            }
        }
        
        total_buy = 0
        total_sell = 0
        regime_counts = {}
        
        for target_date in week_dates:
            daily_data = self.load_daily_signals(target_date)
            
            buy_count = sum(1 for s in daily_data.get('signals', []) if s.get('type') == 'buy')
            sell_count = sum(1 for s in daily_data.get('signals', []) if s.get('type') == 'sell')
            
            # 레짐 정보 추출
            regime = None
            for signal in daily_data.get('signals', []):
                if signal.get('regime'):
                    regime = signal['regime'].get('state', 'unknown')
                    break
            
            if regime:
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            daily_summary = {
                'date': target_date.isoformat(),
                'buy_signals': buy_count,
                'sell_signals': sell_count,
                'regime': regime
            }
            
            analysis['daily_summary'].append(daily_summary)
            
            total_buy += buy_count
            total_sell += sell_count
            
            logger.info(f"{target_date}: 매수 {buy_count}, 매도 {sell_count}, 레짐 {regime}")
        
        # 주간 통계
        analysis['weekly_stats']['total_buy_signals'] = total_buy
        analysis['weekly_stats']['total_sell_signals'] = total_sell
        analysis['weekly_stats']['avg_signals_per_day'] = (total_buy + total_sell) / len(week_dates)
        analysis['weekly_stats']['regime_distribution'] = regime_counts
        
        return analysis
    
    def generate_report(self) -> str:
        """
        주간 리포트 생성
        
        Returns:
            리포트 파일 경로
        """
        analysis = self.analyze_week()
        
        # JSON 저장
        timestamp = datetime.now(KST).strftime('%Y%m%d_%H%M%S')
        json_file = self.output_dir / f"weekly_report_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        # 텍스트 리포트 생성
        txt_file = self.output_dir / f"weekly_report_{timestamp}.txt"
        
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("주간 실시간 신호 분석 리포트\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"기간: {analysis['period']['start']} ~ {analysis['period']['end']}\n\n")
            
            f.write("일별 요약:\n")
            f.write("-" * 60 + "\n")
            for daily in analysis['daily_summary']:
                f.write(f"{daily['date']}: ")
                f.write(f"매수 {daily['buy_signals']}, ")
                f.write(f"매도 {daily['sell_signals']}, ")
                f.write(f"레짐 {daily['regime']}\n")
            
            f.write("\n주간 통계:\n")
            f.write("-" * 60 + "\n")
            stats = analysis['weekly_stats']
            f.write(f"총 매수 신호: {stats['total_buy_signals']}\n")
            f.write(f"총 매도 신호: {stats['total_sell_signals']}\n")
            f.write(f"일평균 신호: {stats['avg_signals_per_day']:.1f}\n")
            
            f.write("\n레짐 분포:\n")
            for regime, count in stats['regime_distribution'].items():
                f.write(f"  {regime}: {count}일\n")
        
        logger.info(f"✅ 리포트 생성: {txt_file}")
        
        return str(txt_file)
    
    def print_summary(self):
        """요약 출력"""
        analysis = self.analyze_week()
        
        print("\n" + "=" * 60)
        print("주간 요약")
        print("=" * 60)
        
        stats = analysis['weekly_stats']
        print(f"총 매수 신호: {stats['total_buy_signals']}")
        print(f"총 매도 신호: {stats['total_sell_signals']}")
        print(f"일평균 신호: {stats['avg_signals_per_day']:.1f}")
        
        print("\n레짐 분포:")
        for regime, count in stats['regime_distribution'].items():
            print(f"  {regime}: {count}일")


def main():
    """주간 리포트 생성"""
    comparison = WeeklyComparison()
    
    # 리포트 생성
    report_file = comparison.generate_report()
    
    # 요약 출력
    comparison.print_summary()
    
    logger.info("✅ 주간 비교 완료")


if __name__ == "__main__":
    main()
