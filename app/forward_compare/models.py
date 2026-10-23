"""POC6-06 — 네 방법 학습 · 저장 · 복원 · 예측(02 고정 recipe 그대로 · PC CPU).

```text
MEDIAN   종목별 학습 목표 중앙값(06 `model.median`) · JSON · 복원 = 학습 직후 값과 정확히 같음
RIDGE    종목별 StandardScaler → Ridge(alpha=1, svd, intercept)(06 `fit_predict` 와 같은 설정)
         JSON(mean_ · scale_ · coef_ · intercept_) · 복원 numpy 식 = 학습 직후 sklearn 예측(≤ 1e-12)
HGB      initial_trainable 공동 · 02 `HGB_PARAMS` · 날짜 d 행 가중치 1/n_d(02 `fit_hgb`) · joblib
         라이브러리 판이 같을 때만 읽음 · 복원 예측 정확히 같음
MLP_CPU  02 `mlp`(5→64→32→1 · Adam · 200 epoch · seed 42 · 가중 표준화 · 가중 L1) · device=cpu
         torch state_dict + 표준화 JSON · `torch.load(weights_only=True)` · 복원 예측 정확히 같음
```

예측은 [-1, 0] 으로 제한한다. 내가 만들고 해시를 기록한 파일만 읽는다(해시 · 판이 다르면 읽지 않음).
방법 하나의 실패는 그 방법의 실패다(다른 값 복사 · 0 대입 · 이전 판 대체 없음).
"""

from __future__ import annotations

import importlib.metadata
import io
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from app.d20_pooled import mlp
from app.d20_pooled import study as S
from app.forward_compare import protocol as P
from app.ml_evidence import store
from app.reentry_review import model as m06

LIBS = ("scikit-learn", "numpy", "scipy", "joblib", "torch", "threadpoolctl")
ENV_LIBS = {"HGB": ("scikit-learn", "numpy", "scipy", "joblib"), "MLP_CPU": ("torch",)}
FILES = {
    "MEDIAN": ("median.json",),
    "RIDGE": ("ridge.json",),
    "HGB": ("hgb.joblib",),
    "MLP_CPU": ("mlp_state.pt", "mlp_norm.json"),
}
CHECK_ROWS = 64
RIDGE_TOL = 1e-12
RECIPE = {
    "target": m06.RECIPE["target"],
    "features": list(m06.FEATURE_NAMES),
    "feature_formulas": m06.RECIPE["features"],
    "clip": [-1.0, 0.0],
    "MEDIAN": "ticker median of training targets(짝수 = 가운데 두 값 평균)",
    "RIDGE": m06.RECIPE["model"] + " · ticker 별 · 날짜 동일 비중",
    "HGB": {
        "params": S.HGB_PARAMS,
        "weights": "1/n_d",
        "threads": "기본(threadpoolctl 제한 없음)",
    },
    "MLP_CPU": {
        **mlp.SPEC,
        "device": "cpu",
        "microbatch": "전체 표본(epoch 당 한 번 갱신)",
    },
}


class ModelError(Exception):
    pass


def env() -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {"python": sys.version.split()[0]}
    for lib in LIBS:
        try:
            out[lib] = importlib.metadata.version(lib)
        except importlib.metadata.PackageNotFoundError:
            out[lib] = None
    return out


def clip(v: float) -> float:
    return min(0.0, max(-1.0, float(v)))


def date_weights(rows: list[dict]) -> list[float]:
    """날짜 d 의 행마다 1/n_d(공동 학습 · 02 `block_sets` 와 같음)."""
    n: dict[str, int] = {}
    for r in rows:
        n[r["date"]] = n.get(r["date"], 0) + 1
    return [1.0 / n[r["date"]] for r in rows]


def hashes(rows: list[dict]) -> dict[str, str]:
    """실제 X · y · 가중치 · 예제 참조의 해시(설계 §5) + 묶음 해시."""
    h = {
        "x": store.sha256_bytes(store.canonical([r["x"] for r in rows])),
        "y": store.sha256_bytes(store.canonical([r["y"] for r in rows])),
        "w": store.sha256_bytes(store.canonical(date_weights(rows))),
        "refs": store.sha256_bytes(
            store.canonical([[r["ticker"], r["date"], r["origin"]] for r in rows])
        ),
    }
    h["data"] = store.sha256_bytes(store.canonical(h))
    return h


# ── 학습(메모리 모델 + 저장 bytes + 확인용 예측) ──────────────────────────


