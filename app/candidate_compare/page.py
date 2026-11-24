"""이번 주 로컬 연구 HTML 한 장(판정 Q1 · §4 · 목업 V1) — 외부 글꼴 · 외부 호출 없음.

순서 = 맨 위(날짜 · 연구 중 표시) → ① 전체 범위 → ② 먼저 볼 세 후보와 이유 → 전체 목록(기본 접힘 · [상세])
→ ③ 후보 상세(모든 후보의 상세를 미리 만들어 두고 고르면 바꿈) → ④ AI 비교 묶음([복사] · 고른 후보 줄 추가).
"""

from __future__ import annotations

import html
import json
from typing import Any, Mapping, Optional

from app.candidate_compare import texts as TX

CSS = """
:root{--bg:#f6f7f4;--card:#fff;--fg:#1d2420;--muted:#5d6862;--line:#dfe3dd;
--accent:#1f6f5c;--accent-soft:#e3f0eb;--up:#b42318;--down:#1f5fb4;--flat:#7a847e;
--warn:#8a5a00;--warn-soft:#fbf1dc;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#151917;--card:#1e2421;--fg:#e6ebe7;
--muted:#9aa59f;--line:#333b37;--accent:#6cc3a8;--accent-soft:#1f3a32;--up:#ff8a7a;
--down:#8ab4ff;--flat:#9aa59f;--warn:#e8b85a;--warn-soft:#3a2f17;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.6 -apple-system,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:20px 16px 48px;display:grid;
grid-template-columns:minmax(0,1fr);gap:16px}
h1{font-size:22px;margin:0}h2{font-size:17px;margin:0 0 8px}
.sub{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;
min-width:0}
.dates{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--muted)}
.dates b{color:var(--fg)}
.status{background:var(--warn-soft);color:var(--warn);border-radius:8px;padding:8px 12px;
font-size:14px;margin-top:6px}
.badge{display:inline-block;background:var(--warn-soft);color:var(--warn);border-radius:4px;
padding:0 6px;font-size:12px}
.nums{display:flex;flex-wrap:wrap;gap:8px 24px;margin:4px 0 12px}
.nums .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
.nums .k{font-size:12px;color:var(--muted)}
.dist{display:grid;gap:4px;max-width:520px}
.dist .row{display:grid;grid-template-columns:96px 1fr 52px;gap:8px;align-items:center;
font-size:13px}
.dist .bar{height:12px;background:var(--accent-soft);border-radius:3px;overflow:hidden}
.dist .bar i{display:block;height:100%;background:var(--accent)}
.dist .n{text-align:right;font-variant-numeric:tabular-nums}
.btn{display:inline-block;border:1px solid var(--accent);color:var(--accent);
background:transparent;border-radius:8px;padding:0 14px;height:40px;line-height:38px;
font-size:14px;cursor:pointer;font-family:inherit}
.btn.primary{background:var(--accent);color:var(--card)}
.btn.sm{height:30px;line-height:28px;padding:0 10px;font-size:13px}
.btnrow{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
details.list>summary{list-style:none;cursor:pointer}
details.list>summary::-webkit-details-marker{display:none}
.tbl{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;white-space:nowrap}
th{color:var(--muted)}td.r,th.r{text-align:right}
.wk span{display:inline-block;width:18px;text-align:center}
.u{color:var(--up)}.d{color:var(--down)}.f{color:var(--flat)}.na{color:var(--warn)}
.tag{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:4px;
padding:0 5px;color:var(--muted)}
.tag.top{border-color:var(--accent);color:var(--accent)}
.pick{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.pc{border:1px solid var(--line);border-radius:8px;padding:12px;display:grid;gap:6px;
min-width:0}
.pc .t{font-weight:700}.pc .m{font-size:13px;color:var(--muted)}
.diff{margin-top:10px;background:var(--accent-soft);border-radius:8px;padding:10px 12px;
font-size:14px}
.lead{font-size:16px;font-weight:600;margin:0 0 4px}
.kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:6px 12px;font-size:14px;
margin-top:8px}
.kv .k{color:var(--muted)}
@media (max-width:560px){.kv{grid-template-columns:minmax(0,1fr)}.kv .k{margin-top:6px}}
.weeks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.weeks div{border:1px solid var(--line);border-radius:6px;padding:6px;font-size:12px;
text-align:center}
.weeks b{display:block;font-size:14px}
.copy{width:100%;font:13px/1.55 ui-monospace,Menlo,monospace;background:var(--bg);
color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px;
white-space:pre-wrap;overflow-wrap:anywhere;margin:0}
.note{font-size:12px;color:var(--muted);margin-top:6px}ul.plain{margin:0;padding-left:18px}
"""

