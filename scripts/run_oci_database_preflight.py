"""OCI Database Preflight v1 — read-only 환경 사전점검 CLI (2026-07-08).

지시문 §3 목표: PC · OCI 각각에서 현재 DB / runtime 관련 경로 / 기존 transfer
staging 실제 상태를 read-only 로 확인해 다음 DB 전환 STEP 진입 가능 여부만
확정한다.

절대 금지 (§4 · §6.2 · §6.5):
- SQLite write / schema · row 변경 / VACUUM · ANALYZE · REINDEX · wal_checkpoint
- JSON migration · 삭제 · rename
- SSH · 외부 API · Telegram · .env 로드
- persistent JSON / JSONL / SQLite / log / temp file 생성
- stdout 에 절대 경로 · SSH host · token · chat id · raw traceback 노출
- 새 상수 · 새 hard-code path 신설 (Q1 (a) 확정: 기존 resolver 재사용)

계약 확정 (Q1 · Q2):
- Q1 (a): `market_data.sqlite` 기준 경로 = `app.market_data_store.DEFAULT_DB_PATH`.
  `app.etf_nav_store.DEFAULT_DB_PATH` 는 동일 반환값을 별도 선언한 보조 정의
  (충돌 아님). 실제 반환 경로가 다르면 `database_path_resolution_conflict`.
- Q2 (a)+(b): 로컬 실측 + audit 근거 인용을 3단계로 분리 (local_observation /
  prior_audit_evidence / unconfirmed_from_audit).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
from pathlib import Path

# 기존 resolver 재사용 (Q1 (a) 확정).
from app.market_data_store import DEFAULT_DB_PATH as MARKET_DATA_DEFAULT_DB_PATH

# audit 근거로 관찰 대상 runtime · staging 경로만 참조 (§6.7).
# audit conclusion §4.1, §6.4, §8 에 명시된 경로 그대로.
_RUNTIME_PATHS_FROM_AUDIT: tuple[str, ...] = (
    "state/three_push/params/latest_runtime_param.json",
    "state/three_push/oci_runtime_status_latest.json",
    "state/three_push/oci_runtime_sent_registry.json",
    "state/three_push/oci_runtime_history.jsonl",
    "state/runtime/three_push_runtime_probe_latest.json",
)

# audit §5 에 명시된 decision_evidence.sqlite 경로 (기존 default 재사용).
# FIX r1 (검증자 B-1): fail-loud. import 실패 시 조용한 하드코딩 fallback 대신
# 예외를 상위로 노출 (main() 의 sanitised 예외 경계에서 status=FAILED 처리).
from app.decision_evidence_store import (  # noqa: E402
    DEFAULT_DB_PATH as DECISION_DEFAULT_DB_PATH,
)

# staging env 변수명만 참조 (audit §8 명시). .env 로드 금지.
STAGING_ENV_NAME = "THREE_PUSH_REMOTE_PACKAGE_DIR"

VALID_ENVIRONMENTS = ("pc", "oci")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=("OCI Database Preflight v1 (read-only). PC · OCI 각각 수동 실행.")
    )
    p.add_argument(
        "--environment",
        required=True,
        choices=list(VALID_ENVIRONMENTS),
        help="pc | oci (라벨만 — 원격 접속·전송·환경 변경 금지)",
    )
    return p.parse_args()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _relative(p: Path) -> str:
    """프로젝트 상대 경로 문자열. 절대 경로 노출 금지."""
    try:
        return p.resolve().relative_to(_project_root()).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _revision() -> str:
    """현재 repository revision (short git hash). 실패 시 'unavailable'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_project_root()),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            r = result.stdout.strip()
            if r:
                return r
    except (OSError, subprocess.SubprocessError):
        pass
    return "unavailable"


# ---------- market_data.sqlite path resolution (§6.4) ----------


