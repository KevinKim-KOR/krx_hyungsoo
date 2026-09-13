"""PUSH 종류별 flag = false → 차단 분기 (2026-08-29).

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

from tests.low_frequency_push._fixtures import (
    _install_mocks_with_kind_disabled,
    _seed_and_get_param,
)


def test_runner_spike_skipped_when_kind_flag_disabled(tmp_path, monkeypatch):
    """spike/falling: flag=false → skipped(push_kind_disabled) · 발송·registry 미호출."""
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner, calls, marked = _install_mocks_with_kind_disabled(
        monkeypatch, tmp_path, "PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED"
    )
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: [])

    before = registry_count()
    rec = runner.run("spike_or_falling_alert", "send")

    assert rec["status"] == "skipped", f"차단돼야 한다 — 실제 {rec['status']}"
    assert (
        rec["reason"] == "push_kind_disabled"
    ), f"전역 flag 는 true 이므로 사유가 push_kind_disabled 여야 한다 — 실제 {rec['reason']}"
    assert calls == [], "차단 시 telegram_send 가 호출되면 안 된다"
    assert marked == [], "차단 시 mark_sent 가 호출되면 안 된다"
    assert registry_count() == before, "차단 시 sent registry 가 증가하면 안 된다"
    assert rec.get("telegram_sent") is not True
    # status/history 종료 기록은 차단 시에도 남는다 (_finish 계약).
    assert rec.get("finished_at")


def test_runner_holdings_skipped_when_kind_flag_disabled(tmp_path, monkeypatch):
    """holdings briefing: flag=false → skipped(push_kind_disabled) · 발송·registry 미호출."""
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner, calls, marked = _install_mocks_with_kind_disabled(
        monkeypatch, tmp_path, "PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED"
    )
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: [])

    before = registry_count()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["status"] == "skipped", f"차단돼야 한다 — 실제 {rec['status']}"
    assert (
        rec["reason"] == "push_kind_disabled"
    ), f"전역 flag 는 true 이므로 사유가 push_kind_disabled 여야 한다 — 실제 {rec['reason']}"
    assert calls == [], "차단 시 telegram_send 가 호출되면 안 된다"
    assert marked == [], "차단 시 mark_sent 가 호출되면 안 된다"
    assert registry_count() == before, "차단 시 sent registry 가 증가하면 안 된다"
    assert rec.get("telegram_sent") is not True
    assert rec.get("finished_at")
