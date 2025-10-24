# adaptive.py  (repo root)
"""
Legacy import shim for scanner.py
`from adaptive import get_effective_cfg` → utils.config로 매핑
"""
try:
    from utils.config import get_effective_cfg  # 선호
except Exception:
    from utils.config import load_cfg as get_effective_cfg  # 호환
