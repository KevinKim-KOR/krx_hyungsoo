"""OCI 3-PUSH **PARAM Runtime** Runner — 정식 운영 경로.

OCI 에서 crontab 으로 실행 (정식 운영 command):
  python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode dry-run
  python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send

이 스크립트가 하는 것:
  - state/three_push/params/latest_runtime_param.json 로드
  - PARAM schema_version 검증
  - PARAM enabled_push_kinds 확인
  - OCI runtime timestamp 기록
  - app.three_push_runtime_message_builder 로 runtime 메시지 생성
    (PC package message_text 를 그대로 사용하지 않음)
  - 금지 문구 검사 / token/chat_id 비노출 검사
  - duplicate guard (key = push_kind + param_id + KST 날짜)
  - enable flag guard (PUSH_AUTOSEND_ENABLED + push_kind별)
  - Telegram 발송 (send 모드 + 모든 조건 충족 시)
  - 실행 결과 기록 (state/three_push/oci_runtime_status_latest.json + history.jsonl)

이 스크립트가 하지 않는 것:
  - PC package message_text 정식 사용 (package 경로는 scripts/run_three_push_oci.py 가 fallback 으로 유지)
  - 외부 API 직접 호출 (Naver/Yahoo/뉴스 등)
  - 매수/매도/비중조절/조정장/위험 threshold 판단
  - 신규 DB / scheduler framework / ML 학습
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

# .env 자동 로드 (다른 import 가 환경변수를 읽기 전에 수행)
from app.three_push_runner_common import (  # noqa: E402
    PUSH_KIND_FLAG_ENVS,
    STATE_DIR,
    VALID_PUSH_KINDS,
    assert_no_sensitive_keys,
    check_forbidden_wording,
    env_bool,
    is_already_sent,
    load_dotenv_file,
    mark_sent,
    setup_logging,
    telegram_send,
    write_status,
)

load_dotenv_file()

from app.three_push_runtime_message_builder import (  # noqa: E402
    availability_summary,
    build_runtime_message,
    kst_now_iso,
    kst_today_date,
)
from app.three_push_runtime_param import read_param_file  # noqa: E402

# ── 경로 ─────────────────────────────────────────────────────────────────────

_PARAM_PATH = STATE_DIR / "params" / "latest_runtime_param.json"
_REGISTRY_PATH = STATE_DIR / "oci_runtime_sent_registry.json"
_STATUS_PATH = STATE_DIR / "oci_runtime_status_latest.json"
_HISTORY_PATH = STATE_DIR / "oci_runtime_history.jsonl"


# ── 메인 runner ───────────────────────────────────────────────────────────────


def _registry_key(push_kind: str, param_id: str, runtime_date_kst: str) -> str:
    return f"{push_kind}::{param_id}::{runtime_date_kst}"


def run(push_kind: str, mode: str) -> dict[str, Any]:
    logger = setup_logging(
        f"three_push_runtime_runner.{push_kind}",
        log_filename="three_push_runtime_cron.log",
    )
    started_at_utc = datetime.now(timezone.utc).isoformat()
    runtime_kst = kst_now_iso()
    runtime_date_kst = kst_today_date()

    record: dict[str, Any] = {
        "push_kind": push_kind,
        "mode": mode,
        "status": "failed",
        "reason": None,
        "started_at": started_at_utc,
        "finished_at": "",
        "runtime_kst": runtime_kst,
        "runtime_date_kst": runtime_date_kst,
        "param_id": "",
        "param_source": "",
        "message_text_length": 0,
        "availability": {},
        "duplicate_key": "",
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
        write_status(_STATUS_PATH, _HISTORY_PATH, record)
        logger.info(
            "runtime runner 완료: push_kind=%s mode=%s status=%s reason=%s",
            push_kind,
            mode,
            status,
            reason,
        )
        return record

    logger.info(
        "runtime runner 시작: push_kind=%s mode=%s runtime_kst=%s",
        push_kind,
        mode,
        runtime_kst,
    )

    # ── 1. latest PARAM 로드 ─────────────────────────────────────────────────
    if not _PARAM_PATH.exists():
        logger.error("latest PARAM 부재: %s", _PARAM_PATH)
        return _finish(
            "failed",
            "missing_latest_param",
            f"PARAM 파일이 없음: {_PARAM_PATH}",
        )
    try:
        param = read_param_file(_PARAM_PATH)
    except Exception as e:
        logger.error("PARAM 로드/검증 실패: %s", e)
        return _finish("failed", "param_load_error", str(e)[:400])

    record["param_id"] = param.param_id
    record["param_source"] = param.param_source

    # PARAM 자체에 secret 포함 여부 점검 (정책상 금지지만 방어적)
    try:
        assert_no_sensitive_keys(param.to_dict(), path="param")
    except RuntimeError as e:
        logger.error("PARAM secret 노출: %s", e)
        return _finish("failed", "param_secret_exposed", str(e)[:400])

    # ── 2. PARAM에서 push_kind 활성화 확인 ────────────────────────────────────
    if not param.is_push_kind_enabled(push_kind):
        logger.info(
            "PARAM enabled_push_kinds 미포함: push_kind=%s param_id=%s",
            push_kind,
            param.param_id,
        )
        return _finish("skipped", "push_kind_not_in_param")

    # ── 3. runtime message 생성 ──────────────────────────────────────────────
    # 본 빌더는 외부 API 호출하지 않으며, 모든 source 를 기본 unavailable 로 표시한다.
    # 향후 OCI에 실제 가용 source 가 추가되면 available_sources 인자로 전달한다.
    try:
        message_text = build_runtime_message(
            push_kind=push_kind,
            param=param,
            runtime_kst_iso=runtime_kst,
            available_sources=None,
        )
    except Exception as e:
        logger.error("runtime message 생성 실패: %s", e)
        return _finish("failed", "runtime_message_build_error", str(e)[:400])

    record["message_text_length"] = len(message_text)
    record["availability"] = availability_summary(None)

    # ── 4. 금지 문구 검사 ────────────────────────────────────────────────────
    bad = check_forbidden_wording(message_text)
    if bad:
        logger.warning("금지 문구 감지: %r — 발송 차단", bad)
        return _finish("failed", "forbidden_wording", f"phrase={bad}")

    # ── 5. dry-run 종료 ──────────────────────────────────────────────────────
    if mode == "dry-run":
        logger.info(
            "dry-run 완료: push_kind=%s param_id=%s msg_len=%d",
            push_kind,
            param.param_id,
            len(message_text),
        )
        return _finish("dry_run_success")

    # ── 6. enable flag guard ─────────────────────────────────────────────────
    if not env_bool("PUSH_AUTOSEND_ENABLED"):
        logger.info("PUSH_AUTOSEND_ENABLED=false — 발송 skip")
        return _finish("skipped", "autosend_disabled")

    kind_flag_env = PUSH_KIND_FLAG_ENVS[push_kind]
    if not env_bool(kind_flag_env):
        logger.info("%s=false — 발송 skip", kind_flag_env)
        return _finish("skipped", "push_kind_disabled")

    # ── 7. duplicate guard ───────────────────────────────────────────────────
    dup_key = _registry_key(push_kind, param.param_id, runtime_date_kst)
    record["duplicate_key"] = dup_key
    try:
        already = is_already_sent(_REGISTRY_PATH, dup_key)
    except RuntimeError as e:
        logger.error("registry 손상으로 발송 차단: %s", e)
        return _finish("failed", "registry_corrupted", str(e)[:400])
    if already:
        logger.info("중복 발송 차단: %s", dup_key)
        return _finish("skipped", "duplicate_runtime")

    # ── 8. Telegram 발송 ─────────────────────────────────────────────────────
    record["telegram_attempted"] = True
    sent, err = telegram_send(message_text)
    record["telegram_sent"] = sent

    if sent:
        sent_at = datetime.now(timezone.utc).isoformat()
        mark_sent(
            _REGISTRY_PATH,
            dup_key,
            {
                "push_kind": push_kind,
                "param_id": param.param_id,
                "runtime_date_kst": runtime_date_kst,
                "sent_at_utc": sent_at,
            },
        )
        return _finish("sent")
    else:
        logger.error("Telegram 발송 실패: %s", err)
        return _finish("failed", "telegram_send_error", (err or "")[:400])


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "OCI 3-PUSH PARAM Runtime Runner — latest PARAM snapshot 기반 "
            "runtime 메시지 생성 + Telegram 발송. "
            "PC-generated package message_text 를 정식 경로에서 사용하지 않는다."
        )
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
        help="dry-run: 검증/메시지 생성만 / send: Telegram 발송",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run(push_kind=args.push_kind, mode=args.mode)
    status = result.get("status", "failed")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status in ("sent", "dry_run_success", "skipped"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
