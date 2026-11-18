"""POC6-32 — 「주간 ETF 점검」 복사 글(PLAN V2 §4-3 · 판정 V2 §2 · §3 · §9 I-15).

글 한 벌을 서버 한 곳에서 만든다 — [AI용 주간 검토 복사]와 [AI 투자 세션으로 넘기기](질문 원문)가 같은 글이다.
- 첫머리 = '최신 공개 자료 확인' 문단(일일 복사와 같은 원문 · `market_evidence_text.LATEST_CHECK`) → 머리 줄
  「주간 ETF 점검」 · 목록 조건. V1 둘째 줄('[근거 n] 의 수치 · 기준일만 써서 답해 주세요')은 없다.
- 근거 번호 = 글 전체에서 한 번씩 붙는 `[근거 n]`(ETF 마다 새로 시작하지 않음).
  순서 = 공통 시장 근거 줄 전부(일일 복사와 같은 줄 · `evidence_items` · 자료 상태 줄만 번호 없이 `[자료 상태]`) →
  주간 근거(목록 조건 · 같은 기간 KODEX 200 · 흐름 첫 3행 · 나머지 · 고른 ETF 어떤 상품인가 · 구성 · 실제로 올랐나 ·
  보유 겹침 확인 범위).
- ② 흐름의 1 · 3개월 값이 '기간 다름'이면 값 + '기간 다름' + 실제 시작 → 끝(V2 W5 · '확인 불가'로 쓰지 않음).
- 답 형식 = 맨 앞 `최신 확인: 같음 | 새 값 있음 | 확인 불가` · 확인한 항목마다 이름 붙은 칸 한 줄
  (`- 항목: … · 값: … · 기준일: … · 출처: … · 확인 시각: … · 달라지는 해석: …` · I-15) ·
  ETF 마다 `[ETF 코드]` · 상태 · 인용 근거 · 이유 · 다음 확인. `weekly_review_answers` 가 이 모듈의 상수로 같은 형식을 읽는다.
- 금액 · 보유 종목 이름은 넣지 않는다(비율 · 개수만). 고른 ETF 의 주요 편입 이름은 그 ETF 자기 구성 행의 이름이다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional, Sequence

from app.market_evidence_text import LATEST_CHECK
from app.weekly_review import FIRST_ROWS, ranks_text

STATES = ("근거 확인", "추가 확인", "자료 부족")
FIELDS = ("상태", "인용 근거", "이유", "다음 확인")
TARGETS_HEAD = "대상 ETF: "
LATEST_HEAD = "최신 확인"
LATEST_STATES = ("같음", "새 값 있음", "확인 불가")
# 확인 항목 줄의 이름 붙은 칸(I-15) — (글 속 칸 이름, 응답 키)
ITEM_FIELDS = (
    ("항목", "item"),
    ("값", "value"),
    ("기준일", "basis_date"),
    ("출처", "source"),
    ("확인 시각", "checked_at"),
    ("달라지는 해석", "changes"),
)
ITEM_TEMPLATE = "- " + " · ".join(f"{label}: …" for label, _ in ITEM_FIELDS)
STATE_MEANING = (
    "상태 뜻: 근거 확인 = 위 근거로 설명이 됨 · 추가 확인 = 판단 전에 더 볼 것이 있음 · "
    "자료 부족 = 이 근거로는 판단할 수 없음"
)
NA = "확인 불가"
DATA_STATUS_KEY = "data_status"
NO_MARKET = "공통 시장 근거 확인 불가"


def _p(v: Optional[float]) -> str:
    if v is None:
        return NA
    s = "+" if v > 0 else ("-" if v < 0 else "")
    return f"{s}{abs(v):.2f}%"


def _md(d: Optional[str]) -> str:
    """'2026-11-16' → '11/16' · 비면 '확인 불가'."""
    if not d:
        return NA
    return f"{int(d[5:7])}/{int(d[8:10])}"


def _val(v: Optional[float], per: Optional[Mapping[str, Any]]) -> str:
    """흐름 값 — 기간 다름이면 값 + '기간 다름' + 실제 시작 → 끝(V2 W5)."""
    if v is None:
        return NA
    if per and per.get("status") == "period_differs":
        return f"{_p(v)} · 기간 다름({_md(per.get('start'))} → {_md(per.get('end'))})"
    return _p(v)


def _member(m: Mapping[str, Any]) -> str:
    per = m.get("periods") or {}
    return (
        f"{m['name']}({m['ticker']}) 1개월 {_val(m['one_month'], per.get('one_month'))} · "
        f"3개월 {_val(m['three_month'], per.get('three_month'))}"
    )


def _index(row: Mapping[str, Any], m: Mapping[str, Any]) -> str:
    """공식 기초지수명이 다른 상품이 섞인 묶음이면 상품마다 공식 지수명(I-29) · 아니면 빈 글."""
    if not row.get("index_names_differ"):
        return ""
    return f" · 공식 기초지수 {m.get('index_name') or NA}"


def flow_text(row: Mapping[str, Any]) -> str:
    ms = row["members"]
    if row["kind"] == "single":
        return f"{ms[0]['rank']}위 {_member(ms[0])} · {row['note']} · 단독"
    return f"{ranks_text(ms)}위 {row['title']} 묶음({row['note']}) — " + " / ".join(
        _member(m) + _index(row, m) for m in ms
    )


def _one(m: Mapping[str, Any]) -> str:
    return _val(m["one_month"], (m.get("periods") or {}).get("one_month"))


def rest_text(rows: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    for r in rows:
        ms = r["members"]
        if r["kind"] == "single":
            m = ms[0]
            parts.append(f"{m['rank']}위 {m['name']}({m['ticker']}) {_one(m)}")
        else:
            inner = ", ".join(f"{m['ticker']} {_one(m)}{_index(r, m)}" for m in ms)
            parts.append(f"{ranks_text(ms)}위 {r['title']} 묶음({inner})")
    return "나머지(원래 순위 · 같은 규칙 · 1개월): " + " · ".join(parts)


# ── 주간 목록 근거 ───────────────────────────────────────────────────────────
def list_items(
    summary: Mapping[str, Any], condition: Mapping[str, Any]
) -> list[tuple[str, str]]:
    """목록 조건(3개월 공통 기간 포함) · 같은 기간 KODEX 200(1 · 3개월 · 목록 요약 값 그대로)."""
    w3 = (summary.get("criteria_periods") or {}).get("three_month") or {}
    per = summary["period"]
    k = summary.get("kodex200") or {}
    has3 = bool(w3.get("start") and w3.get("end"))
    common3 = f"{_md(w3.get('start'))} → {_md(w3.get('end'))}" if has3 else NA
    three = (
        f"3개월 {_p(k.get('three_month_return_pct'))}({common3})"
        if has3
        else f"3개월 {NA}(3개월 공통 기간 없음)"
    )
    return [
        (
            "list_condition",
            f"[목록 조건] {condition['line']} · 3개월 공통 기간 {common3}",
        ),
        (
            "list_kodex",
            f"[같은 기간 KODEX 200] 1개월 {_p(k.get('basis_return_pct'))}"
            f"({_md(per['start'])} → {_md(per['end'])}) · {three} · "
            f"시세 {_md(summary['end_date'])}",
        ),
    ]


# ── 고른 ETF 요약(R1 · R2) ────────────────────────────────────────────────────
def _x(v: Any) -> str:
    s = str(v).strip() if v is not None else ""
    return s or NA


def _fee(v: Any) -> str:
    """총보수 — 공식 CSV 글자(예: '0.450000')를 짧은 소수로(0.45%) · 숫자가 아니면 글자 그대로."""
    s = str(v).strip() if v is not None else ""
    if not s:
        return NA
    try:
        d = Decimal(s)
    except InvalidOperation:
        return s
    return f"{d.normalize():f}%" if d.is_finite() else s


def product_text(sr: Mapping[str, Any]) -> str:
    """어떤 상품인가(R1) — 공식 기준정보(파일 날짜) · 없으면 사유 + '확인 불가'."""
    p = sr["product"]
    head = (
        f"[고른 ETF — 어떤 상품인가] {sr['name']}({sr['ticker']}) · "
        f"1개월 상위 {sr['rank']}위"
    )
    if not p.get("found"):
        why = p.get("missing_reason") or "공식 기준정보에 없음"
        return f"{head} · {why} — 공식 기초지수 · 상품 구조 확인 불가"
    asof = (p.get("csv") or {}).get("asof") or "날짜 확인 불가"
    return (
        f"{head} · 공식 기초지수 {_x(p.get('index_name'))} · "
        f"지수산출기관 {_x(p.get('index_provider'))} · "
        f"투자 대상 {_x(p.get('market'))} · {_x(p.get('asset'))} · "
        f"상품 구조 추적배수 {_x(p.get('multiple'))} · {_x(p.get('replication'))} · "
        f"총보수 {_fee(p.get('fee_pct'))}(KRX 공식 기준정보 {asof} 파일)"
    )


def _w(v: Optional[float]) -> str:
    return "비중 확인 불가" if v is None else f"{v:.2f}%"


def constituents_text(c: Mapping[str, Any]) -> str:
    """주요 편입(주식 상위 3개 · 그 ETF 자기 구성 행) · 상위 합 · 구성 기준일 · 저장 행 · 상태(R1 · I-10)."""
    top = c.get("top_stocks") or []
    parts = []
    if top:
        names = " · ".join(f"{s['name']} {_w(s.get('weight_pct'))}" for s in top)
        total = c.get("top3_sum_pct")
        parts.append(
            f"주요 편입(주식) {names} → 상위 {len(top)}개 합 "
            f"{NA if total is None else f'{total:.2f}%'}"
        )
    parts.append(c["line"])
    return "[고른 ETF — 구성] " + " · ".join(parts)


def _return_text(r: Mapping[str, Any]) -> str:
    v = r.get("value_pct")
    if v is None:
        return f"{r['label']} 수익률 {NA}"
    span = f"{_md(r.get('start'))} → {_md(r.get('end'))}"
    if r.get("status") == "period_differs":
        cm = r.get("common") or {}
        common = (
            f" · 공통 {_md(cm['start'])} → {_md(cm['end'])}"
            if cm.get("start") and cm.get("end")
            else ""
        )
        return f"{r['label']} {_p(v)}(실제 {span}{common}) {r['phrase']}"
    m = r.get("market") or {}
    kodex = (
        f" · 국내시장(KODEX 200) {_p(m.get('value_pct'))}"
        if m.get("comparable")
        else ""
    )
    return f"{r['label']} {_p(v)}({span}) {r['phrase']}{kodex}"


def returns_text(sr: Mapping[str, Any]) -> str:
    """실제로 올랐나(R2) — 1 · 3개월 줄 · 가격 상태(이 ETF · KODEX 200)."""
    body = " / ".join(_return_text(r) for r in sr["returns"])
    return f"[고른 ETF — 실제로 올랐나] {body} · {sr['price_note']}"


# ── 복사 글 ─────────────────────────────────────────────────────────────────
def market_lines(
    mev: Optional[Mapping[str, Any]],
) -> tuple[list[tuple[str, str]], str]:
    """(번호 붙일 공통 시장 근거 줄, 번호 없는 자료 상태 줄).

    못 읽었거나(`None`) 만들지 않았으면(`unavailable`) 번호 줄 없이 '[자료 상태] 공통 시장 근거 확인 불가' 한 줄
    (예전 시장 줄로 대신하지 않음)."""
    if not mev or mev.get("status") == "unavailable":
        why = (mev or {}).get("message") or "시장 근거를 읽지 못함"
        parts = [p for p in (mev or {}).get("data_status") or [] if p != why]
        tail = "".join(f" · {p}" for p in parts)
        return [], f"[자료 상태] {NO_MARKET} — {why}{tail}"
    items = mev.get("evidence_items") or []
    numbered = [(i["key"], i["text"]) for i in items if i["key"] != DATA_STATUS_KEY]
    status = next(
        (i["text"] for i in items if i["key"] == DATA_STATUS_KEY),
        f"[자료 상태] {NA}",
    )
    return numbered, status


def build_copy(
    *,
    condition: Mapping[str, Any],
    flows: Sequence[Mapping[str, Any]],
    selected: Optional[Mapping[str, Any]],
    overlap: Optional[Mapping[str, Any]],
    summary: Mapping[str, Any],
    market_evidence: Optional[Mapping[str, Any]] = None,
    review: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """근거 목록 · 답 받을 ETF · 복사 글. 근거 = [{no, group, key, text, tickers}].

    group = market(공통 시장 근거 · key = `evidence_items` 의 key) · list(목록 조건 · 같은 기간 KODEX 200) ·
    flow · rest · selected(고른 ETF R1 · R2) · overlap(보유 겹침). 답 받을 ETF 마다 관련 근거 =
    market · list 전부 + 그 ETF 가 든 근거.
    """
    ev: list[dict[str, Any]] = []

    def add(group: str, key: str, text: str, tickers: Sequence[str] = ()) -> None:
        ev.append(
            {
                "no": len(ev) + 1,
                "group": group,
                "key": key,
                "text": text,
                "tickers": list(tickers),
            }
        )

    market_items, status_line = market_lines(market_evidence)
    for key, text in market_items:
        add("market", key, text)
    for key, text in list_items(summary, condition):
        add("list", key, text)
    first, rest = list(flows[:FIRST_ROWS]), list(flows[FIRST_ROWS:])
    for i, r in enumerate(first, start=1):
        add("flow", f"flow_{i}", flow_text(r), [m["ticker"] for m in r["members"]])
    if rest:
        tks = [m["ticker"] for r in rest for m in r["members"]]
        add("rest", "rest", rest_text(rest), tks)
    if selected is not None and review is not None:
        tk = [selected["ticker"]]
        add("selected", "selected_product", product_text(review), tk)
        cons = constituents_text(review["constituents"])
        add("selected", "selected_constituents", cons, tk)
        add("selected", "selected_returns", returns_text(review), tk)
    if selected is None:
        add("overlap", "overlap_1", "고른 ETF 없음 — 내 보유와 겹침은 대조 전")
    else:
        head = (
            f"고른 ETF {selected['name']}({selected['ticker']}) · {selected['rank']}위"
        )
        lines = [*overlap["warn_lines"], *overlap["lines"]] if overlap else []
        if overlap and overlap.get("date_line"):
            lines.append(overlap["date_line"])
        for i, line in enumerate(lines or ["보유 겹침 확인 불가"]):
            text = f"{head} — {line}" if i == 0 else line
            add("overlap", f"overlap_{i + 1}", text, [selected["ticker"]])

    targets: list[str] = [r["rep"] for r in first]
    if selected is not None and selected["ticker"] not in targets:
        targets.append(selected["ticker"])
    common_nos = [e["no"] for e in ev if e["group"] in ("market", "list")]
    target_rows = []
    for t in targets:
        own = (
            e["no"]
            for e in ev
            if e["group"] not in ("market", "list") and t in e["tickers"]
        )
        target_rows.append({"ticker": t, "evidence": [*common_nos, *own]})

    def sect(*groups: str) -> list[str]:
        return [f"[근거 {e['no']}] {e['text']}" for e in ev if e["group"] in groups]

    L = [
        LATEST_CHECK,
        "",
        f"[주간 ETF 점검 · {condition['line']}]",
        "",
        "[시장 — 「오늘의 투자 점검」 [AI용 시장 정보 복사]와 같은 공통 시장 근거 · 자료마다 기준일]",
        *sect("market"),
        status_line,
        "",
        "[주간 목록 — 조건 · 같은 기간 KODEX 200]",
        *sect("list"),
        "",
        "[먼저 볼 ETF 흐름 — 같은 기초지수 계열(공식 기초지수명이 같거나 계열 사전으로 확인된 것)만 한 묶음 · "
        "대표 = 묶음에서 가장 높은 순위 · 첫 화면 3행]",
        *sect("flow", "rest"),
    ]
    if any(e["group"] == "selected" for e in ev):
        L += ["", "[고른 ETF — 어떤 상품인가 · 실제로 올랐나]", *sect("selected")]
    L += [
        "",
        "[고른 ETF와 내 보유의 겹침 — 금액 · 보유 종목 이름 없음 · 범위 먼저]",
        *sect("overlap"),
        "",
        "[답 형식 — 이 형식으로만 · 답은 AI 의견으로 기록됩니다(투자 권유 아님)]",
        "첫 줄(셋 중 하나만 남김 · 같음 = 저장값과 같음 · 새 값 있음 = 더 최신 값이나 "
        "같은 날짜의 정정값이 있음 · 확인 불가 = 최신 공개 자료를 확인하지 못함):",
        f"{LATEST_HEAD}: " + " | ".join(LATEST_STATES),
        "확인한 항목마다 한 줄(칸 이름 그대로 · 출처는 링크 · 확인 시각 = 직접 확인한 시각 · "
        "모르는 칸은 비워 둠):",
        ITEM_TEMPLATE,
        "인용 근거에는 이 글의 [근거 n] 번호만 적습니다(새로 확인한 값은 위 항목 줄에).",
        TARGETS_HEAD + " · ".join(targets),
        STATE_MEANING,
    ]
    for tr in target_rows:
        L += [
            f"[ETF {tr['ticker']}] (관련 근거 {', '.join(str(n) for n in tr['evidence'])})",
            "상태: " + " | ".join(STATES) + " 중 하나",
            "인용 근거: 위 [근거 n] 의 번호만(쉼표로 구분)",
            "이유: 한 문장",
            "다음 확인: 한 가지",
        ]
    return {"evidence": ev, "targets": target_rows, "text": "\n".join(L)}
