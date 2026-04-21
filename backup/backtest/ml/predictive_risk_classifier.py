#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/ml/predictive_risk_classifier.py — P210-STEP10A Track B ML

리밸런스 시점에 알 수 있는 정보만으로 다음 N 영업일 crash risk 를 예측하는
tabular classifier 파이프라인.

단일 책임: dataset build → label → feature → leakage check → walk-forward
train/predict → prediction output → training report formatting.

주의:
- 미래 정보 누수 절대 금지 (feature 는 예측 시점 이전, label 은 이후).
- walk_forward_expanding 고정 (무작위 split / CV 금지).
- LR / RF 만 허용 (deep learning / LLM / 외부 API 금지).
- silent fallback 금지. 학습 데이터 부족 시 해당 날짜 prediction 을 생략
  하고 training_log 에 BURN_IN 기록 (명시적 분기).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger(__name__)

# ─── Feature Set v1 ──────────────────────────────────────────────────
FEATURE_COLUMNS_V1 = [
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "vol_5d",
    "vol_10d",
    "vol_20d",
    "drawdown_from_peak_20d",
    "vol_spike_5d_20d",
    "relative_return_vs_benchmark_5d",
    "relative_return_vs_benchmark_20d",
    "scanner_score",
    "selection_rank",
]

BENCHMARK_TICKER = "069500"


# ─── P210-STEP10B: Label Profile 매핑 ───────────────────────────────
# 각 profile = (horizon_days, drawdown_threshold, return_threshold, rule_desc)
LABEL_PROFILES: Dict[str, Dict[str, Any]] = {
    "L0_current_crash20": {
        "horizon_days": 20,
        "drawdown_threshold": -0.05,
        "return_threshold": -0.07,
        "rule_desc": (
            "다음 20영업일 내 max_drawdown <= -5% OR cum_return <= -7%"
            " (broad baseline)"
        ),
    },
    "L1_severe_crash20": {
        "horizon_days": 20,
        "drawdown_threshold": -0.08,
        "return_threshold": -0.10,
        "rule_desc": (
            "다음 20영업일 내 max_drawdown <= -8% OR cum_return <= -10%"
            " (severe only)"
        ),
    },
    "L2_fast_crash10": {
        "horizon_days": 10,
        "drawdown_threshold": -0.06,
        "return_threshold": -0.07,
        "rule_desc": (
            "다음 10영업일 내 max_drawdown <= -6% OR cum_return <= -7%"
            " (fast entry-shock)"
        ),
    },
}


def _resolve_label_profile(label_profile: str) -> Dict[str, Any]:
    """label_profile name → 파라미터 dict. 잘못된 값은 즉시 ValueError."""
    if label_profile not in LABEL_PROFILES:
        raise ValueError(
            f"P210-STEP10B: 허용되지 않은 label_profile={label_profile!r}."
            f" 허용: {sorted(LABEL_PROFILES.keys())}"
        )
    return LABEL_PROFILES[label_profile]


# ─── Label 생성 ──────────────────────────────────────────────────────
def _generate_label_for_sample(
    close_series: pd.Series,
    rebal_date: date,
    horizon_days: int,
    crash_drawdown_threshold: float,
    crash_return_threshold: float,
) -> Optional[int]:
    """단일 종목 × 단일 리밸런스 시점의 crash label 생성.

    양성(1): 다음 horizon 영업일 내 max_drawdown <= threshold OR
             cumulative_return <= threshold.
    음성(0): 위 조건 미충족.
    None: 데이터 부족으로 라벨 생성 불가.

    close_series: 해당 종목의 close price (DatetimeIndex, 정렬됨).
    rebal_date: 리밸런스 날짜 (이 날짜의 close 는 feature 에 포함됨).
    """
    ts = pd.Timestamp(rebal_date)
    future = close_series[close_series.index > ts]
    if len(future) < horizon_days:
        return None

    future_window = future.iloc[:horizon_days]
    entry_price = close_series[close_series.index <= ts].iloc[-1]

    # 누적 수익률
    cum_return = (future_window.iloc[-1] / entry_price) - 1.0

    # 최대 낙폭 (entry 기준)
    running_max = entry_price
    max_dd = 0.0
    for p in future_window.values:
        if p > running_max:
            running_max = p
        dd = (p / running_max) - 1.0
        if dd < max_dd:
            max_dd = dd

    if max_dd <= crash_drawdown_threshold or cum_return <= crash_return_threshold:
        return 1
    return 0


