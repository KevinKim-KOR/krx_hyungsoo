"""POC5-01B — 원장 item · disposition · 전이 · 시장 태그(실제 결과 객체 · 임시 원장).

```text
disposition  PLAN §1-3 표(우선순위 위 → 아래 · 새 값 0) — sent = 조립된 본문에 실림
전이         직전 평가(원장 자기 행 · 예정 회차 · 자료없음 제외) 대비 — 첫 활성 new_entry ·
             반복 repeat_exposure · 강해짐 worsened · 같은 계열 약화 repeat · 비활성 뒤 재진입
             reentry_after_recovery · 비교 불가(급락↔급등 · 사업군 state 변경) new_entry
노출         같은 KST 날짜 · subject · state 는 예정 회차 첫 노출만 PRIMARY(Q29 · Q-D)
태그         same_us_session(원장 직전 시장 run) · after_kr_market_closure(한국 평일 휴장)
```
"""

from __future__ import annotations

import json

from app.market_briefing import evidence as ev
from app.market_briefing.flow import BriefingOutcome
from app.runtime_evidence.holdings_risk import RiskTicker
from app.runtime_evidence.holdings_risk_flow import HoldingsRiskOutcome, RiskAssembly
from app.runtime_evidence.holdings_risk_state import RiskChangeSet
from app.runtime_evidence.holdings_selection import SelectedTicker
from app.runtime_evidence.holdings_selection_flow import HoldingsSelectionOutcome
from app.runtime_evidence.holdings_selection_state import ChangeSet
from app.runtime_evidence.intraday_alert_flow import IntradayAssembly
from app.runtime_evidence.intraday_alert_render import SectionPlan
from app.runtime_evidence.sector_signal import SectorOutcome, SectorSignal
from app.runtime_evidence.sector_signal_state import SectorChangeSet
from app.three_push_runtime import ledger_context as lc
from app.three_push_runtime import ledger_items as li
from app.three_push_runtime import ledger_market as lm
from app.three_push_runtime import ledger_store as ls


class _Q:
    def __init__(self, cur, asof="2026-10-07T10:30:00+09:00"):
        self.current_price, self.price_asof = cur, asof


def _by_subject(items):
    return {i["subject_id"]: i for i in items}


# ── 보유 브리핑 ──────────────────────────────────────────────────────────────


def _obs(ticker, state=None, cause=None, ret=None):
    return {
        "ticker": ticker,
        "current": 90.0,
        "quote_asof": "2026-10-07T09:14:00+09:00",
        "base_close": 100.0,
        "base_day": "2026-09-08",
        "return_pct": ret,
        "state": state,
        "profit_loss_pct": 3.0,
        "cause": cause,
    }


def _sel(ticker, state="D8_10"):
    return SelectedTicker(
        ticker=ticker,
        name=ticker,
        account_count=1,
        reasons={"RECENT_DECLINE": {"state": state, "value": -9.0}},
    )


def test_briefing_full_body_marks_selected_sent_and_others_by_cause():
    out = HoldingsSelectionOutcome(
        message_text="본문",
        selected=[_sel("A")],
        changes=ChangeSet(full_send=True),
        observations=[
            _obs("A", "D8_10", ret=-9.0),
            _obs("B", ret=-1.0),
            _obs("C", cause="base_close"),
            _obs("E", cause="current_price"),
        ],
    )
    got = _by_subject(li.holdings_briefing_items(out))
    # 버린 현재가는 t0 로 남기지 않는다 · 자료없음 = 평가 불가.
    assert got["E"]["t0_price"] is None and got["E"]["evaluable"] is False
    assert got["C"]["t0_price"] == 90.0 and got["C"]["evaluable"] is False
    assert got["A"]["disposition"] == li.SENT and got["A"]["state"] == "D8_10"
    assert got["B"]["disposition"] == li.NOT_SELECTED and got["B"]["state"] is None
    assert got["C"]["disposition"] == li.DATA_UNAVAILABLE
    assert got["C"]["values"]["unavailable_cause"] == "base_close"
    assert got["A"]["t0_price"] == 90.0 and got["A"]["held"] == 1
    assert "avg_buy_price" not in json.dumps(got["A"]["values"])


