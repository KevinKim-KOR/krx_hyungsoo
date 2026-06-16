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
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── 경로 ─────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_PACKAGE_DIR = Path("/home/ubuntu/krx_hyungsoo/state/three_push/packages")


def _load_dotenv_file() -> None:
    """프로젝트 루트 .env 를 stdlib 만으로 로드 (python-dotenv 없이).

    OS 환경변수가 이미 설정돼 있으면 덮어쓰지 않는다 (override=False 동작).
    crontab / SSH 비로그인 셸에서 .env 없이 실행될 때도 안전하게 skip.
    """
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception as exc:
        import sys

        print(f"[warn] .env 로드 실패: {exc}", file=sys.stderr)


_load_dotenv_file()
_REGISTRY_PATH = _PROJECT_ROOT / "state" / "three_push" / "oci_sent_registry.json"
_STATUS_PATH = _PROJECT_ROOT / "state" / "three_push" / "oci_runner_status_latest.json"
_HISTORY_PATH = _PROJECT_ROOT / "state" / "three_push" / "oci_runner_history.jsonl"
_LOG_DIR = _PROJECT_ROOT / "logs"

_MANIFEST_SCHEMA = "three_push_package_manifest.v1"
_PACKAGE_SCHEMA = "three_push_runtime_package.v1"

VALID_PUSH_KINDS = ("market_briefing", "holdings_briefing", "spike_or_falling_alert")

_PACKAGE_FILES = {
    "market_briefing": "latest_market_briefing.json",
    "holdings_briefing": "latest_holdings_briefing.json",
    "spike_or_falling_alert": "latest_spike_or_falling_alert.json",
}

_PUSH_KIND_FLAG_ENVS = {
    "market_briefing": "PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED",
    "holdings_briefing": "PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED",
    "spike_or_falling_alert": "PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED",
}

# ── 금지 문구 (tests/test_three_push_contract.py PROHIBITED_WORDS 기준) ─────

_FORBIDDEN_PHRASES = [
    "매수 후보",
    "매도 후보",
    "지금 매수",
    "지금 매도",
    "매수해야",
    "매도해야",
    "교체 권유",
    "교체 필요",
    "현금비중 확대",
    "현금비중 조절",
    "조정장 확정",
    "상승장 확정",
    "단기 대응 필요",
    "위험 알림 확정",
    "지금 행동",
    "추천 종목",
    # §13 지시문 추가
    "매수 지시",
    "매도 지시",
    "교체 지시",
    "비중 조절 지시",
    "현금 비중 조절",
    "위험 threshold 확정",
]

_FORBIDDEN_SECRET_KEYS = frozenset(
    {"token", "chat_id", "bot_token", "telegram_token", "telegram_chat_id"}
)

# ── 로깅 ─────────────────────────────────────────────────────────────────────


