#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/intraday_alert.py
장중 급등/급락 알림 (보유 종목 우선)
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pykrx.stock as stock
from pykrx.website import naver
from pykrx import stock as pykrx_stock

from extensions.automation.script_base import ScriptBase, handle_script_errors
from extensions.automation.portfolio_helper import PortfolioHelper
from extensions.automation.config_loader import get_config_loader
from extensions.notification.telegram_helper import TelegramHelper

# 스크립트 베이스 초기화
script = ScriptBase("intraday_alert")
logger = script.logger

# Config 로더 초기화
config = get_config_loader()

# 설정 로드 (config.nas.yaml에서)
THRESHOLDS = config.get("intraday_alert.thresholds", {
    'leverage': 3.0,
    'sector': 2.0,
    'index': 1.5,
    'overseas': 1.5,
    'default': 2.0
})

MIN_TRADE_VALUE = config.get("intraday_alert.min_trade_value", 50e8)
EXCLUDE_KEYWORDS = config.get("intraday_alert.exclude_keywords", [
    '레버리지', '인버스', '곱버스', 'LEVERAGE', 'INVERSE',
    '국고채', '회사채', '통안채', '채권', 'BOND',
    '머니마켓', 'MMF', '단기자금'
])


def get_etf_universe():
    """ETF 유니버스 가져오기 (pykrx 전체 조회, 레버리지/인버스/채권 제외)"""
    try:
        # pykrx로 전체 ETF 조회
        today = date.today().strftime('%Y%m%d')
        try:
            all_etf_codes = stock.get_etf_ticker_list(today)
        except Exception as e:
            logger.warning(f"오늘 날짜({today})로 ETF 조회 실패: {e}. 날짜 없이 재시도합니다.")
            all_etf_codes = stock.get_etf_ticker_list()
        
        logger.info(f"전체 ETF: {len(all_etf_codes)}개")
        print(f"전체 ETF: {len(all_etf_codes)}개")
        
        filtered_etfs = []
        excluded_count = 0
        
        for code in all_etf_codes:
            try:
                # 종목명 조회
                name = stock.get_etf_ticker_name(code)
                
                # 제외 키워드 체크 (Config에서 로드)
                if any(keyword in name for keyword in EXCLUDE_KEYWORDS):
                    # logger.debug(f"제외: {code} {name}")
                    excluded_count += 1
                    continue
                
                filtered_etfs.append({'code': code, 'name': name})
            
            except Exception as e:
                logger.debug(f"종목명 조회 실패 [{code}]: {e}")
                continue
        
        logger.info(f"필터링 후 ETF: {len(filtered_etfs)}개 (제외: {excluded_count}개)")
        print(f"필터링 후 ETF: {len(filtered_etfs)}개 (제외: {excluded_count}개)")
        
        # 성공 시 CSV로 저장 (Cloud 환경에서 최신 데이터 유지)
        try:
            import pandas as pd
            csv_path = PROJECT_ROOT / "data" / "universe" / "etf_universe.csv"
            # 디렉토리 생성
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            
            df_save = pd.DataFrame(filtered_etfs)
            df_save.rename(columns={'code': 'ticker'}, inplace=True) # 기존 포맷 호환
            df_save.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"ETF 유니버스 저장 완료: {csv_path}")
        except Exception as save_e:
            logger.warning(f"ETF 유니버스 저장 실패: {save_e}")
            
        return filtered_etfs
    
    except Exception as e:
        logger.error(f"ETF 유니버스 조회 실패: {e}")
        print(f"❌ ETF 유니버스 조회 실패: {e}")
        
        # CSV 파일에서 로드 시도
        csv_path = PROJECT_ROOT / "data" / "universe" / "etf_universe.csv"
        if csv_path.exists():
            logger.info(f"로컬 CSV 파일에서 로드 시도: {csv_path}")
            print(f"📂 로컬 CSV 파일 로드: {csv_path}")
            try:
                import pandas as pd
                df = pd.read_csv(csv_path, dtype={'ticker': str})
                
                # 컬럼 매핑 (ticker -> code, name -> name)
                if 'ticker' in df.columns and 'name' in df.columns:
                    filtered_etfs = []
                    excluded_count = 0
                    
                    for _, row in df.iterrows():
                        code = str(row['ticker']).zfill(6) # 6자리 문자열로 변환
                        name = row['name']
                        
                        # 제외 키워드 체크
                        if any(keyword in name for keyword in EXCLUDE_KEYWORDS):
                            excluded_count += 1
                            continue
                        
                        filtered_etfs.append({'code': code, 'name': name})
                    
                    logger.info(f"CSV 로드 성공: {len(filtered_etfs)}개 (제외: {excluded_count}개)")
                    print(f"✅ CSV 로드 성공: {len(filtered_etfs)}개 ETF")
                    return filtered_etfs
            except Exception as csv_e:
                logger.error(f"CSV 로드 실패: {csv_e}")
                print(f"❌ CSV 로드 실패: {csv_e}")
        
        return []


