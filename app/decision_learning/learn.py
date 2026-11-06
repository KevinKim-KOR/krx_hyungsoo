"""POC6-23 분기 표준화 · s_g · MAE(P) ↔ SPO+(S) 선형계획 · 수치 조건 — 통합 설계 V1 개정 2 §4 · 판정 A-2 · A-5 · A-6.

```text
표준화   분기 유효 학습 D 의 후보/보유 ETF(D · ETF 당 한 번) · 열마다 결측 아닌 ETF 날짜 안 동일 가중 → 관측 있는
         날짜 사이 동일 가중 μ · 같은 가중 (x−μ)² 평균 = 모집단 분산 · 관측 0 열 = CHECK_REQUIRED
         · 관측값이 모두 같은 열 = 상수(변환 0) · 그 밖 (x−μ)/σ 뒤 정상 결측(None) 칸만 0(학습 평균 위치)
s_g      날짜 사이 동일 가중 · 날짜 안 KEEP 외 행동 동일 가중 g 의 RMS 와 1e-6 중 큰 값
점수     κ_a = k_a/s_g · q_a = βᵀz_a − κ_a · y_a = g_a/s_g · KEEP 은 q = y = 0 · ‖β‖₁ ≤ 1(β = β⁺ − β⁻)
P        날짜별 KEEP 외 |q_a − y_a| 평균의 날짜 평균 — t 보조 변수 · 목적에 상수 없음 · LP_full = solver.fun
S        a* = argmax y(고정 순서 · KEEP 포함) · L = max_a(2q_a − y_a) − 2q_a* + y_a* 의 날짜 평균
         m_D ≥ 2q_a − y_a(KEEP = m_D ≥ 0) · 가변 목적 = 날짜 평균(m_D − 2βᵀz_a*)
         · C_fixed = 날짜 평균(2κ_a* + y_a*)
         → LP_full = solver.fun + C_fixed(상수는 목적에서 뺐으므로 한 번만 더함)
solver   새 프로세스 첫 호출부터 이 도우미 하나 · highs-ds · 기본 presolve · threads=1 · 기본값 대체 없음
         · 경고는 threads 옵션 전달 알림 한 종류만 골라 센다(나머지는 다시 낸다)
조건     상태 0 · L1 초과량 · 제약 위반 ≤ 1e-7 · abs(직접 전체 평균 손실 − LP_full) ≤ 1e-7 · SPO+ 상계 · 0 경계는 전체 손실로
```
"""

from __future__ import annotations

import math
import warnings
from typing import Any, Optional, Sequence

import numpy as np
from scipy.optimize import OptimizeWarning, linprog
from scipy.sparse import csr_matrix, hstack, identity, vstack

from app.decision_learning import actions as A
from app.weekly_selection import data as D

CheckRequired = D.CheckRequired
TOL = 1e-7
L1 = 1.0
SG_MIN = 1e-6
UPPER_TOL = 1e-9  # SPO+ ≥ 실제 선택 손실(정규화 문제의 부동소수 여유)
METHOD = "highs-ds"
OPTIONS = {"threads": 1}
NOTICE = "Unrecognized options detected: {'threads': 1}"
NB = 2 * A.WIDTH


# ── 표준화 · 결측 대치 ───────────────────────────────────────────────────────────


def column_stats(dates: Sequence[Sequence[Sequence[Optional[float]]]], names):
    """dates = 날짜마다 서로 다른 ETF 의 34열 원값 목록. (μ · σ · 상수 여부 · 열별 기록)."""
    mu, sd, const, info = [], [], [], []
    for c, col in enumerate(names):
        per = []
        cells = 0
        for rows in dates:
            cells += len(rows)
            v = [r[c] for r in rows if r[c] is not None]
            if any(not math.isfinite(x) for x in v):
                raise CheckRequired(f"{col} 비유한 원값")
            if v:
                per.append(v)
        obs = sum(len(v) for v in per)
        if not per:
            raise CheckRequired(f"{col} 유효 관측 0(분기 학습 자료)")
        flat = [x for v in per for x in v]
        same = max(flat) == min(flat)
        if same:
            m, s = flat[0], 0.0
        else:
            m = sum(sum(v) / len(v) for v in per) / len(per)
            var = sum(sum((x - m) ** 2 for x in v) / len(v) for v in per) / len(per)
            s = math.sqrt(var)
            if not s > 0:
                raise CheckRequired(f"{col} 표준편차 0 인데 관측값이 다름")
        mu.append(m)
        sd.append(s)
        const.append(same)
        info.append(
            {
                "column": col,
                "observed": obs,
                "missing": cells - obs,
                "dates": len(per),
                "constant": same,
            }
        )
    return mu, sd, const, info


