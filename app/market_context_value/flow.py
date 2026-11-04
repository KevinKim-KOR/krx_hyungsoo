"""POC6-20 prepare/lock · run(선행 재생 → 주 평가) · 실패 기록 · 예산 감시 — 설계 §5 ~ §7 · PLAN §3 · 판정 §3 · §4.

```text
prepare  봉인 확인 → H1 분모 → 시장 4열 → 공통 분모를 PLAN 표(EXPECTED)와 대조 → protocol.json
         (정답 크기 · 특징 값 · 순위 · 성과 계산 0 · LightGBM 4.7.0 · OpenMP 순서 확인 뒤에만)
run      잠금과 코드 · 환경 · 사실이 같을 때만 1회 — 선행 재생 12분기 × P/M(24 fit) → P/M/B/K 20bp 장부
         → 하나라도 CHECK_REQUIRED 면 주 평가 미실행 → 주 평가 23분기 × P/M(46 fit) → P/M/B/K × 20 · 40bp
         → M_20 − P_20 주간 bootstrap → 판정 · 보고(선택 단계 없음 · 성과로 멈추거나 바꾸지 않음)
학습     P 와 M 은 같은 행(공통 날짜 · H1 학습 규칙) · 같은 정답 · 같은 가중치 · M 만 시장 4열을 30열 뒤에 붙인다
중단     CheckRequired · 예산 초과(BUDGET_STOP) = 그 시점까지 보존 + 보고 · 그 밖의 예외 = run.json FAILED
```
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Optional


from app.feature_gain import protocol as P8
from app.market_context_value import market_inputs as MI
from app.market_context_value import protocol as P20
from app.market_context_value import report as RP
from app.market_context_value import study as ST
from app.ml_evidence import store
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R
from app.weekly_selection.protocol import BudgetStop, CheckRequired, Refused

_sha = P20._sha


def runtime_env() -> dict[str, Any]:
    """H1 환경 확인(LightGBM · OpenMP 순서) + 실행 OS 판 · libomp 실제 로드 순서(판정 §6 · 비트 재현 보증 아님)."""
    return {
        **FL.runtime_env(),
        "macos": platform.mac_ver()[0] or None,
        "libomp_load_order": M.libomp_in_load_order(),
    }


def _base(repo: Path, market_base: Optional[Path]) -> Path:
    return Path(market_base) if market_base is not None else Path(repo) / MI.RESEARCH


# ── prepare ──────────────────────────────────────────────────────────────────────


def prepare(
    root: Path = P20.ROOT,
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
        fx, *_ = P20.survey(p, _base(repo, market_base))
        diffs = P20.compare(fx)
        if diffs:
            raise CheckRequired("PLAN 표와 다름: " + " · ".join(diffs)[:1500])
        code = P20.code_hashes(repo)
        rec = P20.recipe()
        corrects = None
        if prev is not None:
            norm = P8.loads(
                P8.dumps(
                    {"inputs": P20.input_refs(), "facts": fx, "recipe": rec},
                    compact=True,
                ).decode()
            )
            for key, what in (
                ("inputs", "입력"),
                ("facts", "사실"),
                ("recipe", "recipe"),
            ):
                mine = norm[key]
                theirs = (
                    {k: prev["inputs"].get(k) for k in mine}
                    if key == "inputs"
                    else prev[key]
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
            "schema": P20.SCHEMA["protocol"],
            "protocol_id": P20.PROTOCOL_ID,
            "lock_id": lock_id,
            "locked_at": store.iso(now),
            "inputs": {"db": str(Path(db)), **P20.input_refs()},
            "facts": fx,
            "recipe": rec,
            "code": {"sha256": code},
            "env": env,
            "corrects": corrects,
            "note": "prepare 는 정답 크기 · 특징 값 · 순위 · 성과를 계산하지 않는다(설계 §9 · PLAN §2).",
        }
        P8.write_once(root / lock_id / "protocol.json", P8.dumps(doc))
        return doc


# ── run ──────────────────────────────────────────────────────────────────────────


def run(
    root: Path = P20.ROOT,
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
                "공식 실행이 이미 있음(성과 때문의 재실행 금지 · 코드 정정은 설계자 판정)"
            )
        if P20.code_hashes(repo) != lk["code"]["sha256"]:
            raise CheckRequired("실행 코드가 잠금과 다름")
        if runtime_env() != lk["env"]:
            raise CheckRequired("환경(LightGBM · libomp · numpy · OS 등)이 잠금과 다름")
        bad = P20.lock_problems(lk)
        if bad:
            raise CheckRequired("잠금과 다름: " + " · ".join(bad))
        started = clock()
        run_id = P8.new_id(started)
        rdir = runs / run_id
        meta: dict[str, Any] = {
            "schema": P20.SCHEMA["run"],
            "protocol_id": P20.PROTOCOL_ID,
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
            for (
                k
            ) in (
                ST.FINAL_KEYS
            ):  # 정상 완료에만 있는 칸(판정 · bootstrap · 설명)은 멈춘 보고에 남기지 않는다
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


def _record_failure(rdir, meta, bud, clock, e, stop: Optional[str] = None) -> None:
    if (rdir / "run.json").exists():
        return
    try:
        finished = store.iso(clock())
    except Exception:  # noqa: BLE001 — 시계 실패가 실패 기록을 막지 않게
        finished = None
    reason = f"{type(e).__name__}: {e}"
    if stop:
        reason = f"정지 보고 중 실패(원래 정지 = {stop}) · {reason}"
    meta.update(
        status="FAILED", reason=reason[:300], finished_at=finished, stages=bud.stages
    )
    # 보고를 쓰다 실패하면 남은 보고 파일은 유효한 판정이 아니다 — 남았다는 사실을 기록한다(verify 도 문제로 남김)
    left = [f for f in ("report.json", "report.md") if (rdir / f).exists()]
    if left:
        meta["report_files_left_invalid"] = left
    try:
        meta["files"] = PR.manifest(rdir)
    except OSError as w:
        e.add_note(f"실패 실행 해시 목록을 만들지 못함: {w}")
    try:
        P8.write_once(rdir / "run.json", P8.dumps(meta))
    except Exception as w:  # noqa: BLE001
        e.add_note(f"실패 기록(run.json)도 쓰지 못함: {type(w).__name__}: {w}")


def _finish(rdir, meta, bud, clock, status, rep: dict) -> dict:
    """보고 · 실행 기록 쓰기. 정상 완료는 모든 계산이 예산 상한 안일 때만(검증자 r1 F1 · r2 F2).

    순서: 보고 조립 · JSON · report.md 글 · 실행 파일 해시 목록(보고 두 파일 해시는 메모리 값)까지 다 계산한 뒤
    `finish` 단계로 상한을 판정한다 — 넘으면 BudgetStop(→ BUDGET_STOP · NOT_JUDGED). 판정 뒤에는 파일 세 개
    쓰기만 남는다. finished_at = 상태를 정한 시각(정상 완료 = finish 단계 기록 시각) · written_at = run.json 을
    쓰기 직전 시각(보고 두 파일을 쓴 뒤).
    """
    rep = {
        "schema": P20.SCHEMA["report"],
        "lock_id": meta["lock_id"],
        "run_id": meta["run_id"],
        "note": RP.NOTE,
        "price_note": R.PRICE_NOTE,
        **rep,
    }
    if "judgment" not in rep:
        rep["judgment"] = RP.judge(status, None, None)
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


def _run(rdir, lk, meta, db, base, clock, bud, ctx) -> dict:
    bud.check("start")
    p = D.build_panel(db, PR.VERSION, PR.CONTENT_SHA)
    if p.seal["file_sha256"] != PR.FILE_SHA:
        raise CheckRequired("봉인 파일 해시 다름")
    fx, el, _count, _usable, mkt = P20.survey(p, base)
    if store.canonical(fx) != store.canonical(lk["facts"]):
        raise CheckRequired("자격 · 날짜 · 표본 · 시장 4열 사실이 잠금과 다름")
    diffs = P20.compare(fx)
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
    bud.check("panel · eligibility · market")
    t = F.build_table(
        p, {i: el.members[i] for i in sig if len(el.members[i]) >= D.MIN_ELIGIBLE}
    )
    P8.write_once(
        rdir / "features.json.gz",
        ST.gz(
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
    defined = {i for i in sig if mkt[i]["values"] is not None}
    names = {c: p.series[c].name[-1] for c in p.codes}
    pos = {d: k for k, d in enumerate(p.axis)}
    fits: list[dict] = []
    ctx["fits"] = fits
    # ── 선행 재생: 12분기 × P/M · P/M/B/K 20bp ──
    val_w = ST.window(fx, "val", p)
    vpred = ST.phase_fits(
        rdir, p, t, mkt, fx, "val", rows_by_sig, defined, bud, clock, fits
    )
    vplans = ST.phase_plans(p, t, rows_by_sig, fx, "val", vpred)
    items = P20.val_books()
    vbooks = ST.books(
        rdir, "validation", p, vplans, val_w, sig, items, pos[fx["val"]["k_exec"]]
    )
    ctx["validation"] = {
        n: R.curve(b, val_w["start"], None, pos, names) for n, b in vbooks.items()
    }
    ctx["validation_signal_after_end"] = ST.after_end(p, sig, val_w)
    bud.check("validation books")
    if len(vbooks) < len(items) or any(b["status"] != "OK" for b in vbooks.values()):
        bad = [n for n, b in vbooks.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {
                **ctx,
                "stop": ST.VAL_STOP.format(bad=bad),
            },
        )
    # ── 주 평가: 23분기 × P/M · P/M/B/K × 20 · 40bp ──
    test_w = ST.window(fx, "test", p)
    tpred = ST.phase_fits(
        rdir, p, t, mkt, fx, "test", rows_by_sig, defined, bud, clock, fits
    )
    tplans = ST.phase_plans(p, t, rows_by_sig, fx, "test", tpred)
    items = P20.test_books()
    tbooks = ST.books(
        rdir, "test", p, tplans, test_w, sig, items, pos[fx["test"]["k_exec"]]
    )
    tmet = {
        n: R.curve(b, test_w["start"], PR.SUB_RANGES, pos, names)
        for n, b in tbooks.items()
    }
    ctx.update(test=tmet, test_signal_after_end=ST.after_end(p, sig, test_w))
    bud.check("test books")
    if len(tbooks) < len(items) or any(b["status"] != "OK" for b in tbooks.values()):
        bad = [n for n, b in tbooks.items() if b["status"] != "OK"]
        return _finish(
            rdir,
            meta,
            bud,
            clock,
            "CHECK_REQUIRED",
            {
                **ctx,
                "stop": ST.TEST_STOP.format(bad=bad),
            },
        )
    boot, tail = ST.pair_bootstrap(p, sig, tbooks)
    ctx.update(
        bootstrap=boot,
        bootstrap_tail_excluded=tail,
        judgment=RP.judge("OK", tmet, boot),
        explain={
            "rank_ic": {
                k: R.rank_ic(ST.ic_pairs(t, tplans[k], p)) for k in ("P", "M", "B")
            }
        },
    )
    return _finish(rdir, meta, bud, clock, "OK", ctx)
