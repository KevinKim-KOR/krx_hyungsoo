"""POC3-02D-OPS-02 §3-3 — 정기 PUSH 발송 계약 · 러너 `run()` 관통.

2026-09-18 `02C-OPS-01` 배포부터 정기 PUSH(시장 브리핑 · 보유 브리핑)는 내용이
같아도 거래일 · 슬롯마다 보낸다. fingerprint · `content_unchanged` 는 기록만 한다.
'같은 내용 반복'과 관계된 차단은 둘뿐이다(비거래일 · 선정 0건 · 전체 stale · flag off
같은 다른 미발송 사유는 그대로다).

| 막는 것 | 누가 |
|---|---|
| 같은 날 · 같은 슬롯 재실행 | registry 키 — 시장 = 날짜 · 보유 = 날짜#슬롯 |
| 사건형 위험 알림의 같은 위험 | `worst_state` (`no_new_or_worsened`) |

시장 브리핑은 `scripts/ops02b2/reverse_verify_guards.py` ⑦-a · ⑦-b 가 모듈
수준에서도 본다. 여기서는 러너를 실제로 태운다.

## 격리

conftest autouse 가드가 라이브 state · DB 를 막는다. 상태 경로는 `tmp_path`,
Telegram 은 대역, 실행 시각(`kst_now_iso`)은 고정한다 — 같은 분에 두 번 돌면
분 단위 키와 일 단위 키가 구분되지 않아 테스트가 무력해진다.
"""

from __future__ import annotations

import sys
import types
from datetime import date, timedelta

from app.three_push_runtime_message_builder import kst_today_date
from tests.low_frequency_push._fixtures import (
    _install_common_mocks,
    _seed_and_get_param,
    _stub_holdings_selection_inputs,
)
from tests.test_holdings_risk_alert_runner import (
    RISK_KIND,
    _asof,
    _install_inputs,
    _install_runner,
    _seed_param,
    _tick,
)
from tests.test_market_briefing_flow_through import TODAY_TRADING
from tests.test_market_briefing_flow_through import _advance_window
from tests.test_market_briefing_flow_through import _install as _install_market

HOLDINGS = "holdings_briefing"
MARKET = "market_briefing"


def _at(monkeypatch, runner, day: str, hhmm: str) -> None:
    """실행 시각 고정. 중복 키의 날짜는 `kst_today_date`, 시각은 여기서 온다."""
    monkeypatch.setattr(runner, "kst_now_iso", lambda: f"{day}T{hhmm}:00+09:00")


def _holdings_rig(monkeypatch, tmp_path):
    """보유 1종목 · 20거래일 -12% → 선정 1건. 슬롯마다 **같은 입력**이다.

    입력은 `test_holdings_runner_message_uses_user_facing_header` 와 같다.
    """
    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    state = tmp_path / "sel.json"
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", state)
    today = kst_today_date()
    _stub_holdings_selection_inputs(
        monkeypatch, runner, quotes_asof=f"{today}T09:14:00+09:00"
    )
    import app.market_data_store as store_mod

    end = date.fromisoformat(today)
    # POC3-02D-OPS-03 — 20거래일 기준일은 거래일 캘린더로 정한다. 휴장일이 끼어도
    # 기준일 종가가 있도록 달력일 45일을 둔다(예전 30일은 저장 가격 축 기준이었다).
    rows = [((end - timedelta(days=44 - i)).isoformat(), 100.0) for i in range(45)]
    rows[-1] = (rows[-1][0], 88.0)
    monkeypatch.setattr(store_mod, "fetch_price_history", lambda t, **kw: rows)

    class _Q:
        current_price = 88.0
        price_asof = f"{today}T09:14:00+09:00"

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = _Q()

    fake = types.ModuleType("app.market_naver")
    fake.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fake.fetch_many)

    sent: list[str] = []

    def _send(text, *a, **kw):
        sent.append(text)
        return True, "", False

    monkeypatch.setattr(runner, "telegram_send", _send)
    return runner, sent, state, today


def _holdings_slot(monkeypatch, runner, today, slot_id, hhmm):
    _at(monkeypatch, runner, today, hhmm)
    return runner.run(HOLDINGS, "send", slot_id=slot_id)


# ── 보유 브리핑 — 고정 슬롯마다 발송 · 같은 슬롯 재실행만 차단 ──────────────


def test_holdings_midday_sends_even_if_unchanged_after_open(monkeypatch, tmp_path):
    """(a) OPEN 발송 뒤 같은 입력의 MIDDAY 도 보낸다 — `content_unchanged` 기록만."""
    runner, sent, _, today = _holdings_rig(monkeypatch, tmp_path)

    opened = _holdings_slot(monkeypatch, runner, today, "OPEN", "09:15")
    assert opened["status"] == "sent", opened
    assert opened["content_unchanged"] is False  # OPEN 은 전체 상태 = 변화 있음

    mid = _holdings_slot(monkeypatch, runner, today, "MIDDAY", "12:30")

    assert mid["status"] == "sent", f"실제 {mid['status']}/{mid['reason']}"
    assert mid["content_unchanged"] is True, "같은 입력인데 변화로 판정했다"
    assert mid["reason"] != "no_change"
    assert mid["duplicate_key"].endswith("#MIDDAY"), mid["duplicate_key"]
    assert len(sent) == 2, "내용이 같다는 이유로 MIDDAY 가 빠졌다"
    # 변화분이 아니라 현재 상태 전체를 보낸다.
    assert "20거래일 하락 10% 이상" in sent[1]


