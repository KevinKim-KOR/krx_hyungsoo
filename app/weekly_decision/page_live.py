"""연구 서버 화면 · 저장 안 되는 한 장 조립 — 후보 고르기 · 저장 때 고정하는 조각(page.screen_parts) · ③ 내 판단 남기기 ·
이 ETF 의 지난 판단 · 브라우저 동작(page_script)."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from app.weekly_decision import lines as L
from app.weekly_decision.page import ask_html, screen_parts
from app.weekly_decision.page_base import document, esc, when_kst
from app.weekly_decision.page_saved import ai_line
from app.weekly_decision.page_script import SCRIPT
from app.weekly_decision.page_script_static import SCRIPT_STATIC
from app.weekly_decision.store import AI_BOXES


def _picker(rv: Mapping[str, Any], candidates: list[Mapping[str, Any]]) -> str:
    top = [c for c in candidates if c["top30"]]
    rest = [c for c in candidates if not c["top30"]]

    def opt(c: Mapping[str, Any]) -> str:
        sel = " selected" if c["ticker"] == rv["ticker"] else ""
        tk = esc(c["ticker"])
        return f'<option value="{tk}"{sel}>{c["rank"]}위 · {esc(c["name"])} ({tk})</option>'

    return (
        '<div class="pick"><select id="pick" aria-label="검토할 ETF">'
        f"<optgroup label=\"1개월 상위 30\">{''.join(opt(c) for c in top)}</optgroup>"
        f"<optgroup label=\"그 밖(1개월 순위순)\">{''.join(opt(c) for c in rest)}</optgroup>"
        '</select><span class="sub">'
        "후보를 바꾸면 아래 근거와 질문이 같은 기준일로 바뀝니다</span></div>"
    )


def _answer_boxes(live: bool) -> str:
    """AI 답 세 칸(GPT · Gemini · Claude · PLAN V2 판정 2026-11-26 §3) — 받은 답만 · 칸마다 '판단에 도움이 된 답'.

    체크는 답을 넣은 칸만(처음 모두 미선택 · 빈 칸은 못 고름 · 화면 스크립트가 켜고 끔) · 칸 아래 = 붙인 시각 · 질문 출처."""
    hint = [
        "받은 답만 붙이세요 — 빈 칸은 '답 미입력'으로 남습니다.",
        "답마다 붙인 시각과 그때 복사해 둔 질문이 함께 남습니다." if live else "",
        "'판단에 도움이 된 답' = 결론에 동의하는지와 관계없이, 판단의 근거나 다음 확인을 정하는 데 도움이 된 답입니다.",
        "답을 넣은 칸만 고를 수 있고, 여러 개 골라도 됩니다. 처음에는 모두 비어 있습니다.",
    ]
    boxes = "".join(
        f'<div class="aibox"><div class="aihead"><b>{esc(n)}</b>'
        f'<label class="like"><input type="checkbox" id="help_{n.lower()}" disabled> '
        "판단에 도움이 된 답</label></div>"
        f'<textarea id="answer_{n.lower()}" rows="4" maxlength="60000" '
        f'placeholder="{esc(n)} 답을 붙여 넣으세요 — 받지 않았으면 비워 두세요"></textarea>'
        f'<div class="sub" id="ainote_{n.lower()}">답 미입력</div></div>'
        for n in AI_BOXES
    )
    lines = "".join(f'<span class="sub">{esc(h)}</span>' for h in hint if h)
    orphan = (
        '<details id="orphan" hidden><summary>예전 입력의 AI 답(어느 AI 의 답인지 적혀 있지 않음 · '
        '읽기만)</summary><pre id="orphantext"></pre></details>'
        if live
        else ""
    )
    return f'<div class="field"><span><b>AI 답 붙여 넣기</b></span>{lines}</div>{orphan}{boxes}'


def _form(rv: Mapping[str, Any], *, live: bool) -> str:
    checks = [("rank_flow", "순위 흐름")]
    if L.peer_text(rv):
        checks.append(("peer", "같은 지수 상품"))
    if rv["previous"]:
        checks.append(("previous", "지난 검토와 비교"))
    checks += [("weeks", "지난 네 주"), ("ai_answer", "AI 답")]
    boxes = "".join(
        f'<label><input type="checkbox" name="used" value="{k}"> {esc(t)}</label>'
        for k, t in checks
    )
    save = (
        '<button class="btn" type="button" id="save">저장</button>'
        if live
        else '<button class="btn" type="button" disabled>저장</button>'
    )
    past = '<a class="btn alt" href="/reviews">지난 판단 열기</a>' if live else ""
    keepbox = (
        '<div class="msg bad" id="keepmsg" role="alert" hidden>지금 쓰는 내용을 이 창에 임시로 남기지 '
        "못하고 있습니다 — 저장하기 전에 새로 고치거나 창을 닫으면 방금 쓴 내용은 돌아오지 않습니다.</div>"
        '<div class="sub" id="otherdrafts" hidden></div>'
        '<details id="olddrafts" hidden><summary>예전 화면에 남은 이 ETF 입력 '
        '<span id="olddraftscount"></span>건(읽기만 · 이 화면에 넣지 않음)</summary>'
        '<div class="sub">필요하면 글을 복사해 위 칸에 붙이세요 — 여기서 복사한 AI 답은 어느 질문의 답인지 '
        "'하나로 정할 수 없음'으로 남습니다.</div>"
        '<div id="olddraftsbody"></div></details>'
        if live
        else ""
    )
    note = (
        [
            "저장하면 지금 화면의 근거 · 지난 네 주 · 복사된 질문 원문 · 기준일 · 조회 조건을 함께 고정합니다.",
            "저장하기 전까지 쓴 내용은 이 창에 임시로 남습니다 — 새로 고침 · 서버를 다시 켠 뒤에도 같은 창에서 "
            "되살리고, 창을 닫으면 사라질 수 있습니다(남기지 못하면 바로 알림).",
            "저장이 거절되면 '저장 안 됨', 응답을 못 받으면 '저장됐는지 모름'을 보입니다.",
        ]
        if live
        else [
            "이 파일에서는 저장할 수 없습니다 — 연구 서버(serve)로 연 화면에서 저장합니다."
        ]
    )
    return (
        '<section class="card mine"><h2><span class="step">3</span>내 판단 남기기</h2>'
        '<ul class="lines">'
        "<li>AI 답의 첫 줄('검토 계속' · '보류')은 AI 의견입니다. 판단은 직접 고르세요 — 처음은 '미기록'입니다.</li>"
        "<li>내 보유와 겹치는지는 AI 질문에 넣지 않았습니다 — 위 '지난 네 주' 아래 '구성 · 겹침'에서 보세요.</li>"
        "</ul>"
        '<div class="choice">'
        '<label><input type="radio" name="verdict" value="continue"> 검토 계속</label>'
        '<label><input type="radio" name="verdict" value="hold"> 보류</label>'
        '<label><input type="radio" name="verdict" value="unrecorded" checked> 미기록</label>'
        '</div><div class="form">'
        '<label class="field"><span>이유 한 줄</span>'
        '<input type="text" id="reason" maxlength="500"></label>'
        '<label class="field"><span>다음에 확인할 것 한 가지</span>'
        '<input type="text" id="next" maxlength="500"></label>'
        f'<div class="checks"><span class="sub">판단에 쓴 근거</span>{boxes}</div>'
        f"{_answer_boxes(live)}"
        '<label class="field"><span>AI 답에서 판단에 쓴 대목 — 필요하면 AI 이름도 함께 적으세요</span>'
        '<textarea id="excerpt" rows="2" maxlength="4000"></textarea></label>'
        f'<div class="btnrow">{save}{past}</div>'
        f'<div class="msg" id="savemsg" role="status"></div>{keepbox}'
        f'<div class="sub">{"<br>".join(esc(x) for x in note)}</div></div></section>'
    )


def _past(reviews: list[Mapping[str, Any]]) -> str:
    if not reviews:
        return ""
    items = "".join(
        f"<li><a href=\"/reviews/{esc(r['review_id'])}\">{esc(when_kst(r['saved_at']))} 저장</a>"
        f" · 기준일 {esc(L.md(r['end']))} · "
        f"<b>{esc(L.MY_VERDICT.get(r['verdict'], r['verdict']))}</b>"
        + (f" — {esc(L.clip(r['reason']))}" if r.get("reason") else "")
        + f'<div class="sub">{esc(ai_line(r))}</div>'
        + "</li>"
        for r in reviews
    )
    return (
        '<section class="card"><h2>이 ETF 의 지난 판단</h2>'
        f'<ul class="list">{items}</ul></section>'
    )


def render_live(
    rv: Mapping[str, Any],
    *,
    build_id: Optional[str],
    candidates: list[Mapping[str, Any]],
    reviews: list[Mapping[str, Any]],
) -> str:
    """연구 서버 화면(build_id 있음) 또는 저장 안 되는 한 장(build_id 없음 · CLI page)."""
    live = build_id is not None
    parts = screen_parts(rv)
    head = (
        '<section class="card"><h1>관심 ETF 검토</h1>'
        f"<div class=\"sub\">{parts['sub']}</div>"
        f"{_picker(rv, candidates) if live else ''}{parts['one']}</section>"
    )
    body = (
        head
        + parts["weeks"]
        + ask_html(rv, live=True)
        + _form(rv, live=live)
        + _past(reviews)
    )
    script = (
        SCRIPT
        % {
            "build": json.dumps(build_id),
            "ticker": json.dumps(rv["ticker"]),
            "end": json.dumps(rv["end"]),
            "name": json.dumps(rv["name"]),
        }
        if live
        else SCRIPT_STATIC
    )
    return document(f"관심 ETF 검토 · {rv['name']}", body, script)
