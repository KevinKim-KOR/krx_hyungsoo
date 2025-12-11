#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/market_open_alert.py
장 시작 알림 (포트폴리오 현황 + Live 파라미터 요약)
"""
import sys
from datetime import date
from pathlib import Path
import pandas as pd
import pykrx.stock as stock
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.script_base import ScriptBase, handle_script_errors
from extensions.automation.portfolio_helper import PortfolioHelper
from extensions.notification.telegram_helper import TelegramHelper
from core.strategy.live_signal_generator import LiveSignalGenerator

# 스크립트 베이스 초기화
script = ScriptBase("market_open_alert")
logger = script.logger


@handle_script_errors("장 시작 알림")
def main():
    """장 시작 알림 (실시간 가격 반영)"""
    script.log_header("장 시작 알림")

    # 1. 포트폴리오 로드 (기본 데이터)
    portfolio = PortfolioHelper()
    data = portfolio.load_full_data()

    if not data or not data.get("holdings_detail") is not None:
        logger.warning("포트폴리오 데이터 없음")
        return 0

    holdings_detail = data["holdings_detail"]

    # 2. 실시간(또는 최신) 가격 업데이트
    try:
        today = date.today().strftime("%Y%m%d")
        # 전종목 시세 가져오기 (속도 향상)
        market_df = stock.get_market_ohlcv_by_ticker(today)

        # 만약 장 시작 직후라 데이터가 없으면(빈 DF), 어제 종가 사용
        if market_df.empty:
            logger.info("금일 시세 미생성, 전일 종가 사용")
            yesterday = (pd.Timestamp(today) - pd.tseries.offsets.BusinessDay(1)).strftime("%Y%m%d")
            market_df = stock.get_market_ohlcv_by_ticker(yesterday)
            date_str = f"{date.today()} (전일종가 기준)"
        else:
            date_str = f"{date.today()} (장시작)"

        # 보유 종목 업데이트
        total_value = 0
        total_cost = 0

        updated_holdings = []

        for _, row in holdings_detail.iterrows():
            code = row["code"]
            quantity = row["quantity"]
            avg_price = row["avg_price"]
            name = row["name"]

            # 시세 조회 (0원이면 DB 저장 가격 사용)
            current_price = 0
            if code in market_df.index:
                current_price = market_df.loc[code]["종가"]

            # 시세가 0원이거나 없으면 DB에 저장된 current_price 사용
            if current_price <= 0:
                current_price = row.get("current_price", 0)

            # 그래도 0원이면 매수가 사용
            if current_price <= 0:
                current_price = avg_price

            val = current_price * quantity
            cost = avg_price * quantity

            total_value += val
            total_cost += cost

            # 수익률 계산
            ret_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            ret_amt = val - cost

            updated_holdings.append({"name": name, "return_pct": ret_pct, "return_amt": ret_amt})

        # 3. 요약 재계산
        total_return_amt = total_value - total_cost
        total_return_pct = (total_return_amt / total_cost * 100) if total_cost > 0 else 0

        # 4. Live 파라미터 요약 (한 줄)
        try:
            signal_gen = LiveSignalGenerator()
            params_summary = signal_gen.get_params_summary()
        except Exception as e:
            logger.warning(f"Live 파라미터 로드 실패: {e}")
            params_summary = "기본값"

        # 5. 메시지 생성
        message = "*[장 시작] 포트폴리오 현황*\n\n"
        message += f"📅 {date_str}\n\n"
        message += f"💰 총 평가액: `{total_value:,.0f}원`\n"
        message += f"💵 총 매입액: `{total_cost:,.0f}원`\n"
        message += (
            f"📈 평가손익: {PortfolioHelper.format_return(total_return_amt, total_return_pct)}\n"
        )
        message += f"📊 보유 종목: `{len(holdings_detail)}개`\n"
        message += f"🔧 전략: `{params_summary}`\n\n"

        message += "_오늘도 성투하세요!_ 🚀"

        # 6. 텔레그램 전송
        telegram = TelegramHelper()
        telegram.send_with_logging(message, "장 시작 알림 전송 성공", "장 시작 알림 전송 실패")

    except Exception as e:
        logger.error(f"가격 업데이트 중 오류: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
