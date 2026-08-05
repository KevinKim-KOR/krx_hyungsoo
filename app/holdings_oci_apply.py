"""Holdings 를 OCI 로 명시적 적용(전송·검증)하는 업무 동작.

POC3-07 (PLAN V2 §4.3 · 설계자 Q3·Q4·Q11 · 검증자 REJECTED r1 반영):
  - Holdings 저장(`PUT /holdings`)과 OCI 적용은 **별도 동작**이다. 이 모듈은
    사용자가 명시적으로 "OCI 적용" 을 눌렀을 때만 호출된다(자동 전송 없음).
  - 적용 대상 = OCI 가 실제 읽는 소스 `state/holdings/holdings_latest.json`
    (실측: app/holdings.py :: HOLDINGS_FILE, PC·OCI 동일 경로).

원자적 적용의 순서(확정 PLAN §4.3 그대로 — 기존 active 보존 계약):
  1. 로컬 파일 **schema 검증**(validate_holdings). 손상 파일은 전송조차 안 한다.
  2. payload → payload-tmp, manifest(kind/content_sha256/created_at) → manifest-tmp
     로 **둘 다 전송**(active·active-manifest 는 아직 안 건드림).
  3. **승격 전에** 검증을 모두 끝낸다:
       (a) sha256(payload-tmp) == 로컬 sha256  (전송 무결성)
       (b) payload-tmp JSON 파싱 + holdings 배열 구조 확인  (schema 무결성)
     → 하나라도 실패하면 tmp 를 지우고 **active 는 그대로 둔다**(보존).
  4. 승격: manifest-tmp → active-manifest 를 먼저, **payload-tmp → active 를 마지막에**
     atomic rename. payload 승격이 마지막이므로 그 앞의 어떤 실패(manifest 승격 실패
     포함)도 active(payload) 를 바꾸지 않는다 → 실패 시 보존 성립. (r2 의 "manifest 를
     rename 뒤에 써서 실패 시 active 이미 변경" 결함을 이 순서로 제거한다.)
  5. 승격 후 **OCI active hash 재확인**(PLAN §4.3): PC==OCI 면 OCI_APPLIED, 불일치면
     OUT_OF_SYNC, 재확인 자체 실패면 UNKNOWN.
  - idempotent: 같은 내용을 다시 적용해도 같은 hash·schema → 같은 성공 경로.

응답 데이터 계약(§6·§13): SSH target·remote path·raw subprocess 출력·secret 을
반환하지 않는다. 사용자 중심 상태·시각·짧은 오류 요약만.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import optional_env, require_env
from app.holdings import HoldingsValidationError, validate_holdings

logger = logging.getLogger(__name__)

# PC·OCI 공통 Holdings 소스 경로(app/holdings.py 와 동일 규약).
_LOCAL_HOLDINGS = Path("state/holdings/holdings_latest.json")
_REMOTE_HOME = "/home/ubuntu/krx_hyungsoo"
_REMOTE_DIR = f"{_REMOTE_HOME}/state/holdings"
_REMOTE_FINAL = f"{_REMOTE_DIR}/holdings_latest.json"
_REMOTE_TMP = f"{_REMOTE_DIR}/holdings_latest.json.apply-tmp"
_REMOTE_MANIFEST = f"{_REMOTE_DIR}/holdings_apply_manifest.json"
_REMOTE_MANIFEST_TMP = f"{_REMOTE_DIR}/holdings_apply_manifest.json.apply-tmp"

_MANIFEST_KIND = "holdings_latest"

_SCP_TIMEOUT_SEC = 60
_SSH_TIMEOUT_SEC = 30


# 적용 상태(설계 §6.2 · PLAN §4.3). UI 표시용.
STATUS_PC_SAVED = "PC_SAVED"  # 로컬 파일 없음/미적용 전
STATUS_OCI_APPLIED = "OCI_APPLIED"  # 승격 성공 + active hash == PC hash
STATUS_OUT_OF_SYNC = "OUT_OF_SYNC"  # 승격됐으나 active hash 재확인 불일치(PLAN §4.3)
STATUS_APPLY_FAILED = (
    "APPLY_FAILED"  # 승격 이전 실패(로컬 schema·전송·검증·manifest 전송) → active 보존
)
STATUS_UNKNOWN = "UNKNOWN"  # ENV 미설정 / 승격 후 hash 재확인 자체 실패


@dataclass
class HoldingsApplyResult:
    status: str
    applied_at: Optional[str]
    content_sha256: Optional[str]  # 표시용(전송 payload 해시)
    oci_verified: bool
    message: str


def _ssh_key_opts() -> list[str]:
    key_path = optional_env("OCI_SSH_KEY_PATH", default=None)
    if not key_path:
        return []
    return ["-i", key_path, "-o", "IdentitiesOnly=yes"]


def _run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
    """subprocess 실행. (rc, stdout, stderr). 예외는 (−1, "", msg)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return -1, "", str(e)


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_local_schema(raw_bytes: bytes) -> Optional[str]:
    """로컬 payload 의 holdings schema 를 검증. 문제 있으면 사용자용 사유 문자열.

    통과하면 None. app/holdings.py 의 validate_holdings 재사용(단일 계약).
    """
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return f"JSON 파싱 실패: {e}"
    if not isinstance(data, dict) or "holdings" not in data:
        return "holdings 키가 없는 형식입니다."
    try:
        validate_holdings(data["holdings"])
    except HoldingsValidationError as e:
        return f"보유 종목 형식 오류: {e}"
    return None