def _setup_logging(push_kind: str) -> logging.Logger:
    logger = logging.getLogger(f"three_push_runner.{push_kind}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(_LOG_DIR / "three_push_cron.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


# ── env 헬퍼 ─────────────────────────────────────────────────────────────────


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def _env_bool(key: str) -> bool:
    return _env(key, "").strip().lower() == "true"


def _package_dir() -> Path:
    explicit = _env("THREE_PUSH_PACKAGE_DIR")
    if explicit:
        return Path(explicit)
    return _DEFAULT_PACKAGE_DIR


# ── secret 비노출 가드 ────────────────────────────────────────────────────────


def _assert_no_sensitive_keys(obj: Any, path: str = "root") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in _FORBIDDEN_SECRET_KEYS:
                raise RuntimeError(f"token/chat_id 금지 키 발견: path={path}.{k}")
            _assert_no_sensitive_keys(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_sensitive_keys(item, path=f"{path}[{i}]")


# ── manifest / package load ───────────────────────────────────────────────────


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 파싱 실패: {path} — {e}") from e


def _load_manifest(pkg_dir: Path) -> dict[str, Any]:
    manifest = _load_json(pkg_dir / "manifest.json")
    sv = manifest.get("schema_version")
    if sv != _MANIFEST_SCHEMA:
        raise RuntimeError(
            f"manifest schema_version 불일치: expected={_MANIFEST_SCHEMA!r}, got={sv!r}"
        )
    _assert_no_sensitive_keys(manifest, path="manifest")
    return manifest


_VALID_GEN_STATUSES = frozenset({"ok", "partial", "failed"})


def _load_package(
    pkg_dir: Path, push_kind: str, manifest: dict[str, Any]
) -> dict[str, Any]:
    # manifest.packages.{push_kind}.path 를 우선 사용, fallback 으로 고정 파일명
    manifest_pkg_meta = manifest.get("packages", {}).get(push_kind, {})
    manifest_path = manifest_pkg_meta.get("path", "")
    filename = manifest_path if manifest_path else _PACKAGE_FILES[push_kind]
    package = _load_json(pkg_dir / filename)
    sv = package.get("schema_version")
    if sv != _PACKAGE_SCHEMA:
        raise RuntimeError(
            f"package schema_version 불일치: push_kind={push_kind}, "
            f"expected={_PACKAGE_SCHEMA!r}, got={sv!r}"
        )
    pk = package.get("push_kind")
    if pk != push_kind:
        raise RuntimeError(f"push_kind 불일치: expected={push_kind!r}, got={pk!r}")
    # package_id 존재 검증
    if not package.get("package_id"):
        raise RuntimeError(f"package_id 없음: push_kind={push_kind}")
    # generation_status 허용값 검증
    gs = package.get("generation_status") or {}
    gen_status = gs.get("status")
    if gen_status not in _VALID_GEN_STATUSES:
        raise RuntimeError(
            f"generation_status.status 허용값 위반: push_kind={push_kind}, "
            f"got={gen_status!r} (허용: ok/partial/failed)"
        )
    _assert_no_sensitive_keys(package, path=f"package[{push_kind}]")
    return package


# ── message_text 추출 ─────────────────────────────────────────────────────────


def _extract_message_text(package: dict[str, Any], push_kind: str) -> str:
    mc = package.get("message_contract")
    if not isinstance(mc, dict):
        raise RuntimeError(f"message_contract 없음: push_kind={push_kind}")
    text = mc.get("message_text", "")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"message_text 비어있음: push_kind={push_kind}")
    return text


# ── 금지 문구 검사 ────────────────────────────────────────────────────────────


def _check_forbidden_wording(text: str) -> Optional[str]:
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in text:
            return phrase
    return None


# ── 최신성 guard ──────────────────────────────────────────────────────────────


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Python 3.7+ fromisoformat는 Z를 처리하지 못하므로 대체
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except Exception:
        return None


def _check_staleness(
    package: dict[str, Any], push_kind: str, manifest: dict[str, Any]
) -> Optional[str]:
    max_hours = int(_env("THREE_PUSH_MAX_PACKAGE_AGE_HOURS", "36") or "36")
    now = datetime.now(timezone.utc)

    # data_cutoff 는 dict 일 수 있으므로 str 타입만 후보로 사용
    data_cutoff_raw = package.get("data_cutoff")
    data_cutoff_str = data_cutoff_raw if isinstance(data_cutoff_raw, str) else None

    candidates = [
        ("manifest.generated_at", manifest.get("generated_at")),
        ("package.created_at", package.get("created_at")),
        ("package.asof_date", package.get("asof_date")),
        ("package.data_cutoff", data_cutoff_str),
    ]
    parsed_any = False
    for field, ts_raw in candidates:
        if not ts_raw or not isinstance(ts_raw, str):
            continue
        dt = _parse_iso(ts_raw)
        if dt is None:
            # 문자열인데 파싱 불가 → stale 로 간주
            return (
                f"stale_package: push_kind={push_kind}, "
                f"field={field!r} timestamp 파싱 불가 (ts={ts_raw!r})"
            )
        parsed_any = True
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (now - dt).total_seconds() / 3600
        if age_hours > max_hours:
            return (
                f"stale_package: push_kind={push_kind}, "
                f"age={age_hours:.1f}h > max={max_hours}h (ts={ts_raw!r})"
            )
    if not parsed_any:
        return (
            f"stale_package: push_kind={push_kind}, "
            "날짜 필드 없음 (manifest.generated_at/package.created_at/asof_date/data_cutoff)"
        )
    return None


# ── 중복 발송 방지 ────────────────────────────────────────────────────────────


def _registry_key(push_kind: str, package_id: str) -> str:
    return f"{push_kind}::{package_id}"


def _load_registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        return {}
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(
                f"registry 형식 오류: dict 가 아님 (got {type(data).__name__})"
            )
        return data
    except (json.JSONDecodeError, ValueError) as e:
        # 손상된 registry 는 {} 로 폴백하지 않는다 — duplicate guard 우회 위험.
        # RuntimeError 로 올려서 호출자가 send 를 차단하게 한다.
        raise RuntimeError(f"registry 손상 — 안전을 위해 발송 차단: {e}") from e


def _save_registry(registry: dict[str, Any]) -> None:
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_REGISTRY_PATH)


