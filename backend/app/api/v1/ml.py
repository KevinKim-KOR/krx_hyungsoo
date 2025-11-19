#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/ml.py
머신러닝 모델 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import logging
from typing import Dict, Any, Optional
import pickle

logger = logging.getLogger(__name__)

# 데이터 경로
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "output"
ML_DIR = OUTPUT_DIR / "ml"

router = APIRouter()


def find_latest_file(directory: Path, pattern: str) -> Optional[Path]:
    """최신 파일 찾기"""
    if not directory.exists():
        return None
    
    files = list(directory.glob(pattern))
    if not files:
        return None
    
    return max(files, key=lambda f: f.stat().st_mtime)


@router.get("/model/info")
async def get_ml_model_info() -> Dict[str, Any]:
    """
    ML 모델 정보 조회
    
    Returns:
        - model_type: 모델 타입 (XGBoost, LightGBM 등)
        - timestamp: 학습 시각
        - train_score: 학습 데이터 R² 스코어
        - test_score: 테스트 데이터 R² 스코어
        - n_features: 특징 개수
        - feature_importance: 특징 중요도 (Top 10)
    """
    # 최신 메타 파일 찾기
    meta_file = find_latest_file(ML_DIR, "meta_*.json")
    
    if not meta_file:
        raise HTTPException(
            status_code=404,
            detail="ML 모델 정보를 찾을 수 없습니다."
        )
    
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        logger.info(f"✅ ML 모델 정보 로드: {meta_file.name}")
        
        # Feature Importance 정렬 (상위 10개)
        feature_importance = meta.get("feature_importance", {})
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        response = {
            "model_type": meta.get("model_type", "XGBoost"),
            "timestamp": meta.get("timestamp", ""),
            "train_score": meta.get("train_score", 0.0),
            "test_score": meta.get("test_score", 0.0),
            "n_features": len(feature_importance),
            "feature_importance": [
                {"feature": feat, "importance": imp}
                for feat, imp in sorted_features
            ],
        }
        
        return response
        
    except Exception as e:
        logger.error(f"ML 모델 정보 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"ML 모델 정보 로드 중 오류 발생: {str(e)}"
        )


@router.get("/model/predictions")
async def get_ml_predictions(limit: int = 10) -> list[Dict[str, Any]]:
    """
    ML 모델 예측 결과 조회
    
    Args:
        limit: 조회할 최대 개수
    
    Returns:
        예측 결과 리스트 (상위 종목)
    """
    # TODO: 예측 결과 파일 구현
    # 현재는 더미 데이터 반환
    return [
        {"code": "069500", "name": "KODEX 200", "predicted_score": 0.85},
        {"code": "091160", "name": "KODEX 반도체", "predicted_score": 0.78},
        {"code": "133690", "name": "KOSEF 국고채", "predicted_score": 0.72},
    ]


@router.get("/features")
async def get_feature_list() -> list[str]:
    """
    사용 중인 특징 리스트 조회
    
    Returns:
        특징 이름 리스트
    """
    meta_file = find_latest_file(ML_DIR, "meta_*.json")
    
    if not meta_file:
        return []
    
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        features = list(meta.get("feature_importance", {}).keys())
        logger.info(f"✅ 특징 {len(features)}개 로드")
        
        return features
        
    except Exception as e:
        logger.error(f"특징 리스트 로드 실패: {e}")
        return []
