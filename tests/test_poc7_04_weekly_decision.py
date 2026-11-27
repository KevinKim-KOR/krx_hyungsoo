"""POC7-04 관심 ETF 한 건의 주간 판단 근거 — 지난 네 주 복원 · 기록 대조 · 문장 · 복사문 · 화면 조각(tmp DB 만 · 라이브 DB 안 엶)."""

from __future__ import annotations

import hashlib
import itertools
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

from app.market_evidence_text import LATEST_CHECK
from app.weekly_decision import evidence as E
from app.weekly_decision import history as H
from app.weekly_decision import observe as OB
from app.weekly_decision import lines as L
from app.weekly_decision import page as PG
from app.weekly_decision import page_base as PB
from app.weekly_decision import page_live as PL
from app.weekly_decision import peers as P
from tests._poc7_04_support import (
    REPO,
    KST,
    FILTERS,
    END,
    ROWS,
    trading,
    _line,
    _put,
    OFFICIAL,
    make_market,
    _ctx,
    _item,
    _decision,
    _sessions,
    NONE_SESSIONS,
    _rv,
    FakeReader,
    _records_for_copy,
)


@pytest.fixture
def market(tmp_path: Path) -> Path:
    return make_market(tmp_path)


def test_review_rows_unfinished_week_takes_last_four(market: Path) -> None:
    ctx = _ctx(market)
    assert ctx.end == END and ctx.rows == ROWS and ctx.rows_gap is None


def test_review_rows_finished_week_takes_four_before(market: Path) -> None:
    ctx = _ctx(market, "2026-11-20")  # 금요일 마감 뒤 — 검토가 속한 주(11/20 주)가 끝남
    assert ctx.build["weekly"]["finished"] is True
    assert ctx.rows == ["2026-10-23", "2026-10-30", "2026-11-06", "2026-11-13"]


def test_review_rows_without_dates_reports_reason() -> None:
    assert H.review_rows({"status": "no_common_period"}) == ([], "no_common_period")
    b = {"status": "ok", "weekly": {"dates": None, "gap": {"why": "too_few_weeks"}}}
    assert H.review_rows(b) == ([], "too_few_weeks")


def test_restore_refuses_dates_after_end(market: Path) -> None:
    ctx = _ctx(market)
    with pytest.raises(ValueError):
        ctx.restore("2026-11-24")


def test_restore_ignores_prices_after_the_row_date(market: Path) -> None:
    """AC1 — 그날 뒤 가격을 바꿔도 그때 순위 · 1개월 · 오른 주는 같고, 바뀌는 것은 '그 뒤 관측'뿐."""
    before = _ctx(market)
    seen0 = [H.seen_at(before.restore(d), "DOM001") for d in ROWS]
    after0 = OB.after_move(before, "DOM001", ROWS[0])
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET close = close * 3 WHERE ticker='DOM001' AND date > ?",
            (ROWS[0],),
        )
    again = _ctx(market)
    assert H.seen_at(again.restore(ROWS[0]), "DOM001") == seen0[0]
    assert OB.after_move(again, "DOM001", ROWS[0]) != after0  # 관측만 바뀜
    assert again.item("DOM001")["rank"] != before.item("DOM001")["rank"]


def test_exclusion_matches_build_counts_in_every_restore(market: Path) -> None:
    ctx = _ctx(market)
    for d in ROWS + [END]:
        rs = ctx.restore(d)
        b = rs["build"]
        got = Counter(
            H.exclusion(rs["market"], t, FILTERS, b["windows"]["one_month"])
            for t in rs["market"]["names"]
        )
        for k in (
            "no_price",
            "filter_excluded",
            "no_return",
            "end_differs",
            "start_differs",
        ):
            assert got.get(k, 0) == b["counts"][k], (d, k)
        assert got["in_population"] == b["counts"]["population"]
    assert H.exclusion(ctx.market, "NOPE99", FILTERS, ("a", "b")) == "not_listed"


def test_seen_at_reasons(market: Path) -> None:
    ctx = _ctx(market)
    rs = ctx.restore(ROWS[0])
    assert H.seen_at(rs, "AAA003") == {"state": "out", "why": "filter_excluded"}
    assert H.seen_at(rs, "LATE01") == {"state": "out", "why": "no_price"}
    s = H.seen_at(rs, "AAA002")
    assert (
        s["state"] == "ranked"
        and s["rank"] == 1
        and s["top30"] is True
        and s["up"] == 4
    )
    assert H.seen_at({"build": {"status": "no_common_period"}}, "X") == {
        "state": "unknown",
        "why": "no_common_period",
    }


