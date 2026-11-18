"""POC6-32 V2 — 보유 ETF 겹침 카드의 비교 기준 · 실제 기간(판정 V2 Q9 (a) 보완 · PLAN V2 §9 I-22).

`GET /holdings/market-evidence/latest` 의 겹침 비교는 넘겨받은 목록이 아니라 서버 `compute_topn` 결과(1개월 · 상위
10개 · 제외 4종 기본값)와 대조한다. 카드가 '1개월 상위 10개 기준'과 실제 기간을 적을 수 있게 그 결과에서 기준 ·
시작일 범위 · 끝일을 꺼낸다. 시작일은 ETF 마다 '끝일 − 기간 일수 이후 첫 저장일'이라 다를 수 있어 최소 ~ 최대로 둔다.
이미 손에 있는 응답만 쓴다(새 읽기 · 계산 규칙 없음). `holdings_market_evidence.py`(근접선 초과)는 건드리지 않는다.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


def topn_basis(topn_payload: Mapping[str, Any]) -> dict[str, Any]:
    """{basis, n, count, filters, start_min, start_max, end} — 결과가 없으면 날짜 칸은 None(지어 내지 않음).

    끝 = 후보 기간 끝 중 가장 늦은 날(기존 계산은 늘 시장 저장 최신일 하나) · 후보가 없으면 응답 기준일(`asof`)."""
    cands = [
        c for c in (topn_payload.get("candidates") or []) if isinstance(c, Mapping)
    ]
    starts = sorted(
        str(c["selected_basis_start_date"])
        for c in cands
        if c.get("selected_basis_start_date")
    )
    ends = sorted(
        str(c["selected_basis_end_date"])
        for c in cands
        if c.get("selected_basis_end_date")
    )
    end: Optional[str] = ends[-1] if ends else topn_payload.get("asof")
    filters = topn_payload.get("filters")
    return {
        "basis": topn_payload.get("basis"),
        "n": topn_payload.get("n"),
        "count": len(cands),
        "filters": dict(filters) if isinstance(filters, Mapping) else None,
        "start_min": starts[0] if starts else None,
        "start_max": starts[-1] if starts else None,
        "end": end,
    }
