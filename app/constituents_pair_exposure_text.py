"""판단 근거 미리보기 '[구성종목 비교]' 묶음 글(POC6-31 STEP 5 · PLAN C26 · 판정 Q14 (b)).

`app/constituents_pair_exposure.build` 결과 → 줄(금액 없음 · 수치 · 날짜 · 확인 범위 · 저장 원문에서 다시 읽힘).
화면 표시(`frontend/lib/pairExposureText.ts`)와 같은 낱말 · 같은 반올림(소수 둘째 · 셋째 자리 5 이상 올림).
계산 모듈이 KS-10(백엔드 핵심 모듈 650줄)을 넘지 않게 글 조립만 따로 둔다.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional

from app.constituents_pair_exposure import (
    PAIR_FOUND,
    PAIR_WEIGHT_UNKNOWN,
    PAIR_NO_DATA,
    PAIR_NOT_APPLICABLE,
    PAIR_OUT_OF_RANGE,
    PAIR_SELF,
    PAIR_UNCONFIRMED,
    PAIR_ZERO,
    R_STEP,
    STATE_CONFIRMED,
    STATE_UNCONFIRMED,
    STATUS_HOLDINGS_UNREADABLE,
    STATUS_NO_ETF_LIST,
    STATUS_NO_HOLDINGS,
    STATUS_NO_WEIGHT_BASIS,
    USE_DIRECT,
    USE_NO_DATA,
    USE_NO_WEIGHT,
    USE_OTHER_DATE,
    USE_SUM,
    USE_UNCONFIRMED,
    WEIGHT_UNKNOWN,
    dstr,
)

SECTION_TITLE = "구성종목 비교"
UNBUILT_LINE = "구성종목 비교를 만들지 못했습니다 — [다시 생성]을 누르세요(겹침 없음이라는 뜻 아님)."
AFTER_ADD_LINE = "후보를 더 샀을 때의 예상 비중은 추가 금액과 자금 출처가 있어야 계산할 수 있습니다(지금 확인된 노출만 적음)."
NO_ETF_LIST_LINE = "확인 불가 — ETF 목록을 읽지 못해 보유 ETF 와 직접 보유를 가를 수 없습니다(겹침 없음이라는 뜻 아님)."
NO_HOLDINGS_LINE = "등록 보유 없음 — 내 보유 노출을 계산할 대상이 없습니다."
HOLDINGS_UNREADABLE_LINE = (
    "보유 목록을 읽지 못했습니다 — 내 보유 노출은 확인 불가(겹침 없음이라는 뜻 아님) · "
    "후보와 고른 보유의 편입 비중만 적음."
)
NO_WEIGHT_BASIS_LINE = (
    "비중 확인 불가 — 시세가 확인된 보유가 없어 분모(현금 제외 보유 평가액)를 정하지 못했습니다 · "
    "후보와 고른 보유의 편입 비중만 적음."
)
_PAIR_TEXT = {
    PAIR_ZERO: "0(확인)",
    PAIR_SELF: "이 주식 자체",
    PAIR_NOT_APPLICABLE: "해당 없음(개별 주식)",
    PAIR_NO_DATA: "구성 자료 없음",
    PAIR_WEIGHT_UNKNOWN: "편입 · 비중 확인 불가",
}
# 짝 칸 중 고른 보유의 구성 자료에서 나온 값(구성일이 후보와 다르면 참고 표시를 붙임 · 검증자 r1 F12)
_FROM_HOLDING_SNAPSHOT = (PAIR_FOUND, PAIR_ZERO, PAIR_OUT_OF_RANGE, PAIR_WEIGHT_UNKNOWN)
REF_MARK = "(구성일 다름 · 참고)"


def pct2(s: Optional[str]) -> str:
    """계산 글(%) → 소수 둘째 자리 표시(반올림 · 화면과 같은 규칙)."""
    if s is None:
        return "확인 불가"
    return f"{Decimal(s).quantize(R_STEP, rounding=ROUND_HALF_UP)}%"


def wtext(s: Optional[str]) -> str:
    """원천 비중 글 → 표시(반올림 없음 · 계산에 쓴 자릿수 그대로 · 소수 둘째 자리까지는 0 을 채움)."""
    if s is None:
        return "확인 불가"
    head, _, tail = s.partition(".")
    return f"{head}.{tail.ljust(2, '0')}%"


def pair_text(p: Mapping[str, Any]) -> str:
    st = p["state"]
    if st == PAIR_FOUND:
        return wtext(p["weight"])
    if st == PAIR_OUT_OF_RANGE:
        return f"저장 범위에서 미확인({p['stored_rows']}행 · 저장 행 합 {pct2(p['stored_sum'])})"
    if st == PAIR_UNCONFIRMED:
        return f"원천 기준일 미확인({p['asof']} 보존 자료)"
    return _PAIR_TEXT.get(st, "확인 불가")


def held_text(body: Mapping[str, Any]) -> Optional[str]:
    """후보를 이미 보유 중일 때 — 노출 합계에 들어갔는지와 그 사유(쓰임별 · 검토 지적 backend#2)."""
    c = body["candidate"]
    if not c["held"]:
        return None
    weight = (
        f"(평가 비중 {pct2(c['held_weight'])})" if c["held_weight"] is not None else ""
    )
    why = {
        USE_SUM: "그 구성도 노출 합계에 들어 있음",
        USE_OTHER_DATE: f"후보 구성일 {c['asof']}이 노출 합계일과 달라 합계 밖(다른 구성일 참고)",
        USE_NO_WEIGHT: "시세 미확인이라 분모 밖 — 합계에 넣지 않음",
        USE_UNCONFIRMED: "원천 기준일 미확인이라 합계 밖",
        USE_NO_DATA: "구성 자료 없음이라 합계 밖",
        USE_DIRECT: "ETF 목록에 없어 직접 보유로 셈",
    }.get(c["held_use"], "합계 반영 여부 확인 불가")
    return f"후보를 이미 보유 중{weight} — {why}"


def _scope_line(sc: Mapping[str, Any]) -> str:
    miss = [
        (sc["other_date"], "다른 구성일"),
        (sc["unconfirmed"], "원천 기준일 미확인"),
        (sc["no_data"], "구성 자료 없음"),
    ]
    parts = [
        f"{label} {m['count']}개 {pct2(m['weight'])}" for m, label in miss if m["count"]
    ]
    missing = sum((Decimal(m["weight"]) for m, _ in miss), Decimal(0))
    line = (
        f"확인 범위: 보유 ETF {sc['included']['count']}개(평가액의 {pct2(sc['included']['weight'])}) + "
        f"직접 보유 {sc['direct']['count']}개({pct2(sc['direct']['weight'])}) 계산"
    )
    line += f" · 빠짐 {pct2(dstr(missing))}" + (
        f"({' · '.join(parts)})" if parts else ""
    )
    if sc["no_weight"]["count"]:
        line += (
            f" · 시세 미확인 {sc['no_weight']['count']}종목은 분모 밖(부분 평가액 기준)"
        )
    return line


def _holding_date_text(h: Mapping[str, Any], confirmed: Optional[str]) -> str:
    name = h["name"] or h["ticker"]
    if h["kind"] == "stock":
        # 그 주식 자체(짝 칸 '이 주식 자체')와 전체 보유에서 차지하는 평가 비중을 나눠 적는다(검토 지적 backend#3).
        own = pct2(h["weight"]) if h["weight"] is not None else "미확인"
        return f"고른 보유({name}) 개별 주식 · 전체 보유 평가 비중 {own}"
    if confirmed:
        return f"고른 보유({name}) 구성 {confirmed}"
    state = PAIR_UNCONFIRMED if h["state"] == STATE_UNCONFIRMED else PAIR_NO_DATA
    return f"고른 보유({name}) 구성 {pair_text({'state': state, 'asof': h['asof']})}"


def pair_dates_differ(body: Mapping[str, Any]) -> bool:
    """후보 구성일과 고른 보유 구성일이 둘 다 있고 다르면 True — 짝 비중은 나란히 읽는 참고(검증자 r1 F12)."""
    d = body["dates"]
    return bool(d["candidate"] and d["holding"] and d["candidate"] != d["holding"])


def date_line(body: Mapping[str, Any]) -> str:
    """[구성종목 비교] 기준일 줄 — 미리보기 원문과 화면(GET 응답 `date_line`)이 같은 글을 쓴다(검증자 r1 B-6).

    보유 목록을 못 읽어도 후보 · 고른 보유 구성일은 적는다(검증자 r1 F13).
    """
    d, h, b = body["dates"], body.get("holding"), body.get("basis") or {}
    who = "고른 보유 없음" if h is None else _holding_date_text(h, d["holding"])
    head = f"기준일: 후보 구성 {d['candidate'] or '확인 불가'} · {who}"
    if body["status"] == STATUS_HOLDINGS_UNREADABLE:
        line = f"{head} · 노출 합계 확인 불가(보유 목록을 읽지 못함)"
    else:
        pd = b.get("price_date") or {}
        when = (
            pd.get("min")
            if pd.get("state") == "KNOWN" and pd.get("min") == pd.get("max")
            else (
                f"{pd.get('min')} ~ {pd.get('max')}"
                if pd.get("state") == "KNOWN"
                else "확인 불가"
            )
        )
        base = (
            "현금 제외 · 부분 평가액 기준"
            if b.get("partial")
            else "현금 제외 보유 평가액 기준"
        )
        line = (
            f"{head} · 노출 합계 {d['exposure'] or '구성 자료 없음(직접 보유만)'} · "
            f"보유 평가 {when} · {base}"
        )
        if d["candidate"] and d["exposure"] and d["candidate"] != d["exposure"]:
            line += " · 후보와 보유의 구성일이 달라 나란히 읽는 참고 수치"
    if pair_dates_differ(body):
        line += f" · 고른 보유 비중은 구성일이 달라 나란히 읽는 참고 수치{REF_MARK}"
    return line


def unknown_note(ex: Optional[Mapping[str, Any]]) -> Optional[str]:
    """노출 합계에서 빠진 ETF 를 사유별로(저장 범위 밖 미확인 · 편입 비중 확인 불가) — 미리보기 원문과 화면(GET 응답
    `stock_notes`)이 같은 글을 쓴다(검증자 STEP 4~5 r2 F14 · 서버가 나눈 사유를 한 가지로 적지 않음). 빠진 ETF 가 없으면 None.
    """
    if not ex or not ex["unknown"]:
        return None
    groups = (
        (
            "저장 범위 밖 미확인",
            [u for u in ex["unknown"] if u["range"] != WEIGHT_UNKNOWN],
        ),
        (
            "편입 비중 확인 불가",
            [u for u in ex["unknown"] if u["range"] == WEIGHT_UNKNOWN],
        ),
    )
    parts = []
    for label, us in groups:
        if us:
            w = dstr(sum((Decimal(u["holding_weight"]) for u in us), Decimal(0)))
            parts.append(f"{label} ETF {len(us)}개 · 평가액 {pct2(w)}")
    return " · ".join(parts)


def _stock_line(s: Mapping[str, Any], ref: bool) -> str:
    line = f"{s['name']}: 후보 {wtext(s['candidate_weight'])}"
    if s["pair"] is not None:
        line += f" · 고른 보유 {pair_text(s['pair'])}"
        if ref and s["pair"]["state"] in _FROM_HOLDING_SNAPSHOT:
            line += REF_MARK
    ex = s["exposure"]
    if ex is None:
        return line + " · 내 보유 전체 비중 확인 불가"
    if ex["value"] is None:
        # 확인한 부분이 하나도 없음 — 0.00% 로 적지 않는다(검증자 r1 F10)
        line += " · 내 보유 전체 확인 불가(확인한 구성 없음)"
    else:
        line += f" · 내 보유 전체 {pct2(ex['value'])}"
    note = unknown_note(ex)
    if note:
        line += f"({note})"
    return line


def preview_lines(body: Optional[Mapping[str, Any]]) -> list[str]:
    """`build` 결과 → 미리보기 묶음 줄."""
    if body is None:
        return [UNBUILT_LINE]
    st = body["status"]
    if st == STATUS_NO_ETF_LIST:
        return [NO_ETF_LIST_LINE]
    if st == STATUS_NO_HOLDINGS:
        return [NO_HOLDINGS_LINE]
    if st == STATUS_HOLDINGS_UNREADABLE:
        lines = [date_line(body), HOLDINGS_UNREADABLE_LINE]
    elif st == STATUS_NO_WEIGHT_BASIS:
        lines = [date_line(body), NO_WEIGHT_BASIS_LINE]
    else:
        lines = [date_line(body), _scope_line(body["scope"])]
    cand = body["candidate"]
    if cand["state"] != STATE_CONFIRMED:
        why = (
            f"원천 기준일 미확인({cand['asof']} 보존 자료)"
            if cand["state"] == STATE_UNCONFIRMED
            else "구성 자료 없음"
        )
        return [*lines, f"후보 구성: {why} — 비교하지 않음(겹침 없음이라는 뜻 아님)."]
    held = held_text(body)
    if held:
        lines.append(held)
    ref = pair_dates_differ(body)
    lines.extend(_stock_line(s, ref) for s in body["stocks"])
    if not body["stocks"]:
        lines.append(
            "후보 상위 10행에 식별 가능한 주식이 없습니다(현금 · 채권 · 파생 · ETF · 종류 미확인 가림)."
        )
    elif body["candidate_non_stock_rows"]:
        lines.append(
            f"후보 상위 10행 중 주식이 아닌 · 종류 미확인 행 {body['candidate_non_stock_rows']}개는 뺌"
        )
    refs = [(s["name"], r) for s in body["stocks"] for r in s["reference"]]
    if refs:
        lines.append(
            "다른 구성일 참고(합계 밖): "
            + " · ".join(
                f"{r['name'] or r['ticker']} {r['asof']} — {n} "
                + (
                    wtext(r["constituent_weight"])
                    if r["constituent_weight"] is not None
                    else "비중 확인 불가"
                )
                for n, r in refs
            )
        )
    lines.append(AFTER_ADD_LINE)
    return lines
