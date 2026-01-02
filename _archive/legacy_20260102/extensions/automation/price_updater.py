# -*- coding: utf-8 -*-
"""
extensions/automation/price_updater.py
포트폴리오 가격 업데이트 모듈
"""
import logging
from datetime import date, datetime
import pandas as pd
import pykrx.stock as stock
from extensions.automation.portfolio_helper import PortfolioHelper
from core.db import SessionLocal, Holdings

logger = logging.getLogger(__name__)

class PriceUpdater:
    """포트폴리오 가격 업데이트 클래스"""
    
    def __init__(self):
        self.portfolio_helper = PortfolioHelper()
        self.session = SessionLocal()
        
    def __del__(self):
        if self.session:
            self.session.close()
        
    def update_prices(self) -> dict:
        """
        포트폴리오의 현재가를 실시간/당일 종가로 업데이트하고 DB에 저장
        
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
            
            # 2. 시장 데이터 가져오기 (가장 최근 영업일 찾기)
            today = date.today()
            market_df = pd.DataFrame()
            target_date = today.strftime("%Y%m%d")
            
            # 최대 7일 전까지 조회하며 데이터 있는 날짜 찾기
            for i in range(7):
                check_date = (today - pd.Timedelta(days=i)).strftime("%Y%m%d")
                try:
                    df = stock.get_market_ohlcv_by_ticker(check_date)
                    if not df.empty and len(df) > 100: # 충분한 데이터가 있는지 확인
                        market_df = df
                        target_date = check_date
                        logger.info(f"시세 데이터 로드 성공: {target_date}")
                        break
                except Exception as e:
                    logger.warning(f"{check_date} 시세 조회 실패: {e}")
                    continue
            
            if market_df.empty:
                logger.error("최근 7일간 유효한 시세 데이터를 찾을 수 없습니다.")
                # 시세 조회 실패 시에도 DB에 저장된 값이 있으면 사용해야 함 (아래 로직에서 처리)
            
            # 3. 가격 업데이트 및 DB 저장
            total_value = 0
            total_cost = 0
            
            # DB 세션 새로고침
            db_holdings = {h.code: h for h in self.session.query(Holdings).all()}
            
            # DataFrame 순회하며 업데이트
            for idx, row in holdings_detail.iterrows():
                code = row['code']
                quantity = row['quantity']
                avg_price = row['avg_price']
                
                # 수량이 0 이하면 계산 제외
                if quantity <= 0:
                    continue
                
                # 현재가 결정 로직
                current_price = 0
                
                # 1) 시장 데이터에서 조회
                if not market_df.empty and code in market_df.index:
                    current_price = float(market_df.loc[code]['종가'])
                
                # 2) 실패 시 개별 조회 시도
                if current_price <= 0:
                    try:
                        df = stock.get_market_ohlcv_by_date(target_date, target_date, code)
                        if not df.empty:
                            current_price = float(df.iloc[0]['종가'])
                    except:
                        pass
                
                # 3) DB에 저장된 기존 가격 사용 (Fallback)
                if current_price <= 0:
                    if code in db_holdings and db_holdings[code].current_price:
                         current_price = db_holdings[code].current_price
                         logger.info(f"{code} 시세 조회 실패, DB 저장된 가격 사용: {current_price}")

                # 4) 그래도 없으면 매수가 사용 (최후의 수단)
                if current_price <= 0:
                    current_price = avg_price
                    # logger.warning(f"{code} 가격 정보 없음. 매수가로 대체.")
                
                # DB에 가격 업데이트
                if code in db_holdings and current_price > 0:
                    db_holdings[code].current_price = current_price
                    # update_at은 자동 갱신됨
                
                # 값 갱신
                val = current_price * quantity
                cost = avg_price * quantity
                
                holdings_detail.at[idx, 'current_price'] = current_price
                holdings_detail.at[idx, 'current_value'] = val
                holdings_detail.at[idx, 'return_amount'] = val - cost
                holdings_detail.at[idx, 'return_pct'] = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                
                total_value += val
                total_cost += cost
            
            # DB 커밋
            try:
                self.session.commit()
                logger.info("DB에 최신 가격 저장 완료")
            except Exception as e:
                self.session.rollback()
                logger.error(f"DB 저장 실패: {e}")

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