def test_after_move_values_not_yet_and_missing(market: Path) -> None:
    ctx = _ctx(market)
    a = OB.after_move(ctx, "AAA001", ROWS[0])
    rows = {r.date: r.close for r in ctx.market["raw"]["AAA001"]}
    k = {r.date: r.close for r in ctx.market["kodex_full"]}
    assert a["state"] == "ok" and a["to"] == ROWS[1]
    assert a["etf"]["value"] == pytest.approx((rows[ROWS[1]] / rows[ROWS[0]] - 1) * 100)
    assert a["kodex"]["value"] == pytest.approx((k[ROWS[1]] / k[ROWS[0]] - 1) * 100)
    last = OB.after_move(ctx, "AAA001", ROWS[-1])
    # 기간 미경과 행 = 이번 주 지금까지(V2) — 11/20 → 끝일 11/23(두 종목 공통 마감 종가 마지막 날)
    assert last == {
        "state": "not_yet",
        "from": ROWS[-1],
        "to": "2026-11-27",
        "sofar": {
            "end": END,
            "etf": {
                "value": pytest.approx((rows[END] / rows[ROWS[-1]] - 1) * 100),
                "why": None,
            },
            "kodex": {
                "value": pytest.approx((k[END] / k[ROWS[-1]] - 1) * 100),
                "why": None,
            },
            "why": None,
        },
    }
    with sqlite3.connect(market) as con:
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker='AAA001' AND date=?", (ROWS[1],)
        )
        con.execute(
            "UPDATE etf_daily_price SET fetched_at='2026-11-13T03:00:00+00:00' "
            "WHERE ticker='AAA002' AND date='2026-11-13'"
        )
    ctx2 = _ctx(market)
    m = OB.after_move(ctx2, "AAA001", ROWS[0])
    assert (
        m["etf"] == {"value": None, "why": "no_price"}
        and m["kodex"]["value"] is not None
    )
    i = OB.after_move(ctx2, "AAA002", ROWS[1])
    assert i["etf"] == {"value": None, "why": "intraday_close"}


def test_next_week_end_uses_schedule_after_last_listed_date() -> None:
    assert OB.next_week_end("2026-11-20", ROWS, trading) == "2026-11-27"
    assert OB.next_week_end("2026-11-06", ROWS, trading) == "2026-11-13"
    assert OB.next_week_end("2026-11-20", ROWS, lambda d: False) is None


def test_read_sessions_is_read_only_and_skips_broken_rows(tmp_path: Path) -> None:
    db = _decision(
        tmp_path,
        [
            {
                "asof": "2026-11-16",
                "items": [_item(3, "AAA001", 10.5, "2026-10-19", "2026-11-16")],
            },
            {"asof": "2026-11-16", "items": "{not json"},
            {"asof": "11/16", "items": []},  # 날짜 형식 깨짐 — 실제 파싱으로 거름
        ],
    )
    sha = hashlib.sha256(db.read_bytes()).hexdigest()
    got = H.read_sessions(db)
    assert got["state"] == "ok" and len(got["records"]) == 1 and got["broken"] == 2
    assert hashlib.sha256(db.read_bytes()).hexdigest() == sha
    assert H.read_sessions(tmp_path / "none.sqlite")["state"] == "missing"
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    assert H.read_sessions(empty)["state"] == "error"


@pytest.mark.parametrize(
    "source,verdict,want",
    [
        ("market_discovery", "hold", "default"),
        ("market_discovery", "useful", "chosen"),
        ("today_weekly_review", "unrecorded", "unrecorded"),
        ("today_weekly_review", "hold", "chosen"),
        ("holdings_compare_preview", "hold", "default"),
    ],
)
def test_verdict_state_uses_source_default(
    tmp_path: Path, source: str, verdict: str, want: str
) -> None:
    s = _sessions(
        tmp_path,
        [{"asof": "2026-11-16", "source": source, "verdict": verdict, "items": []}],
    )
    assert H.verdict_state(s["records"][0]) == want


def test_week_records_by_iso_week_and_end(tmp_path: Path) -> None:
    recs = _sessions(
        tmp_path,
        [
            {
                "asof": "2026-11-16",
                "items": [_item(3, "AAA001", 10.5, "2026-10-19", "2026-11-16")],
            },
            {
                "asof": "2026-11-17",
                "items": [_item(1, "DOM001", 3.0, "2026-10-20", "2026-11-17")],
            },
            {
                "asof": "2026-11-23",
                "items": [_item(2, "AAA001", 12.0, "2026-10-26", "2026-11-23")],
            },
        ],
    )["records"]
    w = H.week_records(recs, "2026-11-20", END, "AAA001")
    assert w["count"] == 2 and [m["record"]["asof"] for m in w["mine"]] == [
        "2026-11-16"
    ]
    assert (
        H.week_records(recs, "2026-11-20", "2026-11-16", "AAA001")["count"] == 1
    )  # 끝일 뒤 기록 제외


def test_latest_comparable_skips_records_without_values(tmp_path: Path) -> None:
    recs = _sessions(
        tmp_path,
        [
            {
                "asof": "2026-11-09",
                "items": [_item(5, "AAA001", 8.0, "2026-10-12", "2026-11-09")],
            },
            {
                "asof": "2026-11-16",
                "source": "holdings_compare_preview",
                "items": [
                    {"rank": None, "ticker": "AAA001", "same_period_kodex200": None}
                ],
            },
            {
                "asof": "2026-11-24",
                "items": [_item(1, "AAA001", 20.0, "2026-10-27", "2026-11-24")],
            },
        ],
    )["records"]
    got = H.latest_comparable(recs, END, "AAA001")
    assert got["record"]["asof"] == "2026-11-09"


