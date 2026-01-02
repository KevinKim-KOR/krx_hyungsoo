# -*- coding: utf-8 -*-
"""
extensions/automation/portfolio_helper.py
포트폴리오 관련 공통 기능

포트폴리오 데이터 로딩 및 포맷팅을 위한 헬퍼 함수
"""

import logging
from typing import Dict, Any
from extensions.automation.portfolio_loader import PortfolioLoader


logger = logging.getLogger(__name__)


class PortfolioHelper:
    """포트폴리오 헬퍼"""
    
    def __init__(self, portfolio_file: str = None):
        """
        Args:
            portfolio_file: 포트폴리오 파일 경로 (선택)
        """
        try:
            self.loader = PortfolioLoader(portfolio_file)
            logger.info("PortfolioHelper 초기화 완료")
        except FileNotFoundError as e:
            logger.error(f"포트폴리오 파일을 찾을 수 없습니다: {e}")
            self.loader = None
    
    def load_full_data(self) -> Dict[str, Any]:
        """
        전체 포트폴리오 데이터 로드
        
        Returns:
            {
                'summary': 포트폴리오 요약,
                'holdings_count': 보유 종목 수,
                'holdings_codes': 보유 종목 코드 리스트,
                'holdings_detail': 보유 종목 상세 DataFrame
            }
        """
        if not self.loader:
            logger.warning("포트폴리오 로더가 초기화되지 않았습니다")
            return {}
        
        try:
            return {
                'summary': self.loader.get_portfolio_summary(),
                'holdings_count': len(self.loader.get_holdings_codes()),
                'holdings_codes': self.loader.get_holdings_codes(),
                'holdings_detail': self.loader.get_holdings_detail()
            }
        except Exception as e:
            logger.error(f"포트폴리오 데이터 로드 실패: {e}")
            return {}
    
    @staticmethod
    def format_return(return_amount: float, return_pct: float) -> str:
        """
        수익/손실 포맷 (색상 이모지 포함)
        
        Args:
            return_amount: 평가손익 금액
            return_pct: 수익률 (%)
        
        Returns:
            포맷된 문자열 (예: "🔴 `+1,234,567원` (+12.34%)")
        """
        emoji = "🔴" if return_amount >= 0 else "🔵"
        return f"{emoji} `{return_amount:+,.0f}원` ({return_pct:+.2f}%)"
    
    @staticmethod
    def format_portfolio_summary(summary: Dict[str, Any], holdings_count: int) -> str:
        """
        포트폴리오 요약 포맷 (Markdown)
        
        Args:
            summary: 포트폴리오 요약 딕셔너리
            holdings_count: 보유 종목 수
        
        Returns:
            포맷된 Markdown 문자열
        """
        message = "*💼 포트폴리오 현황*\n"
        message += f"총 평가액: `{summary['total_value']:,.0f}원`\n"
        message += f"총 매입액: `{summary['total_cost']:,.0f}원`\n"
        message += f"평가손익: {PortfolioHelper.format_return(summary['return_amount'], summary['return_pct'])}\n"
        message += f"보유 종목: `{holdings_count}개`\n"
        
        return message


def load_portfolio_safe() -> Dict[str, Any]:
    """
    안전하게 포트폴리오 로드 (에러 시 빈 딕셔너리 반환)
    
    Returns:
        포트폴리오 데이터 또는 빈 딕셔너리
    """
    try:
        helper = PortfolioHelper()
        return helper.load_full_data()
    except Exception as e:
        logger.warning(f"포트폴리오 로드 실패: {e}")
        return {
            'summary': {},
            'holdings_count': 0,
            'holdings_codes': [],
            'holdings_detail': None
        }