def _median(rows):
    by: dict[str, list[float]] = {}
    for r in rows:
        by.setdefault(r["ticker"], []).append(r["y"])
    params = {
        t: {"median": m06.median(ys), "n": len(ys)} for t, ys in sorted(by.items())
    }
    files = {"median.json": P.dumps(P.doc("model_median", by_ticker=params))}
    return files, lambda t, x: params[t]["median"]


def _ridge(rows):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["ticker"], []).append(r)
    params, fitted = {}, {}
    for t, rs in sorted(by.items()):
        X = np.asarray([r["x"] for r in rs], dtype=float)
        scaler = StandardScaler().fit(X)
        model = Ridge(alpha=1.0, solver="svd", fit_intercept=True)
        model.fit(scaler.transform(X), [r["y"] for r in rs])
        fitted[t] = (scaler, model)
        params[t] = {
            "mean": [float(v) for v in scaler.mean_],
            "scale": [float(v) for v in scaler.scale_],
            "coef": [float(v) for v in model.coef_],
            "intercept": float(model.intercept_),
            "n": len(rs),
        }

    def predict(t, x):
        scaler, model = fitted[t]
        return float(model.predict(scaler.transform(np.asarray([x], dtype=float)))[0])

    files = {"ridge.json": P.dumps(P.doc("model_ridge", by_ticker=params))}
    return files, predict


def _hgb(rows):
    import joblib

    model = S.fit_hgb(
        [r["x"] for r in rows], [r["y"] for r in rows], date_weights(rows)
    )
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return {"hgb.joblib": buf.getvalue()}, lambda t, x: predict_hgb_raw(model, [x])[0]


def _mlp(rows):
    import torch

    X, y, w = [r["x"] for r in rows], [r["y"] for r in rows], date_weights(rows)
    mean, std = mlp.standardize_params(X, w)
    Xs = mlp.apply_standardize(X, mean, std)
    with mlp.deterministic(torch, mlp.SEED):
        net, opt = mlp.new_model(torch, "cpu")
        X_t, y_t, w_t = mlp.to_tensors(torch, Xs, y, w, "cpu")
        mlp.run_epochs(torch, net, opt, X_t, y_t, w_t, mlp.EPOCHS, len(Xs))
    net.eval()
    buf = io.BytesIO()
    torch.save(net.state_dict(), buf)
    norm = {"mean": mean, "std": std, "device": "cpu", "epochs": mlp.EPOCHS}
    files = {
        "mlp_state.pt": buf.getvalue(),
        "mlp_norm.json": P.dumps(P.doc("model_mlp_norm", **norm)),
    }
    return files, lambda t, x: predict_mlp_raw(net, norm, [x])[0]


FITTERS: dict[str, Callable] = {
    "MEDIAN": _median,
    "RIDGE": _ridge,
    "HGB": _hgb,
    "MLP_CPU": _mlp,
}


def train(rows: list[dict], methods: tuple = P.METHODS) -> dict[str, Any]:
    """방법마다 격리 학습 → 파일 bytes · 상태 · 학습 직후 확인 예측(앞 64행)."""
    check = rows[:CHECK_ROWS]
    files: dict[str, bytes] = {}
    status: dict[str, dict] = {}
    before: dict[str, list[float]] = {}
    current = env()
    for method in methods:
        try:
            got, predict = FITTERS[method](rows)
            before[method] = [predict(r["ticker"], r["x"]) for r in check]
        except ImportError as e:
            status[method] = {
                "status": "NOT_RUN_ENV",
                "reason": f"{type(e).__name__}: {e}"[:200],
            }
            continue
        except Exception as e:  # noqa: BLE001 — 방법마다 격리
            status[method] = {
                "status": "FAILED",
                "reason": f"{type(e).__name__}: {e}"[:200],
            }
            continue
        files.update(got)
        status[method] = {
            "status": "OK",
            "files": sorted(got),
            # 이 방법 파일을 만든 라이브러리 판 — 복구 판이 파일을 그대로 옮겨도 함께 옮긴다
            "env": {lib: current.get(lib) for lib in ENV_LIBS.get(method, ())},
        }
    return {"files": files, "status": status, "check_before": before}


# ── 복원 · 예측 ─────────────────────────────────────────────────────────


def predict_hgb_raw(model, xs: list[list[float]]) -> list[float]:
    import numpy as np

    return [float(v) for v in model.predict(np.asarray(xs, dtype=float))]


def predict_mlp_raw(net, norm: dict[str, Any], xs: list[list[float]]) -> list[float]:
    import torch

    Xs = mlp.apply_standardize(xs, norm["mean"], norm["std"])
    with torch.no_grad():
        out = net(torch.tensor(Xs, dtype=torch.float32)).squeeze(1)
    return [float(v) for v in out.tolist()]


