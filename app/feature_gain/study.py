"""POC6-08 — 여섯 구성 학습 · 예측 · 모델 bytes · 복원 대조(설계 §4 · PLAN §7 · 판정 §3-1 · §3-3).

```text
행     구간 k: 학습 = 목표 끝 axis[i+20] < 시험 시작(공통 날짜 경계 · 모든 종목 같음) · 시험 = 구간 위치
       여섯 구성 모두 같은 행 집합(V · R 결측으로 빼지 않음)
MEDIAN 종목별 학습 목표 중앙값(m06.median)
RIDGE  종목별 StandardScaler → Ridge(alpha=1, svd) · P 5열 · 학습 날짜 동일 비중(가중치 없음)
HGB    02 HGB_PARAMS · fit_hgb · 날짜별 1/n_d(HGB 네 구성끼리만 같은 행 · 가중치) · 결측 = NaN
예측   원시 + [-1, 0] 제한 · 비유한 = 그 구성 FAILED(다른 구성 값으로 대체 없음)
저장   HGB joblib bytes · RIDGE {feature 순서 · mean · scale · coef · intercept} · MEDIAN 값
복원   저장물만으로 다시 예측 → 학습 직후 원시 예측과 대조(허용 1e-12)
```
"""

from __future__ import annotations

import io
import json
import math
import time
from typing import Any, Callable

from app.d20_pooled import study as S
from app.feature_gain import protocol as P
from app.reentry_review import model as m06

H = m06.H


def clip(v: float) -> float:
    return min(0.0, max(-1.0, float(v)))


def fold_sets(ex: dict[str, Any], k: int) -> tuple[list[dict], list[dict]]:
    """구간 k 의 학습 · 시험 행(모든 종목 같은 날짜 경계)."""
    fold = ex["folds"][k]
    s0, inside = fold[0], set(fold)
    train = [r for r in ex["rows"] if r["i"] + H < s0]
    test = [r for r in ex["rows"] if r["i"] in inside]
    return train, test


def x_of(row: dict[str, Any], cfg: str) -> list[float]:
    """구성의 입력 열(P 5열 + 추가 · 결측 = NaN · HGB 입력에서만)."""
    out = [float(v) for v in row["p"]]
    for extra in P.EXTRA.get(cfg, ()):
        v = row["v"] if extra == "V" else row["r"]
        out.append(float("nan") if v is None else float(v))
    return out


def date_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    n: dict[str, int] = {}
    for r in rows:
        n[r["date"]] = n.get(r["date"], 0) + 1
    return n


def date_weights(rows: list[dict[str, Any]]) -> list[float]:
    """날짜 d 의 행마다 1/n_d(02 · 06 공동 학습과 같은 규칙)."""
    n = date_counts(rows)
    return [1.0 / n[r["date"]] for r in rows]


def model_file(cfg: str) -> str:
    """구성의 저장 파일 이름(verify 가 실행 상태에서 기대 목록을 만든다)."""
    return {"MEDIAN_P": "median.json", "RIDGE_P": "ridge.json"}.get(
        cfg, f"{cfg.lower()}.joblib"
    )


def weights_record(ex: dict[str, Any]) -> dict[str, Any]:
    """examples.json 의 가중치 근거 — 구간별 학습 날짜 n_d(가중치 = 1/n_d 로 다시 만들 수 있음)."""
    return {
        "rule": "HGB 네 구성 = 학습 날짜 d 의 행마다 1/n_d · MEDIAN · RIDGE = 가중치 없음",
        "train_n_by_date": [
            date_counts(fold_sets(ex, k)[0]) for k in range(len(ex["folds"]))
        ],
    }


# ── 구성별 학습(파일 bytes · 원시 예측 함수) ─────────────────────────────────────


def _median(train):
    by: dict[str, list[float]] = {}
    for r in train:
        by.setdefault(r["ticker"], []).append(r["y"])
    params = {
        t: {"median": m06.median(ys), "n": len(ys)} for t, ys in sorted(by.items())
    }
    data = P.dumps({"kind": "MEDIAN_P", "by_ticker": params})
    return (
        {model_file("MEDIAN_P"): data},
        params,
        lambda rows: [params[r["ticker"]]["median"] for r in rows],
    )


