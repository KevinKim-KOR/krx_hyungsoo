"""POC6-04 — D20 확장 표본 재현 검증 CLI(탐색적 · CPU · PC 수동 · 외부 조회 0).

    python scripts/run_d20_expanded_check.py run

입력 = `app/d20_expand/inputs.MANIFEST` 의 고정 파일(전체 sha256 확인 · 다르면 멈춤).
출력 = `state/ml/research/poc6_04/<시각>_<id>/` 새 폴더. GPU 묶음 · POC6-02 결과 · DB · 보유 · OCI 쓰기 0.
종료 코드: 0 = 완료 · 2 = 확인 필요(입력 · 행 구조 · 대조군) · 1 = 저장 · 실행 실패.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.d20_expand import inputs as IN  # noqa: E402
from app.d20_expand import runner as RU  # noqa: E402


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="POC6-04 D20 확장 표본 재현 검증")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="B · C CPU 실행 · 비교 보고")
    parser.parse_args(argv)
    try:
        folder, report = RU.run(
            IN.MANIFEST, IN.PROJECT_ROOT
        )  # 호출 때 읽음(고정 manifest)
    except IN.InputError as e:
        print(f"CHECK_REQUIRED: {e}", file=sys.stderr)
        return 2
    except RU.SaveError as e:
        print(f"RUN_FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — 계산 오류를 숨기지 않음
        print(f"RUN_FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    print(f"산출 폴더: {folder}")
    print(
        f"상태: {report['status']}"
        + (f" · 사유: {report['reason']}" if report.get("reason") else "")
    )
    if report["status"] == RU.COMPLETED:
        print(
            f"주 판정(C {len(report['c_etfs'])}종 · 탐색적): {report['c12']['verdict']['label']}"
        )
        for n in report["direction_notes"]:
            print(f"  {n}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
