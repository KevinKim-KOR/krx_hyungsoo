"""
Evidence Ref Validator (C-P.33)

공용 모듈: /api/evidence/resolve와 Health Checker가 동일하게 사용
- Validator Single Source 정책
- 복제 금지, 분기 금지
"""

import json
import os
import re
import linecache
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent

# Allowlist + Patterns (동일 정책)
ALLOWED_JSONL_FILES = [
    "state/tickets/ticket_receipts.jsonl",
    "state/tickets/ticket_results.jsonl",
    "state/push/send_receipts.jsonl"
]

ALLOWED_JSON_PATTERNS = [
    r"^reports/ops/scheduler/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/postmortem/postmortem_latest\.json$",
    r"^reports/ops/secrets/self_test_latest\.json$",
    r"^reports/ops/push/outbox/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/outbox/outbox_latest\.json$",
    r"^reports/ops/push/live_fire/live_fire_latest\.json$",
    r"^reports/ops/push/live_fire/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/daily/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/evidence/index/evidence_index_latest\.json$",
    r"^reports/ops/evidence/index/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/send/send_latest\.json$",
    r"^reports/ops/push/send/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/preview/preview_latest\.json$",
    r"^reports/phase_c/latest/recon_summary\.json$",
    r"^reports/phase_c/latest/report_human\.json$",
    r"^reports/phase_c/latest/report_ai\.json$",
    # C-P.33: Evidence Health
    r"^reports/ops/evidence/health/health_latest\.json$",
    r"^reports/ops/evidence/health/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # ... (skipping unchanged lines) ...
    r"^reports/ops/push/spike_watch/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/spike_watch/latest/spike_watch_latest\.json$",
    r"^reports/ops/push/holding_watch/latest/holding_watch_latest\.json$",
    r"^reports/ops/push/holding_watch/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/ops/push/daily_status/latest/daily_status_latest\.json$",
    r"^reports/ops/push/daily_status/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P76: Strategy Bundle
    r"^state/strategy_bundle/latest/strategy_bundle_latest\.json$",
    r"^state/strategy_bundle/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P77: Live Cycle Snapshots
    r"^reports/live/cycle/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/live/reco/latest/reco_latest\.json$",
    r"^reports/live/reco/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P102 Order Plan
    r"^reports/live/order_plan/latest/order_plan_latest\.json$",
    r"^reports/live/order_plan/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P103 Contract 5 Report
    r"^reports/ops/contract5/latest/[a-zA-Z0-9_\-\.]+\.(json|md)$",
    r"^reports/ops/contract5/snapshots/[a-zA-Z0-9_\-\.]+\.(json|md)$",
    # P111 Order Plan Export
    r"^reports/live/order_plan_export/latest/order_plan_export_latest\.json$",
    r"^reports/live/order_plan_export/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P112 Execution Prep
    r"^reports/live/execution_prep/latest/execution_prep_latest\.json$",
    r"^reports/live/execution_prep/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P113-A Manual Execution
    r"^reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest\.(json|csv|md)$",
    r"^reports/live/manual_execution_ticket/snapshots/[a-zA-Z0-9_\-\.]+\.(json|csv|md)$",
    r"^reports/live/manual_execution_record/latest/manual_execution_record_latest\.json$",
    r"^reports/live/manual_execution_record/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    r"^reports/phase_c/latest/report_human\.json$",
    # P131: Dry Run Record
    r"^reports/live/dry_run_record/latest/dry_run_record_latest\.json$",
    r"^reports/live/dry_run_record/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
    # P134: Strategy Params
    r"^state/strategy_params/latest/strategy_params_latest\.json$",
    r"^state/strategy_params/snapshots/[a-zA-Z0-9_\-\.]+\.json$",
]

JSONL_REF_PATTERN = r"^(state/tickets/ticket_receipts\.jsonl|state/tickets/ticket_results\.jsonl|state/push/send_receipts\.jsonl):line(\d+)$"

DANGEROUS_TOKENS = ['..', '\\', '://', '%2e', '%2f', '%2E', '%2F', '%00']