def _ridge(train):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    by: dict[str, list[dict]] = {}
    for r in train:
        by.setdefault(r["ticker"], []).append(r)
    fitted, params = {}, {}
    for t, rs in sorted(by.items()):
        X = np.asarray([x_of(r, "RIDGE_P") for r in rs], dtype=float)
        scaler = StandardScaler().fit(X)  # 학습 구간 안에서만
        model = Ridge(alpha=1.0, solver="svd", fit_intercept=True)
        model.fit(scaler.transform(X), [r["y"] for r in rs])
        fitted[t] = (scaler, model)
        params[t] = {
            "features": list(P.P_NAMES),
            "mean": [float(v) for v in scaler.mean_],
            "scale": [float(v) for v in scaler.scale_],
            "coef": [float(v) for v in model.coef_],
            "intercept": float(model.intercept_),
            "n": len(rs),
        }

    def predict(rows):
        """종목별로 묶어 한 번에(값은 행마다 예측과 같음) · 원래 행 순서로 돌려준다."""
        out = [0.0] * len(rows)
        idx: dict[str, list[int]] = {}
        for j, r in enumerate(rows):
            idx.setdefault(r["ticker"], []).append(j)
        for t, js in idx.items():
            scaler, model = fitted[t]
            X = np.asarray([x_of(rows[j], "RIDGE_P") for j in js], dtype=float)
            for j, v in zip(js, model.predict(scaler.transform(X))):
                out[j] = float(v)
        return out

    data = P.dumps({"kind": "RIDGE_P", "by_ticker": params})
    return {model_file("RIDGE_P"): data}, params, predict


def _hgb(cfg: str) -> Callable:
    def fit(train):
        import joblib
        import numpy as np

        model = S.fit_hgb(
            [x_of(r, cfg) for r in train], [r["y"] for r in train], date_weights(train)
        )
        buf = io.BytesIO()
        joblib.dump(model, buf)

        def predict(rows):
            X = np.asarray([x_of(r, cfg) for r in rows], dtype=float)
            return [float(v) for v in model.predict(X)]

        return {model_file(cfg): buf.getvalue()}, None, predict

    return fit


FITTERS: dict[str, Callable] = {
    "MEDIAN_P": _median,
    "RIDGE_P": _ridge,
    **{c: _hgb(c) for c in ("HGB_P", "HGB_PV", "HGB_PR", "HGB_PVR")},
}


def train_fold(train: list[dict], test: list[dict]) -> dict[str, Any]:
    """구성마다 격리 학습 · 시험 행 예측. 실패 · 비유한 예측은 그 구성만 FAILED."""
    out: dict[str, Any] = {}
    for cfg in P.CONFIGS:
        t0 = time.perf_counter()
        try:
            files, params, predict = FITTERS[cfg](train)
            raw = list(predict(test))
        except Exception as e:  # noqa: BLE001 — 구성마다 격리(대체 값 없음)
            out[cfg] = {"status": "FAILED", "reason": f"{type(e).__name__}: {e}"[:200]}
            out[cfg]["seconds"] = time.perf_counter() - t0
            continue
        sec = time.perf_counter() - t0
        if not all(math.isfinite(v) for v in raw):
            out[cfg] = {"status": "FAILED", "reason": "비유한 예측", "seconds": sec}
            continue
        out[cfg] = {
            "status": "OK",
            "files": files,
            "params": params,
            "raw": raw,
            "seconds": sec,
        }
    return out


# ── 복원 대조 ──────────────────────────────────────────────────────────────────


