#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/phase4/compare_stop_loss_strategies.py
손절 전략 백테스트 비교

4가지 손절 전략을 백테스트하여 최적 전략 선택:
1. 고정 손절 (-7%)
2. 레짐별 손절 (-3% ~ -7%)
3. 동적 손절 (-5% ~ -10%)
4. 하이브리드 손절 (레짐 + 변동성)
"""
import sys
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import numpy as np

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.portfolio_loader import PortfolioLoader
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


class StopLossStrategyComparator:
    """손절 전략 비교 클래스"""
    
    # 4가지 손절 전략
    STRATEGIES = {
        'fixed': {
            'name': '고정 손절',
            'description': '-7% 고정',
            'threshold': -7.0
        },
        'regime': {
            'name': '레짐별 손절',
            'description': '상승 -7%, 중립 -5%, 하락 -3%',
            'thresholds': {
                'bull': -7.0,
                'neutral': -5.0,
                'bear': -3.0
            }
        },
        'dynamic': {
            'name': '동적 손절',
            'description': '저변동성 -5%, 중변동성 -7%, 고변동성 -10%',
            'thresholds': {
                'low': -5.0,
                'medium': -7.0,
                'high': -10.0
            }
        },
        'hybrid': {
            'name': '하이브리드 손절',
            'description': '레짐 + 변동성 조합 (9가지)',
            'matrix': {
                'bull': {'low': -5.0, 'medium': -7.0, 'high': -10.0},
                'neutral': {'low': -4.0, 'medium': -5.0, 'high': -7.0},
                'bear': {'low': -3.0, 'medium': -3.0, 'high': -5.0}
            }
        }
    }
    
    def __init__(self):
        """초기화"""
        self.loader = PortfolioLoader()
        
        # 출력 디렉토리
        self.output_dir = PROJECT_ROOT / "data" / "output" / "backtest"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("손절 전략 비교 초기화")
        logger.info(f"비교 전략: {len(self.STRATEGIES)}개")
    
    def simulate_strategy(
        self,
        strategy_name: str,
        holdings: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        전략 시뮬레이션
        
        Args:
            strategy_name: 전략 이름
            holdings: 보유 종목 데이터
        
        Returns:
            시뮬레이션 결과
        """
        try:
            strategy = self.STRATEGIES[strategy_name]
            
            # 손절 대상 판별
            stop_loss_targets = []
            safe_holdings = []
            
            for _, holding in holdings.iterrows():
                code = holding.get('code')
                name = holding.get('name', f'종목_{code}')
                return_pct = holding.get('return_pct', 0.0)
                current_value = holding.get('current_value', 0)
                total_cost = holding.get('total_cost', 0)
                
                # 전략별 손절 기준 결정
                if strategy_name == 'fixed':
                    threshold = strategy['threshold']
                
                elif strategy_name == 'regime':
                    # 단순화: 중립장 가정
                    regime = 'neutral'
                    threshold = strategy['thresholds'][regime]
                
                elif strategy_name == 'dynamic':
                    # 단순화: ATR 기반 변동성 분류
                    # ETF는 저변동성, 개별주는 중변동성 가정
                    if code.startswith('1') or code.startswith('2'):
                        volatility = 'low'
                    else:
                        volatility = 'medium'
                    threshold = strategy['thresholds'][volatility]
                
                elif strategy_name == 'hybrid':
                    # 단순화: 중립장 + 변동성 조합
                    regime = 'neutral'
                    if code.startswith('1') or code.startswith('2'):
                        volatility = 'low'
                    else:
                        volatility = 'medium'
                    threshold = strategy['matrix'][regime][volatility]
                
                else:
                    threshold = -7.0
                
                # 손절 판별
                if return_pct <= threshold:
                    stop_loss_targets.append({
                        'code': code,
                        'name': name,
                        'return_pct': return_pct,
                        'threshold': threshold,
                        'current_value': current_value,
                        'total_cost': total_cost,
                        'loss_amount': current_value - total_cost
                    })
                else:
                    safe_holdings.append({
                        'code': code,
                        'name': name,
                        'return_pct': return_pct,
                        'threshold': threshold
                    })
            
            # 성과 계산
            total_value = holdings['current_value'].sum()
            total_cost = holdings['total_cost'].sum()
            total_return_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0
            
            # 손절 후 예상 성과
            if stop_loss_targets:
                stop_loss_value = sum(t['current_value'] for t in stop_loss_targets)
                stop_loss_cost = sum(t['total_cost'] for t in stop_loss_targets)
                remaining_value = total_value - stop_loss_value
                remaining_cost = total_cost - stop_loss_cost
                
                if remaining_cost > 0:
                    after_stop_loss_return_pct = (remaining_value / remaining_cost - 1) * 100
                else:
                    after_stop_loss_return_pct = 0
            else:
                after_stop_loss_return_pct = total_return_pct
            
            result = {
                'strategy_name': strategy_name,
                'strategy_info': strategy,
                'total_holdings': len(holdings),
                'stop_loss_count': len(stop_loss_targets),
                'safe_count': len(safe_holdings),
                'stop_loss_targets': stop_loss_targets,
                'safe_holdings': safe_holdings,
                'total_value': total_value,
                'total_cost': total_cost,
                'total_return_pct': total_return_pct,
                'after_stop_loss_return_pct': after_stop_loss_return_pct,
                'improvement': after_stop_loss_return_pct - total_return_pct
            }
            
            logger.info(
                f"{strategy['name']}: "
                f"손절 {len(stop_loss_targets)}개, "
                f"안전 {len(safe_holdings)}개, "
                f"개선: {result['improvement']:+.2f}%p"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"전략 시뮬레이션 실패 ({strategy_name}): {e}", exc_info=True)
            return {}
    
    def compare_strategies(self) -> Dict[str, Any]:
        """
        4가지 전략 비교
        
        Returns:
            비교 결과
        """
        try:
            # 보유 종목 로드
            holdings = self.loader.get_holdings_detail()
            
            if holdings.empty:
                logger.warning("보유 종목 데이터 없음")
                return {}
            
            logger.info(f"보유 종목: {len(holdings)}개")
            
            # 각 전략 시뮬레이션
            results = {}
            for strategy_name in self.STRATEGIES.keys():
                result = self.simulate_strategy(strategy_name, holdings)
                if result:
                    results[strategy_name] = result
            
            # 최적 전략 선택
            best_strategy = max(
                results.items(),
                key=lambda x: x[1]['after_stop_loss_return_pct']
            )
            
            comparison = {
                'timestamp': datetime.now().isoformat(),
                'total_holdings': len(holdings),
                'strategies': results,
                'best_strategy': {
                    'name': best_strategy[0],
                    'info': best_strategy[1]
                },
                'summary': self._generate_summary(results)
            }
            
            logger.info(f"최적 전략: {best_strategy[1]['strategy_info']['name']}")
            
            return comparison
        
        except Exception as e:
            logger.error(f"전략 비교 실패: {e}", exc_info=True)
            return {}
    
    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """비교 요약 생성"""
        summary = "=" * 60 + "\n"
        summary += "손절 전략 비교 요약\n"
        summary += "=" * 60 + "\n\n"
        
        for strategy_name, result in results.items():
            strategy_info = result['strategy_info']
            summary += f"[{strategy_info['name']}]\n"
            summary += f"  설명: {strategy_info['description']}\n"
            summary += f"  손절 대상: {result['stop_loss_count']}개\n"
            summary += f"  현재 수익률: {result['total_return_pct']:.2f}%\n"
            summary += f"  손절 후 수익률: {result['after_stop_loss_return_pct']:.2f}%\n"
            summary += f"  개선: {result['improvement']:+.2f}%p\n\n"
        
        return summary
    
    def save_results(self, comparison: Dict[str, Any]):
        """결과 저장"""
        try:
            # JSON 저장
            json_file = self.output_dir / "stop_loss_strategy_comparison.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"JSON 결과 저장: {json_file}")
            
            # TXT 요약 저장
            txt_file = self.output_dir / "stop_loss_strategy_comparison.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(comparison['summary'])
            
            logger.info(f"TXT 요약 저장: {txt_file}")
        
        except Exception as e:
            logger.error(f"결과 저장 실패: {e}", exc_info=True)
    
    def print_comparison(self, comparison: Dict[str, Any]):
        """비교 결과 출력"""
        print("\n" + "=" * 60)
        print("손절 전략 비교 결과")
        print("=" * 60 + "\n")
        
        results = comparison['strategies']
        
        # 전략별 결과
        for strategy_name, result in results.items():
            strategy_info = result['strategy_info']
            print(f"[{strategy_info['name']}]")
            print(f"  설명: {strategy_info['description']}")
            print(f"  손절 대상: {result['stop_loss_count']}개")
            print(f"  안전 종목: {result['safe_count']}개")
            print(f"  현재 수익률: {result['total_return_pct']:.2f}%")
            print(f"  손절 후 수익률: {result['after_stop_loss_return_pct']:.2f}%")
            print(f"  개선: {result['improvement']:+.2f}%p")
            print()
        
        # 최적 전략
        best = comparison['best_strategy']
        print("=" * 60)
        print(f"✅ 최적 전략: {best['info']['strategy_info']['name']}")
        print(f"   손절 후 수익률: {best['info']['after_stop_loss_return_pct']:.2f}%")
        print(f"   개선: {best['info']['improvement']:+.2f}%p")
        print("=" * 60 + "\n")
    
    def run(self) -> int:
        """
        비교 실행
        
        Returns:
            0: 성공, 1: 실패
        """
        logger.info("=" * 60)
        logger.info("손절 전략 비교 시작")
        logger.info("=" * 60)
        
        try:
            # 1. 전략 비교
            comparison = self.compare_strategies()
            
            if not comparison:
                logger.error("전략 비교 실패")
                return 1
            
            # 2. 결과 출력
            self.print_comparison(comparison)
            
            # 3. 결과 저장
            self.save_results(comparison)
            
            # 4. 완료
            logger.info("=" * 60)
            logger.info("손절 전략 비교 완료")
            logger.info("=" * 60)
            
            return 0
        
        except Exception as e:
            logger.error(f"비교 실행 실패: {e}", exc_info=True)
            return 1


def main():
    """메인 실행 함수"""
    comparator = StopLossStrategyComparator()
    return comparator.run()


if __name__ == "__main__":
    sys.exit(main())
