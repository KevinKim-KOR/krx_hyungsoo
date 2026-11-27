"""같은 공식 기초지수 · 같은 구조 ETF 비교(PLAN §2-1 '확인된 근거' · 판정 Q3 · Q5).

```text
같은 지수  공식 기준정보(KRX 상장 ETF 표) '기초지수명' 이 같은 ETF
같은 구조  '추적배수' · '복제방법' 이 같고 이름의 환헤지 표시 '(H)' 여부가 같은 것만 — 다르면 구조 다름(사유)
비교 값    이번 주 후보 목록(같은 조회 조건 · 같은 1개월 공통 기간)에 있는 것만 — 없으면 '이번 조건 목록에 없음'
```
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

STRUCT_KEYS = ("추적배수", "복제방법")
HEDGE_MARK = "(H)"
_INDEX_SUFFIX = re.compile(r"\s*(index|지수)\s*$", re.IGNORECASE)


def index_label(name: str) -> str:
    """'Nifty 50 Index' → 'Nifty 50'(끝의 Index · 지수만 뗀다)."""
    return _INDEX_SUFFIX.sub("", name).strip() or name


def is_overseas(market: Optional[str]) -> bool:
    """기초시장분류 '해외' · '국내&해외' = 해외 몫 있음(원화 가격에 환율이 섞임)."""
    return "해외" in (market or "")


def _hedged(name: Optional[str]) -> bool:
    return HEDGE_MARK in (name or "")


def peers_of(
    ticker: str,
    official: Optional[Mapping[str, Mapping[str, str]]],
    items_by: Mapping[str, Mapping[str, Any]],
    names: Mapping[str, Optional[str]],
) -> dict[str, Any]:
    if official is None:  # 공식 기준정보를 읽지 못함 — '이 ETF 가 없다'와 구별
        return {"state": "official_unread"}
    me = official.get(ticker)
    idx = ((me or {}).get("기초지수명") or "").strip()
    if not me or not idx:
        return {"state": "no_official"}
    my_name = me.get("한글종목약명") or names.get(ticker)
    same: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for t in sorted(official):
        r = official[t]
        if t == ticker or (r.get("기초지수명") or "").strip() != idx:
            continue
        nm = r.get("한글종목약명") or names.get(t) or t
        diff = [str(r.get(k) or "?") for k in STRUCT_KEYS if r.get(k) != me.get(k)]
        if _hedged(nm) != _hedged(my_name):
            diff.append("환헤지 표시 다름")
        if diff:
            other.append({"ticker": t, "name": nm, "why": "structure", "diff": diff})
            continue
        it = items_by.get(t)
        if it is None:
            other.append({"ticker": t, "name": nm, "why": "not_in_population"})
            continue
        same.append(
            {
                "ticker": t,
                "name": nm,
                "fee": r.get("총보수"),
                "rank": it["rank"],
                "one_month": dict(it["one_month"]),
            }
        )
    return {
        "state": "ok",
        "index": idx,
        "label": index_label(idx),
        "market": me.get("기초시장분류"),
        "overseas": is_overseas(me.get("기초시장분류")),
        "structure": {k: me.get(k) for k in STRUCT_KEYS},
        "fee": me.get("총보수"),
        "same": same,
        "other": other,
    }
