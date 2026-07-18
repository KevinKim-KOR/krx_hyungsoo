"""Universe Momentum artifact 공통 validator (B-6 중복 제거 · 재검증 대응).

Publication CLI 와 Runtime composer 가 이 모듈을 공유해서 판정 계약을
단일 소스로 유지한다.

계약:
- refresh_status allowlist = {"ok", "partial"}. 미지 값 · "failed" 는 unavailable.
- candidates 는 list · 각 원소는 dict 이며 최소 ticker(str) + score_result(dict) 보유.
  구조 손상 시 unavailable.
- as-of 필수 (str · 비어있지 않음).
- mode == "universe".
- 검증자 REJECTED r4 재정정: is_scored=True 인 경우 score_value 는 **유한 실수**여야 함.
  NaN · Inf · -Inf 는 정상 계산 결과가 아니므로 unavailable.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Optional

# seed / artifact as-of 공통 형식: YYYY-MM-DD (universe_seed._ASOF_PATTERN 과 일치).
_ASOF_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# refresh_status allowlist. failed / 미지 값 모두 unavailable.
ALLOWED_REFRESH_STATUSES = frozenset({"ok", "partial"})


def _validate_candidate_shape(c: Any) -> Optional[str]:
    """candidate 개별 구조 검증. 실패 시 reason 반환, 성공 시 None.

    검증자 REJECTED r3 재정정:
    - is_scored 는 **실제 bool 타입**이어야 함. "yes" 등 문자열/정수 거부.
    - is_scored=True 인 경우 score_value 는 실수/정수여야 함 (Runtime 이 표시 가능).
    """
    if not isinstance(c, dict):
        return "candidate_not_dict"
    ticker = c.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return "candidate_ticker_missing"
    score_result = c.get("score_result")
    if not isinstance(score_result, dict):
        return "candidate_score_result_missing"
    if "is_scored" not in score_result:
        return "candidate_is_scored_field_missing"
    is_scored = score_result["is_scored"]
    # bool 는 int 의 subclass 이므로 `type(x) is bool` 로 엄격 확인.
    if not isinstance(is_scored, bool):
        return "candidate_is_scored_not_bool"
    if is_scored:
        score_value = score_result.get("score_value")
        if not isinstance(score_value, (int, float)) or isinstance(score_value, bool):
            return "candidate_score_value_missing_or_invalid"
        # 검증자 REJECTED r4: NaN · Inf · -Inf 차단 (정상 momentum 수치 아님).
        # bool 제외 float(score_value) 는 안전 (int → float 변환은 항상 유한).
        if not math.isfinite(float(score_value)):
            return "candidate_score_value_not_finite"
    return None


def validate_artifact(data: Any) -> tuple[bool, Optional[str], dict[str, Any]]:
    """(valid, error_reason, meta) 반환.

    meta: {status, asof, candidate_count}. 실패 시에도 부분 meta 포함.

    검증자 REJECTED r2 재정정:
    - refresh_status allowlist 를 Publication + Runtime 이 공유.
    - candidate 개별 shape 도 검증 (Runtime 이 파싱 중 KeyError 나지 않도록).
    """
    meta: dict[str, Any] = {"status": "", "asof": "", "candidate_count": 0}
    if not isinstance(data, dict):
        return False, "artifact_not_dict", meta
    if data.get("mode") != "universe":
        return False, "artifact_mode_mismatch", meta
    asof = data.get("asof")
    if not isinstance(asof, str) or not asof.strip():
        return False, "artifact_asof_missing", meta
    meta["asof"] = asof
    # 검증자 REJECTED r6 재정정: 실제 날짜 형식 (YYYY-MM-DD) + 실제 존재하는 날짜.
    # producer canonical 계약 (universe_seed._ASOF_PATTERN + date.fromisoformat).
    if not _ASOF_PATTERN.match(asof):
        return False, "artifact_asof_format_invalid", meta
    try:
        date.fromisoformat(asof)
    except ValueError:
        return False, "artifact_asof_not_a_real_date", meta
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return False, "artifact_summary_missing", meta
    status = summary.get("refresh_status") or ""
    meta["status"] = status
    if status not in ALLOWED_REFRESH_STATUSES:
        if status == "failed":
            return False, "artifact_refresh_status_failed", meta
        return False, "artifact_refresh_status_unknown", meta
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        return False, "artifact_candidates_missing", meta
    meta["candidate_count"] = len(candidates)
    # 각 candidate 개별 shape 검증 (하나라도 손상되면 artifact 전체 unavailable).
    for i, c in enumerate(candidates):
        cand_reason = _validate_candidate_shape(c)
        if cand_reason is not None:
            return False, f"{cand_reason}:index={i}", meta
    # 검증자 REJECTED r6 재정정: producer canonical 계약 완전 교차 검증.
    # `universe_refresh.determine_refresh_status` (scored 개수 기반 결정):
    #   - "ok"      : 모든 candidate 가 is_scored=True (scored == total)
    #   - "partial" : 일부만 scored (0 < scored < total)
    #   - "failed"  : scored 0건 (이미 status 검증에서 차단)
    # 아래 3가지 위반을 모두 Publication 에서 차단 → Runtime 판정 차이 재현 불가.
    if candidates:
        total = len(candidates)
        scored_count = sum(
            1
            for c in candidates
            if isinstance(c, dict)
            and isinstance((c.get("score_result") or {}).get("is_scored"), bool)
            and c["score_result"]["is_scored"] is True
        )
        # (1) ok/partial + scored=0 → 위반.
        if scored_count == 0:
            return False, "artifact_status_scored_inconsistency", meta
        # (2) "ok" 인데 일부만 scored → 위반.
        if status == "ok" and scored_count != total:
            return False, "artifact_status_ok_but_partial_scored", meta
        # (3) "partial" 인데 전부 scored → 위반.
        if status == "partial" and scored_count == total:
            return False, "artifact_status_partial_but_all_scored", meta
    return True, None, meta
