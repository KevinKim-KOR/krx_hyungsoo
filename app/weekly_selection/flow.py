"""POC6-11 prepare/lock · run(검증 → 선택 → 시험) · 실패 기록 · 예산 감시 — 설계 §9 · §10 · 판정 §3 · §4.

```text
prepare  봉인 확인 → 자격 · 정답 '가용성' · 날짜 · 표본 수 · 모델 배정을 세어 PLAN 표(EXPECTED)와 대조 → protocol.json
         (정답 크기 · 특징 값 · 순위 · 성과 계산 0 · LightGBM 4.7.0 환경 확인 뒤에만)
run      잠금과 코드 · 환경 · 사실이 같을 때만 1회 — 검증 12분기 × ML_A/B(24 fit) + MOM20/120 + K →
         검증 곡선 하나라도 CHECK_REQUIRED 면 선택 · 시험 미실행 → 선택 저장(2020-12-30 검증 마지막 평가 뒤) →
         선택 구조만 시험 23분기(cutoff 2020-12-30 판부터) → L · B · K 20bp(필수) → 40bp → 보고
중단     CheckRequired · 예산 초과(BUDGET_STOP) = 그 시점까지 보존 + 보고 · 그 밖의 예외 = run.json FAILED
```
"""

from __future__ import annotations

import gzip
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.feature_gain import protocol as P8
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import BudgetStop, CheckRequired, Refused

# ── prepare ──────────────────────────────────────────────────────────────────────


def runtime_env() -> dict[str, Any]:
    M.lgb()
    bad = M.openmp_problem()
    if bad:
        raise CheckRequired(f"OpenMP 로드 순서: {bad}")
    return {**M.env(), "libomp_loaded": M.loaded_libomp()}


def prepare(
    root: Path = PR.ROOT,
    db: Path = PR.DB,
    repo: Path = Path("."),
    clock=store.utc_now,
    correction_reason: Optional[str] = None,
) -> dict:
    """사전 잠금. 이미 잠금이 있으면 거부 — 코드 결함 정정만 `correction_reason` 으로 정정 잠금(설계 §9).

    정정 잠금은 이전 잠금과 입력 · 사실 · recipe 가 같아야 하고 코드나 환경이 달라야 한다.
    이전 잠금 · 실행은 그대로 두고, 새 실행은 정정 잠금 아래에 쌓인다(성과 때문의 재실행 아님).
    """
    root = Path(root)
    with P8.run_lock(root):
        prev = None
        if P8.locks(root):
            if not correction_reason:
                raise Refused(
                    "잠금이 이미 있음(1회 규칙 · 코드 결함 정정은 correction_reason)"
                )
            prev_dir, prev = P8.active_lock(root)
        if M.env().get("lightgbm") != M.LGB_VERSION:
            raise CheckRequired(
                "LightGBM 4.7.0 환경 확인 전 — 공식 잠금 · 실행을 열지 않음"
            )
        env = runtime_env()
        p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
        if p.seal["file_sha256"] != PR.FILE_SHA:
            raise CheckRequired(f"봉인 파일 해시 다름: {p.seal['file_sha256']}")
        fx, *_ = PR.survey(p)
        diffs = PR.compare(fx)
        if diffs:
            raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
        code = PR.code_hashes(repo)
        rec = PR.recipe()
        corrects = None
        if prev is not None:
            norm = P8.loads(
                P8.dumps(
                    {"inputs": PR.input_refs(), "facts": fx, "recipe": rec},
                    compact=True,
                ).decode()
            )
            if {k: prev["inputs"].get(k) for k in PR.input_refs()} != norm["inputs"]:
                raise CheckRequired("정정 잠금의 입력이 이전 잠금과 다름")
            if store.canonical(prev["facts"]) != store.canonical(norm["facts"]):
                raise CheckRequired(
                    "정정 잠금의 사실(자격 · 날짜 · 표본)이 이전 잠금과 다름"
                )
            if store.canonical(prev["recipe"]) != store.canonical(norm["recipe"]):
                raise CheckRequired(
                    "정정 잠금의 recipe 가 이전 잠금과 다름(설정 변경은 정정이 아님)"
                )
            changed = sorted(
                k
                for k in set(code) | set(prev["code"]["sha256"])
                if code.get(k) != prev["code"]["sha256"].get(k)
            )
            if not changed and env == prev["env"]:
                raise Refused("코드 · 환경이 이전 잠금과 같음 — 정정 잠금 불필요")
            runs_dir = prev_dir / "runs"
            corrects = {
                "lock_id": prev["lock_id"],
                "reason": correction_reason,
                "changed_code": changed,
                "env_changed": env != prev["env"],
                "prior_runs": (
                    sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
                    if runs_dir.exists()
                    else []
                ),
            }
        now = clock()
        lock_id = P8.new_id(now)
        doc = {
            "schema": "poc6_11_protocol_v1",
            "protocol_id": PR.PROTOCOL_ID,
            "lock_id": lock_id,
            "locked_at": store.iso(now),
            "inputs": {"db": str(Path(db)), **PR.input_refs()},
            "facts": fx,
            "recipe": rec,
            "code": {"sha256": code},
            "env": env,
            "corrects": corrects,
            "note": "prepare 는 정답 크기 · 특징 값 · 순위 · 성과를 계산하지 않는다(설계 §9).",
        }
        P8.write_once(root / lock_id / "protocol.json", P8.dumps(doc))
        return doc