JS = """
(function(){
var data=JSON.parse(document.getElementById('cc-data').textContent);
var box=document.getElementById('detail'),copy=document.getElementById('copyText');
var done=document.getElementById('copied');
var current=data.selected;
function render(){
  var t=document.getElementById('d-'+current);if(t){box.innerHTML=t.innerHTML;}
  copy.textContent=data.head+(data.tails[current]||'');
}
document.addEventListener('click',function(e){
  var b=e.target.closest('[data-t]');if(!b)return;
  current=b.getAttribute('data-t');render();
  box.scrollIntoView({behavior:'smooth',block:'start'});
});
function shown(m){done.textContent=m;done.hidden=false;
  setTimeout(function(){done.hidden=true;},2500);}
function fallback(){
  var r=document.createRange();r.selectNodeContents(copy);
  var s=window.getSelection();s.removeAllRanges();s.addRange(r);
  try{if(document.execCommand('copy')){shown('복사했습니다');return;}}catch(x){}
  shown('글을 선택해 두었습니다 — ⌘C 로 복사하세요');
}
document.getElementById('copyBtn').addEventListener('click',function(){
  var t=copy.textContent;
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t).then(function(){shown('복사했습니다');},fallback);
  }else{fallback();}
});
render();
})();
"""

MOVE = {"up": ("u", "▲"), "down": ("d", "▼"), "flat": ("f", "－"), "none": ("f", "?")}


def up_text(it: Mapping[str, Any]) -> str:
    return "미확인" if it["up"] is None else f"{it['up']}번"


