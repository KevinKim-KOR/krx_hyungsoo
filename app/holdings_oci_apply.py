"""Holdings 를 OCI 로 명시적 적용(전송·검증)하는 업무 동작.

POC3-07 (PLAN V2 §4.3 · 설계자 Q3·Q4·Q11):
  - Holdings 저장(`PUT /holdings`)과 OCI 적용은 **별도 동작**이다. 이 모듈은
    사용자가 명시적으로 "OCI 적용" 을 눌렀을 때만 호출된다(자동 전송 없음).
  - 적용 대상 = OCI 가 실제 읽는 소스 `state/holdings/holdings_latest.json`
    (실측: app/holdings.py :: HOLDINGS_FILE, PC·OCI 동일 경로).
  - 성공 판정 = **전송 payload 의 SHA-256 == OCI active 파일의 SHA-256**(Q4).
  - 원자적 적용(§13): tmp 로 전송 → 원격 존재·hash 확인 → atomic rename.
    실패 시 기존 OCI active Holdings 를 보존한다(중간 파일을 active 로 승격하지 않음).
  - idempotent: 같은 내용을 다시 적용해도 같은 hash → 같은 성공 결과.

응답 데이터 계약(§6·§13): SSH target·remote path·raw subprocess 출력·secret 을
반환하지 않는다. 사용자 중심 상태·시각·짧은 오류 요약만.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import optional_env, require_env

logger = logging.getLogger(__name__)

# PC·OCI 공통 Holdings 소스 경로(app/holdings.py 와 동일 규약).
_LOCAL_HOLDINGS = Path("state/holdings/holdings_latest.json")
_REMOTE_HOME = "/home/ubuntu/krx_hyungsoo"
_REMOTE_FINAL = f"{_REMOTE_HOME}/state/holdings/holdings_latest.json"
_REMOTE_TMP = f"{_REMOTE_HOME}/state/holdings/holdings_latest.json.apply-tmp"

_SCP_TIMEOUT_SEC = 60
_SSH_TIMEOUT_SEC = 30


# 적용 상태(설계 §6.2). UI 표시용.
STATUS_PC_SAVED = "PC_SAVED"  # 로컬 파일 없음/미적용 전
STATUS_OCI_APPLIED = "OCI_APPLIED"  # PC==OCI hash 일치
STATUS_OUT_OF_SYNC = "OUT_OF_SYNC"  # 적용됐으나 hash 불일치
STATUS_APPLY_FAILED = "APPLY_FAILED"  # 전송·검증·적용 실패
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


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _fail(msg: str, sha: Optional[str] = None) -> HoldingsApplyResult:
    return HoldingsApplyResult(
        status=STATUS_APPLY_FAILED,
        applied_at=None,
        content_sha256=sha,
        oci_verified=False,
        message=msg,
    )


def apply_holdings_to_oci() -> HoldingsApplyResult:
    """저장된 Holdings 를 OCI 에 명시적으로 적용한다(전송 → 검증 → 원자 적용).

    사용자 명시 클릭에서만 호출. 실패해도 기존 OCI active Holdings 는 보존된다.
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

    try:
        target = require_env("OCI_SSH_TARGET")
    except Exception:  # noqa: BLE001 - EnvConfigError 포함
        return HoldingsApplyResult(
            status=STATUS_UNKNOWN,
            applied_at=None,
            content_sha256=None,
            oci_verified=False,
            message="OCI 접속 대상이 설정되지 않아 적용할 수 없습니다.",
        )

    local_sha = _sha256_of_file(_LOCAL_HOLDINGS)
    key_opts = _ssh_key_opts()

    # 1. tmp 로 전송(기존 active 를 아직 건드리지 않음).
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
    rc, _so, se = _run(scp_cmd, timeout=_SCP_TIMEOUT_SEC)
    if rc != 0:
        logger.error("holdings scp 실패: rc=%s", rc)
        return _fail("OCI 전송에 실패했습니다. 기존 적용 상태는 유지됩니다.", local_sha)

    # 2. 원격 tmp 의 sha256 확인(전송 무결성). PC hash 와 일치해야 적용 진행.
    ssh_base = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_TIMEOUT_SEC}",
        *key_opts,
        target,
    ]
    rc, so, _se = _run(
        ssh_base + [f"sha256sum {_REMOTE_TMP} 2>/dev/null | cut -d' ' -f1"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    remote_tmp_sha = so.strip() if rc == 0 else ""
    if rc != 0 or remote_tmp_sha != local_sha:
        # 전송이 손상됨 — tmp 정리, active 는 건드리지 않음.
        _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)
        return _fail(
            "전송 파일 무결성 검증에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 3. atomic rename(tmp → active). 여기서만 active 가 바뀐다.
    rc, _so, _se = _run(
        ssh_base + [f"mv {_REMOTE_TMP} {_REMOTE_FINAL}"], timeout=_SSH_TIMEOUT_SEC
    )
    if rc != 0:
        _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)
        return _fail(
            "OCI 적용(원자 교체)에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 4. 적용 후 OCI active hash 재확인 → PC==OCI 면 성공 판정(Q4).
    rc, so, _se = _run(
        ssh_base + [f"sha256sum {_REMOTE_FINAL} 2>/dev/null | cut -d' ' -f1"],
        timeout=_SSH_TIMEOUT_SEC,
    )
    active_sha = so.strip() if rc == 0 else ""
    applied_at = datetime.now(timezone.utc).isoformat()

    if rc != 0:
        return HoldingsApplyResult(
            status=STATUS_UNKNOWN,
            applied_at=applied_at,
            content_sha256=local_sha,
            oci_verified=False,
            message="적용은 시도됐으나 OCI 상태 확인에 실패했습니다.",
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