# ── run ──────────────────────────────────────────────────────────────────────────


class Budget:
    def __init__(self, clock, started):
        self.clock, self.started = clock, started
        self.cpu0 = time.process_time()
        self.stages: list[dict] = []

    def check(self, stage: str) -> dict:
        now = self.clock()
        wall = (now - self.started).total_seconds()
        rss = store.max_rss()
        rss_b = rss["raw"] if rss["unit"] == "bytes" else rss["raw"] * 1024
        rec = {
            "stage": stage,
            "at": store.iso(now),
            "wall_s": wall,
            "cpu_s": time.process_time() - self.cpu0,
            "max_rss_bytes": rss_b,
        }
        self.stages.append(rec)
        if wall > PR.BUDGET_S or rss_b > PR.RSS_MAX:
            raise BudgetStop(f"{stage}: 경과 {wall:.0f}초 · 최대 RSS {rss_b} bytes")
        return rec


def _gz(obj: Any) -> bytes:
    return gzip.compress(P8.dumps(obj, compact=True), mtime=0)


def run(
    root: Path = PR.ROOT, db: Path = PR.DB, repo: Path = Path("."), clock=store.utc_now
) -> dict:
    root = Path(root)
    with P8.run_lock(root):
        ldir, lk = P8.active_lock(root)
        runs = ldir / "runs"
        if runs.exists() and any(d.is_dir() for d in runs.iterdir()):
            raise Refused(
                "공식 실행이 이미 있음(성과 때문의 재실행 금지 · 코드 정정은 설계자 판정)"
            )
        if PR.code_hashes(repo) != lk["code"]["sha256"]:
            raise CheckRequired("실행 코드가 잠금과 다름")
        if runtime_env() != lk["env"]:
            raise CheckRequired("환경(LightGBM · libomp · numpy 등)이 잠금과 다름")
        bad = PR.lock_problems(
            lk
        )  # 잠금 식별자 · 입력 · recipe ↔ 지금 코드(검증 r1 F1)
        if bad:
            raise CheckRequired("잠금과 다름: " + " · ".join(bad))
        started = clock()
        run_id = P8.new_id(started)
        rdir = runs / run_id
        meta: dict[str, Any] = {
            "schema": "poc6_11_run_v1",
            "protocol_id": PR.PROTOCOL_ID,
            "lock_id": lk["lock_id"],
            "run_id": run_id,
            "started_at": store.iso(started),
        }
        bud = Budget(clock, started)
        ctx: dict[str, Any] = (
            {}
        )  # 단계마다 쌓는 결과 — 멈춰도 이미 계산한 지표 · 선택을 보고에 남긴다
        try:
            return _run(rdir, lk, meta, Path(db), clock, bud, ctx)
        except (CheckRequired, BudgetStop) as e:
            status = "BUDGET_STOP" if isinstance(e, BudgetStop) else "CHECK_REQUIRED"
            ctx.pop("judgment", None)
            try:
                return _finish(
                    rdir,
                    meta,
                    bud,
                    clock,
                    status,
                    {**ctx, "stop": f"{type(e).__name__}: {e}"[:500]},
                )
            except (
                BaseException
            ) as w:  # 정지 보고를 쓰다 난 예외도 FAILED 기록(아래 except 는 여기서 난 예외를 받지 않음)
                _record_failure(rdir, meta, bud, clock, w, f"{type(e).__name__}: {e}")
                raise
        except BaseException as e:
            _record_failure(rdir, meta, bud, clock, e)
            raise


