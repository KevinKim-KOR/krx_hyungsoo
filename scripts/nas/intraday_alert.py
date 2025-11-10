#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/intraday_alert.py
장중 급등/급락 알림
"""
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.notification.telegram_sender import TelegramSender
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


def check_intraday_movements():
    """장중 급등/급락 체크"""
    try:
        import pykrx.stock as stock
        from datetime import datetime
        
        today = date.today()
        
        # KOSPI 200 + KOSDAQ 상위 종목 가져오기
        try:
            # KOSPI 200
            kospi_codes = stock.get_market_ticker_list(date=today, market="KOSPI200")
            logger.info(f"KOSPI 200: {len(kospi_codes)}개")
            
            # KOSDAQ 상위 50개 추가 (변동성 큼)
            try:
                kosdaq_all = stock.get_market_ticker_list(date=today, market="KOSDAQ")
                # 시가총액 기준 상위 50개 (간단히 앞 50개)
                kosdaq_codes = kosdaq_all[:50]
                logger.info(f"KOSDAQ 상위: {len(kosdaq_codes)}개")
            except:
                kosdaq_codes = []
            
            codes = kospi_codes + kosdaq_codes
            logger.info(f"총 체크 대상: {len(codes)}개")
        except Exception as e:
            logger.warning(f"종목 리스트 가져오기 실패, 기본 종목 사용: {e}")
            # 기본 종목 (대형주 위주)
            codes = [
                '005930', '000660', '035420', '051910', '035720',  # 삼성전자, SK하이닉스, NAVER, LG화학, 카카오
                '005380', '068270', '207940', '006400', '005490',  # 현대차, 셀트리온, 삼성바이오, 삼성SDI, POSCO
                '028260', '105560', '055550', '012330', '096770',  # 삼성물산, KB금융, 신한지주, 현대모비스, SK이노베이션
                '017670', '034020', '034220', '003550', '015760',  # SK텔레콤, 두산에너빌리티, LG디스플레이, LG, 한국전력
                '018260', '032830', '009150', '010130', '011200'   # 삼성에스디에스, 삼성생명, 삼성전기, 고려아연, HMM
            ]
        
        alerts = []
        checked = 0
        
        for code in codes:
            try:
                # 오늘 데이터 (장중)
                df = stock.get_market_ohlcv_by_date(
                    fromdate=today.strftime('%Y%m%d'),
                    todate=today.strftime('%Y%m%d'),
                    ticker=code
                )
                
                if df.empty:
                    continue
                
                checked += 1
                
                # 등락률 계산
                change_pct = df.iloc[-1]['등락률']
                
                # 급등/급락 기준 (1.5% 이상으로 완화)
                if abs(change_pct) >= 1.5:
                    name = stock.get_market_ticker_name(code)
                    price = df.iloc[-1]['종가']
                    volume = df.iloc[-1]['거래량']
                    
                    alerts.append({
                        'code': code,
                        'name': name,
                        'change': change_pct,
                        'price': price,
                        'volume': volume
                    })
            
            except Exception as e:
                logger.debug(f"종목 체크 실패 [{code}]: {e}")
                continue
        
        logger.info(f"체크 완료: {checked}개 종목, 알림 대상: {len(alerts)}개")
        
        # 등락률 절대값 기준으로 정렬
        alerts.sort(key=lambda x: abs(x['change']), reverse=True)
        
        return alerts
    
    except Exception as e:
        logger.error(f"장중 체크 실패: {e}")
        return []


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("장중 알림 체크 시작")
    logger.info("=" * 60)
    
    try:
        # 장중 체크
        alerts = check_intraday_movements()
        
        if not alerts:
            logger.info("알림 대상 없음")
            return 0
        
        # 메시지 생성
        message = "*[장중 알림] 급등/급락*\n\n"
        message += f"📅 {date.today()}\n"
        message += f"🔍 총 {len(alerts)}개 종목 발견\n\n"
        
        # 급등 종목
        up_alerts = [a for a in alerts if a['change'] > 0][:10]
        if up_alerts:
            message += "*🟢 급등 종목*\n"
            for alert in up_alerts:
                message += f"• {alert['name']}(코드: {alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래량: {alert['volume']:,}주\n\n"
        
        # 급락 종목
        down_alerts = [a for a in alerts if a['change'] < 0][:10]
        if down_alerts:
            message += "*🔴 급락 종목*\n"
            for alert in down_alerts:
                message += f"• {alert['name']}(코드: {alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래량: {alert['volume']:,}주\n\n"
        
        # 텔레그램 전송
        sender = TelegramSender()
        success = sender.send_custom(message, parse_mode='Markdown')
        
        if success:
            logger.info(f"✅ 장중 알림 전송 성공: {len(alerts)}개")
        else:
            logger.warning("⚠️ 장중 알림 전송 실패")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ 장중 알림 실패: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
