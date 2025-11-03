# -*- coding: utf-8 -*-
"""
extensions/monitoring/reporter.py
일일 리포트 생성
"""
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

from extensions.realtime.signal_generator import Signal
from .tracker import SignalTracker, PerformanceTracker

logger = logging.getLogger(__name__)


class DailyReporter:
    """일일 리포트 생성기"""
    
    def __init__(
        self,
        signal_tracker: Optional[SignalTracker] = None,
        performance_tracker: Optional[PerformanceTracker] = None
    ):
        """
        Args:
            signal_tracker: 신호 추적기
            performance_tracker: 성과 추적기
        """
        self.signal_tracker = signal_tracker or SignalTracker()
        self.performance_tracker = performance_tracker or PerformanceTracker()
        
        logger.info("DailyReporter 초기화")
    
    def generate_daily_report(
        self,
        report_date: date,
        signals: List[Signal] = None
    ) -> str:
        """
        일일 리포트 생성
        
        Args:
            report_date: 리포트 날짜
            signals: 당일 신호 (선택)
            
        Returns:
            리포트 텍스트 (Markdown)
        """
        lines = [
            f"# 일일 리포트 - {report_date}",
            "",
            "---",
            ""
        ]
        
        # 1. 당일 신호 요약
        if signals:
            lines.append("## 📊 당일 신호")
            lines.append("")
            
            buy_signals = [s for s in signals if s.action == 'BUY']
            sell_signals = [s for s in signals if s.action == 'SELL']
            
            lines.append(f"- **총 신호**: {len(signals)}개")
            lines.append(f"- **매수**: {len(buy_signals)}개")
            lines.append(f"- **매도**: {len(sell_signals)}개")
            lines.append("")
            
            if buy_signals:
                lines.append("### 매수 신호")
                lines.append("")
                for i, signal in enumerate(buy_signals[:5], 1):
                    lines.append(f"{i}. **{signal.code}** ({signal.name})")
                    lines.append(f"   - 신뢰도: {signal.confidence:.1%}, 비중: {signal.target_weight:.1%}")
                    lines.append(f"   - MAPS: {signal.maps_score:.2f}, RSI: {signal.rsi_value:.0f}")
                    lines.append("")
        
        # 2. 최근 30일 신호 통계
        lines.append("## 📈 최근 30일 신호 통계")
        lines.append("")
        
        stats = self.signal_tracker.get_signal_stats(days=30)
        lines.append(f"- **총 신호**: {stats['total_signals']}개")
        lines.append(f"- **매수**: {stats['buy_count']}개")
        lines.append(f"- **매도**: {stats['sell_count']}개")
        lines.append(f"- **평균 신뢰도**: {stats['avg_confidence']:.2f}")
        lines.append(f"- **평균 MAPS**: {stats['avg_maps']:.2f}")
        lines.append("")
        
        # 3. 성과 요약
        latest_perf = self.performance_tracker.get_latest_performance()
        
        if latest_perf:
            lines.append("## 💰 포트폴리오 현황")
            lines.append("")
            lines.append(f"- **날짜**: {latest_perf['date']}")
            lines.append(f"- **총 자산**: {latest_perf['total_value']:,.0f}원")
            lines.append(f"- **현금**: {latest_perf['cash']:,.0f}원")
            lines.append(f"- **포지션 가치**: {latest_perf['positions_value']:,.0f}원")
            lines.append(f"- **포지션 수**: {latest_perf['position_count']}개")
            lines.append(f"- **일일 수익률**: {latest_perf['daily_return']:.2%}")
            lines.append(f"- **누적 수익률**: {latest_perf['cumulative_return']:.2%}")
            lines.append("")
        
        # 4. 최근 7일 성과
        week_ago = report_date - timedelta(days=7)
        perf_df = self.performance_tracker.get_performance(week_ago, report_date)
        
        if not perf_df.empty:
            lines.append("## 📅 최근 7일 성과")
            lines.append("")
            lines.append("| 날짜 | 총 자산 | 일일 수익률 | 누적 수익률 |")
            lines.append("|------|---------|-------------|-------------|")
            
            for _, row in perf_df.tail(7).iterrows():
                lines.append(
                    f"| {row['performance_date']} | "
                    f"{row['total_value']:,.0f}원 | "
                    f"{row['daily_return']:.2%} | "
                    f"{row['cumulative_return']:.2%} |"
                )
            lines.append("")
        
        # 5. 푸터
        lines.append("---")
        lines.append("_자동 생성된 리포트입니다._")
        
        return "\n".join(lines)
    
    def save_report(self, report_date: date, content: str, output_dir: Path = None):
        """
        리포트 저장
        
        Args:
            report_date: 리포트 날짜
            content: 리포트 내용
            output_dir: 출력 디렉토리
        """
        if output_dir is None:
            output_dir = Path('reports/daily')
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"report_{report_date:%Y%m%d}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"리포트 저장: {output_file}")
    
    def generate_weekly_summary(self, end_date: date) -> str:
        """
        주간 요약 생성
        
        Args:
            end_date: 종료 날짜
            
        Returns:
            주간 요약 텍스트
        """
        start_date = end_date - timedelta(days=7)
        
        lines = [
            f"# 주간 요약 - {start_date} ~ {end_date}",
            "",
            "---",
            ""
        ]
        
        # 신호 통계
        signals_df = self.signal_tracker.get_signals(start_date, end_date)
        
        if not signals_df.empty:
            buy_count = len(signals_df[signals_df['action'] == 'BUY'])
            sell_count = len(signals_df[signals_df['action'] == 'SELL'])
            
            lines.append("## 📊 신호 통계")
            lines.append("")
            lines.append(f"- **총 신호**: {len(signals_df)}개")
            lines.append(f"- **매수**: {buy_count}개")
            lines.append(f"- **매도**: {sell_count}개")
            lines.append(f"- **평균 신뢰도**: {signals_df['confidence'].mean():.2f}")
            lines.append("")
        
        # 성과 통계
        perf_df = self.performance_tracker.get_performance(start_date, end_date)
        
        if not perf_df.empty:
            first_value = perf_df.iloc[0]['total_value']
            last_value = perf_df.iloc[-1]['total_value']
            weekly_return = (last_value - first_value) / first_value if first_value > 0 else 0
            
            lines.append("## 💰 성과 요약")
            lines.append("")
            lines.append(f"- **시작 자산**: {first_value:,.0f}원")
            lines.append(f"- **종료 자산**: {last_value:,.0f}원")
            lines.append(f"- **주간 수익률**: {weekly_return:.2%}")
            lines.append(f"- **최고 수익률**: {perf_df['daily_return'].max():.2%}")
            lines.append(f"- **최저 수익률**: {perf_df['daily_return'].min():.2%}")
            lines.append("")
        
        lines.append("---")
        lines.append("_자동 생성된 주간 요약입니다._")
        
        return "\n".join(lines)
