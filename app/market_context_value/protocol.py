"""POC6-20 고정 입력 · 기대 분모(PLAN §2 · 판정 §5) · recipe · 잠금 검사 — 설계 §2 ~ §7 · PLAN §5.

```text
기반     H1 survey 를 그대로 다시 세어 H1 PLAN 표와 같은 판인지 먼저 확인(공통 조건 전 분모)
공통     4열이 모두 정의된 주간 신호만 P/M/B 의 정기 계획 · 학습 날짜(자격 20종 이상 · H1 규칙 그대로)
         순위 없는 주 = 새 순위 · 편입 · 통상 교체 없음 · 보유 · 일별 보호 · 재진입 대기 셈은 모든 주간 신호로 계속
분모     잠금 기대값(EXPECTED)과 다르면 CheckRequired(prepare · run · verify) · 결과를 보고 주를 더하거나 빼지 않는다
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.feature_gain import protocol as P8
from app.market_context_value import learner as L
from app.market_context_value import market_inputs as MI
from app.market_context_value import report as RP
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import protocol as PR

PROTOCOL_ID = "poc6-20-v1"
SCHEMA = {
    "protocol": "poc6_20_protocol_v1",
    "run": "poc6_20_run_v1",
    "report": "poc6_20_report_v1",
}
ROOT = Path("state/ml/research/poc6_20")
CODE_FILES = PR.CODE_FILES + (
    "app/market_context_value/__init__.py",
    "app/market_context_value/market_inputs.py",
    "app/market_context_value/learner.py",
    "app/market_context_value/protocol.py",
    "app/market_context_value/report.py",
    "app/market_context_value/flow.py",
    "app/market_context_value/study.py",
    "app/market_context_value/evidence.py",
    "app/market_context_value/verify.py",
    "scripts/run_market_context_value.py",
)
_LOST_VAL = ["2019-08-23", "2019-08-30", "2019-09-06", "2019-09-11"]
_LOST_TEST = [
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
_FAILED_AFTER = {
    **{
        d: "2015-08-26"
        for d in ("2015-08-28", "2015-09-04", "2015-09-11", "2015-09-18")
    },
    **{d: "2019-08-20" for d in _LOST_VAL},
    **{d: "2022-07-21" for d in _LOST_TEST[:5]},
    **{d: "2023-12-18" for d in _LOST_TEST[5:]},
}
# PLAN §2 표(판정 §5 수용 · prepare 가 다시 세어 대조 · 다르면 CheckRequired)
EXPECTED = {
    "defined_signals": 627,
    "first_defined": "2014-05-16",
    "first_common": "2014-07-11",
    "undefined_unique": 36,
    "undefined_occurrences": 46,
    "undefined_after_first_common": {
        d: [f"FLOW_FAILED {f}"] for d, f in sorted(_FAILED_AFTER.items())
    },
    "zero_abs_windows": 0,
    "val": {
        "start": "2018-01-02",
        "end": "2020-12-30",
        "weeks": 153,
        "first_signal": "2017-12-28",
        "k_exec": "2018-01-03",
        "lost": _LOST_VAL,
    },
    "test": {
        "start": "2021-01-04",
        "end": "2026-09-21",
        "weeks": 289,
        "first_signal": "2020-12-30",
        "k_exec": "2021-01-05",
        "lost": _LOST_TEST,
    },
    "sub_weeks": [99, 100, 90],
    "quarters": 35,
    "train_min_weeks": 161,
    "train_min_rows": 7427,
    "train_max_rows": 72418,
    "fits": 70,
    "quarter_spot": {
        "2018Q1": ["2017-12-28", 161, 7427, "2014-07-11", "2017-09-15"],
        "2020Q4": ["2020-09-29", 241, 19574, "2015-10-02", "2020-06-26"],
        "2021Q1": ["2020-12-30", 240, 20659, "2016-01-08", "2020-09-18"],
        "2026Q3": ["2026-06-30", 238, 72418, "2021-07-02", "2026-03-20"],
    },
}
CheckRequired = D.CheckRequired


def _sha(obj: Any) -> str:
    return store.sha256_bytes(store.canonical(obj))


def code_hashes(repo: Path) -> dict[str, str]:
    return {
        rel: store.sha256_bytes((Path(repo) / rel).read_bytes()) for rel in CODE_FILES
    }


def val_books() -> list[tuple]:
    """선행 재생 = P/M/B/K 20bp(판정 §3 Q3)."""
    return [(f"{k}_20", k if k != "K" else None, PR.BASE_COST) for k in "PMBK"]


def test_books() -> list[tuple]:
    """주 평가 = P/M/B/K × 20bp · 40bp(필수 8개)."""
    return [
        (f"{k}_{c}", k if k != "K" else None, cost)
        for c, cost in (("20", PR.BASE_COST), ("40", PR.ALT_COST))
        for k in "PMBK"
    ]


def model_ids(assign: dict[str, str], inp: str) -> dict[str, str]:
    return {d: f"{q}_{inp}" for d, q in assign.items()}


def _window(p, sig, cnt, defined, lo: str, hi: str) -> dict[str, Any]:
    start, end = D.first_trading(p.axis, lo), D.last_trading(p.axis, hi)
    by_exec = [i for i in sig if start <= i + F.EXEC_LAG <= end]
    h1 = [i for i in by_exec if cnt[i] >= D.MIN_ELIGIBLE]
    plan = [i for i in h1 if i in defined]
    return {
        "start": p.axis[start],
        "end": p.axis[end],
        "weeks": len(plan),
        "h1_weeks": len(h1),
        "first_signal": p.axis[plan[0]] if plan else None,
        "k_exec": p.axis[plan[0] + F.EXEC_LAG] if plan else None,
        "lost": [p.axis[i] for i in h1 if i not in defined],
        "plan_signals": [p.axis[i] for i in plan],
    }


def _quarters(p, members, count, usable, defined, rng) -> list[dict]:
    out = []
    for c in F.quarter_cutoffs(p.axis, *rng):
        h1 = F.quarter_rows(p.axis, members, count, usable, c["cutoff_idx"])
        sigs = [i for i in h1 if i in defined]
        out.append(
            {
                "id": c["id"],
                "cutoff": c["cutoff"],
                "weeks": len(sigs),
                "rows": sum(count[i] for i in sigs),
                "h1_weeks": len(h1),
                "h1_rows": sum(count[i] for i in h1),
                "first": p.axis[sigs[0]] if sigs else None,
                "last": p.axis[sigs[-1]] if sigs else None,
                "signals_sha256": _sha([p.axis[i] for i in sigs]),
            }
        )
    return out


def survey(p: D.Panel, base: Path):
    """H1 분모(그대로) → 시장 4열 → 공통 조건 분모. 정답 크기 · 특징 값 · 순위 · 성과를 계산하지 않는다."""
    fx0, el, count, usable = PR.survey(p)
    h1 = PR.compare(fx0)
    if h1:
        raise CheckRequired(
            "H1 분모(공통 조건 전)가 H1 PLAN 표와 다름: " + " · ".join(h1)[:800]
        )
    src = MI.load_sources(base)
    sig = el.sig
    mkt = MI.build(p.axis, sig, src)
    defined = {i for i in sig if mkt[i]["values"] is not None}
    cnt = {i: len(el.members[i]) for i in sig}
    val = _window(p, sig, cnt, defined, *PR.VAL_RANGE)
    test = _window(p, sig, cnt, defined, *PR.TEST_RANGE)
    subs = [_window(p, sig, cnt, defined, lo, hi)["weeks"] for lo, hi in PR.SUB_RANGES]
    vq = _quarters(p, el.members, count, usable, defined, PR.VAL_Q)
    tq = _quarters(p, el.members, count, usable, defined, PR.TEST_Q)
    cuts = F.quarter_cutoffs(p.axis, *PR.VAL_Q) + F.quarter_cutoffs(p.axis, *PR.TEST_Q)
    assign = {}
    for tag, w, ids in (
        ("val", val, {q["id"] for q in vq}),
        ("test", test, {q["id"] for q in tq}),
    ):
        for d in w["plan_signals"]:
            m = F.model_for(p.axis.index(d), cuts)
            if m is None or m["id"] not in ids:
                raise CheckRequired(
                    f"{tag} 신호 {d} 의 모델 배정 이상: {m and m['id']}"
                )
            assign[d] = m["id"]
    undefined = {p.axis[i]: mkt[i]["reasons"] for i in sig if i not in defined}
    common = [i for i in sig if i in defined and cnt[i] >= D.MIN_ELIGIBLE]
    first_common = p.axis[common[0]] if common else None
    span = {
        col: sorted(mkt[i]["evidence"][col]["calendar_days"] for i in sorted(defined))
        for col in ("USDKRW_CHG_20", "WTI_DIFF_20")
    }
    qs = vq + tq
    fx = {
        "h1_base": {
            k: fx0[k]
            for k in (
                "member_dates",
                "file_sha256",
                "content_sha256",
                "signals",
                "first_signal",
                "last_signal",
                "eligible_rows",
                "label_rows",
                "signals_20",
                "usable_dates",
                "members_sha256",
                "usable_sha256",
            )
        },
        "market_files": src.files,
        "defined_signals": len(defined),
        "first_defined": p.axis[min(defined)] if defined else None,
        "first_common": first_common,
        "undefined_unique": len(undefined),
        "undefined_occurrences": sum(len(v) for v in undefined.values()),
        "undefined": undefined,
        "undefined_after_first_common": {
            d: rs for d, rs in undefined.items() if first_common and d > first_common
        },
        "zero_abs_windows": sum(
            1
            for i in defined
            for inv in MI.FLOW_INVESTOR.values()
            if mkt[i]["evidence"]["flow"][inv]["all_zero"]
        ),
        "macro_calendar_days": {
            k: [v[0], v[len(v) // 2], v[-1]] if v else None for k, v in span.items()
        },
        "market_sha256": _sha({p.axis[i]: mkt[i]["values"] for i in sig}),
        "val": val,
        "test": test,
        "sub_weeks": subs,
        "quarters": len(qs),
        "train_min_weeks": min(q["weeks"] for q in qs),
        "train_min_rows": min(q["rows"] for q in qs),
        "train_max_rows": max(q["rows"] for q in qs),
        "fits": len(L.INPUTS) * len(qs),
        "quarter_spot": {
            q["id"]: [q["cutoff"], q["weeks"], q["rows"], q["first"], q["last"]]
            for q in qs
            if q["id"] in EXPECTED.get("quarter_spot", {})
        },
        "quarter_detail": {"val": vq, "test": tq},
        "assign": assign,
    }
    short = []
    if val["weeks"] < PR.MIN_WEEKS["val"] or test["weeks"] < PR.MIN_WEEKS["test"]:
        short.append("평가 주 부족")
    if min(subs) < PR.MIN_WEEKS["sub"]:
        short.append("보조 구간 주 부족")
    if (
        fx["train_min_weeks"] < PR.MIN_TRAIN_WEEKS
        or fx["train_min_rows"] < PR.MIN_TRAIN_ROWS
    ):
        short.append("분기 학습 표본 부족")
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
    return {**PR.input_refs(), "market_files": dict(MI.SHA)}


def recipe() -> dict[str, Any]:
    return {
        "h1": PR.recipe(),
        "struct": L.STRUCT,
        "inputs": {k: list(v) for k, v in L.COLUMNS.items()},
        "inputs_sha256": {k: _sha(list(v)) for k, v in L.COLUMNS.items()},
        "market": {
            "flow_run": MI.FLOW_RUN,
            "macro_run": MI.MACRO_RUN,
            "files": dict(MI.SHA),
            "flow_investors": MI.FLOW_INVESTOR,
            "macro_series": MI.MACRO_SERIES,
            "flow_window": MI.FLOW_WIN,
            "macro_gap": MI.MACRO_GAP,
            "deadline": "신호일 23:59:59 KST",
            "flow_available": f"관측일 다음 축 거래일 {MI.FLOW_HOUR}:00 KST",
            "macro_available": f"원천 시간대 관측일 + {MI.MACRO_LAG_DAYS}달력일 00:00 → KST",
            "calendar": "봉인 판 069500 날짜 축",
        },
        "common_rule": "4열 모두 정의된 신호만 P/M/B 정기 계획 · 학습 날짜 · reviews = 모든 주간 신호",
        "baseline": {"B": "MOM120 = RET_120 고정", "K": "069500 보유"},
        "books": {"val": val_books(), "test": test_books()},
        "judge": {
            "gap_min": RP.GAP_MIN,
            "sub_win_min": RP.SUB_WIN_MIN,
            "mdd_limit": RP.MDD_LIMIT,
            "turnover_max": RP.TURNOVER_MAX,
        },
        "bootstrap": {"pair": "M_20 − P_20 · 평가 구간 완전한 주 전체", **RP.BOOTSTRAP},
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
