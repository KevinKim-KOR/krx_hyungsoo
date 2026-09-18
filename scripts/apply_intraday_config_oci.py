"""POC3-02C-OPS-01 — OCI 측 적용 (사슬 4~7단계).

PC 에서 **일시 업로드해 원격 실행**한다. 상시 배포 스크립트가 아니다 —
실행 후 PC 가 삭제한다. 기존 `verify_three_push_param_oci.py` 와 같은 방식이다.

```text
4 verify              schema 검증 + source_hash 재계산 대조
5 OCI DB version 적재  upsert_version (승인 필드 원본 그대로)
6 승인 확인            approved_at/by 없으면 거부
7 active pointer 갱신  store.activate() — 승인 게이트를 다시 통과한다
```

**어느 단계든 실패하면 active pointer 를 건드리지 않는다.** 직전 승인 버전이
그대로 운영된다.

여기서 승인을 새로 만들지 않는다 — 승인은 PC 에서만 일어난다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# **루트를 자기 위치에서 계산하지 않는다.** 이 스크립트는 원격의 임시 경로
# (`state/three_push/params/`)로 업로드돼 실행되므로 `parents[1]` 은 프로젝트
# 루트가 아니다 — 실제 운영에서 `ModuleNotFoundError: No module named 'app'`
# 이 났다. 호출자가 `--project-root` 로 알려준다.
#
# `python <경로>` 는 **스크립트가 있는 디렉터리**를 sys.path[0] 에 넣는다.
# 호출부의 `cd` 는 import 에 영향을 주지 않는다.
def _bootstrap(project_root: str) -> None:
    root = str(Path(project_root).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


REQUIRED_KEYS = (
    "config_version_id",
    "schema_version",
    "created_at",
    "rule_version",
    "evaluation_input_hash",
    "effective_config_hash",
    "source_hash_sha256",
    "payload_json",
)


def _readback_matches(row: dict) -> tuple[bool, str]:
    """DB 에서 다시 읽은 active 가 방금 적용한 것과 같은가."""
    from app.intraday_config import store

    try:
        back = store.get_active()
    except Exception as e:  # noqa: BLE001
        return False, f"read_error:{type(e).__name__}"
    if not back:
        return False, "no_active"
    if back.get("config_version_id") != row["config_version_id"]:
        return False, f"version:{back.get('config_version_id')}"
    if back.get("source_hash_sha256") != row["source_hash_sha256"]:
        return False, "hash"
    return True, ""


def _restore(before_id: Optional[str], activated_by: str) -> None:
    """실패 시 직전 active 로 되돌린다. **되돌리기 자체는 절대 올리지 않는다.**"""
    from app.intraday_config import store

    try:
        if before_id is None:
            store.clear_active()
        else:
            store.activate(before_id, activated_by=f"{activated_by}:rollback")
    except Exception as e:  # noqa: BLE001
        print(f"WARN rollback_failed {type(e).__name__}: {e}")


def apply_file(json_path: Path, *, activated_by: str = "oci_apply") -> int:
    from app.intraday_config import schema, store

    """반환 0=성공. 실패 시 **active pointer 를 바꾸지 않는다.**"""
    if not json_path.exists():
        print(f"FAILED missing_file {json_path}")
        return 2
    try:
        row = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"FAILED unreadable {type(e).__name__}")
        return 2

    missing = [k for k in REQUIRED_KEYS if not row.get(k)]
    if missing:
        print(f"FAILED missing_fields {missing}")
        return 2

    # 4. verify — payload 자체 검증 + source_hash 재계산 대조
    try:
        payload = json.loads(row["payload_json"])
        schema.validate(payload)
    except (ValueError, schema.ConfigSchemaError) as e:
        print(f"FAILED schema {e}")
        return 2
    recomputed = schema.source_hash(payload)
    if recomputed != row["source_hash_sha256"]:
        print(
            f"FAILED hash_mismatch {recomputed[:16]} != {row['source_hash_sha256'][:16]}"
        )
        return 2

    # 6. 승인 확인 — OCI 에서 승인을 만들지 않는다.
    if not row.get("approved_at") or not row.get("approved_by"):
        print("FAILED not_approved")
        return 2

    # 5. DB version 적재
    try:
        store.upsert_version(row)
    except Exception as e:  # noqa: BLE001
        print(f"FAILED upsert {type(e).__name__}: {e}")
        return 2

    # 직전 active 를 먼저 붙든다 — 8단계에서 되돌려야 할 수도 있다.
    before = store.get_active()
    before_id = before["config_version_id"] if before else None

    # 7. active pointer — 승인 게이트를 한 번 더 통과한다.
    try:
        store.activate(row["config_version_id"], activated_by=activated_by)
    except store.ApprovalRequired as e:
        print(f"FAILED approval_gate {e}")
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"FAILED activate {type(e).__name__}: {e}")
        return 2

    # 8. 재독출 대조 — **원격 안에서** 한다. 예전에는 PC 가 별도 ssh 로 읽었고,
    # 그 왕복이 실패하면 active 는 이미 바뀐 채 deploy 는 실패를 반환했다.
    # 여기서 하면 불일치를 발견한 즉시 되돌릴 수 있다.
    ok, why = _readback_matches(row)
    if not ok:
        _restore(before_id, activated_by)
        print(f"FAILED readback {why} (active 를 {before_id or 'NONE'} 로 되돌렸다)")
        return 2

    print(f"OK {row['config_version_id']} {row['source_hash_sha256']}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", required=True, type=Path)
    ap.add_argument("--activated-by", default="oci_apply")
    ap.add_argument(
        "--project-root",
        required=True,
        help="`app` 패키지가 있는 디렉터리. 업로드 위치와 무관하게 명시한다",
    )
    a = ap.parse_args(argv)
    _bootstrap(a.project_root)
    return apply_file(a.json, activated_by=a.activated_by)


if __name__ == "__main__":
    sys.exit(main())