def test_reconcile_match_differs_and_uses_record_filters(
    market: Path, tmp_path: Path
) -> None:
    ctx = _ctx(market)
    seen = H.seen_at(ctx.restore("2026-11-16"), "AAA001")
    v = round(seen["one_month"]["value"], 4)
    s, e = seen["one_month"]["start"], seen["one_month"]["end"]
    recs = _sessions(
        tmp_path,
        [
            {"asof": "2026-11-16", "items": [_item(seen["rank"], "AAA001", v, s, e)]},
            {
                "asof": "2026-11-16",
                "items": [_item(seen["rank"] + 1, "AAA001", v, s, e)],
            },
            {
                "asof": "2026-11-16",
                "filters": {**FILTERS, "exclude_synthetic": False},
                "items": [_item(seen["rank"], "AAA001", v, s, e)],
            },
        ],
    )["records"]
    assert H.reconcile(ctx, recs[0], recs[0]["items"][0])["state"] == "match"
    assert H.reconcile(ctx, recs[1], recs[1]["items"][0])["state"] == "differs"
    # 합성 포함 조건이면 AAA003 이 앞에 들어와 순위가 하나 밀린다 — 기록 자신의 조건으로 복원
    third = H.reconcile(ctx, recs[2], recs[2]["items"][0])
    assert third["state"] == "differs" and third["restored"]["rank"] == seen["rank"] + 1


def test_peers_same_structure_other_reasons(market: Path) -> None:
    ctx = _ctx(market)
    p = P.peers_of("AAA001", OFFICIAL, H._by_ticker(ctx.build), ctx.market["names"])
    assert p["label"] == "Nifty 50" and p["overseas"] is True
    assert [x["ticker"] for x in p["same"]] == ["AAA002"]
    why = {o["ticker"]: o for o in p["other"]}
    assert (
        why["AAA003"]["why"] == "structure" and "합성(패시브)" in why["AAA003"]["diff"]
    )
    assert why["AAA004"]["diff"] == ["환헤지 표시 다름"]
    d = P.peers_of("DOM001", OFFICIAL, H._by_ticker(ctx.build), ctx.market["names"])
    assert {o["ticker"]: o["why"] for o in d["other"]} == {
        "DOM003": "not_in_population"
    }
    assert P.peers_of("FLAT01", OFFICIAL, {}, {}) == {"state": "no_official"}


@pytest.mark.parametrize(
    "name,want",
    [
        ("Nifty 50 Index", "Nifty 50"),
        ("코스피 200", "코스피 200"),
        ("S&P 500 지수", "S&P 500"),
        ("Index", "Index"),
    ],
)
def test_index_label(name: str, want: str) -> None:
    assert P.index_label(name) == want


@pytest.mark.parametrize(
    "word,want",
    [
        ("Nifty 50", "은"),
        ("코스피 200", "은"),
        ("Nikkei 225", "는"),
        ("코스닥", "은"),
        ("나스닥", "은"),
        ("항셍", "은"),
        ("유로스톡스", "는"),
        ("MSCI World", " 지수는"),
    ],
)
def test_topic_particle(word: str, want: str) -> None:
    assert L.topic(word) == want


def test_pct_and_dates() -> None:
    assert L.pct(18.1064) == "+18.11%"
    assert L.pct(-14.093) == "−14.09%"
    assert L.pct(-0.001) == "0.00%"
    assert L.pct(10.79729, 4) == "+10.7973%"
    assert L.md("2026-11-06") == "11/6" and L.mdw("2026-11-20") == "11/20(금)"


GAP_ORDER = ["no_official", "price_state", "weekly", "peer_gap", "currency", "index"]


@pytest.mark.parametrize("combo", list(itertools.product([True, False], repeat=5)))
def test_gap_decision_order(combo: tuple[bool, ...]) -> None:
    """판정 순서 조합 표 — 앞 조건이 참이면 뒤 조건과 무관하게 앞 종류(순서 뒤집기 변이를 잡음)."""
    no_off, intraday, no_week, overseas, opposite = combo
    rv = _rv(
        official=not no_off,
        price="intraday" if intraday else "after_close",
        up=None if no_week else 3,
        overseas=overseas,
        opposite=opposite,
    )
    flags = [
        no_off,
        intraday,
        no_week,
        opposite and not no_off,
        overseas and not no_off,
    ]
    want = next((k for k, f in zip(GAP_ORDER, flags) if f), "index")
    assert E._gap(rv)["kind"] == want


@pytest.mark.parametrize("combo", list(itertools.product([True, False], repeat=3)))
def test_ask_decision_order(combo: tuple[bool, ...]) -> None:
    official, opposite, overseas = combo
    rv = _rv(official=official, overseas=overseas, opposite=opposite)
    want = (
        "no_official"
        if not official
        else "peer_gap" if opposite else "local_index" if overseas else "index"
    )
    assert E._ask(rv)["kind"] == want


def test_ask_text_follows_sign_and_plan_example() -> None:
    assert E._ask(_rv())["text"] == "10/26~11/23에 Nifty 50은 현지 통화로도 올랐나요?"
    fall = _rv(v=-5.0)
    assert E._ask(fall)["text"] == "10/26~11/23에 Nifty 50은 현지 통화로도 내렸나요?"
    dom = _rv(overseas=False)
    dom["peer"]["label"] = "코스피 200"
    assert E._ask(dom)["text"] == "10/26~11/23에 기초지수 코스피 200도 이만큼 올랐나요?"
    gap = E._ask(_rv(opposite=True))["text"]
    assert "피어(P1)의 수익률은 −10.00%였습니다" in gap and "+10.00%" in gap


def test_design_question_is_verbatim_from_design_doc() -> None:
    doc = (
        REPO
        / "docs/ai_design/POC7/POC7_04_WEEKLY_ETF_REVIEW_DECISION_SUPPORT_DESIGN_V1_2026-11-24.md"
    ).read_text(encoding="utf-8")
    assert "> " + L.DESIGN_QUESTION in doc


