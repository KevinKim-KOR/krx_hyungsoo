"""화면 공통 틀 — CSS(목업 V1) · 글 꾸미기(부호 색 · 줄 중간 쪼개짐 방지) · 기록 시각(한국 시각) · 문서 껍데기."""

from __future__ import annotations

import html
import re
from typing import Any

from app.weekly_decision import history as H
from app.weekly_decision import lines as L

CSS = """
:root { --bg:#f6f7f9; --card:#fff; --fg:#1d2330; --mute:#5b6472; --line:#e2e6ec; --up:#c62828;
  --down:#1565c0;
  --acc:#2f5bd3; --ai:#eef4ff; --aib:#c9d8fb; --mine:#eef7f0; --mineb:#bfe0c8; --warn:#fff8e6;
  --warnb:#f0d98c;
  --warnfg:#6b5200; --bad:#b3261e;
  --s-etf:#0f8f63; --s-kdx:#8c5bd6; --grid:#eef1f5; --zero:#b8bec8; --band:#fff4d6;
  --gapday:#e6e8ec; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.6 -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
  word-break:keep-all; overflow-wrap:break-word; }
.wrap { max-width:920px; margin:0 auto; padding:16px; display:flex; flex-direction:column;
  gap:14px; }
.banner { background:var(--warn); border:1px solid var(--warnb); border-radius:10px;
  padding:10px 14px; font-size:13px; color:var(--warnfg); }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }
h1 { font-size:20px; margin:0 0 4px; }
h2 { font-size:16px; margin:0 0 8px; display:flex; align-items:center; gap:8px; }
.step { display:inline-flex; width:24px; height:24px; border-radius:50%; background:var(--fg);
  color:#fff; font-size:13px;
  align-items:center; justify-content:center; flex:none; }
.sub { color:var(--mute); font-size:13px; }
.nw { white-space:nowrap; }
.up { color:var(--up); } .down { color:var(--down); }
.pick { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:10px 0 4px; }
.pick select { font-size:15px; padding:8px 10px; border:1px solid var(--line); border-radius:8px;
  max-width:100%; background:#fff; }
.lead { font-size:18px; font-weight:700; margin:12px 0 2px; }
.facts { list-style:none; margin:12px 0 0; padding:0; display:grid; gap:10px; }
.facts li { display:grid; grid-template-columns:150px 1fr; gap:4px 14px; }
.facts .k { color:var(--mute); font-size:13px; padding-top:2px; }
.facts .v { min-width:0; }
.src { display:inline-block; font-size:11px; border-radius:6px; padding:0 6px;
  border:1px solid #b9c4dc; color:#40527a; white-space:nowrap; }
.src.rec { border-color:#9bc59f; color:#2e6b34; }
.src.obs { border-color:#d6c49b; color:#7a5b00; }
.ai { background:var(--ai); border:1px solid var(--aib); }
.ask { font-size:18px; font-weight:700; margin:6px 0 10px; }
.btnrow { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
.btn { height:48px; padding:0 18px; border-radius:8px; border:1px solid var(--acc);
  background:var(--acc); color:#fff;
  font-size:16px; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex;
  align-items:center; }
.btn.alt { background:#fff; color:var(--acc); height:40px; font-size:14px; font-weight:500; }
.btn[disabled] { opacity:.5; cursor:not-allowed; }
.look { margin:12px 0 0; padding-left:18px; }
.look li { margin:2px 0; }
details { margin-top:10px; }
summary { cursor:pointer; color:var(--acc); }
pre { white-space:pre-wrap; word-break:break-word; background:#fff; border:1px solid var(--line);
  border-radius:8px; padding:12px;
  font-size:13px; margin:8px 0 0; }
.mine { background:var(--mine); border:1px solid var(--mineb); }
.choice { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 10px; }
.choice label { border:1px solid var(--line); background:#fff; border-radius:8px;
  padding:10px 14px; font-size:15px; }
.form { display:grid; gap:10px; }
.field { display:grid; gap:4px; }
.field > span { font-size:13px; color:var(--mute); }
input[type=text], textarea, .form select { width:100%; font-size:14px; padding:9px;
  border:1px solid var(--line); border-radius:8px;
  font-family:inherit; background:#fff; }
.checks { display:flex; flex-wrap:wrap; gap:6px 14px; font-size:14px; }
.msg { font-size:14px; white-space:pre-line; }
.msg.bad { color:var(--bad); font-weight:600; }
.weeks { display:grid; gap:0; margin-top:8px; }
.wk { display:grid; grid-template-columns:92px 1.4fr 1.3fr 1fr; gap:10px; padding:10px 4px;
  border-bottom:1px solid var(--line); }
.wk > .cell { min-width:0; }
.wk.head { font-size:12px; color:var(--mute); font-weight:600; padding-top:4px; }
.wk .cell div { line-height:1.5; }
.wk .lbl { display:none; font-size:12px; color:var(--mute); }
.date { font-weight:600; }
.list { list-style:none; margin:8px 0 0; padding:0; display:grid; gap:8px; }
.list li { border-bottom:1px solid var(--line); padding-bottom:8px; }
.olditem { border-top:1px solid var(--line); padding:8px 0; font-size:13px; }
.btn.sm { height:30px; padding:0 10px; font-size:13px; margin-top:4px; }
ul.lines { margin:6px 0 0; padding-left:18px; font-size:13px; color:var(--mute); display:grid;
  gap:4px; }
.keep { white-space:pre-wrap; }
dialog.pop { width:min(560px, calc(100% - 32px)); border:1px solid var(--line); border-radius:12px;
  padding:16px 18px; color:var(--fg); background:var(--card); }
dialog.pop::backdrop { background:rgba(20, 24, 33, .45); }
dialog.pop h3 { font-size:16px; margin:0 0 10px; }
dialog.pop dl { display:grid; grid-template-columns:120px 1fr; gap:8px 14px; margin:0 0 14px;
  font-size:14px; }
dialog.pop dt { color:var(--mute); font-size:13px; padding-top:1px; }
dialog.pop dd { margin:0; min-width:0; overflow-wrap:anywhere; }
dialog.pop form { display:flex; justify-content:flex-end; }
.aibox { border:1px solid var(--mineb); background:#fff; border-radius:10px; padding:10px 12px;
  display:grid; gap:6px; }
.aihead { display:flex; justify-content:space-between; align-items:center; gap:10px;
  flex-wrap:wrap; }
.aihead .like { font-size:14px; white-space:nowrap; }
.aihead .like:has(input:disabled) { color:var(--mute); }
.ailist { display:grid; gap:10px; }
.likebadge { display:inline-block; font-size:12px; border:1px solid var(--mineb);
  background:var(--mine); border-radius:999px; padding:0 8px; }
.thenwk { margin-top:6px; padding-top:6px; border-top:1px dashed var(--line); }
.flow { margin:10px 0 8px; display:grid; gap:2px; }
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:13px; margin-top:4px; }
.legend i { display:inline-block; width:14px; height:3px; border-radius:2px; vertical-align:middle;
  margin-right:6px; }
.plot { margin-top:4px; }
.fsvg { display:none; width:100%; height:auto; }
.fsvg.w { display:block; max-width:820px; }
.fsvg .ax { font-size:11px; fill:var(--mute); }
.fsvg .rk { font-size:12px; fill:var(--mute); }
.fsvg .rk.top { fill:var(--fg); font-weight:700; }
.fsvg .lab { font-size:12px; fill:var(--fg); font-variant-numeric:tabular-nums; }
.fsvg .bandname { font-size:12px; fill:var(--warnfg); font-weight:600; }
.fsvg .band { fill:var(--band); }
.fsvg .gapday { fill:var(--gapday); }
.fsvg .grid { stroke:var(--grid); stroke-width:1; }
.fsvg .zero { stroke:var(--zero); stroke-width:1; }
.fsvg .wkline { stroke:var(--grid); stroke-width:1; stroke-dasharray:3 3; }
.fsvg .line { stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }
.fsvg .dot { stroke:var(--card); stroke-width:2; }
.fsvg .hit { fill:transparent; }
@media (max-width: 899px) {
  .fsvg.w { display:none; }
  .fsvg.m { display:block; max-width:530px; }
}
@media (max-width: 600px) {
  .fsvg.m { display:none; }
  .fsvg.n { display:block; max-width:340px; }
  .facts li { grid-template-columns:1fr; }
  .wk.head { display:none; }
  .wk { grid-template-columns:1fr; gap:6px; border:1px solid var(--line); border-radius:10px;
  margin-bottom:10px; padding:12px; }
  .wk .lbl { display:block; }
  dialog.pop dl { grid-template-columns:1fr; gap:2px; }
  dialog.pop dd { margin-bottom:8px; }
}
"""

