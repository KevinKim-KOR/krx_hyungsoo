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


def get_etf_universe():
    """ETF 유니버스 가져오기 (레버리지/인버스 제외)"""
    import pykrx.stock as stock
    
    # 주요 ETF 리스트 (수동 관리 - 가장 안정적)
    # Jason 친구 코드 및 config/universe.yaml 참고
    all_etfs = [
        # 대형주 ETF
        '069500',  # KODEX 200
        '102110',  # TIGER 200
        '114800',  # KODEX 인버스 (제외 예정)
        '122630',  # KODEX 레버리지 (제외 예정)
        
        # 코스닥 ETF
        '229200',  # KODEX 코스닥150
        '233740',  # KODEX 코스닥150레버리지 (제외 예정)
        '251340',  # KODEX 코스닥150선물인버스 (제외 예정)
        
        # 섹터 ETF
        '091160',  # KODEX 반도체
        '091180',  # KODEX 자동차
        '091170',  # KODEX 은행
        '102780',  # KODEX 삼성그룹
        '117460',  # KODEX 2차전지산업
        '364980',  # KODEX 2차전지산업 (신규)
        
        # 해외 ETF
        '272560',  # KODEX 미국S&P500TR
        '379800',  # KODEX 미국나스닥100TR
        '360750',  # TIGER 미국S&P500
        '133690',  # TIGER 미국나스닥100
        
        # 채권 ETF (제외 예정)
        '148070',  # KOSEF 국고채10년
        '114260',  # KODEX 국고채3년
    ]
    
    logger.info(f"기본 ETF 리스트: {len(all_etfs)}개")
    
    # 레버리지/인버스/채권 ETF 제외 (코드 기반)
    exclude_codes = [
        '114800',  # KODEX 인버스
        '122630',  # KODEX 레버리지
        '233740',  # KODEX 코스닥150레버리지
        '251340',  # KODEX 코스닥150선물인버스
        '148070',  # KOSEF 국고채10년
        '114260',  # KODEX 국고채3년
    ]
    
    # 제외 키워드 (종목명 체크용)
    exclude_keywords = [
        '레버리지', '인버스', '곱버스', 'LEVERAGED', 'INVERSE',
        '선물', 'FUTURES', '채권', 'BOND', '커버드콜', 'COVERED'
    ]
    
    filtered_etfs = []
    for code in all_etfs:
        # 제외 코드 체크
        if code in exclude_codes:
            logger.debug(f"제외 (코드): {code}")
            continue
        
        try:
            name = stock.get_market_ticker_name(code)
            # 제외 키워드 체크
            if any(kw in name for kw in exclude_keywords):
                logger.debug(f"제외 (키워드): {code} {name}")
                continue
            filtered_etfs.append({'code': code, 'name': name})
        except Exception as e:
            # 종목명 조회 실패해도 코드만으로 추가 (나중에 다시 조회)
            logger.warning(f"종목명 조회 실패 [{code}]: {e}, 코드만 추가")
            filtered_etfs.append({'code': code, 'name': None})
    
    logger.info(f"필터링 후 ETF: {len(filtered_etfs)}개")
    return filtered_etfs


def check_intraday_movements():
    """장중 급등/급락 체크 (ETF 전용)"""
    try:
        import pykrx.stock as stock
        from datetime import datetime
        
        today = date.today()
        
        # ETF 유니버스 가져오기
        etf_universe = get_etf_universe()
        
        if not etf_universe:
            logger.warning("ETF 유니버스가 비어있습니다.")
            return []
        
        alerts = []
        checked = 0
        
        for etf in etf_universe:
            code = etf['code']
            name = etf.get('name')
            
            try:
                # 종목명이 없으면 다시 조회
                if not name:
                    try:
                        name = stock.get_market_ticker_name(code)
                    except:
                        name = f"ETF_{code}"  # 조회 실패 시 기본 이름
                
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
                
                # 급등/급락 기준 (ETF는 1.5% 이상)
                if abs(change_pct) >= 1.5:
                    price = df.iloc[-1]['종가']
                    volume = df.iloc[-1]['거래량']
                    value = price * volume  # 거래대금
                    
                    alerts.append({
                        'code': code,
                        'name': name,
                        'change': change_pct,
                        'price': price,
                        'volume': volume,
                        'value': value
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
        message = "*[장중 알림] ETF 급등/급락*\n\n"
        message += f"📅 {date.today()}\n"
        message += f"📊 총 {len(alerts)}개 ETF 발견\n\n"
        
        # 급등 ETF
        up_alerts = [a for a in alerts if a['change'] > 0][:10]
        if up_alerts:
            message += "*🟢 급등 ETF*\n"
            for alert in up_alerts:
                message += f"• {alert['name']} ({alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래대금: {alert['value']/1e8:.1f}억원\n\n"
        
        # 급락 ETF
        down_alerts = [a for a in alerts if a['change'] < 0][:10]
        if down_alerts:
            message += "*🔴 급락 ETF*\n"
            for alert in down_alerts:
                message += f"• {alert['name']} ({alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래대금: {alert['value']/1e8:.1f}억원\n\n"
        
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
