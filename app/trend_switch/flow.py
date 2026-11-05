"""POC6-21 prepare/lock · run(선행 재생 → 주 평가) · 실패 기록 · 예산 감시 — 통합 설계 §6 · §7 · PLAN §4 · 판정 §5.

```text
prepare  봉인 확인 → POC6-20 사실(H1 분모 · 시장 4열 · 공통 주) → 절대 정답 네 모수를 PLAN 표(EXPECTED)와 대조
         → protocol.json(정답 크기 · 특징 값 · 순위 · 성과 계산 0 · LightGBM 4.7.0 · OpenMP 순서 확인 뒤에만)
run      잠금과 코드 · 환경 · 사실이 같을 때만 1회 — 선행 재생 12분기 M(12 fit) → R0/R1/M0/M1/K 20bp 장부
         → 하나라도 CHECK_REQUIRED 면 주 평가 미실행 → 주 평가 23분기 M(23 fit) → 5곡선 × 20 · 40bp
         → 거래 분석 · M1_20 − R1_20 주간 bootstrap · 판정 · 보고 글 · 파일 해시까지 계산 → finish 예산 판정 → 쓰기
학습     분기마다 M 1개(절대 정답 · 34열 · ML_B) · R 은 학습 없음 · 정책 · 비용별 재학습 없음
중단     CheckRequired · 예산 초과(BUDGET_STOP) = 그 시점까지 보존 + 보고 · 그 밖의 예외 = run.json FAILED
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.feature_gain import protocol as P8
from app.market_context_value import flow as FW20
from app.market_context_value import market_inputs as MI
from app.ml_evidence import store
from app.trend_switch import protocol as P21
from app.trend_switch import report as RP
from app.trend_switch import study as ST
from app.weekly_selection import data as D
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import BudgetStop, CheckRequired, Refused

runtime_env = FW20.runtime_env
_base = FW20._base
_record_failure = FW20._record_failure


# ── prepare ──────────────────────────────────────────────────────────────────────


def prepare(
    root: Path = P21.ROOT,
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
        if M.env().get("lightgbm") != M.LGB_VERSION:
            raise CheckRequired(
                "LightGBM 4.7.0 환경 확인 전 — 공식 잠금 · 실행을 열지 않음"
            )
        env = runtime_env()
        p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
        if p.seal["file_sha256"] != PR.FILE_SHA:
            raise CheckRequired(f"봉인 파일 해시 다름: {p.seal['file_sha256']}")
        fx, *_ = P21.survey(p, _base(repo, market_base))
        diffs = P21.compare(fx)
        if diffs:
            raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
        code = P21.code_hashes(repo)
        rec = P21.recipe()
        corrects = None
        if prev is not None:
            corrects = _correction(
                prev_dir, prev, fx, rec, code, env, correction_reason
            )
        now = clock()
        lock_id = P8.new_id(now)
        doc = {
            "schema": P21.SCHEMA["protocol"],
            "protocol_id": P21.PROTOCOL_ID,
            "lock_id": lock_id,
            "locked_at": store.iso(now),
            "inputs": {"db": str(Path(db)), **P21.input_refs()},
            "facts": fx,
            "recipe": rec,
            "code": {"sha256": code},
            "env": env,
            "corrects": corrects,
            "note": "prepare 는 정답 크기 · 특징 값 · 순위 · 성과를 계산하지 않는다(PLAN §2 · 판정 §3).",
        }
        P8.write_once(root / lock_id / "protocol.json", P8.dumps(doc))
        return doc


def _correction(prev_dir, prev, fx, rec, code, env, reason) -> dict:
    norm = P8.loads(
        P8.dumps(
            {"inputs": P21.input_refs(), "facts": fx, "recipe": rec}, compact=True
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
    root: Path = P21.ROOT,
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
        if P21.code_hashes(repo) != lk["code"]["sha256"]:
            raise CheckRequired("실행 코드가 잠금과 다름")
        if runtime_env() != lk["env"]:
            raise CheckRequired("환경(LightGBM · libomp · numpy · OS 등)이 잠금과 다름")
        bad = P21.lock_problems(lk)
        if bad:
            raise CheckRequired("잠금과 다름: " + " · ".join(bad))
        started = clock()
        run_id = P8.new_id(started)
        rdir = runs / run_id
        meta: dict[str, Any] = {
            "schema": P21.SCHEMA["run"],
            "protocol_id": P21.PROTOCOL_ID,
            "lock_id": lk["lock_id"],
            "run_id": run_id,
            "started_at": store.iso(started),
        }
        bud = FL.Budget(clock, started)
        ctx: dict[str, Any] = {}
        try:
            return _run(
                rdir, lk, meta, Path(db), _base(repo, market_base), clock, bud, ctx
            )
        except (CheckRequired, BudgetStop) as e:
            status = "BUDGET_STOP" if isinstance(e, BudgetStop) else "CHECK_REQUIRED"
            for k in ST.FINAL_KEYS:  # 정상 완료에만 있는 칸은 멈춘 보고에 남기지 않는다
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
            except BaseException as w:  # 정지 보고를 쓰다 난 예외도 FAILED 기록
                _record_failure(rdir, meta, bud, clock, w, f"{type(e).__name__}: {e}")
                raise
        except BaseException as e:
            _record_failure(rdir, meta, bud, clock, e)
            raise


def _finish(rdir, meta, bud, clock, status, rep: dict) -> dict:
    """보고 · 실행 기록 쓰기. 정상 완료는 모든 계산이 예산 상한 안일 때만(POC6-20 검증자 r1 F1 · r2 F2 교훈).

    순서: 보고 조립 · JSON · report.md 글 · 실행 파일 해시 목록(보고 두 파일 해시는 메모리 값)까지 다 계산한 뒤
    `finish` 단계로 상한을 판정한다 — 넘으면 BudgetStop(→ BUDGET_STOP · NOT_JUDGED). 판정 뒤에는 파일 세 개
    쓰기만 남는다. finished_at = 상태를 정한 시각 · written_at = run.json 을 쓰기 직전 시각.
    """
    rep = {
        "schema": P21.SCHEMA["report"],
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


def _inputs(rdir, p, el, mkt, fx) -> None:
    sig = el.sig
    P8.write_once(
        rdir / "eligibility.json.gz",
        ST.gz(
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
    P8.write_once(
        rdir / "market.json.gz",
        ST.gz(
            {
                "columns": list(MI.COLUMNS),
                "files": fx["market_files"],
                "signals": {p.axis[i]: mkt[i] for i in sig},
            }
        ),
    )


def _phase(rdir, p, t, el, mkt, fx, tag, rows_by_sig, defined, bud, clock, fits):
    preds = ST.phase_fits(
        rdir, p, t, mkt, fx, tag, rows_by_sig, defined, bud, clock, fits
    )
    plans = ST.phase_plans(p, t, el, rows_by_sig, fx, tag, preds)
    w = ST.window(fx, tag, p)
    items = P21.val_books() if tag == "val" else P21.test_books()
    sub = "validation" if tag == "val" else "test"
    k_idx = p.axis.index(fx[tag]["k_exec"])
    books = ST.books(rdir, sub, p, plans, w, items, k_idx)
    bounds = PR.SUB_RANGES if tag == "test" else None
    return books, ST.metrics(p, books, w, bounds), ST.extra(p, books, bounds), items, w


def _run(rdir, lk, meta, db, base, clock, bud, ctx) -> dict:
    bud.check("start")
    p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
    if p.seal["file_sha256"] != PR.FILE_SHA:
        raise CheckRequired("봉인 파일 해시 다름")
    fx, el, _count, _usable, mkt = P21.survey(p, base)
    if store.canonical(fx) != store.canonical(lk["facts"]):
        raise CheckRequired(
            "자격 · 날짜 · 표본 · 시장 4열 · 절대 정답 사실이 잠금과 다름"
        )
    diffs = P21.compare(fx)
    if diffs:
        raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
    ctx["coverage"] = ST.coverage(fx)
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
    _inputs(rdir, p, el, mkt, fx)
    bud.check("panel · eligibility · market")
    t = ST.abs_table(p, el)
    P8.write_once(rdir / "features.json.gz", ST.gz(ST.features_doc(p, t)))
    bud.check("features · labels")
    rows_by_sig = ST.rows_by_signal(t)
    defined = {i for i in sig if mkt[i]["values"] is not None}
    fits: list[dict] = []
    ctx["fits"] = fits
    # ── 선행 재생: 12분기 M · R0/R1/M0/M1/K 20bp ──
    args = (rdir, p, t, el, mkt, fx)
    vb, vmet, vex, items, vw = _phase(
        *args, "val", rows_by_sig, defined, bud, clock, fits
    )
    ctx.update(
        validation=vmet,
        validation_trades=vex,
        validation_signal_after_end=ST.after_end(p, sig, vw),
    )
    bud.check("validation books")
    if len(vb) < len(items) or any(b["status"] != "OK" for b in vb.values()):
        bad = [n for n, b in vb.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {**ctx, "stop": ST.VAL_STOP.format(bad=bad)},
        )
    # ── 주 평가: 23분기 M · 5곡선 × 20 · 40bp ──
    tb, tmet, tex, items, tw = _phase(
        *args, "test", rows_by_sig, defined, bud, clock, fits
    )
    ctx.update(
        test=tmet, test_trades=tex, test_signal_after_end=ST.after_end(p, sig, tw)
    )
    bud.check("test books")
    if len(tb) < len(items) or any(b["status"] != "OK" for b in tb.values()):
        bad = [n for n, b in tb.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {**ctx, "stop": ST.TEST_STOP.format(bad=bad)},
        )
    boot, tail = ST.pair_bootstrap(p, sig, tb)
    ctx.update(
        bootstrap=boot,
        bootstrap_tail_excluded=tail,
        judgment=RP.judge("OK", tmet, boot, RP.opportunities(tex)),
    )
    return _finish(rdir, meta, bud, clock, "OK", ctx)
