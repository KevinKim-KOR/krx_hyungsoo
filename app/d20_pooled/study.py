"""POC6-02 — 공동 학습 D20 비교(설계 개정 2 §4 ~ §7 · PLAN 판정 §1 · §2). 외부 조회 · 쓰기 · torch 0.

```text
표본    06 그대로 — 창 [i-60, i+20] 이 유효한 연구 축 위치 i(누락 · 허용 밖 출처 · 비정상 종가 · 경계 = 제외 · 사유 집계)
구간    anchor = 축 T-20 · 그 앞 189 축일을 63 씩 3구간 · 구간 시작 s 마다 학습 = 정답 끝(i+20) < s 인 표본만
        (모든 ETF 같은 축 경계 · 구간 안 재학습 · 무작위 분할 · early stopping 없음)
적격    ETF 마다 세 구간 모두 학습 ≥ 252 · 그 구간 유효 시험 날짜 ≥ 42 · 적격 ETF < 4 = DATA_SHORT
        (최초 5종 → 4종 = 설계자 PLAN 판정 Q1 (b) · 성과 미열람 · 잠금 전)
방법    MEDIAN · RIDGE_EXISTING = ETF 별 06 그대로(같은 비중) · POOLED_HGB = 적격 ETF 공동 · 가중 1/n_d ·
        POOLED_GPU_MLP = RTX PC 결과를 merge 때 같은 행에 붙임(맥북 단계 = GPU_NOT_RUN)
평가    같은 (ETF, 날짜) 행 · 예측 [-1, 0] · 날짜 균형 MAE(%p) = 날짜별 유효 ETF 평균 → 날짜 평균 · 반올림 전 판정
판정    후보마다 두 기준 각각: 전체 5% 이상 감소 · 3구간 중 2구간 이상 작음 · 어느 구간도 5% 넘게 커지지 않음
```
"""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Optional

from app.d20_pooled import mlp
from app.d20_pooled.snapshot import rows_of, snapshot_problem
from app.reentry_review import model as m06
from app.reentry_review import prices

H, LB, N_VAL, BLOCK, MIN_TRAIN = m06.H, m06.LB, m06.N_VAL, m06.BLOCK, m06.MIN_TRAIN
MIN_TEST = 42
MIN_ETFS = 4
MIN_ETFS_ORIGINAL = 5
IMPROVE = 0.05
WORSE_LIMIT = 0.05
WIN_BLOCKS = 2
NEAR_RATIO = 1e-6
NEAR_MAE_PP = 1e-9
DEEP_LOSS = -0.08

MEDIAN, RIDGE, HGB, GPU_MLP = "MEDIAN", "RIDGE_EXISTING", "POOLED_HGB", "POOLED_GPU_MLP"
BASELINES = (MEDIAN, RIDGE)
CANDIDATES = (HGB, GPU_MLP)
CPU_METHODS = (MEDIAN, RIDGE, HGB)

PROMISING, REJECT = "RESEARCH_PROMISING", "REJECT"
DATA_SHORT, GPU_NOT_RUN = "DATA_SHORT", "GPU_NOT_RUN"
CHECK_REQUIRED, RUN_FAILED, COMPLETED = "CHECK_REQUIRED", "RUN_FAILED", "COMPLETED"

HGB_PARAMS: dict[str, Any] = {
    "loss": "absolute_error",
    "learning_rate": 0.05,
    "max_iter": 100,
    "max_leaf_nodes": 7,
    "max_depth": 3,
    "min_samples_leaf": 50,
    "l2_regularization": 1.0,
    "max_bins": 63,
    "early_stopping": False,
    "categorical_features": None,
    "random_state": 42,
}

