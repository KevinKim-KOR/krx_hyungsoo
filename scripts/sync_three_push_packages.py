"""PC-to-OCI 3-PUSH Evidence Package Sync — 실행 스크립트.

실행:
    python scripts/sync_three_push_packages.py [--dry-run] [--export-only]

옵션:
    --dry-run      : package 생성 + OCI 업로드 시뮬레이션 (실제 SCP 없음)
    --export-only  : package 생성 + local 저장만 수행 (OCI 업로드 없음)

환경변수 (필수 — OCI 업로드 시):
    OCI_SSH_TARGET              : ubuntu@<host> 또는 ~/.ssh/config alias
    OCI_REMOTE_INBOX 또는
    THREE_PUSH_REMOTE_PACKAGE_DIR : OCI 측 three_push/packages 경로

환경변수 (선택):
    OCI_SSH_KEY_PATH            : SSH 개인키 절대경로

sync 결과는 state/three_push/sync_status_latest.json 에 기록된다.

이번 Step 범위 (지시문 §5.1):
- PC local package artifact 생성
- push_kind 별 latest package 3종 저장
- manifest.json 생성
- SCP 기반 OCI 업로드 (atomic)
- OCI read verification (scripts/verify_three_push_packages_oci.py 호출)
- sync status 기록

이번 Step 에서 하지 않는 것 (지시문 §5.2):
- OCI crontab runner / crontab 등록
- Telegram send
- scheduler
- SQLite OCI 이전 / 신규 DB
"""

from __future__ import annotations

import argparse
import json
import logging
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path 에 추가 (스크립트 직접 실행 지원).
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import EnvConfigError, optional_env, require_env  # noqa: E402
from app.three_push_package_exporter import (  # noqa: E402
    LOCAL_PACKAGE_DIR,
    MANIFEST_FILENAME,
    PUSH_KINDS,
    _PACKAGE_FILENAMES,
    run_export,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sync_three_push")

# ── sync status 경로 ──────────────────────────────────────────────────────────
SYNC_STATUS_DIR = _PROJECT_ROOT / "state" / "three_push"
SYNC_STATUS_FILE = SYNC_STATUS_DIR / "sync_status_latest.json"

# ── SCP / SSH 설정 ────────────────────────────────────────────────────────────
SCP_TIMEOUT_SEC = 30
SSH_TIMEOUT_SEC = 15


def _ssh_target() -> str:
    return require_env("OCI_SSH_TARGET")


def _remote_package_dir() -> str:
    """THREE_PUSH_REMOTE_PACKAGE_DIR 우선, 없으면 OCI_REMOTE_INBOX 기반 구성."""
    explicit = optional_env("THREE_PUSH_REMOTE_PACKAGE_DIR", default=None)
    if explicit:
        return explicit
    inbox = optional_env("OCI_REMOTE_INBOX", default=None)
    if inbox:
        # OCI_REMOTE_INBOX 가 poc1_inbox 형태라면 sibling 경로로 추론.
        base = inbox.rstrip("/").rsplit("/", 1)[0]
        return f"{base}/three_push/packages"
    raise EnvConfigError(
        "THREE_PUSH_REMOTE_PACKAGE_DIR 또는 OCI_REMOTE_INBOX 가 설정되지 않았습니다."
    )


def _ssh_key_opts() -> list[str]:
    key_path = optional_env("OCI_SSH_KEY_PATH", default=None)
    if not key_path:
        return []
    return ["-i", key_path, "-o", "IdentitiesOnly=yes"]


def _scp_upload(local_path: Path, remote_uri: str, dry_run: bool = False) -> None:
    """scp 단일 파일 업로드. dry_run 시 명령어만 출력."""
    cmd = [
        "scp",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SCP_TIMEOUT_SEC}",
        *_ssh_key_opts(),
        str(local_path),
        remote_uri,
    ]
    if dry_run:
        logger.info("[dry-run] scp: %s", " ".join(cmd))
        return
    logger.info("[scp] %s → %s", local_path.name, remote_uri)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SCP_TIMEOUT_SEC + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"scp timeout: {e}")
    except FileNotFoundError as e:
        raise RuntimeError(f"scp 실행 파일 미발견: {e}")
    if result.returncode != 0:
        raise RuntimeError(
            f"scp 실패 (exit {result.returncode}): "
            f"stdout={result.stdout.strip()!r} stderr={result.stderr.strip()!r}"
        )


def _ssh_run(target: str, command: str, dry_run: bool = False) -> str:
    """SSH 원격 명령 실행. dry_run 시 명령어만 출력 후 빈 문자열 반환."""
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SSH_TIMEOUT_SEC}",
        *_ssh_key_opts(),
        target,
        command,
    ]
    if dry_run:
        logger.info("[dry-run] ssh: %s", " ".join(cmd))
        return ""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SSH_TIMEOUT_SEC + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ssh timeout: {e}")
    except FileNotFoundError as e:
        raise RuntimeError(f"ssh 실행 파일 미발견: {e}")
    if result.returncode != 0:
        raise RuntimeError(
            f"ssh 실패 (exit {result.returncode}): " f"stderr={result.stderr.strip()!r}"
        )
    return result.stdout


