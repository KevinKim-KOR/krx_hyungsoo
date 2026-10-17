"""POC5-22 — PC 후보와 KODEX200 의 동일 기간 수익률 비교(설계 V1 §3 · PLAN 판정 2026-10-17).

후보 수익률이 실제로 쓴 시작 · 끝 저장 날짜(A · B)의 KODEX200(069500) 저장 종가로 KODEX200 수익률을
다시 계산해 뺀다.

- 같은 날짜만 쓴다: 전후 날짜 · 최근 날짜 · 보간으로 대신하지 않는다. 양수 · 유한 종가만 쓴다.
- 반올림 전 후보 수익률 − 반올림 전 KODEX200 수익률 → 마지막에 소수 4자리(후보 `return_pct` 와 같은 자리).
- 가격 조정 기준(자료원 · 저장 change)의 연속성은 검사하지 않는다(판정 Q1 (a)). `status = ok` 는 필요한
  날짜 · 유효 가격으로 산술 비교를 했다는 뜻이지, 가격 기준 연결을 확인했다는 뜻이 아니다.
- 순수 계산이다(조회 · 외부 호출 · 연구 모듈 import 없음). `compute_topn` 이 이미 읽은 069500 이력을
  `close_by_date` 로 한 번 정리해 넘긴다.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"

REASON_CANDIDATE_PERIOD_UNKNOWN = "candidate_period_unknown"
REASON_KODEX200_START_MISSING = "kodex200_start_price_missing"
REASON_KODEX200_END_MISSING = "kodex200_end_price_missing"

# 비교 대상 기간 — 후보의 1개월 · 3개월(설계 §2 · 6개월 이상 · 단기 흐름은 대상 아님).
PERIOD_KEYS = ("one_month", "three_month")


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def valid_close(v: Any) -> bool:
    """양수 · 유한 종가."""
    return _finite(v) and v > 0


def close_by_date(history: Sequence[tuple[str, Any]]) -> dict[str, float]:
    """(날짜, 종가) 이력 → {날짜: 종가} — 유효 종가만(같은 날짜 조회용 · 한 번 정리)."""
    return {d: float(c) for d, c in history if d and valid_close(c)}


def compare(
    candidate_return_pct: Optional[float],
    start_date: Optional[str],
    end_date: Optional[str],
    kodex200_close: Mapping[str, float],
) -> dict[str, Any]:
    """후보 한 기간의 동일 기간 비교 객체.

    `candidate_return_pct` 는 기존 계산의 반올림 전 값(단위 %). A · B 는 그 계산이 고른 저장 행 날짜.
    계산할 수 없으면 값은 None(0 · 다른 기간 차이로 채우지 않음)이고 사유를 남긴다.
    """
    cand = candidate_return_pct if _finite(candidate_return_pct) else None
    out: dict[str, Any] = {
        "status": STATUS_UNAVAILABLE,
        "reason": None,
        "start_date": start_date,
        "end_date": end_date,
        "candidate_return_pct": round(cand, 4) if cand is not None else None,
        "kodex200_return_pct": None,
        "diff_pctp": None,
    }
    if cand is None or not start_date or not end_date:
        out["reason"] = REASON_CANDIDATE_PERIOD_UNKNOWN
        return out
    k_start = kodex200_close.get(start_date)
    if not valid_close(k_start):
        out["reason"] = REASON_KODEX200_START_MISSING
        return out
    k_end = kodex200_close.get(end_date)
    if not valid_close(k_end):
        out["reason"] = REASON_KODEX200_END_MISSING
        return out
    kodex_pct = (k_end / k_start - 1.0) * 100.0
    out.update(
        status=STATUS_OK,
        kodex200_return_pct=round(kodex_pct, 4),
        diff_pctp=round(cand - kodex_pct, 4),
    )
    return out