def restore_predict(cfg: str, files: dict[str, bytes], test: list[dict]) -> list[float]:
    """저장물만으로 원시 예측(학습 객체 미사용)."""
    if cfg == "MEDIAN_P":
        p = json.loads(files["median.json"])["by_ticker"]
        return [p[r["ticker"]]["median"] for r in test]
    if cfg == "RIDGE_P":
        p = json.loads(files["ridge.json"])["by_ticker"]
        out = []
        for r in test:
            q = p[r["ticker"]]
            x = x_of(r, "RIDGE_P")
            z = [(xv - m) / s for xv, m, s in zip(x, q["mean"], q["scale"])]
            out.append(sum(c * v for c, v in zip(q["coef"], z)) + q["intercept"])
        return out
    import joblib
    import numpy as np

    model = joblib.load(io.BytesIO(files[f"{cfg.lower()}.joblib"]))
    return [
        float(v)
        for v in model.predict(np.asarray([x_of(r, cfg) for r in test], dtype=float))
    ]


def restore_check(fold_out: dict[str, Any], test: list[dict]) -> dict[str, Any]:
    out = {}
    for cfg, res in fold_out.items():
        if res.get("status") != "OK":
            out[cfg] = {"ok": False, "reason": "학습 실패 · 복원 대상 아님"}
            continue
        again = restore_predict(cfg, res["files"], test)
        diff = max((abs(a - b) for a, b in zip(again, res["raw"])), default=0.0)
        clip_same = all(
            clip(a) == clip(b) or abs(clip(a) - clip(b)) <= P.RESTORE_TOL
            for a, b in zip(again, res["raw"])
        )
        out[cfg] = {
            "ok": len(again) == len(res["raw"]) and diff <= P.RESTORE_TOL and clip_same,
            "max_abs_diff_raw": diff,
            "tolerance": P.RESTORE_TOL,
            "rows": len(again),
        }
    return out


# ── 실행 흐름: lock → run(공식 1회) ─────────────────────────────────────────────


def real_loader(repo, evidence_root):
    """고정 입력 → (Inputs, 축). 거래일 파일은 임시 폴더(호출이 끝나면 지움)."""
    import tempfile
    from pathlib import Path

    from app.feature_gain import inputs as fin

    def load():
        tmp = tempfile.TemporaryDirectory(
            prefix="poc6_08_cal_", ignore_cleanup_errors=True
        )
        inp = fin.load(Path(repo), Path(evidence_root), Path(tmp.name) / "cal")
        ax = fin.build_axis(inp)
        return inp, ax, tmp

    return load


def _plan_from(load) -> tuple[Any, Any, dict]:
    from app.feature_gain import inputs as fin

    inp, ax, tmp = load()
    try:
        return inp, ax, fin.plan(inp, ax)
    finally:
        if tmp is not None:
            tmp.cleanup()