def test_compose_values_and_copy_contract(market: Path, tmp_path: Path) -> None:
    ctx = _ctx(market)
    sessions = _sessions(tmp_path, _records_for_copy())
    reviews = [
        {
            "review_id": "20261123T000000Z_aaaaaaaa",
            "ticker": "AAA001",
            "end": "2026-11-20",
            "saved_at": "2026-11-20T20:00:00+09:00",
            "verdict": "hold",
            "reason": "내이유ZZZ",
            "filters": FILTERS,
            "rank": 2,
            "one_month": {"value": 7.0, "start": "2026-10-21", "end": "2026-11-20"},
        }
    ]
    rv = E.compose(
        ctx, "AAA001", sessions=sessions, reviews=reviews, reader=FakeReader()
    )
    item = ctx.item("AAA001")
    assert rv["rank"] == item["rank"] and rv["one_month"] == item["one_month"]
    assert rv["kodex"] == ctx.build["kodex"]["one_month"] and rv["up"] == 4
    assert rv["previous"]["kind"] == "review"  # Q7 — POC7-04 기록이 먼저
    assert rv["ask"]["kind"] == "local_index" and rv["gap"]["kind"] == "currency"
    assert rv["composition"]["weight"] == pytest.approx(70.5)
    assert rv["composition"]["weight_missing"] == 1
    assert rv["composition"]["overlap"] == {
        "checked": 2,
        "hits": ["보유주식ABC"],
        "other_date": [],
    }
    c = rv["copy"]
    one = rv["one_month"]
    when = f"{L.md(one['start'])}~{L.md(one['end'])}"
    # V2 Q3 · Q4 — 첫머리 문단 → 이 묶음에 없는 값 · 저장 기준일 → 검토 범위 → 검토 대상
    assert c.startswith(
        LATEST_CHECK
        + "\n\n[이 묶음에 없는 값]\n"
        + f"- 같은 기간({when}) {rv['peer']['label']}의 현지 통화 기준 수익률\n"
        + "- 같은 기간 환율(ETF 원화 가격과 같은 시각 기준)\n"
        + f"이 묶음의 값은 {END}(월)까지 저장한 가격 기준입니다. {L.MISSING_TAIL}\n\n"
        + "[검토 범위] 이 ETF 자체와 비교 대상(같은 기간 KODEX 200 · 같은 지수 상품)의 공개 근거로 "
        + f"검토해 주세요. {L.SCOPE_TAIL}\n\n"
        + "[검토 대상] 가 인도A(AAA001)"
    )
    # V2 Q1 · Q2 — 답하는 방식이 설계 §4 질문 바로 앞 · 질문 원문으로 끝
    assert c.rstrip().endswith("\n".join(L.ANSWER_FORMAT) + "\n\n" + L.DESIGN_QUESTION)
    assert f"[AI에 확인할 것] {rv['ask']['text']}" in c
    # 11/16 기록은 저장값(2위 · +9.50%)이 그날 다시 계산한 값과 달라 같은 조건인지 확인 못 함 → 인용 안 함
    # (V2 RESULT 판정 §2 · 사용자가 고른 판단도 넣지 않음 · F14)
    m = [x for r in rv["weeks"]["rows"] for x in r["records"]["mine"]][0]
    assert m["cite"] == "unknown" and m["check"]["state"] == "differs"
    assert "[당시 저장 기록] 인용할 기록 없음\n" in c
    for local in ("사용자 판단", "내 판단", "직접 고름", "미확인", "쓸 만함"):
        assert local not in c, local
    so = rv["weeks"]["rows"][-1]["after"]["sofar"]
    assert (
        f"이번 주 지금까지 11/20 → 11/23 ETF {L.pct(so['etf']['value'])} · "
        f"KODEX 200 {L.pct(so['kodex']['value'])}(주 진행 중 · 11/27 마감 예정)"
    ) in c
    assert "기간 미경과" not in c
    # 개인 항목 · 메모 원문 · 내 이유 · 구성 · 겹침 · '보유와 비교' 기록은 복사문에 없음
    for bad in (
        "비밀메모XYZ",
        "다음확인QQQ",
        "내이유ZZZ",
        "보유주식ABC",
        "보유",
        "겹침",
        "편입 비중",
    ):
        assert bad not in c, bad


def test_compose_previous_priority_and_end_cut(market: Path, tmp_path: Path) -> None:
    ctx = _ctx(market)
    sessions = _sessions(tmp_path, _records_for_copy())
    late = [
        {"ticker": "AAA001", "end": "2026-11-24", "saved_at": "x", "verdict": "hold"}
    ]
    rv = E.compose(ctx, "AAA001", sessions=sessions, reviews=late)
    assert (
        rv["previous"]["kind"] == "session" and rv["previous"]["asof"] == "2026-11-16"
    )
    assert rv["previous"]["verdict_state"] == "default"
    rv2 = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    assert rv2["previous"] == {
        "kind": "restore",
        "date": ROWS[-1],
        "seen": rv2["weeks"]["rows"][-1]["seen"],
    }
    assert rv2["composition"] is None
    with pytest.raises(KeyError):
        E.compose(
            ctx, "AAA003", sessions=NONE_SESSIONS, reviews=[]
        )  # 조건 제외 — 후보 목록 밖


