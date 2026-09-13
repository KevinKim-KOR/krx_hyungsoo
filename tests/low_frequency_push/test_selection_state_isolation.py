"""POC3-OPS-01A — 선정 상태가 라이브 경로에 새지 않는가.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

import json

import sys

from tests.low_frequency_push._fixtures import (
    _install_common_mocks,
    _seed_and_get_param,
    _stub_holdings_selection_inputs,
)


def test_holdings_selection_state_never_written_to_live_path(monkeypatch, tmp_path):
    """상태 저장은 주입된 경로에만 일어나고 라이브 경로는 건드리지 않는다."""
    from app.three_push_runtime_message_builder import kst_today_date

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    live_path = runner.HOLDINGS_SELECTION_STATE_PATH
    injected = tmp_path / "selection_state.json"
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", injected)
    _stub_holdings_selection_inputs(
        monkeypatch, runner, quotes_asof=f"{kst_today_date()}T09:14:00+09:00"
    )

    live_existed = live_path.exists()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["status"] == "skipped"
    assert rec["reason"] == "no_selection", f"실제 {rec['reason']}"
    assert injected.exists(), "주입 경로에 빈 상태가 저장돼야 한다"
    if not live_existed:
        assert not live_path.exists(), "라이브 상태 경로가 생성됐다"


def test_holdings_non_trading_day_skips_without_touching_state(monkeypatch, tmp_path):
    """비거래일이면 발송·상태 저장 모두 하지 않는다 (29종목 경고도 없다)."""
    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    injected = tmp_path / "selection_state.json"
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", injected)
    _stub_holdings_selection_inputs(
        monkeypatch, runner, quotes_asof="2020-01-02T15:30:00+09:00"
    )
    calls: list[str] = []
    monkeypatch.setattr(
        runner,
        "telegram_send",
        lambda text, *a, **kw: (calls.append(text), (True, "", False))[1],
    )

    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["status"] == "skipped"
    assert rec["reason"] == "non_trading_day", f"실제 {rec['reason']}"
    assert calls == [], "비거래일인데 Telegram 을 호출했다"
    assert not injected.exists(), "비거래일에 상태를 저장했다"
    assert rec["non_trading_day_evidence"]["max_price_asof"] == "2020-01-02"


def test_t21_non_trading_day_produces_no_stale_judgment(monkeypatch, tmp_path):
    """T-21 — 휴장일에는 `DATA_UNAVAILABLE_OR_STALE` 판정을 만들지 않는다.

    검증자 r2 지적: 기존 T-21 은 `detect_non_trading_day` 의 불완전 quote 처리만
    봤다. 정작 확인해야 할 계약은 **휴장일에 정상 종목이 데이터 지연으로 분류되지
    않는다**는 것이다.

    휴장일이면 종가 이력 조회 자체가 돌 이유가 없으므로, `fetch_price_history`
    호출 0건까지 함께 고정한다. 선정이 비거래일 판정보다 **먼저** 돌면 이 테스트가
    깨진다.
    """
    import app.market_data_store as store_mod

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    injected = tmp_path / "selection_state.json"
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", injected)
    # 전 종목 시세가 과거 일자 → 휴장일.
    _stub_holdings_selection_inputs(
        monkeypatch, runner, quotes_asof="2020-01-02T15:30:00+09:00"
    )
    history_calls: list[str] = []
    real_history = store_mod.fetch_price_history

    def _tracking_history(ticker, **kw):
        history_calls.append(ticker)
        return real_history(ticker, **kw)

    monkeypatch.setattr(store_mod, "fetch_price_history", _tracking_history)
    monkeypatch.setattr(
        runner, "telegram_send", lambda text, *a, **kw: (True, "", False)
    )

    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["reason"] == "non_trading_day", f"실제 {rec['reason']}"
    assert history_calls == [], (
        "휴장일인데 종가 이력을 조회했다 — 선정이 비거래일 판정보다 먼저 돌았다: "
        f"{history_calls}"
    )
    blob = json.dumps(rec, ensure_ascii=False, default=str)
    assert (
        "DATA_UNAVAILABLE_OR_STALE" not in blob
    ), "휴장일에 데이터 지연 판정을 만들었다"
    assert rec.get("holdings_selected_count") in (None, 0)


def test_holdings_partial_delivery_does_not_save_selection_state(monkeypatch, tmp_path):
    """부분 발송 실패면 선정 상태를 저장하지 않는다 (PLAN §4.6).

    미발송 신호가 발송 완료로 기록되면 다음 슬롯에서 그 변화가 영영 사라진다.
    중복은 허용하고 누락은 허용하지 않는다.
    """
    from app.three_push_runtime_message_builder import kst_today_date

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    injected = tmp_path / "selection_state.json"
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", injected)
    _stub_holdings_selection_inputs(
        monkeypatch, runner, quotes_asof=f"{kst_today_date()}T09:14:00+09:00"
    )
    # 20거래일 -12% → 선정 1건.
    import app.market_data_store as store_mod

    rows = [(f"2026-08-{i + 1:02d}", 100.0) for i in range(30)]
    rows[-1] = (rows[-1][0], 88.0)
    monkeypatch.setattr(store_mod, "fetch_price_history", lambda t, **kw: rows)

    class _Q:
        current_price = 88.0
        price_asof = f"{kst_today_date()}T09:14:00+09:00"

    import types as _t

    fake = _t.ModuleType("app.market_naver")

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = _Q()

    fake.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fake.fetch_many)

    # chunk 일부만 전달된 상태로 반환.
    monkeypatch.setattr(runner, "telegram_send", lambda *a, **kw: (True, "", True))

    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["telegram_partial_delivery"] is True
    assert not injected.exists(), "부분 발송 실패인데 선정 상태를 저장했다"


def test_holdings_runner_message_uses_user_facing_header(monkeypatch, tmp_path):
    """러너를 **실제로 통과한** 본문의 헤더 형식을 고정한다.

    preview 와 운영 본문은 서로 다른 경로다 — preview 통과가 운영 통과를
    보장하지 않는다(검증자 지적). 내부 식별자(`OPEN`)와 ISO 실행시각을
    그대로 노출하면 안 된다.
    """
    from app.three_push_runtime_message_builder import kst_today_date

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", tmp_path / "sel.json")
    today = kst_today_date()
    _stub_holdings_selection_inputs(
        monkeypatch, runner, quotes_asof=f"{today}T09:14:00+09:00"
    )
    import app.market_data_store as store_mod

    import datetime as _dt

    end = _dt.date.fromisoformat(today)
    rows = [((end - _dt.timedelta(days=29 - i)).isoformat(), 100.0) for i in range(30)]
    rows[-1] = (rows[-1][0], 88.0)
    monkeypatch.setattr(store_mod, "fetch_price_history", lambda t, **kw: rows)

    class _Q:
        current_price = 88.0
        price_asof = f"{today}T09:14:00+09:00"

    import types as _t

    fake = _t.ModuleType("app.market_naver")

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = _Q()

    fake.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fake.fetch_many)

    sent_texts: list[str] = []

    def _capture(text, *a, **kw):
        sent_texts.append(text)
        return True, "", False

    monkeypatch.setattr(runner, "telegram_send", _capture)

    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["status"] == "sent", f"실제 {rec['status']}/{rec['reason']}"
    assert len(sent_texts) == 1
    body = sent_texts[0]
    assert "09:15" in body, "슬롯 시각 표기가 없다"
    assert "OPEN" not in body, "내부 슬롯 식별자가 노출됐다"
    assert "+09:00" not in body, "ISO 실행시각이 그대로 노출됐다"
    assert "T0" not in body.split("\n")[1], "ISO 형식 잔존"
    assert "20거래일 하락 10% 이상" in body
    # 면책·운영 설명 없음.
    for phrase in ("매도·교체·비중 조절", "매매 지시", "이 알림은"):
        assert phrase not in body
