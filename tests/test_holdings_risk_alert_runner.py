"""POC3-OPS-02A — 러너 **흐름 통과** test.

단위 테스트만 있으면 배선이 끊겨도 못 잡는다(OPS-01A 에서 `avg_buy_prices` 배선
유실이 실제로 미탐지였다 — PLAN §5 역검증 운영 규칙).

여기서는 `scripts.run_three_push_runtime_oci.run()` 을 **실제로 통과**시키고
본문·기록·상태 저장을 고정한다.

- **Telegram 발송 0건** — `telegram_send` 를 mock 으로 갈아끼운다.
- **라이브 state 미접근** — 상태 경로는 `tmp_path` 로 주입한다.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from app.runtime_evidence.holdings_risk import (
    STATE_D5_7,
    STATE_D7_10,
    STATE_D10_PLUS,
)
from app.runtime_evidence.holdings_risk_state import SCHEMA_VERSION

RISK_KIND = "holdings_risk_alert"
RISK_FLAG = "PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED"


def _seed_param():
    from app.runtime_param_store import activate_param_version, create_param_version
    from app.three_push_runtime_param import build_manual_seed_param

    p = build_manual_seed_param()
    assert p.is_push_kind_enabled(RISK_KIND), "PARAM 이 위험 알림을 안 켠다"
    vid, _, _ = create_param_version(p.to_dict())
    activate_param_version(vid, activated_by="test")
    return p


class _Sender:
    """발송 mock. 실제 Telegram 호출 0건임을 본문과 함께 고정한다."""

    def __init__(self, sent=True, partial=False):
        self.calls: list[str] = []
        self._sent, self._partial = sent, partial

    def __call__(self, text, *a, **kw):
        self.calls.append(text)
        return (self._sent, "" if self._sent else "mock 실패", self._partial)


def _install_runner(monkeypatch, tmp_path, *, sender=None, flag="true"):
    import scripts.run_three_push_runtime_oci as runner

    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setattr(
        runner, "HOLDINGS_RISK_STATE_PATH", tmp_path / "risk_state.json"
    )
    monkeypatch.setattr(
        runner, "HOLDINGS_SELECTION_STATE_PATH", tmp_path / "selection_state.json"
    )
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    monkeypatch.setenv(RISK_FLAG, flag)
    send = sender if sender is not None else _Sender()
    monkeypatch.setattr(runner, "telegram_send", send)
    return runner, send


def _install_inputs(monkeypatch, runner, *, specs, quotes_asof, axis_end=None):
    """보유 원장·종가 이력·Naver 시세를 통제. 외부 조회 0건.

    specs: [(ticker, name, 직전거래일 종가, 현재가)]
    """
    from dataclasses import dataclass

    import app.holdings as holdings_mod
    import app.market_data_store as store_mod
    from app.three_push_runtime_message_builder import kst_today_date

    @dataclass
    class _H:
        ticker: str
        name: str
        account_group: str = "일반"

    @dataclass
    class _Q:
        current_price: float
        price_asof: str

    today = kst_today_date()
    # 실행일 **이전** 거래일 축. 축 마지막이 직전 거래일이 된다.
    axis = _axis_before(today) if axis_end is None else axis_end

    rows = {t: [(d, base) for d in axis] for t, _, base, _ in specs}
    # 거래일 축 ticker(KODEX200)는 보유에 없어도 이력을 줘야 한다 — 없으면 축이
    # 비어 직전 거래일을 못 잡고 전 종목이 데이터 확인 대상이 된다.
    from app.runtime_evidence.holdings_selection import TRADING_DAY_AXIS_TICKER

    rows.setdefault(TRADING_DAY_AXIS_TICKER, [(d, 10000.0) for d in axis])
    monkeypatch.setattr(
        holdings_mod, "load", lambda *a, **k: [_H(t, n) for t, n, _, _ in specs]
    )
    monkeypatch.setattr(
        store_mod, "fetch_price_history", lambda t, **kw: rows.get(t, [])
    )
    monkeypatch.setattr(
        runner, "_collect_target_tickers", lambda pk: [t for t, _, _, _ in specs]
    )

    cur = {t: c for t, _, _, c in specs}
    fake = types.ModuleType("app.market_naver")

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = _Q(current_price=cur[t], price_asof=quotes_asof)

    fake.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fake.fetch_many)
    return axis


def _axis_before(today: str) -> list[str]:
    """실행일 직전 30 거래일 (합성). 축 마지막 = 직전 거래일."""
    from datetime import date, timedelta

    d = date.fromisoformat(today)
    out: list[str] = []
    step = 1
    while len(out) < 30:
        c = d - timedelta(days=step)
        if c.weekday() < 5:
            out.append(c.isoformat())
        step += 1
    return sorted(out)


@pytest.fixture
def today():
    from app.three_push_runtime_message_builder import kst_today_date

    return kst_today_date()


def _asof(today, hhmm="10:30"):
    return f"{today}T{hhmm}:00+09:00"


def _tick(monkeypatch, runner, today, hhmm):
    """실행 시각을 고정한다.

    중복 가드 키의 슬롯 접미는 **실행 시각 `HH:MM`** 이라(같은 틱 재실행만 막고
    악화 재발송은 통과시키는 계약), 여러 틱을 흉내내려면 시각을 밀어야 한다.
    """
    monkeypatch.setattr(runner, "kst_now_iso", lambda: _asof(today, hhmm))


# ── 흐름 통과 · 배선 ─────────────────────────────────────────────────────────


def test_runner_sends_risk_alert_with_all_three_metrics(monkeypatch, tmp_path, today):
    """러너를 실제로 통과한 본문에 trigger + 보조 2종이 모두 들어 있다.

    보조 정보가 조립 단계에서 유실되면(OPS-01A 에서 실제로 겪었다) 여기서 깨진다.
    """
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today),
    )
    # flow 모듈이 이미 이름을 바인딩했으므로 **그 이름**을 갈아끼워야 한다.
    monkeypatch.setattr(
        "app.runtime_evidence.holdings_risk_flow.average_buy_prices",
        lambda rows: {"102110": 8000.0},
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent", rec
    assert len(send.calls) == 1
    body = send.calls[0]
    assert "TIGER200" in body
    assert "전일 대비 -8.0%" in body
    assert "고점 대비" in body
    assert "매입대비 +15.0%" in body
    # 1종목이면 "동시" 를 붙이지 않는다 (사용자 지시 2026-09-07).
    assert "[보유 급락 알림] " in body
    assert "보유 1종목 중 1종목 하락" in body
    assert "동시" not in body


def test_runner_state_file_written_only_after_send(monkeypatch, tmp_path, today):
    """R-10 — 발송 실패면 state 를 저장하지 않는다."""
    _seed_param()
    runner, _ = _install_runner(monkeypatch, tmp_path, sender=_Sender(sent=False))
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "failed"
    assert rec["reason"] == "telegram_send_error"
    assert not (tmp_path / "risk_state.json").exists(), "미발송인데 state 를 저장했다"


def test_runner_partial_delivery_does_not_save_state(monkeypatch, tmp_path, today):
    """부분 전달도 state 를 확정하지 않는다 (OPS-01A 와 같은 계약)."""
    _seed_param()
    runner, _ = _install_runner(monkeypatch, tmp_path, sender=_Sender(partial=True))
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["telegram_partial_delivery"] is True
    assert not (tmp_path / "risk_state.json").exists()


def test_runner_saves_worst_state_after_send(monkeypatch, tmp_path, today):
    _seed_param()
    runner, _ = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 8800.0)],  # -12.0%
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent"
    saved = json.loads((tmp_path / "risk_state.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == SCHEMA_VERSION
    assert saved["kst_date"] == today
    assert saved["entries"] == {"102110": {"worst_state": STATE_D10_PLUS}}


# ── R-5 / R-6 억제 — 러너 2회 연속 실행 ──────────────────────────────────────


def test_runner_second_tick_same_band_is_suppressed(monkeypatch, tmp_path, today):
    """같은 구간이면 두 번째 틱에서 발송하지 않는다 (registry 가 아니라 상태 계약)."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today, "10:30"),
    )
    _tick(monkeypatch, runner, today, "10:30")
    first = runner.run(RISK_KIND, "send")
    assert first["status"] == "sent"

    # 두 번째 틱 — 같은 구간(-8.5% 도 D7_10).
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9150.0)],
        quotes_asof=_asof(today, "11:30"),
    )
    _tick(monkeypatch, runner, today, "11:30")
    second = runner.run(RISK_KIND, "send")

    assert second["status"] == "skipped"
    assert second["reason"] == "no_new_or_worsened"
    assert len(send.calls) == 1, "같은 구간인데 재발송했다"