def test_select_holdings_observes_every_evaluated_ticker():
    """L13 — 비선정 종목도 관측에 들어가 원장 not_selected 행이 된다(실제 함수)."""
    from datetime import date, timedelta

    from app.runtime_evidence.holdings_selection import select_holdings

    today = "2026-10-07"
    d, axis = date.fromisoformat(today), []
    while len(axis) < 25:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            axis.append(d.isoformat())
    axis.sort()
    asof = f"{today}T10:00:00+09:00"
    obs: list = []
    selected = select_holdings(
        holdings=[{"ticker": "AAA", "name": "A"}, {"ticker": "BBB", "name": "B"}],
        price_history={t: [(x, 100.0) for x in axis] for t in ("AAA", "BBB")},
        market_quotes={"AAA": _Q(85.0, asof), "BBB": _Q(100.0, asof)},
        today_kst=today,
        axis_dates=axis,
        observations=obs,
    )
    assert [s.ticker for s in selected] == ["AAA"]
    assert [(o["ticker"], o["state"]) for o in obs] == [
        ("AAA", "D10_PLUS"),
        ("BBB", None),
    ]
    out = HoldingsSelectionOutcome(
        message_text="본문",
        selected=selected,
        changes=ChangeSet(full_send=True),
        observations=obs,
    )
    got = _by_subject(li.holdings_briefing_items(out))
    assert (
        got["BBB"]["disposition"] == li.NOT_SELECTED and got["BBB"]["t0_price"] == 100.0
    )


def test_briefing_change_body_suppresses_unchanged_selected():
    a, b = _sel("A"), _sel("B", "D5_8")
    out = HoldingsSelectionOutcome(
        message_text="변화분",
        selected=[a, b],
        changes=ChangeSet(new=[a]),
        observations=[_obs("A", "D8_10"), _obs("B", "D5_8")],
    )
    got = _by_subject(li.holdings_briefing_items(out))
    assert got["A"]["disposition"] == li.SENT
    assert got["B"]["disposition"] == li.SUPPRESSED


# ── 장중 ────────────────────────────────────────────────────────────────────


def _ev(ticker, ret, state=None, unavailable=False):
    return {
        "ticker": ticker,
        "current": 100.0,
        "price_asof": "2026-10-07T10:30:00+09:00",
        "day_return": None if unavailable else ret,
        "state": state,
        "unavailable": unavailable,
    }


def _rt(ticker, state):
    return RiskTicker(ticker=ticker, name=ticker, account_count=1, state=state)


def test_risk_old_body_marks_new_sent_suppressed_and_unavailable():
    a, b = _rt("A", "D7_10"), _rt("B", "D5_7")
    outcome = HoldingsRiskOutcome(
        selected=[a, b],
        changes=RiskChangeSet(new=[a], suppressed=["B"]),
        message_text="[보유 급락 알림]",
        evaluated=[
            _ev("A", -8, "D7_10"),
            _ev("B", -6, "D5_7"),
            _ev("C", 0.3),
            _ev("D", 0, unavailable=True),
        ],
    )
    got = _by_subject(
        li.risk_items(RiskAssembly(outcome=outcome), intraday_isolated=False)
    )
    assert [got[t]["disposition"] for t in "ABCD"] == [
        li.SENT,
        li.SUPPRESSED,
        li.NOT_SELECTED,
        li.DATA_UNAVAILABLE,
    ]
    assert got["D"]["t0_price"] is None and got["D"]["evaluable"] is False
    assert got["A"]["t0_price"] == 100.0


def _intraday(**over):
    a = IntradayAssembly()
    for k, v in over.items():
        setattr(a, k, v)
    return a


def test_risk_daily_cap_cuts_items_that_would_have_been_sent():
    a = _rt("A", "D7_10")
    surge = SectorSignal(
        sector_key="보유", ticker="S", name="S", state="U5_7", day_return_pct=6.0
    )
    sig = SectorSignal(
        sector_key="S1", ticker="T1", name="T1", state="AVOID_DROP", day_return_pct=-3.0
    )
    intraday = _intraday(
        daily_cap_reached=True,
        observed=[sig, surge],
        surge_changes=SectorChangeSet(send=[surge]),
        changes=SectorChangeSet(send=[sig]),
        sector=SectorOutcome(
            evaluated=[("S1", "T1", False, -3.0, None, None, 1, "AVOID_DROP")],
            quotes={"T1": _Q(9700.0)},
        ),
    )
    outcome = HoldingsRiskOutcome(
        selected=[a],
        changes=RiskChangeSet(new=[a]),
        message_text="[보유 급락 알림]",  # 구 본문은 남지만 상한 회차는 보내지 않는다
        evaluated=[_ev("A", -8, "D7_10"), _ev("S", 6.0)],
    )
    ra = RiskAssembly(outcome=outcome, intraday_eval=intraday)
    got = _by_subject(li.risk_items(ra, intraday_isolated=False))
    assert got["A"]["disposition"] == li.CUT_DAILY
    assert got["S"]["disposition"] == li.CUT_DAILY and got["S"]["state"] == "U5_7"
    assert got["S1"]["disposition"] == li.CUT_DAILY
    assert got["S1"]["t0_price"] == 9700.0  # 병합된 시세 참조에서(대체 ETF 포함)