# ─── Feature 생성 ────────────────────────────────────────────────────
def _generate_features_for_sample(
    close_series: pd.Series,
    benchmark_close: pd.Series,
    rebal_date: date,
    scanner_score: Optional[float],
    selection_rank: Optional[int],
) -> Optional[Dict[str, float]]:
    """단일 종목 × 단일 리밸런스 시점의 feature dict 생성.

    close_series: 해당 종목 close (DatetimeIndex).
    benchmark_close: 069500 close (DatetimeIndex).
    rebal_date: 리밸런스 날짜. feature 는 이 날짜 이전 정보만 사용.
    """
    ts = pd.Timestamp(rebal_date)
    hist = close_series[close_series.index <= ts].astype(float)
    if len(hist) < 21:
        return None

    returns = hist.pct_change().dropna()
    if len(returns) < 20:
        return None

    close_arr = hist.values
    peak_20d = np.max(close_arr[-20:])
    current_price = close_arr[-1]

    # 벤치마크 수익률
    bm_hist = benchmark_close[benchmark_close.index <= ts].astype(float)
    if len(bm_hist) < 21:
        bm_ret_5d = 0.0
        bm_ret_20d = 0.0
    else:
        bm_ret_5d = (
            (bm_hist.iloc[-1] / bm_hist.iloc[-5] - 1.0) if len(bm_hist) >= 5 else 0.0
        )
        bm_ret_20d = (
            (bm_hist.iloc[-1] / bm_hist.iloc[-20] - 1.0) if len(bm_hist) >= 20 else 0.0
        )

    ret_5d = (hist.iloc[-1] / hist.iloc[-5] - 1.0) if len(hist) >= 5 else 0.0
    ret_20d = (hist.iloc[-1] / hist.iloc[-20] - 1.0) if len(hist) >= 20 else 0.0

    vol_5d = float(returns.tail(5).std() * (252**0.5)) if len(returns) >= 5 else 0.0
    vol_10d = float(returns.tail(10).std() * (252**0.5)) if len(returns) >= 10 else 0.0
    vol_20d = float(returns.tail(20).std() * (252**0.5)) if len(returns) >= 20 else 0.0

    features = {
        "ret_1d": float(returns.iloc[-1]) if len(returns) >= 1 else 0.0,
        "ret_3d": float(hist.iloc[-1] / hist.iloc[-3] - 1.0) if len(hist) >= 3 else 0.0,
        "ret_5d": ret_5d,
        "ret_10d": (
            float(hist.iloc[-1] / hist.iloc[-10] - 1.0) if len(hist) >= 10 else 0.0
        ),
        "ret_20d": ret_20d,
        "vol_5d": vol_5d,
        "vol_10d": vol_10d,
        "vol_20d": vol_20d,
        "drawdown_from_peak_20d": (
            (current_price / peak_20d - 1.0) if peak_20d > 0 else 0.0
        ),
        "vol_spike_5d_20d": (vol_5d / vol_20d) if vol_20d > 0 else 1.0,
        "relative_return_vs_benchmark_5d": ret_5d - bm_ret_5d,
        "relative_return_vs_benchmark_20d": ret_20d - bm_ret_20d,
    }
    return features