def _resolve_market_data_path() -> tuple[str, str, str]:
    """(canonical path str, path_status, comparison_note).

    Q1 (a) 확정: 기존 resolver 재사용. 반환값 동일 = 충돌 아님.
    실제 반환 경로가 다르면 database_path_resolution_conflict.
    """
    canonical = MARKET_DATA_DEFAULT_DB_PATH
    try:
        canonical_str = str(Path(canonical).as_posix())
    except Exception:  # noqa: BLE001
        return ("", "database_path_resolution_conflict", "canonical_unreadable")
    # 보조 정의 (etf_nav_store) 실제 반환값 비교.
    try:
        from app.etf_nav_store import DEFAULT_DB_PATH as _AUX

        aux_str = str(Path(_AUX).as_posix())
    except Exception:  # noqa: BLE001
        aux_str = canonical_str  # 보조 정의 로드 실패는 충돌로 판단하지 않음.
    if aux_str != canonical_str:
        return (
            canonical_str,
            "database_path_resolution_conflict",
            f"aux_returns_different_path (aux={aux_str}, canonical={canonical_str})",
        )
    return (canonical_str, "resolved", "single_canonical_path")


# ---------- SQLite read-only observation (§6.5 · §6.6) ----------


def _observe_sqlite(rel_path: str) -> dict:
    """지시문 §6.5 관찰 항목. write 유발 명령 금지.

    반환 dict 는 stdout 조립용. 절대 경로 · secret · raw traceback 미포함.
    """
    obs: dict = {
        "path": rel_path,
        "exists": False,
        "is_regular_file": False,
        "parent_dir_exists": False,
        "read_open_success": False,
        "integrity_check": None,
        "table_count": None,
        "schema_version": None,
        "application_id": None,
        "file_size_bytes": None,
        "read_access": False,
    }
    p = Path(rel_path)
    obs["parent_dir_exists"] = p.parent.exists() and p.parent.is_dir()
    if not p.exists():
        return obs
    obs["exists"] = True
    obs["is_regular_file"] = p.is_file()
    try:
        obs["file_size_bytes"] = int(p.stat().st_size)
    except OSError:
        pass
    obs["read_access"] = os.access(p, os.R_OK)
    if not obs["is_regular_file"]:
        return obs
    # read-only open (uri mode=ro). write 유발 명령 · 저장 이력 변경 금지.
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        obs["read_open_success"] = True
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
            if row:
                obs["integrity_check"] = str(row[0])
            tbl_rows = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            obs["table_count"] = len(tbl_rows)
            sv = con.execute("PRAGMA schema_version").fetchone()
            if sv:
                obs["schema_version"] = int(sv[0])
            ai = con.execute("PRAGMA application_id").fetchone()
            if ai:
                obs["application_id"] = int(ai[0])
        finally:
            con.close()
    except sqlite3.Error:
        obs["read_open_success"] = False
    return obs


def _market_readiness(obs: dict, path_status: str) -> str:
    """§7.1 market_data.sqlite 개별 READY / NOT_READY / UNAVAILABLE / FAILED."""
    if path_status == "database_path_resolution_conflict":
        return "NOT_READY"
    if path_status != "resolved":
        return "UNAVAILABLE"
    if not obs["exists"]:
        return "NOT_READY"
    if not obs["is_regular_file"]:
        return "NOT_READY"
    if not obs["read_open_success"]:
        return "NOT_READY"
    if obs["integrity_check"] != "ok":
        return "NOT_READY"
    if obs["table_count"] is None:
        return "NOT_READY"
    return "READY"


def _decision_readiness(obs: dict) -> str:
    """§6.6 · §7.2: 부재는 OPTIONAL_MISSING, overall 실패 강제 안 함."""
    if not obs["exists"]:
        return "OPTIONAL_MISSING"
    if not obs["is_regular_file"]:
        return "NOT_READY"
    if not obs["read_open_success"]:
        return "NOT_READY"
    if obs["integrity_check"] != "ok":
        return "NOT_READY"
    return "READY"


# ---------- runtime paths + staging (§6.7 · Q2 (a)+(b)) ----------


