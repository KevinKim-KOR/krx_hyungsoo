"""POC6-23 고정 입력 · 기대값(PLAN §1 실측) · 분기 학습 창 · recipe · 환경 · 잠금 검사 — 통합 설계 V1 개정 2 §4-3 · §5 · §6.

```text
기반     POC6-20 survey 그대로(H1 분모 · 시장 4열 · 공통 계획 주 · 평가 구간 · 모형 배정) — 같은 달력이면 PLAN 값과 같다
공통     공통 신호 = 시장 4열 정의 · 자격 20종 이상 · 참조 경로 시작 = 최초 공통 신호(2014-07-11)
창       분기 cutoff C = 분기 첫 거래일의 직전 거래일 · D ≥ 분기 시작일 5년 전 같은 날 · 위치(D) + 21 ≤ 위치(C) − 20
         · 창 상한(정답 전) = PLAN 표 · 실제 유효 D(KEEP 외 · 완전한 정답) ≥ 104 는 공식 실행에서만 확인
환경     SciPy 1.18.0 · HiGHS 1.12.0 · numpy 2.4.6 · BLAS/OpenMP 스레드 환경 변수 1 — 다르면 잠금 · 실행 거절
```
"""

from __future__ import annotations

import datetime as dt
import os
import platform
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from app.decision_learning import actions as A
from app.decision_learning import labels as LB
from app.decision_learning import learn as LN
from app.decision_learning import report as RP
from app.feature_gain import protocol as P8
from app.market_context_value import learner as L
from app.market_context_value import protocol as P20
from app.ml_evidence import store
from app.trend_switch import policy as TP
from app.trend_switch import protocol as P21
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR

PROTOCOL_ID = "poc6-23-v1"
SCHEMA = {
    "protocol": "poc6_23_protocol_v1",
    "run": "poc6_23_run_v1",
    "report": "poc6_23_report_v1",
}
ROOT = Path("state/ml/research/poc6_23")
INPUT = "M"
COLUMNS = tuple(L.COLUMNS[INPUT])
MATURE = 20  # 위치(T) ≤ 위치(C) − 20
TRAIN_YEARS = 5
MIN_DATES = 104
FITS_MAX = 70
KINDS = ("P", "S")
VERSIONS = {"scipy": "1.18.0", "highs": "1.12.0", "numpy": "2.4.6"}
THREAD_ENV = ("VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")
CODE_FILES = P21.CODE_FILES + (
    "app/decision_learning/__init__.py",
    "app/decision_learning/actions.py",
    "app/decision_learning/labels.py",
    "app/decision_learning/learn.py",
    "app/decision_learning/policy.py",
    "app/decision_learning/audit.py",
    "app/decision_learning/protocol.py",
    "app/decision_learning/report.py",
    "app/decision_learning/flow.py",
    "app/decision_learning/verify.py",
    "scripts/run_decision_learning.py",
)
_UPPER = (168, 181, 193, 207, 220, 233, 246, 247, 243, 244, 244, 248)
_UPPER += (247, 247, 248, 246, 247, 246, 247, 245, 243, 243, 243, 243)
_UPPER += (243, 239, 239, 243, 243, 243, 243, 243, 243, 243, 243)
_QIDS = [f"{y}Q{q}" for y in range(2018, 2027) for q in (1, 2, 3, 4)][:35]
# PLAN §1 실측(2026-11-05 · 읽기 전용) — prepare 가 같은 정의로 다시 세어 대조 · 다르면 CheckRequired
EXPECTED = {
    "axis": ["2014-01-02", "2026-09-21", 3122],
    "common": {"count": 619, "first": "2014-07-11", "last": "2026-09-18"},
    "val": P21.EXPECTED["val"],
    "test": P21.EXPECTED["test"],
    "sub_weeks": P21.EXPECTED["sub_weeks"],
    "quarters": 35,
    "train_upper": dict(zip(_QIDS, _UPPER)),
    "last_train": "2026-04-24",
    "label_end": "2026-05-28",
}
CheckRequired = D.CheckRequired
_sha = P20._sha
_KEEP20 = (
    "h1_base",
    "market_files",
    "defined_signals",
    "first_defined",
    "first_common",
    "undefined_after_first_common",
    "market_sha256",
    "sub_weeks",
    "assign",
)


def code_hashes(repo: Path) -> dict[str, str]:
    return {
        rel: store.sha256_bytes((Path(repo) / rel).read_bytes()) for rel in CODE_FILES
    }


def highs_version():
    try:
        from scipy.optimize._highspy import _core  # 판 기록만(설정 · 호출에 쓰지 않음)

        return _core._Highs().version()
    except Exception:  # noqa: BLE001 — 읽지 못하면 None(잠금 대조에서 다름으로 걸린다)
        return None


