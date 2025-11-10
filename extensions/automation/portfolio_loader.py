# -*- coding: utf-8 -*-
"""
extensions/automation/portfolio_loader.py
포트폴리오 데이터 로더

실제 보유 종목 데이터를 로드하여 리포트 및 백테스트에 활용
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
from datetime import datetime


class PortfolioLoader:
    """포트폴리오 데이터 로더"""
    
    def __init__(self, portfolio_file: str = None):
        """
        Args:
            portfolio_file: 포트폴리오 JSON 파일 경로 (기본: data/portfolio/holdings.json)
        """
        if portfolio_file is None:
            # 프로젝트 루트 기준 경로
            project_root = Path(__file__).parent.parent.parent
            portfolio_file = project_root / "data" / "portfolio" / "holdings.json"
        
        self.portfolio_file = Path(portfolio_file)
        
        if not self.portfolio_file.exists():
            raise FileNotFoundError(f"포트폴리오 파일을 찾을 수 없습니다: {self.portfolio_file}")
    
    def load_portfolio(self) -> dict:
        """포트폴리오 전체 데이터 로드"""
        with open(self.portfolio_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_holdings_codes(self) -> List[str]:
        """보유 종목 코드 리스트 반환"""
        portfolio = self.load_portfolio()
        return [h['code'] for h in portfolio['holdings']]
    
    def get_holdings_detail(self) -> pd.DataFrame:
        """보유 종목 상세 정보 DataFrame 반환"""
        portfolio = self.load_portfolio()
        df = pd.DataFrame(portfolio['holdings'])
        
        # broker 필드가 없는 경우 처리
        if 'broker' not in df.columns:
            df['broker'] = ''
        
        return df
    
    def get_portfolio_value(self) -> float:
        """총 평가액 반환"""
        portfolio = self.load_portfolio()
        return sum(h['current_value'] for h in portfolio['holdings'])
    
    def get_total_cost(self) -> float:
        """총 매입액 반환"""
        portfolio = self.load_portfolio()
        return sum(h['total_cost'] for h in portfolio['holdings'])
    
    def get_total_return(self) -> Tuple[float, float]:
        """
        총 평가손익 반환
        
        Returns:
            (평가손익 금액, 수익률%)
        """
        portfolio = self.load_portfolio()
        total_cost = sum(h['total_cost'] for h in portfolio['holdings'])
        total_value = sum(h['current_value'] for h in portfolio['holdings'])
        return_amount = total_value - total_cost
        return_pct = (return_amount / total_cost * 100) if total_cost > 0 else 0
        return return_amount, return_pct
    
    def get_top_performers(self, n: int = 5) -> pd.DataFrame:
        """
        수익률 상위 N개 종목 반환
        
        Args:
            n: 반환할 종목 수
            
        Returns:
            상위 N개 종목 DataFrame
        """
        df = self.get_holdings_detail()
        return df.nlargest(n, 'return_pct')[['name', 'code', 'return_amount', 'return_pct']]
    
    def get_worst_performers(self, n: int = 5) -> pd.DataFrame:
        """
        수익률 하위 N개 종목 반환
        
        Args:
            n: 반환할 종목 수
            
        Returns:
            하위 N개 종목 DataFrame
        """
        df = self.get_holdings_detail()
        return df.nsmallest(n, 'return_pct')[['name', 'code', 'return_amount', 'return_pct']]
    
    def get_holdings_by_broker(self) -> Dict[str, pd.DataFrame]:
        """
        증권사별 보유 종목 반환
        
        Returns:
            {증권사명: DataFrame} 딕셔너리
        """
        df = self.get_holdings_detail()
        
        # broker 필드가 없거나 빈 값인 경우 처리
        if 'broker' not in df.columns or df['broker'].isna().all():
            return {'전체': df}
        
        # 증권사별 그룹화
        result = {}
        for broker in df['broker'].unique():
            if broker:  # 빈 문자열 제외
                result[broker] = df[df['broker'] == broker]
        
        return result
    
    def get_portfolio_summary(self) -> dict:
        """
        포트폴리오 요약 정보 반환
        
        Returns:
            {
                'total_value': 총 평가액,
                'total_cost': 총 매입액,
                'return_amount': 평가손익,
                'return_pct': 수익률,
                'holdings_count': 보유 종목 수,
                'last_updated': 마지막 업데이트 시간
            }
        """
        portfolio = self.load_portfolio()
        total_cost = sum(h['total_cost'] for h in portfolio['holdings'])
        total_value = sum(h['current_value'] for h in portfolio['holdings'])
        return_amount = total_value - total_cost
        return_pct = (return_amount / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'return_amount': return_amount,
            'return_pct': return_pct,
            'holdings_count': len(portfolio['holdings']),
            'last_updated': portfolio.get('last_updated', '')
        }
    
    def get_holdings_by_category(self) -> Dict[str, List[dict]]:
        """
        카테고리별 보유 종목 분류
        
        Returns:
            {
                '국내 ETF': [...],
                '해외 ETF': [...],
                '개별 주식': [...]
            }
        """
        df = self.get_holdings_detail()
        
        result = {
            '국내 ETF': [],
            '해외 ETF': [],
            '개별 주식': []
        }
        
        for _, row in df.iterrows():
            code = row['code']
            name = row['name']
            
            # ETF 판별 (코드가 6자리 숫자로 시작하면 개별 주식, 아니면 ETF)
            if code.isdigit() and len(code) == 6:
                # 개별 주식
                result['개별 주식'].append(row.to_dict())
            else:
                # ETF - 이름으로 국내/해외 구분
                if any(keyword in name for keyword in ['미국', '글로벌', '베트남', '차이나']):
                    result['해외 ETF'].append(row.to_dict())
                else:
                    result['국내 ETF'].append(row.to_dict())
        
        return result


# 테스트 코드
if __name__ == "__main__":
    loader = PortfolioLoader()
    
    print("=" * 60)
    print("포트폴리오 요약")
    print("=" * 60)
    summary = loader.get_portfolio_summary()
    print(f"총 평가액: {summary['total_value']:,.0f}원")
    print(f"총 매입액: {summary['total_cost']:,.0f}원")
    print(f"평가손익: {summary['return_amount']:+,.0f}원 ({summary['return_pct']:+.2f}%)")
    print(f"보유 종목: {summary['holdings_count']}개")
    print()
    
    print("=" * 60)
    print("수익률 Top 5")
    print("=" * 60)
    top5 = loader.get_top_performers(5)
    for idx, row in top5.iterrows():
        print(f"{row['name']:30s} {row['return_amount']:+10,.0f}원 ({row['return_pct']:+6.2f}%)")
    print()
    
    print("=" * 60)
    print("손실 Top 5")
    print("=" * 60)
    worst5 = loader.get_worst_performers(5)
    for idx, row in worst5.iterrows():
        print(f"{row['name']:30s} {row['return_amount']:+10,.0f}원 ({row['return_pct']:+6.2f}%)")
    print()
    
    print("=" * 60)
    print("증권사별 보유 종목")
    print("=" * 60)
    by_broker = loader.get_holdings_by_broker()
    for broker, df in by_broker.items():
        broker_value = df['current_value'].sum()
        broker_return = df['return_amount'].sum()
        broker_return_pct = (broker_return / df['total_cost'].sum() * 100) if df['total_cost'].sum() > 0 else 0
        print(f"\n{broker}: {len(df)}개 종목")
        print(f"  평가액: {broker_value:,.0f}원")
        print(f"  손익: {broker_return:+,.0f}원 ({broker_return_pct:+.2f}%)")
    print()
    
    print("=" * 60)
    print("카테고리별 보유 종목")
    print("=" * 60)
    by_category = loader.get_holdings_by_category()
    for category, holdings in by_category.items():
        if holdings:
            category_value = sum(h['current_value'] for h in holdings)
            category_return = sum(h['return_amount'] for h in holdings)
            category_cost = sum(h['total_cost'] for h in holdings)
            category_return_pct = (category_return / category_cost * 100) if category_cost > 0 else 0
            print(f"\n{category}: {len(holdings)}개 종목")
            print(f"  평가액: {category_value:,.0f}원")
            print(f"  손익: {category_return:+,.0f}원 ({category_return_pct:+.2f}%)")