def _record_failure(rdir, meta, bud, clock, e, stop: Optional[str] = None) -> None:
    if (rdir / "run.json").exists():
        return
    try:
        finished = store.iso(clock())
    except Exception:  # noqa: BLE001 — 시계 실패가 실패 기록을 막지 않게
        finished = None
    reason = f"{type(e).__name__}: {e}"
    if (
        stop
    ):  # 정지 보고를 쓰다 실패 — 원래 정지 이유를 앞에 남긴다(300자 자름에 잘리지 않게)
        reason = f"정지 보고 중 실패(원래 정지 = {stop}) · {reason}"
    meta.update(
        status="FAILED",
        reason=reason[:300],
        finished_at=finished,
        stages=bud.stages,
    )
    try:  # 실패 실행도 그때까지 만든 근거의 해시 목록을 남긴다(검증 r2 F3)
        meta["files"] = PR.manifest(rdir)
    except OSError as w:
        e.add_note(f"실패 실행 해시 목록을 만들지 못함: {w}")
    try:
        P8.write_once(rdir / "run.json", P8.dumps(meta))
    except Exception as w:  # noqa: BLE001
        e.add_note(f"실패 기록(run.json)도 쓰지 못함: {type(w).__name__}: {w}")


def _finish(rdir, meta, bud, clock, status, rep: dict) -> dict:
    rep = {
        "schema": "poc6_11_report_v1",
        "lock_id": meta["lock_id"],
        "run_id": meta["run_id"],
        "price_note": R.PRICE_NOTE,
        **rep,
    }
    if "judgment" not in rep:
        rep["judgment"] = R.judge(status, None, None)
    data, md = P8.dumps(rep), R.markdown(rep).encode(
        "utf-8"
    )  # 내용을 모두 만든 뒤 쓴다(중간 실패 = 보고 파일 없음)
    P8.write_once(rdir / "report.json", data)
    P8.write_once(rdir / "report.md", md)
    meta.update(status=status, finished_at=store.iso(clock()), stages=bud.stages)
    meta["files"] = PR.manifest(rdir)
    P8.write_once(rdir / "run.json", P8.dumps(meta))
    return {"meta": meta, "report": rep}