# ── OCI remote directory 생성 ─────────────────────────────────────────────────


def _ensure_remote_dir(target: str, remote_dir: str, dry_run: bool) -> None:
    quoted = shlex.quote(remote_dir)
    _ssh_run(target, f"mkdir -p {quoted}", dry_run=dry_run)


# ── atomic OCI 업로드 ──────────────────────────────────────────────────────────


def upload_packages_to_oci(
    target: str,
    remote_dir: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """package 3종을 tmp → rename atomic 으로 업로드.

    반환: {push_kind: "ok" | "failed", ...}
    """
    _ensure_remote_dir(target, remote_dir, dry_run)
    results: dict[str, str] = {}

    for push_kind in PUSH_KINDS:
        filename = _PACKAGE_FILENAMES[push_kind]
        local_path = LOCAL_PACKAGE_DIR / filename
        if not local_path.exists():
            logger.warning("[upload] %s 로컬 파일 없음: %s", push_kind, local_path)
            results[push_kind] = "failed"
            continue
        tmp_remote = f"{remote_dir}/{filename}.tmp"
        final_remote = f"{remote_dir}/{filename}"
        try:
            # 1) tmp 로 업로드
            _scp_upload(local_path, f"{target}:{tmp_remote}", dry_run=dry_run)
            # 2) rename → 최종 파일명 (atomic)
            quoted_tmp = shlex.quote(tmp_remote)
            quoted_final = shlex.quote(final_remote)
            _ssh_run(target, f"mv {quoted_tmp} {quoted_final}", dry_run=dry_run)
            results[push_kind] = "ok"
            logger.info("[upload] %s OK → %s", push_kind, final_remote)
        except RuntimeError as e:
            logger.error("[upload] %s 실패: %s", push_kind, e)
            results[push_kind] = "failed"

    return results


def upload_manifest_to_oci(
    target: str,
    remote_dir: str,
    dry_run: bool = False,
) -> str:
    """manifest.json 을 마지막에 atomic 업로드."""
    local_path = LOCAL_PACKAGE_DIR / MANIFEST_FILENAME
    if not local_path.exists():
        logger.error("[upload] manifest 로컬 파일 없음: %s", local_path)
        return "failed"
    tmp_remote = f"{remote_dir}/{MANIFEST_FILENAME}.tmp"
    final_remote = f"{remote_dir}/{MANIFEST_FILENAME}"
    try:
        _scp_upload(local_path, f"{target}:{tmp_remote}", dry_run=dry_run)
        quoted_tmp = shlex.quote(tmp_remote)
        quoted_final = shlex.quote(final_remote)
        _ssh_run(target, f"mv {quoted_tmp} {quoted_final}", dry_run=dry_run)
        logger.info("[upload] manifest OK → %s", final_remote)
        return "ok"
    except RuntimeError as e:
        logger.error("[upload] manifest 실패: %s", e)
        return "failed"


# ── OCI read verification 호출 ────────────────────────────────────────────────


def run_oci_read_verification(
    target: str,
    remote_dir: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """OCI 에 verify 스크립트를 업로드하고 원격 실행 → 결과 반환.

    scripts/verify_three_push_packages_oci.py 를 OCI 의 /tmp 에 복사 후
    python3 로 실행하고 JSON 출력을 파싱한다.
    """
    verify_script = _SCRIPT_DIR / "verify_three_push_packages_oci.py"
    if not verify_script.exists():
        logger.warning("[verify] verify 스크립트 없음: %s", verify_script)
        return {"status": "skipped", "reason": "verify script not found"}

    remote_script = "/tmp/verify_three_push_packages_oci.py"

    if dry_run:
        logger.info(
            "[dry-run] verify: scp %s → %s:%s", verify_script, target, remote_script
        )
        logger.info(
            "[dry-run] verify: ssh %s python3 %s --remote-dir %s",
            target,
            remote_script,
            remote_dir,
        )
        return {"status": "dry_run", "skipped": True}

    # 1) 스크립트 업로드
    try:
        _scp_upload(verify_script, f"{target}:{remote_script}", dry_run=False)
    except RuntimeError as e:
        logger.error("[verify] 스크립트 업로드 실패: %s", e)
        return {"status": "failed", "reason": f"script upload failed: {e}"}

    # 2) 원격 실행
    quoted_dir = shlex.quote(remote_dir)
    quoted_script = shlex.quote(remote_script)
    cmd = f"python3 {quoted_script} --remote-dir {quoted_dir}"
    try:
        output = _ssh_run(target, cmd, dry_run=False)
    except RuntimeError as e:
        logger.error("[verify] 원격 실행 실패: %s", e)
        return {"status": "failed", "reason": f"remote execution failed: {e}"}

    # 3) JSON 파싱
    try:
        result = json.loads(output.strip())
        logger.info(
            "[verify] OCI read verification 완료: status=%s", result.get("status")
        )
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("[verify] JSON 파싱 실패: %s — output=%r", e, output[:500])
        return {
            "status": "failed",
            "reason": f"JSON parse error: {e}",
            "raw": output[:500],
        }


# ── sync status 기록 ──────────────────────────────────────────────────────────


def _write_sync_status(status: dict[str, Any]) -> None:
    SYNC_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("[status] sync status saved → %s", SYNC_STATUS_FILE)


# ── 타입 임포트 (Any) ─────────────────────────────────────────────────────────
from typing import Any  # noqa: E402

# ── 메인 ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PC-to-OCI 3-PUSH Evidence Package Sync"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="package 생성 + OCI 업로드 시뮬레이션 (실제 SCP 없음)",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="package 생성 + local 저장만 (OCI 업로드 없음)",
    )
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== 3-PUSH Evidence Package Sync 시작 ===")

    # ── 1단계: package 3종 + manifest local 생성 ─────────────────────────────
    logger.info("[step 1] package 3종 + manifest 생성 중...")
    try:
        export_info = run_export()
    except Exception as e:
        logger.error("[step 1] export 전체 실패: %s", e)
        _write_sync_status(
            {
                "status": "failed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "step": "export",
            }
        )
        sys.exit(1)

    export_status = export_info.get("status", "failed")
    export_errors = export_info.get("export_result", {}).get("errors", {})
    logger.info(
        "[step 1] 완료: status=%s, errors=%s", export_status, list(export_errors.keys())
    )

    if args.export_only:
        logger.info("[export-only] OCI 업로드 건너뜀.")
        _write_sync_status(
            {
                "status": export_status,
                "mode": "export_only",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "export": export_info,
                "oci_upload": None,
                "oci_verification": None,
            }
        )
        logger.info("=== export-only 완료 ===")
        return

    # ── 2단계: OCI 환경변수 확인 ─────────────────────────────────────────────
    try:
        oci_target = _ssh_target()
        remote_dir = _remote_package_dir()
    except EnvConfigError as e:
        logger.error("[step 2] OCI 환경변수 미설정: %s", e)
        _write_sync_status(
            {
                "status": "failed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "export": export_info,
                "oci_upload": None,
                "oci_verification": None,
                "error": str(e),
                "step": "oci_env",
            }
        )
        sys.exit(1)

    logger.info("[step 2] OCI 타겟: %s → %s", oci_target, remote_dir)

    # ── 3단계: package 3종 업로드 (atomic) ───────────────────────────────────
    logger.info("[step 3] package 3종 OCI 업로드 중...")
    upload_results = upload_packages_to_oci(
        oci_target, remote_dir, dry_run=args.dry_run
    )
    upload_ok_count = sum(1 for v in upload_results.values() if v == "ok")
    logger.info("[step 3] 업로드 결과: %s", upload_results)

    # ── 4단계: manifest 마지막에 업로드 ──────────────────────────────────────
    logger.info("[step 4] manifest OCI 업로드 (마지막)...")
    manifest_upload_status = upload_manifest_to_oci(
        oci_target, remote_dir, dry_run=args.dry_run
    )

    # ── 5단계: OCI read verification ─────────────────────────────────────────
    logger.info("[step 5] OCI read verification 실행...")
    verify_result = run_oci_read_verification(
        oci_target, remote_dir, dry_run=args.dry_run
    )
    verify_status = verify_result.get("status", "failed")

    # ── 최종 status 산정 ─────────────────────────────────────────────────────
    if args.dry_run:
        # dry_run 은 실제 업로드/검증이 없으므로 success 로 기록하지 않는다.
        overall = "dry_run"
    else:
        all_uploaded = (upload_ok_count == len(PUSH_KINDS)) and (
            manifest_upload_status == "ok"
        )
        if all_uploaded and verify_status in ("success", "ok"):
            overall = "success"
        elif upload_ok_count == 0:
            overall = "failed"
        else:
            overall = "partial"

    completed_at = datetime.now(timezone.utc).isoformat()
    sync_status = {
        "status": overall,
        "started_at": started_at,
        "completed_at": completed_at,
        "mode": "dry_run" if args.dry_run else "normal",
        "export": export_info,
        "oci_upload": {
            "target": oci_target,
            "remote_dir": remote_dir,
            "package_results": upload_results,
            "manifest_status": manifest_upload_status,
            "packages_ok": upload_ok_count,
            "atomic_upload_used": True,
            "manifest_uploaded_last": True,
        },
        "oci_verification": verify_result,
    }
    _write_sync_status(sync_status)

    logger.info(
        "=== sync 완료: status=%s (upload %d/3, manifest=%s, verify=%s) ===",
        overall,
        upload_ok_count,
        manifest_upload_status,
        verify_status,
    )

    if overall == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