_PCT = re.compile(r"[+\u2212]?\d+\.\d+%p?")
_DATE = re.compile(
    r"\d{1,2}/\d{1,2}(?:\([월화수목금토일]\))?(?:\s?(?:→|~)\s?\d{1,2}/\d{1,2}(?:\([월화수목금토일]\))?)?"
)
_RANKS = re.compile(r"\(\d+(?: · \d+)*위\)|\d+위")
_QUOTED = re.compile(r"'[^'<>&]{1,12}'")
_TOKENS = re.compile(
    "|".join(f"(?:{p.pattern})" for p in (_PCT, _DATE, _RANKS, _QUOTED))
)
MINUS = L.MINUS


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def deco(text: str) -> str:
    """글 → HTML — 부호 수익률 색 · 날짜 범위 · 순위 · 짧은 상태명 줄 중간 쪼개짐 방지(글자는 그대로)."""
    # 글 내용 자리라 따옴표는 그대로 둔다('보류' 같은 상태명을 감싸려고) — <, >, & 만 바꾼다
    out = html.escape(text, quote=False)

    def wrap(m: re.Match) -> str:
        t = m.group(0)
        cls = "nw"
        if _PCT.fullmatch(t):
            cls = "up nw" if t.startswith("+") else "down nw" if t[0] == MINUS else "nw"
        return f'<span class="{cls}">{t}</span>'

    # 서로 겹치지 않는 토큰을 한 번에 감싼다(이미 감싼 안쪽을 다시 감싸지 않게)
    return _TOKENS.sub(wrap, out)


def sign_num(v: float) -> str:
    return deco(L.pct(v))


def when_kst(ts: Any) -> str:
    """기록 시각 → 'M/D HH:MM'(한국 시각 · 시간대 없으면 한국 시각으로 봄)."""
    t = H.parse_time(ts)
    if t is None:
        return str(ts)[:16]
    return f"{t.month}/{t.day} {t:%H:%M}"


def document(title: str, body: str, script: str = "") -> str:
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{CSS}</style></head>"
        f'<body><div class="wrap">{body}</div>'
        f"{script}</body></html>"
    )
