"""Spike 신호 note 생성 · body 재조립 (혼합 신호) · Producer publish.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

import pytest

from app.runtime_evidence.universe_reevaluator import (
    SpikeSignal,
    format_spike_signal_note,
)

from app.three_push_runtime.spike_body import filter_extra_notes_to_new_signals


def test_format_spike_signal_note_shape():
    s = SpikeSignal(
        ticker="000660",
        name="SK하이닉스",
        trigger_type="falling",
        direction="down",
        fingerprint="000660#falling#down",
        runtime_return_pct=-30.0,
        runtime_price=700.0,
        price_asof="2026-07-24T15:30:00+09:00",
        base_close=1000.0,
        base_date="2026-06-24",
        threshold_pct=-10.0,
        evidence_as_of="2026-07-24",
    )
    n = format_spike_signal_note(s)
    assert n.startswith("[신규 falling] SK하이닉스 (000660):")
    assert "현재가 700원" in n


# ── Producer publish ─────────────────────────────────────────────────────


def test_universe_producer_publishes_trigger_direction_evidence_as_of():
    from app.universe_seed import UniverseSeed, UniverseSeedItem
    from app.momentum.universe_mode import build_universe_momentum_result_scored

    seed = UniverseSeed(
        asof="2026-07-24",
        source="manual_seed",
        source_freshness="fresh",
        staleness_days=0,
        items=[
            UniverseSeedItem(
                ticker="000660",
                name="SK하이닉스",
                universe_group=None,
                sector_or_theme=None,
            )
        ],
    )
    art = build_universe_momentum_result_scored(seed, scores=[], refresh_status="ok")
    s = art["summary"]
    assert s["spike_trigger_type"] == "falling"
    assert s["spike_direction"] == "down"
    assert s["evidence_as_of"] == "2026-07-24"
    assert s["falling_threshold_pct"] == -10.0


# ── Spike body 재조립 (혼합 신호) ────────────────────────────────────────


def test_filter_extra_notes_keeps_only_new_fingerprints():
    all_notes = ["A note", "B note", "C note"]
    all_fps = ["A#falling#down", "B#falling#down", "C#falling#down"]
    new_fps = ["B#falling#down"]
    out = filter_extra_notes_to_new_signals(all_notes, all_fps, new_fps)
    assert out == ["B note"]


def test_filter_extra_notes_empty_when_no_new():
    assert filter_extra_notes_to_new_signals(["A"], ["A#f#d"], []) == []


def test_format_spike_signal_note_raises_on_missing_asof():
    """A+ 재정정: SpikeSignal.price_asof None 이면 note 포맷 시 raise."""
    s = SpikeSignal(
        ticker="000660",
        name="SK",
        trigger_type="falling",
        direction="down",
        fingerprint="000660#falling#down",
        runtime_return_pct=-30.0,
        runtime_price=700.0,
        price_asof=None,
        base_close=1000.0,
        base_date="2026-06-24",
        threshold_pct=-10.0,
        evidence_as_of="2026-07-24",
    )
    with pytest.raises(ValueError):
        format_spike_signal_note(s)


def test_filter_extra_notes_length_mismatch_raises():
    """A+ 재정정: length mismatch 는 조용히 [] 반환 금지 · ValueError."""
    with pytest.raises(ValueError):
        filter_extra_notes_to_new_signals(["A", "B"], ["A#f#d"], ["A#f#d"])
