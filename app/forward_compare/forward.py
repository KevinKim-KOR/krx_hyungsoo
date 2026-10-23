"""POC6-06 — PC 수동 run 한 번: 보관본 확인 → 성숙 → 학습 결정 → 예측 기록 → 보고(설계 §6 · §7).

```text
D            05 거래일 파일(그 묶음의 object) 기준 오늘 KST 직전 거래일 = 05 '최근 완료 거래일'과 같은 규칙
마감         D 다음 거래일 15:30 KST(CLOSE_CUTOFF) · 다음 거래일을 못 정하면 판정 안 함(PENDING_CALENDAR)
시각         입력 공개 · PC 수신 ≤ input_cutoff ≤ 계산 시작 · 학습 완료 ≤ 예측 시작 · 공개 = 파일을 놓기 직전 실제 시각
기록 종류    놓기 직전 시각 < 마감 = FORWARD_RESEARCH 후보 · 아니면 DIAGNOSTIC(SKIPPED_TOO_LATE · 성과 · 학습 제외)
             후보는 놓인 뒤 찍은 공개 확인 영수증(.receipt.json · 공개 시각의 상한) < 마감 일 때만 주 기록
잠금         연구 폴더 단일 실행(`.run.lock` · 다른 실행 중이면 P.Busy · 아무것도 쓰지 않음)
중복         (ticker, D) 의 첫 주 기록 고정 · 같은 입력 재실행 = 새 예측 없음 · 다른 입력 = SUPPLEMENTARY
             주 기록에서 실패한 방법 = 같은 입력 · 같은 모델 판일 때만 RETRY 로 연결(마감 전)
```

과거 시각을 입력받는 인자는 없다. SSH · 외부 조회는 이 모듈에서 하지 않는다(--pull · --archive 는 CLI 가 명시 실행).
"""

from __future__ import annotations

import time as _time
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Callable, Optional

from app import trading_day_lag as tdl
from app.forward_compare import cohort as C
from app.forward_compare import inputs, mature, records, report, training
from app.forward_compare import models as M
from app.forward_compare import protocol as P
from app.ml_evidence import store
from app.reentry_review import model as m06
from app.reentry_review import prices as px


def close_cutoff(next_day: str) -> datetime:
    hh, mm = (int(v) for v in P.CLOSE_CUTOFF.split(":"))
    return datetime.combine(date.fromisoformat(next_day), time(hh, mm), P.KST)


def _seen(root: Path, D: str) -> set[tuple]:
    """이미 남긴 진단 · 부가 · 재시도 — 같은 재실행이 새 기록을 다시 쓰지 않게(설계 §7 기존 기록 반환)."""
    out = set()
    for d in records.prediction_docs(root):
        if d["D"] != D:
            continue
        mv = d["model"]["model_version"]
        for e in d["entries"]:
            role = e["role"]
            if role in ("DIAGNOSTIC", "SUPPLEMENTARY"):
                out.add((role, e["ticker"], e["input"]["source"]["object"], mv))
            elif role == "RETRY":
                out |= {(role, e["ticker"], m, mv) for m in e["methods"]}
    return out


def _entries(root, D, tickers, sel, loaded, late_now) -> tuple[list, list, list]:
    prims = records.primaries(root)
    seen = _seen(root, D)
    entries, missing, existing = [], [], []
    for t in tickers:
        s = sel[t]
        if s["status"] != "OK":
            missing.append({"ticker": t, "status": s["status"], "tried": s["tried"]})
            continue
        x, obj, mv = s["features"], s["source"]["object"], loaded.version
        prim = prims.get((t, D))
        if prim is None:
            if late_now and ("DIAGNOSTIC", t, obj, mv) in seen:
                existing.append({"ticker": t, "role": "DIAGNOSTIC_EXISTS"})
                continue
            entries.append(
                {
                    "ticker": t,
                    "role": "PRIMARY",
                    "input": s,
                    "methods": loaded.predict(t, x),
                }
            )
            continue
        if prim["input"]["source"]["object"] != obj:
            if ("SUPPLEMENTARY", t, obj, mv) in seen or (
                late_now and ("DIAGNOSTIC", t, obj, mv) in seen
            ):
                existing.append({"ticker": t, "role": "SUPPLEMENTARY_EXISTS"})
                continue
            entries.append(
                {
                    "ticker": t,
                    "role": "SUPPLEMENTARY",
                    "primary_run": prim["run_id"],
                    "input": s,
                    "methods": loaded.predict(t, x),
                }
            )
            continue
        # 재시도 = 주 기록에서 예측 실행이 실패했고 · 같은 판에서 그 방법을 읽을 수 있고 · 아직 안 해 본 것만
        # (학습 실패 · 판 불일치 · 자료 부족은 같은 판에서 다시 해도 같다)
        failed = tuple(
            m
            for m in P.METHODS
            if prim["methods"][m].get("status") == "FAILED"
            and loaded.status[m]["status"] == "OK"
            and ("RETRY", t, m, mv) not in seen
        )
        if failed and prim["model_version"] == mv and not late_now:
            entries.append(
                {
                    "ticker": t,
                    "role": "RETRY",
                    "retry_of": prim["run_id"],
                    "input": s,
                    "methods": loaded.predict(t, x, failed),
                }
            )
        else:
            existing.append(
                {"ticker": t, "role": "PRIMARY_EXISTS", "primary_run": prim["run_id"]}
            )
    return entries, missing, existing


