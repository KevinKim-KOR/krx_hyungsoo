"""POC6-03 — 가격 이력 기준 일관성 검증 CLI(PC 수동 · 연구 사본 · 라이브 DB 쓰기 0).

    python scripts/run_price_basis_check.py fetch --snapshot <POC6-02 공식 input_snapshot.json> \
        --expect-digest <승인된 snapshot digest>
        # 외부 조회(FinanceDataReader · 종목마다 1회 · 최대 26회) — 사용자 승인 뒤에만 실행
        # digest 다름 · 26종 초과 · 같은 snapshot 사본이 이미 있으면 조회 0 으로 거절
    python scripts/run_price_basis_check.py compare --copy-dir <사본 폴더> [--krx-db <봉인 DB>]
        # 외부 조회 0 · 같은 사본으로 대조만 다시
    python scripts/run_price_basis_check.py run --snapshot <...> --expect-digest <...>
        # fetch 다음 compare

종료 코드: 0 = 완료(조회 실패 · 대조 불가가 있어도 보고) · 2 = 입력 확인 필요 · 1 = 저장 · 실행 실패.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import krx_sealed_reader as krx  # noqa: E402
from app.d20_pooled.snapshot import SnapshotError, load_snapshot  # noqa: E402
from app.price_basis_check import compare as C  # noqa: E402
from app.price_basis_check import fetch as F  # noqa: E402
from app.price_basis_check import report as R  # noqa: E402


def _fetch(snapshot: Path, expect_digest: str) -> Path:
    snap = load_snapshot(snapshot)
    F.preflight(snap, expect_digest)
    batch = F.fetch_batch(snap)
    folder = F.write_copy(snap, snapshot.resolve(), batch)
    counts: dict[str, int] = {}
    for e in batch["log"]:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print(f"사본 폴더: {folder}")
    print(f"조회 결과: {counts}")
    return folder


def _compare(copy_dir: Path, krx_db: Path) -> Path:
    out = R.run_compare(copy_dir, krx_db=krx_db)
    body = json.loads((out / "report.json").read_text(encoding="utf-8"))
    sm, rec = body["summary"], body["recount"]
    print(f"대조 보고서: {out}")
    print(
        f"경계 기존 {sm['live_breaks']} → 사본 {sm['copy_breaks']}"
        " (사본 change = 같은 응답 종가 비율 → 사본 경계 0 은 근거가 아님)"
    )
    print(
        f"KRX 일치 {sm['krx_match']} · 불일치 {sm['krx_mismatch']} · 대조 불가 {sm['krx_not_comparable']}"
    )
    print(
        f"적격(POC6-02 규칙) 공식 {len(rec['official']['eligible'])}"
        f" → 사본 {len(rec['copy']['eligible'])}"
        " (사본은 06 경계가 구조적으로 사라져 늘 수 있음 — KRX 대조와 함께 읽기)"
    )
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="POC6-03 가격 이력 기준 일관성 검증")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch", help="한 묶음 조회 → 연구 사본(외부 조회)")
    p_fetch.add_argument("--snapshot", type=Path, required=True)
    p_fetch.add_argument("--expect-digest", required=True)
    p_cmp = sub.add_parser("compare", help="사본 대조(외부 조회 0)")
    p_cmp.add_argument("--copy-dir", type=Path, required=True)
    p_cmp.add_argument("--krx-db", type=Path, default=krx.DEFAULT_SEALED_DB)
    p_run = sub.add_parser("run", help="fetch 다음 compare")
    p_run.add_argument("--snapshot", type=Path, required=True)
    p_run.add_argument("--expect-digest", required=True)
    p_run.add_argument("--krx-db", type=Path, default=krx.DEFAULT_SEALED_DB)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "fetch":
            _fetch(args.snapshot, args.expect_digest)
        elif args.cmd == "compare":
            _compare(args.copy_dir, args.krx_db)
        else:
            _compare(_fetch(args.snapshot, args.expect_digest), args.krx_db)
        return 0
    except (SnapshotError, C.CompareError, F.FetchRefused) as e:
        print(f"CHECK_REQUIRED: {e}", file=sys.stderr)
        return 2
    except (F.CopySaveError, R.ReportSaveError) as e:
        print(f"RUN_FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — 계산 오류를 숨기지 않음
        print(f"RUN_FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
