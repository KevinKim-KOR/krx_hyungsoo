"""OCI 3-PUSH Runner 헬퍼 — 상수·설정·guard·I/O 로직.

run_three_push_oci.py 의 flow control 은 이 모듈을 import 해서 사용한다.
직접 실행 불가.
"""

from __future__ import annotations

import json
import logging
import os
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

# PUSH 사용자 표현 정리 STEP (2026-06-20, 지시문 §4.1):
# Telegram 본문에 절대 노출되면 안 되는 raw 기술 식별자. PC builder 가 사용자 중심
# 메시지를 생성하지만, OCI runner 단에서도 이중 차단으로 보호한다.
_FORBIDDEN_RAW_IDENTIFIERS = (
    "param_id",
    "param_source",
    "manual_seed",
    "kr_realtime_price_snapshot",
    "overnight_us_market_snapshot",
    "market_discovery_snapshot",
    "holdings_snapshot",
    "nav_discount_snapshot",
    "universe_momentum_snapshot",
    "ml_baseline_v0",
    "news_snapshot",
)

# ── 로깅 ─────────────────────────────────────────────────────────────────────


def setup_logging(push_kind: str) -> logging.Logger:
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


def env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def env_bool(key: str) -> bool:
    return env(key, "").strip().lower() == "true"


def package_dir() -> Path:
    explicit = env("THREE_PUSH_PACKAGE_DIR")
    if explicit:
        return Path(explicit)
    return _DEFAULT_PACKAGE_DIR


# ── secret 비노출 가드 ────────────────────────────────────────────────────────


def assert_no_sensitive_keys(obj: Any, path: str = "root") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in _FORBIDDEN_SECRET_KEYS:
                raise RuntimeError(f"token/chat_id 금지 키 발견: path={path}.{k}")
            assert_no_sensitive_keys(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            assert_no_sensitive_keys(item, path=f"{path}[{i}]")


# ── manifest / package load ───────────────────────────────────────────────────


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 파싱 실패: {path} — {e}") from e


def load_manifest(pkg_dir: Path) -> dict[str, Any]:
    manifest = load_json(pkg_dir / "manifest.json")
    sv = manifest.get("schema_version")
    if sv != _MANIFEST_SCHEMA:
        raise RuntimeError(
            f"manifest schema_version 불일치: expected={_MANIFEST_SCHEMA!r}, got={sv!r}"
        )
    assert_no_sensitive_keys(manifest, path="manifest")
    return manifest


_VALID_GEN_STATUSES = frozenset({"ok", "partial", "failed"})


def load_package(
    pkg_dir: Path, push_kind: str, manifest: dict[str, Any]
) -> dict[str, Any]:
    # manifest.packages.{push_kind}.path 를 우선 사용, fallback 으로 고정 파일명
    manifest_pkg_meta = manifest.get("packages", {}).get(push_kind, {})
    manifest_path = manifest_pkg_meta.get("path", "")
    filename = manifest_path if manifest_path else _PACKAGE_FILES[push_kind]
    package = load_json(pkg_dir / filename)
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
    assert_no_sensitive_keys(package, path=f"package[{push_kind}]")
    return package


# ── message_text 추출 ─────────────────────────────────────────────────────────


def extract_message_text(package: dict[str, Any], push_kind: str) -> str:
    mc = package.get("message_contract")
    if not isinstance(mc, dict):
        raise RuntimeError(f"message_contract 없음: push_kind={push_kind}")
    text = mc.get("message_text", "")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"message_text 비어있음: push_kind={push_kind}")
    return text


# ── 금지 문구 검사 ────────────────────────────────────────────────────────────


def check_forbidden_wording(text: str) -> Optional[str]:
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in text:
            return phrase
    return None


def check_raw_identifiers(text: str) -> Optional[str]:
    """Telegram 본문에 raw 기술 식별자 노출 차단 (지시문 §4.1, AC-1).

    PC builder 가 사용자 중심 메시지를 생성하지만, OCI runner 가 이중 차단으로
    보호한다. 감지 시 발송 차단.
    """
    for ident in _FORBIDDEN_RAW_IDENTIFIERS:
        if ident in text:
            return ident
    return None


# ── 최신성 guard ──────────────────────────────────────────────────────────────


def parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Python 3.7+ fromisoformat는 Z를 처리하지 못하므로 대체
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except Exception:
        return None


def check_staleness(
    package: dict[str, Any], push_kind: str, manifest: dict[str, Any]
) -> Optional[str]:
    max_hours = int(env("THREE_PUSH_MAX_PACKAGE_AGE_HOURS", "36") or "36")
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
        dt = parse_iso(ts_raw)
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


def registry_key(push_kind: str, package_id: str) -> str:
    return f"{push_kind}::{package_id}"


def load_registry() -> dict[str, Any]:
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


def save_registry(reg: dict[str, Any]) -> None:
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_REGISTRY_PATH)


def is_already_sent(push_kind: str, package_id: str) -> bool:
    if not package_id:
        return False
    reg = load_registry()
    return registry_key(push_kind, package_id) in reg


def mark_sent(push_kind: str, package_id: str, sent_at: str) -> None:
    reg = load_registry()
    reg[registry_key(push_kind, package_id)] = {
        "push_kind": push_kind,
        "package_id": package_id,
        "sent_at": sent_at,
    }
    save_registry(reg)


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


def write_status(record: dict[str, Any]) -> None:
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_STATUS_PATH)

    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