def _observe_runtime_paths() -> list[dict]:
    """지시문 §6.7: audit conclusion 에 명시된 경로만 로컬 실측.

    exists / is_file / metadata 기반 read 관찰. content read 금지.
    """
    out: list[dict] = []
    for rel in _RUNTIME_PATHS_FROM_AUDIT:
        p = Path(rel)
        entry: dict = {
            "path": rel,
            "exists": p.exists(),
            "is_regular_file": p.is_file() if p.exists() else False,
            "read_access": os.access(p, os.R_OK) if p.exists() else False,
            "source_of_truth": "prior_audit_evidence",  # audit §4.1 · §6.4.
        }
        out.append(entry)
    return out


def _observe_staging() -> dict:
    """§6.7 Q2 (a)+(b) 3단계 근거 분리.

    - 로컬 실측: env 변수 presence 만 (값 · 절대 경로 stdout 노출 금지).
    - prior_audit_evidence: audit §8 에서 확인된 항목 (여기서는 script 존재 여부).
    - unconfirmed_from_audit: 현재 OCI 실제 remote staging 절대 경로 · 권한 ·
      atomic rename 가능 여부 · 현재 remote verify 가능 여부.
    """
    env_present = STAGING_ENV_NAME in os.environ

    # audit §8 명시 script 존재 여부 (로컬 실측).
    audit_scripts = [
        "scripts/sync_three_push_packages.py",
        "scripts/sync_three_push_runtime_param.py",
        "scripts/verify_three_push_packages_oci.py",
        "scripts/verify_three_push_param_oci.py",
    ]
    audit_script_status = [
        {
            "path": s,
            "exists": Path(s).exists(),
            "is_regular_file": Path(s).is_file(),
        }
        for s in audit_scripts
    ]

    if env_present:
        local_observation = "env_variable_present"
    else:
        local_observation = "env_variable_absent"

    # 현재 OCI 환경 실제 remote 상태는 이번 로컬 실행에서 확인 불가.
    unconfirmed = [
        "remote_staging_absolute_path",
        "remote_permission",
        "remote_atomic_rename_capability",
        "remote_verify_capability",
    ]

    return {
        "env_variable_name": STAGING_ENV_NAME,
        "local_observation": local_observation,
        "prior_audit_evidence": {
            "sync_scripts": audit_script_status,
            "note": "audit §8 명시 PC↔OCI transfer script 로컬 존재. "
            "remote staging 실제 상태는 이번 실행에서 미확인.",
        },
        "unconfirmed_from_audit": unconfirmed,
    }


def _staging_status(staging: dict) -> str:
    """§6.7: env 값 부재 + audit 미확인 → unconfirmed_from_audit."""
    if staging["local_observation"] == "env_variable_present":
        # env 는 있지만 remote 실제 상태 미확인.
        return "unconfirmed_from_audit"
    return "unconfirmed_from_audit"


# ---------- overall readiness (§7.2) ----------


def _runtime_paths_status(runtime_obs: list[dict]) -> str:
    """참조: audit §4.1 · §6.4 근거로 confirmed 상태 반영.

    단, 이번 로컬 실행이 오직 한쪽 environment 이므로 overall 판정에는 부족.
    로컬 실측만으로는 confirmed_from_local_and_prior_audit / unconfirmed_from_audit.
    """
    # 로컬에서 exists 확인이 하나라도 있으면 audit 근거와 함께 confirmed.
    any_exists = any(e["exists"] for e in runtime_obs)
    if any_exists:
        return "confirmed_from_local_and_prior_audit"
    return "unconfirmed_from_audit"


# ---------- main ----------


