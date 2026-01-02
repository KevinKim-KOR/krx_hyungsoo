#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/phase3/compare_backtest_vs_real.py
백테스트 vs 실전 성과 비교
"""
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class BacktestRealComparison:
    """백테스트 vs 실전 비교"""
    
    def __init__(
        self,
        backtest_result_file: str,
        holdings_file: str
    ):
        """
        Args:
            backtest_result_file: 백테스트 결과 JSON 파일
            holdings_file: 보유 종목 JSON 파일
        """
        self.backtest_result_file = backtest_result_file
        self.holdings_file = holdings_file
        
        self.backtest_result = self.load_backtest_result()
        self.holdings = self.load_holdings()
    
    def load_backtest_result(self) -> Dict:
        """백테스트 결과 로드"""
        with open(self.backtest_result_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_holdings(self) -> List[Dict]:
        """보유 종목 로드"""
        with open(self.holdings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['holdings']
    
    def calculate_real_performance(self) -> Dict:
        """
        실전 성과 계산
        
        Returns:
            dict: 실전 성과
        """
        returns = []
        total_cost = 0
        total_value = 0
        
        for holding in self.holdings:
            return_pct = holding['return_pct']
            cost = holding['total_cost']
            value = holding['current_value']
            
            returns.append(return_pct)
            total_cost += cost
            total_value += value
        
        # 포트폴리오 통계
        portfolio_return = ((total_value / total_cost) - 1) * 100 if total_cost > 0 else 0
        portfolio_std = np.std(returns)
        sharpe_ratio = np.mean(returns) / portfolio_std if portfolio_std > 0 else 0
        max_drawdown = min(returns)
        
        return {
            'portfolio_return': portfolio_return,
            'avg_return': np.mean(returns),
            'portfolio_std': portfolio_std,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_cost': total_cost,
            'total_value': total_value,
            'profit_loss': total_value - total_cost
        }
    
    def compare(self) -> Dict:
        """
        백테스트 vs 실전 비교
        
        Returns:
            dict: 비교 결과
        """
        print("=" * 60)
        print("백테스트 vs 실전 성과 비교")
        print("=" * 60)
        print("")
        
        # 백테스트 결과
        backtest = self.backtest_result.get('optimal_result', {})
        
        print("📊 백테스트 성과:")
        print(f"  평균 수익률: {backtest.get('portfolio_return', 0):.2f}%")
        print(f"  표준편차: {backtest.get('portfolio_std', 0):.2f}%")
        print(f"  Sharpe Ratio: {backtest.get('sharpe_ratio', 0):.4f}")
        print(f"  Max Drawdown: {backtest.get('max_drawdown', 0):.2f}%")
        print("")
        
        # 실전 성과
        real = self.calculate_real_performance()
        
        print("💼 실전 성과:")
        print(f"  포트폴리오 수익률: {real['portfolio_return']:.2f}%")
        print(f"  평균 수익률: {real['avg_return']:.2f}%")
        print(f"  표준편차: {real['portfolio_std']:.2f}%")
        print(f"  Sharpe Ratio: {real['sharpe_ratio']:.4f}")
        print(f"  Max Drawdown: {real['max_drawdown']:.2f}%")
        print(f"  총 투자금: {real['total_cost']:,.0f}원")
        print(f"  현재 가치: {real['total_value']:,.0f}원")
        print(f"  손익: {real['profit_loss']:+,.0f}원")
        print("")
        
        # 차이 분석
        return_diff = real['avg_return'] - backtest.get('portfolio_return', 0)
        sharpe_diff = real['sharpe_ratio'] - backtest.get('sharpe_ratio', 0)
        mdd_diff = real['max_drawdown'] - backtest.get('max_drawdown', 0)
        
        print("📈 차이 분석:")
        print(f"  수익률 차이: {return_diff:+.2f}%p")
        print(f"  Sharpe 차이: {sharpe_diff:+.4f}")
        print(f"  MDD 차이: {mdd_diff:+.2f}%p")
        print("")
        
        # 평가
        if abs(return_diff) <= 2.0 and abs(sharpe_diff) <= 0.1:
            print("✅ 백테스트와 실전 성과가 유사합니다!")
        elif return_diff > 2.0:
            print("🎉 실전 성과가 백테스트보다 우수합니다!")
        else:
            print("⚠️ 실전 성과가 백테스트보다 저조합니다.")
        
        return {
            'backtest': backtest,
            'real': real,
            'diff': {
                'return_diff': return_diff,
                'sharpe_diff': sharpe_diff,
                'mdd_diff': mdd_diff
            }
        }
    
    def generate_report(self, comparison: Dict) -> str:
        """
        비교 리포트 생성
        
        Args:
            comparison: 비교 결과
            
        Returns:
            str: 리포트 텍스트
        """
        backtest = comparison['backtest']
        real = comparison['real']
        diff = comparison['diff']
        
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("백테스트 vs 실전 성과 비교 리포트")
        lines.append("=" * 60)
        lines.append(f"날짜: {date.today()}")
        lines.append("")
        
        lines.append("📊 백테스트 성과:")
        lines.append(f"  평균 수익률: {backtest.get('portfolio_return', 0):.2f}%")
        lines.append(f"  표준편차: {backtest.get('portfolio_std', 0):.2f}%")
        lines.append(f"  Sharpe Ratio: {backtest.get('sharpe_ratio', 0):.4f}")
        lines.append(f"  Max Drawdown: {backtest.get('max_drawdown', 0):.2f}%")
        lines.append("")
        
        lines.append("💼 실전 성과:")
        lines.append(f"  포트폴리오 수익률: {real['portfolio_return']:.2f}%")
        lines.append(f"  평균 수익률: {real['avg_return']:.2f}%")
        lines.append(f"  표준편차: {real['portfolio_std']:.2f}%")
        lines.append(f"  Sharpe Ratio: {real['sharpe_ratio']:.4f}")
        lines.append(f"  Max Drawdown: {real['max_drawdown']:.2f}%")
        lines.append(f"  총 투자금: {real['total_cost']:,.0f}원")
        lines.append(f"  현재 가치: {real['total_value']:,.0f}원")
        lines.append(f"  손익: {real['profit_loss']:+,.0f}원")
        lines.append("")
        
        lines.append("📈 차이 분석:")
        lines.append(f"  수익률 차이: {diff['return_diff']:+.2f}%p")
        lines.append(f"  Sharpe 차이: {diff['sharpe_diff']:+.4f}")
        lines.append(f"  MDD 차이: {diff['mdd_diff']:+.2f}%p")
        lines.append("")
        
        # 평가
        if abs(diff['return_diff']) <= 2.0 and abs(diff['sharpe_diff']) <= 0.1:
            lines.append("✅ 평가: 백테스트와 실전 성과가 유사합니다!")
        elif diff['return_diff'] > 2.0:
            lines.append("🎉 평가: 실전 성과가 백테스트보다 우수합니다!")
        else:
            lines.append("⚠️ 평가: 실전 성과가 백테스트보다 저조합니다.")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def run(self):
        """비교 실행"""
        # 비교
        comparison = self.compare()
        
        # 리포트 생성
        report = self.generate_report(comparison)
        print(report)
        
        # 결과 저장
        output_dir = PROJECT_ROOT / 'data' / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f'backtest_vs_real_{date.today()}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✅ 결과 저장: {output_file}")
        
        # 리포트 저장
        report_file = output_dir / f'backtest_vs_real_report_{date.today()}.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 리포트 저장: {report_file}")


def main():
    """메인 실행"""
    # 파일 경로
    backtest_result_file = PROJECT_ROOT / 'data' / 'output' / 'stop_loss_optimization_result.json'
    holdings_file = PROJECT_ROOT / 'data' / 'portfolio' / 'holdings.json'
    
    # 비교 실행
    comparison = BacktestRealComparison(backtest_result_file, holdings_file)
    comparison.run()


if __name__ == '__main__':
    main()
