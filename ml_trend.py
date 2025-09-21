# ml_trend.py (간단 스켈레톤)
import pandas as pd
from typing import Dict, List, Tuple
from sqlalchemy import select
from db import SessionLocal, PriceDaily
from sklearn.ensemble import GradientBoostingRegressor

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    # df: [date, code, close] 정렬 가정
    df = df.sort_values(["code","date"]).copy()
    df["ret_21"] = df.groupby("code")["close"].pct_change(21)
    df["ret_63"] = df.groupby("code")["close"].pct_change(63)
    df["ret_126"]= df.groupby("code")["close"].pct_change(126)
    df["sma_20"] = df.groupby("code")["close"].transform(lambda s: s.rolling(20).mean())
    df["sma_60"] = df.groupby("code")["close"].transform(lambda s: s.rolling(60).mean())
    df["sma_200"]= df.groupby("code")["close"].transform(lambda s: s.rolling(200).mean())
    df["k_sma200"]= (df["close"]/df["sma_200"] - 1.0)
    return df

def make_labels(df: pd.DataFrame, horizon=21) -> pd.DataFrame:
    # 다음 21영업일 수익률을 회귀 타깃으로
    df = df.sort_values(["code","date"]).copy()
    df["fwd_ret"] = df.groupby("code")["close"].shift(-horizon) / df["close"] - 1.0
    return df

def train_model(prices: pd.DataFrame) -> Tuple[GradientBoostingRegressor, pd.DataFrame]:
    # 피쳐/라벨 만들기
    Xy = make_labels(build_features(prices))
    X = Xy.dropna(subset=["ret_21","ret_63","ret_126","sma_20","sma_60","sma_200","fwd_ret"]).copy()
    feats = ["ret_21","ret_63","ret_126","k_sma200"]
    model = GradientBoostingRegressor(random_state=42)
    # 워크포워드가 이상적이지만, 데모로 단순 훈련:
    model.fit(X[feats], X["fwd_ret"])
    return model, X[["date","code"] + feats + ["fwd_ret"]]

def predict_scores(model, latest_slice: pd.DataFrame) -> pd.Series:
    feats = ["ret_21","ret_63","ret_126","k_sma200"]
    L = latest_slice.dropna(subset=feats).copy()
    preds = model.predict(L[feats])
    return pd.Series(preds, index=L["code"].values)
