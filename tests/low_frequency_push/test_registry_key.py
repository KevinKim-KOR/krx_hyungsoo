"""Registry key — slot 격리 · date 필드 중복 금지.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

from app.three_push_runtime.registry_key import (
    registry_key,
    resolve_registry_date_field,
)

# ── Registry key ─────────────────────────────────────────────────────────


def test_registry_key_holdings_slot_isolation():
    date = "2026-07-24"
    o1 = registry_key("holdings_briefing", "p1", date, slot_id="OPEN")
    o2 = registry_key("holdings_briefing", "p1", date, slot_id="OPEN")
    m = registry_key("holdings_briefing", "p1", date, slot_id="MIDDAY")
    assert o1 == o2
    assert o1 != m
    assert registry_key("market_briefing", "p1", date) == f"market_briefing::p1::{date}"


def test_registry_date_field_no_double_date_for_spike():
    date = "2026-07-24"
    fp = "000660#falling#down"
    df = resolve_registry_date_field(date, signal_fingerprint=fp)
    assert df == f"{date}#{fp}"
    assert df.count(date) == 1
