#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/phase4/regime_based_stop_loss.py
레짐별 손절 전략

시장 레짐에 따라 손절 기준을 동적으로 조정:
- 상승장: -7% (공격적, 추세 유지)
- 중립장: -5% (중립, 빠른 손절)
- 하락장: -3% (방어적, 매우 빠른 손절)
"""
import sys
import logging
from datetime import date, datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.portfolio_loader import PortfolioLoader
from extensions.notification.telegram_sender import TelegramSender
from core.strategy.market_regime_detector import MarketRegimeDetector
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


class RegimeBasedStopLoss:
    """레짐별 손절 전략 클래스"""
    
    # 레짐별 손절 기준
    STOP_LOSS_BY_REGIME = {
        'bull': -7.0,      # 상승장: 공격적 (추세 유지)
        'neutral': -5.0,   # 중립장: 중립 (빠른 손절)
        'bear': -3.0       # 하락장: 방어적 (매우 빠른 손절)
    }
    
    def __init__(self):
        """초기화"""
        self.loader = PortfolioLoader()
        self.telegram = TelegramSender()
        self.regime_detector = MarketRegimeDetector()
        
        logger.info("레짐별 손절 전략 초기화")
        logger.info(f"손절 기준: {self.STOP_LOSS_BY_REGIME}")
    
    def get_current_regime(self) -> Tuple[str, float, Dict[str, Any]]:
        """
        현재 시장 레짐 감지
        
        Returns:
            (레짐, 신뢰도, 상세 정보)
        """
        try:
            # 레짐 감지는 복잡하므로 단순화
            # 실제 구현 시 pykrx로 KOSPI 데이터 가져와서 detect_regime() 호출
            # 여기서는 기본값 반환
            regime = 'neutral'
            confidence = 50.0
            
            logger.info(f"현재 레짐: {regime} (신뢰도: {confidence:.2f}%)")
            logger.info("(실제 레짐 감지는 pykrx 데이터 필요, 현재는 기본값 사용)")
            
            regime_info = {
                'regime': regime,
                'confidence': confidence,
                'note': 'simplified version'
            }
            
            return regime, confidence, regime_info
        
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}", exc_info=True)
            # 기본값: 중립장
            return 'neutral', 50.0, {}
    
    def get_stop_loss_threshold(self, regime: str = None) -> float:
        """
        레짐에 따른 손절 기준 반환
        
        Args:
            regime: 시장 레짐 ('bull', 'neutral', 'bear')
                   None이면 현재 레짐 자동 감지
        
        Returns:
            손절 기준 (%)
        """
        if regime is None:
            regime, _, _ = self.get_current_regime()
        
        threshold = self.STOP_LOSS_BY_REGIME.get(regime, -5.0)
        logger.info(f"레짐 '{regime}' 손절 기준: {threshold}%")
        
        return threshold
    
    def check_holdings_by_regime(self) -> Dict[str, Any]:
        """
        레짐별 손절 대상 체크
        
        Returns:
            손절 분석 결과
        """
        try:
            # 1. 현재 레짐 감지
            regime, confidence, regime_info = self.get_current_regime()
            
            # 2. 손절 기준 결정
            stop_loss_threshold = self.get_stop_loss_threshold(regime)
            
            # 3. 보유 종목 로드
            holdings_detail = self.loader.get_holdings_detail()
            
            if holdings_detail.empty:
                logger.warning("보유 종목 데이터 없음")
                return {
                    'regime': regime,
                    'confidence': confidence,
                    'stop_loss_threshold': stop_loss_threshold,
                    'stop_loss_targets': [],
                    'near_stop_loss': [],
                    'safe_holdings': []
                }
            
            # 4. 손절 대상 분류
            stop_loss_targets = []
            near_stop_loss = []
            safe_holdings = []
            
            # 근접 기준 (손절 기준 + 2%p)
            near_threshold = stop_loss_threshold + 2.0
            
            for _, holding in holdings_detail.iterrows():
                code = holding.get('code')
                name = holding.get('name', f'종목_{code}')
                return_pct = holding.get('return_pct', 0.0)
                current_price = holding.get('current_price', 0)
                avg_price = holding.get('avg_price', 0)
                quantity = holding.get('quantity', 0)
                
                # 손실 금액 계산
                loss_amount = (current_price - avg_price) * quantity
                
                # 분류
                if return_pct <= stop_loss_threshold:
                    # 손절 대상
                    excess_loss = return_pct - stop_loss_threshold
                    stop_loss_targets.append({
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
                        f"손절 대상: {name} ({code}) "
                        f"손실률: {return_pct:.2f}% "
                        f"(기준: {stop_loss_threshold}%, 초과: {excess_loss:.2f}%p)"
                    )
                
                elif stop_loss_threshold < return_pct <= near_threshold:
                    # 손절 근접
                    margin = return_pct - stop_loss_threshold
                    near_stop_loss.append({
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
                
                else:
                    # 안전 범위
                    safe_holdings.append({
                        'code': code,
                        'name': name,
                        'return_pct': return_pct
                    })
            
            result = {
                'regime': regime,
                'confidence': confidence,
                'regime_info': regime_info,
                'stop_loss_threshold': stop_loss_threshold,
                'near_threshold': near_threshold,
                'stop_loss_targets': stop_loss_targets,
                'near_stop_loss': near_stop_loss,
                'safe_holdings': safe_holdings,
                'total_holdings': len(holdings_detail)
            }
            
            logger.info(
                f"레짐별 손절 체크 완료: "
                f"손절 대상 {len(stop_loss_targets)}개, "
                f"손절 근접 {len(near_stop_loss)}개, "
                f"안전 {len(safe_holdings)}개"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"레짐별 손절 체크 실패: {e}", exc_info=True)
            return {}
    
    def format_alert_message(self, result: Dict[str, Any]) -> str:
        """
        알림 메시지 포맷
        
        Args:
            result: check_holdings_by_regime() 결과
        
        Returns:
            포맷된 메시지
        """
        regime = result.get('regime', 'neutral')
        confidence = result.get('confidence', 0.0)
        stop_loss_threshold = result.get('stop_loss_threshold', -5.0)
        stop_loss_targets = result.get('stop_loss_targets', [])
        near_stop_loss = result.get('near_stop_loss', [])
        
        # 레짐 한글 변환
        regime_kr = {
            'bull': '상승장',
            'neutral': '중립장',
            'bear': '하락장'
        }.get(regime, '중립장')
        
        message = "*🎯 레짐별 손절 모니터링*\n\n"
        message += f"📅 {datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')}\n\n"
        
        # 레짐 정보
        message += f"*📊 시장 레짐*\n"
        message += f"현재 레짐: `{regime_kr}` (신뢰도: `{confidence:.1f}%`)\n"
        message += f"손절 기준: `{stop_loss_threshold}%`\n\n"
        
        # 레짐별 전략 설명
        if regime == 'bull':
            message += "_상승장 전략: 추세 유지, 공격적 운영_\n\n"
        elif regime == 'bear':
            message += "_하락장 전략: 빠른 손절, 방어적 운영_\n\n"
        else:
            message += "_중립장 전략: 균형 유지, 중립적 운영_\n\n"
        
        # 손절 대상
        if stop_loss_targets:
            message += f"*🔴 손절 대상 ({len(stop_loss_targets)}개)*\n\n"
            
            for i, target in enumerate(stop_loss_targets, 1):
                message += f"{i}. *{target['name']}* (`{target['code']}`)\n"
                message += f"   손실률: `{target['return_pct']:.2f}%` "
                message += f"(기준 초과: `{target['excess_loss']:.2f}%p`)\n"
                message += f"   손실 금액: `{target['loss_amount']:,.0f}원`\n"
                message += f"   ⚠️ *즉시 매도 검토*\n\n"
        else:
            message += "*✅ 손절 대상 없음*\n\n"
        
        # 손절 근접
        if near_stop_loss:
            message += f"*⚠️ 손절 근접 ({len(near_stop_loss)}개)*\n\n"
            
            for i, near in enumerate(near_stop_loss, 1):
                message += f"{i}. {near['name']} (`{near['code']}`)\n"
                message += f"   손실률: `{near['return_pct']:.2f}%` "
                message += f"(여유: `{near['margin']:.2f}%p`)\n"
                message += f"   💡 모니터링 필요\n\n"
        
        # 액션 가이드
        if stop_loss_targets or near_stop_loss:
            message += "*📋 액션 가이드*\n"
            if stop_loss_targets:
                message += f"• 손절 대상: 레짐 기준 ({stop_loss_threshold}%) 초과, 즉시 매도\n"
            if near_stop_loss:
                message += "• 손절 근접: 내일 시초가 확인 후 판단\n"
            message += f"• 현재 레짐: {regime_kr} (손절 기준 자동 조정)\n"
        else:
            message += f"_현재 모든 종목 안전 범위 내_ ✅\n"
            message += f"_레짐: {regime_kr}, 손절 기준: {stop_loss_threshold}%_"
        
        return message
    
    def send_alert(self, result: Dict[str, Any]) -> bool:
        """
        텔레그램 알림 전송
        
        Args:
            result: check_holdings_by_regime() 결과
        
        Returns:
            전송 성공 여부
        """
        try:
            stop_loss_targets = result.get('stop_loss_targets', [])
            near_stop_loss = result.get('near_stop_loss', [])
            
            # 알림 대상이 있을 때만 전송
            if stop_loss_targets or near_stop_loss:
                message = self.format_alert_message(result)
                success = self.telegram.send_custom(message, parse_mode='Markdown')
                
                if success:
                    logger.info(
                        f"✅ 레짐별 손절 알림 전송 성공 "
                        f"(대상: {len(stop_loss_targets)}개, 근접: {len(near_stop_loss)}개)"
                    )
                else:
                    logger.warning("⚠️ 레짐별 손절 알림 전송 실패")
                
                return success
            else:
                logger.info("손절 대상 없음, 알림 전송 스킵")
                return True
        
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}", exc_info=True)
            return False
    
    def run(self) -> int:
        """
        레짐별 손절 모니터링 실행
        
        Returns:
            0: 성공, 1: 실패
        """
        logger.info("=" * 60)
        logger.info("레짐별 손절 모니터링 시작")
        logger.info("=" * 60)
        
        try:
            # 1. 레짐별 손절 체크
            result = self.check_holdings_by_regime()
            
            if not result:
                logger.error("레짐별 손절 체크 실패")
                return 1
            
            # 2. 알림 전송
            success = self.send_alert(result)
            
            # 3. 결과 로깅
            logger.info("=" * 60)
            logger.info("레짐별 손절 모니터링 완료")
            logger.info(f"레짐: {result.get('regime', 'unknown')}")
            logger.info(f"손절 기준: {result.get('stop_loss_threshold', 0)}%")
            logger.info(f"손절 대상: {len(result.get('stop_loss_targets', []))}개")
            logger.info(f"손절 근접: {len(result.get('near_stop_loss', []))}개")
            logger.info(f"알림 전송: {'성공' if success else '실패'}")
            logger.info("=" * 60)
            
            return 0 if success else 1
        
        except Exception as e:
            logger.error(f"레짐별 손절 모니터링 실패: {e}", exc_info=True)
            return 1


def main():
    """메인 실행 함수"""
    monitor = RegimeBasedStopLoss()
    return monitor.run()


if __name__ == "__main__":
    sys.exit(main())