def test_runner_worsening_resends_same_day(monkeypatch, tmp_path, today):
    """악화는 같은 날에도 재발송한다 — 일 단위 중복키면 여기서 막힌다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9400.0)],  # -6.0 → D5_7
        quotes_asof=_asof(today, "10:30"),
    )
    _tick(monkeypatch, runner, today, "10:30")
    assert runner.run(RISK_KIND, "send")["status"] == "sent"

    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 8800.0)],  # -12.0 → D10_PLUS
        quotes_asof=_asof(today, "11:30"),
    )
    _tick(monkeypatch, runner, today, "11:30")
    second = runner.run(RISK_KIND, "send")

    assert second["status"] == "sent", second
    assert len(send.calls) == 2
    # 그룹 헤더는 악화 후 구간, 줄 끝 전이 표기는 `이전 → 현재`.
    assert "■ 전일 대비 하락 10% 이상" in send.calls[1]
    assert "(5~7% → 10% 이상)" in send.calls[1]


def test_runner_same_tick_rerun_is_duplicate_blocked(monkeypatch, tmp_path, today):
    """같은 틱을 두 번 돌리면 registry 중복 가드가 막는다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today, "10:30"),
    )
    _tick(monkeypatch, runner, today, "10:30")
    first = runner.run(RISK_KIND, "send")
    assert first["status"] == "sent"
    assert first["duplicate_key"].endswith("#10:30"), first["duplicate_key"]

    # 상태를 지워 "신규" 로 만들어도 registry 가 같은 틱을 막아야 한다.
    (tmp_path / "risk_state.json").unlink()
    second = runner.run(RISK_KIND, "send")

    assert second["status"] == "skipped"
    assert second["reason"] == "duplicate_runtime"
    assert len(send.calls) == 1


