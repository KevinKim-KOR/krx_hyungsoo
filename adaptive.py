# adaptive.py
"""
Legacy import shim for scanner.py.
Maps `from adaptive import get_effective_cfg` to the current config loader.
"""
try:
    from utils.config import get_effective_cfg  # preferred
except Exception:
    from utils.config import load_cfg as get_effective_cfg  # fallback