def _is_already_sent(push_kind: str, package_id: str) -> bool:
    if not package_id:
        return False
    registry = _load_registry()
    return _registry_key(push_kind, package_id) in registry


def _mark_sent(push_kind: str, package_id: str, sent_at: str) -> None:
    registry = _load_registry()
    registry[_registry_key(push_kind, package_id)] = {
        "push_kind": push_kind,
        "package_id": package_id,
        "sent_at": sent_at,
    }
    _save_registry(registry)


# ── Telegram 발송 ─────────────────────────────────────────────────────────────


def _telegram_send(text: str) -> tuple[bool, Optional[str]]:
    """Telegram Bot API 로 메시지 발송.

    token/chat_id 는 환경변수에서만 읽고 로그/status 에 출력하지 않는다.
    반환: (성공 여부, 에러 요약 또는 None)
    """
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token:
        return (
            False,
            "invalid_or_placeholder_bot_token: TELEGRAM_BOT_TOKEN 없음 (.env 또는 환경변수 미설정)",
        )
    if not chat_id:
        return (
            False,
            "invalid_or_placeholder_bot_token: TELEGRAM_CHAT_ID 없음 (.env 또는 환경변수 미설정)",
        )
    # placeholder 감지 (길이 기준 — 실제 token 은 최소 30자 이상)
    if len(token) < 20 or token in ("...", "your_token_here", "TOKEN"):
        return (
            False,
            "invalid_or_placeholder_bot_token: token 형식 이상 (너무 짧거나 placeholder)",
        )

    if str(token) in text or str(chat_id) in text:
        return False, "message_text 에 token/chat_id 노출 — 발송 차단"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            result = json.loads(body)
            if result.get("ok"):
                return True, None
            return False, f"Telegram API 오류: {result.get('description', 'unknown')}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 404:
            # URL 에 token 이 포함돼 있으므로 body 만 안전하게 노출
            return (
                False,
                "malformed_telegram_api_url: HTTP 404 — bot token 형식 오류 또는 API URL 잘못됨",
            )
        if e.code == 401:
            return False, "invalid_or_placeholder_bot_token: HTTP 401 — token 인증 실패"
        return False, f"other_non_secret_error: HTTP {e.code}"
    except Exception as e:
        # token 이 exception message 에 포함될 수 있어 안전하게 마스킹
        msg = str(e)
        if token and token in msg:
            msg = msg.replace(token, "***TOKEN***")
        if chat_id and chat_id in msg:
            msg = msg.replace(chat_id, "***CHAT_ID***")
        return False, f"other_non_secret_error: {msg[:200]}"


# ── status 기록 ───────────────────────────────────────────────────────────────