def _fit_quarter(
    rdir, p, t, q, struct, plan_rows, bud, clock, phase, fits
) -> dict[str, Any]:
    """한 분기 · 한 구조 학습 → 저장 → 복원 예측 대조 → 배정 신호 예측. 실제 시각 · 가상 정보 시각 기록."""
    ci = p.axis.index(q["cutoff"])
    rows = F.training_rows(t, p.axis, ci)
    weeks = len({t.rows[r][0] for r in rows})
    if weeks != q["weeks"] or len(rows) != q["rows"]:
        raise CheckRequired(
            f"{q['id']} 학습 표본이 잠금과 다름: {weeks}주 · {len(rows)}행"
        )
    X = M.matrix([t.X[r] for r in rows])
    t0 = clock()
    booster = M.train(struct, X, [t.y[r] for r in rows], F.weights(t, rows))
    trained = clock()
    text = M.to_text(booster)
    mid = f"{q['id']}_{struct}"
    P8.write_once(rdir / "models" / f"{mid}.txt", text.encode("utf-8"))
    back = M.restore(text)
    preds: dict[str, dict[str, float]] = {}
    diff = 0.0
    for d, rs in plan_rows.items():
        Xp = M.matrix([t.X[r] for r in rs])
        a, b = M.predict(booster, Xp), M.predict(back, Xp)
        diff = max(diff, float(np.max(np.abs(a - b))))
        preds[d] = {p.codes[t.rows[r][1]]: float(v) for r, v in zip(rs, a)}
    if (
        diff > M.RESTORE_TOL
    ):  # 정지 근거(메모리 예측 · 차이)를 남겨 verify 가 복원 예측과 다시 대조하게 한다
        P8.write_once(
            rdir / "models" / f"{mid}{PR.MISMATCH_SUFFIX}",
            P8.dumps({"id": mid, "diff": diff, "predictions": preds}, compact=True),
        )
        raise CheckRequired(f"{mid} 저장 전후 예측 차이 {diff}")
    rec = {
        "id": mid,
        "phase": phase,
        "quarter": q["id"],
        "struct": struct,
        "cutoff": q["cutoff"],
        "rows": len(rows),
        "weeks": weeks,
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
    fits.append(
        rec
    )  # 기록을 쓴 직후 목록에(예산 정지여도 보고의 fits = 모델 기록 · 검증 r1)
    bud.check(f"fit {mid}")
    return {"rec": rec, "preds": preds}


def _plans(p, t, rows_by_sig, ids, signals, scores) -> dict[int, PO.Plan]:
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


def _books(rdir, sub, p, plans_by_key, w, sig, items, k_idx) -> dict[str, dict]:
    """items = (곡선 이름 · 계획 키(None = K) · 비용) 순서대로. CHECK_REQUIRED 를 만나면 나머지는 열지 않는다."""
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


def _run(rdir, lk, meta, db, clock, bud, ctx) -> dict:
    bud.check("start")
    p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
    if p.seal["file_sha256"] != PR.FILE_SHA:
        raise CheckRequired("봉인 파일 해시 다름")
    fx, el, count, usable = PR.survey(p)
    if store.canonical(fx) != store.canonical(lk["facts"]):
        raise CheckRequired("자격 · 날짜 · 표본 사실이 잠금과 다름")
    diffs = PR.compare(fx)
    if diffs:
        raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
    if fx["data_short"]:
        return _finish(
            rdir, meta, bud, clock, "DATA_SHORT", {"stop": " · ".join(fx["data_short"])}
        )
    sig = el.sig
    P8.write_once(
        rdir / "eligibility.json.gz",
        _gz(
            {
                "reasons": el.reasons,
                "members": {
                    p.axis[i]: [p.codes[j] for j in el.members[i]] for i in sig
                },
                "excluded": {
                    p.axis[i]: {
                        k: [p.codes[j] for j in v] for k, v in el.excluded[i].items()
                    }
                    for i in sig
                },
            }
        ),
    )
    bud.check("panel · eligibility")
    t = F.build_table(
        p, {i: el.members[i] for i in sig if len(el.members[i]) >= D.MIN_ELIGIBLE}
    )
    P8.write_once(
        rdir / "features.json.gz",
        _gz(
            {
                "columns": list(F.COLUMNS),
                "rows": [[p.axis[i], p.codes[j]] for i, j in t.rows],
                "X": t.X,
                "missing": t.missing,
                "z": t.z,
                "y": t.y,
                "usable": {p.axis[i]: t.usable[i] for i in t.sig},
                "label_count": {p.axis[i]: t.label_count[i] for i in t.sig},
            }
        ),
    )
    bud.check("features · labels")
    rows_by_sig: dict[int, list[int]] = {}
    for r, (i, _j) in enumerate(t.rows):
        rows_by_sig.setdefault(i, []).append(r)
    assign = fx["assign"]
    val_w = {
        **fx["val"],
        "start_idx": p.axis.index(fx["val"]["start"]),
        "end_idx": p.axis.index(fx["val"]["end"]),
    }
    test_w = {
        **fx["test"],
        "start_idx": p.axis.index(fx["test"]["start"]),
        "end_idx": p.axis.index(fx["test"]["end"]),
    }
    names = {c: p.series[c].name[-1] for c in p.codes}
    pos = {d: k for k, d in enumerate(p.axis)}
    # ── 검증: 12분기 × ML_A/B ──
    preds: dict[str, dict[str, dict]] = {"ML_A": {}, "ML_B": {}}
    fits: list[dict] = []
    ctx["fits"] = fits
    for q in fx["quarter_detail"]["val"]:
        mine = {
            d: rows_by_sig[p.axis.index(d)]
            for d in fx["val"]["plan_signals"]
            if assign[d] == q["id"]
        }
        for struct in ("ML_A", "ML_B"):
            res = _fit_quarter(rdir, p, t, q, struct, mine, bud, clock, "val", fits)
            preds[struct].update(res["preds"])
    P8.write_once(rdir / "predictions_validation.json", P8.dumps(preds, compact=True))
    P8.write_once(
        rdir / "schedule_validation.json", P8.dumps(PR.schedule(p.axis, fits))
    )

    def ml(src):
        return lambda d, rs: {t.rows[r][1]: src[d][p.codes[t.rows[r][1]]] for r in rs}

    def mom(col):
        return lambda d, rs: PR.scores_for(t, rs, col)

    vsig = fx["val"]["plan_signals"]
    vplans = {
        "ML_A": _plans(
            p, t, rows_by_sig, PR.model_ids(assign, "ML_A"), vsig, ml(preds["ML_A"])
        ),
        "ML_B": _plans(
            p, t, rows_by_sig, PR.model_ids(assign, "ML_B"), vsig, ml(preds["ML_B"])
        ),
        "MOM20": _plans(p, t, rows_by_sig, {}, vsig, mom("RET_20")),
        "MOM120": _plans(p, t, rows_by_sig, {}, vsig, mom("RET_120")),
    }
    k_val = p.axis.index(fx["val"]["k_exec"])
    vbooks = _books(
        rdir,
        "validation",
        p,
        vplans,
        val_w,
        sig,
        [(n, n, PR.BASE_COST) for n in ("ML_A", "ML_B", "MOM20", "MOM120")]
        + [("K", None, PR.BASE_COST)],
        k_val,
    )
    vmet = {n: R.curve(b, val_w["start"], None, pos, names) for n, b in vbooks.items()}
    base = ctx
    base.update(validation=vmet, validation_signal_after_end=_after_end(p, sig, val_w))
    bud.check("validation books")
    if len(vbooks) < 5 or any(b["status"] != "OK" for b in vbooks.values()):
        bad = [n for n, b in vbooks.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {
                **base,
                "stop": f"검증 곡선 평가 미확정 {bad} — 선택 · 시험 미실행(판정 §3-3)",
            },
        )
    # ── 선택 저장(2020-12-30 검증 마지막 평가 뒤 · 2021Q1 학습 전) ──
    sel = R.select(vmet)
    sel["selected_at"] = store.iso(clock())
    P8.write_once(rdir / "selection.json", P8.dumps(sel))
    base["selection"] = sel
    # ── 시험: 선택 구조만 23분기 ──
    tpred: dict[str, dict] = {}
    for q in fx["quarter_detail"]["test"]:
        mine = {
            d: rows_by_sig[p.axis.index(d)]
            for d in fx["test"]["plan_signals"]
            if assign[d] == q["id"]
        }
        res = _fit_quarter(rdir, p, t, q, sel["L"], mine, bud, clock, "test", fits)
        tpred.update(res["preds"])
    P8.write_once(
        rdir / "predictions_test.json", P8.dumps({sel["L"]: tpred}, compact=True)
    )
    P8.write_once(
        rdir / "schedule_test.json",
        P8.dumps(PR.schedule(p.axis, [r for r in fits if r["phase"] == "test"])),
    )
    tsig = fx["test"]["plan_signals"]
    tplans = {
        "L": _plans(p, t, rows_by_sig, PR.model_ids(assign, sel["L"]), tsig, ml(tpred)),
        "B": _plans(
            p,
            t,
            rows_by_sig,
            {},
            tsig,
            mom("RET_20" if sel["B"] == "MOM20" else "RET_120"),
        ),
    }
    k_test = p.axis.index(fx["test"]["k_exec"])
    order = [
        ("L_20", "L", PR.BASE_COST),
        ("B_20", "B", PR.BASE_COST),
        ("K_20", None, PR.BASE_COST),
        ("L_40", "L", PR.ALT_COST),
        ("B_40", "B", PR.ALT_COST),
        ("K_40", None, PR.ALT_COST),
    ]
    tbooks = _books(rdir, "test", p, tplans, test_w, sig, order, k_test)
    tmet = {
        n: R.curve(b, test_w["start"], PR.SUB_RANGES, pos, names)
        for n, b in tbooks.items()
    }
    base.update(test=tmet, test_signal_after_end=_after_end(p, sig, test_w))
    bud.check("test books")
    if len(tbooks) < len(order) or any(b["status"] != "OK" for b in tbooks.values()):
        bad = [n for n, b in tbooks.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {
                **base,
                "stop": f"시험 곡선 평가 미확정 {bad} — H1 · 후보 NOT_JUDGED(판정 §3-3)",
            },
        )
    week_ends = {p.axis[i] for i in sig}
    wl, tail = R.weekly_returns(tbooks["L_20"]["ledger"], week_ends, PO.START_VALUE)
    wb, _ = R.weekly_returns(tbooks["B_20"]["ledger"], week_ends, PO.START_VALUE)
    if [d for d, _ in wl] != [d for d, _ in wb]:
        raise CheckRequired("L · B 주간 날짜가 다름")
    boot = R.bootstrap([a - b for (_, a), (_, b) in zip(wl, wb)])
    base.update(
        bootstrap=boot,
        bootstrap_tail_excluded=tail,
        judgment=R.judge("OK", tmet, boot),
        explain={
            "rank_ic": {k: R.rank_ic(_ic_pairs(t, tplans[k], p)) for k in ("L", "B")}
        },
    )
    return _finish(rdir, meta, bud, clock, "OK", base)


def _after_end(p, sig, w) -> list[str]:
    """평가 끝 뒤에 실행될 정기 신호(평가 안 신호 중 · 예측 없이 미실행 기록 · 판정 §4)."""
    return [
        p.axis[i] for i in sig if w["start_idx"] <= i <= w["end_idx"] < i + F.EXEC_LAG
    ]


def _ic_pairs(t: F.Table, plans: dict[int, PO.Plan], p: D.Panel) -> dict[str, list]:
    zmap = {(i, j): t.z[r] for r, (i, j) in enumerate(t.rows)}
    out = {}
    for i, pl in plans.items():
        out[p.axis[i]] = [
            (s, zmap[(i, j)])
            for j, s in pl.scores.items()
            if zmap.get((i, j)) is not None
        ]
    return out
