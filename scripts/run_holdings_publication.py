"""Holdings Evidence OCI Publication v1 — prepare / verify / activate CLI.

지시문 §5 · Q1 (b) 확정본:
- prepare: PC source 검증 + SHA-256/size/count 산출.
- verify:  OCI 임시 파일 검증 + PC expected 값과 비교.
- activate: TOCTOU 재검증 + mode 600 + owner + atomic replace + active 재검증.

계약 (Q2/Q6/Q7/Q8/Q11):
- 신규 validator 신설 X. `app.holdings.validate_holdings` 를 직접 재사용.
- holding_count = len(validate_holdings(raw)).
- verify/activate 는 `--expected-hash`, `--expected-size`, `--expected-count` 필수 인자.
- activate 직전 재검증 (TOCTOU 방지).
- mode 600 + owner 확인 통과해야 `active_file_permission_checked=true`.
- SCP 는 사용자가 별도 수행. CLI 는 SSH/SCP 미수행.

지시문 §9 원문 비노출:
- 종목명 · ticker · 수량 · 평단 · account_group · JSON 원문 stdout 미출력.
- SHA-256, size, count, mode, owner 등 정합성 근거만 출력.
"""

from __future__ import annotations

import argparse
import getpass
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

from app.holdings import (  # noqa: E402
    HOLDINGS_FILE as _DEFAULT_ACTIVE_PATH,
    HoldingsValidationError,
    validate_holdings,
)