def check_intraday_movements():
    """장중 급등/급락 체크 (ETF + 보유종목) - 네이버 실시간 데이터 사용"""
    try:
        today = date.today()
        
        # 1. ETF 유니버스 가져오기
        etf_universe = get_etf_universe()
        
        # 2. 보유 종목 가져오기 (추가)
        portfolio = PortfolioHelper()
        pf_data = portfolio.load_full_data()
        holdings_codes = set()
        if pf_data and pf_data.get('holdings_codes'):
            holdings_codes = set(pf_data['holdings_codes'])
            
            # 유니버스에 보유 종목 병합 (없는 경우 추가)
            universe_codes = {item['code'] for item in etf_universe}
            for code in holdings_codes:
                if code not in universe_codes:
                    # 이름 조회 필요
                    try:
                        name = stock.get_market_ticker_name(code)
                        if not name: name = stock.get_etf_ticker_name(code)
                    except:
                        name = f"보유종목_{code}"
                    
                    etf_universe.append({'code': code, 'name': name, 'is_holding': True})
                else:
                    # 기존 항목에 마킹
                    for item in etf_universe:
                        if item['code'] == code:
                            item['is_holding'] = True
                            break
        
        print(f"검사 대상: {len(etf_universe)}개 (보유 {len(holdings_codes)}개 포함)")
        
        if not etf_universe:
            logger.warning("검사 대상이 없습니다.")
            return []
        
        alerts = []
        checked = 0
        total = len(etf_universe)
        
        print(f"\n📊 데이터 수집 및 분석 시작...")
        
        for idx, etf in enumerate(etf_universe, 1):
            code = etf['code']
            name = etf.get('name')
            is_holding = etf.get('is_holding', False)
            
            try:
                # 종목명이 없으면 기본 이름 사용
                if not name:
                    name = f"ETF_{code}"
                
                # 진행 상황 표시 (매 50개마다)
                if idx % 50 == 0 or idx == total:
                    print(f"  진행: {idx}/{total} ({idx/total*100:.1f}%) - 체크: {checked}개")
                
                # 네이버 실시간 데이터 사용
                fromdate = (today - timedelta(days=5)).strftime('%Y%m%d')
                todate = today.strftime('%Y%m%d')
                
                df = naver.get_market_ohlcv_by_date(fromdate, todate, code)
                
                if df is None or df.empty or len(df) == 0:
                    continue
                
                checked += 1
                
                # 등락률 계산
                try:
                    change_pct = df.iloc[-1]['등락률']
                except IndexError:
                    continue
                
                # ETF 특성 판별 (보유 종목은 개별주 일수도 있음)
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
                
                # 보유 종목은 기준 완화? (일단 동일 기준 적용하되, 급락 시 무조건 알림 검토)
                # 급등/급락 기준 체크
                is_alert = False
                
                if abs(change_pct) >= threshold:
                    price = df.iloc[-1]['종가']
                    volume = df.iloc[-1]['거래량']
                    value = price * volume
                    
                    # 거래대금 필터 (보유 종목은 거래대금 무관하게 알림)
                    if is_holding or value >= MIN_TRADE_VALUE:
                         is_alert = True

                if is_alert:
                    price = df.iloc[-1]['종가']
                    volume = df.iloc[-1]['거래량']
                    value = price * volume
                    
                    # 추가 정보 계산 (3개월 수익률, 괴리율 등)
                    if len(df) >= 60:
                        price_3m_ago = df.iloc[-60]['종가']
                        return_3m = ((price / price_3m_ago) - 1) * 100
                    else:
                        return_3m = None

                    if len(df) >= 5:
                        volume_5d_avg = df.iloc[-6:-1]['거래량'].mean()
                        volume_today = df.iloc[-1]['거래량']
                        volume_ratio = (volume_today / volume_5d_avg) if volume_5d_avg > 0 else 1.0
                    else:
                        volume_ratio = 1.0

                    tracking_error = None
                    # ETF인 경우 괴리율 (생략 가능 또는 try)
                    
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
                        'tracking_error': tracking_error,
                        'is_holding': is_holding
                    })
            
            except Exception as e:
                # logger.debug(f"종목 체크 실패 [{code}]: {e}")
                continue
        
        logger.info(f"체크 완료: {checked}개 종목, 알림 대상: {len(alerts)}개")
        print(f"체크 완료: {checked}개 중 {len(alerts)}개 알림 대상")
        
        # 등락률 절대값 기준으로 정렬
        alerts.sort(key=lambda x: abs(x['change']), reverse=True)
        
        return alerts
    
    except Exception as e:
        logger.error(f"장중 체크 실패: {e}")
        return []


