"""POC3-02C-OPS-01 — `INTRADAY_ALERT_CONFIG` API.

설계자 §10-3(3) — **승인과 적용은 사용자 한 번의 동작**이다. 버튼을 두 번 누르게
하지 않는다.

```text
POST /intraday-config/approve-and-apply
  1 PC 승인 기록 → 2 JSON export → 3 OCI 전달·검증 → 4 OCI DB 적재
  → 5 승인 게이트 검사 → 6 active pointer 변경 → 7 hash 재검증
```

전달 실패 시 **`APPROVED_NOT_DEPLOYED`** 로 남기고 직전 OCI active 를 유지한다.
**재시도할 때 재승인을 요구하지 않는다.**

**ETF 를 직접 고르는 편집 엔드포인트는 만들지 않는다** (§4-3).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.intraday_config import store

router = APIRouter(prefix="/intraday-config", tags=["intraday-config"])

DEPLOY_OK = "DEPLOYED"
DEPLOY_APPROVED_NOT_DEPLOYED = "APPROVED_NOT_DEPLOYED"
DEPLOY_NOT_APPROVED = "NOT_APPROVED"
# 설계자 확정(2026-09-18) — 적용 결과를 **모르는** 상태. 완료도 실패도 아니다.
DEPLOY_UNCONFIRMED = "UNCONFIRMED"


class SectorChange(BaseModel):
    sector_key: str
    change: str  # added / removed / replaced
    before: Optional[str] = None
    after: Optional[str] = None


class ConfigStateResponse(BaseModel):
    active_version_id: Optional[str] = None
    active_source_hash: Optional[str] = None
    active_data_asof: Optional[str] = None
    active_sector_count: int = 0
    candidate_version_id: Optional[str] = None
    candidate_source_hash: Optional[str] = None
    candidate_data_asof: Optional[str] = None
    candidate_sector_count: int = 0
    changes: list[SectorChange] = []
    policy_enabled: bool = False
    policy_status: Optional[str] = None
    deploy_status: Optional[str] = None
    deploy_error: Optional[str] = None
    # 지금 사용자가 해야 할 일. pending_approval = 승인 · approved_not_deployed =
    # 재시도(재승인 불필요). 새로고침해도 유지된다.
    action_state: Optional[str] = None
    # 저장된 설정 내용이 깨졌을 때. 비정상을 "0개" 로 보이게 하지 않는다.
    payload_error: Optional[str] = None


class ApproveRequest(BaseModel):
    config_version_id: str
    approved_by: str = "user"


class RejectRequest(BaseModel):
    config_version_id: str
    rejected_by: str = "user"
    reason: str


class ActionResponse(BaseModel):
    ok: bool
    config_version_id: str
    deploy_status: str
    message: str


class PayloadCorrupt(RuntimeError):
    """저장된 설정 내용을 읽을 수 없다."""


def _payload(row: Optional[dict[str, Any]]) -> dict[str, Any]:
    """저장된 payload 를 푼다.

    **손상을 빈 객체로 바꾸지 않는다.** 예전에는 `except: return {}` 라서 내용이
    깨진 버전이 화면에 "0개 사업군" 으로 보였다 — 정상적으로 비어 있는 것과
    구분되지 않는 거짓 표시다(검증자 지적).
    """
    if not row:
        return {}
    try:
        body = json.loads(row["payload_json"])
    except (KeyError, TypeError, ValueError) as e:
        raise PayloadCorrupt(
            f"{row.get('config_version_id')} 설정 내용을 읽을 수 없다: {e}"
        ) from e
    if not isinstance(body, dict):
        raise PayloadCorrupt(f"{row.get('config_version_id')} payload 가 객체가 아니다")
    return body


def _sectors(payload: dict[str, Any]) -> dict[str, str]:
    uni = payload.get("sector_representative_universe") or {}
    out: dict[str, str] = {}
    for s in uni.get("sectors") or []:
        rep = s.get("representative") or {}
        key = str(s.get("sector_key") or "")
        if key:
            out[key] = str(rep.get("ticker") or "")
    return out


def _diff(active: dict[str, Any], cand: dict[str, Any]) -> list[SectorChange]:
    """직전 승인 버전 대비 변경 요약 (§4-3). 종목 선택 UI 가 아니라 **요약**이다."""
    a, c = _sectors(active), _sectors(cand)
    out: list[SectorChange] = []
    for k in sorted(set(a) | set(c)):
        if k not in a:
            out.append(SectorChange(sector_key=k, change="added", after=c[k]))
        elif k not in c:
            out.append(SectorChange(sector_key=k, change="removed", before=a[k]))
        elif a[k] != c[k]:
            out.append(
                SectorChange(sector_key=k, change="replaced", before=a[k], after=c[k])
            )
    return out


@router.get("/state", response_model=ConfigStateResponse)
def get_state() -> ConfigStateResponse:
    active = store.get_active()
    # `latest_candidate()` 를 직접 쓰지 않는다 — 승인 직후 전달 실패한 버전이
    # 조회에서 빠져 재시도 대상이 사라진다(새로고침 1회에 실패 상태 소실).
    cand, action_state = store.actionable_version()
    try:
        ap, cp = _payload(active), _payload(cand)
    except PayloadCorrupt as e:
        # 값을 지어내지 않는다 — 무엇이 깨졌는지 그대로 올린다.
        return ConfigStateResponse(
            active_version_id=(active or {}).get("config_version_id"),
            candidate_version_id=(cand or {}).get("config_version_id"),
            action_state=action_state,
            payload_error=str(e),
        )
    policy = (cp or ap).get("intraday_alert_policy") or {}
    sync = store.latest_sync(cand["config_version_id"]) if cand else None
    uni_a = ap.get("sector_representative_universe") or {}
    uni_c = cp.get("sector_representative_universe") or {}
    return ConfigStateResponse(
        active_version_id=active["config_version_id"] if active else None,
        active_source_hash=active["source_hash_sha256"] if active else None,
        active_data_asof=uni_a.get("data_asof"),
        active_sector_count=len(uni_a.get("sectors") or []),
        candidate_version_id=cand["config_version_id"] if cand else None,
        candidate_source_hash=cand["source_hash_sha256"] if cand else None,
        candidate_data_asof=uni_c.get("data_asof"),
        candidate_sector_count=len(uni_c.get("sectors") or []),
        changes=_diff(ap, cp) if cand else [],
        policy_enabled=bool(policy.get("enabled")),
        policy_status=policy.get("policy_status"),
        deploy_status=(sync or {}).get("status"),
        deploy_error=(sync or {}).get("error"),
        action_state=action_state,
    )


@router.post("/approve-and-apply", response_model=ActionResponse)
def approve_and_apply(req: ApproveRequest) -> ActionResponse:
    """승인 + 전달을 **한 번의 동작**으로 수행 (§10-3(3))."""
    try:
        row = store.get_version(req.config_version_id)
    except store.ConfigNotFound:
        raise HTTPException(status_code=404, detail="config_version_id 없음")

    if row.get("rejected_at"):
        raise HTTPException(status_code=409, detail="기각된 버전은 적용할 수 없다")

    # **지금 조치 대상인 버전만** 적용한다. 화면을 오래 열어두면 그 사이 새
    # 후보가 산출될 수 있고, 그때 옛 버전으로 POST 하면 조회 화면은 최신본을
    # 보여주는데 실제로는 옛 설정이 OCI 로 나간다(검증자 지적).
    current, _state = store.actionable_version()
    if current is None or current["config_version_id"] != req.config_version_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "화면이 오래됐다. 새로고침 후 다시 시도해 주기 바란다 "
                f"(요청={req.config_version_id} · 현재="
                f"{(current or {}).get('config_version_id')})"
            ),
        )

    # **승인은 멱등이다.** 재시도도 이 엔드포인트를 쓰는데, 무조건 approve 하면
    # 전달이 실패할 때마다 `approved_at` 이 새로 찍힌다 — "승인은 그대로 남고
    # 재승인을 요구하지 않는다" 는 계약과 어긋난다(검증자 r2 P1).
    already = bool(row.get("approved_at") and row.get("approved_by"))
    if not already:
        store.approve(req.config_version_id, approved_by=req.approved_by)

    from scripts.sync_intraday_config import deploy

    ok, err = deploy(req.config_version_id)
    if ok:
        status = DEPLOY_OK
    elif err == "deploy_unconfirmed":
        # **완료·실패로 단정하지 않는다.** 사람이 OCI 를 확인해야 한다.
        status = DEPLOY_UNCONFIRMED
    else:
        status = DEPLOY_APPROVED_NOT_DEPLOYED
    return ActionResponse(
        ok=ok,
        config_version_id=req.config_version_id,
        deploy_status=status,
        message=(
            "OCI 적용 여부 확인 필요 — 통신이 끊겨 적용 결과를 확인하지 못했다. "
            "OCI 상태를 직접 확인한 뒤 재시도하기 바란다."
            if status == DEPLOY_UNCONFIRMED
            else (
                ("OCI 적용 완료" if already else "승인 후 OCI 적용 완료")
                if ok
                # 재승인을 요구하지 않는다 — 승인 기록을 다시 쓰지도 않는다.
                else f"승인은 기록돼 있고 전달이 실패했다. 재시도하면 된다: {err}"
            )
        ),
    )


@router.post("/reject", response_model=ActionResponse)
def reject(req: RejectRequest) -> ActionResponse:
    try:
        store.reject(
            req.config_version_id, rejected_by=req.rejected_by, reason=req.reason
        )
    except store.ConfigNotFound:
        raise HTTPException(status_code=404, detail="config_version_id 없음")
    except store.CannotRejectActive as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ActionResponse(
        ok=True,
        config_version_id=req.config_version_id,
        deploy_status=DEPLOY_NOT_APPROVED,
        message="기각했다. OCI active 는 바뀌지 않았다.",
    )


__all__ = ["router"]
