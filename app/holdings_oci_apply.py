"""Holdings 를 OCI 로 명시적 적용(전송·검증)하는 업무 동작.

POC3-07 (PLAN V2 §4.3 · 설계자 Q3·Q4·Q11 · 검증자 REJECTED r1 반영):
  - Holdings 저장(`PUT /holdings`)과 OCI 적용은 **별도 동작**이다. 이 모듈은
    사용자가 명시적으로 "OCI 적용" 을 눌렀을 때만 호출된다(자동 전송 없음).
  - 적용 대상 = OCI 가 실제 읽는 소스 `state/holdings/holdings_latest.json`
    (실측: app/holdings.py :: HOLDINGS_FILE, PC·OCI 동일 경로).

원자적 적용의 순서(중요 — 기존 active 보존 계약):
  1. 로컬 파일 **schema 검증**(validate_holdings). 손상 파일은 전송조차 안 한다.
  2. manifest(kind/content_sha256/created_at) 생성.
  3. payload·manifest 를 원격 **tmp** 로 전송(active 는 아직 안 건드림).
  4. **rename 전에** 원격 tmp 에서 검증을 모두 끝낸다:
       (a) sha256(tmp) == 로컬 sha256  (전송 무결성)
       (b) tmp 를 JSON 파싱 + holdings 배열 구조 확인  (schema 무결성)
     → 하나라도 실패하면 tmp 를 지우고 **active 는 그대로 둔다**(보존).
  5. 위 검증을 모두 통과한 tmp 만 atomic rename(tmp → active) 한다. 즉 active 로
     승격되는 파일은 항상 검증을 통과한 내용이다. rename 자체가 실패하면 active 는
     바뀌지 않는다(tmp 만 남고, 정리한다).
  6. rename 성공 후 active manifest 를 기록하고, active sha256 을 재확인해
     PC==OCI 면 OCI_APPLIED 로 확정한다.
  - idempotent: 같은 내용을 다시 적용해도 같은 hash → 같은 성공 결과.

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
_LOCAL_MANIFEST = Path("state/holdings/holdings_apply_manifest.json")
_REMOTE_HOME = "/home/ubuntu/krx_hyungsoo"
_REMOTE_DIR = f"{_REMOTE_HOME}/state/holdings"
_REMOTE_FINAL = f"{_REMOTE_DIR}/holdings_latest.json"
_REMOTE_TMP = f"{_REMOTE_DIR}/holdings_latest.json.apply-tmp"
_REMOTE_MANIFEST = f"{_REMOTE_DIR}/holdings_apply_manifest.json"

_MANIFEST_KIND = "holdings_latest"

_SCP_TIMEOUT_SEC = 60
_SSH_TIMEOUT_SEC = 30


# 적용 상태(설계 §6.2). UI 표시용.
STATUS_PC_SAVED = "PC_SAVED"  # 로컬 파일 없음/미적용 전
STATUS_OCI_APPLIED = "OCI_APPLIED"  # 검증 통과 후 PC==OCI hash 일치
STATUS_OUT_OF_SYNC = "OUT_OF_SYNC"  # 적용됐으나 사후 hash 불일치
STATUS_APPLY_FAILED = "APPLY_FAILED"  # 로컬 schema·전송·검증 실패(active 보존)
STATUS_UNKNOWN = "UNKNOWN"  # OCI 상태 확인 불가


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


def _write_local_manifest(sha: str, created_at: str) -> None:
    """PC 전송 manifest 기록(kind/content_sha256/created_at). 실패는 무시(부가)."""
    try:
        _LOCAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        _LOCAL_MANIFEST.write_text(
            json.dumps(
                {
                    "kind": _MANIFEST_KIND,
                    "content_sha256": sha,
                    "created_at": created_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as e:  # noqa: BLE001 - manifest 기록 실패는 적용 자체를 막지 않음
        logger.warning("로컬 apply manifest 기록 실패(무시): %s", e)


def apply_holdings_to_oci() -> HoldingsApplyResult:
    """저장된 Holdings 를 OCI 에 명시적으로 적용한다.

    순서: 로컬 schema 검증 → tmp 전송 → (rename 전) tmp hash·schema 검증 →
    atomic rename → manifest 기록 → 사후 hash 확인. 검증 실패는 모두 rename
    이전이라 기존 OCI active Holdings 가 보존된다. 사용자 명시 클릭에서만 호출.
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
    _write_local_manifest(local_sha, created_at)

    ssh_base = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_TIMEOUT_SEC}",
        *key_opts,
        target,
    ]

    # 2. tmp 로 전송(active 를 아직 건드리지 않음).
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
        _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)
        return _fail("OCI 전송에 실패했습니다. 기존 적용 상태는 유지됩니다.", local_sha)

    # 3. (rename 전) tmp hash 검증 — 전송 무결성.
    rc, so, _se = _run(
        ssh_base + [f"sha256sum {_REMOTE_TMP} 2>/dev/null | cut -d' ' -f1"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    remote_tmp_sha = so.strip() if rc == 0 else ""
    if rc != 0 or remote_tmp_sha != local_sha:
        _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)
        return _fail(
            "전송 파일 무결성 검증에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 4. (rename 전) tmp schema 검증 — 원격에서 JSON 파싱 + holdings 배열 확인.
    #    파이썬 한 줄로 구조를 검사한다(비어있거나 holdings 키 없으면 rc!=0).
    remote_schema_check = (
        'python3 -c "import json,sys; '
        f"d=json.load(open('{_REMOTE_TMP}')); "
        "sys.exit(0 if (isinstance(d,dict) and isinstance(d.get('holdings'),list) "
        "and len(d['holdings'])>0) else 1)\""
    )
    rc, _so, _se = _run(ssh_base + [remote_schema_check], timeout=_SSH_TIMEOUT_SEC)
    if rc != 0:
        _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)
        return _fail(
            "전송 파일 구조 검증에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 5. 모든 검증 통과 — atomic rename(tmp → active). 여기서만 active 가 바뀐다.
    #    승격되는 tmp 는 hash·schema 를 이미 통과한 내용이다.
    rc, _so, _se = _run(
        ssh_base + [f"mv {_REMOTE_TMP} {_REMOTE_FINAL}"], timeout=_SSH_TIMEOUT_SEC
    )
    if rc != 0:
        _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)
        return _fail(
            "OCI 적용(원자 교체)에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    applied_at = datetime.now(timezone.utc).isoformat()

    # 6. active manifest 기록(원격). 부가 — 실패해도 적용 자체는 성공으로 본다.
    manifest_json = json.dumps(
        {
            "kind": _MANIFEST_KIND,
            "content_sha256": local_sha,
            "created_at": created_at,
            "applied_at": applied_at,
        },
        ensure_ascii=False,
    )
    _run(
        ssh_base + [f"printf '%s' {json.dumps(manifest_json)} > {_REMOTE_MANIFEST}"],
        timeout=_SSH_TIMEOUT_SEC,
    )

    # 7. 사후 active hash 재확인 → PC==OCI 면 성공 확정.
    rc, so, _se = _run(
        ssh_base + [f"sha256sum {_REMOTE_FINAL} 2>/dev/null | cut -d' ' -f1"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    active_sha = so.strip() if rc == 0 else ""
    if rc != 0:
        # 적용된 내용은 검증을 통과한 것이지만 사후 확인만 실패.
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