def transform(raw: Sequence[Optional[float]], mu, sd, const) -> tuple[np.ndarray, int]:
    """(u · 정상 결측 대치 칸 수)."""
    u = np.zeros(A.NCOL)
    imputed = 0
    for c, x in enumerate(raw):
        if x is None:
            imputed += 1
            continue
        if not math.isfinite(x):
            raise CheckRequired("비유한 원값(정상 결측 아님)")
        if not const[c]:
            u[c] = (x - mu[c]) / sd[c]
    return u, imputed


def scale(g_by_date: Sequence[Sequence[float]]) -> float:
    """g_by_date = 날짜마다 KEEP 외 행동의 g."""
    ms = [sum(x * x for x in g) / len(g) for g in g_by_date]
    return max(math.sqrt(sum(ms) / len(ms)), SG_MIN)


# ── 학습 자료(분기) ──────────────────────────────────────────────────────────────


class Problem:
    """정규화된 학습 문제 — 행 = (날짜 · KEEP 외 행동) · 날짜 단위 a* · 가중치."""

    def __init__(self, dates: list[dict]):
        """dates[k] = {z: (n_k, 70) · kappa · y: (n_k,) · star: KEEP 포함 위치(0 = KEEP)}."""
        self.dates = dates
        self.Z = np.vstack([d["z"] for d in dates])
        self.kappa = np.concatenate([d["kappa"] for d in dates])
        self.y = np.concatenate([d["y"] for d in dates])
        self.date = np.concatenate(
            [np.full(len(d["y"]), k, dtype=int) for k, d in enumerate(dates)]
        )
        n = np.array([len(d["y"]) for d in dates], dtype=float)
        self.w = 1.0 / (len(dates) * n[self.date])


def _zstar(pb: Problem, k: int) -> tuple[np.ndarray, float, float]:
    d = pb.dates[k]
    if d["star"] == 0:
        return np.zeros(NB), 0.0, 0.0
    r = d["star"] - 1
    return d["z"][r], float(d["kappa"][r]), float(d["y"][r])


def direct_mae(pb: Problem, beta: np.ndarray) -> float:
    q = pb.Z @ beta - pb.kappa
    return float(np.sum(pb.w * np.abs(q - pb.y)))


def direct_spo(pb: Problem, beta: np.ndarray) -> tuple[float, float]:
    """(날짜 평균 SPO+ · 최소 여유 = min(L_D − 실제 선택 손실_D))."""
    total, margin = 0.0, math.inf
    for k, d in enumerate(pb.dates):
        q = np.concatenate([[0.0], d["z"] @ beta - d["kappa"]])
        y = np.concatenate([[0.0], d["y"]])
        v = 2.0 * q - y
        s = d["star"]
        loss = float(np.max(v) - v[s])
        pick = int(np.argmax(q))  # 같은 값이면 앞(고정 순서)
        regret = float(y[s] - y[pick])
        total += loss
        margin = min(margin, loss - regret)
    return total / len(pb.dates), margin


def solve(c, A_ub, b_ub) -> tuple[Any, int]:
    """유일한 linprog 호출 지점(threads=1 · 기본값 대체 없음)."""
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        res = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=(0, None),
            method=METHOD,
            options=dict(OPTIONS),
        )
    notices = 0
    for w in ws:
        if issubclass(w.category, OptimizeWarning) and str(w.message).startswith(
            NOTICE
        ):
            notices += 1
        else:
            warnings.warn_explicit(w.message, w.category, w.filename, w.lineno)
    return res, notices


def _l1() -> csr_matrix:
    return csr_matrix(np.ones((1, 2 * NB)))


def mae_lp(pb: Problem):
    n = len(pb.y)
    Zs = csr_matrix(pb.Z)
    eye = identity(n, format="csr")
    A_ub = vstack(
        [
            hstack([Zs, -Zs, -eye]),
            hstack([-Zs, Zs, -eye]),
            hstack([_l1(), csr_matrix((1, n))]),
        ]
    ).tocsr()
    b_ub = np.concatenate([pb.kappa + pb.y, -(pb.kappa + pb.y), [L1]])
    c = np.concatenate([np.zeros(2 * NB), pb.w])
    return c, A_ub, b_ub, 0.0


