"""POC6-02 — RTX PC GPU 실행기(PLAN 판정 §3 · §3-1). 사용: 이 폴더에서 `python gpu_runner.py` 한 번.

필요한 것 = Python + CUDA 용 PyTorch 뿐(저장소 · 시장 DB · scikit-learn · numpy · 서버 · 키 불필요 · 인터넷 0).
같은 폴더의 `mlp.py`(맥북 시험과 같은 학습 본문)와 `gpu_input.json` 을 읽어 `gpu_result.json` 을 쓴다.

```text
1. 환경 확인   Python · torch · CUDA · 장치 — torch 없음 · CUDA 없음 = GPU_NOT_RUN(원인 기록 · CPU 로 바꾸지 않음)
2. 입력 확인   gpu_input.json 을 읽고 digest 를 다시 계산해 같아야 함 · 이 폴더 mlp.py · gpu_runner.py 의 sha256 이
               입력에 적힌 값과 같아야 함(아니면 CHECK_REQUIRED · 학습 0)
3. 예비 측정   1구간 학습 자료로 microbatch {min(N,256), min(N,4096), N}(중복 제거)마다 warm-up 1 + 3 epoch
               · 처리량 · 최대 VRAM · OOM 기록 → 작동한 가장 큰 크기 사용 · 같은 MLP 의 CPU / CUDA 속도 비교
               · 모든 크기가 메모리 부족이면 RUN_FAILED(크기 1 등으로 몰래 낮추지 않음)
4. 공식 실행   구간마다 200 epoch 학습 · 시험 예측(raw) · 같은 입력으로 한 번 더 학습해 예측 차이 ≤ 1e-6 확인
               · 예측에 유한하지 않은 값이 있으면 RUN_FAILED
```

각 구간이 예측하는 시험 행의 정답은 그 구간 학습 자료에 없다(앞 구간 시험 행의 정답은 뒤 구간 학습에 들어간다 —
앞으로 굴려 가는 학습). 결과 파일은 맥북 `merge` 가 study ID · digest · 코드 해시 · 행 ID 를 대조해 붙인다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))

SCHEMA = "poc6_02_gpu_result_v1"
GPU_NOT_RUN, CHECK_REQUIRED, RUN_FAILED, OK = (
    "GPU_NOT_RUN",
    "CHECK_REQUIRED",
    "RUN_FAILED",
    "OK",
)
PROBE_EPOCHS = 3
DEVICE = "cuda"  # 공식 GPU 장치(시험만 "cpu" 로 바꿔 같은 경로를 확인)


def code_sha256() -> dict:
    out = {}
    for name in ("mlp.py", "gpu_runner.py"):
        with open(os.path.join(HERE, name), "rb") as f:
            out[name] = hashlib.sha256(f.read()).hexdigest()
    return out


def canonical_hash(payload) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def peak_rss_mb():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            c = Counters()
            c.cb = ctypes.sizeof(Counters)
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb
            )
            return round(c.PeakWorkingSetSize / 1024 / 1024, 1) if ok else None
        except Exception:  # noqa: BLE001 — 측정 실패는 값 없음
            return None
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(
            rss * (1.0 if sys.platform == "darwin" else 1024.0) / 1024 / 1024, 1
        )
    except Exception:  # noqa: BLE001
        return None


def environment(torch=None) -> dict:
    env = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "torch": None,
        "cuda_runtime": None,
        "cudnn": None,
        "cuda_available": False,
        "device": None,
        "vram_total_bytes": None,
    }
    if torch is not None:
        env["torch"] = torch.__version__
        env["cuda_runtime"] = torch.version.cuda
        env["cuda_available"] = bool(torch.cuda.is_available())
        if env["cuda_available"]:
            p = torch.cuda.get_device_properties(0)
            env["device"] = p.name
            env["vram_total_bytes"] = int(p.total_memory)
            env["cudnn"] = torch.backends.cudnn.version()
    return env


def _sync(torch, device):
    if device == "cuda":
        torch.cuda.synchronize()


def epoch_seconds(torch, mlp, blk, device, mb) -> dict:
    """같은 MLP · 같은 자료로 warm-up 1 + 3 epoch(시험 예측 0). 전송 시간은 따로 잰다."""
    Xs = mlp.apply_standardize(blk["train_X"], blk["mean"], blk["std"])
    with mlp.deterministic(torch):
        net, opt = mlp.new_model(torch, device)
        _sync(torch, device)
        t0 = time.perf_counter()
        X_t, y_t, w_t = mlp.to_tensors(
            torch, Xs, blk["train_y"], blk["train_w"], device
        )
        _sync(torch, device)
        transfer = time.perf_counter() - t0
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        mlp.run_epochs(torch, net, opt, X_t, y_t, w_t, 1, mb)  # warm-up
        _sync(torch, device)
        t1 = time.perf_counter()
        mlp.run_epochs(torch, net, opt, X_t, y_t, w_t, PROBE_EPOCHS, mb)
        _sync(torch, device)
        sec = (time.perf_counter() - t1) / PROBE_EPOCHS
    out = {
        "device": device,
        "microbatch": mb,
        "rows": len(Xs),
        "seconds_per_epoch": sec,
        "rows_per_second": len(Xs) / sec if sec > 0 else None,
        "transfer_seconds": transfer,
    }
    if device == "cuda":
        out["peak_vram_bytes"] = int(torch.cuda.max_memory_allocated())
    return out


class AllSizesOOM(RuntimeError):
    """모든 microbatch 크기에서 GPU 메모리 부족."""


def probe(torch, mlp, blk) -> dict:
    n = len(blk["train_X"])
    sizes = sorted({min(n, 256), min(n, 4096), n})
    rows, chosen = [], None
    for mb in sizes:
        try:
            rows.append(epoch_seconds(torch, mlp, blk, DEVICE, mb))
            chosen = mb
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            rows.append({"device": DEVICE, "microbatch": mb, "oom": True})
    if chosen is None:
        raise AllSizesOOM(f"모든 microbatch 크기 {sizes} 에서 GPU 메모리 부족")
    cpu = epoch_seconds(torch, mlp, blk, "cpu", chosen)
    cuda = next(
        (r for r in rows if r.get("microbatch") == chosen and not r.get("oom")), None
    )
    return {
        "microbatch_probe": rows,
        "chosen_microbatch": chosen,
        "same_mlp_cpu_vs_cuda": {
            "cpu": cpu,
            "cuda": cuda,
            "cuda_speedup_excluding_transfer": (
                cpu["seconds_per_epoch"] / cuda["seconds_per_epoch"]
                if cuda and cuda["seconds_per_epoch"] > 0
                else None
            ),
            "cpu_threads": torch.get_num_threads(),
        },
    }


def official(torch, mlp, blocks, mb) -> dict:
    out, max_diff = [], 0.0
    for blk in blocks:
        args = (
            blk["train_X"],
            blk["train_y"],
            blk["train_w"],
            blk["test_X"],
            blk["mean"],
            blk["std"],
        )
        t0 = time.perf_counter()
        pred = mlp.train_predict(
            *args, device=DEVICE, microbatch=min(mb, len(blk["train_X"]))
        )
        _sync(torch, DEVICE)
        fit_s = time.perf_counter() - t0
        again = mlp.train_predict(
            *args, device=DEVICE, microbatch=min(mb, len(blk["train_X"]))
        )
        if not all(math.isfinite(v) for v in list(pred) + list(again)):
            raise FloatingPointError(
                f"{blk['block']}구간 예측에 유한하지 않은 값(NaN · inf)"
            )
        diff = max((abs(a - b) for a, b in zip(pred, again)), default=0.0)
        max_diff = max(max_diff, diff)
        out.append(
            {
                "block": blk["block"],
                "test_ids": blk["test_ids"],
                "pred": pred,
                "fit_predict_seconds": fit_s,
                "repeat_max_abs_diff": diff,
            }
        )
    return {"blocks": out, "repeat_max_abs_diff": max_diff}


def main() -> int:
    # 직접 실행할 때만 — CUDA 초기화 전에 결정적 행렬 곱 설정 · 같은 폴더의 mlp.py 를 찾게 한다
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    started = time.perf_counter()
    result = {
        "schema": SCHEMA,
        "study_id": None,
        "input_digest": None,
        "recipe_digest": None,
        "bundle_digest": None,
        "code_sha256": None,
        "status": None,
        "reason": None,
    }
    try:
        try:
            with open(os.path.join(HERE, "gpu_input.json"), encoding="utf-8") as f:
                inp = json.load(f)
            if not isinstance(inp, dict):
                raise ValueError("JSON 객체가 아님")
        except (OSError, ValueError) as e:
            result.update(
                status=CHECK_REQUIRED,
                reason=f"gpu_input.json 을 읽을 수 없음({type(e).__name__}) — 묶음 다시 복사",
            )
            result["env"] = environment()
            return _finish(result, started)
        for k in ("study_id", "input_digest", "recipe_digest", "bundle_digest"):
            result[k] = inp.get(k)
        body = {k: v for k, v in inp.items() if k != "bundle_digest"}
        if canonical_hash(body) != inp.get("bundle_digest"):
            result.update(
                status=CHECK_REQUIRED,
                reason="gpu_input.json digest 불일치(복사 중 손상 · 다른 묶음)",
            )
            result["env"] = environment()
            return _finish(result, started)
        result["code_sha256"] = code_sha256()
        if result["code_sha256"] != inp.get("code_sha256"):
            result.update(
                status=CHECK_REQUIRED,
                reason="mlp.py · gpu_runner.py 가 묶음 입력에 적힌 코드와 다름(수정 · 다른 묶음)",
            )
            result["env"] = environment()
            return _finish(result, started)
        try:
            import torch
        except ImportError as e:
            result.update(status=GPU_NOT_RUN, reason=f"torch 없음: {e}")
            result["env"] = environment()
            return _finish(result, started)
        result["env"] = environment(torch)
        if not torch.cuda.is_available():
            result.update(
                status=GPU_NOT_RUN,
                reason=f"CUDA 사용 불가(torch {torch.__version__}"
                f" · torch.version.cuda={torch.version.cuda}"
                " — GPU 없음 또는 CPU 전용 torch)",
            )
            return _finish(result, started)
        import mlp

        if mlp.SPEC != inp.get("mlp_spec"):
            result.update(
                status=CHECK_REQUIRED, reason="묶음의 mlp.py 와 입력 recipe 가 다름"
            )
            return _finish(result, started)
        res = probe(torch, mlp, inp["blocks"][0])
        result["resources"] = res
        off = official(torch, mlp, inp["blocks"], res["chosen_microbatch"])
        result["blocks"] = off["blocks"]
        result["repeat_max_abs_diff"] = off["repeat_max_abs_diff"]
        result["peak_vram_bytes"] = int(torch.cuda.max_memory_allocated())
        if off["repeat_max_abs_diff"] > mlp.REPRO_TOL:
            result.update(
                status=CHECK_REQUIRED,
                reason="같은 입력 두 학습의 예측 차이가 허용값 초과(재현 실패)",
            )
        else:
            result["status"] = OK
    except Exception as e:  # noqa: BLE001 — 학습 오류는 GPU 부재와 구분해 기록
        result.update(status=RUN_FAILED, reason=f"{type(e).__name__}: {e}")
        result["traceback"] = traceback.format_exc()[-4000:]
    return _finish(result, started)


def _finish(result: dict, started: float) -> int:
    result["wall_seconds"] = time.perf_counter() - started
    result["peak_rss_mb"] = peak_rss_mb()
    path = os.path.join(HERE, "gpu_result.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print(f"[POC6-02] 상태 = {result['status']} · 사유 = {result.get('reason')}")
    print(f"[POC6-02] 결과 파일 = {path} — 이 파일을 맥북으로 옮겨 주세요.")
    return 0 if result["status"] in (OK, GPU_NOT_RUN) else 1


if __name__ == "__main__":
    sys.exit(main())
