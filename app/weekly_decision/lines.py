"""첫 화면 줄 · AI에 확인할 것 · 복사문(PLAN §2 · 판정 §2 · Q3 · Q4 · Q5 · Q7).

```text
자료      evidence.compose(ctx, ticker) 가 만든 한 후보 자료(rv)를 문장으로 — 화면(page)과 복사문이 같은 함수를 씀
① 왜      선정 이유(조건 · 순위 · 실제 기간 · 같은 기간 KODEX 200 · 최근 네 주) · 확인된 근거 한 가지(같은 지수 상품)
          · 순위 흐름(복원) · 지난 검토와 비교(Q7 순서) · 자료 공백 한 가지
② AI      질문 한 가지 — 같은 지수 상품과 방향이 다름 → 해외 지수(현지 통화) → 국내 지수(지수 자체)
복사문    LATEST_CHECK 첫머리 → 이 묶음에 없는 값 · 저장 기준일(V2 Q3) → 검토 범위(Q4) → 근거 → AI에 확인할 것
          → 답하는 방식(Q1 · Q2) → 설계 §4 질문 원문으로 끝 · 공개 자료만(PLAN V2 판정 §1) — 개인 보유 항목 ·
          메모 원문 · 사용자가 고른 판단(직접 고른 값 · 내 판단 기록과 그 이유) · 로컬 기록 상태(읽기 실패 · 건수) 없음 ·
          당시 저장 기록 = 순위 · 1개월 값 · 기간(없으면 '인용할 기록 없음')
그 뒤     기간 미경과 행 = 이번 주 지금까지(그 마감 → 두 종목 공통 마감 종가 마지막 날 · 주 진행 중 · 예정 마감)
```
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Mapping, Optional

from app.market_evidence_text import LATEST_CHECK
from app.weekly_decision import conditions as C

SCREEN = "poc7_04_research"
MINUS = "−"
WD = "월화수목금토일"
DESIGN_QUESTION = (
    "이 ETF를 이번 주 계속 검토할지 보류할지 권고해 주세요. 우리 후보 기준에서 이번에 어떻게 보였는지와 이전 네 주에서 "
    "달라진 점을 근거로 들어 주세요. 같은 기간 비교에서 권고에 불리한 근거 한 가지와, 어떤 사실을 확인하면 결론이 달라질지 "
    "한 가지를 알려 주세요. 당시 저장 기록, 현재 기준 복원, 그 뒤 관측은 구분해서 인용해 주세요."
)
# V2 판정 2026-11-25 Q1 · Q2 — 결론 한 줄 → 핵심 요약 최대 세 줄 → 상세 근거와 출처
ANSWER_FORMAT = (
    "[답하는 방식] 아래 순서로 답해 주세요.",
    "1. 결론 한 줄 — '검토 계속' 또는 '보류' 중 하나. 판단에 중요한 근거가 부족하면 '보류(근거 부족)'과 "
    "필요한 확인 한 가지.",
    "2. 핵심 요약 최대 세 줄 — 판단에 쓴 근거 / 가장 중요한 반대 근거나 자료 공백 / 결론을 바꿀 확인 한 가지와 "
    "그 결과에 따라 어느 쪽으로 바뀌는지.",
    "3. 상세 근거와 출처.",
)
# Q3 — 이 묶음에 없는 값 뒤 · Q4 — 검토 범위(개인 계좌 정보 없음 · 겹침은 PC 화면에서 직접)
MISSING_TAIL = (
    "위 값을 공식 공개 자료에서 확인하면 출처 · 기준일과 함께 적어 이 묶음의 저장값과 구별해 주세요. "
    "확인이 어려우면 그 공백과 결론을 바꿀 확인 한 가지를 적고, 확인된 근거 범위에서 잠정 의견을 주세요."
)
SCOPE_TAIL = (
    "제 계좌 정보는 넣지 않았습니다 — 이미 가진 종목과 겹치는지는 제가 따로 봅니다."
)
RESTORE_LABEL = "현재 ETF 목록과 저장 가격으로 복원"
FILTER_NAMES = (
    ("inverse", "인버스"),
    ("leveraged", "레버리지"),
    ("synthetic", "합성"),
    ("futures", "선물"),
)
FILTER_LABEL = {f"exclude_{k}": n for k, n in FILTER_NAMES}
PRICE_STATE = {
    "after_close": "가격 마감 뒤 저장",
    "intraday": "장중 저장값(잠정)",
    "unknown": "가격 저장 시각 확인 필요",
}
SOURCE_LABEL = {
    "market_discovery": "「요즘 잘 오르는 ETF」(당시 화면 이름)",
    "today_weekly_review": "「주간 ETF 점검」",
    "holdings_compare_preview": "「보유와 비교」 판단 근거",
}
VERDICT_LABEL = {
    "useful": "쓸 만함",
    "needs_constituents": "구성 종목 필요",
    "needs_market_compare": "시장 비교 필요",
    "hold": "보류",
    "unrecorded": "미기록",
}
MY_VERDICT = {"continue": "검토 계속", "hold": "보류", "unrecorded": "미기록"}
WHY = {
    "not_listed": "현재 ETF 목록에 없음",
    "no_price": "그날까지 저장 가격 없음",
    "filter_excluded": "조회 조건에서 제외",
    "no_return": "1개월 수익률을 계산할 가격이 모자람",
    "no_common_period": "그날 KODEX 200 1개월 기간을 정할 수 없음",
    "end_differs": "그날 가격 없음",
    "start_differs": "1개월 시작일 가격 없음",
    "intraday_close": "장중 저장값",
    "unknown_close": "저장 시각 불명",
    "weekly_unavailable": "주 마감일을 정하지 못함",
    "no_schedule": "다음 주 거래일 없음",
    "no_new_day": "그 마감 뒤 저장한 거래일 자료 없음",
    "no_common_close": "두 종목 모두 마감 뒤 저장한 종가가 있는 날이 아직 없음",
    "no_base": "기준일 종가 없음",
    "no_prev_close": "직전 주 마감 종가 없음",
}


# --- 표기(화면 · 복사문 공통) ---


def md(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f"{x.month}/{x.day}"


def mdw(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f"{x.month}/{x.day}({WD[x.weekday()]})"


def sign_of(v: float, nd: int = 2) -> int:
    r = round(v, nd)
    return 1 if r > 0 else -1 if r < 0 else 0


def pct(v: float, nd: int = 2) -> str:
    s = sign_of(v, nd)
    return ("+" if s > 0 else MINUS if s < 0 else "") + f"{abs(round(v, nd)):.{nd}f}%"


def fee(v: Any) -> Optional[str]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f"{f:g}%" if math.isfinite(f) else None


def filter_parts(filters: Mapping[str, Any], basis: bool = True) -> list[str]:
    """조회 조건 글 조각(사실 하나에 하나) — 네 칸이 모두 불리언이면 'A · B 제외' · '제외 없음' ·
    아니면 칸마다 아는 만큼만(빠진 칸 = 저장 안 됨 · 형식이 틀린 칸 = 형식 오류 · '제외 없음'이라고
    단정하지 않음 · 검증 F19) · 지금 조건에 없는 칸도 밝힘. basis = 순위 기준('1개월 수익률')을 붙임 —
    「AI 투자 세션」 기록은 순위 기준이 저장되지 않아 붙이지 않는다(반박 검토)."""
    got = [(n, C.filter_value(filters, f"exclude_{k}")) for k, n in FILTER_NAMES]
    known = {f"exclude_{k}" for k, _ in FILTER_NAMES}
    extra = sorted(str(k) for k in filters if k not in known)
    ex = [n for n, v in got if v is True]
    if all(isinstance(v, bool) for _, v in got):
        parts = [" · ".join(ex) + " 제외" if ex else "제외 없음"]
    elif all(v is C.MISSING for _, v in got):
        parts = ["제외 조건 네 칸 저장 안 됨"]
    else:
        parts = [
            " · ".join(names) + tail
            for names, tail in (
                (ex, " 제외"),
                ([n for n, v in got if v is False], " 포함"),
                ([n for n, v in got if v is C.MISSING], " 제외 여부 저장 안 됨"),
                ([n for n, v in got if v is C.INVALID], " 제외 여부 형식 오류"),
                (
                    [n for n, v in got if v is C.CONFLICT],
                    " 제외 여부 값 충돌(두 번 저장)",
                ),
            )
            if names
        ]
    if extra:
        parts.append(f"지금 조건에 없는 칸 저장됨({' · '.join(extra)})")
    return (["1개월 수익률"] if basis else []) + parts


def filter_text(filters: Mapping[str, Any], basis: bool = True) -> str:
    return " · ".join(filter_parts(filters, basis))


def topic(word: str) -> str:
    """주제 조사 은/는 — 한글 · 숫자로 끝나면 받침으로 · 그 밖(영문)은 ' 지수는'."""
    ch = word.rstrip()[-1:]
    if "가" <= ch <= "힣":
        return "은" if (ord(ch) - 0xAC00) % 28 else "는"
    if ch.isdigit():
        return "은" if ch in "013678" else "는"
    return " 지수는"


def why(code: Optional[str]) -> str:
    return WHY.get(code or "", code or "사유 없음")


def clip(text: str, n: int = 80) -> str:
    """긴 글 줄이기 — 잘랐으면 '…'(잘린 줄이 전체처럼 보이지 않게 · 반박 검토 L4)."""
    return text if len(text) <= n else text[:n] + "…"


def same_filters(a: Mapping[str, Any], b: Mapping[str, bool]) -> bool:
    """네 칸이 모두 불리언으로 저장돼 지금과 같고 다른 칸이 없을 때만(빠진 칸 · 형식이 틀린 칸 · 지금 조건에 없는 칸 = 같다고 보지 않음 · 검증 F18)."""
    return all(C.filter_value(a, k) is bool(b[k]) for k in b) and all(k in b for k in a)


# 저장 기록의 같은 조건 판정 · 외부 AI 질문 인용(V2 RESULT 판정 2026-11-26 §2) — history.cite_judge 의 이유별
CITE_WHY = {
    "differs": "다시 계산한 순위 · 1개월 값이 저장값과 다름",
    "period_differs": "비교 기간이 달라 값을 맞춰 보지 않음",
    "no_restore": "그날을 다시 계산하지 못함",
    "after_end": "검토 끝일 뒤라 맞춰 보지 않음",
}
CITE_NOTE = {
    "differs": "다른 조회 조건 — AI 질문에 인용 안 함",
    "unknown": "같은 조건인지 확인 못 함 — AI 질문에 인용 안 함",
}


def _incl(v: bool) -> str:
    return "제외" if v else "포함"


def cite_lines(j: Mapping[str, Any]) -> tuple[list[str], str]:
    """(같은 조건 판정 줄들, AI 질문 인용 줄) — 사실 하나에 한 줄."""
    if j["state"] == "same":
        return [
            "같음 — 제외 조건 네 가지가 지금과 같음",
            "그날 다시 계산한 순위 · 1개월 값 · 기간도 저장값과 같음",
        ], "인용함 — 순위 · 1개월 값 · 기간만"
    if j["state"] == "differs":
        out = ["다름 — 제외 조건이 지금과 다름"]
        for d in j["diff"]:
            name = FILTER_LABEL.get(d["key"], d["key"])
            out.append(f"{name}: 그 기록 {_incl(d['stored'])} · 지금 {_incl(d['now'])}")
        return out, "인용 안 함 — 조회 조건이 지금과 다름"
    if j["why"] == "no_value":
        return [
            "확인 안 함 — 순위 · 1개월 값이 없거나 읽을 수 없음"
        ], "인용 안 함 — 인용할 값 없음"
    return [f"확인 못 함 — {unknown_why(j)}"], "인용 안 함 — 같은 조건인지 확인 못 함"


def unknown_why(j: Mapping[str, Any]) -> str:
    """같은 조건인지 확인 못 한 실제 사유(반박 검토 D2 — 다른 사유로 덮지 않음)."""
    if j["why"] == "filter_unknown":

        def names(keys: list[str]) -> str:
            return " · ".join(FILTER_LABEL.get(k, k) for k in keys)

        parts = []
        if j["missing"]:
            parts.append(f"{names(j['missing'])} 제외 여부가 저장되지 않음")
        if j["invalid"]:
            parts.append(f"{names(j['invalid'])} 제외 여부의 저장 형식이 맞지 않음")
        if j["conflict"]:
            parts.append(
                f"{names(j['conflict'])} 제외 여부가 서로 다른 값으로 두 번 저장됨"
            )
        if j["extra"]:
            parts.append(f"지금 조건에 없는 칸이 저장됨({' · '.join(j['extra'])})")
        return " · ".join(parts)
    return CITE_WHY.get(j["why"], "값을 맞춰 보지 못함")


def verdict_text(state: str, verdict: str) -> str:
    """Q4 — 기본값과 같으면 직접 고른 값인지 모름."""
    if state == "unrecorded":
        return "사용자 판단 미기록"
    if state == "default":
        return "사용자 판단 미확인"
    return f"사용자 판단 '{VERDICT_LABEL.get(verdict, verdict)}'(직접 고름)"


# --- 문장(화면과 복사문이 같은 함수) ---


def up_text(rv: Mapping[str, Any]) -> str:
    w0 = rv["weekly"].get("w0")
    if rv["up"] is None:
        return f"주 마감 가격 확인 불가({why(rv['week_gap'])})"
    head = f"{md(w0)} 마감까지 " if w0 else ""
    if rv["up"] == 4:
        return head + "최근 네 주 모두 상승"
    if rv["up"] == 0:
        return head + "최근 네 주 모두 오르지 않음"
    return head + f"최근 네 주 중 {rv['up']}주 상승"


def peer_text(rv: Mapping[str, Any]) -> Optional[str]:
    """확인된 근거 한 가지 — 같은 지수 · 같은 구조 ETF 의 같은 기간 수익률(해석은 방향까지만)."""
    peer = rv["peer"]
    if peer["state"] != "ok" or not peer["same"]:
        return None
    one = rv["one_month"]
    same = peer["same"]
    signs = {sign_of(p["one_month"]["value"]) for p in same} | {sign_of(one["value"])}
    together = signs in ({1}, {-1})  # 모두 같은 방향(0.00% 없이)일 때만 '도 · 함께'
    if len(same) == 1:
        p = same[0]
        f = fee(p["fee"])
        who_is = (
            f"같은 {peer['label']} 지수를 따르는 {p['name']}(같은 구조"
            + (f" · 총보수 {f}" if f else "")
            + ")"
        )
        v = pct(p["one_month"]["value"])
        head = (
            f"{who_is}도 같은 기간 {v}"
            if together
            else f"{who_is}의 같은 기간 수익률은 {v}"
        )
    else:
        vs = sorted(p["one_month"]["value"] for p in same)
        span = f"{pct(vs[0])} ~ {pct(vs[-1])}"
        who_is = f"같은 {peer['label']} 지수를 따르는 같은 구조 ETF {len(same)}개"
        head = (
            f"{who_is}도 같은 기간 {span}"
            if together
            else f"{who_is}의 같은 기간 수익률은 {span}"
        )
    won = "원화 " if peer["overseas"] else ""
    if signs == {1}:
        tail = f"{won}가격이 함께 올랐습니다"
    elif signs == {-1}:
        tail = f"{won}가격이 함께 내렸습니다"
    elif {1, -1} <= signs:
        tail = "방향이 엇갈렸습니다"
    elif signs == {0}:
        tail = "가격 변동이 거의 없었습니다(0.00%)"
    else:
        tail = "변동 방향이 같지 않았습니다(0.00% 포함)"
    who = "두 상품의" if len(same) == 1 else "이 상품들의"
    return f"{head}. {who} {tail}."


def flow_groups(rv: Mapping[str, Any]) -> list[dict[str, Any]]:
    """순위 흐름 — 연속한 '상위 30' · '순위권 밖' 주를 묶는다(확인 불가는 따로)."""
    out: list[dict[str, Any]] = []
    for row in rv["weeks"].get("rows") or []:
        s = row["seen"]
        if s["state"] == "ranked":
            kind = "top30" if s["top30"] else "outside"
            if out and out[-1]["kind"] == kind:
                out[-1]["dates"].append(row["date"])
                out[-1]["ranks"].append(s["rank"])
                continue
            out.append({"kind": kind, "dates": [row["date"]], "ranks": [s["rank"]]})
        else:
            out.append({"kind": "unknown", "dates": [row["date"]], "why": s["why"]})
    return out


def flow_plain(rv: Mapping[str, Any]) -> str:
    parts = []
    first_out = True
    for row in rv["weeks"].get("rows") or []:
        s = row["seen"]
        if s["state"] != "ranked":
            parts.append(f"{md(row['date'])} 순위 확인 불가({why(s['why'])})")
        elif s["top30"]:
            parts.append(f"{md(row['date'])} {s['rank']}위")
        else:
            parts.append(
                f"{md(row['date'])} {s['rank']}위("
                + ("순위권(상위 30) 밖" if first_out else "순위권 밖")
                + ")"
            )
            first_out = False
    return " → ".join(parts)


def record_notes(rv: Mapping[str, Any]) -> list[str]:
    """저장 기록을 다 읽지 못한 사유(없으면 빈 목록) — 화면(로컬)만 · '없음'을 단정하지 않게.

    외부 AI 복사문에는 넣지 않는다(로컬 기록 상태 · 공개 자료 한정 · 검증 F17)."""
    s = rv["sessions"]
    out = []
    if s.get("state") == "missing":
        out.append("「AI 투자 세션」 기록 파일 없음")
    elif s.get("state") != "ok":
        out.append("「AI 투자 세션」 기록을 읽지 못함")
    if s.get("broken"):
        out.append(f"못 읽은 「AI 투자 세션」 기록 {s['broken']}건 빠짐")
    if s.get("reviews_broken"):
        out.append(f"못 읽은 내 판단 기록 {s['reviews_broken']}건 빠짐")
    return out


def session_plain(asof: str, rank: int, one: Mapping[str, Any]) -> str:
    """복사문의 당시 저장 기록 한 줄 — 순위 · 1개월 값 · 기간만(공개 가격에서 나온 값).

    사용자가 고른 판단(직접 고른 값 · 내 판단 기록)은 외부 AI 복사문에 넣지 않는다(PLAN V2 판정 §1 · 검증 F14)."""
    span = f"{md(one['start'])} → {md(one['end'])}"
    return f"{md(asof)} 기준 — {rank}위 · 1개월 {pct(one['value'])}({span})"


def _pair(a: Mapping[str, Any]) -> str:
    parts = []
    for label, key in (("ETF", "etf"), ("KODEX 200", "kodex")):
        c = a[key]
        parts.append(
            f"{label} {pct(c['value'])}"
            if c["value"] is not None
            else f"{label} 완료 주 마감 종가 없음({why(c['why'])})"
        )
    return " · ".join(parts)


def progress_text(a: Mapping[str, Any]) -> str:
    """진행 주 상태 — 주 진행 중 · 예정 마감(또는 마감일인데 아직 장중 저장값)."""
    if a.get("intraday"):
        return f"주 진행 중 · {md(a['to'])} 마감 종가 아직 없음(장중 저장값)"
    return f"주 진행 중 · {md(a['to'])} 마감 예정"


def after_plain(row: Mapping[str, Any]) -> str:
    a = row["after"]
    if a["state"] == "not_yet":
        so = a["sofar"]
        if (
            so["why"] == "no_prev_close"
        ):  # 판정 2026-11-26 §2-3 — 한 종목 값만 보이지 않음
            return (
                f"이번 주 지금까지 비교 불가({md(a['from'])} 직전 주 마감 종가 없음 · "
                f"{progress_text(a)})"
            )
        if so["end"] is None:
            return (
                f"이번 주 지금까지 {md(a['from'])} 이후 자료 없음({why(so['why'])} · "
                f"{progress_text(a)})"
            )
        return (
            f"이번 주 지금까지 {md(a['from'])} → {md(so['end'])} {_pair(so)}"
            f"({progress_text(a)})"
        )
    if a["state"] != "ok":
        return f"{md(a['from'])} 이후 자료 없음({why(a['state'])})"
    out = f"{md(a['from'])} → {md(a['to'])} " + _pair(a)
    if a.get("then"):  # 주 마감 규칙이 건너뛴 직전 주 뒤의 진행 주(history.four_weeks)
        out += " / " + after_plain({"after": a["then"]})
    return out


def copy_text(rv: Mapping[str, Any]) -> str:
    """AI 질문 복사문 — 공개 수치 · 개인을 드러내지 않는 근거만(보유 · 금액 · 비중 · 메모 · 내 이유 없음)."""
    one, k = rv["one_month"], rv["kodex"]
    w0 = rv["weekly"].get("w0")
    wd = WD[dt.date.fromisoformat(rv["end"]).weekday()]
    state = PRICE_STATE.get(rv["price_state"], rv["price_state"])
    head = f"[검토 대상] {rv['name']}({rv['ticker']}) · 검토 기준일 {rv['end']}({wd} · {state})"
    if w0:
        head += f" · 완료 주 마감 {mdw(w0)}"
    kodex = (
        f"같은 기간 KODEX 200 {pct(k['value'])}"
        if k and (k["start"], k["end"]) == (one["start"], one["end"])
        else "같은 기간 KODEX 200 확인 불가"
    )
    reason = (
        f"[이번에 후보로 나온 이유] 「주간 ETF 점검」 조건({filter_text(rv['filters'])}) {rv['population']}개 중 "
        f"{rv['rank']}위"
        + ("" if rv["top30"] else "(상위 30 밖)")
        + f" · {md(one['start'])} ~ {md(one['end'])} {pct(one['value'])} · {kodex} · {up_text(rv)}"
    )
    scope = "같은 기간 KODEX 200" + (
        " · 같은 지수 상품"
        if rv["peer"]["state"] == "ok" and rv["peer"]["same"]
        else ""
    )
    lines = [
        LATEST_CHECK,
        "",
        "[이 묶음에 없는 값]",
        *(f"- {x}" for x in rv["missing"]),
        f"이 묶음의 값은 {rv['end']}({wd})까지 저장한 가격 기준입니다. {MISSING_TAIL}",
        "",
        f"[검토 범위] 이 ETF 자체와 비교 대상({scope})의 공개 근거로 검토해 주세요. {SCOPE_TAIL}",
        "",
        head,
        reason,
    ]
    pt = peer_text(rv)
    if pt:
        lines.append(f"[확인된 근거] {pt}")
    rows = rv["weeks"].get("rows") or []
    if rows:
        lines.append(f"[지난 네 주 — {RESTORE_LABEL}] {flow_plain(rv)}")
    else:
        lines.append(f"[지난 네 주] 확인 불가({why(rv['weeks'].get('why'))})")
    # 조회 조건이 지금과 같다고 확인된 기록만(history.cited_records · V2 RESULT 판정 §2)
    recs = [
        session_plain(c["asof"], c["rank"], c["one_month"]) for c in rv["cite_records"]
    ]
    # 인용하는 기록(순위 · 1개월 값 · 기간)만 — 내 판단 기록 · 로컬 기록 상태(파일 없음 · 읽기 실패 · 못 읽은
    # 건수)는 넣지 않는다(공개 자료 한정 · 검증 F14 · F17) · 인용할 것이 없으면 '없다'고 단정하지 않고
    # '인용할 기록 없음'(로컬 상태는 화면에만)
    body = " / ".join(recs) if recs else "인용할 기록 없음"
    lines.append("[당시 저장 기록] " + body)
    if rows:
        lines.append("[그 뒤 관측] " + " / ".join(after_plain(r) for r in rows))
    lines.append(
        f"[판단에 영향을 주는 자료 공백] {rv['gap']['copy'].rstrip('.')} · 분배금 미반영"
    )
    lines += [
        "",
        f"[AI에 확인할 것] {rv['ask']['text']}",
        *rv["ask"]["guide"],
        "",
        *ANSWER_FORMAT,
        "",
        DESIGN_QUESTION,
    ]
    return "\n".join(lines) + "\n"
