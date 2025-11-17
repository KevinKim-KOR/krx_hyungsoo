#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pc/analysis/lookback_analysis.py
룩백 분석 (Walk-Forward Analysis)

과거 시점 기준으로 "그때 전략을 썼다면?" 시뮬레이션
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
import json
from tqdm import tqdm

# 프로젝트 모듈
from core.data_loader import get_ohlcv
from pc.ml.feature_engineering import FeatureEngineer
from pc.ml.train_xgboost import ETFRankingModel
from pc.optimization.portfolio_optimizer import PortfolioOptimizer

logger = logging.getLogger(__name__)


class LookbackAnalyzer:
    """룩백 분석 클래스"""
    
    def __init__(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        lookback_window: int = 252,  # 1년 (252 거래일)
        rebalance_freq: int = 21,    # 1개월 (21 거래일)
        test_window: int = 21        # 테스트 기간 (21 거래일)
    ):
        """
        Args:
            codes: 종목 코드 리스트
            start_date: 시작일
            end_date: 종료일
            lookback_window: 학습 윈도우 (거래일 수)
            rebalance_freq: 리밸런싱 주기 (거래일 수)
            test_window: 테스트 윈도우 (거래일 수)
        """
        self.codes = codes
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.lookback_window = lookback_window
        self.rebalance_freq = rebalance_freq
        self.test_window = test_window
        
        self.prices = None
        self.results = []
        
        logger.info(f"LookbackAnalyzer 초기화: {len(codes)}개 종목")
        logger.info(f"기간: {start_date} ~ {end_date}")
        logger.info(f"학습 윈도우: {lookback_window}일, 리밸런싱: {rebalance_freq}일")
    
    def load_data(self) -> pd.DataFrame:
        """
        가격 데이터 로드
        
        Returns:
            가격 데이터프레임
        """
        logger.info("=" * 60)
        logger.info("가격 데이터 로드 시작")
        logger.info("=" * 60)
        
        price_data = {}
        
        for code in self.codes:
            logger.info(f"로드 중: {code}")
            
            # KRX 종목은 .KS 접미사 추가
            symbol = f"{code}.KS" if len(code) == 6 else code
            df = get_ohlcv(symbol, start=self.start_date, end=self.end_date)
            
            if df.empty:
                logger.warning(f"데이터 없음: {code}")
                continue
            
            # 컬럼명 정규화
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = df.columns.str.lower()
            
            # AdjClose 또는 Close 사용
            if 'adjclose' in df.columns:
                price_data[code] = df['adjclose']
            elif 'close' in df.columns:
                price_data[code] = df['close']
            else:
                logger.warning(f"가격 컬럼 없음: {code}")
                continue
        
        # 데이터프레임 생성
        self.prices = pd.DataFrame(price_data)
        self.prices = self.prices.dropna()
        
        logger.info(f"✅ 가격 데이터 로드 완료: {len(self.prices)}행, {len(self.prices.columns)}개 종목")
        logger.info("=" * 60)
        
        return self.prices
    
    def run_walkforward_analysis(
        self,
        method: str = "portfolio_optimization"
    ) -> List[Dict]:
        """
        워크포워드 분석 실행
        
        Args:
            method: 분석 방법
                - portfolio_optimization: 포트폴리오 최적화
                - ml_ranking: ML 기반 랭킹
        
        Returns:
            결과 리스트
        """
        logger.info("=" * 60)
        logger.info(f"워크포워드 분석 시작 ({method})")
        logger.info("=" * 60)
        
        # 리밸런싱 날짜 생성
        rebalance_dates = self._generate_rebalance_dates()
        
        logger.info(f"리밸런싱 횟수: {len(rebalance_dates)}")
        
        # 각 리밸런싱 시점마다 분석
        for i, rebal_date in enumerate(tqdm(rebalance_dates, desc="워크포워드 분석")):
            logger.info(f"\n[{i+1}/{len(rebalance_dates)}] 리밸런싱 날짜: {rebal_date.date()}")
            
            # 학습 기간
            train_start = rebal_date - pd.Timedelta(days=self.lookback_window * 2)  # 여유 있게
            train_end = rebal_date
            
            # 테스트 기간
            test_start = rebal_date
            test_end = rebal_date + pd.Timedelta(days=self.test_window * 2)  # 여유 있게
            
            # 데이터 필터링
            train_prices = self.prices.loc[train_start:train_end]
            test_prices = self.prices.loc[test_start:test_end]
            
            if len(train_prices) < self.lookback_window * 0.8:
                logger.warning(f"학습 데이터 부족: {len(train_prices)}행")
                continue
            
            if len(test_prices) < self.test_window * 0.5:
                logger.warning(f"테스트 데이터 부족: {len(test_prices)}행")
                continue
            
            # 방법별 분석
            if method == "portfolio_optimization":
                result = self._analyze_portfolio_optimization(
                    train_prices, test_prices, rebal_date
                )
            elif method == "ml_ranking":
                result = self._analyze_ml_ranking(
                    train_prices, test_prices, rebal_date
                )
            else:
                raise ValueError(f"Unknown method: {method}")
            
            if result:
                self.results.append(result)
        
        logger.info("=" * 60)
        logger.info(f"✅ 워크포워드 분석 완료: {len(self.results)}개 결과")
        logger.info("=" * 60)
        
        return self.results
    
    def _generate_rebalance_dates(self) -> List[pd.Timestamp]:
        """
        리밸런싱 날짜 생성
        
        Returns:
            리밸런싱 날짜 리스트
        """
        dates = []
        current = self.start_date + pd.Timedelta(days=self.lookback_window * 2)
        
        while current < self.end_date:
            # 실제 거래일 찾기
            valid_dates = self.prices.index[self.prices.index >= current]
            if len(valid_dates) > 0:
                dates.append(valid_dates[0])
                current = valid_dates[0] + pd.Timedelta(days=self.rebalance_freq * 2)
            else:
                break
        
        return dates
    
    def _analyze_portfolio_optimization(
        self,
        train_prices: pd.DataFrame,
        test_prices: pd.DataFrame,
        rebal_date: pd.Timestamp
    ) -> Optional[Dict]:
        """
        포트폴리오 최적화 분석
        
        Args:
            train_prices: 학습 가격 데이터
            test_prices: 테스트 가격 데이터
            rebal_date: 리밸런싱 날짜
        
        Returns:
            분석 결과
        """
        try:
            # 기대 수익률 및 공분산 계산
            returns = train_prices.pct_change().dropna()
            mu = returns.mean() * 252  # 연율화
            S = returns.cov() * 252    # 연율화
            
            # Sharpe Ratio 최대화 (간단한 버전)
            from pypfopt import EfficientFrontier
            ef = EfficientFrontier(mu, S)
            weights = ef.max_sharpe(risk_free_rate=0.03)
            cleaned_weights = ef.clean_weights()
            
            # 테스트 기간 성과
            test_returns = test_prices.pct_change().dropna()
            portfolio_returns = (test_returns * pd.Series(cleaned_weights)).sum(axis=1)
            
            cumulative_return = (1 + portfolio_returns).prod() - 1
            volatility = portfolio_returns.std() * np.sqrt(252)
            sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
            
            return {
                'date': rebal_date.strftime('%Y-%m-%d'),
                'method': 'portfolio_optimization',
                'weights': cleaned_weights,
                'train_period': f"{train_prices.index[0].date()} ~ {train_prices.index[-1].date()}",
                'test_period': f"{test_prices.index[0].date()} ~ {test_prices.index[-1].date()}",
                'cumulative_return': float(cumulative_return),
                'volatility': float(volatility),
                'sharpe_ratio': float(sharpe)
            }
        
        except Exception as e:
            logger.error(f"포트폴리오 최적화 실패: {e}")
            return None
    
    def _analyze_ml_ranking(
        self,
        train_prices: pd.DataFrame,
        test_prices: pd.DataFrame,
        rebal_date: pd.Timestamp
    ) -> Optional[Dict]:
        """
        ML 기반 랭킹 분석
        
        Args:
            train_prices: 학습 가격 데이터
            test_prices: 테스트 가격 데이터
            rebal_date: 리밸런싱 날짜
        
        Returns:
            분석 결과
        """
        try:
            # 간단한 모멘텀 기반 랭킹 (실제로는 ML 모델 사용)
            returns_20d = train_prices.pct_change(20).iloc[-1]
            returns_60d = train_prices.pct_change(60).iloc[-1]
            
            # 모멘텀 스코어
            momentum_score = returns_20d * 0.6 + returns_60d * 0.4
            momentum_score = momentum_score.sort_values(ascending=False)
            
            # Top 3 선택 (동일 가중)
            top_n = min(3, len(momentum_score))
            top_codes = momentum_score.head(top_n).index.tolist()
            weights = {code: 1.0 / top_n for code in top_codes}
            
            # 테스트 기간 성과
            test_returns = test_prices[top_codes].pct_change().dropna()
            portfolio_returns = test_returns.mean(axis=1)
            
            cumulative_return = (1 + portfolio_returns).prod() - 1
            volatility = portfolio_returns.std() * np.sqrt(252)
            sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() > 0 else 0
            
            return {
                'date': rebal_date.strftime('%Y-%m-%d'),
                'method': 'ml_ranking',
                'weights': weights,
                'train_period': f"{train_prices.index[0].date()} ~ {train_prices.index[-1].date()}",
                'test_period': f"{test_prices.index[0].date()} ~ {test_prices.index[-1].date()}",
                'cumulative_return': float(cumulative_return),
                'volatility': float(volatility),
                'sharpe_ratio': float(sharpe)
            }
        
        except Exception as e:
            logger.error(f"ML 랭킹 분석 실패: {e}")
            return None
    
    def calculate_summary_statistics(self) -> Dict:
        """
        요약 통계 계산
        
        Returns:
            요약 통계
        """
        if not self.results:
            return {}
        
        df = pd.DataFrame(self.results)
        
        summary = {
            'total_periods': len(df),
            'avg_return': float(df['cumulative_return'].mean()),
            'avg_volatility': float(df['volatility'].mean()),
            'avg_sharpe': float(df['sharpe_ratio'].mean()),
            'win_rate': float((df['cumulative_return'] > 0).sum() / len(df)),
            'best_return': float(df['cumulative_return'].max()),
            'worst_return': float(df['cumulative_return'].min()),
            'best_sharpe': float(df['sharpe_ratio'].max()),
            'worst_sharpe': float(df['sharpe_ratio'].min())
        }
        
        return summary
    
    def save_results(
        self,
        output_dir: str = "data/output/analysis"
    ):
        """
        결과 저장
        
        Args:
            output_dir: 출력 디렉토리
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 결과 저장
        output_file = output_path / f"lookback_analysis_{timestamp}.json"
        
        data = {
            'config': {
                'codes': self.codes,
                'start_date': self.start_date.strftime('%Y-%m-%d'),
                'end_date': self.end_date.strftime('%Y-%m-%d'),
                'lookback_window': self.lookback_window,
                'rebalance_freq': self.rebalance_freq,
                'test_window': self.test_window
            },
            'results': self.results,
            'summary': self.calculate_summary_statistics()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 결과 저장 완료: {output_file}")


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="룩백 분석")
    parser.add_argument("--codes", type=str, default="069500,091160,133690,305720,373220", help="종목 코드")
    parser.add_argument("--start-date", type=str, default="2022-01-01")
    parser.add_argument("--end-date", type=str, default="2024-11-01")
    parser.add_argument("--lookback-window", type=int, default=252, help="학습 윈도우 (거래일)")
    parser.add_argument("--rebalance-freq", type=int, default=21, help="리밸런싱 주기 (거래일)")
    parser.add_argument("--test-window", type=int, default=21, help="테스트 윈도우 (거래일)")
    parser.add_argument("--method", type=str, default="portfolio_optimization", 
                       choices=["portfolio_optimization", "ml_ranking"])
    
    args = parser.parse_args()
    
    # 종목 코드 파싱
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    
    # 분석 초기화
    analyzer = LookbackAnalyzer(
        codes=codes,
        start_date=args.start_date,
        end_date=args.end_date,
        lookback_window=args.lookback_window,
        rebalance_freq=args.rebalance_freq,
        test_window=args.test_window
    )
    
    # 데이터 로드
    analyzer.load_data()
    
    # 워크포워드 분석 실행
    results = analyzer.run_walkforward_analysis(method=args.method)
    
    # 요약 통계
    summary = analyzer.calculate_summary_statistics()
    
    # 결과 저장
    analyzer.save_results()
    
    # 출력
    print("\n" + "=" * 60)
    print("✨ 룩백 분석 완료!")
    print("=" * 60)
    print(f"종목 수: {len(codes)}")
    print(f"기간: {args.start_date} ~ {args.end_date}")
    print(f"분석 방법: {args.method}")
    print(f"\n총 리밸런싱 횟수: {summary.get('total_periods', 0)}")
    print(f"평균 수익률: {summary.get('avg_return', 0):.4f}")
    print(f"평균 변동성: {summary.get('avg_volatility', 0):.4f}")
    print(f"평균 Sharpe Ratio: {summary.get('avg_sharpe', 0):.4f}")
    print(f"승률: {summary.get('win_rate', 0):.2%}")
    print(f"최고 수익률: {summary.get('best_return', 0):.4f}")
    print(f"최저 수익률: {summary.get('worst_return', 0):.4f}")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