def test_risk_plan_section_cap_and_sector_reasons():
    a, b = _rt("A", "D10_PLUS"), _rt("B", "D5_7")
    s1 = SectorSignal(
        sector_key="S1", ticker="T1", name="T1", state="AVOID_DROP", day_return_pct=-3.0
    )
    s2 = SectorSignal(
        sector_key="S2", ticker="T2", name="T2", state="AVOID_DROP", day_return_pct=-2.0
    )
    plan = SectionPlan(
        held_drop=[a],
        avoid_drop=[s1],
        dropped=[
            {
                "section": "held",
                "ticker": "B",
                "state": "D5_7",
                "reason": "section_cap",
            },
            {
                "section": "avoid",
                "ticker": "T2",
                "state": "AVOID_DROP",
                "reason": "section_cap",
            },
        ],
    )
    intraday = _intraday(
        message_text="[장중 급등락]",
        plan=plan,
        changes=SectorChangeSet(send=[s1, s2]),
        sector=SectorOutcome(
            evaluated=[
                ("S1", "T1", False, -3.0, -1.0, -2.0, 1, "AVOID_DROP"),
                ("S2", "T2", True, -2.0, None, None, 2, "AVOID_DROP"),
                ("S3", "T3", False, 1.0, None, None, 3, "ENTRY_REVIEW"),
                ("S4", "T4", False, 2.0, None, None, 4, None),
                ("S5", "T5", False, 0.1, None, None, 5, None),
            ],
            excluded=[
                {"sector_key": "S3", "ticker": "T3", "reason": "held"},
                {"sector_key": "S4", "ticker": "T4", "reason": "trend_not_t1"},
                {"sector_key": "S6", "ticker": "T6", "reason": "no_quote"},
            ],
        ),
    )
    outcome = HoldingsRiskOutcome(
        selected=[a, b],
        changes=RiskChangeSet(new=[a, b]),
        message_text="[보유 급락 알림]",
        evaluated=[_ev("A", -11, "D10_PLUS"), _ev("B", -6, "D5_7")],
        holding_rows=[
            {"ticker": "A"},
            {"ticker": "B"},
            {"ticker": "T3"},
            {"ticker": "T5"},
        ],
    )
    got = _by_subject(
        li.risk_items(
            RiskAssembly(outcome=outcome, intraday_eval=intraday),
            intraday_isolated=False,
        )
    )
    assert got["A"]["disposition"] == li.SENT
    assert got["B"]["disposition"] == li.CUT_SECTION
    assert got["S1"]["disposition"] == li.SENT
    assert (
        got["S2"]["disposition"] == li.CUT_SECTION
        and got["S2"]["values"]["used_alternate"]
    )
    assert got["S3"]["disposition"] == li.NOT_SELECTED and got["S3"]["held"] == 1
    assert got["S3"]["state"] == "ENTRY_REVIEW"  # 계산된 state 는 남긴다
    assert got["S3"]["evaluable"] is False  # 보유 제외 = 평가 불가(코드 UNEVALUABLE)
    assert (
        got["S5"]["held"] == 1 and got["S5"]["evaluable"] is True
    )  # 신호 없는 보유 대표
    assert got["S4"]["disposition"] == li.DATA_UNAVAILABLE
    assert got["S5"]["disposition"] == li.NOT_SELECTED
    assert got["S6"]["disposition"] == li.DATA_UNAVAILABLE


