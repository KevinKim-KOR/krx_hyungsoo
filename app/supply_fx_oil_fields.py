"""POC6-27 — `GET /market/flow-context` 의 구조 칸(화면 · 복사문이 문장을 해석하지 않게).

`supply_fx_oil_context` 가 문장을 만들 때 쓴 계산 값을 그대로 응답 칸으로 싣는다(새 계산 없음 · 문장 불변).
- `short_lines[].obs` = 단기 관측(가격: 그날 값 · 직전 대비 · 5개 관측 · 직전 20개 범위 이탈 / 수급: 그날 순매수 ·
  이전 20거래일 평균 규모 배수). 범위 이탈의 `bound` 는 **비교 기준값**(직전 20개 최저 · 최고)이고 그날 값이 아니다.
- `events[].key` = 자료 코드(kospi · usdkrw · wti · foreign · institution).
- `windows.foreign20` · `windows.r60` = 20 · 60거래일 창의 합 · 일평균 · 실제 시작 · 끝 날짜(원).
"""

from __future__ import annotations

from typing import Optional


def _change(c: Optional[dict]) -> Optional[dict]:
    if not c:
        return None
    return {"from_date": c["from_date"], "diff": c["diff"], "pct": c["pct"]}


def price_obs(st: dict, unit: str) -> dict:
    """`supply_fx_oil_calc.short_term` 결과 → 가격 단기 관측 칸."""
    r = st.get("range")
    return {
        "date": st["date"],
        "value": st["value"],
        "unit": unit,
        "d1": _change(st.get("d1")),
        "d5": _change(st.get("d5")),
        "range": (
            {"dir": r["dir"], "bound": r["bound"], "bound_date": r["bound_date"]}
            if r
            else None
        ),
    }


def flow_obs(f: dict) -> dict:
    """`supply_fx_oil_calc.flow_short` 결과 → 수급 단기 관측 칸(원)."""
    return {
        "date": f["date"],
        "value": f["value"],
        "unit": "원",
        "ratio": f.get("ratio"),
        "base_from": f.get("base_from"),
        "base_to": f.get("base_to"),
        "note": f.get("note"),
    }


def line(text: str, flags: list, key: str, obs: Optional[dict] = None) -> dict:
    """단기 줄(기존 text · flags 그대로 + 자료 코드 · 관측 칸)."""
    return {"text": text, "flags": flags, "key": key, "obs": obs}


def keyed(events: list[dict], key: str) -> list[dict]:
    """사건마다 자료 코드를 붙인다(기존 칸 · 문장 그대로)."""
    return [{**e, "key": key} for e in events]


def _win(w: Optional[dict], *, avg: bool) -> Optional[dict]:
    if not w:
        return None
    out = {"sum": w["sum"], "from": w["from"], "to": w["to"]}
    if avg:
        out["avg"] = w["avg"]
    return out


def windows_fields(w: Optional[dict]) -> dict:
    """`_windows` 의 창 계산 결과 → `foreign20` · `r60` 칸. 수급이 없으면(w=None) 둘 다 None."""
    if w is None:
        return {"foreign20": None, "r60": None}
    a, b = w["foreign"]["r20"], w["foreign"]["p20"]
    return {
        "foreign20": (
            {"recent": _win(a, avg=True), "previous": _win(b, avg=True)}
            if a and b
            else None
        ),
        "r60": {
            k: _win(w[k]["r60"], avg=False)
            for k in ("foreign", "individual", "institution")
        },
    }
