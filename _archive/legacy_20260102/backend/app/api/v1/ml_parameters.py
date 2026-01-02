#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/ml_parameters.py
ML 모델 파라미터 설정 API
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
PARAMS_FILE = PROJECT_ROOT / "config" / "ml_params.json"
HISTORY_FILE = PROJECT_ROOT / "data" / "output" / "ml_history.json"

router = APIRouter()


class MLParameters(BaseModel):
    """ML 모델 파라미터 스키마"""
    model_config = {'protected_namespaces': ()}
    
    model_type: str = Field(default="xgboost", description="모델 타입")
    task: str = Field(default="regression", description="작업 타입")
    n_estimators: int = Field(default=100, description="트리 개수")
    max_depth: int = Field(default=6, description="최대 깊이")
    learning_rate: float = Field(default=0.1, description="학습률")
    min_child_weight: int = Field(default=1, description="최소 자식 가중치")
    subsample: float = Field(default=0.8, description="서브샘플 비율")
    colsample_bytree: float = Field(default=0.8, description="특징 샘플링 비율")


class MLHistory(BaseModel):
    """ML 히스토리 스키마"""
    id: str
    timestamp: str
    parameters: dict
    metrics: dict
    status: str


@router.get("/current")
async def get_ml_parameters():
    """현재 ML 파라미터 조회"""
    if PARAMS_FILE.exists():
        try:
            with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return MLParameters(**data)
        except Exception as e:
            logger.error(f"파라미터 로드 실패: {e}")
    
    return MLParameters()


@router.post("/update")
async def update_ml_parameters(params: MLParameters):
    """ML 파라미터 업데이트"""
    try:
        PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(params.model_dump(), f, ensure_ascii=False, indent=2)
        return params
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_ml_history():
    """ML 히스토리 조회"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"히스토리 로드 실패: {e}")
    
    return [
        MLHistory(
            id="1",
            timestamp="2025-11-24T10:00:00",
            parameters={"model_type": "xgboost", "n_estimators": 100},
            metrics={"train_score": 0.85, "test_score": 0.78},
            status="success"
        ).model_dump()
    ]


@router.post("/history/save")
async def save_ml_history(history: MLHistory):
    """ML 히스토리 저장"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    existing = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass
    
    existing.insert(0, history.model_dump())
    existing = existing[:50]
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    return {"message": "저장 완료", "id": history.id}
