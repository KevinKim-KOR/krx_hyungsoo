"""POC6-20 학습 · 계획 · 장부 · 쌍 bootstrap 도우미(flow · verify 공용) — PLAN §3 · 판정 §3 · §4.

```text
행       H1 학습 행(5달력년 · 성숙 + 5거래일 · 사용 가능 날짜 · 정답 있음) 중 공통 날짜만 · 잠금 분기와 대조
입력     P = 30열 · M = 30열 + 시장 4열(같은 행 · 정답 · 가중치) · 행 지문과 입력 배열 지문을 따로 기록
모델     `<분기>_P` · `<분기>_M` · 저장 → 열 이름 확인 → 복원 예측 대조(1e-12)
계획     P · M = 저장 예측 점수 · B = RET_120 · 정기 계획은 공통 계획 주만 · reviews = 모든 주간 신호
```
"""

from __future__ import annotations

import gzip
from typing import Any

import numpy as np

from app.feature_gain import protocol as P8
from app.market_context_value import learner as L
from app.market_context_value import protocol as P20
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import CheckRequired

_sha = P20._sha
VAL_STOP = "선행 재생 장부 평가 미확정 {bad} — 주 평가 미실행(판정 §3 Q3)"
TEST_STOP = "주 평가 장부 평가 미확정 {bad} — 개선 판정 NOT_JUDGED(설계 §7)"
FINAL_KEYS = (
    "judgment",
    "bootstrap",
    "bootstrap_tail_excluded",
    "explain",
)  # 정상 완료에만 있는 보고 칸


def coverage(fx: dict) -> dict:
    """보고의 사용 · 제외 주(잠금 사실 그대로 · flow · verify 공용)."""
    return {
        **{
            k: {kk: fx[k][kk] for kk in ("weeks", "h1_weeks", "lost")}
            for k in ("val", "test")
        },
        "sub_weeks": fx["sub_weeks"],
    }


def gz(obj: Any) -> bytes:
    return gzip.compress(P8.dumps(obj, compact=True), mtime=0)


def x_row(t: F.Table, mkt: dict, r: int, inp: str) -> list:
    v = list(t.X[r])
    if inp == "M":
        extra = mkt[t.rows[r][0]]["values"]
        if extra is None:
            raise CheckRequired(f"M 행의 시장 4열 미정의: 행 {r}")
        v += list(extra)
    return v


def train_rows(t: F.Table, p: D.Panel, q: dict, defined: set[int]) -> list[int]:
    """H1 학습 행(5달력년 · 성숙 + 5거래일 · 사용 가능 날짜 · 정답 있음) 중 공통 날짜만 — 잠금 분기와 대조."""
    ci = p.axis.index(q["cutoff"])
    rows = [r for r in F.training_rows(t, p.axis, ci) if t.rows[r][0] in defined]
    weeks = len({t.rows[r][0] for r in rows})
    if weeks != q["weeks"] or len(rows) != q["rows"]:
        raise CheckRequired(
            f"{q['id']} 학습 표본이 잠금과 다름: {weeks}주 · {len(rows)}행"
        )
    return rows


def row_prints(t: F.Table, p: D.Panel, rows: list[int]) -> dict[str, str]:
    """P/M 공통 행 지문(날짜 · ETF · 순서 · 정답 · 가중치 · 기존 30열) — 판정 §4."""
    return {
        "rows_sha256": _sha(
            [[p.axis[t.rows[r][0]], p.codes[t.rows[r][1]]] for r in rows]
        ),
        "label_sha256": _sha([t.y[r] for r in rows]),
        "weight_sha256": _sha(F.weights(t, rows)),
        "x30_sha256": _sha([t.X[r] for r in rows]),
    }


def fit(rdir, p, t, mkt, q, inp, rows, plan_rows, bud, clock, phase, fits) -> dict:
    cols = L.COLUMNS[inp]
    X = L.matrix([x_row(t, mkt, r, inp) for r in rows], len(cols))
    t0 = clock()
    booster = L.train(inp, X, [t.y[r] for r in rows], F.weights(t, rows))
    trained = clock()
    text = M.to_text(booster)
    mid = f"{q['id']}_{inp}"
    P8.write_once(rdir / "models" / f"{mid}.txt", text.encode("utf-8"))
    if L.feature_names(text) != list(cols):
        raise CheckRequired(f"{mid} 모델 열 이름 · 순서가 입력과 다름")
    bad = L.param_problems(text)
    if bad:
        raise CheckRequired(f"{mid} 매개변수 ≠ 고정 ML_B 설정: {', '.join(bad)}")
    back = M.restore(text)
    preds: dict[str, dict[str, float]] = {}
    diff = 0.0
    for d, rs in plan_rows.items():
        Xp = L.matrix([x_row(t, mkt, r, inp) for r in rs], len(cols))
        a, b = M.predict(booster, Xp), M.predict(back, Xp)
        diff = max(diff, float(np.max(np.abs(a - b))))
        preds[d] = {p.codes[t.rows[r][1]]: float(v) for r, v in zip(rs, a)}
    if diff > M.RESTORE_TOL:
        P8.write_once(
            rdir / "models" / f"{mid}{PR.MISMATCH_SUFFIX}",
            P8.dumps({"id": mid, "diff": diff, "predictions": preds}, compact=True),
        )
        raise CheckRequired(f"{mid} 저장 전후 예측 차이 {diff}")
    rec = {
        "id": mid,
        "phase": phase,
        "quarter": q["id"],
        "input": inp,
        "struct": L.STRUCT,
        "cutoff": q["cutoff"],
        "rows": len(rows),
        "weeks": len({t.rows[r][0] for r in rows}),
        "columns_sha256": _sha(list(cols)),
        **row_prints(t, p, rows),
        "x_sha256": _sha([x_row(t, mkt, r, inp) for r in rows]),
        "train_started_at": store.iso(t0),
        "trained_at": store.iso(trained),
        "predicted_at": store.iso(clock()),
        "seconds": (trained - t0).total_seconds(),
        "restore_max_abs_diff": diff,
        "resolved_params": M.resolved_params(text),
        "model_sha256": store.sha256_bytes(text.encode("utf-8")),
        "signals": sorted(preds),
        "predictions": preds,
    }
    P8.write_once(rdir / "models" / f"{mid}.json", P8.dumps(rec))
    fits.append(rec)
    bud.check(f"fit {mid}")
    return preds


