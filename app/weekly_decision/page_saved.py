"""저장한 판단 다시 열기 · 저장 목록 · 오류 화면 — 저장 때 고정한 화면 조각을 그대로 보인다(다시 그리지 않음)."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from app.weekly_decision import lines as L
from app.weekly_decision import store as ST
from app.weekly_decision.page_base import document, esc, when_kst
from app.weekly_decision.page_script_static import SCRIPT_MARK


def _asked_html(ai: Mapping[str, Any]) -> str:
    """AI 답의 질문 출처(서버가 화면 번호로 판정해 남긴 것)."""
    a = ai.get("asked") or {}
    st = a.get("state")
    if st == "this_screen":
        return "<br>질문: 이 화면의 복사문"
    if st == "same_copy":
        return "<br>질문: 이 화면과 같은 복사문(같은 질문 원문을 앞서 연 화면에서 복사)"
    if st == "mixed":
        return (
            "<br><b>질문: 어느 질문의 답인지 하나로 정할 수 없음</b>"
            " — 다른 질문의 답이 섞였거나, 붙여 넣은 글이 질문 복사 뒤의 AI 답인지 확인되지 않음"
        )
    if st == "other_screen":
        return (
            f"<br><b>질문: 다른 화면(기준일 {esc(a.get('end'))} · {esc(a.get('ticker'))})의 "
            "복사문</b> — 이 화면 근거와 다를 수 있음"
            f"<details><summary>그 복사문</summary><pre>\n{esc(a.get('copy') or '')}</pre></details>"
        )
    if st == "unknown_screen":
        return (
            "<br><b>질문: 어느 화면의 복사문인지 모름</b>"
            "(서버를 다시 켰거나 오래돼 서버에 그 화면 자료가 없음)"
        )
    if ai.get("answer"):
        return (
            "<br>질문: 답을 붙일 때 복사한 기록 없음 — 어느 질문으로 받은 답인지 모름"
        )
    return ""


def _ai_one(ai: Mapping[str, Any], helpful: str) -> str:
    """AI 답 한 칸 — 이름 · 판단에 도움 · 붙인 시각 · 질문 복사 시각 · 질문 출처 · 답 전체(줄마다)."""
    head = f"<b>{esc(ai.get('name') or 'AI 이름 미기록')}</b> {helpful}"
    rows = [
        (
            f"붙인 시각 {esc(when_kst(ai['pasted_at']))}"
            if ai.get("pasted_at")
            else "붙인 시각 없음"
        )
    ]
    if ai.get("copied_at"):
        rows.append(f"질문 복사 {esc(when_kst(ai['copied_at']))}")
    sub = "".join(f'<div class="sub">{r}</div>' for r in rows)
    return (
        f"<div>{head}{sub}{_asked_html(ai)}"
        "<details><summary>붙여 넣은 답 전체</summary>"
        f"<pre>\n{esc(ai['answer'])}</pre></details></div>"
    )


def ai_html(doc: Mapping[str, Any]) -> str:
    """그때 남긴 AI 답 — 새 기록 = 칸마다(넣지 않은 칸 = 답 미입력) · 예전 기록 = 답 하나 · 도움 선택 미기록."""
    dec = doc["decision"]
    badge = '<span class="likebadge">판단에 도움이 된 답</span>'
    if doc["schema"] == ST.SCHEMA_V1:
        ai = dec["ai"]
        parts = (
            [_ai_one(ai, '<span class="sub">판단에 도움 여부 미기록(예전 기록)</span>')]
            # 목록 요약과 같은 '답 있음' 규칙(반박 검토 L5)
            if ST.js_trim(ai.get("answer") or "")
            else ["<div>붙여 넣은 답 없음</div>"]
        )
        excerpt = ai.get("excerpt")
    else:
        by = {a["name"]: a for a in dec["ais"]}
        parts = [
            (
                _ai_one(by[n], badge if by[n]["helpful"] else "")
                if n in by
                else f'<div><b>{esc(n)}</b><div class="sub">답 미입력</div></div>'
            )
            for n in ST.AI_BOXES
        ]
        excerpt = dec.get("excerpt")
    if excerpt:
        # 여러 줄 칸 — 줄바꿈을 지킴(반박 검토 D2)
        parts.append(f'<div>쓴 대목: <span class="keep">{esc(excerpt)}</span></div>')
    return f'<div class="ailist">{"".join(parts)}</div>'


def ai_line(r: Mapping[str, Any]) -> str:
    """저장 목록 한 줄의 AI 답 요약(store.ai_summary)."""
    n = r.get("ai_count") or 0
    if not n:
        return "AI 답 없음"
    helpful = r.get("helpful")
    if helpful is None:
        tail = "판단에 도움 여부 미기록"
    elif helpful:
        tail = "판단에 도움이 된 답 " + " · ".join(helpful)
    else:
        tail = "판단에 도움이 된 답 고르지 않음"
    return f"AI 답 {n}개 · {tail}"


def render_saved(doc: Mapping[str, Any]) -> str:
    """다시 열기 — 저장 때 고정한 조각 그대로 + 그때 남긴 판단."""
    snap, dec = doc["snapshot"], doc["decision"]
    sc = snap["screen"]
    used_label = {
        "rank_flow": "순위 흐름",
        "peer": "같은 지수 상품",
        "previous": "지난 검토와 비교",
        "weeks": "지난 네 주",
        "ai_answer": "AI 답",
    }
    used = (
        " · ".join(used_label.get(u, u) for u in dec.get("used") or []) or "고르지 않음"
    )
    rows = [
        ("판단", f"<b>{esc(L.MY_VERDICT.get(dec['verdict'], dec['verdict']))}</b>"),
        ("이유", esc(dec.get("reason") or "적지 않음")),
        ("다음 확인", esc(dec.get("next_check") or "적지 않음")),
        ("판단에 쓴 근거", esc(used)),
        ("AI 답", ai_html(doc)),
    ]
    facts = "".join(
        f'<li><div class="k">{esc(k)}</div><div class="v">{v}</div></li>'
        for k, v in rows
    )
    decision = (
        '<section class="card mine"><h2><span class="step">3</span>그때 남긴 내 판단</h2>'
        f'<ul class="facts">{facts}</ul></section>'
    )
    banner = (
        f"<div class=\"banner\">저장한 판단 — {esc(when_kst(doc['saved_at']))} 저장 · "
        "그때 화면 그대로(뒤에 바뀐 값으로 다시 그리지 않음)"
        f" · <a href=\"/?ticker={esc(snap['ticker'])}\">지금 검토 화면</a>"
        ' · <a href="/reviews">저장 목록</a></div>'
    )
    head = (
        '<section class="card"><h1>관심 ETF 검토 · '
        f"{esc(snap.get('name') or snap['ticker'])}</h1>"
        f"<div class=\"sub\">{sc['sub']}</div>{sc['one']}</section>"
    )
    return document(
        f"저장한 판단 · {snap.get('name') or snap['ticker']}",
        banner + head + sc["weeks"] + sc["ask"] + decision,
        SCRIPT_MARK,
    )


def render_list(
    listing: Mapping[str, Any],
    *,
    later: Optional[set] = None,
    end: Optional[str] = None,
) -> str:
    """전체 보관 목록 — 끝일을 지정한 서버(end)면 검토 시점 이후에 저장한 판단에 표시를 단다."""
    items = listing["items"]
    later = later or set()

    def tag(r: Mapping[str, Any]) -> str:
        if r["review_id"] not in later:
            return ""
        return ' <span class="src obs">검토 시점 이후 저장</span>'

    rows = "".join(
        f"<li><a href=\"/reviews/{esc(r['review_id'])}\">{esc(when_kst(r['saved_at']))} 저장</a>"
        f" · {esc(r.get('name') or r['ticker'])} ({esc(r['ticker'])})"
        f" · 기준일 {esc(L.md(r['end']))} · "
        f"<b>{esc(L.MY_VERDICT.get(r['verdict'], r['verdict']))}</b>"
        + (f" — {esc(L.clip(r['reason']))}" if r.get("reason") else "")
        + f'<div class="sub">{esc(ai_line(r))}</div>'
        + tag(r)
        + "</li>"
        for r in items
    )
    note = (
        f'<div class="banner">이 서버는 {esc(L.md(end))} 기준 검토입니다. 이 목록은 전체 보관 목록이라 '
        "그 검토 시점 이후에 저장한 판단도 '검토 시점 이후 저장' 표시와 함께 보입니다 — "
        "그 판단은 그때 검토 화면의 근거에 들어가지 않습니다.</div>"
        if end
        else ""
    )
    body = (
        '<section class="card"><h1>저장한 판단</h1>'
        '<div class="sub"><a href="/">← 검토 화면으로</a></div>'
        + note
        + (
            f'<ul class="list">{rows}</ul>'
            if items
            else "<div>아직 저장한 판단이 없습니다.</div>"
        )
        + (
            f"<div class=\"msg bad\">읽지 못한 기록 {len(listing['broken'])}건: "
            f"{esc(', '.join(listing['broken']))}</div>"
            if listing["broken"]
            else ""
        )
        + "</section>"
    )
    return document("저장한 판단", body, SCRIPT_MARK)


def render_error(title: str, text: str) -> str:
    return document(
        title,
        f'<section class="card"><h1>{esc(title)}</h1><div>{esc(text)}</div>'
        '<div class="sub"><a href="/">← 검토 화면으로</a></div></section>',
    )
