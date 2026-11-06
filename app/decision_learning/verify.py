"""POC6-23 verify — 저장 산출물에서 다시 계산(재학습 · 외부 조회 없음) · 필수 근거 계약 — 통합 설계 V1 개정 2 §6-2.

```text
잠금     식별자 · 입력 · recipe · 코드 해시 · 환경 · 실행 파일 목록 · 한 잠금 아래 실행 1회 · 단계 기록(POC6-20 계약)
사실     봉인 판 → POC6-20 사실 → 공통 신호 · 분기 창을 다시 세어 잠금 facts 와 같은지
자료     eligibility · market(POC6-20 검산) · features(30열) 재계산 대조
참조     R0 참조 루프 다시 · 저장 장부 · POC6-21 simulate 와 같은지 · POC6-21 독립 손검산 · 정답(분기 g) 다시 계산 대조
모형     분기 유효 D · 표준화 통계 · s_g · 행을 다시 · 저장 해(x)로 목적 · 위반 · 직접 손실 · 절대 차이 다시(재학습 없음)
         · 수치 조건 · β = x⁺ − x⁻ · 정상 완료 = 35분기 전부
장부     저장 모형으로 정책 재적용 = 저장 장부 · P/S 독립 손검산(audit) · R = POC6-21 감사 · K = H1 감사
보고     지표 · 거래 분석 · 학습 · 참조 요약 · bootstrap · 판정 · report.md 재계산 · 정지 주장 · 파일 계약
```
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.decision_learning import audit as AU
from app.decision_learning import flow as FW
from app.decision_learning import labels as LB
from app.decision_learning import learn as LN
from app.decision_learning import protocol as P23
from app.decision_learning import report as RP
from app.feature_gain import protocol as P8
from app.market_context_value import evidence as EV20
from app.market_context_value import study as S20
from app.market_context_value import verify as VR20
from app.ml_evidence import store
from app.trend_switch import audit as AU21
from app.trend_switch import study as ST21
from app.weekly_selection import audit as AU1
from app.weekly_selection import data as D
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R

CheckRequired = D.CheckRequired
_guard, _load, _same, _norm = VR20._guard, VR20._load, VR20._same, VR20._norm
FIXED = {
    "eligibility.json.gz",
    "market.json.gz",
    "features.json.gz",
    "reference.json",
    "labels.json.gz",
    "report.json",
    "report.md",
}
REPORT_KEYS = {
    "schema",
    "lock_id",
    "run_id",
    "note",
    "price_note",
    "coverage",
    "stop",
    "reference",
    "learning",
    "validation",
    "validation_trades",
    "validation_signal_after_end",
    "test",
    "test_trades",
    "test_signal_after_end",
    "bootstrap",
    "bootstrap_tail_excluded",
    "judgment",
}
_MODEL = re.compile(r"^models/(\d{4}Q[1-4])\.json$")
_NUMERIC = re.compile(r"^CheckRequired: (\d{4}Q[1-4]) 수치 조건: ")
_MEASURED = (
    "fun_raw",
    "c_fixed",
    "lp_full",
    "fun_recomputed",
    "l1",
    "l1_excess",
    "max_violation",
    "bound_violation",
    "rows",
    "dates",
    "direct",
    "abs_diff",
    "upper_margin",
)


def verify(
    root: Path = P23.ROOT,
    db: Path = PR.DB,
    repo: Path = Path("."),
    run_id: Optional[str] = None,
    clock=store.utc_now,
    market_base: Optional[Path] = None,
) -> dict:
    ldir, lk, rdir = PR.latest_run(Path(root), run_id)
    out: list[str] = []
    meta = _guard(out, "run.json", _load, rdir / "run.json") or {}
    status = meta.get("status")
    out += [f"잠금: {x}" for x in P23.lock_problems(lk)]
    if P23.code_hashes(repo) != lk["code"]["sha256"]:
        out.append("코드 ≠ 잠금 코드")
    if P23.runtime_env() != lk["env"]:
        out.append("환경 ≠ 잠금 환경")
    if meta.get("env") != lk["env"]:
        out.append("run.json 실행 환경 ≠ 잠금 환경")
    _guard(out, "식별자", identity_problems, lk, meta, ldir, rdir)
    if PR.manifest(rdir) != meta.get("files"):
        out.append("실행 폴더 파일 해시 ≠ run.json 파일 목록")
    _guard(out, "단계", EV20.stage_problems, meta)
    s = _guard(out, "사실", _survey, db, repo, market_base, lk)
    if s is None:
        return _record(ldir, rdir, out, status, clock)
    p, fx, el, mkt, common = s
    _guard(out, "파일", files_problems, fx, rdir, status)
    rep = None
    if (rdir / "report.json").exists():
        rep = _guard(out, "report.json", _load, rdir / "report.json")
    res: dict[str, Any] = {
        "labels": None,
        "docs": {},
        "books": {},
        "ref": None,
        "repro": [],  # 다시 계산에서 같은 CHECK_REQUIRED 가 재현된 정지 문구
    }
    if status != "DATA_SHORT":
        _guard(out, "자격 · 시장", VR20._check_inputs, p, el, mkt, fx, rdir)
        built = _guard(out, "특징", _build, p, el, mkt, fx, common, rdir, res)
        ref = None
        if built is not None:
            plans = built
            ref = _guard(
                out, "참조 · 정답", _check_reference, p, el, fx, plans, rdir, res
            )
        if ref is not None:
            res["ref"], res["labels"] = ref
            args = (p, fx, common, plans, res["labels"], rdir, status, res)
            res["docs"] = _guard(out, "모형", _check_models, *args) or {}
            res["books"] = (
                _guard(
                    out,
                    "장부",
                    _check_books,
                    p,
                    el,
                    fx,
                    plans,
                    res["docs"],
                    rdir,
                    status,
                    res,
                )
                or {}
            )
        if status == "CHECK_REQUIRED" and _complete(res, fx):
            _try(res, FW.pair_bootstrap, p, el.sig, res["books"]["test"])
    vstat = {n: b["status"] for n, b in (res["books"].get("val") or {}).items()}
    tstat = {n: b["status"] for n, b in (res["books"].get("test") or {}).items()}
    _guard(
        out,
        "정지 주장",
        stop_problems,
        lk,
        meta,
        rep,
        rdir,
        vstat,
        tstat,
        res,
        p,
        fx,
        common,
    )
    if rep is not None:
        _guard(out, "보고 칸", report_meta_problems, p, el.sig, fx, lk, meta, rdir, rep)
        if status not in ("DATA_SHORT",) and res["labels"] is not None:
            _guard(
                out, "보고 값", _check_report, p, el.sig, fx, common, rep, status, res
            )
    return _record(ldir, rdir, out, status, clock)


def _survey(db, repo, market_base, lk):
    p = D.build_panel(Path(db), PR.VERSION, PR.CONTENT_SHA)
    fx, el, mkt, common = P23.survey(p, FW._base(repo, market_base))
    if not _same(fx, lk["facts"]):
        return ["다시 센 사실 ≠ 잠금 facts"], None
    return [], (p, fx, el, mkt, common)


def _record(ldir, rdir, problems, status, clock) -> dict:
    now = clock()
    doc = {
        "schema": "poc6_23_verify_v1",
        "run_id": rdir.name,
        "verified_at": store.iso(now),
        "run_status": status,
        "status": "OK" if not problems else "MISMATCH",
        "problems": problems,
    }
    P8.write_once(ldir / "verify" / f"{rdir.name}_{P8.new_id(now)}.json", P8.dumps(doc))
    return doc


def _try(res, fn, *args):
    """다시 계산이 CHECK_REQUIRED 로 멈추면 그 문구를 재현 목록에 남긴다(실행 정지 문구와 같은 형식)."""
    try:
        return fn(*args)
    except CheckRequired as e:
        res["repro"].append(f"CheckRequired: {e}"[:500])
        return None


def _complete(res, fx) -> bool:
    """참조 · 정답 · 모든 분기 모형 · 선행 · 주 평가 장부가 다 있고 정상인가(일반 정지 재현 확인용)."""
    ids = {q["id"] for q in fx["quarter_detail"]}
    bk = res["books"]
    return (
        res["labels"] is not None
        and set(res["docs"]) == ids
        and all(not LN.check(d[k]) for d in res["docs"].values() for k in P23.KINDS)
        and len(bk.get("val") or {}) == len(P23.val_books())
        and len(bk.get("test") or {}) == len(P23.test_books())
        and all(b["status"] == "OK" for t in bk.values() for b in t.values())
    )


def _build(p, el, mkt, fx, common, rdir, res):
    t = _try(res, FW.table, p, el)
    if t is None:
        return [], None
    f = rdir / "features.json.gz"
    out = []
    if f.exists() and not _same(PR.read_gz(f), _norm(FW.features_doc(p, t))):
        out.append("features.json.gz ≠ 다시 만든 30열")
    rows_by_sig = ST21.rows_by_signal(t)
    return out, _try(res, FW.dplans, p, t, el, mkt, rows_by_sig, common, fx["assign"])


def _audit_ctx(p, el, plans, sigs, assign) -> dict[str, Any]:
    members = {i: el.members[i] for i in sigs}
    return {
        "cands": AU21.candidates(p, members, sigs),
        "outs": AU21.excluded(p, el, sigs),
        "members": {p.axis[i]: {p.codes[j] for j in el.members[i]} for i in sigs},
        "rows": {
            p.axis[i]: {p.codes[j]: v for j, v in plans[i].rows.items()} for i in sigs
        },
        "assign": assign,
        "scores_r": AU21.r_scores(p, members, sigs),
    }


def _check_reference(p, el, fx, plans, rdir, res):
    out: list[str] = []
    f = rdir / "reference.json"
    start, last, end = FW.ref_bounds(p, fx)
    common = [i for i in sorted(plans) if start <= i <= last]
    ref_plans = {i: plans[i] for i in common}
    got = _try(res, LB.reference, p, ref_plans, start, end, PR.BASE_COST)
    if not f.exists() or got is None:
        if f.exists():
            out.append("reference.json 이 있는데 다시 돈 참조 경로가 멈춤")
        return out, None
    saved = PR.load_json(f)
    bk, states = got
    js = PO.to_json(bk)
    if not _same(js, saved):
        out.append("reference.json ≠ 다시 돈 R0 참조 경로")
    if js["status"] != "OK":
        res["repro"].append(
            f"CheckRequired: R0 참조 경로 평가 미확정({js['end'].get('stopped_at')})"[
                :500
            ]
        )
    same = LB.reference_same(p, ref_plans, start, end, PR.BASE_COST, bk)
    if not same:
        out.append("R0 참조 루프 ≠ POC6-21 simulate(R0)")
        res["repro"].append(
            "CheckRequired: R0 참조 루프 장부 ≠ POC6-21 simulate(R0) 장부"
        )
    ctx = _audit_ctx(p, el, plans, common, fx["assign"])
    out += [
        f"참조 {x}"
        for x in AU21.audit_book(
            p, saved, ctx["scores_r"], ctx["cands"], ctx["outs"], False, start, end
        )
    ]
    if js["status"] != "OK" or not same:
        return out, ((js, same, len(states)), None)
    labels_doc = _try(res, LB.labels, p, ref_plans, states, PR.BASE_COST)
    f = rdir / "labels.json.gz"
    if labels_doc is None:
        if f.exists():
            out.append("labels.json.gz 가 있는데 다시 계산한 정답이 멈춤")
        return out, ((js, same, len(states)), None)
    if f.exists() and not _same(PR.read_gz(f), _norm(labels_doc)):
        out.append("labels.json.gz ≠ 다시 계산한 분기 정답")
    return out, ((js, same, len(states)), labels_doc)


def _check_models(p, fx, common, plans, labels_doc, rdir, status, res):
    out: list[str] = []
    docs: dict[str, dict] = {}
    if labels_doc is None:
        return out, docs
    qs = fx["quarter_detail"]
    for q in qs:
        f = rdir / "models" / f"{q['id']}.json"
        if not f.exists():
            if (
                status == "CHECK_REQUIRED"
            ):  # 기록 없는 첫 분기 = 그 학습 문제를 다시 만들어 정지 재현
                ds, _ex = FW.window_dates(p, common, q, labels_doc)
                if len(ds) >= P23.MIN_DATES:
                    _try(res, FW.problem, p, plans, labels_doc, ds)
            break
        doc = PR.load_json(f)
        docs[q["id"]] = doc
        ds, ex = FW.window_dates(p, common, q, labels_doc)
        pb, meta = FW.problem(p, plans, labels_doc, ds)
        mine = {
            "quarter": q["id"],
            "phase": q["phase"],
            "cutoff": q["cutoff"],
            "lo": q["lo"],
            "upper": q["upper"],
            "excluded": ex,
            **meta,
        }
        if not _same({k: doc.get(k) for k in mine}, _norm(mine)):
            out.append(f"{q['id']} 학습 D · 표준화 · s_g · 행 ≠ 다시 계산")
        for kind in P23.KINDS:
            rec = doc.get(kind) or {}
            x = rec.get("x")
            if x is None:  # 해 없는 solver 실패 정지는 정지 주장 검사가 확인한다
                if status == "OK":
                    out.append(f"{q['id']} {kind} 해 없음")
                continue
            xa = np.asarray(x, dtype=float)
            beta = xa[: LN.NB] - xa[LN.NB : 2 * LN.NB]  # noqa: E203
            if not _same(rec.get("beta"), _norm(beta.tolist())):
                out.append(f"{q['id']} {kind} β ≠ x⁺ − x⁻")
            again = LN.measure(pb, kind, xa, rec["fun_raw"])
            if not _same({k: rec.get(k) for k in again}, _norm(again)):
                out.append(
                    f"{q['id']} {kind} 목적 · 위반 · 직접 손실 ≠ 저장 해로 다시 잰 값"
                )
            if (
                status == "OK"
            ):  # 수치 실패로 멈춘 실행은 그 실패가 정지 사유다(정지 주장 검사)
                out += [f"{q['id']} {x}" for x in LN.check(rec)]
    want = {q["id"] for q in qs}
    if status == "OK" and set(docs) != want:
        out.append(f"정상 완료인데 모형 기록 {len(docs)} ≠ {len(want)}")
    return out, docs


def _check_books(p, el, fx, plans, docs, rdir, status, rv):
    out: list[str] = []
    res: dict[str, Any] = {}
    ids = {q["id"] for q in fx["quarter_detail"]}
    ready = set(docs) == ids  # 모든 분기 모형이 있어야 장부 단계가 시작된다
    models = FW.models_for_books(docs) if docs else {}
    pos = {d: k for k, d in enumerate(p.axis)}
    for tag, sub, items in (
        ("val", "validation", P23.val_books()),
        ("test", "test", P23.test_books()),
    ):
        have = [(rdir / sub / f"{n}.json").exists() for n, _k, _c in items]
        prev_ok = tag == "val" or (
            len(res.get("val") or {}) == len(P23.val_books())
            and all(b["status"] == "OK" for b in res["val"].values())
        )
        if not any(have) and not (status == "CHECK_REQUIRED" and ready and prev_ok):
            continue
        w = S20.window(fx, tag, p)
        k_idx = pos[fx[tag]["k_exec"]]
        s_i, e_i = w["start_idx"], w["end_idx"]
        sigs = [pos[d] for d in w["plan_signals"]]
        ctx = _audit_ctx(p, el, plans, sigs, fx["assign"])
        bplans = {i: plans[i] for i in sigs}
        again: dict[str, dict] = {}
        for name, key, cost in items:
            f = rdir / sub / f"{name}.json"
            if not f.exists():
                if (
                    status == "CHECK_REQUIRED" and ready
                ):  # 첫 빠진 장부 = 다시 돌려 정지 재현
                    _try(rv, FW.simulate, p, bplans, models, key, w, cost, name, k_idx)
                break
            saved = PR.load_json(f)
            if key == "K":
                probs = AU1.audit_k(p, saved, k_idx, s_i, e_i)
            elif key == "R":
                probs = AU21.audit_book(
                    p,
                    saved,
                    ctx["scores_r"],
                    ctx["cands"],
                    ctx["outs"],
                    False,
                    s_i,
                    e_i,
                )
            else:
                probs = AU.audit_book(
                    p, saved, ctx, models, key, ctx["scores_r"], s_i, e_i
                )
            out += [f"{tag} {name}: {x}" for x in probs]
            if key in ("P", "S") and not models:
                out.append(f"{tag} {name}: 모형 기록 없이 장부가 있음")
                continue
            js = PO.to_json(FW.simulate(p, bplans, models, key, w, cost, name, k_idx))
            if not _same(js, saved):
                out.append(f"{tag} {name}: 정책 재적용 ≠ 저장 장부")
            again[name] = js
        res[tag] = again
    return out, res


# ── 필수 근거 계약 ──────────────────────────────────────────────────────────────


def _book_files() -> set[str]:
    return {f"validation/{n}.json" for n, _k, _c in P23.val_books()} | {
        f"test/{n}.json" for n, _k, _c in P23.test_books()
    }


def files_problems(fx: dict, rdir: Path, status: str) -> list[str]:
    out = []
    ids = {q["id"] for q in fx["quarter_detail"]}
    rels = sorted(
        str(f.relative_to(rdir)) for f in Path(rdir).rglob("*") if f.is_file()
    )
    books = _book_files()

    def ok(rel: str) -> bool:
        if rel in FIXED or rel in books or rel == "run.json":
            return True
        m = _MODEL.match(rel)
        return bool(m) and m.group(1) in ids

    outside = [r for r in rels if not ok(r)]
    if outside:
        out.append(f"계약 밖 파일: {outside[:5]}")
    have = set(rels)
    if status == "OK":
        miss = sorted((FIXED | books | {f"models/{i}.json" for i in ids}) - have)
        if miss:
            out.append(f"정상 완료인데 필수 근거 없음: {miss[:5]}")
    if status in (
        "OK",
        "CHECK_REQUIRED",
        "BUDGET_STOP",
        "DATA_SHORT",
        "INSUFFICIENT_DATA",
    ):
        gone = sorted({"report.json", "report.md"} - have)
        if gone:
            out.append(f"상태 {status} 인데 보고 파일 없음: {gone}")
    if status == "DATA_SHORT":
        extra = sorted(have - {"run.json", "report.json", "report.md"})
        if extra:
            out.append(f"DATA_SHORT 인데 계산 산출물이 있음: {extra[:5]}")
    elif status == "INSUFFICIENT_DATA":
        extra = sorted(
            r for r in have if r.startswith(("models/", "validation/", "test/"))
        )
        if extra:
            out.append(f"INSUFFICIENT_DATA 인데 모형 · 장부가 있음: {extra[:5]}")
    elif status == "FAILED":
        left = sorted(have & {"report.json", "report.md"})
        if left:
            out.append(f"실패 실행에 보고 파일이 남음(유효한 판정 아님): {left}")
    return out


def _short(p, fx, common, labels_doc) -> list[str]:
    out = []
    for q in fx["quarter_detail"]:
        ds, _ex = FW.window_dates(p, common, q, labels_doc)
        if len(ds) < P23.MIN_DATES:
            out.append(f"{q['id']} {len(ds)}")
    return out


def stop_problems(lk, meta, rep, rdir, vstat, tstat, res, p, fx, common) -> list[str]:
    out = []
    status = meta.get("status")
    stop = (rep or {}).get("stop")
    test_made = (rdir / "test").exists()
    vbad = [n for n, s in vstat.items() if s != "OK"]
    if test_made and (len(vstat) < len(P23.val_books()) or vbad):
        out.append("선행 재생 장부가 모두 OK 가 아닌데 주 평가 장부가 있음")
    if rep is None:
        return out
    if status == "OK":
        if "stop" in rep:
            out.append("정상 완료 보고에 정지 문구가 있음")
        return out
    if not isinstance(stop, str):
        return out + [f"정지 문구 없음(상태 {status})"]
    if status == "DATA_SHORT":
        short = lk["facts"].get("data_short") or []
        if not short or stop != " · ".join(short):
            out.append("DATA_SHORT 근거 없음(잠금 사실의 부족 기록과 다름)")
    elif status == "INSUFFICIENT_DATA":
        short = (
            _short(p, fx, common, res["labels"]) if res["labels"] is not None else []
        )
        if not short or stop != FW.SHORT_STOP.format(bad=short):
            out.append("INSUFFICIENT_DATA 정지 문구 ≠ 다시 센 분기 유효 D")
    elif status == "CHECK_REQUIRED":
        if stop.startswith(FW.VAL_STOP.split("{")[0]):
            if not vbad or stop != FW.VAL_STOP.format(bad=vbad) or test_made:
                out.append("선행 재생 정지 문구 ≠ 다시 적용한 선행 재생 장부 상태")
        elif stop.startswith(FW.TEST_STOP.split("{")[0]):
            tbad = [n for n, s in tstat.items() if s != "OK"]
            if vbad or not tbad or stop != FW.TEST_STOP.format(bad=tbad):
                out.append("주 평가 정지 문구 ≠ 다시 적용한 주 평가 장부 상태")
        elif not stop.startswith("CheckRequired: "):
            out.append("정지 문구 형식 ≠ CHECK_REQUIRED")
        elif not _NUMERIC.match(stop) and stop not in res["repro"]:
            out.append("일반 정지 문구를 저장 자료에서 다시 계산해 재현하지 못함")
        elif m := _NUMERIC.match(stop):
            qid, docs = m.group(1), res["docs"]
            ids = [q["id"] for q in fx["quarter_detail"]]
            doc = docs.get(qid)
            if doc is None or not any(LN.check(doc[k]) for k in P23.KINDS):
                out.append("수치 조건 정지 문구 ≠ 저장 모형의 수치 조건")
            elif any(ids.index(k) > ids.index(qid) for k in docs) or test_made:
                out.append("수치 조건 정지 뒤의 모형 · 장부가 있음")
        elif vbad or any(s != "OK" for s in tstat.values()):
            out.append("장부 미확정인데 장부 정지 문구가 아닌 일반 정지 문구")
    elif status == "BUDGET_STOP":
        last = (meta.get("stages") or [{}])[-1].get("stage")
        if not stop.startswith(f"BudgetStop: {last}:"):
            out.append("BUDGET_STOP 정지 문구 ≠ 마지막 단계 기록")
    return out


def identity_problems(lk: dict, meta: dict, ldir: Path, rdir: Path) -> list[str]:
    out = []
    runs = [d for d in (Path(ldir) / "runs").iterdir() if d.is_dir()]
    if len(runs) != 1:
        out.append(f"한 잠금 아래 실행이 {len(runs)}개(공식 실행 1회)")
    if (
        meta.get("schema") != P23.SCHEMA["run"]
        or meta.get("protocol_id") != P23.PROTOCOL_ID
        or meta.get("lock_id") != lk.get("lock_id")
        or meta.get("run_id") != Path(rdir).name
    ):
        out.append("run.json 식별자(schema · protocol · 잠금 · 실행 id) ≠ 잠금 · 폴더")
    return out


def report_meta_problems(p, sig, fx, lk, meta, rdir, rep) -> list[str]:
    out = []
    extra = sorted(set(rep) - REPORT_KEYS)
    if extra:
        out.append(f"report.json 계약 밖 칸: {extra}")
    if (
        rep.get("schema") != P23.SCHEMA["report"]
        or rep.get("lock_id") != lk.get("lock_id")
        or rep.get("run_id") != Path(rdir).name
        or rep.get("note") != RP.NOTE
        or rep.get("price_note") != R.PRICE_NOTE
    ):
        out.append("report.json 식별자 · 의미 문구 다름")
    if meta.get("status") == "OK":
        need = sorted(REPORT_KEYS - {"stop"} - set(rep))
        if need:
            out.append(f"정상 완료 report.json 필수 칸 없음: {need}")
    if "coverage" in rep and not _same(rep["coverage"], _norm(S20.coverage(fx))):
        out.append("report.json coverage ≠ 잠금 사실")
    for tag, key in (
        ("val", "validation_signal_after_end"),
        ("test", "test_signal_after_end"),
    ):
        if key in rep and rep[key] != S20.after_end(p, sig, S20.window(fx, tag, p)):
            out.append(f"report.json {key} ≠ 재계산")
    if meta.get("status") != "OK":
        if not _same(
            rep.get("judgment"), _norm(RP.judge(meta.get("status"), None, None, None))
        ):
            out.append("멈춘 실행의 판정 ≠ NOT_JUDGED 규칙")
        if any(k in rep for k in ("bootstrap", "bootstrap_tail_excluded")):
            out.append("정상 완료가 아닌데 bootstrap 칸이 있음")
    md = Path(rdir) / "report.md"
    if not md.exists() or md.read_text(encoding="utf-8") != RP.markdown(rep):
        out.append("report.md ≠ report.json 에서 다시 만든 보고")
    return out


def _check_report(p, sig, fx, common, rep, status, res) -> list[str]:
    out = []
    (rjs, same, n_states), labels_doc = res["ref"], res["labels"]
    if "reference" in rep and not _same(
        rep["reference"],
        _norm(FW.reference_summary(p, rjs, n_states, labels_doc, same)),
    ):
        out.append("보고 reference 요약 ≠ 다시 계산")
    if "learning" in rep:
        rows = []
        for q in fx["quarter_detail"]:
            ds, ex = FW.window_dates(p, common, q, labels_doc)
            rows.append(FW.learning_row(q, ds, ex, res["docs"].get(q["id"])))
        if not _same(rep["learning"], _norm(rows)):
            out.append("보고 learning ≠ 다시 계산")
    for tag, key in (("val", "validation"), ("test", "test")):
        bks = res["books"].get(tag) or {}
        if not bks and key not in rep:
            continue
        w = S20.window(fx, tag, p)
        bounds = PR.SUB_RANGES if tag == "test" else None
        if not _same(rep.get(key, {}), _norm(FW.metrics(p, bks, w, bounds))):
            out.append(f"보고 {key} 지표 ≠ 다시 계산")
        if not _same(rep.get(f"{key}_trades", {}), _norm(RP.extra(p, bks, bounds))):
            out.append(f"보고 {key}_trades 거래 분석 ≠ 다시 계산")
    if status == "OK":
        tb = res["books"]["test"]
        boot, tail = FW.pair_bootstrap(p, sig, tb)
        if not _same(rep.get("bootstrap"), _norm(boot)) or tail != rep.get(
            "bootstrap_tail_excluded"
        ):
            out.append("보고 bootstrap ≠ 다시 계산")
        w = S20.window(fx, "test", p)
        judged = RP.judge(
            "OK",
            FW.metrics(p, tb, w, PR.SUB_RANGES),
            RP.extra(p, tb, PR.SUB_RANGES),
            boot,
        )
        if not _same(rep.get("judgment"), _norm(judged)):
            out.append("보고 판정 ≠ 다시 계산")
    return out