def test_risk_isolated_intraday_records_only_held_drop_and_block_rows():
    a = _rt("A", "D7_10")
    outcome = HoldingsRiskOutcome(
        selected=[a],
        changes=RiskChangeSet(new=[a]),
        message_text="[보유 급락 알림]",
        evaluated=[_ev("A", -8, "D7_10")],
    )
    ra = RiskAssembly(outcome=outcome, intraday_eval=_intraday(message_text="x"))
    items = li.risk_items(ra, intraday_isolated=True)
    assert [i["subject_id"] for i in items] == ["A"] and items[0][
        "disposition"
    ] == li.SENT

    blocked = _intraday(
        sector_error="RuntimeError: x",
        sector=SectorOutcome(),
    )
    items = li.risk_items(
        RiskAssembly(outcome=outcome, intraday_eval=blocked), intraday_isolated=False
    )
    block = [i for i in items if i["subject_kind"] == "sector_block"]
    assert block and block[0]["disposition"] == li.DATA_UNAVAILABLE
    assert block[0]["state"] == "sector_error"
    assert block[0]["evaluable"] is False  # 구역 장애 = 평가 불가


# ── 시장 ────────────────────────────────────────────────────────────────────


def _cand(name, tickers=("T1", "T2")):
    return ev.IndexCandidate(
        agency="A",
        name=name,
        ret_5d_pct=1.0,
        ret_20d_pct=2.0,
        ticker_count=2,
        tickers=tickers,
    )


def test_market_items_outlook_candidates_and_index_states():
    out = BriefingOutcome(
        message_text="본문",
        outlook=ev.Outlook(state="UP", sp500_return_pct=0.5, sp500_asof="2026-10-06"),
        index=ev.IndexLeadership(
            status="ok", candidates=[_cand("X"), _cand("Y")], price_asof="2026-10-06"
        ),
    )
    items = lm.market_items(out, {"sp500_asof": "2026-10-06"})
    assert items[0]["state"] == "UP" and items[0]["disposition"] == li.SENT
    groups = [i for i in items if i["subject_kind"] == "index_group"]
    assert [g["subject_id"] for g in groups] == ["A|X", "A|Y"]
    assert (
        groups[0]["values"]["tickers"] == ["T1", "T2"]
        and groups[0]["disposition"] == li.SENT
    )

    none = BriefingOutcome(
        message_text="",
        outlook=ev.Outlook(state="NONE"),
        index=ev.IndexLeadership(status="no_candidate_normal"),
    )
    got = lm.market_items(none, {})
    assert got[0]["disposition"] == li.DATA_UNAVAILABLE
    assert got[0]["evaluable"] is False  # 미국 입력 없음 = 평가 불가
    assert got[1]["evaluable"] is True  # 정상 평가 · 후보 0
    assert items[0]["evaluable"] is True
    assert (
        got[1]["subject_kind"] == "index_block"
        and got[1]["disposition"] == li.NOT_SELECTED
    )

    stale = BriefingOutcome(
        outlook=ev.Outlook(state="NONE"), index=ev.IndexLeadership(status="stale")
    )
    stale_items = lm.market_items(stale, {})
    assert stale_items[1]["disposition"] == li.DATA_UNAVAILABLE
    assert stale_items[1]["evaluable"] is False  # 구역 장애 = 평가 불가
    assert lm.market_items(BriefingOutcome(), {}) == []  # 비거래일 — 평가 전 종료


# ── 전이 · 노출 · 태그 (임시 원장) ──────────────────────────────────────────────


def _persist(kind, raw, *, eid, day="2026-10-07", hhmm="10:30", off=0):
    con = ls.connect()
    try:
        ls.insert_started(
            con,
            {
                "event_id": eid,
                "push_kind": kind,
                "runtime_date_kst": day,
                "started_at": f"{day}T{hhmm}:00+09:00",
                "off_schedule": off,
            },
        )
        ls.finalize(
            con,
            eid,
            {"status": "sent"},
            lambda c: li.apply_transitions(
                c, raw, push_kind=kind, runtime_date_kst=day
            ),
            {"delivery_status": "sent"},
        )
        return con.execute(
            "SELECT subject_id, state, prev_state, event_type, exposure FROM signal_item"
            " WHERE event_id = ? ORDER BY item_seq",
            (eid,),
        ).fetchall()
    finally:
        con.close()


def _risk(ticker, state, disposition=li.SENT, **over):
    item = li.make_item(
        "ticker",
        ticker,
        state=state,
        disposition=disposition,
        values={},
        held=1,
        axis=li.AXIS_RISK,
        evaluable=disposition != li.DATA_UNAVAILABLE,
    )
    item.update(over)
    return item