# ─── Leakage 검증 ────────────────────────────────────────────────────
def check_leakage(
    dataset: pd.DataFrame,
    price_data: pd.DataFrame,
    label_horizon_days: int,
) -> bool:
    """누수 검증: 모든 sample 에서 max(feature_dates) < min(label_dates).

    구체적으로:
    1. feature 는 rebalance_date 이하의 close 만 사용해야 한다.
    2. label 은 rebalance_date 초과 ~ rebalance_date + horizon 구간만 사용한다.
    3. 따라서 max(feature_date) = rebalance_date < min(label_date) = rebalance_date + 1bd.

    이를 sample 별로 assertion 검증한다.
    dataset 에 'rebalance_date', 'ticker', 'label' 컬럼이 있어야 함.
    label 이 None 인 행은 검증 대상에서 제외.

    Returns True if no leakage detected. Raises AssertionError on leakage.
    """
    labeled = dataset[dataset["label"].notna()].copy()
    if labeled.empty:
        return True

    for _, row in labeled.iterrows():
        rd_str = row["rebalance_date"]
        ticker = row["ticker"]
        rd_ts = pd.Timestamp(rd_str)

        try:
            ticker_close = price_data.xs(ticker, level="code")["close"]
        except KeyError:
            continue

        # feature 가 사용한 최대 날짜 = rebalance_date 이하
        feature_dates = ticker_close[ticker_close.index <= rd_ts].index
        if feature_dates.empty:
            continue

        # label 이 사용한 최소 날짜 = rebalance_date 초과
        label_dates = ticker_close[ticker_close.index > rd_ts].index
        if label_dates.empty:
            continue

        max_feature_date = feature_dates.max()
        min_label_date = label_dates.min()

        assert max_feature_date < min_label_date, (
            f"LEAKAGE DETECTED: ticker={ticker}, rebalance_date={rd_str},"
            f" max_feature_date={max_feature_date}, min_label_date={min_label_date}."
            f" feature 가 label 구간에 침범했음."
        )

    logger.info(
        f"[P210-STEP10A] leakage check passed:"
        f" {len(labeled)} labeled samples 검증 완료."
        f" 모든 sample 에서 max(feature_date) < min(label_date) 확인."
    )
    return True


# ─── Dataset 구축 ────────────────────────────────────────────────────
def build_dataset(
    price_data: pd.DataFrame,
    rebalance_trace: List[Dict[str, Any]],
    label_horizon_days: int,
    crash_drawdown_threshold: float,
    crash_return_threshold: float,
) -> pd.DataFrame:
    """전체 리밸런스 시점 × 후보 종목 dataset 구축.

    각 행: (rebalance_date, ticker, feature_1..N, label).
    label 이 None 인 행 = 미래 데이터 부족 (백테스트 끝 부근).
    """
    # REQUIRED: 벤치마크 close (069500).
    # relative_return_vs_benchmark 은 핵심 feature 이므로 benchmark 누락 시
    # silent 0 처리가 아니라 즉시 실패해야 한다.
    if BENCHMARK_TICKER not in price_data.index.get_level_values("code"):
        raise KeyError(
            f"P210-STEP10A: benchmark {BENCHMARK_TICKER} 가 price_data 에 없음."
            f" dynamic_etf_market 모드에서는 069500 이 반드시 로드되어야 함."
        )
    benchmark_close = price_data.xs(BENCHMARK_TICKER, level="code")["close"]

    rows: List[Dict[str, Any]] = []
    for trace_entry in rebalance_trace:
        rebal_date_str = trace_entry["rebalance_date"]
        rebal_date = date.fromisoformat(rebal_date_str)
        # REQUIRED: rebalance_trace 계약상 top_candidates_ranked 는 필수 키.
        # 누락 시 KeyError (BacktestRunner.run 이 항상 설정).
        if "top_candidates_ranked" not in trace_entry:
            raise KeyError(
                f"rebalance_trace entry 에 'top_candidates_ranked' 누락."
                f" rebalance_date={rebal_date_str}"
            )
        candidates = trace_entry["top_candidates_ranked"]

        for cand in candidates:
            ticker = cand["code"]
            score = cand["score"]
            rank = cand["rank"]

            try:
                ticker_close = price_data.xs(ticker, level="code")["close"]
            except KeyError:
                continue

            features = _generate_features_for_sample(
                close_series=ticker_close,
                benchmark_close=benchmark_close,
                rebal_date=rebal_date,
                scanner_score=score,
                selection_rank=rank,
            )
            if features is None:
                continue

            label = _generate_label_for_sample(
                close_series=ticker_close,
                rebal_date=rebal_date,
                horizon_days=label_horizon_days,
                crash_drawdown_threshold=crash_drawdown_threshold,
                crash_return_threshold=crash_return_threshold,
            )

            row = {
                "rebalance_date": rebal_date_str,
                "ticker": ticker,
                "scanner_score": score,
                "selection_rank": rank,
                **features,
                "label": label,
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        logger.info(
            f"[P210-STEP10A] dataset 구축 완료:"
            f" {len(df)} samples, {df['rebalance_date'].nunique()} rebalance dates,"
            f" label 분포: {df['label'].value_counts(dropna=False).to_dict()}"
        )
    return df


# ─── Walk-Forward Train/Predict ──────────────────────────────────────
def _create_model(model_family: str):
    """모델 인스턴스 생성. 고정 하이퍼파라미터."""
    if model_family == "logistic_regression":
        return LogisticRegression(
            C=1.0,
            penalty="l2",
            class_weight="balanced",
            solver="lbfgs",
            max_iter=500,
            random_state=42,
        )
    if model_family == "random_forest":
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            class_weight="balanced",
            random_state=42,
        )
    raise ValueError(f"허용되지 않은 model_family: {model_family!r}")


