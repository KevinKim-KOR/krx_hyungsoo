"""PC-to-OCI 3-PUSH Evidence Package OCI Read Verification.

OCI 에서 직접 실행되는 standalone 스크립트.
sync_three_push_packages.py 가 SCP 로 /tmp 에 복사 후 python3 로 호출한다.

실행:
    python3 /tmp/verify_three_push_packages_oci.py --remote-dir /path/to/packages

출력:
    JSON 단일 라인 (stdout) — sync_three_push_packages.py 가 파싱.

검증 범위 (지시문 §11):
    - manifest 존재 여부
    - manifest schema_version 확인
    - push_kind 3종 존재 확인
    - package 파일 3종 존재 확인
    - 각 package schema_version = three_push_runtime_package.v1
    - 각 package push_kind 가 manifest key 와 일치
    - generation_status 가 ok/partial/failed 중 하나
    - token / chat_id 가 package 또는 manifest 에 미포함

이 스크립트는 stdlib 만 사용한다 — OCI 에 추가 패키지 설치 불필요.
Telegram 발송 / DB 접근 / 외부 source 호출 0건.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# ── 상수 ──────────────────────────────────────────────────────────────────────
EXPECTED_PACKAGE_SCHEMA = "three_push_runtime_package.v1"
EXPECTED_MANIFEST_SCHEMA = "three_push_package_manifest.v1"
PUSH_KINDS = ("market_briefing", "holdings_briefing", "spike_or_falling_alert")
PACKAGE_FILENAMES = {
    "market_briefing": "latest_market_briefing.json",
    "holdings_briefing": "latest_holdings_briefing.json",
    "spike_or_falling_alert": "latest_spike_or_falling_alert.json",
}
MANIFEST_FILENAME = "manifest.json"

FORBIDDEN_KEYS = frozenset(
    {"token", "chat_id", "bot_token", "telegram_token", "telegram_chat_id"}
)
ALLOWED_GEN_STATUS = frozenset({"ok", "partial", "failed"})


# ── 유틸 ──────────────────────────────────────────────────────────────────────


def _find_sensitive_keys(obj: Any, path: str = "root") -> list[str]:
    """token/chat_id 금지 키 발견 시 경로 목록 반환."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_KEYS:
                found.append(f"{path}.{k}")
            found.extend(_find_sensitive_keys(v, path=f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_sensitive_keys(item, path=f"{path}[{i}]"))
    return found


def _read_json(path: str) -> tuple[Any, str | None]:
    """파일을 읽어 JSON 파싱. 실패 시 (None, 오류문자열)."""
    if not os.path.isfile(path):
        return None, f"파일 없음: {path}"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"읽기/파싱 실패 ({path}): {e}"


# ── 검증 로직 ─────────────────────────────────────────────────────────────────


def verify(remote_dir: str) -> dict[str, Any]:
    """remote_dir 에서 manifest + package 3종 검증.

    반환:
    {
      "status": "success" | "partial" | "failed",
      "checks": { ... },
      "errors": [...],
      "warnings": [...],
    }
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    # 1) manifest 존재 + 파싱
    manifest_path = os.path.join(remote_dir, MANIFEST_FILENAME)
    manifest, err = _read_json(manifest_path)
    if err:
        errors.append(f"[manifest] {err}")
        checks["manifest_exists"] = False
        return {
            "status": "failed",
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
        }
    checks["manifest_exists"] = True

    # 2) manifest schema_version
    manifest_sv = manifest.get("schema_version") if isinstance(manifest, dict) else None
    if manifest_sv != EXPECTED_MANIFEST_SCHEMA:
        errors.append(
            f"[manifest] schema_version 불일치: expected={EXPECTED_MANIFEST_SCHEMA!r}, "
            f"got={manifest_sv!r}"
        )
        checks["manifest_schema_version"] = False
    else:
        checks["manifest_schema_version"] = True

    # 3) manifest token/chat_id 비노출
    sensitive_in_manifest = _find_sensitive_keys(manifest, path="manifest")
    if sensitive_in_manifest:
        errors.append(f"[manifest] token/chat_id 발견: {sensitive_in_manifest}")
        checks["manifest_no_token"] = False
    else:
        checks["manifest_no_token"] = True

    # 4) manifest packages 키 3종 확인
    manifest_packages = (
        manifest.get("packages") if isinstance(manifest, dict) else {}
    ) or {}
    for push_kind in PUSH_KINDS:
        if push_kind not in manifest_packages:
            errors.append(f"[manifest] push_kind 누락: {push_kind}")
            checks[f"manifest_has_{push_kind}"] = False
        else:
            checks[f"manifest_has_{push_kind}"] = True

    # 5) package 파일 3종 각각 검증
    package_checks: dict[str, dict[str, Any]] = {}
    for push_kind in PUSH_KINDS:
        filename = PACKAGE_FILENAMES[push_kind]
        pkg_path = os.path.join(remote_dir, filename)
        pkg, err = _read_json(pkg_path)
        pc: dict[str, Any] = {}

        if err:
            errors.append(f"[{push_kind}] {err}")
            pc["file_exists"] = False
            package_checks[push_kind] = pc
            continue
        pc["file_exists"] = True

        if not isinstance(pkg, dict):
            errors.append(f"[{push_kind}] 파일이 dict 가 아님")
            pc["valid_dict"] = False
            package_checks[push_kind] = pc
            continue
        pc["valid_dict"] = True

        # schema_version
        pkg_sv = pkg.get("schema_version")
        if pkg_sv != EXPECTED_PACKAGE_SCHEMA:
            errors.append(
                f"[{push_kind}] schema_version 불일치: "
                f"expected={EXPECTED_PACKAGE_SCHEMA!r}, got={pkg_sv!r}"
            )
            pc["schema_version_ok"] = False
        else:
            pc["schema_version_ok"] = True

        # push_kind 일치
        pkg_kind = pkg.get("push_kind")
        if pkg_kind != push_kind:
            errors.append(
                f"[{push_kind}] push_kind 불일치: "
                f"expected={push_kind!r}, got={pkg_kind!r}"
            )
            pc["push_kind_matches"] = False
        else:
            pc["push_kind_matches"] = True

        # manifest key 와 일치
        manifest_entry = manifest_packages.get(push_kind, {})
        manifest_pkg_id = (
            manifest_entry.get("package_id", "")
            if isinstance(manifest_entry, dict)
            else ""
        )
        pkg_id = pkg.get("package_id", "")
        if manifest_pkg_id and pkg_id != manifest_pkg_id:
            warnings.append(
                f"[{push_kind}] package_id manifest 불일치: "
                f"manifest={manifest_pkg_id!r}, file={pkg_id!r}"
            )
            pc["package_id_matches_manifest"] = False
        else:
            pc["package_id_matches_manifest"] = True

        # generation_status
        gs = pkg.get("generation_status") or {}
        gen_status = gs.get("status") if isinstance(gs, dict) else None
        if gen_status not in ALLOWED_GEN_STATUS:
            errors.append(
                f"[{push_kind}] generation_status.status 이상: {gen_status!r} "
                f"(ok/partial/failed 만 허용)"
            )
            pc["generation_status_valid"] = False
        else:
            pc["generation_status_valid"] = True
            pc["generation_status"] = gen_status

        # token/chat_id 비노출
        sensitive = _find_sensitive_keys(pkg, path=f"package[{push_kind}]")
        if sensitive:
            errors.append(f"[{push_kind}] token/chat_id 발견: {sensitive}")
            pc["no_token"] = False
        else:
            pc["no_token"] = True

        package_checks[push_kind] = pc

    checks["packages"] = package_checks

    # ── 최종 판정 ────────────────────────────────────────────────────────────
    if errors:
        # 파일이 하나도 없는 경우 vs 일부 실패
        files_ok = sum(1 for pc in package_checks.values() if pc.get("file_exists"))
        overall = "failed" if files_ok == 0 else "partial"
    else:
        overall = "success"

    return {
        "status": overall,
        "remote_dir": remote_dir,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


# ── 메인 ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCI three_push package read verification"
    )
    parser.add_argument(
        "--remote-dir",
        required=True,
        help="OCI 측 packages 경로 (예: ~/krx-alertor/state/three_push/packages)",
    )
    args = parser.parse_args()

    remote_dir = os.path.expanduser(args.remote_dir)
    result = verify(remote_dir)

    # stdout 에 JSON 한 줄 출력 (호출자가 파싱)
    print(json.dumps(result, ensure_ascii=False))

    if result["status"] == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