def runtime_env() -> dict[str, Any]:
    cfg = np.show_config(mode="dicts")["Build Dependencies"]["blas"]
    return {
        "python": platform.python_version(),
        "macos": platform.mac_ver()[0] or None,
        "scipy": scipy.__version__,
        "highs": highs_version(),
        "numpy": np.__version__,
        "blas": cfg.get("name"),
        "threads_env": {k: os.environ.get(k) for k in THREAD_ENV},
        "solver": {"method": LN.METHOD, "options": dict(LN.OPTIONS)},
    }


def env_problems(env: dict[str, Any]) -> list[str]:
    out = [f"{k} {env.get(k)} ≠ {v}" for k, v in VERSIONS.items() if env.get(k) != v]
    bad = [k for k, v in (env.get("threads_env") or {}).items() if v != "1"]
    if bad:
        out.append(f"스레드 환경 변수 1 아님: {bad}")
    return out


def val_books() -> list[tuple]:
    """선행 재생 = P/S/R/K 20bp."""
    return [(f"{k}_20", k, PR.BASE_COST) for k in ("P", "S", "R", "K")]


def test_books() -> list[tuple]:
    """주 평가 = P/S/R/K × 20bp · 40bp."""
    return [
        (f"{k}_{c}", k, cost)
        for c, cost in (("20", PR.BASE_COST), ("40", PR.ALT_COST))
        for k in ("P", "S", "R", "K")
    ]


def common_signals(el: D.Eligibility, mkt: dict) -> list[int]:
    return [
        i
        for i in el.sig
        if mkt[i]["values"] is not None and len(el.members[i]) >= D.MIN_ELIGIBLE
    ]


def windows(axis: list[str], common: list[int]) -> list[dict]:
    """분기 학습 창(정답 전 상한) — 선행 12 + 주 평가 23 분기."""
    out = []
    for c in F.quarter_cutoffs(axis, *PR.VAL_Q) + F.quarter_cutoffs(axis, *PR.TEST_Q):
        y, q = int(c["id"][:4]), int(c["id"][-1])
        lo = dt.date(y - TRAIN_YEARS, 3 * (q - 1) + 1, 1).isoformat()
        ds = [
            i
            for i in common
            if axis[i] >= lo and i + LB.T_LAG <= c["cutoff_idx"] - MATURE
        ]
        out.append(
            {
                "id": c["id"],
                "phase": "val" if (y, q) <= PR.VAL_Q[1] else "test",
                "cutoff": c["cutoff"],
                "lo": lo,
                "upper": len(ds),
                "first": axis[ds[0]] if ds else None,
                "last": axis[ds[-1]] if ds else None,
                "dates_sha256": _sha([axis[i] for i in ds]),
            }
        )
    return out


def survey(p: D.Panel, base: Path):
    """POC6-20 사실 → 공통 신호 · 분기 창 상한. 참조 경로 · 정답 · 점수 · 성과를 계산하지 않는다."""
    fx20, el, _count, _usable, mkt = P20.survey(p, base)
    common = common_signals(el, mkt)
    qs = windows(p.axis, common)
    pos = {d: k for k, d in enumerate(p.axis)}
    last = max((pos[q["last"]] for q in qs if q["last"]), default=None)
    end = None if last is None else last + LB.T_LAG
    fx = {k: fx20[k] for k in _KEEP20}
    for tag in ("val", "test"):
        w = fx20[tag]
        fx[tag] = {
            **w,
            "last_signal": w["plan_signals"][-1] if w["plan_signals"] else None,
        }
    fx.update(
        axis=[p.axis[0], p.axis[-1], len(p.axis)],
        common={
            "count": len(common),
            "first": p.axis[common[0]] if common else None,
            "last": p.axis[common[-1]] if common else None,
            "sha256": _sha([p.axis[i] for i in common]),
        },
        quarters=len(qs),
        train_upper={q["id"]: q["upper"] for q in qs},
        last_train=None if last is None else p.axis[last],
        label_end=p.axis[end] if end is not None and end < len(p.axis) else None,
        quarter_detail=qs,
        fits=len(KINDS) * len(qs),
    )
    short = []
    if (
        fx["val"]["weeks"] < PR.MIN_WEEKS["val"]
        or fx["test"]["weeks"] < PR.MIN_WEEKS["test"]
    ):
        short.append("평가 주 부족")
    if min(fx["sub_weeks"]) < PR.MIN_WEEKS["sub"]:
        short.append("보조 구간 주 부족")
    if any(q["upper"] < MIN_DATES for q in qs):
        short.append("분기 학습 창 상한 부족")
    if fx["label_end"] is None:
        short.append("정답 끝이 날짜 축 밖")
    if fx["fits"] > FITS_MAX:
        short.append("최대 fit 초과")
    fx["data_short"] = short
    return fx, el, mkt, common


