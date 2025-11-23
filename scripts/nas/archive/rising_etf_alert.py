#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/rising_etf_alert.py
상승중인 ETF 알림 (친구 스타일)
"""
import sys
import logging
from datetime import date, datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import re

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.notification.telegram_sender import TelegramSender
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


def get_etf_list():
    """ETF 리스트 조회 (네이버 금융)"""
    try:
        import pykrx.stock as stock
        
        # KRX ETF 리스트
        today = date.today()
        etf_list = stock.get_etf_ticker_list(today.strftime('%Y%m%d'))
        
        # 종목명 매핑
        etf_info = {}
        for code in etf_list:
            try:
                name = stock.get_market_ticker_name(code)
                etf_info[code] = name
            except:
                continue
        
        return etf_info
    
    except Exception as e:
        logger.error(f"ETF 리스트 조회 실패: {e}")
        return {}


def get_realtime_price(code: str):
    """실시간 시세 조회 (네이버 금융)"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 현재가
        price_elem = soup.select_one('.no_today .blind')
        if not price_elem:
            return None
        
        price = int(price_elem.text.replace(',', ''))
        
        # 등락률
        rate_elem = soup.select_one('.no_exday .blind')
        if not rate_elem:
            return None
        
        rate_text = rate_elem.text.strip()
        # "상승 3.45%" 또는 "하락 2.10%" 형태
        match = re.search(r'(상승|하락)\s*([\d.]+)%', rate_text)
        if not match:
            return None
        
        direction = match.group(1)
        rate = float(match.group(2))
        if direction == '하락':
            rate = -rate
        
        # 거래량
        volume_elem = soup.select_one('.first .blind')
        volume = 0
        if volume_elem:
            try:
                volume = int(volume_elem.text.replace(',', ''))
            except:
                pass
        
        return {
            'price': price,
            'change_rate': rate,
            'volume': volume
        }
    
    except Exception as e:
        logger.debug(f"시세 조회 실패 [{code}]: {e}")
        return None


def filter_etf_name(name: str) -> bool:
    """제외 키워드 필터링"""
    exclude_keywords = ['레버리지', '인버스', '채권', '커버드콜', 'ETN', '곱버스']
    
    for keyword in exclude_keywords:
        if keyword in name:
            return False
    
    return True


def find_rising_etfs(threshold: float = 3.0, limit: int = 10):
    """상승중인 ETF 찾기"""
    logger.info(f"상승 ETF 검색 시작 (기준: {threshold}% 이상)")
    
    # ETF 리스트
    etf_info = get_etf_list()
    logger.info(f"총 ETF 수: {len(etf_info)}개")
    
    if not etf_info:
        logger.warning("ETF 리스트 조회 실패")
        return []
    
    # 제외 키워드 필터링
    filtered_etfs = {code: name for code, name in etf_info.items() if filter_etf_name(name)}
    excluded_count = len(etf_info) - len(filtered_etfs)
    logger.info(f"제외 키워드 필터링: {excluded_count}개 제외, {len(filtered_etfs)}개 남음")
    
    # 실시간 시세 조회
    rising_etfs = []
    
    for i, (code, name) in enumerate(filtered_etfs.items()):
        if i >= 100:  # 최대 100개만 조회 (시간 절약)
            break
        
        price_info = get_realtime_price(code)
        
        if price_info and price_info['change_rate'] >= threshold:
            rising_etfs.append({
                'code': code,
                'name': name,
                'price': price_info['price'],
                'change_rate': price_info['change_rate'],
                'volume': price_info['volume']
            })
    
    # 등락률 순 정렬
    rising_etfs.sort(key=lambda x: x['change_rate'], reverse=True)
    
    logger.info(f"등락률 {threshold}% 이상 상승 종목: {len(rising_etfs)}개")
    
    return rising_etfs[:limit]


def main():
    """상승 ETF 알림"""
    logger.info("=" * 60)
    logger.info(f"상승중인 ETF 알림 - {datetime.now():%Y-%m-%d %H:%M:%S}")
    logger.info("=" * 60)
    
    try:
        # 상승 ETF 검색
        rising_etfs = find_rising_etfs(threshold=3.0, limit=10)
        
        if not rising_etfs:
            logger.info("상승 ETF 없음")
            return 0
        
        # 메시지 생성 (친구 스타일)
        message = f"*[상승중인 ETF]*\n\n"
        message += f"📅 기준일: {date.today()}\n"
        message += f"📊 {len(rising_etfs)}개 종목 발견\n\n"
        message += "--- 상승중인 ETF 목록 ---\n"
        
        for etf in rising_etfs:
            message += f"\n• *{etf['name']}* (`{etf['code']}`)\n"
            message += f"  금일수익률: *{etf['change_rate']:+.2f}%*\n"
            message += f"  현재가: {etf['price']:,}원\n"
            message += f"  거래량: {etf['volume']:,}\n"
        
        # 텔레그램 전송
        sender = TelegramSender()
        success = sender.send_custom(message, parse_mode='Markdown')
        
        if success:
            logger.info(f"✅ 상승 ETF 알림 전송 성공: {len(rising_etfs)}개")
        else:
            logger.warning("⚠️ 상승 ETF 알림 전송 실패")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ 상승 ETF 알림 실패: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
