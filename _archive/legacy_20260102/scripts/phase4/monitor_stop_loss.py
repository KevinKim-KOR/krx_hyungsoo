#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/phase4/monitor_stop_loss.py
실시간 손절 모니터링 및 알림

평일 15:30 실행 (장 마감 30분 전)
손절 기준 -7% 도달 시 텔레그램 알림
"""
import sys
import logging
from datetime import date, datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.portfolio_loader import PortfolioLoader
from extensions.notification.telegram_sender import TelegramSender
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


class StopLossMonitor:
    """손절 모니터링 클래스"""
    
    def __init__(self, stop_loss_pct: float = -7.0):
        """
        Args:
            stop_loss_pct: 손절 기준 (기본 -7%)
        """
        self.stop_loss_pct = stop_loss_pct
        self.loader = PortfolioLoader()
        self.telegram = TelegramSender()
        
        logger.info(f"손절 모니터링 초기화 (기준: {self.stop_loss_pct}%)")
    
    def check_holdings(self) -> List[Dict[str, Any]]:
        """
        보유 종목 손절 체크
        
        Returns:
            손절 대상 종목 리스트
        """
        try:
            # 보유 종목 상세 정보 로드
            holdings_detail = self.loader.get_holdings_detail()
            
            if holdings_detail.empty:
                logger.warning("보유 종목 데이터 없음")
                return []
            
            alerts = []
            
            for _, holding in holdings_detail.iterrows():
                code = holding.get('code')
                name = holding.get('name', f'종목_{code}')
                return_pct = holding.get('return_pct', 0.0)
                current_price = holding.get('current_price', 0)
                avg_price = holding.get('avg_price', 0)
                quantity = holding.get('quantity', 0)
                
                # 손절 기준 체크
                if return_pct <= self.stop_loss_pct:
                    # 손실 금액 계산
                    loss_amount = (current_price - avg_price) * quantity
                    
                    # 손절 기준 초과 정도
                    excess_loss = return_pct - self.stop_loss_pct
                    
                    alerts.append({
                        'code': code,
                        'name': name,
                        'return_pct': return_pct,
                        'current_price': current_price,
                        'avg_price': avg_price,
                        'quantity': quantity,
                        'loss_amount': loss_amount,
                        'excess_loss': excess_loss,
                        'action': 'SELL'
                    })
                    
                    logger.warning(
                        f"손절 대상 발견: {name} ({code}) "
                        f"손실률: {return_pct:.2f}% "
                        f"(기준 초과: {excess_loss:.2f}%p)"
                    )
            
            logger.info(f"손절 체크 완료: {len(holdings_detail)}개 중 {len(alerts)}개 대상")
            return alerts
        
        except Exception as e:
            logger.error(f"손절 체크 실패: {e}", exc_info=True)
            return []
    
    def check_near_stop_loss(self, threshold: float = -5.0) -> List[Dict[str, Any]]:
        """
        손절 라인 근접 종목 체크
        
        Args:
            threshold: 근접 기준 (기본 -5%)
        
        Returns:
            손절 근접 종목 리스트
        """
        try:
            holdings_detail = self.loader.get_holdings_detail()
            
            if holdings_detail.empty:
                return []
            
            near_alerts = []
            
            for _, holding in holdings_detail.iterrows():
                return_pct = holding.get('return_pct', 0.0)
                
                # 손절 라인 근접 체크 (-7% ~ -5%)
                if self.stop_loss_pct < return_pct <= threshold:
                    code = holding.get('code')
                    name = holding.get('name', f'종목_{code}')
                    
                    # 손절까지 남은 여유
                    margin = return_pct - self.stop_loss_pct
                    
                    near_alerts.append({
                        'code': code,
                        'name': name,
                        'return_pct': return_pct,
                        'margin': margin,
                        'action': 'WATCH'
                    })
                    
                    logger.info(
                        f"손절 근접: {name} ({code}) "
                        f"손실률: {return_pct:.2f}% "
                        f"(여유: {margin:.2f}%p)"
                    )
            
            return near_alerts
        
        except Exception as e:
            logger.error(f"손절 근접 체크 실패: {e}", exc_info=True)
            return []
    
    def format_alert_message(
        self,
        alerts: List[Dict[str, Any]],
        near_alerts: List[Dict[str, Any]]
    ) -> str:
        """
        알림 메시지 포맷
        
        Args:
            alerts: 손절 대상 종목
            near_alerts: 손절 근접 종목
        
        Returns:
            포맷된 메시지
        """
        message = "*🚨 손절 모니터링 알림*\n\n"
        message += f"📅 {datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')}\n"
        message += f"⏰ 장 마감 30분 전\n\n"
        
        # 손절 대상
        if alerts:
            message += f"*🔴 손절 대상 ({len(alerts)}개)*\n"
            message += f"_손절 기준: {self.stop_loss_pct}% 이하_\n\n"
            
            for i, alert in enumerate(alerts, 1):
                message += f"{i}. *{alert['name']}* (`{alert['code']}`)\n"
                message += f"   현재가: `{alert['current_price']:,.0f}원`\n"
                message += f"   매입가: `{alert['avg_price']:,.0f}원`\n"
                message += f"   손실률: `{alert['return_pct']:.2f}%` "
                message += f"(기준 초과: `{alert['excess_loss']:.2f}%p`)\n"
                message += f"   손실 금액: `{alert['loss_amount']:,.0f}원`\n"
                message += f"   수량: `{alert['quantity']:,.0f}주`\n"
                message += f"   ⚠️ *즉시 매도 검토 필요*\n\n"
        else:
            message += "*✅ 손절 대상 없음*\n\n"
        
        # 손절 근접
        if near_alerts:
            message += f"*⚠️ 손절 근접 ({len(near_alerts)}개)*\n"
            message += f"_주의 필요 (손절까지 여유 2%p 이내)_\n\n"
            
            for i, alert in enumerate(near_alerts, 1):
                message += f"{i}. {alert['name']} (`{alert['code']}`)\n"
                message += f"   손실률: `{alert['return_pct']:.2f}%` "
                message += f"(여유: `{alert['margin']:.2f}%p`)\n"
                message += f"   💡 모니터링 필요\n\n"
        
        # 액션 가이드
        if alerts or near_alerts:
            message += "*📋 액션 가이드*\n"
            if alerts:
                message += "• 손절 대상: 즉시 매도 검토\n"
            if near_alerts:
                message += "• 손절 근접: 내일 시초가 확인 후 판단\n"
            message += "• 감정적 판단 배제, 기계적 실행\n"
        else:
            message += "_현재 모든 종목 안전 범위 내_ ✅"
        
        return message
    
    def send_alerts(
        self,
        alerts: List[Dict[str, Any]],
        near_alerts: List[Dict[str, Any]]
    ) -> bool:
        """
        텔레그램 알림 전송
        
        Args:
            alerts: 손절 대상 종목
            near_alerts: 손절 근접 종목
        
        Returns:
            전송 성공 여부
        """
        try:
            # 알림 대상이 있을 때만 전송
            if alerts or near_alerts:
                message = self.format_alert_message(alerts, near_alerts)
                success = self.telegram.send_custom(message, parse_mode='Markdown')
                
                if success:
                    logger.info(f"✅ 손절 알림 전송 성공 (대상: {len(alerts)}개, 근접: {len(near_alerts)}개)")
                else:
                    logger.warning("⚠️ 손절 알림 전송 실패")
                
                return success
            else:
                logger.info("손절 대상 없음, 알림 전송 스킵")
                return True
        
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}", exc_info=True)
            return False
    
    def run(self) -> int:
        """
        손절 모니터링 실행
        
        Returns:
            0: 성공, 1: 실패
        """
        logger.info("=" * 60)
        logger.info("손절 모니터링 시작")
        logger.info("=" * 60)
        
        try:
            # 1. 손절 대상 체크
            alerts = self.check_holdings()
            
            # 2. 손절 근접 체크
            near_alerts = self.check_near_stop_loss()
            
            # 3. 알림 전송
            success = self.send_alerts(alerts, near_alerts)
            
            # 4. 결과 로깅
            logger.info("=" * 60)
            logger.info(f"손절 모니터링 완료")
            logger.info(f"손절 대상: {len(alerts)}개")
            logger.info(f"손절 근접: {len(near_alerts)}개")
            logger.info(f"알림 전송: {'성공' if success else '실패'}")
            logger.info("=" * 60)
            
            return 0 if success else 1
        
        except Exception as e:
            logger.error(f"손절 모니터링 실패: {e}", exc_info=True)
            return 1


def main():
    """메인 실행 함수"""
    monitor = StopLossMonitor(stop_loss_pct=-7.0)
    return monitor.run()


if __name__ == "__main__":
    sys.exit(main())
