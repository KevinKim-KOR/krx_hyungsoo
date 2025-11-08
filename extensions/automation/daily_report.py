# -*- coding: utf-8 -*-
"""
extensions/automation/daily_report.py
일일 리포트 생성

기능:
- 포트폴리오 현황
- 당일 수익률
- 레짐 상태
- 매매 신호
"""

from datetime import date, datetime
from typing import Optional, Dict, List
import logging

from extensions.automation.regime_monitor import RegimeMonitor
from extensions.automation.signal_generator import AutoSignalGenerator
from extensions.automation.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class DailyReport:
    """
    일일 리포트 생성 클래스
    
    기능:
    1. 포트폴리오 현황 요약
    2. 레짐 상태 보고
    3. 매매 신호 요약
    4. 텔레그램 전송
    """
    
    def __init__(
        self,
        telegram_enabled: bool = False,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        """
        Args:
            telegram_enabled: 텔레그램 알림 활성화
            bot_token: 텔레그램 봇 토큰
            chat_id: 채팅 ID
        """
        self.regime_monitor = RegimeMonitor()
        self.signal_generator = AutoSignalGenerator()
        self.notifier = TelegramNotifier(
            bot_token=bot_token,
            chat_id=chat_id,
            enabled=telegram_enabled
        )
    
    def generate_report(
        self,
        target_date: Optional[date] = None,
        current_holdings: Optional[List[str]] = None,
        portfolio_value: Optional[float] = None,
        initial_capital: float = 10000000
    ) -> str:
        """
        일일 리포트 생성
        
        Args:
            target_date: 대상 날짜 (None이면 오늘)
            current_holdings: 현재 보유 종목
            portfolio_value: 포트폴리오 가치
            initial_capital: 초기 자본
        
        Returns:
            str: 리포트 텍스트
        """
        if target_date is None:
            target_date = date.today()
        
        if current_holdings is None:
            current_holdings = []
        
        logger.info(f"일일 리포트 생성: {target_date}")
        
        # 1. 레짐 분석
        regime_info = self.regime_monitor.analyze_daily_regime(target_date)
        
        # 2. 매매 신호 생성
        signals = self.signal_generator.generate_daily_signals(
            target_date=target_date,
            current_holdings=current_holdings
        )
        
        # 3. 리포트 작성
        report_lines = []
        report_lines.append("=" * 50)
        report_lines.append("📊 일일 투자 리포트")
        report_lines.append("=" * 50)
        report_lines.append(f"📅 날짜: {target_date.strftime('%Y년 %m월 %d일')}")
        report_lines.append("")
        
        # 포트폴리오 현황
        report_lines.append("💼 포트폴리오 현황")
        report_lines.append("-" * 50)
        
        if portfolio_value:
            total_return = portfolio_value - initial_capital
            total_return_pct = (total_return / initial_capital) * 100
            
            report_lines.append(f"  평가액: {portfolio_value:,.0f}원")
            report_lines.append(f"  수익: {total_return:+,.0f}원 ({total_return_pct:+.2f}%)")
        else:
            report_lines.append(f"  초기 자본: {initial_capital:,.0f}원")
        
        report_lines.append(f"  보유 종목: {len(current_holdings)}개")
        report_lines.append("")
        
        # 시장 레짐
        if regime_info:
            regime_emoji = {
                'bull': '📈',
                'bear': '📉',
                'neutral': '➡️'
            }
            regime_name = {
                'bull': '상승장',
                'bear': '하락장',
                'neutral': '중립장'
            }
            
            emoji = regime_emoji.get(regime_info['regime'], '❓')
            name = regime_name.get(regime_info['regime'], regime_info['regime'])
            
            report_lines.append("🎯 시장 레짐")
            report_lines.append("-" * 50)
            report_lines.append(f"  {emoji} 현재 레짐: {name}")
            report_lines.append(f"  📊 신뢰도: {regime_info['confidence']:.1%}")
            report_lines.append(f"  💪 포지션 비율: {regime_info['position_ratio']:.0%}")
            
            if regime_info['defense_mode']:
                report_lines.append("  ⚠️ 방어 모드 활성화")
            
            report_lines.append("")
        
        # 매매 신호
        buy_signals = signals.get('buy_signals', [])
        sell_signals = signals.get('sell_signals', [])
        
        report_lines.append("📈 매매 신호")
        report_lines.append("-" * 50)
        
        if buy_signals:
            report_lines.append(f"  🟢 매수: {len(buy_signals)}개")
            for i, signal in enumerate(buy_signals[:5], 1):  # 상위 5개만
                report_lines.append(
                    f"     {i}. {signal['code']} "
                    f"(MAPS: {signal['maps_score']:.2f})"
                )
            if len(buy_signals) > 5:
                report_lines.append(f"     ... 외 {len(buy_signals)-5}개")
        else:
            report_lines.append("  🟢 매수: 없음")
        
        report_lines.append("")
        
        if sell_signals:
            report_lines.append(f"  🔴 매도: {len(sell_signals)}개")
            for i, signal in enumerate(sell_signals[:5], 1):
                report_lines.append(
                    f"     {i}. {signal['code']} "
                    f"({signal['reason']})"
                )
            if len(sell_signals) > 5:
                report_lines.append(f"     ... 외 {len(sell_signals)-5}개")
        else:
            report_lines.append("  🔴 매도: 없음")
        
        report_lines.append("")
        report_lines.append("=" * 50)
        report_lines.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 50)
        
        report_text = "\n".join(report_lines)
        
        # 4. 텔레그램 전송
        self._send_to_telegram(regime_info, signals)
        
        return report_text
    
    def _send_to_telegram(
        self,
        regime_info: Optional[Dict],
        signals: Dict
    ):
        """
        텔레그램으로 리포트 전송 (상세 정보 포함)
        
        Args:
            regime_info: 레짐 정보
            signals: 매매 신호
        """
        try:
            # 종목명 조회 함수
            def get_stock_name(code: str) -> str:
                """종목명 조회 (매핑 우선, pykrx 보조)"""
                # 주요 ETF 매핑 (우선 사용)
                etf_names = {
                    '069500': 'KODEX 200',
                    '102110': 'TIGER 200',
                    '229200': 'KODEX 코스닥150',
                    '091160': 'KODEX 반도체',
                    '091180': 'KODEX 자동차',
                    '091170': 'KODEX 은행',
                    '091220': 'TIGER 은행',
                    '143850': 'TIGER 미국S&P500',
                    '360750': 'TIGER 미국NASDAQ100',
                    '133690': 'TIGER 미국NASDAQ100레버리지',
                    '138230': 'KOSEF 미국S&P500',
                    '388420': 'KBSTAR 미국S&P500',
                    '379800': 'KODEX 미국S&P500TR',
                    '360200': 'TIGER 미국S&P500선물(H)',
                    '332620': 'KODEX 미국S&P500선물(H)',
                    '364980': 'TIGER 미국NASDAQ100TR',
                    '379810': 'KODEX 미국NASDAQ100TR',
                    '462010': 'ARIRANG 미국S&P500(H)',
                    '453810': 'TIGER 미국S&P500패시브',
                    '448630': 'TIGER 미구S&P500선물레버리지(H)',
                    '308620': 'KODEX 미구S&P500선물레버리지(H)',
                }
                
                # 매핑 테이블에 있으면 바로 반환
                if code in etf_names:
                    return etf_names[code]
                
                # 매핑에 없으면 pykrx로 조회 시도
                try:
                    import pykrx.stock as stock
                    name = stock.get_market_ticker_name(code)
                    if name and name.strip():
                        return name.strip()
                except Exception as e:
                    logger.debug(f"종목명 조회 실패 [{code}]: {e}")
                
                # 모두 실패하면 코드 반환
                return code
            
            # 상세 일일 리포트 메시지 생성
            message_lines = []
            message_lines.append("="*40)
            message_lines.append("📊 *일일 투자 리포트*")
            message_lines.append("="*40)
            message_lines.append(f"📅 날짜: {date.today().strftime('%Y년 %m월 %d일 (%A)')}")
            message_lines.append("")
            
            # 시장 레짐 상세
            if regime_info:
                regime_emoji = {
                    'bull': '📈',
                    'bear': '📉',
                    'neutral': '➡️'
                }
                regime_name = {
                    'bull': '상승장',
                    'bear': '하락장',
                    'neutral': '중립장'
                }
                
                emoji = regime_emoji.get(regime_info['regime'], '❓')
                name = regime_name.get(regime_info['regime'], regime_info['regime'])
                
                message_lines.append("🎯 *시장 레짐 분석*")
                message_lines.append("-"*40)
                message_lines.append(f"  {emoji} *현재 레짐*: {name}")
                message_lines.append(f"  📊 *신뢰도*: {regime_info['confidence']:.1%}")
                message_lines.append(f"  💪 *권장 포지션*: {regime_info['position_ratio']:.0%}")
                
                if regime_info.get('defense_mode'):
                    message_lines.append("  ⚠️ *방어 모드*: 활성")
                else:
                    message_lines.append("  ✅ *방어 모드*: 비활성")
                
                message_lines.append("")
            
            # 매매 신호 상세
            buy_signals = signals.get('buy_signals', [])
            sell_signals = signals.get('sell_signals', [])
            
            message_lines.append("📈 *매매 신호 상세*")
            message_lines.append("-"*40)
            
            # 매수 신호
            if buy_signals:
                message_lines.append(f"\n🟢 *매수 신호*: {len(buy_signals)}개")
                message_lines.append("")
                for i, signal in enumerate(buy_signals, 1):
                    code = signal['code']
                    name = get_stock_name(code)
                    maps_score = signal.get('maps_score', 0)
                    
                    # 종목명(코드: 123456) 형태
                    display_name = f"{name}(코드: {code})"
                    
                    message_lines.append(f"  {i}. *{display_name}*")
                    message_lines.append(f"     📊 MAPS 점수: {maps_score:.2f}")
                    
                    # MAPS 점수에 따른 강도 표시
                    if maps_score >= 10:
                        message_lines.append(f"     🔥 강도: 매우 강함")
                    elif maps_score >= 5:
                        message_lines.append(f"     ⭐ 강도: 강함")
                    else:
                        message_lines.append(f"     👍 강도: 보통")
                    
                    message_lines.append("")
            else:
                message_lines.append(f"\n🟢 *매수 신호*: 없음")
                message_lines.append("  - 현재 매수 조건을 충족하는 종목이 없습니다.")
                message_lines.append("")
            
            # 매도 신호
            if sell_signals:
                message_lines.append(f"\n🔴 *매도 신호*: {len(sell_signals)}개")
                message_lines.append("")
                for i, signal in enumerate(sell_signals, 1):
                    code = signal['code']
                    name = get_stock_name(code)
                    reason = signal.get('reason', 'unknown')
                    
                    # 사유 한글화
                    reason_map = {
                        'negative_maps_score': '하락 추세 (MAPS < 0)',
                        'stop_loss': '손절 발동',
                        'regime_change': '레짐 변경',
                        'defense_mode': '방어 모드',
                    }
                    reason_kr = reason_map.get(reason, reason)
                    
                    # 종목명(코드: 123456) 형태
                    display_name = f"{name}(코드: {code})"
                    
                    message_lines.append(f"  {i}. *{display_name}*")
                    message_lines.append(f"     🚨 사유: {reason_kr}")
                    message_lines.append("")
            else:
                message_lines.append(f"\n🔴 *매도 신호*: 없음")
                message_lines.append("  - 모든 보유 종목이 정상 범위 내에 있습니다.")
                message_lines.append("")
            
            # 투자 전략 및 주의사항
            message_lines.append("-"*40)
            if regime_info:
                if regime_info['regime'] == 'bull':
                    message_lines.append("💡 *투자 전략*")
                    message_lines.append(f"  ✅ 현재 {regime_name.get(regime_info['regime'])} 유지 중")
                    message_lines.append(f"  ✅ 공격적 포지션 권장: {regime_info['position_ratio']:.0%}")
                    message_lines.append("  ✅ 적극적 매수 기회 탐색")
                    message_lines.append("")
                    message_lines.append("⚠️ *주의사항*")
                    message_lines.append("  - 과도한 레버리지 주의")
                    message_lines.append("  - 단기 급등종목 경계")
                    message_lines.append("  - 레짐 변경 신호 모니터링")
                elif regime_info['regime'] == 'bear':
                    message_lines.append("🚨 *투자 전략*")
                    message_lines.append(f"  ⚠️ 현재 {regime_name.get(regime_info['regime'])} 진입")
                    message_lines.append(f"  ⚠️ 방어적 포지션 권장: {regime_info['position_ratio']:.0%}")
                    message_lines.append("  ⚠️ 현금 비중 확대 권장")
                    message_lines.append("")
                    message_lines.append("🛑 *주의사항*")
                    message_lines.append("  - 신규 매수 자제")
                    message_lines.append("  - 손절 라인 엄수 준수")
                    message_lines.append("  - 변동성 확대 대비")
                else:
                    message_lines.append("🧐 *투자 전략*")
                    message_lines.append(f"  ➡️ 현재 {regime_name.get(regime_info['regime'])} 진입")
                    message_lines.append(f"  ➡️ 중립적 포지션 권장: {regime_info['position_ratio']:.0%}")
                    message_lines.append("  ➡️ 선별적 매수 전략")
                    message_lines.append("")
                    message_lines.append("📌 *주의사항*")
                    message_lines.append("  - 레짐 방향성 확인 필요")
                    message_lines.append("  - 고품질 종목 선별")
                    message_lines.append("  - 리스크 관리 철저")
            
            message_lines.append("")
            message_lines.append("="*40)
            message_lines.append(f"🕒 생성 시간: {datetime.now().strftime('%H:%M:%S')}")
            message_lines.append("="*40)
            
            message = "\n".join(message_lines)
            
            # 텔레그램 전송
            self.notifier.send_message(message, parse_mode='Markdown')
            logger.info("✅ 일일 리포트 텔레그램 전송 완료")
                
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}", exc_info=True)
