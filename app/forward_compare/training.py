"""POC6-06 — 학습 결정 · 예제 묶음 · 모델 판 저장(설계 §5 · 판정 §5).

```text
INITIAL  모델 판이 없을 때 1회(늦은 실행이어도 · 경계 = 그 회차 D · 실제 시각 기록)
MONTHLY  KST 달이 바뀐 뒤 첫 유효 실행(마감 전 입력 있음)에서 새 LOGGED_FORWARD 예제가 있을 때만 · 달마다 최대 1회
         새 예제 없음 = NO_NEW_TRAINING_EXAMPLES(그 달 기회 소진 아님) · 같은 데이터 해시 = 다시 fit 하지 않음
REPAIR   최신 판에서 실패 · 미실행 방법만 같은 예제 묶음으로 다시(정상 방법 재학습 없음 · 달 기회와 무관)
예제     초기 회고(BOOTSTRAP_RETROSPECTIVE) + 주 전향 기록 × 성숙 목표(LOGGED_FORWARD) · (ticker, 기준일) 중복 없음
         목표 끝 < 그 회차 D · 실제 가용 시각 ≤ training_started_at · 진단 · 부가 기록 제외
```
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.forward_compare import bootstrap
from app.forward_compare import models as M
from app.forward_compare import protocol as P
from app.forward_compare import records
from app.ml_evidence import store
from app.reentry_review import prices as px

INITIAL, MONTHLY, REPAIR = "INITIAL", "MONTHLY", "REPAIR"
LOGGED = "LOGGED_FORWARD"


def versions(root: Path) -> list[tuple[Path, dict]]:
    """완료된 모델 판(training.json 이 있는 폴더) · 학습 시작 순."""
    base = root / "models"
    out = []
    for f in sorted(base.glob("mv_*/training.json")) if base.is_dir() else []:
        meta = P.read_json(f)
        if (
            meta.get("schema") != P.SCHEMAS["training"]
            or meta.get("model_version") != f.parent.name
        ):
            raise store.EvidenceError(f"모델 판 기록 이상: {f.parent.name}")
        out.append((f.parent, meta))
    out.sort(
        key=lambda v: (
            store.parse_iso(v[1]["training_started_at"]),
            v[1]["model_version"],
        )
    )
    return out


def _sorted(rows) -> list[dict]:
    """학습 · 해시 · 저장이 모두 같은 순서(기준일 · ticker · origin)."""
    return sorted(rows, key=lambda r: (r["date"], r["ticker"], r["origin"]))


def _rows(doc: dict) -> list[dict]:
    keys = ("ticker", "date", "origin", "x", "y", "target_end", "available_at")
    return [dict(zip(keys, r)) for r in doc["rows"]]


def load_examples(root: Path, ref: dict) -> list[dict]:
    """예제 묶음(+ 참조한 초기 예제) 전체 행 · 파일 해시를 기록과 대조한다."""
    data = (root / ref["path"]).read_bytes()
    if store.sha256_bytes(data) != ref["sha256"]:
        raise store.EvidenceError(f"예제 파일 해시가 기록과 다름: {ref['path']}")
    doc = json.loads(data)
    base = (
        load_examples(root, doc["initial_examples"])
        if doc.get("initial_examples")
        else []
    )
    return _sorted(base + _rows(doc))


def logged_examples(
    root: Path, D: str, started: datetime, trainable: list[str]
) -> tuple[list, dict]:
    """주 전향 기록 × 성숙 목표 → 학습 예제(목표 끝 < D · 가용 ≤ 학습 시작).

    가용 시각 = max(예측 공개 확인 시각(영수증 · 공개의 상한), 목표 계산 시각).
    """
    prims, tgts = records.primaries(root), records.targets(root)
    rows, skipped = [], {
        "target_end_not_before_D": 0,
        "available_after_start": 0,
        "not_trainable": 0,
    }
    for key, prim in sorted(prims.items()):
        tgt = tgts.get(key)
        if tgt is None:
            continue
        if key[0] not in trainable:
            skipped["not_trainable"] += 1
            continue
        if tgt["target_end"] >= D:
            skipped["target_end_not_before_D"] += 1
            continue
        avail = max(
            store.parse_iso(prim["visible_by"]), store.parse_iso(tgt["computed_at"])
        )
        if avail > started:
            skipped["available_after_start"] += 1
            continue
        rows.append(
            {
                "ticker": key[0],
                "date": key[1],
                "origin": LOGGED,
                "x": prim["input"]["features"],
                "y": tgt["target"],
                "target_end": tgt["target_end"],
                "available_at": store.iso(avail),
            }
        )
    return rows, skipped


def _write_examples(
    root: Path, started: datetime, D: str, rows: list[dict], extra: dict
) -> tuple[str, str]:
    eid = P.new_id(started)
    body = P.doc(
        "examples",
        id=eid,
        boundary_D=D,
        row_format=["ticker", "date", "origin", "x", "y", "target_end", "available_at"],
        rows=[
            [
                r[k]
                for k in (
                    "ticker",
                    "date",
                    "origin",
                    "x",
                    "y",
                    "target_end",
                    "available_at",
                )
            ]
            for r in rows
        ],
        origin_counts={
            o: sum(1 for r in rows if r["origin"] == o)
            for o in (bootstrap.ORIGIN, LOGGED)
        },
        hashes=M.hashes(rows),
        **extra,
    )
    path = root / "examples" / f"{eid}.json"
    return P.rel_in(root, path), P.write_once(path, P.dumps(body, compact=True))


def _save(
    root,
    *,
    kind,
    started,
    D,
    rows,
    trainable,
    data_short,
    examples_ref,
    trained,
    parent,
    clock,
    code_commit,
):
    env = M.env()
    h = M.hashes(rows)
    mv = (
        "mv_"
        + store.sha256_bytes(
            store.canonical(
                [
                    P.PROTOCOL_ID,
                    P.COHORT_ID,
                    M.RECIPE,
                    h["data"],
                    env,
                    kind,
                    store.iso(started),
                ]
            )
        )[:16]
    )
    folder = root / "models" / mv
    file_sha = {
        name: P.write_once(folder / name, data)
        for name, data in trained["files"].items()
    }
    meta = P.doc(
        "training",
        model_version=mv,
        kind=kind,
        parent=parent,
        training_started_at=store.iso(started),
        trained_month=P.kst_day(started)[:7],
        boundary_D=D,
        target_end_rule="모든 학습 목표 끝 < boundary_D · 가용 시각 ≤ training_started_at",
        examples=examples_ref,
        rows=len(rows),
        origin_counts={
            o: sum(1 for r in rows if r["origin"] == o)
            for o in (bootstrap.ORIGIN, LOGGED)
        },
        hashes=h,
        trainable=trainable,
        data_short=data_short,
        recipe=M.RECIPE,
        env=env,
        methods={m: dict(v) for m, v in trained["status"].items()},
        file_sha256=file_sha,
        code_commit=code_commit,
        training_completed_at=None,
        restore_check=None,
    )
    loaded = M.Loaded(folder, dict(meta, file_sha256=file_sha))
    meta["restore_check"] = M.restore_check(loaded, rows, trained["check_before"])
    for method, rc in meta["restore_check"].items():
        # 복원 대조 실패 = 그 방법은 쓰지 않는다(기록만 남기고 예측 · 비교 제외)
        if not rc["ok"]:
            meta["methods"][method] = {
                "status": "RESTORE_MISMATCH",
                "reason": f"복원 예측 차 {rc.get('max_abs_diff')} > 허용 {rc.get('tolerance')}",
                "files": meta["methods"][method].get("files"),
            }
    meta["training_completed_at"] = store.iso(clock())
    P.write_once(folder / "training.json", P.dumps(meta))
    return folder, meta


def ensure(
    root: Path,
    *,
    D: str,
    axis: Optional[dict],
    valid_run: bool,
    clock,
    code_commit: Optional[str],
) -> dict[str, Any]:
    """이 회차의 학습 결정 · 실행. 돌려주는 값 = 결정 기록(+ 쓸 모델 판 폴더)."""
    have = versions(root)
    started = clock()
    if not have:
        if axis is None or px.axis_problem(D, axis):
            return {"decision": "TRAINING_PENDING_CALENDAR", "folder": None}
        _, meta_b, prices = bootstrap.load(root)
        ex = bootstrap.build_examples(prices, meta_b, axis, D)
        rows = _sorted(r for r in _rows(ex) if r["ticker"] in ex["initial_trainable"])
        if not rows:
            return {
                "decision": "NO_TRAINABLE_TICKER",
                "folder": None,
                "per_ticker": ex["per_ticker"],
            }
        extra = {
            k: ex[k]
            for k in ("per_ticker", "initial_trainable", "data_short", "bootstrap")
        }
        ref = _write_examples(root, started, D, rows, extra)
        trained = M.train(rows)
        folder, meta = _save(
            root,
            kind=INITIAL,
            started=started,
            D=D,
            rows=rows,
            trainable=ex["initial_trainable"],
            data_short=ex["data_short"],
            examples_ref={"path": ref[0], "sha256": ref[1]},
            trained=trained,
            parent=None,
            clock=clock,
            code_commit=code_commit,
        )
        return {
            "decision": INITIAL,
            "folder": folder,
            "model_version": meta["model_version"],
        }
    folder, latest = have[-1]
    failed = tuple(
        m for m in P.METHODS if latest["methods"].get(m, {}).get("status") != "OK"
    )
    out: dict[str, Any] = {
        "decision": "KEEP",
        "folder": folder,
        "model_version": latest["model_version"],
    }
    if failed:
        out["repair"] = _repair(root, folder, latest, failed, clock, code_commit)
        fixed_folder = out["repair"].pop("folder", None)
        if fixed_folder is not None:
            folder, latest = fixed_folder, P.read_json(fixed_folder / "training.json")
            out.update(folder=folder, model_version=latest["model_version"])
    trained_months = {
        v[1]["trained_month"] for v in have if v[1]["kind"] in (INITIAL, MONTHLY)
    }
    if P.kst_day(started)[:7] in trained_months:
        out["reason"] = "SAME_MONTH_TRAINED"
        return out
    if not valid_run:
        out["reason"] = "NOT_VALID_RUN(그 달 기회 소진 아님)"
        return out
    logged, skipped = logged_examples(root, D, started, latest["trainable"])
    initial = next(v[1] for v in have if v[1]["kind"] == INITIAL)
    base = load_examples(root, initial["examples"])
    seen = {(r["ticker"], r["date"]) for r in base}
    logged = _sorted(r for r in logged if (r["ticker"], r["date"]) not in seen)
    prev = {(r["ticker"], r["date"]) for r in load_examples(root, latest["examples"])}
    new = [r for r in logged if (r["ticker"], r["date"]) not in prev]
    out["logged_skipped"] = skipped
    if not new:
        out["reason"] = "NO_NEW_TRAINING_EXAMPLES"
        return out
    rows = _sorted(base + logged)
    if M.hashes(rows)["data"] == latest["hashes"]["data"]:
        out["reason"] = "SAME_DATA_HASH"
        return out
    ref = _write_examples(
        root, started, D, logged, {"initial_examples": initial["examples"]}
    )
    trained = M.train(rows)
    folder, meta = _save(
        root,
        kind=MONTHLY,
        started=started,
        D=D,
        rows=rows,
        trainable=latest["trainable"],
        data_short=latest["data_short"],
        examples_ref={"path": ref[0], "sha256": ref[1]},
        trained=trained,
        parent=latest["model_version"],
        clock=clock,
        code_commit=code_commit,
    )
    out.update(
        decision=MONTHLY,
        folder=folder,
        model_version=meta["model_version"],
        new_logged=len(new),
    )
    return out


def _repair(root, folder, latest, failed, clock, code_commit) -> dict:
    """실패 · 미실행 방법만 같은 예제 묶음으로 다시 학습. 하나도 고치지 못하면 판을 만들지 않는다."""
    rows = load_examples(root, latest["examples"])
    if M.hashes(rows)["data"] != latest["hashes"]["data"]:
        return {"status": "CHECK_REQUIRED", "reason": "예제 묶음 해시가 판 기록과 다름"}
    started = clock()
    trained = M.train(rows, failed)
    fixed = [m for m in failed if trained["status"][m]["status"] == "OK"]
    if not fixed:
        return {"status": "NOT_FIXED", "methods": trained["status"]}
    for m in P.METHODS:
        if m in failed:
            continue
        for name in M.FILES[m]:
            data = (folder / name).read_bytes()
            if store.sha256_bytes(data) != latest["file_sha256"][name]:
                return {
                    "status": "CHECK_REQUIRED",
                    "reason": f"정상 방법 파일 해시 다름 {name}",
                }
            trained["files"][name] = data
        trained["status"][m] = dict(
            latest["methods"][m], copied_from=latest["model_version"]
        )
    new_folder, meta = _save(
        root,
        kind=REPAIR,
        started=started,
        D=latest["boundary_D"],
        rows=rows,
        trainable=latest["trainable"],
        data_short=latest["data_short"],
        examples_ref=latest["examples"],
        trained=trained,
        parent=latest["model_version"],
        clock=clock,
        code_commit=code_commit,
    )
    return {
        "status": "OK",
        "fixed": fixed,
        "folder": new_folder,
        "model_version": meta["model_version"],
    }
