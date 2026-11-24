"""이번 주 한 장의 글 — 먼저 볼 이유 · 상세 첫 문장(R2) · 어디까지 말할 수 있나 · 다음 확인 · AI 비교 복사문.

```text
복사문  첫머리 = market_evidence_text.LATEST_CHECK(기존 '최신 공개 자료 확인' 문단 그대로 · 판정 Q7)
        담는 것 = 후보 · KODEX 200 공개 수치 · 날짜 · 근거 · 자료 상태 · 개인을 드러내지 않는 겹침 확인 범위
        빼는 것 = 형수님 보유 금액 · 비중 · 종목 · 수량 · 건수(로컬 상세에만)
```
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, Optional, Sequence

from app.market_evidence_text import LATEST_CHECK

WEEKDAY = "월화수목금토일"
# 끝일 가격 상태(마감 뒤 저장이 아닌 경우) — 장중과 저장 시각 불명을 구분(검증자 r1 F3)
STATE_TEXT = {
    "intraday": "끝일 가격 장중 저장",
    "unknown": "끝일 가격 저장 시각 확인 불가",
}
# 네 주 오름 미확인 사유
WEEK_GAP_TEXT = {
    "no_price": "주 마감 가격 없음",
    "intraday_close": "주 마감값이 장중 저장",
    "unknown_close": "주 마감값의 저장 시각 불명",
    "weekly_unavailable": "주 마감 날짜를 정하지 못함",
}
# 네 주 끝일을 앞으로 옮긴 사유(건너뛴 주) · 네 주 날짜를 정하지 못한 사유(반박 m5)
SKIP_TEXT = {
    "week_unfinished": "그 주 거래가 아직 끝나지 않음",
    "schedule_gap": "그 주 마지막 거래일({scheduled}) KODEX 200 가격이 없음",
    "bench_not_after_close": "그날 KODEX 200 가격이 마감 뒤 저장이 아님",
}
GAP_TEXT = {
    "no_finished_week": "거래를 마친 주를 찾지 못함",
    "too_few_weeks": "다섯 주 자료가 모자람",
    "schedule_gap": "{week_last}가 있는 주의 마지막 거래일({scheduled}) KODEX 200 가격이 없음",
    "missing_week": "{scheduled}가 있는 주의 KODEX 200 가격이 없음",
}
FILTERS_TEXT = "인버스 · 레버리지 · 합성 · 선물 제외"


def md(d: Optional[str]) -> str:
    return "확인 불가" if not d else f"{int(d[5:7])}/{int(d[8:10])}"


def kday(d: str) -> str:
    return f"{int(d[5:7])}월 {int(d[8:10])}일"


def wday(d: str) -> str:
    return WEEKDAY[dt.date.fromisoformat(d).weekday()]


def pct(v: Optional[float]) -> str:
    return "확인 불가" if v is None else f"{v:+.2f}%"


def chg(v: Optional[float]) -> str:
    """구간 변화율(비율) → % 글."""
    return "미확인" if v is None else f"{v * 100:+.2f}%"


def _fill(text: str, rec: Mapping[str, Any]) -> str:
    return text.format(**{k: md(rec.get(k)) for k in ("week_last", "scheduled")})


def week_note(wk: Mapping[str, Any], end: str) -> Optional[str]:
    """네 주 날짜 설명 — 끝일과 다르면 실제 네 주 끝일 · 건너뛴 주와 사유 · 정하지 못했으면 그 사유(반박 m5)."""
    skipped = [
        f"{md(s.get('week_last'))}가 있는 주: {_fill(SKIP_TEXT.get(s.get('why'), '사유 불명'), s)}"
        for s in wk.get("skipped") or []
    ]
    if not wk.get("dates"):
        gap = wk.get("gap") or {}
        why = _fill(GAP_TEXT.get(gap.get("why"), "사유 불명"), gap)
        return " · ".join(
            [
                f"네 주 날짜를 정하지 못했습니다({why}) — 모든 후보의 오른 주는 미확인입니다.",
                *skipped,
            ]
        )
    if not wk.get("mid_week") and not skipped:
        return None
    head = (
        f"1개월 끝일({md(end)})과 네 주 끝일({md(wk['w0'])})이 다릅니다 — 네 주는 {md(wk['w0'])} 마감까지입니다."
        if wk.get("mid_week")
        else f"네 주는 {md(wk['w0'])} 마감까지입니다."
    )
    return " ".join([head, *(f"({x})" for x in skipped)])


def _verb(v: float) -> str:
    if v > 0:
        return f"{abs(v):.2f}% 올랐습니다"
    if v < 0:
        return f"{abs(v):.2f}% 내렸습니다"
    return "변화가 없었습니다(0.00%)"


def lead(item: Mapping[str, Any], kodex: Mapping[str, Any]) -> str:
    """상세 첫 문장 — 실제 움직임과 같은 기간 KODEX 200(R2 예시 꼴)."""
    om = item["one_month"]
    k = kodex.get("one_month")
    head = f"{kday(om['start'])}부터 {kday(om['end'])}까지 {item['name']}의 가격은 {_verb(om['value'])}."
    if k is None:
        return head + " 같은 기간 KODEX 200 값은 확인하지 못했습니다."
    return head + f" 같은 기간 국내 시장 비교 기준인 KODEX 200은 {_verb(k['value'])}."


def three_line(item: Mapping[str, Any], kodex: Mapping[str, Any]) -> str:
    t = item.get("three_month")
    if t is None:
        return "3개월 값이 없습니다(3개월 전 가격이 저장돼 있지 않음)."
    if t["status"] == "kodex_window_unknown":
        return (
            f"3개월 {pct(t['value'])}(실제 {md(t['start'])} → {md(t['end'])}) — KODEX 200 의 3개월 기간을 "
            "정할 수 없어 같은 기간으로 비교하지 못했습니다."
        )
    if t["status"] != "ok":
        return (
            f"3개월 {pct(t['value'])}(실제 {md(t['start'])} → {md(t['end'])}) — KODEX 200 과 기간이 달라 "
            "같은 기간으로 비교할 수 없습니다."
        )
    k = kodex.get("three_month")
    tail = "" if k is None else f" 같은 기간 KODEX 200은 {_verb(k['value'])}."
    return f"{kday(t['start'])}부터 {kday(t['end'])}까지 {_verb(t['value'])}.{tail}"


def reasons(data: Mapping[str, Any]) -> dict[str, Any]:
    """② 먼저 볼 세 후보의 이유 한 문장씩 + 수익률 순위와 다른 점."""
    by = {it["ticker"]: it for it in data["items"]}
    a, b = data["picks_a"], data["picks_b"]
    if not b:
        return {
            "picks": [],
            "diff": "공통 후보군이 3개보다 적어 먼저 볼 후보를 고르지 못했습니다(근거 부족).",
        }
    top = by[a[0]]
    picks = []
    for code in b:
        it = by[code]
        up = it["up"]
        head = (
            "지난 4주에 매주 올랐습니다."
            if up == 4
            else f"지난 4주 중 {up}주 올랐습니다."
        )
        if it["one_month"]["value"] <= 0:
            tail = " 1개월이 플러스인 ETF 가 모자라 1개월 순위로 채운 자리입니다."
        elif code in a:
            tail = f" 1개월 수익률 순위도 {it['rank']}위입니다."
        elif it["one_month"]["value"] < top["one_month"]["value"]:
            tail = f" 1개월 수익률은 {top['name']}보다 낮습니다."
        else:
            tail = f" 1개월 수익률은 {top['name']}와(과) 같습니다."
        picks.append({"ticker": code, "text": head + tail})
    if set(a) == set(b):
        diff = "두 기준이 같은 세 ETF 를 골랐습니다(순서만 다를 수 있음)."
    else:
        names = " · ".join(by[c]["name"] for c in a)
        parts = [f"수익률 순위로 먼저 보던 후보는 {names} 입니다."]
        for c in a:
            if c not in b:
                it = by[c]
                parts.append(
                    f"{it['name']}: 1개월 {it['rank']}위({pct(it['one_month']['value'])})지만 "
                    f"네 주 중 {it['up']}주만 올랐습니다."
                )
        new = " · ".join(by[c]["name"] for c in b if c not in a)
        parts.append(f"그래서 오른 주가 더 많은 후보({new})를 앞세웠습니다.")
        diff = " ".join(parts)
    dropped_top = [it for it in data["items"] if it["rank"] <= 3 and it["up"] is None]
    if dropped_top:
        diff += (
            f" 1개월 상위 3 중 {len(dropped_top)}개는 주 마감값을 확인하지 못해 비교에서 빠졌습니다"
            "(오른 횟수 미확인)."
        )
    return {"picks": picks, "diff": diff}


def _holdings_unconfirmed(det: Optional[Mapping[str, Any]]) -> Optional[bool]:
    """보유 쪽 구성 미확인 부분이 있나(겹침 계산 숫자로 가름 · 글에는 숫자를 쓰지 않음)."""
    ov = (det or {}).get("overlap") or {}
    nums = ov.get("numbers")
    if not nums or nums.get("full_confirmed") is None:
        return None
    no_weight = (det or {}).get("no_weight") or 0
    return float(nums["full_confirmed"]) < 100.0 or no_weight > 0


def scope_lines(item: Mapping[str, Any]) -> list[str]:
    """어디까지 말할 수 있나 — 가격 · 구성 · 보유 쪽 확인 범위."""
    out = ["가격 움직임(1 · 3개월 · 네 주)은 위 기간으로 말할 수 있습니다."]
    det = item.get("detail") or {}
    cons = det.get("constituents") or {}
    st = cons.get("state")
    if det.get("error") or st is None or st == "error":
        out.append("구성 · 겹침 자료를 읽지 못해 내 보유와의 겹침은 말할 수 없습니다.")
    elif st == "full":
        out.append("구성은 전체를 확인했습니다.")
    elif st == "top_rows":
        out.append(
            f"구성은 상위 {cons.get('stored_rows')}행만 있어, 내 보유와 얼마나 겹치는지는 일부만 말할 수 있습니다."
        )
    else:
        out.append(
            f"구성 자료가 {cons.get('state_label')} 상태라 내 보유와의 겹침은 말할 수 없습니다."
        )
    if _holdings_unconfirmed(det):
        out.append(
            "내 보유 ETF 일부도 구성을 확인하지 못해 '겹침 없음'이라고 말할 수 없습니다."
        )
    if item.get("state") == "intraday":
        out.append(
            "끝일 가격은 장중 저장값이라 마감값이 아닙니다 — 1개월 값이 바뀔 수 있습니다."
        )
    elif item.get("state") != "after_close":
        out.append("끝일 가격의 저장 시각을 확인할 수 없어 마감값인지 모릅니다.")
    if item.get("week_gap") in WEEK_GAP_TEXT:
        out.append(
            f"네 주 오름은 확인하지 못했습니다 — {WEEK_GAP_TEXT[item['week_gap']]}."
        )
    return out


def next_check(item: Mapping[str, Any]) -> str:
    """다음 확인 한 가지와 이유(정해진 순서)."""
    det = item.get("detail") or {}
    st = (det.get("constituents") or {}).get("state")
    name = item["name"]
    if det.get("error") or st == "error":
        return f"{name}의 구성 자료 다시 읽기 — 이번에 읽지 못해 내 보유와의 겹침을 말할 수 없었기 때문입니다."
    if item.get("state") == "intraday":
        return f"{name}의 마감 뒤 종가 — 지금 값은 장중 저장값이라 1개월 움직임이 바뀔 수 있기 때문입니다."
    if item.get("state") != "after_close":
        return f"{name}의 끝일 가격 저장 시각 — 마감값인지 확인할 수 없기 때문입니다."
    if st != "full":
        return f"{name}의 전체 구성 — 내 보유와 같은 주식을 많이 담았다면 새로 담아도 위험이 분산되지 않기 때문입니다."
    if _holdings_unconfirmed(det):
        return "내 보유 ETF 의 전체 구성 — 겹침을 끝까지 확인하려면 보유 쪽 구성도 있어야 하기 때문입니다."
    if (item.get("three_month") or {}).get("status") != "ok":
        return f"{name}의 3개월 흐름 — 기간이 달라 같은 기간 비교를 하지 못했기 때문입니다."
    return (
        f"{name}의 총보수 · 추적 차이(같은 기초지수를 따르는 다른 ETF 와 비교) — 같은 지수면 비용이 낮은 쪽이 "
        "유리하기 때문입니다."
    )


def _copy_item(it: Mapping[str, Any]) -> str:
    cons = ((it.get("detail") or {}).get("constituents")) or {}
    parts = [
        f"1개월 {pct(it['one_month']['value'])}({it['rank']}위)",
    ]
    t = it.get("three_month")
    if t is not None:
        parts.append(
            f"3개월 {pct(t['value'])}"
            + (
                ""
                if t["status"] == "ok"
                else f"(기간 다름 {md(t['start'])} → {md(t['end'])})"
            )
        )
    if it["up"] is None:
        parts.append(
            f"오른 주 미확인({WEEK_GAP_TEXT.get(it.get('week_gap'), '주 마감값 미확인')})"
        )
    else:
        parts.append(
            f"오른 주 {it['up']}번(" + " / ".join(chg(c) for c in it["changes"]) + ")"
        )
    if cons.get("state_label"):
        parts.append(f"구성 {cons['state_label']}({md(cons.get('asof'))})")
    if it.get("state") in STATE_TEXT:
        parts.append(STATE_TEXT[it["state"]])
    return f"- {it['name']}({it['ticker']}): " + " · ".join(parts)


def _scope_line(det: Optional[Mapping[str, Any]]) -> str:
    unconf = _holdings_unconfirmed(det)
    if unconf is None:
        return "내 보유와의 겹침은 확인하지 못함"
    if unconf:
        return "확보된 구성 범위에서만 확인 · 내 보유 쪽에도 구성을 확인하지 못한 부분이 있어 '겹침 없음'이 아님"
    return "확보된 구성 범위에서 확인 · 내 보유 쪽 구성은 모두 확인됨"


def copy_head(data: Mapping[str, Any]) -> str:
    """복사문 공통 부분 — 최신 확인 문단 · 범위 · 기간 · 두 기준 후보(고른 후보와 무관)."""
    by = {it["ticker"]: it for it in data["items"]}
    wk = data["weekly"]
    k = data["kodex"]
    end = data["end"]
    om = data["windows"]["one_month"]
    lines = [
        LATEST_CHECK,
        "",
        f"[주간 ETF 비교 묶음 · 1개월 끝일 {md(end)}({wday(end)}) · "
        "개인 보유 자료(금액 · 비중 · 종목 · 수량 · 건수) 없음]",
        f"비교 범위: {FILTERS_TEXT} ETF {data['counts']['population']}개 · 오른 횟수 미확인 "
        f"{data['up_distribution']['none']}개",
        f"기간: 1개월 {md(om[0])} → {md(om[1])} · 네 주 "
        + (" → ".join(md(d) for d in wk["dates"]) if wk["dates"] else "확인 불가")
        + (
            f" · 주중 참고(네 주 끝일 {md(wk['w0'])} · 1개월 끝일과 다름)"
            if wk.get("mid_week")
            else ""
        )
        + f" · 비교 기준 KODEX 200(1개월 {pct((k.get('one_month') or {}).get('value'))} · "
        f"3개월 {pct((k.get('three_month') or {}).get('value'))})",
        "",
        "[연구 기준이 먼저 본 3개] 1개월 플러스 중 오른 주가 많은 순",
        *[_copy_item(by[c]) for c in data["picks_b"]],
        "[수익률 순위 상위 3개(주 마감값이 확인된 후보 중)]",
        *[_copy_item(by[c]) for c in data["picks_a"]],
    ]
    return "\n".join(lines) + "\n"


def copy_tail(data: Mapping[str, Any], selected: Optional[str] = None) -> str:
    """고른 후보에 따라 달라지는 부분 — [고른 후보] 줄 · 그 후보의 겹침 확인 범위 · 질문 견본."""
    by = {it["ticker"]: it for it in data["items"]}
    picks = set(data["picks_a"]) | set(data["picks_b"])
    lines: list[str] = []
    if selected and selected not in picks and selected in by:
        lines += ["[고른 후보]", _copy_item(by[selected])]
    target = by.get(selected) or (by[data["picks_b"][0]] if data["picks_b"] else None)
    if target is not None:
        scope = _scope_line(target.get("detail"))
        lines += ["", f"[내 보유와 겹침 확인 범위 — {target['name']}] {scope}", ""]
    if data["picks_b"] and data["picks_a"]:
        first_b = by[data["picks_b"][0]]["name"]
        first_a = by[data["picks_a"][0]]["name"]
        if first_b == first_a:
            q = f"연구 기준 1번({first_b})을 먼저 볼 이유가 다른 후보와 어떻게 다르고"
        else:
            q = f"연구 기준 1번({first_b})을 먼저 볼 이유가 수익률 순위 1번({first_a})과 어떻게 다르고"
        if target is not None and target["ticker"] not in picks:
            q += f", 고른 후보({target['name']})는 어디에 해당하며"
        lines.append(
            f"질문 견본: {q}, 내 보유와 겹치는지를 어디까지 확인했나요? 대상 · 기간 · 근거를 짚어 "
            "설명해 주세요. 매수 · 매도 결론은 쓰지 마세요."
        )
    return "\n".join(lines) + "\n"


def copy_text(data: Mapping[str, Any], selected: Optional[str] = None) -> str:
    """AI 비교 묶음(판정 Q7) — 개인 보유 자료 없음 · 공통 부분 + 고른 후보 부분."""
    return copy_head(data) + copy_tail(data, selected)


def picks_names(data: Mapping[str, Any], codes: Sequence[str]) -> list[str]:
    by = {it["ticker"]: it for it in data["items"]}
    return [by[c]["name"] for c in codes]
