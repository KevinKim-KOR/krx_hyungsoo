import os, time, numpy as np
from pathlib import Path

# 1) 데이터 존재 확인 (캐시 폴더 예시)
DATA_DIR = Path(r"\\192.168.0.18\homes\Hyungsoo\krx\krx_alertor_modular\data\cache\kr")
print("[DATA] exists:", DATA_DIR.exists(), "files:", len(list(DATA_DIR.glob("*"))))

# 2) 연산 테스트: CPU vs GPU matmul 시간 비교
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
print("[TORCH] version:", torch.__version__, "device:", device)

n = 4096  # 충분히 큰 행렬로 연산차 확인
a = torch.randn((n, n), device=device)
b = torch.randn((n, n), device=device)

torch.cuda.synchronize() if device=="cuda" else None
t0 = time.time()
c = a @ b
torch.cuda.synchronize() if device=="cuda" else None
dt = time.time() - t0
print(f"[MATMUL] {device} time: {dt:.3f}s, result mean={c.mean().item():.6f}")

# 3) 결과 저장 (NAS로 바로 떨어뜨리기)
OUT_DIR = Path(r"\\192.168.0.18\homes\Hyungsoo\krx\krx_alertor_modular\backtests")
OUT_DIR.mkdir(parents=True, exist_ok=True)
out_file = OUT_DIR / "gpu_smoke_result.txt"
out_file.write_text(f"device={device}, n={n}, time={dt:.3f}s\n")
print("[WRITE]", out_file, "OK")