def _fail(msg: str, sha: Optional[str] = None) -> HoldingsApplyResult:
    return HoldingsApplyResult(
        status=STATUS_APPLY_FAILED,
        applied_at=None,
        content_sha256=sha,
        oci_verified=False,
        message=msg,
    )


def _cleanup_tmp(ssh_base: list[str]) -> None:
    """승격 실패·검증 실패 시 원격 tmp(payload·manifest) 정리. active 는 안 건드림."""
    _run(
        ssh_base + [f"rm -f {_REMOTE_TMP} {_REMOTE_MANIFEST_TMP}"],
        timeout=_SSH_TIMEOUT_SEC,
    )


def apply_holdings_to_oci() -> HoldingsApplyResult:
    """저장된 Holdings 를 OCI 에 명시적으로 적용한다.

    순서(모든 검증·전송이 payload 승격 이전 → 실패 시 active 보존):
      1. 로컬 schema 검증(손상 파일 전송 안 함).
      2. payload → payload-tmp, manifest → manifest-tmp **둘 다 전송**
         (active·active-manifest 는 아직 안 건드림).
      3. (승격 전) 검증: payload-tmp sha256 == 로컬, payload-tmp schema,
         manifest-tmp 존재. 하나라도 실패하면 tmp 정리 후 **active 보존**.
      4. 승격: manifest-tmp → active-manifest 를 먼저, **payload-tmp → active
         를 마지막에** atomic rename. payload 승격이 마지막이므로 그 앞 어떤
         실패(manifest 승격 실패 포함)도 active(payload) 미변경 = 보존.
      5. atomic 승격 후 **OCI active hash 재확인**(PLAN §4.3): PC==OCI 면
         OCI_APPLIED, 불일치면 OUT_OF_SYNC.
    사용자 명시 클릭에서만 호출.
    """
    # 0. 로컬 소스 존재 확인.
    if not _LOCAL_HOLDINGS.exists():
        return HoldingsApplyResult(
            status=STATUS_PC_SAVED,
            applied_at=None,
            content_sha256=None,
            oci_verified=False,
            message="저장된 보유 종목 파일이 없습니다. 먼저 종목 관리에서 저장하세요.",
        )

    raw_bytes = _LOCAL_HOLDINGS.read_bytes()
    local_sha = _sha256_of_bytes(raw_bytes)

    # 1. 로컬 schema 검증 — 손상 파일은 전송조차 하지 않는다(active 보존).
    schema_err = _validate_local_schema(raw_bytes)
    if schema_err is not None:
        return _fail(
            f"보유 종목 파일 검증에 실패해 적용하지 않았습니다. 기존 적용 상태는 "
            f"유지됩니다. ({schema_err})",
            local_sha,
        )

    try:
        target = require_env("OCI_SSH_TARGET")
    except Exception:  # noqa: BLE001 - EnvConfigError 포함
        return HoldingsApplyResult(
            status=STATUS_UNKNOWN,
            applied_at=None,
            content_sha256=local_sha,
            oci_verified=False,
            message="OCI 접속 대상이 설정되지 않아 적용할 수 없습니다.",
        )

    key_opts = _ssh_key_opts()
    created_at = datetime.now(timezone.utc).isoformat()
    applied_at = created_at

    ssh_base = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_TIMEOUT_SEC}",
        *key_opts,
        target,
    ]

    # 2a. payload 를 payload-tmp 로 전송(active 는 아직 안 건드림).
    scp_cmd = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_TIMEOUT_SEC}",
        *key_opts,
        str(_LOCAL_HOLDINGS),
        f"{target}:{_REMOTE_TMP}",
    ]
    rc, _so, _se = _run(scp_cmd, timeout=_SCP_TIMEOUT_SEC)
    if rc != 0:
        logger.error("holdings scp 실패: rc=%s", rc)
        _cleanup_tmp(ssh_base)
        return _fail("OCI 전송에 실패했습니다. 기존 적용 상태는 유지됩니다.", local_sha)

    # 2b. active manifest 를 manifest-tmp 로 전송(Q4). active-manifest 는 안 건드림.
    #     manifest 전송을 승격 이전에 끝내므로, manifest 문제도 active 보존 범위 안이다.
    manifest_json = json.dumps(
        {
            "kind": _MANIFEST_KIND,
            "content_sha256": local_sha,
            "created_at": created_at,
            "applied_at": applied_at,
        },
        ensure_ascii=False,
    )
    rc, _so, _se = _run(
        ssh_base
        + [f"printf '%s' {json.dumps(manifest_json)} > {_REMOTE_MANIFEST_TMP}"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    if rc != 0:
        _cleanup_tmp(ssh_base)
        return _fail(
            "적용 기록(manifest) 전송에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 3. (승격 전) payload-tmp hash 검증 — 전송 무결성.
    rc, so, _se = _run(
        ssh_base + [f"sha256sum {_REMOTE_TMP} 2>/dev/null | cut -d' ' -f1"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    remote_tmp_sha = so.strip() if rc == 0 else ""
    if rc != 0 or remote_tmp_sha != local_sha:
        _cleanup_tmp(ssh_base)
        return _fail(
            "전송 파일 무결성 검증에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 4. (승격 전) payload-tmp schema 검증 — 원격 JSON 파싱 + holdings 배열 확인.
    remote_schema_check = (
        'python3 -c "import json,sys; '
        f"d=json.load(open('{_REMOTE_TMP}')); "
        "sys.exit(0 if (isinstance(d,dict) and isinstance(d.get('holdings'),list) "
        "and len(d['holdings'])>0) else 1)\""
    )
    rc, _so, _se = _run(ssh_base + [remote_schema_check], timeout=_SSH_TIMEOUT_SEC)
    if rc != 0:
        _cleanup_tmp(ssh_base)
        return _fail(
            "전송 파일 구조 검증에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 5. 승격 — manifest 를 먼저, payload 를 **마지막에** atomic rename 한다.
    #    payload 승격이 마지막이므로, 그 앞의 어떤 실패(manifest 승격 실패 포함)도
    #    active(payload) 를 바꾸지 않는다 → "실패 시 기존 active 보존"(PLAN Q11) 성립.
    rc, _so, _se = _run(
        ssh_base + [f"mv {_REMOTE_MANIFEST_TMP} {_REMOTE_MANIFEST}"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    if rc != 0:
        _cleanup_tmp(ssh_base)  # payload 는 아직 active 아님 → 보존.
        return _fail(
            "적용 기록(manifest) 반영에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )
    rc, _so, _se = _run(
        ssh_base + [f"mv {_REMOTE_TMP} {_REMOTE_FINAL}"], timeout=_SSH_TIMEOUT_SEC
    )
    if rc != 0:
        _cleanup_tmp(ssh_base)  # payload 승격 실패 → payload active 미변경(보존).
        return _fail(
            "OCI 적용(원자 교체)에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 6. OCI active hash 재확인(PLAN §4.3) → PC==OCI 면 OCI_APPLIED, 불일치면 OUT_OF_SYNC.
    rc, so, _se = _run(
        ssh_base + [f"sha256sum {_REMOTE_FINAL} 2>/dev/null | cut -d' ' -f1"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    active_sha = so.strip() if rc == 0 else ""
    if rc != 0:
        return HoldingsApplyResult(
            status=STATUS_UNKNOWN,
            applied_at=applied_at,
            content_sha256=local_sha,
            oci_verified=False,
            message="적용은 완료됐으나 OCI 상태 확인에 실패했습니다.",
        )
    if active_sha == local_sha:
        return HoldingsApplyResult(
            status=STATUS_OCI_APPLIED,
            applied_at=applied_at,
            content_sha256=local_sha,
            oci_verified=True,
            message="보유 종목을 OCI 에 적용했습니다.",
        )
    return HoldingsApplyResult(
        status=STATUS_OUT_OF_SYNC,
        applied_at=applied_at,
        content_sha256=local_sha,
        oci_verified=False,
        message="적용 후 OCI 값이 PC 와 일치하지 않습니다. 다시 적용하세요.",
    )
