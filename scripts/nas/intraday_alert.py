#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/intraday_alert.py
장중 급등/급락 알림 (보유 종목 우선)
"""
import sys
import logging
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pykrx.stock as stock
from pykrx.website import naver
from pykrx import stock as pykrx_stock

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
    """ETF 유니버스 가져오기 (pykrx 전체 조회, 레버리지/인버스/채권 제외)"""
    try:
        # pykrx로 전체 ETF 조회
        today = date.today().strftime('%Y%m%d')
        all_etf_codes = stock.get_etf_ticker_list(today)
        
        logger.info(f"전체 ETF: {len(all_etf_codes)}개")
        print(f"전체 ETF: {len(all_etf_codes)}개")
        
        # 제외 키워드 (레버리지/인버스/채권)
        exclude_keywords = [
            '레버리지', '인버스', '곱버스', 'LEVERAGE', 'INVERSE',
            '국고채', '회사채', '통안채', '채권', 'BOND',
            '머니마켓', 'MMF', '단기자금',
        ]
        
        filtered_etfs = []
        excluded_count = 0
        
        for code in all_etf_codes:
            try:
                # 종목명 조회
                name = stock.get_etf_ticker_name(code)
                
                # 제외 키워드 체크
                if any(keyword in name for keyword in exclude_keywords):
                    logger.debug(f"제외: {code} {name}")
                    excluded_count += 1
                    continue
                
                filtered_etfs.append({'code': code, 'name': name})
            
            except Exception as e:
                logger.debug(f"종목명 조회 실패 [{code}]: {e}")
                continue
        
        logger.info(f"필터링 후 ETF: {len(filtered_etfs)}개 (제외: {excluded_count}개)")
        print(f"필터링 후 ETF: {len(filtered_etfs)}개 (제외: {excluded_count}개)")
        return filtered_etfs
    
    except Exception as e:
        logger.error(f"ETF 유니버스 조회 실패: {e}")
        print(f"❌ ETF 유니버스 조회 실패: {e}")
        return []


def check_intraday_movements():
    """장중 급등/급락 체크 (ETF 전용) - 네이버 실시간 데이터 사용"""
    try:
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
                
                # 3개월 수익률 계산 (약 60거래일)
                if len(df) >= 60:
                    price_3m_ago = df.iloc[-60]['종가']
                    price_now = df.iloc[-1]['종가']
                    return_3m = ((price_now / price_3m_ago) - 1) * 100
                else:
                    return_3m = None
                
                # 거래량 트렌드 (5일 평균 대비)
                if len(df) >= 5:
                    volume_5d_avg = df.iloc[-6:-1]['거래량'].mean()
                    volume_today = df.iloc[-1]['거래량']
                    volume_ratio = (volume_today / volume_5d_avg) if volume_5d_avg > 0 else 1.0
                else:
                    volume_ratio = 1.0
                
                # ETF 특성 판별
                etf_type = 'default'
                if '레버리지' in name or '인버스' in name:
                    etf_type = 'leverage'
                elif '미국' in name or '글로벌' in name or '해외' in name or '중국' in name:
                    etf_type = 'overseas'
                elif '200' in name or '코스닥' in name or 'KOSPI' in name:
                    etf_type = 'index'
                elif any(sector in name for sector in ['반도체', '자동차', '은행', '배당', '에너지', '제약', '바이오', '헬스케어', '의료']):
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
                        # 괴리율 조회 (ETF 전용)
                        try:
                            etf_info = pykrx_stock.get_etf_ohlcv_by_date(date.today().strftime('%Y%m%d'), date.today().strftime('%Y%m%d'), code)
                            if not etf_info.empty and 'NAV' in etf_info.columns:
                                nav = etf_info.iloc[-1]['NAV']
                                tracking_error = ((price - nav) / nav) * 100 if nav > 0 else 0
                            else:
                                tracking_error = None
                        except:
                            tracking_error = None
                        
                        alerts.append({
                            'code': code,
                            'name': name,
                            'change': change_pct,
                            'price': price,
                            'volume': volume,
                            'value': value,
                            'type': etf_type,
                            'return_3m': return_3m,
                            'volume_ratio': volume_ratio,
                            'tracking_error': tracking_error
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
        
        # 보유 종목 제외 (새로운 투자처 발굴 목적)
        new_opportunities = [a for a in alerts if a['code'] not in holdings_codes]
        
        if not new_opportunities:
            logger.info("신규 투자 기회 없음 - 전송 생략")
            print("✅ 신규 투자 기회 없음 (보유 종목 외 급등/급락 없음)")
            return 0
        
        # 메시지 생성 (새로운 투자처 발굴)
        message = "*[장중 알림] 새로운 투자 기회*\n\n"
        message += f"📅 {date.today()}\n"
        message += f"🔍 신규 투자 기회: {len(new_opportunities)}개\n"
        message += f"💼 현재 보유: {len(holdings_codes)}개 (제외됨)\n\n"
        
        # 급등 종목 (상위 10개)
        up_alerts = [a for a in new_opportunities if a['change'] > 0][:10]
        if up_alerts:
            message += "*🟢 급등 ETF (신규 투자 기회)*\n"
            for i, alert in enumerate(up_alerts, 1):
                message += f"{i}. {alert['name']} ({alert['code']})\n"
                message += f"   금일: {alert['change']:+.2f}%"
                
                # 3개월 수익률
                if alert.get('return_3m') is not None:
                    message += f" | 3개월: {alert['return_3m']:+.2f}%"
                
                message += f" | 가격: {alert['price']:,.0f}원\n"
                
                # 거래량 트렌드
                volume_emoji = "🔥" if alert.get('volume_ratio', 1.0) > 2.0 else ""
                message += f"   거래대금: {alert['value']/1e8:.1f}억원 {volume_emoji}"
                
                if alert.get('volume_ratio') and alert['volume_ratio'] > 1.5:
                    message += f" (거래량 {alert['volume_ratio']:.1f}배)"
                
                # 괴리율
                if alert.get('tracking_error') is not None:
                    message += f" | 괴리율: {alert['tracking_error']:+.2f}%"
                
                message += "\n\n"
        
        # 급락 종목 (상위 5개)
        down_alerts = [a for a in new_opportunities if a['change'] < 0][:5]
        if down_alerts:
            message += "*🔴 급락 ETF (저가 매수 기회)*\n"
            for i, alert in enumerate(down_alerts, 1):
                message += f"{i}. {alert['name']} ({alert['code']})\n"
                message += f"   금일: {alert['change']:+.2f}%"
                
                # 3개월 수익률
                if alert.get('return_3m') is not None:
                    message += f" | 3개월: {alert['return_3m']:+.2f}%"
                
                message += f" | 가격: {alert['price']:,.0f}원\n"
                
                # 거래량 트렌드
                volume_emoji = "🔥" if alert.get('volume_ratio', 1.0) > 2.0 else ""
                message += f"   거래대금: {alert['value']/1e8:.1f}억원 {volume_emoji}"
                
                if alert.get('volume_ratio') and alert['volume_ratio'] > 1.5:
                    message += f" (거래량 {alert['volume_ratio']:.1f}배)"
                
                # 괴리율
                if alert.get('tracking_error') is not None:
                    message += f" | 괴리율: {alert['tracking_error']:+.2f}%"
                
                message += "\n\n"
        
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
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
