"""POC6-08 — verify: 새 fit 없이 잠긴 입력 · 저장 산출물만으로 다시 계산 · 대조(판정 §3-3 · r1 F2).

```text
읽기   모든 산출물 = 비유한 수(NaN · Infinity · 1e999) 거절(protocol.loads) · 없거나 손상 = CHECK_REQUIRED
입력   잠긴 입력(해시 고정)에서 계획 · 예제(X · y · 사유 · 가중치 근거)를 다시 만들어 examples.json 과 통째로 대조
예측   시험 행 = 예측 행(순서 · 정답) · 구성별 칸 = 실행 상태 · 제한 = clip(원시)
       저장 모델(기록 해시가 맞는 파일만)로 원시 예측을 다시 계산해 predictions.json 원시 값과 대조(허용 1e-12)
기록   restore.json ↔ run.json · '일치' 표시 = 행 수 · 최대 차 · 모델 목록(실행 상태 기준) · 해시
보고   report.json 전체 재계산 · report.md 재생성 대조 · 실행 상태(run_status)를 함께 돌려줌
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.feature_gain import protocol as P
from app.feature_gain import report as R

ARTIFACTS = ("examples.json", "predictions.json", "report.json", "restore.json")


def _find_run(root: Path, run_id: Optional[str]):
    """run_id 가 있으면 모든 잠금에서 찾고, 없으면 지금 잠금의 마지막 실행."""
    if run_id:
        for ldir, lk in P.locks(root).values():
            d = ldir / "runs" / run_id
            if d.is_dir():
                return ldir, lk, d
        return None, None, None
    ldir, lk = P.active_lock(root)
    runs = (
        sorted(d for d in (ldir / "runs").iterdir() if d.is_dir())
        if (ldir / "runs").exists()
        else []
    )
    return ldir, lk, (runs[-1] if runs else None)


def verify(root, load, run_id: Optional[str] = None) -> dict[str, Any]:
    """`load` = 잠긴 입력 읽기(run 과 같은 함수 · 예제를 다시 만든다)."""
    root = Path(root)
    try:
        ldir, lk, rdir = _find_run(root, run_id)
    except P.CheckRequired as e:
        return {"status": "CHECK_REQUIRED", "problems": [str(e)]}
    if rdir is None:
        return {"status": "CHECK_REQUIRED", "problems": ["실행 없음"]}

    def rd(name: str) -> Any:
        return P.loads((rdir / name).read_text(encoding="utf-8"))

    try:
        meta = rd("run.json")
    except (OSError, ValueError) as e:
        return {
            "status": "CHECK_REQUIRED",
            "run_id": rdir.name,
            "problems": [f"run.json 없음 · 손상(중단된 실행 · 비유한 수): {e}"[:200]],
        }
    if isinstance(meta, dict) and meta.get("status") == "FAILED":
        return {
            "status": "RUN_FAILED",
            "run_id": rdir.name,
            "problems": [f"실행 실패 기록: {meta.get('reason')}"],
        }
    got = {}
    for name in ARTIFACTS:
        try:
            got[name] = rd(name)
        except (OSError, ValueError) as e:
            return {
                "status": "CHECK_REQUIRED",
                "run_id": rdir.name,
                "problems": [f"{name} 없음 · 손상(비유한 수 포함): {e}"[:200]],
            }
    try:
        problems = _check(lk, meta, got, rdir)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        problems = [f"산출물 형식 손상(다시 계산 불가): {type(e).__name__}: {e}"[:200]]
    try:  # 다른 문제가 있어도 입력 대조까지 한다(확인 범위를 줄이지 않음)
        problems += _against_inputs(lk, got["examples.json"], load)
    except P.CheckRequired as e:
        problems.append(f"잠긴 입력을 다시 읽지 못함: {e}"[:200])
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        problems.append(f"예제 형식 손상(입력 대조 불가): {type(e).__name__}"[:200])
    return {
        "status": "OK" if not problems else "MISMATCH",
        "run_id": rdir.name,
        # 산출물이 서로 맞아도 실행 자체의 상태(복원 불일치 · 구성 실패)를 숨기지 않는다.
        "run_status": meta.get("status"),
        "problems": problems,
    }


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check(lk, meta, got, rdir) -> list[str]:
    from app.feature_gain import study as ST
    from app.ml_evidence import store

    ex, preds = got["examples.json"], got["predictions.json"]
    problems: list[str] = []
    pl = lk["plan"]
    if meta.get("lock_id") != lk["lock_id"]:
        problems.append("run.json 의 잠금이 폴더 잠금과 다름")
    if ex.get("weights") != ST.weights_record(ex):
        problems.append("examples.json 가중치 근거(n_d)가 학습 행과 다름")
    tests = []
    for k in range(P.FOLDS):
        train, test = ST.fold_sets(ex, k)
        tests.append(test)
        for part, rows in (("train", train), ("test", test)):
            ids = store.canonical([[r["ticker"], r["date"]] for r in rows])
            if store.sha256_bytes(ids) != pl["ids_sha256"][part][k]:
                problems.append(f"구간 {k + 1} {part} 행 식별자가 잠금과 다름")
        fold_preds = [p for p in preds if p["fold"] == k]
        if [(p["ticker"], p["date"], p["truth"]) for p in fold_preds] != [
            (r["ticker"], r["date"], r["y"]) for r in test
        ]:
            problems.append(f"구간 {k + 1} 예측 행이 시험 행과 어긋남")
        ok = [c for c in P.CONFIGS if meta["config_status"][k][c] == "OK"]
        for p in fold_preds:
            if sorted(p["preds"]) != sorted(ok) or sorted(p["raw"]) != sorted(ok):
                problems.append(f"구간 {k + 1} 구성별 예측 칸이 어긋남")
                return problems  # 칸이 어긋나면 지표를 다시 계산할 수 없음
            vals = [p["truth"], *p["raw"].values(), *p["preds"].values()]
            if not all(_num(v) for v in vals):
                problems.append(f"구간 {k + 1} 예측 · 정답이 수가 아님")
                return problems
            if any(p["preds"][c] != ST.clip(p["raw"][c]) for c in ok):
                problems.append(f"구간 {k + 1} 제한 예측 ≠ clip(원시)")
                break
    if pl["review"] != [t for t in pl["eligible"] if t not in P.REVIEW_OUT]:
        problems.append("G_REVIEW 구성원이 설계와 다름")
    problems += _models_and_restore(meta, got, rdir, tests, preds)
    again = R.build(lk, meta, preds)
    again["restore_ok"] = meta["restore_ok"]
    if store.canonical(again) != store.canonical(got["report.json"]):
        problems.append("저장 보고서 ≠ 저장 예측에서 다시 계산한 보고서")
    try:
        md = (rdir / "report.md").read_text(encoding="utf-8")
        md_same = md == R.markdown(got["report.json"])
    except OSError:
        md_same = False
    if not md_same:
        problems.append("report.md ≠ report.json 에서 다시 만든 글")
    return problems


def _models_and_restore(meta, got, rdir, tests, preds) -> list[str]:
    """모델 목록 · 해시 → 기록 해시가 맞는 모델로 원시 예측 재계산 · restore.json 표시 대조."""
    from app.feature_gain import study as ST
    from app.ml_evidence import store

    problems: list[str] = []
    restores = got["restore.json"]
    recorded = meta.get("model_files") or {}
    if set(recorded) - {f"fold{k + 1}" for k in range(P.FOLDS)}:
        problems.append("모델 파일 기록에 없는 구간이 있음")
    restore_all = True
    for k, test in enumerate(tests):
        fold = f"fold{k + 1}"
        ok = [c for c in P.CONFIGS if meta["config_status"][k][c] == "OK"]
        want = {ST.model_file(c) for c in ok}
        listed = recorded.get(fold) or {}
        d = rdir / "models" / fold
        on_disk = {f.name for f in d.iterdir()} if d.is_dir() else set()
        if set(listed) != want or on_disk != want:
            problems.append(f"모델 파일 목록이 실행 상태와 다름: {fold}")
        fold_preds = [p for p in preds if p["fold"] == k]
        for c in ok:
            name = ST.model_file(c)
            e = restores[k][c]
            restore_all = restore_all and e["ok"] is True
            if e["ok"] and not (
                e["rows"] == len(test) and e["max_abs_diff_raw"] <= P.RESTORE_TOL
            ):
                problems.append(f"restore.json '일치' 표시가 수치와 다름: {fold}/{c}")
            if name not in listed or name not in on_disk:
                continue
            data = (d / name).read_bytes()
            if store.sha256_bytes(data) != listed[name]:
                problems.append(f"모델 파일 해시 불일치: {fold}/{name}")
                continue  # 기록과 다른 파일은 열지 않는다
            try:
                again = ST.restore_predict(c, {name: data}, test)
            except Exception as err:  # noqa: BLE001 — 복원 실패 = 불일치(대체 없음)
                problems.append(
                    f"저장 모델 복원 실패: {fold}/{c}: {type(err).__name__}"
                )
                continue
            stored = [p["raw"][c] for p in fold_preds]
            if len(again) != len(stored) or any(
                abs(a - b) > P.RESTORE_TOL for a, b in zip(again, stored)
            ):
                problems.append(f"원시 예측 ≠ 저장 모델로 다시 계산한 값: {fold}/{c}")
    if restore_all != meta.get("restore_ok"):
        problems.append("restore.json 과 run.json 의 복원 결과가 다름")
    return problems


def _against_inputs(lk, ex, load) -> list[str]:
    """잠긴 입력 → 계획 · 예제 다시 만들기(학습 없음) → examples.json 통째로 대조."""
    from app.feature_gain import inputs as fin
    from app.feature_gain import study as ST
    from app.ml_evidence import store

    inp, ax, tmp = load()
    try:
        pl = fin.plan(inp, ax)
        if store.canonical(inp.refs) != store.canonical(lk["inputs"]) or (
            store.canonical(pl) != store.canonical(lk["plan"])
        ):
            return ["잠긴 입력에서 다시 만든 계획이 잠금과 다름"]
        again = fin.examples(inp, ax, pl)
        again["weights"] = ST.weights_record(again)
    finally:
        if tmp is not None:
            tmp.cleanup()
    if store.canonical(again) != store.canonical(ex):
        return ["examples.json ≠ 잠긴 입력에서 다시 만든 예제(X · y · 사유)"]
    return []