def test_compose_week_rows_and_records(market: Path, tmp_path: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(
        ctx, "AAA001", sessions=_sessions(tmp_path, _records_for_copy()), reviews=[]
    )
    rows = rv["weeks"]["rows"]
    assert [r["date"] for r in rows] == ROWS
    assert rows[1]["records"] == {"count": 1, "mine": []}  # 11/3 기록 — 이 ETF 없음
    mine = rows[3]["records"]["mine"]
    assert rows[3]["records"]["count"] == 2 and len(mine) == 2
    assert (
        mine[0]["check"]["state"] == "differs"
    )  # 저장 2위 · 9.5% 는 이 가짜 자료 복원과 다름
    assert mine[1]["check"] is None  # 순위 · 값 없는 기록은 대조하지 않음
    assert rows[3]["after"]["state"] == "not_yet"


def test_flow_groups_and_text(market: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(ctx, "DOM002", sessions=NONE_SESSIONS, reviews=[])
    groups = L.flow_groups(rv)
    assert all(g["kind"] in ("top30", "outside", "unknown") for g in groups)
    assert sum(len(g["dates"]) for g in groups) == 4
    text = PG.flow_text(rv)
    assert text.endswith(f"11/23 {rv['rank']}위")
    fake = {
        "end": END,
        "rank": 4,
        "weeks": {
            "rows": [
                {
                    "date": ROWS[0],
                    "seen": {"state": "ranked", "rank": 138, "top30": False},
                },
                {
                    "date": ROWS[1],
                    "seen": {"state": "ranked", "rank": 9, "top30": True},
                },
                {
                    "date": ROWS[2],
                    "seen": {"state": "ranked", "rank": 9, "top30": True},
                },
                {"date": ROWS[3], "seen": {"state": "out", "why": "no_price"}},
            ]
        },
    }
    assert PG.flow_text(fake) == (
        "10/30 순위권 밖(138위) → 11/6 · 11/13 마감 기준 상위 30(9 · 9위) → "
        "11/20 순위 확인 불가(그날까지 저장 가격 없음) → 11/23 4위"
    )
    assert L.flow_plain(fake) == (
        "10/30 138위(순위권(상위 30) 밖) → 11/6 9위 → 11/13 9위 → "
        "11/20 순위 확인 불가(그날까지 저장 가격 없음)"
    )


def test_page_order_and_decoration(market: Path, tmp_path: Path) -> None:
    ctx = _ctx(market)
    rv = E.compose(
        ctx, "AAA001", sessions=_sessions(tmp_path, _records_for_copy()), reviews=[]
    )
    html = PL.render_live(
        rv, build_id="20261123T000000Z_bbbbbbbb", candidates=[], reviews=[]
    )
    pos = [
        html.index(t)
        for t in (
            "왜 이번에 보나",
            "<h2>지난 네 주</h2>",
            "AI에 확인할 것",
            "내 판단 남기기",
        )
    ]
    assert pos == sorted(pos)
    assert '<span class="up nw">+' in html and "사용자 판단 미확인" in html
    # 로컬 화면에는 보임 — [자세히] 팝업 안 항목(메모 줄바꿈 유지)
    assert (
        '<dt>메모(이 화면에서만)</dt><dd><span class="keep">비밀메모XYZ</span></dd>'
        in html
    )
    assert PB.deco("'보류' · 10/26 ~ 11/23 −2.00%") == (
        '<span class="nw">\'보류\'</span> · <span class="nw">10/26 ~ 11/23</span> '
        '<span class="down nw">−2.00%</span>'
    )
    assert PB.deco("<b>&") == "&lt;b&gt;&amp;"


def test_read_sessions_tolerates_odd_rows(tmp_path: Path) -> None:
    """검토 1 — 칸 형이 틀린 행은 그 행만 건너뛰거나(형 오류) 비교 불가로 읽는다(전체 실패 금지)."""
    rows = [
        {
            "asof": "2026-11-16",
            "items": [{"ticker": "AAA001", "same_period_kodex200": "x"}],
        },
        {
            "asof": "2026-11-16",
            "items": [{"ticker": "AAA001", "same_period_kodex200": {"one_month": 3}}],
        },
        {"asof": "2026-11-16", "items": "[1]"},
        {"asof": "2026-11-16", "items": "{}"},
        {"asof": "2026-11-16", "created": "언젠가", "items": []},
    ]
    got = H.read_sessions(_decision(tmp_path, rows))
    assert got["state"] == "ok" and len(got["records"]) == 2 and got["broken"] == 3
    assert all(not H.comparable(r["items"][0]) for r in got["records"])


def test_unreadable_sessions_never_claim_none(market: Path, tmp_path: Path) -> None:
    """검토 2 · 검증 F17 — 기록을 못 읽으면 화면은 '확인 불가'와 사유 · 외부 복사문은 로컬 기록 상태 없이
    '인용할 기록 없음'(없다고 단정하지 않음 · 공개 자료 한정)."""
    ctx = _ctx(market)
    clean = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[])
    assert "[당시 저장 기록] 인용할 기록 없음\n" in clean["copy"]
    for sessions, why in (
        (
            {"state": "error", "records": [], "broken": 0},
            "「AI 투자 세션」 기록을 읽지 못함",
        ),
        (
            {"state": "missing", "records": [], "broken": 0},
            "「AI 투자 세션」 기록 파일 없음",
        ),
        (
            {"state": "ok", "records": [], "broken": 2},
            "못 읽은 「AI 투자 세션」 기록 2건 빠짐",
        ),
    ):
        rv = E.compose(ctx, "AAA001", sessions=sessions, reviews=[])
        assert rv["copy"] == clean["copy"] and why not in rv["copy"]
        html = PL.render_live(
            rv, build_id="20261123T000000Z_bbbbbbbb", candidates=[], reviews=[]
        )
        assert html.count("<div>확인 불가</div>") == 4 and "<div>없음</div>" not in html
        assert why in html
    rv = E.compose(ctx, "AAA001", sessions=NONE_SESSIONS, reviews=[], reviews_broken=1)
    # 내 판단 기록 · 못 읽은 수도 복사문에 없음(화면에는 남음 · PLAN V2 판정 §1 · F14)
    assert rv["copy"] == clean["copy"] and "내 판단" not in rv["copy"]
    html = PL.render_live(
        rv, build_id="20261123T000000Z_bbbbbbbb", candidates=[], reviews=[]
    )
    assert "못 읽은 내 판단 기록 1건 빠짐" in html


def test_records_made_after_review_time_are_excluded(
    market: Path, tmp_path: Path
) -> None:
    """검토 3 — 기준일이 끝일 이하여도 검토 시점 뒤에 만든 기록 · 내 판단은 넣지 않음(나중 값 0건)."""
    ctx = _ctx(market, "2026-11-13")
    sessions = _sessions(
        tmp_path,
        [
            {
                "asof": "2026-11-13",
                "created": "2026-11-24T09:00:00+0900",
                "verdict": "useful",
                "items": [_item(1, "AAA001", 9.0, "2026-10-14", "2026-11-13")],
            },
            {
                "asof": "2026-11-10",
                "created": "2026-11-10T22:00:00+0900",
                "items": [_item(2, "AAA001", 8.0, "2026-10-10", "2026-11-10")],
            },
        ],
    )
    reviews = [
        {
            "ticker": "AAA001",
            "end": "2026-11-13",
            "saved_at": "2026-11-20T10:00:00+09:00",
            "verdict": "continue",
            "reason": "",
            "filters": FILTERS,
        },
    ]
    cut = H.cutoff_of("2026-11-13", ctx.end, datetime(2026, 11, 25, 9, 0, tzinfo=KST))
    assert cut == datetime(2026, 11, 14, 0, 0, tzinfo=KST)
    rv = E.compose(ctx, "AAA001", sessions=sessions, reviews=reviews, cutoff=cut)
    assert (
        rv["previous"]["kind"] == "session" and rv["previous"]["asof"] == "2026-11-10"
    )
    assert rv["sessions"]["late"] == 2
    assert "쓸 만함" not in rv["copy"] and "내 판단 기록" not in rv["copy"]
    live = H.cutoff_of(None, ctx.end, datetime(2026, 11, 25, 9, 0, tzinfo=KST))
    assert live == datetime(2026, 11, 25, 9, 0, tzinfo=KST)
    rv2 = E.compose(ctx, "AAA001", sessions=sessions, reviews=reviews, cutoff=live)
    assert rv2["previous"]["kind"] == "review" and rv2["sessions"]["late"] == 0
    assert H.known("2026-11-13T23:59:00", cut) and not H.known("bad", cut)


def test_after_move_intraday_on_end_is_not_yet(market: Path) -> None:
    """검토 5 — 다음 주 마감일이 끝일인데 그날 값이 장중 저장이면 '기간 미경과'(자료 없음 아님 · 관측 표시 없음)."""
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET fetched_at='2026-11-20T02:00:00+00:00' "
            "WHERE ticker='AAA001' AND date='2026-11-20'"
        )
    ctx = _ctx(market, "2026-11-20")
    assert ctx.rows[-1] == "2026-11-13"
    a = OB.after_move(ctx, "AAA001", "2026-11-13")
    sofar = a.pop("sofar")
    assert a == {
        "state": "not_yet",
        "from": "2026-11-13",
        "to": "2026-11-20",
        "intraday": True,
    }
    # 이번 주 지금까지 = 11/20 은 이 ETF 가 장중 저장값 → 공통 마감 종가 마지막 날 11/19
    assert sofar["end"] == "2026-11-19" and sofar["why"] is None
    a["sofar"] = sofar
    html = re.sub(r"<[^>]+>", "", PG._after_html(a))
    assert (
        "11/20(금) 마감 종가 아직 없음(장중 저장값)" in html
        and "11/13 → 11/19(목)" in html
    )
    assert (
        "주 진행 중 11/20(금) 마감 종가 아직 없음(장중 저장값)" in html
    )  # V2 — 장중이어도 주 진행 중
    assert L.after_plain({"after": a}).endswith(
        "(주 진행 중 · 11/20 마감 종가 아직 없음(장중 저장값))"
    )
    part = {
        "state": "ok",
        "from": "a",
        "to": "b",
        "etf": {"value": None, "why": "no_price"},
        "kodex": {"value": 1.0, "why": None},
    }
    row = {
        "date": "2026-11-13",
        "seen": {"state": "out", "why": "no_price"},
        "records": {"count": 0, "mine": []},
        "reviews": [],
        "after": part,
    }
    assert "관측" not in PG._row_html(row, [])


