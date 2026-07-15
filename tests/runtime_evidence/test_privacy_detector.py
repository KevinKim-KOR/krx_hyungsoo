"""Privacy detector — 실제 값 감지 · boolean 계약 · false-positive 회피.

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.runtime_evidence._fixtures import (
    _evidence_matched,
    _make_result_for_holdings_briefing,
    _nav_ok,
)


def test_holdings_privacy_fields_are_boolean_r5(tmp_path: Path) -> None:
    """FIX r5: private_fields_exposed / raw_identifier_exposed 는 boolean."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched)
    d = r.diagnostics
    assert isinstance(d.get("private_fields_exposed"), bool)
    assert isinstance(d.get("raw_identifier_exposed"), bool)
    assert d["private_fields_exposed"] is False
    assert d["raw_identifier_exposed"] is False


def test_holdings_privacy_detects_actual_value_leak_r5(tmp_path: Path) -> None:
    """FIX r5: 실제 개인정보 값이 notes 에 나타나면 True."""

    def _leaky_evidence(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "market_asof": "2026-07-11",
            "market_context": {},
            "summary": {},
            "holdings": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200 수량 10 평단 35000",
                    "returns": {"status": "unavailable"},
                    "excess_return": {"status": "unavailable"},
                    "topn_match": {"status": "matched_topn_candidate", "rank": 1},
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    r = _make_result_for_holdings_briefing(tmp_path, _leaky_evidence)
    assert r.diagnostics["private_fields_exposed"] is True


def test_holdings_privacy_detects_evaluation_amount_r7(tmp_path: Path) -> None:
    """FIX r7 (Round 3C · §7.1): 평가금액 (evaluation_amount) 노출 감지.

    평가금액 = quantity × market_price 이며 invested_amount (= avg × qty) 와 다르다.
    detector 는 evidence_payload 의 `holding.evaluation_amount` 힌트를 참고해
    실제 평가금액 값이 notes 안에 노출되면 True 로 감지해야 한다.

    반증 시나리오:
    - _fake_holdings_ok: qty=10, avg=35000 → invested_amount=350000
    - 이 test 의 평가금액=400000 (avg × qty 와 다른 값)
    - 만약 detector 가 invested_amount 만 검사한다면 400000 은 감지 못 함.
    """

    def _leaky_eval_amount(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "market_asof": "2026-07-11",
            "market_context": {},
            "summary": {},
            "holdings": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    # holding block 에 실제 평가금액 힌트 (invested=350000 과 다른 400000).
                    "holding": {
                        "quantity": 10.0,
                        "avg_buy_price": 35000.0,
                        "evaluation_amount": 400000.0,
                        "pnl_rate_pct": 14.28,
                    },
                    # notes 에 평가금액 400000 이 개인정보 문맥과 함께 노출된 상황.
                    "returns": {"status": "unavailable"},
                    "excess_return": {"status": "unavailable"},
                    "topn_match": {"status": "unavailable"},
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    # notes 에 평가금액 값을 직접 넣기 위해 이름에 삽입 (test 시나리오 시뮬레이션).
    def _leaky_with_eval_in_name(**_kwargs: Any) -> dict[str, Any]:
        payload = _leaky_eval_amount(**_kwargs)
        payload["holdings"][0]["name"] = "KODEX 200 평가금액 400000"
        # notes 생성을 위해 유효 evidence 신호 추가 (matched_topn_candidate).
        payload["holdings"][0]["topn_match"] = {
            "status": "matched_topn_candidate",
            "rank": 1,
        }
        return payload

    r = _make_result_for_holdings_briefing(tmp_path, _leaky_with_eval_in_name)
    # 평가금액 400000 은 invested_amount (350000) 와 다른 값이지만 detector 가 감지.
    assert r.diagnostics["private_fields_exposed"] is True


def test_holdings_privacy_detects_short_two_char_value_r6(tmp_path: Path) -> None:
    """FIX r6: quantity=10 (2자) 노출도 감지."""

    def _leaky_qty10_evidence(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "market_asof": "2026-07-11",
            "market_context": {},
            "summary": {},
            "holdings": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200 보유수량 10주",
                    "returns": {"status": "unavailable"},
                    "excess_return": {"status": "unavailable"},
                    "topn_match": {"status": "matched_topn_candidate", "rank": 1},
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    r = _make_result_for_holdings_briefing(tmp_path, _leaky_qty10_evidence)
    assert r.diagnostics["private_fields_exposed"] is True


def test_holdings_briefing_message_privacy_and_content_r3(tmp_path: Path) -> None:
    """FIX r3 Q4 (c): Composer extra_notes 에 개인정보/금지 문구 미노출."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched, nav_fn=_nav_ok)
    text = "\n".join(r.extra_notes)
    assert "KODEX 200" in text
    assert "2026-07-11" in text
    for kw in (
        "avg_buy_price",
        "account_group",
        "quantity",
        "invested_amount",
        "35000",
        "350000",
    ):
        assert kw not in text, f"forbidden {kw!r} leaked in extra_notes"
    for kw in (
        "unavailable_external_fetch_required",
        "unavailable_not_implemented",
        "holdings_source_missing",
    ):
        assert kw not in text
    assert r.diagnostics.get("private_fields_exposed") is False
    assert r.diagnostics.get("raw_identifier_exposed") is False


def test_holdings_message_body_no_privacy_leakage_via_build_runtime_message_r3(
    tmp_path: Path,
) -> None:
    """FIX r4 Q4 (b·c): 실제 build_runtime_message() 결과 본문에 개인정보 미노출."""
    from app.three_push_runner_common import (
        FORBIDDEN_PHRASES,
        check_forbidden_wording,
    )
    from app.three_push_runtime_message_builder import build_runtime_message
    from app.three_push_runtime_param import RuntimeParam

    ev = _make_result_for_holdings_briefing(tmp_path, _evidence_matched, nav_fn=_nav_ok)
    param = RuntimeParam(
        param_id="test",
        created_at="2026-07-11T00:00:00+00:00",
        approved_at="2026-07-11T00:00:00+00:00",
        approved_by="test",
        param_source="manual",
        enabled_push_kinds=["holdings_briefing"],
        runtime_policy={},
        evidence_policy={},
        safety_policy={},
    )
    body = build_runtime_message(
        push_kind="holdings_briefing",
        param=param,
        runtime_kst_iso="2026-07-11T09:00:00+09:00",
        available_sources=ev.available_sources,
        extra_notes=ev.extra_notes,
    )
    assert "KODEX 200" in body
    assert "2026-07-11" in body
    for kw in (
        "avg_buy_price",
        "account_group",
        "quantity",
        "invested_amount",
        "35000",
        "350000",
    ):
        assert kw not in body, f"forbidden {kw!r} leaked in message body"
    assert check_forbidden_wording(body) is None
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in body, f"FORBIDDEN_PHRASE {phrase!r} leaked"
    for kw in (
        "unavailable_external_fetch_required",
        "unavailable_not_implemented",
        "holdings_source_missing",
    ):
        assert kw not in body
