#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/phase3/optimize_stop_loss.py
Optuna를 사용한 손절 파라미터 최적화
"""
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import optuna
from optuna.visualization import plot_optimization_history, plot_param_importances

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pykrx import stock


class StopLossOptimizer:
    """손절 파라미터 최적화"""
    
    def __init__(
        self, 
        holdings_file: str,
        entry_dates: Dict[str, str],
        n_trials: int = 100
    ):
        """
        Args:
            holdings_file: 보유 종목 JSON 파일 경로
            entry_dates: 매입일 정보 (code: 'YYYY-MM-DD')
            n_trials: Optuna 시행 횟수
        """
        self.holdings_file = holdings_file
        self.entry_dates = entry_dates
        self.n_trials = n_trials
        self.holdings = self.load_holdings()
        
    def load_holdings(self) -> List[Dict]:
        """보유 종목 로드"""
        with open(self.holdings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['holdings']
    
    def get_price_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """종목 가격 히스토리 조회"""
        try:
            # 6자리 코드만 pykrx 지원
            if len(code) != 6:
                return pd.DataFrame()
            
            df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
            
            if df.empty:
                return pd.DataFrame()
            
            return df
            
        except Exception as e:
            return pd.DataFrame()
    
    def simulate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: float,
        entry_date: str,
        stop_loss_pct: float
    ) -> Tuple[float, str, float]:
        """
        손절 시뮬레이션
        
        Args:
            df: 가격 데이터
            entry_price: 매입가
            entry_date: 매입일
            stop_loss_pct: 손절 비율 (%)
            
        Returns:
            tuple: (최종 수익률, 손절 날짜, 손절가)
        """
        # 매입일 이후 데이터만 사용
        try:
            entry_datetime = pd.to_datetime(entry_date)
            df = df[df.index >= entry_datetime]
            if df.empty:
                return 0.0, None, 0.0
        except:
            return 0.0, None, 0.0
        
        # 손절 임계값
        threshold = entry_price * (1 - stop_loss_pct / 100)
        
        # 손절 시점 찾기
        stop_mask = df['종가'] <= threshold
        
        if stop_mask.any():
            # 손절 발동
            stop_date = df[stop_mask].index[0]
            stop_price = df.loc[stop_date, '종가']
            final_return = ((stop_price / entry_price) - 1) * 100
            return final_return, stop_date.strftime('%Y-%m-%d'), stop_price
        else:
            # 손절 없이 보유
            current_price = df.iloc[-1]['종가']
            final_return = ((current_price / entry_price) - 1) * 100
            return final_return, None, current_price
    
    def evaluate_portfolio(self, stop_loss_pct: float) -> Dict:
        """
        포트폴리오 전체 평가
        
        Args:
            stop_loss_pct: 손절 비율 (%)
            
        Returns:
            dict: 평가 결과
        """
        results = []
        
        for holding in self.holdings:
            code = holding['code']
            name = holding['name']
            avg_price = holding['avg_price']
            quantity = holding['quantity']
            current_return = holding['return_pct']
            
            # 수익 종목은 스킵
            if current_return >= 0:
                results.append({
                    'code': code,
                    'name': name,
                    'return': current_return,
                    'stop_loss': False
                })
                continue
            
            # 매입일 확인
            entry_date = self.entry_dates.get(code)
            if not entry_date:
                # 매입일 정보 없으면 현재 수익률 사용
                results.append({
                    'code': code,
                    'name': name,
                    'return': current_return,
                    'stop_loss': False
                })
                continue
            
            # 가격 히스토리 조회
            end_date = datetime.now(KST).strftime('%Y%m%d')
            start_date = pd.to_datetime(entry_date).strftime('%Y%m%d')
            
            df = self.get_price_history(code, start_date, end_date)
            
            if df.empty:
                results.append({
                    'code': code,
                    'name': name,
                    'return': current_return,
                    'stop_loss': False
                })
                continue
            
            # 손절 시뮬레이션
            final_return, stop_date, stop_price = self.simulate_stop_loss(
                df, avg_price, entry_date, stop_loss_pct
            )
            
            results.append({
                'code': code,
                'name': name,
                'return': final_return,
                'stop_loss': stop_date is not None,
                'stop_date': stop_date,
                'stop_price': stop_price
            })
        
        # 포트폴리오 통계 계산
        returns = [r['return'] for r in results]
        
        portfolio_return = np.mean(returns)
        portfolio_std = np.std(returns)
        sharpe_ratio = portfolio_return / portfolio_std if portfolio_std > 0 else 0
        max_drawdown = min(returns)
        
        return {
            'portfolio_return': portfolio_return,
            'portfolio_std': portfolio_std,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'stop_loss_count': sum(1 for r in results if r['stop_loss']),
            'results': results
        }
    
    def objective(self, trial: optuna.Trial) -> float:
        """
        Optuna 목적 함수
        
        Args:
            trial: Optuna trial
            
        Returns:
            float: 최적화 목표 (Sharpe Ratio)
        """
        # 손절 비율 샘플링 (5% ~ 30%)
        stop_loss_pct = trial.suggest_int('stop_loss_pct', 5, 30)
        
        # 포트폴리오 평가
        result = self.evaluate_portfolio(stop_loss_pct)
        
        # Sharpe Ratio 최대화
        return result['sharpe_ratio']
    
    def optimize(self) -> optuna.Study:
        """
        최적화 실행
        
        Returns:
            optuna.Study: 최적화 결과
        """
        print("=" * 60)
        print("손절 파라미터 최적화 시작")
        print("=" * 60)
        print(f"시행 횟수: {self.n_trials}")
        print(f"최적화 목표: Sharpe Ratio 최대화")
        print("")
        
        # Optuna study 생성
        study = optuna.create_study(
            direction='maximize',
            study_name='stop_loss_optimization'
        )
        
        # 최적화 실행
        study.optimize(self.objective, n_trials=self.n_trials, show_progress_bar=True)
        
        return study
    
    def analyze_results(self, study: optuna.Study):
        """
        최적화 결과 분석
        
        Args:
            study: Optuna study
        """
        print("\n" + "=" * 60)
        print("최적화 결과")
        print("=" * 60)
        
        # 최적 파라미터
        best_params = study.best_params
        best_value = study.best_value
        
        print(f"\n최적 손절 비율: {best_params['stop_loss_pct']}%")
        print(f"최적 Sharpe Ratio: {best_value:.4f}")
        
        # 최적 파라미터로 포트폴리오 평가
        result = self.evaluate_portfolio(best_params['stop_loss_pct'])
        
        print(f"\n포트폴리오 성과:")
        print(f"  평균 수익률: {result['portfolio_return']:.2f}%")
        print(f"  표준편차: {result['portfolio_std']:.2f}%")
        print(f"  Sharpe Ratio: {result['sharpe_ratio']:.4f}")
        print(f"  Max Drawdown: {result['max_drawdown']:.2f}%")
        print(f"  손절 횟수: {result['stop_loss_count']}개")
        
        # Jason 기준과 비교
        print(f"\n" + "=" * 60)
        print("Jason 기준 (-7%) 비교")
        print("=" * 60)
        
        jason_result = self.evaluate_portfolio(7.0)
        
        print(f"\nJason 기준 성과:")
        print(f"  평균 수익률: {jason_result['portfolio_return']:.2f}%")
        print(f"  표준편차: {jason_result['portfolio_std']:.2f}%")
        print(f"  Sharpe Ratio: {jason_result['sharpe_ratio']:.4f}")
        print(f"  Max Drawdown: {jason_result['max_drawdown']:.2f}%")
        print(f"  손절 횟수: {jason_result['stop_loss_count']}개")
        
        print(f"\n개선 효과:")
        print(f"  수익률: {result['portfolio_return'] - jason_result['portfolio_return']:+.2f}%p")
        print(f"  Sharpe: {result['sharpe_ratio'] - jason_result['sharpe_ratio']:+.4f}")
        print(f"  MDD: {result['max_drawdown'] - jason_result['max_drawdown']:+.2f}%p")
        
        # 파라미터 중요도 분석
        print(f"\n" + "=" * 60)
        print("파라미터 분석")
        print("=" * 60)
        
        # 상위 10개 시행 결과
        trials_df = study.trials_dataframe()
        top_trials = trials_df.nlargest(10, 'value')
        
        print(f"\n상위 10개 시행:")
        for i, row in enumerate(top_trials.iterrows(), 1):
            trial = row[1]
            print(f"  {i}. 손절 {trial['params_stop_loss_pct']}% → Sharpe {trial['value']:.4f}")
        
        return result, jason_result


def main():
    """메인 실행"""
    # 보유 종목 파일 경로
    holdings_file = PROJECT_ROOT / 'data' / 'portfolio' / 'holdings.json'
    
    # 매입일 정보
    entry_dates = {
        '001510': '2020-07-01',  # SK증권
        '221840': '2020-10-01',  # 하이즈항공
        '323410': '2020-07-01',  # 카카오뱅크
    }
    
    # 최적화 실행
    optimizer = StopLossOptimizer(holdings_file, entry_dates, n_trials=50)
    study = optimizer.optimize()
    
    # 결과 분석
    result, jason_result = optimizer.analyze_results(study)
    
    # 결과 저장
    output_dir = PROJECT_ROOT / 'data' / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 최적화 결과 저장
    optimization_result = {
        'best_params': study.best_params,
        'best_value': study.best_value,
        'optimal_result': {
            'portfolio_return': result['portfolio_return'],
            'portfolio_std': result['portfolio_std'],
            'sharpe_ratio': result['sharpe_ratio'],
            'max_drawdown': result['max_drawdown'],
            'stop_loss_count': result['stop_loss_count']
        },
        'jason_result': {
            'portfolio_return': jason_result['portfolio_return'],
            'portfolio_std': jason_result['portfolio_std'],
            'sharpe_ratio': jason_result['sharpe_ratio'],
            'max_drawdown': jason_result['max_drawdown'],
            'stop_loss_count': jason_result['stop_loss_count']
        },
        'improvement': {
            'return_diff': result['portfolio_return'] - jason_result['portfolio_return'],
            'sharpe_diff': result['sharpe_ratio'] - jason_result['sharpe_ratio'],
            'mdd_diff': result['max_drawdown'] - jason_result['max_drawdown']
        }
    }
    
    output_file = output_dir / 'stop_loss_optimization_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(optimization_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 결과 저장: {output_file}")


if __name__ == '__main__':
    main()
