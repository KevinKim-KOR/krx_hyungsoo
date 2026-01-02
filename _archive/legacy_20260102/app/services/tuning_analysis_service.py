"""
튜닝 결과 AI 분석 서비스

튜닝 Trial 데이터를 Claude API로 분석하여 7개 섹션 리포트 생성
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class TuningTrialPayload:
    """AI 분석용 튜닝 Trial 페이로드"""
    
    lookback: str  # "3M", "6M", "12M"
    trial_id: int
    strategy: str
    params: Dict[str, float]  # ma_period, rsi_period, stop_loss
    metrics: Dict[str, Dict[str, float]]  # train/val/test → sharpe, cagr, mdd
    engine_health: Dict  # is_valid, warnings


@dataclass
class AnalysisSections:
    """AI 분석 결과 7개 섹션"""
    
    param_summary: str
    stability: str
    overfitting: str
    strategy_interpretation: str
    risks: str
    improvements: str
    conclusion: str


class TuningAnalysisService:
    """튜닝 결과 AI 분석 서비스"""
    
    def __init__(self):
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다")
        
        self._client = anthropic.Anthropic(api_key=self._api_key)
        self._prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """프롬프트 템플릿 로드"""
        prompt_path = Path(__file__).parent.parent.parent / "config" / "prompts" / "tuning_analysis.prompt"
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"프롬프트 템플릿 파일이 없습니다: {prompt_path}")
        
        return prompt_path.read_text(encoding="utf-8")
    
    def analyze(self, payload: TuningTrialPayload) -> Dict:
        """
        튜닝 Trial 분석 실행
        
        Args:
            payload: TuningTrialPayload
            
        Returns:
            {
                "trial_id": int,
                "lookback": str,
                "sections": AnalysisSections dict
            }
            
        Raises:
            ValueError: 엔진 비정상 시
        """
        # 엔진 헬스체크
        if not payload.engine_health.get("is_valid", True):
            warnings = payload.engine_health.get("warnings", [])
            raise ValueError(f"엔진 비정상: {', '.join(warnings)}")
        
        # 페이로드를 JSON 문자열로 변환
        payload_dict = {
            "lookback": payload.lookback,
            "trial_id": payload.trial_id,
            "strategy": payload.strategy,
            "params": payload.params,
            "metrics": payload.metrics,
            "engine_health": payload.engine_health,
        }
        payload_json = json.dumps(payload_dict, ensure_ascii=False, indent=2)
        
        # 프롬프트 생성
        prompt = self._prompt_template.replace("{{TUNING_TRIAL_JSON}}", payload_json)
        
        logger.info(f"AI 분석 요청: trial_id={payload.trial_id}, lookback={payload.lookback}")
        
        # Claude API 호출
        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            logger.debug(f"AI 응답: {response_text[:200]}...")
            
            # JSON 파싱
            sections = self._parse_response(response_text)
            
            return {
                "trial_id": payload.trial_id,
                "lookback": payload.lookback,
                "sections": sections,
            }
            
        except anthropic.APIError as e:
            logger.error(f"Claude API 오류: {e}")
            raise RuntimeError(f"AI 분석 실패: {e}")
    
    def _parse_response(self, response_text: str) -> Dict[str, str]:
        """
        AI 응답에서 JSON 파싱
        
        응답이 ```json ... ``` 블록으로 감싸져 있을 수 있음
        """
        text = response_text.strip()
        
        # ```json ... ``` 블록 추출
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        
        try:
            sections = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}\n응답: {text[:500]}")
            # 파싱 실패 시 기본 응답
            sections = {
                "param_summary": "AI 응답 파싱 실패",
                "stability": response_text[:500],
                "overfitting": "",
                "strategy_interpretation": "",
                "risks": "",
                "improvements": "",
                "conclusion": "",
            }
        
        # 필수 키 확인
        required_keys = [
            "param_summary", "stability", "overfitting",
            "strategy_interpretation", "risks", "improvements", "conclusion"
        ]
        for key in required_keys:
            if key not in sections:
                sections[key] = ""
        
        return sections


# 싱글톤 인스턴스
_analysis_service: Optional[TuningAnalysisService] = None


def get_analysis_service() -> TuningAnalysisService:
    """분석 서비스 싱글톤 반환"""
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = TuningAnalysisService()
    return _analysis_service