def test_risk_transitions_and_same_day_primary_once():
    K = "holdings_risk_alert"
    steps = [
        ("10:30", "D5_7", li.SENT, ("new_entry", "PRIMARY")),
        ("11:30", "D5_7", li.SUPPRESSED, ("repeat_exposure", "SECONDARY")),
        ("12:30", "D10_PLUS", li.SENT, ("worsened", "PRIMARY")),
        (
            "13:30",
            "D7_10",
            li.SUPPRESSED,
            ("repeat_exposure", "SECONDARY"),
        ),  # 같은 계열 약화
        ("14:30", None, li.NOT_SELECTED, (None, None)),  # 회복 관측
        # 회복 뒤 재진입 — 그날 D5_7 이 이미 PRIMARY 였으므로 노출은 SECONDARY(Q29).
        ("15:20", "D5_7", li.SENT, ("reentry_after_recovery", "SECONDARY")),
    ]
    for n, (hhmm, state, disp, want) in enumerate(steps):
        row = _persist(K, [_risk("A", state, disp)], eid=f"ev_{n:04d}", hhmm=hhmm)[0]
        assert (row[3], row[4]) == want, (hhmm, row)
    # 급락 → 급등 = 비교 불가 → new_entry.
    row = _persist(
        K, [_risk("A", "U5_7")], eid="ev_0100", day="2026-10-08", hhmm="09:30"
    )[0]
    assert (row[2], row[3], row[4]) == ("D5_7", "new_entry", "PRIMARY")
    # 다음 날 같은 state 반복 = repeat(SECONDARY) · 자료없음은 직전 평가에서 뺀다.
    _persist(
        K,
        [_risk("A", None, li.DATA_UNAVAILABLE)],
        eid="ev_0101",
        day="2026-10-09",
        hhmm="09:30",
    )
    row = _persist(
        K, [_risk("A", "U5_7")], eid="ev_0102", day="2026-10-09", hhmm="10:30"
    )[0]
    assert (row[2], row[3], row[4]) == ("U5_7", "repeat_exposure", "SECONDARY")
    row = _persist(
        K, [_risk("A", "U7_10")], eid="ev_0103", day="2026-10-09", hhmm="11:30"
    )[0]
    assert (row[3], row[4]) == ("worsened", "PRIMARY")


def test_off_schedule_runs_are_not_previous_evaluation():
    K = "holdings_risk_alert"
    _persist(K, [_risk("A", "D5_7")], eid="ev_0001", hhmm="10:30")
    _persist(K, [_risk("A", "D10_PLUS")], eid="ev_0002", hhmm="21:54", off=1)
    row = _persist(
        K, [_risk("A", "D7_10")], eid="ev_0003", day="2026-10-08", hhmm="09:30"
    )[0]
    assert (row[2], row[3]) == ("D5_7", "worsened")


def test_sector_state_change_is_incomparable_new_entry_and_briefing_bands_order():
    K = "holdings_risk_alert"
    sec = lambda st: li.make_item(  # noqa: E731
        "sector",
        "S1",
        state=st,
        disposition=li.SENT,
        values={},
        held=0,
        axis=li.AXIS_SECTOR,
    )
    _persist(K, [sec("AVOID_DROP")], eid="ev_0001")
    row = _persist(K, [sec("ENTRY_REVIEW")], eid="ev_0002", hhmm="11:30")[0]
    assert (row[2], row[3], row[4]) == ("AVOID_DROP", "new_entry", "PRIMARY")

    B = "holdings_briefing"
    brf = lambda st: li.make_item(  # noqa: E731
        "ticker",
        "Z",
        state=st,
        disposition=li.SENT,
        values={},
        held=1,
        axis=li.AXIS_BRIEFING,
    )
    assert _persist(B, [brf("D5_8")], eid="ev_0010", hhmm="09:15")[0][3] == "new_entry"
    row = _persist(B, [brf("D8_10")], eid="ev_0011", hhmm="12:30")[0]
    assert (row[3], row[4]) == ("worsened", "PRIMARY")


