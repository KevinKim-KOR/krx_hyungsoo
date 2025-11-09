#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실시간 신호 기록 시스템
텔레그램으로 받은 신호를 자동 기록하고 백테스트 예상과 비교
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from datetime import datetime, date
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalLogger:
    """실시간 신호 기록 및 분석"""
    
    def __init__(self, log_dir: str = None):
        """
        Args:
            log_dir: 로그 저장 디렉토리
        """
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "data" / "monitoring" / "signals"
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.today = date.today()
        self.log_file = self.log_dir / f"signals_{self.today.strftime('%Y%m%d')}.json"
    
    def log_signal(self, signal_type: str, signals: list, regime_info: dict = None):
        """
        신호 기록
        
        Args:
            signal_type: 'buy' or 'sell'
            signals: 신호 리스트
            regime_info: 레짐 정보
        """
        try:
            # 기존 로그 로드
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = {
                    'date': self.today.isoformat(),
                    'signals': []
                }
            
            # 새 신호 추가
            signal_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': signal_type,
                'count': len(signals),
                'signals': signals,
                'regime': regime_info
            }
            
            log_data['signals'].append(signal_entry)
            
            # 저장
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"✅ {signal_type.upper()} 신호 {len(signals)}개 기록 완료")
            
        except Exception as e:
            logger.error(f"❌ 신호 기록 실패: {e}")
    
    def get_daily_summary(self) -> dict:
        """일일 신호 요약"""
        try:
            if not self.log_file.exists():
                return {'buy': 0, 'sell': 0, 'signals': []}
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            buy_count = sum(1 for s in log_data['signals'] if s['type'] == 'buy')
            sell_count = sum(1 for s in log_data['signals'] if s['type'] == 'sell')
            
            return {
                'date': log_data['date'],
                'buy': buy_count,
                'sell': sell_count,
                'signals': log_data['signals']
            }
            
        except Exception as e:
            logger.error(f"❌ 요약 생성 실패: {e}")
            return {'buy': 0, 'sell': 0, 'signals': []}
    
    def compare_with_backtest(self, backtest_signals: dict) -> dict:
        """
        백테스트 예상 신호와 비교
        
        Args:
            backtest_signals: 백테스트 예상 신호
            
        Returns:
            비교 결과
        """
        try:
            real_summary = self.get_daily_summary()
            
            comparison = {
                'date': self.today.isoformat(),
                'real_signals': real_summary,
                'backtest_signals': backtest_signals,
                'match_rate': 0.0,
                'differences': []
            }
            
            # 매치율 계산 (간단 버전)
            real_codes = set()
            for signal in real_summary['signals']:
                for s in signal['signals']:
                    real_codes.add(s.get('code', ''))
            
            backtest_codes = set(backtest_signals.get('buy_codes', []))
            
            if real_codes and backtest_codes:
                matched = real_codes & backtest_codes
                comparison['match_rate'] = len(matched) / max(len(real_codes), len(backtest_codes))
                comparison['matched_codes'] = list(matched)
                comparison['real_only'] = list(real_codes - backtest_codes)
                comparison['backtest_only'] = list(backtest_codes - real_codes)
            
            return comparison
            
        except Exception as e:
            logger.error(f"❌ 비교 실패: {e}")
            return {}


def main():
    """테스트 실행"""
    logger.info("=" * 60)
    logger.info("신호 로거 테스트")
    logger.info("=" * 60)
    
    # 로거 초기화
    signal_logger = SignalLogger()
    
    # 테스트 신호
    test_signals = [
        {'code': '069500', 'name': 'KODEX 200', 'maps_score': 85.23},
        {'code': '143850', 'name': 'TIGER 미국S&P500', 'maps_score': 82.15}
    ]
    
    test_regime = {
        'state': 'bull',
        'confidence': 95.0,
        'position_ratio': 120
    }
    
    # 신호 기록
    signal_logger.log_signal('buy', test_signals, test_regime)
    
    # 요약 출력
    summary = signal_logger.get_daily_summary()
    print(f"\n일일 요약: {json.dumps(summary, ensure_ascii=False, indent=2)}")
    
    logger.info("✅ 테스트 완료")


if __name__ == "__main__":
    main()
