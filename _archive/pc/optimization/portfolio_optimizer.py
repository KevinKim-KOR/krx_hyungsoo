#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pc/optimization/portfolio_optimizer.py
포트폴리오 최적화 모듈

PyPortfolioOpt 기반:
- 평균-분산 최적화 (Mean-Variance Optimization)
- 리스크 패리티 (Risk Parity)
- 블랙-리터만 모델 (Black-Litterman)
- 효율적 프론티어 (Efficient Frontier)
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

# PyPortfolioOpt
from pypfopt import EfficientFrontier, risk_models, expected_returns
from pypfopt import objective_functions
from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices

# 프로젝트 모듈
from core.data_loader import get_ohlcv

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """포트폴리오 최적화 클래스"""
    
    def __init__(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        risk_free_rate: float = 0.03  # 무위험 수익률 (3%)
    ):
        """
        Args:
            codes: 종목 코드 리스트
            start_date: 시작일
            end_date: 종료일
            risk_free_rate: 무위험 수익률
        """
        self.codes = codes
        self.start_date = start_date
        self.end_date = end_date
        self.risk_free_rate = risk_free_rate
        
        self.prices = None
        self.returns = None
        self.mu = None  # 기대 수익률
        self.S = None   # 공분산 행렬
        
        logger.info(f"PortfolioOptimizer 초기화: {len(codes)}개 종목")
    
    def load_data(self) -> pd.DataFrame:
        """
        가격 데이터 로드
        
        Returns:
            가격 데이터프레임 (columns: 종목 코드)
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
                logger.warning(f"가격 컬럼 없음: {code}, 컬럼: {df.columns.tolist()}")
                continue
        
        # 데이터프레임 생성
        self.prices = pd.DataFrame(price_data)
        self.prices = self.prices.dropna()
        
        logger.info(f"✅ 가격 데이터 로드 완료: {len(self.prices)}행, {len(self.prices.columns)}개 종목")
        
        # 수익률 계산
        self.returns = self.prices.pct_change().dropna()
        
        logger.info("=" * 60)
        
        return self.prices
    
    def calculate_expected_returns_and_risk(
        self,
        method: str = "mean_historical_return"
    ):
        """
        기대 수익률과 리스크 계산
        
        Args:
            method: 기대 수익률 계산 방법
                - mean_historical_return: 과거 평균 수익률
                - ema_historical_return: 지수 이동 평균
                - capm_return: CAPM 기반
        """
        logger.info("=" * 60)
        logger.info("기대 수익률 및 리스크 계산")
        logger.info("=" * 60)
        
        # 1. 기대 수익률
        if method == "mean_historical_return":
            self.mu = expected_returns.mean_historical_return(self.prices)
        elif method == "ema_historical_return":
            self.mu = expected_returns.ema_historical_return(self.prices)
        elif method == "capm_return":
            self.mu = expected_returns.capm_return(self.prices)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        logger.info(f"기대 수익률 계산 완료 ({method})")
        
        # 2. 공분산 행렬 (리스크)
        self.S = risk_models.sample_cov(self.prices)
        
        logger.info("공분산 행렬 계산 완료")
        logger.info("=" * 60)
    
    def optimize_max_sharpe(
        self,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        Sharpe Ratio 최대화
        
        Args:
            constraints: 제약 조건
                - max_weight: 최대 비중 (예: 0.3 = 30%)
                - min_weight: 최소 비중 (예: 0.05 = 5%)
        
        Returns:
            최적 포트폴리오 딕셔너리
        """
        logger.info("=" * 60)
        logger.info("Sharpe Ratio 최대화")
        logger.info("=" * 60)
        
        # Efficient Frontier 초기화
        ef = EfficientFrontier(self.mu, self.S)
        
        # 제약 조건 적용
        if constraints:
            if 'max_weight' in constraints:
                ef.add_constraint(lambda w: w <= constraints['max_weight'])
            if 'min_weight' in constraints:
                ef.add_constraint(lambda w: w >= constraints['min_weight'])
        
        # Sharpe Ratio 최대화
        weights = ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        cleaned_weights = ef.clean_weights()
        
        # 성능 지표
        performance = ef.portfolio_performance(verbose=False, risk_free_rate=self.risk_free_rate)
        
        result = {
            'method': 'max_sharpe',
            'weights': cleaned_weights,
            'expected_return': performance[0],
            'volatility': performance[1],
            'sharpe_ratio': performance[2]
        }
        
        logger.info(f"✅ 최적화 완료")
        logger.info(f"  기대 수익률: {performance[0]:.4f}")
        logger.info(f"  변동성: {performance[1]:.4f}")
        logger.info(f"  Sharpe Ratio: {performance[2]:.4f}")
        logger.info("=" * 60)
        
        return result
    
    def optimize_min_volatility(
        self,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        변동성 최소화
        
        Args:
            constraints: 제약 조건
        
        Returns:
            최적 포트폴리오 딕셔너리
        """
        logger.info("=" * 60)
        logger.info("변동성 최소화")
        logger.info("=" * 60)
        
        ef = EfficientFrontier(self.mu, self.S)
        
        if constraints:
            if 'max_weight' in constraints:
                ef.add_constraint(lambda w: w <= constraints['max_weight'])
            if 'min_weight' in constraints:
                ef.add_constraint(lambda w: w >= constraints['min_weight'])
        
        weights = ef.min_volatility()
        cleaned_weights = ef.clean_weights()
        
        performance = ef.portfolio_performance(verbose=False, risk_free_rate=self.risk_free_rate)
        
        result = {
            'method': 'min_volatility',
            'weights': cleaned_weights,
            'expected_return': performance[0],
            'volatility': performance[1],
            'sharpe_ratio': performance[2]
        }
        
        logger.info(f"✅ 최적화 완료")
        logger.info(f"  기대 수익률: {performance[0]:.4f}")
        logger.info(f"  변동성: {performance[1]:.4f}")
        logger.info(f"  Sharpe Ratio: {performance[2]:.4f}")
        logger.info("=" * 60)
        
        return result
    
    def optimize_efficient_return(
        self,
        target_return: float,
        constraints: Optional[Dict] = None
    ) -> Dict:
        """
        목표 수익률 달성하는 최소 리스크 포트폴리오
        
        Args:
            target_return: 목표 수익률 (연율)
            constraints: 제약 조건
        
        Returns:
            최적 포트폴리오 딕셔너리
        """
        logger.info("=" * 60)
        logger.info(f"목표 수익률 달성 (target={target_return:.4f})")
        logger.info("=" * 60)
        
        ef = EfficientFrontier(self.mu, self.S)
        
        if constraints:
            if 'max_weight' in constraints:
                ef.add_constraint(lambda w: w <= constraints['max_weight'])
            if 'min_weight' in constraints:
                ef.add_constraint(lambda w: w >= constraints['min_weight'])
        
        weights = ef.efficient_return(target_return=target_return)
        cleaned_weights = ef.clean_weights()
        
        performance = ef.portfolio_performance(verbose=False, risk_free_rate=self.risk_free_rate)
        
        result = {
            'method': 'efficient_return',
            'target_return': target_return,
            'weights': cleaned_weights,
            'expected_return': performance[0],
            'volatility': performance[1],
            'sharpe_ratio': performance[2]
        }
        
        logger.info(f"✅ 최적화 완료")
        logger.info(f"  기대 수익률: {performance[0]:.4f}")
        logger.info(f"  변동성: {performance[1]:.4f}")
        logger.info(f"  Sharpe Ratio: {performance[2]:.4f}")
        logger.info("=" * 60)
        
        return result
    
    def calculate_discrete_allocation(
        self,
        weights: Dict[str, float],
        total_portfolio_value: float
    ) -> Dict:
        """
        이산 배분 계산 (실제 매수 가능한 주식 수)
        
        Args:
            weights: 최적 비중
            total_portfolio_value: 총 포트폴리오 가치
        
        Returns:
            종목별 매수 주식 수
        """
        logger.info("=" * 60)
        logger.info("이산 배분 계산")
        logger.info("=" * 60)
        
        # 최신 가격
        latest_prices = get_latest_prices(self.prices)
        
        # 이산 배분
        da = DiscreteAllocation(
            weights,
            latest_prices,
            total_portfolio_value=total_portfolio_value
        )
        
        allocation, leftover = da.greedy_portfolio()
        
        logger.info(f"✅ 이산 배분 완료")
        logger.info(f"  총 투자액: {total_portfolio_value:,.0f}원")
        logger.info(f"  잔액: {leftover:,.0f}원")
        logger.info("=" * 60)
        
        return {
            'allocation': allocation,
            'leftover': leftover,
            'total_value': total_portfolio_value
        }
    
    def save_results(
        self,
        results: List[Dict],
        output_dir: str = "data/output/optimization"
    ):
        """
        최적화 결과 저장
        
        Args:
            results: 최적화 결과 리스트
            output_dir: 출력 디렉토리
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON 저장
        output_file = output_path / f"optimal_portfolio_{timestamp}.json"
        
        # numpy 타입 변환
        def convert_types(obj):
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(v) for v in obj]
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            else:
                return obj
        
        results_json = convert_types(results)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_json, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 결과 저장 완료: {output_file}")


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="포트폴리오 최적화")
    parser.add_argument("--codes", type=str, default="069500,091160,133690,305720,373220", help="종목 코드 (쉼표 구분)")
    parser.add_argument("--start-date", type=str, default="2023-01-01")
    parser.add_argument("--end-date", type=str, default="2024-11-01")
    parser.add_argument("--portfolio-value", type=float, default=10_000_000, help="총 포트폴리오 가치")
    parser.add_argument("--max-weight", type=float, default=0.3, help="최대 비중")
    parser.add_argument("--min-weight", type=float, default=0.05, help="최소 비중")
    
    args = parser.parse_args()
    
    # 종목 코드 파싱
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    
    # 최적화 초기화
    optimizer = PortfolioOptimizer(
        codes=codes,
        start_date=args.start_date,
        end_date=args.end_date
    )
    
    # 데이터 로드
    optimizer.load_data()
    
    # 기대 수익률 및 리스크 계산
    optimizer.calculate_expected_returns_and_risk()
    
    # 제약 조건
    constraints = {
        'max_weight': args.max_weight,
        'min_weight': args.min_weight
    }
    
    # 최적화 실행
    results = []
    
    # 1. Sharpe Ratio 최대화
    result_sharpe = optimizer.optimize_max_sharpe(constraints)
    results.append(result_sharpe)
    
    # 2. 변동성 최소화
    result_vol = optimizer.optimize_min_volatility(constraints)
    results.append(result_vol)
    
    # 3. 이산 배분 (Sharpe 최대화 기준)
    allocation = optimizer.calculate_discrete_allocation(
        result_sharpe['weights'],
        args.portfolio_value
    )
    results.append({
        'method': 'discrete_allocation',
        'allocation': allocation['allocation'],
        'leftover': allocation['leftover'],
        'total_value': allocation['total_value']
    })
    
    # 결과 저장
    optimizer.save_results(results)
    
    print("\n" + "=" * 60)
    print("✨ 포트폴리오 최적화 완료!")
    print("=" * 60)
    print(f"종목 수: {len(codes)}")
    print(f"기간: {args.start_date} ~ {args.end_date}")
    print("\n1. Sharpe Ratio 최대화:")
    print(f"  - 기대 수익률: {result_sharpe['expected_return']:.4f}")
    print(f"  - 변동성: {result_sharpe['volatility']:.4f}")
    print(f"  - Sharpe Ratio: {result_sharpe['sharpe_ratio']:.4f}")
    print("\n2. 변동성 최소화:")
    print(f"  - 기대 수익률: {result_vol['expected_return']:.4f}")
    print(f"  - 변동성: {result_vol['volatility']:.4f}")
    print(f"  - Sharpe Ratio: {result_vol['sharpe_ratio']:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
