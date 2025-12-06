#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/weekly_report_alert.py
주간 투자 리포트 및 텔레그램 알림

매주 토요일 10:00 실행
주간 성과 요약, 손절 실행 내역, 다음 주 전략
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import pykrx.stock as stock

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.script_base import ScriptBase, handle_script_errors
from extensions.automation.portfolio_helper import PortfolioHelper
from extensions.notification.telegram_helper import TelegramHelper
from core.strategy.market_regime_detector import MarketRegimeDetector
from extensions.automation.price_updater import PriceUpdater

# 스크립트 베이스 초기화
script = ScriptBase("weekly_report_alert")
logger = script.logger


class WeeklyReport:
    """주간 리포트 클래스"""
    
    def __init__(self):
        self.price_updater = PriceUpdater()
        self.telegram = TelegramHelper()
        self.regime_detector = MarketRegimeDetector()
        self.today = date.today()
        
        # 주간 기간 계산 (월~금)
        self.week_start = self.today - timedelta(days=self.today.weekday())  # 월요일
        self.week_end = self.week_start + timedelta(days=4)  # 금요일
    
    def get_market_regime(self):
        """시장 레짐 조회"""
        try:
            today_str = self.today.strftime('%Y%m%d')
            from_date = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y%m%d')
            kospi = stock.get_index_ohlcv_by_date(from_date, today_str, "1001")
            
            if kospi.empty:
                return 'neutral', 0.5
                
            kospi.rename(columns={'시가': 'Open', '고가': 'High', '저가': 'Low', '종가': 'Close', '거래량': 'Volume'}, inplace=True)
            return self.regime_detector.detect_regime(kospi, self.today)
        except:
            return 'neutral', 0.5

    def generate_report(self) -> str:
        """주간 리포트 생성"""
        try:
            # 포트폴리오 현황 (가격 업데이트 포함)
            data = self.price_updater.update_prices()
            if not data:
                return self._format_error_message()
            
            summary = data['summary']
            holdings_detail = data['holdings_detail']
            # holdings_count도 갱신된 summary 기준으로 재계산하거나 data에서 가져옴
            # PriceUpdater는 holdings_count를 summary에 포함시키지 않고 원본 data 구조 유지
            # 하지만 summary['holdings_count']는 PortfolioLoader에서 온 것일 수 있음.
            # 안전하게 재계산
            if holdings_detail is not None:
                active_holdings = holdings_detail[holdings_detail['quantity'] > 0]
                holdings_count = len(active_holdings)
            else:
                holdings_count = 0
            
            # 레짐 조회
            regime, confidence = self.get_market_regime()
            
            # 메시지 생성
            message = self._format_header()
            message += self._format_portfolio_summary(summary, holdings_count)
            message += self._format_top_performers(holdings_detail)
            message += self._format_risk_analysis(holdings_detail)
            message += self._format_next_week_strategy(regime, confidence)
            message += self._format_footer()
            
            return message
        
        except Exception as e:
            logger.error(f"주간 리포트 생성 실패: {e}", exc_info=True)
            return self._format_error_message()
    
    def _format_header(self) -> str:
        """헤더 포맷"""
        return (
            "*📊 주간 투자 리포트*\n\n"
            f"📅 기간: {self.week_start.strftime('%m/%d')} ~ "
            f"{self.week_end.strftime('%m/%d')} ({self.week_start.strftime('%Y년 %W주차')})\n"
            f"📆 리포트 생성: {self.today.strftime('%Y년 %m월 %d일 (%A)')}\n\n"
        )
    
    def _format_portfolio_summary(
        self,
        summary: Dict[str, Any],
        holdings_count: int
    ) -> str:
        """포트폴리오 요약 포맷"""
        message = "*💼 포트폴리오 현황*\n"
        message += f"총 평가액: `{summary['total_value']:,.0f}원`\n"
        message += f"총 매입액: `{summary['total_cost']:,.0f}원`\n"
        message += f"평가손익: {PortfolioHelper.format_return(summary['return_amount'], summary['return_pct'])}\n"
        message += f"보유 종목: `{holdings_count}개`\n\n"
        return message
    
    def _format_top_performers(self, holdings_detail) -> str:
        """보유 종목 성과 (보유 수량 > 0 인 것만)"""
        if holdings_detail is None or holdings_detail.empty:
            return ""
        
        # 보유 수량이 있는 것만 필터링
        active_holdings = holdings_detail[holdings_detail['quantity'] > 0].copy()
        
        if active_holdings.empty:
            return "*📈 주간 성과*\n보유 종목이 없습니다.\n\n"

        # 수익률 기준 정렬
        sorted_holdings = active_holdings.sort_values('return_pct', ascending=False)
        
        message = "*📈 내 보유 종목 성과 Top 5*\n\n"
        
        # 상위 5개
        message += "_🔴 수익 Top 5_\n"
        for i, (_, holding) in enumerate(sorted_holdings.head(5).iterrows(), 1):
            name = holding.get('name', '알 수 없음')
            return_pct = holding.get('return_pct', 0)
            return_amount = holding.get('return_amount', 0)
            message += f"{i}. {name}: `{return_pct:+.2f}%` (`{return_amount:+,.0f}원`)\n"
        
        message += "\n_🔵 손실 Top 5_\n"
        # 하위 5개
        for i, (_, holding) in enumerate(sorted_holdings.tail(5).iloc[::-1].iterrows(), 1):
            name = holding.get('name', '알 수 없음')
            return_pct = holding.get('return_pct', 0)
            return_amount = holding.get('return_amount', 0)
            message += f"{i}. {name}: `{return_pct:+.2f}%` (`{return_amount:+,.0f}원`)\n"
        
        message += "\n"
        return message
    
    def _format_risk_analysis(self, holdings_detail) -> str:
        """리스크 분석 포맷"""
        if holdings_detail is None or holdings_detail.empty:
            return ""
        
        stop_loss_threshold = -7.0
        stop_loss_targets = []
        near_stop_loss = []
        
        for _, holding in holdings_detail.iterrows():
            if holding['quantity'] <= 0: continue
            
            return_pct = holding.get('return_pct', 0)
            name = holding.get('name', '알 수 없음')
            
            if return_pct <= stop_loss_threshold:
                stop_loss_targets.append((name, return_pct))
            elif stop_loss_threshold < return_pct <= -5.0:
                near_stop_loss.append((name, return_pct))
        
        message = "*🚨 리스크 분석*\n\n"
        
        if stop_loss_targets:
            message += f"_🔴 손절 대상 ({len(stop_loss_targets)}개)_\n"
            for name, return_pct in stop_loss_targets[:5]:
                message += f"• {name}: `{return_pct:.2f}%`\n"
            message += "⚠️ *즉시 매도 검토 필요*\n\n"
        
        if near_stop_loss:
            message += f"_⚠️ 손절 근접 ({len(near_stop_loss)}개)_\n"
            for name, return_pct in near_stop_loss[:5]:
                message += f"• {name}: `{return_pct:.2f}%`\n"
            message += "💡 모니터링 필요\n\n"
        
        if not stop_loss_targets and not near_stop_loss:
            message += "✅ 모든 종목 안전 범위 내\n\n"
        
        return message
    
    def _format_next_week_strategy(self, regime: str, confidence: float) -> str:
        """다음 주 전략 포맷 (동적 생성)"""
        next_monday = self.week_start + timedelta(days=7)
        next_friday = next_monday + timedelta(days=4)
        
        regime_kr = {'bull': '상승장', 'neutral': '중립장', 'bear': '하락장'}.get(regime, '중립장')
        conf_pct = confidence * 100 if confidence <= 1.0 else confidence # 0~1 or 0~100 handle
        
        message = "*📋 다음 주 전략*\n\n"
        message += f"📅 기간: {next_monday.strftime('%m/%d')} ~ {next_friday.strftime('%m/%d')}\n"
        message += f"📊 시장 전망: *{regime_kr}* (신뢰도 {conf_pct:.0f}%)\n\n"
        
        message += "_전략 포인트:_\n"
        if regime == 'bull':
            message += "• 상승 추세 지속 시 비중 확대\n"
            message += "• 주도 섹터(반도체/2차전지) 중심 매매\n"
            message += "• 손절 라인 상향 조정 (Trailing Stop)\n"
        elif regime == 'bear':
            message += "• 🚨 보수적 대응 필요 (현금 비중 확대)\n"
            message += "• 신규 매수 자제 및 손절 기준 엄수\n"
            message += "• 인버스/달러 등 헷지 자산 고려\n"
        else: # neutral
            message += "• 박스권 장세 예상 (단기 트레이딩)\n"
            message += "• 저평가 종목 분할 매수\n"
            message += "• 변동성 축소 시 방향성 탐색\n"
            
        message += "• 평일 15:30 손절 모니터링 필참\n\n"
        return message

    def _format_footer(self) -> str:
        """푸터 포맷"""
        return (
            "*🎯 투자 원칙*\n"
            "• 손절은 빠를수록 좋다\n"
            "• 데이터 기반 의사결정\n"
            "• 백테스트 결과 신뢰\n"
            "• 규율 있는 투자\n\n"
            "_다음 주도 성공적인 투자 되세요!_ 🚀"
        )

    def _format_error_message(self) -> str:
        """에러 메시지 포맷"""
        return (
            "*⚠️ 주간 리포트 생성 실패*\n\n"
            "포트폴리오 데이터를 불러올 수 없습니다.\n"
            "holdings.json 파일을 확인해주세요."
        )
    
    def send_report(self) -> bool:
        """주간 리포트 전송"""
        script.log_header("주간 리포트 생성 및 전송")
        
        try:
            message = self.generate_report()
            
            success = self.telegram.send_with_logging(
                message,
                "주간 리포트 전송 성공",
                "주간 리포트 전송 실패"
            )
            
            script.log_footer()
            return success
        
        except Exception as e:
            logger.error(f"주간 리포트 전송 실패: {e}", exc_info=True)
            return False


@handle_script_errors("주간 리포트")
def main():
    """메인 실행 함수"""
    report = WeeklyReport()
    success = report.send_report()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