@handle_script_errors("장중 알림")
def main():
    """메인 실행 함수"""
    script.log_header("장중 알림 체크 시작 (보유 종목 우선)")
    
    print("=" * 60)
    print("장중 알림 체크 시작")
    print("=" * 60)
    
    # 장중 체크 (보유 종목 포함)
    alerts = check_intraday_movements()
    
    print(f"알림 대상: {len(alerts)}개")
    
    if not alerts:
        logger.info("알림 대상 없음 - 전송 생략")
        print("✅ 의미 있는 급등/급락 없음 (알림 생략)")
        print("💡 현재 횡보장이거나 안정적인 장세입니다.")
        print(f"💡 기준: 지수 ETF 1.5%, 섹터 ETF 2.0%, 해외 ETF 1.5% (보유종목 포함)")
        print(f"💡 최소 거래대금: 50억원 이상 (보유종목 제외)")
        return 0
    
    # 알림 분류
    holding_alerts = [a for a in alerts if a['is_holding']]
    new_opportunities = [a for a in alerts if not a['is_holding']]
    
    if not holding_alerts and not new_opportunities:
        return 0
    
    # 메시지 생성
    message = "*[장중 알림] 급등/급락 감지*\n\n"
    message += f"📅 {date.today()}\n"
    
    # 1. 보유 종목 알림 (최우선)
    if holding_alerts:
        message += f"🚨 *보유 종목 변동 ({len(holding_alerts)}개)*\n\n"
        for i, alert in enumerate(holding_alerts, 1):
            emoji = "🔴" if alert['change'] < 0 else "🟢"
            message += f"{i}. {emoji} *{alert['name']}* (`{alert['code']}`)\n"
            message += f"   등락률: `{alert['change']:+.2f}%`\n"
            message += f"   현재가: `{alert['price']:,.0f}원`\n"
            message += f"   거래대금: `{alert['value']/1e8:.1f}억원`\n\n"
    
    # 2. 신규 투자 기회
    if new_opportunities:
        message += f"🔍 *신규 투자 기회 ({len(new_opportunities)}개)*\n\n"
        
        # 급등 (Top 5)
        up_alerts = [a for a in new_opportunities if a['change'] > 0][:5]
        if up_alerts:
            message += "*🟢 급등 (매수 관점)*\n"
            for i, alert in enumerate(up_alerts, 1):
                message += f"{i}. {alert['name']} ({alert['code']})\n"
                message += f"   {alert['change']:+.2f}% | {alert['value']/1e8:.1f}억\n"
                if alert.get('volume_ratio', 0) > 1.5:
                    message += f"   🔥 거래폭발 ({alert['volume_ratio']:.1f}배)\n"
                message += "\n"
        
        # 급락 (Top 5)
        down_alerts = [a for a in new_opportunities if a['change'] < 0][:5]
        if down_alerts:
            message += "*🔴 급락 (저점 매수)*\n"
            for i, alert in enumerate(down_alerts, 1):
                message += f"{i}. {alert['name']} ({alert['code']})\n"
                message += f"   {alert['change']:+.2f}% | {alert['value']/1e8:.1f}억\n\n"

    # 텔레그램 전송
    print("\n텔레그램 전송 시도...")
    
    telegram = TelegramHelper()
    success = telegram.send_with_logging(
        message,
        f"장중 알림 전송 성공: {len(alerts)}개",
        "장중 알림 전송 실패"
    )
    
    if success:
        print(f"✅ 텔레그램 전송 성공")
    else:
        print("❌ 텔레그램 전송 실패")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
