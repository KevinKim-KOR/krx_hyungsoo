"""POC6-20 verify — 저장 산출물에서 다시 계산(새 학습 · 외부 조회 없음) — 설계 §8 AC2 · AC3 · 판정 §6.

```text
잠금     식별자 · 입력 · recipe · 코드 해시 · 환경 · 실행 파일 목록(run.json files) · 실행 1회 ↔ 지금
사실     봉인 판 → H1 분모 → 시장 4열 → 공통 분모를 다시 세어 잠금 facts 와 같은지
자료     eligibility · market(4열 값 · 근거 · 사유 · 열 · 사본 지문) · features(30열 · 정답) 재계산 대조
모델     분기 학습 행 지문 · 입력 배열 · 열 이름 · 원문 해시 · 고정 ML_B 매개변수 · id · 시각 · 복원 차이 기록
         · 예측 신호 = 배정 신호 · 예측 종목 = 자격 종목 · 복원 예측 ↔ 저장 예측(1e-12) · 일정 파일
장부     저장 예측 → 계획 → 정책 재적용 = 저장 장부 · 독립 손검산(audit) 문제 0(실패 실행 포함)
보고     지표 · bootstrap · 판정 · 설명(rank IC) · 나머지 칸 · report.md 재계산 · 정지 주장 · 단계 기록(evidence)
손상     기록 형식이 깨져도 멈추지 않고 문제로 남긴다(정상 통과로 바꾸지 않음 · verify 기록은 늘 쓴다)
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.feature_gain import protocol as P8
from app.market_context_value import evidence as EV
from app.market_context_value import flow as FW
from app.market_context_value import learner as L
from app.market_context_value import market_inputs as MI
from app.market_context_value import protocol as P20
from app.market_context_value import report as RP
from app.market_context_value import study as ST
from app.ml_evidence import store
from app.weekly_selection import audit as AU
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R

CheckRequired = D.CheckRequired
GUARD_ERRORS = (
    KeyError,
    TypeError,
    ValueError,
    AttributeError,
    IndexError,
    OSError,
    EOFError,
)


def _same(a: Any, b: Any) -> bool:
    return store.canonical(a) == store.canonical(b)


def _norm(obj: Any) -> Any:
    return P8.loads(P8.dumps(obj, compact=True).decode())


def _guard(out: list[str], label: str, fn, *args):
    """검사 하나 — 기록 형식 손상 · 재계산 정지는 문제로 남기고 다음 검사로 간다(값을 돌려주면 (문제, 값))."""
    try:
        res = fn(*args)
    except (CheckRequired, *GUARD_ERRORS) as e:
        out.append(f"{label} 검사 중 손상 · 정지({type(e).__name__}: {str(e)[:120]})")
        return None
    if isinstance(res, tuple):
        out.extend(res[0])
        return res[1]
    out.extend(res or [])
    return None


def _load(path: Path):
    return [], PR.load_json(path)


def verify(
    root: Path = P20.ROOT,
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
    out += [f"잠금: {x}" for x in P20.lock_problems(lk)]
    if P20.code_hashes(repo) != lk["code"]["sha256"]:
        out.append("코드 ≠ 잠금 코드")
    if FW.runtime_env() != lk["env"]:
        out.append("환경 ≠ 잠금 환경")
    _guard(out, "식별자", EV.identity_problems, lk, meta, ldir, rdir)
    if PR.manifest(rdir) != meta.get("files"):
        out.append("실행 폴더 파일 해시 ≠ run.json 파일 목록")
    _guard(out, "단계", EV.stage_problems, meta)
    s = _guard(out, "사실", _survey, db, repo, market_base, lk)
    if s is None:
        return _record(ldir, rdir, out, status, clock)
    p, fx, el, mkt = s
    sig = el.sig
    _guard(out, "파일", EV.files_problems, fx, rdir, status)
    rep = None
    if (rdir / "report.json").exists():
        rep = _guard(out, "report.json", _load, rdir / "report.json")
    recs = _guard(out, "모델 기록", _model_recs, rdir) or {}
    t = None
    books = {
        "vstat": {},
        "tstat": {},
        "mets": {"val": {}, "test": {}},
        "tb": {},
        "tplans": {},
    }
    if status != "DATA_SHORT":
        _guard(out, "자격 · 시장", _check_inputs, p, el, mkt, fx, rdir)
        t = F.build_table(
            p, {i: el.members[i] for i in sig if len(el.members[i]) >= D.MIN_ELIGIBLE}
        )
        _guard(out, "특징", _check_features, p, t, rdir)
        rows_by_sig: dict[int, list[int]] = {}
        for r, (i, _j) in enumerate(t.rows):
            rows_by_sig.setdefault(i, []).append(r)
        defined = {i for i in sig if mkt[i]["values"] is not None}
        _guard(
            out, "모델", _check_models, p, t, mkt, fx, defined, rows_by_sig, recs, rdir
        )
        _guard(out, "모델 집합", _check_expected_set, fx, recs, status)
        _guard(out, "일정", _check_schedule, p, recs, rdir)
        preds = _guard(out, "예측 파일", _check_predictions, recs, rdir) or {}
        books = (
            _guard(out, "장부", _check_books, p, t, rows_by_sig, fx, sig, rdir, preds)
            or books
        )
    _guard(
        out,
        "정지 주장",
        EV.stop_problems,
        lk,
        meta,
        rep,
        rdir,
        recs,
        books["vstat"],
        books["tstat"],
    )
    if rep is not None:
        _guard(
            out,
            "보고 칸",
            EV.report_meta_problems,
            p,
            sig,
            fx,
            lk,
            meta,
            rdir,
            rep,
            recs,
        )
        if t is not None:
            _guard(out, "보고 값", _check_report, p, t, sig, rep, status, books)
    return _record(ldir, rdir, out, status, clock)


def _model_recs(rdir: Path):
    return [], {f.stem: PR.load_json(f) for f in PR.model_files(rdir)}


def _survey(db, repo, market_base, lk):
    p = D.build_panel(Path(db), PR.VERSION, PR.CONTENT_SHA)
    fx, el, _c, _u, mkt = P20.survey(p, FW._base(repo, market_base))
    if not _same(fx, lk["facts"]):
        return ["다시 센 사실 ≠ 잠금 facts"], None
    return [], (p, fx, el, mkt)


def _record(ldir, rdir, problems, status, clock) -> dict:
    now = clock()
    doc = {
        "schema": "poc6_20_verify_v1",
        "run_id": rdir.name,
        "verified_at": store.iso(now),
        "run_status": status,
        "status": "OK" if not problems else "MISMATCH",
        "problems": problems,
    }
    P8.write_once(ldir / "verify" / f"{rdir.name}_{P8.new_id(now)}.json", P8.dumps(doc))
    return doc


def _check_inputs(p, el, mkt, fx, rdir) -> list[str]:
    out = []
    sig = el.sig
    f = rdir / "eligibility.json.gz"
    if f.exists():
        mine = {
            "reasons": el.reasons,
            "members": {p.axis[i]: [p.codes[j] for j in el.members[i]] for i in sig},
            "excluded": {
                p.axis[i]: {
                    k: [p.codes[j] for j in v] for k, v in el.excluded[i].items()
                }
                for i in sig
            },
        }
        if not _same(PR.read_gz(f), _norm(mine)):
            out.append("eligibility.json.gz ≠ 다시 만든 자격")
    f = rdir / "market.json.gz"
    if f.exists():
        saved = PR.read_gz(f)
        if not _same(saved.get("signals"), _norm({p.axis[i]: mkt[i] for i in sig})):
            out.append("market.json.gz ≠ 다시 만든 시장 4열 · 근거")
        if saved.get("columns") != list(MI.COLUMNS) or not _same(
            saved.get("files"), fx["market_files"]
        ):
            out.append("market.json.gz 열 · 사본 지문 ≠ 계약 · 잠금")
    return out


def _check_features(p, t, rdir) -> list[str]:
    f = rdir / "features.json.gz"
    if not f.exists():
        return []
    mine = {
        "columns": list(F.COLUMNS),
        "rows": [[p.axis[i], p.codes[j]] for i, j in t.rows],
        "X": t.X,
        "missing": t.missing,
        "z": t.z,
        "y": t.y,
        "usable": {p.axis[i]: t.usable[i] for i in t.sig},
        "label_count": {p.axis[i]: t.label_count[i] for i in t.sig},
    }
    ok = _same(PR.read_gz(f), _norm(mine))
    return [] if ok else ["features.json.gz ≠ 다시 만든 30열 · 정답"]


def _check_one_model(
    p, t, mkt, fx, defined, rows_by_sig, mid, rec, rdir, q
) -> list[str]:
    out = []
    tag, inp = rec["phase"], rec["input"]
    rows = ST.train_rows(t, p, q, defined)
    exp = {
        "id": mid,
        "quarter": q["id"],
        "rows": len(rows),
        "weeks": len({t.rows[r][0] for r in rows}),
        "columns_sha256": P20._sha(list(L.COLUMNS[inp])),
        **ST.row_prints(t, p, rows),
        "x_sha256": P20._sha([ST.x_row(t, mkt, r, inp) for r in rows]),
        "struct": L.STRUCT,
        "cutoff": q["cutoff"],
    }
    out += [
        f"모델 {mid}: {k} ≠ 다시 만든 값" for k, v in exp.items() if rec.get(k) != v
    ]
    ts = [
        store.parse_iso(rec[k])
        for k in ("train_started_at", "trained_at", "predicted_at")
    ]
    secs = rec.get("seconds")
    if ts != sorted(ts) or not isinstance(secs, (int, float)) or secs < 0:
        out.append(f"모델 {mid}: 학습 · 예측 시각 순서 · 소요 기록 이상")
    diff = rec.get("restore_max_abs_diff")
    if not isinstance(diff, (int, float)) or not 0 <= diff <= M.RESTORE_TOL:
        out.append(f"모델 {mid}: 복원 차이 기록이 허용 범위 밖")
    text = (rdir / "models" / f"{mid}.txt").read_text(encoding="utf-8")
    if store.sha256_bytes(text.encode("utf-8")) != rec.get("model_sha256"):
        out.append(f"모델 {mid}: 원문 해시 ≠ 기록")
    if L.feature_names(text) != list(L.COLUMNS[inp]):
        out.append(f"모델 {mid}: 열 이름 · 순서 ≠ 입력")
    if M.resolved_params(text) != rec.get("resolved_params"):
        out.append(f"모델 {mid}: 해석된 매개변수 ≠ 기록")
    bad = L.param_problems(text)
    if bad:
        out.append(f"모델 {mid}: 매개변수 ≠ 고정 ML_B 설정: {', '.join(bad)}")
    mine = sorted(d for d in fx[tag]["plan_signals"] if fx["assign"][d] == q["id"])
    if rec.get("signals") != mine or sorted(rec.get("predictions") or {}) != mine:
        out.append(f"모델 {mid}: 예측 신호 ≠ 배정 신호")
    back = M.restore(text)
    for d in mine:
        rs = rows_by_sig[p.axis.index(d)]
        codes = [p.codes[t.rows[r][1]] for r in rs]
        got = (rec.get("predictions") or {}).get(d) or {}
        if sorted(got) != sorted(codes):
            out.append(f"모델 {mid}: {d} 예측 종목 ≠ 자격 종목")
            break
        Xp = L.matrix([ST.x_row(t, mkt, r, inp) for r in rs], len(L.COLUMNS[inp]))
        saved = np.array([got[c] for c in codes], dtype=float)
        if not np.all(np.abs(M.predict(back, Xp) - saved) <= M.RESTORE_TOL):
            out.append(f"모델 {mid}: {d} 복원 예측 ≠ 저장 예측")
            break
    return out


def _check_models(p, t, mkt, fx, defined, rows_by_sig, recs, rdir) -> list[str]:
    out: list[str] = []
    qs = {
        (tag, q["id"]): q for tag in ("val", "test") for q in fx["quarter_detail"][tag]
    }
    for mid, rec in recs.items():
        q = qs.get((rec.get("phase"), rec.get("quarter")))
        if (
            q is None
            or rec.get("input") not in L.INPUTS
            or mid != f"{q['id']}_{rec['input']}"
        ):
            out.append(f"모델 {mid}: 단계 · 분기 · 입력 이름이 계약 밖")
            continue
        args = (p, t, mkt, fx, defined, rows_by_sig, mid, rec, rdir, q)
        _guard(out, f"모델 {mid}", _check_one_model, *args)
    return out


def _check_expected_set(fx, recs, status) -> list[str]:
    """정상 완료 = 70 모델 전부. 멈춘 실행 = 계약 안 모델만(멈춘 단계 주장은 evidence 가 본다)."""
    want = EV.model_ids(fx)
    if status == "OK" and set(recs) != want:
        return [f"정상 완료인데 모델 기록 수 {len(recs)} ≠ {len(want)}"]
    return ["계약 밖 모델 기록"] if set(recs) - want else []


def _check_schedule(p, recs, rdir) -> list[str]:
    out = []
    for tag, name in (("val", "validation"), ("test", "test")):
        f = rdir / f"schedule_{name}.json"
        mine = [r for r in recs.values() if r.get("phase") == tag]
        if not f.exists():
            if (rdir / f"predictions_{name}.json").exists():
                out.append(f"schedule_{name}.json 없음")
            continue
        if not _same(_norm(PR.schedule(p.axis, mine)), PR.load_json(f)):
            out.append(f"schedule_{name}.json ≠ 모델 기록")
    return out


def _check_predictions(recs, rdir):
    out, preds = [], {}
    for tag, name in (("val", "validation"), ("test", "test")):
        f = rdir / f"predictions_{name}.json"
        if not f.exists():
            continue
        preds[tag] = PR.load_json(f)
        joined: dict[str, dict] = {k: {} for k in L.INPUTS}
        for r in recs.values():
            if r.get("phase") == tag:
                joined[r["input"]].update(r["predictions"])
        if not _same(preds[tag], joined):
            out.append(f"predictions_{name}.json ≠ 모델 기록 예측 합")
    return out, preds


def _check_books(p, t, rows_by_sig, fx, sig, rdir, preds):
    """저장 장부 → 정책 재적용 · 독립 손검산 · 곡선 지표(보고 유무와 무관 · 실패 실행 포함)."""
    out: list[str] = []
    pos = {d: k for k, d in enumerate(p.axis)}
    names = {c: p.series[c].name[-1] for c in p.codes}
    ml, mom = ST.scorers(p, t)
    res: dict[str, Any] = {
        "vstat": {},
        "tstat": {},
        "mets": {"val": {}, "test": {}},
        "tb": {},
        "tplans": {},
    }
    for tag, sub, items in (
        ("val", "validation", P20.val_books()),
        ("test", "test", P20.test_books()),
    ):
        w = ST.window(fx, tag, p)
        k_idx = pos[fx[tag]["k_exec"]]
        s_i, e_i = w["start_idx"], w["end_idx"]
        for name, key, cost in items:
            f = rdir / sub / f"{name}.json"
            if not f.exists():
                continue
            saved = PR.load_json(f)
            if key is None:
                bk = PO.simulate_bench(p, p.ci[D.BENCH], k_idx, s_i, e_i, cost)
                out += [
                    f"{tag} {name}: {x}" for x in AU.audit_k(p, saved, k_idx, s_i, e_i)
                ]
            else:
                src = preds.get(tag, {}).get(key, {})
                scorer = mom("RET_120") if key == "B" else ml(src)
                try:
                    pl = ST.plans(p, t, rows_by_sig, {}, w["plan_signals"], scorer)
                except KeyError as e:
                    out.append(
                        f"{tag} {name}: 저장 예측 없음({str(e)[:40]}) · 재적용 불가"
                    )
                    continue
                ids = P20.model_ids(fx["assign"], key) if key in L.INPUTS else {}
                for i, x in pl.items():
                    x.model_id = ids.get(p.axis[i])
                if tag == "test":
                    res["tplans"][key] = pl
                sc = {
                    p.axis[i]: {p.codes[j]: v for j, v in x.scores.items()}
                    for i, x in pl.items()
                }
                bk = PO.simulate(p, pl, s_i, e_i, cost, name, sig)
                out += [
                    f"{tag} {name}: {x}"
                    for x in AU.audit_book(p, saved, sc, sig, s_i, e_i)
                ]
            js = PO.to_json(bk)
            if not _same(js, saved):
                out.append(f"{tag} {name}: 정책 재적용 ≠ 저장 장부")
            res["vstat" if tag == "val" else "tstat"][name] = js["status"]
            bounds = PR.SUB_RANGES if tag == "test" else None
            res["mets"][tag][name] = R.curve(js, w["start"], bounds, pos, names)
            if tag == "test":
                res["tb"][name] = js
    return out, res


def _check_report(p, t, sig, rep, status, books) -> list[str]:
    out = []
    for tag, key in (("val", "validation"), ("test", "test")):
        if (books["mets"][tag] or key in rep) and not _same(
            _norm(books["mets"][tag]), rep.get(key, {})
        ):
            out.append(f"보고 {key} 지표 ≠ 다시 계산")
    if status == "OK":
        boot, tail = ST.pair_bootstrap(p, sig, books["tb"])
        if not _same(_norm(boot), rep.get("bootstrap")) or tail != rep.get(
            "bootstrap_tail_excluded"
        ):
            out.append("보고 bootstrap ≠ 다시 계산")
        judged = RP.judge("OK", books["mets"]["test"], boot)
        if not _same(_norm(judged), rep.get("judgment")):
            out.append("보고 판정 ≠ 다시 계산")
        ic = {
            k: R.rank_ic(ST.ic_pairs(t, books["tplans"][k], p)) for k in ("P", "M", "B")
        }
        if not _same(_norm({"rank_ic": ic}), rep.get("explain")):
            out.append("보고 설명(rank IC) ≠ 다시 계산")
    return out