def test_runner_easing_is_not_sent(monkeypatch, tmp_path, today):
    """R-3 — 완화는 발송하지 않는다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 8800.0)],  # D10_PLUS
        quotes_asof=_asof(today, "10:30"),
    )
    _tick(monkeypatch, runner, today, "10:30")
    assert runner.run(RISK_KIND, "send")["status"] == "sent"

    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9400.0)],  # D5_7 로 완화
        quotes_asof=_asof(today, "11:30"),
    )
    _tick(monkeypatch, runner, today, "11:30")
    second = runner.run(RISK_KIND, "send")

    assert second["status"] == "skipped"
    assert second["reason"] == "no_new_or_worsened"
    assert len(send.calls) == 1


def test_runner_reentry_after_easing_same_day_is_suppressed(
    monkeypatch, tmp_path, today
):
    """R-6 — 완화 후 같은 날 재진입도 발송하지 않는다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    for hhmm, price in (("10:30", 8800.0), ("11:30", 9800.0), ("12:30", 8850.0)):
        _install_inputs(
            monkeypatch,
            runner,
            specs=[("102110", "TIGER200", 10000.0, price)],
            quotes_asof=_asof(today, hhmm),
        )
        _tick(monkeypatch, runner, today, hhmm)
        runner.run(RISK_KIND, "send")

    assert len(send.calls) == 1, "완화 후 재진입을 재발송했다"


