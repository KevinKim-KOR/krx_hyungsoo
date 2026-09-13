"""Reevaluator — Published Evidence 강제 · fingerprint 축약.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

from app.market_cache import MarketQuote

from app.runtime_evidence.universe_reevaluator import reevaluate_spike_signals

from tests.low_frequency_push._fixtures import (
    _artifact_full,
    _quote,
    _scored,
)


def test_reeval_uses_published_trigger_direction():
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    quotes = {"000660": _quote("000660", 700.0, "2026-07-24T15:30:00+09:00")}
    r = reevaluate_spike_signals(art, quotes, runtime_date_kst="2026-07-24")
    assert r.status == "ok"
    assert len(r.signals) == 1
    assert r.signals[0].fingerprint == "000660#falling#down"
    assert "2026-07-24" not in r.signals[0].fingerprint


def test_reeval_missing_threshold_returns_failed():
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    del art["summary"]["falling_threshold_pct"]
    r = reevaluate_spike_signals(art, {}, runtime_date_kst="2026-07-24")
    assert r.status == "failed"
    assert "falling_threshold_pct" in r.missing_fields


def test_reeval_missing_trigger_type_returns_failed():
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    del art["summary"]["spike_trigger_type"]
    r = reevaluate_spike_signals(art, {}, runtime_date_kst="2026-07-24")
    assert r.status == "failed"
    assert "spike_trigger_type" in r.missing_fields


def test_reeval_missing_evidence_as_of_returns_failed():
    """A+ 재정정: evidence_as_of 도 필수."""
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    del art["summary"]["evidence_as_of"]
    r = reevaluate_spike_signals(art, {}, runtime_date_kst="2026-07-24")
    assert r.status == "failed"
    assert "evidence_as_of" in r.missing_fields


def test_reeval_missing_base_date_reports_candidate_missing():
    """A+ 재정정: base_date 도 필수 per-candidate 필드."""
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    del art["candidates"][0]["price_history_basis"]["base_date"]
    quotes = {"000660": _quote("000660", 700.0, "2026-07-24T15:30:00+09:00")}
    r = reevaluate_spike_signals(art, quotes, runtime_date_kst="2026-07-24")
    assert r.status == "partial"
    assert "000660" in r.candidate_missing_fields
    assert "price_history_basis.base_date" in r.candidate_missing_fields["000660"]


def test_reeval_missing_quote_reports_partial():
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    r = reevaluate_spike_signals(art, {}, runtime_date_kst="2026-07-24")
    assert r.status == "partial"
    assert r.quote_missing_tickers == ["000660"]


def test_reeval_multiple_signals_all_returned():
    art = _artifact_full(
        [
            _scored("000660", "SK하이닉스", 1000.0),
            _scored("069500", "KODEX 200", 100000.0),
        ]
    )
    quotes = {
        "000660": _quote("000660", 700.0, "t"),
        "069500": _quote("069500", 85000.0, "t"),
    }
    r = reevaluate_spike_signals(art, quotes, runtime_date_kst="2026-07-24")
    assert r.status == "ok"
    assert [s.fingerprint for s in r.signals] == [
        "000660#falling#down",
        "069500#falling#down",
    ]


# ── as-of · loader · spike_body raise · reeval 예외 강제 ──────────────────


def test_reeval_missing_asof_reports_partial():
    """A+ 재정정: price_asof 없는 quote 도 partial (quote_missing) 처리."""
    art = _artifact_full([_scored("000660", "SK하이닉스", 1000.0)])
    # asof=None 인 quote.
    q = MarketQuote(
        ticker="000660",
        name=None,
        current_price=700.0,
        price_asof=None,
        price_source="naver",
    )
    r = reevaluate_spike_signals(art, {"000660": q}, runtime_date_kst="2026-07-24")
    assert r.status == "partial"
    assert r.quote_missing_tickers == ["000660"]
    assert r.signals == []


def test_composer_reeval_fn_exception_produces_failed_result(monkeypatch):
    """D 실제 변환 경로: composer 의 reeval_fn 예외 → status=failed diagnostic.

    라운드 5 정정: u_status="available" 을 강제하여 반드시 reeval_fn 이 호출되도록
    한다. 이전 조건부 assert 는 환경 (universe artifact 존재 여부) 에 의존하여
    회귀 안전망이 취약했다.
    """
    from app.runtime_evidence.composer import (
        compose_runtime_evidence as _lowlevel,
    )
    from app.runtime_evidence import composer as _composer_mod

    # composer.compose_runtime_evidence 안의 compose_universe_momentum 을 mock 하여
    # u_status="available" 을 강제. 이렇게 하면 reeval_fn 이 반드시 호출된다.
    def _fake_compose_um(*a, **kw):
        return (
            "available",
            [],
            {
                "universe_snapshot_status": "available",
                "universe_snapshot_reason": "",
                "universe_artifact_present": True,
                "universe_artifact_valid": True,
                "universe_artifact_status": "available",
                "universe_artifact_asof": "2026-07-24",
                "universe_candidate_count": 1,
                "universe_selected_count": 1,
                "universe_contentful_fact_count": 0,
            },
        )

    monkeypatch.setattr(_composer_mod, "compose_universe_momentum", _fake_compose_um)

    def _boom():
        raise RuntimeError("reeval boom in fn")

    result = _lowlevel(
        "spike_or_falling_alert",
        market_quotes=None,
        universe_reevaluate_fn=_boom,
    )
    # composer 는 예외 전파 금지 + status=failed 신호를 diagnostic 에 실제 기록.
    assert result.diagnostics.get("reevaluate_status") == "failed"
    assert "reeval boom in fn" in (result.diagnostics.get("reevaluate_exception") or "")
    _ = _composer_mod  # import 보존