def test_composition_states_and_other_date() -> None:
    """검토 6 — 읽기 실패 · 원천 범위 · 다른 기준일 구성은 실제 상태대로."""
    item = {"ticker": "T", "rank": 1, "one_month": {"start": "2026-10-26", "end": END}}
    err = E.composition(
        lambda t, c: {"constituents": {"state": "error", "rows": []}}, item, FILTERS
    )
    assert err == {"state": "error"} and "읽지 못했습니다" in PG._composition_detail(
        err
    )

    def reader(t, c):
        return {
            "constituents": {
                "state": "full",
                "asof": "2026-11-16",
                "rows": [{"name": "A", "weight_pct": 100.0}],
            },
            "exposure": {
                "status": "ok",
                "stocks": [
                    {
                        "name": "A",
                        "exposure": {"terms": [], "direct": []},
                        "reference": [{"x": 1}],
                    },
                    {"name": "B", "exposure": "깨짐"},
                ],
            },
        }

    c = E.composition(reader, item, FILTERS)
    assert c["coverage"] == "full" and c["overlap"] == {
        "checked": 2,
        "hits": [],
        "other_date": ["A"],
    }
    text = PG._composition_detail(c)
    assert "원천 전체 구성" in text and "남은 구성은 미확인" not in text
    assert (
        "기준일이 다른 구성에서만 겹치는 주식 1종목은 중복으로 세지 않았습니다" in text
    )