def test_runner_new_ticker_later_in_day_is_sent(monkeypatch, tmp_path, today):
    """나중 틱에서 처음 진입한 종목은 신규로 발송한다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("102110", "TIGER200", 10000.0, 9200.0),
            ("069500", "KODEX200", 10000.0, 10000.0),
        ],
        quotes_asof=_asof(today, "10:30"),
    )
    _tick(monkeypatch, runner, today, "10:30")
    assert runner.run(RISK_KIND, "send")["status"] == "sent"

    _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("102110", "TIGER200", 10000.0, 9200.0),  # 같은 구간 — 억제
            ("069500", "KODEX200", 10000.0, 9300.0),  # 신규 진입
        ],
        quotes_asof=_asof(today, "11:30"),
    )
    _tick(monkeypatch, runner, today, "11:30")
    second = runner.run(RISK_KIND, "send")

    assert second["status"] == "sent"
    assert "KODEX200" in send.calls[1]
    assert "TIGER200" not in send.calls[1], "억제 대상을 다시 실었다"


# ── R-9 / R-11 가드 ─────────────────────────────────────────────────────────


def test_runner_skips_on_non_trading_day(monkeypatch, tmp_path, today):
    """R-9 — 전 종목 시세가 과거 일자면 비거래일로 skip 하고 발송하지 않는다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof="2020-01-02T15:30:00+09:00",
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["reason"] == "non_trading_day", rec
    assert send.calls == []
    assert not (tmp_path / "risk_state.json").exists()


def test_runner_flag_off_blocks_before_any_skip_decision(monkeypatch, tmp_path, today):
    """R-11 — flag 가 꺼져 있으면 **skip·fail 판정보다 먼저** 차단된다.

    비거래일이라 skip 사유가 성립하는 입력을 주고도 `reason` 이 flag 차단이어야
    한다. 가드 순서가 뒤집히면 `non_trading_day` 가 나와 깨진다.
    """
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path, flag="false")
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof="2020-01-02T15:30:00+09:00",
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "skipped"
    assert (
        rec["reason"] == "push_kind_disabled"
    ), "flag 차단보다 skip 판정이 먼저 돌았다"
    assert send.calls == []


def test_runner_flag_off_beats_no_new_or_worsened(monkeypatch, tmp_path, today):
    """R-11 — `no_new_or_worsened` 도 flag 차단을 가로채면 안 된다.

    위험 구간 종목이 하나도 없는(=skip 사유가 성립하는) 입력을 주고도 `reason`
    이 `push_kind_disabled` 여야 한다. 종류별 flag 가 꺼져 있다는 사실이
    "오늘 보낼 게 없었다" 로 기록되면 미발송 원인을 운영에서 구분할 수 없다.
    """
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path, flag="false")
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 10000.0)],  # 하락 없음
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "skipped"
    assert rec["reason"] == "push_kind_disabled", rec["reason"]
    assert send.calls == []


def test_runner_dry_run_sends_nothing(monkeypatch, tmp_path, today):
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "dry-run")

    assert send.calls == []
    assert rec.get("telegram_attempted") is not True
    assert not (tmp_path / "risk_state.json").exists()


# ── R-13 기존 spike 재사용 금지 ──────────────────────────────────────────────


