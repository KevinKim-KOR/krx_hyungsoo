"""tests for app.three_push_runtime_message_builder.

핵심:
  - 모든 push_kind 에 대해 메시지가 빈 문자열이 아니다.
  - 메시지에 runtime timestamp / param_id / push_kind / 면책 / data availability
    라벨이 포함된다.
  - available_sources=None 이면 unavailable 라인이 출력된다.
  - PC package message_text 를 재사용하지 않는다 (본 빌더는 외부 입력 message_text
    인자 자체가 없다 — API 표면으로 보장).
  - 금지 문구가 본문에 들어가지 않는다.
"""

from __future__ import annotations

import pytest

from app.three_push_runner_common import check_forbidden_wording
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
def test_message_contains_required_fields(push_kind, param):
    msg = build_runtime_message(push_kind=push_kind, param=param)
    assert PUSH_KIND_KOREAN[push_kind] in msg
    assert param.param_id in msg
    assert param.param_source in msg
    assert push_kind in msg
    assert "발송 시각(KST)" in msg
    assert "데이터 가용성" in msg
    assert "면책" in msg


def test_message_marks_unavailable_when_no_sources(param):
    msg = build_runtime_message(
        push_kind="market_briefing",
        param=param,
        available_sources=None,
    )
    # 모든 source 가 unavailable 로 표시되어야 함
    assert "unavailable" in msg


def test_message_lists_available_sources(param):
    sources = {
        "kr_realtime_price_snapshot": "available",
        "overnight_us_market_snapshot": "unavailable",
    }
    msg = build_runtime_message(
        push_kind="market_briefing",
        param=param,
        available_sources=sources,
    )
    assert "kr_realtime_price_snapshot: available" in msg
    assert "overnight_us_market_snapshot: unavailable" in msg


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
