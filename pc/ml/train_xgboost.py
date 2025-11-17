#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pc/ml/train_xgboost.py
XGBoost/LightGBM 기반 ETF 랭킹 모델 학습

목표: MAPS 점수를 개선하는 ML 스코어 생성
- 입력: 기술적 지표 + 모멘텀 + 변동성 + 거시 지표
- 출력: 다음 N일 수익률 예측 (회귀) 또는 상승/하락 (분류)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
import json
import pickle

# ML 라이브러리
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler

# 프로젝트 모듈
from core.db import SessionLocal
from core.fetchers import OHLCVFetcher
from pc.ml.feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


class ETFRankingModel:
    """ETF 랭킹 ML 모델"""
    
    def __init__(
        self,
        model_type: str = "xgboost",  # xgboost, lightgbm
        task: str = "regression",  # regression, classification
        target_days: int = 5,  # 예측 기간 (N일 후 수익률)
        test_size: float = 0.2
    ):
        """
        Args:
            model_type: 모델 타입 (xgboost, lightgbm)
            task: 태스크 (regression, classification)
            target_days: 예측 기간 (일)
            test_size: 테스트 데이터 비율
        """
        self.model_type = model_type
        self.task = task
        self.target_days = target_days
        self.test_size = test_size
        
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.feature_importance = {}
        
        logger.info(f"ETFRankingModel 초기화: {model_type}, {task}, target_days={target_days}")
    
    def prepare_data(
        self,
        codes: List[str],
        start_date: str = "2020-01-01",
        end_date: str = "2024-12-31"
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        학습 데이터 준비
        
        Args:
            codes: 종목 코드 리스트
            start_date: 시작일
            end_date: 종료일
        
        Returns:
            (X, y): 특징 데이터프레임, 타겟 시리즈
        """
        logger.info("=" * 60)
        logger.info("데이터 준비 시작")
        logger.info("=" * 60)
        
        db = SessionLocal()
        fetcher = OHLCVFetcher(db)
        engineer = FeatureEngineer()
        
        all_data = []
        
        for code in codes:
            logger.info(f"처리 중: {code}")
            
            # 1. OHLCV 데이터 로드
            df = fetcher.get_ohlcv(code, start_date=start_date, end_date=end_date)
            
            if df.empty:
                logger.warning(f"데이터 없음: {code}")
                continue
            
            # 2. 특징 엔지니어링
            df_features = engineer.create_features(df)
            
            # 3. 타겟 생성 (N일 후 수익률)
            df_features['target'] = df_features['close'].pct_change(periods=self.target_days).shift(-self.target_days)
            
            # 4. 종목 코드 추가
            df_features['code'] = code
            
            all_data.append(df_features)
        
        db.close()
        
        # 5. 전체 데이터 병합
        df_all = pd.concat(all_data, ignore_index=True)
        
        # 6. NaN 제거
        df_all = df_all.dropna()
        
        logger.info(f"✅ 데이터 준비 완료: {len(df_all)}행, {len(codes)}개 종목")
        
        # 7. X, y 분리
        feature_cols = [col for col in df_all.columns if col not in ['target', 'code', 'date']]
        X = df_all[feature_cols]
        y = df_all['target']
        
        # 8. 분류 태스크면 타겟 변환 (0: 하락, 1: 상승)
        if self.task == "classification":
            y = (y > 0).astype(int)
        
        self.feature_names = feature_cols
        
        logger.info(f"특징 수: {len(feature_cols)}")
        logger.info(f"샘플 수: {len(X)}")
        
        return X, y
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        모델 학습
        
        Args:
            X: 특징 데이터프레임
            y: 타겟 시리즈
            params: 모델 하이퍼파라미터
        
        Returns:
            학습 결과 딕셔너리
        """
        logger.info("=" * 60)
        logger.info("모델 학습 시작")
        logger.info("=" * 60)
        
        # 1. 데이터 스케일링
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
        
        # 2. Train/Test 분리 (시계열 순서 유지)
        split_idx = int(len(X_scaled) * (1 - self.test_size))
        X_train, X_test = X_scaled.iloc[:split_idx], X_scaled.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        logger.info(f"Train: {len(X_train)}행, Test: {len(X_test)}행")
        
        # 3. 모델 초기화
        if params is None:
            params = self._get_default_params()
        
        if self.model_type == "xgboost":
            if self.task == "regression":
                self.model = xgb.XGBRegressor(**params)
            else:
                self.model = xgb.XGBClassifier(**params)
        elif self.model_type == "lightgbm":
            if self.task == "regression":
                self.model = lgb.LGBMRegressor(**params)
            else:
                self.model = lgb.LGBMClassifier(**params)
        
        # 4. 학습
        logger.info(f"모델 학습 중: {self.model_type}")
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
        # 5. 예측
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)
        
        # 6. 평가
        results = {}
        
        if self.task == "regression":
            train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
            test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
            train_r2 = r2_score(y_train, y_train_pred)
            test_r2 = r2_score(y_test, y_test_pred)
            
            results = {
                'train_rmse': train_rmse,
                'test_rmse': test_rmse,
                'train_r2': train_r2,
                'test_r2': test_r2
            }
            
            logger.info(f"Train RMSE: {train_rmse:.6f}, R²: {train_r2:.4f}")
            logger.info(f"Test RMSE: {test_rmse:.6f}, R²: {test_r2:.4f}")
        
        else:  # classification
            train_acc = accuracy_score(y_train, y_train_pred)
            test_acc = accuracy_score(y_test, y_test_pred)
            
            results = {
                'train_accuracy': train_acc,
                'test_accuracy': test_acc
            }
            
            logger.info(f"Train Accuracy: {train_acc:.4f}")
            logger.info(f"Test Accuracy: {test_acc:.4f}")
        
        # 7. Feature Importance
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            self.feature_importance = dict(zip(self.feature_names, importance))
            
            # Top 10 중요 특징
            top_features = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info("\nTop 10 중요 특징:")
            for feat, imp in top_features:
                logger.info(f"  {feat}: {imp:.4f}")
        
        logger.info("=" * 60)
        logger.info("✨ 모델 학습 완료")
        logger.info("=" * 60)
        
        return results
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        예측
        
        Args:
            X: 특징 데이터프레임
        
        Returns:
            예측값 배열
        """
        if self.model is None:
            raise ValueError("모델이 학습되지 않았습니다")
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        
        return predictions
    
    def save_model(self, output_dir: str = "data/output/ml"):
        """
        모델 저장
        
        Args:
            output_dir: 출력 디렉토리
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. 모델 저장
        model_file = output_path / f"{self.model_type}_{self.task}_{timestamp}.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump(self.model, f)
        
        # 2. 스케일러 저장
        scaler_file = output_path / f"scaler_{timestamp}.pkl"
        with open(scaler_file, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        # 3. 메타데이터 저장
        meta = {
            'model_type': self.model_type,
            'task': self.task,
            'target_days': self.target_days,
            'feature_names': self.feature_names,
            'feature_importance': self.feature_importance,
            'timestamp': timestamp
        }
        
        meta_file = output_path / f"meta_{timestamp}.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 모델 저장 완료:")
        logger.info(f"  - 모델: {model_file}")
        logger.info(f"  - 스케일러: {scaler_file}")
        logger.info(f"  - 메타: {meta_file}")
    
    def _get_default_params(self) -> Dict:
        """기본 하이퍼파라미터"""
        if self.model_type == "xgboost":
            return {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }
        elif self.model_type == "lightgbm":
            return {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42,
                'verbose': -1
            }
        else:
            return {}


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ETF 랭킹 ML 모델 학습")
    parser.add_argument("--model", type=str, default="xgboost", choices=["xgboost", "lightgbm"])
    parser.add_argument("--task", type=str, default="regression", choices=["regression", "classification"])
    parser.add_argument("--target-days", type=int, default=5, help="예측 기간 (일)")
    parser.add_argument("--codes", type=str, default="069500,091160,133690,305720,373220", help="종목 코드 (쉼표 구분)")
    parser.add_argument("--start-date", type=str, default="2020-01-01")
    parser.add_argument("--end-date", type=str, default="2024-12-31")
    
    args = parser.parse_args()
    
    # 종목 코드 파싱
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    
    # 모델 초기화
    model = ETFRankingModel(
        model_type=args.model,
        task=args.task,
        target_days=args.target_days
    )
    
    # 데이터 준비
    X, y = model.prepare_data(codes, args.start_date, args.end_date)
    
    # 학습
    results = model.train(X, y)
    
    # 모델 저장
    model.save_model()
    
    print("\n" + "=" * 60)
    print("✨ 학습 완료!")
    print("=" * 60)
    print(f"모델: {args.model}")
    print(f"태스크: {args.task}")
    print(f"예측 기간: {args.target_days}일")
    print(f"결과: {results}")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
