# -*- coding: utf-8 -*-
"""
core/strategy/weight_scaler.py
비중 스케일링 모듈

파이프라인:
① 모멘텀 기반 base weight (equal weight)
② RSI 스케일링 (종목 레벨)
③ Soft Normalize (초과 시만 압축, 부족 시 cash)
④ 레짐 스케일링 (포트폴리오 레벨)
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import date
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RSIRule:
    """RSI 스케일링 규칙"""
    min: float
    max: float
    scale: float


@dataclass
class RSIProfile:
    """RSI 스케일링 프로파일"""
    name: str
    description: str = ""
    rsi_boost_enabled: bool = True
    rules: List[RSIRule] = field(default_factory=list)


@dataclass
class WeightScalingResult:
    """비중 스케일링 결과"""
    date: date
    regime: str
    regime_confidence: float
    etf_list: List[str]
    rsi_values: Dict[str, float]
    w_base: Dict[str, float]
    w_rsi_scaled: Dict[str, float]
    w_soft_normalized: Dict[str, float]
    w_final: Dict[str, float]
    cash: float
    rsi_profile_name: str


class WeightScaler:
    """
    비중 스케일링 관리자
    
    파이프라인:
    1. base_weight (equal weight)
    2. RSI scaling (종목 레벨)
    3. Soft normalize (초과 시만 압축)
    4. Regime scaling (포트폴리오 레벨)
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: RSI 프로파일 설정 파일 경로
        """
        self.profiles: Dict[str, RSIProfile] = {}
        self.regime_profile_mapping: Dict[str, str] = {}
        self.default_profile: str = "balanced"
        
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "rsi_profile.yaml"
        
        self._load_config(config_path)
    
    def _load_config(self, config_path) -> None:
        """설정 파일 로드"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            # 프로파일 로드
            for name, profile_data in config.get("profiles", {}).items():
                rules = [
                    RSIRule(min=r["min"], max=r["max"], scale=r["scale"])
                    for r in profile_data.get("rules", [])
                ]
                self.profiles[name] = RSIProfile(
                    name=profile_data.get("name", name),
                    description=profile_data.get("description", ""),
                    rsi_boost_enabled=profile_data.get("rsi_boost_enabled", True),
                    rules=rules,
                )
            
            # 레짐-프로파일 매핑
            self.regime_profile_mapping = config.get("regime_profile_mapping", {
                "bull": "balanced",
                "neutral": "conservative",
                "bear": "conservative",
            })
            
            self.default_profile = config.get("default_profile", "balanced")
            logger.info(f"RSI 프로파일 로드 완료: {list(self.profiles.keys())}")
            
        except FileNotFoundError:
            logger.warning(f"RSI 프로파일 설정 파일 없음: {config_path}, 기본값 사용")
            self._create_default_profiles()
        except Exception as e:
            logger.error(f"RSI 프로파일 로드 실패: {e}")
            self._create_default_profiles()
    
    def _create_default_profiles(self) -> None:
        """기본 프로파일 생성"""
        self.profiles["balanced"] = RSIProfile(
            name="balanced",
            description="균형 프로파일",
            rsi_boost_enabled=True,
            rules=[
                RSIRule(min=80, max=100, scale=0.0),
                RSIRule(min=70, max=80, scale=0.5),
                RSIRule(min=60, max=70, scale=0.8),
                RSIRule(min=40, max=60, scale=1.0),
                RSIRule(min=30, max=40, scale=1.1),
                RSIRule(min=0, max=30, scale=1.2),
            ],
        )
        self.profiles["conservative"] = RSIProfile(
            name="conservative",
            description="보수적 프로파일",
            rsi_boost_enabled=True,
            rules=[
                RSIRule(min=80, max=100, scale=0.0),
                RSIRule(min=70, max=80, scale=0.5),
                RSIRule(min=60, max=70, scale=0.8),
                RSIRule(min=0, max=60, scale=1.0),
            ],
        )
        self.regime_profile_mapping = {
            "bull": "balanced",
            "neutral": "conservative",
            "bear": "conservative",
        }
        self.default_profile = "balanced"
    
    def get_profile_for_regime(self, regime: str) -> RSIProfile:
        """레짐에 맞는 RSI 프로파일 반환"""
        profile_name = self.regime_profile_mapping.get(regime, self.default_profile)
        return self.profiles.get(profile_name, self.profiles.get(self.default_profile))
    
    def scale_from_rsi(self, rsi: float, profile: RSIProfile) -> float:
        """
        RSI 값에 따른 스케일 계수 반환
        
        Args:
            rsi: RSI 값 (0~100)
            profile: RSI 프로파일
            
        Returns:
            스케일 계수
        """
        for rule in profile.rules:
            if rule.min <= rsi < rule.max:
                # boost가 비활성화된 경우 scale > 1.0 사용 금지
                if not profile.rsi_boost_enabled and rule.scale > 1.0:
                    return 1.0
                return rule.scale
        
        # 규칙에 매칭되지 않으면 기본값
        return 1.0
    
    def apply_rsi_scaling(
        self,
        base_weights: Dict[str, float],
        rsi_values: Dict[str, float],
        profile: RSIProfile,
    ) -> Dict[str, float]:
        """
        RSI 기반 비중 스케일링 적용 (종목 레벨)
        
        Args:
            base_weights: 기본 비중
            rsi_values: RSI 값
            profile: RSI 프로파일
            
        Returns:
            RSI 스케일링 적용된 비중
        """
        scaled_weights = {}
        for code, base_weight in base_weights.items():
            rsi = rsi_values.get(code, 50.0)
            scale = self.scale_from_rsi(rsi, profile)
            scaled_weights[code] = base_weight * scale
        
        return scaled_weights
    
    def soft_normalize(
        self,
        weights: Dict[str, float],
        risk_budget: float = 1.0,
    ) -> Dict[str, float]:
        """
        Soft Normalize 적용
        
        - 합계가 risk_budget 초과 시: 압축하여 budget에 맞춤
        - 합계가 risk_budget 이하 시: 그대로 유지 (부족분은 cash)
        
        Args:
            weights: 비중 딕셔너리
            risk_budget: 최대 투자 비중 (기본 1.0)
            
        Returns:
            정규화된 비중
        """
        if not weights:
            return {}
        
        total = sum(weights.values())
        
        if total <= risk_budget:
            # 부족분은 cash로 유지
            return weights.copy()
        else:
            # 초과 시 압축
            factor = risk_budget / total
            return {code: w * factor for code, w in weights.items()}
    
    def apply_regime_scaling(
        self,
        weights: Dict[str, float],
        regime_scale: float,
    ) -> Dict[str, float]:
        """
        레짐 스케일링 적용 (포트폴리오 레벨)
        
        Args:
            weights: 비중 딕셔너리
            regime_scale: 레짐 스케일 (0.0 ~ 1.2)
            
        Returns:
            레짐 스케일링 적용된 비중
        """
        return {code: w * regime_scale for code, w in weights.items()}
    
    def compute_final_weights(
        self,
        top_n_codes: List[str],
        rsi_values: Dict[str, float],
        regime: str,
        regime_confidence: float,
        regime_scale: float,
        current_date: date,
        log_details: bool = False,
    ) -> WeightScalingResult:
        """
        최종 비중 계산 (전체 파이프라인)
        
        파이프라인:
        1. base_weight (equal weight)
        2. RSI scaling (종목 레벨)
        3. Soft normalize (초과 시만 압축)
        4. Regime scaling (포트폴리오 레벨)
        
        Args:
            top_n_codes: Top N 종목 코드 리스트
            rsi_values: RSI 값 딕셔너리
            regime: 레짐 (bull/neutral/bear)
            regime_confidence: 레짐 신뢰도
            regime_scale: 레짐 스케일 (position_ratio)
            current_date: 현재 날짜
            log_details: 상세 로깅 여부
            
        Returns:
            WeightScalingResult
        """
        if not top_n_codes:
            return WeightScalingResult(
                date=current_date,
                regime=regime,
                regime_confidence=regime_confidence,
                etf_list=[],
                rsi_values={},
                w_base={},
                w_rsi_scaled={},
                w_soft_normalized={},
                w_final={},
                cash=1.0,
                rsi_profile_name="",
            )
        
        # 레짐에 맞는 RSI 프로파일 선택
        profile = self.get_profile_for_regime(regime)
        
        # ① 모멘텀 기반 base weight (equal weight)
        base_weight = 1.0 / len(top_n_codes)
        w_base = {code: base_weight for code in top_n_codes}
        
        # ② RSI 스케일링 (종목 레벨)
        w_rsi_scaled = self.apply_rsi_scaling(w_base, rsi_values, profile)
        
        # ③ Soft Normalize (초과 시만 압축, 부족 시 cash)
        w_soft_normalized = self.soft_normalize(w_rsi_scaled, risk_budget=1.0)
        
        # ④ 레짐 스케일링 (포트폴리오 레벨)
        w_final = self.apply_regime_scaling(w_soft_normalized, regime_scale)
        
        # Cash 계산
        cash = 1.0 - sum(w_final.values())
        cash = max(0.0, cash)  # 음수 방지
        
        # 상세 로깅
        if log_details:
            logger.info(f"[{current_date}] 비중 스케일링 파이프라인:")
            logger.info(f"  레짐: {regime} (confidence={regime_confidence:.2f}, scale={regime_scale:.2f})")
            logger.info(f"  RSI 프로파일: {profile.name} (boost_enabled={profile.rsi_boost_enabled})")
            
            for code in top_n_codes[:5]:  # 상위 5개만
                rsi = rsi_values.get(code, 50.0)
                rsi_scale = self.scale_from_rsi(rsi, profile)
                logger.info(
                    f"  {code}: base={w_base[code]:.3f} "
                    f"→ RSI({rsi:.0f}, scale={rsi_scale:.1f}) → {w_rsi_scaled.get(code, 0):.3f} "
                    f"→ soft_norm → {w_soft_normalized.get(code, 0):.3f} "
                    f"→ regime({regime_scale:.2f}) → {w_final.get(code, 0):.3f}"
                )
            
            logger.info(f"  Cash: {cash:.3f}")
        
        return WeightScalingResult(
            date=current_date,
            regime=regime,
            regime_confidence=regime_confidence,
            etf_list=top_n_codes,
            rsi_values={code: rsi_values.get(code, 50.0) for code in top_n_codes},
            w_base=w_base,
            w_rsi_scaled=w_rsi_scaled,
            w_soft_normalized=w_soft_normalized,
            w_final=w_final,
            cash=cash,
            rsi_profile_name=profile.name,
        )
    
    def result_to_dict(self, result: WeightScalingResult) -> Dict[str, Any]:
        """WeightScalingResult를 딕셔너리로 변환 (로그 저장용)"""
        return {
            "date": result.date.isoformat() if result.date else None,
            "regime": result.regime,
            "regime_confidence": result.regime_confidence,
            "etf": result.etf_list,
            "rsi": result.rsi_values,
            "w_base": result.w_base,
            "w_rsi_scaled": result.w_rsi_scaled,
            "w_soft_normalized": result.w_soft_normalized,
            "w_final": result.w_final,
            "cash": result.cash,
            "rsi_profile": result.rsi_profile_name,
        }
