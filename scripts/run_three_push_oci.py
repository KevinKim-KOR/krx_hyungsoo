"""OCI 3-PUSH Crontab Runner — package 소비 + Telegram 자동 발송.

OCI 에서 crontab 으로 실행:
  python scripts/run_three_push_oci.py --push-kind market_briefing --mode dry-run
  python scripts/run_three_push_oci.py --push-kind holdings_briefing --mode send

이 스크립트가 하는 것:
- state/three_push/packages/ 에서 manifest + push_kind package 읽기
- schema / push_kind / generation_status / message_text 검증
- 최신성 guard (THREE_PUSH_MAX_PACKAGE_AGE_HOURS, 기본 36)
- 금지 문구 검사 (매수/매도/교체/비중조절 등)
- token/chat_id 비노출 검사
- 중복 발송 방지 (state/three_push/oci_sent_registry.json)
- enable flag guard (PUSH_AUTOSEND_ENABLED + push_kind 별)
- Telegram 발송 (send 모드 + 모든 조건 충족 시)
- 실행 결과 기록 (oci_runner_status_latest.json + oci_runner_history.jsonl + 로그)

이 스크립트가 하지 않는 것:
- PC package 생성 / OCI 업로드 (scripts/sync_three_push_packages.py 가 담당)
- 신규 DB / scheduler framework
- SQLite OCI 이전
- 매수/매도/비중조절 판단
- 조정장/위험 threshold 확정
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# 프로젝트 루트를 sys.path 에 추가 (스크립트 직접 실행 지원).
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT_FOR_PATH = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT_FOR_PATH) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_FOR_PATH))

from scripts.three_push_oci_helpers import (  # noqa: E402
    VALID_PUSH_KINDS,
    _PUSH_KIND_FLAG_ENVS,
    assert_no_sensitive_keys,
    check_forbidden_wording,
    check_raw_identifiers,
    check_staleness,
    env_bool,
    extract_message_text,
    is_already_sent,
    load_manifest,
    load_package,
    mark_sent,
    package_dir,
    setup_logging,
    telegram_send,
    write_status,
)


def run(push_kind: str, mode: str) -> dict[str, Any]:
    logger = setup_logging(push_kind)
    started_at = datetime.now(timezone.utc).isoformat()

    record: dict[str, Any] = {
        "push_kind": push_kind,
        "mode": mode,
        "status": "failed",
        "reason": None,
        "started_at": started_at,
        "finished_at": "",
        "package_id": "",
        "package_created_at": "",
        "package_asof_date": "",
        "message_text_length": 0,
        "telegram_attempted": False,
        "telegram_sent": False,
        "error": None,
    }

    def _finish(
        status: str, reason: Optional[str] = None, error: Optional[str] = None
    ) -> dict[str, Any]:
        record["status"] = status
        record["reason"] = reason
        record["error"] = error
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_status(record)
        logger.info(
            "runner 완료: push_kind=%s mode=%s status=%s reason=%s",
            push_kind,
            mode,
            status,
            reason,
        )
        return record

    logger.info("runner 시작: push_kind=%s mode=%s", push_kind, mode)

    # ── 1. package load ──────────────────────────────────────────────────────
    pkg_dir = package_dir()
    try:
        manifest = load_manifest(pkg_dir)
    except Exception as e:
        logger.error("manifest 로드 실패: %s", e)
        return _finish("failed", "manifest_load_error", str(e)[:400])

    if push_kind not in manifest.get("packages", {}):
        return _finish("failed", "push_kind_not_in_manifest")

    try:
        package = load_package(pkg_dir, push_kind, manifest)
    except Exception as e:
        logger.error("package 로드 실패: %s", e)
        return _finish("failed", "package_load_error", str(e)[:400])

    package_id = package.get("package_id", "")
    record["package_id"] = package_id
    record["package_created_at"] = package.get("created_at", "")
    record["package_asof_date"] = package.get("asof_date") or package.get(
        "data_cutoff", ""
    )

    # ── 2. generation_status 검증 ────────────────────────────────────────────
    # load_package 에서 허용값(ok/partial/failed) 검증을 완료했으므로
    # 여기서는 failed 차단만 수행한다.
    gs = package.get("generation_status") or {}
    gen_status = gs.get("status", "failed")
    if gen_status == "failed":
        logger.warning("generation_status=failed — 발송 차단: push_kind=%s", push_kind)
        return _finish("skipped", "failed_generation_status")

    # ── 3. message_text 추출 ─────────────────────────────────────────────────
    try:
        message_text = extract_message_text(package, push_kind)
    except Exception as e:
        logger.error("message_text 추출 실패: %s", e)
        return _finish("failed", "message_text_missing", str(e)[:400])

    record["message_text_length"] = len(message_text)

    # ── 4. 금지 문구 검사 ────────────────────────────────────────────────────
    bad_phrase = check_forbidden_wording(message_text)
    if bad_phrase:
        logger.warning("금지 문구 감지: %r — 발송 차단", bad_phrase)
        return _finish("skipped", "forbidden_wording")

    # ── 4-b. raw 기술 식별자 노출 차단 (지시문 §4.1, AC-1) ─────────────────
    raw_ident = check_raw_identifiers(message_text)
    if raw_ident:
        logger.warning(
            "raw 기술 식별자 감지: %r — 발송 차단 (사용자용 메시지 아님)", raw_ident
        )
        return _finish("skipped", "raw_identifier_exposed")

    # ── 5. token/chat_id 노출 검사 ───────────────────────────────────────────
    try:
        assert_no_sensitive_keys(package, path=f"package[{push_kind}]")
    except RuntimeError as e:
        logger.error("secret 노출 감지: %s", e)
        return _finish("failed", "secret_exposed", str(e)[:400])

    # ── 6. dry-run: 여기까지가 끝 ────────────────────────────────────────────
    if mode == "dry-run":
        stale_msg = check_staleness(package, push_kind, manifest)
        if stale_msg:
            logger.warning("dry-run stale 감지: %s", stale_msg)
            return _finish("dry_run_stale", "stale_package", stale_msg[:400])
        logger.info(
            "dry-run 검증 완료: push_kind=%s package_id=%s gen=%s msg_len=%d",
            push_kind,
            package_id,
            gen_status,
            len(message_text),
        )
        return _finish("dry_run_success")

    # ── 7. send 모드 — enable flag guard ─────────────────────────────────────
    if not env_bool("PUSH_AUTOSEND_ENABLED"):
        logger.info("PUSH_AUTOSEND_ENABLED=false — 발송 skip")
        return _finish("skipped", "autosend_disabled")

    kind_flag_env = _PUSH_KIND_FLAG_ENVS[push_kind]
    if not env_bool(kind_flag_env):
        logger.info("%s=false — 발송 skip", kind_flag_env)
        return _finish("skipped", "push_kind_disabled")

    # ── 8. 최신성 guard ──────────────────────────────────────────────────────
    stale_msg = check_staleness(package, push_kind, manifest)
    if stale_msg:
        logger.warning("stale package 차단: %s", stale_msg)
        return _finish("skipped", "stale_package", stale_msg[:400])

    # ── 9. 중복 발송 방지 ────────────────────────────────────────────────────
    try:
        already_sent = package_id and is_already_sent(push_kind, package_id)
    except RuntimeError as e:
        # registry 손상 — duplicate guard 우회 위험이므로 발송 차단
        logger.error("registry 손상으로 발송 차단: %s", e)
        return _finish("failed", "registry_corrupted", str(e)[:400])
    if already_sent:
        logger.info("중복 발송 차단: push_kind=%s package_id=%s", push_kind, package_id)
        return _finish("skipped", "duplicate_package")

    # ── 10. Telegram 발송 ────────────────────────────────────────────────────
    record["telegram_attempted"] = True
    sent, err = telegram_send(message_text)
    record["telegram_sent"] = sent

    if sent:
        sent_at = datetime.now(timezone.utc).isoformat()
        if package_id:
            mark_sent(push_kind, package_id, sent_at)
        final_status = "partial_sent" if gen_status == "partial" else "sent"
        return _finish(final_status)
    else:
        logger.error("Telegram 발송 실패: %s", err)
        return _finish("failed", "telegram_send_error", (err or "")[:400])


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OCI 3-PUSH Crontab Runner — package 소비 + Telegram 발송"
    )
    parser.add_argument(
        "--push-kind",
        required=True,
        choices=list(VALID_PUSH_KINDS),
        help="실행할 push_kind",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["dry-run", "send"],
        help="dry-run: 검증만 / send: Telegram 발송",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run(push_kind=args.push_kind, mode=args.mode)
    status = result.get("status", "failed")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status in ("sent", "dry_run_success", "partial_sent", "skipped"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