# ── 유틸 ─────────────────────────────────────────────────────────────────────


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _hash_size(path: Path) -> tuple[str, int]:
    b = path.read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def _parse_and_validate(path: Path) -> tuple[bool, int, Optional[str]]:
    """returns (valid, holding_count, error_reason)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return False, 0, f"read_error:{type(e).__name__}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return False, 0, f"json_parse_error:{type(e).__name__}"
    if not isinstance(data, dict):
        return False, 0, "top_level_not_dict"
    raw = data.get("holdings")
    if raw is None:
        return False, 0, "missing_holdings_key"
    try:
        holdings = validate_holdings(raw)
    except HoldingsValidationError as e:
        return False, 0, f"holdings_validation_error:{str(e)[:200]}"
    return True, len(holdings), None


def _file_mode_owner(path: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """returns (mode_octal, owner_name, group_name).

    Windows 는 chown/chmod 개념이 POSIX 와 다르므로 mode 는 stat, owner 는 최선노력.
    OCI (POSIX) 에서 실제 정책 판정에 사용.
    """
    try:
        st = path.stat()
    except OSError:
        return None, None, None
    mode_octal = format(stat.S_IMODE(st.st_mode), "03o")
    owner_name: Optional[str] = None
    group_name: Optional[str] = None
    try:
        import pwd  # POSIX only.

        owner_name = pwd.getpwuid(st.st_uid).pw_name
    except (ImportError, KeyError):
        pass
    try:
        import grp  # POSIX only.

        group_name = grp.getgrgid(st.st_gid).gr_name
    except (ImportError, KeyError):
        pass
    return mode_octal, owner_name, group_name


def _apply_mode_600(path: Path) -> Optional[str]:
    """chmod 600. returns error reason or None."""
    try:
        os.chmod(path, 0o600)
    except OSError as e:
        return f"chmod_error:{type(e).__name__}"
    return None


def _current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return ""


# ── prepare ──────────────────────────────────────────────────────────────────


def cmd_prepare(args: argparse.Namespace) -> int:
    source = Path(args.source or _DEFAULT_ACTIVE_PATH)
    out: dict[str, Any] = {
        "command": "prepare",
        "status": "failed",
        "source_exists": False,
        "source_valid": False,
        "source_hash": "",
        "source_size": 0,
        "source_holding_count": 0,
        "error_reason": "",
    }
    if not source.exists():
        out["error_reason"] = "source_not_found"
        _emit(out)
        return 2
    out["source_exists"] = True
    valid, hc, err = _parse_and_validate(source)
    if not valid:
        out["error_reason"] = err or "invalid_holdings"
        _emit(out)
        return 2
    sha, size = _hash_size(source)
    out.update(
        {
            "status": "ok",
            "source_valid": True,
            "source_hash": sha,
            "source_size": size,
            "source_holding_count": hc,
        }
    )
    _emit(out)
    return 0


# ── verify ───────────────────────────────────────────────────────────────────


def cmd_verify(args: argparse.Namespace) -> int:
    tmp = Path(args.temp)
    out: dict[str, Any] = {
        "command": "verify",
        "status": "failed",
        "destination_temp_received": False,
        "destination_valid": False,
        "destination_hash": "",
        "destination_size": 0,
        "destination_holding_count": 0,
        "hash_match": False,
        "size_match": False,
        "holding_count_match": False,
        "activation_ready": False,
        "error_reason": "",
    }
    if not tmp.exists():
        out["error_reason"] = "temp_not_found"
        _emit(out)
        return 2
    out["destination_temp_received"] = True
    valid, hc, err = _parse_and_validate(tmp)
    if not valid:
        out["error_reason"] = err or "invalid_holdings"
        _emit(out)
        return 2
    sha, size = _hash_size(tmp)
    out.update(
        {
            "destination_valid": True,
            "destination_hash": sha,
            "destination_size": size,
            "destination_holding_count": hc,
            "hash_match": sha == args.expected_hash,
            "size_match": size == args.expected_size,
            "holding_count_match": hc == args.expected_count,
        }
    )
    activation_ready = (
        out["hash_match"] and out["size_match"] and out["holding_count_match"]
    )
    out["activation_ready"] = activation_ready
    if not activation_ready:
        out["error_reason"] = "mismatch:" + ",".join(
            k
            for k, v in {
                "hash": out["hash_match"],
                "size": out["size_match"],
                "count": out["holding_count_match"],
            }.items()
            if not v
        )
        _emit(out)
        return 3
    # Optional: mode/owner 정보 참고용 (권한 변경은 activate 에서).
    mode, owner, group = _file_mode_owner(tmp)
    out["temp_mode"] = mode
    out["temp_owner"] = owner
    out["temp_group"] = group
    out["status"] = "ok"
    _emit(out)
    return 0


# ── activate ─────────────────────────────────────────────────────────────────


def cmd_activate(args: argparse.Namespace) -> int:
    tmp = Path(args.temp)
    active = Path(args.active or _DEFAULT_ACTIVE_PATH)
    out: dict[str, Any] = {
        "command": "activate",
        "status": "failed",
        "final_validation_passed": False,
        "atomic_activation_completed": False,
        "active_file_exists": False,
        "active_hash": "",
        "active_size": 0,
        "active_holding_count": 0,
        "active_file_mode": "",
        "active_file_owner": "",
        "active_file_permission_checked": False,
        "error_reason": "",
    }
    if not tmp.exists():
        out["error_reason"] = "temp_not_found"
        _emit(out)
        return 2
    # 동일 디렉터리 확인 (원자적 replace 조건).
    if tmp.parent.resolve() != active.parent.resolve():
        out["error_reason"] = "temp_and_active_directory_mismatch"
        _emit(out)
        return 2

    # TOCTOU 방지: activate 직전 재검증.
    valid, hc, err = _parse_and_validate(tmp)
    if not valid:
        out["error_reason"] = f"final_validation_failed:{err}"
        _emit(out)
        return 3
    sha, size = _hash_size(tmp)
    if (
        sha != args.expected_hash
        or size != args.expected_size
        or hc != args.expected_count
    ):
        mismatches = []
        if sha != args.expected_hash:
            mismatches.append("hash")
        if size != args.expected_size:
            mismatches.append("size")
        if hc != args.expected_count:
            mismatches.append("count")
        out["error_reason"] = "final_validation_mismatch:" + ",".join(mismatches)
        _emit(out)
        return 3
    out["final_validation_passed"] = True

    # mode 600 적용 및 owner 확인 (임시 파일에 먼저).
    chmod_err = _apply_mode_600(tmp)
    if chmod_err is not None:
        # Windows 등에서는 chmod 가 완전 반영 안 될 수 있음. 실행 계정 및 mode 재확인.
        pass
    tmp_mode, tmp_owner, _ = _file_mode_owner(tmp)
    exec_user = _current_user()
    if tmp_owner is not None and exec_user and tmp_owner != exec_user:
        out["error_reason"] = (
            f"temp_owner_mismatch:owner={tmp_owner!r} exec_user={exec_user!r}"
        )
        _emit(out)
        return 4

    # 원자적 replace (POSIX rename 은 atomic).
    try:
        os.replace(str(tmp), str(active))
    except OSError as e:
        out["error_reason"] = f"replace_error:{type(e).__name__}"
        _emit(out)
        return 5
    out["atomic_activation_completed"] = True
    out["active_file_exists"] = active.exists()

    # active 파일 재검증.
    valid2, hc2, err2 = _parse_and_validate(active)
    if not valid2 or hc2 != args.expected_count:
        out["error_reason"] = f"post_replace_validation_failed:{err2 or 'count'}"
        _emit(out)
        return 6
    sha2, size2 = _hash_size(active)
    out.update(
        {
            "active_hash": sha2,
            "active_size": size2,
            "active_holding_count": hc2,
        }
    )
    if sha2 != args.expected_hash or size2 != args.expected_size:
        out["error_reason"] = "post_replace_hash_or_size_mismatch"
        _emit(out)
        return 6

    # active 파일 권한 재확인.
    a_mode, a_owner, a_group = _file_mode_owner(active)
    out["active_file_mode"] = a_mode or ""
    out["active_file_owner"] = a_owner or ""
    permission_ok = a_mode == "600" and (
        not a_owner or not exec_user or a_owner == exec_user
    )
    out["active_file_permission_checked"] = permission_ok
    if not permission_ok:
        # active 파일에 재적용 시도 (안전망).
        chmod_err2 = _apply_mode_600(active)
        a_mode2, a_owner2, _ = _file_mode_owner(active)
        out["active_file_mode"] = a_mode2 or ""
        out["active_file_owner"] = a_owner2 or ""
        out["active_file_permission_checked"] = (
            a_mode2 == "600"
            and (not a_owner2 or not exec_user or a_owner2 == exec_user)
            and chmod_err2 is None
        )
        if not out["active_file_permission_checked"]:
            out["error_reason"] = (
                f"active_permission_not_met:mode={a_mode2!r} owner={a_owner2!r}"
            )
            _emit(out)
            return 7

    out["status"] = "ok"
    _emit(out)
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Holdings Evidence OCI Publication v1 CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser("prepare", help="PC source 검증 + SHA/size/count 산출")
    p_prepare.add_argument("--source", default=None)
    p_prepare.set_defaults(func=cmd_prepare)

    p_verify = sub.add_parser("verify", help="OCI 임시 파일 검증 + expected 값 비교")
    p_verify.add_argument("--temp", required=True)
    p_verify.add_argument("--expected-hash", required=True, dest="expected_hash")
    p_verify.add_argument(
        "--expected-size", required=True, type=int, dest="expected_size"
    )
    p_verify.add_argument(
        "--expected-count", required=True, type=int, dest="expected_count"
    )
    p_verify.set_defaults(func=cmd_verify)

    p_activate = sub.add_parser(
        "activate",
        help="임시 파일 재검증 + mode 600 + atomic replace + active 재검증",
    )
    p_activate.add_argument("--temp", required=True)
    p_activate.add_argument("--active", default=None)
    p_activate.add_argument("--expected-hash", required=True, dest="expected_hash")
    p_activate.add_argument(
        "--expected-size", required=True, type=int, dest="expected_size"
    )
    p_activate.add_argument(
        "--expected-count", required=True, type=int, dest="expected_count"
    )
    p_activate.set_defaults(func=cmd_activate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
