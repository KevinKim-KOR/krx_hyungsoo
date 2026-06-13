"""외부 전달 어댑터 — POC1 Step 3 실 OCI 연결.

흐름:
1) `write_handoff_artifact(run, approved_at)` 로 로컬 staging 파일 생성
2) SCP 로 OCI 측 inbox(`OCI_REMOTE_INBOX/{run_id}.json`) 에 전송
3) 성공 시 staging 파일을 processed/ 로 이동
4) 이 시점까지가 한 차례 deliver() 의 책임. 최종 COMPLETED/FAILED 는
   OCI 측 daily_ops.sh → poc1_consume_inbox.sh 가 outbox 에 결과 파일을
   쓰고, 로컬 GET /runs/{run_id} 가 이를 조회하여 갱신한다.

새로운 worker/scheduler 를 만들지 않는다. 기존 OCI crontab 자산
(daily_ops.sh) 에 step 으로 끼워 넣는 것이 설계자 결정.

환경변수 (필수):
- OCI_SSH_TARGET   : ubuntu@<host> 또는 ~/.ssh/config 의 alias
- OCI_REMOTE_INBOX : OCI 측 inbox 경로 (예: /home/ubuntu/krx_hyungsoo/state/poc1_inbox)
- OCI_REMOTE_OUTBOX: OCI 측 outbox 경로

환경변수 (선택):
- OCI_SSH_KEY_PATH : SSH 개인키 절대경로. 미설정 시 OpenSSH 기본 키 검색
                     (~/.ssh/id_rsa, id_ed25519 등) 사용

환경변수는 app.config 의 require_env / optional_env 표준 진입점을 통해
조회한다 (.env 자동 로드 + 누락 시 fail-loud).

테스트는 이 모듈의 deliver / scp_upload / fetch_outbox_result 를
monkeypatch 하여 실 SSH 호출을 차단한다.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Optional

from app import draft_message, store
from app.config import EnvConfigError, optional_env, require_env
from app.models import Run

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    pass


# 표준 환경변수 누락 예외와 별칭. 기존 import 호환을 위해 유지.
DeliveryConfigError = EnvConfigError


SCP_TIMEOUT_SEC = 15
SSH_TIMEOUT_SEC = 10


def _ssh_target() -> str:
    return require_env("OCI_SSH_TARGET")


def _remote_inbox() -> str:
    return require_env("OCI_REMOTE_INBOX")


def _remote_outbox() -> str:
    return require_env("OCI_REMOTE_OUTBOX")


def _ssh_key_opts() -> list[str]:
    """OCI_SSH_KEY_PATH 가 설정된 경우 ssh/scp 의 -i 옵션을 구성.

    미설정이면 빈 리스트 → OpenSSH 가 기본 키를 자동 검색.
    """
    key_path = optional_env("OCI_SSH_KEY_PATH", default=None)
    if not key_path:
        return []
    # IdentitiesOnly=yes: 지정한 키만 사용하여 인증 시도. 다른 키로의 fallback 차단.
    return ["-i", key_path, "-o", "IdentitiesOnly=yes"]


def _scp_upload(local_path: str, remote_uri: str) -> None:
    """scp 단일 파일 업로드. 실패 시 DeliveryError."""
    cmd = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SCP_TIMEOUT_SEC}",
        *_ssh_key_opts(),
        local_path,
        remote_uri,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SCP_TIMEOUT_SEC + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise DeliveryError(f"scp timeout: {e}")
    except FileNotFoundError as e:
        raise DeliveryError(f"scp 실행 파일을 찾을 수 없음: {e}")
    if result.returncode != 0:
        raise DeliveryError(
            f"scp 실패 (exit {result.returncode}): "
            f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}"
        )


def deliver(run: Run) -> None:
    """DELIVERING 상태의 run 을 OCI inbox 로 SCP 전송한다.

    성공 시 예외 없이 반환. 실패 시 DeliveryError raise.
    """
    if run.status != "DELIVERING":
        raise DeliveryError(f"DELIVERING 상태만 전달 가능: current={run.status}")
    if not run.draft_payload:
        raise DeliveryError(f"payload 없음: run_id={run.run_id}")
    if "title" not in run.draft_payload:
        raise DeliveryError(f"payload 에 필수 키 'title' 누락: run_id={run.run_id}")

    target = _ssh_target()
    remote_dir = _remote_inbox()
    approved_at = datetime.now(timezone.utc).isoformat()

    # POC2 Step 2D: preview ↔ 실제 발송문 단일 소스 — Run 에 저장된 message_text 를
    # 그대로 사용한다. 신규 run 은 generate 시점에 백엔드가 빌드해 Run 에 저장했고,
    # GET /runs/{id} 응답·OCI handoff·Telegram 발송 모두 동일 문자열이다.
    # 과거(Step 2D 이전 생성) run 은 Run.message_text 가 None 일 수 있다 — 이 경우
    # holdings draft 라면 동일 빌더를 그 자리에서 호출해 fallback (POC2 Step 1A 호환).
    # 이 fallback 은 신규 run 에서는 절대 트리거되지 않는다 (None 일 수 없음).
    message_text: Optional[str] = run.message_text
    if message_text is None and draft_message.is_holdings_draft(run.draft_payload):
        message_text = draft_message.build_message_text(
            run.run_id, run.draft_payload or {}
        )
    # POC2 3-PUSH (2026-06-11): PUSH-1 / PUSH-3 은 generate 시점에 message_text 가
    # 항상 박혀있다. 본 분기에서 message_text 가 None 이면 운영 상 결함이므로
    # holdings fallback 으로 raw 가 노출되지 않도록 명시 에러로 떨어진다 (§10.10
    # raw JSON 금지).
    if message_text is None and run.push_kind in (
        "market_briefing",
        "spike_or_falling_alert",
    ):
        raise DeliveryError(
            f"push_kind={run.push_kind} run 에 message_text 가 없습니다 — "
            f"holdings fallback 으로 대체 발송 금지: run_id={run.run_id}"
        )

    # 1) staging artifact 작성
    local_path = store.write_handoff_artifact(run, approved_at, message_text)
    remote_uri = f"{target}:{remote_dir}/{run.run_id}.json"

    # 2) SCP 업로드
    logger.info(f"[delivery] scp {local_path} → {remote_uri}")
    _scp_upload(str(local_path), remote_uri)

    # 3) staging → processed
    store.archive_handoff_artifact(run.run_id)
    logger.info(
        f"[delivery] handoff queued at OCI inbox (run_id={run.run_id}). "
        "최종 status 는 OCI consumer 가 outbox 에 기록 후 polling 으로 반영됨."
    )


_RUN_ID_PATTERN = re.compile(r"^run_[0-9A-Za-z_]+$")


def fetch_outbox_result(run_id: str) -> Optional[dict]:
    """OCI 측 outbox 의 {run_id}.json 을 SSH cat 으로 조회.

    반환:
    - dict (status / processed_at / 등) — outbox 파일이 존재할 때
    - None — 아직 결과 없음 (DELIVERING 유지)

    실 호출은 GET /runs/{run_id} 핸들러에서 트리거됨. 별도 worker 없음.
    """
    # run_id 는 외부에서 들어오므로 화이트리스트 패턴으로 1차 검증.
    # 그 다음 remote command 도 shlex.quote 로 두 번째 방어.
    if not _RUN_ID_PATTERN.match(run_id):
        logger.warning(f"[delivery] 비정상 run_id 패턴: {run_id!r}")
        return None

    target = _ssh_target()
    remote_dir = _remote_outbox()
    remote_path = f"{remote_dir}/{run_id}.json"
    quoted_path = shlex.quote(remote_path)

    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SSH_TIMEOUT_SEC}",
        *_ssh_key_opts(),
        target,
        f"test -f {quoted_path} && cat {quoted_path} || echo __NOFILE__",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT_SEC + 5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # outbox 조회 실패는 DELIVERING 유지로 fallback (다음 polling 에서 재시도)
        logger.warning(f"[delivery] outbox 조회 timeout run_id={run_id}")
        return None
    except FileNotFoundError:
        logger.warning("[delivery] ssh 실행 파일 미발견")
        return None
    if result.returncode != 0:
        logger.warning(
            f"[delivery] outbox 조회 실패 (exit {result.returncode}): "
            f"{result.stderr.strip()!r}"
        )
        return None

    body = result.stdout.strip()
    if not body or body == "__NOFILE__":
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        logger.warning(f"[delivery] outbox JSON 파싱 실패 run_id={run_id}: {e}")
        return None
