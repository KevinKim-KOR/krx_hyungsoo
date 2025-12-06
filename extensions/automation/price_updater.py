# -*- coding: utf-8 -*-
"""
extensions/automation/price_updater.py
포트폴리오 가격 업데이트 모듈
"""
import logging
from datetime import date
import pandas as pd
import pykrx.stock as stock
from extensions.automation.portfolio_helper import PortfolioHelper

logger = logging.getLogger(__name__)

class PriceUpdater:
    """포트폴리오 가격 업데이트 클래스"""
    
    def __init__(self):
        self.portfolio_helper = PortfolioHelper()
        
    def update_prices(self) -> dict:
        """
        포트폴리오의 현재가를 실시간/당일 종가로 업데이트
        
        Returns:
            업데이트된 포트폴리오 데이터 (summary, holdings_detail 등)
        """
        try:
            # 1. 포트폴리오 로드
            data = self.portfolio_helper.load_full_data()
            if not data or data.get('holdings_detail') is None:
                logger.warning("포트폴리오 데이터가 없습니다.")
                return data
            
            holdings_detail = data['holdings_detail']
            
            # 2. 시장 데이터 가져오기 (오늘)
            today = date.today().strftime("%Y%m%d")
            market_df = stock.get_market_ohlcv_by_ticker(today)
            
            # 장 시작 전/휴일 등으로 데이터 없으면 어제 날짜 시도
            if market_df.empty:
                yesterday = (pd.Timestamp(today) - pd.tseries.offsets.BusinessDay(1)).strftime("%Y%m%d")
                market_df = stock.get_market_ohlcv_by_ticker(yesterday)
                logger.info(f"금일 시세 미생성, 전일 종가 사용 ({yesterday})")
            
            # 3. 가격 업데이트 및 요약 재계산
            total_value = 0
            total_cost = 0
            
            # DataFrame 순회하며 업데이트
            for idx, row in holdings_detail.iterrows():
                code = row['code']
                quantity = row['quantity']
                avg_price = row['avg_price']
                
                # 수량이 0 이하면 계산 제외 (보유 안함)
                if quantity <= 0:
                    continue
                
                # 현재가 조회
                current_price = 0
                if code in market_df.index:
                    current_price = float(market_df.loc[code]['종가'])
                
                # 만약 0원이면 개별 조회 시도 (혹시 누락되었을 경우)
                if current_price <= 0:
                    try:
                        df = stock.get_market_ohlcv_by_date(today, today, code)
                        if not df.empty:
                            current_price = float(df.iloc[0]['종가'])
                    except:
                        pass
                
                # 여전히 0원이면 기존 값 유지
                if current_price <= 0:
                    current_price = float(row.get('current_price', avg_price))
                    if current_price <= 0: current_price = avg_price # 최후의 수단
                
                # 값 갱신
                val = current_price * quantity
                cost = avg_price * quantity
                
                holdings_detail.at[idx, 'current_price'] = current_price
                holdings_detail.at[idx, 'current_value'] = val
                holdings_detail.at[idx, 'return_amount'] = val - cost
                holdings_detail.at[idx, 'return_pct'] = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                
                total_value += val
                total_cost += cost
            
            # 요약 정보 갱신
            summary = data['summary']
            summary['total_value'] = total_value
            summary['total_cost'] = total_cost
            summary['return_amount'] = total_value - total_cost
            summary['return_pct'] = (summary['return_amount'] / total_cost * 100) if total_cost > 0 else 0
            
            # 데이터 반환
            data['holdings_detail'] = holdings_detail
            data['summary'] = summary
            
            logger.info("포트폴리오 가격 업데이트 완료")
            return data
            
        except Exception as e:
            logger.error(f"가격 업데이트 실패: {e}", exc_info=True)
            return self.portfolio_helper.load_full_data() # 실패 시 원본 반환