# P70: Resolver Aliases (Guard)
REF_ALIASES = {
    "guard_spike_latest": "reports/ops/push/spike_watch/latest/spike_watch_latest.json",
    "guard_holding_latest": "reports/ops/push/holding_watch/latest/holding_watch_latest.json",
    "guard_report_human_latest": "reports/ops/contract5/latest/human_report_latest.md",
    "guard_report_ai_latest": "reports/ops/contract5/latest/ai_report_latest.json",
    "guard_daily_status_latest": "reports/ops/push/daily_status/latest/daily_status_latest.json",
    "guard_bundle_latest": "state/strategy_bundle/latest/strategy_bundle_latest.json",
    "guard_strategy_bundle_latest": "state/strategy_bundle/latest/strategy_bundle_latest.json",
    "guard_order_plan_export_latest": "reports/live/order_plan_export/latest/order_plan_export_latest.json",
    "guard_execution_prep_latest": "reports/live/execution_prep/latest/execution_prep_latest.json",
    "guard_execution_ticket_latest": "reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json",
    "guard_execution_record_latest": "reports/live/manual_execution_record/latest/manual_execution_record_latest.json",
    "guard_strategy_params_latest": "state/strategy_params/latest/strategy_params_latest.json",
    "guard_dry_run_record_latest": "reports/live/dry_run_record/latest/dry_run_record_latest.json"
}


@dataclass
class ResolvedEvidence:
    """Ref 검증 결과"""
    decision: str  # OK | INVALID_REF | NOT_FOUND | PARSE_ERROR
    http_status_equivalent: int  # 200 | 400 | 404
    content_type: str  # json | jsonl_line | text | none
    resolved_path: Optional[str]
    data: Optional[Any]
    reason: Optional[str]
    source_kind: Optional[str]
    source_line: Optional[int]
    raw_content: Optional[str] = None  # P146.2 Fail-Soft Preview