def walk_forward_train(
    dataset: pd.DataFrame,
    model_family: str,
    min_train_samples: int,
    feature_columns: Optional[List[str]] = None,
) -> Tuple[Dict[str, Dict[str, float]], List[Dict[str, Any]]]:
    """Walk-forward expanding 학습 + per-rebalance-date prediction.

    Returns:
        predictions: {rebalance_date_str: {ticker: crash_probability, ...}}
        training_log: 날짜별 학습/예측 상태 로그 리스트
    """
    if feature_columns is None:
        feature_columns = list(FEATURE_COLUMNS_V1)

    labeled = dataset[dataset["label"].notna()].copy()
    labeled["label"] = labeled["label"].astype(int)
    all_dates = sorted(dataset["rebalance_date"].unique())

    predictions: Dict[str, Dict[str, float]] = {}
    training_log: List[Dict[str, Any]] = []

    for predict_date in all_dates:
        # train: predict_date 이전의 labeled 데이터만
        train_data = labeled[labeled["rebalance_date"] < predict_date]
        train_samples = len(train_data)

        if train_samples < min_train_samples:
            # EXPLICIT BURN-IN: 학습 데이터 부족 → prediction 생략
            training_log.append(
                {
                    "predict_date": predict_date,
                    "status": "BURN_IN",
                    "train_samples": train_samples,
                    "min_required": min_train_samples,
                    "model_family": model_family,
                }
            )
            continue

        # 학습
        X_train = train_data[feature_columns].values
        y_train = train_data["label"].values
        positive_ratio = float(y_train.mean())

        # 모든 label 이 동일한 경우 (e.g. 전부 0) → 예측 불가
        if len(set(y_train)) < 2:
            training_log.append(
                {
                    "predict_date": predict_date,
                    "status": "SINGLE_CLASS",
                    "train_samples": train_samples,
                    "positive_ratio": positive_ratio,
                    "model_family": model_family,
                }
            )
            continue

        model = _create_model(model_family)
        model.fit(X_train, y_train)

        # 예측 대상: predict_date 의 모든 후보
        predict_data = dataset[dataset["rebalance_date"] == predict_date]
        if predict_data.empty:
            training_log.append(
                {
                    "predict_date": predict_date,
                    "status": "NO_CANDIDATES",
                    "train_samples": train_samples,
                    "model_family": model_family,
                }
            )
            continue

        X_predict = predict_data[feature_columns].values

        # NaN 처리: feature 가 NaN 인 경우 0 으로 대체
        # (WHITELIST math: 수치 계산 불가 = 중립 신호)
        X_predict = np.nan_to_num(X_predict, nan=0.0)

        probas = model.predict_proba(X_predict)
        # crash=1 의 확률
        if probas.shape[1] >= 2:
            crash_probs = probas[:, 1]
        else:
            crash_probs = np.zeros(len(predict_data))

        date_preds: Dict[str, float] = {}
        for idx, (_, row) in enumerate(predict_data.iterrows()):
            date_preds[row["ticker"]] = float(round(crash_probs[idx], 6))
        predictions[predict_date] = date_preds

        # Feature importance (LR: coef, RF: feature_importances_)
        importance = {}
        if model_family == "logistic_regression" and hasattr(model, "coef_"):
            for fi, fc in enumerate(feature_columns):
                importance[fc] = float(round(model.coef_[0][fi], 6))
        elif model_family == "random_forest" and hasattr(model, "feature_importances_"):
            for fi, fc in enumerate(feature_columns):
                importance[fc] = float(round(model.feature_importances_[fi], 6))

        training_log.append(
            {
                "predict_date": predict_date,
                "status": "PREDICTED",
                "train_samples": train_samples,
                "positive_ratio": round(positive_ratio, 4),
                "model_family": model_family,
                "predicted_count": len(date_preds),
                "avg_crash_prob": float(round(np.mean(crash_probs), 4)),
                "max_crash_prob": float(round(np.max(crash_probs), 4)),
                "feature_importance": importance,
            }
        )

    # 요약 로그
    predicted_dates = [e for e in training_log if e["status"] == "PREDICTED"]
    burnin_dates = [e for e in training_log if e["status"] == "BURN_IN"]
    logger.info(
        f"[P210-STEP10A] walk_forward 완료: {len(predicted_dates)} predicted,"
        f" {len(burnin_dates)} burn-in, {len(all_dates)} total rebalance dates"
    )

    return predictions, training_log


