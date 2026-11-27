"""POC7-04 PLAN V2(설계자 RESULT 판정 2026-11-25) — 이번 주 지금까지 · 흐름 그래프 · AI 질문 형식(tmp DB 만)."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.weekly_decision import evidence as E
from app.weekly_decision import flow as FL
from app.weekly_decision import history as H
from app.weekly_decision import observe as OB
from app.weekly_decision import lines as L
from app.weekly_decision import page as PG
from app.weekly_decision import page_chart as PC
from app.weekly_decision import page_live as PL
from app.weekly_decision import page_saved as PS
from app.weekly_decision import server as SV
from app.weekly_decision import store as ST
from tests._poc7_04_support import (
    REPO,
    _sessions,
    _true_item,
    _cite_line,
    FILTERS,
    OFFICIAL,
    END,
    ROWS,
    NONE_SESSIONS,
    FakeReader,
    _app,
    _bid,
    _bump,
    _ctx,
    _put,
    _rv,
    make_market,
    trading,
)

W0 = ROWS[-1]  # 11/20 — 마지막 완료 주 마감


@pytest.fixture
def market(tmp_path: Path) -> Path:
    return make_market(tmp_path)


def _closes(ctx: H.Context, ticker: str) -> tuple[dict[str, float], dict[str, float]]:
    e = {r.date: r.close for r in ctx.market["raw"][ticker]}
    k = {r.date: r.close for r in ctx.market["kodex_full"]}
    return e, k


def _set_intraday(db: Path, ticker: str, d: str) -> None:
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE etf_daily_price SET fetched_at=? WHERE ticker=? AND date=?",
            (f"{d}T02:00:00+00:00", ticker, d),  # 11:00 KST — 장중 저장
        )


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


# --- 이번 주 지금까지(판정 Q6 · §3) ---


def test_week_so_far_runs_to_last_common_close(market: Path) -> None:
    ctx = _ctx(market)
    e, k = _closes(ctx, "AAA001")
    so = OB.week_so_far(ctx, "AAA001", W0)
    assert so == {
        "end": END,
        "etf": {"value": pytest.approx((e[END] / e[W0] - 1) * 100), "why": None},
        "kodex": {"value": pytest.approx((k[END] / k[W0] - 1) * 100), "why": None},
        "why": None,
    }
    # 그 마감 뒤 저장한 날이 없으면 자료 없음(no_new_day)
    assert OB.week_so_far(ctx, "AAA001", END) == {"end": None, "why": "no_new_day"}


def test_week_so_far_takes_the_last_of_several_common_days(market: Path) -> None:
    _put(market, "AAA001", [131.0, 133.0], ["2026-11-24", "2026-11-25"])
    _put(market, "069500", [94.0, 93.0], ["2026-11-24", "2026-11-25"])
    ctx = _ctx(market)
    so = OB.week_so_far(ctx, "AAA001", W0)
    e, k = _closes(ctx, "AAA001")
    assert so["end"] == "2026-11-25"
    assert so["etf"]["value"] == pytest.approx((133.0 / e[W0] - 1) * 100)
    assert so["kodex"]["value"] == pytest.approx((93.0 / k[W0] - 1) * 100)


def test_week_so_far_skips_day_with_only_one_close(market: Path) -> None:
    """끝일에 이 ETF 만 마감 종가 · KODEX 200 은 장중 저장 → 공통 마지막 날은 그 전날."""
    _put(market, "AAA001", [131.0], ["2026-11-24"])
    _put(market, "069500", [94.0], ["2026-11-24"])
    _set_intraday(market, "069500", "2026-11-24")
    ctx = _ctx(market)
    assert ctx.end == "2026-11-24"
    e, k = _closes(ctx, "AAA001")
    so = OB.week_so_far(ctx, "AAA001", W0)
    assert so["end"] == END  # 11/23
    assert so["etf"]["value"] == pytest.approx((e[END] / e[W0] - 1) * 100)
    assert so["kodex"]["value"] == pytest.approx((k[END] / k[W0] - 1) * 100)
    a = ctx.restore  # 복원은 끝일 뒤를 받지 않음(그래프 · 표가 끝일 뒤 값을 쓰지 않음)
    with pytest.raises(ValueError):
        a("2026-11-25")


def test_week_so_far_no_common_close_and_off_schedule_rows(market: Path) -> None:
    """끝일 이 ETF 장중 저장뿐 · 일정 밖(일요일) 행은 마감 뒤 저장이어도 쓰지 않음 → 자료 없음."""
    _put(market, "AAA001", [129.0], ["2026-11-22"])  # 일요일 — 일정 밖
    _put(market, "069500", [95.5], ["2026-11-22"])
    _set_intraday(market, "AAA001", END)
    ctx = _ctx(market)
    so = OB.week_so_far(ctx, "AAA001", W0)
    assert so == {"end": None, "why": "no_common_close"}
    a = OB.after_move(ctx, "AAA001", W0)
    assert a["state"] == "not_yet" and a["sofar"] == so
    plain = L.after_plain({"after": a})
    assert plain == (
        "이번 주 지금까지 11/20 이후 자료 없음(두 종목 모두 마감 뒤 저장한 종가가 있는 날이 아직 없음 · "
        "주 진행 중 · 11/27 마감 예정)"
    )
    html = _text(PG._after_html(a))
    assert (
        "이번 주 지금까지자료 없음" in html and "주 진행 중 11/27(금) 마감 예정" in html
    )
    assert PG._observed(a) is False
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    assert (
        rv["flow"]["last"] == W0
    )  # 그래프 끝 값은 11/20 · 표는 자료 없음 → '같은 날 종가' 안내 없음
    weeks = _text(PG.weeks_html(rv))
    assert "그래프 끝 값과 표의" not in weeks and "'이번 주 지금까지' =" in weeks


def test_finished_week_keeps_v1_after_and_no_progress(market: Path) -> None:
    """검토가 속한 주가 끝났으면 마지막 행은 완료 주 → 다음 주 마감(이번 주 지금까지 없음)."""
    ctx = _ctx(market, "2026-11-20")
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    last = rv["weeks"]["rows"][-1]
    assert last["date"] == "2026-11-13" and last["after"]["state"] == "ok"
    assert rv["flow"]["progress"] is None
    assert [(m["date"], m["kind"]) for m in rv["flow"]["marks"]] == [
        ("2026-10-23", "week"),
        ("2026-10-30", "week"),
        ("2026-11-06", "week"),
        ("2026-11-13", "week"),
        ("2026-11-20", "week"),
    ]
    assert rv["flow"]["marks"][-1]["seen"]["rank"] == rv["rank"]
    assert "이번 주 지금까지" not in rv["copy"]
    weeks = PG.weeks_html(rv)
    assert "(이번 주는 지금까지)" not in weeks and 'class="band"' not in weeks
    assert "'이번 주 지금까지' =" not in weeks and "그래프 끝 값과 표의" not in weeks


# --- 흐름 그래프 자료 ---


def test_flow_points_marks_and_same_close_as_table(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    e, k = _closes(ctx, "AAA001")
    days = [d for d in sorted(k) if ROWS[0] <= d <= END]
    assert [p["date"] for p in f["points"]] == days and f["base"] == ROWS[0]
    for p in f["points"]:
        assert p["etf"] == pytest.approx((e[p["date"]] / e[ROWS[0]] - 1) * 100)
        assert p["kodex"] == pytest.approx((k[p["date"]] / k[ROWS[0]] - 1) * 100)
    assert f["last"] == END and f["end"] == END
    assert f["progress"] == {
        "from": W0,
        "to": "2026-11-27",
        "intraday": False,
        "sofar_end": END,
    }
    assert [(m["date"], m["kind"]) for m in f["marks"]] == [
        *((d, "week") for d in ROWS),
        (END, "now"),
    ]
    assert [m["seen"] for m in f["marks"][:4]] == [
        r["seen"] for r in rv["weeks"]["rows"]
    ]
    assert f["marks"][-1]["seen"]["rank"] == rv["rank"]
    # 그래프 끝 값과 표의 '이번 주 지금까지'는 같은 종가(완료 주 마감 → 공통 마지막 날)
    so = rv["weeks"]["rows"][-1]["after"]["sofar"]
    at = {p["date"]: p for p in f["points"]}
    for key in ("etf", "kodex"):
        week = (1 + at[END][key] / 100) / (1 + at[W0][key] / 100) - 1
        assert week * 100 == pytest.approx(so[key]["value"])


def test_flow_now_mark_uses_current_rank_not_last_week(market: Path) -> None:
    """끝일 순위 = 검토 기준일 순위(마지막 완료 주 복원 순위와 다를 때도)."""
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET close = 145 WHERE ticker='AAA001' AND date=?",
            (END,),
        )
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    last_week = rv["weeks"]["rows"][-1]["seen"]["rank"]
    assert rv["rank"] != last_week
    assert rv["flow"]["marks"][-1]["seen"]["rank"] == rv["rank"]
    assert rv["flow"]["marks"][-2]["seen"]["rank"] == last_week


def test_flow_progress_only_for_unfinished_week(market: Path) -> None:
    """마지막 행이 '다음 주 거래일 없음'(no_schedule)이면 진행 띠를 그리지 않음."""
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    rows = [dict(r) for r in rv["weeks"]["rows"]]
    rows[-1]["after"] = {"state": "no_schedule", "from": W0, "to": None}
    f = FL.flow(ctx, "AAA001", rows, ctx.item("AAA001"))
    assert f["progress"] is None and f["marks"][-1]["kind"] == "week"
    assert [
        m["date"] for m in f["marks"]
    ] == ROWS  # 마지막 행이 그 주 마감이면 표식을 다시 넣지 않음


def test_skipped_week_close_still_shows_this_week(market: Path) -> None:
    """금요일 KODEX 200 이 장중 저장뿐 → 주 마감 규칙이 그 주를 건너뜀 · 끝일은 다음 주 월요일.

    표 마지막 행(11/13 → 11/20) = 완료 주 마감 종가 없음 · 그 아래 '이번 주 지금까지' = 시작(거래 일정상 직전 완료
    주 마감 11/20)에 두 종목 마감 종가가 다 있지 않아 비교 불가(판정 2026-11-26 §2-3) · 그래프는 진행 주."""
    _set_intraday(market, "069500", W0)
    ctx = _ctx(market)
    assert ctx.rows[-1] == "2026-11-13" and not ctx.build["weekly"]["finished"]
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    a = rv["weeks"]["rows"][-1]["after"]
    assert (
        a["state"] == "ok" and a["to"] == W0 and a["kodex"]["why"] == "intraday_close"
    )
    t = a["then"]
    assert t["state"] == "not_yet" and t["from"] == W0 and t["to"] == "2026-11-27"
    assert t["sofar"] == {"end": None, "why": "no_prev_close"}
    f = rv["flow"]
    assert f["progress"]["from"] == W0 and f["marks"][-1]["kind"] == "now"
    assert f["last"] == END
    c = rv["copy"]
    assert (
        "11/13 → 11/20 ETF " in c
        and "KODEX 200 완료 주 마감 종가 없음(장중 저장값)" in c
    )
    assert (
        " / 이번 주 지금까지 비교 불가(11/20 직전 주 마감 종가 없음 · 주 진행 중 · 11/27 마감 예정)"
        in c
    )
    weeks = _text(PG.weeks_html(rv))
    assert (
        "(이번 주는 지금까지)" in PG.weeks_html(rv)
        and "비교 불가직전 주(11/20(금)) 마감 종가 없음" in weeks
    )
    assert (
        "그래프 끝 값과 표의" not in weeks
    )  # 표에 이번 주 값이 없으니 '같은 날 종가' 안내 없음
    assert (
        "11/20(금) 완료 주 마감 종가 없음 — KODEX 200 장중 저장값(마감 전)"
        in PC.missing_lines(f)
    )


def test_this_week_start_close_missing_is_not_compared(market: Path) -> None:
    """정상 진행 주에서도 직전 주 마감(11/20)에 이 ETF 종가가 없으면 한 종목 값만 보이지 않고 비교 불가."""
    with sqlite3.connect(market) as con:
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker='AAA001' AND date=?", (W0,)
        )
    ctx = _ctx(market)
    so = OB.week_so_far(ctx, "AAA001", W0)
    assert so == {"end": None, "why": "no_prev_close"}
    a = OB.after_move(ctx, "AAA001", W0)
    assert a["state"] == "not_yet" and a["sofar"] == so
    assert L.after_plain({"after": a}) == (
        "이번 주 지금까지 비교 불가(11/20 직전 주 마감 종가 없음 · 주 진행 중 · 11/27 마감 예정)"
    )
    assert (
        OB.this_week(ctx, "AAA001")["sofar"] == so
    )  # 표 행과 진행 주 계산이 같은 상태


def test_this_week_progress_rules() -> None:
    """진행 중 판정 = 그 주 일정상 마감 > 끝일 · 또는 = 끝일인데 장중 · 시작 = 거래 일정상 직전 주 마감."""
    assert OB.prev_week_close("2026-11-23", trading) == "2026-11-20"
    assert OB.prev_week_close("2026-11-27", trading) == "2026-11-20"
    holiday = {"2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"}
    assert (
        OB.prev_week_close("2026-11-23", lambda d: trading(d) and d not in holiday)
        == "2026-11-13"
    )
    assert OB.prev_week_close("2026-11-23", lambda d: False) is None


def test_off_schedule_end_puts_last_mark_on_week_close(market: Path) -> None:
    """일요일 행 때문에 끝일이 일정 밖(11/22) — 주는 끝남 · 마지막 표식은 그 주 마감(11/20) 복원."""
    _put(market, "AAA001", [130.5], ["2026-11-22"])
    _put(market, "069500", [95.2], ["2026-11-22"])
    ctx = _ctx(market, "2026-11-22")
    assert ctx.end == "2026-11-22" and ctx.build["weekly"]["finished"]
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    assert f["progress"] is None and f["points"][-1]["date"] == W0
    assert f["marks"][-1] == {
        "date": W0,
        "kind": "week",
        "seen": H.seen_at(ctx.restore(W0), "AAA001"),
    }
    assert "then" not in rv["weeks"]["rows"][-1]["after"]
    assert "이번 주 지금까지" not in rv["copy"]
    html = _text(PC.chart_html(rv, rv["name"]))
    assert "끝 값 = 11/20(금) 종가 기준" in html and "검토 기준일 = 11/22(일)" in html


def test_intraday_rank_is_provisional_and_dates_are_separate(market: Path) -> None:
    """끝일 이 ETF 가 장중 저장 — 띠 순위 '(잠정)' · 그래프 끝 값(11/20)과 검토 기준일(11/23)을 각각 적음."""
    _set_intraday(market, "AAA001", END)
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    assert rv["price_state"] == "intraday" and f["last"] == W0
    assert rv["weeks"]["rows"][-1]["after"]["sofar"] == {
        "end": None,
        "why": "no_common_close",
    }
    for cls, w, h in PC.VARIANTS:
        s = PC.svg(f, cls, w, h)
        band = re.search(r'<text class="bandname"[^>]*>([^<]*)</text>', s).group(1)
        assert band == f"이번 주 진행 중 · 11/23 {rv['rank']}위(잠정)"
        _no_overlap(s)
    html = _text(PC.chart_html(rv, rv["name"]))
    assert "끝 값 = 11/20(금) 종가 기준" in html and "검토 기준일 = 11/23(월)" in html
    assert "11/23(월) — 이 ETF 장중 저장값(마감 전)" in PC.missing_lines(
        f
    )  # 진행 주는 '완료 주' 아님
    weeks = _text(PG.weeks_html(rv))
    assert "그래프 끝 값과 표의" not in weeks


def test_same_review_day_and_last_close_shows_one_date(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    html = _text(PC.chart_html(rv, rv["name"]))
    assert "끝 값 = 11/23(월) 종가 기준" in html and "검토 기준일 =" not in html
    assert rv["flow"]["week_closes"] == ["2026-10-30", "2026-11-06", "2026-11-13", W0]


def test_flow_gap_day_breaks_line_and_is_listed(market: Path) -> None:
    with sqlite3.connect(market) as con:
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker='069500' AND date='2026-11-11'"
        )
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    gap = next(p for p in f["points"] if p["date"] == "2026-11-11")
    assert (
        gap["kodex"] is None
        and gap["kodex_why"] == "no_price"
        and gap["etf"] is not None
    )
    assert PC.missing_lines(f) == ["11/11(수) — KODEX 200 저장 가격 없음"]
    for cls, w, h in PC.VARIANTS:
        s = PC.svg(f, cls, w, h)
        assert s.count('stroke="var(--s-kdx)"') == 2  # 선이 끊김(두 조각)
        assert s.count('stroke="var(--s-etf)"') == 1
        assert s.count('class="gapday"') == 1
    html = PC.chart_html(rv, rv["name"])
    assert "값이 빠진 날(회색 띠)" in html and "KODEX 200 저장 가격 없음" in html


def test_flow_without_base_close_draws_no_line(market: Path) -> None:
    with sqlite3.connect(market) as con:
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker='AAA001' AND date=?", (ROWS[0],)
        )
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    assert all(p["etf"] is None and p["etf_why"] == "no_base" for p in f["points"])
    assert f["last"] is None
    # 비교할 이 ETF 기준일 종가가 없으니 KODEX 200 선도 그리지 않음 — 사유는 그대로(검증 F15 · 반박 검토)
    assert all(
        p["kodex"] is None and p["kodex_why"] == "pair_no_base" for p in f["points"]
    )
    assert PC.missing_lines(f) == [
        "이 ETF — 기준일(10/30) 종가가 없어 선을 그리지 못함",
        "KODEX 200 — 비교할 이 ETF 기준일 종가가 없어 선을 그리지 않음",
    ]
    tips = re.findall(r"<title>([^<]*)</title>", PC.svg(f, "w", 820, 230))
    assert "KODEX 200 그리지 않음(비교할 이 ETF 기준일 종가 없음)" in tips[0]
    assert "공통 마감 종가가 있는 날이 없어" not in " ".join(PC.missing_lines(f))
    s = PC.svg(f, "w", 820, 230)
    assert 'stroke="var(--s-etf)"' not in s and 'class="lab"' not in s
    assert 'stroke="var(--s-kdx)"' not in s
    assert (
        'class="gapday"' not in s
    )  # 기준일 종가 없음은 날마다 띠를 칠하지 않고 한 줄로
    for cls, w, h in PC.VARIANTS:  # 끝 글자가 없어 오른쪽이 좁아도 띠 이름은 그림 안
        _no_overlap(PC.svg(f, cls, w, h))
    html = _text(PC.chart_html(rv, rv["name"]))
    assert "이 ETF 기준일(10/30) 종가가 없어 끝 값을 적지 않음" in html
    assert "두 종목 모두 마감 종가가 있는 날이 없어" not in html
    weeks = _text(PG.weeks_html(rv))
    assert "그래프 끝 값과 표의" not in weeks and "'이번 주 지금까지' =" in weeks


def test_flow_intraday_end_day(market: Path) -> None:
    """끝일이 그 주 마감일인데 이 ETF 가 장중 저장 — 띠 '이번 주 진행 중' · 끝 값은 전날 · 검토 기준일 따로."""
    _set_intraday(market, "AAA001", "2026-11-20")
    ctx = _ctx(market, "2026-11-20")
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    assert f["progress"]["intraday"] is True and f["last"] == "2026-11-19"
    assert "11/20(금) — 이 ETF 장중 저장값(마감 전)" in PC.missing_lines(f)
    assert all(
        "이번 주 진행 중 · 11/20 " in PC.svg(f, c, w, h) for c, w, h in PC.VARIANTS
    )


# --- 그림(세 폭) — 글자가 서로 겹치지 않고 그림 안에 ---

SIZE = {"ax": 11, "rk": 12, "rk top": 12, "lab": 12, "bandname": 12}


def _boxes(svg: str) -> tuple[list[tuple[float, float, float, float, str]], int, int]:
    w, h = (int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
    out = []
    for m in re.finditer(
        r'<text class="([^"]+)" x="([\d.]+)" y="([\d.]+)"(?: text-anchor="(\w+)")?>([^<]*)</text>',
        svg,
    ):
        cls, x, y, anchor, txt = m.groups()
        size = SIZE[cls]
        tw = PC.text_width(txt, size)
        x, y = float(x), float(y)
        x0 = x - tw / 2 if anchor == "middle" else x - tw if anchor == "end" else x
        out.append((x0, x0 + tw, y - size * 0.85, y + size * 0.25, txt))
    return out, w, h


def _no_overlap(svg: str) -> None:
    boxes, w, h = _boxes(svg)
    assert boxes
    for a in boxes:
        assert a[0] >= 0 and a[1] <= w and a[2] >= 0 and a[3] <= h, a
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:  # noqa: E203
            apart = a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2]
            assert apart, (a, b)


def _flow_variants(rv: dict[str, Any]) -> list[dict[str, Any]]:
    """실제 계산한 흐름 + 긴 순위 글('조건 제외')로 바꾼 것."""
    f = rv["flow"]
    long = dict(f)
    long["marks"] = [
        (
            {**m, "seen": {"state": "out", "why": "filter_excluded"}}
            if m["kind"] == "week"
            else m
        )
        for m in f["marks"]
    ]
    return [f, long]


@pytest.mark.parametrize("end", [None, "2026-11-19", "2026-11-20"])
def test_svg_labels_do_not_overlap_in_three_widths(market: Path, end) -> None:
    ctx = _ctx(market, end)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    for f in _flow_variants(rv):
        for cls, w, h in PC.VARIANTS:
            s = PC.svg(f, cls, w, h)
            assert f'class="fsvg {cls}"' in s and f'viewBox="0 0 {w} ' in s
            _no_overlap(s)


def _synthetic(
    n: int, marks: list[int], etf: list[float], kodex: list[float], long: bool = True
) -> dict[str, Any]:
    days = [(date(2026, 11, 2) + timedelta(days=i)).isoformat() for i in range(n)]
    seen = (
        {"state": "out", "why": "filter_excluded"}
        if long
        else {"state": "ranked", "rank": 7, "top30": True}
    )
    return {
        "state": "ok",
        "base": days[0],
        "end": days[-1],
        "points": [
            {
                "date": d,
                "etf": etf[i],
                "etf_why": None,
                "kodex": kodex[i],
                "kodex_why": None,
            }
            for i, d in enumerate(days)
        ],
        "marks": [{"date": days[i], "kind": "week", "seen": seen} for i in marks],
        "progress": None,
        "last": days[-1],
    }


def test_crowded_week_labels_move_to_a_second_row() -> None:
    """주 표식이 붙어 있으면(긴 순위 글) 한 줄 아래로 — 겹치지 않고 그림 높이가 늘어남."""
    f = _synthetic(6, [0, 1, 2, 3], [0, 1, 2, 3, 4, 5], [0, -1, -2, -3, -4, -5])
    for cls, w, h in PC.VARIANTS:
        s = PC.svg(f, cls, w, h)
        _no_overlap(s)
        if cls == "n":
            height = int(re.search(r'viewBox="0 0 \d+ (\d+)"', s).group(1))
            assert height == PC.TOP + h + 8 + PC.ROW * 2


def test_end_labels_at_both_edges_stay_inside_plot() -> None:
    """두 끝 값이 눈금 맨 위 · 맨 아래 가까이 — 글자가 선 영역 안 · 점 아래 날짜와 겹치지 않음."""
    e = [19.6 * i / 9 for i in range(10)]
    k = [-19.8 * i / 9 for i in range(10)]
    f = _synthetic(10, [0, 5, 9], e, k, False)
    for cls, w, h in PC.VARIANTS:
        _no_overlap(PC.svg(f, cls, w, h))


def test_many_crowded_marks_use_more_rows() -> None:
    """연휴 등으로 표식 네 개가 붙어 있어도 겹치지 않음(줄을 더 씀)."""
    f = _synthetic(
        40, [0, 1, 2, 3], [0.1 * i for i in range(40)], [-0.1 * i for i in range(40)]
    )
    for cls, w, h in PC.VARIANTS:
        s = PC.svg(f, cls, w, h)
        _no_overlap(s)
    height = int(re.search(r'viewBox="0 0 \d+ (\d+)"', s).group(1))
    assert height == PC.TOP + h + 8 + PC.ROW * 4


def test_close_end_values_are_spread_apart() -> None:
    """두 끝 값이 거의 같아도 끝 글자가 겹치지 않음 — 그래프 맨 위 · 맨 아래 가장자리에서도."""
    up = [
        i / 9 for i in range(10)
    ]  # 끝 값 = 눈금 맨 위(1%) — 위 가장자리에서 벌린 간격 유지
    for sign in (1, -1):
        e = [sign * v for v in up]
        k = [sign * v - 0.01 for v in up]
        f = _synthetic(10, [0, 5], e, k, False)
        for cls, w, h in PC.VARIANTS:
            _no_overlap(PC.svg(f, cls, w, h))


def test_end_labels_at_top_stay_below_progress_band_name() -> None:
    """끝 값이 눈금 맨 위 · 진행 주 띠가 오른쪽 끝 — 띠 이름과 끝 값 글자가 겹치지 않음."""
    up = [i / 9 for i in range(10)]
    f = _synthetic(10, [0, 5, 7], up, [v - 0.01 for v in up], False)
    f["marks"].append(
        {"date": f["points"][-1]["date"], "kind": "now", "seen": f["marks"][0]["seen"]}
    )
    f["progress"] = {
        "from": f["points"][7]["date"],
        "to": "2026-11-13",
        "intraday": False,
    }
    for cls, w, h in PC.VARIANTS:
        _no_overlap(PC.svg(f, cls, w, h))


def test_progress_rank_shows_date_and_progress(market: Path) -> None:
    """진행 주 순위 = 늘 띠 이름에 검토 기준일 날짜와 함께 · 점 아래(완료 주 마감 자리)에는 없음."""
    for end, now in ((None, END), ("2026-11-19", "2026-11-19")):
        ctx = _ctx(market, end)
        rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
        rank = f"{rv['rank']}위"
        for cls, w, h in PC.VARIANTS:
            s = PC.svg(rv["flow"], cls, w, h)
            band = re.search(r'<text class="bandname"[^>]*>([^<]*)</text>', s).group(1)
            assert band == f"이번 주 진행 중 · {L.md(now)} {rank}"
            bottom = re.findall(
                r'<text class="(?:ax|rk|rk top)"[^>]*>([^<]*)</text>', s
            )
            assert L.md(now) not in bottom
            tip = re.findall(r"<title>([^<]*)</title>", s)[-1]
            assert (
                tip.startswith(L.mdw(now))
                and f"검토 기준일 순위 {rank} · 주 진행 중" in tip
            )


def test_hover_titles_have_date_and_both_values(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    s = PC.svg(f, "w", 820, 230)
    tips = re.findall(r"<title>([^<]*)</title>", s)
    assert len(tips) == len(f["points"])
    marked = {m["date"] for m in f["marks"]}
    j = next(i for i, q in enumerate(f["points"]) if q["date"] not in marked)
    p = f["points"][j]
    assert (
        tips[j]
        == f"{L.mdw(p['date'])}\n이 ETF {L.pct(p['etf'])}\nKODEX 200 {L.pct(p['kodex'])}"
    )
    i = [q["date"] for q in f["points"]].index(ROWS[1])
    assert tips[i].endswith(f"그 마감 순위 {f['marks'][1]['seen']['rank']}위")


def test_ticks_include_zero_and_cover_values() -> None:
    assert PC.ticks([16.56, -19.45]) == (-20, 20, 10)
    assert PC.ticks([0.3, -0.2]) == (-1, 1, 1)
    assert PC.ticks([]) == (0, 1, 1)
    lo, hi, step = PC.ticks([123.0, -4.0])
    assert lo <= -4 and hi >= 123 and (hi - lo) / step <= 5 and lo <= 0 <= hi
    assert PC.tick_label(-20) == "−20%" and PC.tick_label(10) == "+10%"


# --- 화면: 그래프가 표보다 먼저 · 표 머리 · 안내 ---


def test_weeks_card_puts_chart_before_table(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(
        ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[], reader=FakeReader()
    )
    weeks = PG.weeks_html(rv)
    assert weeks.index('class="flow"') < weeks.index('class="weeks"')
    assert weeks.count('class="fsvg ') == 3
    assert "그 뒤 다음 주 마감까지<br>(이번 주는 지금까지)" in weeks
    assert "'이번 주 지금까지' = 거래 일정상 직전 완료 주 마감" in _text(weeks)
    last = _text(PG._row_html(rv["weeks"]["rows"][-1], []))
    so = rv["weeks"]["rows"][-1]["after"]["sofar"]
    assert "그 뒤 관측이번 주 지금까지" in last
    assert f"11/20 → 11/23(월)ETF {L.pct(so['etf']['value'])}" in last
    assert "주 진행 중 11/27(금) 마감 예정" in last


def test_my_judgment_hint_says_ai_line_is_opinion(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(
        ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[], reader=FakeReader()
    )
    for live in (True, False):
        form = PL._form(rv, live=live)
        assert "AI 답의 첫 줄('검토 계속' · '보류')은 AI 의견입니다." in form
        assert "판단은 직접 고르세요 — 처음은 '미기록'입니다." in form
        assert "위 '지난 네 주' 아래 '구성 · 겹침'에서 보세요" in form
    assert "<summary>구성 · 겹침" in PG.weeks_html(rv)


# --- AI 질문(판정 Q1 ~ Q5) ---


def test_missing_values_and_guides_by_path() -> None:
    over = _rv()
    assert E.missing_values(over) == [
        "같은 기간(10/26~11/23) Nifty 50의 현지 통화 기준 수익률",
        "같은 기간 환율(ETF 원화 가격과 같은 시각 기준)",
    ]
    g = E._ask(over)["guide"]
    assert g == [
        "먼저 같은 기간 Nifty 50의 현지 통화 기준 수익률을 확인해 주세요.",
        E.GUIDE_GAP_OVERSEAS,
    ]
    dom = _rv(overseas=False)
    dom["peer"]["label"] = "코스피 200"
    assert E.missing_values(dom) == [
        "같은 기간(10/26~11/23) 기초지수 코스피 200의 수익률"
    ]
    g = E._ask(dom)["guide"]
    assert g == [
        "먼저 같은 기간 기초지수 코스피 200의 수익률을 확인해 주세요.",
        E.GUIDE_GAP_DOMESTIC,
    ]
    assert not any("환율" in x for x in g)  # 국내는 환율을 묻지 않음
    none = _rv(official=False)
    assert E.missing_values(none) == [
        "이 ETF 의 기초지수 이름과 상품 구조(배수 · 복제 방법 · 환헤지)",
        "같은 기간(10/26~11/23) 그 기초지수의 수익률",
    ]
    g = E._ask(none)["guide"]
    assert g[0].startswith(
        "먼저 공식 공개 자료에서 이 ETF 의 기초지수와 상품 구조를 확인하고"
    )
    assert g[1] == E.GUIDE_GAP_UNKNOWN
    gap_over = E._ask(_rv(opposite=True))["guide"]
    assert gap_over[0] == (
        "먼저 같은 기간 Nifty 50의 현지 통화 기준 수익률을 확인해 두 상품 중 어느 쪽이 지수와 가까운지 봐 주세요."
    )
    gd = _rv(opposite=True, overseas=False)
    gd["peer"]["label"] = "코스피 200"
    assert E._ask(gd)["guide"][0].startswith(
        "먼저 같은 기간 기초지수 코스피 200의 수익률을"
    )


@pytest.mark.parametrize(
    "kw",
    [
        {},
        {"overseas": False},
        {"official": False},
        {"opposite": True},
        {"opposite": True, "overseas": False},
    ],
)
def test_guides_check_index_before_fx_or_fees(kw: dict[str, bool]) -> None:
    """Q5 — 모든 경로에서 첫 안내 = 지수부터 · 환율 · 보수 등은 그 뒤에만(필요할 때만)."""
    g = E._ask(_rv(**kw))["guide"]
    assert g[0].startswith("먼저 ") and "수익률" in g[0]
    for word in ("환율", "환헤지", "보수", "분배금", "괴리율"):
        assert word not in g[0], word
    rest = " ".join(g[1:])
    # 판정 2026-11-26 §1 — 차이 설명 항목은 출처와 기준 시각을 붙여 · 원인을 말할 때는 실제 근거
    assert (
        "출처와 기준 시각을 붙여 확인해 주세요" in rest
        and "실제 근거를 제시해 주세요" in rest
    )
    if kw.get("opposite"):
        assert "두 상품의 공식 자료" in rest
    else:
        assert "의미 있는 차이를 설명할 필요가 있을 때만" in rest


def test_missing_tail_asks_gap_and_one_deciding_check() -> None:
    """판정 2026-11-26 §1 — 확인이 어려우면 그 공백과 결론을 바꿀 확인 한 가지."""
    assert "확인이 어려우면 그 공백과 결론을 바꿀 확인 한 가지를 적고" in L.MISSING_TAIL
    assert "출처 · 기준일과 함께" in L.MISSING_TAIL


def test_copy_blocks_order_for_domestic_candidate(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(ctx, "DOM001", sessions=NONE_SESSIONS, reviews=[])
    c = rv["copy"]
    order = [
        "[이 묶음에 없는 값]",
        "[검토 범위]",
        "[검토 대상]",
        "[그 뒤 관측]",
        "[AI에 확인할 것]",
        "[답하는 방식]",
        L.DESIGN_QUESTION,
    ]
    idx = [c.index(x) for x in order]
    assert idx == sorted(idx)
    one = rv["one_month"]
    block = c[c.index("[이 묶음에 없는 값]") : c.index("[검토 범위]")]  # noqa: E203
    assert block == (
        "[이 묶음에 없는 값]\n"
        f"- 같은 기간({L.md(one['start'])}~{L.md(one['end'])}) 기초지수 코스피 200의 수익률\n"
        f"이 묶음의 값은 {END}(월)까지 저장한 가격 기준입니다. {L.MISSING_TAIL}\n\n"
    )
    assert "환율" not in block
    assert c.count("[답하는 방식]") == 1 and "보유" not in c and "겹침" not in c


def test_scope_line_without_same_index_products(market: Path) -> None:
    """같은 지수 상품이 없으면 검토 범위에 'KODEX 200'만."""
    ctx = _ctx(market)
    rv = E.compose(ctx, "FLAT01", sessions=NONE_SESSIONS, reviews=[])
    assert rv["peer"]["state"] != "ok"
    assert (
        "[검토 범위] 이 ETF 자체와 비교 대상(같은 기간 KODEX 200)의 공개 근거로 검토해 주세요."
        in rv["copy"]
    )


# --- 저장 · 다시 열기(판정 §4) ---


def test_saved_page_keeps_chart_copy_and_reason(market: Path, tmp_path: Path) -> None:
    app = _app(market, tmp_path)
    bid = _bid(app.page("AAA001"))
    code, out = app.save(
        {
            "build_id": bid,
            "ticker": "AAA001",
            "verdict": "hold",
            "reason": "현지 지수 확인 뒤",
        }
    )
    assert code == 200
    doc = ST.load(app.root, out["review_id"])
    assert "[답하는 방식]" in doc["snapshot"]["copy"]
    saved = PS.render_saved(doc)
    assert saved.count('class="fsvg ') == 3 and "이번 주 지금까지" in saved
    assert "현지 지수 확인 뒤" in saved
    # 자료가 바뀌어도 저장 화면의 그래프 · 복사문은 그때 그대로
    _put(market, "AAA001", [150.0], ["2026-11-24"])
    _put(market, "069500", [80.0], ["2026-11-24"])
    assert "11/24" in app.page("AAA001")
    again = PS.render_saved(ST.load(app.root, out["review_id"]))
    assert again == saved and "11/24(화)" not in again


# --- AI 답 세 칸 · 저장 계약 v2 · 예전 기록(v1) 읽기(PLAN V2 판정 2026-11-26 §3 · §4) ---


def _three(b: str, other: str, **over: Any) -> dict[str, Any]:
    ais = [
        {"name": "GPT", "answer": "답G", "answer_from": b, "helpful": True},
        {"name": "Gemini", "answer": "답M", "answer_from": other},
        {"name": "Claude", "answer": "답C", "answer_from": "mixed", "helpful": True},
    ]
    return {
        "build_id": b,
        "ticker": "AAA001",
        "verdict": "hold",
        "reason": "이유",
        "ais": ais,
        **over,
    }


def test_three_answers_each_own_provenance_reopen_and_list(
    market: Path, tmp_path: Path
) -> None:
    app = _app(market, tmp_path)
    b0 = _bid(app.page("AAA001"))
    _bump(market)
    b = _bid(app.page("AAA001"))
    code, out = app.save(_three(b, b0))
    assert code == 200
    doc = ST.load(app.root, out["review_id"])
    assert doc["schema"] == ST.SCHEMA
    got = {
        a["name"]: (a["asked"]["state"], a["helpful"]) for a in doc["decision"]["ais"]
    }
    assert got == {
        "GPT": ("this_screen", True),
        "Gemini": ("other_screen", False),
        "Claude": ("mixed", True),
    }
    saved = PS.render_saved(doc)
    i_g, i_m, i_c = (saved.index(f"<b>{n}</b>") for n in ("GPT", "Gemini", "Claude"))
    assert i_g < i_m < i_c  # 고정 순서
    assert saved.count("판단에 도움이 된 답</span>") == 2
    assert "질문: 이 화면의 복사문" in saved[i_g:i_m]
    assert "다른 화면(기준일" in saved[i_m:i_c]
    assert "하나로 정할 수 없음" in saved[i_c:]
    assert saved.count("<summary>붙여 넣은 답 전체</summary>") == 3
    line = "AI 답 3개 · 판단에 도움이 된 답 GPT · Claude"
    assert line in app.list_page()
    assert line in app.page("AAA001")  # 검토 화면 아래 '이 ETF 의 지난 판단'


def test_missing_boxes_show_not_entered_and_no_choice(
    market: Path, tmp_path: Path
) -> None:
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    code, out = app.save(
        {
            "build_id": b,
            "ticker": "AAA001",
            "ais": [{"name": "Claude", "answer": "답C"}],
        }
    )
    assert code == 200
    saved = PS.render_saved(ST.load(app.root, out["review_id"]))
    assert saved.count("답 미입력") == 2 and "판단에 도움이 된 답</span>" not in saved
    assert "AI 답 1개 · 판단에 도움이 된 답 고르지 않음" in app.list_page()
    code, out = app.save({"build_id": b, "ticker": "AAA001", "verdict": "hold"})
    assert "AI 답 없음" in app.list_page()


def test_helpful_on_empty_box_is_rejected_before_write(
    market: Path, tmp_path: Path
) -> None:
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    body = {
        "build_id": b,
        "ticker": "AAA001",
        "ais": [
            {"name": "GPT", "answer": "답"},
            {"name": "Gemini", "answer": "", "helpful": True},
        ],
    }
    code, out = app.save(body)
    assert code == 422 and "Gemini" in out["error"]
    assert ST.list_reviews(app.root)["items"] == []


V1_DOC = {
    "schema": "poc7_04_review_v1",
    "decision": {
        "verdict": "hold",
        "reason": "예전이유",
        "next_check": "예전확인",
        "used": [],
        "ai": {
            "name": "Claude",
            "answer": "예전 답 원문",
            "excerpt": "예전 대목",
            "pasted_at": "2026-11-26T00:03:01.310Z",
            "copied_at": "2026-11-25T05:03:19.778Z",
            "asked": {
                "build_id": "20261125T050024Z_8c259b00",
                "state": "unknown_screen",
            },
        },
    },
}


def _put_doc(root: Path, rid: str, doc: dict[str, Any], snap: dict[str, Any]) -> None:
    d = root / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    full = {
        **doc,
        "review_id": rid,
        "saved_at": "2026-11-26T09:03:18+09:00",
        "snapshot": snap,
    }
    (d / f"{rid}.json").write_text(
        json.dumps(full, ensure_ascii=False), encoding="utf-8"
    )


def test_v1_record_with_one_answer_still_opens(market: Path, tmp_path: Path) -> None:
    """예전 기록(답 하나 · 11/26 형수님 저장 형식) — 원문 · 출처 그대로 · 도움 선택 = 미기록(판정 §3-4)."""
    app = _app(market, tmp_path)
    bid = _bid(app.page("AAA001"))
    snap = app.builds[bid]
    rid = "20261126T000318Z_5ef54a10"
    _put_doc(
        app.root,
        rid,
        V1_DOC,
        {k: snap[k] for k in ("ticker", "name", "end", "filters", "copy", "screen")},
    )
    doc = ST.load(app.root, rid)
    saved = PS.render_saved(doc)
    for want in (
        "<b>Claude</b>",
        "판단에 도움 여부 미기록(예전 기록)",
        "어느 화면의 복사문인지 모름",
        "예전 답 원문",
        '쓴 대목: <span class="keep">예전 대목</span>',
        "붙인 시각 11/26 09:03",
        "질문 복사 11/25 14:03",
    ):
        assert want in saved, want
    assert "답 미입력" not in saved  # 예전 기록은 칸 세 개가 아니었음
    assert "AI 답 1개 · 판단에 도움 여부 미기록" in app.list_page()
    empty = json.loads(json.dumps(V1_DOC))
    empty["decision"]["ai"]["answer"] = ""
    _put_doc(
        app.root,
        "20261126T000319Z_5ef54a11",
        empty,
        {k: snap[k] for k in ("ticker", "end", "copy", "screen")},
    )
    assert "붙여 넣은 답 없음" in PS.render_saved(
        ST.load(app.root, "20261126T000319Z_5ef54a11")
    )
    assert "AI 답 없음" in app.list_page()


@pytest.mark.parametrize(
    "bad",
    [
        {"helpful": "yes"},
        {"answer": "  "},
        {"name": "기타"},
        {"asked": None},
        {"pasted_at": "어제"},
    ],
)
def test_v2_record_shape_is_checked_on_read(market: Path, tmp_path: Path, bad) -> None:
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    code, out = app.save(_three(b, b))
    path = app.root / "reviews" / f"{out['review_id']}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["decision"]["ais"][0].update(bad)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        ST.load(app.root, out["review_id"])
    assert ST.list_reviews(app.root)["broken"] == [path.name]


def test_v2_record_duplicate_names_or_old_shape_is_checked(
    market: Path, tmp_path: Path
) -> None:
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    code, out = app.save(_three(b, b))
    path = app.root / "reviews" / f"{out['review_id']}.json"
    good = json.loads(path.read_text(encoding="utf-8"))
    dup = json.loads(json.dumps(good))
    dup["decision"]["ais"][1]["name"] = "GPT"
    old_shape = json.loads(json.dumps(good))
    old_shape["decision"]["ai"] = old_shape["decision"].pop("ais")[0]
    for doc in (dup, old_shape):
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError):
            ST.load(app.root, out["review_id"])


def test_request_cap_fits_three_full_answers() -> None:
    """판정 반영 §6-3 — 답 칸 하나 60,000자 × 세 칸이 요청 상한 안에 들어감(한글 3바이트 · 줄바꿈 이스케이프)."""
    full = "가" * 59000 + "\n" * 1000
    body = {
        "build_id": "20261126T000000Z_00000000",
        "ticker": "AAA001",
        "reason": "가" * 500,
        "next_check": "가" * 500,
        "ai_excerpt": "가" * 4000,
        "ais": [
            {"name": n, "answer": full, "pasted_at": "2026-11-26T00:00:00.000Z"}
            for n in ST.AI_BOXES
        ],
    }
    size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    assert size < SV.MAX_BODY
    assert len(ST.clean_decision(body)["ais"]) == 3


def test_this_week_on_scheduled_end_day(market: Path) -> None:
    """예정 마감일 = 끝일 — 두 종목 마감 뒤 저장이면 주가 끝남(None) · 하나라도 장중이면 진행 주(마감 종가 아직 없음)."""
    ctx = _ctx(market, "2026-11-20")
    assert OB.this_week(ctx, "AAA001") is None
    _set_intraday(market, "AAA001", "2026-11-20")
    ctx = _ctx(market, "2026-11-20")
    tw = OB.this_week(ctx, "AAA001")
    assert tw["state"] == "not_yet" and tw["intraday"] is True
    assert (tw["from"], tw["to"]) == ("2026-11-13", "2026-11-20")
    assert tw["sofar"]["end"] == "2026-11-19"
    assert tw == {**OB.after_move(ctx, "AAA001", "2026-11-13")}  # 표 행과 같은 상태


# --- 반박 검토(2026-11-26) F1 ~ F3 ---


def test_scheduled_end_day_progress_uses_that_day_closes(market: Path) -> None:
    """F1 — 끝일 = 예정 마감일 · '장중'은 그날 종가로 판정(시작일 사유가 앞서지 않게) · 표 = this_week 한 곳."""
    # (a) 그날 두 종목 마감 뒤 저장 · 이 ETF 의 11/13 종가만 장중 → 주가 끝남(완료 주 마감 종가 없음)
    _set_intraday(market, "AAA001", "2026-11-13")
    ctx = _ctx(market, "2026-11-20")
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    a = rv["weeks"]["rows"][-1]["after"]
    assert a["state"] == "ok" and a["etf"]["why"] == "intraday_close"
    assert OB.this_week(ctx, "AAA001") is None and rv["flow"]["progress"] is None
    plain = L.after_plain(rv["weeks"]["rows"][-1])
    assert plain.startswith(
        "11/13 → 11/20 ETF 완료 주 마감 종가 없음(장중 저장값) · KODEX 200 "
    )
    assert "2026-11-20" in rv["flow"]["week_closes"]


def test_scheduled_end_intraday_with_missing_start_is_not_compared(
    market: Path, tmp_path: Path
) -> None:
    """F1 (b) — 끝일 11/20 이 ETF 장중 · 11/13 가격 없음 → 진행 주 · 비교 불가(KODEX 값만 보이지 않음)."""
    with sqlite3.connect(market) as con:
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker='AAA001' AND date='2026-11-13'"
        )
    _set_intraday(market, "AAA001", "2026-11-20")
    ctx = _ctx(market, "2026-11-20")
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    a = rv["weeks"]["rows"][-1]["after"]
    assert a["state"] == "not_yet" and a["intraday"] is True
    assert a["sofar"] == {"end": None, "why": "no_prev_close"}
    assert L.after_plain(rv["weeks"]["rows"][-1]) == (
        "이번 주 지금까지 비교 불가(11/13 직전 주 마감 종가 없음 · 주 진행 중 · "
        "11/20 마감 종가 아직 없음(장중 저장값))"
    )
    f = rv["flow"]
    assert f["progress"]["to"] == "2026-11-20" and "2026-11-20" not in f["week_closes"]
    assert f["marks"][-1]["kind"] == "now"


def test_skipped_week_close_gets_its_own_rank_mark(market: Path) -> None:
    """F2 — 주 마감 규칙이 건너뛴 주(금요일 KODEX 200 장중)의 실제 마감에도 그때 순위 표식(주말 끝일 · 평일 끝일)."""
    _set_intraday(market, "069500", W0)
    _put(market, "AAA001", [130.5], ["2026-11-22"])
    _put(market, "069500", [95.2], ["2026-11-22"])
    ctx = _ctx(market, "2026-11-22")
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    assert [r["date"] for r in rv["weeks"]["rows"]][-1] == "2026-11-13"
    assert f["progress"] is None
    assert f["marks"][-1] == {
        "date": W0,
        "kind": "week",
        "seen": H.seen_at(ctx.restore(W0), "AAA001"),
    }
    ctx = _ctx(market, END)  # 평일 끝일(11/23) — 진행 주 앞에 11/20 표식
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    kinds = [(m["date"], m["kind"]) for m in rv["flow"]["marks"]][-2:]
    assert kinds == [(W0, "week"), (END, "now")]


def test_week_after_holiday_week_is_shown_as_this_week(market: Path) -> None:
    """F3 — 거래일 없는 주(11/16 ~ 11/20 휴장) 다음 진행 주 = 직전 완료 주 마감(11/13)부터 · 표 · 그래프 같은 상태."""
    hol = {"2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"}
    more = ["2026-11-24", "2026-11-25"]
    _put(market, "AAA001", [131.0, 131.5], more)
    _put(market, "069500", [95.1, 95.3], more)
    ctx = H.load_context(
        market,
        "2026-11-25",
        filters=FILTERS,
        official=OFFICIAL,
        dictionary=None,
        is_trading=lambda d: trading(d) and d not in hol,
    )
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    a = rv["weeks"]["rows"][-1]["after"]
    assert a["state"] == "not_yet" and a["from"] == "2026-11-13"
    assert a["sofar"]["end"] == "2026-11-25"
    assert L.after_plain(rv["weeks"]["rows"][-1]).startswith(
        "이번 주 지금까지 11/13 → 11/25 ETF "
    )
    assert rv["flow"]["progress"]["from"] == "2026-11-13"


# --- 검증자 PLAN V2 r1(2026-11-26) F14 ~ F16 ---


def test_copy_text_has_no_user_choices_from_any_record(
    market: Path, tmp_path: Path
) -> None:
    """F14 — 「AI 투자 세션」에서 직접 고른 판단 · POC7-04 내 판단(이유 포함)은 외부 AI 복사문에 없음(공개 자료만)."""
    ctx = _ctx(market)
    recs = [
        {
            "asof": "2026-11-16",
            "verdict": "useful",  # 「요즘 잘 오르는 ETF」 기본값(보류)과 달라 '직접 고름'
            "items": [_true_item(ctx, "2026-11-16")],
        }
    ]
    reviews = [
        {
            "review_id": "20261121T000000Z_aaaaaaaa",
            "ticker": "AAA001",
            "end": W0,
            "saved_at": "2026-11-20T20:00:00+09:00",
            "verdict": "continue",
            "reason": "공개아님이유",
            "filters": FILTERS,
        }
    ]
    rv = E.compose(ctx, "AAA001", sessions=_sessions(tmp_path, recs), reviews=reviews)
    c = rv["copy"]
    assert (
        _cite_line(recs[0]["items"][0], "2026-11-16") in c
    )  # 같은 조건 기록의 공개 값은 인용
    for local in ("쓸 만함", "직접 고름", "사용자 판단", "내 판단", "공개아님이유"):
        assert local not in c, local
    # '검토 계속'은 답하는 방식 · 설계 질문의 낱말로만(내 판단 값으로는 나오지 않음)
    assert c.count("검토 계속") == c.count("'검토 계속'") == 1
    # 화면(로컬)에는 그대로 보임
    weeks = _text(PG.weeks_html(rv))
    assert "내 판단" in weeks
    # 지난 검토와 비교가 표 밖(10/20 주)의 「AI 투자 세션」 기록일 때도 순위 · 1개월 값만
    old = [
        {
            "asof": "2026-10-20",
            "verdict": "useful",
            "items": [_true_item(ctx, "2026-10-20")],
        }
    ]
    (tmp_path / "old").mkdir()
    old_sessions = _sessions(tmp_path / "old", old)
    rv2 = E.compose(ctx, "AAA001", sessions=old_sessions, reviews=[])
    assert (
        rv2["previous"]["kind"] == "session" and rv2["previous"]["asof"] == "2026-10-20"
    )
    c2 = rv2["copy"]
    assert _cite_line(old[0]["items"][0], "2026-10-20") in c2
    assert "쓸 만함" not in c2 and "직접 고름" not in c2 and "사용자 판단" not in c2
    # 내 판단 기록이 있어도(지난 검토와 비교 = 내 판단) 복사문은 같은 저장 기록을 인용(반박 검토)
    rv3 = E.compose(ctx, "AAA001", sessions=old_sessions, reviews=reviews)
    assert rv3["previous"]["kind"] == "review"
    assert _cite_line(old[0]["items"][0], "2026-10-20") in rv3["copy"]
    assert "인용할 기록 없음" not in rv3["copy"]


def test_graph_line_stops_at_last_common_close(market: Path) -> None:
    """F15 — 끝일 11/24 에 이 ETF 만 마감 종가 · KODEX 200 은 장중 → 두 선 모두 11/23 에서 끝(표 · 복사문과 같은 끝일)."""
    _put(market, "AAA001", [131.0], ["2026-11-24"])
    _put(market, "069500", [94.0], ["2026-11-24"])
    _set_intraday(market, "069500", "2026-11-24")
    ctx = _ctx(market, "2026-11-24")
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    f = rv["flow"]
    so = rv["weeks"]["rows"][-1]["after"]["sofar"]
    assert f["last"] == END == so["end"]
    tail = [p for p in f["points"] if p["date"] == "2026-11-24"][0]
    assert tail["etf"] is None and tail["etf_why"] == "after_common"
    assert tail["kodex"] is None and tail["kodex_why"] == "intraday_close"
    assert PC.missing_lines(f) == [
        "11/24(화) — KODEX 200 장중 저장값(마감 전)",
        "11/24(화)부터 — 두 종목 공통 마감 종가가 없어 그리지 않음(끝 값 = 11/23(월))",
    ]
    for cls, w, h in PC.VARIANTS:
        s = PC.svg(f, cls, w, h)
        ends = {}
        for color in ("var(--s-etf)", "var(--s-kdx)"):
            pat = 'points="([^"]+)" fill="none" stroke="' + re.escape(color) + '"'
            pts = re.findall(pat, s)
            ends[color] = float(pts[-1].split()[-1].split(",")[0])
        assert (
            ends["var(--s-etf)"] == ends["var(--s-kdx)"]
        )  # 두 선의 마지막 x 좌표가 같음
        _no_overlap(s)
    tips = re.findall(r"<title>([^<]*)</title>", PC.svg(f, "w", 820, 230))
    assert (
        "이 ETF 그리지 않음(두 종목 공통 마감일 11/23 뒤)" in tips[-1]
    )  # 값은 있지만 그리지 않음


def test_ai_answer_original_whitespace_is_kept(market: Path, tmp_path: Path) -> None:
    """F16 — 답 원문의 첫 줄 들여쓰기 · 마지막 줄바꿈까지 그대로 저장 · 다시 열기 · 공백만이면 답 없음."""
    app = _app(market, tmp_path)
    b = _bid(app.page("AAA001"))
    raw = "    첫 줄(들여쓰기)\n둘째 줄\n"
    code, out = app.save(
        {
            "build_id": b,
            "ticker": "AAA001",
            "ais": [
                {"name": "GPT", "answer": raw, "helpful": True},
                {"name": "Gemini", "answer": " \n\t "},
            ],
        }
    )
    assert code == 200
    doc = ST.load(app.root, out["review_id"])
    assert [(a["name"], a["answer"]) for a in doc["decision"]["ais"]] == [("GPT", raw)]
    # <pre> 바로 뒤 줄바꿈 하나는 HTML 이 버리므로 하나를 앞에 둠 — 원문 첫 줄바꿈도 지킴
    assert f"<pre>\n{raw}</pre>" in PS.render_saved(doc)
    body = {"build_id": b, "ticker": "AAA001"}
    for blank in (
        "  ",
        "\ufeff",
        " \ufeff\n",
    ):  # 공백 · BOM 만 = 답 없음(화면 JS trim 과 같게)
        one = [{"name": "Claude", "answer": blank, "helpful": True}]
        assert app.save({**body, "ais": one})[0] == 422
        code, out = app.save({**body, "ais": [{"name": "Claude", "answer": blank}]})
        assert ST.load(app.root, out["review_id"])["decision"]["ais"] == []
    lead = "\n결론: 보류\n"
    code, out = app.save({**body, "ais": [{"name": "GPT", "answer": lead}]})
    assert f"<pre>\n{lead}</pre>" in PS.render_saved(
        ST.load(app.root, out["review_id"])
    )


def test_copy_text_is_the_same_with_unreadable_local_records(
    market: Path, tmp_path: Path
) -> None:
    """F17 — 읽을 수 있는 기록이 같으면 손상된 로컬 기록이 있든 없든 외부 복사문은 글자 하나까지 같음."""
    ctx = _ctx(market)
    rec = {"asof": "2026-11-16", "items": [_true_item(ctx, "2026-11-16")]}
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    good = _sessions(tmp_path / "a", [rec])
    broken = _sessions(
        tmp_path / "b",
        [rec, {"asof": "2026-11-17", "items": "{깨짐"}, {"asof": "11/18", "items": []}],
    )
    assert broken["broken"] == 2 and len(broken["records"]) == 1
    c_good = E.compose(ctx, "AAA001", sessions=good, reviews=[])["copy"]
    rv = E.compose(ctx, "AAA001", sessions=broken, reviews=[])
    assert rv["copy"] == c_good
    assert _cite_line(rec["items"][0], "2026-11-16") in c_good
    for local in ("못 읽은", "빠짐", "기록 파일", "읽지 못함", "확인 불가(", "2건"):
        assert local not in rv["copy"], local
    # 화면(로컬)에는 못 읽은 기록 수가 그대로
    assert "못 읽은 「AI 투자 세션」 기록 2건 빠짐" in _text(PG.weeks_html(rv))


def test_unreadable_official_info_is_not_called_absent(
    market: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """공식 기준정보 파일을 못 읽으면 '이 ETF 가 없다'고 단정하지 않음 — 화면 = 읽지 못함 · 복사문 = 로컬 상태 없이."""
    ctx = H.load_context(
        market,
        None,
        filters=FILTERS,
        official=None,
        dictionary=None,
        is_trading=trading,
    )
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    assert (
        rv["peer"] == {"state": "official_unread"}
        and rv["ask"]["kind"] == "no_official"
    )
    assert rv["gap"]["text"].startswith("공식 기준정보를 읽지 못해")
    c = rv["copy"]
    assert (
        "[판단에 영향을 주는 자료 공백] 이 묶음에는 이 ETF 의 기초지수와 상품 구조가 없습니다 · "
        in c
    )
    for bad in ("공식 기준정보에 이 ETF 가 없어", "읽지 못", "파일"):
        assert bad not in c, bad
    assert "공식 기준정보를 읽지 못해" in PG.one_html(rv)  # 화면(로컬)은 정확한 사유
    # 실제로 없을 때(읽기는 됨)는 그대로 '없어'
    missing = {k: v for k, v in OFFICIAL.items() if k != "AAA001"}
    ctx2 = H.load_context(
        market,
        None,
        filters=FILTERS,
        official=missing,
        dictionary=None,
        is_trading=trading,
    )
    rv2 = E.compose(ctx2, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    assert rv2["peer"] == {"state": "no_official"}
    assert "공식 기준정보에 이 ETF 가 없어" in rv2["copy"]
    # 실행 스크립트 — 못 읽으면 None 을 넘김(빈 목록이면 '없다'로 판정돼 버림)
    import importlib.util

    from app import api_etf_compare as AE

    spec = importlib.util.spec_from_file_location(
        "run_weekly_decision_test", REPO / "scripts" / "run_weekly_decision.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(AE, "_official", lambda: ({}, {"status": "unavailable"}))
    monkeypatch.setattr(AE, "_dictionary", lambda: (None, {}))
    assert mod._sources() == (None, None)
    monkeypatch.setattr(AE, "_official", lambda: (OFFICIAL, {"status": "ok"}))
    assert mod._sources() == (OFFICIAL, None)
