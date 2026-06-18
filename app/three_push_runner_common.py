"""three_push runner 공통 헬퍼.

scripts/run_three_push_oci.py (package fallback runner) 와
scripts/run_three_push_runtime_oci.py (PARAM runtime runner) 가 공유한다.

이 모듈에 포함되는 것:
  - .env stdlib 로더 (load_dotenv_file)
  - env helper (env / env_bool)
  - secret 비노출 검사 (assert_no_sensitive_keys)
  - forbidden wording 검사 (check_forbidden_wording)
  - Telegram 발송 (telegram_send) — token/chat_id 마스킹 포함
  - 중복 발송 registry (load_registry / save_registry / mark_sent / is_already_sent)
  - status / history 기록 (write_status)
  - 표준 push_kind 상수 + push_kind별 enable flag env 매핑

이 모듈에 포함되지 않는 것:
  - package load / manifest 검증 → scripts/run_three_push_oci.py 전용
  - PARAM load / PARAM message build → app/three_push_runtime_param.py /
    app/three_push_runtime_message_builder.py / scripts/run_three_push_runtime_oci.py 전용
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

# ── 경로 ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STATE_DIR = PROJECT_ROOT / "state" / "three_push"
LOG_DIR = PROJECT_ROOT / "logs"


# ── 표준 push_kind 상수 ──────────────────────────────────────────────────────

VALID_PUSH_KINDS = ("market_briefing", "holdings_briefing", "spike_or_falling_alert")

PUSH_KIND_FLAG_ENVS = {
    "market_briefing": "PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED",
    "holdings_briefing": "PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED",
    "spike_or_falling_alert": "PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED",
}


# ── 금지 문구 (tests/test_three_push_contract.py 와 동일) ────────────────────

FORBIDDEN_PHRASES = [
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
    "매수 지시",
    "매도 지시",
    "교체 지시",
    "비중 조절 지시",
    "현금 비중 조절",
    "위험 threshold 확정",
]

FORBIDDEN_SECRET_KEYS = frozenset(
    {"token", "chat_id", "bot_token", "telegram_token", "telegram_chat_id"}
)


# ── .env 로더 ────────────────────────────────────────────────────────────────


def load_dotenv_file() -> None:
    """프로젝트 루트 .env 를 stdlib 만으로 로드.

    OS 환경변수가 이미 설정돼 있으면 덮어쓰지 않는다 (override=False 동작).
    crontab / SSH 비로그인 셸에서 .env 없이 실행될 때도 안전하게 skip.
    """
    env_path = PROJECT_ROOT / ".env"
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
        print(f"[warn] .env 로드 실패: {exc}", file=sys.stderr)


# ── env 헬퍼 ─────────────────────────────────────────────────────────────────


def env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def env_bool(key: str) -> bool:
    return env(key, "").strip().lower() == "true"


# ── 로깅 ─────────────────────────────────────────────────────────────────────


def setup_logging(
    name: str, log_filename: str = "three_push_cron.log"
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_DIR / log_filename, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


# ── secret 비노출 가드 ────────────────────────────────────────────────────────


def assert_no_sensitive_keys(obj: Any, path: str = "root") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_SECRET_KEYS:
                raise RuntimeError(f"token/chat_id 금지 키 발견: path={path}.{k}")
            assert_no_sensitive_keys(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            assert_no_sensitive_keys(item, path=f"{path}[{i}]")


# ── 금지 문구 검사 ────────────────────────────────────────────────────────────


def check_forbidden_wording(text: str) -> Optional[str]:
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            return phrase
    return None


# ── Telegram 발송 ─────────────────────────────────────────────────────────────


def telegram_send(text: str) -> tuple[bool, Optional[str]]:
    """Telegram Bot API 로 메시지 발송.

    token/chat_id 는 환경변수에서만 읽고 로그/status 에 출력하지 않는다.
    반환: (성공 여부, 에러 요약 또는 None)
    """
    token = env("TELEGRAM_BOT_TOKEN")
    chat_id = env("TELEGRAM_CHAT_ID")
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
            return (
                False,
                "malformed_telegram_api_url: HTTP 404 — bot token 형식 오류 또는 API URL 잘못됨",
            )
        if e.code == 401:
            return False, "invalid_or_placeholder_bot_token: HTTP 401 — token 인증 실패"
        return False, f"other_non_secret_error: HTTP {e.code}"
    except Exception as e:
        msg = str(e)
        if token and token in msg:
            msg = msg.replace(token, "***TOKEN***")
        if chat_id and chat_id in msg:
            msg = msg.replace(chat_id, "***CHAT_ID***")
        return False, f"other_non_secret_error: {msg[:200]}"


# ── 중복 발송 registry ───────────────────────────────────────────────────────


def load_registry(registry_path: Path) -> dict[str, Any]:
    """registry 를 dict 로 로드. 손상 시 RuntimeError — 발송 차단 의도."""
    if not registry_path.exists():
        return {}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(
                f"registry 형식 오류: dict 가 아님 (got {type(data).__name__})"
            )
        return data
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"registry 손상 — 안전을 위해 발송 차단: {e}") from e


def save_registry(registry_path: Path, registry: dict[str, Any]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = registry_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(registry_path)


def is_already_sent(registry_path: Path, key: str) -> bool:
    if not key:
        return False
    registry = load_registry(registry_path)
    return key in registry


def mark_sent(registry_path: Path, key: str, entry: dict[str, Any]) -> None:
    registry = load_registry(registry_path)
    registry[key] = entry
    save_registry(registry_path, registry)


# ── status / history ─────────────────────────────────────────────────────────


def write_status(status_path: Path, history_path: Path, record: dict[str, Any]) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = status_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(status_path)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