def validate_and_resolve_ref(ref: str) -> ResolvedEvidence:
    """
    Ref 검증 + 해석 (단일 정공 함수)
    
    - 0차: Alias Resolution (P70)
    - 1차: 위험 토큰 거부
    - 2차: regex/allowlist 검증
    - 3차: path normalization + allowed_root 검증
    - 4차: 파일 존재 확인 + 내용 읽기
    """
    
    # === 0차: Alias Resolution ===
    if ref in REF_ALIASES:
        ref = REF_ALIASES[ref]

    # === 1차 검증: 위험 토큰 즉시 거부 ===
    for token in DANGEROUS_TOKENS:
        if token in ref:
            return ResolvedEvidence(
                decision="INVALID_REF",
                http_status_equivalent=400,
                content_type="none",
                resolved_path=None,
                data=None,
                reason=f"Dangerous token detected: {token}",
                source_kind=None,
                source_line=None
            )
    
    # === JSONL Line Ref 처리 ===
    jsonl_match = re.match(JSONL_REF_PATTERN, ref)
    if jsonl_match:
        jsonl_path = jsonl_match.group(1)
        line_no = int(jsonl_match.group(2))
        
        if line_no < 1:
            return ResolvedEvidence(
                decision="INVALID_REF",
                http_status_equivalent=400,
                content_type="none",
                resolved_path=None,
                data=None,
                reason="Line number must be >= 1",
                source_kind=None,
                source_line=None
            )
        
        # Allowlist 검증
        if jsonl_path not in ALLOWED_JSONL_FILES:
            return ResolvedEvidence(
                decision="INVALID_REF",
                http_status_equivalent=400,
                content_type="none",
                resolved_path=None,
                data=None,
                reason="JSONL file not in allowlist",
                source_kind=None,
                source_line=None
            )
        
        # 2차 검증: Path Normalization
        full_path = BASE_DIR / jsonl_path
        abs_path = os.path.abspath(str(full_path))
        allowed_root = os.path.abspath(str(BASE_DIR))
        
        if not abs_path.startswith(allowed_root + os.sep):
            return ResolvedEvidence(
                decision="INVALID_REF",
                http_status_equivalent=400,
                content_type="none",
                resolved_path=None,
                data=None,
                reason="Path escape attempt blocked",
                source_kind=None,
                source_line=None
            )
        
        if not full_path.exists():
            return ResolvedEvidence(
                decision="NOT_FOUND",
                http_status_equivalent=404,
                content_type="none",
                resolved_path=jsonl_path,
                data=None,
                reason=f"File not found: {jsonl_path}",
                source_kind="JSONL_LINE",
                source_line=line_no
            )
        
        # linecache로 특정 라인만 읽기 (전체 읽기 금지)
        linecache.checkcache(str(full_path))
        line_content = linecache.getline(str(full_path), line_no)
        
        if not line_content.strip():
            return ResolvedEvidence(
                decision="NOT_FOUND",
                http_status_equivalent=404,
                content_type="none",
                resolved_path=jsonl_path,
                data=None,
                reason=f"Line {line_no} is empty or out of range",
                source_kind="JSONL_LINE",
                source_line=line_no
            )
        
        try:
            data = json.loads(line_content)
            return ResolvedEvidence(
                decision="OK",
                http_status_equivalent=200,
                content_type="jsonl_line",
                resolved_path=jsonl_path,
                data=data,
                reason=None,
                source_kind="JSONL_LINE",
                source_line=line_no
            )
        except json.JSONDecodeError as e:
            return ResolvedEvidence(
                decision="PARSE_ERROR",
                http_status_equivalent=200,
                content_type="jsonl_line",
                resolved_path=jsonl_path,
                data=None,
                reason=f"JSON parse error at line {line_no}: {str(e)}",
                source_kind="JSONL_LINE",
                source_line=line_no,
                raw_content=line_content[:4096] # P146.2 Fail-Soft
            )
    
    # === JSON Ref 처리 ===
    json_matched = False
    for pattern in ALLOWED_JSON_PATTERNS:
        if re.match(pattern, ref):
            json_matched = True
            break
    
    if not json_matched:
        return ResolvedEvidence(
            decision="INVALID_REF",
            http_status_equivalent=400,
            content_type="none",
            resolved_path=None,
            data=None,
            reason=f"Ref does not match any allowed pattern: {ref}",
            source_kind=None,
            source_line=None
        )
    
    # 2차 검증: Path Normalization
    full_path = BASE_DIR / ref
    abs_path = os.path.abspath(str(full_path))
    allowed_root = os.path.abspath(str(BASE_DIR))
    
    if not abs_path.startswith(allowed_root + os.sep):
        return ResolvedEvidence(
            decision="INVALID_REF",
            http_status_equivalent=400,
            content_type="none",
            resolved_path=None,
            data=None,
            reason="Path escape attempt blocked",
            source_kind=None,
            source_line=None
        )
    
    if not full_path.exists():
        return ResolvedEvidence(
            decision="NOT_FOUND",
            http_status_equivalent=404,
            content_type="none",
            resolved_path=ref,
            data=None,
            reason=f"File not found: {ref}",
            source_kind="JSON",
            source_line=None
        )
    
    # P146.5: Extension-based branching — non-JSON files returned as raw text
    ext = full_path.suffix.lower()
    if ext in ('.md', '.txt', '.csv'):
        try:
            content = full_path.read_text(encoding="utf-8")
            return ResolvedEvidence(
                decision="OK",
                http_status_equivalent=200,
                content_type="text",
                resolved_path=ref,
                data={"raw_text": content[:8192], "file_type": ext.lstrip('.')},
                reason=None,
                source_kind="TEXT",
                source_line=None
            )
        except Exception as e:
            return ResolvedEvidence(
                decision="PARSE_ERROR",
                http_status_equivalent=200,
                content_type="text",
                resolved_path=ref,
                data=None,
                reason=f"File read error: {str(e)}",
                source_kind="TEXT",
                source_line=None,
                raw_content="Read Fail"
            )

    # JSON files: standard parse path
    try:
        content = full_path.read_text(encoding="utf-8")
        data = json.loads(content)
        return ResolvedEvidence(
            decision="OK",
            http_status_equivalent=200,
            content_type="json",
            resolved_path=ref,
            data=data,
            reason=None,
            source_kind="JSON",
            source_line=None
        )
    except json.JSONDecodeError as e:
        return ResolvedEvidence(
            decision="PARSE_ERROR",
            http_status_equivalent=200,
            content_type="json",
            resolved_path=ref,
            data=None,
            reason=f"JSON parse error: {str(e)}",
            source_kind="JSON",
            source_line=None,
            raw_content=content[:4096] if 'content' in locals() else "Read Fail"
        )
