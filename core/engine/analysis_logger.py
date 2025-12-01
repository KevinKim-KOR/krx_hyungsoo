# -*- coding: utf-8 -*-
"""
core/engine/analysis_logger.py
Phase 5: 분석 로그 추가

일자별/트레이드별 상세 로그 생성

사용법:
    from core.engine.analysis_logger import AnalysisLogger
    
    logger = AnalysisLogger()
    
    # 일자별 로그 기록
    logger.log_daily(
        date=date(2024, 1, 1),
        portfolio_value=10_500_000,
        regime='bull',
        equity_exposure=0.8,
        cash_exposure=0.2
    )
    
    # 트레이드 로그 기록
    logger.log_trade(
        date=date(2024, 1, 1),
        ticker='069500',
        side='BUY',
        qty=100,
        price_gross=50000,
        price_net=49950,
        fee=50,
        slippage=50
    )
    
    # DataFrame으로 변환
    daily_df = logger.get_daily_logs()
    trade_df = logger.get_trade_logs()
    
    # 저장
    logger.save_logs(output_dir)
"""
from typing import Dict, List, Optional, Any
from datetime import date
from pathlib import Path
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)


class AnalysisLogger:
    """분석 로그 관리자"""
    
    def __init__(self):
        """초기화"""
        self.daily_logs: List[Dict[str, Any]] = []
        self.trade_logs: List[Dict[str, Any]] = []
        self.regime_changes: List[Dict[str, Any]] = []
        self.defense_events: List[Dict[str, Any]] = []
        
    def reset(self):
        """로그 초기화"""
        self.daily_logs = []
        self.trade_logs = []
        self.regime_changes = []
        self.defense_events = []
    
    # =========================================================================
    # 일자별 로그
    # =========================================================================
    
    def log_daily(
        self,
        date: date,
        portfolio_value: float,
        cash: float,
        holdings_value: float,
        regime: str = 'neutral',
        regime_confidence: float = 0.5,
        regime_ratio: float = 1.0,
        num_positions: int = 0,
        daily_return: float = 0.0,
        cumulative_return: float = 0.0,
        drawdown: float = 0.0,
        **kwargs
    ):
        """
        일자별 로그 기록
        
        Args:
            date: 날짜
            portfolio_value: 포트폴리오 가치
            cash: 현금
            holdings_value: 보유 자산 가치
            regime: 시장 레짐 (bull, bear, neutral)
            regime_confidence: 레짐 신뢰도
            regime_ratio: 레짐 비율
            num_positions: 보유 포지션 수
            daily_return: 일간 수익률
            cumulative_return: 누적 수익률
            drawdown: 현재 낙폭
            **kwargs: 추가 필드
        """
        equity_exposure = holdings_value / portfolio_value if portfolio_value > 0 else 0
        cash_exposure = cash / portfolio_value if portfolio_value > 0 else 1
        
        log_entry = {
            'date': date,
            'portfolio_value': portfolio_value,
            'cash': cash,
            'holdings_value': holdings_value,
            'equity_exposure': equity_exposure,
            'cash_exposure': cash_exposure,
            'regime': regime,
            'regime_confidence': regime_confidence,
            'regime_ratio': regime_ratio,
            'num_positions': num_positions,
            'daily_return': daily_return,
            'cumulative_return': cumulative_return,
            'drawdown': drawdown,
            **kwargs
        }
        
        self.daily_logs.append(log_entry)
    
    def get_daily_logs(self) -> pd.DataFrame:
        """일자별 로그 DataFrame 반환"""
        if not self.daily_logs:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.daily_logs)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        return df
    
    # =========================================================================
    # 트레이드 로그
    # =========================================================================
    
    def log_trade(
        self,
        date: date,
        ticker: str,
        side: str,  # BUY, SELL
        qty: int,
        price: float,
        commission: float = 0.0,
        tax: float = 0.0,
        slippage: float = 0.0,
        reason: str = '',
        **kwargs
    ):
        """
        트레이드 로그 기록
        
        Args:
            date: 거래일
            ticker: 종목 코드
            side: 매수/매도 (BUY, SELL)
            qty: 수량
            price: 체결 가격
            commission: 수수료
            tax: 세금
            slippage: 슬리피지
            reason: 거래 사유
            **kwargs: 추가 필드
        """
        gross_amount = qty * price
        total_cost = commission + tax + slippage
        
        if side == 'BUY':
            net_amount = gross_amount + total_cost
        else:
            net_amount = gross_amount - total_cost
        
        log_entry = {
            'date': date,
            'ticker': ticker,
            'side': side,
            'qty': qty,
            'price': price,
            'gross_amount': gross_amount,
            'commission': commission,
            'tax': tax,
            'slippage': slippage,
            'total_cost': total_cost,
            'net_amount': net_amount,
            'reason': reason,
            **kwargs
        }
        
        self.trade_logs.append(log_entry)
    
    def get_trade_logs(self) -> pd.DataFrame:
        """트레이드 로그 DataFrame 반환"""
        if not self.trade_logs:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.trade_logs)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    # =========================================================================
    # 레짐 변경 로그
    # =========================================================================
    
    def log_regime_change(
        self,
        date: date,
        from_regime: str,
        to_regime: str,
        confidence: float,
        action_taken: str = ''
    ):
        """
        레짐 변경 로그 기록
        
        Args:
            date: 변경일
            from_regime: 이전 레짐
            to_regime: 새 레짐
            confidence: 신뢰도
            action_taken: 취한 조치
        """
        log_entry = {
            'date': date,
            'from_regime': from_regime,
            'to_regime': to_regime,
            'confidence': confidence,
            'action_taken': action_taken
        }
        
        self.regime_changes.append(log_entry)
        logger.info(f"레짐 변경: {from_regime} → {to_regime} (신뢰도 {confidence:.2f})")
    
    def get_regime_changes(self) -> pd.DataFrame:
        """레짐 변경 로그 DataFrame 반환"""
        if not self.regime_changes:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.regime_changes)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    # =========================================================================
    # 방어 이벤트 로그
    # =========================================================================
    
    def log_defense_event(
        self,
        date: date,
        event_type: str,  # portfolio_stop, individual_stop, crash_detected, regime_reduce
        details: str = '',
        impact: float = 0.0
    ):
        """
        방어 이벤트 로그 기록
        
        Args:
            date: 발생일
            event_type: 이벤트 유형
            details: 상세 내용
            impact: 영향 (손실률 등)
        """
        log_entry = {
            'date': date,
            'event_type': event_type,
            'details': details,
            'impact': impact
        }
        
        self.defense_events.append(log_entry)
        logger.info(f"방어 이벤트: {event_type} - {details}")
    
    def get_defense_events(self) -> pd.DataFrame:
        """방어 이벤트 로그 DataFrame 반환"""
        if not self.defense_events:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.defense_events)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    # =========================================================================
    # 통계 및 요약
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """로그 요약 통계"""
        daily_df = self.get_daily_logs()
        trade_df = self.get_trade_logs()
        
        summary = {
            'total_days': len(self.daily_logs),
            'total_trades': len(self.trade_logs),
            'regime_changes': len(self.regime_changes),
            'defense_events': len(self.defense_events)
        }
        
        # 레짐 분포
        if not daily_df.empty and 'regime' in daily_df.columns:
            regime_counts = daily_df['regime'].value_counts()
            total_days = len(daily_df)
            summary['regime_distribution'] = {
                regime: {
                    'days': int(count),
                    'pct': count / total_days * 100
                }
                for regime, count in regime_counts.items()
            }
        
        # 거래 통계
        if not trade_df.empty:
            summary['trade_stats'] = {
                'buy_count': len(trade_df[trade_df['side'] == 'BUY']),
                'sell_count': len(trade_df[trade_df['side'] == 'SELL']),
                'total_commission': trade_df['commission'].sum(),
                'total_tax': trade_df['tax'].sum(),
                'total_slippage': trade_df['slippage'].sum(),
                'total_costs': trade_df['total_cost'].sum()
            }
        
        # 방어 이벤트 통계
        if self.defense_events:
            event_types = {}
            for event in self.defense_events:
                event_type = event['event_type']
                event_types[event_type] = event_types.get(event_type, 0) + 1
            summary['defense_event_types'] = event_types
        
        return summary
    
    # =========================================================================
    # 저장 및 로드
    # =========================================================================
    
    def save_logs(
        self,
        output_dir: Path,
        prefix: str = 'backtest'
    ):
        """
        로그 저장
        
        Args:
            output_dir: 출력 디렉토리
            prefix: 파일 접두사
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 일자별 로그
        daily_df = self.get_daily_logs()
        if not daily_df.empty:
            daily_file = output_dir / f'{prefix}_daily_logs.csv'
            daily_df.to_csv(daily_file, encoding='utf-8-sig')
            logger.info(f"일자별 로그 저장: {daily_file}")
        
        # 트레이드 로그
        trade_df = self.get_trade_logs()
        if not trade_df.empty:
            trade_file = output_dir / f'{prefix}_trade_logs.csv'
            trade_df.to_csv(trade_file, index=False, encoding='utf-8-sig')
            logger.info(f"트레이드 로그 저장: {trade_file}")
        
        # 레짐 변경 로그
        regime_df = self.get_regime_changes()
        if not regime_df.empty:
            regime_file = output_dir / f'{prefix}_regime_changes.csv'
            regime_df.to_csv(regime_file, index=False, encoding='utf-8-sig')
            logger.info(f"레짐 변경 로그 저장: {regime_file}")
        
        # 방어 이벤트 로그
        defense_df = self.get_defense_events()
        if not defense_df.empty:
            defense_file = output_dir / f'{prefix}_defense_events.csv'
            defense_df.to_csv(defense_file, index=False, encoding='utf-8-sig')
            logger.info(f"방어 이벤트 로그 저장: {defense_file}")
        
        # 요약 저장
        summary = self.get_summary()
        summary_file = output_dir / f'{prefix}_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"요약 저장: {summary_file}")
    
    def load_logs(
        self,
        input_dir: Path,
        prefix: str = 'backtest'
    ):
        """
        로그 로드
        
        Args:
            input_dir: 입력 디렉토리
            prefix: 파일 접두사
        """
        input_dir = Path(input_dir)
        
        # 일자별 로그
        daily_file = input_dir / f'{prefix}_daily_logs.csv'
        if daily_file.exists():
            df = pd.read_csv(daily_file, encoding='utf-8-sig', index_col=0)
            self.daily_logs = df.reset_index().to_dict('records')
            logger.info(f"일자별 로그 로드: {len(self.daily_logs)}건")
        
        # 트레이드 로그
        trade_file = input_dir / f'{prefix}_trade_logs.csv'
        if trade_file.exists():
            df = pd.read_csv(trade_file, encoding='utf-8-sig')
            self.trade_logs = df.to_dict('records')
            logger.info(f"트레이드 로그 로드: {len(self.trade_logs)}건")


# 편의 함수
def create_analysis_logger() -> AnalysisLogger:
    """분석 로거 생성"""
    return AnalysisLogger()
