#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/nas/daily_recommendation_alert.py
일일 추천 알림 (Live 파라미터 기반)

PLAN.md 긴급 항목 #3 구현:
- Live 파라미터 기반 매수/매도 신호 생성
- 텔레그램 알림 발송
- 크론 등록 (예: 08:30 장시작 전)
"""
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.script_base import ScriptBase, handle_script_errors

# 스크립트 베이스 초기화
script = ScriptBase("daily_recommendation_alert")
logger = script.logger


def load_current_holdings() -> dict:
    """
    현재 보유 비중 로드 (holdings.json에서)

    Returns:
        dict: {ticker: weight%}
    """
    import json

    holdings_path = PROJECT_ROOT / "data" / "portfolio" / "holdings.json"

    if not holdings_path.exists():
        logger.warning(f"holdings.json 없음: {holdings_path}")
        return {}

    try:
        with open(holdings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        holdings = data.get("holdings", [])
        if not holdings:
            return {}

        # 총 평가액 계산
        total_value = sum(h.get("current_value", 0) for h in holdings if h.get("quantity", 0) > 0)

        if total_value <= 0:
            return {}

        # 비중 계산
        weights = {}
        for h in holdings:
            if h.get("quantity", 0) > 0:
                code = h.get("code", "")
                value = h.get("current_value", 0)
                weights[code] = (value / total_value) * 100

        return weights

    except Exception as e:
        logger.error(f"보유 비중 로드 실패: {e}")
        return {}


def get_stock_name(code: str) -> str:
    """종목명 조회"""
    # 주요 ETF 매핑
    etf_names = {
        "069500": "KODEX 200",
        "102110": "TIGER 200",
        "229200": "KODEX 코스닥150",
        "091160": "KODEX 반도체",
        "091180": "KODEX 자동차",
        "091170": "KODEX 은행",
        "143850": "TIGER 미국S&P500",
        "360750": "TIGER 미국NASDAQ100",
        "379800": "KODEX 미국S&P500TR",
        "364980": "TIGER 미국NASDAQ100TR",
        "379810": "KODEX 미국NASDAQ100TR",
        "453810": "TIGER 미국S&P500패시브",
        "461930": "KODEX 미국빅테크10(H)",
        "446720": "TIGER 미국테크TOP10 INDXX",
    }

    if code in etf_names:
        return etf_names[code]

    # pykrx로 조회 시도
    try:
        from pykrx import stock

        name = stock.get_market_ticker_name(code)
        if name and name.strip():
            return name.strip()
    except Exception:
        pass

    return code


def format_telegram_message(result: dict) -> str:
    """
    추천 결과를 텔레그램 메시지 형식으로 변환

    Args:
        result: generate_recommendation() 결과

    Returns:
        str: 포맷된 메시지
    """
    lines = []

    # 헤더
    lines.append("=" * 35)
    lines.append("📊 *일일 추천*")
    lines.append(f"📅 {date.today().strftime('%Y-%m-%d (%a)')}")
    lines.append("=" * 35)

    # Live 파라미터 요약
    params = result.get("live_params", {})
    if params:
        lookback = params.get("lookback", "3M")
        ma = params.get("ma_period", 60)
        rsi = params.get("rsi_period", 14)
        stop = params.get("stop_loss", -10)
        lines.append(f"🔧 *전략*: {lookback} / MA{ma} / RSI{rsi}")
        lines.append(f"   손절: {stop}%")
        lines.append("")

    # 레짐 정보
    regime_info = result.get("regime_info", {})
    if regime_info:
        regime_emoji = {"bull": "📈", "bear": "📉", "neutral": "➡️"}
        regime_name = {"bull": "상승장", "bear": "하락장", "neutral": "중립장"}
        regime = regime_info.get("regime", "neutral")
        emoji = regime_emoji.get(regime, "❓")
        name = regime_name.get(regime, regime)
        confidence = regime_info.get("confidence", 0)
        position = regime_info.get("position_ratio", 0.8)
        lines.append(f"{emoji} *레짐*: {name}")
        lines.append(f"   신뢰도: {confidence:.0%} / 포지션: {position:.0%}")
        lines.append("")

    # 매수 검토
    buy_recs = result.get("buy_recommendations", [])
    lines.append("📥 *매수 검토*")
    lines.append("-" * 25)
    if buy_recs:
        for rec in buy_recs[:5]:  # 최대 5개
            code = rec["code"]
            name = get_stock_name(code)
            target = rec["target_weight"]
            score = rec["final_score"]
            lines.append(f"  • {name}")
            lines.append(f"    목표 {target:.1f}% (점수 {score:.1f})")
    else:
        lines.append("  (없음)")
    lines.append("")

    # 매도 검토
    sell_recs = result.get("sell_recommendations", [])
    lines.append("📤 *매도 검토*")
    lines.append("-" * 25)
    if sell_recs:
        for rec in sell_recs[:5]:  # 최대 5개
            code = rec["code"]
            name = get_stock_name(code)
            current = rec["current_weight"]
            reason = rec.get("reason", "")
            lines.append(f"  • {name}")
            lines.append(f"    {current:.1f}% → 0% ({reason})")
    else:
        lines.append("  (없음)")
    lines.append("")

    # 푸터
    lines.append("=" * 35)
    target_pos = result.get("target_positions", 0)
    target_wt = result.get("target_weight", 0)
    lines.append(f"목표: {target_pos}종목 × {target_wt:.1f}%")

    return "\n".join(lines)


@handle_script_errors("일일 추천 알림")
def main():
    """메인 실행 함수"""
    script.log_header("일일 추천 알림 생성 시작")

    print("=" * 60)
    print("일일 추천 알림 생성 (Live 파라미터 기반)")
    print("=" * 60)

    # 텔레그램 설정
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.warning("텔레그램 설정 없음 - 콘솔 출력만")
        print("⚠️ 텔레그램 설정 없음 (.env 파일 확인)")
        telegram_enabled = False
    else:
        telegram_enabled = True
        print("✅ 텔레그램 설정 확인")

    # 현재 보유 비중 로드
    print("\n📂 보유 비중 로드 중...")
    current_holdings = load_current_holdings()
    print(f"   보유 종목: {len(current_holdings)}개")

    # Live 신호 생성기
    print("\n🔄 Live 파라미터 기반 추천 생성 중...")
    from core.strategy.live_signal_generator import LiveSignalGenerator

    generator = LiveSignalGenerator()
    result = generator.generate_recommendation(
        target_date=date.today(), current_holdings=current_holdings
    )

    # 결과 확인
    if result.get("message"):
        print(f"⚠️ {result['message']}")
        script.log_footer()
        return 1

    buy_count = len(result.get("buy_recommendations", []))
    sell_count = len(result.get("sell_recommendations", []))
    print(f"   매수 검토: {buy_count}개")
    print(f"   매도 검토: {sell_count}개")

    # 메시지 생성
    message = format_telegram_message(result)

    # 콘솔 출력
    print("\n" + "=" * 60)
    print("일일 추천")
    print("=" * 60)
    print(message)
    print("=" * 60)

    # 텔레그램 전송
    if telegram_enabled:
        try:
            from extensions.automation.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id, enabled=True)
            notifier.send_message(message, parse_mode="Markdown")
            logger.info("✅ 일일 추천 텔레그램 전송 완료")
            print("\n✅ 텔레그램 전송 완료")
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}")
            print(f"\n❌ 텔레그램 전송 실패: {e}")
    else:
        print("\n✅ 추천 생성 완료 (텔레그램 미전송)")

    script.log_footer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
