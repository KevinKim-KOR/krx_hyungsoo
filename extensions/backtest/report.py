# -*- coding: utf-8 -*-
"""
extensions/backtest/report.py
백테스트 성과 리포트 생성
"""
from typing import Dict, List, Optional
from datetime import date
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BacktestReport:
    """백테스트 리포트 생성기"""
    
    def __init__(self, result: Dict):
        """
        Args:
            result: 백테스트 결과
        """
        self.result = result
        self.metrics = result['metrics']
        self.nav_history = result['nav_history']
        self.trades = result['trades']
        self.final_positions = result.get('final_positions', {})
    
    def generate_summary(self) -> str:
        """요약 리포트 생성"""
        lines = []
        lines.append("=" * 60)
        lines.append("백테스트 성과 요약")
        lines.append("=" * 60)
        lines.append("")
        
        # 수익률
        lines.append("## 수익률")
        lines.append(f"총 수익률: {self.metrics['total_return']:>15.2f}%")
        lines.append(f"연율화 수익률: {self.metrics['annual_return']:>11.2f}%")
        lines.append("")
        
        # 리스크
        lines.append("## 리스크")
        lines.append(f"변동성 (연): {self.metrics['volatility']:>14.2f}%")
        lines.append(f"최대 낙폭 (MDD): {self.metrics['max_drawdown']:>10.2f}%")
        lines.append("")
        
        # 위험조정 수익률
        lines.append("## 위험조정 수익률")
        lines.append(f"샤프 비율: {self.metrics['sharpe_ratio']:>17.2f}")
        lines.append("")
        
        # 거래 통계
        lines.append("## 거래 통계")
        lines.append(f"총 거래 횟수: {self.metrics['total_trades']:>14}회")
        lines.append(f"승률: {self.metrics['win_rate']:>24.2f}%")
        lines.append("")
        
        # 최종 자산
        lines.append("## 최종 자산")
        lines.append(f"최종 가치: {self.metrics['final_value']:>16,.0f}원")
        lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def generate_trade_log(self) -> pd.DataFrame:
        """거래 로그 생성"""
        if not self.trades:
            return pd.DataFrame()
        
        records = []
        for trade in self.trades:
            records.append({
                'date': trade.date,
                'symbol': trade.symbol,
                'action': trade.action,
                'quantity': trade.quantity,
                'price': trade.price,
                'amount': trade.amount,
                'commission': trade.commission
            })
        
        df = pd.DataFrame(records)
        return df
    
    def generate_position_summary(self) -> pd.DataFrame:
        """포지션 요약 생성"""
        if not self.final_positions:
            return pd.DataFrame()
        
        records = []
        for symbol, position in self.final_positions.items():
            records.append({
                'symbol': symbol,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'market_value': position.market_value,
                'pnl': position.pnl,
                'pnl_pct': position.pnl_pct
            })
        
        df = pd.DataFrame(records)
        df = df.sort_values('pnl_pct', ascending=False)
        return df
    
    def generate_nav_series(self) -> pd.Series:
        """NAV 시계열 생성"""
        if not self.nav_history:
            return pd.Series()
        
        dates = [d for d, _ in self.nav_history]
        navs = [nav for _, nav in self.nav_history]
        
        return pd.Series(navs, index=dates, name='NAV')
    
    def generate_drawdown_series(self) -> pd.Series:
        """낙폭 시계열 생성"""
        nav_series = self.generate_nav_series()
        
        if nav_series.empty:
            return pd.Series()
        
        cummax = nav_series.cummax()
        drawdown = (nav_series / cummax - 1.0) * 100
        
        return drawdown
    
    def generate_monthly_returns(self) -> pd.DataFrame:
        """월별 수익률 생성"""
        nav_series = self.generate_nav_series()
        
        if nav_series.empty:
            return pd.DataFrame()
        
        # 월말 NAV
        monthly_nav = nav_series.resample('M').last()
        
        # 월별 수익률
        monthly_returns = monthly_nav.pct_change() * 100
        
        # 연도별로 재구성
        df = pd.DataFrame({
            'year': monthly_returns.index.year,
            'month': monthly_returns.index.month,
            'return': monthly_returns.values
        })
        
        pivot = df.pivot(index='year', columns='month', values='return')
        pivot.columns = [f'{m}월' for m in pivot.columns]
        
        # 연간 수익률 추가
        yearly_returns = []
        for year in pivot.index:
            year_data = nav_series[nav_series.index.year == year]
            if len(year_data) > 0:
                yearly_return = (year_data.iloc[-1] / year_data.iloc[0] - 1.0) * 100
                yearly_returns.append(yearly_return)
            else:
                yearly_returns.append(np.nan)
        
        pivot['연간'] = yearly_returns
        
        return pivot
    
    def save_to_file(self, output_dir: Path):
        """파일로 저장"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 요약 리포트
        summary_file = output_dir / 'summary.txt'
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_summary())
        logger.info(f"요약 리포트 저장: {summary_file}")
        
        # 거래 로그
        trade_log = self.generate_trade_log()
        if not trade_log.empty:
            trade_file = output_dir / 'trades.csv'
            trade_log.to_csv(trade_file, index=False, encoding='utf-8-sig')
            logger.info(f"거래 로그 저장: {trade_file}")
        
        # 포지션 요약
        position_summary = self.generate_position_summary()
        if not position_summary.empty:
            position_file = output_dir / 'positions.csv'
            position_summary.to_csv(position_file, index=False, encoding='utf-8-sig')
            logger.info(f"포지션 요약 저장: {position_file}")
        
        # NAV 시계열
        nav_series = self.generate_nav_series()
        if not nav_series.empty:
            nav_file = output_dir / 'nav.csv'
            nav_series.to_csv(nav_file, header=True, encoding='utf-8-sig')
            logger.info(f"NAV 시계열 저장: {nav_file}")
        
        # 월별 수익률
        monthly_returns = self.generate_monthly_returns()
        if not monthly_returns.empty:
            monthly_file = output_dir / 'monthly_returns.csv'
            monthly_returns.to_csv(monthly_file, encoding='utf-8-sig')
            logger.info(f"월별 수익률 저장: {monthly_file}")
        
        logger.info(f"모든 리포트 저장 완료: {output_dir}")


class ComparisonReport:
    """비교 리포트 생성기"""
    
    def __init__(self, results: Dict[str, Dict]):
        """
        Args:
            results: {전략명: 백테스트 결과} 딕셔너리
        """
        self.results = results
    
    def generate_comparison_table(self) -> pd.DataFrame:
        """전략 비교 테이블 생성"""
        records = []
        
        for strategy_name, result in self.results.items():
            metrics = result['metrics']
            records.append({
                '전략': strategy_name,
                '총 수익률 (%)': metrics['total_return'],
                '연율화 수익률 (%)': metrics['annual_return'],
                '변동성 (%)': metrics['volatility'],
                '샤프 비율': metrics['sharpe_ratio'],
                'MDD (%)': metrics['max_drawdown'],
                '승률 (%)': metrics['win_rate'],
                '거래 횟수': metrics['total_trades']
            })
        
        df = pd.DataFrame(records)
        df = df.sort_values('샤프 비율', ascending=False)
        
        return df
    
    def save_to_file(self, output_file: Path):
        """파일로 저장"""
        comparison_table = self.generate_comparison_table()
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        comparison_table.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        logger.info(f"비교 리포트 저장: {output_file}")


def create_report(result: Dict) -> BacktestReport:
    """백테스트 리포트 생성"""
    return BacktestReport(result)


def create_comparison_report(results: Dict[str, Dict]) -> ComparisonReport:
    """비교 리포트 생성"""
    return ComparisonReport(results)