def compare(fx: dict[str, Any]) -> list[str]:
    diffs = []
    for k, exp in EXPECTED.items():
        got = fx.get(k)
        if k in ("val", "test", "common"):
            got = {kk: (got or {}).get(kk) for kk in exp}
        if got != exp:
            diffs.append(f"{k}: PLAN {exp} · 실제 {got}")
    return diffs


def input_refs() -> dict[str, Any]:
    return P20.input_refs()


def recipe() -> dict[str, Any]:
    cols = list(COLUMNS)
    return {
        "h1": PR.recipe(),
        "market": P20.recipe()["market"],
        "columns": cols,
        "columns_sha256": _sha(cols),
        "reference": {
            "policy": "POC6-21 R0(강화 없음) · RET_120 상위 5 · log(1+RET_60) · h",
            "h": TP.H,
            "cost": PR.BASE_COST,
            "start": "최초 공통 신호 · 현금 100",
            "snapshot": "공통 신호일 _weekly 직전(그날 체결 · 평가 · 보호 뒤)",
        },
        "label": {
            "formula": "g = [NAV_T(a) − NAV_T(KEEP)] / NAV_D",
            "horizon": LB.HORIZON,
            "t_lag": LB.T_LAG,
            "branch": "E = D+2 · D+1 ~ T 체결 · 평가 · 보호만 · 새 통상 계획 없음",
            "exclude": ["NORMAL_PENDING", "NO_ACTION", "BRANCH_UNRESOLVED"],
        },
        "actions": {
            "kinds": list(A.KINDS),
            "max": 1 + A.SLOTS + A.SLOTS + A.SLOTS * PO.ENTRY_TOP,
            "slots": A.SLOTS,
            "share": A.SHARE,
            "budget_eps": A.EPS,
            "order": "통상 거래 수 → KEEP · SELL · BUY · SWITCH → 종목코드(매도 → 매수)",
            "pending": "매수 대기 또는 사유 EXIT 매도 → KEEP 만",
            "slot_rule": "5 − 보유 − 매수 대기 + 이번 매도 + 보유 중 살아 있는 보호 매도 ≥ 1",
            "budget_rule": "h + (1−c)s > 1e-9 · 보호 예정 대금 미포함 · c = 그 장부 비용",
        },
        "model": {
            "coefficients": 2 * A.WIDTH,
            "z": "[b·[1,u_매수] · s·[1,u_매도]]",
            "b": "min(0.2, h + (1−c)s)/(1+c)",
            "k": "c(b + s)",
            "q": "βᵀz − k/s_g",
            "l1": LN.L1,
            "sg_min": LN.SG_MIN,
            "standardize": "날짜 안 · 사이 동일 가중 μ · 모집단 분산 · 정상 결측 = 0 · 상수 열 = 0",
            "cost_40bp": "같은 β · μ · σ · s_g · 예산 조건 · b · z · k = c 0.004",
        },
        "train": {
            "years": TRAIN_YEARS,
            "mature": MATURE,
            "min_dates": MIN_DATES,
            "kinds": list(KINDS),
            "fits_max": FITS_MAX,
        },
        "solver": {
            "method": LN.METHOD,
            "options": dict(LN.OPTIONS),
            "tol": LN.TOL,
            "upper_tol": LN.UPPER_TOL,
            "versions": VERSIONS,
            "threads_env": list(THREAD_ENV),
        },
        "books": {"val": val_books(), "test": test_books()},
        "judge": RP.recipe(),
        "budget": {
            "wall_s": PR.BUDGET_S,
            "rss_bytes": PR.RSS_MAX,
            "threads_max": 4,
            "solver_threads": 1,
        },
    }


def lock_problems(lk: dict[str, Any]) -> list[str]:
    out = []
    if lk.get("schema") != SCHEMA["protocol"] or lk.get("protocol_id") != PROTOCOL_ID:
        out.append("잠금 식별자(schema · protocol_id) 다름")
    got = {k: (lk.get("inputs") or {}).get(k) for k in input_refs()}
    if store.canonical(got) != store.canonical(input_refs()):
        out.append("잠금 입력(판 · 파일 · 시장 사본 해시) ≠ 코드 고정값")
    norm = P8.loads(P8.dumps(recipe(), compact=True).decode())
    if store.canonical(lk.get("recipe")) != store.canonical(norm):
        diff = sorted(
            k
            for k in norm
            if store.canonical((lk.get("recipe") or {}).get(k))
            != store.canonical(norm[k])
        )
        out.append(f"잠금 recipe ≠ 지금 코드의 설정({', '.join(diff) or '키 구성'})")
    return out
