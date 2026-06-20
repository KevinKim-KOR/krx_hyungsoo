"""tests for app.three_push_runtime_message_builder.

PUSH 사용자 표현 정리 STEP (2026-06-20, 지시문 §4) 갱신:
  - 메시지 본문에 raw 기술 식별자 (param_id / param_source / push_kind /
    snake_case source key) 노출 0건 (지시문 AC-1).
  - 모든 source unavailable 시 사용자 중심 축약 메시지 (지시문 §4.3).
  - 일부 source available 시 사용자 라벨 + 별도 확인 필요 블록 (지시문 §4.4).
  - PC package message_text 재사용 안 함 (본 빌더는 외부 message_text 인자 없음).
  - 금지 문구 0건.
"""

from __future__ import annotations

import pytest

from app.push_user_labels import SOURCE_USER_LABELS
from app.three_push_runner_common import (
    check_forbidden_wording,
    check_raw_identifiers,
)
from app.three_push_runtime_message_builder import (
    PUSH_KIND_KOREAN,
    availability_summary,
    build_runtime_message,
    kst_now_iso,
    kst_today_date,
)
from app.three_push_runtime_param import build_manual_seed_param


@pytest.fixture
def param():
    return build_manual_seed_param(param_description="unit", source_note="builder")


@pytest.mark.parametrize(
    "push_kind",
    ["market_briefing", "holdings_briefing", "spike_or_falling_alert"],
)
def test_build_runtime_message_non_empty(push_kind, param):
    msg = build_runtime_message(push_kind=push_kind, param=param)
    assert isinstance(msg, str)
    assert msg.strip() != ""


@pytest.mark.parametrize(
    "push_kind",
    ["market_briefing", "holdings_briefing", "spike_or_falling_alert"],
)
def test_message_contains_user_friendly_header_only(push_kind, param):
    """사용자 친화 헤더 + 기준 시각 표시만 포함하며 raw 식별자는 노출 X."""
    msg = build_runtime_message(push_kind=push_kind, param=param)
    # 사용자용 한국어 타이틀 (PUSH_KIND_KOREAN 매핑에서 가져옴) 일부 포함.
    expected_title_fragment = PUSH_KIND_KOREAN[push_kind].split(" ")[0]
    assert expected_title_fragment in msg
    assert "기준 시각" in msg


@pytest.mark.parametrize(
    "push_kind",
    ["market_briefing", "holdings_briefing", "spike_or_falling_alert"],
)
def test_message_has_no_raw_identifiers(push_kind, param):
    """AC-1 / §4.1 — 본문에 raw 기술 식별자 노출 0건."""
    msg = build_runtime_message(push_kind=push_kind, param=param)
    assert (
        check_raw_identifiers(msg) is None
    ), f"raw 식별자 노출: push_kind={push_kind}, msg={msg!r}"
    # 직접 확인 — param.param_id / param_source / push_kind 모두 본문 미포함.
    assert param.param_id not in msg
    assert param.param_source not in msg
    assert push_kind not in msg
    # snake_case source key 도 본문 미포함.
    for src_key in SOURCE_USER_LABELS:
        assert src_key not in msg, f"source key {src_key!r} 노출됨"


def test_message_all_unavailable_uses_user_centric_copy(param):
    """모든 source unavailable 시 사용자 중심 축약 메시지 (지시문 §4.3).

    헤더 + 기준 시각 + 안내 + "별도 확인 필요" 사용자 라벨 + 짧은 주의 문장.
    """
    msg = build_runtime_message(
        push_kind="market_briefing",
        param=param,
        available_sources=None,
    )
    # 지시문 §4.3 예시 문구 — 모든 source 가 unavailable 일 때의 안내.
    assert "별도 확인 필요" in msg
    # 사용자 라벨 (snake_case 가 아니라 한국어).
    assert "국내 ETF 시세" in msg
    assert "밤사이 미국 시장" in msg
    # 매매 지시 아님 면책 (NEUTRAL_NOTES).
    assert "매매" in msg or "정보" in msg
    # raw 식별자 노출 0건.
    assert check_raw_identifiers(msg) is None


def test_message_partial_available_shows_user_labels(param):
    """일부 available 시 사용자 라벨 + 별도 확인 필요 블록 (지시문 §4.4)."""
    sources = {
        "kr_realtime_price_snapshot": "available",
        "overnight_us_market_snapshot": "unavailable",
        "market_discovery_snapshot": "unavailable",
        "ml_baseline_v0": "unavailable",
    }
    msg = build_runtime_message(
        push_kind="market_briefing",
        param=param,
        available_sources=sources,
    )
    # available 항목은 사용자 라벨로 표시.
    assert "국내 ETF 시세" in msg
    # unavailable 항목도 사용자 라벨로 표시 (snake_case 노출 X).
    assert "밤사이 미국 시장" in msg
    assert "ETF 후보 흐름" in msg
    # raw snake_case 노출 0건.
    assert check_raw_identifiers(msg) is None


def test_message_does_not_contain_forbidden_wording(param):
    for push_kind in ("market_briefing", "holdings_briefing", "spike_or_falling_alert"):
        msg = build_runtime_message(push_kind=push_kind, param=param)
        assert (
            check_forbidden_wording(msg) is None
        ), f"{push_kind} 메시지에 금지 문구 포함됨"


def test_unknown_push_kind_raises(param):
    with pytest.raises(ValueError, match="unknown push_kind"):
        build_runtime_message(push_kind="invalid_kind", param=param)


def test_kst_helpers_format():
    iso = kst_now_iso()
    assert "+09:00" in iso
    assert "T" in iso
    date = kst_today_date()
    assert len(date) == 10
    assert date[4] == "-" and date[7] == "-"


def test_availability_summary_counts():
    s = availability_summary({"a": "available", "b": "unavailable", "c": "error"})
    assert s == {"available": 1, "unavailable_or_other": 2}
    assert availability_summary(None) == {"available": 0, "unavailable_or_other": 0}
    assert availability_summary({}) == {"available": 0, "unavailable_or_other": 0}
