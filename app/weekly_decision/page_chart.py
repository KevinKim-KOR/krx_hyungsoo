"""지난 네 주 흐름 그래프(V2 판정 2026-11-25 Q6 · §3) — 서버가 SVG 로 그린다(화면 스크립트 없음).

```text
자료   rv["flow"](flow.flow) — 첫 완료 주 마감 = 0% · 끝일까지 일정상 거래일마다 두 종목 누적 변화
그림   넓은 화면 · 중간 · 좁은 화면(420px) 세 장 — 화면 폭에 따라 한 장만 보임(글자가 줄지 않게 · page_base CSS)
표식   완료 주 마감마다 점 · 아래에 날짜와 그 마감 순위(복원 · 주가 끝났으면 마지막 = 그 주 마감)
진행   진행 주는 띠를 칠하고 '이번 주 진행 중 · 날짜 순위'(진행 주 순위는 늘 띠 이름에 · 점 아래 = 완료 주 마감만)
빠짐   값이 빠진 날은 선을 끊고 회색 세로 띠 · 그래프 아래에 날짜마다 종목 · 사유(기준일 종가 없음은 한 줄)
끝 값  두 종목 공통 마지막 날(flow.last) — 표의 '이번 주 지금까지'와 같은 종가
안내   날짜마다 마우스를 올리면 날짜 · 두 값(브라우저 기본 표시 · SVG title)
```
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional

from app.weekly_decision import lines as L
from app.weekly_decision.page_base import deco, esc

# (CSS 이름, 그림 폭, 선 영역 높이) — page_base 의 화면 폭 구간과 짝(넓음 ≥ 900px · 중간 601~899px ·
# 좁음 ≤ 600px) · 미니 선이 아니라 흐름이 보이게 크게
VARIANTS = (("w", 820, 230), ("m", 530, 220), ("n", 340, 210))
TOP = 30  # 띠 이름 자리
LEFT = 46  # 세로 눈금 글자 자리
ROW = 32  # 아래 표식 한 줄(날짜 + 순위)
SERIES = (("etf", "이 ETF", "var(--s-etf)"), ("kodex", "KODEX 200", "var(--s-kdx)"))
# 하루 값이 빠진 사유(그래프 · 아래 목록) — history.close_at 의 사유 + no_base
DAY_WHY = {
    "no_price": "저장 가격 없음",
    "intraday_close": "장중 저장값(마감 전)",
    "unknown_close": "저장 시각 불명",
    "no_base": "기준일 종가 없음",
}
DRAWN_GAPS = (
    "no_base",
    "after_common",
    "pair_no_base",
)  # 날마다 회색 띠 · 날마다 목록에 적지 않는 사유(한 줄로 따로)


def day_why(code: Optional[str]) -> str:
    return DAY_WHY.get(code or "", L.why(code))


def text_width(s: str, size: float) -> float:
    """글 폭 어림(px) — 한글 1em · 공백 0.32em · 그 밖 0.62em(실제보다 넉넉하게)."""
    em = 0.0
    for ch in s:
        if ord(ch) >= 0x1100:
            em += 1.0
        elif ch == " ":
            em += 0.32
        else:
            em += 0.62
    return em * size


def ticks(vals: list[float]) -> tuple[float, float, float]:
    """세로 눈금 — 0 을 포함하고 칸이 5개 이하인 가장 촘촘한 간격."""
    lo0 = min([0.0, *vals])
    hi0 = max([0.0, *vals])
    lo = hi = step = 0.0
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000):
        lo = math.floor(lo0 / step) * step
        hi = math.ceil(hi0 / step) * step
        if hi == lo:
            hi = lo + step
        if (hi - lo) / step <= 5:
            break
    return lo, hi, step


def tick_label(v: float) -> str:
    if v == 0:
        return "0%"
    return ("+" if v > 0 else L.MINUS) + f"{abs(v):g}%"


def rank_text(seen: Mapping[str, Any]) -> str:
    """순위 글 — 장중 등 마감 뒤 저장이 아닌 가격 기준 순위는 '잠정'(판정 2026-11-26 §2-2)."""
    if seen["state"] == "ranked":
        tail = (
            "" if seen.get("price_state", "after_close") == "after_close" else "(잠정)"
        )
        return f"{seen['rank']}위{tail}"
    return "조건 제외" if seen.get("why") == "filter_excluded" else "확인 불가"


def _other(key: str) -> str:
    return next(label for k, label, _ in SERIES if k != key)


def _value(p: Mapping[str, Any], key: str, last: Optional[str]) -> str:
    """마우스 안내의 값 — 값이 있어도 그리지 않은 날은 '자료 없음'이 아니라 '그리지 않음'(반박 검토)."""
    v = p[key]
    if v is not None:
        return L.pct(v)
    why = p[key + "_why"]
    if why == "after_common":
        return (
            f"그리지 않음(두 종목 공통 마감일 {L.md(last)} 뒤)"
            if last
            else "그리지 않음(두 종목 공통 마감일 없음)"
        )
    if why == "pair_no_base":
        return f"그리지 않음(비교할 {_other(key)} 기준일 종가 없음)"
    return f"자료 없음({day_why(why)})"


def tip(
    p: Mapping[str, Any], mark: Optional[Mapping[str, Any]], last: Optional[str] = None
) -> str:
    rows = [L.mdw(p["date"])]
    rows += [f"{label} {_value(p, key, last)}" for key, label, _ in SERIES]
    if mark:
        r = rank_text(mark["seen"])
        rows.append(
            f"검토 기준일 순위 {r} · 주 진행 중"
            if mark["kind"] == "now"
            else f"그 마감 순위 {r}"
        )
    return "\n".join(rows)


def _n(v: float) -> str:
    return f"{v:.1f}"


def svg(f: Mapping[str, Any], cls: str, width: int, plot_h: int) -> str:
    """한 폭의 그림."""
    pts = f["points"]
    n = len(pts)
    at = {p["date"]: i for i, p in enumerate(pts)}

    def pos(d: str) -> int:
        """그 날짜 이하 마지막 거래일 칸(끝일이 일정 밖이면 앞 거래일)."""
        return max((i for i, p in enumerate(pts) if p["date"] <= d), default=0)

    vals = [p[k] for p in pts for k, _, _ in SERIES if p[k] is not None]
    lo, hi, step = ticks(vals)
    last = pts[at[f["last"]]] if f["last"] in at else None
    narrow = width < 400
    if last:
        ends = [(label, L.pct(last[k])) for k, label, _ in SERIES]
        if narrow:
            need = max(max(text_width(a, 12), text_width(b, 12)) for a, b in ends)
        else:
            need = max(text_width(f"{a} {b}", 12) for a, b in ends)
        right = math.ceil(need) + 14
    else:
        right = 16
    x0, x1 = LEFT, width - right
    dx = (x1 - x0) / max(n - 1, 1)

    def x(i: int) -> float:
        return (x0 + x1) / 2 if n == 1 else x0 + i * dx

    y_bottom = TOP + plot_h

    def y(v: float) -> float:
        return TOP + (hi - v) / (hi - lo) * plot_h

    # 아래 표식 — 겹치면 끝일(진행 주)은 띠 이름에 합치고, 완료 주는 한 줄 아래로
    labels = []
    for m in f["marks"]:
        i = pos(m["date"])
        dt_, rk = L.md(m["date"]), rank_text(m["seen"])
        w = max(text_width(dt_, 11), text_width(rk, 12))
        labels.append(
            {
                "m": m,
                "i": i,
                "cx": x(i),  # 점 · 세로 점선 위치
                "x": min(max(x(i), w / 2 + 2), width - w / 2 - 2),  # 글자는 그림 안으로
                "w": w,
                "date": dt_,
                "rank": rk,
                "row": 0,
            }
        )
    # 진행 주 순위(now)는 늘 띠 이름에 날짜와 함께 — 점 아래에는 완료 주 마감 순위만(판정 §3)
    merged = next((lb for lb in labels if lb["m"]["kind"] == "now"), None)
    shown = [lb for lb in labels if lb is not merged]
    last_in_row: dict[int, dict[str, Any]] = {}
    for lb in shown:  # 앞 표식과 겹치면 겹치지 않는 첫 줄로(여러 줄 엇갈림)
        r = 0
        while r in last_in_row and (
            lb["x"] - lb["w"] / 2 < last_in_row[r]["x"] + last_in_row[r]["w"] / 2 + 6
        ):
            r += 1
        lb["row"] = r
        last_in_row[r] = lb
    rows_used = 1 + max((lb["row"] for lb in shown), default=0)
    height = TOP + plot_h + 8 + ROW * rows_used

    out: list[str] = []
    add = out.append
    prog = f["progress"]
    if prog:
        bx0, bx1 = x(pos(prog["from"])), x(n - 1)
        add(
            f'<rect class="band" x="{_n(bx0)}" y="{TOP}" width="{_n(max(bx1 - bx0, 4))}" '
            f'height="{plot_h}"/>'
        )
        name = "이번 주 진행 중"
        if merged:
            name += f" · {merged['date']} {merged['rank']}"
        w = text_width(name, 12)
        cx = min(max((bx0 + bx1) / 2, x0 + w / 2), width - 2 - w / 2)
        add(
            f'<text class="bandname" x="{_n(cx)}" y="{TOP - 10}" text-anchor="middle">'
            f"{esc(name)}</text>"
        )
    for i, p in enumerate(pts):
        if any(p[k] is None and p[k + "_why"] not in DRAWN_GAPS for k, _, _ in SERIES):
            gw = max(4.0, dx * 0.6)
            add(
                f'<rect class="gapday" x="{_n(x(i) - gw / 2)}" y="{TOP}" width="{_n(gw)}" '
                f'height="{plot_h}"/>'
            )
    v = lo
    while v <= hi + 1e-9:
        yy = _n(y(v))
        add(
            f'<line class="{"zero" if v == 0 else "grid"}" x1="{x0}" x2="{_n(x1)}" '
            f'y1="{yy}" y2="{yy}"/>'
        )
        add(
            f'<text class="ax" x="{x0 - 6}" y="{_n(y(v) + 4)}" text-anchor="end">'
            f"{esc(tick_label(v))}</text>"
        )
        v += step
    for lb in labels:
        if lb["m"]["kind"] == "week":
            xx = _n(lb["cx"])
            add(
                f'<line class="wkline" x1="{xx}" x2="{xx}" y1="{TOP}" y2="{y_bottom}"/>'
            )
    for key, _, color in SERIES:
        run: list[str] = []
        for i, p in enumerate([*pts, None]):
            if p is not None and p[key] is not None:
                run.append(f"{_n(x(i))},{_n(y(p[key]))}")
                continue
            if len(run) > 1:
                add(
                    f'<polyline class="line" points="{" ".join(run)}" fill="none" '
                    f'stroke="{color}"/>'
                )
            elif len(run) == 1:
                cx_, cy_ = run[0].split(",")
                add(f'<circle cx="{cx_}" cy="{cy_}" r="2.5" fill="{color}"/>')
            run = []
        for lb in labels:
            pv = pts[lb["i"]][key]
            if pv is not None:
                add(
                    f'<circle class="dot" cx="{_n(lb["cx"])}" cy="{_n(y(pv))}" r="4" '
                    f'fill="{color}"/>'
                )
    for lb in shown:
        base = y_bottom + 8 + ROW * lb["row"]
        top = lb["m"]["seen"].get("state") == "ranked" and lb["m"]["seen"].get("top30")
        add(
            f'<text class="ax" x="{_n(lb["x"])}" y="{_n(base + 11)}" text-anchor="middle">'
            f'{esc(lb["date"])}</text>'
        )
        add(
            f'<text class="{"rk top" if top else "rk"}" x="{_n(lb["x"])}" y="{_n(base + 26)}" '
            f'text-anchor="middle">{esc(lb["rank"])}</text>'
        )
    if last:
        # 글자 자리 = 선 영역 안(위 = 띠 이름 아래 · 아래 = 점 아래 날짜 위) — 각자 맞춘 뒤, 가까우면 함께 벌림
        top_y = TOP + 12.0
        bot_y = y_bottom - (14.0 if narrow else 6.0)
        gap = 30.0 if narrow else 16.0
        ys = {k: min(max(y(last[k]), top_y), bot_y) for k, _, _ in SERIES}
        if abs(ys["etf"] - ys["kodex"]) < gap:
            mid = (ys["etf"] + ys["kodex"]) / 2
            up = min(max(mid - gap / 2, top_y), bot_y - gap)
            ys = (
                {"etf": up, "kodex": up + gap}
                if y(last["etf"]) <= y(last["kodex"])
                else {"etf": up + gap, "kodex": up}
            )
        lx = _n(x1 + 8)
        for key, label, _ in SERIES:
            yy = ys[key]
            val = L.pct(last[key])
            if narrow:
                add(f'<text class="lab" x="{lx}" y="{_n(yy - 4)}">{esc(label)}</text>')
                add(f'<text class="lab" x="{lx}" y="{_n(yy + 12)}">{esc(val)}</text>')
            else:
                add(
                    f'<text class="lab" x="{lx}" y="{_n(yy + 4)}">{esc(label)} {esc(val)}</text>'
                )
    by_date = {lb["m"]["date"]: lb["m"] for lb in labels}
    by_i = {lb["i"]: lb["m"] for lb in labels}
    for i, p in enumerate(pts):
        hw = (x1 - x0) if n == 1 else dx
        mark = by_date.get(p["date"]) or by_i.get(i)
        add(
            f'<rect class="hit" x="{_n(x(i) - hw / 2)}" y="{TOP}" width="{_n(hw)}" '
            f'height="{plot_h}"><title>{esc(tip(p, mark, f["last"]))}</title></rect>'
        )
    aria = f"{L.md(f['base'])} 마감 기준 이 ETF 와 KODEX 200 누적 변화"
    return (
        f'<svg class="fsvg {cls}" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="{esc(aria)}">{"".join(out)}</svg>'
    )


def missing_lines(f: Mapping[str, Any]) -> list[str]:
    """값이 빠진 날 — 날짜마다 한 줄(기준일 종가가 없어 선을 못 그린 종목은 한 줄로)."""
    out = []
    no_base = [
        label
        for key, label, _ in SERIES
        if f["points"] and all(p[key + "_why"] == "no_base" for p in f["points"])
    ]
    for label in no_base:
        out.append(f"{label} — 기준일({L.md(f['base'])}) 종가가 없어 선을 그리지 못함")
    weeks = set(f.get("week_closes") or ())
    for p in f["points"]:
        parts = [
            f"{label} {day_why(p[key + '_why'])}"
            for key, label, _ in SERIES
            if p[key] is None
            and label not in no_base
            and p[key + "_why"] not in ("after_common", "pair_no_base")
        ]
        # 이미 끝난 주 마감일의 결측은 '완료 주 마감 종가 없음'(판정 2026-11-26 §2-1)
        if parts:
            head = " 완료 주 마감 종가 없음" if p["date"] in weeks else ""
            out.append(f"{L.mdw(p['date'])}{head} — " + " · ".join(parts))
    # 공통 마감일 뒤를 그리지 않은 것은 날마다가 아니라 끝에 한 줄로(검증 F15)
    cut = [
        p["date"]
        for p in f["points"]
        if "after_common" in (p["etf_why"], p["kodex_why"])
    ]
    if cut and f["last"]:
        out.append(
            f"{L.mdw(cut[0])}부터 — 두 종목 공통 마감 종가가 없어 그리지 않음"
            f"(끝 값 = {L.mdw(f['last'])})"
        )
    elif cut:
        out.append("두 종목 공통 마감 종가가 있는 날이 없어 선을 그리지 않음")
    for key, label, _ in SERIES:
        if any(p[key + "_why"] == "pair_no_base" for p in f["points"]):
            out.append(
                f"{label} — 비교할 {_other(key)} 기준일 종가가 없어 선을 그리지 않음"
            )
    return out


def chart_html(rv: Mapping[str, Any], name: str) -> str:
    """지난 네 주 카드 맨 위 그래프(표보다 먼저) · 자료 없으면 빈 글."""
    f = rv.get("flow") or {}
    if f.get("state") != "ok" or not f["points"]:
        return ""
    last = f["last"]
    no_base = [
        label
        for key, label, _ in SERIES
        if all(p[key + "_why"] == "no_base" for p in f["points"])
    ]
    if last:
        end_line = f"끝 값 = {L.mdw(last)} 종가 기준"
    elif no_base:
        who = " · ".join(no_base)
        end_line = f"{who} 기준일({L.md(f['base'])}) 종가가 없어 끝 값을 적지 않음"
    else:
        end_line = "두 종목 모두 마감 종가가 있는 날이 없어 끝 값을 적지 않음"
    legend = "".join(
        f'<span><i style="background:{color}"></i>'
        f'{esc(f"{label}({name})" if key == "etf" else label)}</span>'
        for key, label, color in SERIES
    )
    # 그래프 마지막 반영일 ≠ 검토 기준일(장중 · 주말 끝일 등)이면 두 날짜를 각각(판정 2026-11-26 §2-2 · §2-4)
    review_day = "검토 기준일 = " + L.mdw(f["end"])
    base_day = f'<div class="sub">{deco(review_day)}</div>' if last != f["end"] else ""
    miss = missing_lines(f)
    foot = (
        '<div class="sub">값이 빠진 날(회색 띠)</div>'
        f'<ul class="lines">{"".join(f"<li>{deco(m)}</li>" for m in miss)}</ul>'
        if miss
        else ""
    )
    svgs = "".join(svg(f, cls, w, h) for cls, w, h in VARIANTS)
    return (
        '<div class="flow">'
        f"<div><b>흐름</b> — {deco(L.md(f['base']))} 마감 = 0% 기준 누적 변화</div>"
        f'<div class="sub">{deco(end_line)}</div>{base_day}'
        '<div class="sub">점 아래 순위 = 그 마감일 기준으로 다시 계산한 순위</div>'
        f'<div class="legend">{legend}</div>'
        f'<div class="plot">{svgs}</div>{foot}</div>'
    )
