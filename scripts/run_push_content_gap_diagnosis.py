"""PUSH Content Gap Diagnosis v1 — 수동 실행 진입점 (2026-07-05).

지시문 §8: PC / OCI 각각 1회 수동 실행. 발송 없음. 외부 API 호출 없음.

Usage:
  python -m scripts.run_push_content_gap_diagnosis --environment pc
  python -m scripts.run_push_content_gap_diagnosis --environment oci

--environment 는 명시 필수 (host 추정 금지, §6.1).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.market_data_store import DEFAULT_DB_PATH
from app.push_content_gap_diagnosis import (
    DIAGNOSIS_ARTIFACT_PATH,
    VALID_ENVIRONMENTS,
    run_push_content_gap_diagnosis,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PUSH Content Gap Diagnosis v1 (read only, no send)."
    )
    p.add_argument(
        "--environment",
        required=True,
        choices=list(VALID_ENVIRONMENTS),
        help="pc | oci (호스트명 추정 금지, 명시 인자 필수).",
    )
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--artifact-path", type=Path, default=DIAGNOSIS_ARTIFACT_PATH)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    payload = run_push_content_gap_diagnosis(
        environment=args.environment,
        db_path=args.db_path,
        artifact_path=args.artifact_path,
    )
    print(
        f"[push-content-gap-diagnosis] environment={payload['environment']} "
        f"status={payload['status']} commit={payload['code_version']['commit']}"
    )
    print(
        f"[runtime_readiness] sqlite_integrity="
        f"{payload['runtime_readiness']['sqlite_integrity']} "
        f"required_paths_ready="
        f"{payload['runtime_readiness']['required_logical_paths_ready']}"
    )
    for push in payload["pushes"]:
        cg = push["content_generation"]
        print(
            f"[push:{push['push_id']}] "
            f"root_cause={push['primary_root_cause']} "
            f"content={cg['status']} "
            f"reason={cg['exact_reason_code']} "
            f"selection={cg['selection_result_count']}"
        )
    print(f"[artifact] {args.artifact_path}")
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
