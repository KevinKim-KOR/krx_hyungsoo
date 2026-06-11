"""GET /ml/baseline-v0/latest — read-only ML baseline v0 룩백 검증 조회 (2026-06-11).

지시문 §13 — Data Status 표시용. 본 API 는:
- state/ml/ml_baseline_v0_report_latest.json 만 read.
- baseline 재계산 X, feature 생성 X, ML 학습 X, 외부 source 호출 X.
- 매수/매도 판단 반환 X.

status:
- empty: snapshot 미생성 (CLI 미실행).
- error: snapshot 손상 (fail-loud).
- ok: 정상 반환.

추가 (POC2 ML Baseline Evidence Draft Integration FIX r3, 2026-06-11):
- GET /ml/baseline-v0/evidence-snapshot — AI Sessions 등 외부 화면이 GenerateDraft
  와 동일한 정규화 evidence snapshot 을 직접 받을 수 있게 노출. 본 STEP 의 데이터
  계약 단일화 (지시문 §5.1 동일 shape 보장). build_ml_baseline_evidence_snapshot
  은 read-only — 재계산 / 외부 호출 0건.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.ml_baseline_evidence import build_ml_baseline_evidence_snapshot

BASELINE_REPORT_PATH = Path("state/ml/ml_baseline_v0_report_latest.json")

router = APIRouter()


class MlBaselineV0Response(BaseModel):
    status: str  # ok / empty / error
    report_path: str
    report: Optional[dict[str, Any]] = None
    message: Optional[str] = None


class MlBaselineEvidenceSnapshotResponse(BaseModel):
    """draft_payload.ml_baseline_evidence_snapshot 과 동일 shape.

    AI Sessions / Decision Evidence 저장 경로가 동일 정규화 구조를 사용하도록
    노출. 본 API 는 build_ml_baseline_evidence_snapshot() 결과를 그대로 반환.
    재계산 X / 외부 호출 X.
    """

    status: str
    report_status: str
    report_path: str
    report_generated_at: Optional[str] = None
    feature_asof_range: Optional[dict[str, Any]] = None
    evaluated_asof_range: Optional[dict[str, Any]] = None
    candidate_summary: Optional[dict[str, Any]] = None
    risk_summary: Optional[dict[str, Any]] = None
    leakage_summary: Optional[dict[str, Any]] = None
    limitations: list[str] = []
    external_context_checklist: list[str] = []
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


@router.get(
    "/ml/baseline-v0/evidence-snapshot",
    response_model=MlBaselineEvidenceSnapshotResponse,
)
def get_ml_baseline_evidence_snapshot() -> MlBaselineEvidenceSnapshotResponse:
    """GenerateDraft 와 동일 shape 의 정규화 evidence snapshot 반환.

    AI Sessions / Decision Evidence 저장 경로가 본 API 결과를 그대로 payload
    의 `ml_baseline_evidence_snapshot` 에 담는다 — 데이터 계약 단일화.

    report 부재 / 손상 / stale 도 200 으로 반환 (조용히 빠지지 않음).
    status ∈ {ok, warn, stale, unavailable, error}.
    """
    snap = build_ml_baseline_evidence_snapshot()
    return MlBaselineEvidenceSnapshotResponse(**snap)
