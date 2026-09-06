"""POC3-OPS-01A — 보유 브리핑 선정·구간·렌더 계약 test.

PLAN §7.1 T-1~T-4 · T-13~T-16 · T-18 대응.
합성 fixture 만 사용한다. 외부 조회 0건 · 라이브 state 미접근.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.runtime_evidence.holdings_selection import (
    DRAWDOWN_NOTE_MAX_PCT,
    REASON_DATA_UNAVAILABLE,
    REASON_RECENT_DECLINE,
    STATE_ACTIVE,
    STATE_D5_8,
    STATE_D8_10,
    STATE_D10_PLUS,
    classify_decline,
    group_label,
    select_holdings,
)
from app.runtime_evidence.holdings_selection_render import (
    render_full,
    render_groups,
)


@dataclass
class FakeQuote:
    current_price: float
    price_asof: str = "2026-09-04T09:14:00+09:00"


# 설계자 확정 2026-09-05 — 분모는 **거래일 축의 기준일 종가**다. 축을 주지 않으면
# 기준일이 없어 전 종목이 `DATA_UNAVAILABLE_OR_STALE` 이 된다(정상 동작).
TODAY = "2026-09-04"

# 실행일(2026-09-04) 이전 거래일 30개. 뒤에서 20번째가 기준일이 된다.
AXIS = [f"2026-08-{i + 1:02d}" for i in range(30)]
BASE_DAY = AXIS[-20]


def _history(base: float, last: float, n: int = 30) -> list[tuple[str, float]]:
    """축과 같은 날짜열의 종가 시계열. 기준일 종가가 `base`, 마지막이 `last`."""
    rows = [(AXIS[i], base) for i in range(n)]
    rows[-1] = (rows[-1][0], last)
    return rows


def _holding(ticker: str, name: str, account: str = "일반") -> dict:
    return {"ticker": ticker, "name": name, "account_group": account}


def _select(specs, *, quotes=None, axis=None, today=TODAY):
    """specs: [(ticker, name, base_close, current_price)]"""
    holdings = [_holding(t, n) for t, n, _, _ in specs]
    history = {t: _history(b, b) for t, _, b, _ in specs}
    q = (
        quotes
        if quotes is not None
        else {t: FakeQuote(current_price=c) for t, _, _, c in specs if c is not None}
    )
    return select_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes=q,
        today_kst=today,
        axis_dates=AXIS if axis is None else axis,
    )


# --- T-16 구간 경계 정규화 --------------------------------------------------


def test_t16_band_boundaries_are_upper_exclusive_lower_inclusive():
    assert classify_decline(-4.99) is None
    assert classify_decline(-5.0) == STATE_D5_8
    assert classify_decline(-7.99) == STATE_D5_8
    # -8.0 은 D5_8 의 `-8% < r` 을 만족하지 않으므로 D8_10 이다.
    assert classify_decline(-8.0) == STATE_D8_10
    assert classify_decline(-9.99) == STATE_D8_10
    assert classify_decline(-10.0) == STATE_D10_PLUS
    assert classify_decline(-25.0) == STATE_D10_PLUS
    assert classify_decline(None) is None
    assert classify_decline(0.0) is None
    assert classify_decline(5.0) is None


def test_t16_classification_uses_the_displayed_value():
    """판정 입력과 화면 표시가 같은 정규화 값이어야 한다.

    92/100-1 은 float 로 -7.999999999999996 이다. 정규화 없이 판정하면 `D5_8`
    인데 화면에는 `-8.0%` 로 찍혀 `-8.0%인데 5~8% 그룹` 이 된다.
    """
    items = _select([("AAA", "가나다", 100.0, 92.0)])
    value = items[0].reasons[REASON_RECENT_DECLINE]["value"]
    assert value == -8.0, f"정규화 안 됨: {value!r}"
    assert classify_decline(value) == items[0].reasons[REASON_RECENT_DECLINE]["state"]


def test_t16_boundary_value_and_label_agree():
    """판정값과 표시값이 어긋나면 안 된다 — `-8.0%인데 5~8% 그룹` 금지."""
    items = _select([("AAA", "가나다", 100.0, 92.0)])  # 정확히 -8.00%
    assert len(items) == 1
    assert items[0].reasons[REASON_RECENT_DECLINE]["state"] == STATE_D8_10
    text = "\n".join(render_groups(items))
    assert "20거래일 하락 8~10%" in text
    assert "20거래일 하락 5~8%" not in text


# --- T-1 / T-2 선정 필터 ----------------------------------------------------


def test_t1_ticker_without_reason_is_not_shown():
    items = _select(
        [
            ("AAA", "가나다", 100.0, 99.0),  # -1% → 선정 안 됨
            ("BBB", "라마바", 100.0, 90.0),  # -10% → D10_PLUS
        ]
    )
    assert [i.ticker for i in items] == ["BBB"]
    text = "\n".join(render_groups(items))
    assert "가나다" not in text


def test_t2_all_selected_tickers_are_shown_without_cap():
    specs = [(f"T{i:02d}", f"종목{i:02d}", 100.0, 80.0) for i in range(29)]
    items = _select(specs)
    assert len(items) == 29
    text = "\n".join(render_groups(items))
    for _, name, _, _ in specs:
        assert name in text
    assert "20거래일 하락 10% 이상 (29)" in text


# --- T-3 다계좌 --------------------------------------------------------------


def test_t3_same_ticker_in_multiple_accounts_is_one_row():
    holdings = [
        _holding("069500", "KODEX 200", "일반"),
        _holding("069500", "KODEX 200", "ISA"),
        _holding("069500", "KODEX 200", "연금"),
    ]
    items = select_holdings(
        holdings=holdings,
        price_history={"069500": _history(100.0, 100.0)},
        market_quotes={"069500": FakeQuote(current_price=88.0)},
    )
    assert len(items) == 1
    assert items[0].account_count == 3
    text = "\n".join(render_groups(items))
    assert text.count("KODEX 200") == 1
    assert "(3개 계좌)" in text


# --- T-4 그룹화 --------------------------------------------------------------


def test_t4_same_state_is_grouped_and_ordered():
    items = _select(
        [
            ("AAA", "하락10", 100.0, 88.0),  # -12% → D10_PLUS
            ("BBB", "하락9", 100.0, 91.0),  # -9%  → D8_10
            ("CCC", "하락6", 100.0, 94.0),  # -6%  → D5_8
            ("DDD", "하락11", 100.0, 89.0),  # -11% → D10_PLUS
        ]
    )
    text = "\n".join(render_groups(items))
    assert "■ 20거래일 하락 10% 이상 (2)" in text
    assert "■ 20거래일 하락 8~10% (1)" in text
    assert "■ 20거래일 하락 5~8% (1)" in text
    # 그룹 표시 순서: 10% 이상 → 8~10% → 5~8%
    assert text.index("10% 이상") < text.index("8~10%") < text.index("5~8%")
    # 그룹 내 정렬: 근거 값 악화순 (-12% 가 -11% 보다 앞)
    assert text.index("하락11") > text.index("하락10")


# --- T-18 데이터 문제 --------------------------------------------------------


def test_t18_missing_quote_becomes_data_unavailable_not_silent_drop():
    items = _select([("AAA", "가나다", 100.0, None)], quotes={})
    assert len(items) == 1
    assert REASON_DATA_UNAVAILABLE in items[0].reasons
    assert items[0].reasons[REASON_DATA_UNAVAILABLE]["state"] == STATE_ACTIVE
    assert "데이터 확인 필요" in "\n".join(render_groups(items))


def test_t18_missing_base_close_becomes_data_unavailable():
    """분모(20거래일 전 종가)가 없으면 stale 종가로 대체하지 않는다."""
    items = select_holdings(
        holdings=[_holding("AAA", "가나다")],
        price_history={"AAA": [("2026-08-31", 100.0)]},  # 21개 미만
        market_quotes={"AAA": FakeQuote(current_price=50.0)},
    )
    assert items[0].reasons.keys() == {REASON_DATA_UNAVAILABLE}


def test_t18_zero_or_negative_price_is_data_unavailable():
    items = _select([("AAA", "가나다", 100.0, 0.0)])
    assert REASON_DATA_UNAVAILABLE in items[0].reasons


def test_data_unavailable_group_is_separate_from_decline_bands():
    items = _select(
        [("AAA", "하락", 100.0, 85.0), ("BBB", "미확인", 100.0, None)],
        quotes={"AAA": FakeQuote(current_price=85.0)},
    )
    text = "\n".join(render_groups(items))
    assert "■ 20거래일 하락 10% 이상 (1)" in text
    assert "■ 데이터 확인 필요 (1)" in text
    # 데이터 확인 필요가 맨 뒤
    assert text.index("데이터 확인 필요") > text.index("10% 이상")


# --- T-13 면책문구 없음 -------------------------------------------------------

FORBIDDEN_COPY = [
    "매도·교체·비중 조절",
    "매매 지시",
    "이 알림은",
    "정보이며",
    "참고용",
    "투자 판단에 사용하지",
]


def test_t13_no_disclaimer_or_operational_copy_in_body():
    items = _select([("AAA", "가나다", 100.0, 85.0)])
    text = render_full(
        items,
        slot_label="09:15",
        base_close_date="2026-08-06",
        quote_asof="2026-09-04 09:14",
    )
    for phrase in FORBIDDEN_COPY:
        assert phrase not in text, f"금지 문구 노출: {phrase}"


def test_t13_header_shows_two_different_dates():
    """분모는 과거 종가일, 분자는 실행 시점 시세 — 같은 날짜로 적으면 안 된다."""
    items = _select([("AAA", "가나다", 100.0, 85.0)])
    text = render_full(
        items,
        slot_label="09:15",
        base_close_date="2026-08-06",
        quote_asof="2026-09-04 09:14",
    )
    assert "20거래일 전 종가 2026-08-06" in text
    assert "시세 2026-09-04 09:14" in text


# --- 보조 정보 (고점 대비) ----------------------------------------------------


def test_drawdown_note_only_when_deep_enough():
    history = [(f"2026-08-{i + 1:02d}", 100.0) for i in range(30)]
    history[-1] = (history[-1][0], 85.0)  # 고점 100 대비 -15%
    items = select_holdings(
        holdings=[_holding("AAA", "가나다")],
        price_history={"AAA": history},
        market_quotes={"AAA": FakeQuote(current_price=85.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].drawdown_20d_pct is not None
    assert items[0].drawdown_20d_pct <= DRAWDOWN_NOTE_MAX_PCT
    assert "고점 대비" in "\n".join(render_groups(items))


def test_drawdown_is_auxiliary_only_never_a_group():
    """고점 대비는 선정 근거가 아니다 — 그룹·fingerprint 를 만들지 않는다."""
    history = [(f"2026-08-{i + 1:02d}", 100.0) for i in range(30)]
    history[-1] = (history[-1][0], 88.0)  # 고점 대비 -12% 지만 20일 수익률은 -12%
    items = select_holdings(
        holdings=[_holding("AAA", "가나다")],
        price_history={"AAA": history},
        market_quotes={"AAA": FakeQuote(current_price=99.5)},  # -0.5% → 선정 안 됨
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items == []


def test_group_label_never_uses_severity_words():
    for reason, state in [
        (REASON_RECENT_DECLINE, STATE_D5_8),
        (REASON_RECENT_DECLINE, STATE_D8_10),
        (REASON_RECENT_DECLINE, STATE_D10_PLUS),
        (REASON_DATA_UNAVAILABLE, STATE_ACTIVE),
    ]:
        label = group_label(reason, state)
        for word in ("관찰", "주의", "경고"):
            assert word not in label, f"{label} 에 심각도 명칭 {word}"


# --- fingerprint -------------------------------------------------------------


def test_fingerprint_is_reason_state_pairs_not_max_severity():
    items = _select([("AAA", "가나다", 100.0, 85.0)])
    fp = items[0].fingerprint()
    assert fp == "AAA|RECENT_DECLINE:D10_PLUS"


def test_fingerprint_ignores_value_changes_within_band():
    a = _select([("AAA", "가나다", 100.0, 89.0)])[0]  # -11%
    b = _select([("AAA", "가나다", 100.0, 88.0)])[0]  # -12%
    assert (
        a.reasons[REASON_RECENT_DECLINE]["value"]
        != b.reasons[REASON_RECENT_DECLINE]["value"]
    )
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_changes_when_band_moves():
    a = _select([("AAA", "가나다", 100.0, 91.0)])[0]  # -9%  → D8_10
    b = _select([("AAA", "가나다", 100.0, 89.0)])[0]  # -11% → D10_PLUS
    assert a.fingerprint() != b.fingerprint()


# --- 검증자 r2 B-6 — 직접 검증이 없던 계약 ----------------------------------


def test_base_close_must_be_exactly_the_reference_trading_day():
    """분모는 **기준일 그 날짜** 종가다 (설계자 확정 2026-09-05).

    `MAX_PRICE_STALE_DAYS` 달력일 임계는 폐기됐다. 기준일 종가가 없으면 더 오래된
    종가로 대체하지 않고 `DATA_UNAVAILABLE_OR_STALE` 로 뺀다 — 대체하면 20거래일이
    아닌 구간의 수익률을 20거래일이라고 보고하게 된다.
    """
    from app.runtime_evidence.holdings_selection import close_on, reference_trading_day

    assert reference_trading_day(AXIS, TODAY, 20) == BASE_DAY

    history = [(d, 100.0) for d in AXIS]
    assert close_on(history, BASE_DAY) == 100.0

    # 기준일만 빠진 이력 → 대체 없이 None
    gapped = [(d, 100.0) for d in AXIS if d != BASE_DAY]
    assert close_on(gapped, BASE_DAY) is None

    items = select_holdings(
        holdings=[_holding("AAA", "가나다")],
        price_history={"AAA": gapped},
        market_quotes={"AAA": FakeQuote(current_price=80.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert list(items[0].reasons) == [REASON_DATA_UNAVAILABLE]


def test_axis_too_short_yields_no_reference_day():
    """거래일이 20개에 못 미치면 기준일이 없다."""
    from app.runtime_evidence.holdings_selection import reference_trading_day

    assert reference_trading_day(AXIS[:19], TODAY, 20) is None
    assert reference_trading_day(AXIS[:20], TODAY, 20) == AXIS[0]
    assert reference_trading_day([], TODAY, 20) is None
    assert reference_trading_day(AXIS, None, 20) is None


def test_reference_day_is_strictly_before_run_date():
    """실행일 당일은 기준일 후보가 아니다."""
    from app.runtime_evidence.holdings_selection import reference_trading_day

    axis = AXIS + [TODAY]
    assert reference_trading_day(axis, TODAY, 1) == AXIS[-1]
    assert reference_trading_day(axis, TODAY, 20) == BASE_DAY


def test_quote_from_a_past_day_is_data_unavailable():
    """분자는 **실행일** 시세여야 한다. 과거 시각 quote 는 그 종목만 뺀다."""
    items = _select(
        [("AAA", "가나다", 100.0, 80.0)],
        quotes={
            "AAA": FakeQuote(current_price=80.0, price_asof="2026-09-03T15:30:00+09:00")
        },
    )
    assert list(items[0].reasons) == [REASON_DATA_UNAVAILABLE]

    fresh = _select(
        [("AAA", "가나다", 100.0, 80.0)],
        quotes={
            "AAA": FakeQuote(current_price=80.0, price_asof="2026-09-04T09:14:00+09:00")
        },
    )
    assert list(fresh[0].reasons) == [REASON_RECENT_DECLINE]


def test_incomplete_aux_window_drops_only_the_note_not_the_selection():
    """보조값 구간이 불완전하면 **보조값만** 생략한다.

    설계자 확정 — 보조값 누락 때문에 계산 가능한 `RECENT_DECLINE` 까지 버리지
    않는다. 구간에 빠진 날이 있는 채로 고점을 잡으면 하락이 얕게 보고된다.
    """
    # 기준일 종가는 있고, 보조 구간 중간 한 날이 빠진 이력
    drop = AXIS[-5]
    history = [(d, 100.0) for d in AXIS if d != drop]
    items = select_holdings(
        holdings=[_holding("AAA", "가나다")],
        price_history={"AAA": history},
        market_quotes={"AAA": FakeQuote(current_price=80.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert list(items[0].reasons) == [
        REASON_RECENT_DECLINE
    ], "보조값 때문에 선정을 버렸다"
    assert items[0].drawdown_20d_pct is None, "불완전 구간인데 보조값을 만들었다"


def test_price_history_exception_becomes_outcome_error_not_raise(tmp_path):
    """가격 이력 조회 예외는 밖으로 새지 않고 `outcome.error` 로 수렴한다.

    러너는 이 값을 보고 `holdings_selection_error` 로 끝낸다
    (`runtime_evidence_error` 가 아니다 — 결과서 r1 오보).
    """
    from app.runtime_evidence.holdings_selection_flow import build_holdings_selection

    def _boom(ticker, **kw):
        raise RuntimeError("가격 DB 잠김")

    out = build_holdings_selection(
        holdings_loader=lambda: [
            SimpleNamespace(ticker="AAA", name="가나다", account_group="일반")
        ],
        fetch_history=_boom,
        market_quotes={},
        state_path=tmp_path / "s.json",
        slot_id="OPEN",
        runtime_kst="2026-09-04T09:15:00+09:00",
        today_kst="2026-09-04",
    )
    assert out.error, "예외가 error 로 수렴하지 않았다"
    assert "가격 DB 잠김" in out.error
    assert out.message_text in (None, "")


def test_privacy_check_failure_blocks_send(tmp_path, monkeypatch):
    """privacy 검사 자체가 실패하면 발송을 막는다 (fail-open 금지).

    검사 실패를 '노출 없음' 으로 기록하면 안전 신호가 거짓이 된다.
    """
    import app.runtime_evidence.holdings_selection_flow as flow

    monkeypatch.setattr(
        flow,
        "detect_privacy_on_body",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("탐지기 고장")),
    )
    out = flow.build_holdings_selection(
        holdings_loader=lambda: [
            SimpleNamespace(ticker="AAA", name="가나다", account_group="일반")
        ],
        fetch_history=lambda t, **kw: [
            (f"2026-08-{i + 1:02d}", 100.0) for i in range(30)
        ],
        market_quotes={
            "AAA": SimpleNamespace(
                current_price=80.0, price_asof="2026-09-04T09:00:00+09:00"
            )
        },
        state_path=tmp_path / "s.json",
        slot_id="OPEN",
        runtime_kst="2026-09-04T09:15:00+09:00",
        today_kst="2026-09-04",
    )
    assert out.error, "privacy 검사 실패인데 통과시켰다"
    assert "privacy_check_failed" in out.error
    assert out.save_state_on_send is False


# --- 사용자 요청 2026-09-06 — 매입가 대비 손익률 (C안 두 줄) ----------------


def _pl_select(specs, buy_prices):
    """specs: [(ticker, name, base_close, current_price)]"""
    holdings = [_holding(t, n) for t, n, _, _ in specs]
    history = {t: _history(b, b) for t, _, b, _ in specs}
    q = {t: FakeQuote(current_price=c) for t, _, _, c in specs if c is not None}
    return select_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes=q,
        today_kst=TODAY,
        axis_dates=AXIS,
        avg_buy_prices=buy_prices,
    )


def test_profit_loss_uses_same_current_price_as_return():
    """매입 대비의 분자는 20일 수익률과 **같은 현재가**다.

    사용자 확정: 세 슬롯 모두 실행 시점 시세 기준. OPEN 만 종가로 바꾸지 않는다.
    """
    items = _pl_select([("AAA", "가나다", 100.0, 80.0)], {"AAA": 50.0})
    assert items[0].reasons[REASON_RECENT_DECLINE]["value"] == -20.0  # 80/100
    assert items[0].profit_loss_pct == 60.0  # 80/50


def test_profit_loss_missing_buy_price_keeps_selection():
    """매입가가 없으면 **손익 표시만 생략**한다. 선정을 버리지 않는다."""
    items = _pl_select([("AAA", "가나다", 100.0, 80.0)], {})
    assert list(items[0].reasons) == [REASON_RECENT_DECLINE]
    assert items[0].profit_loss_pct is None
    body = "\n".join(render_groups(items))
    assert "매입대비" not in body
    assert "20거래일 -20.0%" in body


def test_profit_loss_is_not_in_fingerprint():
    """손익률은 **보조 정보**다 — identity 에 넣으면 매 슬롯 재발송된다."""
    a = _pl_select([("AAA", "가나다", 100.0, 80.0)], {"AAA": 50.0})[0]
    b = _pl_select([("AAA", "가나다", 100.0, 80.0)], {"AAA": 70.0})[0]
    assert a.profit_loss_pct != b.profit_loss_pct
    assert a.fingerprint() == b.fingerprint()


def test_item_renders_as_two_lines_with_purchase_first():
    """C안 — 종목명 줄 + 상세 줄. 상세는 매입 → 20거래일 → 고점 대비 순."""
    items = _pl_select([("AAA", "가나다", 100.0, 80.0)], {"AAA": 50.0})
    body = "\n".join(render_groups(items))
    lines = [ln for ln in body.split("\n") if ln.strip()]
    assert lines[1] == "  가나다"
    assert lines[2].strip().startswith("매입대비 +60.0% · 20거래일 -20.0%")


def test_data_unavailable_row_has_no_purchase_figure():
    """현재가가 없으면 손익도 낼 수 없다 — 숫자를 지어내지 않는다."""
    items = _pl_select([("AAA", "가나다", 100.0, None)], {"AAA": 50.0})
    assert list(items[0].reasons) == [REASON_DATA_UNAVAILABLE]
    assert items[0].profit_loss_pct is None
    assert "매입대비" not in "\n".join(render_groups(items))


def test_average_buy_price_is_quantity_weighted():
    """다계좌는 계좌별 매입가가 다르다 — **금액합/수량합** 이다.

    단순 평균을 내면 소량 계좌가 과대 반영된다. 실측 예: KODEX 200 이
    84,190(3주) / 88,058(15주) / 114,941(2주).
    """
    from app.runtime_evidence.holdings_selection_source import average_buy_prices

    rows = [
        {"ticker": "A", "quantity": 3, "avg_buy_price": 84190.0},
        {"ticker": "A", "quantity": 15, "avg_buy_price": 88058.0},
        {"ticker": "A", "quantity": 2, "avg_buy_price": 114941.0},
    ]
    got = average_buy_prices(rows)["A"]
    expected = (84190 * 3 + 88058 * 15 + 114941 * 2) / 20
    assert abs(got - expected) < 1e-9
    simple = (84190 + 88058 + 114941) / 3
    assert abs(got - simple) > 1.0, "단순 평균과 구분되지 않는다"


def test_average_buy_price_skips_unusable_rows():
    from app.runtime_evidence.holdings_selection_source import average_buy_prices

    rows = [
        {"ticker": "A", "quantity": 0, "avg_buy_price": 100.0},
        {"ticker": "A", "quantity": 5, "avg_buy_price": 200.0},
        {"ticker": "B", "quantity": 5, "avg_buy_price": None},
        {"ticker": "C", "quantity": "x", "avg_buy_price": 10.0},
    ]
    out = average_buy_prices(rows)
    assert out == {"A": 200.0}
