"""PC latest three_push_runtime_param.v1 snapshot 을 OCI 로 전달.

기존 sync_three_push_packages.py 와 별개로, PARAM snapshot 만 동기화한다.
message package 와는 무관하다.

전제:
  - PC .env 에 OCI_SSH_TARGET 이 설정되어 있어야 함 (예: oci-krx)
  - ssh OCI_SSH_TARGET "echo OK" 가 성공해야 함
  - PC local 에 state/three_push/params/latest_runtime_param.json 이 존재해야 함

동작:
  1. PC local PARAM 파일 schema/금지키 검증
  2. scp 로 OCI tmp 위치에 업로드
  3. ssh 로 atomic rename (tmp → latest)
  4. OCI verification (verify_three_push_param_oci.py 를 일시 업로드 → 실행)
  5. sync_status_latest 기록

기록:
  state/three_push/params/param_sync_status_latest.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path 에 추가 (스크립트 직접 실행 지원).
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.three_push_runner_common import STATE_DIR, load_dotenv_file  # noqa: E402
from app.three_push_runtime_param import read_param_file  # noqa: E402

load_dotenv_file()


_PARAM_DIR = STATE_DIR / "params"
_LATEST_PATH = _PARAM_DIR / "latest_runtime_param.json"
_SYNC_STATUS_PATH = _PARAM_DIR / "param_sync_status_latest.json"

_DEFAULT_OCI_REMOTE_PARAM_DIR = "/home/ubuntu/krx_hyungsoo/state/three_push/params"

_VERIFY_SCRIPT_LOCAL = (
    Path(__file__).resolve().parent / "verify_three_push_param_oci.py"
)


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("sync_three_push_param")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """subprocess.run wrapper — (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PC latest PARAM snapshot 을 OCI 로 전달"
    )
    parser.add_argument(
        "--ssh-target",
        default=os.environ.get("OCI_SSH_TARGET", ""),
        help="SSH alias 또는 user@host (기본: env OCI_SSH_TARGET)",
    )
    parser.add_argument(
        "--remote-dir",
        default=os.environ.get(
            "THREE_PUSH_REMOTE_PARAM_DIR", _DEFAULT_OCI_REMOTE_PARAM_DIR
        ),
        help="OCI 측 PARAM 디렉토리 (기본: env THREE_PUSH_REMOTE_PARAM_DIR)",
    )
    args = parser.parse_args()

    logger = _setup_logger()
    started_at = datetime.now(timezone.utc).isoformat()
    status_record: dict = {
        "status": "failed",
        "started_at": started_at,
        "completed_at": "",
        "ssh_target": args.ssh_target,
        "remote_dir": args.remote_dir,
        "param_id": "",
        "param_source": "",
        "upload_status": "",
        "verify_status": "",
        "error": None,
    }

    def _finish(status: str, error: str = "") -> None:
        status_record["status"] = status
        status_record["error"] = error or None
        status_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        _SYNC_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _SYNC_STATUS_PATH.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(status_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(_SYNC_STATUS_PATH)

    if not args.ssh_target:
        logger.error("OCI_SSH_TARGET 미설정. PC .env 또는 --ssh-target 필요")
        _finish("failed", "missing_ssh_target")
        sys.exit(2)

    # ── 1. local PARAM 검증 ──────────────────────────────────────────────────
    if not _LATEST_PATH.exists():
        logger.error("local PARAM 없음: %s", _LATEST_PATH)
        _finish("failed", f"local PARAM missing: {_LATEST_PATH}")
        sys.exit(2)
    try:
        param = read_param_file(_LATEST_PATH)
    except Exception as e:
        logger.error("local PARAM 검증 실패: %s", e)
        _finish("failed", f"local PARAM invalid: {e}")
        sys.exit(2)

    status_record["param_id"] = param.param_id
    status_record["param_source"] = param.param_source

    # ── 2. remote 디렉토리 보장 ──────────────────────────────────────────────
    remote_dir = args.remote_dir
    logger.info("OCI 대상: %s → %s", args.ssh_target, remote_dir)
    rc, so, se = _run(["ssh", args.ssh_target, f"mkdir -p {remote_dir}"], timeout=30)
    if rc != 0:
        logger.error("remote 디렉토리 생성 실패: %s", se.strip())
        _finish("failed", f"remote mkdir failed: {se.strip()[:200]}")
        sys.exit(1)

    # ── 3. scp PARAM 업로드 (atomic via .tmp) ────────────────────────────────
    remote_tmp = f"{remote_dir}/latest_runtime_param.json.tmp"
    remote_final = f"{remote_dir}/latest_runtime_param.json"
    logger.info("[scp] %s → %s:%s", _LATEST_PATH, args.ssh_target, remote_tmp)
    rc, so, se = _run(
        ["scp", str(_LATEST_PATH), f"{args.ssh_target}:{remote_tmp}"], timeout=60
    )
    if rc != 0:
        logger.error("scp 실패: %s", se.strip())
        status_record["upload_status"] = "failed"
        _finish("failed", f"scp failed: {se.strip()[:200]}")
        sys.exit(1)
    rc, so, se = _run(
        ["ssh", args.ssh_target, f"mv {remote_tmp} {remote_final}"], timeout=30
    )
    if rc != 0:
        logger.error("atomic rename 실패: %s", se.strip())
        status_record["upload_status"] = "failed"
        _finish("failed", f"remote rename failed: {se.strip()[:200]}")
        sys.exit(1)
    status_record["upload_status"] = "ok"
    logger.info("[upload] PARAM OK → %s", remote_final)

    # ── 4. OCI verification ──────────────────────────────────────────────────
    if _VERIFY_SCRIPT_LOCAL.exists():
        verify_remote = "/tmp/verify_three_push_param_oci.py"
        logger.info(
            "[scp] %s → %s:%s", _VERIFY_SCRIPT_LOCAL, args.ssh_target, verify_remote
        )
        rc, so, se = _run(
            ["scp", str(_VERIFY_SCRIPT_LOCAL), f"{args.ssh_target}:{verify_remote}"],
            timeout=30,
        )
        if rc == 0:
            rc, so, se = _run(
                [
                    "ssh",
                    args.ssh_target,
                    f"python3 {verify_remote} --path {remote_final}",
                ],
                timeout=30,
            )
            if rc == 0:
                status_record["verify_status"] = "success"
                logger.info("[verify] OK")
            else:
                status_record["verify_status"] = "failed"
                logger.error("[verify] 실패: rc=%d stderr=%s", rc, se.strip()[:200])
                _finish(
                    "partial",
                    f"verify failed rc={rc} {se.strip()[:200]}",
                )
                sys.exit(1)
        else:
            status_record["verify_status"] = "skipped"
            logger.warning("verify script 업로드 실패 — 검증 skip")
    else:
        status_record["verify_status"] = "skipped"
        logger.warning("verify script 부재 — 검증 skip")

    _finish("success")
    logger.info("=== sync 완료: param_id=%s status=success ===", param.param_id)


if __name__ == "__main__":
    main()