RECIPE: dict[str, Any] = {
    "version": "poc6_02.v1",
    "target": m06.RECIPE["target"],
    "features": m06.RECIPE["features"],
    "feature_names": list(m06.FEATURE_NAMES),
    "axis": "06 연구 축 · 공통 기준일 T = KOSPI 저장 최신일",
    "blocks": {
        "anchor": "axis T-20",
        "dates": N_VAL,
        "blocks": 3,
        "block": BLOCK,
        "train_rule": "label end (axis i+20) < block start s",
    },
    "eligibility": {
        "min_train_per_block": MIN_TRAIN,
        "min_test_dates_per_block": MIN_TEST,
        "min_etfs": MIN_ETFS,
        "min_etfs_original": MIN_ETFS_ORIGINAL,
        "min_etfs_change": (
            "설계자 PLAN 판정 2026-10-21 Q1 (b) — 성과 미열람 · 공식 잠금 전 · 최소 비교 범위 선택값 변경"
            "(통계적 충분성 기준 아님)"
        ),
        "test_dates_meaning": "ETF 마다 각 구간 유효 시험 날짜 ≥ 42(PLAN 판정 Q3)",
    },
    "methods": {
        MEDIAN: "ETF 별 학습 표본 D20 중앙값(짝수 = 가운데 둘 평균 · 06 median)",
        RIDGE: m06.RECIPE["model"] + " · ETF 별 · 06 fit_predict",
        HGB: {"model": "sklearn HistGradientBoostingRegressor", "params": HGB_PARAMS},
        GPU_MLP: {"model": "PyTorch MLP (RTX PC CUDA)", "spec": mlp.SPEC},
    },
    "weights": "공동 학습 = 학습 날짜 d 의 행마다 1/n_d · ETF 별 기준 = 같은 비중",
    "clip": [-1.0, 0.0],
    "metric": "date-balanced MAE %p (날짜별 유효 ETF 평균 → 날짜 평균)",
    "verdict": {
        "overall_improve_min": IMPROVE,
        "block_wins_min": WIN_BLOCKS,
        "block_worse_max": WORSE_LIMIT,
        "against": list(BASELINES),
        "base_zero": "REJECT",
        "rounding": "판정은 반올림 전 값",
        "near_boundary": {"ratio": NEAR_RATIO, "block_mae_pp": NEAR_MAE_PP},
    },
    "reproducibility": {
        "cpu_methods": "같은 장비 두 번 학습 예측 완전 같음",
        "mlp": f"같은 장비 두 번 학습 예측 최대 차 ≤ {mlp.REPRO_TOL}",
    },
    "deep_loss_threshold": DEEP_LOSS,
}


LOOKBACK_SHORT = (
    "LOOKBACK_SHORT"  # 축 시작 뒤 60거래일 전(feature 창 없음 · manifest 집계용)
)


