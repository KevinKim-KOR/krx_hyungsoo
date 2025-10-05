# adaptive.py  (repo root)
"""
Legacy import shim.
scanner.py 가 기대하는 `from adaptive import get_effective_cfg`를
현재 구성(utils/config.py)으로 매핑한다.
"""
try:
    # 먼저 동일 시그니처가 있는 경우
    from utils.config import get_effective_cfg  # type: ignore
except Exception:
    # 이름이 load_cfg 인 프로젝트도 있으니 호환
    from utils.config import load_cfg as get_effective_cfg  # type: ignore
