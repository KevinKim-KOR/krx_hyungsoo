"""POC5-04 — R0 수집 점검 · R1 원시 결과 리포트 CLI(PC 수동 · 읽기 전용).

    python scripts/run_ledger_report.py r0 [--db] [--end YYYY-MM-DD] \\
        [--reconcile-evidence 파일] [--ops-evidence 파일] [--out-dir 폴더]
    python scripts/run_ledger_report.py r1 [--db] [--end] [--iterations 1000] [--seed 0] [--out-dir]

입력 기본 = PC 원장 사본 `state/decision/decision_evidence.sqlite`(03 · mode=ro).
출력 = `state/ml/research/poc5_04/` 아래 새 폴더(report.md · report.json). SSH · 외부 조회 · DB 쓰기 0.
대조 근거 = 01B 대조 CLI 출력 + 첫 줄 `captured_at=<ISO>`(개발자가 OCI 에서 읽기 전용으로 받아 저장).
운영 근거 = `price_batch_price_date=` · `price_batch_status=` · `price_batch_completed_at=` 줄 + 메모.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ledger_copy import store  # noqa: E402
from app.ledger_reports import bootstrap, dates, r0, r1, render  # noqa: E402
from app.ledger_reports.source import load_snapshot  # noqa: E402


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("1 이상이어야 한다")
    return value


def _read(path: Optional[str]) -> Optional[str]:
    return None if not path else Path(path).read_text(encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="report", required=True)
    for name in ("r0", "r1"):
        p = sub.add_parser(name)
        p.add_argument("--db", default=None)
        p.add_argument("--end", default=None)
        p.add_argument("--calendar-dir", default=None)
        p.add_argument("--out-dir", default=str(render.DEFAULT_ROOT))
        if name == "r0":
            p.add_argument("--reconcile-evidence", default=None)
            p.add_argument("--ops-evidence", default=None)
        else:
            p.add_argument("--iterations", type=_positive, default=bootstrap.ITERATIONS)
            p.add_argument("--seed", type=int, default=bootstrap.SEED)
    args = parser.parse_args(argv)

    db = Path(args.db) if args.db else store.DEFAULT_DB_PATH
    cal = dates.calendar(Path(args.calendar_dir) if args.calendar_dir else None)
    today = dates.today_kst()
    end = args.end or dates.default_end(cal, today)
    try:
        dates.validate_end(cal, end or "", today)
    except ValueError as e:
        print(f"status=FAILED reason=end_date detail={e}")
        return 2
    now = datetime.now(dates.KST)
    generated = now.isoformat(timespec="seconds")
    snap = load_snapshot(db)
    if args.report == "r0":
        report = r0.build(
            snap,
            cal,
            end=end,
            reconcile_text=_read(args.reconcile_evidence),
            ops_text=_read(args.ops_evidence),
            generated_at=generated,
        )
    else:
        try:
            report = r1.build(
                snap,
                cal,
                end=end,
                generated_at=generated,
                iterations=args.iterations,
                seed=args.seed,
            )
        except r1.InvalidInput as e:
            print(f"status=FAILED reason=invalid_input detail={e}")
            return 3
    folder = render.write(report, Path(args.out_dir), now.strftime("%Y%m%dT%H%M%S"))
    verdict = report.get("verdict", "-")
    print(
        f"status=OK report={report['report']} end={end} verdict={verdict} out={folder}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
