"""POC3-02C-OPS-01 — `INTRADAY_ALERT_CONFIG` DB 저장소.

**DB 가 SSOT 다.** JSON 은 전송·archive 형식이고 여기서 읽지 않는다.

| DB | 역할 |
|---|---|
| PC `runtime_state.sqlite` | 후보 버전 · 사용자 승인 · 전달 결과 |
| OCI `runtime_state.sqlite` | 실제 운영 active 버전 |

**DB 파일 자체를 복사하거나 덮어쓰지 않는다** (설계자 §10-3(4)).

## 승인 게이트 — 이 모듈의 핵심

조사 결과 기존 `activate_param_version` 은 `approved_*` 를 **검사하지 않는다**
(감사 필드일 뿐). 설계자가 확정한 `AUTO_PROMOTION_WITHOUT_APPROVAL = false` 를
여기서는 **코드로 강제**한다.

```text
approved_at · approved_by 가 없으면  activate 거부 (ApprovalRequired)
```

기존 `activate_param_version` 은 **건드리지 않는다** — 운영 중 경로다.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app import runtime_state_db as _db
from app.intraday_config import schema

STATE_PENDING_APPROVAL = "pending_approval"
STATE_APPROVED_NOT_DEPLOYED = "approved_not_deployed"

ACTIVE_SCOPE = schema.DEFAULT_ACTIVE_SCOPE


class CannotRejectActive(RuntimeError):
    """운영 중(active)인 설정을 기각하려 했다."""


class ApprovalRequired(RuntimeError):
    """미승인 버전을 활성화하려 했다. **설계자 확정 계약 위반.**"""


class ConfigNotFound(LookupError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(db_path: Optional[Path]) -> Path:
    return Path(db_path or _db.DEFAULT_DB_PATH)


def _connect(db_path: Optional[Path]) -> sqlite3.Connection:
    p = _path(db_path)
    _db.init_db(p)  # idempotent — 신규 3 table 포함
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    return con


def new_version_id(now: Optional[datetime] = None) -> str:
    t = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S-%f")
    return f"intraday-{t}"


# ── 생성 ────────────────────────────────────────────────────────────────────


def find_by_effective_hash(
    effective_hash: str, *, db_path: Optional[Path] = None
) -> Optional[dict[str, Any]]:
    """같은 **유효 설정**이 이미 있으면 그 행. 새 버전을 만들지 않기 위함."""
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM intraday_alert_config_version "
            "WHERE effective_config_hash=? ORDER BY created_at DESC LIMIT 1",
            (effective_hash,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def create_candidate(
    payload: dict[str, Any],
    *,
    evaluation_input_hash: str,
    db_path: Optional[Path] = None,
) -> tuple[str, bool]:
    """**미승인 후보**를 만든다. 반환 `(config_version_id, created)`.

    같은 `effective_config_hash` 가 이미 있으면 **만들지 않고** 그 id 를 돌려준다
    (§10-3(1)). 가격 기준일만 달라진 재계산이 승인 요청으로 쌓이는 것을 막는다.
    """
    schema.validate(payload)
    eff = schema.effective_config_hash(payload)
    existing = find_by_effective_hash(eff, db_path=db_path)
    if existing:
        return existing["config_version_id"], False

    vid = new_version_id()
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO intraday_alert_config_version ("
            "config_version_id, schema_version, created_at, rule_version, "
            "evaluation_input_hash, effective_config_hash, source_hash_sha256, "
            "payload_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                vid,
                payload["schema_version"],
                _now(),
                str(payload["rule_version"]),
                evaluation_input_hash,
                eff,
                schema.source_hash(payload),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        con.commit()
    finally:
        con.close()
    return vid, True


def upsert_version(row: dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    """전달받은 version 을 그대로 적재한다 (OCI 측 5단계).

    **승인 필드를 포함해** 원본 그대로 넣는다 — OCI 에서 승인을 새로 만들지
    않는다. 이미 있으면 덮어쓴다(idempotent 재전달 허용).
    """
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT OR REPLACE INTO intraday_alert_config_version ("
            "config_version_id, schema_version, created_at, rule_version, "
            "evaluation_input_hash, effective_config_hash, source_hash_sha256, "
            "payload_json, approved_at, approved_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                row["config_version_id"],
                row["schema_version"],
                row["created_at"],
                row["rule_version"],
                row["evaluation_input_hash"],
                row["effective_config_hash"],
                row["source_hash_sha256"],
                row["payload_json"],
                row.get("approved_at"),
                row.get("approved_by"),
            ),
        )
        con.commit()
    finally:
        con.close()


# ── 조회 ────────────────────────────────────────────────────────────────────


def get_version(
    config_version_id: str, *, db_path: Optional[Path] = None
) -> dict[str, Any]:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM intraday_alert_config_version WHERE config_version_id=?",
            (config_version_id,),
        ).fetchone()
        if not row:
            raise ConfigNotFound(config_version_id)
        return dict(row)
    finally:
        con.close()


def latest_candidate(*, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """가장 최근 **미승인·미기각** 후보."""
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM intraday_alert_config_version "
            "WHERE approved_at IS NULL AND rejected_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def actionable_version(
    *, db_path: Optional[Path] = None
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """사용자가 **지금 조치해야 할** 버전과 그 상태.

    반환 `(행, 상태)`. 상태는 둘 중 하나다.

    ```text
    pending_approval        미승인·미기각 후보 → 승인 버튼
    approved_not_deployed   승인됐으나 active 가 아님 → 재시도 버튼
    ```

    **조치 대상은 최신 미기각 버전 하나뿐이다.** 과거 버전은 이력이지 할 일이
    아니다. 예전에는 "active 가 아닌 승인본" 을 물었는데, v1 배포 후 v2 를
    정상 배포하면 v1 이 그 조건에 그대로 걸려 **옛 설정을 재배포 대상으로**
    내놨다(검증자 r2 P1). active 를 제외하는 것만으로는 부족하다.

    최신본이 이미 active 면 할 일이 없다 — `(None, None)`.
    """
    active = get_active(db_path=db_path)
    active_id = active["config_version_id"] if active else None
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM intraday_alert_config_version "
            "WHERE rejected_at IS NULL ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None, None
    row = dict(row)
    if row["config_version_id"] == active_id:
        return None, None  # 최신본이 운영 중 — 할 일 없음
    if row.get("approved_at") and row.get("approved_by"):
        return row, STATE_APPROVED_NOT_DEPLOYED
    return row, STATE_PENDING_APPROVAL


def get_active(*, db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    con = _connect(db_path)
    try:
        ptr = con.execute(
            "SELECT * FROM intraday_alert_config_active WHERE active_scope=?",
            (ACTIVE_SCOPE,),
        ).fetchone()
        if not ptr:
            return None
        row = con.execute(
            "SELECT * FROM intraday_alert_config_version WHERE config_version_id=?",
            (ptr["config_version_id"],),
        ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["activated_at"] = ptr["activated_at"]
        out["activated_by"] = ptr["activated_by"]
        return out
    finally:
        con.close()


# ── 승인 / 기각 ─────────────────────────────────────────────────────────────


def approve(
    config_version_id: str, *, approved_by: str, db_path: Optional[Path] = None
) -> None:
    """사용자가 **버전 전체**를 승인한다. 종목 단위 선택이 아니다."""
    con = _connect(db_path)
    try:
        cur = con.execute(
            "UPDATE intraday_alert_config_version "
            "SET approved_at=?, approved_by=?, rejected_at=NULL, rejected_by=NULL, "
            "reject_reason=NULL WHERE config_version_id=?",
            (_now(), approved_by, config_version_id),
        )
        if cur.rowcount == 0:
            raise ConfigNotFound(config_version_id)
        con.commit()
    finally:
        con.close()


def reject(
    config_version_id: str,
    *,
    rejected_by: str,
    reason: str,
    db_path: Optional[Path] = None,
) -> None:
    # 운영 중인 설정은 기각 대상이 아니다. 허용하면 active pointer 는 그대로인데
    # 그 버전이 `approved_at=NULL · rejected_at!=NULL` 이 되어, **지금 돌아가는
    # 설정이 동시에 기각 상태**인 모순이 생긴다(검증자 r2 P1).
    active = get_active(db_path=db_path)
    if active and active["config_version_id"] == config_version_id:
        raise CannotRejectActive(
            f"운영 중인 설정은 기각할 수 없다: {config_version_id}"
        )
    con = _connect(db_path)
    try:
        # 승인 후 기각하면 **승인을 지운다.** 남겨두면 `activate()` 의 승인
        # 게이트를 이미 통과한 상태라 기각본이 활성화될 수 있다.
        cur = con.execute(
            "UPDATE intraday_alert_config_version "
            "SET rejected_at=?, rejected_by=?, reject_reason=?, "
            "approved_at=NULL, approved_by=NULL "
            "WHERE config_version_id=?",
            (_now(), rejected_by, reason, config_version_id),
        )
        if cur.rowcount == 0:
            raise ConfigNotFound(config_version_id)
        con.commit()
    finally:
        con.close()


# ── 활성화 — 승인 게이트 ────────────────────────────────────────────────────


def activate(
    config_version_id: str, *, activated_by: str, db_path: Optional[Path] = None
) -> None:
    """active pointer 갱신. **미승인이면 거부한다.**

    기존 `activate_param_version` 과 다른 점이 이것이다 — 거기는 `approved_*` 를
    검사하지 않아 승인이 관행으로만 지켜지고 있었다.
    """
    row = get_version(config_version_id, db_path=db_path)
    # 기각을 **직접** 본다. `reject()` 가 승인을 지우는 것에만 기대면, 승인
    # 필드를 남기는 경로가 하나라도 생기는 순간 기각본이 활성화된다.
    if row.get("rejected_at"):
        raise ApprovalRequired(f"기각된 버전은 활성화할 수 없다: {config_version_id}")
    if not row.get("approved_at") or not row.get("approved_by"):
        raise ApprovalRequired(f"미승인 버전은 활성화할 수 없다: {config_version_id}")
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO intraday_alert_config_active ("
            "active_scope, config_version_id, activated_at, activated_by) "
            "VALUES (?,?,?,?) ON CONFLICT(active_scope) DO UPDATE SET "
            "config_version_id=excluded.config_version_id, "
            "activated_at=excluded.activated_at, "
            "activated_by=excluded.activated_by",
            (ACTIVE_SCOPE, config_version_id, _now(), activated_by),
        )
        con.commit()
    finally:
        con.close()


def clear_active(*, db_path: Optional[Path] = None) -> None:
    """active pointer 를 지운다. **rollback 전용**이다.

    직전 active 가 없던 상태(최초 전달)에서 8단계 재독출이 실패했을 때
    "되돌릴 자리"가 없으므로 지운다. 운영 중 임의 호출 대상이 아니다.
    """
    con = _connect(db_path)
    try:
        con.execute(
            "DELETE FROM intraday_alert_config_active WHERE active_scope=?",
            (ACTIVE_SCOPE,),
        )
        con.commit()
    finally:
        con.close()


# ── 전달 이력 ───────────────────────────────────────────────────────────────


def record_sync(
    config_version_id: str,
    *,
    target: str,
    status: str,
    verify_status: Optional[str] = None,
    remote_hash: Optional[str] = None,
    error: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO intraday_alert_config_sync ("
            "config_version_id, target, attempted_at, status, verify_status, "
            "remote_hash, error) VALUES (?,?,?,?,?,?,?)",
            (
                config_version_id,
                target,
                _now(),
                status,
                verify_status,
                remote_hash,
                error,
            ),
        )
        con.commit()
    finally:
        con.close()


def latest_sync(
    config_version_id: str, *, db_path: Optional[Path] = None
) -> Optional[dict[str, Any]]:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM intraday_alert_config_sync WHERE config_version_id=? "
            "ORDER BY attempted_at DESC, sync_id DESC LIMIT 1",
            (config_version_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


__all__ = [
    "ACTIVE_SCOPE",
    "ApprovalRequired",
    "CannotRejectActive",
    "STATE_APPROVED_NOT_DEPLOYED",
    "STATE_PENDING_APPROVAL",
    "actionable_version",
    "clear_active",
    "ConfigNotFound",
    "activate",
    "approve",
    "create_candidate",
    "find_by_effective_hash",
    "get_active",
    "get_version",
    "latest_candidate",
    "latest_sync",
    "new_version_id",
    "record_sync",
    "reject",
    "upsert_version",
]