@pytest.mark.parametrize(
    "mine,peer,opposite,tail",
    [
        (0.001, 0.4, False, "변동 방향이 같지 않았습니다(0.00% 포함)"),
        (0.001, -0.001, False, "가격 변동이 거의 없었습니다(0.00%)"),
        (5.0, -2.0, True, "방향이 엇갈렸습니다"),
        (5.0, 2.0, False, "원화 가격이 함께 올랐습니다"),
        (-5.0, -2.0, False, "원화 가격이 함께 내렸습니다"),
    ],
)
def test_peer_direction_uses_real_opposite(mine, peer, opposite, tail) -> None:
    """검토 7 — 0.00% 는 반대 방향이 아님 · '도 · 함께'는 모두 같은 방향일 때만."""
    rv = _rv(v=mine)
    rv["peer"]["same"][0]["one_month"]["value"] = peer
    assert bool(E._opposite(rv)) is opposite
    t = L.peer_text(rv)
    assert t.endswith(tail + ".")
    assert ("도 같은 기간" in t) is tail.startswith("원화 가격이 함께")
    assert E._ask(rv)["kind"] == ("peer_gap" if opposite else "local_index")


def test_exclusion_end_checked_before_start(market: Path) -> None:
    """끝일 · 시작일 가격이 둘 다 없으면 build 와 같이 end_differs(판정 순서 뒤집기 변이)."""
    end = "2026-11-23"
    with sqlite3.connect(market) as con:
        con.executemany(
            "INSERT INTO etf_master(ticker, name, category, price, volume, market_cap, source,"
            " last_seen_at) VALUES (?,?,NULL,NULL,NULL,NULL,'test','2026-11-10T00:00:00Z')",
            [
                ("GAP001", "차 끝없음"),
                ("GAP002", "카 시작없음"),
                ("GAP003", "타 둘다없음"),
            ],
        )
    for tk in ("GAP001", "GAP002", "GAP003"):
        _put(market, tk, _line(90, 100.0, 105.0))
    ctx0 = _ctx(market)
    s, e = ctx0.build["windows"]["one_month"]
    assert e == end
    with sqlite3.connect(market) as con:
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker IN ('GAP001','GAP003') AND date=?",
            (e,),
        )
        con.execute(
            "DELETE FROM etf_daily_price WHERE ticker IN ('GAP002','GAP003') AND date=?",
            (s,),
        )
    ctx = _ctx(market)
    b = ctx.build
    common = b["windows"]["one_month"]
    got = {
        t: H.exclusion(ctx.market, t, FILTERS, common)
        for t in ("GAP001", "GAP002", "GAP003")
    }
    assert got == {
        "GAP001": "end_differs",
        "GAP002": "start_differs",
        "GAP003": "end_differs",
    }
    before = ctx0.build["counts"]
    assert b["counts"]["end_differs"] - before["end_differs"] == 2
    assert b["counts"]["start_differs"] - before["start_differs"] == 1


def test_comparable_needs_rank_value_and_dates() -> None:
    full = {"rank": 3, "one_month": 1.0, "start": "2026-10-19", "end": "2026-11-16"}
    assert H.comparable(full)
    for k in ("rank", "one_month", "start", "end"):
        assert not H.comparable({**full, k: None}), k
    assert not H.comparable(None)


@pytest.mark.parametrize(
    "word,want",
    [
        ("KRX 19", "는"),
        ("KRX 12", "는"),
        ("KRX 14", "는"),
        ("KRX 15", "는"),
        ("KRX 11", "은"),
    ],
)
def test_topic_particle_digits(word: str, want: str) -> None:
    assert L.topic(word) == want


# --- 검증자 r1 정정(2026-11-25) — 검토 시점 경계 · 대조 기간 ---