# ─── Sweep 용 통합 함수 ──────────────────────────────────────────────
def build_predictions_for_sweep(
    price_data: pd.DataFrame,
    rebalance_trace: List[Dict[str, Any]],
    config: Dict[str, Any],
    model_family: str,
    min_train_samples_override: Optional[int] = None,
    label_profile: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, float]], List[Dict[str, Any]], pd.DataFrame]:
    """sweep 모듈에서 호출. dataset 구축 → walk-forward → predictions 반환.

    config: trackb_predictive_risk_classifier SSOT 블록.
    min_train_samples_override: 실험군별 override (Step10A-2).
    label_profile: 실험군별 label 재정의 (Step10B). None 이면 config 기본값.

    Returns:
        predictions: {date_str: {ticker: prob}}
        training_log: walk-forward 로그
        dataset: 구축된 DataFrame (training report 용)
    """
    # P210-STEP10B: label_profile override 적용
    if label_profile is not None:
        lp = _resolve_label_profile(label_profile)
        label_horizon_days = lp["horizon_days"]
        crash_drawdown_threshold = lp["drawdown_threshold"]
        crash_return_threshold = lp["return_threshold"]
    else:
        label_horizon_days = config["label_horizon_days"]
        crash_drawdown_threshold = config["label_crash_drawdown_threshold"]
        crash_return_threshold = config["label_crash_return_threshold"]

    dataset = build_dataset(
        price_data=price_data,
        rebalance_trace=rebalance_trace,
        label_horizon_days=label_horizon_days,
        crash_drawdown_threshold=crash_drawdown_threshold,
        crash_return_threshold=crash_return_threshold,
    )

    if dataset.empty:
        logger.warning("[P210-STEP10B] dataset 이 비어있음 → predictions 없음")
        return {}, [], dataset

    check_leakage(
        dataset=dataset,
        price_data=price_data,
        label_horizon_days=label_horizon_days,
    )

    # P210-STEP10A-2: per-experiment min_train_samples override
    effective_mts = (
        min_train_samples_override
        if min_train_samples_override is not None
        else config["min_train_samples"]
    )

    predictions, training_log = walk_forward_train(
        dataset=dataset,
        model_family=model_family,
        min_train_samples=effective_mts,
    )

    return predictions, training_log, dataset


