# -*- coding: utf-8 -*-
"""
app/services/optimal_params_service.py
최적 파라미터 영구 저장 서비스

구조:
- live: 현재 운영 중인 파라미터 (실전 적용)
- live_history: 이전 live 파라미터 히스토리
- research: 연구용 파라미터 (튜닝 결과)
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# 저장 경로
OPTIMAL_PARAMS_FILE = Path("data/optimal_params.json")


class OptimalParamsService:
    """최적 파라미터 저장/로드 서비스"""

    def __init__(self, file_path: Path = OPTIMAL_PARAMS_FILE):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        # 마이그레이션 체크
        self._migrate_if_needed()

    def _migrate_if_needed(self):
        """기존 current/history 구조를 live/research로 마이그레이션"""
        if not self.file_path.exists():
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 이미 마이그레이션됨
            if "live" in data or "research" in data:
                return

            # 마이그레이션 필요
            if "current" in data or "history" in data:
                logger.info("optimal_params.json 마이그레이션 시작...")

                new_data = {"live": None, "live_history": [], "research": data.get("history", [])}

                # current가 있으면 live로 변환
                if data.get("current"):
                    current = data["current"]
                    new_data["live"] = {
                        "params": current.get("params", {}),
                        "promoted_at": current.get("timestamp", datetime.now(KST).isoformat()),
                        "source_trial_id": current.get("id"),
                        "result": current.get("result", {}),
                        "notes": current.get("notes", "마이그레이션됨"),
                    }

                # 백업 후 저장
                backup_path = self.file_path.with_suffix(".json.bak")
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"백업 생성: {backup_path}")

                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                logger.info("마이그레이션 완료")

        except Exception as e:
            logger.error(f"마이그레이션 실패: {e}")

    # ========================================
    # Live 파라미터 관리 (운영용)
    # ========================================

    def load_live(self) -> Optional[Dict]:
        """현재 Live 파라미터 로드"""
        data = self._load_all()
        return data.get("live")

    def promote_to_live(
        self,
        params: Dict,
        result: Dict,
        source_trial_id: Optional[int] = None,
        lookback: Optional[str] = None,
        notes: str = "",
    ) -> bool:
        """
        파라미터를 Live로 승격

        Args:
            params: 파라미터 딕셔너리 (ma_period, rsi_period, stop_loss, max_positions 등)
            result: 백테스트 결과 딕셔너리
            source_trial_id: 출처 Trial ID
            lookback: 룩백 기간 ("3M", "6M", "12M")
            notes: 메모
        """
        try:
            data = self._load_all()

            # 기존 Live를 live_history로 이동
            if data.get("live"):
                old_live = data["live"].copy()
                old_live["demoted_at"] = datetime.now(KST).isoformat()
                old_live["reason"] = "새 파라미터로 교체"

                if "live_history" not in data:
                    data["live_history"] = []
                data["live_history"].insert(0, old_live)

                # live_history 최대 20개 유지
                data["live_history"] = data["live_history"][:20]

            # 새 Live 설정
            live_params = params.copy()
            if lookback:
                live_params["lookback"] = lookback

            data["live"] = {
                "params": live_params,
                "promoted_at": datetime.now(KST).isoformat(),
                "source_trial_id": source_trial_id,
                "result": result,
                "notes": notes,
            }

            self._save_all(data)
            logger.info(f"Live 파라미터 승격 완료: {live_params}")
            return True

        except Exception as e:
            logger.error(f"Live 승격 실패: {e}")
            return False

    def rollback_live(self, history_index: int = 0, reason: str = "사용자 수동 롤백") -> bool:
        """
        이전 Live 파라미터로 롤백

        Args:
            history_index: live_history 인덱스 (0 = 가장 최근)
            reason: 롤백 사유
        """
        try:
            data = self._load_all()

            live_history = data.get("live_history", [])
            if not live_history or history_index >= len(live_history):
                logger.warning("롤백할 Live 히스토리가 없습니다")
                return False

            # 현재 Live를 히스토리로
            if data.get("live"):
                old_live = data["live"].copy()
                old_live["demoted_at"] = datetime.now(KST).isoformat()
                old_live["reason"] = reason
                live_history.insert(0, old_live)

            # 선택한 히스토리를 Live로 복원
            restored = live_history.pop(history_index + 1)  # +1: 방금 추가한 것 다음
            restored.pop("demoted_at", None)
            restored.pop("reason", None)
            restored["promoted_at"] = datetime.now(KST).isoformat()
            restored["notes"] = f"롤백 복원 (원본: {restored.get('notes', '')})"

            data["live"] = restored
            data["live_history"] = live_history[:20]

            self._save_all(data)
            logger.info(f"Live 롤백 완료: {restored.get('params')}")
            return True

        except Exception as e:
            logger.error(f"Live 롤백 실패: {e}")
            return False

    def get_live_history(self, limit: int = 10) -> List[Dict]:
        """Live 히스토리 조회"""
        data = self._load_all()
        return data.get("live_history", [])[:limit]

    # ========================================
    # Research 파라미터 관리 (연구용)
    # ========================================

    def save(
        self,
        params: Dict,
        result: Dict,
        source: str = "tuning",
        lookback: Optional[str] = None,
        notes: str = "",
    ) -> bool:
        """
        Research 파라미터 저장 (튜닝 결과)

        Args:
            params: 파라미터 딕셔너리
            result: 백테스트 결과 딕셔너리
            source: 출처 (tuning, manual, ai_suggestion)
            lookback: 룩백 기간 ("3M", "6M", "12M")
            notes: 메모
        """
        try:
            data = self._load_all()

            if "research" not in data:
                data["research"] = []

            # 새 항목 추가
            entry = {
                "id": len(data["research"]) + 1,
                "timestamp": datetime.now(KST).isoformat(),
                "source": source,
                "params": params,
                "result": result,
                "notes": notes,
            }
            if lookback:
                entry["lookback"] = lookback

            data["research"].append(entry)

            self._save_all(data)
            logger.info(f"Research 파라미터 저장 완료: {params}")
            return True

        except Exception as e:
            logger.error(f"Research 파라미터 저장 실패: {e}")
            return False

    def load_research(self, limit: int = 10) -> List[Dict]:
        """Research 파라미터 히스토리 로드"""
        data = self._load_all()
        research = data.get("research", [])
        return sorted(research, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

    def get_research_by_id(self, entry_id: int) -> Optional[Dict]:
        """ID로 Research 파라미터 조회"""
        data = self._load_all()
        for item in data.get("research", []):
            if item.get("id") == entry_id:
                return item
        return None

    # ========================================
    # 하위 호환성 (deprecated)
    # ========================================

    def load_current(self) -> Optional[Dict]:
        """현재 활성 파라미터 로드 (deprecated: load_live 사용)"""
        live = self.load_live()
        if live:
            # 기존 current 형식으로 변환
            return {
                "id": live.get("source_trial_id"),
                "timestamp": live.get("promoted_at"),
                "params": live.get("params", {}),
                "result": live.get("result", {}),
                "notes": live.get("notes", ""),
                "is_active": True,
            }
        return None

    def load_history(self, limit: int = 10) -> List[Dict]:
        """파라미터 히스토리 로드 (deprecated: load_research 사용)"""
        return self.load_research(limit)

    def activate(self, entry_id: int) -> bool:
        """특정 파라미터를 활성화 (deprecated: promote_to_live 사용)"""
        research = self.get_research_by_id(entry_id)
        if research:
            return self.promote_to_live(
                params=research.get("params", {}),
                result=research.get("result", {}),
                source_trial_id=entry_id,
                lookback=research.get("lookback"),
                notes=f"Research #{entry_id}에서 승격",
            )
        return False

    # ========================================
    # 내부 메서드
    # ========================================

    def _load_all(self) -> Dict:
        """전체 데이터 로드"""
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"live": None, "live_history": [], "research": []}

    def _save_all(self, data: Dict):
        """전체 데이터 저장"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