def test_market_tags_same_us_session_and_after_kr_closure(tmp_path):
    cal = tmp_path / "cal"
    cal.mkdir()
    # 10-06(화)을 휴장으로 둔 합성 캘린더 — 기대 T-1 = 10-05 · 사이에 평일 휴장 1일.
    days = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-07", "2026-10-08"]
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", "utf-8"
    )
    sp = li.make_item(
        "market",
        lm.SP500_SUBJECT,
        state="UP",
        disposition=li.SENT,
        values={"sp500_asof": "2026-10-05"},
    )
    _persist("market_briefing", [sp], eid="ev_0001", day="2026-10-06", hhmm="08:30")
    con = ls.connect()
    try:
        rec = {
            "sp500_asof": "2026-10-05",
            "sp500_session_check": {"reason": "ok"},
            "index_status": "ok",
            "batch_failure_notice": {"reasons": []},
        }
        tags = lm.market_tags(
            con, rec, [sp], runtime_date_kst="2026-10-07", calendar_dir=cal
        )
        later = lm.market_tags(
            con,
            dict(
                rec,
                sp500_asof="2026-10-06",
                sp500_session_check={"reason": "last_session_not_expected"},
            ),
            [sp],
            runtime_date_kst="2026-10-08",
            calendar_dir=cal,
        )
    finally:
        con.close()
    assert tags["same_us_session"] is True and tags["after_kr_market_closure"] is True
    assert tags["input_delay"] is False and tags["flat_or_none"] is False
    assert (
        later["same_us_session"] is False and later["after_kr_market_closure"] is False
    )
    assert later["input_delay"] is True


def test_same_us_session_unknown_when_previous_asof_missing():
    """직전 시장 run 의 미국 기준일을 모르면 '같은 세션' 을 판정하지 않는다(모름 = None)."""
    sp = li.make_item(
        "market",
        lm.SP500_SUBJECT,
        state="NONE",
        disposition=li.DATA_UNAVAILABLE,
        values={"sp500_asof": None},
        evaluable=False,
    )
    _persist("market_briefing", [sp], eid="ev_0001", day="2026-10-06", hhmm="08:30")
    con = ls.connect()
    try:
        tags = lm.market_tags(
            con,
            {"sp500_asof": "2026-10-06"},
            [sp],
            runtime_date_kst="2026-10-07",
            calendar_dir=None,
        )
    finally:
        con.close()
    assert tags["same_us_session"] is None


def test_held_sector_rows_get_no_transition_and_are_not_previous():
    """logic-1 — 보유로 제외된 사업군은 전이가 없고 직전 평가로 쓰지 않는다(매도 뒤 첫 실림 = new_entry)."""
    K = "holdings_risk_alert"

    def sec(state, disposition, evaluable=True):
        return li.make_item(
            "sector",
            "S3",
            state=state,
            disposition=disposition,
            values={},
            held=1,
            axis=li.AXIS_SECTOR,
            evaluable=evaluable,
        )

    row = _persist(
        K, [sec("AVOID_DROP", li.NOT_SELECTED, evaluable=False)], eid="ev_0001"
    )[0]
    assert (row[3], row[4]) == (None, None)
    _persist(K, [sec(None, li.NOT_SELECTED)], eid="ev_0002", hhmm="11:30")
    _persist(
        K,
        [sec("AVOID_DROP", li.NOT_SELECTED, evaluable=False)],
        eid="ev_0003",
        hhmm="12:30",
    )
    row = _persist(K, [sec("AVOID_DROP", li.SENT)], eid="ev_0004", hhmm="13:30")[0]
    assert (row[3], row[4]) == ("new_entry", "PRIMARY")


def test_unevaluated_surge_run_is_not_recovery():
    """logic-2 — 급등을 평가하지 못한 회차(격리 · 정책 비활성)의 state None 은 회복이 아니다."""
    a = _rt("A", "D7_10")
    outcome = HoldingsRiskOutcome(
        selected=[a],
        changes=RiskChangeSet(new=[a]),
        message_text="[보유 급락 알림]",
        evaluated=[_ev("A", -8, "D7_10"), _ev("S", 6.0)],
    )
    items = _by_subject(
        li.risk_items(RiskAssembly(outcome=outcome), intraday_isolated=True)
    )
    assert items["S"]["evaluable"] is False and items["A"]["evaluable"] is True
    K = "holdings_risk_alert"
    _persist(K, [_risk("S", "U5_7")], eid="ev_0001")
    row = _persist(K, [items["S"]], eid="ev_0002", hhmm="11:30")[0]
    assert row[3] is None
    row = _persist(K, [_risk("S", "U5_7")], eid="ev_0003", hhmm="12:30")[0]
    assert (row[2], row[3], row[4]) == ("U5_7", "repeat_exposure", "SECONDARY")


