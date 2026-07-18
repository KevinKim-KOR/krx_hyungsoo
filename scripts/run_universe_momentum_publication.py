"""Universe Momentum artifact controlled publication CLI (지시문 §16~§19).

subcommand:
  prepare      — PC canonical artifact 사전 검증 (sanitized JSON stdout).
  verify       — OCI 임시 파일 검증 (expected 값 비교).
  activate     — activate 직전 재검증 + atomic replace + active 재검증.

SSH/SCP 는 CLI 에서 수행하지 않는다. 사용자가 PC→OCI 전송.

Holdings publication 과 schema 통합 X · 범용 framework 신설 X (§16).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Canonical 경로 (기존 producer 계약 유지).
DEFAULT_SOURCE = Path("state/universe/universe_momentum_latest.json")
DEFAULT_ACTIVE = Path("state/universe/universe_momentum_latest.json")

# 검증자 REJECTED r4 재정정: expected owner 는 **오직 소스 코드 상수** (§20).
# CLI 인자 · 환경 변수 · 어떤 외부 override 도 완전 금지. Test 는 monkeypatch 로
# `_EXPECTED_OWNER_CONST` 상수 자체를 대체해서만 격리 (env 우회 경로 제거).
_EXPECTED_OWNER_CONST = "ubuntu"


def _resolve_expected_owner() -> str:
    """expected owner = 소스 상수 `ubuntu`. 어떤 외부 override 도 없음."""
    return _EXPECTED_OWNER_CONST


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _size_of(path: Path) -> int:
    return path.stat().st_size


def _validate_artifact_dict(data: Any) -> tuple[bool, Optional[str], dict[str, Any]]:
    """공통 validator 위임 (B-6 중복 제거).

    검증자 REJECTED r2 재정정: Publication 과 Runtime 이 동일 계약을 공유.
    refresh_status allowlist · candidate shape · asof 등 단일 소스.
    """
    from app.universe_bootstrap.artifact_validator import validate_artifact

    return validate_artifact(data)


def _load_json(path: Path) -> tuple[Optional[Any], Optional[str]]:
    """(data, error_reason)."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text), None
    except FileNotFoundError:
        return None, "file_not_found"
    except json.JSONDecodeError as e:
        return None, f"json_parse_error:{type(e).__name__}"
    except OSError as e:
        return None, f"io_error:{type(e).__name__}"


def _file_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))[2:]


def _file_owner(path: Path) -> str:
    try:
        import pwd  # type: ignore

        return pwd.getpwuid(path.stat().st_uid).pw_name
    except Exception:  # noqa: BLE001
        # Windows 등 pwd 미지원: uid 만 반환.
        try:
            return str(path.stat().st_uid)
        except Exception:  # noqa: BLE001
            return ""


def _file_group(path: Path) -> str:
    try:
        import grp  # type: ignore

        return grp.getgrgid(path.stat().st_gid).gr_name
    except Exception:  # noqa: BLE001
        try:
            return str(path.stat().st_gid)
        except Exception:  # noqa: BLE001
            return ""


def _current_user() -> Optional[str]:
    try:
        import getpass

        u = getpass.getuser()
        return u or None
    except Exception:  # noqa: BLE001
        return None


# ── prepare (PC) ──────────────────────────────────────────────────────────────


def _cmd_prepare(args) -> int:
    source = Path(args.source) if args.source else DEFAULT_SOURCE
    out: dict[str, Any] = {
        "command": "prepare",
        "status": "failed",
        "source_exists": False,
        "source_valid": False,
        "source_artifact_status": "",
        "source_asof": "",
        "source_candidate_count": 0,
        "source_hash": "",
        "source_size": 0,
        "publishable": False,
        "error_reason": "",
    }
    if not source.exists():
        out["error_reason"] = "source_file_missing"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    out["source_exists"] = True
    data, err = _load_json(source)
    if err:
        out["error_reason"] = err
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    valid, reason, meta = _validate_artifact_dict(data)
    out["source_artifact_status"] = meta["status"]
    out["source_asof"] = meta["asof"]
    out["source_candidate_count"] = meta["candidate_count"]
    if not valid:
        out["error_reason"] = reason or "validation_failed"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    out["source_valid"] = True
    out["source_hash"] = _sha256_of(source)
    out["source_size"] = _size_of(source)
    out["publishable"] = True
    out["status"] = "ok"
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


# ── verify (OCI) ──────────────────────────────────────────────────────────────


