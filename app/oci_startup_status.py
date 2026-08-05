"""OCI 운영 상태 — PC 백엔드 기동 시 1회만 읽는 읽기 전용 스냅샷.

설계(POC3-07 PLAN V2 §4.2 · 설계자 Q2):
  - PC 백엔드가 기동될 때 **승인된 SSH 읽기 1회만** 수행한다.
  - 사용자 요청·화면 진입·브라우저 새로고침·타이머·수동 버튼으로 다시 조회하지 않는다.
  - 결과는 프로세스 로컬(모듈 전역)에 유지한다. 조회 API 는 이 캐시를 반환한다.
  - 조회 실패는 PC 기동을 막지 않고 status=UNKNOWN 으로 남긴다.
  - 이것은 모니터링 시스템이 아니다. 기존 status·artifact 를 기동 시 한 번 안전하게 읽는
    최소 계약이다. OCI runner·crontab 을 수정하지 않는다(설계자 Q5).

읽기 전용 SSH 만 사용한다(BatchMode=yes). 원격 쓰기·job 실행·Telegram 발송·재시작은
이 모듈에서 절대 하지 않는다.

민감정보(토큰·chat id·원격 경로·raw payload)는 스냅샷에 담지 않는다(설계 §13).
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.config import optional_env, require_env

logger = logging.getLogger(__name__)

# 기동 시 SSH 읽기의 짧은 타임아웃. 기동을 오래 막지 않는다.
_SSH_CONNECT_TIMEOUT_SEC = 8
_SSH_RUN_TIMEOUT_SEC = 15

# OCI 원격 홈(배포 규약). 경로는 민감정보가 아니며 저장소 스크립트에 이미 공개돼 있다.
_REMOTE_HOME = "/home/ubuntu/krx_hyungsoo"


@dataclass
class OciJobStatus:
    """단일 job 의 기동 시 관측 상태. 구분 불가는 UNKNOWN."""

    job: str
    status: str  # SUCCESS / STALE / UNKNOWN (기동 읽기로 구분 가능한 범위만)
    detail: str = ""


@dataclass
class OciStartupSnapshot:
    """기동 시 1회 읽은 OCI 상태 스냅샷(프로세스 로컬 유지)."""

    checked_at: Optional[str] = None  # ISO8601, 읽기를 시도한 시각
    reachable: bool = False
    overall: str = "UNKNOWN"  # OPERATING / DEGRADED / UNKNOWN
    summary_line: str = "OCI 상태 미확인"  # 첫 화면 한 줄
    crontab_active: Optional[bool] = None
    jobs: list[OciJobStatus] = field(default_factory=list)
    note: str = ""  # 사용자용 요약(민감정보 없음)


# 프로세스 로컬 캐시. 기동 시 1회 채워지고 이후 재조회하지 않는다.
_snapshot: OciStartupSnapshot = OciStartupSnapshot()


def _ssh_key_opts() -> list[str]:
    """OCI_SSH_KEY_PATH 가 설정되면 -i 옵션. 미설정이면 기본 키 자동 검색."""
    key_path = optional_env("OCI_SSH_KEY_PATH", default=None)
    if not key_path:
        return []
    return ["-i", key_path, "-o", "IdentitiesOnly=yes"]


def _ssh_read(remote_cmd: str) -> tuple[bool, str]:
    """읽기 전용 SSH 명령 1회 실행. (성공여부, stdout) 반환.

    BatchMode=yes 로 비밀번호 프롬프트 시 즉시 실패(행 방지). 실패해도 예외를
    올리지 않고 (False, "") 를 반환해 기동을 막지 않는다.
    """
    target = require_env("OCI_SSH_TARGET")
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_SSH_CONNECT_TIMEOUT_SEC}",
        *_ssh_key_opts(),
        target,
        remote_cmd,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SSH_RUN_TIMEOUT_SEC,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("OCI 기동 읽기 실패(무시하고 기동 진행): %s", e)
        return False, ""
    if result.returncode != 0:
        logger.warning("OCI 기동 읽기 non-zero(무시): exit=%s", result.returncode)
        return False, ""
    return True, result.stdout.strip()


# crontab 에 등록되어 있어야 하는 필수 push-kind(설계·crontab 실측 기준).
#   이 중 하나라도 crontab 에서 빠지면 "일부 스케줄 누락" 으로 구분한다
#   (검증자 B-6: runner 한 줄만 있어도 OPERATING 으로 판정하던 문제 정정).
_REQUIRED_PUSH_KINDS = (
    "market_briefing",
    "holdings_briefing",
    "spike_or_falling_alert",
)


def _classify_schedule(scheduled_kinds: set[str]) -> tuple[str, list[str]]:
    """등록된 push-kind 집합으로 스케줄 상태를 판정.

    반환: (overall, missing_kinds)
      - OPERATING: 필수 kind 가 모두 등록됨
      - DEGRADED: 일부 필수 kind 누락(운영 중이나 불완전)
      - UNKNOWN: 등록된 runner 가 하나도 없음
    """
    if not scheduled_kinds:
        return "UNKNOWN", list(_REQUIRED_PUSH_KINDS)
    missing = [k for k in _REQUIRED_PUSH_KINDS if k not in scheduled_kinds]
    if missing:
        return "DEGRADED", missing
    return "OPERATING", []


def _unknown_snapshot(checked_at: str, summary: str, note: str) -> OciStartupSnapshot:
    return OciStartupSnapshot(
        checked_at=checked_at,
        reachable=False,
        overall="UNKNOWN",
        summary_line=summary,
        note=note,
    )


def refresh_snapshot() -> OciStartupSnapshot:
    """OCI 상태를 SSH 읽기 1회로 조회해 프로세스 로컬 캐시를 채운다.

    기동 시 한 번 호출. 실패해도 예외 없이 UNKNOWN 스냅샷을 남긴다.
    """
    global _snapshot
    checked_at = datetime.now(timezone.utc).isoformat()

    # 환경변수 미설정이면 조회 자체를 시도하지 않는다(로컬 개발 등).
    try:
        require_env("OCI_SSH_TARGET")
    except Exception:  # noqa: BLE001 - EnvConfigError 포함, 기동 막지 않음
        _snapshot = _unknown_snapshot(
            checked_at,
            "OCI 상태 미확인 (OCI_SSH_TARGET 미설정)",
            "OCI 접속 대상이 설정되지 않아 기동 시 조회를 건너뛰었습니다.",
        )
        return _snapshot

    # 한 번의 SSH 세션으로 필요한 읽기 전용 사실을 모아 읽는다(모두 읽기 전용).
    #   1) crontab 에 등록된 push-kind 목록(--push-kind 인자 추출)
    #   2) holdings 소스 파일 최근 수정 epoch
    #   3) runtime_state.sqlite 최근 수정 epoch·크기
    # 구분자 '###' 로 세 블록을 나눠 파싱한다.
    remote_cmd = (
        "crontab -l 2>/dev/null "
        "| grep -oE -- '--push-kind [a-z_]+' | awk '{print $2}' | sort -u; "
        "echo '###'; "
        f"stat -c '%Y' {_REMOTE_HOME}/state/holdings/holdings_latest.json "
        "2>/dev/null || echo 0; "
        f"stat -c '%Y %s' {_REMOTE_HOME}/state/runtime/runtime_state.sqlite "
        "2>/dev/null || echo '0 0'"
    )
    ok, out = _ssh_read(remote_cmd)

    if not ok:
        _snapshot = _unknown_snapshot(
            checked_at,
            "OCI 상태 미확인 (접속 실패)",
            "OCI 에 접속하지 못해 상태를 확인할 수 없습니다. 기동은 정상 진행됩니다.",
        )
        return _snapshot

    # 파싱: '###' 앞 = push-kind 목록, 뒤 = stat 두 줄.
    parts = out.split("###")
    kinds_block = parts[0] if len(parts) > 0 else ""
    stat_block = parts[1] if len(parts) > 1 else ""
    scheduled_kinds = {ln.strip() for ln in kinds_block.splitlines() if ln.strip()}
    stat_lines = [ln.strip() for ln in stat_block.splitlines() if ln.strip()]
    holdings_epoch = stat_lines[0] if len(stat_lines) > 0 else "0"
    runtime_stat = stat_lines[1] if len(stat_lines) > 1 else "0 0"

    overall, missing = _classify_schedule(scheduled_kinds)
    crontab_active = overall in ("OPERATING", "DEGRADED")

    jobs: list[OciJobStatus] = []
    # crontab — 필수 push-kind 등록 여부(누락 구분).
    if overall == "OPERATING":
        cron_detail = "필수 스케줄(시장·보유·급등락) 모두 등록됨"
        cron_status = "SUCCESS"
    elif overall == "DEGRADED":
        cron_detail = f"일부 스케줄 누락: {', '.join(missing)}"
        cron_status = "STALE"
    else:
        cron_detail = "등록된 스케줄 확인 불가"
        cron_status = "UNKNOWN"
    jobs.append(OciJobStatus(job="crontab", status=cron_status, detail=cron_detail))

    # 관측한 artifact 최신성(읽어온 stat 값을 실제로 사용한다 — 검증자 B-6).
    jobs.append(
        OciJobStatus(
            job="holdings_source",
            status="SUCCESS" if holdings_epoch not in ("", "0") else "UNKNOWN",
            detail=_epoch_detail("holdings 소스", holdings_epoch),
        )
    )
    runtime_epoch = runtime_stat.split()[0] if runtime_stat else "0"
    runtime_size = runtime_stat.split()[1] if len(runtime_stat.split()) > 1 else "0"
    jobs.append(
        OciJobStatus(
            job="runtime_state_db",
            status="SUCCESS" if runtime_size not in ("", "0") else "UNKNOWN",
            detail=(
                _epoch_detail("runtime_state.sqlite", runtime_epoch)
                + f" · {runtime_size} bytes"
            ),
        )
    )
    # 개별 PUSH job 의 최신 성공/실패는 기동 읽기만으로 신뢰성 있게 구분 불가
    # (단일 status 파일은 spike 1건만 유지 — PROGRAM_TRUTH §14). UNKNOWN 유지(Q5).
    jobs.append(
        OciJobStatus(
            job="push_job_results",
            status="UNKNOWN",
            detail="개별 PUSH job 최신 성공/실패는 기동 읽기 범위 밖 (Q5)",
        )
    )

    if overall == "OPERATING":
        summary = "OCI 자동 운영 스케줄 활성 (필수 3종 등록 · 기동 시 확인)"
    elif overall == "DEGRADED":
        summary = f"OCI 스케줄 일부 누락: {', '.join(missing)} (기동 시 확인)"
    else:
        summary = "OCI 스케줄 확인 불가"

    _snapshot = OciStartupSnapshot(
        checked_at=checked_at,
        reachable=True,
        overall=overall,
        summary_line=summary,
        crontab_active=crontab_active,
        jobs=jobs,
        note=(
            "기동 시 1회 읽은 읽기 전용 스냅샷입니다. crontab 필수 push-kind 등록 "
            "여부와 artifact 최신성을 표시합니다. 개별 PUSH job 의 최신 성공/실패는 "
            "기존 단일 status 파일만으로 신뢰성 있게 구분할 수 없어 UNKNOWN 으로 둡니다."
        ),
    )
    return _snapshot


def _epoch_detail(label: str, epoch_str: str) -> str:
    """epoch 문자열을 사용자용 '최근 수정 …' 문구로. 0/파싱실패는 '확인 불가'."""
    try:
        epoch = int(epoch_str)
    except (TypeError, ValueError):
        return f"{label} 시각 확인 불가"
    if epoch <= 0:
        return f"{label} 파일 없음/확인 불가"
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    return f"{label} 최근 수정 {dt}"


def get_snapshot() -> OciStartupSnapshot:
    """기동 시 채워진 프로세스 로컬 스냅샷을 반환(재조회하지 않음)."""
    return _snapshot
