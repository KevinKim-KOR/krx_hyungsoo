"""Holdings 를 OCI 로 명시적 적용(전송·검증)하는 업무 동작.

POC3-07 (PLAN §4.3 · 설계자 Q3·Q11 · manifest 계약 확정 2026-08-06):
  - Holdings 저장(`PUT /holdings`)과 OCI 적용은 **별도 동작**이다. 이 모듈은
    사용자가 명시적으로 "OCI 적용" 을 눌렀을 때만 호출된다(자동 전송 없음).
  - 적용 대상 = OCI 가 실제 읽는 소스 `state/holdings/holdings_latest.json`
    (실측: app/holdings.py :: HOLDINGS_FILE, PC·OCI 동일 경로).

POC5-05 (설계 개정 2 §7 · PLAN §2-5): PC 파일 바이트를 그대로 보내지 않는다.
  - PC 보유 문서를 한 번 읽어 **허용 5필드 payload**(ticker · quantity ·
    avg_buy_price · name · account_group)를 기존 save 형식으로 만들어 보낸다.
    개인 이력 · position_id · cycle_id · 메모 · 과거 보유는 구조상 들어가지 않는다.
  - 로컬 hash · 원격 대조 · 교체 뒤 재확인 모두 이 payload bytes 기준이다. 이력만
    바뀐 문서는 payload 가 같아 hash 도 같다.
  - 정상 빈 보유([] · 전량매도)도 전송한다. 파일 없음 · 손상 · 형식 오류와 구분한다.
  - 상태 기록에 마지막 **성공** 적용 hash(last_applied_sha256)를 따로 두어 '미적용
    변경 있음'(pending_apply)을 판정한다. 실패 기록이 덮어써도 이어받아 보존한다.

**manifest 계약(설계자 확정 2026-08-06):**
  - OCI 의 active 정본은 **payload 파일 1개**다. 별도 active manifest 파일을 만들지
    않는다(2개 파일은 파일시스템이 동시 원자 교체를 보장 못 해 정합이 깨지므로).
  - applied_hash 는 적용 완료 후 OCI active payload 원문 바이트에서 SHA-256 으로
    다시 계산한다. PC 가 전송 전 계산한 hash 와 같으면 성공.
  - kind/created_at 은 응답·로그에만 담고, payload 와 원자 교체할 별도 정본 파일로
    만들지 않는다. Holdings JSON 스키마에 _apply_meta 를 추가하지 않는다.
  - 기존 manifest 가 있더라도 이번 적용 성공 판정 근거로 쓰지 않는다.

원자적 적용의 순서(기존 적용 상태 보존 계약):
  1. 로컬 문서 **schema 검증 + payload 생성**(validate_holdings → serialize_payload).
     손상 파일은 전송조차 안 한다.
  2. payload(PC 임시 파일) → payload-tmp 전송(active 는 아직 안 건드림).
  3. **replace 전에** 검증을 모두 끝낸다:
       (a) sha256(payload-tmp) == payload sha256  (전송 무결성)
       (b) payload-tmp JSON 파싱 + holdings 가 리스트인지  (schema 무결성 · 빈 목록 허용)
     → 하나라도 실패하면 payload-tmp 를 지우고 active 는 그대로 둔다(보존).
  4. **payload-tmp → active 를 단일 atomic mv 로 교체**한다. active 를 바꾸는
     원자 연산은 이 mv 하나뿐이고, 정본 파일도 이 payload 하나뿐이므로 부분 실패로
     정합이 깨지는 경로가 없다. mv 이전 실패는 전부 active 보존, mv 자체 실패도
     active 미변경.
  5. **active payload 재독출 + hash 재계산**: PC hash == OCI active hash 면
     OCI_APPLIED, 불일치면 OUT_OF_SYNC, 재확인 자체 실패면 UNKNOWN.
  - idempotent: 같은 내용을 다시 적용해도 같은 hash·schema → 같은 성공 경로.

응답 데이터 계약(§6·§13): SSH target·remote path·raw subprocess 출력·secret 을
반환하지 않는다. 사용자 중심 상태·시각·짧은 오류 요약만.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app import holdings as holdings_module
from app.config import optional_env, require_env
from app.holdings import (
    HoldingsValidationError,
    holdings_from_document,
    serialize_payload,
    validate_holdings,
)

logger = logging.getLogger(__name__)

# PC 보유 문서 경로. None(기본) = 호출 때 holdings.HOLDINGS_FILE 을 쓴다(PC·OCI 공통
# 규약 · 테스트 격리 일원화). 테스트가 경로를 지정하면 그 경로를 쓴다.
_LOCAL_HOLDINGS: Optional[Path] = None
# POC3-08: 마지막 OCI 적용 시각·상태를 PC 로컬에 남긴다(PARAM 의 sync_status 패턴).
#   OCI active manifest(r5 에서 정합 문제로 제거)와 무관 — 이건 PC 로컬 기록일 뿐이고
#   적용 성공 판정 근거가 아니다(판정은 active 재독출 hash). "언제 적용했나" 만 남긴다.
_LOCAL_APPLY_STATUS = Path("state/holdings/holdings_apply_status_latest.json")
_REMOTE_HOME = "/home/ubuntu/krx_hyungsoo"
_REMOTE_DIR = f"{_REMOTE_HOME}/state/holdings"
_REMOTE_FINAL = f"{_REMOTE_DIR}/holdings_latest.json"
_REMOTE_TMP = f"{_REMOTE_DIR}/holdings_latest.json.apply-tmp"

# kind: 응답·로그용 식별자(별도 정본 파일 아님).
_APPLY_KIND = "holdings_latest"

_SCP_TIMEOUT_SEC = 60
_SSH_TIMEOUT_SEC = 30


# 적용 상태(설계 §6.2 · PLAN §4.3). UI 표시용.
STATUS_PC_SAVED = "PC_SAVED"  # 로컬 파일 없음/미적용 전
STATUS_OCI_APPLIED = "OCI_APPLIED"  # replace 성공 + active hash == PC hash
STATUS_OUT_OF_SYNC = (
    "OUT_OF_SYNC"  # replace 됐으나 active hash 재확인 불일치(PLAN §4.3)
)
STATUS_APPLY_FAILED = (
    "APPLY_FAILED"  # replace 이전 실패(로컬 schema·전송·검증·mv) → active 보존
)
STATUS_UNKNOWN = "UNKNOWN"  # ENV 미설정 / replace 후 hash 재확인 자체 실패


@dataclass
class HoldingsApplyResult:
    status: str
    applied_at: Optional[str]
    content_sha256: Optional[str]  # PC 전송 payload 해시(표시용)
    oci_verified: bool
    message: str
    kind: str = _APPLY_KIND  # 응답용 식별자(별도 정본 파일 아님)


def _local_holdings_path() -> Path:
    """PC 보유 문서 경로(기본 = 호출 때의 holdings.HOLDINGS_FILE)."""
    if _LOCAL_HOLDINGS is not None:
        return _LOCAL_HOLDINGS
    return holdings_module.HOLDINGS_FILE


def _last_applied(rec: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    """상태 기록에서 마지막 **성공** 적용의 (payload sha, 시각). 없으면 (None, None).

    POC5-05: last_applied_sha256 이 없는 구 기록은 OCI_APPLIED 기록의 content_sha256 을
    마지막 성공으로 본다 — 구 기록의 content_sha256 은 파일 바이트 hash 이고, 기존 save
    형식 파일은 payload 와 바이트가 같으므로 그대로 이어진다.
    """
    if not isinstance(rec, dict):
        return None, None
    sha = rec.get("last_applied_sha256")
    if isinstance(sha, str) and sha:
        return sha, rec.get("last_applied_at")
    if rec.get("status") == STATUS_OCI_APPLIED:
        legacy = rec.get("content_sha256")
        if isinstance(legacy, str) and legacy:
            return legacy, rec.get("applied_at")
    return None, None


def _save_apply_status(result: "HoldingsApplyResult") -> None:
    """마지막 OCI 적용 상태를 PC 로컬에 기록(요구 4). 실패는 무시(부가 기록).

    PARAM 의 sync_status 패턴과 동일. 이 파일은 성공 판정 근거가 아니라 "언제·무슨
    결과로 적용했나" 표시용이다(판정은 active 재독출 hash). OCI active manifest
    (r5 에서 정합 문제로 제거)와 무관한 PC 로컬 기록이다.

    POC5-05: last_applied_sha256 · last_applied_at 은 OCI_APPLIED 때만 이번 값으로
    갱신하고, 실패 · 기타 결과로 덮어쓸 때는 이전 기록의 값을 이어받는다(미적용 판정용).
    """
    if result.status == STATUS_OCI_APPLIED:
        last_sha, last_at = result.content_sha256, result.applied_at
    else:
        last_sha, last_at = _last_applied(read_apply_status())
    try:
        _LOCAL_APPLY_STATUS.parent.mkdir(parents=True, exist_ok=True)
        recorded_at = datetime.now(timezone.utc).isoformat()
        _LOCAL_APPLY_STATUS.write_text(
            json.dumps(
                {
                    "kind": _APPLY_KIND,
                    "status": result.status,
                    "oci_verified": result.oci_verified,
                    "applied_at": result.applied_at,
                    "content_sha256": result.content_sha256,
                    "last_applied_sha256": last_sha,
                    "last_applied_at": last_at,
                    "message": result.message,
                    "recorded_at": recorded_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as e:  # noqa: BLE001 - 상태 기록 실패는 적용 결과를 바꾸지 않음
        logger.warning("holdings apply status 기록 실패(무시): %s", e)


def read_apply_status() -> Optional[dict]:
    """마지막 OCI 적용 상태를 읽는다. 파일 없거나 손상이면 None.

    저장 시 원격 경로·SSH target·secret 을 애초에 담지 않으므로 마스킹 불필요.
    """
    if not _LOCAL_APPLY_STATUS.exists():
        return None
    try:
        data = json.loads(_LOCAL_APPLY_STATUS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("holdings apply status 파일 손상: %s", type(e).__name__)
        return None
    return data if isinstance(data, dict) else None


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


def _build_payload(raw_bytes: bytes) -> tuple[Optional[bytes], Optional[str]]:
    """PC 보유 문서 원문 → OCI 적용 payload(허용 5필드 · 기존 save 형식 bytes).

    (payload, None) 또는 (None, 사용자용 사유). app/holdings.py 의 holdings_from_document ·
    serialize_payload 재사용(단일 계약). 정상 빈 보유([])는 payload 로 통과한다.
    이력 포함 문서의 holdings 는 줄 ID 로 계산한 결과라 삼중조합 중복을 거절하지 않는다
    (load() 와 같은 판정).
    """
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"JSON 파싱 실패: {e}"
    if not isinstance(data, dict) or "holdings" not in data:
        return None, "holdings 키가 없는 형식입니다."
    try:
        # load() 와 같은 판정 — 이력 문서는 holdings 가 이력과 맞아야 한다(POC5-05).
        holdings = holdings_from_document(data)
    except HoldingsValidationError as e:
        return None, f"보유 종목 형식 오류: {e}"
    return serialize_payload(holdings), None


def _payload_readable_by_consumer(payload: bytes) -> Optional[str]:
    """payload 를 OCI loader 와 같은 판정으로 다시 검증. 문제 있으면 사용자용 사유.

    payload 는 이력 포함 문서가 아니므로 OCI load() 는 (종목, 계좌, 평단) 삼중조합
    중복을 거절한다. PC 줄 ID 계산으로 평단이 우연히 같아진 두 줄을 그대로 보내면 OCI
    보유 소비 경로가 모두 실패하므로, 전송 전에 막고 기존 적용 상태를 보존한다.
    """
    try:
        validate_holdings(json.loads(payload)["holdings"], allow_empty=True)
    except HoldingsValidationError as e:
        return f"OCI 가 읽을 수 없는 보유 목록입니다: {e}"
    return None


def current_payload_sha256() -> Optional[str]:
    """현재 PC 보유로 만든 적용 payload 의 sha256. 파일 없음 · 읽기/형식 실패면 None."""
    try:
        raw_bytes = _local_holdings_path().read_bytes()
    except OSError:
        return None
    payload, _err = _build_payload(raw_bytes)
    return None if payload is None else _sha256_of_bytes(payload)


def last_applied_at(rec: Optional[dict]) -> Optional[str]:
    """마지막 **성공** 적용 시각(실패 기록이 덮어써도 남는다). 없으면 None."""
    return _last_applied(rec)[1]


def pending_apply(rec: Optional[dict]) -> Optional[bool]:
    """현재 PC 보유가 마지막 성공 적용과 다른가(미적용 변경 있음).

    True/False = 현재 payload sha != / == 마지막 성공 sha. 성공 기록이 없거나 PC 문서를
    읽을 수 없으면 None('확인 안 됨' · 적용 완료로 표시하지 않음). 이력만 바뀐 문서는
    payload 가 같으므로 False 다. 마지막 시도가 교체 뒤 확인 불일치 · 확인 불가
    (OUT_OF_SYNC · UNKNOWN)면 OCI 내용을 모르므로 None 이다.
    """
    if isinstance(rec, dict) and rec.get("status") in (
        STATUS_OUT_OF_SYNC,
        STATUS_UNKNOWN,
    ):
        return None
    last_sha, _last_at = _last_applied(rec)
    if last_sha is None:
        return None
    current = current_payload_sha256()
    if current is None:
        return None
    return current != last_sha


def _fail(msg: str, sha: Optional[str] = None) -> HoldingsApplyResult:
    return HoldingsApplyResult(
        status=STATUS_APPLY_FAILED,
        applied_at=None,
        content_sha256=sha,
        oci_verified=False,
        message=msg,
    )


def _cleanup_tmp(ssh_base: list[str]) -> None:
    """검증·replace 실패 시 원격 payload-tmp 정리. active 는 안 건드림."""
    _run(ssh_base + [f"rm -f {_REMOTE_TMP}"], timeout=_SSH_TIMEOUT_SEC)


def apply_holdings_to_oci() -> HoldingsApplyResult:
    """저장된 Holdings 를 OCI 에 적용하고, 마지막 적용 상태를 PC 로컬에 기록한다.

    실제 적용 로직은 _apply_holdings_to_oci_impl 이 수행하고, 여기서 결과를 받아
    holdings_apply_status_latest.json 에 남긴다(요구 4 — 언제 적용했는지 지속 표시).
    """
    result = _apply_holdings_to_oci_impl()
    # PC_SAVED(적용 시도 자체 안 함)를 제외하고 실제 적용 시도 결과만 기록한다.
    if result.status != STATUS_PC_SAVED:
        _save_apply_status(result)
    return result


def _apply_holdings_to_oci_impl() -> HoldingsApplyResult:
    """저장된 Holdings 를 OCI 에 명시적으로 적용한다(단일 정본 payload).

    임시 파일 전송 → 형식 검증 → 단일 atomic replace → active 재독출 → hash 확인.
    별도 manifest 정본 파일을 만들지 않으므로 2파일 정합 문제가 없다.
    사용자 명시 클릭에서만 호출.
    """
    # 0. 로컬 소스 존재 확인.
    local_path = _local_holdings_path()
    if not local_path.exists():
        return HoldingsApplyResult(
            status=STATUS_PC_SAVED,
            applied_at=None,
            content_sha256=None,
            oci_verified=False,
            message="저장된 보유 종목 파일이 없습니다. 먼저 종목 관리에서 저장하세요.",
        )

    # 1. 문서를 한 번 읽어 schema 검증 + 허용 5필드 payload 생성 — 손상 파일은 전송조차
    #    하지 않는다(active 보존). 이후 hash · 전송 · 재확인은 모두 이 payload 기준.
    try:
        raw_bytes = local_path.read_bytes()
    except OSError as e:
        return _fail(
            f"보유 종목 파일을 읽지 못해 적용하지 않았습니다. 기존 적용 상태는 "
            f"유지됩니다. ({type(e).__name__})"
        )
    payload, schema_err = _build_payload(raw_bytes)
    if payload is None:
        return _fail(
            f"보유 종목 파일 검증에 실패해 적용하지 않았습니다. 기존 적용 상태는 "
            f"유지됩니다. ({schema_err})"
        )
    local_sha = _sha256_of_bytes(payload)
    consumer_err = _payload_readable_by_consumer(payload)
    if consumer_err is not None:
        return _fail(
            f"보유 종목 검증에 실패해 적용하지 않았습니다. 기존 적용 상태는 "
            f"유지됩니다. ({consumer_err})",
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

    # payload 를 PC 임시 파일(바이너리)로 써서 보낸다. 전송이 끝나면(성공 · 실패 무관) 지운다.
    try:
        local_tmp = _write_local_payload(payload)
    except OSError as e:
        logger.error("holdings 적용 payload 임시 파일 작성 실패: %s", type(e).__name__)
        return _fail(
            "전송할 파일을 준비하지 못했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )
    try:
        return _transfer_and_replace(target, local_tmp, local_sha)
    finally:
        try:
            local_tmp.unlink()
        except OSError as e:  # noqa: BLE001 - 정리 실패는 적용 결과를 바꾸지 않음
            logger.warning(
                "holdings 적용 payload 임시 파일 삭제 실패: %s", type(e).__name__
            )


def _write_local_payload(payload: bytes) -> Path:
    """payload bytes 를 PC 임시 파일에 바이너리로 쓴다(mkstemp = 소유자 전용 권한)."""
    fd, name = tempfile.mkstemp(prefix="holdings_apply_", suffix=".json")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
    except OSError:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def _transfer_and_replace(
    target: str, local_tmp: Path, local_sha: str
) -> HoldingsApplyResult:
    """payload 임시 파일 전송 → (replace 전) hash · 구조 검증 → 단일 mv → 재확인."""
    key_opts = _ssh_key_opts()

    ssh_base = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_TIMEOUT_SEC}",
        *key_opts,
        target,
    ]

    # 2. payload 를 payload-tmp 로 전송(active 는 아직 안 건드림).
    scp_cmd = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_TIMEOUT_SEC}",
        *key_opts,
        str(local_tmp),
        f"{target}:{_REMOTE_TMP}",
    ]
    rc, _so, _se = _run(scp_cmd, timeout=_SCP_TIMEOUT_SEC)
    if rc != 0:
        logger.error("holdings scp 실패: rc=%s", rc)
        _cleanup_tmp(ssh_base)
        return _fail("OCI 전송에 실패했습니다. 기존 적용 상태는 유지됩니다.", local_sha)

    # 3. (replace 전) payload-tmp hash 검증 — 전송 무결성.
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

    # 4. (replace 전) payload-tmp schema 검증 — 원격 JSON 파싱 + holdings 가 리스트인지.
    #    POC5-05: 정상 빈 보유(전량매도)를 보내야 하므로 len>0 조건은 두지 않는다.
    remote_schema_check = (
        'python3 -c "import json,sys; '
        f"d=json.load(open('{_REMOTE_TMP}')); "
        "sys.exit(0 if (isinstance(d,dict) and isinstance(d.get('holdings'),list)) "
        'else 1)"'
    )
    rc, _so, _se = _run(ssh_base + [remote_schema_check], timeout=_SSH_TIMEOUT_SEC)
    if rc != 0:
        _cleanup_tmp(ssh_base)
        return _fail(
            "전송 파일 구조 검증에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    # 5. 단일 atomic replace — payload-tmp → active. active 를 바꾸는 원자 연산은
    #    이 mv 하나뿐이고 정본 파일도 payload 하나뿐이므로, 부분 실패로 정합이
    #    깨지는 경로가 없다. mv 이전 실패는 전부 active 보존, mv 자체 실패도 미변경.
    rc, _so, _se = _run(
        ssh_base + [f"mv {_REMOTE_TMP} {_REMOTE_FINAL}"], timeout=_SSH_TIMEOUT_SEC
    )
    if rc != 0:
        _cleanup_tmp(ssh_base)  # payload active 미변경 → 보존.
        return _fail(
            "OCI 적용(원자 교체)에 실패했습니다. 기존 적용 상태는 유지됩니다.",
            local_sha,
        )

    applied_at = datetime.now(timezone.utc).isoformat()

    # 6. active payload 재독출 + hash 재계산(PLAN §4.3). PC hash == OCI active hash 면
    #    OCI_APPLIED, 불일치면 OUT_OF_SYNC, 재확인 자체 실패면 UNKNOWN.
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
        logger.info(
            "holdings OCI 적용 성공: kind=%s applied_at=%s", _APPLY_KIND, applied_at
        )
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
