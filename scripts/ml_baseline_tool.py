"""POC4-01 — ML baseline 불변 스냅샷 도구 (설계자 결정 1 — 2026-09-23).

  build   라이브 DB 를 읽기 전용으로 열어 새 스냅샷 bundle 을 만든다 (덮어쓰기 금지)
  verify  manifest 와 파일 sha256 을 대조한다 (누락·불일치면 종료코드 2)
  compare 두 run_manifest 가 같은 결과인지 대조한다 (결정성 검증 · 다르면 종료코드 1)

예:
  python scripts/ml_baseline_tool.py build --cutoff 2026-09-21 \\
      --baseline-id relative_upside_v1_snap_20260921
  python scripts/ml_baseline_tool.py verify \\
      --manifest state/ml/baselines/<id>/dataset_manifest.json
  python scripts/ml_baseline_tool.py compare runs/run1/run_manifest.json \\
      runs/run2/run_manifest.json

하지 않는 것 — 라이브 DB 쓰기 / OCI / 외부 API / 기존 bundle 덮어쓰기.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.market_data_store import DEFAULT_DB_PATH  # noqa: E402
from app.ml_baseline_snapshot import (  # noqa: E402
    MANIFEST_FILENAME,
    SnapshotIntegrityError,
    build_snapshot,
    verify_snapshot,
)
from app.ml_relative_upside_score import SCORE_SNAPSHOT_PATH  # noqa: E402

BASELINES_DIR = _PROJECT_ROOT / "state" / "ml" / "baselines"


def compare_run_manifests(a: dict, b: dict) -> dict:
    """두 실행이 같은 입력·코드로 같은 결과를 냈는지 항목별로 대조한다."""

    def _get(m: dict, dotted: str):
        node = m
        for part in dotted.split("."):
            node = (node or {}).get(part)
        return node

    keys = (
        "status",
        "dataset.dataset_sha256",
        "dataset.manifest_canonical_sha256",
        "dataset.data_cutoff",
        "code.git.head",
        "code.frozen_modules",
        "code.evaluator_modules",
        "evaluation.count",
        "evaluation.dates",
        "result.canonical_sha256",
    )
    checks = {k: _get(a, k) == _get(b, k) for k in keys}
    return {
        "identical": all(checks.values()),
        "checks": checks,
        "canonical_sha256": [
            _get(a, "result.canonical_sha256"),
            _get(b, "result.canonical_sha256"),
        ],
        "evaluation_count": [_get(a, "evaluation.count"), _get(b, "evaluation.count")],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="ML baseline 불변 스냅샷 도구")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--cutoff", required=True)
    b.add_argument("--baseline-id", required=True)
    b.add_argument("--live-db", default=str(DEFAULT_DB_PATH))
    b.add_argument("--e1-source", default=str(SCORE_SNAPSHOT_PATH))
    b.add_argument("--root", default=str(BASELINES_DIR))
    v = sub.add_parser("verify")
    v.add_argument("--manifest", required=True)
    c = sub.add_parser("compare")
    c.add_argument("run_manifests", nargs=2)
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            manifest = build_snapshot(
                live_db_path=Path(args.live_db),
                e1_source_path=Path(args.e1_source),
                bundle_dir=Path(args.root) / args.baseline_id,
                cutoff=args.cutoff,
                baseline_id=args.baseline_id,
            )
            out = {
                "manifest": str(Path(args.root) / args.baseline_id / MANIFEST_FILENAME),
                "dataset_sha256": manifest["files"]["dataset"]["sha256"],
                "tables": manifest["tables"],
                "e2_count": manifest["evaluation_calendar"]["e2_count"],
            }
        elif args.command == "verify":
            manifest = verify_snapshot(Path(args.manifest))
            out = {"status": "OK", "baseline_id": manifest["baseline_id"]}
        else:
            a, b2 = (json.loads(Path(p).read_text("utf-8")) for p in args.run_manifests)
            out = compare_run_manifests(a, b2)
    except SnapshotIntegrityError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("identical", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
