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
        텔레그램으로 리포트 전송 (간결한 요약)
        
        Args:
            regime_info: 레짐 정보
            signals: 매매 신호
        """
        try:
            # 간결한 일일 리포트 메시지 생성
            message_lines = []
            message_lines.append("📊 *일일 투자 리포트*")
            message_lines.append(f"📅 {date.today().strftime('%Y년 %m월 %d일')}")
            message_lines.append("")
            
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
                
                message_lines.append("🎯 *시장 레짐*")
                message_lines.append(f"  {emoji} 현재: {name}")
                message_lines.append(f"  📊 신뢰도: {regime_info['confidence']:.1%}")
                message_lines.append(f"  💪 포지션: {regime_info['position_ratio']:.0%}")
                
                if regime_info.get('defense_mode'):
                    message_lines.append("  ⚠️ 방어 모드 활성")
                
                message_lines.append("")
            
            # 매매 신호 요약
            buy_signals = signals.get('buy_signals', [])
            sell_signals = signals.get('sell_signals', [])
            
            message_lines.append("📈 *매매 신호*")
            
            if buy_signals:
                message_lines.append(f"  🟢 매수: {len(buy_signals)}개")
                for i, signal in enumerate(buy_signals[:3], 1):  # 상위 3개만
                    message_lines.append(
                        f"    {i}. `{signal['code']}` (MAPS: {signal['maps_score']:.1f})"
                    )
                if len(buy_signals) > 3:
                    message_lines.append(f"    ... 외 {len(buy_signals)-3}개")
            else:
                message_lines.append("  🟢 매수: 없음")
            
            message_lines.append("")
            
            if sell_signals:
                message_lines.append(f"  🔴 매도: {len(sell_signals)}개")
                for i, signal in enumerate(sell_signals[:3], 1):
                    message_lines.append(
                        f"    {i}. `{signal['code']}` ({signal['reason']})"
                    )
                if len(sell_signals) > 3:
                    message_lines.append(f"    ... 외 {len(sell_signals)-3}개")
            else:
                message_lines.append("  🔴 매도: 없음")
            
            # 주의사항
            message_lines.append("")
            if regime_info:
                if regime_info['regime'] == 'bull':
                    message_lines.append("⚠️ *주의사항*")
                    message_lines.append(f"  - 현재 {regime_name.get(regime_info['regime'])} 유지 중")
                    message_lines.append(f"  - 포지션 비율 {regime_info['position_ratio']:.0%} 권장")
                elif regime_info['regime'] == 'bear':
                    message_lines.append("⚠️ *주의사항*")
                    message_lines.append(f"  - 현재 {regime_name.get(regime_info['regime'])} 진입")
                    message_lines.append("  - 방어적 포지션 유지")
                    message_lines.append(f"  - 포지션 비율 {regime_info['position_ratio']:.0%} 권장")
                else:
                    message_lines.append("💡 *전략*")
                    message_lines.append(f"  - 중립장 대응 전략")
                    message_lines.append(f"  - 포지션 비율 {regime_info['position_ratio']:.0%} 유지")
            
            message = "\n".join(message_lines)
            
            # 텔레그램 전송
            self.notifier.send_message(message, parse_mode='Markdown')
            logger.info("✅ 일일 리포트 텔레그램 전송 완료")
                
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}", exc_info=True)