# ─── Training Report ─────────────────────────────────────────────────
def format_training_report(
    training_log: List[Dict[str, Any]],
    dataset: pd.DataFrame,
    config: Dict[str, Any],
    model_family: str,
    min_train_samples_used: Optional[int] = None,
    label_profile: Optional[str] = None,
    action_policy: Optional[str] = None,
) -> Dict[str, Any]:
    """training report 구조화 데이터 반환 (md/json 생성은 compare 모듈에서).

    Returns:
        report dict with: label_definition, feature_set, training_scheme,
        class_imbalance, model_summary, leakage_check, interpretation_warning.
    """
    labeled = dataset[dataset["label"].notna()]
    total_samples = len(labeled)
    positive_count = int((labeled["label"] == 1).sum()) if not labeled.empty else 0
    negative_count = total_samples - positive_count
    positive_ratio = (
        round(positive_count / total_samples, 4) if total_samples > 0 else 0.0
    )

    predicted_entries = [e for e in training_log if e["status"] == "PREDICTED"]
    burnin_entries = [e for e in training_log if e["status"] == "BURN_IN"]

    # Top feature importance (마지막 predicted entry 기준)
    top_features = {}
    if predicted_entries:
        last_predicted = predicted_entries[-1]
        importance = last_predicted.get("feature_importance", {})
        top_features = dict(
            sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        )

    first_predict_date = (
        predicted_entries[0]["predict_date"] if predicted_entries else None
    )
    last_predict_date = (
        predicted_entries[-1]["predict_date"] if predicted_entries else None
    )

    # P210-STEP10B: predicted 평균 확률 + top feature summary 계산
    _avg_probs = [
        e["avg_crash_prob"] for e in predicted_entries if "avg_crash_prob" in e
    ]
    avg_predicted_probability = (
        round(sum(_avg_probs) / len(_avg_probs), 6) if _avg_probs else None
    )
    # top feature summary: name/coefficient/abs_value
    top_feature_summary = [
        {"feature": fname, "coefficient": fval, "abs_value": abs(fval)}
        for fname, fval in top_features.items()
    ]

    # P210-STEP10B: label_profile override 반영
    if label_profile is not None:
        lp = _resolve_label_profile(label_profile)
        _horizon = lp["horizon_days"]
        _dd_thresh = lp["drawdown_threshold"]
        _ret_thresh = lp["return_threshold"]
        _rule_desc = lp["rule_desc"]
    else:
        _horizon = config["label_horizon_days"]
        _dd_thresh = config["label_crash_drawdown_threshold"]
        _ret_thresh = config["label_crash_return_threshold"]
        _rule_desc = (
            f"다음 {_horizon}영업일 내"
            f" max_drawdown <= {_dd_thresh}"
            f" OR cum_return <= {_ret_thresh}"
        )

    return {
        "label_profile": label_profile,
        "action_policy": action_policy,
        # P210-STEP10B: 지시문 요구 top-level 필드 4종
        "label_positive_ratio": positive_ratio,
        "predicted_dates_count": len(predicted_entries),
        "avg_predicted_probability": avg_predicted_probability,
        "top_feature_summary": top_feature_summary,
        "label_definition": {
            "profile": label_profile,
            "horizon_days": _horizon,
            "crash_drawdown_threshold": _dd_thresh,
            "crash_return_threshold": _ret_thresh,
            "rule_description": _rule_desc,
            "positive_meaning": _rule_desc,
        },
        "feature_set": {
            "version": config["feature_set_version"],
            "columns": list(FEATURE_COLUMNS_V1),
            "count": len(FEATURE_COLUMNS_V1),
            "benchmark_ticker": BENCHMARK_TICKER,
        },
        "training_scheme": config["training_scheme"],
        "model_family": model_family,
        "class_imbalance": {
            "total_labeled_samples": total_samples,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "positive_ratio": positive_ratio,
        },
        "walk_forward_summary": {
            "total_rebalance_dates": len(training_log),
            "predicted_dates": len(predicted_entries),
            "burnin_dates": len(burnin_entries),
            "first_predict_date": first_predict_date,
            "last_predict_date": last_predict_date,
            "min_train_samples": (
                min_train_samples_used
                if min_train_samples_used is not None
                else config["min_train_samples"]
            ),
        },
        "top_feature_importance": top_features,
        "leakage_check_passed": True,
        "interpretation_warning": (
            "이 ML 은 연구/검증 전용이며 운영 SSOT 에 자동 승격되지 않는다."
            " burn-in 구간이 길어 유효 예측 구간이 짧을 수 있고,"
            " 통계적 유의성을 주장하지 않는다."
        ),
    }
