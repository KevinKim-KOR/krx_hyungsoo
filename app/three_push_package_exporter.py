"""PC-to-OCI 3-PUSH Evidence Package Sync — package artifact export helper.

이번 Step 목표: PC 에서 생성된 three_push_runtime_package.v1 package 3종과
manifest 를 OCI 지정 경로로 동기화하는 경로의 첫 단계.

본 모듈 책임:
- push_kind 별 latest package artifact 를 state/three_push/packages/ 에 저장.
- manifest.json 생성 (push_kind 3종 포인터).
- token / chat_id 를 package / manifest 에 절대 넣지 않음.
- 기존 draft 생성 흐름 (draft_three_push / draft.py _build_holdings_payload)
  을 read-only 로 재사용 — 신규 source / 신규 endpoint 0건.

본 모듈은 절대 하지 않는 것:
- SCP / OCI 업로드 (scripts/sync_three_push_packages.py 가 담당).
- Telegram 발송.
- SQLite OCI 이전.
- 신규 DB / scheduler / 신규 external source.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 경로 상수 ────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_PACKAGE_DIR = _PROJECT_ROOT / "state" / "three_push" / "packages"

MANIFEST_SCHEMA_VERSION = "three_push_package_manifest.v1"

PUSH_KINDS = (
    "market_briefing",
    "holdings_briefing",
    "spike_or_falling_alert",
)

_PACKAGE_FILENAMES: dict[str, str] = {
    "market_briefing": "latest_market_briefing.json",
    "holdings_briefing": "latest_holdings_briefing.json",
    "spike_or_falling_alert": "latest_spike_or_falling_alert.json",
}

MANIFEST_FILENAME = "manifest.json"

# ── package 생성 ─────────────────────────────────────────────────────────────


def build_market_briefing_package() -> dict[str, Any]:
    """PUSH-1 runtime_package 생성 (기존 generic entry 재사용)."""
    from app.draft_three_push import generate_market_briefing_via_generic

    run = generate_market_briefing_via_generic({})
    rp = (run.draft_payload or {}).get("runtime_package")
    if not isinstance(rp, dict):
        raise RuntimeError(
            f"market_briefing runtime_package 생성 실패: run_id={run.run_id}"
        )
    return rp


def build_holdings_briefing_package() -> dict[str, Any]:
    """PUSH-2 runtime_package 생성 (기존 holdings 흐름 재사용).

    holdings 파일이 없으면 RuntimeError — 호출자가 처리.
    """
    import json as _json

    from app.draft import _build_holdings_payload
    from app.holdings import HOLDINGS_FILE, Holding

    if not HOLDINGS_FILE.exists():
        raise RuntimeError(f"holdings 파일 없음 (PUSH-2 생성 불가): {HOLDINGS_FILE}")
    raw = _json.loads(HOLDINGS_FILE.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("holdings", [])
    holdings = [Holding(**h) for h in items]
    if not holdings:
        raise RuntimeError("holdings 항목 0건 — PUSH-2 package 생성 불가")

    payload = _build_holdings_payload(holdings, market_quotes=None)
    rp = payload.get("runtime_package")
    if not isinstance(rp, dict):
        raise RuntimeError("holdings_briefing runtime_package 생성 실패")
    return rp


def build_spike_or_falling_alert_package() -> dict[str, Any]:
    """PUSH-3 runtime_package 생성 (기존 generic entry 재사용)."""
    from app.draft_three_push import generate_spike_alert_via_generic

    run = generate_spike_alert_via_generic({})
    rp = (run.draft_payload or {}).get("runtime_package")
    if not isinstance(rp, dict):
        raise RuntimeError(
            f"spike_or_falling_alert runtime_package 생성 실패: run_id={run.run_id}"
        )
    return rp


# ── token / chat_id 비노출 가드 ──────────────────────────────────────────────

_FORBIDDEN_KEYS = frozenset(
    {"token", "chat_id", "bot_token", "telegram_token", "telegram_chat_id"}
)


def _assert_no_sensitive_keys(obj: Any, path: str = "root") -> None:
    """package / manifest dict 에 token / chat_id 가 없는지 재귀 확인.

    발견 시 RuntimeError — package 파일에 secret 이 섞이지 않도록 차단.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in _FORBIDDEN_KEYS:
                raise RuntimeError(
                    f"token/chat_id 금지 키 발견: path={path}.{k} — "
                    "package / manifest 에 secret 포함 금지 (AC-7)"
                )
            _assert_no_sensitive_keys(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_sensitive_keys(item, path=f"{path}[{i}]")


# ── schema_version 검증 ───────────────────────────────────────────────────────

_EXPECTED_SCHEMA = "three_push_runtime_package.v1"


def _validate_package(package: dict[str, Any], push_kind: str) -> None:
    """schema_version / push_kind / generation_status 기본 검증."""
    sv = package.get("schema_version")
    if sv != _EXPECTED_SCHEMA:
        raise RuntimeError(
            f"schema_version 불일치: push_kind={push_kind}, "
            f"expected={_EXPECTED_SCHEMA!r}, got={sv!r}"
        )
    pk = package.get("push_kind")
    if pk != push_kind:
        raise RuntimeError(f"push_kind 불일치: expected={push_kind!r}, got={pk!r}")
    gs = package.get("generation_status") or {}
    status = gs.get("status")
    if status not in ("ok", "partial", "failed"):
        raise RuntimeError(
            f"generation_status.status 값 이상: push_kind={push_kind}, "
            f"status={status!r} (ok/partial/failed 만 허용)"
        )
    _assert_no_sensitive_keys(package, path=f"package[{push_kind}]")


# ── local artifact 저장 ───────────────────────────────────────────────────────


def _write_atomic(path: Path, content: str) -> None:
    """tmp 파일로 쓰고 rename — 읽는 쪽이 partial 파일을 보지 않도록."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def export_packages() -> dict[str, Any]:
    """push_kind 3종 package artifact 를 LOCAL_PACKAGE_DIR 에 저장.

    반환 dict:
    {
      "packages": {
        "market_briefing": {"path": ..., "package_id": ..., ...},
        ...
      },
      "generated_at": <iso>,
      "errors": {push_kind: str, ...},
    }

    errors 가 비어있으면 3종 모두 성공.
    개별 push_kind 실패는 errors 에 기록하고 나머지는 계속 진행.
    """
    LOCAL_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    packages: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}

    builders = {
        "market_briefing": build_market_briefing_package,
        "holdings_briefing": build_holdings_briefing_package,
        "spike_or_falling_alert": build_spike_or_falling_alert_package,
    }

    for push_kind, builder in builders.items():
        filename = _PACKAGE_FILENAMES[push_kind]
        target = LOCAL_PACKAGE_DIR / filename
        try:
            package = builder()
            _validate_package(package, push_kind)
            _write_atomic(target, json.dumps(package, ensure_ascii=False, indent=2))
            gs = package.get("generation_status") or {}
            packages[push_kind] = {
                "path": filename,
                "package_id": package.get("package_id", ""),
                "created_at": package.get("created_at", ""),
                "asof_date": package.get("asof_date", ""),
                "status": gs.get("status", "failed"),
            }
            logger.info("[exporter] %s package saved → %s", push_kind, target)
        except Exception as e:
            logger.error("[exporter] %s 생성 실패: %s", push_kind, e)
            errors[push_kind] = str(e)

    return {
        "packages": packages,
        "generated_at": generated_at,
        "errors": errors,
    }


# ── manifest 생성 ─────────────────────────────────────────────────────────────


def build_manifest(export_result: dict[str, Any]) -> dict[str, Any]:
    """export_result 를 바탕으로 manifest dict 를 생성.

    manifest 에는 token / chat_id 를 절대 넣지 않는다 (AC-7).
    """
    packages_meta = export_result.get("packages", {})
    generated_at = export_result.get(
        "generated_at", datetime.now(timezone.utc).isoformat()
    )

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": "pc",
        "packages": {},
    }

    for push_kind in PUSH_KINDS:
        meta = packages_meta.get(push_kind)
        if meta:
            manifest["packages"][push_kind] = {
                "path": meta["path"],
                "package_id": meta["package_id"],
                "created_at": meta["created_at"],
                "asof_date": meta["asof_date"],
                "status": meta["status"],
            }
        else:
            manifest["packages"][push_kind] = {
                "path": _PACKAGE_FILENAMES[push_kind],
                "package_id": "",
                "created_at": "",
                "asof_date": "",
                "status": "failed",
            }

    _assert_no_sensitive_keys(manifest, path="manifest")
    return manifest


def save_manifest(manifest: dict[str, Any]) -> Path:
    """manifest.json 을 LOCAL_PACKAGE_DIR 에 atomic 저장."""
    LOCAL_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    target = LOCAL_PACKAGE_DIR / MANIFEST_FILENAME
    _write_atomic(target, json.dumps(manifest, ensure_ascii=False, indent=2))
    logger.info("[exporter] manifest saved → %s", target)
    return target


# ── 일괄 실행 진입점 ──────────────────────────────────────────────────────────


def run_export() -> dict[str, Any]:
    """package 3종 생성 + manifest 저장 일괄 실행.

    반환 dict:
    {
      "export_result": {...},   # push_kind 별 package 생성 결과
      "manifest": {...},        # 저장된 manifest 내용
      "status": "success" | "partial" | "failed",
      "local_package_dir": str,
    }
    """
    export_result = export_packages()
    errors = export_result.get("errors", {})
    packages = export_result.get("packages", {})

    manifest = build_manifest(export_result)
    save_manifest(manifest)

    if not errors:
        overall = "success"
    elif len(errors) == len(PUSH_KINDS):
        overall = "failed"
    else:
        overall = "partial"

    logger.info(
        "[exporter] run_export 완료: status=%s, packages=%d/3, errors=%s",
        overall,
        len(packages),
        list(errors.keys()),
    )

    return {
        "export_result": export_result,
        "manifest": manifest,
        "status": overall,
        "local_package_dir": str(LOCAL_PACKAGE_DIR),
    }