def e(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def _dates(data: Mapping[str, Any], verdict: Optional[str]) -> str:
    wk = data["weekly"]
    om = data["windows"]["one_month"]
    k1 = (data["kodex"].get("one_month") or {}).get("value")
    state = {
        "after_close": "마감 뒤 저장",
        "intraday": "장중 저장 · 마감값 아님",
    }.get(data["bench_state"], "저장 시각 불명")
    mid = ' <span class="badge">주중 참고</span>' if wk.get("mid_week") else ""
    weeks = " → ".join(TX.md(d) for d in wk["dates"]) if wk["dates"] else "확인 불가"
    status = verdict or "아직 판정 전"
    note = TX.week_note(wk, om[1])
    return (
        '<section class="card"><h1>이번 주 ETF 전체 비교</h1><div class="dates">'
        f"<span>1개월 <b>{TX.md(om[0])} → {TX.md(om[1])}({TX.wday(om[1])})</b> · {e(state)}</span>"
        f"<span>네 주 <b>{e(weeks)}</b>{mid}</span>"
        f"<span>비교 기준 <b>KODEX 200</b>(1개월 {e(TX.pct(k1))})</span></div>"
        + (f'<div class="sub">{e(note)}</div>' if note else "")
        + f'<div class="status">이 순서는 <b>연구 중인 기준</b>입니다. 과거 비교 결과: {e(status)}</div></section>'
    )


def _range(data: Mapping[str, Any]) -> str:
    c = data["counts"]
    dist = data["up_distribution"]
    mx = max(dist.values()) or 1
    rows = "".join(
        f'<div class="row"><span>{label}</span><span class="bar">'
        f'<i style="width:{100 * dist[key] / mx:.0f}%"></i>'
        f'</span><span class="n">{dist[key]}</span></div>'
        for key, label in (
            ("4", "4번 모두"),
            ("3", "3번"),
            ("2", "2번"),
            ("1", "1번"),
            ("0", "0번"),
            ("none", "미확인"),
        )
    )
    excl = (
        f"전체 {c.get('universe', 0)}개 중 가격 없음 {c.get('no_price', 0)} · 인버스 · 레버리지 · 합성 · 선물 "
        f"{c.get('filter_excluded', 0)} · 1개월 계산 불가 {c.get('no_return', 0)} · 기간 다름 "
        f"{c.get('end_differs', 0) + c.get('start_differs', 0)}개를 뺐습니다."
    )
    return (
        '<section class="card"><h2>① 전체 범위</h2><div class="nums">'
        f'<div><div class="v">{c["population"]}개</div><div class="k">비교한 ETF</div></div>'
        f'<div><div class="v">{sum(1 for it in data["items"] if it["top30"])}개</div>'
        '<div class="k">기존 「주간 ETF 점검」 상위</div></div>'
        f'<div><div class="v">{dist["none"]}개</div>'
        "<div class=\"k\">주 마감값을 확인하지 못해 '오른 횟수 미확인'</div></div>"
        '</div><div class="sub" style="margin-bottom:6px">지난 네 주 중 오른 주가 몇 번이었나'
        f'(변화 없음은 오름으로 세지 않음)</div><div class="dist">{rows}</div>'
        f'<div class="note">{e(excl)}</div></section>'
    )


def _picks(data: Mapping[str, Any], why: Mapping[str, Any]) -> str:
    by = {it["ticker"]: it for it in data["items"]}
    cards = []
    for n, p in enumerate(why["picks"], 1):
        it = by[p["ticker"]]
        where = "" if it["top30"] else " · 상위 30 밖"
        cards.append(
            f'<div class="pc"><div class="t">{n}. {e(it["name"])}</div><div>{e(p["text"])}</div>'
            f'<div class="m">1개월 {e(TX.pct(it["one_month"]["value"]))}({it["rank"]}위{where}) · '
            f'오른 주 {it["up"]}번</div>'
            f'<button class="btn" type="button" data-t="{e(it["ticker"])}">자세히 보기'
            "</button></div>"
        )
    return (
        '<section class="card"><h2>② 먼저 볼 후보</h2>'
        '<div class="sub" style="margin-bottom:8px">1개월 수익률이 '
        "플러스인 ETF 중, 지난 네 주에 오른 주가 많은 순서입니다. 같으면 1개월 순위를 따릅니다.</div>"
        f'<div class="pick">{"".join(cards)}</div>'
        f'<div class="diff">{e(why["diff"])}</div></section>'
    )


def _list(data: Mapping[str, Any]) -> str:
    rows = []
    for it in data["items"]:
        marks = "".join(
            f'<span class="{MOVE[m][0]}">{MOVE[m][1]}</span>' for m in it["moves"]
        )
        tags = [
            (
                '<span class="tag top">상위 30</span>'
                if it["top30"]
                else '<span class="tag">상위 30 밖</span>'
            )
        ]
        if it.get("family_size") and it["family_size"] > 1:
            tags.append(
                f'<span class="tag">같은 기초지수 계열 {it["family_size"]}개(전체 목록 안)</span>'
            )
        if it["up"] is None:
            why = TX.WEEK_GAP_TEXT.get(it.get("week_gap"), "주 마감값 미확인")
            tags.append(f'<span class="tag">{e(why)} — 오른 주 미확인</span>')
        if it["state"] in TX.STATE_TEXT:
            tags.append(f'<span class="tag">{e(TX.STATE_TEXT[it["state"]])}</span>')
        cr = (
            it["common_rank"]
            if it["common_rank"] is not None
            else '<span class="na">미확인</span>'
        )
        up = it["up"] if it["up"] is not None else '<span class="na">미확인</span>'
        cls = (
            "u"
            if it["one_month"]["value"] > 0
            else ("d" if it["one_month"]["value"] < 0 else "f")
        )
        rows.append(
            f'<tr><td class="r">{it["rank"]}</td><td class="r">{cr}</td><td>{e(it["name"])}</td>'
            f'<td class="r {cls}">{e(TX.pct(it["one_month"]["value"]))}</td>'
            f'<td class="wk">{marks}</td>'
            f'<td class="r">{up}</td><td>{" ".join(tags)}</td>'
            f'<td><button class="btn sm" type="button" data-t="{e(it["ticker"])}">상세</button>'
            "</td></tr>"
        )
    return (
        '<section class="card"><details class="list"><summary><span class="btn">전체 목록 열기 '
        f'({len(data["items"])}개)</span> <span class="sub">기본은 접혀 있습니다 · 상위 30 밖도 골라 상세를 볼 수 '
        '있습니다</span></summary><div class="tbl"><table><thead><tr><th class="r">1개월 순위</th>'
        '<th class="r">공통 순위</th><th>ETF</th><th class="r">1개월</th><th>네 주</th>'
        '<th class="r">오른 주</th>'
        f'<th>표시</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        '<div class="note">1개월 순위 = 비교한 전체 안의 순위(기존 「주간 ETF 점검」과 같은 규칙) · 공통 순위 = 주 마감값이 '
        "모두 확인된 후보 안의 순위. ▲ 오름 · ▼ 내림 · － 변화 없음 · ? 주 마감값 미확인. "
        "같은 기초지수 계열 = 기존 「주간 ETF 점검」과 같은 계열 규칙(같은 공식 기초지수 · 확인된 같은 지수 묶음)"
        "으로 전체 목록 안에서 센 수.</div></details></section>"
    )


def _detail(it: Mapping[str, Any], data: Mapping[str, Any]) -> str:
    wk = data["weekly"]["dates"] or []
    boxes = "".join(
        f'<div>{TX.md(a)} → {TX.md(b)}<b class="{MOVE[m][0]}">{e(TX.chg(c))}</b></div>'
        for a, b, m, c in zip(wk, wk[1:], it["moves"], it["changes"])
    )
    det = it.get("detail") or {}
    cons = (det.get("constituents") or {}).get("line") or "구성 자료를 읽지 못함"
    ov = det.get("overlap") or {}
    ov_lines = [
        x.replace("[다시 읽기]로 다시 시도", "한 장을 다시 만들어 다시 시도")
        for x in (ov.get("warn_lines") or []) + (ov.get("lines") or [])
    ]
    if ov.get("date_line"):
        ov_lines.append(ov["date_line"])
    if not ov_lines:
        ov_lines = ["보유 겹침을 계산하지 못했습니다(겹침 없음이라는 뜻 아님)."]
    li = "".join(f"<li>{e(x)}</li>" for x in ov_lines)
    scope = "".join(f"<li>{e(x)}</li>" for x in TX.scope_lines(it))
    return (
        f'<h2>③ 후보 상세 — {e(it["name"])}({e(it["ticker"])})</h2>'
        f'<p class="lead">{e(TX.lead(it, data["kodex"]))}</p><div class="kv">'
        f'<div class="k">3개월</div><div>{e(TX.three_line(it, data["kodex"]))}</div>'
        f'<div class="k">네 주 구간</div><div><div class="weeks">{boxes}</div></div>'
        f'<div class="k">순위</div><div>1개월 {it["rank"]}위 · 공통 '
        + (f'{it["common_rank"]}위' if it["common_rank"] is not None else "미확인")
        + f" · 오른 주 {up_text(it)}</div>"
        f'<div class="k">구성 자료</div><div>{e(cons)}</div>'
        f'<div class="k">내 보유와 겹침</div><div><ul class="plain">{li}</ul></div>'
        f'<div class="k">어디까지 말할 수 있나</div><div><ul class="plain">{scope}</ul></div>'
        f'<div class="k">다음 확인 한 가지</div><div><b>{e(TX.next_check(it))}</b></div></div>'
        '<div class="note">구성종목은 저장된 것만 씁니다(새로 조회하지 않음). 보유 비중 같은 개인 자료는 이 로컬 상세에만 '
        "보이고 복사문에는 넣지 않습니다.</div>"
    )


def render(
    data: Mapping[str, Any], *, generated_at: str, verdict: Optional[str] = None
) -> str:
    if not data.get("items"):
        raise ValueError("비교할 후보가 없음 — 한 장을 만들지 않음")
    why = TX.reasons(data)
    by_t = {it["ticker"]: it for it in data["items"]}
    selected = data["picks_b"][0] if data["picks_b"] else data["items"][0]["ticker"]
    templates = "".join(
        f'<template id="d-{e(it["ticker"])}">{_detail(it, data)}</template>'
        for it in data["items"]
    )
    payload = {
        "selected": selected,
        "head": TX.copy_head(data),
        "tails": {t: TX.copy_tail(data, t) for t in by_t},
    }
    blob = (
        json.dumps(payload, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("<!--", "<\\u0021--")
    )
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>주간 ETF 전체 비교</title>"
        f'<style>{CSS}</style></head><body><div class="wrap">'
        + _dates(data, verdict)
        + _range(data)
        + _picks(data, why)
        + _list(data)
        + '<section class="card" id="detail"></section>'
        + '<section class="card"><h2>④ AI 에 물을 비교 묶음</h2>'
        '<div class="btnrow" style="margin:0 0 8px">'
        '<button class="btn primary" id="copyBtn" type="button">복사</button>'
        '<span class="sub" id="copied" hidden></span></div><pre class="copy" id="copyText"></pre>'
        '<div class="note">순서는 프로그램이 계산합니다. AI 는 위 묶음의 대상 · 기간 · 근거로 차이를 설명합니다. '
        "첫 문단은 기존 '최신 공개 자료 확인' 문단 그대로입니다.</div></section>"
        f'<div class="note">연구 화면(운영 화면 아님) · 만든 시각 {e(generated_at)} · 가격 = PC 저장 종가(분배금 미반영 · '
        "과거 비교의 봉인 KRX 가격과 출처가 다름)</div>"
        f"{templates}</div>"
        f'<script type="application/json" id="cc-data">{blob}</script>'
        f"<script>{JS}</script></body></html>"
    )
