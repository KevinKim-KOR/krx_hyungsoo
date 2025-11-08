# -*- coding: utf-8 -*-
"""
extensions/automation/weekly_report.py
주간 리포트 생성

기능:
- 주간 성과 요약
- 레짐 변경 히스토리
- 다음 주 전망
"""

from datetime import date, datetime, timedelta
from typing import Optional, Dict, List
import logging

from extensions.automation.regime_monitor import RegimeMonitor
from extensions.automation.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class WeeklyReport:
    """
    주간 리포트 생성 클래스
    
    기능:
    1. 주간 성과 요약
    2. 레짐 변경 히스토리
    3. 다음 주 전망
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
        self.notifier = TelegramNotifier(
            bot_token=bot_token,
            chat_id=chat_id,
            enabled=telegram_enabled
        )
    
    def generate_report(
        self,
        end_date: Optional[date] = None,
        portfolio_history: Optional[List[Dict]] = None
    ) -> str:
        """
        주간 리포트 생성
        
        Args:
            end_date: 종료 날짜 (None이면 오늘)
            portfolio_history: 포트폴리오 이력
                [{'date': date, 'value': float, 'return_pct': float}, ...]
        
        Returns:
            str: 리포트 텍스트
        """
        if end_date is None:
            end_date = date.today()
        
        start_date = end_date - timedelta(days=7)
        
        logger.info(f"주간 리포트 생성: {start_date} ~ {end_date}")
        
        # 1. 레짐 요약
        regime_summary = self.regime_monitor.get_regime_summary(days=7)
        
        # 2. 레짐 히스토리
        regime_history = self.regime_monitor.load_history(days=7)
        
        # 3. 리포트 작성
        report_lines = []
        report_lines.append("=" * 50)
        report_lines.append("📊 주간 투자 리포트")
        report_lines.append("=" * 50)
        report_lines.append(
            f"📅 기간: {start_date.strftime('%Y-%m-%d')} ~ "
            f"{end_date.strftime('%Y-%m-%d')}"
        )
        report_lines.append("")
        
        # 포트폴리오 성과
        if portfolio_history and len(portfolio_history) > 0:
            report_lines.append("💼 주간 성과")
            report_lines.append("-" * 50)
            
            # 주간 수익률 계산
            start_value = portfolio_history[0]['value']
            end_value = portfolio_history[-1]['value']
            weekly_return = ((end_value - start_value) / start_value) * 100
            
            report_lines.append(f"  시작 평가액: {start_value:,.0f}원")
            report_lines.append(f"  종료 평가액: {end_value:,.0f}원")
            report_lines.append(f"  주간 수익률: {weekly_return:+.2f}%")
            
            # 최고/최저
            max_value = max(h['value'] for h in portfolio_history)
            min_value = min(h['value'] for h in portfolio_history)
            report_lines.append(f"  최고 평가액: {max_value:,.0f}원")
            report_lines.append(f"  최저 평가액: {min_value:,.0f}원")
            
            report_lines.append("")
        
        # 레짐 분석
        if regime_summary:
            report_lines.append("🎯 시장 레짐 분석")
            report_lines.append("-" * 50)
            
            regime_counts = regime_summary.get('regime_counts', {})
            total_days = regime_summary.get('total_days', 0)
            
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
            
            for regime, count in regime_counts.items():
                emoji = regime_emoji.get(regime, '❓')
                name = regime_name.get(regime, regime)
                pct = (count / total_days * 100) if total_days > 0 else 0
                report_lines.append(f"  {emoji} {name}: {count}일 ({pct:.1f}%)")
            
            changes = regime_summary.get('regime_changes', 0)
            report_lines.append(f"  🔄 레짐 변경: {changes}회")
            
            current_regime = regime_summary.get('current_regime', 'unknown')
            current_confidence = regime_summary.get('current_confidence', 0)
            current_emoji = regime_emoji.get(current_regime, '❓')
            current_name = regime_name.get(current_regime, current_regime)
            
            report_lines.append("")
            report_lines.append(f"  현재 레짐: {current_emoji} {current_name}")
            report_lines.append(f"  신뢰도: {current_confidence:.1%}")
            report_lines.append("")
        
        # 레짐 변경 히스토리
        if regime_history and len(regime_history) > 1:
            report_lines.append("📜 레짐 변경 히스토리")
            report_lines.append("-" * 50)
            
            regime_emoji = {
                'bull': '📈',
                'bear': '📉',
                'neutral': '➡️'
            }
            
            for i in range(len(regime_history) - 1):
                current = regime_history[i]
                next_item = regime_history[i + 1]
                
                if current['regime'] != next_item['regime']:
                    old_emoji = regime_emoji.get(current['regime'], '❓')
                    new_emoji = regime_emoji.get(next_item['regime'], '❓')
                    
                    report_lines.append(
                        f"  {next_item['date']}: "
                        f"{old_emoji} {current['regime']} → "
                        f"{new_emoji} {next_item['regime']}"
                    )
            
            if not any(
                regime_history[i]['regime'] != regime_history[i+1]['regime']
                for i in range(len(regime_history) - 1)
            ):
                report_lines.append("  변경 없음")
            
            report_lines.append("")
        
        # 다음 주 전망
        report_lines.append("🔮 다음 주 전망")
        report_lines.append("-" * 50)
        
        if regime_summary:
            current_regime = regime_summary.get('current_regime', 'unknown')
            current_confidence = regime_summary.get('current_confidence', 0)
            
            if current_regime == 'bull' and current_confidence > 0.7:
                report_lines.append("  ✅ 상승 추세 지속 예상")
                report_lines.append("  💡 공격적 포지션 유지")
            elif current_regime == 'bear' and current_confidence > 0.7:
                report_lines.append("  ⚠️ 하락 추세 지속 예상")
                report_lines.append("  💡 방어적 포지션 권장")
            else:
                report_lines.append("  ➡️ 중립 추세 예상")
                report_lines.append("  💡 균형 잡힌 포지션 유지")
        
        report_lines.append("")
        report_lines.append("=" * 50)
        report_lines.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 50)
        
        report_text = "\n".join(report_lines)
        
        # 텔레그램 전송
        self._send_to_telegram(report_text)
        
        return report_text
    
    def _send_to_telegram(self, report_text: str):
        """
        텔레그램으로 리포트 전송
        
        Args:
            report_text: 리포트 텍스트
        """
        try:
            # 주간 리포트는 전체 텍스트 전송
            self.notifier.send_message(
                f"📊 *주간 리포트*\n\n{report_text}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}")