def plans(p, t, rows_by_sig, ids, signals, scores) -> dict[int, PO.Plan]:
    out = {}
    for d in signals:
        i = p.axis.index(d)
        rs = rows_by_sig[i]
        out[i] = PO.Plan(
            signal=i,
            scores=scores(d, rs),
            trend_ok=PR.trend_ok(t, rs),
            model_id=ids.get(d),
        )
    return out


def books(rdir, sub, p, plans_by_key, w, sig, items, k_idx) -> dict[str, dict]:
    """items = (곡선 이름 · 계획 키(None = K) · 비용). reviews = 모든 주간 신호(판정 §3 Q2)."""
    out = {}
    for name, key, cost in items:
        if key is None:
            bk = PO.simulate_bench(
                p, p.ci[D.BENCH], k_idx, w["start_idx"], w["end_idx"], cost
            )
        else:
            bk = PO.simulate(
                p, plans_by_key[key], w["start_idx"], w["end_idx"], cost, name, sig
            )
        js = PO.to_json(bk)
        P8.write_once(rdir / sub / f"{name}.json", P8.dumps(js, compact=True))
        out[name] = js
        if js["status"] != "OK":
            break
    return out


def scorers(p: D.Panel, t: F.Table):
    def ml(src):
        return lambda d, rs: {t.rows[r][1]: src[d][p.codes[t.rows[r][1]]] for r in rs}

    def mom(col):
        return lambda d, rs: PR.scores_for(t, rs, col)

    return ml, mom


def window(fx: dict, tag: str, p: D.Panel) -> dict:
    return {
        **fx[tag],
        "start_idx": p.axis.index(fx[tag]["start"]),
        "end_idx": p.axis.index(fx[tag]["end"]),
    }


def phase_fits(
    rdir, p, t, mkt, fx, tag, rows_by_sig, defined, bud, clock, fits
) -> dict:
    preds: dict[str, dict] = {k: {} for k in L.INPUTS}
    for q in fx["quarter_detail"][tag]:
        mine = {
            d: rows_by_sig[p.axis.index(d)]
            for d in fx[tag]["plan_signals"]
            if fx["assign"][d] == q["id"]
        }
        rows = train_rows(t, p, q, defined)
        for inp in L.INPUTS:
            preds[inp].update(
                fit(rdir, p, t, mkt, q, inp, rows, mine, bud, clock, tag, fits)
            )
    name = "validation" if tag == "val" else "test"
    P8.write_once(rdir / f"predictions_{name}.json", P8.dumps(preds, compact=True))
    P8.write_once(
        rdir / f"schedule_{name}.json",
        P8.dumps(PR.schedule(p.axis, [r for r in fits if r["phase"] == tag])),
    )
    return preds


def phase_plans(p, t, rows_by_sig, fx, tag, preds) -> dict[str, dict]:
    ml, mom = scorers(p, t)
    sigs = fx[tag]["plan_signals"]
    return {
        "P": plans(
            p, t, rows_by_sig, P20.model_ids(fx["assign"], "P"), sigs, ml(preds["P"])
        ),
        "M": plans(
            p, t, rows_by_sig, P20.model_ids(fx["assign"], "M"), sigs, ml(preds["M"])
        ),
        "B": plans(p, t, rows_by_sig, {}, sigs, mom("RET_120")),
    }


def pair_bootstrap(p, sig, tbooks) -> tuple[dict, int]:
    """평가 구간 완전한 주 전체의 M_20 − P_20 주간 수익 차이(같은 주 쌍 · 판정 §3 Q4)."""
    week_ends = {p.axis[i] for i in sig}
    wm, tail = R.weekly_returns(tbooks["M_20"]["ledger"], week_ends, PO.START_VALUE)
    wp, _ = R.weekly_returns(tbooks["P_20"]["ledger"], week_ends, PO.START_VALUE)
    if [d for d, _ in wm] != [d for d, _ in wp]:
        raise CheckRequired("M · P 주간 날짜가 다름")
    return R.bootstrap([a - b for (_, a), (_, b) in zip(wm, wp)]), tail


def after_end(p, sig, w) -> list[str]:
    return [
        p.axis[i] for i in sig if w["start_idx"] <= i <= w["end_idx"] < i + F.EXEC_LAG
    ]


def ic_pairs(t: F.Table, pl: dict[int, PO.Plan], p: D.Panel) -> dict[str, list]:
    zmap = {(i, j): t.z[r] for r, (i, j) in enumerate(t.rows)}
    return {
        p.axis[i]: [
            (s, zmap[(i, j)])
            for j, s in x.scores.items()
            if zmap.get((i, j)) is not None
        ]
        for i, x in pl.items()
    }