def test_runner_does_not_reuse_spike_signals(monkeypatch, tmp_path, today):
    """위험 알림 본문에 spike 신호·문구가 섞이지 않는다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent"
    assert rec.get("spike_new_fingerprints") in (None, [])
    assert "급등" not in send.calls[0] and "spike" not in send.calls[0].lower()


# ── 진단 필드 ────────────────────────────────────────────────────────────────


def test_runner_records_risk_diagnostics(monkeypatch, tmp_path, today):
    _seed_param()
    runner, _ = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("102110", "TIGER200", 10000.0, 9200.0),
            ("069500", "KODEX200", 10000.0, 10000.0),
        ],
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["risk_holdings_loaded_count"] == 2
    assert rec["risk_unique_ticker_count"] == 2
    assert rec["risk_selected_count"] == 1
    assert rec["risk_new_count"] == 1
    assert rec["risk_worsened_count"] == 0
    assert rec["risk_prev_trading_day"]


def test_runner_reports_unavailable_tickers(monkeypatch, tmp_path, today):
    """직전 종가가 없으면 데이터 확인 대상으로 진단에 남는다 (§4.7)."""
    import app.market_data_store as store_mod

    _seed_param()
    runner, _ = _install_runner(monkeypatch, tmp_path)
    axis = _install_inputs(
        monkeypatch,
        runner,
        specs=[("102110", "TIGER200", 10000.0, 9200.0)],
        quotes_asof=_asof(today),
    )
    # 축은 그대로 두고 이력에서 직전 거래일만 뺀다.
    trimmed = [(d, 10000.0) for d in axis[:-1]]
    axis_ticker = "069500"

    def _history(t, **kw):
        return [(d, 10000.0) for d in axis] if t == axis_ticker else trimmed

    monkeypatch.setattr(store_mod, "fetch_price_history", _history)

    rec = runner.run(RISK_KIND, "send")

    assert rec["risk_selected_count"] == 0
    assert rec["risk_data_unavailable_tickers"] == ["102110"]
    assert rec["reason"] == "no_new_or_worsened"


def test_band_states_are_all_reachable_through_runner(monkeypatch, tmp_path, today):
    """세 구간이 모두 러너를 통과해 본문에 나온다."""
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("A00001", "얕은", 10000.0, 9500.0),  # -5.0 → D5_7
            ("A00002", "중간", 10000.0, 9300.0),  # -7.0 → D7_10
            ("A00003", "깊은", 10000.0, 9000.0),  # -10.0 → D10_PLUS
        ],
        quotes_asof=_asof(today),
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent"
    body = send.calls[0]
    for label in ("하락 5~7%", "하락 7~10%", "하락 10% 이상"):
        assert label in body
    assert "보유 3종목 중 3종목 동시 하락" in body
    saved = json.loads((tmp_path / "risk_state.json").read_text(encoding="utf-8"))
    assert saved["entries"] == {
        "A00001": {"worst_state": STATE_D5_7},
        "A00002": {"worst_state": STATE_D7_10},
        "A00003": {"worst_state": STATE_D10_PLUS},
    }


# ── PLAN §4.6 부분 실패 · §4.7 결손 — **본문 표시** ──────────────────────────


def test_partial_failure_ticker_appears_in_sent_body(monkeypatch, tmp_path, today):
    """검증자 r1 A-3 재현 — A는 −10%, B는 시세 조회 실패.

    B 가 진단 목록에만 남고 본문에서 빠지면 "B 는 괜찮다" 로 읽힌다. 데이터를
    못 봤다는 사실이 알림에서 숨으면 안 된다.
    """
    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("A00001", "가나다ETF", 10000.0, 9000.0),  # -10.0%
            ("B00002", "라마바ETF", 10000.0, 9000.0),
        ],
        quotes_asof=_asof(today),
    )
    # B 만 시세 조회 실패 (quote=None) — 부분 실패.
    fake = types.ModuleType("app.market_naver")

    class _Q:
        current_price = 9000.0
        price_asof = _asof(today)

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = None if t == "B00002" else _Q()

    fake.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fake.fetch_many)

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent", rec
    assert rec["runtime_price_refresh"]["failed"] == 1
    assert rec["risk_data_unavailable_tickers"] == ["B00002"]
    body = send.calls[0]
    assert "가나다ETF" in body
    assert "라마바ETF" in body, "부분 실패 종목이 본문에서 빠졌다"
    assert "데이터 확인 필요" in body


def test_missing_previous_close_ticker_appears_in_sent_body(
    monkeypatch, tmp_path, today
):
    """§4.7 — 직전 거래일 종가가 없는 종목도 본문에 실린다.

    시세는 정상이지만 분모가 없어 하락률을 계산할 수 없는 경우다. 더 오래된
    종가로 대체하지 않으므로(§4.7) 선정에서는 빠지고, 대신 표시된다.
    """
    import app.market_data_store as store_mod

    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    axis = _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("A00001", "가나다ETF", 10000.0, 9000.0),  # -10.0%
            ("B00002", "라마바ETF", 10000.0, 9000.0),
        ],
        quotes_asof=_asof(today),
    )
    from app.runtime_evidence.holdings_selection import TRADING_DAY_AXIS_TICKER

    full = [(d, 10000.0) for d in axis]

    def _history(t, **kw):
        # B 만 직전 거래일 행이 없다.
        return full[:-1] if t == "B00002" else full

    monkeypatch.setattr(store_mod, "fetch_price_history", _history)
    assert TRADING_DAY_AXIS_TICKER != "B00002"

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent", rec
    assert rec["risk_data_unavailable_tickers"] == ["B00002"]
    body = send.calls[0]
    assert "라마바ETF" in body, "직전 종가 결손 종목이 본문에서 빠졌다"
    assert "데이터 확인 필요" in body


def test_unavailable_alone_does_not_trigger_a_send(monkeypatch, tmp_path, today):
    """결손만으로는 발송하지 않는다.

    §4.3 발송 표에 결손 항목이 없고, 촉발시키면 억제 계약이 없어 매 틱 알림이
    나간다. 발송이 성립할 때 **함께** 싣는 것이 계약이다.
    """
    import app.market_data_store as store_mod

    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    axis = _install_inputs(
        monkeypatch,
        runner,
        specs=[("B00002", "라마바ETF", 10000.0, 9900.0)],  # 하락 -1% (구간 밖)
        quotes_asof=_asof(today),
    )
    full = [(d, 10000.0) for d in axis]
    monkeypatch.setattr(
        store_mod,
        "fetch_price_history",
        lambda t, **kw: full[:-1] if t == "B00002" else full,
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["risk_data_unavailable_tickers"] == ["B00002"]
    assert rec["status"] == "skipped"
    assert rec["reason"] == "no_new_or_worsened"
    assert send.calls == []


def test_multi_account_unavailable_ticker_listed_once(monkeypatch, tmp_path, today):
    """다계좌 결손 종목도 ticker 기준으로 한 번만 표시한다."""
    from dataclasses import dataclass

    import app.holdings as holdings_mod
    import app.market_data_store as store_mod

    @dataclass
    class _H:
        ticker: str
        name: str
        account_group: str = "일반"

    _seed_param()
    runner, send = _install_runner(monkeypatch, tmp_path)
    axis = _install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("A00001", "가나다ETF", 10000.0, 9000.0),
            ("B00002", "라마바ETF", 10000.0, 9000.0),
        ],
        quotes_asof=_asof(today),
    )
    monkeypatch.setattr(
        holdings_mod,
        "load",
        lambda *a, **k: [
            _H("A00001", "가나다ETF"),
            _H("B00002", "라마바ETF", "일반"),
            _H("B00002", "라마바ETF", "연금"),
        ],
    )
    full = [(d, 10000.0) for d in axis]
    monkeypatch.setattr(
        store_mod,
        "fetch_price_history",
        lambda t, **kw: full[:-1] if t == "B00002" else full,
    )

    rec = runner.run(RISK_KIND, "send")

    assert rec["status"] == "sent"
    assert rec["risk_data_unavailable_tickers"] == ["B00002"]
    body = send.calls[0]
    assert body.count("라마바ETF") == 1, "다계좌 결손 종목을 여러 번 표시했다"
