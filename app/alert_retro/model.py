"""POC5-08 — +5 고정 Ridge 시간 분리 검증(설계 §5 · §6 · PLAN §2-2 · §2-6 · 판정 §2 · §3-A).

```text
가중치      신호일의 서로 다른 series 수 S · 그 날 같은 series 행 수 N → w = 1/(S×N)(날짜 합 1 · 정확한 분수)
기준        학습 y 의 가중 중앙값 — y 오름차순 · 누적 가중치 ≥ 총합/2 인 첫 값
전처리      학습 구간에서만 fit — 숫자 2개: 결측 표시(0/1) + 유효값 가중 중앙값 대입(없으면 0) +
            가중 평균 · 가중 모집단 표준편차 표준화(값이 모두 같으면 0) · 범주 6개: 학습 사전 one-hot
            (dense float64 · 처음 보는 값 = 그 묶음 0 벡터 + 건수)
모델        Ridge(alpha=1.0, solver="svd", fit_intercept=True) · sample_weight=w · 추정 하한 -1(상한 없음)
구간        anchor = 종료일 5거래일 전 · anchor 로 끝나는 15거래일 = 5일 × 3(빈 날도 날짜로 남김)
            시험 = 구간 신호일 · +5 평가일 ≤ 종료일 · 시험 시작 = 그 행들의 가장 이른 runtime_kst
            학습 = 구간 첫날보다 앞 신호일 · 평가일 15:30 < 시험 시작 · computed_at < 시험 시작
            학습 신호일 20 미만 또는 시험 행 0 = 그 구간 DATA_SHORT
MAE         날짜별 가중 절대오차 합 → 날짜 평균(%p) · 세 구간 모두 유효할 때만 전체 비교 판정
```
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any, Optional, Sequence

import numpy as np

from app.alert_retro import features as F
from app.ledger_reports.dates import at_kst
from app.three_push_runtime import ledger_outcome_prices as px

ALPHA = 1.0
MIN_TRAIN_DATES = 20
BLOCK_COUNT = 3
BLOCK_DAYS = 5
ANCHOR_LAG = 5
FLOOR = -1.0
CLOSE = "15:30"

RECIPE: dict[str, Any] = {
    "label": "price_outcome.return_raw(horizon=5 · MATURED)",
    "key": "event_id + item_seq + series_id",
    "model": "Ridge(alpha=1.0, solver='svd', fit_intercept=True) · sample_weight",
    "baseline": "학습 표본 날짜 균형 가중 중앙값(누적 가중치 ≥ 총합/2 인 첫 y)",
    "weights": "1/(S×N) — 신호일의 서로 다른 series 수 S · 그 날 같은 series 행 수 N",
    "numeric": list(F.NUMERIC),
    "numeric_source": {f"{k[0]}/{k[1]}": v for k, v in F.NUMERIC_KEYS.items()},
    "numeric_unit": "values_json % ÷ 100 = 비율",
    "numeric_transform": "결측 표시 0/1(표준화 안 함) + 학습 유효값 가중 중앙값 대입(없으면 0) + "
    "학습 가중 평균 · 가중 모집단 표준편차 표준화(값이 모두 같으면 0)",
    "categorical": list(F.CATEGORICAL),
    "categorical_transform": "학습 사전 dense float64 one-hot(NULL = NONE · 처음 보는 값 = 0 벡터)",
    "prediction_floor": FLOOR,
    "blocks": "anchor = 종료일 5거래일 전 · anchor 로 끝나는 15거래일 = 5일 × 3",
    "train_boundary": "신호일 < 구간 첫날 · 평가일 15:30 < 시험 시작 · computed_at < 시험 시작",
    "test_start": "구간 ML 시험 행의 가장 이른 runtime_kst",
    "min_train_dates": MIN_TRAIN_DATES,
    "mae": "날짜별 가중 절대오차 합의 날짜 평균 · %p",
    "verdict": "소수 2자리 %p 비교(반올림 half-up) — 모델 < 기준 = 개선 · 같음 = 차이 없음 · 큼 = 악화",
    "ml_scope": {
        "push_kind": list(F.ML_PUSH_KINDS),
        "subject_kind": list(F.ML_SUBJECT_KINDS),
        "price_basis": list(F.ML_PRICE_BASES),
        "contract_version": list(F.SUPPORTED_CONTRACTS),
    },
}
VERDICT_TEXT = {"IMPROVED": "개선", "NO_DIFFERENCE": "차이 없음", "WORSE": "악화"}


def weights(rows: Sequence[dict[str, Any]]) -> list[Fraction]:
    per: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        per[r["signal_date"]][r["series_id"]] += 1
    return [
        Fraction(1, len(per[r["signal_date"]]) * per[r["signal_date"]][r["series_id"]])
        for r in rows
    ]


def weighted_median(values: Sequence[float], w: Sequence[Fraction]) -> float:
    order = sorted(range(len(values)), key=lambda i: values[i])
    half = sum(w, Fraction(0)) / 2
    acc = Fraction(0)
    for i in order:
        acc += w[i]
        if acc >= half:
            return float(values[i])
    raise ValueError("빈 표본")


class Prep:
    """학습 구간에서만 fit 하는 변환(숫자 대입 · 표준화 · 범주 사전)."""

    def __init__(self, train: Sequence[dict[str, Any]], w: Sequence[Fraction]):
        wf = np.array([float(x) for x in w])
        self.fill: dict[str, float] = {}
        self.mean: dict[str, float] = {}
        self.std: dict[str, Optional[float]] = {}
        for name in F.NUMERIC:
            vals = [r["num"].get(name) for r in train]
            valid = [(v, w[i]) for i, v in enumerate(vals) if v is not None]
            self.fill[name] = (
                weighted_median([v for v, _ in valid], [x for _, x in valid])
                if valid
                else 0.0
            )
            col = np.array([self.fill[name] if v is None else v for v in vals])
            if col.size == 0 or float(col.max()) == float(col.min()):
                self.mean[name], self.std[name] = (
                    float(col[0]) if col.size else 0.0
                ), None
                continue
            mean = float(np.sum(wf * col) / np.sum(wf))
            std = math.sqrt(float(np.sum(wf * (col - mean) ** 2) / np.sum(wf)))
            self.mean[name], self.std[name] = mean, (std if std > 0 else None)
        self.vocab = {
            name: sorted({r["cat"][name] for r in train}) for name in F.CATEGORICAL
        }

    def columns(self) -> list[str]:
        cols = []
        for name in F.NUMERIC:
            cols += [f"{name}", f"{name}_missing"]
        for name in F.CATEGORICAL:
            cols += [f"{name}={v}" for v in self.vocab[name]]
        return cols

    def transform(
        self, rows: Sequence[dict[str, Any]]
    ) -> tuple[np.ndarray, dict[str, int]]:
        unseen: Counter[str] = Counter()
        out = np.zeros((len(rows), len(self.columns())), dtype=np.float64)
        for i, r in enumerate(rows):
            j = 0
            for name in F.NUMERIC:
                v = r["num"].get(name)
                x = self.fill[name] if v is None else v
                std = self.std[name]
                out[i, j] = 0.0 if std is None else (x - self.mean[name]) / std
                out[i, j + 1] = 1.0 if v is None else 0.0
                j += 2
            for name in F.CATEGORICAL:
                vocab = self.vocab[name]
                value = r["cat"][name]
                if value in vocab:
                    out[i, j + vocab.index(value)] = 1.0
                else:
                    unseen[name] += 1
                j += len(vocab)
        return out, dict(sorted(unseen.items()))


def window(cal: px.Calendar, end: str) -> Optional[list[list[str]]]:
    """세 구간의 거래일(오래된 순) — 캘린더로 정할 수 없으면 None."""
    anchor: Optional[str] = end
    for _ in range(ANCHOR_LAG):
        anchor = cal.previous(anchor) if anchor else None
    if anchor is None:
        return None
    days = [anchor]
    while len(days) < BLOCK_COUNT * BLOCK_DAYS:
        prev = cal.previous(days[0])
        if prev is None:
            return None
        days.insert(0, prev)
    starts = range(0, BLOCK_COUNT * BLOCK_DAYS, BLOCK_DAYS)
    return [days[i:][:BLOCK_DAYS] for i in starts]


def pp(x: float) -> float:
    """비율 → %p 소수 2자리(half-up) — 표시 · 판정 값. 원시값은 따로 보존한다."""
    return float(Decimal(repr(x * 100.0)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def verdict_of(model_mae: float, baseline_mae: float) -> str:
    """표시하는 소수 2자리 %p 로 비교 — 원시 차이가 있어도 표시값이 같으면 '차이 없음'."""
    m, b = pp(model_mae), pp(baseline_mae)
    return "IMPROVED" if m < b else ("NO_DIFFERENCE" if m == b else "WORSE")


def _date_errors(
    rows: Sequence[dict[str, Any]], w: Sequence[Fraction], pred: np.ndarray, base: float
) -> dict[str, tuple[float, float]]:
    out: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r, wi, p in zip(rows, w, pred):
        acc = out[r["signal_date"]]
        acc[0] += float(wi) * abs(r["y"] - float(p))
        acc[1] += float(wi) * abs(r["y"] - base)
    return {d: (v[0], v[1]) for d, v in sorted(out.items())}


def _block(
    index: int, days: list[str], obs: Sequence[dict[str, Any]], end: str
) -> tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]]:
    start, dayset = days[0], set(days)
    test = [o for o in obs if o["signal_date"] in dayset and o["eval_date"] <= end]
    info: dict[str, Any] = {
        "index": index,
        "days": days,
        "start": start,
        "end": days[-1],
        "test_rows": len(test),
        "test_dates": len({o["signal_date"] for o in test}),
        "test_groups": dict(sorted(Counter(o["group"] for o in test).items())),
    }
    keys = {(o["event_id"], o["item_seq"], o["slot"]) for o in test}
    if not test:
        info.update(status="DATA_SHORT", reason="시험 행 없음")
        return info, {k: {"status": "DATA_SHORT", "block": index} for k in keys}
    test_start = min(o["runtime"] for o in test)
    before = [o for o in obs if o["signal_date"] < start]
    train = [
        o
        for o in before
        if at_kst(o["eval_date"], CLOSE) < test_start
        and o["computed"] is not None
        and o["computed"] < test_start
    ]
    n_dates = len({o["signal_date"] for o in train})
    info.update(
        test_start=test_start.isoformat(),
        train_rows=len(train),
        train_dates=n_dates,
        train_excluded_by_time=len(before) - len(train),
    )
    if n_dates < MIN_TRAIN_DATES:
        info.update(
            status="DATA_SHORT", reason=f"학습 신호일 {n_dates} < {MIN_TRAIN_DATES}"
        )
        return info, {k: {"status": "DATA_SHORT", "block": index} for k in keys}

    from sklearn.linear_model import Ridge  # 학습할 때만 읽는다(조회 GET 은 읽지 않음)

    w_train = weights(train)
    prep = Prep(train, w_train)
    x_train, _ = prep.transform(train)
    y_train = np.array([o["y"] for o in train])
    model = Ridge(alpha=ALPHA, solver="svd", fit_intercept=True)
    model.fit(x_train, y_train, sample_weight=np.array([float(x) for x in w_train]))
    base = weighted_median([o["y"] for o in train], w_train)
    x_test, unseen = prep.transform(test)
    pred = np.maximum(model.predict(x_test), FLOOR)
    w_test = weights(test)
    errors = _date_errors(test, w_test, pred, base)
    m = sum(v[0] for v in errors.values()) / len(errors)
    b = sum(v[1] for v in errors.values()) / len(errors)
    info.update(
        status="VALID",
        reason=None,
        baseline_value=base,
        baseline_pct=pp(base),
        model_mae=m,
        baseline_mae=b,
        model_mae_pp=pp(m),
        baseline_mae_pp=pp(b),
        unseen_categories=unseen,
        columns=len(prep.columns()),
        # 학습 구간에서만 fit 한 변환값(감사용 · 시험 행이 바뀌어도 같아야 한다)
        numeric_fit={
            name: {
                "fill": prep.fill[name],
                "mean": prep.mean[name],
                "std": prep.std[name],
            }
            for name in F.NUMERIC
        },
        vocab_sizes={name: len(v) for name, v in prep.vocab.items()},
        date_errors=errors,
    )
    rows: dict[tuple[str, int, int], dict[str, Any]] = {}
    for o, p in zip(test, pred):
        rows[(o["event_id"], o["item_seq"], o["slot"])] = {
            "status": "ESTIMATED",
            "block": index,
            "actual_pct": pp(o["y"]),
            "estimate_pct": pp(float(p)),
            "baseline_pct": pp(base),
            "abs_error_pp": pp(abs(o["y"] - float(p))),
            "baseline_abs_error_pp": pp(abs(o["y"] - base)),
            "actual_raw": o["y"],
            "estimate_raw": float(p),
        }
    return info, rows


def evaluate(
    obs: Sequence[dict[str, Any]], cal: px.Calendar, end: str
) -> dict[str, Any]:
    """세 구간 검증 — {status, reason, blocks, overall, rows(슬롯 키 → ML 칸)}."""
    days = window(cal, end)
    if days is None:
        return {
            "status": "DATA_SHORT",
            "reason": "운영 캘린더로 검증 구간을 정할 수 없음",
            "blocks": [],
            "overall": None,
            "rows": {},
        }
    blocks, rows = [], {}
    for i, block_days in enumerate(days, start=1):
        info, got = _block(i, block_days, obs, end)
        blocks.append(info)
        rows.update(got)
    overall = None
    if all(b["status"] == "VALID" for b in blocks):
        errs = [e for b in blocks for e in b["date_errors"].values()]
        m = sum(e[0] for e in errs) / len(errs)
        b = sum(e[1] for e in errs) / len(errs)
        mp, bp = pp(m), pp(b)
        verdict = verdict_of(m, b)
        overall = {
            "test_dates": len(errs),
            "model_mae": m,
            "baseline_mae": b,
            "model_mae_pp": mp,
            "baseline_mae_pp": bp,
            "difference_pp": float(Decimal(repr(mp)) - Decimal(repr(bp))),
            "verdict": verdict,
            "verdict_text": VERDICT_TEXT[verdict],
        }
    for b in blocks:
        if "date_errors" in b:
            b["date_errors"] = {d: list(v) for d, v in b["date_errors"].items()}
    return {
        "status": "COMPARED" if overall else "DATA_SHORT",
        "reason": None if overall else "세 구간이 모두 유효하지 않음 — 구간별 진단만",
        "blocks": blocks,
        "overall": overall,
        "rows": rows,
    }
