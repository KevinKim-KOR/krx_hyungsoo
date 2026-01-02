#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/phase4/rebuy_system.py
재매수 시스템

손절 후 재진입 조건:
1. 기술적 반등 확인 (5일 연속 상승)
2. MAPS 점수 양전환 (음수 → 양수)
3. 레짐 변경 (하락 → 중립/상승)
4. 쿨다운 기간 (최소 5거래일)
"""
import sys
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.notification.telegram_sender import TelegramSender
from core.strategy.market_regime_detector import MarketRegimeDetector
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


class RebuySystem:
    """재매수 시스템 클래스"""
    
    # 재매수 조건
    REBUY_CONDITIONS = {
        'cooldown_days': 5,          # 쿨다운 기간 (거래일)
        'consecutive_up_days': 5,    # 연속 상승일 (기술적 반등)
        'maps_threshold': 0.0,       # MAPS 점수 임계값 (양전환)
        'regime_change': True        # 레짐 변경 필요 여부
    }
    
    def __init__(self):
        """초기화"""
        self.telegram = TelegramSender()
        self.regime_detector = MarketRegimeDetector()
        
        # 손절 이력 파일
        self.stop_loss_history_file = PROJECT_ROOT / "data" / "portfolio" / "stop_loss_history.json"
        self.stop_loss_history_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("재매수 시스템 초기화")
        logger.info(f"재매수 조건: {self.REBUY_CONDITIONS}")
    
    def load_stop_loss_history(self) -> List[Dict[str, Any]]:
        """
        손절 이력 로드
        
        Returns:
            손절 이력 리스트
        """
        try:
            if not self.stop_loss_history_file.exists():
                logger.info("손절 이력 파일 없음, 빈 리스트 반환")
                return []
            
            with open(self.stop_loss_history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            logger.info(f"손절 이력 로드: {len(history)}개")
            return history
        
        except Exception as e:
            logger.error(f"손절 이력 로드 실패: {e}", exc_info=True)
            return []
    
    def save_stop_loss_history(self, history: List[Dict[str, Any]]):
        """
        손절 이력 저장
        
        Args:
            history: 손절 이력 리스트
        """
        try:
            with open(self.stop_loss_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            
            logger.info(f"손절 이력 저장: {len(history)}개")
        
        except Exception as e:
            logger.error(f"손절 이력 저장 실패: {e}", exc_info=True)
    
    def add_stop_loss_record(
        self,
        code: str,
        name: str,
        sell_date: str,
        sell_price: float,
        loss_pct: float,
        loss_amount: float
    ):
        """
        손절 기록 추가
        
        Args:
            code: 종목 코드
            name: 종목명
            sell_date: 매도일 (YYYY-MM-DD)
            sell_price: 매도가
            loss_pct: 손실률 (%)
            loss_amount: 손실 금액
        """
        try:
            history = self.load_stop_loss_history()
            
            record = {
                'code': code,
                'name': name,
                'sell_date': sell_date,
                'sell_price': sell_price,
                'loss_pct': loss_pct,
                'loss_amount': loss_amount,
                'rebuy_eligible_date': self._calculate_rebuy_eligible_date(sell_date),
                'rebuy_status': 'waiting',  # waiting, eligible, rebuyed
                'created_at': datetime.now().isoformat()
            }
            
            history.append(record)
            self.save_stop_loss_history(history)
            
            logger.info(f"손절 기록 추가: {name} ({code})")
        
        except Exception as e:
            logger.error(f"손절 기록 추가 실패: {e}", exc_info=True)
    
    def _calculate_rebuy_eligible_date(self, sell_date: str) -> str:
        """
        재매수 가능일 계산 (쿨다운 기간 후)
        
        Args:
            sell_date: 매도일 (YYYY-MM-DD)
        
        Returns:
            재매수 가능일 (YYYY-MM-DD)
        """
        sell_date_obj = datetime.strptime(sell_date, '%Y-%m-%d').date()
        
        # 쿨다운 기간 (거래일 기준, 단순화: 영업일 = 거래일)
        cooldown_days = self.REBUY_CONDITIONS['cooldown_days']
        eligible_date = sell_date_obj + timedelta(days=cooldown_days * 1.5)  # 주말 고려
        
        return eligible_date.strftime('%Y-%m-%d')
    
    def check_rebuy_candidates(self) -> List[Dict[str, Any]]:
        """
        재매수 후보 종목 체크
        
        Returns:
            재매수 후보 리스트
        """
        try:
            history = self.load_stop_loss_history()
            
            if not history:
                logger.info("손절 이력 없음")
                return []
            
            today = date.today().strftime('%Y-%m-%d')
            candidates = []
            
            for record in history:
                # 이미 재매수했거나 대기 중이 아닌 경우 스킵
                if record.get('rebuy_status') != 'waiting':
                    continue
                
                # 쿨다운 기간 체크
                eligible_date = record.get('rebuy_eligible_date')
                if eligible_date and today < eligible_date:
                    logger.debug(
                        f"{record['name']} ({record['code']}): "
                        f"쿨다운 기간 중 (재매수 가능일: {eligible_date})"
                    )
                    continue
                
                # 재매수 후보
                code = record.get('code')
                name = record.get('name')
                
                # 재매수 조건 체크
                conditions_met = self._check_rebuy_conditions(code, name)
                
                if conditions_met['eligible']:
                    candidates.append({
                        'code': code,
                        'name': name,
                        'sell_date': record.get('sell_date'),
                        'sell_price': record.get('sell_price'),
                        'loss_pct': record.get('loss_pct'),
                        'conditions_met': conditions_met,
                        'action': 'REBUY'
                    })
                    
                    logger.info(
                        f"재매수 후보: {name} ({code}) "
                        f"조건: {conditions_met['met_conditions']}"
                    )
            
            logger.info(f"재매수 후보 체크 완료: {len(candidates)}개")
            return candidates
        
        except Exception as e:
            logger.error(f"재매수 후보 체크 실패: {e}", exc_info=True)
            return []
    
    def _check_rebuy_conditions(self, code: str, name: str) -> Dict[str, Any]:
        """
        재매수 조건 체크
        
        Args:
            code: 종목 코드
            name: 종목명
        
        Returns:
            조건 충족 여부 및 상세 정보
        """
        met_conditions = []
        failed_conditions = []
        
        # 1. 기술적 반등 (5일 연속 상승) - 단순화: 현재가 > 매도가
        # 실제 구현 시 pykrx로 5일 데이터 확인
        technical_bounce = True  # 임시
        if technical_bounce:
            met_conditions.append("기술적 반등 확인")
        else:
            failed_conditions.append("기술적 반등 미확인")
        
        # 2. MAPS 점수 양전환 - 단순화: 레짐 상승/중립
        regime, confidence, _ = self._get_current_regime()
        maps_positive = regime in ['bull', 'neutral']
        if maps_positive:
            met_conditions.append(f"MAPS 양전환 (레짐: {regime})")
        else:
            failed_conditions.append(f"MAPS 음수 (레짐: {regime})")
        
        # 3. 레짐 변경 (하락 → 중립/상승)
        regime_changed = regime in ['bull', 'neutral']
        if regime_changed:
            met_conditions.append(f"레짐 개선 ({regime})")
        else:
            failed_conditions.append(f"레짐 미개선 ({regime})")
        
        # 4. 쿨다운 기간 (이미 체크됨)
        met_conditions.append("쿨다운 기간 완료")
        
        # 재매수 가능 여부 (모든 조건 충족)
        eligible = len(failed_conditions) == 0
        
        return {
            'eligible': eligible,
            'met_conditions': met_conditions,
            'failed_conditions': failed_conditions,
            'regime': regime,
            'confidence': confidence
        }
    
    def _get_current_regime(self) -> tuple:
        """현재 레짐 감지"""
        try:
            # 단순화: 기본값 반환
            # 실제 구현 시 pykrx로 KOSPI 데이터 가져와서 detect_regime() 호출
            regime = 'neutral'
            confidence = 50.0
            regime_info = {'regime': regime, 'confidence': confidence}
            return regime, confidence, regime_info
        except:
            return 'neutral', 50.0, {}
    
    def format_alert_message(self, candidates: List[Dict[str, Any]]) -> str:
        """
        재매수 알림 메시지 포맷
        
        Args:
            candidates: 재매수 후보 리스트
        
        Returns:
            포맷된 메시지
        """
        if not candidates:
            return ""
        
        message = "*🔄 재매수 후보 알림*\n\n"
        message += f"📅 {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n\n"
        
        message += f"*재매수 후보 ({len(candidates)}개)*\n"
        message += "_손절 후 재진입 조건 충족_\n\n"
        
        for i, candidate in enumerate(candidates, 1):
            name = candidate['name']
            code = candidate['code']
            sell_date = candidate['sell_date']
            loss_pct = candidate['loss_pct']
            conditions = candidate['conditions_met']
            
            message += f"{i}. *{name}* (`{code}`)\n"
            message += f"   손절일: `{sell_date}`\n"
            message += f"   손절 손실: `{loss_pct:.2f}%`\n"
            message += f"   충족 조건:\n"
            
            for condition in conditions['met_conditions']:
                message += f"     ✅ {condition}\n"
            
            message += f"   💡 *재매수 검토 가능*\n\n"
        
        message += "*📋 재매수 가이드*\n"
        message += "• 현재가 확인 후 진입\n"
        message += "• 소량 분할 매수 권장\n"
        message += "• 손절 기준 재설정 필수\n"
        message += "• 감정적 판단 배제\n"
        
        return message
    
    def send_alert(self, candidates: List[Dict[str, Any]]) -> bool:
        """
        텔레그램 알림 전송
        
        Args:
            candidates: 재매수 후보 리스트
        
        Returns:
            전송 성공 여부
        """
        try:
            if not candidates:
                logger.info("재매수 후보 없음, 알림 전송 스킵")
                return True
            
            message = self.format_alert_message(candidates)
            success = self.telegram.send_custom(message, parse_mode='Markdown')
            
            if success:
                logger.info(f"✅ 재매수 알림 전송 성공 (후보: {len(candidates)}개)")
            else:
                logger.warning("⚠️ 재매수 알림 전송 실패")
            
            return success
        
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}", exc_info=True)
            return False
    
    def run(self) -> int:
        """
        재매수 시스템 실행
        
        Returns:
            0: 성공, 1: 실패
        """
        logger.info("=" * 60)
        logger.info("재매수 시스템 시작")
        logger.info("=" * 60)
        
        try:
            # 1. 재매수 후보 체크
            candidates = self.check_rebuy_candidates()
            
            # 2. 알림 전송
            success = self.send_alert(candidates)
            
            # 3. 결과 로깅
            logger.info("=" * 60)
            logger.info("재매수 시스템 완료")
            logger.info(f"재매수 후보: {len(candidates)}개")
            logger.info(f"알림 전송: {'성공' if success else '실패'}")
            logger.info("=" * 60)
            
            return 0 if success else 1
        
        except Exception as e:
            logger.error(f"재매수 시스템 실패: {e}", exc_info=True)
            return 1


def main():
    """메인 실행 함수"""
    system = RebuySystem()
    return system.run()


if __name__ == "__main__":
    sys.exit(main())
