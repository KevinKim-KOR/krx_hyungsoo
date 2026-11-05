"""POC6-21 고정 입력 · 기대 분모(PLAN §2 · 판정 §3) · recipe · 잠금 검사 — 통합 설계 §3 ~ §7.

```text
기반     POC6-20 survey 그대로(H1 분모를 H1 PLAN 표와 대조 → 시장 4열 → 공통 계획 주 · 모델 배정)
절대     ETF 자체 정답 가용성(069500 미래 행 요구 없음)으로 날짜 사용 · 분기 학습 표본을 다시 센다
모수     ① S · S20 · D · S20∩D ② 시장 조건 적용 전(S20) / 후(S20∩D) 정답 행 · 날짜
         ③ 분기 학습 = S20∩D ∩ 사용 날짜 ∩ 성숙 ∩ 5년 창 ④ 정기 계획 주 = 실행일 구간 ∩ S20 ∩ D(정답 무관)
분모     잠금 기대값(EXPECTED)과 다르면 CheckRequired(prepare · run · verify) · 결과를 보고 주를 더하거나 빼지 않는다
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.feature_gain import protocol as P8
from app.market_context_value import learner as L
from app.market_context_value import protocol as P20
from app.ml_evidence import store
from app.trend_switch import labels as LB
from app.trend_switch import policy as TP
from app.trend_switch import report as RP
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR

PROTOCOL_ID = "poc6-21-v1"
SCHEMA = {
    "protocol": "poc6_21_protocol_v1",
    "run": "poc6_21_run_v1",
    "report": "poc6_21_report_v1",
}
ROOT = Path("state/ml/research/poc6_21")
INPUT = "M"
CURVES = ("R0", "R1", "M0", "M1")
FITS_MAX = 35
CODE_FILES = P20.CODE_FILES + (
    "app/trend_switch/__init__.py",
    "app/trend_switch/labels.py",
    "app/trend_switch/policy.py",
    "app/trend_switch/audit.py",
    "app/trend_switch/trades.py",
    "app/trend_switch/protocol.py",
    "app/trend_switch/report.py",
    "app/trend_switch/study.py",
    "app/trend_switch/flow.py",
    "app/trend_switch/evidence.py",
    "app/trend_switch/verify.py",
    "scripts/run_trend_switch.py",
)
_UNDEF_20 = [
    "2015-08-28",
    "2015-09-04",
    "2015-09-11",
    "2015-09-18",
    "2019-08-23",
    "2019-08-30",
    "2019-09-06",
    "2019-09-11",
    "2022-07-22",
    "2022-07-29",
    "2022-08-05",
    "2022-08-12",
    "2022-08-19",
    "2023-12-22",
    "2023-12-28",
    "2024-01-05",
    "2024-01-12",
]
_UNUSABLE = ["2015-12-11", "2016-01-29"]
# PLAN §2 표(판정 §3 보완 반영 · prepare 가 같은 정의로 다시 세어 대조 · 다르면 CheckRequired)
EXPECTED = {
    "populations": {
        "signals": 663,
        "signals_20": 636,
        "defined": 627,
        "signals_20_defined": 619,
        "undefined_20": _UNDEF_20,
        "defined_lt20": 8,
    },
    "labels": {
        "s20": {
            "rows": 113269,
            "usable": 621,
            "unusable_matured": _UNUSABLE,
            "immature": 13,
        },
        "s20_defined": {
            "rows": 110809,
            "usable": 604,
            "unusable_matured": _UNUSABLE,
            "immature": 13,
        },
        "rows_h1_s20": 113269,
        "usable_differs_h1": [],
    },
    "val": {
        **{k: P20.EXPECTED["val"][k] for k in P20.EXPECTED["val"]},
        "last_signal": "2020-12-24",
    },
    "test": {
        **{k: P20.EXPECTED["test"][k] for k in P20.EXPECTED["test"]},
        "last_signal": "2026-09-11",
    },
    "sub_weeks": [99, 100, 90],
    "quarters": 35,
    "train_min_weeks": 161,
    "train_min_rows": 7427,
    "train_max_rows": 72418,
    "fits": 35,
    "quarter_spot": P20.EXPECTED["quarter_spot"],
}
CheckRequired = D.CheckRequired
_sha = P20._sha
_KEEP = (
    "h1_base",
    "market_files",
    "defined_signals",
    "first_defined",
    "first_common",
    "undefined_unique",
    "undefined_occurrences",
    "undefined",
    "undefined_after_first_common",
    "zero_abs_windows",
    "macro_calendar_days",
    "market_sha256",
    "sub_weeks",
    "assign",
)


def code_hashes(repo: Path) -> dict[str, str]:
    return {
        rel: store.sha256_bytes((Path(repo) / rel).read_bytes()) for rel in CODE_FILES
    }


def val_books() -> list[tuple]:
    """선행 재생 = R0/R1/M0/M1/K 20bp(판정 Q6)."""
    return [(f"{k}_20", k if k != "K" else None, PR.BASE_COST) for k in (*CURVES, "K")]


def test_books() -> list[tuple]:
    """주 평가 = R0/R1/M0/M1/K × 20bp · 40bp(필수 10개)."""
    return [
        (f"{k}_{c}", k if k != "K" else None, cost)
        for c, cost in (("20", PR.BASE_COST), ("40", PR.ALT_COST))
        for k in (*CURVES, "K")
    ]


def model_ids(assign: dict[str, str]) -> dict[str, str]:
    return {d: f"{q}_{INPUT}" for d, q in assign.items()}


def _split(p: D.Panel, group: list[int], count, usable) -> dict[str, Any]:
    last = F.EXEC_LAG + F.HORIZON - 1
    n = len(p.axis)
    return {
        "rows": sum(count[i] for i in group),
        "usable": sum(1 for i in group if usable[i]),
        "unusable_matured": [
            p.axis[i] for i in group if i + last < n and not usable[i]
        ],
        "immature": sum(1 for i in group if i + last >= n),
    }


def survey(p: D.Panel, base: Path):
    """POC6-20 사실 → 절대 정답 가용성 → 네 모수. 정답 크기 · 특징 값 · 순위 · 성과를 계산하지 않는다."""
    fx20, el, count_h1, usable_h1, mkt = P20.survey(p, base)
    sig, members = el.sig, el.members
    count, usable = LB.availability(p, {i: members[i] for i in sig})
    defined = {i for i in sig if mkt[i]["values"] is not None}
    s20 = [i for i in sig if len(members[i]) >= D.MIN_ELIGIBLE]
    both = [i for i in s20 if i in defined]
    vq = P20._quarters(p, members, count, usable, defined, PR.VAL_Q)
    tq = P20._quarters(p, members, count, usable, defined, PR.TEST_Q)
    qs = vq + tq
    fx = {k: fx20[k] for k in _KEEP}
    for tag in ("val", "test"):
        w = fx20[tag]
        fx[tag] = {
            **w,
            "last_signal": w["plan_signals"][-1] if w["plan_signals"] else None,
        }
    fx.update(
        populations={
            "signals": len(sig),
            "signals_20": len(s20),
            "defined": len(defined),
            "signals_20_defined": len(both),
            "undefined_20": [p.axis[i] for i in s20 if i not in defined],
            "defined_lt20": len(defined - set(s20)),
        },
        labels={
            "s20": _split(p, s20, count, usable),
            "s20_defined": _split(p, both, count, usable),
            "rows_h1_s20": sum(count_h1[i] for i in s20),
            "usable_differs_h1": [p.axis[i] for i in s20 if usable[i] != usable_h1[i]],
        },
        abs_sha256=_sha({p.axis[i]: [count[i], usable[i]] for i in sig}),
        quarters=len(qs),
        train_min_weeks=min(q["weeks"] for q in qs),
        train_min_rows=min(q["rows"] for q in qs),
        train_max_rows=max(q["rows"] for q in qs),
        fits=len(qs),
        quarter_spot={
            q["id"]: [q["cutoff"], q["weeks"], q["rows"], q["first"], q["last"]]
            for q in qs
            if q["id"] in EXPECTED.get("quarter_spot", {})
        },
        quarter_detail={"val": vq, "test": tq},
    )
    short = []
    if (
        fx["val"]["weeks"] < PR.MIN_WEEKS["val"]
        or fx["test"]["weeks"] < PR.MIN_WEEKS["test"]
    ):
        short.append("평가 주 부족")
    if min(fx["sub_weeks"]) < PR.MIN_WEEKS["sub"]:
        short.append("보조 구간 주 부족")
    if (
        fx["train_min_weeks"] < PR.MIN_TRAIN_WEEKS
        or fx["train_min_rows"] < PR.MIN_TRAIN_ROWS
    ):
        short.append("분기 학습 표본 부족")
    if fx["fits"] > FITS_MAX:
        short.append("최대 fit 초과")
    fx["data_short"] = short
    return fx, el, count, usable, mkt


def compare(fx: dict[str, Any]) -> list[str]:
    diffs = []
    for k, exp in EXPECTED.items():
        got = fx.get(k)
        if k in ("val", "test"):
            got = {kk: (got or {}).get(kk) for kk in exp}
        if got != exp:
            diffs.append(f"{k}: PLAN {exp} · 실제 {got}")
    return diffs


def input_refs() -> dict[str, Any]:
    return P20.input_refs()


def recipe() -> dict[str, Any]:
    cols = list(L.COLUMNS[INPUT])
    return {
        "h1": PR.recipe(),
        "market": P20.recipe()["market"],
        "struct": L.STRUCT,
        "input": INPUT,
        "columns": cols,
        "columns_sha256": _sha(cols),
        "target": {
            "formula": "log(I[E+59] / O*[E]) · E = 신호 + 2거래일(E 를 첫째로 셈)",
            "exec_lag": F.EXEC_LAG,
            "horizon": F.HORIZON,
            "bench_rows_required": False,
            "rank_or_center": False,
        },
        "label_rule": {
            "min_eligible": D.MIN_ELIGIBLE,
            "usable_min": F.USABLE_MIN,
            "usable_share": F.USABLE_SHARE,
            "train_years": F.TRAIN_YEARS,
            "mature_gap": F.MATURE_GAP,
            "min_train_weeks": PR.MIN_TRAIN_WEEKS,
            "min_train_rows": PR.MIN_TRAIN_ROWS,
        },
        "score_R": "log(1 + RET_60) = log(I_t / I_(t−60))",
        "candidates": {
            "column": "RET_120",
            "top": TP.CAND_TOP,
            "tie": "종목코드 오름차순",
        },
        "threshold": {
            "h": TP.H,
            "strong": TP.STRONG,
            "recent_days": TP.RECENT_DAYS,
            "same_for_all_costs": True,
            "recent_basis": "판단일 축 위치 − 실제 체결일 축 위치(재진입 = 마지막 전량 매도 · 재이탈 = 지금 보유 진입)",
        },
        "policy": {
            "slots": PO.SLOTS,
            "first_plan_entries": PO.SLOTS,
            "weekly_entries": 1,
            "weekly_exits": 1,
            "exit_pick": "점수가 가장 낮은 1개 · 동점 = 종목코드",
            "budget_share": PO.BUDGET_SHARE,
            "protect": PO.PROTECT,
            "protect_overlap": "살아 있는 통상 이탈이 보호 조건이 되면 한 건 · 사유 PROTECT",
            "start_value": PO.START_VALUE,
            "not_used": ["KEEP_RANK", "SMA60", "COOLDOWN_REVIEWS"],
            "held_not_eligible": "통상 판단 보류 · 보유 평가 · 일별 보호 계속(자동 매도 없음)",
        },
        "common_rule": "4열 정의 · 자격 20종 이상 신호만 정기 계획 · 학습 날짜(그 밖의 주 = 통상 판단 없음)",
        "books": {"val": val_books(), "test": test_books()},
        "judge": {
            "gap_min": RP.GAP_MIN,
            "sub_win_min": RP.SUB_WIN_MIN,
            "mdd_limit": RP.MDD_LIMIT,
            "turnover_max": RP.TURNOVER_MAX,
        },
        "bootstrap": {
            "pair": "M1_20 − R1_20 · 평가 구간 완전한 주 전체",
            **RP.BOOTSTRAP,
        },
        "budget": {
            "fits_max": FITS_MAX,
            "wall_s": PR.BUDGET_S,
            "rss_bytes": PR.RSS_MAX,
            "threads": M.THREADS,
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
