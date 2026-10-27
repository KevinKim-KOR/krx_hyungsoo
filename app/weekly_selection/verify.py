"""POC6-11 verify — 새 학습 없이 저장 산출물에서 다시 계산 · 대조(설계 §9 · 판정 §6).

```text
1 입력   봉인 판에서 자격 · 30열 · 정답을 다시 만들어 저장본과 통째로 대조 · 잠금 사실과 대조
2 모델   저장 원문 해시 · 해석된 매개변수 · 복원 예측 = 저장 예측(≤ 1e-12) · cutoff ≤ 신호 · 가장 최근 판 · 구조
3 재생   저장 점수 + 다시 만든 추세 조건으로 공통 정책을 다시 적용 → 의도 · 체결 · 장부 · 계획 기록이 같아야 함
4 손검산 정책 함수를 쓰지 않는 독립 검산 — 현금 · 수량 · 체결가 = 그날 O* · 거래 가능 · 5종목 · 예산 · 비용 ·
         상위 5 편입 · 추세 · 주 편입 한도 · 10위 유지 · 통상 이탈 1개 · 보호 이탈 조건과 누락 · 4회 재진입 대기 ·
         중복 의도 · 매도 이연 · 매수 취소 사유 · 실행일 = 신호 + 2
5 보고   장부에서 곡선 · 지표 · 선택 · bootstrap · 판정을 다시 계산해 report.json 과 대조
```
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.feature_gain import protocol as P8
from app.ml_evidence import store
from app.weekly_selection import audit as AU
from app.weekly_selection import data as D
from app.weekly_selection import evidence as EV
from app.weekly_selection import features as F
from app.weekly_selection import flow as FL
from app.weekly_selection import model as M
from app.weekly_selection import policy as PO
from app.weekly_selection import protocol as PR
from app.weekly_selection import report as R


def verify(
    root: Path = PR.ROOT,
    db: Path = PR.DB,
    run_id: Optional[str] = None,
    repo: Path = Path("."),
) -> dict[str, Any]:
    ldir, lk, rdir = PR.latest_run(Path(root), run_id)
    meta = PR.load_json(rdir / "run.json")
    rep = (
        PR.load_json(rdir / "report.json") if (rdir / "report.json").exists() else None
    )
    problems: list[str] = []
    M.lgb()
    bad = M.openmp_problem()
    if bad:  # 복원 · 예측 전에 멈춤(세그폴트 대신 이유를 남김)
        raise PR.CheckRequired(f"OpenMP 로드 순서: {bad}")
    if PR.code_hashes(repo) != lk["code"]["sha256"]:
        problems.append("지금 코드 ≠ 잠금 코드(재계산이 잠금 코드와 다름)")
    problems += _guard("run · 잠금 기록", EV.lock_run_problems, lk, ldir, meta, rdir)
    problems += _guard(
        "필수 근거(완결성)", EV.completeness_problems, lk, meta, rep, rdir
    )
    p = D.build_panel(Path(db), PR.VERSION, PR.CONTENT_SHA)
    fx, el, _count, _usable = PR.survey(p)
    if store.canonical(fx) != store.canonical(lk["facts"]):
        problems.append("자격 · 날짜 · 표본 사실 ≠ 잠금")
    problems += [f"PLAN 표와 다름: {x}" for x in PR.compare(fx)]
    sig = el.sig
    elig = {
        "reasons": el.reasons,
        "members": {p.axis[i]: [p.codes[j] for j in el.members[i]] for i in sig},
        "excluded": {
            p.axis[i]: {k: [p.codes[j] for j in v] for k, v in el.excluded[i].items()}
            for i in sig
        },
    }
    if (rdir / "eligibility.json.gz").exists() and store.canonical(
        PR.read_gz(rdir / "eligibility.json.gz")
    ) != store.canonical(P8.loads(P8.dumps(elig, compact=True).decode())):
        problems.append("자격 · 제외 목록 ≠ 저장본")
    t = F.build_table(
        p, {i: el.members[i] for i in sig if len(el.members[i]) >= D.MIN_ELIGIBLE}
    )
    feats = {
        "columns": list(F.COLUMNS),
        "rows": [[p.axis[i], p.codes[j]] for i, j in t.rows],
        "X": t.X,
        "missing": t.missing,
        "z": t.z,
        "y": t.y,
        "usable": {p.axis[i]: t.usable[i] for i in t.sig},
        "label_count": {p.axis[i]: t.label_count[i] for i in t.sig},
    }
    if (rdir / "features.json.gz").exists() and store.canonical(
        PR.read_gz(rdir / "features.json.gz")
    ) != store.canonical(P8.loads(P8.dumps(feats, compact=True).decode())):
        problems.append("30열 · 정답 ≠ 저장본")
    rows_by_sig: dict[int, list[int]] = {}
    for r, (i, _j) in enumerate(t.rows):
        rows_by_sig.setdefault(i, []).append(r)
    preds = (
        PR.load_json(rdir / "predictions_validation.json")
        if (rdir / "predictions_validation.json").exists()
        else {}
    )
    if (rdir / "predictions_test.json").exists():
        tp = PR.load_json(rdir / "predictions_test.json")
        preds = {**preds, **{f"TEST_{k}": v for k, v in tp.items()}}
    problems += _guard("모델 기록", _check_models, p, t, rows_by_sig, lk, rdir, preds)
    problems += _guard(
        "정지 이유", _check_stop_claim, p, t, lk, meta, rep, rdir, el.sig
    )
    problems += _guard("상태 · 순서", _check_shape, rdir, meta, rep, lk)
    out = {
        "run_id": rdir.name,
        "lock_id": lk["lock_id"],
        "run_status": meta.get("status"),
    }
    if rep is not None:
        problems += _guard(
            "장부 · 보고",
            _check_books_and_report,
            p,
            t,
            rows_by_sig,
            fx,
            sig,
            rdir,
            preds,
            rep,
        )
        problems += _guard(
            "보고 기록", EV.report_meta_problems, p, sig, fx, lk, meta, rdir, rep
        )
    if not isinstance(
        meta.get("files"), dict
    ):  # 해시 목록은 모든 상태에서 필수(빈 값 대체 없음)
        problems.append("run.json 해시 목록(files) 없음")
    elif PR.manifest(rdir) != meta["files"]:
        problems.append("산출물 해시 ≠ run.json 목록")
    problems += _guard("모델 적용 일정", _check_schedule, p, rdir, meta.get("status"))
    out.update(status="OK" if not problems else "MISMATCH", problems=problems[:80])
    out["verified_at"] = store.iso(store.utc_now())
    # verify 기록은 실행 폴더 밖(잠금 폴더 verify/)에 남긴다 — 실행 근거와 섞지 않음(검증 r3 적대 검토)
    P8.write_once(
        ldir / "verify" / f"{rdir.name}_{P8.new_id(store.utc_now())}.json",
        P8.dumps(out),
    )
    return out


GUARD_ERRORS = (
    KeyError,
    TypeError,
    ValueError,
    AttributeError,
    IndexError,
    OSError,
    EOFError,
)


def _guard(label: str, fn, *args) -> list[str]:
    """기록 형식이 깨져도 verify 가 멈추지 않고 불일치로 남긴다(정상 통과로 바꾸지 않음)."""
    try:
        return fn(*args)
    except GUARD_ERRORS as e:
        return [f"{label} 검사 중 기록 형식 손상({type(e).__name__}: {str(e)[:80]})"]


def _check_stop_claim(p, t, lk, meta, rep, rdir, sig) -> list[str]:
    """정지 이유 = 흐름이 남기는 문구 그대로 · 그 이유가 지금 다시 계산해도 성립(위조된 정지 검출 · 검증 r3).

    일시적이 아니라 같은 코드 · 같은 자료에서 결정적으로 다시 나는 결함만 정지 이유로 인정한다.
    """
    status = meta.get("status")
    stop = (rep or {}).get("stop")
    stages = meta["stages"]
    if status == "BUDGET_STOP":
        x = stages[-1]
        want = (
            f"BudgetStop: {x['stage']}: 경과 {x['wall_s']:.0f}초 · "
            f"최대 RSS {x['max_rss_bytes']} bytes"
        )
        return [] if stop == want else ["예산 정지 문구 ≠ 마지막 단계 기록"]
    if status != "CHECK_REQUIRED":
        return []
    names = [x["stage"] for x in stages]
    sel_f = rdir / "selection.json"
    struct = PR.load_json(sel_f)["L"] if sel_f.exists() else None
    full = EV.expected_stages(lk, struct)
    last, nxt = names[-1], (full[len(names)] if len(names) < len(full) else None)
    stop = str(stop)
    for stage, sub, order, msg in (
        (
            "validation books",
            "validation",
            EV.VAL_BOOKS,
            "검증 곡선 평가 미확정 {} — 선택 · 시험 미실행(판정 §3-3)",
        ),
        (
            "test books",
            "test",
            EV.TEST_BOOKS,
            "시험 곡선 평가 미확정 {} — H1 · 후보 NOT_JUDGED(판정 §3-3)",
        ),
    ):
        if stop.startswith(msg.split("{}")[0]):
            bad = [
                b
                for b in order
                if (rdir / sub / f"{b}.json").exists()
                and PR.load_json(rdir / sub / f"{b}.json")["status"] != "OK"
            ]
            ok = last == stage and bool(bad) and stop == msg.format(bad)
            return [] if ok else [f"정지 이유(곡선 미확정) ≠ {sub} 장부"]
    if stop == "CheckRequired: L · B 주간 날짜가 다름":
        wk = {p.axis[i] for i in sig}
        dates = [
            [
                d
                for d, _ in R.weekly_returns(
                    PR.load_json(rdir / "test" / f"{b}.json")["ledger"],
                    wk,
                    PO.START_VALUE,
                )[0]
            ]
            for b in ("L_20", "B_20")
        ]
        return (
            []
            if last == "test books" and dates[0] != dates[1]
            else ["정지 이유(주간 날짜) ≠ 다시 센 L · B 주간 날짜"]
        )
    m = re.fullmatch(
        r"CheckRequired: (\S+) 학습 표본이 잠금과 다름: (\d+)주 · (\d+)행", stop
    )
    if m:
        q = next(
            (
                q
                for ph in ("val", "test")
                for q in lk["facts"]["quarter_detail"][ph]
                if q["id"] == m[1]
            ),
            None,
        )
        if q is None or not (nxt or "").startswith(f"fit {q['id']}_"):
            return ["정지 이유(학습 표본) 분기 ≠ 멈춘 학습 단계"]
        rows = F.training_rows(t, p.axis, p.axis.index(q["cutoff"]))
        got = (len({t.rows[r][0] for r in rows}), len(rows))
        ok = got != (q["weeks"], q["rows"]) and got == (int(m[2]), int(m[3]))
        return [] if ok else [f"정지 이유(학습 표본 불일치) ≠ 다시 센 {q['id']} 표본"]
    m = re.fullmatch(r"CheckRequired: (\S+) 저장 전후 예측 차이 (\S+)", stop)
    if m:
        mid, ev = m[1], rdir / "models" / f"{m[1]}{PR.MISMATCH_SUFFIX}"
        if (
            nxt != f"fit {mid}"
            or not ev.exists()
            or not (rdir / "models" / f"{mid}.txt").exists()
        ):
            return ["정지 이유(복원 차이) 근거 없음 · 멈춘 학습 단계와 다름"]
        evd = PR.load_json(ev)
        back = M.restore((rdir / "models" / f"{mid}.txt").read_text(encoding="utf-8"))
        diff = 0.0
        for d, sc in evd["predictions"].items():
            rs = [r for r, (i, _j) in enumerate(t.rows) if p.axis[i] == d]
            got = M.predict(back, M.matrix([t.X[r] for r in rs]))
            saved = np.array([sc.get(p.codes[t.rows[r][1]], math.nan) for r in rs])
            diff = max(diff, float(np.max(np.abs(got - saved))))
        ok = (
            evd.get("id") == mid
            and diff > M.RESTORE_TOL
            and diff == evd.get("diff") == float(m[2])
        )
        return (
            [] if ok else ["정지 이유(복원 차이) ≠ 지금 복원한 예측과 근거 예측의 차이"]
        )
    for col in ("RET_20", "RET_120"):
        if (
            stop
            == f"CheckRequired: {col} 점수 결측(연속 126 자격이 창을 보장하지 못함)"
        ):
            k = F.COLUMNS.index(col)
            ph = "val" if last == full[full.index("validation books") - 1] else "test"
            plan = set(lk["facts"][ph]["plan_signals"])
            miss = any(
                t.X[r][k] is None
                for r, (i, _j) in enumerate(t.rows)
                if p.axis[i] in plan
            )
            at_end = last in (full[full.index("validation books") - 1], full[-2])
            return (
                [] if miss and at_end else [f"정지 이유({col} 결측) ≠ 다시 확인한 30열"]
            )
    return [f"알 수 없는 정지 이유: {stop[:80]}"]


def _check_schedule(p: D.Panel, rdir: Path, status: Optional[str]) -> list[str]:
    """모델 적용 일정 파일 = 모델 기록에서 다시 만든 일정(신호 · 실행일 · cutoff · 실제 시각 연결)."""
    out: list[str] = []
    recs = [PR.load_json(f) for f in PR.model_files(rdir)]
    for phase, name, agg in (
        ("val", "schedule_validation.json", "predictions_validation.json"),
        ("test", "schedule_test.json", "predictions_test.json"),
    ):
        f = rdir / name
        mine = [r for r in recs if r["phase"] == phase]
        if (
            not f.exists()
        ):  # 일정은 그 단계 학습이 다 끝나 모은 예측과 함께 쓴다(중간 정지엔 없음)
            if (rdir / agg).exists() or (status == "OK" and mine):
                out.append(f"{name} 없음")
            continue
        if _norm(PR.schedule(p.axis, mine)) != _norm(PR.load_json(f)):
            out.append(f"{name} ≠ 모델 기록")
    return out


def _check_shape(rdir: Path, meta: dict, rep: Optional[dict], lk: dict) -> list[str]:
    """상태 · 순서 — 선택 전 시험 산출물 없음 · 검증 모델 < 선택 시각 < 시험 모델 · 시험 = 선택 구조만."""
    out: list[str] = []
    status = meta.get("status")
    if status != "FAILED" and (rep is None or rep["judgment"]["validity"] != status):
        out.append(f"run 상태 {status} ≠ report 판정 상태")
    recs = [PR.load_json(f) for f in PR.model_files(rdir)]
    sel_f = rdir / "selection.json"
    sel = PR.load_json(sel_f) if sel_f.exists() else None
    test = [r for r in recs if r["phase"] == "test"]
    val = [r for r in recs if r["phase"] == "val"]
    if sel is None:
        if (
            test
            or (rdir / "test").exists()
            or (rdir / "predictions_test.json").exists()
        ):
            out.append("선택 없이 시험 산출물이 있음")
        return out
    if rep is not None and any(
        sel[k] != (rep.get("selection") or {}).get(k)
        for k in ("L", "B", "cagr", "selected_at")
    ):
        out.append("selection.json ≠ report 선택")
    nq = {k: len(v) for k, v in lk["facts"]["quarter_detail"].items()}
    if sorted((r["quarter"], r["struct"]) for r in val) != sorted(
        (q["id"], st)
        for q in lk["facts"]["quarter_detail"]["val"]
        for st in ("ML_A", "ML_B")
    ):
        out.append(f"검증 모델 분기 · 구조 이상({len(val)} · 기대 {2 * nq['val']})")
    if status == "OK" and len(test) != nq["test"]:
        out.append(f"시험 모델 수 {len(test)} ≠ {nq['test']}")
    if any(r["struct"] != sel["L"] for r in test):
        out.append("시험에 선택하지 않은 구조의 모델")
    when = store.parse_iso(sel["selected_at"])
    if any(store.parse_iso(r["predicted_at"]) > when for r in val):
        out.append("검증 예측이 선택 시각 뒤")
    if any(store.parse_iso(r["train_started_at"]) < when for r in test):
        out.append("시험 학습이 선택 시각 앞(판정 §4 순서)")
    return out


def _same_param(got: Optional[str], want: Any) -> bool:
    """LightGBM 모델 원문의 해석값(문자열)과 고정 설정 비교 — 별칭 · 참거짓 · 수 표기 차이만 맞춘다."""
    if got is None:
        return False
    if isinstance(want, bool):
        return got in (("1", "true") if want else ("0", "false"))
    if isinstance(want, (int, float)):
        try:
            return float(got) == float(want)
        except ValueError:
            return False
    return got == {"regression_l2": "regression"}.get(want, want)


def _check_models(p, t, rows_by_sig, lk, rdir, preds) -> list[str]:
    """모델 기록 칸 전부를 잠금 · 다시 계산한 값과 대조(검증 r1 F2 — 저장 cutoff · 행 · 신호 · 시각 포함)."""
    out: list[str] = []
    fx = lk["facts"]
    cuts = F.quarter_cutoffs(p.axis, *PR.VAL_Q) + F.quarter_cutoffs(p.axis, *PR.TEST_Q)
    now = {c["id"]: c["cutoff"] for c in cuts}
    qd = {ph: {q["id"]: q for q in fx["quarter_detail"][ph]} for ph in ("val", "test")}
    agg: dict[str, dict] = {}
    for f in PR.model_files(rdir):
        rec = PR.load_json(f)
        ph, qid, st = rec.get("phase"), rec.get("quarter"), rec.get("struct")
        q = qd.get(ph, {}).get(qid)
        if (
            q is None
            or st not in M.STRUCTS
            or rec.get("id") != f"{qid}_{st}"
            or f.stem != rec.get("id")
        ):
            out.append(f"{f.name} 모델 식별(단계 · 분기 · 구조 · id) 이상")
            continue
        mid = rec["id"]
        if not (rec.get("cutoff") == q["cutoff"] == now.get(qid)):
            out.append(f"{mid} cutoff {rec.get('cutoff')} ≠ 잠금 {q['cutoff']}")
        if now.get(qid) is None:
            continue
        rows = F.training_rows(t, p.axis, p.axis.index(now[qid]))
        weeks = len({t.rows[r][0] for r in rows})
        if (rec.get("rows"), rec.get("weeks")) != (q["rows"], q["weeks"]) or (
            len(rows),
            weeks,
        ) != (
            q["rows"],
            q["weeks"],
        ):
            out.append(
                f"{mid} 학습 행 · 주 {rec.get('rows')} · {rec.get('weeks')} ≠ 잠금 · 재계산"
            )
        want_sig = sorted(d for d in fx[ph]["plan_signals"] if fx["assign"][d] == qid)
        src = (
            rec.get("predictions") or {}
        )  # 학습 직후 모델과 함께 쓴 예측(멈춘 실행에도 있음)
        if rec.get("signals") != want_sig or sorted(src) != want_sig:
            out.append(f"{mid} 배정 신호 ≠ 잠금 배정")
        try:
            ts, tr, tp = (
                store.parse_iso(rec[k])
                for k in ("train_started_at", "trained_at", "predicted_at")
            )
            if (
                not ts <= tr <= tp
                or abs(rec["seconds"] - (tr - ts).total_seconds()) > 1e-6
            ):
                out.append(f"{mid} 학습 · 예측 시각 순서 · 소요 이상")
        except (KeyError, TypeError, ValueError):
            out.append(f"{mid} 시각 형식 이상")
        diff = rec.get("restore_max_abs_diff")
        if not isinstance(diff, (int, float)) or not 0 <= diff <= M.RESTORE_TOL:
            out.append(f"{mid} 저장 전후 예측 차이 기록 이상")
        text = (f.with_suffix(".txt")).read_text(encoding="utf-8")
        if store.sha256_bytes(text.encode("utf-8")) != rec.get("model_sha256"):
            out.append(f"{mid} 모델 원문 해시 다름")
            continue
        rp = M.resolved_params(text)
        if rp != rec.get("resolved_params"):
            out.append(f"{mid} 해석된 매개변수 기록 다름")
        want = {
            **M.params(st),
            "num_iterations": M.NUM_ROUNDS,
        }  # 반복 300 · early stopping 없음
        bad = sorted(
            k
            for k, w in want.items()
            if k != "verbosity" and not _same_param(rp.get(k), w)
        )
        if bad:
            out.append(f"{mid} 매개변수 ≠ 고정 설정: {', '.join(bad)}")
        booster = M.restore(text)
        key = st if ph == "val" else f"TEST_{st}"
        agg.setdefault(key, {}).update(src)
        for (
            d
        ) in want_sig:  # 잠금 배정 신호로 돈다(기록의 신호 목록이 변조돼도 멈추지 않음)
            i = p.axis.index(d)
            m = F.model_for(i, cuts)
            if m is None or m["id"] != qid or m["cutoff"] > d:
                out.append(f"{mid} 신호 {d} 모델 배정 · cutoff 위반")
            rs = rows_by_sig[i]
            codes = [p.codes[t.rows[r][1]] for r in rs]
            if sorted(src.get(d, {})) != sorted(codes):
                out.append(f"{mid} {d} 예측 종목 ≠ 그날 자격 종목")
            got = M.predict(booster, M.matrix([t.X[r] for r in rs]))
            saved = np.array([src.get(d, {}).get(c, math.nan) for c in codes])
            if not np.all(np.abs(got - saved) <= M.RESTORE_TOL):
                out.append(f"{mid} {d} 복원 예측 ≠ 저장 예측")
    for key, val in preds.items():
        if _norm(val) != _norm(agg.get(key, {})):
            out.append(f"예측 파일 {key} ≠ 모델별 예측 합")
    return out


def _plan_scores(
    p, t, rows_by_sig, signals, src
) -> tuple[dict[int, PO.Plan], dict[str, dict[str, float]]]:
    plans, sc = {}, {}
    for d in signals:
        i = p.axis.index(d)
        rs = rows_by_sig[i]
        s = src(d, rs)
        plans[i] = PO.Plan(signal=i, scores=s, trend_ok=PR.trend_ok(t, rs))
        sc[d] = {p.codes[j]: v for j, v in s.items()}
    return plans, sc


def _check_books_and_report(p, t, rows_by_sig, fx, sig, rdir, preds, rep) -> list[str]:
    out: list[str] = []
    pos = {d: k for k, d in enumerate(p.axis)}
    names = {c: p.series[c].name[-1] for c in p.codes}
    assign = fx["assign"]

    def ml(src):
        return lambda d, rs: {t.rows[r][1]: src[d][p.codes[t.rows[r][1]]] for r in rs}

    def mom(col):
        return lambda d, rs: PR.scores_for(t, rs, col)

    sel = rep.get("selection") or {}
    struct_of = {"ML_A": "ML_A", "ML_B": "ML_B", "L": sel.get("L")}
    for tag, w, sub in (("val", fx["val"], "validation"), ("test", fx["test"], "test")):
        s_i, e_i = pos[w["start"]], pos[w["end"]]
        k_idx = pos[w["k_exec"]]
        if tag == "val":
            srcs = {
                "ML_A": ml(preds.get("ML_A", {})),
                "ML_B": ml(preds.get("ML_B", {})),
                "MOM20": mom("RET_20"),
                "MOM120": mom("RET_120"),
            }
            names_costs = [(n, n, PR.BASE_COST) for n in srcs] + [
                ("K", None, PR.BASE_COST)
            ]
        else:
            if not sel:
                break
            srcs = {
                "L": ml(preds.get(f"TEST_{sel['L']}", {})),
                "B": mom("RET_20" if sel["B"] == "MOM20" else "RET_120"),
            }
            names_costs = [
                (f"{k}_{c}", k if k != "K" else None, cost)
                for c, cost in (("20", PR.BASE_COST), ("40", PR.ALT_COST))
                for k in ("L", "B", "K")
            ]
        books, met, tplans = {}, {}, {}
        for name, key, cost in names_costs:
            f = rdir / sub / f"{name}.json"
            if not f.exists():
                continue
            saved = PR.load_json(f)
            bk = None
            if key is None:
                bk = PO.simulate_bench(p, p.ci[D.BENCH], k_idx, s_i, e_i, cost)
                out += [
                    f"{tag} {name}: {x}" for x in AU.audit_k(p, saved, k_idx, s_i, e_i)
                ]
            else:
                try:
                    plans, sc = _plan_scores(
                        p, t, rows_by_sig, w["plan_signals"], srcs[key]
                    )
                except KeyError as e:
                    # 저장 예측에 신호 · 종목이 없음 = 재적용 불가(멈추지 않고 불일치로 남김)
                    out.append(
                        f"{tag} {name}: 저장 예측 없음({str(e)[:40]}) · 재적용 불가"
                    )
                    plans = None
                if plans is not None:
                    if tag == "test":
                        tplans[key] = plans
                    ids = (
                        PR.model_ids(assign, struct_of[key]) if key in struct_of else {}
                    )
                    for i, pl in plans.items():
                        pl.model_id = ids.get(p.axis[i])
                    bk = PO.simulate(p, plans, s_i, e_i, cost, name, sig)
                    out += [
                        f"{tag} {name}: {x}"
                        for x in AU.audit_book(p, saved, sc, sig, s_i, e_i)
                    ]
            if bk is not None and store.canonical(
                P8.loads(P8.dumps(PO.to_json(bk), compact=True).decode())
            ) != store.canonical(saved):
                out.append(f"{tag} {name}: 정책 재적용 장부 ≠ 저장 장부")
            books[name] = saved
            met[name] = R.curve(
                saved, w["start"], PR.SUB_RANGES if tag == "test" else None, pos, names
            )
        key = "validation" if tag == "val" else "test"
        if store.canonical(_norm(met)) != store.canonical(_norm(rep.get(key) or {})):
            out.append(f"{key} 지표 재계산 ≠ report.json")
        if tag == "val" and rep.get("selection"):
            sel2 = R.select(met)
            if any(
                sel2[k] != rep["selection"].get(k) for k in ("L", "B", "cagr", "rule")
            ):
                out.append("선택 재계산 ≠ report.json")
        if tag == "test" and "explain" in rep:
            ic = {k: R.rank_ic(FL._ic_pairs(t, tplans[k], p)) for k in tplans}
            if _norm(ic) != _norm(rep["explain"].get("rank_ic")):
                out.append("순위 IC 재계산 ≠ report.json")
        if (
            tag == "test" and "bootstrap" in rep
        ):  # 칸이 있으면 값과 무관하게 재계산(빈 값 위조 검출)
            if "L_20" not in books or "B_20" not in books:
                out.append("bootstrap 이 있는데 L_20 · B_20 장부 없음")
                return out
            wk = {p.axis[i] for i in sig}
            wl, tail = R.weekly_returns(books["L_20"]["ledger"], wk, PO.START_VALUE)
            wb, _ = R.weekly_returns(books["B_20"]["ledger"], wk, PO.START_VALUE)
            boot = R.bootstrap([a - b for (_, a), (_, b) in zip(wl, wb)])
            jd = R.judge("OK", met, boot)
            if _norm(boot) != _norm(rep["bootstrap"]) or tail != rep.get(
                "bootstrap_tail_excluded"
            ):
                out.append("bootstrap 재계산 ≠ report.json")
            if _norm(jd) != _norm(rep["judgment"]):
                out.append("판정 재계산 ≠ report.json")
    return out


def _norm(obj: Any) -> Any:
    return P8.loads(P8.dumps(obj, compact=True).decode())