def _cmd_verify(args) -> int:
    temp = Path(args.temp)
    out: dict[str, Any] = {
        "command": "verify",
        "status": "failed",
        "destination_temp_received": False,
        "destination_valid": False,
        "destination_artifact_status": "",
        "destination_asof": "",
        "destination_candidate_count": 0,
        "destination_hash": "",
        "destination_size": 0,
        "hash_match": False,
        "size_match": False,
        "asof_match": False,
        "candidate_count_match": False,
        "mode_match": False,
        "owner_match": False,
        "activation_ready": False,
        "temp_mode": "",
        "temp_owner": "",
        "temp_group": "",
        "error_reason": "",
    }
    if not temp.exists():
        out["error_reason"] = "temp_file_missing"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    out["destination_temp_received"] = True
    out["temp_mode"] = _file_mode(temp)
    out["temp_owner"] = _file_owner(temp)
    out["temp_group"] = _file_group(temp)
    data, err = _load_json(temp)
    if err:
        out["error_reason"] = err
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    valid, reason, meta = _validate_artifact_dict(data)
    out["destination_artifact_status"] = meta["status"]
    out["destination_asof"] = meta["asof"]
    out["destination_candidate_count"] = meta["candidate_count"]
    if not valid:
        out["error_reason"] = reason or "validation_failed"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    out["destination_valid"] = True
    out["destination_hash"] = _sha256_of(temp)
    out["destination_size"] = _size_of(temp)
    out["hash_match"] = out["destination_hash"] == args.expected_hash
    out["size_match"] = out["destination_size"] == args.expected_size
    out["asof_match"] = out["destination_asof"] == args.expected_asof
    out["candidate_count_match"] = (
        out["destination_candidate_count"] == args.expected_count
    )
    # 검증자 REJECTED r6 재정정: mode / owner 도 activation_ready 판정에 포함.
    # §18 "하나라도 불일치하면 activation_ready=false" 계약. temp 파일이 mode 600
    # + owner=_EXPECTED_OWNER_CONST 가 아니면 이후 activate 단계에서 확실히 실패.
    expected_owner = _resolve_expected_owner()
    out["mode_match"] = out["temp_mode"] == "600"
    out["owner_match"] = out["temp_owner"] == expected_owner
    out["activation_ready"] = all(
        [
            out["hash_match"],
            out["size_match"],
            out["asof_match"],
            out["candidate_count_match"],
            out["mode_match"],
            out["owner_match"],
        ]
    )
    out["status"] = "ok" if out["activation_ready"] else "failed"
    if not out["activation_ready"]:
        # 우선순위: expected 값 mismatch → mode/owner mismatch.
        if not out["hash_match"]:
            out["error_reason"] = "expected_hash_mismatch"
        elif not out["size_match"]:
            out["error_reason"] = "expected_size_mismatch"
        elif not out["asof_match"]:
            out["error_reason"] = "expected_asof_mismatch"
        elif not out["candidate_count_match"]:
            out["error_reason"] = "expected_count_mismatch"
        elif not out["mode_match"]:
            out["error_reason"] = (
                f"temp_mode_mismatch:temp={out['temp_mode']},expected=600"
            )
        else:
            out["error_reason"] = (
                f"temp_owner_mismatch:temp={out['temp_owner']},expected={expected_owner}"
            )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["activation_ready"] else 3


# ── activate (OCI) ────────────────────────────────────────────────────────────


