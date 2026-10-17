"""POC5-20 — 가격 · 거래량 · 변동성 근거 조합의 과거 사례 대조 CLI(PC 수동 · 읽기 전용).

    python scripts/run_evidence_combination_review.py --end 2026-10-14

입력 = 현재 보유 파일(종목 코드만) · PC 시장 DB(`mode=ro`) · 2026 거래일 캘린더.
출력 = `state/ml/research/poc5_20/<종료일>_<생성시각>/` 새 폴더(report.md · report.json · input_snapshot.json).
DB · 보유 · 원장 쓰기 · 외부 조회 · OCI · PUSH 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evidence_combo import report  # noqa: E402


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="POC5-20 근거 조합 과거 사례 대조(읽기 전용)"
    )
    parser.add_argument(
        "--end", required=True, help="종료일 YYYY-MM-DD(이후 가격은 쓰지 않음)"
    )
    args = parser.parse_args(argv)
    try:
        folder = report.run(args.end)
    except report.EndDateError as e:
        print(f"실행하지 않음: {e}", file=sys.stderr)
        return 2
    body = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    print(f"산출 폴더: {folder}")
    print(f"입력 식별: {body['input_hash']} · 본문 식별: {body['body_hash']}")
    print(
        f"종목 × 기준일 {body['universe']['pairs']} → 공통 표본 {body['common_sample']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
