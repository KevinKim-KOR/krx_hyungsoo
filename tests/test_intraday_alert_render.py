"""POC3-02C-OPS-02 — 억제·cooldown·상한·본문 계약 (설계자 §5·§6·§7·§8).

실제 Naver·Telegram 호출 0건.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pytest

from app.runtime_evidence.holdings_risk import STATE_D5_7, STATE_D10_PLUS, STATE_U7_10
from app.runtime_evidence.intraday_alert_render import (
    SECTION_AVOID,
    SECTION_ENTRY,
    SECTION_HELD,
    build_section_plan,
    render_checkup_summary,
    render_intraday_alert,
)
from app.runtime_evidence.sector_signal import (
    STATE_AVOID_CHASE,
    STATE_AVOID_DROP,
    STATE_ENTRY_REVIEW,
    SectorSignal,
)
from app.runtime_evidence.sector_signal_state import (
    KST,
    LoadedSectorState,
    compute_sector_changes,
    load_sector_state,
    merge_sector_entries,
    save_sector_state,
)

NOW = datetime(2026, 9, 16, 10, 30, tzinfo=KST)
TODAY = "2026-09-16"


@dataclass
class H:
    ticker: str
    name: str
    state: str
    day_drop_pct: Optional[float] = None
    day_return_pct: Optional[float] = None


def _sig(ticker, state, pct, *, key="반도체", r5=4.3, r20=8.7):
    return SectorSignal(key, ticker, f"{key}ETF", state, pct, r5, r20)


# ── §5 억제와 cooldown ──────────────────────────────────────────────────────


def test_first_time_signal_is_sent():
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_DROP, -2.4)],
        previous=LoadedSectorState(entries={}, fallback=False),
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert [s.ticker for s in ch.send] == ["T1"]


def test_same_state_within_cooldown_is_suppressed():
    """같은 ticker 같은 상태가 계속 유지 — 보내지 않는다."""
    prev = LoadedSectorState(
        entries={
            "T1": {
                "state": STATE_AVOID_DROP,
                "last_sent_at": (NOW - timedelta(minutes=60)).isoformat(),
            }
        },
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_DROP, -3.9)],  # 수치만 달라짐
        previous=prev,
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert ch.send == []
    assert ch.suppressed == [("T1", STATE_AVOID_DROP)]


def test_continuous_signal_is_never_resent_by_time_alone():
    """**지속 중인 신호는 시간이 지나도 재발송하지 않는다**(설계 §5).

    검증자 지적 — 예전에는 경과 시간만 보고 120분 뒤 다시 보냈다. 설계는
    "임계 밖으로 **회복된 뒤** 다시 진입하고 120분이 지남" 이라 두 조건이
    모두 필요하다.
    """
    prev = LoadedSectorState(
        entries={
            "T1": {
                "state": STATE_AVOID_DROP,
                "last_sent_at": (NOW - timedelta(minutes=600)).isoformat(),
                "continuous": True,  # 계속 관측 중
            }
        },
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_DROP, -2.4)],
        previous=prev,
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert ch.send == [], "지속 중인데 재발송했다"
    assert ch.suppressed == [("T1", STATE_AVOID_DROP)]


def test_reentry_after_recovery_sends_once_cooldown_passed():
    """회복 후 재진입 + cooldown 경과 → 발송."""
    prev = LoadedSectorState(
        entries={
            "T1": {
                "state": STATE_AVOID_DROP,
                "last_sent_at": (NOW - timedelta(minutes=120)).isoformat(),
                "continuous": False,  # 임계 밖으로 나갔다 돌아옴
            }
        },
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_DROP, -2.4)],
        previous=prev,
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert [s.ticker for s in ch.send] == ["T1"]


def test_reentry_within_cooldown_is_suppressed():
    prev = LoadedSectorState(
        entries={
            "T1": {
                "state": STATE_AVOID_DROP,
                "last_sent_at": (NOW - timedelta(minutes=119)).isoformat(),
                "continuous": False,
            }
        },
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_DROP, -2.4)],
        previous=prev,
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert ch.send == []


def test_absent_tick_clears_continuous_flag():
    """임계 밖으로 나가면 `continuous` 가 내려간다 — 회복 판정의 근거다."""
    from app.runtime_evidence.sector_signal_state import mark_absent_entries

    prev = LoadedSectorState(
        entries={"T1": {"state": STATE_AVOID_DROP, "continuous": True}},
        fallback=False,
    )
    entries = mark_absent_entries(observed=[], previous=prev)
    assert entries["T1"]["continuous"] is False
    assert "T1" in entries, "기록 자체를 지우면 재진입이 신규로 잡힌다"


def test_observed_tick_keeps_continuous_true():
    prev = LoadedSectorState(entries={}, fallback=False)
    sig = _sig("T1", STATE_AVOID_DROP, -2.4)
    entries = merge_sector_entries(sent=[], previous=prev, now_kst=NOW, observed=[sig])
    assert entries["T1"]["continuous"] is True
    assert "last_sent_at" not in entries["T1"], "보내지 않았는데 발송 시각을 찍었다"


def test_state_change_ignores_cooldown():
    """상태가 달라지면 cooldown 과 **무관하게** 보낸다."""
    prev = LoadedSectorState(
        entries={
            "T1": {
                "state": STATE_AVOID_DROP,
                "last_sent_at": (NOW - timedelta(minutes=5)).isoformat(),
            }
        },
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_CHASE, 4.6)],
        previous=prev,
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert [s.ticker for s in ch.send] == ["T1"]


def test_uncomparable_state_sends_everything():
    """비교 불가면 **조용한 억제로 대체하지 않는다**."""
    ch = compute_sector_changes(
        signals=[
            _sig("T1", STATE_AVOID_DROP, -2.4),
            _sig("T2", STATE_AVOID_CHASE, 5.0),
        ],
        previous=LoadedSectorState(fallback=True, fallback_reason="missing"),
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert len(ch.send) == 2


def test_corrupt_timestamp_sends_rather_than_suppress():
    prev = LoadedSectorState(
        entries={"T1": {"state": STATE_AVOID_DROP, "last_sent_at": "깨진값"}},
        fallback=False,
    )
    ch = compute_sector_changes(
        signals=[_sig("T1", STATE_AVOID_DROP, -2.4)],
        previous=prev,
        now_kst=NOW,
        cooldown_minutes=120,
    )
    assert [s.ticker for s in ch.send] == ["T1"]


def test_suppressed_signal_does_not_push_cooldown():
    """억제된 신호로 `last_sent_at` 을 밀면 cooldown 이 영원히 안 끝난다."""
    stamp = (NOW - timedelta(minutes=60)).isoformat()
    prev = LoadedSectorState(
        entries={"T1": {"state": STATE_AVOID_DROP, "last_sent_at": stamp}},
        fallback=False,
    )
    merged = merge_sector_entries(sent=[], previous=prev, now_kst=NOW)
    assert merged["T1"]["last_sent_at"] == stamp


def test_sent_signal_updates_timestamp():
    prev = LoadedSectorState(entries={}, fallback=False)
    merged = merge_sector_entries(
        sent=[_sig("T1", STATE_AVOID_DROP, -2.4)], previous=prev, now_kst=NOW
    )
    assert merged["T1"]["last_sent_at"] == NOW.isoformat()
    assert merged["T1"]["state"] == STATE_AVOID_DROP


def test_state_file_round_trip(tmp_path):
    p = tmp_path / "s.json"
    save_sector_state(
        p,
        entries={"T1": {"state": STATE_AVOID_DROP, "last_sent_at": NOW.isoformat()}},
        today_kst=TODAY,
        sent_today=2,
    )
    loaded = load_sector_state(p, today_kst=TODAY)
    assert loaded.comparable and loaded.sent_today == 2
    assert loaded.entries["T1"]["state"] == STATE_AVOID_DROP


def test_new_trading_day_resets_comparison(tmp_path):
    """어제 억제를 오늘로 끌고 오지 않는다."""
    p = tmp_path / "s.json"
    save_sector_state(p, entries={"T1": {}}, today_kst="2026-09-15", sent_today=4)
    loaded = load_sector_state(p, today_kst=TODAY)
    assert loaded.fallback and loaded.fallback_reason == "date_reset"


@pytest.mark.parametrize("body", ["{깨짐", '{"schema_version": "다른것"}', "[]"])
def test_corrupt_state_file_is_uncomparable(tmp_path, body):
    p = tmp_path / "s.json"
    p.write_text(body, encoding="utf-8")
    assert load_sector_state(p, today_kst=TODAY).fallback


def test_missing_state_file_is_uncomparable(tmp_path):
    assert load_sector_state(tmp_path / "없음.json", today_kst=TODAY).fallback


# ── §6 상한과 우선순위 ──────────────────────────────────────────────────────


def test_section_cap_keeps_three_and_records_dropped():
    """구역별 최대 3종목. 잘린 것도 **이력에는 남는다**."""
    sigs = [_sig(f"T{i}", STATE_AVOID_DROP, -2.0 - i, key=f"S{i}") for i in range(5)]
    plan = build_section_plan(
        held_drop=[], held_surge=[], sector_signals=sigs, max_items_per_section=3
    )
    assert len(plan.avoid_drop) == 3
    assert len(plan.dropped) == 2
    assert all(d["reason"] == "section_cap" for d in plan.dropped)


def test_priority_order_in_body():
    """§6 우선순위 — 보유 급락 → 보유 급등 → 회피 → 진입 검토."""
    plan = build_section_plan(
        held_drop=[H("H1", "보유하락", STATE_D5_7, day_drop_pct=-5.4)],
        held_surge=[H("H2", "보유상승", STATE_U7_10, day_return_pct=7.8)],
        sector_signals=[
            _sig("E1", STATE_ENTRY_REVIEW, 2.1),
            _sig("A1", STATE_AVOID_DROP, -2.4, key="조선"),
        ],
        max_items_per_section=3,
    )
    text = render_intraday_alert(plan, slot_label="10:30")
    assert text.index(SECTION_HELD) < text.index(SECTION_ENTRY)
    assert text.index("보유하락") < text.index("보유상승")
    assert text.index(SECTION_ENTRY) < text.index(SECTION_AVOID)


# ── §7 본문 ─────────────────────────────────────────────────────────────────


def test_empty_plan_renders_nothing():
    """모든 구역이 비면 **미발송**."""
    plan = build_section_plan(
        held_drop=[], held_surge=[], sector_signals=[], max_items_per_section=3
    )
    assert plan.is_empty()
    assert render_intraday_alert(plan, slot_label="10:30") == ""


def test_empty_section_is_omitted_entirely():
    """후보 없는 구역은 **통째로 생략**한다."""
    plan = build_section_plan(
        held_drop=[H("H1", "보유하락", STATE_D10_PLUS, day_drop_pct=-11.0)],
        held_surge=[],
        sector_signals=[],
        max_items_per_section=3,
    )
    text = render_intraday_alert(plan, slot_label="10:30")
    assert SECTION_HELD in text
    assert SECTION_ENTRY not in text
    assert SECTION_AVOID not in text


def test_body_carries_basis():
    plan = build_section_plan(
        held_drop=[],
        held_surge=[],
        sector_signals=[_sig("A1", STATE_AVOID_DROP, -2.4)],
        max_items_per_section=3,
    )
    text = render_intraday_alert(
        plan,
        slot_label="10:30",
        quote_asof="2026-09-21 10:30",
        base_close_date="2026-09-18",
    )
    assert "기준" in text and "2026-09-21 10:30" in text and "2026-09-18" in text


def test_disclaimer_passes_forbidden_phrase_guard():
    """**확정 문구가 금지어 가드를 통과한다**(설계자 §15-1).

    최초 §7 문구 `"매수·매도 지시가 아닙니다"` 는 부정문인데도 `"매도 지시"` 에
    부분일치해 러너가 발송을 막았다. 가드를 완화하지 않고 문구를 바꿨다.
    """
    from app.runtime_evidence.intraday_alert_render import DISCLAIMER
    from app.three_push_runner_common import FORBIDDEN_PHRASES

    assert DISCLAIMER == "※ 자동 감지 결과이며, 최종 판단은 사용자가 합니다."
    assert [p for p in FORBIDDEN_PHRASES if p in DISCLAIMER] == []


def test_disclaimer_avoids_trade_words():
    """`매수`·`매도`·`매매`·`지시` 를 **모두 피한다**(§15-1)."""
    from app.runtime_evidence.intraday_alert_render import DISCLAIMER

    for w in ("매수", "매도", "매매", "지시"):
        assert w not in DISCLAIMER, w


def test_forbidden_guard_is_not_weakened():
    """가드 완화 금지 — `"매도 지시"` 가 목록에 그대로 있어야 한다."""
    from app.three_push_runner_common import FORBIDDEN_PHRASES

    assert "매도 지시" in FORBIDDEN_PHRASES
    assert "매수 지시" in FORBIDDEN_PHRASES


def test_unified_body_carries_disclaimer():
    """신규 통합 메시지에는 붙는다."""
    plan = build_section_plan(
        held_drop=[],
        held_surge=[],
        sector_signals=[_sig("A1", STATE_AVOID_DROP, -2.4)],
        max_items_per_section=3,
    )
    text = render_intraday_alert(plan, slot_label="10:30")
    assert text.rstrip().endswith("최종 판단은 사용자가 합니다.")


def test_legacy_body_has_no_disclaimer():
    """**비활성 상태의 기존 본문에는 넣지 않는다**(§15-1).

    `holdings_risk_render` 의 "면책문구·매매지시 문구 없음"(POC3-OPS-02A)
    계약을 그대로 유지한다.
    """
    from pathlib import Path

    src = Path("app/runtime_evidence/holdings_risk_render.py").read_text(
        encoding="utf-8"
    )
    assert "최종 판단은 사용자가 합니다" not in src
    assert "DISCLAIMER" not in src


def test_disclaimer_is_injectable():
    """호출자가 바꿀 수 있다 — 미리보기 등에서 다른 문구가 필요할 수 있다."""
    plan = build_section_plan(
        held_drop=[],
        held_surge=[],
        sector_signals=[_sig("A1", STATE_AVOID_DROP, -2.4)],
        max_items_per_section=3,
    )
    text = render_intraday_alert(plan, slot_label="10:30", disclaimer="※ 참고용입니다.")
    assert text.rstrip().endswith("※ 참고용입니다.")


def test_entry_section_shows_windows_avoid_shows_reason():
    plan = build_section_plan(
        held_drop=[],
        held_surge=[],
        sector_signals=[
            _sig("E1", STATE_ENTRY_REVIEW, 2.1, r5=4.3, r20=8.7),
            _sig("A1", STATE_AVOID_CHASE, 4.6, key="조선"),
        ],
        max_items_per_section=3,
    )
    text = render_intraday_alert(plan, slot_label="10:30")
    assert "5일 +4.3% · 20일 +8.7%" in text
    assert "단기 급등 · 추격 주의" in text


def test_held_line_uses_short_label_not_duplicate_phrase():
    """줄 앞에 이미 `전일 대비 -5.4%` 가 있다 — 긴 라벨은 같은 말 반복이다."""
    plan = build_section_plan(
        held_drop=[H("H1", "보유하락", STATE_D5_7, day_drop_pct=-5.4)],
        held_surge=[],
        sector_signals=[],
        max_items_per_section=3,
    )
    text = render_intraday_alert(plan, slot_label="10:30")
    assert "보유 급락 5~7%" in text
    assert "전일 대비 하락 5~7%" not in text


# ── §8 15:40 점검 요약 ──────────────────────────────────────────────────────


def test_checkup_summary_is_one_line():
    line = render_checkup_summary(checks=7, sent=2, suppressed=3, no_signal=2)
    assert "\n" not in line
    assert line == "장중 점검 7회 · 알림 2건 · 중복 억제 3건 · 신호 없음 2건"


def test_checkup_summary_shows_failures_separately():
    line = render_checkup_summary(checks=7, sent=1, suppressed=2, no_signal=3, failed=1)
    assert "조회 실패 1회" in line


def test_checkup_summary_unknown_is_not_disguised_as_zero():
    """집계 불가를 성공처럼 `0` 으로 표시하지 않는다(설계 §8)."""
    line = render_checkup_summary(
        checks=0, sent=0, suppressed=0, no_signal=0, unknown=True
    )
    assert line == "장중 점검 확인 불가"
    assert "0건" not in line
