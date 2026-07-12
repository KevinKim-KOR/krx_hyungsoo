"""Refactor v1 Q5/Q6: 테스트가 실제 운영 runtime_state.sqlite 를 절대 쓰지 않음.

- 테스트 전후 실제 파일의 size/mtime/sha256 (또는 absent) 이 변하지 않아야 한다.
- absent 인 경우 테스트가 새로 만들지 않아야 한다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from app import runtime_state_db
from app.runtime_param_store import activate_param_version, create_param_version
from app.three_push_runtime_param import build_manual_seed_param

_REAL_DB_PATH = Path("state/runtime/runtime_state.sqlite")


def _snapshot() -> dict[str, Any]:
    if not _REAL_DB_PATH.exists():
        return {"exists": False}
    b = _REAL_DB_PATH.read_bytes()
    return {
        "exists": True,
        "size": len(b),
        "mtime": _REAL_DB_PATH.stat().st_mtime,
        "sha256": hashlib.sha256(b).hexdigest(),
    }


@pytest.fixture
def real_db_snapshot_before():
    return _snapshot()


def test_default_db_path_is_monkeypatched_to_tmp_path(tmp_path: Path) -> None:
    """conftest autouse fixture 가 실제 운영 path 를 override 했는지 확인."""
    patched = runtime_state_db.DEFAULT_DB_PATH
    assert patched != Path("state/runtime/runtime_state.sqlite")
    assert str(tmp_path) in str(patched.resolve()) or str(tmp_path) in str(patched)


def test_param_apply_writes_to_tmp_not_real_db(
    tmp_path: Path, real_db_snapshot_before
) -> None:
    """create_param_version + activate_param_version 이 실제 DB 를 건드리지 않는지 확인."""
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="isolation_test")
    after = _snapshot()
    assert after == real_db_snapshot_before, (
        f"실제 runtime_state.sqlite 가 테스트에 의해 변경됨. "
        f"before={real_db_snapshot_before} after={after}"
    )