def _main_impl() -> int:
    """실제 preflight 실행 본체. 예외 처리는 main() 이 담당 (§6.2)."""
    args = _parse_args()
    env = args.environment
    revision = _revision()

    canonical_path_str, path_status, path_note = _resolve_market_data_path()

    if path_status == "resolved":
        market_obs = _observe_sqlite(canonical_path_str)
    else:
        market_obs = {
            "path": canonical_path_str or "unresolved",
            "exists": False,
            "is_regular_file": False,
            "parent_dir_exists": False,
            "read_open_success": False,
            "integrity_check": None,
            "table_count": None,
            "schema_version": None,
            "application_id": None,
            "file_size_bytes": None,
            "read_access": False,
        }
    market_readiness = _market_readiness(market_obs, path_status)

    decision_rel = _relative(Path(DECISION_DEFAULT_DB_PATH))
    decision_obs = _observe_sqlite(decision_rel)
    decision_readiness = _decision_readiness(decision_obs)

    runtime_obs = _observe_runtime_paths()
    runtime_paths_status = _runtime_paths_status(runtime_obs)

    staging = _observe_staging()
    staging_status = _staging_status(staging)

    # 이번 실행이 하나의 environment 만 담당 → overall 판정은 conclusion 에서.
    single_env_readiness = market_readiness  # market 이 gate.

    # stdout 조립 (sanitised).
    print("=" * 60)
    print(f"[preflight] environment={env} revision={revision}")
    print(f"[market_data] path={market_obs['path']}")
    print(f"[market_data] path_status={path_status} note={path_note}")
    print(
        f"[market_data] exists={market_obs['exists']} "
        f"regular_file={market_obs['is_regular_file']} "
        f"read_access={market_obs['read_access']} "
        f"read_open_success={market_obs['read_open_success']}"
    )
    print(
        f"[market_data] integrity_check={market_obs['integrity_check']} "
        f"table_count={market_obs['table_count']} "
        f"schema_version={market_obs['schema_version']} "
        f"application_id={market_obs['application_id']} "
        f"file_size_bytes={market_obs['file_size_bytes']}"
    )
    print(f"[market_data] readiness={market_readiness}")
    print(f"[decision_evidence] path={decision_obs['path']}")
    print(
        f"[decision_evidence] exists={decision_obs['exists']} "
        f"regular_file={decision_obs['is_regular_file']} "
        f"read_open_success={decision_obs['read_open_success']} "
        f"integrity_check={decision_obs['integrity_check']} "
        f"table_count={decision_obs['table_count']}"
    )
    print(f"[decision_evidence] readiness={decision_readiness}")
    print("[runtime_paths] (audit §4.1 · §6.4 명시 경로 로컬 실측)")
    for r in runtime_obs:
        print(
            f"  - path={r['path']} exists={r['exists']} "
            f"regular_file={r['is_regular_file']} "
            f"read_access={r['read_access']}"
        )
    print(f"[runtime_paths] status={runtime_paths_status}")
    print(
        f"[staging] env_variable={staging['env_variable_name']} "
        f"local_observation={staging['local_observation']}"
    )
    print(f"[staging] status={staging_status}")
    print(f"[single_environment_readiness] {single_env_readiness}")
    print(
        "[note] overall READY/NOT_READY/PARTIAL 은 PC·OCI 양쪽 실행 후 "
        "conclusion 에서 확정. 이번 실행은 한쪽 environment 결과만 담음."
    )
    print("=" * 60)

    # non-zero exit 은 preflight 자체 오류로만 사용. NOT_READY 는 정상 종료.
    return 0


def main() -> int:
    """지시문 §6.2 최상위 예외 경계.

    예상하지 못한 오류가 발생해도 raw traceback 대신
    `status=FAILED / error_class=<class 이름>` 만 stdout 에 노출한다.
    절대 경로 · secret · exception message 자체는 노출하지 않는다.

    SystemExit (argparse 종료 등) 는 그대로 상위로 노출.
    """
    try:
        return _main_impl()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        # 사용자 지정 error 분류 label 이면 그것을, 아니면 exception class 이름.
        cls_name = type(exc).__name__
        # cls_name 은 파일시스템 · secret 을 포함하지 않는 Python 식별자만.
        print("=" * 60)
        print("status=FAILED")
        print(f"error_class={cls_name}")
        print("=" * 60)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