def test_holdings_same_midday_rerun_is_duplicate_blocked(monkeypatch, tmp_path):
    """(b) 같은 MIDDAY 재실행은 registry 가 막는다 · 발송 0 · 선정 상태 불변.

    재실행은 **다른 분(12:35)** 에 돈다. 슬롯 키가 분 단위로 바뀌면 통과해
    버리므로 여기서 깨진다.
    """
    runner, sent, state, today = _holdings_rig(monkeypatch, tmp_path)
    opened = _holdings_slot(monkeypatch, runner, today, "OPEN", "09:15")
    assert opened["status"] == "sent", opened
    first = _holdings_slot(monkeypatch, runner, today, "MIDDAY", "12:30")
    assert first["status"] == "sent", first
    snapshot = state.read_bytes()

    again = _holdings_slot(monkeypatch, runner, today, "MIDDAY", "12:35")

    assert again["status"] == "skipped", again
    assert again["reason"] == "duplicate_runtime", f"실제 {again['reason']}"
    assert again["duplicate_key"] == first["duplicate_key"]
    assert len(sent) == 2, "같은 슬롯을 두 번 보냈다"
    assert state.read_bytes() == snapshot, "중복 차단인데 선정 상태가 바뀌었다"


def test_holdings_close_after_midday_is_not_blocked(monkeypatch, tmp_path):
    """(c) MIDDAY 뒤 CLOSE 는 막히지 않는다 — 키가 슬롯별(`#CLOSE`)이다."""
    runner, sent, _, today = _holdings_rig(monkeypatch, tmp_path)
    opened = _holdings_slot(monkeypatch, runner, today, "OPEN", "09:15")
    assert opened["status"] == "sent", opened
    mid = _holdings_slot(monkeypatch, runner, today, "MIDDAY", "12:30")
    assert mid["status"] == "sent", mid

    close = _holdings_slot(monkeypatch, runner, today, "CLOSE", "15:40")

    assert close["status"] == "sent", f"실제 {close['status']}/{close['reason']}"
    assert close["content_unchanged"] is True
    assert close["duplicate_key"].endswith("#CLOSE"), close["duplicate_key"]
    assert len(sent) == 3


# ── 위험 알림 — 사건형 억제는 그대로 ────────────────────────────────────────


def test_risk_alert_second_tick_same_risk_is_suppressed(monkeypatch, tmp_path):
    """(d) 같은 위험이 두 번째 틱에 그대로면 `no_new_or_worsened` 로 막는다.

    첫 틱과 **같은 입력 그대로**다 — 정기 PUSH 의 '내용이 같아도 발송' 이
    사건형 알림으로 새면 여기서 깨진다. 틱 시각이 달라 registry 키(`#HH:MM`)는
    막지 않는다.
    """
    today = kst_today_date()
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    spec = [("102110", "TIGER200", 10000.0, 9200.0)]  # -8.0%
    _install_inputs(monkeypatch, runner, specs=spec, quotes_asof=_asof(today, "10:30"))
    _tick(monkeypatch, runner, today, "10:30")
    first = runner.run(RISK_KIND, "send")
    assert first["status"] == "sent", first

    _install_inputs(monkeypatch, runner, specs=spec, quotes_asof=_asof(today, "11:30"))
    _tick(monkeypatch, runner, today, "11:30")
    second = runner.run(RISK_KIND, "send")

    assert second["status"] == "skipped", second
    assert second["reason"] == "no_new_or_worsened", f"실제 {second['reason']}"
    assert len(send.calls) == 1, "같은 위험을 다시 보냈다"


# ── 시장 브리핑 — 다음 거래일 발송 · 같은 날 재실행 차단 ─────────────────────


def test_market_next_day_same_fp_sends_and_same_day_rerun_is_duplicate(
    tmp_path, monkeypatch
):
    """(e) 08:00 발송 → 08:05 재실행 `duplicate_runtime` → 다음 거래일 같은 fp 발송."""
    runner, sent, state_dir = _install_market(monkeypatch, tmp_path)
    _at(monkeypatch, runner, TODAY_TRADING, "08:00")
    first = runner.run(MARKET, "send")
    assert first["status"] == "sent", first

    _at(monkeypatch, runner, TODAY_TRADING, "08:05")
    rerun = runner.run(MARKET, "send")
    assert rerun["status"] == "skipped", rerun
    assert rerun["reason"] == "duplicate_runtime", f"실제 {rerun['reason']}"
    assert len(sent) == 1, "같은 날 두 번 보냈다"

    monkeypatch.setattr(runner, "kst_today_date", lambda: "2026-09-21")
    _at(monkeypatch, runner, "2026-09-21", "08:00")
    # POC3-02D-OPS-03 확정 계약 6 — 다음 거래일은 그날 T-1(09-18)이 적재 · 판정돼야
    # 같은 fingerprint 가 나온다(옛 lag ≤ 1 은 전날 창을 받아 줬다).
    _advance_window(tmp_path, state_dir)
    nxt = runner.run(MARKET, "send")

    assert nxt["status"] == "sent", f"실제 {nxt['status']}/{nxt['reason']}"
    assert nxt["content_unchanged"] is True
    fp = nxt["state_fingerprint"]
    assert fp, "fingerprint 가 비었다 — None 끼리 비교하면 공허하다"
    assert nxt["previous_fingerprint"] == fp
    assert len(sent) == 2, "다음 거래일인데 같은 fingerprint 라서 빠졌다"