def spo_lp(pb: Problem):
    nd = len(pb.dates)
    Zs = csr_matrix(pb.Z)
    M = csr_matrix(
        (np.ones(len(pb.y)), (np.arange(len(pb.y)), pb.date)), shape=(len(pb.y), nd)
    )
    A_ub = vstack(
        [hstack([2.0 * Zs, -2.0 * Zs, -M]), hstack([_l1(), csr_matrix((1, nd))])]
    ).tocsr()
    b_ub = np.concatenate([2.0 * pb.kappa + pb.y, [L1]])
    zs = np.zeros(NB)
    fixed = 0.0
    for k in range(nd):
        z, kap, y = _zstar(pb, k)
        zs += z
        fixed += 2.0 * kap + y
    zs /= nd
    c = np.concatenate([-2.0 * zs, 2.0 * zs, np.full(nd, 1.0 / nd)])
    return c, A_ub, b_ub, fixed / nd


def fit(pb: Problem, kind: str) -> dict[str, Any]:
    """한 번 풀고 수치 조건을 잰다(조건 판정은 check). 결과 계수 · 해 그대로 보존."""
    lp = (mae_lp if kind == "P" else spo_lp)(pb)
    c, A_ub, b_ub, fixed = lp
    res, notices = solve(c, A_ub, b_ub)
    rec: dict[str, Any] = {
        "kind": kind,
        "status": int(res.status),
        "message": str(res.message),
        "nit": int(getattr(res, "nit", -1)),
        "notices": notices,
        "method": METHOD,
        "options": dict(OPTIONS),
    }
    if res.x is None:
        return {**rec, "x": None, "beta": None}
    x = np.asarray(res.x, dtype=float)
    beta = x[:NB] - x[NB : 2 * NB]  # noqa: E203
    rec.update(x=x.tolist(), beta=beta.tolist(), **measure(pb, kind, x, res.fun, lp))
    return rec


def measure(pb: Problem, kind: str, x, fun_raw, lp=None) -> dict[str, Any]:
    """저장 해로 다시 잴 수 있는 칸(verify 공용 · 재학습 없음)."""
    x = np.asarray(x, dtype=float)
    fun_raw = float(fun_raw)
    c, A_ub, b_ub, fixed = lp or (mae_lp if kind == "P" else spo_lp)(pb)
    beta = x[:NB] - x[NB : 2 * NB]  # noqa: E203
    out: dict[str, Any] = {
        "fun_raw": fun_raw,
        "c_fixed": fixed,
        "lp_full": fun_raw + fixed,
        "fun_recomputed": float(c @ x),
        "l1": float(np.sum(np.abs(beta))),
        "l1_excess": max(0.0, float(np.sum(np.abs(beta))) - L1),
        "max_violation": max(0.0, float(np.max(A_ub @ x - b_ub))),
        "bound_violation": max(0.0, float(-np.min(x))),
        "rows": int(len(pb.y)),
        "dates": len(pb.dates),
    }
    if kind == "P":
        out["direct"] = direct_mae(pb, beta)
    else:
        out["direct"], out["upper_margin"] = direct_spo(pb, beta)
    out["abs_diff"] = abs(out["direct"] - out["lp_full"])
    return out


def check(rec: dict[str, Any]) -> list[str]:
    """고정 수치 조건(판정 A-5) — 문제 목록(비면 통과)."""
    if rec.get("status") != 0 or rec.get("beta") is None:
        return [f"{rec['kind']} solver 비정상 종료(status {rec.get('status')})"]
    out = []
    for k in ("l1_excess", "max_violation", "bound_violation", "abs_diff"):
        if not rec[k] <= TOL:
            out.append(f"{rec['kind']} {k} {rec[k]:.3e} > {TOL}")
    if abs(rec["fun_recomputed"] - rec["fun_raw"]) > TOL:
        out.append(f"{rec['kind']} 목적값 재계산 ≠ solver.fun")
    if not rec["direct"] >= -TOL:
        out.append(f"{rec['kind']} 전체 손실 음수 {rec['direct']:.3e}")
    if rec["kind"] == "S" and not rec["upper_margin"] >= -UPPER_TOL:
        out.append(f"S SPO+ < 실제 선택 손실(여유 {rec['upper_margin']:.3e})")
    return out