def confirm_pending(root: Path, clock: Callable[[], datetime]) -> list[dict]:
    """영수증 없는 전향 후보(예: 놓은 뒤 영수증 전 중단) — 지금이 그 마감 전이면 공개 확인을 남긴다.

    확인 시각 = 지금(파일이 이미 놓여 있음을 본 시각 = 공개 시각의 상한). 마감이 지났으면 남기지 않는다
    (그 기록은 전향 기록이 아니다). 영수증 파일이 이미 있으면(손상 포함) 손대지 않는다.
    """
    done = []
    for d in records.prediction_docs(root):
        rp = records.receipt_path(d["_path"])
        if d["record_type"] != records.FORWARD or rp.exists():
            continue
        now = clock()
        cutoff = store.parse_iso(d["times"]["close_cutoff_at"])
        if now < cutoff:
            records.write_receipt(root, d["_path"], now, "LATER_RUN_BEFORE_CUTOFF")
            done.append({"id": d["id"], "D": d["D"], "confirmed_at": store.iso(now)})
        else:
            done.append(
                {"id": d["id"], "D": d["D"], "unconfirmed": "마감 뒤 — 전향 기록 아님"}
            )
    return done


@P.exclusive  # 같은 연구 폴더에 다른 실행이 있으면 P.Busy · 아무것도 쓰지 않음
def run(
    root: Path,
    ev_root: Path,
    *,
    clock: Callable[[], datetime] = store.utc_now,
    code_commit: Optional[str] = None,
) -> dict[str, Any]:
    t0 = _time.monotonic()
    input_cutoff = clock()
    last = records.latest_recorded(root)
    if (
        last is not None and input_cutoff < last
    ):  # 시계 역행 — 마감 판정을 믿을 수 없다(검토 L1)
        raise P.ClockBehind(
            f"지금 {store.iso(input_cutoff)} < 이미 남은 기록 {store.iso(last)}"
        )
    started = clock()
    rid = P.new_id(started)
    cohort = C.load(root)
    tickers = list(cohort["tickers"])
    ev = inputs.Evidence(ev_root, input_cutoff, tickers=set(tickers))
    out: dict[str, Any] = {
        "id": rid,
        "input_cutoff": store.iso(input_cutoff),
        "computation_started_at": store.iso(started),
        "today_kst": P.kst_day(started),
        "inventory": ev.inventory(),
        "excluded_runs": ev.excluded,
    }
    out["confirmed_earlier"] = confirm_pending(root, clock)
    try:
        out.update(_run(root, ev, rid, cohort, tickers, started, clock, code_commit))
    finally:
        ev.close()
    out["report"] = report.write(root, cohort, rid, clock)
    out["finished_at"] = store.iso(clock())
    out["resources"] = {
        "elapsed_s": round(_time.monotonic() - t0, 3),
        "max_rss": store.max_rss(),
    }
    P.write_once(root / "runs" / f"{rid}.json", P.dumps(P.doc("run", **out)))
    return out