def lock(
    root,
    repo,
    load,
    clock,
    expected=P.EXPECTED,
    base_commit=None,
    correction_reason=None,
) -> dict[str, Any]:
    """protocol 잠금 — 입력 해시 · 축 · T · 구간 · 행 식별자 · 적격 · 가용 · recipe · 코드 근거. 성과 계산 없음.

    잠금은 1회다. 코드 결함 정정으로 실행 코드가 바뀌면 `correction_reason` 과 함께 **정정 잠금**을 새로 만든다
    (이전 잠금 · 실행은 그대로 두고 정정 관계 · 이유 · 바뀐 파일을 적음 · 입력 · recipe 는 이전과 같아야 함 · 판정 §3-3).
    """
    from pathlib import Path

    from app.feature_gain import inputs as fin
    from app.ml_evidence import store

    root = Path(root)
    with P.run_lock(root):
        existing = P.locks(root)
        if existing and not correction_reason:
            raise P.Refused("이미 잠근 protocol 이 있음(공식 1회 · 정정은 사유와 함께)")
        if correction_reason and not existing:
            raise P.Refused("정정할 이전 잠금이 없음")
        inp, ax, pl = _plan_from(load)
        diffs = fin.check_expected(pl, expected)
        if diffs:
            raise P.CheckRequired("PLAN 표와 다름: " + " · ".join(diffs))
        code = P.code_hashes(Path(repo))
        env = P.env()
        recipe = P.recipe()
        corrects = None
        if correction_reason:
            prev_dir, prev = P.active_lock(root)
            if store.canonical(inp.refs) != store.canonical(prev["inputs"]):
                raise P.CheckRequired("정정 잠금의 입력이 이전 잠금과 다름")
            if store.canonical(expected) != store.canonical(prev.get("expected")):
                raise P.CheckRequired("정정 잠금의 PLAN 표가 이전 잠금과 다름")
            if store.canonical(recipe) != store.canonical(prev["recipe"]):
                raise P.CheckRequired(
                    "정정 잠금의 recipe(구성 · 설정 · 기준)가 이전 잠금과 다름"
                )
            changed = sorted(
                f for f in code if code[f] != prev["code"]["sha256"].get(f)
            )
            if not changed and env == prev["env"]:
                raise P.Refused("코드 · 환경이 이전 잠금과 같음 — 정정 잠금 불필요")
            runs_dir = prev_dir / "runs"
            corrects = {
                "lock_id": prev["lock_id"],
                "reason": correction_reason,
                "changed_code": changed,
                "env_changed": env != prev["env"],
                "plan_same": store.canonical(pl) == store.canonical(prev["plan"]),
                "prior_runs": (
                    sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
                    if runs_dir.exists()
                    else []
                ),
            }
        now = clock()
        lock_id = P.new_id(now)
        doc = {
            "schema": "poc6_08_protocol_v1",
            "protocol_id": P.PROTOCOL_ID,
            "lock_id": lock_id,
            "locked_at": store.iso(now),
            "inputs": inp.refs,
            "plan": pl,
            "recipe": recipe,
            "code": {"base_commit": base_commit, "sha256": code},
            "env": env,
            "expected": expected,  # lock 이 대조한 PLAN 표(정정 잠금도 같아야 함)
            "corrects": corrects,
            "note": "lock 은 목표 크기 · 예측 · 오차를 계산하지 않는다(판정 §2).",
        }
        P.write_once(root / lock_id / "protocol.json", P.dumps(doc))
        return doc


def run(root, repo, load, clock, correction_reason=None) -> dict[str, Any]:
    """공식 실행 1회 — 잠금과 입력 · 코드 · 환경 · 계획이 같을 때만. 결과를 보고 다시 돌리지 않는다."""
    from pathlib import Path

    from app.feature_gain import inputs as fin
    from app.ml_evidence import store

    root = Path(root)
    with P.run_lock(root):
        ldir, lk = P.active_lock(root)
        runs_dir = ldir / "runs"
        prior = (
            sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
            if runs_dir.exists()
            else []
        )
        if prior and not correction_reason:
            raise P.Refused(
                "공식 실행이 이미 있음 — 같은 코드 재실행(중단 등)은 사유와 함께 · 코드 정정은 정정 잠금"
                "(성과 때문의 재실행 금지)"
            )
        if P.code_hashes(Path(repo)) != lk["code"]["sha256"]:
            raise P.CheckRequired("실행 코드가 잠금과 다름")
        if P.env() != lk["env"]:
            raise P.CheckRequired("라이브러리 판이 잠금과 다름")
        inp, ax, tmp = load()
        try:
            pl = fin.plan(inp, ax)
            if inp.refs != lk["inputs"] or store.canonical(pl) != store.canonical(
                lk["plan"]
            ):
                raise P.CheckRequired(
                    "입력 · 계획(행 식별자 · 분모 · 가용)이 잠금과 다름"
                )
            started = clock()
            run_id = P.new_id(started)
            rdir = runs_dir / run_id
            meta: dict[str, Any] = {
                "schema": "poc6_08_run_v1",
                "protocol_id": P.PROTOCOL_ID,
                "lock_id": lk["lock_id"],
                "run_id": run_id,
                "started_at": store.iso(started),
                "corrects": prior,
                "correction_reason": correction_reason,
                "lock_corrects": lk.get("corrects"),
            }
            # 실행 식별자를 정한 뒤의 실패는 모두(예제 생성 · 중단 포함) 실패 기록을 남긴다(판정 §3-3 · r1 F1).
            try:
                ex = fin.examples(inp, ax, pl)
                ex["weights"] = weights_record(ex)
                P.write_once(rdir / "examples.json", P.dumps(ex, compact=True))
                return _train_and_report(rdir, lk, meta, ex, clock)
            except BaseException as e:
                _record_failure(rdir, meta, e, clock)
                raise
        finally:
            if tmp is not None:
                tmp.cleanup()