def ridge_raw(p: dict[str, Any], x: list[float]) -> float:
    z = [(xi - m) / s for xi, m, s in zip(x, p["mean"], p["scale"])]
    return sum(c * zi for c, zi in zip(p["coef"], z)) + p["intercept"]


def _open(method: str, blobs: dict[str, bytes]) -> Any:
    if method == "MEDIAN":
        return json.loads(blobs["median.json"])["by_ticker"]
    if method == "RIDGE":
        return json.loads(blobs["ridge.json"])["by_ticker"]
    if method == "HGB":
        import joblib

        return joblib.load(io.BytesIO(blobs["hgb.joblib"]))
    import torch

    net = mlp.build_net(torch)
    net.load_state_dict(
        torch.load(io.BytesIO(blobs["mlp_state.pt"]), weights_only=True)
    )
    net.eval()
    return net, json.loads(blobs["mlp_norm.json"])


class Loaded:
    """저장한 모델 판을 해시 · 라이브러리 판 확인 뒤 읽는다(방법마다 따로)."""

    def __init__(self, folder: Path, meta: dict[str, Any]) -> None:
        self.meta = meta
        self.version = meta["model_version"]
        self.status: dict[str, dict] = {}
        self._m: dict[str, Any] = {}
        current = env()
        for method in P.METHODS:
            st = meta["methods"].get(method, {})
            if st.get("status") != "OK":
                self.status[method] = {
                    "status": st.get("status", "FAILED"),
                    "reason": st.get("reason"),
                }
                continue
            try:
                made = st.get("env") or {
                    lib: meta["env"].get(lib) for lib in ENV_LIBS.get(method, ())
                }
                for lib in ENV_LIBS.get(method, ()):
                    if current.get(lib) != made.get(lib):
                        self.status[method] = {
                            "status": "ENV_MISMATCH",
                            "reason": f"{lib} {made.get(lib)} → {current.get(lib)}",
                        }
                        break
                else:
                    blobs = {}
                    for name in FILES[method]:
                        data = (folder / name).read_bytes()
                        if store.sha256_bytes(data) != meta["file_sha256"][name]:
                            raise ModelError(f"모델 파일 해시 다름: {name}")
                        blobs[name] = data
                    self._m[method] = _open(method, blobs)
                    self.status[method] = {"status": "OK"}
            except Exception as e:  # noqa: BLE001 — 방법마다 격리
                self.status[method] = {
                    "status": "FAILED",
                    "reason": f"{type(e).__name__}: {e}"[:200],
                }

    def raw(self, method: str, ticker: str, x: list[float]) -> float:
        m = self._m[method]
        if method == "MEDIAN":
            return float(m[ticker]["median"])
        if method == "RIDGE":
            return ridge_raw(m[ticker], x)
        if method == "HGB":
            return predict_hgb_raw(m, [x])[0]
        net, norm = m
        return predict_mlp_raw(net, norm, [x])[0]

    def predict(
        self, ticker: str, x: list[float], methods: tuple = P.METHODS
    ) -> dict[str, dict]:
        out = {}
        for method in methods:
            if self.status[method]["status"] != "OK":
                out[method] = dict(self.status[method])
                continue
            if ticker not in self.meta["trainable"]:
                out[method] = {"status": "DATA_SHORT"}
                continue
            try:
                raw = self.raw(method, ticker, x)
            except Exception as e:  # noqa: BLE001
                out[method] = {
                    "status": "FAILED",
                    "reason": f"{type(e).__name__}: {e}"[:200],
                }
                continue
            out[method] = {"status": "OK", "raw": raw, "pred": clip(raw)}
        return out


def restore_check(
    loaded: Loaded, rows: list[dict], before: dict[str, list[float]]
) -> dict:
    """저장 파일로 복원한 예측 = 학습 직후 메모리 모델 예측(같은 고정 입력 · 앞 64행)."""
    check = rows[:CHECK_ROWS]
    out = {}
    for method, want in before.items():
        if loaded.status[method]["status"] != "OK":
            out[method] = {"ok": False, "reason": loaded.status[method]}
            continue
        got = [loaded.raw(method, r["ticker"], r["x"]) for r in check]
        diff = max((abs(a - b) for a, b in zip(got, want)), default=0.0)
        tol = RIDGE_TOL if method == "RIDGE" else 0.0
        out[method] = {
            "ok": diff <= tol,
            "max_abs_diff": diff,
            "rows": len(check),
            "tolerance": tol,
        }
    return out
