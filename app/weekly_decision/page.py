"""저장 때 고정하는 화면 조각(PLAN §2 · §3 · 목업 V1) — ① 왜 이번에 보나 · 지난 네 주 · ② AI에 확인할 것.

③ 내 판단 남기기와 페이지 조립은 page_live · 다시 열기는 page_saved.

```text
글     숫자 · 날짜는 lines 의 같은 함수(복사문과 같음) · 화면은 부호 색 · 줄 중간 쪼개짐 방지만 덧입힘
조각   sub · one · weeks · ask = 저장 때 그대로 고정(다시 열기는 이 조각을 그대로 보임 · 다시 그리지 않음)
       weeks 맨 위 = 흐름 그래프(page_chart · 서버가 그린 SVG — 저장 조각에 그대로 들어감)
폭     넓은 화면 = 주별 한 행 · 600px 이하 = 주마다 세로 카드(가로로 밀지 않음)
```
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from app.weekly_decision import history as H
from app.weekly_decision import observe as OB
from app.weekly_decision import lines as L
from app.weekly_decision.page_base import deco, esc, sign_num, when_kst
from app.weekly_decision.page_chart import chart_html

# --- 문장(화면) ---


def sub_line(rv: Mapping[str, Any]) -> str:
    end = rv["end"]
    wk = rv["weekly"]
    parts = [
        f"검토 기준일 {L.mdw(end)}",
        L.PRICE_STATE.get(rv["price_state"], rv["price_state"]),
    ]
    if wk.get("w0"):
        parts.append(f"완료 주 마감 {L.mdw(wk['w0'])}")
    if not wk.get("finished"):
        parts.append(f"{L.md(end)} 주는 거래 중")
    return " · ".join(parts)


def flow_text(rv: Mapping[str, Any]) -> Optional[str]:
    groups = L.flow_groups(rv)
    if not groups:
        return None
    parts = []
    for g in groups:
        ds = " · ".join(L.md(d) for d in g["dates"])
        if g["kind"] == "unknown":
            parts.append(f"{ds} 순위 확인 불가({L.why(g['why'])})")
        elif g["kind"] == "outside":
            rk = " · ".join(str(r) for r in g["ranks"])
            parts.append(f"{ds} 순위권 밖({rk}위)")
        else:
            rk = " · ".join(str(r) for r in g["ranks"])
            head = f"{ds} 마감 기준" if len(g["dates"]) > 1 else ds
            parts.append(f"{head} 상위 30({rk}위)")
    parts.append(f"{L.md(rv['end'])} {rv['rank']}위")
    return " → ".join(parts)


def _one_span(one: Mapping[str, Any]) -> str:
    return f"{L.pct(one['value'])} · {L.md(one['start'])} → {L.md(one['end'])}"


def previous_lines(rv: Mapping[str, Any]) -> Optional[tuple[list[str], str, str]]:
    """지난 검토와 비교(Q7) — (줄들, 표 꼬리 종류, 꼬리 글)."""
    prev = rv["previous"]
    if prev is None:
        return None
    now = f"→ 지금 {rv['rank']}위 · {_one_span(rv['one_month'])}"
    if prev["kind"] == "review":
        r = prev["review"]
        lines = [
            f"{L.md(r['end'])} 내 판단: {L.MY_VERDICT.get(r['verdict'], r['verdict'])}"
            + (f" — {L.clip(r['reason'])}" if r.get("reason") else "")
        ]
        if r.get("rank") is not None and r.get("one_month"):
            cond = (
                " · 같은 조건"
                if prev["same_filters"]
                else f" · 조건: {L.filter_text(r['filters'])}"
            )
            lines.append(f"그때 {r['rank']}위 · {_one_span(r['one_month'])}{cond}")
            if not prev[
                "same_filters"
            ]:  # 지금 값도 조건과 함께(저장 기록 경로와 같게 · 반박 검토)
                now += f" · 조건: {L.filter_text(rv['filters'])}"
        lines.append(now)
        return lines, "rec", "내 판단 기록"
    if prev["kind"] == "session":
        # 같은 조건 = 복사문 인용과 같은 판정(제외 조건 + 그날 다시 계산 · 반박 검토 D1)
        j = prev["cite_why"]
        same = j["state"] == "same"
        cond = (
            " · 같은 조건"
            if same
            else f" · 조건: {L.filter_text(prev['filters'], basis=False)}"
        )
        lines = [
            f"{L.md(prev['asof'])} 저장 기록: {prev['rank']}위 · {_one_span(prev['one_month'])}{cond}"
        ]
        if j["state"] == "unknown":
            lines.append(f"같은 조건인지 확인 못 함 — {L.unknown_why(j)}")
        lines.append(now + ("" if same else f" · 조건: {L.filter_text(rv['filters'])}"))
        tag = "저장 기록 있음 · " + L.verdict_text(
            prev["verdict_state"], prev["verdict"]
        )
        return lines, "rec", tag
    s = prev["seen"]
    if s["state"] == "ranked":
        first = f"{L.md(prev['date'])} 마감 복원: {s['rank']}위 · {_one_span(s['one_month'])}"
    else:
        first = f"{L.md(prev['date'])} 마감 복원: 순위 확인 불가({L.why(s['why'])})"
    return [first, now], "", L.RESTORE_LABEL


def seen_lines(seen: Mapping[str, Any]) -> tuple[list[str], str]:
    """그때 후보로 어떻게 보였나(복원) — (줄들, 작은 글)."""
    if seen["state"] != "ranked":
        head = "조건 제외" if seen["why"] == "filter_excluded" else "순위 확인 불가"
        return [head, L.why(seen["why"])], ""
    rank = f"{seen['rank']}위 · " + ("상위 30" if seen["top30"] else "순위권 밖")
    lines = [rank, f"1개월 {_one_span(seen['one_month'])}"]
    up = seen["up"]
    if up is None:
        small = f"주간 상승 확인 불가({L.why(seen['week_gap'])})"
    elif up == 4:
        small = "네 주 모두 상승"
    elif up == 0:
        small = "네 주 모두 오르지 않음"
    else:
        small = f"네 주 중 {up}주 상승"
    if seen.get("price_state") != "after_close":
        small += " · 그날 가격 " + L.PRICE_STATE.get(
            seen.get("price_state"), "확인 필요"
        )
    return lines, small


def _pop(button: str, title: str, rows: list[tuple[str, str]]) -> str:
    """[자세히] 팝업 — 항목마다 한 줄(값 안의 줄바꿈 유지) · 브라우저 기본 대화창이라 다시 열기 화면에서도 열림."""
    items = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
    return (
        f'<button type="button" class="btn alt sm" onclick="this.nextElementSibling.showModal()">'
        f"{esc(button)}</button>"
        f'<dialog class="pop"><h3>{esc(title)}</h3><dl>{items}</dl>'
        '<form method="dialog"><button class="btn alt">닫기</button></form></dialog>'
    )


def _record_html(m: Mapping[str, Any]) -> str:
    """그 주 저장 기록 — 칸에는 순위 · 판단 두 줄만 · 나머지는 [자세히] 팝업에 항목별로."""
    rec, e, chk = m["record"], m["entry"], m.get("check")
    src_name = L.SOURCE_LABEL.get(rec["source"], rec["source"])
    if H.comparable(e):
        one = {"value": e["one_month"], "start": e["start"], "end": e["end"]}
        rank_one = deco(f"{e['rank']}위 · {_one_span(one)}")
        main = f"<b>{esc(L.md(rec['asof']))} 기록</b> · {rank_one}"
    else:
        main = f"<b>{esc(L.md(rec['asof']))} 기록</b> · 순위 · 1개월 값 없음(또는 읽을 수 없음)"
    state = H.verdict_state(rec)
    small = L.verdict_text(state, rec["verdict"]) + (
        " · 메모 있음" if rec["memo"].strip() else ""
    )
    raw = L.VERDICT_LABEL.get(rec["verdict"], rec["verdict"])
    verdict = f"저장값 '{raw}'"
    if state == "default":
        verdict += f"<br>직접 고른 값인지 모름(그 저장 화면의 기본값이 '{esc(raw)}')"
    rows = []
    if H.comparable(e):
        rows.append(("순위 · 1개월", rank_one))
    rows += [
        ("사용자 판단", verdict),
        ("저장한 곳", esc(f"「{src_name}」 · {when_kst(rec['created_at'])} 저장")),
    ]
    if rec["answers"]:
        rows.append(("저장된 AI 답", esc(" · ".join(rec["answers"]))))
    if chk:
        rows.append(("값 맞춰 보기", deco(check_text(chk))))
    same, cite = L.cite_lines(m["cite_why"])
    cond = L.filter_parts(rec["filters"], basis=False)  # 사실 하나에 한 줄
    rows.append(("그 기록의 조회 조건", "<br>".join(esc(x) for x in cond)))
    rows.append(("지금과 같은 조건인가", "<br>".join(esc(x) for x in same)))
    rows.append(("AI 질문 인용", esc(cite)))
    rows.append(
        (
            "메모(이 화면에서만)",
            (
                f'<span class="keep">{esc(rec["memo"].strip())}</span>'
                if rec["memo"].strip()
                else "없음"
            ),
        )
    )
    if rec["next_checks"]:
        rows.append(
            ("그때 적은 다음 확인", "<br>".join(esc(x) for x in rec["next_checks"]))
        )
    title = f"{L.mdw(rec['asof'])} 저장 기록 — 「{src_name}」"
    # 조회 조건이 지금과 다르거나 확인 못 한 기록은 칸에도 한 줄(외부 AI 질문에는 인용하지 않음 · 판정 §2)
    j = m["cite_why"]
    note = None if j["why"] == "no_value" else L.CITE_NOTE.get(j["state"])
    return (
        f'<div>{main}</div><div class="sub">{deco(small)} · '
        '<span class="src rec">당시 저장 기록</span></div>'
        + (f'<div class="sub">{esc(note)}</div>' if note else "")
        + _pop("자세히", title, rows)
    )


def check_text(chk: Mapping[str, Any]) -> str:
    """Q6 저장 기록과 맞춰 보기 한 줄."""
    d = L.md(chk["date"])
    if chk["state"] == "match":
        r = chk["restored"]
        got = f"{r['rank']}위 · {L.pct(r['value'], 4)}"
        return f"{d} 기준으로 다시 계산하면 {got} — 그날 저장값과 같습니다"
    if chk["state"] == "differs":
        r, s = chk["restored"], chk["stored"]
        return (
            f"{d} 기준으로 다시 계산하면 {r['rank']}위 · {L.pct(r['value'], 4)} / 저장값 {s['rank']}위 · "
            f"{L.pct(s['value'], 4)} — 다릅니다(지금 목록 · 저장 가격이 그날과 다를 수 있음)"
        )
    if chk["state"] == "period_differs":
        r, s = chk["restored"], chk["stored"]
        return (
            f"{d} 기준 다시 계산한 기간 {L.md(r['start'])} → {L.md(r['end'])} / 저장 기간 "
            f"{L.md(s['start'])} → {L.md(s['end'])} — 비교 기간이 달라 값을 맞춰 보지 않음"
        )
    if chk["state"] == "no_restore":
        return f"{d} 기준으로 다시 계산하지 못함({L.why(chk.get('why'))})"
    if chk["state"] == "filters_unknown":
        return f"{d} 기준 — 그 기록의 조회 조건 일부를 알 수 없어 다시 계산하지 않음"
    if chk["state"] == "after_end":
        return f"{d} 는 검토 끝일 뒤라 맞춰 보지 않음"
    raise ValueError(f"대조 상태를 모름: {chk['state']}")


def _pair_html(a: Mapping[str, Any]) -> str:
    out = []
    for label, key in (("ETF", "etf"), ("KODEX 200", "kodex")):
        c = a[key]
        if c["value"] is None:
            out.append(  # 이미 끝난 주의 결측(판정 2026-11-26 §2-1)
                f"<div>{label} 완료 주 마감 종가 없음 "
                f"<span class=\"sub\">{esc(L.why(c['why']))}</span></div>"
            )
        else:
            out.append(f"<div>{label} {sign_num(c['value'])}</div>")
    return "".join(out)


def _after_html(a: Mapping[str, Any]) -> str:
    if a["state"] == "not_yet":
        so = a["sofar"]
        head = '<div class="sub"><b>이번 주 지금까지</b></div>'
        if so["why"] == "no_prev_close":
            body = (
                "<div>비교 불가</div>"
                f"<div class=\"sub\">직전 주({deco(L.mdw(a['from']))}) 마감 종가 없음</div>"
            )
        elif so["end"] is None:
            body = (
                f"<div>자료 없음</div><div class=\"sub\">{esc(L.why(so['why']))}</div>"
            )
        else:
            span = f"{L.md(a['from'])} → {L.mdw(so['end'])}"
            body = f'<div class="sub">{deco(span)}</div>' + _pair_html(so)
        when = "마감 종가 아직 없음(장중 저장값)" if a.get("intraday") else "마감 예정"
        tail = f'<span class="src obs">주 진행 중</span> {deco(L.mdw(a["to"]))} {when}'
        return f'{head}{body}<div class="sub">{tail}</div>'
    if a["state"] != "ok":
        return f"<div>자료 없음</div><div class=\"sub\">{esc(L.why(a['state']))}</div>"
    if a.get("then"):  # 건너뛴 주 마감 뒤 진행 주 — 그 주 값 아래에 이어서
        span = f"{L.md(a['from'])} → {L.md(a['to'])}"
        return (
            f'<div class="sub">{deco(span)}</div>{_pair_html(a)}'
            f'<div class="thenwk">{_after_html(a["then"])}</div>'
        )
    return _pair_html(a)


def _observed(a: Mapping[str, Any]) -> bool:
    """두 종목 값이 모두 있는 '그 뒤' 칸(관측 표시)."""
    if a["state"] == "ok":
        c = a
    elif a["state"] == "not_yet" and a["sofar"]["end"] is not None:
        c = a["sofar"]
    else:
        return False
    return None not in (c["etf"]["value"], c["kodex"]["value"])


def _row_html(row: Mapping[str, Any], notes: list[str]) -> str:
    seen_main, seen_small = seen_lines(row["seen"])
    seen = "".join(
        (
            f"<div><b>{deco(t)}</b></div>"
            if i == 0 and row["seen"].get("top30")
            else f"<div>{deco(t)}</div>"
        )
        for i, t in enumerate(seen_main)
    )
    if seen_small:
        seen += (
            f'<div class="sub">{deco(seen_small)} · <span class="src">복원</span></div>'
        )
    recs = row["records"]
    cells = [_record_html(m) for m in recs["mine"]]
    for r in row["reviews"]:
        cells.append(
            f"<div><b>{esc(L.md(r['end']))} 내 판단</b> · "
            f"{esc(L.MY_VERDICT.get(r['verdict'], r['verdict']))}</div>"
            + (
                f"<div class=\"sub\">{esc(L.clip(r['reason']))}</div>"
                if r.get("reason")
                else ""
            )
        )
    if not cells and notes:
        cells.append("<div>확인 불가</div>")
        cells.append(f'<div class="sub">{esc(" · ".join(notes))}</div>')
    elif not cells:
        cells.append("<div>없음</div>")
        if recs["count"]:
            cells.append(
                f"<div class=\"sub\">그 주 저장 기록 {recs['count']}건에 이 ETF 없음</div>"
            )
    a = row["after"]
    obs = ' <span class="src obs">관측</span>' if _observed(a) else ""
    return (
        '<div class="wk">'
        f"<div class=\"cell date\">{esc(L.mdw(row['date']))}</div>"
        f'<div class="cell"><div class="lbl">그때</div>{seen}</div>'
        f"<div class=\"cell\"><div class=\"lbl\">그 주 저장 기록</div>{''.join(cells)}</div>"
        f'<div class="cell"><div class="lbl">그 뒤{obs}</div>{_after_html(a)}</div>'
        "</div>"
    )


def _peers_detail(peer: Mapping[str, Any]) -> str:
    """같은 지수의 다른 상품 — 상품마다 한 줄."""
    if peer["state"] != "ok" or not peer["other"]:
        return ""
    items = []
    for o in peer["other"]:
        why = (
            "구조가 다름(" + " · ".join(o["diff"]) + ")"
            if o["why"] == "structure"
            else "이번 조회 조건 목록에 없음"
        )
        items.append(f"<li>{esc(o['name'])}({esc(o['ticker'])}) — {esc(why)}</li>")
    return (
        f"<details><summary>같은 {esc(peer['label'])} 지수의 다른 상품 {len(items)}개 "
        "— 비교에서 뺀 이유</summary>"
        f"<ul class=\"lines\">{''.join(items)}</ul></details>"
    )


COVERAGE = {
    "full": "원천 전체 구성",
    "top_rows": "남은 구성은 미확인",
    "source_unconfirmed": "원천 전체 구성인지 미확인",
}


def _composition_detail(c: Optional[Mapping[str, Any]]) -> str:
    """구성 · 겹침(로컬 화면만) — 사실마다 한 줄 · 실제 계산한 만큼만 말한다."""
    if c is None:
        return ""
    if c["state"] == "error":
        lines = ["구성 · 겹침을 읽지 못했습니다."]
    elif c["state"] == "none":
        lines = ["저장된 구성이 없습니다(수집되지 않음)."]
    else:
        head = f"{L.md(c['asof'])} 에 저장된 " if c["asof"] else "저장된 "
        w = (
            f" = 이 ETF 편입 비중 {c['weight']:.2f}%"
            if c["weight"] is not None and not c["weight_missing"]
            else ""
        )
        lines = [
            f"{head}{c['rows']}종목{w}",
            "범위: " + COVERAGE.get(c.get("coverage"), "원천 전체 구성인지 미확인"),
        ]
        if c["top"]:
            lines.append("상위: " + " · ".join(str(t) for t in c["top"]))
        ov = c["overlap"]
        if ov is None:
            lines.append("내 보유와의 겹침: 확인하지 못했습니다.")
        else:
            hits = ov["hits"]
            lines.append(
                f"내 보유와의 겹침: 이 ETF 상위 {ov['checked']}종목 중 내 보유 쪽 저장 구성에서 "
                f"확인된 중복 주식 {len(hits)}종목"
                + (f"({' · '.join(str(h) for h in hits)})" if hits else "")
            )
            if ov.get("other_date"):
                lines.append(
                    f"기준일이 다른 구성에서만 겹치는 주식 {len(ov['other_date'])}종목은 "
                    "중복으로 세지 않았습니다."
                )
            lines.append("내 보유 쪽 저장 구성 밖은 확인하지 못했습니다.")
    items = "".join(f"<li>{esc(x)}</li>" for x in lines)
    return (
        "<details><summary>구성 · 겹침(이 화면에서만 · 복사문에 넣지 않음)</summary>"
        f'<ul class="lines">{items}</ul></details>'
    )


# --- 조각(저장 때 고정) ---


def one_html(rv: Mapping[str, Any]) -> str:
    one, k = rv["one_month"], rv["kodex"]
    rank = f"1개월 <b>{rv['rank']}위</b>" + ("" if rv["top30"] else " · 상위 30 밖")
    span = deco(f"{L.md(one['start'])} ~ {L.md(one['end'])}")
    lead = f"{span} {sign_num(one['value'])} · {rank}"
    facts = []

    def fact(key: str, val: str) -> None:
        facts.append(
            f'<li><div class="k">{esc(key)}</div><div class="v">{val}</div></li>'
        )

    same = k is not None and (k["start"], k["end"]) == (one["start"], one["end"])
    fact("같은 기간 KODEX 200", sign_num(k["value"]) if same else "확인 불가")
    fact("최근 네 주", deco(L.up_text(rv)))
    pt = L.peer_text(rv)
    if pt:
        head, _, tail = pt.partition(". ")
        fact("확인된 근거", deco(head + ".") + ("<br>" + deco(tail) if tail else ""))
    ft = flow_text(rv)
    if ft:
        fact(
            "순위 흐름",
            deco(ft) + f'<br><span class="src">{esc(L.RESTORE_LABEL)}</span>',
        )
    pv = previous_lines(rv)
    if pv:
        lines, cls, tag = pv
        fact(
            "지난 검토와 비교",
            "<br>".join(deco(x) for x in lines)
            + f'<br><span class="src {cls}">{esc(tag)}</span>',
        )
    fact("자료 공백", deco(rv["gap"]["text"]))
    notes = L.record_notes(rv)
    if notes:
        fact(
            "저장 기록 읽기",
            esc(
                " · ".join(notes) + " — 위 '지난 검토'는 읽은 기록만으로 만들었습니다."
            ),
        )
    return (
        '<h2><span class="step">1</span>왜 이번에 보나</h2>'
        f'<div class="lead">{lead}</div>'
        f"<div class=\"sub\">「주간 ETF 점검」 조건({esc(L.filter_text(rv['filters']))}) "
        f"{rv['population']}개 중</div>"
        f"<ul class=\"facts\">{''.join(facts)}</ul>"
    )


def weeks_html(rv: Mapping[str, Any]) -> str:
    w = rv["weeks"]
    if not w.get("rows"):
        return (
            '<section class="card"><h2>지난 네 주</h2>'
            "<div>주 마감일을 정하지 못해 지난 네 주를 보일 수 없습니다"
            f"({esc(L.why(w.get('why')))}).</div></section>"
        )
    wk = rv["weekly"]
    base = wk.get("w0") if wk.get("finished") else rv["end"]
    sub = f"검토가 속한 주({L.md(base)} 주) 직전 네 완료 주 · 실제 거래 일정의 마감일"
    skipped = [s for s in w.get("skipped") or [] if s.get("why") != "week_unfinished"]
    if skipped:
        sub += " · 건너뛴 주 " + ", ".join(
            f"{L.md(s['week_last'])}({s['why']})" for s in skipped
        )
    checks = [
        check_text(m["check"])
        for row in w["rows"]
        for m in row["records"]["mine"]
        if m.get("check")
    ]
    prev = rv["previous"]
    if prev and prev["kind"] == "session" and prev.get("check"):
        t = check_text(prev["check"])
        if t not in checks:
            checks.append(t)
    late = rv["sessions"].get("late")
    parts = [
        "'그때' 순위 · 1개월 값 = 현재 ETF 목록과 저장 가격으로 복원한 값 — 그 마감일 기준으로 다시 "
        "계산했고, 그날 화면에 보였던 값 그대로가 아닐 수 있습니다.",
        "다시 계산은 그 마감일까지의 가격과 같은 조회 조건만 씁니다. 상장폐지 등으로 그때 목록과 다를 수 있습니다.",
    ]
    parts += [f"저장 기록과 맞춰 보기: {c}." for c in checks] or [
        "맞춰 볼 저장 기록이 없습니다."
    ]
    parts.append("'그 뒤' 값은 그때 판단에 쓰지 않은 나중 값입니다.")
    wk_open = OB.open_week(w["rows"][-1])
    progress = wk_open is not None
    if progress:
        parts.append(
            "'이번 주 지금까지' = 거래 일정상 직전 완료 주 마감 → 이 ETF 와 KODEX 200 에 공통으로 마감 뒤 저장한 "
            "종가가 있는 마지막 날(검토 기준일까지). 직전 주 마감에 두 종목 마감 종가가 다 있지 않으면 비교 불가로 "
            "적고, 더 오래된 날부터의 변화는 그래프(실제 기간)로만 봅니다."
        )
    f = rv.get("flow") or {}
    if f.get("state") == "ok":
        parts.append(
            "그래프는 표의 첫 주 마감 종가를 0% 로 두고, 마감 뒤 저장한 종가만으로 그렸습니다."
        )
        if progress and f["last"] and f["last"] == wk_open["sofar"]["end"]:
            parts.append(
                "그래프 끝 값과 표의 '이번 주 지금까지'는 같은 날 종가로 계산합니다."
            )
    if late:
        cut = when_kst(rv["sessions"]["cutoff"])
        parts.append(
            f"검토 시점({cut}) 이후에 만든 이 ETF 기록 · 내 판단 {late}건은 넣지 않았습니다."
        )
    basis = "".join(f"<li>{deco(x)}</li>" for x in parts)
    notes = L.record_notes(rv)
    rows = "".join(_row_html(r, notes) for r in w["rows"])
    after_head = "그 뒤 다음 주 마감까지" + (
        "<br>(이번 주는 지금까지)" if progress else ""
    )
    return (
        '<section class="card"><h2>지난 네 주</h2>'
        f'<div class="sub">{deco(sub)}</div>'
        f"{chart_html(rv, rv['name'])}"
        '<div class="weeks"><div class="wk head"><div>주 마감</div>'
        "<div>그때 후보로 어떻게 보였나</div>"
        f"<div>그 주 저장 기록</div><div>{after_head}</div></div>"
        f"{rows}</div>"
        "<details><summary>이 표의 값은 어떻게 구했나</summary>"
        f'<ul class="lines">{basis}</ul></details>'
        f"{_peers_detail(rv['peer'])}{_composition_detail(rv['composition'])}"
        "</section>"
    )


def ask_html(rv: Mapping[str, Any], *, live: bool) -> str:
    a = rv["ask"]
    look = a["look"]
    items = [f"<li><b>답에서 볼 것</b> · {deco(look[0])}</li>"] + [
        f"<li>{deco(x)}</li>" for x in look[1:]
    ]
    button = (
        '<div class="btnrow"><button class="btn" type="button" id="copy">AI 질문 복사</button>'
        '<span id="copymsg">복사한 질문을 평소 쓰는 AI 채팅에 붙여 넣으세요.</span></div>'
        if live
        else '<div class="sub">저장할 때 화면에 있던 질문과 복사문입니다.</div>'
    )
    return (
        '<section class="card ai"><h2><span class="step">2</span>AI에 확인할 것</h2>'
        f"<div class=\"ask\">{deco(a['text'])}</div>{button}"
        f"<ul class=\"look\">{''.join(items)}</ul>"
        '<details id="copybox"><summary>복사되는 전체 글 보기</summary>'
        f"<pre id=\"copytext\">{esc(rv['copy'])}</pre></details>"
        "</section>"
    )


def screen_parts(rv: Mapping[str, Any]) -> dict[str, str]:
    """저장 때 고정하는 화면 조각."""
    return {
        "sub": esc(sub_line(rv)),
        "one": one_html(rv),
        "weeks": weeks_html(rv),
        "ask": ask_html(rv, live=False),
    }