def _record_failure(rdir, meta: dict[str, Any], e: BaseException, clock) -> None:
    """부분 산출물은 그대로 두고 run.json 에 실패를 남긴다(대체 결과 없음). 이미 있으면 두지 않는다."""
    from app.ml_evidence import store

    if (rdir / "run.json").exists():
        return
    try:
        finished = store.iso(clock())
    except Exception:  # noqa: BLE001 — 시계 실패가 실패 기록을 막지 않게
        finished = None
    meta.update(
        status="FAILED", reason=f"{type(e).__name__}: {e}"[:300], finished_at=finished
    )
    try:
        P.write_once(rdir / "run.json", P.dumps(meta))
    except Exception as w:  # noqa: BLE001 — 원래 예외를 올리되 기록 실패를 붙인다
        e.add_note(f"실패 기록(run.json)도 쓰지 못함: {type(w).__name__}: {w}")


def _train_and_report(rdir, lk, meta, ex, clock) -> dict[str, Any]:
    from app.feature_gain import report as R
    from app.ml_evidence import store

    statuses, restores, pred_rows, timing = [], [], [], []
    model_files: dict[str, dict[str, str]] = {}
    for k in range(P.FOLDS):
        train, test = fold_sets(ex, k)
        res = train_fold(train, test)
        fold = f"fold{k + 1}"
        for cfg, r in res.items():
            for name, data in (r.get("files") or {}).items():
                P.write_once(rdir / "models" / fold / name, data)
                model_files.setdefault(fold, {})[name] = store.sha256_bytes(data)
        restores.append(restore_check(res, test))
        statuses.append({c: res[c]["status"] for c in P.CONFIGS})
        timing.append({c: res[c]["seconds"] for c in P.CONFIGS})
        failures = {
            c: res[c].get("reason") for c in P.CONFIGS if res[c]["status"] != "OK"
        }
        if failures:
            restores[-1]["_failures"] = failures
        ok = [c for c in P.CONFIGS if res[c]["status"] == "OK"]
        for j, r in enumerate(test):
            pred_rows.append(
                {
                    "fold": k,
                    "ticker": r["ticker"],
                    "date": r["date"],
                    "target_end": r["target_end"],
                    "truth": r["y"],
                    "raw": {c: res[c]["raw"][j] for c in ok},
                    "preds": {c: clip(res[c]["raw"][j]) for c in ok},
                }
            )
    restore_ok = all(
        restores[k][c]["ok"]
        for k in range(P.FOLDS)
        for c in P.CONFIGS
        if statuses[k][c] == "OK"
    )
    failed = sorted({c for st in statuses for c, v in st.items() if v != "OK"})
    P.write_once(rdir / "predictions.json", P.dumps(pred_rows, compact=True))
    P.write_once(rdir / "restore.json", P.dumps(restores))
    meta.update(
        config_status=statuses,
        failed_configs=failed,
        restore_ok=restore_ok,
        model_files=model_files,
        timing_seconds=timing,
    )
    rep = R.build(lk, meta, pred_rows)
    rep["restore_ok"] = restore_ok
    data = P.dumps(rep)
    P.write_once(rdir / "report.json", data)
    # 글은 저장된 JSON 에서 만든다(verify 가 같은 방법으로 다시 만들어 대조).
    P.write_once(rdir / "report.md", R.markdown(json.loads(data)).encode("utf-8"))
    meta["finished_at"] = store.iso(clock())
    meta["status"] = (
        "RESTORE_MISMATCH" if not restore_ok else "CONFIG_FAILED" if failed else "OK"
    )
    P.write_once(rdir / "run.json", P.dumps(meta))
    return {"run_dir": rdir, "meta": meta, "report": rep}