def _surge_run(surge_error):
    """정책 활성 장중 회차 — 급등 선정이 예외면 `surge_error` 가 찬다(관측 급등 0)."""
    intraday = IntradayAssembly(
        diagnostics={"intraday_policy_enabled": True}, surge_error=surge_error
    )
    outcome = HoldingsRiskOutcome(
        message_text="",
        evaluated=[_ev("S", 6.0), _ev("D", -6.0, "D5_7")],
        holding_rows=[{"ticker": "S"}, {"ticker": "D"}],
    )
    return _by_subject(
        li.risk_items(
            RiskAssembly(outcome=outcome, intraday_eval=intraday),
            intraday_isolated=False,
        )
    )


def test_surge_selection_exception_run_is_unevaluable_not_recovery():
    """검증자 r1 A-1 — 전날 U5_7 → 다음 날 급등 선정 예외 → 같은 U5_7 은 회복 · 재진입이 아니다."""
    items = _surge_run("RuntimeError")
    assert items["S"]["state"] is None and items["S"]["evaluable"] is False
    assert items["D"]["state"] == "D5_7" and items["D"]["evaluable"] is True
    K = "holdings_risk_alert"
    _persist(K, [_risk("S", "U5_7")], eid="ev_0001", day="2026-10-06")
    row = _persist(K, [items["S"]], eid="ev_0002", day="2026-10-07", hhmm="09:30")[0]
    assert row[3] is None  # 전이 없음
    row = _persist(K, [_risk("S", "U5_7")], eid="ev_0003", day="2026-10-07")[0]
    assert (row[1], row[2], row[3], row[4]) == (
        "U5_7",
        "U5_7",
        "repeat_exposure",
        "SECONDARY",
    )


def test_surge_evaluated_none_is_recovery_then_reentry():
    """대조군 — 급등을 평가한 회차의 state None 은 비활성 관측이라 다음 U5_7 은 재진입이다."""
    items = _surge_run(None)
    assert items["S"]["state"] is None and items["S"]["evaluable"] is True
    K = "holdings_risk_alert"
    _persist(K, [_risk("S", "U5_7")], eid="ev_0001", day="2026-10-06")
    _persist(K, [items["S"]], eid="ev_0002", day="2026-10-07", hhmm="09:30")
    row = _persist(K, [_risk("S", "U5_7")], eid="ev_0003", day="2026-10-07")[0]
    assert (row[3], row[4]) == ("reentry_after_recovery", "PRIMARY")


def test_surge_unknown_none_is_unevaluable_after_drop_too():
    """급등 미평가 회차의 '상태 없음' 은 직전이 급락 계열이어도 평가 불가(급등 여부를 모른다)."""
    items = _surge_run("RuntimeError")
    K = "holdings_risk_alert"
    _persist(K, [_risk("S", "D5_7")], eid="ev_0001", day="2026-10-06")
    _persist(K, [items["S"]], eid="ev_0002", day="2026-10-07", hhmm="09:30")
    row = _persist(K, [_risk("S", "D5_7")], eid="ev_0003", day="2026-10-07")[0]
    assert (row[2], row[3]) == ("D5_7", "repeat_exposure")


def test_market_tags_without_session_check_leave_input_delay_unknown():
    """logic-5 — 시장 평가 전에 끝난 run 은 '입력 지연' 을 정하지 않는다."""
    con = ls.connect()
    try:
        tags = lm.market_tags(
            con, {}, [], runtime_date_kst="2026-10-07", calendar_dir=None
        )
    finally:
        con.close()
    assert tags["input_delay"] is None
    con = ls.connect()
    try:
        late, ok = (
            lm.market_tags(
                con,
                {"sp500_session_check": {"reason": r}},
                [],
                runtime_date_kst="2026-10-07",
                calendar_dir=None,
            )["input_delay"]
            for r in ("last_session_not_expected", "ok")
        )
    finally:
        con.close()
    assert (late, ok) == (True, False)


def test_contract_versions_cover_only_operating_kinds():
    assert set(lc.CONTRACT_VERSIONS) == {
        "market_briefing",
        "holdings_briefing",
        "holdings_risk_alert",
    }
