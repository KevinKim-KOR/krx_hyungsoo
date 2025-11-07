# -*- coding: utf-8 -*-
"""
Jason 백테스트 엔진 어댑터

Jason의 검증된 백테스트 엔진을 우리 시스템에 통합하기 위한 어댑터
"""
from typing import Dict, Optional
from datetime import date, datetime
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import logging

# Jason 모듈 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
JASON_PATH = PROJECT_ROOT / "momentum-etf"
if str(JASON_PATH) not in sys.path:
    sys.path.insert(0, str(JASON_PATH))

from core.engine.jason.rules import StrategyRules

logger = logging.getLogger(__name__)


class JasonBacktestAdapter:
    """
    Jason 백테스트 엔진 어댑터
    
    역할:
    1. 데이터 형식 변환 (우리 ↔ Jason)
    2. Jason 엔진 실행
    3. 에러 처리 및 롤백
    """
    
    def __init__(
        self,
        initial_capital: float = 10_000_000,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001,
        max_positions: int = 10,
        country_code: str = "kor"
    ):
        """
        Args:
            initial_capital: 초기 자본
            commission_rate: 수수료율 (0.015%)
            slippage_rate: 슬리피지율 (0.1%)
            max_positions: 최대 보유 종목 수
            country_code: 국가 코드
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.country_code = country_code
        
        logger.info(f"JasonBacktestAdapter 초기화: capital={initial_capital:,}, positions={max_positions}")
    
    def run(
        self,
        price_data: pd.DataFrame,
        strategy,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        백테스트 실행
        
        Args:
            price_data: MultiIndex DataFrame (code, date)
            strategy: SignalGenerator
            start_date: 시작일 (선택)
            end_date: 종료일 (선택)
        
        Returns:
            백테스트 결과 (Dict)
        """
        try:
            logger.info("백테스트 시작...")
            
            # 1. 데이터 변환
            logger.info("1. 데이터 변환 중...")
            jason_data = self._convert_data(price_data)
            logger.info(f"   변환 완료: {len(jason_data)}개 종목")
            
            # 2. 전략 변환
            logger.info("2. 전략 변환 중...")
            jason_strategy = self._convert_strategy(strategy, self.max_positions)
            logger.info(f"   변환 완료: MA={jason_strategy.ma_period}, TopN={jason_strategy.portfolio_topn}")
            
            # 3. Jason 백테스트 실행
            logger.info("3. Jason 백테스트 실행 중...")
            jason_results = self._run_jason_backtest(
                jason_data,
                jason_strategy,
                start_date,
                end_date
            )
            logger.info("   실행 완료")
            
            # 4. 결과 변환
            logger.info("4. 결과 변환 중...")
            our_results = self._convert_results(jason_results, start_date, end_date)
            logger.info("   변환 완료")
            
            logger.info(f"백테스트 완료: 수익률 {our_results['total_return_pct']:.2f}%")
            return our_results
            
        except Exception as e:
            logger.error(f"백테스트 실패: {e}")
            import traceback
            traceback.print_exc()
            
            # 폴백: 임시 결과 반환
            return self._get_fallback_results()
    
    def _convert_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        데이터 변환: 우리 형식 → Jason 형식
        
        입력: MultiIndex DataFrame (code, date)
        출력: Dict[ticker, DataFrame(Date, Open, Close, ...)]
        """
        jason_data = {}
        
        try:
            # 종목 코드 추출
            if isinstance(df.index, pd.MultiIndex):
                tickers = df.index.get_level_values(0).unique()
            else:
                raise ValueError("MultiIndex DataFrame이 아닙니다")
            
            # 종목별로 변환
            for ticker in tickers:
                try:
                    # 종목별 데이터 추출
                    ticker_df = df.xs(ticker, level=0).copy()
                    
                    # 날짜 변환 (date → pd.Timestamp)
                    if not isinstance(ticker_df.index, pd.DatetimeIndex):
                        ticker_df.index = pd.to_datetime(ticker_df.index)
                    ticker_df.index.name = 'Date'
                    
                    # 컬럼명 변환 (open → Open)
                    ticker_df.columns = [col.capitalize() for col in ticker_df.columns]
                    
                    # 데이터 검증
                    if len(ticker_df) < 20:  # 최소 20일 데이터 필요
                        logger.warning(f"종목 {ticker}: 데이터 부족 ({len(ticker_df)}일)")
                        continue
                    
                    jason_data[ticker] = ticker_df
                    
                except Exception as e:
                    logger.warning(f"종목 {ticker} 변환 실패: {e}")
                    continue
            
            if not jason_data:
                raise ValueError("변환된 데이터가 없습니다")
            
            return jason_data
            
        except Exception as e:
            logger.error(f"데이터 변환 실패: {e}")
            raise
    
    def _convert_strategy(self, strategy, portfolio_topn: int = 10) -> StrategyRules:
        """
        전략 변환: SignalGenerator → StrategyRules
        
        매핑:
        - ma_period: 그대로 사용
        - portfolio_topn: 파라미터로 받음
        - replace_threshold: maps_buy_threshold 사용
        - ma_type: "SMA" 고정
        - core_holdings: 빈 리스트
        """
        try:
            return StrategyRules(
                ma_period=getattr(strategy, 'ma_period', 60),
                portfolio_topn=portfolio_topn,
                replace_threshold=getattr(strategy, 'maps_buy_threshold', 0.0),
                ma_type="SMA",
                core_holdings=[]
            )
        except Exception as e:
            logger.error(f"전략 변환 실패: {e}")
            # 기본 전략 반환
            return StrategyRules(
                ma_period=60,
                portfolio_topn=10,
                replace_threshold=0.0,
                ma_type="SMA",
                core_holdings=[]
            )
    
    def _run_jason_backtest(
        self,
        jason_data: Dict[str, pd.DataFrame],
        jason_strategy: StrategyRules,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict:
        """
        Jason 백테스트 실행
        
        현재는 간단한 MAPS 전략으로 구현
        추후 Jason의 portfolio_runner.py 통합 예정
        """
        try:
            # 간단한 MAPS 백테스트 구현
            return self._simple_maps_backtest(
                jason_data,
                jason_strategy,
                start_date,
                end_date
            )
        except Exception as e:
            logger.error(f"Jason 백테스트 실행 실패: {e}")
            raise
    
    def _simple_maps_backtest(
        self,
        price_data: Dict[str, pd.DataFrame],
        strategy: StrategyRules,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict:
        """
        간단한 MAPS 백테스트 구현
        
        로직:
        1. 각 종목의 MA 계산
        2. MA 대비 수익률 계산 (MAPS 점수)
        3. Top N 선택
        4. 동일 가중 포지션
        5. 일별 리밸런싱
        """
        # 초기화
        cash = self.initial_capital
        positions = {}  # {ticker: shares}
        trades = []
        daily_values = []
        
        # 모든 날짜 추출
        all_dates = set()
        for ticker_df in price_data.values():
            all_dates.update(ticker_df.index)
        all_dates = sorted(all_dates)
        
        # 날짜 필터링
        if start_date:
            all_dates = [d for d in all_dates if d >= pd.Timestamp(start_date)]
        if end_date:
            all_dates = [d for d in all_dates if d <= pd.Timestamp(end_date)]
        
        logger.info(f"백테스트 기간: {all_dates[0].date()} ~ {all_dates[-1].date()} ({len(all_dates)}일)")
        
        # 일별 백테스트
        for current_date in all_dates:
            # 1. 현재 가격 및 MA 계산
            current_prices = {}
            ma_scores = {}
            
            for ticker, ticker_df in price_data.items():
                if current_date not in ticker_df.index:
                    continue
                
                # 현재까지의 데이터
                hist_df = ticker_df[ticker_df.index <= current_date]
                if len(hist_df) < strategy.ma_period:
                    continue
                
                # 현재 가격 (iloc로 마지막 값 가져오기)
                current_price = float(hist_df['Close'].iloc[-1])
                current_prices[ticker] = current_price
                
                # MA 계산
                ma = float(hist_df['Close'].rolling(window=strategy.ma_period).mean().iloc[-1])
                
                # MAPS 점수 계산
                if ma > 0:
                    ma_score = ((current_price / ma) - 1.0) * 100
                    ma_scores[ticker] = float(ma_score)
            
            # 2. Top N 선택 (MA 점수 > threshold)
            candidates = {
                ticker: score 
                for ticker, score in ma_scores.items() 
                if score > strategy.replace_threshold
            }
            
            top_n = sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:strategy.portfolio_topn]
            top_tickers = [ticker for ticker, _ in top_n]
            
            # 3. 리밸런싱
            # 매도: Top N에 없는 종목
            for ticker in list(positions.keys()):
                if ticker not in top_tickers:
                    shares = positions[ticker]
                    price = current_prices.get(ticker, 0)
                    if price > 0:
                        sell_amount = shares * price
                        cash += sell_amount
                        trades.append({
                            'date': current_date.date(),
                            'ticker': ticker,
                            'action': 'SELL',
                            'shares': shares,
                            'price': price
                        })
                        del positions[ticker]
            
            # 매수: Top N 중 미보유 종목
            if top_tickers:
                # 현재 포트폴리오 가치
                holdings_value = sum(
                    positions.get(ticker, 0) * current_prices.get(ticker, 0)
                    for ticker in positions
                )
                total_value = cash + holdings_value
                
                # 목표 포지션 크기
                target_value_per_position = total_value / len(top_tickers)
                
                for ticker in top_tickers:
                    if ticker not in positions:
                        price = current_prices.get(ticker, 0)
                        if price > 0 and cash > target_value_per_position * 0.5:
                            # 매수 가능 금액
                            buy_amount = min(target_value_per_position, cash)
                            shares = int(buy_amount / price)
                            
                            if shares > 0:
                                actual_amount = shares * price
                                cash -= actual_amount
                                positions[ticker] = shares
                                trades.append({
                                    'date': current_date.date(),
                                    'ticker': ticker,
                                    'action': 'BUY',
                                    'shares': shares,
                                    'price': price
                                })
            
            # 4. 일별 평가액 기록
            holdings_value = sum(
                positions.get(ticker, 0) * current_prices.get(ticker, 0)
                for ticker in positions
            )
            total_value = cash + holdings_value
            daily_values.append((current_date.date(), total_value))
        
        # 결과 반환
        final_value = daily_values[-1][1] if daily_values else self.initial_capital
        
        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return_pct': ((final_value / self.initial_capital) - 1) * 100,
            'trades': trades,
            'daily_values': daily_values,
            'start_date': all_dates[0].date() if all_dates else None,
            'end_date': all_dates[-1].date() if all_dates else None
        }
    
    def _convert_results(
        self,
        jason_results: Dict,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict:
        """
        결과 변환: Jason 형식 → 우리 형식
        """
        try:
            # 기본 지표
            initial_capital = jason_results['initial_capital']
            final_value = jason_results['final_value']
            total_return = final_value - initial_capital
            total_return_pct = jason_results['total_return_pct']
            
            # 일별 수익률 계산
            daily_values = jason_results['daily_values']
            daily_returns = []
            for i in range(1, len(daily_values)):
                prev_value = daily_values[i-1][1]
                curr_value = daily_values[i][1]
                if prev_value > 0:
                    daily_return = (curr_value / prev_value) - 1
                    daily_returns.append(daily_return)
            
            # Sharpe Ratio 계산
            if daily_returns:
                mean_return = np.mean(daily_returns)
                std_return = np.std(daily_returns)
                sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
            else:
                sharpe_ratio = 0.0
            
            # Max Drawdown 계산
            max_drawdown = 0.0
            peak = initial_capital
            for _, value in daily_values:
                if value > peak:
                    peak = value
                drawdown = ((value / peak) - 1) * 100 if peak > 0 else 0.0
                if drawdown < max_drawdown:
                    max_drawdown = drawdown
            
            # CAGR 계산
            start_dt = jason_results.get('start_date') or start_date
            end_dt = jason_results.get('end_date') or end_date
            cagr = self._calculate_cagr(initial_capital, final_value, start_dt, end_dt)
            
            # 거래 통계
            trades = jason_results['trades']
            num_trades = len(trades)
            
            return {
                'final_value': final_value,
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'cagr': cagr,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'num_trades': num_trades,
                'trades': trades,
                'daily_values': daily_values
            }
            
        except Exception as e:
            logger.error(f"결과 변환 실패: {e}")
            # 기본 결과 반환
            return self._get_default_results()
    
    def _calculate_cagr(
        self,
        initial_capital: float,
        final_value: float,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> float:
        """CAGR 계산"""
        try:
            if not start_date or not end_date or initial_capital <= 0:
                return 0.0
            
            # 기간 계산 (년)
            days = (end_date - start_date).days
            years = days / 365.25
            
            if years <= 0:
                return 0.0
            
            # CAGR = (최종가치 / 초기자본)^(1/년수) - 1
            cagr = ((final_value / initial_capital) ** (1 / years) - 1) * 100
            return cagr
            
        except Exception as e:
            logger.warning(f"CAGR 계산 실패: {e}")
            return 0.0
    
    def _get_fallback_results(self) -> Dict:
        """폴백: 임시 결과 반환"""
        logger.warning("폴백 결과 반환")
        return {
            'final_value': self.initial_capital,
            'total_return': 0.0,
            'total_return_pct': 0.0,
            'cagr': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'num_trades': 0,
            'trades': [],
            'daily_values': []
        }
    
    def _get_default_results(self) -> Dict:
        """기본 결과 반환"""
        return self._get_fallback_results()


__all__ = ['JasonBacktestAdapter']
