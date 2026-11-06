"""POC6-23 prepare/lock · run(참조 · 정답 → 분모 → 70 fit → 선행 재생 → 주 평가) · 실패 기록 — 통합 설계 V1 개정 2 §6.

```text
prepare  환경(SciPy · HiGHS · numpy · 스레드 변수) → 봉인 확인 → POC6-20 사실 · 공통 신호 · 분기 창 상한을 PLAN 표와 대조
         → protocol.json(참조 경로 · 정답 · 점수 · 성과 계산 0)
run      잠금과 코드 · 환경 · 사실이 같을 때만 1회:
         30열 표 → R0 참조 경로(POC6-21 simulate 와 장부 대조) → 행동별 20거래일 분기 정답
         → 분기마다 유효 D ≥ 104(아니면 INSUFFICIENT_DATA · 창 · 행동 · 기준 변경 없음)
         → 35분기 × P · S = 최대 70 fit(수치 조건 실패 = CHECK_REQUIRED · 모형 기록은 남김)
         → 선행 P/S/R/K 20bp(하나라도 미확정이면 주 평가 미실행) → 주 평가 × 20 · 40bp
         → 거래 분석 · 주간 S_20 − P_20 bootstrap · 판정 · 보고 글 · 파일 해시까지 계산 → finish 예산 판정 → 쓰기
중단     CheckRequired · 예산 초과 = 그 시점까지 보존 + 보고 · 그 밖의 예외 = run.json FAILED
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.decision_learning import actions as A
from app.decision_learning import labels as LB
from app.decision_learning import learn as LN
from app.decision_learning import policy as PL
from app.decision_learning import protocol as P23
from app.decision_learning import report as RP
from app.feature_gain import protocol as P8
from app.market_context_value import flow as FW20
from app.market_context_value import study as S20
from app.ml_evidence import store
from app.trend_switch import flow as FW21
from app.trend_switch import study as ST21
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import flow as FL
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import BudgetStop, CheckRequired, Refused

_base = FW20._base
_record_failure = FW20._record_failure
VAL_STOP = "선행 재생 장부 평가 미확정 {bad} — 주 평가 미실행"
TEST_STOP = "주 평가 장부 평가 미확정 {bad} — 판정 NOT_JUDGED"
SHORT_STOP = "분기 유효 학습 D < 104: {bad} — 창 · 행동 · 기준 변경 없이 중단"
FINAL_KEYS = ("judgment", "bootstrap", "bootstrap_tail_excluded")


# ── 조립(flow · verify 공용) ─────────────────────────────────────────────────────


def table(p: D.Panel, el: D.Eligibility) -> F.Table:
    return F.build_table(
        p, {i: el.members[i] for i in el.sig if len(el.members[i]) >= D.MIN_ELIGIBLE}
    )


def features_doc(p: D.Panel, t: F.Table) -> dict[str, Any]:
    return {
        "columns": list(F.COLUMNS),
        "rows": [[p.axis[i], p.codes[j]] for i, j in t.rows],
        "X": t.X,
        "missing": t.missing,
    }


def dplans(p, t, el, mkt, rows_by_sig, signals: list[int], assign) -> dict:
    """공통 계획 신호 → DPlan(R0 계획 · 34열 원값 · 분기 배정 · 참조 경로는 배정 없음)."""
    r0 = ST21.plans(p, t, el, rows_by_sig, [p.axis[i] for i in signals], {}, {}, "R")
    out = {}
    for i in signals:
        rows = {t.rows[r][1]: S20.x_row(t, mkt, r, P23.INPUT) for r in rows_by_sig[i]}
        out[i] = PL.DPlan(
            signal=i, r0=r0[i], rows=rows, quarter=assign.get(p.axis[i], "")
        )
    return out


def ref_bounds(p: D.Panel, fx: dict) -> tuple[int, int, int]:
    pos = {d: k for k, d in enumerate(p.axis)}
    return pos[fx["common"]["first"]], pos[fx["last_train"]], pos[fx["label_end"]]


def window_dates(p, common, q, labels_doc) -> tuple[list[int], dict[str, int]]:
    """분기 창 ∩ 유효 정답(KEEP 외 · 완전한 분기) — (D 목록 · 제외 사유 수)."""
    cut = p.axis.index(q["cutoff"])
    ds, bad = [], {}
    for i in common:
        if not (p.axis[i] >= q["lo"] and i + LB.T_LAG <= cut - P23.MATURE):
            continue
        why = labels_doc[p.axis[i]]["excluded"]
        if why is None:
            ds.append(i)
        else:
            bad[why] = bad.get(why, 0) + 1
    return ds, dict(sorted(bad.items()))


def _snap(rec: dict, ci: dict[str, int]) -> A.Snapshot:
    return A.Snapshot(
        nav=rec["nav"],
        cash=rec["cash"],
        held={ci[c]: v for c, v in rec["held"].items()},
        sell_live={ci[c]: r for c, r in rec["sell_live"].items()},
        buy_live=set(),
    )


def problem(p, plans, labels_doc, ds: list[int]) -> tuple[LN.Problem, dict]:
    """분기 학습 문제(20bp) — 표준화 통계 · s_g · 행 · a*(flow · verify 같은 정의)."""
    ci, cost = p.ci, PR.BASE_COST
    recs = [labels_doc[p.axis[i]] for i in ds]
    acts = [[A.parse(n, ci) for n in r["actions"]] for r in recs]
    need = [A.needed(a) for a in acts]
    raw = [[plans[i].rows[j] for j in js] for i, js in zip(ds, need)]
    mu, sd, const, info = LN.column_stats(raw, P23.COLUMNS)
    sg = LN.scale([r["g"][1:] for r in recs])
    dates, imputed, uses = [], 0, 0
    for i, r, a, js in zip(ds, recs, acts, need):
        sn = _snap(r, ci)
        u, miss = {}, {}
        for j in js:
            u[j], miss[j] = LN.transform(plans[i].rows[j], mu, sd, const)
            imputed += miss[j]
        z, kap = [], []
        for x in a[1:]:
            uses += sum(miss[j] for j in (x.sell, x.buy) if j is not None)
            b, s, k = A.amounts(sn, x, cost)
            z.append(A.z_vector(x, b, s, u))
            kap.append(k / sg)
        y_all = np.asarray(r["g"], dtype=float) / sg
        dates.append(
            {
                "z": np.vstack(z),
                "kappa": np.asarray(kap),
                "y": y_all[1:],
                "star": int(np.argmax(y_all)),
            }
        )
    meta = {
        "dates": [p.axis[i] for i in ds],
        "rows": sum(len(a) - 1 for a in acts),
        "mu": mu,
        "sigma": sd,
        "constant": const,
        "columns": info,
        "s_g": sg,
        "imputed_cells": imputed,
        "imputed_action_uses": uses,
    }
    return LN.Problem(dates), meta


def fit_quarter(rdir, p, plans, labels_doc, q, ds, excluded, clock):
    """(모형 기록 · 수치 조건 문제) — 기록을 먼저 쓰고, 판정은 부른 쪽이 보고 칸을 채운 뒤 한다."""
    started = store.iso(clock())
    pb, meta = problem(p, plans, labels_doc, ds)
    doc = {
        "quarter": q["id"],
        "phase": q["phase"],
        "cutoff": q["cutoff"],
        "lo": q["lo"],
        "upper": q["upper"],
        "excluded": excluded,
        **meta,
        "train_started_at": started,
    }
    for kind in P23.KINDS:
        doc[kind] = LN.fit(pb, kind)
    doc["trained_at"] = store.iso(clock())
    P8.write_once(rdir / "models" / f"{q['id']}.json", P8.dumps(doc, compact=True))
    return doc, [x for kind in P23.KINDS for x in LN.check(doc[kind])]


def learning_row(q, ds, excluded, doc: Optional[dict]) -> dict:
    row = {"id": q["id"], "upper": q["upper"], "valid": len(ds), "excluded": excluded}
    if doc is not None:
        row.update(
            rows=doc["rows"],
            s_g=doc["s_g"],
            imputed=doc["imputed_cells"],
            imputed_action_uses=doc["imputed_action_uses"],
        )
        for kind in P23.KINDS:
            f = doc[kind]
            row[kind] = {
                k: f.get(k)
                for k in ("status", "abs_diff", "l1", "max_violation", "upper_margin")
                if k in f
            }
    return row


def simulate(p, plans, models, key, w, cost, name, k_idx) -> PO.Book:
    s, e = w["start_idx"], w["end_idx"]
    if key == "K":
        return PO.simulate_bench(p, p.ci[D.BENCH], k_idx, s, e, cost)
    if key == "R":
        return PL.simulate_r(p, plans, s, e, cost, name)
    return PL.simulate(p, plans, models, key, s, e, cost, name)


def books(rdir, sub, p, plans, models, w, items, k_idx, out=None) -> dict[str, dict]:
    out = {} if out is None else out
    for name, key, cost in items:
        js = PO.to_json(simulate(p, plans, models, key, w, cost, name, k_idx))
        P8.write_once(rdir / sub / f"{name}.json", P8.dumps(js, compact=True))
        out[name] = js
        if js["status"] != "OK":
            break
    return out


def metrics(p, books_, w, bounds) -> dict[str, dict]:
    pos = {d: k for k, d in enumerate(p.axis)}
    names = {c: p.series[c].name[-1] for c in p.codes}
    return {n: R.curve(b, w["start"], bounds, pos, names) for n, b in books_.items()}


def pair_bootstrap(p, sig, tbooks) -> tuple[dict, int]:
    """평가 구간 완결 주 전체의 S_20 − P_20 주간 수익 차이(같은 주 쌍)."""
    week_ends = {p.axis[i] for i in sig}
    ws, tail = R.weekly_returns(tbooks["S_20"]["ledger"], week_ends, PO.START_VALUE)
    wp, _ = R.weekly_returns(tbooks["P_20"]["ledger"], week_ends, PO.START_VALUE)
    if [d for d, _ in ws] != [d for d, _ in wp]:
        raise CheckRequired("S · P 주간 날짜가 다름")
    return R.bootstrap([a - b for (_, a), (_, b) in zip(ws, wp)]), tail


def models_for_books(docs: dict[str, dict]) -> dict[str, dict]:
    return {
        q: {
            "mu": d["mu"],
            "sigma": d["sigma"],
            "constant": d["constant"],
            "s_g": d["s_g"],
            **{k: {"beta": d[k]["beta"]} for k in P23.KINDS},
        }
        for q, d in docs.items()
    }


def reference_summary(p, bk: dict, states: int, labels_doc, same: bool) -> dict:
    ex: dict[str, int] = {}
    for r in labels_doc.values():
        k = r["excluded"] or "VALID"
        ex[k] = ex.get(k, 0) + 1
    return {
        "status": bk["status"],
        "same_as_poc6_21": same,
        "start": bk["ledger"][0]["date"] if bk["ledger"] else None,
        "end": bk["ledger"][-1]["date"] if bk["ledger"] else None,
        "states": states,
        "fills": len(bk["fills"]),
        "excluded": dict(sorted(ex.items())),
    }


# ── prepare ──────────────────────────────────────────────────────────────────────


def prepare(
    root: Path = P23.ROOT,
    db: Path = PR.DB,
    repo: Path = Path("."),
    clock=store.utc_now,
    correction_reason: Optional[str] = None,
    market_base: Optional[Path] = None,
) -> dict:
    """사전 잠금. 이미 잠금이 있으면 거부 — 코드 결함 정정만 `correction_reason` 으로 정정 잠금."""
    root = Path(root)
    with P8.run_lock(root):
        prev = None
        if P8.locks(root):
            if not correction_reason:
                raise Refused(
                    "잠금이 이미 있음(1회 규칙 · 코드 결함 정정은 correction_reason)"
                )
            prev_dir, prev = P8.active_lock(root)
        env = P23.runtime_env()
        bad = P23.env_problems(env)
        if bad:
            raise CheckRequired("환경 확인 전 — " + " · ".join(bad))
        p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
        if p.seal["file_sha256"] != PR.FILE_SHA:
            raise CheckRequired(f"봉인 파일 해시 다름: {p.seal['file_sha256']}")
        fx, *_ = P23.survey(p, _base(repo, market_base))
        diffs = P23.compare(fx)
        if diffs:
            raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
        code = P23.code_hashes(repo)
        rec = P23.recipe()
        corrects = None
        if prev is not None:
            corrects = _correction(
                prev_dir, prev, fx, rec, code, env, correction_reason
            )
        now = clock()
        lock_id = P8.new_id(now)
        doc = {
            "schema": P23.SCHEMA["protocol"],
            "protocol_id": P23.PROTOCOL_ID,
            "lock_id": lock_id,
            "locked_at": store.iso(now),
            "inputs": {"db": str(Path(db)), **P23.input_refs()},
            "facts": fx,
            "recipe": rec,
            "code": {"sha256": code},
            "env": env,
            "corrects": corrects,
            "note": "prepare 는 참조 경로 · 정답 · 점수 · 성과를 계산하지 않는다(PLAN §1 · 판정 A-6).",
        }
        P8.write_once(root / lock_id / "protocol.json", P8.dumps(doc))
        return doc


def _correction(prev_dir, prev, fx, rec, code, env, reason) -> dict:
    norm = P8.loads(
        P8.dumps(
            {"inputs": P23.input_refs(), "facts": fx, "recipe": rec}, compact=True
        ).decode()
    )
    for key, what in (("inputs", "입력"), ("facts", "사실"), ("recipe", "recipe")):
        mine = norm[key]
        theirs = (
            {k: prev["inputs"].get(k) for k in mine} if key == "inputs" else prev[key]
        )
        if store.canonical(theirs) != store.canonical(mine):
            raise CheckRequired(f"정정 잠금의 {what}이 이전 잠금과 다름")
    changed = sorted(
        k
        for k in set(code) | set(prev["code"]["sha256"])
        if code.get(k) != prev["code"]["sha256"].get(k)
    )
    if not changed and env == prev["env"]:
        raise Refused("코드 · 환경이 이전 잠금과 같음 — 정정 잠금 불필요")
    runs_dir = prev_dir / "runs"
    return {
        "lock_id": prev["lock_id"],
        "reason": reason,
        "changed_code": changed,
        "env_changed": env != prev["env"],
        "prior_runs": (
            sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
            if runs_dir.exists()
            else []
        ),
    }


# ── run ──────────────────────────────────────────────────────────────────────────


def run(
    root: Path = P23.ROOT,
    db: Path = PR.DB,
    repo: Path = Path("."),
    clock=store.utc_now,
    market_base: Optional[Path] = None,
) -> dict:
    root = Path(root)
    with P8.run_lock(root):
        ldir, lk = P8.active_lock(root)
        runs = ldir / "runs"
        if runs.exists() and any(d.is_dir() for d in runs.iterdir()):
            raise Refused(
                "공식 실행이 이미 있음(성과 때문의 재실행 금지 · 코드 정정은 별도 승인)"
            )
        if P23.code_hashes(repo) != lk["code"]["sha256"]:
            raise CheckRequired("실행 코드가 잠금과 다름")
        env = P23.runtime_env()
        if env != lk["env"] or P23.env_problems(env):
            raise CheckRequired(
                "환경(SciPy · HiGHS · numpy · 스레드 변수 · OS)이 잠금과 다름"
            )
        bad = P23.lock_problems(lk)
        if bad:
            raise CheckRequired("잠금과 다름: " + " · ".join(bad))
        started = clock()
        run_id = P8.new_id(started)
        rdir = runs / run_id
        meta: dict[str, Any] = {
            "schema": P23.SCHEMA["run"],
            "protocol_id": P23.PROTOCOL_ID,
            "lock_id": lk["lock_id"],
            "run_id": run_id,
            "started_at": store.iso(started),
            "env": env,
        }
        bud = FL.Budget(clock, started)
        ctx: dict[str, Any] = {}
        try:
            return _run(
                rdir, lk, meta, Path(db), _base(repo, market_base), clock, bud, ctx
            )
        except (CheckRequired, BudgetStop) as e:
            status = "BUDGET_STOP" if isinstance(e, BudgetStop) else "CHECK_REQUIRED"
            for k in FINAL_KEYS:
                ctx.pop(k, None)
            try:
                return _finish(
                    rdir,
                    meta,
                    bud,
                    clock,
                    status,
                    {**ctx, "stop": f"{type(e).__name__}: {e}"[:500]},
                )
            except BaseException as w:
                _record_failure(rdir, meta, bud, clock, w, f"{type(e).__name__}: {e}")
                raise
        except BaseException as e:
            _record_failure(rdir, meta, bud, clock, e)
            raise


def _finish(rdir, meta, bud, clock, status, rep: dict) -> dict:
    """보고 · 실행 기록 쓰기. 정상 완료는 보고 · 글 · 해시 목록까지 계산한 뒤 finish 한 곳에서 상한 판정(F1/F2)."""
    rep = {
        "schema": P23.SCHEMA["report"],
        "lock_id": meta["lock_id"],
        "run_id": meta["run_id"],
        "note": RP.NOTE,
        "price_note": R.PRICE_NOTE,
        **rep,
    }
    if "judgment" not in rep:
        rep["judgment"] = RP.judge(status, None, None, None)
    data, md = P8.dumps(rep), RP.markdown(rep).encode("utf-8")
    files = {
        **PR.manifest(rdir),
        "report.json": store.sha256_bytes(data),
        "report.md": store.sha256_bytes(md),
    }
    decided = bud.check("finish")["at"] if status == "OK" else store.iso(clock())
    meta.update(status=status, finished_at=decided, stages=bud.stages, files=files)
    P8.write_once(rdir / "report.json", data)
    P8.write_once(rdir / "report.md", md)
    meta["written_at"] = store.iso(clock())
    P8.write_once(rdir / "run.json", P8.dumps(meta))
    return {"meta": meta, "report": rep}


def _phase(rdir, tag, p, plans, models, fx, ctx) -> tuple[dict, list]:
    w = S20.window(fx, tag, p)
    items = P23.val_books() if tag == "val" else P23.test_books()
    sub = "validation" if tag == "val" else "test"
    k_idx = p.axis.index(fx[tag]["k_exec"])
    sig = [p.axis.index(d) for d in fx[tag]["plan_signals"]]
    bounds = PR.SUB_RANGES if tag == "test" else None
    key = "validation" if tag == "val" else "test"
    bks: dict[str, dict] = {}
    try:
        books(rdir, sub, p, {i: plans[i] for i in sig}, models, w, items, k_idx, bks)
    finally:  # 모의 실행 도중 CHECK_REQUIRED 여도 이미 쓴 장부의 보고 칸은 같은 기록으로 남긴다
        ctx[key] = metrics(p, bks, w, bounds)
        ctx[f"{key}_trades"] = RP.extra(p, bks, bounds)
    return bks, items


def _run(rdir, lk, meta, db, base, clock, bud, ctx) -> dict:
    bud.check("start")
    p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
    if p.seal["file_sha256"] != PR.FILE_SHA:
        raise CheckRequired("봉인 파일 해시 다름")
    fx, el, mkt, common = P23.survey(p, base)
    if store.canonical(fx) != store.canonical(lk["facts"]):
        raise CheckRequired(
            "자격 · 날짜 · 시장 4열 · 공통 신호 · 분기 창 사실이 잠금과 다름"
        )
    diffs = P23.compare(fx)
    if diffs:
        raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
    ctx["coverage"] = S20.coverage(fx)
    if fx["data_short"]:
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "DATA_SHORT",
            {**ctx, "stop": " · ".join(fx["data_short"])},
        )
    sig = el.sig
    FW21._inputs(rdir, p, el, mkt, fx)
    t = table(p, el)
    P8.write_once(rdir / "features.json.gz", S20.gz(features_doc(p, t)))
    bud.check("panel · eligibility · market · features")
    rows_by_sig = ST21.rows_by_signal(t)
    plans = dplans(p, t, el, mkt, rows_by_sig, common, fx["assign"])
    # ── R0 참조 경로 · 행동별 분기 정답(20bp) ──
    start, last, end = ref_bounds(p, fx)
    ref_plans = {i: plans[i] for i in common if start <= i <= last}
    rbk, states = LB.reference(p, ref_plans, start, end, PR.BASE_COST)
    rjs = PO.to_json(rbk)
    P8.write_once(rdir / "reference.json", P8.dumps(rjs, compact=True))
    if rjs["status"] != "OK":
        raise CheckRequired(f"R0 참조 경로 평가 미확정({rjs['end'].get('stopped_at')})")
    same = LB.reference_same(p, ref_plans, start, end, PR.BASE_COST, rbk)
    if not same:
        raise CheckRequired("R0 참조 루프 장부 ≠ POC6-21 simulate(R0) 장부")
    bud.check("reference")
    labels_doc = LB.labels(p, ref_plans, states, PR.BASE_COST)
    P8.write_once(rdir / "labels.json.gz", S20.gz(labels_doc))
    ctx["reference"] = reference_summary(p, rjs, len(states), labels_doc, same)
    bud.check("labels")
    # ── 분기 분모 → 70 fit ──
    qs = lk["facts"]["quarter_detail"]
    wins = {q["id"]: window_dates(p, common, q, labels_doc) for q in qs}
    ctx["learning"] = [learning_row(q, *wins[q["id"]], None) for q in qs]
    short = [
        f"{q} {len(ds)}" for q, (ds, _x) in wins.items() if len(ds) < P23.MIN_DATES
    ]
    if short:
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "INSUFFICIENT_DATA",
            {**ctx, "stop": SHORT_STOP.format(bad=short)},
        )
    docs = {}
    for k, q in enumerate(qs):
        ds, ex = wins[q["id"]]
        doc, bad = fit_quarter(rdir, p, plans, labels_doc, q, ds, ex, clock)
        docs[q["id"]] = doc
        ctx["learning"][k] = learning_row(
            q, ds, ex, doc
        )  # 기록을 쓴 뒤 보고 칸 먼저(정지해도 같은 기록)
        if bad:
            raise CheckRequired(f"{q['id']} 수치 조건: " + " · ".join(bad))
        bud.check(f"fit {q['id']}")
    models = models_for_books(docs)
    # ── 선행 재생 → 주 평가 ──
    vb, items = _phase(rdir, "val", p, plans, models, fx, ctx)
    ctx["validation_signal_after_end"] = S20.after_end(p, sig, S20.window(fx, "val", p))
    bud.check("validation books")
    if len(vb) < len(items) or any(b["status"] != "OK" for b in vb.values()):
        bad = [n for n, b in vb.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {**ctx, "stop": VAL_STOP.format(bad=bad)},
        )
    tb, items = _phase(rdir, "test", p, plans, models, fx, ctx)
    ctx["test_signal_after_end"] = S20.after_end(p, sig, S20.window(fx, "test", p))
    bud.check("test books")
    if len(tb) < len(items) or any(b["status"] != "OK" for b in tb.values()):
        bad = [n for n, b in tb.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {**ctx, "stop": TEST_STOP.format(bad=bad)},
        )
    # 주 끝 = 모든 주간 신호일(통상 판단 없는 주 포함)
    boot, tail = pair_bootstrap(p, sig, tb)
    ctx.update(
        bootstrap=boot,
        bootstrap_tail_excluded=tail,
        judgment=RP.judge("OK", ctx["test"], ctx["test_trades"], boot),
    )
    return _finish(rdir, meta, bud, clock, "OK", ctx)
