"""POC3-OPS-02A — 보유 위험 즉시 알림 단위 계약 test.

PLAN V1.2 §5 역검증 R-1 ~ R-17 대응. 합성 fixture 만 쓴다.
외부 조회 0건 · 라이브 state 미접근 · Telegram 발송 0건.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.runtime_evidence.holdings_risk import (
    GROUP_ORDER,
    REASON_DAY_DROP,
    STATE_D5_7,
    STATE_D7_10,
    STATE_D10_PLUS,
    RiskTicker,
    classify_day_drop,
    previous_trading_day,
    select_risk_holdings,
    severity,
    sort_risk,
)
from app.runtime_evidence.holdings_risk_render import (
    render_risk_alert,
    render_unavailable_group,
)
from app.runtime_evidence.holdings_risk_state import (
    SCHEMA_VERSION,
    compute_risk_changes,
    load_risk_state,
    merge_worst,
    save_risk_state,
)

TODAY = "2026-09-07"
# 실행일 직전 거래일 30개. 마지막이 직전 거래일이 된다.
AXIS = [f"2026-08-{i + 1:02d}" for i in range(30)]
PREV_DAY = AXIS[-1]


@dataclass
class FakeQuote:
    current_price: float
    price_asof: str = "2026-09-07T10:30:00+09:00"


def _history(close: float, *, prev: float | None = None) -> list[tuple[str, float]]:
    """축과 같은 날짜열. 마지막(직전 거래일) 종가만 `prev` 로 덮어쓸 수 있다."""
    rows = [(d, close) for d in AXIS]
    if prev is not None:
        rows[-1] = (rows[-1][0], prev)
    return rows


def _select(specs, *, quotes=None, axis=None, today=TODAY, buy=None):
    """specs: [(ticker, name, 직전종가, 현재가)] → select_risk_holdings"""
    holdings = [{"ticker": t, "name": n} for t, n, _, _ in specs]
    history = {t: _history(base) for t, _, base, _ in specs}
    q = quotes if quotes is not None else {t: FakeQuote(c) for t, _, _, c in specs}
    return select_risk_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes=q,
        today_kst=today,
        axis_dates=AXIS if axis is None else axis,
        avg_buy_prices=buy or {},
    )


# ── R-15 구간 경계 ────────────────────────────────────────────────────────────


def test_band_boundaries_are_inclusive_at_minus_5_7_10():
    """정확히 −5 / −7 / −10% 는 **더 나쁜 구간**에 든다 (PLAN §4.1)."""
    assert classify_day_drop(-5.0) == STATE_D5_7
    assert classify_day_drop(-7.0) == STATE_D7_10
    assert classify_day_drop(-10.0) == STATE_D10_PLUS


def test_band_just_above_threshold_is_not_selected():
    assert classify_day_drop(-4.9) is None
    assert classify_day_drop(-6.9) == STATE_D5_7
    assert classify_day_drop(-9.9) == STATE_D7_10
    assert classify_day_drop(0.0) is None
    assert classify_day_drop(None) is None


def test_selection_uses_normalized_pct_at_exact_boundary():
    """분모/분자에서 −5.0% 가 나오면 반올림 후에도 D5_7 이어야 한다."""
    selected, _ = _select([("069500", "KODEX200", 10000.0, 9500.0)])
    assert [(i.ticker, i.state, i.day_drop_pct) for i in selected] == [
        ("069500", STATE_D5_7, -5.0)
    ]


# ── R-1 / R-2 분모·분자 ───────────────────────────────────────────────────────


def test_denominator_is_previous_trading_day_close_not_today_open():
    """갭 하락 — 직전 종가 10000 → 현재 9200 이면 −8.0% 다.

    당일 시가(가령 9300)를 분모로 쓰면 −1.1% 로 보여 선정에서 빠진다.
    """
    selected, _ = _select([("102110", "TIGER200", 10000.0, 9200.0)])
    assert len(selected) == 1
    assert selected[0].day_drop_pct == -8.0
    assert selected[0].state == STATE_D7_10


def test_numerator_must_be_todays_quote():
    """`price_asof` 가 실행일이 아니면 선정하지 않고 데이터 확인 대상으로."""
    stale = {"102110": FakeQuote(9200.0, price_asof="2026-09-04T15:40:00+09:00")}
    selected, unavailable = _select(
        [("102110", "TIGER200", 10000.0, 9200.0)], quotes=stale
    )
    assert selected == []
    assert unavailable == ["102110"]


def test_previous_trading_day_excludes_today():
    assert previous_trading_day(AXIS, TODAY) == PREV_DAY
    assert previous_trading_day(AXIS + [TODAY], TODAY) == PREV_DAY
    assert previous_trading_day([], TODAY) is None


# ── R-16 결손 대체 금지 ───────────────────────────────────────────────────────


def test_missing_previous_close_is_not_substituted_by_older_close():
    """직전 거래일 종가가 없으면 더 오래된 값으로 대체하지 않는다 (§4.7)."""
    history = {"102110": [(d, 10000.0) for d in AXIS[:-1]]}  # 직전 거래일 결손
    selected, unavailable = select_risk_holdings(
        holdings=[{"ticker": "102110", "name": "TIGER200"}],
        price_history=history,
        market_quotes={"102110": FakeQuote(9200.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert selected == []
    assert unavailable == ["102110"]


# ── R-12 fingerprint 에 보조 정보 금지 ────────────────────────────────────────


def test_fingerprint_excludes_auxiliary_metrics_and_raw_value():
    a = RiskTicker("102110", "T", 1, STATE_D7_10, day_drop_pct=-7.4)
    b = RiskTicker("102110", "T", 1, STATE_D7_10, day_drop_pct=-9.1)
    b.drawdown_pct, b.profit_loss_pct = -30.0, 12.5
    assert (
        a.fingerprint() == b.fingerprint() == f"102110#{REASON_DAY_DROP}#{STATE_D7_10}"
    )


def test_fingerprint_changes_only_with_state():
    a = RiskTicker("102110", "T", 1, STATE_D7_10, day_drop_pct=-7.4)
    c = RiskTicker("102110", "T", 1, STATE_D10_PLUS, day_drop_pct=-10.4)
    assert a.fingerprint() != c.fingerprint()


# ── R-17 다계좌 ──────────────────────────────────────────────────────────────


def test_multi_account_ticker_is_rendered_once_with_account_count():
    holdings = [
        {"ticker": "102110", "name": "TIGER200", "account_group": "일반"},
        {"ticker": "102110", "name": "TIGER200", "account_group": "연금"},
    ]
    selected, _ = select_risk_holdings(
        holdings=holdings,
        price_history={"102110": _history(10000.0)},
        market_quotes={"102110": FakeQuote(9200.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert len(selected) == 1
    assert selected[0].account_count == 2
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=1)
    assert text.count("TIGER200") == 1
    assert "(2개 계좌)" in text


def _missing_path():
    from pathlib import Path

    return Path("/nonexistent-risk-state-for-test.json")


# ── R-14 동시 발생 한 메시지 · Top N 금지 ─────────────────────────────────────


def test_all_simultaneous_drops_appear_in_one_message():
    specs = [(f"1021{i:02d}", f"ETF{i}", 10000.0, 9200.0) for i in range(12)]
    selected, _ = _select(specs)
    assert len(selected) == 12
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=12)
    for _, name, _, _ in specs:
        assert name in text
    assert "보유 12종목 중 12종목 동시 하락" in text


def test_groups_ordered_worst_first_and_empty_groups_omitted():
    selected, _ = _select(
        [
            ("A", "얕은", 10000.0, 9400.0),  # -6.0 → D5_7
            ("B", "깊은", 10000.0, 8800.0),  # -12.0 → D10_PLUS
        ]
    )
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=2)
    assert text.index("10% 이상") < text.index("5~7%")
    assert "7~10%" not in text
    assert GROUP_ORDER[0] == STATE_D10_PLUS


def test_sort_is_worst_band_then_biggest_drop():
    items = [
        RiskTicker("B", "b", 1, STATE_D5_7, day_drop_pct=-5.2),
        RiskTicker("A", "a", 1, STATE_D5_7, day_drop_pct=-6.8),
        RiskTicker("C", "c", 1, STATE_D10_PLUS, day_drop_pct=-11.0),
    ]
    assert [i.ticker for i in sort_risk(items)] == ["C", "A", "B"]


# ── 보조 정보 표시 ────────────────────────────────────────────────────────────


def test_render_shows_three_metrics_in_contract_order():
    selected, _ = _select(
        [("102110", "TIGER200", 10000.0, 9200.0)], buy={"102110": 8000.0}
    )
    item = selected[0]
    assert item.day_drop_pct == -8.0
    assert item.drawdown_pct == -8.0  # 창 고점 10000 대비
    assert item.profit_loss_pct == 15.0  # 매입 8000 대비
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=1)
    assert "전일 대비 -8.0%" in text
    assert "고점 대비 -8.0%" in text
    assert "매입대비 +15.0%" in text
    assert text.index("전일 대비") < text.index("고점 대비") < text.index("매입대비")


def test_render_omits_open_price_comparison():
    """PLAN V1.3 §4.2-b — 시가 대비는 표시하지 않는다."""
    selected, _ = _select([("102110", "TIGER200", 10000.0, 9200.0)])
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=1)
    assert "시가" not in text


def test_render_has_no_disclaimer_or_country_sector_interpretation():
    selected, _ = _select([("102110", "TIGER200", 10000.0, 9200.0)])
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=1)
    for banned in ("투자 판단", "책임", "매도", "매수", "익스포저", "섹터"):
        assert banned not in text


# ── R-3 ~ R-8 상태·변화 판정 ─────────────────────────────────────────────────


def _state_file(tmp_path, entries, *, date=TODAY, schema=SCHEMA_VERSION):
    p = tmp_path / "risk.json"
    p.write_text(
        json.dumps(
            {"schema_version": schema, "kst_date": date, "entries": entries},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


def _item(ticker, state):
    return RiskTicker(ticker, ticker, 1, state, day_drop_pct=-6.0)


def test_first_entry_is_new(tmp_path):
    prev = load_risk_state(_state_file(tmp_path, {}), today_kst=TODAY)
    ch = compute_risk_changes(selected=[_item("A", STATE_D5_7)], previous=prev)
    assert [i.ticker for i in ch.new] == ["A"]
    assert ch.worsened == [] and ch.suppressed == []


def test_same_band_is_suppressed(tmp_path):
    """R-5 — 같은 구간 유지는 발송하지 않는다."""
    prev = load_risk_state(
        _state_file(tmp_path, {"A": {"worst_state": STATE_D5_7}}), today_kst=TODAY
    )
    ch = compute_risk_changes(selected=[_item("A", STATE_D5_7)], previous=prev)
    assert ch.new == [] and ch.worsened == []
    assert ch.suppressed == ["A"]
    assert ch.has_send is False


def test_worsening_is_sent_with_previous_band(tmp_path):
    prev = load_risk_state(
        _state_file(tmp_path, {"A": {"worst_state": STATE_D5_7}}), today_kst=TODAY
    )
    ch = compute_risk_changes(selected=[_item("A", STATE_D10_PLUS)], previous=prev)
    assert ch.new == []
    assert [(i.ticker, p) for i, p in ch.worsened] == [("A", STATE_D5_7)]
    assert ch.has_send is True


def test_easing_is_not_sent(tmp_path):
    """R-3 — 완화는 발송하지 않는다."""
    prev = load_risk_state(
        _state_file(tmp_path, {"A": {"worst_state": STATE_D10_PLUS}}), today_kst=TODAY
    )
    ch = compute_risk_changes(selected=[_item("A", STATE_D5_7)], previous=prev)
    assert ch.has_send is False
    assert ch.suppressed == ["A"]


def test_resolution_is_not_sent(tmp_path):
    """R-4 — 구간을 벗어난 해소도 발송하지 않는다 (선정에서 아예 빠진다)."""
    prev = load_risk_state(
        _state_file(tmp_path, {"A": {"worst_state": STATE_D7_10}}), today_kst=TODAY
    )
    ch = compute_risk_changes(selected=[], previous=prev)
    assert ch.has_send is False
    assert ch.new == [] and ch.worsened == []


def test_reentry_same_day_after_easing_is_suppressed(tmp_path):
    """R-6 / R-8 — 완화 후 같은 날 재진입은 재발송하지 않는다.

    `worst_state` 를 낮추지 않기 때문에 성립한다. 직전 구간과 비교하면 재발송된다.
    """
    path = _state_file(tmp_path, {"A": {"worst_state": STATE_D7_10}})
    prev = load_risk_state(path, today_kst=TODAY)
    # 완화 — 선정에서 빠짐. worst 는 유지돼야 한다.
    entries = merge_worst(selected=[], previous=prev)
    assert entries == {"A": {"worst_state": STATE_D7_10}}
    save_risk_state(path, entries=entries, today_kst=TODAY)
    # 같은 날 D7_10 재진입.
    prev2 = load_risk_state(path, today_kst=TODAY)
    ch = compute_risk_changes(selected=[_item("A", STATE_D7_10)], previous=prev2)
    assert ch.has_send is False
    assert ch.suppressed == ["A"]


def test_merge_worst_never_lowers(tmp_path):
    prev = load_risk_state(
        _state_file(tmp_path, {"A": {"worst_state": STATE_D10_PLUS}}), today_kst=TODAY
    )
    entries = merge_worst(selected=[_item("A", STATE_D5_7)], previous=prev)
    assert entries["A"]["worst_state"] == STATE_D10_PLUS


def test_merge_worst_raises_on_worsening(tmp_path):
    prev = load_risk_state(
        _state_file(tmp_path, {"A": {"worst_state": STATE_D5_7}}), today_kst=TODAY
    )
    entries = merge_worst(selected=[_item("A", STATE_D10_PLUS)], previous=prev)
    assert entries["A"]["worst_state"] == STATE_D10_PLUS


# ── R-7 거래일 경계 초기화 ───────────────────────────────────────────────────


def test_previous_day_state_is_discarded(tmp_path):
    """R-7 — 전일 상태를 이월하면 오늘 첫 진입이 억제된다."""
    prev = load_risk_state(
        _state_file(
            tmp_path, {"A": {"worst_state": STATE_D10_PLUS}}, date="2026-09-04"
        ),
        today_kst=TODAY,
    )
    assert prev.fallback == "date_reset"
    assert prev.comparable is False
    ch = compute_risk_changes(selected=[_item("A", STATE_D5_7)], previous=prev)
    assert [i.ticker for i in ch.new] == ["A"]


def test_state_fallbacks_treat_everything_as_new(tmp_path):
    missing = tmp_path / "none.json"
    assert load_risk_state(missing, today_kst=TODAY).fallback == "missing"

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert load_risk_state(corrupt, today_kst=TODAY).fallback == "corrupt"

    bad = _state_file(tmp_path, {}, schema="holdings_risk_state.v0")
    assert load_risk_state(bad, today_kst=TODAY).fallback == "schema_mismatch"

    ch = compute_risk_changes(
        selected=[_item("A", STATE_D5_7)],
        previous=load_risk_state(missing, today_kst=TODAY),
    )
    assert [i.ticker for i in ch.new] == ["A"]


def test_save_and_reload_roundtrip(tmp_path):
    p = tmp_path / "sub" / "risk.json"
    save_risk_state(
        p,
        entries={"A": {"worst_state": STATE_D7_10}},
        today_kst=TODAY,
        runtime_kst="2026-09-07T10:30:00+09:00",
    )
    loaded = load_risk_state(p, today_kst=TODAY)
    assert loaded.comparable is True
    assert loaded.entries == {"A": {"worst_state": STATE_D7_10}}


def test_severity_order():
    assert severity(STATE_D5_7) < severity(STATE_D7_10) < severity(STATE_D10_PLUS)
    assert severity(None) == 0


# ── PLAN §4.6 / §4.7 — `데이터 확인 필요` 렌더 ───────────────────────────────


def test_unavailable_group_is_rendered_after_bands():
    selected, _ = _select([("102110", "TIGER200", 10000.0, 9200.0)])
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(
        changes,
        slot_label="10:30",
        held_ticker_count=2,
        unavailable=[("069500", "KODEX200")],
    )
    assert "■ 데이터 확인 필요 (1)" in text
    assert "KODEX200" in text
    assert "직전 거래일 종가 또는 오늘 시세를 확인할 수 없음" in text
    # 구간 그룹 뒤에 온다 — 하락 구간이 먼저 눈에 들어와야 한다.
    assert text.index("하락 7~10%") < text.index("데이터 확인 필요")


def test_unavailable_group_omitted_when_empty():
    selected, _ = _select([("102110", "TIGER200", 10000.0, 9200.0)])
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="10:30", held_ticker_count=1)
    assert "데이터 확인 필요" not in text


def test_unavailable_alone_renders_nothing():
    """결손만 있고 신규·악화가 없으면 본문 자체를 만들지 않는다."""
    empty = compute_risk_changes(selected=[], previous=load_risk_state(_missing_path()))
    text = render_risk_alert(
        empty,
        slot_label="10:30",
        held_ticker_count=1,
        unavailable=[("069500", "KODEX200")],
    )
    assert text == ""


def test_unavailable_group_has_no_band_label():
    """하락률을 계산할 수 없으므로 구간을 붙이지 않는다."""
    lines = render_unavailable_group([("069500", "KODEX200")])
    joined = "\n".join(lines)
    for band in ("5~7%", "7~10%", "10% 이상"):
        assert band not in joined
    assert "전일 대비" not in joined


# ── 헤더 문구 (사용자 지시 2026-09-07) ───────────────────────────────────────


def test_header_name_is_the_new_alert_name():
    """`[보유 급락 알림]` — 09:15 `[보유 종목 관찰 브리핑]` 과 구분한다."""
    from app.runtime_evidence.holdings_risk_render import HEADER, PREVIEW_HEADER

    assert HEADER == "[보유 급락 알림]"
    assert PREVIEW_HEADER.startswith("[보유 급락 알림")
    assert "관찰" not in HEADER and "위험 알림" not in HEADER


def test_single_item_header_drops_the_word_simultaneous():
    selected, _ = _select([("102110", "TIGER200", 10000.0, 9200.0)])
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="14:30", held_ticker_count=23)
    assert text.startswith("[보유 급락 알림] 14:30 — 보유 23종목 중 1종목 하락")
    assert "동시" not in text


def test_two_or_more_items_keep_simultaneous():
    selected, _ = _select(
        [
            ("102110", "TIGER200", 10000.0, 9200.0),
            ("069500", "KODEX200", 10000.0, 9300.0),
        ]
    )
    changes = compute_risk_changes(
        selected=selected, previous=load_risk_state(_missing_path())
    )
    text = render_risk_alert(changes, slot_label="14:30", held_ticker_count=23)
    assert "보유 23종목 중 2종목 동시 하락" in text
