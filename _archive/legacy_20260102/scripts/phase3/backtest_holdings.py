#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/phase3/backtest_holdings.py
실제 보유 종목 백테스트 및 손절 분석
"""
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pykrx import stock


class HoldingsBacktest:
    """실제 보유 종목 백테스트"""
    
    def __init__(self, holdings_file: str, entry_dates: Optional[Dict[str, str]] = None):
        """
        Args:
            holdings_file: 보유 종목 JSON 파일 경로
            entry_dates: 매입일 정보 (code: 'YYYY-MM-DD')
        """
        self.holdings_file = holdings_file
        self.entry_dates = entry_dates or {}
        self.holdings = self.load_holdings()
        
    def load_holdings(self) -> List[Dict]:
        """보유 종목 로드"""
        with open(self.holdings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['holdings']
    
    def get_price_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        종목 가격 히스토리 조회
        
        Args:
            code: 종목 코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            
        Returns:
            가격 데이터 DataFrame
        """
        try:
            # 6자리 코드만 pykrx 지원
            if len(code) != 6:
                print(f"  ⚠️ {code}: ETF 코드는 백테스트 미지원 (pykrx 제한)")
                return pd.DataFrame()
            
            df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
            
            if df.empty:
                print(f"  ⚠️ {code}: 데이터 없음")
                return pd.DataFrame()
            
            # 수익률 계산
            df['return_pct'] = ((df['종가'] / df['종가'].iloc[0]) - 1) * 100
            
            return df
            
        except Exception as e:
            print(f"  ❌ {code} 가격 조회 실패: {e}")
            return pd.DataFrame()
    
    def find_optimal_stop_loss(
        self, 
        df: pd.DataFrame, 
        entry_price: float,
        current_price: float,
        entry_date: Optional[str] = None,
        stop_loss_levels: List[int] = [7, 10, 15, 20, 25, 30]
    ) -> Optional[Dict]:
        """
        최적 손절 시점 찾기
        
        Args:
            df: 가격 데이터
            entry_price: 매입가
            current_price: 현재가
            entry_date: 매입일 (YYYY-MM-DD)
            stop_loss_levels: 손절 비율 리스트 (%)
            
        Returns:
            최적 손절 정보 또는 None
        """
        # 현재 손실률
        current_return = ((current_price / entry_price) - 1) * 100
        
        # 매입일 이후 데이터만 사용
        if entry_date:
            try:
                entry_datetime = pd.to_datetime(entry_date)
                df = df[df.index >= entry_datetime]
                if df.empty:
                    print(f"  ⚠️ 매입일 {entry_date} 이후 데이터 없음")
                    return None
            except:
                pass
        
        # 손절 시점 찾기 (매입가 기준)
        for stop_loss_pct in stop_loss_levels:
            threshold = entry_price * (1 - stop_loss_pct / 100)
            
            # 손절 시점 찾기
            stop_mask = df['종가'] <= threshold
            
            if stop_mask.any():
                stop_date = df[stop_mask].index[0]
                stop_price = df.loc[stop_date, '종가']
                stop_return = ((stop_price / entry_price) - 1) * 100
                
                # 절약 금액 계산 (현재 손실 대비)
                # 예: 현재 -40%, 손절 -15% → 절약 +25%p
                saved_pct = stop_return - current_return
                
                # 손절이 현재보다 나은 경우만 반환
                if saved_pct > 0:
                    return {
                        'stop_loss_pct': stop_loss_pct,
                        'stop_date': stop_date.strftime('%Y-%m-%d'),
                        'stop_price': stop_price,
                        'stop_return': stop_return,
                        'saved_pct': saved_pct
                    }
        
        return None  # 손절 없이 보유가 최선
    
    def analyze_stock(self, holding: Dict) -> Dict:
        """
        개별 종목 분석
        
        Args:
            holding: 보유 종목 정보
            
        Returns:
            분석 결과
        """
        code = holding['code']
        name = holding['name']
        avg_price = holding['avg_price']
        quantity = holding['quantity']
        current_price = holding['current_price']
        current_return = holding['return_pct']
        
        print(f"\n분석 중: {name} ({code})")
        print(f"  매입가: {avg_price:,.0f}원 | 현재가: {current_price:,.0f}원 | 수익률: {current_return:+.2f}%")
        
        # 손실 종목만 분석
        if current_return >= 0:
            print(f"  ✅ 수익 종목 - 손절 분석 불필요")
            return {
                'code': code,
                'name': name,
                'avg_price': avg_price,
                'quantity': quantity,
                'current_price': current_price,
                'current_return': current_return,
                'analysis': 'profit',
                'optimal_stop': None
            }
        
        # 매입일 확인
        entry_date = self.entry_dates.get(code)
        
        # 가격 히스토리 조회 (매입일부터 또는 최근 5년)
        end_date = datetime.now().strftime('%Y%m%d')
        if entry_date:
            # 매입일부터 조회
            start_date = pd.to_datetime(entry_date).strftime('%Y%m%d')
            print(f"  📅 매입일: {entry_date}")
        else:
            # 매입일 정보 없으면 5년 전부터 조회
            start_date = (datetime.now() - timedelta(days=1825)).strftime('%Y%m%d')
            print(f"  ⚠️ 매입일 정보 없음 (5년 전부터 조회)")
        
        df = self.get_price_history(code, start_date, end_date)
        
        if df.empty:
            return {
                'code': code,
                'name': name,
                'avg_price': avg_price,
                'quantity': quantity,
                'current_price': current_price,
                'current_return': current_return,
                'analysis': 'no_data',
                'optimal_stop': None
            }
        
        # 최적 손절 시점 찾기
        optimal_stop = self.find_optimal_stop_loss(df, avg_price, current_price, entry_date)
        
        if optimal_stop:
            saved_amount = (optimal_stop['saved_pct'] / 100) * (avg_price * quantity)
            optimal_stop['saved_amount'] = saved_amount
            
            print(f"  🎯 최적 손절: {optimal_stop['stop_date']}")
            print(f"     손절가: {optimal_stop['stop_price']:,.0f}원 ({optimal_stop['stop_return']:+.2f}%)")
            print(f"     절약: {saved_amount:+,.0f}원 ({optimal_stop['saved_pct']:+.2f}%p)")
        else:
            print(f"  ⚠️ 손절 없이 보유 (현재 전략 유지)")
        
        return {
            'code': code,
            'name': name,
            'avg_price': avg_price,
            'quantity': quantity,
            'current_price': current_price,
            'current_return': current_return,
            'analysis': 'loss',
            'optimal_stop': optimal_stop
        }
    
    def run_all(self) -> List[Dict]:
        """전체 보유 종목 분석"""
        print("=" * 60)
        print("실제 보유 종목 백테스트 시작")
        print("=" * 60)
        print(f"총 {len(self.holdings)}개 종목 분석")
        
        results = []
        
        for holding in self.holdings:
            result = self.analyze_stock(holding)
            results.append(result)
        
        return results
    
    def generate_report(self, results: List[Dict]) -> str:
        """
        분석 리포트 생성
        
        Args:
            results: 분석 결과 리스트
            
        Returns:
            리포트 텍스트
        """
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("실제 보유 종목 백테스트 결과")
        lines.append("=" * 60)
        
        # 손실 종목만 필터링
        loss_results = [r for r in results if r['analysis'] == 'loss' and r['optimal_stop']]
        
        if not loss_results:
            lines.append("\n✅ 손절 대상 종목 없음 (모든 종목 수익 중)")
            return "\n".join(lines)
        
        lines.append(f"\n📊 손절 분석 대상: {len(loss_results)}개 종목")
        lines.append("")
        
        total_saved = 0
        
        for i, result in enumerate(loss_results, 1):
            stop = result['optimal_stop']
            
            lines.append(f"{i}. {result['name']} ({result['code']})")
            lines.append(f"   매입가: {result['avg_price']:,.0f}원 × {result['quantity']:.0f}주 = {result['avg_price'] * result['quantity']:,.0f}원")
            lines.append(f"   현재가: {result['current_price']:,.0f}원 ({result['current_return']:+.2f}%)")
            lines.append("")
            lines.append(f"   🎯 최적 손절:")
            lines.append(f"      날짜: {stop['stop_date']}")
            lines.append(f"      가격: {stop['stop_price']:,.0f}원 ({stop['stop_return']:+.2f}%)")
            lines.append(f"      절약: {stop['saved_amount']:+,.0f}원 ({stop['saved_pct']:+.2f}%p) 💰")
            lines.append("")
            
            total_saved += stop['saved_amount']
        
        lines.append("=" * 60)
        lines.append(f"총 절약 가능 금액: {total_saved:+,.0f}원 🎉")
        lines.append("=" * 60)
        
        return "\n".join(lines)


def main():
    """메인 실행"""
    # 보유 종목 파일 경로
    holdings_file = PROJECT_ROOT / 'data' / 'portfolio' / 'holdings.json'
    
    # 매입일 정보 (사용자 제공)
    entry_dates = {
        '001510': '2020-07-01',  # SK증권 (2020년 여름)
        '221840': '2020-10-01',  # 하이즈항공 (2020년 가을)
        '323410': '2020-07-01',  # 카카오뱅크 (2020년 여름)
    }
    
    # 백테스트 실행
    backtest = HoldingsBacktest(holdings_file, entry_dates)
    results = backtest.run_all()
    
    # 리포트 생성
    report = backtest.generate_report(results)
    print(report)
    
    # 결과 저장
    output_dir = PROJECT_ROOT / 'data' / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'holdings_backtest_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 결과 저장: {output_file}")
    
    # 리포트 저장
    report_file = output_dir / 'holdings_backtest_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 리포트 저장: {report_file}")


if __name__ == '__main__':
    main()