def _cmd_activate(args) -> int:
    temp = Path(args.temp)
    active = Path(args.active) if args.active else DEFAULT_ACTIVE
    out: dict[str, Any] = {
        "command": "activate",
        "status": "failed",
        "final_validation_passed": False,
        "atomic_activation_completed": False,
        "active_file_exists": False,
        "active_artifact_status": "",
        "active_asof": "",
        "active_candidate_count": 0,
        "active_hash": "",
        "active_size": 0,
        "active_file_mode": "",
        "active_file_owner": "",
        "active_file_permission_checked": False,
        "error_reason": "",
    }
    if not temp.exists():
        out["error_reason"] = "temp_file_missing"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    if temp.parent.resolve() != active.parent.resolve():
        out["error_reason"] = "temp_and_active_in_different_directories"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    data, err = _load_json(temp)
    if err:
        out["error_reason"] = err
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    valid, reason, meta = _validate_artifact_dict(data)
    if not valid:
        out["error_reason"] = reason or "validation_failed"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    # activate 직전 재검증 (§19).
    if _sha256_of(temp) != args.expected_hash:
        out["error_reason"] = "expected_hash_mismatch"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    if _size_of(temp) != args.expected_size:
        out["error_reason"] = "expected_size_mismatch"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    if meta["asof"] != args.expected_asof:
        out["error_reason"] = "expected_asof_mismatch"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    if meta["candidate_count"] != args.expected_count:
        out["error_reason"] = "expected_count_mismatch"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    # 권한 확인 · 적용 (§20: mode 600, owner ubuntu 고정).
    # 검증자 REJECTED r4 재정정: owner 는 **소스 코드 상수 `_EXPECTED_OWNER_CONST`**
    # 만으로 결정. CLI 인자 · 환경 변수 · argparse namespace 어떤 외부 override 도
    # 없음. Test 는 monkeypatch 로 상수 자체를 대체해서만 격리한다.
    exec_user = _current_user()
    if exec_user is None:
        out["error_reason"] = "current_user_unavailable"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    expected_owner = _resolve_expected_owner()
    if exec_user != expected_owner:
        # activation 계정이 expected owner 와 다름 → 임의 chown X, PARTIAL 로 중단.
        out["error_reason"] = (
            f"exec_user_not_expected_owner:exec={exec_user},expected={expected_owner}"
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    try:
        os.chmod(temp, 0o600)
    except OSError as e:
        out["error_reason"] = f"chmod_failed:{type(e).__name__}"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    tmp_owner = _file_owner(temp)
    if not tmp_owner or tmp_owner != expected_owner:
        out["error_reason"] = (
            f"temp_owner_mismatch:tmp={tmp_owner},expected={expected_owner}"
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    out["final_validation_passed"] = True
    # atomic replace.
    try:
        os.replace(temp, active)
    except OSError as e:
        out["error_reason"] = f"replace_failed:{type(e).__name__}"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    out["atomic_activation_completed"] = True
    # active 재검증.
    out["active_file_exists"] = active.exists()
    if not out["active_file_exists"]:
        out["error_reason"] = "active_file_missing_after_replace"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    a_data, a_err = _load_json(active)
    if a_err:
        out["error_reason"] = a_err
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    a_valid, a_reason, a_meta = _validate_artifact_dict(a_data)
    if not a_valid:
        out["error_reason"] = a_reason or "post_activation_validation_failed"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 4
    out["active_artifact_status"] = a_meta["status"]
    out["active_asof"] = a_meta["asof"]
    out["active_candidate_count"] = a_meta["candidate_count"]
    out["active_hash"] = _sha256_of(active)
    out["active_size"] = _size_of(active)
    out["active_file_mode"] = _file_mode(active)
    out["active_file_owner"] = _file_owner(active)
    out["active_file_permission_checked"] = (
        out["active_file_mode"] == "600" and out["active_file_owner"] == expected_owner
    )
    out["status"] = "ok" if out["active_file_permission_checked"] else "failed"
    if not out["active_file_permission_checked"]:
        out["error_reason"] = (
            f"active_permission_mismatch:mode={out['active_file_mode']},"
            f"owner={out['active_file_owner']}"
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["status"] == "ok" else 4


def _parse_args(argv: Optional[list[str]] = None):
    p = argparse.ArgumentParser(
        prog="run_universe_momentum_publication",
        description="Universe Momentum artifact controlled publication (prepare/verify/activate).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp_p = sub.add_parser("prepare", help="PC: source artifact 사전 검증.")
    sp_p.add_argument(
        "--source", default=None, help="artifact 경로 (default: canonical)."
    )

    sp_v = sub.add_parser("verify", help="OCI: 임시 파일 검증 + expected 값 비교.")
    sp_v.add_argument("--temp", required=True)
    sp_v.add_argument("--expected-hash", required=True, dest="expected_hash")
    sp_v.add_argument("--expected-size", required=True, type=int, dest="expected_size")
    sp_v.add_argument("--expected-asof", required=True, dest="expected_asof")
    sp_v.add_argument(
        "--expected-count", required=True, type=int, dest="expected_count"
    )

    sp_a = sub.add_parser(
        "activate", help="OCI: activate 직전 재검증 + atomic replace."
    )
    sp_a.add_argument("--temp", required=True)
    sp_a.add_argument("--active", default=None)
    sp_a.add_argument("--expected-hash", required=True, dest="expected_hash")
    sp_a.add_argument("--expected-size", required=True, type=int, dest="expected_size")
    sp_a.add_argument("--expected-asof", required=True, dest="expected_asof")
    sp_a.add_argument(
        "--expected-count", required=True, type=int, dest="expected_count"
    )
    # 검증자 REJECTED r3 재정정: expected owner CLI 인자 완전 제거.
    # owner 는 소스 코드 상수 (§20). 운영 CLI 로는 override 불가.

    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    if args.command == "prepare":
        return _cmd_prepare(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "activate":
        return _cmd_activate(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
