# -*- coding: utf-8 -*-
"""
extensions/automation/regime_monitor.py
레짐 감지 자동화

기능:
- 일별 레짐 분석
- 레짐 변경 감지
- 방어 모드 판단
- 변경 이력 저장
"""

from datetime import date, datetime, timedelta
from typing import Optional, Dict, Tuple
import pandas as pd
import logging
import json
from pathlib import Path

from core.strategy.market_regime_detector import MarketRegimeDetector
from extensions.automation.data_updater import DataUpdater

logger = logging.getLogger(__name__)


class RegimeMonitor:
    """
    레짐 감지 자동화 클래스
    
    기능:
    1. 일별 레짐 분석
    2. 레짐 변경 감지
    3. 이력 관리
    """
    
    def __init__(
        self,
        short_ma: int = 50,
        long_ma: int = 200,
        bull_threshold: float = 0.02,
        bear_threshold: float = -0.02
    ):
        """
        Args:
            short_ma: 단기 이동평균 기간
            long_ma: 장기 이동평균 기간
            bull_threshold: 상승장 임계값
            bear_threshold: 하락장 임계값
        """
        self.detector = MarketRegimeDetector(
            short_ma_period=short_ma,
            long_ma_period=long_ma,
            bull_threshold=bull_threshold,
            bear_threshold=bear_threshold
        )
        self.data_updater = DataUpdater()
        self.history_file = Path("data/output/regime_history.json")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
    def analyze_daily_regime(
        self,
        target_date: Optional[date] = None
    ) -> Optional[Dict]:
        """
        일별 레짐 분석
        
        Args:
            target_date: 대상 날짜 (None이면 오늘)
        
        Returns:
            Optional[Dict]: 레짐 분석 결과 (실패 시 None)
        """
        try:
            if target_date is None:
                target_date = date.today()
            
            logger.info(f"레짐 분석 시작: {target_date}")
            
            # KOSPI 데이터 수집
            kospi_data = self.data_updater.update_kospi_index(target_date)
            if kospi_data is None or kospi_data.empty:
                logger.error("KOSPI 데이터 없음")
                return None
            
            # 레짐 감지
            regime, confidence = self.detector.detect_regime(
                market_data=kospi_data,
                current_date=target_date
            )
            
            # 포지션 비율 계산
            position_ratio = self.detector.get_position_ratio(regime, confidence)
            
            # 방어 모드 판단
            defense_mode = self.detector.should_enter_defense_mode(regime, confidence)
            
            # 결과 생성
            result = {
                'date': target_date.isoformat(),
                'regime': regime,
                'confidence': float(confidence),
                'position_ratio': float(position_ratio),
                'defense_mode': defense_mode,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ 레짐 분석 완료: {regime} (신뢰도: {confidence:.2%})")
            
            # 이력 저장
            self._save_to_history(result)
            
            # 현재 상태 저장 (Web UI 연동용)
            self._save_current_state(result)
            
            return result
            
        except Exception as e:
            logger.error(f"레짐 분석 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_current_state(self, result: Dict):
        """
        현재 상태 저장 (Web UI 연동용)
        Args:
            result: 레짐 분석 결과
        """
        try:
            state_file = Path("data/state/current_regime.json")
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Web UI 포맷에 맞게 변환
            state_data = {
                "regime": result['regime'],
                "confidence": result['confidence'],
                "date": result['date'],
                "us_market_regime": result.get('us_market_regime', 'neutral'), # US 정보가 없다면 기본값
                "updated_at": datetime.now().isoformat()
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"현재 레짐 상태 저장 완료: {state_file}")
            
        except Exception as e:
            logger.error(f"현재 상태 저장 실패: {e}")

    def check_regime_change(
        self,
        target_date: Optional[date] = None
    ) -> Optional[Dict]:
        """
        레짐 변경 감지
        
        Args:
            target_date: 대상 날짜 (None이면 오늘)
        
        Returns:
            Optional[Dict]: 변경 정보 (변경 없으면 None)
        """
        try:
            # 현재 레짐 분석
            current = self.analyze_daily_regime(target_date)
            if current is None:
                return None
            
            # 이전 레짐 조회
            history = self.load_history(days=2)
            if len(history) < 2:
                logger.info("이전 레짐 없음 (첫 실행)")
                return None
            
            previous = history[-2]  # 마지막에서 두 번째 (이전)
            
            # 레짐 변경 확인
            if current['regime'] != previous['regime']:
                change_info = {
                    'date': current['date'],
                    'old_regime': previous['regime'],
                    'new_regime': current['regime'],
                    'old_confidence': previous['confidence'],
                    'new_confidence': current['confidence']
                }
                
                logger.warning(
                    f"🔄 레짐 변경 감지! "
                    f"{previous['regime']} → {current['regime']}"
                )
                
                return change_info
            
            return None
            
        except Exception as e:
            logger.error(f"레짐 변경 감지 실패: {e}")
            return None
    
    def _save_to_history(self, result: Dict):
        """
        이력 저장
        
        Args:
            result: 레짐 분석 결과
        """
        try:
            # 기존 이력 로드
            history = self.load_history()
            
            # 중복 제거 (같은 날짜)
            history = [h for h in history if h['date'] != result['date']]
            
            # 새 결과 추가
            history.append(result)
            
            # 최근 365일만 유지
            if len(history) > 365:
                history = history[-365:]
            
            # 저장
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"이력 저장 실패: {e}")
    
    def load_history(self, days: Optional[int] = None) -> list:
        """
        이력 조회
        
        Args:
            days: 조회할 일수 (None이면 전체)
        
        Returns:
            list: 레짐 이력
        """
        try:
            if not self.history_file.exists():
                return []
            
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            if days is not None:
                history = history[-days:]
            
            return history
            
        except Exception as e:
            logger.error(f"이력 조회 실패: {e}")
            return []
    
    def get_regime_summary(self, days: int = 30) -> Dict:
        """
        레짐 요약 통계
        
        Args:
            days: 조회할 일수
        
        Returns:
            Dict: 요약 통계
        """
        try:
            history = self.load_history(days=days)
            if not history:
                return {}
            
            # 레짐별 카운트
            regime_counts = {}
            for h in history:
                regime = h['regime']
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            # 레짐 변경 횟수
            changes = 0
            for i in range(1, len(history)):
                if history[i]['regime'] != history[i-1]['regime']:
                    changes += 1
            
            # 현재 레짐
            current_regime = history[-1]['regime'] if history else 'unknown'
            current_confidence = history[-1]['confidence'] if history else 0.0
            
            return {
                'total_days': len(history),
                'regime_counts': regime_counts,
                'regime_changes': changes,
                'current_regime': current_regime,
                'current_confidence': current_confidence
            }
            
        except Exception as e:
            logger.error(f"요약 통계 생성 실패: {e}")
            return {}
