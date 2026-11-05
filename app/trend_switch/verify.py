"""POC6-21 verify — 저장 산출물에서 다시 계산(새 학습 · 외부 조회 없음) — 통합 설계 §7 AC5 · 판정 §5.

```text
잠금     식별자 · 입력 · recipe · 코드 해시 · 환경 · 실행 파일 목록(run.json files) · 실행 1회 ↔ 지금
사실     봉인 판 → POC6-20 사실 → 절대 정답 네 모수를 다시 세어 잠금 facts 와 같은지
자료     eligibility · market(POC6-20 검산 그대로) · features(30열 · 절대 정답 · 사용 가능) 재계산 대조
모델     POC6-20 모델 검산(학습 행 지문 · 입력 배열 · 열 · 원문 해시 · ML_B 매개변수 · 배정 신호 · 복원 예측 1e-12)
         · 정상 완료 = 분기 수만큼 `<분기>_M` 전부 · 일정 · 예측 파일 = 모델 기록 예측 합
장부     저장 예측 → 계획 → 정책 재적용 = 저장 장부 · 독립 손검산(audit · 정책 함수 미사용) 문제 0
보고     지표 · 거래 분석 · bootstrap · 판정 · 나머지 칸 · report.md 재계산 · 정지 주장 · 단계 기록(evidence)
손상     기록 형식이 깨져도 멈추지 않고 문제로 남긴다(정상 통과로 바꾸지 않음 · verify 기록은 늘 쓴다)
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.feature_gain import protocol as P8
from app.market_context_value import verify as VR20
from app.ml_evidence import store
from app.trend_switch import audit as AU
from app.trend_switch import evidence as EV
from app.trend_switch import flow as FW
from app.trend_switch import protocol as P21
from app.trend_switch import report as RP
from app.trend_switch import study as ST
from app.weekly_selection import audit as AU1
from app.weekly_selection import data as D
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR

CheckRequired = D.CheckRequired
_guard, _load, _same, _norm = VR20._guard, VR20._load, VR20._same, VR20._norm


def verify(
    root: Path = P21.ROOT,
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
    out += [f"잠금: {x}" for x in P21.lock_problems(lk)]
    if P21.code_hashes(repo) != lk["code"]["sha256"]:
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
    recs = _guard(out, "모델 기록", VR20._model_recs, rdir) or {}
    books: dict[str, Any] = {
        "vstat": {},
        "tstat": {},
        "mets": {},
        "extra": {},
        "tb": {},
    }
    if status != "DATA_SHORT":
        _guard(out, "자격 · 시장", VR20._check_inputs, p, el, mkt, fx, rdir)
        t = ST.abs_table(p, el)
        _guard(out, "특징 · 절대 정답", _check_features, p, t, rdir)
        rows_by_sig = ST.rows_by_signal(t)
        defined = {i for i in sig if mkt[i]["values"] is not None}
        args = (p, t, mkt, fx, defined, rows_by_sig, recs, rdir)
        _guard(out, "모델", VR20._check_models, *args)
        _guard(out, "모델 집합", _check_expected_set, fx, recs, status)
        _guard(out, "일정", VR20._check_schedule, p, recs, rdir)
        preds = _guard(out, "예측 파일", _check_predictions, recs, rdir) or {}
        books = (
            _guard(out, "장부", _check_books, p, t, el, rows_by_sig, fx, rdir, preds)
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
        if status != "DATA_SHORT":
            _guard(out, "보고 값", _check_report, p, sig, rep, status, books)
    return _record(ldir, rdir, out, status, clock)


def _survey(db, repo, market_base, lk):
    p = D.build_panel(Path(db), PR.VERSION, PR.CONTENT_SHA)
    fx, el, _c, _u, mkt = P21.survey(p, FW._base(repo, market_base))
    if not _same(fx, lk["facts"]):
        return ["다시 센 사실 ≠ 잠금 facts"], None
    return [], (p, fx, el, mkt)


def _record(ldir, rdir, problems, status, clock) -> dict:
    now = clock()
    doc = {
        "schema": "poc6_21_verify_v1",
        "run_id": rdir.name,
        "verified_at": store.iso(now),
        "run_status": status,
        "status": "OK" if not problems else "MISMATCH",
        "problems": problems,
    }
    P8.write_once(ldir / "verify" / f"{rdir.name}_{P8.new_id(now)}.json", P8.dumps(doc))
    return doc


def _check_features(p, t, rdir) -> list[str]:
    f = rdir / "features.json.gz"
    if not f.exists():
        return []
    ok = _same(PR.read_gz(f), _norm(ST.features_doc(p, t)))
    return [] if ok else ["features.json.gz ≠ 다시 만든 30열 · 절대 정답"]


def _check_expected_set(fx, recs, status) -> list[str]:
    """정상 완료 = 분기 수만큼 M 모델 전부. 멈춘 실행 = 계약 안 모델만."""
    want = EV.model_ids(fx)
    if status == "OK" and set(recs) != want:
        return [f"정상 완료인데 모델 기록 수 {len(recs)} ≠ {len(want)}"]
    return ["계약 밖 모델 기록"] if set(recs) - want else []


def _check_predictions(recs, rdir):
    out, preds = [], {}
    for tag, name in (("val", "validation"), ("test", "test")):
        f = rdir / f"predictions_{name}.json"
        if not f.exists():
            continue
        preds[tag] = PR.load_json(f)
        joined: dict[str, dict] = {}
        for r in recs.values():
            if r.get("phase") == tag:
                joined.update(r["predictions"])
        if not _same(preds[tag], joined):
            out.append(f"predictions_{name}.json ≠ 모델 기록 예측 합")
    return out, preds


def _check_books(p, t, el, rows_by_sig, fx, rdir, preds):
    """저장 장부 → 정책 재적용 · 독립 손검산 · 지표 · 거래 분석(보고 유무와 무관 · 실패 실행 포함)."""
    out: list[str] = []
    res: dict[str, Any] = {"vstat": {}, "tstat": {}, "mets": {}, "extra": {}, "tb": {}}
    pos = {d: k for k, d in enumerate(p.axis)}
    for tag, sub, items in (
        ("val", "validation", P21.val_books()),
        ("test", "test", P21.test_books()),
    ):
        if not any((rdir / sub / f"{n}.json").exists() for n, _k, _c in items):
            continue  # 이 구간 장부 없음(선행 재생 정지 · 실패) — 만들지 않은 계획을 다시 만들지 않는다
        w = ST.window(fx, tag, p)
        k_idx = pos[fx[tag]["k_exec"]]
        s_i, e_i = w["start_idx"], w["end_idx"]
        sigs = [pos[d] for d in w["plan_signals"]]
        members = {i: el.members[i] for i in sigs}
        cands = AU.candidates(p, members, sigs)
        outs = AU.excluded(p, el, sigs)
        scores_r = AU.r_scores(p, members, sigs)
        try:
            pl = ST.phase_plans(p, t, el, rows_by_sig, fx, tag, preds.get(tag, {}))
        except (CheckRequired, KeyError) as e:
            out.append(f"{tag}: 저장 예측으로 계획 재구성 불가({str(e)[:60]})")
            pl = None
        again: dict[str, dict] = {}
        for name, key, cost in items:
            f = rdir / sub / f"{name}.json"
            if not f.exists():
                continue
            saved = PR.load_json(f)
            if key is None:
                out += [
                    f"{tag} {name}: {x}" for x in AU1.audit_k(p, saved, k_idx, s_i, e_i)
                ]
            else:
                sc = scores_r if key[0] == "R" else preds.get(tag, {})
                out += [
                    f"{tag} {name}: {x}"
                    for x in AU.audit_book(
                        p, saved, sc, cands, outs, key[1] == "1", s_i, e_i
                    )
                ]
                if pl is None:
                    continue
            js = PO.to_json(ST.simulate(p, pl or {}, w, key, cost, name, k_idx))
            if not _same(js, saved):
                out.append(f"{tag} {name}: 정책 재적용 ≠ 저장 장부")
            res["vstat" if tag == "val" else "tstat"][name] = js["status"]
            again[name] = js
        bounds = PR.SUB_RANGES if tag == "test" else None
        res["mets"][tag] = ST.metrics(p, again, w, bounds)
        res["extra"][tag] = ST.extra(p, again, bounds)
        if tag == "test":
            res["tb"] = again
    return out, res


def _check_report(p, sig, rep, status, books) -> list[str]:
    out = []
    for tag, key in (("val", "validation"), ("test", "test")):
        mets, ex = books["mets"].get(tag) or {}, books["extra"].get(tag) or {}
        if (mets or key in rep) and not _same(_norm(mets), rep.get(key, {})):
            out.append(f"보고 {key} 지표 ≠ 다시 계산")
        if (ex or f"{key}_trades" in rep) and not _same(
            _norm(ex), rep.get(f"{key}_trades", {})
        ):
            out.append(f"보고 {key}_trades 거래 분석 ≠ 다시 계산")
    if status == "OK":
        boot, tail = ST.pair_bootstrap(p, sig, books["tb"])
        if not _same(_norm(boot), rep.get("bootstrap")) or tail != rep.get(
            "bootstrap_tail_excluded"
        ):
            out.append("보고 bootstrap ≠ 다시 계산")
        opps = RP.opportunities(books["extra"]["test"])
        judged = RP.judge("OK", books["mets"]["test"], boot, opps)
        if not _same(_norm(judged), rep.get("judgment")):
            out.append("보고 판정 ≠ 다시 계산")
    return out
