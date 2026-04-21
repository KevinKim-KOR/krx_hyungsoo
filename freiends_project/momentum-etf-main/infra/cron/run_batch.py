#!/usr/bin/env python3
"""VM cron 배치 래퍼.

사용법:
    python infra/cron/run_batch.py <job_name> <command...>

예시:
    python infra/cron/run_batch.py cache_refresh python scripts/stock_price_cache_updater.py

동작:
    1) subprocess 로 <command> 를 실행
    2) 종료 코드/소요시간/마지막 로그 꼬리(15줄)를 슬랙으로 전송
    3) 프로세스 종료 코드를 그대로 반환

알림 채널:
    utils.notification.send_slack_message_v2() 를 사용하므로
    환경변수 SLACK_BOT_TOKEN 과 config.SLACK_CHANNEL 을 따릅니다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 프로젝트 루트를 파이썬 경로에 추가 (컨테이너 WORKDIR=/app)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MAX_TAIL_LINES = 15
MAX_TAIL_CHARS = 1500

LOCK_DIR = PROJECT_ROOT / "logs" / "cron"


def _acquire_lock(job_name: str) -> Path:
    """실행 중 락파일 생성. 내용에는 pid 와 시작시각을 기록."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f"{job_name}.lock"
    lock_path.write_text(
        f"pid={os.getpid()}\nstarted={datetime.now(KST).isoformat()}\n",
        encoding="utf-8",
    )
    return lock_path


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception as exc:  # pragma: no cover
        print(f"[run_batch] 락 해제 실패: {exc}", file=sys.stderr)


def _notify(text: str) -> None:
    """슬랙 전송. 실패해도 배치 결과에 영향 없도록 방어적으로 처리."""
    try:
        from utils.notification import send_slack_message_v2  # 지연 임포트

        send_slack_message_v2(text)
    except Exception as exc:  # pragma: no cover - 알림 실패는 로그만
        print(f"[run_batch] 슬랙 전송 실패: {exc}", file=sys.stderr)


def _format_tail(stdout: str, stderr: str) -> str:
    combined = (stdout or "") + (stderr or "")
    lines = combined.strip().splitlines()
    if not lines:
        return "(출력 없음)"
    tail = "\n".join(lines[-MAX_TAIL_LINES:])
    if len(tail) > MAX_TAIL_CHARS:
        tail = "…(생략)…\n" + tail[-MAX_TAIL_CHARS:]
    return tail


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "usage: run_batch.py <job_name> <command...>",
            file=sys.stderr,
        )
        return 2

    job_name = argv[1]
    command = argv[2:]

    started_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    started_monotonic = time.monotonic()

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    print(f"[run_batch] START job={job_name} cmd={' '.join(command)} at={started_at}")

    lock_path = _acquire_lock(job_name)

    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        _release_lock(lock_path)
        elapsed = time.monotonic() - started_monotonic
        app_label = os.environ.get("APP_TYPE", "VM").strip() or "VM"
        _notify(
            f"❌ *[{app_label}] 배치 실행 불가*: `{job_name}`\n"
            f"• 시작: {started_at}\n"
            f"• 소요: {elapsed:.1f}s\n"
            f"• 에러: `{exc}`"
        )
        print(f"[run_batch] FAIL {exc}", file=sys.stderr)
        return 127
    except Exception as exc:
        _release_lock(lock_path)
        elapsed = time.monotonic() - started_monotonic
        app_label = os.environ.get("APP_TYPE", "VM").strip() or "VM"
        _notify(
            f"❌ *[{app_label}] 배치 예외*: `{job_name}`\n"
            f"• 시작: {started_at}\n"
            f"• 소요: {elapsed:.1f}s\n"
            f"• 에러: `{exc}`"
        )
        print(f"[run_batch] EXCEPTION {exc}", file=sys.stderr)
        return 1
    finally:
        _release_lock(lock_path)

    elapsed = time.monotonic() - started_monotonic
    exit_code = result.returncode
    success = exit_code == 0

    # 원본 출력은 그대로 stdout/stderr 로 흘려서 cron 로그파일에도 남김
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    emoji = "✅" if success else "❌"
    status = "성공" if success else "실패"
    tail = _format_tail(result.stdout, result.stderr)
    app_label = os.environ.get("APP_TYPE", "VM").strip() or "VM"

    _notify(
        f"{emoji} *[{app_label}] 배치 {status}*: `{job_name}`\n"
        f"• 시작: {started_at}\n"
        f"• 소요: {elapsed:.1f}s\n"
        f"• exit: {exit_code}\n"
        f"```\n{tail}\n```"
    )

    print(
        f"[run_batch] END job={job_name} status={status} exit={exit_code} elapsed={elapsed:.1f}s"
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
