# -*- coding: utf-8 -*-
"""
app/services/optimal_params_service.py
최적 파라미터 영구 저장 서비스
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# 저장 경로
OPTIMAL_PARAMS_FILE = Path("data/optimal_params.json")


class OptimalParamsService:
    """최적 파라미터 저장/로드 서비스"""
    
    def __init__(self, file_path: Path = OPTIMAL_PARAMS_FILE):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def save(
        self,
        params: Dict,
        result: Dict,
        source: str = "tuning",
        notes: str = ""
    ) -> bool:
        """
        최적 파라미터 저장
        
        Args:
            params: 파라미터 딕셔너리
            result: 백테스트 결과 딕셔너리
            source: 출처 (tuning, manual, ai_suggestion)
            notes: 메모
        """
        try:
            # 기존 데이터 로드
            data = self._load_all()
            
            # 새 항목 추가
            entry = {
                "id": len(data.get("history", [])) + 1,
                "timestamp": datetime.now().isoformat(),
                "source": source,
                "params": params,
                "result": result,
                "notes": notes,
                "is_active": True
            }
            
            # 기존 active 비활성화
            for item in data.get("history", []):
                item["is_active"] = False
            
            # 히스토리에 추가
            if "history" not in data:
                data["history"] = []
            data["history"].append(entry)
            
            # 현재 활성 파라미터 업데이트
            data["current"] = entry
            
            # 저장
            self._save_all(data)
            logger.info(f"최적 파라미터 저장 완료: {params}")
            return True
            
        except Exception as e:
            logger.error(f"최적 파라미터 저장 실패: {e}")
            return False
    
    def load_current(self) -> Optional[Dict]:
        """현재 활성 파라미터 로드"""
        data = self._load_all()
        return data.get("current")
    
    def load_history(self, limit: int = 10) -> List[Dict]:
        """파라미터 히스토리 로드"""
        data = self._load_all()
        history = data.get("history", [])
        return sorted(history, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    def activate(self, entry_id: int) -> bool:
        """특정 파라미터를 활성화"""
        try:
            data = self._load_all()
            
            target = None
            for item in data.get("history", []):
                if item["id"] == entry_id:
                    item["is_active"] = True
                    target = item
                else:
                    item["is_active"] = False
            
            if target:
                data["current"] = target
                self._save_all(data)
                logger.info(f"파라미터 #{entry_id} 활성화")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"파라미터 활성화 실패: {e}")
            return False
    
    def _load_all(self) -> Dict:
        """전체 데이터 로드"""
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"current": None, "history": []}
    
    def _save_all(self, data: Dict):
        """전체 데이터 저장"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