def hgb_resolved_params() -> dict[str, Any]:
    """설치 버전의 HGB 전체 설정(고정 11개 + 나머지 기본값 · 설계 §5 '기본값을 recipe 에 남김')."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    got = HistGradientBoostingRegressor(**HGB_PARAMS).get_params()
    return {
        k: v if v is None or isinstance(v, (bool, int, float, str)) else repr(v)
        for k, v in sorted(got.items())
    }


class StudyError(Exception):
    """입력 · 계열 계약 위반(CHECK_REQUIRED)."""


def clip(v: float) -> float:
    return min(0.0, max(-1.0, float(v)))


# ── 표본 · 구간 · 적격 ──────────────────────────────────────────────────────────


def _breaks(rows: list[prices.PriceRow]) -> list[dict[str, Any]]:
    """06 경계 판정이 잡은 자리(사실) — 날짜 · 종류 · 앞뒤 행 출처 · 수집 시각."""
    out = []
    for prev, row in zip(rows, rows[1:]):
        kind = prices.link_break(prev, row)
        if kind:
            out.append(
                {
                    "date": row.date,
                    "kind": kind,
                    "prev_date": prev.date,
                    "prev_source": prev.source,
                    "source": row.source,
                    "prev_fetched_at": prev.fetched_at,
                    "fetched_at": row.fetched_at,
                }
            )
    return out


def prepare(snap: dict[str, Any]) -> dict[str, Any]:
    """snapshot → 축 · 구간 · ETF 별 표본 · 적격. 성과 계산 0."""
    bad = snapshot_problem(snap)  # 어느 경로로 오든 손상 입력은 계산 전에 거절
    if bad:
        raise StudyError(f"snapshot 계약 위반: {bad}")
    axis = snap["axis"]
    if axis.get("problem"):
        raise StudyError(f"연구 축 확정 불가: {axis['problem']}")
    dates = axis["dates"]
    if not dates or dates[-1] != snap["T"]:
        raise StudyError("연구 축 끝이 기준일 T 와 다름")
    last = len(dates) - 1
    first = last - H - N_VAL + 1
    blocks = (
        [list(range(first + b * BLOCK, first + (b + 1) * BLOCK)) for b in range(3)]
        if first >= 0  # 06 `_validate` 와 같음
        else []
    )
    etfs: dict[str, Any] = {}
    for t, entry in sorted(snap["etfs"].items()):
        rows = rows_of(entry)
        series = prices.AxisSeries(dates, rows)
        valid, excluded, reason_at = [], Counter(), {}
        for i in range(LB, last - H + 1):
            reason = series.window_reason(i - LB, i + H)
            if reason is None:
                valid.append(i)
            else:
                excluded[reason] += 1
                reason_at[i] = reason
        vset = set(valid)
        per_block = []
        for idx in blocks:
            s = idx[0]
            train = [i for i in valid if i + H < s]
            per_block.append(
                {
                    "train_n": len(train),
                    "test_dates": sum(1 for i in idx if i in vset),
                    # ETF × 구간 manifest(PLAN §3) — 학습 후보 · 시험 날짜의 제외 사유 수 · 마지막 학습 정답 끝일
                    "train_excluded_by_reason": dict(
                        Counter(
                            reason_at.get(i, LOOKBACK_SHORT)
                            for i in range(0, s - H)
                            if i not in vset
                        )
                    ),
                    "test_excluded_by_reason": dict(
                        Counter(
                            reason_at.get(i, LOOKBACK_SHORT)
                            for i in idx
                            if i not in vset
                        )
                    ),
                    "train_label_end": dates[train[-1] + H] if train else None,
                }
            )
        short = [
            f"{b + 1}구간 "
            + " · ".join(
                x
                for x in (
                    (
                        f"학습 {pb['train_n']} < {MIN_TRAIN}"
                        if pb["train_n"] < MIN_TRAIN
                        else ""
                    ),
                    (
                        f"시험 날짜 {pb['test_dates']} < {MIN_TEST}"
                        if pb["test_dates"] < MIN_TEST
                        else ""
                    ),
                )
                if x
            )
            for b, pb in enumerate(per_block)
            if pb["train_n"] < MIN_TRAIN or pb["test_dates"] < MIN_TEST
        ]
        etfs[t] = {
            "name": entry.get("name"),
            "rows_n": len(rows),
            "first": rows[0].date if rows else None,
            "last": rows[-1].date if rows else None,
            "applicable_now": bool(rows) and rows[-1].date >= snap["T"],
            "sources": dict(Counter(r.source for r in rows)),
            "valid_n": len(valid),
            "excluded_by_reason": dict(excluded),
            "blocks": per_block,
            "eligible": bool(blocks) and not short,
            "ineligible_reasons": (
                short if blocks else ["연구 축이 3구간 검증보다 짧음"]
            ),
            "breaks": _breaks(rows),
            "_closes": series.closes,
            "_valid": valid,
        }
    eligible = [t for t, e in etfs.items() if e["eligible"]]
    return {
        "dates": dates,
        "T": snap["T"],
        "blocks": blocks,
        "etfs": etfs,
        "eligible": eligible,
        "status": DATA_SHORT if len(eligible) < MIN_ETFS or not blocks else None,
    }


def block_sets(prep: dict[str, Any], b: int) -> dict[str, Any]:
    """구간 b 의 학습 · 시험 행(적격 ETF 만). 행 = (ticker, 축 위치)."""
    idx = prep["blocks"][b]
    s = idx[0]
    idx_set = set(idx)
    train: dict[str, list[int]] = {}
    test: list[tuple[str, int]] = []
    for t in prep["eligible"]:
        valid = prep["etfs"][t]["_valid"]
        train[t] = [i for i in valid if i + H < s]
        test += [(t, i) for i in valid if i in idx_set]
    test.sort(key=lambda r: (r[1], r[0]))
    pooled = [(t, i) for t in prep["eligible"] for i in train[t]]
    n_d = Counter(i for _, i in pooled)
    return {
        "start": s,
        "train": train,
        "pooled": pooled,
        "weights": [1.0 / n_d[i] for _, i in pooled],
        "test": test,
    }


def feats(prep: dict[str, Any], t: str, i: int) -> list[float]:
    return m06.features_at(prep["etfs"][t]["_closes"], i)


def target(prep: dict[str, Any], t: str, i: int) -> float:
    return m06.target_at(prep["etfs"][t]["_closes"], i)


def row_id(prep: dict[str, Any], t: str, i: int) -> str:
    return f"{t}|{prep['dates'][i]}"


# ── 세 CPU 방법 ───────────────────────────────────────────────────────────────


def predict_median(prep, bs) -> dict[str, float]:
    base = {
        t: m06.median([target(prep, t, i) for i in tr]) for t, tr in bs["train"].items()
    }
    return {row_id(prep, t, i): clip(base[t]) for t, i in bs["test"]}


def predict_ridge(prep, bs) -> dict[str, float]:
    out: dict[str, float] = {}
    for t, tr in bs["train"].items():
        rows = [(tt, i) for tt, i in bs["test"] if tt == t]
        pred = m06.fit_predict(
            [feats(prep, t, i) for i in tr],
            [target(prep, t, i) for i in tr],
            [feats(prep, t, i) for _, i in rows],
        )
        out.update({row_id(prep, t, i): clip(p) for (_, i), p in zip(rows, pred)})
    return out


def pooled_xyw(prep, bs) -> tuple[list[list[float]], list[float], list[float]]:
    X = [feats(prep, t, i) for t, i in bs["pooled"]]
    y = [target(prep, t, i) for t, i in bs["pooled"]]
    return X, y, list(bs["weights"])


def fit_hgb(X, y, w, threads: Optional[int] = None):
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=threads):
        model = HistGradientBoostingRegressor(**HGB_PARAMS)
        model.fit(
            np.asarray(X, dtype=float),
            np.asarray(y, dtype=float),
            sample_weight=np.asarray(w),
        )
    return model


def predict_hgb(prep, bs) -> dict[str, float]:
    import numpy as np

    X, y, w = pooled_xyw(prep, bs)
    model = fit_hgb(X, y, w)
    test_X = np.asarray([feats(prep, t, i) for t, i in bs["test"]], dtype=float)
    pred = model.predict(test_X)
    return {row_id(prep, t, i): clip(p) for (t, i), p in zip(bs["test"], pred)}


CPU_PREDICTORS: dict[str, Callable] = {
    MEDIAN: predict_median,
    RIDGE: predict_ridge,
    HGB: predict_hgb,
}


# ── 평가 · 판정 ───────────────────────────────────────────────────────────────


def date_balanced_mae(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    """rows = [{date, ticker, truth, preds{method}}]. 날짜별 평균 절대오차(%p) → 날짜 평균."""
    by_date: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(abs(r["preds"][method] - r["truth"]) * 100.0)
    per_date = [sum(v) / len(v) for v in by_date.values()]
    return {
        "mae_pp": sum(per_date) / len(per_date) if per_date else None,
        "dates": len(per_date),
        "rows": len(rows),
    }


def judge(cand: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """후보 c · 기준 b 의 세 조건(반올림 전 값). cand/base = {overall, blocks[3]} MAE %p."""
    b, c = base["overall"], cand["overall"]
    if b == 0:
        return {
            "pass": False,
            "reason": "기준 MAE 0 — 우위 판정 없음",
            "base_zero": True,
        }
    rel = (b - c) / b
    wins = sum(1 for cb, bb in zip(cand["blocks"], base["blocks"]) if cb < bb)
    worse_ok, near = [], []
    for k, (cb, bb) in enumerate(zip(cand["blocks"], base["blocks"])):
        worse_ok.append(cb <= bb * (1.0 + WORSE_LIMIT) if bb > 0 else cb <= 0)
        if abs(cb - bb) < NEAR_MAE_PP:
            near.append(f"{k + 1}구간 MAE 차 < {NEAR_MAE_PP}%p")
        if bb > 0 and abs(cb / bb - 1.0 - WORSE_LIMIT) < NEAR_RATIO:
            near.append(f"{k + 1}구간 악화 5% 경계")
    if abs(rel - IMPROVE) < NEAR_RATIO:
        near.append("전체 개선 5% 경계")
    conds = {
        "overall_improve": rel >= IMPROVE,
        "block_wins": wins >= WIN_BLOCKS,
        "no_block_worse_5pct": all(worse_ok),
    }
    return {
        "pass": all(conds.values()),
        "relative_improvement": rel,
        "block_wins": wins,
        "conditions": conds,
        "near_boundary": near,
    }


def method_scores(
    rows_by_block: list[list[dict[str, Any]]], method: str
) -> dict[str, Any]:
    allrows = [r for rows in rows_by_block for r in rows]
    blocks = [date_balanced_mae(rows, method) for rows in rows_by_block]
    overall = date_balanced_mae(allrows, method)
    return {
        "overall": overall["mae_pp"],
        "blocks": [x["mae_pp"] for x in blocks],
        "dates": overall["dates"],
        "rows": overall["rows"],
    }


def verdict_for(scores: dict[str, Any], cand: str) -> dict[str, Any]:
    per_base = {b: judge(scores[cand], scores[b]) for b in BASELINES}
    return {
        "verdict": PROMISING if all(j["pass"] for j in per_base.values()) else REJECT,
        "against": per_base,
    }


def diagnostics(rows_by_block, methods: tuple[str, ...]) -> dict[str, Any]:
    """보조 보고(설계 §7) — 깊은 하락 행 · 위험 과소 추정 · ETF 별 분포. 주 판정을 바꾸지 않는다."""
    allrows = [r for rows in rows_by_block for r in rows]
    deep = [r for r in allrows if r["truth"] <= DEEP_LOSS]
    deep_out: dict[str, Any] = {
        "threshold": DEEP_LOSS,
        "rows": len(deep),
        "dates": len({r["date"] for r in deep}),
    }
    for m in methods:
        if deep:
            deep_out[m] = {
                "mae_pp": sum(abs(r["preds"][m] - r["truth"]) for r in deep)
                * 100
                / len(deep),
                "under_pp": sum(max(r["preds"][m] - r["truth"], 0.0) for r in deep)
                * 100
                / len(deep),
            }
    per_etf: dict[str, Any] = {}
    for t in sorted({r["ticker"] for r in allrows}):
        rs = [r for r in allrows if r["ticker"] == t]
        per_etf[t] = {
            "rows": len(rs),
            "mae_pp": {
                m: sum(abs(r["preds"][m] - r["truth"]) for r in rs) * 100 / len(rs)
                for m in methods
            },
        }
    spread = {}
    for c in methods:
        if c not in CANDIDATES:
            continue
        spread[c] = {}
        for b in BASELINES:
            rel = [
                (e["mae_pp"][b] - e["mae_pp"][c]) / e["mae_pp"][b]
                for e in per_etf.values()
                if e["mae_pp"][b] > 0
            ]
            spread[c][b] = {
                "improved_etfs": sum(1 for x in rel if x > 0),
                "worse_etfs": sum(1 for x in rel if x < 0),
                "relative": rel,
            }
    return {"deep_loss": deep_out, "per_etf": per_etf, "per_etf_spread": spread}


# ── 실행(맥북 CPU 단계) ────────────────────────────────────────────────────────


def run_cpu(
    snap: dict[str, Any], *, smoke: bool = False, repeat_check: bool = True
) -> dict[str, Any]:
    """MEDIAN · RIDGE · HGB 공식 실행(smoke = 1구간만 · 지표 없음). GPU 후보 = GPU_NOT_RUN."""
    t0 = time.perf_counter()
    prep = prepare(snap)
    out: dict[str, Any] = {"prep": prep, "status": prep["status"], "blocks": []}
    if prep["status"] == DATA_SHORT:
        return {**out, "seconds": time.perf_counter() - t0}
    rows_by_block: list[list[dict[str, Any]]] = []
    repro_ok = True
    for b in range(1 if smoke else 3):
        bs = block_sets(prep, b)
        preds, timing = {}, {}
        for m, fn in CPU_PREDICTORS.items():
            s = time.perf_counter()
            preds[m] = fn(prep, bs)
            timing[m] = time.perf_counter() - s
            if repeat_check and fn(prep, bs) != preds[m]:
                repro_ok = False
        rows = []
        for t, i in bs["test"]:
            rid = row_id(prep, t, i)
            missing = [m for m in CPU_PREDICTORS if rid not in preds[m]]
            if missing:
                raise RuntimeError(f"예측 행 누락 {rid}: {missing}")
            rows.append(
                {
                    "id": rid,
                    "ticker": t,
                    "date": prep["dates"][i],
                    "truth": target(prep, t, i),
                    "preds": {m: preds[m][rid] for m in CPU_PREDICTORS},
                }
            )
        rows_by_block.append(rows)
        per_date = Counter(r["date"] for r in rows)
        out["blocks"].append(
            {
                "block": b + 1,
                "first_date": prep["dates"][prep["blocks"][b][0]],
                "last_date": prep["dates"][prep["blocks"][b][-1]],
                "start_index": bs["start"],
                "train_rows_pooled": len(bs["pooled"]),
                "train_rows_by_etf": {t: len(v) for t, v in bs["train"].items()},
                "train_label_end_max": prep["dates"][
                    max(i for _, i in bs["pooled"]) + H
                ],
                "label_before_start": max(i for _, i in bs["pooled"]) + H < bs["start"],
                "test_rows": len(rows),
                "test_dates": len(per_date),
                "etfs_per_date": {
                    "min": min(per_date.values()),
                    "max": max(per_date.values()),
                    # 날짜별 ETF 수 분포 {ETF 수: 날짜 수}
                    "dates_by_etf_count": {
                        str(k): v for k, v in sorted(Counter(per_date.values()).items())
                    },
                },
                "seconds": timing,
            }
        )
    out["rows_by_block"] = rows_by_block
    out["repro_cpu_identical"] = repro_ok
    if not repro_ok:
        out["status"] = CHECK_REQUIRED
        out["reason"] = "같은 장비 · 같은 입력의 두 학습 예측이 다름(재현 실패)"
    elif not smoke:
        scores = {m: method_scores(rows_by_block, m) for m in CPU_METHODS}
        out["scores"] = scores
        out["candidates"] = {
            HGB: verdict_for(scores, HGB),
            GPU_MLP: {"verdict": GPU_NOT_RUN, "reason": "RTX PC 실행 결과 취합 전"},
        }
        out["diagnostics"] = diagnostics(rows_by_block, CPU_METHODS)
        out["status"] = COMPLETED
    else:
        out["status"] = "SMOKE"
    out["seconds"] = time.perf_counter() - t0
    return out


def gpu_input(prep: dict[str, Any], *, smoke: bool = False) -> dict[str, Any]:
    """RTX PC 묶음 입력 — 구간별 학습 feature · 정답 · 가중치 · 표준화 값 · 시험 feature · 행 ID.

    각 구간이 예측하는 시험 행의 정답은 그 구간 학습에 없다. 앞 구간 시험 행의 정답은 뒤 구간 학습 정답으로
    들어간다(앞으로 굴려 가는 학습 · 누수 아님). 시험 정답 칸(truth)은 묶음에 없다.
    """
    blocks = []
    for b in range(1 if smoke else 3):
        bs = block_sets(prep, b)
        X, y, w = pooled_xyw(prep, bs)
        mean, std = mlp.standardize_params(X, w)
        blocks.append(
            {
                "block": b + 1,
                "train_X": X,
                "train_y": y,
                "train_w": w,
                "mean": mean,
                "std": std,
                "test_ids": [row_id(prep, t, i) for t, i in bs["test"]],
                "test_X": [feats(prep, t, i) for t, i in bs["test"]],
            }
        )
    return {"blocks": blocks, "feature_names": list(m06.FEATURE_NAMES)}


def merge_gpu(
    cpu_rows_by_block: list[list[dict[str, Any]]],
    gpu_blocks: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """GPU 예측을 같은 시험 행에 붙인다 — 구간 · 행 ID 순서 완전 일치 · 유한 값만(아니면 ValueError)."""
    if len(gpu_blocks) != len(cpu_rows_by_block):
        raise ValueError("구간 수가 다름")
    merged = []
    for rows, gb in zip(cpu_rows_by_block, gpu_blocks):
        ids = [r["id"] for r in rows]
        if gb.get("test_ids") != ids:
            raise ValueError(
                f"{gb.get('block')}구간 행 ID 가 맥북 시험 행과 다름(누락 · 중복 · 순서)"
            )
        preds = gb.get("pred")
        if not isinstance(preds, list) or len(preds) != len(ids):
            raise ValueError(f"{gb.get('block')}구간 예측 개수가 다름")
        for p in preds:
            if (
                not isinstance(p, (int, float))
                or isinstance(p, bool)
                or not math.isfinite(p)
            ):
                raise ValueError(f"{gb.get('block')}구간 예측에 수가 아닌 값")
        merged.append(
            [
                {**r, "preds": {**r["preds"], GPU_MLP: clip(p)}}
                for r, p in zip(rows, preds)
            ]
        )
    return merged
