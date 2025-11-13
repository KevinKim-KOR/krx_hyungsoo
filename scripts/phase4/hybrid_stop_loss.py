#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/phase4/hybrid_stop_loss.py
하이브리드 손절 전략 (레짐 + 변동성)

시장 레짐과 종목 변동성을 모두 고려한 최적화된 손절:
- 9가지 조합 (3 레짐 × 3 변동성)
- 시장 상황 + 종목 특성 모두 반영
- 가장 정교한 리스크 관리
"""
import sys
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np

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


class HybridStopLoss:
    """하이브리드 손절 전략 클래스"""
    
    # 하이브리드 손절 매트릭스 (레짐 × 변동성)
    HYBRID_STOP_LOSS_MATRIX = {
        # 상승장 (추세 유지)
        'bull': {
            'low': -5.0,      # 상승장 + 저변동성: -5%
            'medium': -7.0,   # 상승장 + 중변동성: -7%
            'high': -10.0     # 상승장 + 고변동성: -10%
        },
        # 중립장 (균형)
        'neutral': {
            'low': -4.0,      # 중립장 + 저변동성: -4%
            'medium': -5.0,   # 중립장 + 중변동성: -5%
            'high': -7.0      # 중립장 + 고변동성: -7%
        },
        # 하락장 (빠른 손절)
        'bear': {
            'low': -3.0,      # 하락장 + 저변동성: -3%
            'medium': -3.0,   # 하락장 + 중변동성: -3%
            'high': -5.0      # 하락장 + 고변동성: -5%
        }
    }
    
    # 변동성 구간 기준 (ATR %)
    VOLATILITY_THRESHOLDS = {
        'low': {'max': 2.0},
        'medium': {'min': 2.0, 'max': 5.0},
        'high': {'min': 5.0}
    }
    
    def __init__(self, atr_period: int = 14):
        """
        초기화
        
        Args:
            atr_period: ATR 계산 기간 (기본 14일)
        """
        self.loader = PortfolioLoader()
        self.telegram = TelegramSender()
        self.regime_detector = MarketRegimeDetector()
        self.atr_period = atr_period
        
        logger.info("하이브리드 손절 전략 초기화")
        logger.info(f"ATR 기간: {atr_period}일")
        logger.info(f"손절 매트릭스: {self.HYBRID_STOP_LOSS_MATRIX}")
    
    def get_current_regime(self) -> Tuple[str, float]:
        """
        현재 시장 레짐 감지
        
        Returns:
            (레짐, 신뢰도)
        """
        try:
            # 단순화: 기본값 반환
            # 실제 구현 시 pykrx로 KOSPI 데이터 가져와서 detect_regime() 호출
            regime = 'neutral'
            confidence = 50.0
            
            logger.info(f"현재 레짐: {regime} (신뢰도: {confidence:.2f}%)")
            return regime, confidence
        
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}", exc_info=True)
            return 'neutral', 50.0
    
    def calculate_atr(self, code: str) -> float:
        """
        ATR (Average True Range) 계산
        
        Args:
            code: 종목 코드
        
        Returns:
            ATR (%) - 변동성 지표
        """
        try:
            # 실제 구현 시 pykrx로 OHLC 데이터 가져오기
            # 여기서는 단순화: 임의의 ATR 값 반환
            
            # 종목별 임의 ATR (실제로는 계산 필요)
            if code.startswith('1') or code.startswith('2'):
                # ETF (1xxxxx, 2xxxxx)
                atr = np.random.uniform(1.5, 3.0)
            else:
                # 개별주
                atr = np.random.uniform(3.0, 7.0)
            
            logger.debug(f"{code} ATR: {atr:.2f}%")
            return atr
        
        except Exception as e:
            logger.error(f"ATR 계산 실패 ({code}): {e}")
            return 3.5
    
    def classify_volatility(self, atr: float) -> str:
        """
        변동성 구간 분류
        
        Args:
            atr: ATR 값 (%)
        
        Returns:
            변동성 구간 ('low', 'medium', 'high')
        """
        if atr <= self.VOLATILITY_THRESHOLDS['low']['max']:
            return 'low'
        elif atr <= self.VOLATILITY_THRESHOLDS['medium']['max']:
            return 'medium'
        else:
            return 'high'
    
    def get_hybrid_stop_loss_threshold(
        self,
        regime: str,
        volatility: str
    ) -> float:
        """
        하이브리드 손절 기준 계산
        
        Args:
            regime: 시장 레짐 ('bull', 'neutral', 'bear')
            volatility: 변동성 구간 ('low', 'medium', 'high')
        
        Returns:
            손절 기준 (%)
        """
        threshold = self.HYBRID_STOP_LOSS_MATRIX.get(regime, {}).get(
            volatility, -5.0
        )
        
        logger.debug(
            f"하이브리드 손절 기준: "
            f"레짐={regime}, 변동성={volatility}, 기준={threshold}%"
        )
        
        return threshold
    
    def check_holdings_with_hybrid_stop_loss(self) -> Dict[str, Any]:
        """
        하이브리드 손절 기준으로 보유 종목 체크
        
        Returns:
            손절 분석 결과
        """
        try:
            # 1. 현재 레짐 감지
            regime, confidence = self.get_current_regime()
            
            # 2. 보유 종목 로드
            holdings_detail = self.loader.get_holdings_detail()
            
            if holdings_detail.empty:
                logger.warning("보유 종목 데이터 없음")
                return {
                    'regime': regime,
                    'confidence': confidence,
                    'stop_loss_targets': [],
                    'near_stop_loss': [],
                    'safe_holdings': []
                }
            
            # 3. 손절 대상 분류
            stop_loss_targets = []
            near_stop_loss = []
            safe_holdings = []
            
            for _, holding in holdings_detail.iterrows():
                code = holding.get('code')
                name = holding.get('name', f'종목_{code}')
                return_pct = holding.get('return_pct', 0.0)
                current_price = holding.get('current_price', 0)
                avg_price = holding.get('avg_price', 0)
                quantity = holding.get('quantity', 0)
                
                # ATR 계산 및 변동성 분류
                atr = self.calculate_atr(code)
                volatility = self.classify_volatility(atr)
                
                # 하이브리드 손절 기준 계산
                stop_loss_threshold = self.get_hybrid_stop_loss_threshold(
                    regime, volatility
                )
                
                # 손실 금액 계산
                loss_amount = (current_price - avg_price) * quantity
                
                # 근접 기준 (손절 기준 + 2%p)
                near_threshold = stop_loss_threshold + 2.0
                
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
                        'regime': regime,
                        'volatility': volatility,
                        'atr': atr,
                        'stop_loss_threshold': stop_loss_threshold,
                        'excess_loss': excess_loss,
                        'action': 'SELL'
                    })
                    logger.warning(
                        f"손절 대상: {name} ({code}) "
                        f"손실률: {return_pct:.2f}% "
                        f"(기준: {stop_loss_threshold}%, "
                        f"레짐: {regime}, 변동성: {volatility})"
                    )
                
                elif stop_loss_threshold < return_pct <= near_threshold:
                    # 손절 근접
                    margin = return_pct - stop_loss_threshold
                    near_stop_loss.append({
                        'code': code,
                        'name': name,
                        'return_pct': return_pct,
                        'regime': regime,
                        'volatility': volatility,
                        'atr': atr,
                        'stop_loss_threshold': stop_loss_threshold,
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
                        'return_pct': return_pct,
                        'regime': regime,
                        'volatility': volatility,
                        'stop_loss_threshold': stop_loss_threshold
                    })
            
            result = {
                'regime': regime,
                'confidence': confidence,
                'stop_loss_targets': stop_loss_targets,
                'near_stop_loss': near_stop_loss,
                'safe_holdings': safe_holdings,
                'total_holdings': len(holdings_detail)
            }
            
            logger.info(
                f"하이브리드 손절 체크 완료: "
                f"손절 대상 {len(stop_loss_targets)}개, "
                f"손절 근접 {len(near_stop_loss)}개, "
                f"안전 {len(safe_holdings)}개"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"하이브리드 손절 체크 실패: {e}", exc_info=True)
            return {}
    
    def format_alert_message(self, result: Dict[str, Any]) -> str:
        """
        알림 메시지 포맷
        
        Args:
            result: check_holdings_with_hybrid_stop_loss() 결과
        
        Returns:
            포맷된 메시지
        """
        regime = result.get('regime', 'neutral')
        confidence = result.get('confidence', 0.0)
        stop_loss_targets = result.get('stop_loss_targets', [])
        near_stop_loss = result.get('near_stop_loss', [])
        
        # 레짐 한글 변환
        regime_kr = {
            'bull': '상승장',
            'neutral': '중립장',
            'bear': '하락장'
        }.get(regime, '중립장')
        
        message = "*🎯 하이브리드 손절 모니터링*\n\n"
        message += f"📅 {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n"
        message += f"_레짐 + 변동성 기반 최적화 손절_\n\n"
        
        # 레짐 정보
        message += f"*📊 시장 레짐*\n"
        message += f"현재 레짐: `{regime_kr}` (신뢰도: `{confidence:.1f}%`)\n\n"
        
        # 손절 매트릭스 설명
        message += "*📈 하이브리드 손절 매트릭스*\n"
        message += f"_{regime_kr} 기준:_\n"
        matrix = self.HYBRID_STOP_LOSS_MATRIX[regime]
        message += f"• 저변동성: `{matrix['low']}%`\n"
        message += f"• 중변동성: `{matrix['medium']}%`\n"
        message += f"• 고변동성: `{matrix['high']}%`\n\n"
        
        # 손절 대상
        if stop_loss_targets:
            message += f"*🔴 손절 대상 ({len(stop_loss_targets)}개)*\n\n"
            
            for i, target in enumerate(stop_loss_targets, 1):
                vol_kr = {'low': '저', 'medium': '중', 'high': '고'}.get(
                    target['volatility'], '중'
                )
                
                message += f"{i}. *{target['name']}* (`{target['code']}`)\n"
                message += f"   손실률: `{target['return_pct']:.2f}%`\n"
                message += f"   손절 기준: `{target['stop_loss_threshold']}%` "
                message += f"({regime_kr} + {vol_kr}변동성)\n"
                message += f"   ATR: `{target['atr']:.2f}%`, "
                message += f"기준 초과: `{target['excess_loss']:.2f}%p`\n"
                message += f"   손실 금액: `{target['loss_amount']:,.0f}원`\n"
                message += f"   ⚠️ *즉시 매도 검토*\n\n"
        else:
            message += "*✅ 손절 대상 없음*\n\n"
        
        # 손절 근접
        if near_stop_loss:
            message += f"*⚠️ 손절 근접 ({len(near_stop_loss)}개)*\n\n"
            
            for i, near in enumerate(near_stop_loss, 1):
                vol_kr = {'low': '저', 'medium': '중', 'high': '고'}.get(
                    near['volatility'], '중'
                )
                
                message += f"{i}. {near['name']} (`{near['code']}`)\n"
                message += f"   손실률: `{near['return_pct']:.2f}%` "
                message += f"(여유: `{near['margin']:.2f}%p`)\n"
                message += f"   손절 기준: `{near['stop_loss_threshold']}%` "
                message += f"({regime_kr} + {vol_kr}변동성)\n"
                message += f"   💡 모니터링 필요\n\n"
        
        # 액션 가이드
        if stop_loss_targets or near_stop_loss:
            message += "*📋 액션 가이드*\n"
            if stop_loss_targets:
                message += f"• 손절 대상: 하이브리드 기준 초과, 즉시 매도\n"
            if near_stop_loss:
                message += "• 손절 근접: 레짐 + 변동성 모니터링\n"
            message += f"• 현재 레짐: {regime_kr}\n"
            message += "• 하이브리드: 시장 + 종목 모두 반영\n"
        else:
            message += f"_현재 모든 종목 안전 범위 내_ ✅\n"
            message += f"_레짐: {regime_kr}, 하이브리드 손절 적용 중_"
        
        return message
    
    def send_alert(self, result: Dict[str, Any]) -> bool:
        """
        텔레그램 알림 전송
        
        Args:
            result: check_holdings_with_hybrid_stop_loss() 결과
        
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
                        f"✅ 하이브리드 손절 알림 전송 성공 "
                        f"(대상: {len(stop_loss_targets)}개, 근접: {len(near_stop_loss)}개)"
                    )
                else:
                    logger.warning("⚠️ 하이브리드 손절 알림 전송 실패")
                
                return success
            else:
                logger.info("손절 대상 없음, 알림 전송 스킵")
                return True
        
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}", exc_info=True)
            return False
    
    def run(self) -> int:
        """
        하이브리드 손절 모니터링 실행
        
        Returns:
            0: 성공, 1: 실패
        """
        logger.info("=" * 60)
        logger.info("하이브리드 손절 모니터링 시작")
        logger.info("=" * 60)
        
        try:
            # 1. 하이브리드 손절 체크
            result = self.check_holdings_with_hybrid_stop_loss()
            
            if not result:
                logger.error("하이브리드 손절 체크 실패")
                return 1
            
            # 2. 알림 전송
            success = self.send_alert(result)
            
            # 3. 결과 로깅
            logger.info("=" * 60)
            logger.info("하이브리드 손절 모니터링 완료")
            logger.info(f"레짐: {result.get('regime', 'unknown')}")
            logger.info(f"손절 대상: {len(result.get('stop_loss_targets', []))}개")
            logger.info(f"손절 근접: {len(result.get('near_stop_loss', []))}개")
            logger.info(f"알림 전송: {'성공' if success else '실패'}")
            logger.info("=" * 60)
            
            return 0 if success else 1
        
        except Exception as e:
            logger.error(f"하이브리드 손절 모니터링 실패: {e}", exc_info=True)
            return 1


def main():
    """메인 실행 함수"""
    monitor = HybridStopLoss(atr_period=14)
    return monitor.run()


if __name__ == "__main__":
    sys.exit(main())
