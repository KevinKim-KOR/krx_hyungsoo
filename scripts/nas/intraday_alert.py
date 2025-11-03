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
        
        # KOSPI 200 구성 종목 (간단히 일부만)
        # 실제로는 유니버스에서 가져오는 것이 좋음
        codes = ['005930', '000660', '035420', '051910', '035720']  # 삼성전자, SK하이닉스 등
        
        alerts = []
        
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
                
                # 등락률 계산
                change_pct = df.iloc[-1]['등락률']
                
                # 급등/급락 기준 (3% 이상)
                if abs(change_pct) >= 3.0:
                    name = stock.get_market_ticker_name(code)
                    price = df.iloc[-1]['종가']
                    
                    alerts.append({
                        'code': code,
                        'name': name,
                        'change': change_pct,
                        'price': price
                    })
            
            except Exception as e:
                logger.warning(f"종목 체크 실패 [{code}]: {e}")
                continue
        
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
        message += f"📅 {date.today()}\n\n"
        
        for alert in alerts[:5]:  # 최대 5개
            emoji = "🔴" if alert['change'] < 0 else "🟢"
            message += f"{emoji} `{alert['code']}` {alert['name']}\n"
            message += f"   변동: {alert['change']:+.2f}%\n"
            message += f"   가격: {alert['price']:,.0f}원\n\n"
        
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
