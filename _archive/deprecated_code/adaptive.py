# adaptive.py  (repo root)
"""
Legacy import shim for scanner.py
`from adaptive import get_effective_cfg` → core.utils.config로 매핑
"""
try:
    from core.utils.config import get_effective_cfg  # 선호
except Exception:
    from core.utils.config import load_cfg as get_effective_cfg  # 호환
