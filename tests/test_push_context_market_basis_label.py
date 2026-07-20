"""Holdings-Market PENDING Judgment Draft v1 REJECTED r3 정정 focused test.

계약:
- 사용자 화면 문구에 내부 basis identifier 는 어떤 경우에도 원문 그대로
  노출되지 않는다 (지시문 §5.3 · "내부 source key 기본 화면 노출 금지").
- 매핑된 basis (daily · one_month · three_month · 별칭 1m/3m/6m/1y) 는
  사용자 이해 가능한 한국어 라벨로 표시.
- 미등록 basis 는 라벨 자체를 생략 ("상위:" · "하위:" 형태).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.market_topn_helpers import ALLOWED_BASIS
from app.push_context_market import (
    _BASIS_USER_LABEL,
    _basis_user_label,
    _market_trend_observation,
)


def _md(basis: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "asof": "2026-07-19",
        "basis": basis,
        "candidates": [
            {
                "rank": 1,
                "ticker": "AAA",
                "name": "종목A",
                "selected_return_pct": 5.0,
                "returns": {basis: {"return_pct": 5.0}},
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "name": "종목B",
                "selected_return_pct": -3.0,
                "returns": {basis: {"return_pct": -3.0}},
            },
        ],
    }


def test_allowed_basis_all_mapped_to_user_label() -> None:
    """market_topn_helpers.ALLOWED_BASIS 전 항목이 매핑에 존재."""
    for basis in ALLOWED_BASIS:
        assert basis in _BASIS_USER_LABEL, (
            f"허용 basis {basis!r} 가 _BASIS_USER_LABEL 매핑에 없음 — "
            f"사용자 화면에 내부 identifier 가 노출될 수 있음"
        )


@pytest.mark.parametrize("basis", list(ALLOWED_BASIS))
def test_allowed_basis_never_exposes_raw_key_in_text(basis: str) -> None:
    """허용 basis 어떤 값이라도 사용자 텍스트에 내부 identifier 노출 없음."""
    result = _market_trend_observation(_md(basis))
    assert result is not None
    text = result.get("text", "")
    assert (
        basis not in text
    ), f"허용 basis {basis!r} 가 사용자 텍스트 {text!r} 에 그대로 노출됨"
    # 매핑된 사용자 라벨은 포함되어야 함.
    user_label = _BASIS_USER_LABEL[basis]
    assert user_label in text, f"사용자 라벨 {user_label!r} 이 텍스트 {text!r} 에 없음"


def test_unregistered_basis_omits_label_no_raw_key_exposed() -> None:
    """매핑에 없는 basis 는 라벨 자체를 생략하고 내부 값 노출하지 않음."""
    raw = "unexpected_internal_key"
    assert raw not in _BASIS_USER_LABEL  # 전제 확인
    result = _market_trend_observation(_md(raw))
    assert result is not None
    text = result.get("text", "")
    assert raw not in text, f"미등록 basis {raw!r} 가 사용자 텍스트 {text!r} 에 노출됨"
    # 라벨 생략 형식: "상위: ..." · "하위: ..." (괄호 없음).
    assert "상위: " in text or "하위: " in text
    assert "(unexpected_internal_key)" not in text
    assert "(" + raw + ")" not in text


def test_basis_user_label_helper_returns_empty_for_unregistered() -> None:
    """_basis_user_label 은 미등록 값에 대해 빈 문자열 반환."""
    assert _basis_user_label("one_month") == "최근 1개월"
    assert _basis_user_label("daily") == "일간"
    assert _basis_user_label("three_month") == "최근 3개월"
    assert _basis_user_label("unknown_basis") == ""
    assert _basis_user_label("") == ""


def test_market_view_header_has_no_internal_source_key() -> None:
    """[시장 흐름 연결] 헤더에 (market_view) 등 내부 source key 접미 없음.

    holdings_observation_lines 가 생성하는 헤더는 순수 "[시장 흐름 연결]" 이어야 함.
    """
    from app.push_context_holdings import holdings_observation_lines

    pc = {
        "holdings_view": {
            "observations": [{"text": "종목A 관찰 필요"}],
            "review_points": [],
        },
        "market_view": {
            "observations": [
                {"type": "overnight_us", "summary_text": "NASDAQ +0.85%"},
            ],
        },
    }
    lines = holdings_observation_lines(pc)
    joined = "\n".join(lines)
    assert "[시장 흐름 연결]" in joined
    assert "(market_view)" not in joined
