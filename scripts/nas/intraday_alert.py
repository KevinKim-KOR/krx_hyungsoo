#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/intraday_alert.py
장중 급등/급락 알림 (보유 종목 우선)
"""
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.notification.telegram_sender import TelegramSender
from extensions.automation.portfolio_loader import PortfolioLoader
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)

# 급등/급락 기준 (특성별 차별화)
THRESHOLDS = {
    'leverage': 3.0,      # 레버리지 ETF: 3% 이상
    'sector': 2.0,        # 섹터 ETF: 2% 이상
    'index': 1.5,         # 지수 ETF: 1.5% 이상
    'overseas': 1.5,      # 해외 ETF: 1.5% 이상
    'default': 2.0        # 기본: 2% 이상
}

# 최소 거래대금 (의미 있는 알림만)
MIN_TRADE_VALUE = 50e8  # 50억원 이상


def get_etf_universe():
    """ETF 유니버스 가져오기 (레버리지/인버스 제외)"""
    # ETF 코드와 이름 매핑 (수동 관리)
    etf_map = {
        # 대형주 ETF
        '069500': 'KODEX 200',
        '102110': 'TIGER 200',
        '114800': 'KODEX 인버스',  # 제외
        '122630': 'KODEX 레버리지',  # 제외
        
        # 코스닥 ETF
        '229200': 'KODEX 코스닥150',
        '233740': 'KODEX 코스닥150레버리지',  # 제외
        '251340': 'KODEX 코스닥150선물인버스',  # 제외
        
        # 섹터 ETF
        '091160': 'KODEX 반도체',
        '091180': 'KODEX 자동차',
        '091170': 'KODEX 은행',
        '102780': 'KODEX 삼성그룹',
        '117460': 'KODEX 2차전지산업',
        '364980': 'KODEX 2차전지산업',
        
        # 해외 ETF
        '272560': 'KODEX 미국S&P500TR',
        '379800': 'KODEX 미국나스닥100TR',
        '360750': 'TIGER 미국S&P500',
        '133690': 'TIGER 미국나스닥100',
        
        # 채권 ETF (제외)
        '148070': 'KOSEF 국고채10년',  # 제외
        '114260': 'KODEX 국고채3년',  # 제외
    }
    
    logger.info(f"기본 ETF 리스트: {len(etf_map)}개")
    print(f"기본 ETF 리스트: {len(etf_map)}개")
    
    # 레버리지/인버스/채권 ETF 제외 (코드 기반)
    exclude_codes = [
        '114800',  # KODEX 인버스
        '122630',  # KODEX 레버리지
        '233740',  # KODEX 코스닥150레버리지
        '251340',  # KODEX 코스닥150선물인버스
        '148070',  # KOSEF 국고채10년
        '114260',  # KODEX 국고채3년
    ]
    
    filtered_etfs = []
    for code, name in etf_map.items():
        # 제외 코드 체크
        if code in exclude_codes:
            logger.debug(f"제외: {code} {name}")
            print(f"  제외: {code} {name}")
            continue
        
        filtered_etfs.append({'code': code, 'name': name})
        print(f"  추가: {code} {name}")
    
    logger.info(f"필터링 후 ETF: {len(filtered_etfs)}개")
    print(f"필터링 후 ETF: {len(filtered_etfs)}개")
    return filtered_etfs


def check_intraday_movements():
    """장중 급등/급락 체크 (ETF 전용) - 네이버 실시간 데이터 사용"""
    try:
        import pykrx.stock as stock
        from pykrx.website import naver  # 네이버 실시간 데이터
        from datetime import datetime
        
        today = date.today()
        
        # ETF 유니버스 가져오기
        etf_universe = get_etf_universe()
        
        print(f"ETF 유니버스: {len(etf_universe)}개")
        
        if not etf_universe:
            logger.warning("ETF 유니버스가 비어있습니다.")
            print("❌ ETF 유니버스가 비어있습니다!")
            return []
        
        alerts = []
        checked = 0
        
        for etf in etf_universe:
            code = etf['code']
            name = etf.get('name')
            
            try:
                # 종목명이 없으면 기본 이름 사용
                if not name:
                    name = f"ETF_{code}"
                
                # 네이버 실시간 데이터 사용 (장중 데이터 포함)
                # 최근 5일 데이터 가져오기
                fromdate = (today - timedelta(days=5)).strftime('%Y%m%d')
                todate = today.strftime('%Y%m%d')
                
                df = naver.get_market_ohlcv_by_date(fromdate, todate, code)
                
                if df.empty:
                    print(f"  ❌ {code} {name}: 데이터 없음")
                    continue
                
                checked += 1
                print(f"  ✅ {code} {name}: {len(df)}일 데이터")
                
                # 등락률 계산
                change_pct = df.iloc[-1]['등락률']
                
                # ETF 특성 판별
                etf_type = 'default'
                if '레버리지' in name or '인버스' in name:
                    etf_type = 'leverage'
                elif '미국' in name or '글로벌' in name or '해외' in name:
                    etf_type = 'overseas'
                elif '200' in name or '코스닥' in name:
                    etf_type = 'index'
                elif any(sector in name for sector in ['반도체', '자동차', '은행', '배당', '에너지']):
                    etf_type = 'sector'
                
                # 특성별 기준 적용
                threshold = THRESHOLDS.get(etf_type, THRESHOLDS['default'])
                
                # 급등/급락 기준 체크
                if abs(change_pct) >= threshold:
                    price = df.iloc[-1]['종가']
                    volume = df.iloc[-1]['거래량']
                    value = price * volume  # 거래대금
                    
                    # 거래대금 필터 (의미 있는 알림만)
                    if value >= MIN_TRADE_VALUE:
                        alerts.append({
                            'code': code,
                            'name': name,
                            'change': change_pct,
                            'price': price,
                            'volume': volume,
                            'value': value,
                            'type': etf_type
                        })
            
            except Exception as e:
                logger.debug(f"종목 체크 실패 [{code}]: {e}")
                continue
        
        logger.info(f"체크 완료: {checked}개 종목, 알림 대상: {len(alerts)}개")
        print(f"체크 완료: {checked}개 ETF 중 {len(alerts)}개 알림 대상")
        
        # 등락률 절대값 기준으로 정렬
        alerts.sort(key=lambda x: abs(x['change']), reverse=True)
        
        return alerts
    
    except Exception as e:
        logger.error(f"장중 체크 실패: {e}")
        return []


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("장중 알림 체크 시작 (보유 종목 우선)")
    logger.info("=" * 60)
    
    print("=" * 60)
    print("장중 알림 체크 시작")
    print("=" * 60)
    
    try:
        # 보유 종목 로드
        try:
            loader = PortfolioLoader()
            holdings_codes = loader.get_holdings_codes()
            holdings_detail = loader.get_holdings_detail()
            print(f"보유 종목: {len(holdings_codes)}개")
            logger.info(f"보유 종목: {len(holdings_codes)}개")
        except Exception as e:
            logger.warning(f"보유 종목 로드 실패: {e}")
            holdings_codes = []
            holdings_detail = None
        
        # 장중 체크
        alerts = check_intraday_movements()
        
        print(f"알림 대상: {len(alerts)}개")
        
        if not alerts:
            logger.info("알림 대상 없음 - 전송 생략")
            print("✅ 의미 있는 급등/급락 없음 (알림 생략)")
            print("💡 현재 횡보장이거나 안정적인 장세입니다.")
            print(f"💡 기준: 지수 ETF 1.5%, 섹터 ETF 2.0%, 해외 ETF 1.5%")
            print(f"💡 최소 거래대금: 50억원 이상")
            return 0
        
        # 보유 종목 분류
        holding_alerts = [a for a in alerts if a['code'] in holdings_codes]
        other_alerts = [a for a in alerts if a['code'] not in holdings_codes]
        
        # 메시지 생성
        message = "*[장중 알림] ETF 급등/급락*\n\n"
        message += f"📅 {date.today()}\n"
        message += f"📊 총 {len(alerts)}개 ETF 발견\n"
        
        if holding_alerts:
            message += f"💼 보유 종목: {len(holding_alerts)}개\n"
        message += "\n"
        
        # 1순위: 보유 종목 급등/급락
        if holding_alerts:
            message += "*💼 보유 종목*\n"
            for alert in holding_alerts[:5]:  # 최대 5개
                emoji = "🟢" if alert['change'] > 0 else "🔴"
                message += f"{emoji} {alert['name']} ({alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래대금: {alert['value']/1e8:.1f}억원\n\n"
        
        # 2순위: 기타 주요 ETF (최대 5개)
        if other_alerts and len(other_alerts) > 0:
            message += "*📊 주요 ETF*\n"
            # 급등 상위 3개
            up_others = [a for a in other_alerts if a['change'] > 0][:3]
            for alert in up_others:
                message += f"🟢 {alert['name']} ({alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래대금: {alert['value']/1e8:.1f}억원\n\n"
            
            # 급락 상위 3개
            down_others = [a for a in other_alerts if a['change'] < 0][:3]
            for alert in down_others:
                message += f"🔴 {alert['name']} ({alert['code']})\n"
                message += f"  변동: {alert['change']:+.2f}% | 가격: {alert['price']:,.0f}원\n"
                message += f"  거래대금: {alert['value']/1e8:.1f}억원\n\n"
        
        # 텔레그램 전송
        print("\n텔레그램 전송 시도...")
        print(f"메시지 길이: {len(message)} 문자")
        
        sender = TelegramSender()
        success = sender.send_custom(message, parse_mode='Markdown')
        
        if success:
            logger.info(f"✅ 장중 알림 전송 성공: {len(alerts)}개")
            print(f"✅ 텔레그램 전송 성공: {len(alerts)}개 ETF")
        else:
            logger.warning("⚠️ 장중 알림 전송 실패")
            print("❌ 텔레그램 전송 실패")
            print("💡 .env 파일의 TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 확인하세요")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ 장중 알림 실패: {e}", exc_info=True)
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
