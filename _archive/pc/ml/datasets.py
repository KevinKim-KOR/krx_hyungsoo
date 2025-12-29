# ml/datasets.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, pandas as pd, numpy as np, torch
from torch.utils.data import Dataset

DATA_CACHE = os.path.join("data","cache","kr")

def _load_close_series(code: str) -> pd.Series:
    # 캐시 pkl: date, close 열 가정
    pkl = os.path.join(DATA_CACHE, f"{code}.pkl")
    if not os.path.exists(pkl):
        raise FileNotFoundError(pkl)
    df = pd.read_pickle(pkl)
    s = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]))
    s = s.sort_index().dropna()
    return s

def make_returns(close: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"close": close})
    df["r1"]  = df["close"].pct_change(1)
    df["r5"]  = df["close"].pct_change(5)
    df["r20"] = df["close"].pct_change(20)
    df["sma5"]  = df["close"].rolling(5).mean()/df["close"] - 1
    df["sma20"] = df["close"].rolling(20).mean()/df["close"] - 1
    df = df.dropna()
    return df

class SeqDataset(Dataset):
    """
    단순 next-day 방향성 분류(>0 → 1 else 0).
    Development Rules: 병렬 금지 → DataLoader num_workers=0로만 사용.
    """
    def __init__(self, codes, seq_len=60, threshold=0.0):
        self.X, self.y = [], []
        for code in codes:
            s  = _load_close_series(code)
            df = make_returns(s)
            feats = df[["r1","r5","r20","sma5","sma20"]].values.astype(np.float32)
            label = (df["r1"].shift(-1) > threshold).astype(np.int64).values   # 다음날
            # 시퀀스 구성
            for i in range(seq_len, len(df)-1):
                self.X.append(feats[i-seq_len:i])
                self.y.append(label[i])
        if not self.X:
            raise RuntimeError("데이터가 부족합니다. 캐시 또는 코드 셋을 확인하세요.")
        self.X = torch.from_numpy(np.stack(self.X))     # (N, T, F)
        self.y = torch.from_numpy(np.array(self.y))

    def __len__(self): return self.X.shape[0]
    def __getitem__(self, idx): return self.X[idx], self.y[idx]
