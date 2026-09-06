"""POC3-OPS-01A — 반복 억제 상태 · 비거래일 가드 계약 test.

PLAN §7.1 T-5~T-12 · T-14 · T-15 · T-17 · §9.5 T-19~T-21 대응.
합성 fixture + tmp_path 만 사용한다. 라이브 state 미접근 · 외부 조회 0건.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.runtime_evidence.holdings_selection import (
    REASON_DATA_UNAVAILABLE,
    REASON_RECENT_DECLINE,
    STATE_D8_10,
    STATE_D10_PLUS,
    select_holdings,
)
from app.runtime_evidence.holdings_selection_state import (
    FALLBACK_CORRUPT,
    FALLBACK_DATE,
    FALLBACK_MISSING,
    FALLBACK_SCHEMA,
    SCHEMA_VERSION,
    compute_changes,
    load_state,
    save_state,
)
from app.three_push_runtime.non_trading_day import detect_non_trading_day

TODAY = "2026-09-04"
YESTERDAY = "2026-09-03"


@dataclass
class FakeQuote:
    current_price: float
    price_asof: str = f"{TODAY}T09:14:00+09:00"


# 설계자 확정 2026-09-05 — 분모는 거래일 축의 기준일 종가다.
AXIS = [f"2026-08-{i + 1:02d}" for i in range(30)]
BASE_DAY = AXIS[-20]


def _history(base: float, n: int = 30) -> list[tuple[str, float]]:
    return [(AXIS[i], base) for i in range(n)]


def _select(specs):
    """specs: [(ticker, name, base, current)]"""
    return select_holdings(
        holdings=[{"ticker": t, "name": n} for t, n, _, _ in specs],
        price_history={t: _history(b) for t, _, b, _ in specs},
        market_quotes={
            t: FakeQuote(current_price=c) for t, _, _, c in specs if c is not None
        },
        today_kst=TODAY,
        axis_dates=AXIS,
    )


def _state_path(tmp_path):
    return tmp_path / "holdings_selection_state_latest.json"


# --- T-5 / T-9 상태 로드 · fallback -----------------------------------------


def test_t9_missing_state_falls_back_to_full_send(tmp_path):
    st = load_state(_state_path(tmp_path), today_kst=TODAY)
    assert st.fallback == FALLBACK_MISSING
    assert st.comparable is False
    changes = compute_changes(selected=[], previous=st, is_first_slot=False)
    assert changes.full_send is True
    assert changes.fallback == FALLBACK_MISSING


def test_t9_corrupt_state_falls_back_to_full_send(tmp_path):
    p = _state_path(tmp_path)
    p.write_text("{ not json", encoding="utf-8")
    st = load_state(p, today_kst=TODAY)
    assert st.fallback == FALLBACK_CORRUPT
    assert (
        compute_changes(selected=[], previous=st, is_first_slot=False).full_send is True
    )


def test_t9_schema_mismatch_falls_back(tmp_path):
    p = _state_path(tmp_path)
    p.write_text(
        json.dumps({"schema_version": "other.v9", "kst_date": TODAY, "entries": {}}),
        encoding="utf-8",
    )
    assert load_state(p, today_kst=TODAY).fallback == FALLBACK_SCHEMA


def test_t9_date_mismatch_falls_back(tmp_path):
    p = _state_path(tmp_path)
    save_state(p, selected=[], slot_id="CLOSE", today_kst=YESTERDAY)
    st = load_state(p, today_kst=TODAY)
    assert st.fallback == FALLBACK_DATE
    assert (
        compute_changes(selected=[], previous=st, is_first_slot=False).full_send is True
    )


def test_t9_comparison_failure_is_never_reported_as_no_change(tmp_path):
    """비교 실패를 `변화 없음` 으로 대체하면 판단 재료를 조용히 삼킨다."""
    for setup in (
        lambda p: None,
        lambda p: p.write_text("broken", encoding="utf-8"),
        lambda p: p.write_text(json.dumps({"schema_version": "x"}), encoding="utf-8"),
    ):
        p = tmp_path / f"s_{id(setup)}.json"
        setup(p)
        st = load_state(p, today_kst=TODAY)
        ch = compute_changes(selected=[], previous=st, is_first_slot=False)
        assert ch.has_change is True, "비교 불가인데 변화 없음으로 판정됨"


def test_t5_first_slot_always_full_send(tmp_path):
    p = _state_path(tmp_path)
    items = _select([("AAA", "가나다", 100.0, 88.0)])
    save_state(p, selected=items, slot_id="OPEN", today_kst=TODAY)
    st = load_state(p, today_kst=TODAY)
    assert st.comparable is True
    ch = compute_changes(selected=items, previous=st, is_first_slot=True)
    assert ch.full_send is True


# --- T-6 동일 상태 억제 -------------------------------------------------------


def test_t6_identical_state_produces_no_change(tmp_path):
    p = _state_path(tmp_path)
    items = _select([("AAA", "가나다", 100.0, 88.0)])
    save_state(p, selected=items, slot_id="OPEN", today_kst=TODAY)
    st = load_state(p, today_kst=TODAY)
    ch = compute_changes(selected=items, previous=st, is_first_slot=False)
    assert ch.has_change is False
    assert ch.new == [] and ch.moved == [] and ch.resolved == []


# --- T-7 새 종목 · 구간 이동 --------------------------------------------------


def test_t7_new_ticker_is_a_change(tmp_path):
    p = _state_path(tmp_path)
    save_state(
        p,
        selected=_select([("AAA", "가나다", 100.0, 88.0)]),
        slot_id="OPEN",
        today_kst=TODAY,
    )
    later = _select([("AAA", "가나다", 100.0, 88.0), ("BBB", "라마바", 100.0, 85.0)])
    ch = compute_changes(
        selected=later, previous=load_state(p, today_kst=TODAY), is_first_slot=False
    )
    assert [i.ticker for i in ch.new] == ["BBB"]
    assert ch.moved == []


def test_t7_band_move_is_a_change(tmp_path):
    p = _state_path(tmp_path)
    save_state(
        p,
        selected=_select([("AAA", "가나다", 100.0, 91.0)]),  # -9% D8_10
        slot_id="OPEN",
        today_kst=TODAY,
    )
    later = _select([("AAA", "가나다", 100.0, 88.0)])  # -12% D10_PLUS
    ch = compute_changes(
        selected=later, previous=load_state(p, today_kst=TODAY), is_first_slot=False
    )
    assert len(ch.moved) == 1
    item, before = ch.moved[0]
    assert before == {REASON_RECENT_DECLINE: STATE_D8_10}
    assert item.reasons[REASON_RECENT_DECLINE]["state"] == STATE_D10_PLUS


# --- T-8 정상 해소 ------------------------------------------------------------


def test_t8_resolved_ticker_is_a_change(tmp_path):
    p = _state_path(tmp_path)
    save_state(
        p,
        selected=_select([("AAA", "가나다", 100.0, 88.0)]),
        slot_id="OPEN",
        today_kst=TODAY,
    )
    later = _select([("AAA", "가나다", 100.0, 99.5)])  # -0.5% → 선정 해제
    ch = compute_changes(
        selected=later, previous=load_state(p, today_kst=TODAY), is_first_slot=False
    )
    assert ch.resolved == ["AAA"]
    assert ch.has_change is True


# --- T-10 secondary reason 만 변할 때 ----------------------------------------


def test_t10_secondary_reason_change_is_detected(tmp_path):
    """primary 가 그대로여도 다른 reason 의 state 가 바뀌면 변화다.

    `max_severity` 하나만 저장하면 이 케이스가 삼켜진다 — V1 의 결함이었다.
    """
    p = _state_path(tmp_path)
    before_items = _select([("AAA", "가나다", 100.0, 85.0)])  # D10_PLUS 만
    save_state(p, selected=before_items, slot_id="OPEN", today_kst=TODAY)

    after = _select([("AAA", "가나다", 100.0, 85.0)])
    # primary(RECENT_DECLINE:D10_PLUS) 는 그대로, 데이터 문제만 추가된다.
    after[0].reasons[REASON_DATA_UNAVAILABLE] = {"state": "ACTIVE", "value": None}

    ch = compute_changes(
        selected=after, previous=load_state(p, today_kst=TODAY), is_first_slot=False
    )
    assert len(ch.moved) == 1, "secondary reason 추가가 감지되지 않음"
    _, before = ch.moved[0]
    assert REASON_DATA_UNAVAILABLE not in before


# --- T-11 / T-12 발송 성공 후에만 상태 확정 ----------------------------------


def _simulate_slot(path, *, selected, send_ok: bool, slot_id: str):
    """러너 순서 재현: 변화 계산 → 발송 → 전체 성공일 때만 저장 (PLAN §4.6)."""
    previous = load_state(path, today_kst=TODAY)
    changes = compute_changes(
        selected=selected, previous=previous, is_first_slot=(slot_id == "OPEN")
    )
    if not changes.has_change:
        return "no_change"
    if not send_ok:
        return "send_failed"  # 상태 저장하지 않는다.
    save_state(path, selected=selected, slot_id=slot_id, today_kst=TODAY)
    return "sent"


def test_t11_total_send_failure_leaves_state_unchanged(tmp_path):
    p = _state_path(tmp_path)
    first = _select([("AAA", "가나다", 100.0, 91.0)])
    assert _simulate_slot(p, selected=first, send_ok=True, slot_id="OPEN") == "sent"
    snapshot = p.read_text(encoding="utf-8")

    moved = _select([("AAA", "가나다", 100.0, 85.0)])
    assert (
        _simulate_slot(p, selected=moved, send_ok=False, slot_id="MIDDAY")
        == "send_failed"
    )
    assert p.read_text(encoding="utf-8") == snapshot, "발송 실패인데 상태가 바뀌었다"


def test_t12_failed_slot_retries_same_change_next_slot(tmp_path):
    p = _state_path(tmp_path)
    _simulate_slot(
        p,
        selected=_select([("AAA", "가나다", 100.0, 91.0)]),
        send_ok=True,
        slot_id="OPEN",
    )
    moved = _select([("AAA", "가나다", 100.0, 85.0)])
    _simulate_slot(p, selected=moved, send_ok=False, slot_id="MIDDAY")

    # 다음 슬롯에서 같은 변화가 다시 잡혀야 한다 (미발송이 발송 완료로 기록되면 안 됨).
    ch = compute_changes(
        selected=moved, previous=load_state(p, today_kst=TODAY), is_first_slot=False
    )
    assert ch.has_change is True
    assert len(ch.moved) == 1


def test_open_zero_selection_saves_empty_state(tmp_path):
    """OPEN 선정 0건은 전달할 내용이 없으므로 빈 상태 저장을 허용한다."""
    p = _state_path(tmp_path)
    save_state(p, selected=[], slot_id="OPEN", today_kst=TODAY)
    st = load_state(p, today_kst=TODAY)
    assert st.comparable is True
    assert st.entries == {}


def test_save_state_is_atomic_and_leaves_no_tmp(tmp_path):
    p = _state_path(tmp_path)
    save_state(
        p,
        selected=_select([("AAA", "가나다", 100.0, 88.0)]),
        slot_id="OPEN",
        today_kst=TODAY,
    )
    assert p.exists()
    assert list(tmp_path.glob("*.tmp")) == []
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["schema_version"] == SCHEMA_VERSION
    # 보조 정보는 저장하지 않는다.
    assert "drawdown" not in json.dumps(raw)


# --- T-14 / T-15 장중 변화 (DB 고정 · 현재가만 이동) -------------------------


def test_t14_intraday_price_move_crosses_band_and_is_sent(tmp_path):
    """DB(분모)는 그대로 두고 runtime 현재가만 바꿔 구간을 넘기면 발송된다.

    분자를 당일 종가로 쓰면 OPEN·MIDDAY 가 같은 값이라 이 테스트가 성립하지 않는다.
    """
    p = _state_path(tmp_path)
    history = {"AAA": _history(100.0)}
    holdings = [{"ticker": "AAA", "name": "가나다"}]

    open_items = select_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes={"AAA": FakeQuote(current_price=91.0)},  # -9% D8_10
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    save_state(p, selected=open_items, slot_id="OPEN", today_kst=TODAY)

    midday_items = select_holdings(
        holdings=holdings,
        price_history=history,  # DB 동일
        market_quotes={"AAA": FakeQuote(current_price=88.0)},  # -12% D10_PLUS
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    ch = compute_changes(
        selected=midday_items,
        previous=load_state(p, today_kst=TODAY),
        is_first_slot=False,
    )
    assert ch.has_change is True
    assert len(ch.moved) == 1


def test_t15_intraday_move_within_same_band_is_suppressed(tmp_path):
    p = _state_path(tmp_path)
    history = {"AAA": _history(100.0)}
    holdings = [{"ticker": "AAA", "name": "가나다"}]

    open_items = select_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes={"AAA": FakeQuote(current_price=88.0)},  # -12%
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    save_state(p, selected=open_items, slot_id="OPEN", today_kst=TODAY)

    midday_items = select_holdings(
        holdings=holdings,
        price_history=history,
        market_quotes={"AAA": FakeQuote(current_price=86.0)},  # -14% 같은 구간
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert (
        midday_items[0].reasons[REASON_RECENT_DECLINE]["value"]
        != open_items[0].reasons[REASON_RECENT_DECLINE]["value"]
    )
    ch = compute_changes(
        selected=midday_items,
        previous=load_state(p, today_kst=TODAY),
        is_first_slot=False,
    )
    assert ch.has_change is False, "같은 구간인데 발송됨"


# --- §9.5 비거래일 가드 -------------------------------------------------------


def _quotes(*asof_dates):
    return {
        f"T{i}": FakeQuote(current_price=100.0, price_asof=f"{d}T15:30:00+09:00")
        for i, d in enumerate(asof_dates)
    }


def _sets(n_target, n_success=None, failed=()):
    """설계자 확정 계약의 집합 인자. 기본은 완전 수집."""
    target = [f"T{i}" for i in range(n_target)]
    success = [f"T{i}" for i in range(n_target if n_success is None else n_success)]
    return {
        "target_tickers": target,
        "success_tickers": success,
        "failed_tickers": list(failed),
    }


def test_t19_all_quotes_before_today_is_non_trading_day():
    q = _quotes(YESTERDAY, YESTERDAY, YESTERDAY)
    r = detect_non_trading_day(q, today_kst=TODAY, **_sets(3))
    assert r.is_non_trading_day is True
    assert r.max_price_asof == YESTERDAY
    assert r.evidence()["quote_count"] == 3


def test_t20_one_quote_traded_today_is_a_trading_day():
    """`any` 가 아니라 `all` 이다 — 한 종목이라도 오늘 체결값이면 거래일."""
    q = _quotes(YESTERDAY, YESTERDAY, TODAY)
    r = detect_non_trading_day(q, today_kst=TODAY, **_sets(3))
    assert r.is_non_trading_day is False
    assert r.reason == "traded_today"


def test_t21_incomplete_quotes_are_not_judged_as_non_trading_day():
    """조회 실패를 휴장일로 오인하지 않는다."""
    q = _quotes(YESTERDAY, YESTERDAY)
    r = detect_non_trading_day(q, today_kst=TODAY, **_sets(3, 2, failed=["T2"]))
    assert r.is_non_trading_day is False
    assert r.reason == "quote_incomplete"


def test_non_trading_day_with_zero_attempted_is_not_judged():
    r = detect_non_trading_day(
        {},
        today_kst=TODAY,
        target_tickers=[],
        success_tickers=[],
        failed_tickers=[],
    )
    assert r.is_non_trading_day is False


# --- 설계자 확정 2026-09-05 — 완전성은 **집합 일치** -------------------------


def test_completeness_uses_unique_ticker_sets_not_row_counts():
    """보유 행 수(32)와 고유 ticker 수(29)가 달라도 집합이 맞으면 완전 수집이다.

    `attempted`(행 수)를 분모로 쓰면 실패 0건인데도 가드가 죽는다 — 그 결함이
    전체 회귀를 통과했던 이력이 있다.
    """
    q = _quotes(*([YESTERDAY] * 29))
    r = detect_non_trading_day(q, today_kst=TODAY, **_sets(29))
    assert r.is_non_trading_day is True
    assert r.quote_count == 29


def test_same_count_but_different_tickers_is_not_complete():
    """건수만 같고 **다른 ticker** 가 섞이면 통과시키지 않는다 (설계자 명시)."""
    q = _quotes(*([YESTERDAY] * 3))
    r = detect_non_trading_day(
        q,
        today_kst=TODAY,
        target_tickers=["A", "B", "C"],
        success_tickers=["A", "B", "X"],  # 건수 3 동일, 집합 불일치
        failed_tickers=[],
    )
    assert r.is_non_trading_day is False
    assert r.reason == "quote_incomplete"


def test_success_superset_of_target_is_not_complete():
    """target 에 없는 ticker 가 성공 집합에 있으면 완전 수집이 아니다."""
    q = _quotes(*([YESTERDAY] * 3))
    r = detect_non_trading_day(
        q,
        today_kst=TODAY,
        target_tickers=["A", "B"],
        success_tickers=["A", "B", "C"],
        failed_tickers=[],
    )
    assert r.is_non_trading_day is False


def test_non_trading_day_real_shape_trading_day_is_not_skipped():
    q = _quotes(*([YESTERDAY] * 28 + [TODAY]))
    r = detect_non_trading_day(q, today_kst=TODAY, **_sets(29))
    assert r.is_non_trading_day is False


def test_non_trading_day_any_failure_blocks_judgement():
    q = _quotes(*([YESTERDAY] * 28))
    r = detect_non_trading_day(q, today_kst=TODAY, **_sets(29, 28, failed=["T28"]))
    assert r.is_non_trading_day is False
    assert r.reason == "quote_incomplete"


# --- 설계자 확정 2026-09-05 — 분모는 '기준일 그 날짜' 종가 ------------------
#
# 달력일 임계(`MAX_PRICE_STALE_DAYS = 7`)는 **폐기**됐다. "며칠 전인가" 가 아니라
# "정확한 기준일 데이터가 있는가" 로 판정한다.


def _axis_history(base: float = 100.0, *, drop: str | None = None):
    """축과 같은 날짜열의 이력. `drop` 이 있으면 그 날짜만 뺀다."""
    return [(d, base) for d in AXIS if d != drop]


def test_missing_reference_day_close_is_data_unavailable_not_a_decline():
    """기준일 종가가 없으면 하락 종목으로 선정하지 않는다.

    더 오래된 종가로 대체하면 20거래일이 아닌 구간의 수익률을 20거래일이라고
    보고하게 된다.
    """
    items = select_holdings(
        holdings=[{"ticker": "AAA", "name": "가나다"}],
        price_history={"AAA": _axis_history(drop=BASE_DAY)},
        market_quotes={"AAA": FakeQuote(current_price=88.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].reasons.keys() == {
        REASON_DATA_UNAVAILABLE
    }, f"기준일 종가가 없는데 {list(items[0].reasons)} 로 선정됐다"


def test_history_stopped_long_ago_has_no_reference_day_close():
    """이력이 오래전에 끊긴 종목 — 기준일 종가가 없으므로 제외된다.

    (개별주 시세 미갱신이 이 경로로 나타난다. BACKLOG `DEF-PRICE-EQUITY-REFRESH`)
    """
    stopped = [(d, 100.0) for d in AXIS[:5]]  # 축 앞부분에서 멈춤
    items = select_holdings(
        holdings=[{"ticker": "AAA", "name": "가나다"}],
        price_history={"AAA": stopped},
        market_quotes={"AAA": FakeQuote(current_price=88.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].reasons.keys() == {REASON_DATA_UNAVAILABLE}


def test_quote_asof_before_run_date_is_data_unavailable():
    """분자(현재가)의 체결일이 실행일이 아니면 그 종목만 뺀다."""
    items = select_holdings(
        holdings=[{"ticker": "AAA", "name": "가나다"}],
        price_history={"AAA": _axis_history()},
        market_quotes={
            "AAA": FakeQuote(current_price=88.0, price_asof="2026-09-03T15:30:00+09:00")
        },
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].reasons.keys() == {REASON_DATA_UNAVAILABLE}


def test_exact_reference_day_close_is_selected_normally():
    items = select_holdings(
        holdings=[{"ticker": "AAA", "name": "가나다"}],
        price_history={"AAA": _axis_history()},
        market_quotes={"AAA": FakeQuote(current_price=88.0)},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].reasons.keys() == {REASON_RECENT_DECLINE}
    assert items[0].reasons[REASON_RECENT_DECLINE]["state"] == STATE_D10_PLUS


def test_unparsable_asof_is_not_treated_as_today():
    """알 수 없는 기준시각을 정상으로 통과시키지 않는다 (fail-closed)."""
    items = select_holdings(
        holdings=[{"ticker": "AAA", "name": "가나다"}],
        price_history={"AAA": _axis_history()},
        market_quotes={"AAA": FakeQuote(current_price=88.0, price_asof="garbage")},
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].reasons.keys() == {REASON_DATA_UNAVAILABLE}


def test_future_asof_is_not_treated_as_today():
    """미래 시각 quote 는 DB/소스 오염이다 — 통과시키지 않는다."""
    items = select_holdings(
        holdings=[{"ticker": "AAA", "name": "가나다"}],
        price_history={"AAA": _axis_history()},
        market_quotes={
            "AAA": FakeQuote(current_price=88.0, price_asof="2026-12-31T15:30:00+09:00")
        },
        today_kst=TODAY,
        axis_dates=AXIS,
    )
    assert items[0].reasons.keys() == {REASON_DATA_UNAVAILABLE}


# --- 검증자 r1 지적 — 헤더 형식 -----------------------------------------------


def test_slot_and_asof_are_user_facing_format():
    """내부 식별자(`OPEN`)와 ISO 실행시각을 헤더에 그대로 노출하지 않는다."""
    from app.runtime_evidence.holdings_selection_flow import (
        format_quote_asof,
        slot_label_for,
    )

    assert slot_label_for("OPEN") == "09:15"
    assert slot_label_for("MIDDAY") == "12:30"
    assert slot_label_for("CLOSE") == "15:40"
    assert slot_label_for(None) == ""
    assert format_quote_asof("2026-09-04T09:14:03+09:00") == "2026-09-04 09:14"


# --- 검증자 r5 지적 — 대상 밖 ticker 의 Fail-Closed 우회 ---------------------


def test_out_of_target_today_quote_does_not_bypass_fail_closed():
    """대상 밖 ticker 의 오늘 시세가 불완전 수집 가드를 뚫으면 안 된다.

    검증자 r5 재현: `target={A,B,C}` · `success={A,B,X}` 에서 X 만 오늘 시세면
    집합 불일치(`quote_incomplete`)인데도 `blocked=None` 이 되어 정상 선정 경로로
    들어갔다. 보유하지도 않은 종목의 체결이 발송 여부를 정하면 안 된다.

    1차 판정(`detect_non_trading_day`)만 보면 못 잡는다 — **후속 가드까지** 본다.
    """
    from app.runtime_evidence.holdings_selection_flow import (
        check_incomplete_without_today,
        today_quote_exists,
    )

    mq = {
        "A": FakeQuote(current_price=100.0, price_asof=f"{YESTERDAY}T15:30:00+09:00"),
        "B": FakeQuote(current_price=100.0, price_asof=f"{YESTERDAY}T15:30:00+09:00"),
        "X": FakeQuote(current_price=100.0, price_asof=f"{TODAY}T09:14:00+09:00"),
    }
    target = ["A", "B", "C"]

    r = detect_non_trading_day(
        mq,
        today_kst=TODAY,
        target_tickers=target,
        success_tickers=["A", "B", "X"],
        failed_tickers=[],
    )
    assert r.reason == "quote_incomplete"

    assert today_quote_exists(mq, TODAY, target) is False, "대상 밖 시세를 셌다"
    blocked = check_incomplete_without_today(
        market_quotes=mq,
        today_kst=TODAY,
        skip_non_trading_day=r.is_non_trading_day,
        non_trading_day_reason=r.reason,
        target_tickers=target,
    )
    assert blocked is not None, "집합 불일치인데 Fail-Closed 를 우회했다"


def test_assemble_blocks_when_only_out_of_target_has_today_quote(tmp_path):
    """조립 진입점까지 연결해 확인한다 — 선정을 아예 시작하지 않아야 한다."""
    from app.runtime_evidence.holdings_selection_flow import assemble_holdings_push

    mq = {
        "A": FakeQuote(current_price=100.0, price_asof=f"{YESTERDAY}T15:30:00+09:00"),
        "X": FakeQuote(current_price=100.0, price_asof=f"{TODAY}T09:14:00+09:00"),
    }
    history_calls: list[str] = []

    def _history(ticker, **kw):
        history_calls.append(ticker)
        return [(d, 100.0) for d in AXIS]

    asm = assemble_holdings_push(
        market_quotes=mq,
        price_refresh_diag={
            "target_tickers": ["A", "B"],
            "success_tickers": ["A", "X"],
            "failed_tickers": [],
        },
        today_kst=TODAY,
        state_path=tmp_path / "s.json",
        slot_id="OPEN",
        runtime_kst=f"{TODAY}T09:15:00+09:00",
        holdings_loader=lambda: [],
        fetch_history=_history,
    )
    assert asm.fail is not None, "집합 불일치인데 조립이 통과했다"
    assert asm.fail[1] == "holdings_quotes_incomplete_no_today"
    assert asm.outcome is None
    assert history_calls == [], "차단돼야 하는데 종가 이력을 조회했다"


def test_target_tickers_is_required_and_fails_loud():
    """필수 대상 집합 누락은 **조용히 넘기지 않는다** (검증자 r6 B-1).

    기본값 `None` 을 두면 인자를 빠뜨린 호출이 "전체 시세를 훑는" 과거의 위험한
    동작으로 조용히 되돌아간다. 그 동작이 r5 에서 실제로 Fail-Closed 가드를
    뚫었다. fallback 금지 — 누락은 즉시 실패다.
    """
    import inspect

    import pytest

    from app.runtime_evidence.holdings_selection_flow import (
        check_incomplete_without_today,
        today_quote_exists,
    )

    mq = {"X": FakeQuote(current_price=100.0, price_asof=f"{TODAY}T09:14:00+09:00")}

    # 기본값이 없어야 한다 — 있으면 누락이 조용히 통과한다.
    for fn, param in (
        (today_quote_exists, "target_tickers"),
        (check_incomplete_without_today, "target_tickers"),
    ):
        sig = inspect.signature(fn)
        assert (
            sig.parameters[param].default is inspect.Parameter.empty
        ), f"{fn.__name__}({param}=...) 에 기본값이 생겼다 — fallback 금지"

    with pytest.raises(TypeError):
        today_quote_exists(mq, TODAY)  # 인자 생략

    with pytest.raises(ValueError):
        today_quote_exists(mq, TODAY, None)  # 명시적 None

    # ⚠️ **모든 분기**에서 실패해야 한다. 검증이 조기 반환 뒤에 있으면
    # `skip_non_trading_day=True` 와 `traded_today` 두 경로가 None 을 그대로
    # 통과시킨다 — 검증자 r7 이 실제로 재현했다. 한 분기만 검사하면 못 잡는다.
    for skip, reason in (
        (False, "quote_incomplete"),
        (True, "all_quotes_before_today"),
        (False, "traded_today"),
        (False, "asof_missing"),
    ):
        with pytest.raises(ValueError, match="target_tickers"):
            check_incomplete_without_today(
                market_quotes=mq,
                today_kst=TODAY,
                skip_non_trading_day=skip,
                non_trading_day_reason=reason,
                target_tickers=None,
            )


def test_flow_carries_buy_price_into_message(tmp_path):
    """**흐름 전체**를 통과해 본문에 매입 대비가 실제로 실리는지 본다.

    선정기 단위 테스트만 있으면 `build_holdings_selection` 이 `avg_buy_prices`
    를 안 넘겨도 아무도 못 잡는다(역검증 P-6 이 실제로 미탐지였다). 보유 원장의
    `avg_buy_price` 가 최종 Telegram 본문까지 도달하는 경로를 고정한다.
    """
    from dataclasses import dataclass

    from app.runtime_evidence.holdings_selection_flow import build_holdings_selection

    @dataclass
    class H:
        ticker: str
        name: str
        account_group: str = "일반"
        quantity: float = 10.0
        avg_buy_price: float = 50.0

    out = build_holdings_selection(
        holdings_loader=lambda: [H("AAA", "가나다")],
        fetch_history=lambda t, **kw: [(d, 100.0) for d in AXIS],
        market_quotes={"AAA": FakeQuote(current_price=80.0)},
        state_path=tmp_path / "s.json",
        slot_id="OPEN",
        runtime_kst=f"{TODAY}T09:15:00+09:00",
        today_kst=TODAY,
    )
    assert not out.error, out.error
    assert out.message_text, "본문이 비었다"
    # 80 / 50 - 1 = +60.0%
    assert "매입대비 +60.0%" in out.message_text, out.message_text
    assert "20거래일 -20.0%" in out.message_text


def test_flow_multi_account_uses_weighted_buy_price(tmp_path):
    """다계좌는 흐름에서도 **수량 가중평균**으로 합쳐진다."""
    from dataclasses import dataclass

    from app.runtime_evidence.holdings_selection_flow import build_holdings_selection

    @dataclass
    class H:
        ticker: str
        name: str
        account_group: str
        quantity: float
        avg_buy_price: float

    rows = [
        H("AAA", "가나다", "일반", 1.0, 100.0),
        H("AAA", "가나다", "ISA", 9.0, 50.0),
    ]
    out = build_holdings_selection(
        holdings_loader=lambda: rows,
        fetch_history=lambda t, **kw: [(d, 100.0) for d in AXIS],
        market_quotes={"AAA": FakeQuote(current_price=80.0)},
        state_path=tmp_path / "s.json",
        slot_id="OPEN",
        runtime_kst=f"{TODAY}T09:15:00+09:00",
        today_kst=TODAY,
    )
    assert not out.error, out.error
    # 가중평균 = (100*1 + 50*9)/10 = 55 → 80/55-1 = +45.5%
    assert "매입대비 +45.5%" in out.message_text, out.message_text
    assert "(2개 계좌)" in out.message_text
