"""GET /ml/baseline-v0/latest — read-only ML baseline v0 룩백 검증 조회 (2026-06-11).

지시문 §13 — Data Status 표시용. 본 API 는:
- state/ml/ml_baseline_v0_report_latest.json 만 read.
- baseline 재계산 X, feature 생성 X, ML 학습 X, 외부 source 호출 X.
- 매수/매도 판단 반환 X.

status:
- empty: snapshot 미생성 (CLI 미실행).
- error: snapshot 손상 (fail-loud).
- ok: 정상 반환.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

BASELINE_REPORT_PATH = Path("state/ml/ml_baseline_v0_report_latest.json")

router = APIRouter()


class MlBaselineV0Response(BaseModel):
    status: str  # ok / empty / error
    report_path: str
    report: Optional[dict[str, Any]] = None
    message: Optional[str] = None


@router.get("/ml/baseline-v0/latest", response_model=MlBaselineV0Response)
def get_ml_baseline_v0_latest() -> MlBaselineV0Response:
    """저장된 baseline 룩백 report 만 반환 (재계산 X / 외부 호출 X)."""
    if not BASELINE_REPORT_PATH.exists():
        return MlBaselineV0Response(
            status="empty",
            report_path=str(BASELINE_REPORT_PATH),
            report=None,
            message=(
                "ML baseline v0 룩백 report 미생성. CLI "
                "'python scripts/run_ml_baseline_v0.py' 를 1회 실행하면 본 화면에 "
                "검증 결과가 표시됩니다."
            ),
        )
    try:
        with BASELINE_REPORT_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        return MlBaselineV0Response(
            status="error",
            report_path=str(BASELINE_REPORT_PATH),
            report=None,
            message=(
                f"baseline report 파일이 손상되어 읽을 수 없습니다 "
                f"(json_decode_failed): {e}"
            ),
        )
    return MlBaselineV0Response(
        status="ok",
        report_path=str(BASELINE_REPORT_PATH),
        report=payload,
    )
