# ml/__init__.py
# 순차·재현성 기본
import os, torch, random, numpy as np
os.environ.setdefault("PYTHONHASHSEED","0")
torch.set_num_threads(1)                          # 병렬 금지
torch.use_deterministic_algorithms(False)         # 일부 연산 가속 허용(필요시 True)
random.seed(0); np.random.seed(0); torch.manual_seed(0)
try:
    torch.set_float32_matmul_precision("high")    # Ampere↑ TF32
except Exception:
    pass
