"""POC6-21 학습 · 계획 · 장부 · 쌍 bootstrap 도우미(flow · verify 공용) — PLAN §3 · 판정 §4.

```text
표       H1 build_table(자격 20종 이상 신호의 30열) + 절대 정답(labels.table)
행       H1 학습 행 규칙(5달력년 · 성숙 + 5거래일 · 사용 가능 날짜 · 정답 있음) 중 공통 날짜만 · 잠금 분기와 대조
모델     분기마다 M 1개 `<분기>_M`(34열 · ML_B) — POC6-20 fit 그대로(저장 → 열 이름 → 매개변수 → 복원 예측 1e-12)
계획     R = log(1 + RET_60) · M = 저장 예측 · 후보 = RET_120 상위 5(동점 = 종목코드) · 자격 밖 사유 = 자격 판정 그대로
장부     R0 · M0 = 강화 없음 · R1 · M1 = 최근 10거래일 2h · K = H1 simulate_bench
```
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.feature_gain import protocol as P8
from app.market_context_value import study as S20
from app.trend_switch import labels as LB
from app.trend_switch import policy as TP
from app.trend_switch import protocol as P21
from app.trend_switch import trades as TR
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import CheckRequired

VAL_STOP = "선행 재생 장부 평가 미확정 {bad} — 주 평가 미실행(판정 Q6)"
TEST_STOP = "주 평가 장부 평가 미확정 {bad} — 판정 NOT_JUDGED(설계 §6)"
FINAL_KEYS = (
    "judgment",
    "bootstrap",
    "bootstrap_tail_excluded",
)  # 정상 완료에만 있는 보고 칸
coverage = S20.coverage
window = S20.window
after_end = S20.after_end
gz = S20.gz


def abs_table(p: D.Panel, el: D.Eligibility) -> F.Table:
    t = F.build_table(
        p, {i: el.members[i] for i in el.sig if len(el.members[i]) >= D.MIN_ELIGIBLE}
    )
    return LB.table(p, t)


def features_doc(p: D.Panel, t: F.Table) -> dict[str, Any]:
    return {
        "columns": list(F.COLUMNS),
        "rows": [[p.axis[i], p.codes[j]] for i, j in t.rows],
        "X": t.X,
        "missing": t.missing,
        "y_abs": t.y,
        "usable": {p.axis[i]: t.usable[i] for i in t.sig},
        "label_count": {p.axis[i]: t.label_count[i] for i in t.sig},
    }


def rows_by_signal(t: F.Table) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for r, (i, _j) in enumerate(t.rows):
        out.setdefault(i, []).append(r)
    return out


def phase_fits(
    rdir, p, t, mkt, fx, tag, rows_by_sig, defined, bud, clock, fits
) -> dict:
    """분기마다 M 1개(정책 · 비용별 재학습 없음) — 예측 = 그 분기에 배정된 공통 계획 신호의 자격 종목."""
    preds: dict[str, dict] = {}
    for q in fx["quarter_detail"][tag]:
        mine = {
            d: rows_by_sig[p.axis.index(d)]
            for d in fx[tag]["plan_signals"]
            if fx["assign"][d] == q["id"]
        }
        rows = S20.train_rows(t, p, q, defined)
        preds.update(
            S20.fit(rdir, p, t, mkt, q, P21.INPUT, rows, mine, bud, clock, tag, fits)
        )
    name = "validation" if tag == "val" else "test"
    P8.write_once(rdir / f"predictions_{name}.json", P8.dumps(preds, compact=True))
    P8.write_once(
        rdir / f"schedule_{name}.json",
        P8.dumps(PR.schedule(p.axis, [r for r in fits if r["phase"] == tag])),
    )
    return preds


def r_score(t: F.Table, rs: list[int]) -> dict[int, float]:
    return {j: math.log1p(v) for j, v in PR.scores_for(t, rs, "RET_60").items()}


def m_score(
    p: D.Panel, t: F.Table, rs: list[int], src: dict, d: str
) -> dict[int, float]:
    got = src.get(d)
    out = {}
    for r in rs:
        j = t.rows[r][1]
        v = None if got is None else got.get(p.codes[j])
        if not isinstance(v, float) or not math.isfinite(v):
            raise CheckRequired(f"{d} {p.codes[j]} M 예측 없음 · 비유한 값")
        out[j] = v
    return out


def plans(p, t, el, rows_by_sig, signals, preds, ids, kind) -> dict[int, TP.Plan]:
    out = {}
    for d in signals:
        i = p.axis.index(d)
        rs = rows_by_sig[i]
        mom = PR.scores_for(t, rs, "RET_120")
        out[i] = TP.Plan(
            signal=i,
            scores=r_score(t, rs) if kind == "R" else m_score(p, t, rs, preds, d),
            cands=sorted(mom, key=lambda j: (-mom[j], p.codes[j]))[: TP.CAND_TOP],
            excluded={j: why for why, js in el.excluded[i].items() for j in js},
            model_id=ids.get(d) if kind == "M" else None,
        )
    return out


def phase_plans(p, t, el, rows_by_sig, fx, tag, preds) -> dict[str, dict]:
    sigs = fx[tag]["plan_signals"]
    ids = P21.model_ids(fx["assign"])
    return {k: plans(p, t, el, rows_by_sig, sigs, preds, ids, k) for k in ("R", "M")}


def simulate(p, plans_by_kind, w, key, cost, name, k_idx) -> PO.Book:
    if key is None:
        return PO.simulate_bench(
            p, p.ci[D.BENCH], k_idx, w["start_idx"], w["end_idx"], cost
        )
    return TP.simulate(
        p,
        plans_by_kind[key[0]],
        w["start_idx"],
        w["end_idx"],
        cost,
        name,
        strengthen=key[1] == "1",
    )


def books(rdir, sub, p, plans_by_kind, w, items, k_idx) -> dict[str, dict]:
    """items = (곡선 이름 · 곡선 키(None = K) · 비용). 미확정 장부가 나오면 거기서 멈춘다."""
    out = {}
    for name, key, cost in items:
        js = PO.to_json(simulate(p, plans_by_kind, w, key, cost, name, k_idx))
        P8.write_once(rdir / sub / f"{name}.json", P8.dumps(js, compact=True))
        out[name] = js
        if js["status"] != "OK":
            break
    return out


def extra(p: D.Panel, books_: dict[str, dict], bounds=None) -> dict[str, dict]:
    """정상 장부만 — R/M = 거래 · 묶음 · 회복 · 현금 · 검토 · 보류 · K = 회복 · 현금 · 비용 · 보유(편입 → 끝)."""
    pos = {d: k for k, d in enumerate(p.axis)}
    out = {}
    for n, b in books_.items():
        if b["status"] != "OK":
            continue
        led = b["ledger"]
        if n.startswith("K_"):
            buy = b["fills"][0] if b["fills"] else None
            out[n] = {
                "underwater": TR.underwater(led, PO.START_VALUE),
                "cash": TR.cash(led),
                "costs_total": sum(f["cost"] for f in b["fills"]),
                "holding": {
                    "entry": buy and buy["date"],
                    "market_days_to_end": buy
                    and pos[led[-1]["date"]] - pos[buy["date"]],
                },
            }
        else:
            out[n] = TR.analyze(p, b, PO.START_VALUE)
        out[n]["underwater_sub"] = TR.underwater_sub(led, bounds, PO.START_VALUE)
    return out


def metrics(p, books_, w, bounds) -> dict[str, dict]:
    pos = {d: k for k, d in enumerate(p.axis)}
    names = {c: p.series[c].name[-1] for c in p.codes}
    return {n: R.curve(b, w["start"], bounds, pos, names) for n, b in books_.items()}


def pair_bootstrap(p, sig, tbooks) -> tuple[dict, int]:
    """평가 구간 완전한 주 전체의 M1_20 − R1_20 주간 수익 차이(같은 주 쌍)."""
    week_ends = {p.axis[i] for i in sig}
    wm, tail = R.weekly_returns(tbooks["M1_20"]["ledger"], week_ends, PO.START_VALUE)
    wr, _ = R.weekly_returns(tbooks["R1_20"]["ledger"], week_ends, PO.START_VALUE)
    if [d for d, _ in wm] != [d for d, _ in wr]:
        raise CheckRequired("M1 · R1 주간 날짜가 다름")
    diffs = np.array([a - b for (_, a), (_, b) in zip(wm, wr)], dtype=float)
    return R.bootstrap(diffs.tolist()), tail
