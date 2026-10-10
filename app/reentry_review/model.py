"""POC5-06 — D20 연구 추정 한 가지(설계 개정 2 §5 · 고정 recipe · 설정 탐색 0).

```text
목표     D20(t) = min(0, min_{h=1..20} C(t+h) / C(t) − 1) — 연구 축 위치로 센 20거래일
입력     5 · 20 · 60거래일 종가 변화 · 최근 20개 일별 로그수익률 모집단 표준편차(ddof=0) ·
         최근 60거래일 최고 종가 대비 현재 종가 변화
모델     StandardScaler → Ridge(alpha=1.0, solver='svd', fit_intercept=True) · 예측 [-1, 0] 제한
기준     그 학습 구간 D20 중앙값을 모든 검증 날짜에 적용
검증     끝 = 축에서 t 의 20일 전 · 그 앞 189 축 날짜를 63씩 3구간 · 학습 = 구간 시작 전에 D20
         평가가 끝난 유효 표본만(252 미만 = DATA_SHORT) · 표준화는 학습 구간만 · MAE %p
최종     t 까지 D20 이 성숙한 유효 표본으로 fit · t 의 feature 로 추정(세 구간 검증이 모두 될 때만)
```

sklearn 은 `fit_predict` 안에서만 불러온다 — 검토 창 조회는 학습을 하지 않는다(설계 §2 · §7).
"""

from __future__ import annotations

import math
from typing import Any, Optional

from app.reentry_review import models as M
from app.reentry_review.prices import REASON_TEXT, AxisSeries

H = 20  # 목표 창(축 날짜)
LB = 60  # feature 창(축 날짜)
N_VAL = 189
BLOCK = 63
MIN_TRAIN = 252

RECIPE = {
    "target": "D20(t) = min(0, min_{h=1..20} C(t+h)/C(t) - 1) · 연구 축 위치 기준",
    "features": [
        "C(t)/C(t-5)-1",
        "C(t)/C(t-20)-1",
        "C(t)/C(t-60)-1",
        "std(ddof=0) of last 20 daily log returns",
        "C(t)/max(C(t-59)..C(t))-1",
    ],
    "model": "StandardScaler -> Ridge(alpha=1.0, solver='svd', fit_intercept=True)",
    "clip": [-1.0, 0.0],
    "baseline": "median D20 of the training block",
    "validation": {"end": "axis t-20", "dates": N_VAL, "blocks": 3, "block": BLOCK},
    "min_train": MIN_TRAIN,
    "mae_unit": "%p",
    "version": "poc5_06.v1",
}

FEATURE_NAMES = ("chg5", "chg20", "chg60", "vol20", "from_high60")


def features_at(c: list[Optional[float]], i: int) -> list[float]:
    """축 위치 i 의 feature 5개(창 c[i-60..i] 가 유효하다고 호출부가 확인)."""
    ci = c[i]
    lo, hi = i - LB, i + 1
    w = c[lo:hi]
    logs = [math.log(w[k] / w[k - 1]) for k in range(len(w) - H, len(w))]
    mean = sum(logs) / len(logs)
    vol = math.sqrt(sum((x - mean) ** 2 for x in logs) / len(logs))
    return [
        ci / c[i - 5] - 1.0,
        ci / c[i - 20] - 1.0,
        ci / c[i - LB] - 1.0,
        vol,
        ci / max(w[-LB:]) - 1.0,
    ]


def target_at(c: list[Optional[float]], i: int) -> float:
    """D20(축 위치 i) — c[i..i+20] 이 유효하다고 호출부가 확인."""
    lowest = min(c[i + h] / c[i] - 1.0 for h in range(1, H + 1))
    return min(0.0, lowest)


def fit_predict(train_x, train_y, test_x) -> list[float]:
    """학습 구간만으로 표준화 · Ridge · [-1, 0] 제한."""
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(np.asarray(train_x, dtype=float))
    model = Ridge(alpha=1.0, solver="svd", fit_intercept=True)
    model.fit(scaler.transform(np.asarray(train_x, dtype=float)), train_y)
    raw = model.predict(scaler.transform(np.asarray(test_x, dtype=float)))
    return [min(0.0, max(-1.0, float(v))) for v in raw]


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def verdict(model_mae: float, base_mae: float) -> str:
    """전체 MAE 비교 — 화면 소수 2자리(%p) 기준."""
    m, b = round(model_mae, 2), round(base_mae, 2)
    if m < b:
        return M.IMPROVED
    return M.NO_DIFFERENCE if m == b else M.WORSE


