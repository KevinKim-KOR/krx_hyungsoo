"""deps 라우터 — 의존성 상태 조회, 스냅샷 저장/조회.

NOTE: /api/deps/reconcile/check (preflight)는 execution_gate,
emergency_stop, get_active_window 의존이 있어 S5-4에서 이동.
"""

import json
import sys
from datetime import datetime

from fastapi import APIRouter

from backend.utils import (
    KST,
    BASE_DIR,
    STATE_DIR,
    logger,
)

router = APIRouter()

DEPS_SNAPSHOT_DIR = BASE_DIR / "state" / "deps"
DEPS_SNAPSHOT_FILE = DEPS_SNAPSHOT_DIR / "installed_deps_snapshot.json"


def check_reconcile_deps() -> dict:
    """Check reconcile dependencies"""
    result = {
        "python_version": (
            f"{sys.version_info.major}"
            f".{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        ),
        "python_ok": sys.version_info >= (3, 10),
        "pandas_installed": False,
        "pyarrow_installed": False,
        "required_missing": [],
    }

    try:
        import pandas

        result["pandas_installed"] = True
        result["pandas_version"] = pandas.__version__
    except ImportError:
        result["required_missing"].append("pandas")

    try:
        import pyarrow

        result["pyarrow_installed"] = True
        result["pyarrow_version"] = pyarrow.__version__
    except ImportError:
        result["required_missing"].append("pyarrow")

    result["all_deps_ok"] = len(result["required_missing"]) == 0 and result["python_ok"]
    return result


@router.get("/api/deps/reconcile", summary="Reconcile 의존성 상태 조회")
def get_reconcile_deps():
    """현재 reconcile REAL 실행 가능 여부 확인"""
    deps = check_reconcile_deps()
    return {
        "status": "ready" if deps["all_deps_ok"] else "missing_deps",
        "schema": "RECONCILE_DEPENDENCY_V2",
        "asof": datetime.now(KST).isoformat(),
        "row_count": 1,
        "rows": [deps],
        "error": (
            None if deps["all_deps_ok"] else f"Missing: {deps['required_missing']}"
        ),
    }


@router.post("/api/deps/snapshot", summary="의존성 스냅샷 저장")
def save_deps_snapshot():
    """설치된 의존성을 스냅샷으로 저장"""
    DEPS_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    deps = check_reconcile_deps()

    snapshot = {
        "schema": "DEPS_SNAPSHOT_V1",
        "asof": datetime.now(KST).isoformat(),
        "python_version": deps.get("python_version"),
        "packages": {
            "pandas": deps.get("pandas_version"),
            "pyarrow": deps.get("pyarrow_version"),
        },
        "source": "importlib metadata",
        "all_deps_ok": deps.get("all_deps_ok"),
    }

    DEPS_SNAPSHOT_FILE.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Deps snapshot saved: {DEPS_SNAPSHOT_FILE}")

    return {
        "result": "OK",
        "path": str(DEPS_SNAPSHOT_FILE.relative_to(BASE_DIR)),
        "snapshot": snapshot,
    }


@router.get("/api/deps/snapshot", summary="의존성 스냅샷 조회")
def get_deps_snapshot():
    """저장된 의존성 스냅샷 조회"""
    if not DEPS_SNAPSHOT_FILE.exists():
        return {"status": "not_found", "error": "Snapshot not found"}

    snapshot = json.loads(DEPS_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return {"status": "ready", "snapshot": snapshot}
