"""POC2 Cleanup — push_context 공통 formatting / helper 분리 (2026-06-14).

3-PUSH Message Text Runtime Evidence 반영 STEP 의 KS-10 trigger 해소를 위해
`app/push_context.py` 의 책임 일부를 본 모듈로 분리했다.

본 모듈은 다음 helper 만 제공한다 (산식 / 문구 / 데이터 계약 변경 0건):

- `_US_SECTOR_HINTS` — 미국 지수별 섹터 해석 hint 문장.
- `_has_data` — evidence/runtime snapshot dict 가 의미 있는 데이터를 갖는지.
- `_fmt_pct` — % 단위 값의 부호 포함 문자열.
- `_topn_candidates` — compute_topn payload 의 candidates / items 정규화.
- `_candidate_return_pct` — candidate 의 표시용 return_pct (%) (ratio→% 자동 변환).
- `_candidate_name` / `_candidate_ticker` — candidate 표시 helper.
"""

from __future__ import annotations

from typing import Any, Optional

_US_SECTOR_HINTS: dict[str, str] = {
    "SOX": "반도체 지수 강세는 국내 반도체/성장 ETF 해석에 참고 가능",
    "NASDAQ": "기술주 지수 강세는 국내 성장/IT 테마 해석에 참고 가능",
    "SPX": "S&P 500 흐름은 한국 시장 전반의 위험 선호 분위기에 참고 가능",
}


def _has_data(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict) or not snapshot:
        return False
    status = snapshot.get("status")
    if status in ("unavailable", "failed"):
        return False
    return True


def _fmt_pct(value: Any) -> Optional[str]:
    """이미 % 단위 (e.g. 0.85 = 0.85%) 인 값을 사람이 읽는 부호 포함 문자열로.

    주의: 본 헬퍼는 입력을 그대로 % 로 본다. compute_topn 의 selected_return_pct
    같이 ratio(0.15 = 15%) 일 수 있는 값은 호출자가 미리 변환하거나 별도 분기를
    사용해야 한다 (예: _candidate_return_pct).
    """
    if not isinstance(value, (int, float)):
        return None
    pct = float(value)
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def _topn_candidates(md: Any) -> list[dict[str, Any]]:
    """compute_topn payload 의 candidates 또는 items 를 정규화."""
    if not isinstance(md, dict):
        return []
    cand = md.get("candidates")
    if isinstance(cand, list) and cand:
        return [c for c in cand if isinstance(c, dict)]
    items = md.get("items")
    if isinstance(items, list) and items:
        return [c for c in items if isinstance(c, dict)]
    return []


def _candidate_return_pct(c: dict[str, Any]) -> Optional[float]:
    """candidate dict 에서 표시용 return_pct (%) 추출. ratio→% 자동 변환."""
    v = c.get("selected_return_pct")
    if not isinstance(v, (int, float)):
        v = c.get("return_pct")
    if not isinstance(v, (int, float)):
        return None
    return float(v) * 100.0 if abs(v) < 1.5 else float(v)


def _candidate_name(c: dict[str, Any]) -> str:
    return c.get("name") or c.get("ticker") or "-"


def _candidate_ticker(c: dict[str, Any]) -> Optional[str]:
    t = c.get("ticker")
    return t if isinstance(t, str) and t.strip() else None