def t_window_problem(series: AxisSeries, T: int) -> Optional[tuple[str, str]]:
    """기준일 feature 창(축 T-60..T)을 못 쓰면 (상태, 사유) · 쓰면 None.

    축 날짜 61일 미만 = DATA_SHORT. 창 안의 축 공백 · 무효 종가 · 허용 밖 출처 · 감지된 경계 =
    PRICE_BASIS_UNCONFIRMED(설계 §4 'feature 창을 확정할 수 없으면' · §10-3 '축 공백도 경계').
    """
    if T < LB:
        return (
            M.DATA_SHORT,
            f"기준일까지 연구 축 날짜가 {LB + 1}일 미만입니다(60거래일 변화 계산 불가).",
        )
    reasons = series.window_reasons(T - LB, T)
    if not reasons:
        return None
    text = " · ".join(REASON_TEXT[r] for r in reasons)
    return (
        M.PRICE_BASIS_UNCONFIRMED,
        f"기준일 feature 창(60거래일)을 확정할 수 없음 — {text}",
    )


def evaluate(series: AxisSeries, t: str) -> dict[str, Any]:
    """선택 ETF 하나의 표본 · 검증 · 최종 추정. 쓰기 · 외부 조회 0."""
    dates = series.dates
    T = dates.index(t)
    c = series.closes
    out: dict[str, Any] = {"t": t, "recipe_version": RECIPE["version"]}

    t_problem = t_window_problem(series, T)
    if t_problem is None:
        out["features_at_t"] = dict(zip(FEATURE_NAMES, features_at(c, T)))
    else:
        out["features_at_t"] = None

    # 표본: 창 [i-60, i+20] 이 유효한 i(정답 끝 i+20 ≤ T)
    valid: list[int] = []
    excluded: dict[str, int] = {}
    for i in range(LB, T - H + 1):
        reason = series.window_reason(i - LB, i + H)
        if reason is None:
            valid.append(i)
        else:
            excluded[reason] = excluded.get(reason, 0) + 1
    xs = {i: features_at(c, i) for i in valid}
    ys = {i: target_at(c, i) for i in valid}
    out["samples"] = {"valid_n": len(valid), "excluded_by_reason": excluded}

    blocks, errs_m, errs_b, all_ok = _validate(dates, valid, xs, ys, T)
    out["blocks"] = blocks

    if t_problem is not None:
        out.update(status=t_problem[0], reason=t_problem[1])
        return out
    if not all_ok:
        out.update(
            status=M.DATA_SHORT,
            reason="세 검증 구간 중 학습 · 검증 자료가 부족한 구간이 있음",
        )
        return out

    mae_m = sum(errs_m) / len(errs_m)
    mae_b = sum(errs_b) / len(errs_b)
    v = verdict(mae_m, mae_b)
    out["overall"] = {
        "n": len(errs_m),
        "mae_model_pp": mae_m,
        "mae_baseline_pp": mae_b,
        "verdict": v,
        "verdict_text": M.VERDICT_TEXT[v],
    }
    matured = [i for i in valid if i + H <= T]
    pred = fit_predict(
        [xs[i] for i in matured], [ys[i] for i in matured], [features_at(c, T)]
    )
    out["final"] = {
        "train_n": len(matured),
        "train_first": dates[matured[0]],
        "train_last": dates[matured[-1]],
        "estimate_pct": pred[0] * 100.0,
        "baseline_median_pct": _median([ys[i] for i in matured]) * 100.0,
    }
    out.update(status=M.OK, reason=None)
    return out


def _validate(dates, valid, xs, ys, T):
    """세 구간 검증 → (구간 정보, 모델 오차, 기준 오차, 모두 됨). 오차는 같은 유효 날짜 · 같은 목표."""
    end = T - H
    first = end - N_VAL + 1
    if first < 0:
        return [], [], [], False
    valid_set = set(valid)
    blocks: list[dict[str, Any]] = []
    errs_m: list[float] = []
    errs_b: list[float] = []
    all_ok = True
    for b in range(3):
        idx = list(range(first + b * BLOCK, first + (b + 1) * BLOCK))
        start = idx[0]
        train = [i for i in valid if i + H < start]
        val = [i for i in idx if i in valid_set]
        info: dict[str, Any] = {
            "block": b + 1,
            "first_date": dates[idx[0]],
            "last_date": dates[idx[-1]],
            "axis_dates": len(idx),
            "train_n": len(train),
            "valid_n": len(val),
            "excluded_n": len(idx) - len(val),
        }
        if len(train) < MIN_TRAIN or not val:
            info["status"] = M.DATA_SHORT
            all_ok = False
            blocks.append(info)
            continue
        ty = [ys[i] for i in train]
        pred = fit_predict([xs[i] for i in train], ty, [xs[i] for i in val])
        base = _median(ty)
        err_m = [abs(p - ys[i]) * 100.0 for p, i in zip(pred, val)]
        err_b = [abs(base - ys[i]) * 100.0 for i in val]
        info.update(
            status=M.OK,
            train_last_eval_end=dates[train[-1] + H],
            baseline_median_pct=base * 100.0,
            mae_model_pp=sum(err_m) / len(err_m),
            mae_baseline_pp=sum(err_b) / len(err_b),
        )
        errs_m.extend(err_m)
        errs_b.extend(err_b)
        blocks.append(info)
    return blocks, errs_m, errs_b, all_ok