def _write_status(record: dict[str, Any]) -> None:
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_STATUS_PATH)

    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 메인 runner ───────────────────────────────────────────────────────────────


def run(push_kind: str, mode: str) -> dict[str, Any]:
    logger = _setup_logging(push_kind)
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
        _write_status(record)
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
    pkg_dir = _package_dir()
    try:
        manifest = _load_manifest(pkg_dir)
    except Exception as e:
        logger.error("manifest 로드 실패: %s", e)
        return _finish("failed", "manifest_load_error", str(e)[:400])

    if push_kind not in manifest.get("packages", {}):
        return _finish("failed", "push_kind_not_in_manifest")

    try:
        package = _load_package(pkg_dir, push_kind, manifest)
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
    # _load_package 에서 허용값(ok/partial/failed) 검증을 완료했으므로
    # 여기서는 failed 차단만 수행한다.
    gs = package.get("generation_status") or {}
    gen_status = gs.get("status", "failed")
    if gen_status == "failed":
        logger.warning("generation_status=failed — 발송 차단: push_kind=%s", push_kind)
        return _finish("skipped", "failed_generation_status")

    # ── 3. message_text 추출 ─────────────────────────────────────────────────
    try:
        message_text = _extract_message_text(package, push_kind)
    except Exception as e:
        logger.error("message_text 추출 실패: %s", e)
        return _finish("failed", "message_text_missing", str(e)[:400])

    record["message_text_length"] = len(message_text)

    # ── 4. 금지 문구 검사 ────────────────────────────────────────────────────
    bad_phrase = _check_forbidden_wording(message_text)
    if bad_phrase:
        logger.warning("금지 문구 감지: %r — 발송 차단", bad_phrase)
        return _finish("skipped", "forbidden_wording")

    # ── 5. token/chat_id 노출 검사 ───────────────────────────────────────────
    try:
        _assert_no_sensitive_keys(package, path=f"package[{push_kind}]")
    except RuntimeError as e:
        logger.error("secret 노출 감지: %s", e)
        return _finish("failed", "secret_exposed", str(e)[:400])

    # ── 6. dry-run: 여기까지가 끝 ────────────────────────────────────────────
    if mode == "dry-run":
        stale_msg = _check_staleness(package, push_kind, manifest)
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
    if not _env_bool("PUSH_AUTOSEND_ENABLED"):
        logger.info("PUSH_AUTOSEND_ENABLED=false — 발송 skip")
        return _finish("skipped", "autosend_disabled")

    kind_flag_env = _PUSH_KIND_FLAG_ENVS[push_kind]
    if not _env_bool(kind_flag_env):
        logger.info("%s=false — 발송 skip", kind_flag_env)
        return _finish("skipped", "push_kind_disabled")

    # ── 8. 최신성 guard ──────────────────────────────────────────────────────
    stale_msg = _check_staleness(package, push_kind, manifest)
    if stale_msg:
        logger.warning("stale package 차단: %s", stale_msg)
        return _finish("skipped", "stale_package", stale_msg[:400])

    # ── 9. 중복 발송 방지 ────────────────────────────────────────────────────
    try:
        already_sent = package_id and _is_already_sent(push_kind, package_id)
    except RuntimeError as e:
        # registry 손상 — duplicate guard 우회 위험이므로 발송 차단
        logger.error("registry 손상으로 발송 차단: %s", e)
        return _finish("failed", "registry_corrupted", str(e)[:400])
    if already_sent:
        logger.info("중복 발송 차단: push_kind=%s package_id=%s", push_kind, package_id)
        return _finish("skipped", "duplicate_package")

    # ── 10. Telegram 발송 ────────────────────────────────────────────────────
    record["telegram_attempted"] = True
    sent, err = _telegram_send(message_text)
    record["telegram_sent"] = sent

    if sent:
        sent_at = datetime.now(timezone.utc).isoformat()
        if package_id:
            _mark_sent(push_kind, package_id, sent_at)
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