def test_review_time_boundary_is_exclusive(market: Path, tmp_path: Path) -> None:
    """F1 — 끝일 다음 날 0시 정각에 만든 기록은 그 끝일 검토에 넣지 않는다(직전 초는 넣음)."""
    ctx = _ctx(market, "2026-11-13")
    cut = H.cutoff_of("2026-11-13", ctx.end, datetime(2026, 11, 25, 9, 0, tzinfo=KST))
    sessions = _sessions(
        tmp_path,
        [
            {
                "id": "at_midnight",
                "asof": "2026-11-13",
                "created": "2026-11-14T00:00:00+0900",
                "items": [_item(1, "AAA001", 9.0, "2026-10-14", "2026-11-13")],
            },
            {
                "id": "just_before",
                "asof": "2026-11-12",
                "created": "2026-11-13T23:59:59+0900",
                "items": [_item(2, "AAA001", 8.0, "2026-10-13", "2026-11-12")],
            },
            {
                "id": "other_etf_late",
                "asof": "2026-11-13",
                "created": "2026-11-20T10:00:00+0900",
                "items": [_item(1, "DOM001", 5.0, "2026-10-14", "2026-11-13")],
            },
        ],
    )
    other_review = {
        "ticker": "DOM001",
        "end": "2026-11-13",
        "saved_at": "2026-11-20T10:00:00+09:00",
        "verdict": "hold",
        "reason": "",
        "filters": FILTERS,
    }
    rv = E.compose(ctx, "AAA001", sessions=sessions, reviews=[other_review], cutoff=cut)
    assert rv["previous"]["kind"] == "session"
    assert rv["previous"]["record_id"] == "just_before"
    # 반박 L1 — 뺀 수는 이 ETF 가 들어 있는 기록 · 이 ETF 판단만(다른 ETF 기록 · 판단은 세지 않음)
    assert rv["sessions"]["late"] == 1
    assert "이후에 만든 이 ETF 기록 · 내 판단 1건은 넣지 않았습니다" in PG.weeks_html(
        rv
    )
    assert not H.known("2026-11-14T00:00:00+09:00", cut)
    assert not H.known("2026-11-13T15:00:00Z", cut)  # = 11/14 00:00 KST
    assert H.known("2026-11-13T23:59:59+09:00", cut)


def test_reconcile_needs_same_period(
    market: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3 — 순위 · 값이 같아도 비교 기간(시작일 · 끝일)이 다르면 '일치'가 아니다(값 대조 안 함)."""
    ctx = _ctx(market)
    seen = H.seen_at(ctx.restore("2026-11-16"), "AAA001")
    v = round(seen["one_month"]["value"], 4)
    s, e = seen["one_month"]["start"], seen["one_month"]["end"]
    sessions = _sessions(
        tmp_path,
        [
            {
                "id": "start_differs",
                "asof": "2026-11-16",
                "items": [_item(seen["rank"], "AAA001", v, "2026-10-01", e)],
            },
        ],
    )
    rec = sessions["records"][0]
    got = H.reconcile(ctx, rec, rec["items"][0])
    assert got["state"] == "period_differs"
    assert (got["restored"]["start"], got["stored"]["start"]) == (s, "2026-10-01")
    text = PG.check_text(got)
    assert "비교 기간이 달라 값을 맞춰 보지 않음" in text and "같습니다" not in text
    # 끝일만 다름 — 복원 날짜가 기록 끝일이라 실제로는 드물어 복원 결과를 바꿔 끼워 분기만 확인
    shifted = {**seen, "one_month": {**seen["one_month"], "end": "2026-11-13"}}
    monkeypatch.setattr(H, "seen_at", lambda rs, tk: shifted)
    same_start = {**rec["items"][0], "start": s}
    assert H.reconcile(ctx, rec, same_start)["state"] == "period_differs"
    monkeypatch.setattr(H, "seen_at", lambda rs, tk: seen)
    assert H.reconcile(ctx, rec, same_start)["state"] == "match"
    monkeypatch.undo()
    # 화면의 '복원 · 대조 근거'에도 '같습니다'로 나오지 않는다
    rv = E.compose(ctx, "AAA001", sessions=sessions, reviews=[])
    weeks = PG.weeks_html(rv)
    assert "비교 기간이 달라 값을 맞춰 보지 않음" in weeks
    assert "그날 저장값과 같습니다" not in weeks
    with pytest.raises(ValueError):
        PG.check_text({"state": "weird", "date": "2026-11-16"})


# --- 형수님 실사용 의견(2026-11-25) — 긴 세부는 팝업 · 목록으로 줄 나눔 ---


def test_long_details_are_split_into_lines(market: Path, tmp_path: Path) -> None:
    """저장 기록 자세히 = [자세히] 팝업(항목별 줄) · '이 표의 값은 어떻게 구했나' · 같은 지수 상품 = 목록."""
    ctx = _ctx(market)
    sessions = _sessions(tmp_path, _records_for_copy())
    rv = E.compose(ctx, "AAA001", sessions=sessions, reviews=[], reader=FakeReader())
    weeks = PG.weeks_html(rv)
    assert weeks.count('<dialog class="pop">') >= 1 and "showModal()" in weeks
    start = weeks.index('<dialog class="pop">')
    pop = weeks[start : weeks.index("</dialog>", start)]  # noqa: E203
    for label in ("순위 · 1개월", "사용자 판단", "저장한 곳", "메모(이 화면에서만)"):
        assert f"<dt>{label}</dt>" in pop
    assert (
        "복원 · 대조 근거" not in weeks
        and "<summary>이 표의 값은 어떻게 구했나</summary>" in weeks
    )
    start = weeks.index("이 표의 값은 어떻게 구했나")
    basis = weeks[start : weeks.index("</ul>", start)]  # noqa: E203
    assert basis.count("<li>") >= 3 and "현재 ETF 목록과 저장 가격으로 복원" in basis
    peer = PG._peers_detail(rv["peer"])
    assert peer.count("<li>") == len(rv["peer"]["other"]) >= 1
    assert " / " not in peer  # 상품을 한 줄에 잇지 않음
    comp = PG._composition_detail(rv["composition"])
    assert comp.count("<li>") >= 2