def _run(root, ev, rid, cohort, tickers, started, clock, code_commit) -> dict[str, Any]:
    latest = ev.latest()
    if latest is None:
        return {"status": "NO_EVIDENCE"}
    dates, cal_dir, axis_ref = ev.axis_inputs(latest)
    D = tdl.expected_previous_trading_day(P.kst_day(started), calendar_dir=cal_dir)
    nxt = inputs.next_trading_day(D, cal_dir) if D else None
    res: dict[str, Any] = {
        "D": D,
        "next_trading_day": nxt,
        "calendar_from_run": latest.run_id,
    }
    res["maturity"] = mature.evaluate(root, ev, clock, rid)
    if D is None or nxt is None:
        return {**res, "status": "PENDING_CALENDAR"}
    cutoff_at = close_cutoff(nxt)
    res["close_cutoff_at"] = store.iso(cutoff_at)
    sel = {t: ev.select_input(t, D) for t in tickers}
    res["input_ok"] = sum(1 for s in sel.values() if s["status"] == "OK")
    timely = clock() < cutoff_at
    prims = records.primaries(root)
    new_primary = [
        t for t in tickers if sel[t]["status"] == "OK" and (t, D) not in prims
    ]
    # 유효 실행 = 마감 전 · 아직 주 기록이 없는 종목의 입력이 있음(같은 날 재실행이 달 학습을 쓰지 않게)
    valid_run = timely and bool(new_primary)
    res["valid_run"] = valid_run
    axis = px.research_axis(D, dates[0], dates, calendar_dir=cal_dir) if dates else None
    tr = training.ensure(
        root, D=D, axis=axis, valid_run=valid_run, clock=clock, code_commit=code_commit
    )
    res["training"] = {k: (str(v) if isinstance(v, Path) else v) for k, v in tr.items()}
    if tr.get("folder") is None:
        return {**res, "status": "NO_MODEL"}
    meta = P.read_json(tr["folder"] / "training.json")
    loaded = M.Loaded(tr["folder"], meta)
    pred_started = clock()
    if store.parse_iso(meta["training_completed_at"]) > pred_started:
        return {
            **res,
            "status": "CHECK_REQUIRED",
            "reason": "학습 완료 시각이 예측 시작보다 늦음",
        }
    late_now = clock() >= cutoff_at
    entries, missing, existing = _entries(root, D, tickers, sel, loaded, late_now)
    res.update(existing=existing, not_predicted=missing)
    if not entries:
        return {**res, "status": "ALREADY_RECORDED" if existing else "NO_INPUT"}
    finished = clock()
    path = root / "predictions" / D / f"{rid}.json"
    common = dict(
        id=rid,
        D=D,
        cohort_id=cohort["cohort_id"],
        cohort_sha256=store.sha256_file(C.path(root)),
        target_definition=m06.RECIPE["target"],
        unit="ratio(−0.05 = −5%) · [-1, 0] 제한 후 pred · 제한 전 raw",
        feature_names=list(m06.FEATURE_NAMES),
        axis={"from_run": latest.run_id, **axis_ref},
        model={
            "model_version": meta["model_version"],
            "kind": meta["kind"],
            "training": f"models/{meta['model_version']}/training.json",
            "file_sha256": meta["file_sha256"],
            "boundary_D": meta["boundary_D"],
            "env": meta["env"],
            "method_status": loaded.status,
        },
        code_commit=code_commit,
        not_predicted=missing,
    )

    def build(forward: bool, published: datetime) -> bytes:
        kept = (
            entries
            if forward
            else [dict(e, role="DIAGNOSTIC") for e in entries if e["role"] != "RETRY"]
        )
        times = {
            "input_cutoff": store.iso(ev.cutoff),
            "computation_started_at": store.iso(started),
            "training_completed_at": meta["training_completed_at"],
            "prediction_started_at": store.iso(pred_started),
            "computation_finished_at": store.iso(finished),
            # 파일 쓰기 시작 직전 시각(하한) · 실제 공개의 상한 = 영수증 confirmed_at
            "published_at": store.iso(published),
            "next_trading_day": res["next_trading_day"],
            "close_cutoff_at": res["close_cutoff_at"],
        }
        body = P.doc(
            "prediction",
            record_type=records.FORWARD if forward else records.DIAGNOSTIC,
            status="FORWARD_CANDIDATE" if forward else "SKIPPED_TOO_LATE",
            validity_rule=(
                "FORWARD_RESEARCH 는 같은 이름 .receipt.json 의 해시가 맞고"
                " confirmed_at < close_cutoff_at 일 때만 전향 기록(아니면 성과 · 학습 제외)"
            ),
            times=times,
            entries=kept,
            excluded_from_performance=not forward,
            **common,
        )
        return P.dumps(body)

    published = clock()
    forward = published < cutoff_at
    linked = None
    if forward:  # 임시 파일 · fsync 가 끝난 뒤 놓기 직전에 마감을 다시 본다(F1)
        linked = P.write_once(path, build(True, published), lambda: clock() < cutoff_at)
        if linked is not None:
            confirmed = clock()  # 놓인 뒤의 시각 = 공개 시각의 상한
            # 마감 뒤 확인도 남긴다 — 무효로 남고 이후 run 이 다시 확인하지 못한다(검토 L1)
            records.write_receipt(root, path, confirmed, "RUN_AFTER_LINK")
            res["confirmed_at"] = store.iso(confirmed)
            res["publication_confirmed"] = confirmed < cutoff_at
    if linked is None:
        forward = False
        P.write_once(path, build(False, clock()))
    confirmed_ok = forward and res.get("publication_confirmed") is True
    kinds = {e["role"] for e in entries} if forward else {"DIAGNOSTIC"}
    res.update(
        status="OK" if confirmed_ok else "SKIPPED_TOO_LATE",
        record_type=records.FORWARD if forward else records.DIAGNOSTIC,
        publication_confirmed=confirmed_ok,
        prediction=P.rel_in(root, path),
        roles={
            r: sum(1 for e in entries if (e["role"] if forward else "DIAGNOSTIC") == r)
            for r in kinds
        },
    )
    return res
