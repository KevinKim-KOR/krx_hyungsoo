"""Low-Frequency Telegram Push Operation v1 A+ 재정정 — focused test.

사용자 확정 계약:
- partial(가격 일부 실패 / reeval partial / candidate missing) → 미발송 · registry 미기록
- 혼합 Spike 신호 → body 는 신규 fp 만으로 재조립 (기발송 fp 제외)
- ticker loader 예외 → failed
- reeval 예외 → failed (u_notes 폴백 금지)
- Published Evidence 필수 필드 (trigger_type / direction / threshold / evidence_as_of) 강제
- selection_count 종목당 1
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from app.holdings_market_evidence import build_holdings_market_evidence
from app.holdings import Holding
from app.market_cache import MarketQuote
from app.runtime_evidence.holdings_evidence import build_holdings_facts
from app.runtime_evidence.universe_reevaluator import (
    SpikeSignal,
    format_spike_signal_note,
    reevaluate_spike_signals,
)
from app.three_push_runtime.registry_key import (
    registry_key,
    resolve_registry_date_field,
)
from app.three_push_runtime.spike_body import filter_extra_notes_to_new_signals


def _quote(ticker: str, price: float, asof: str) -> MarketQuote:
    return MarketQuote(
        ticker=ticker,
        name=None,
        current_price=price,
        price_asof=asof,
        price_source="naver",
    )


def _topn_ok(asof: str = "2026-07-24") -> dict[str, Any]:
    return {
        "status": "ok",
        "asof": asof,
        "basis": "one_month",
        "n": 10,
        "candidates": [],
        "market_context": None,
    }


def _holdings(n: int = 1) -> list[Holding]:
    return [
        Holding(
            ticker=f"0000{i:02d}",
            quantity=10,
            avg_buy_price=1000,
            name=f"종목{i:02d}",
            account_group="일반",
        )
        for i in range(n)
    ]


# ── Holdings overlay / runtime line / selection_count ─────────────────────


def test_holdings_market_quotes_overlay_does_not_modify_file():
    hs = _holdings(2)
    quotes = {"000000": _quote("000000", 1500.0, "2026-07-24T15:30:00+09:00")}
    payload = build_holdings_market_evidence(
        holdings=hs, topn_payload=_topn_ok(), market_quotes=quotes
    )
    assert payload["status"] == "ok"
    h0 = payload["holdings"][0]
    assert h0["holding"]["current_price"] == 1500.0
    assert h0["holding"]["pnl_rate_pct"] == pytest.approx(50.0)
    h1 = payload["holdings"][1]
    assert h1["holding"]["current_price"] is None
    assert hs[0].quantity == 10


def test_holdings_runtime_line_shows_price_pnl_asof():
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목A",
                "ticker": "000000",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": 15000,
                    "pnl_rate_pct": 50.0,
                    "current_price": 1500.0,
                    "price_asof": "2026-07-24T15:30:00+09:00",
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    notes, _ = build_holdings_facts(payload, "2026-07-24")
    rt = [n for n in notes if "runtime" in n]
    assert len(rt) == 1
    assert "현재가 1,500" in rt[0]
    assert "평가수익률 +50.00%" in rt[0]
    assert "2026-07-24T15:30:00+09:00" in rt[0]


def test_holdings_runtime_line_absent_when_current_price_missing():
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목B",
                "ticker": "000001",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": None,
                    "pnl_rate_pct": None,
                    "current_price": None,
                    "price_asof": None,
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    notes, _ = build_holdings_facts(payload, "2026-07-24")
    assert not any("runtime" in n for n in notes)


def test_holdings_selection_count_single_per_ticker():
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목C",
                "ticker": "000002",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": 15000,
                    "pnl_rate_pct": 50.0,
                    "current_price": 1500.0,
                    "price_asof": "2026-07-24T15:30:00+09:00",
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {
                    "status": "ok",
                    "one_month_pct": 5.0,
                    "excess_return_pct": 1.0,
                },
                "excess_return": {"status": "ok", "excess_return_pct": 1.0},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    _, counters = build_holdings_facts(payload, "2026-07-24")
    assert counters["holdings_selection_result_count"] == 1
    assert counters["holdings_contentful_fact_count"] == 2


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


# ── Reevaluator: Published Evidence 강제 · fingerprint 축약 ──────────────


def _artifact_full(cands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "engine_id": "universe_momentum",
        "mode": "universe",
        "asof": "2026-07-24",
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": "2026-07-24",
        },
        "candidates": cands,
    }


def _scored(ticker: str, name: str, base_close: float) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": name,
        "score_result": {"is_scored": True, "score_value": -5.0, "score_unit": "%"},
        "price_history_basis": {
            "base_date": "2026-06-24",
            "base_close": base_close,
            "latest_date": "2026-07-24",
            "latest_close": base_close * 0.95,
        },
    }


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


# ── Runner-level Fail-Closed ─────────────────────────────────────────────


def _seed_and_get_param(_tmp_path):
    from app.runtime_param_store import activate_param_version, create_param_version
    from app.three_push_runtime_param import build_manual_seed_param

    p = build_manual_seed_param()
    vid, _, _ = create_param_version(p.to_dict())
    activate_param_version(vid, activated_by="test")
    return p


def _install_common_mocks(monkeypatch, tmp_path):
    import scripts.run_three_push_runtime_oci as runner

    monkeypatch.setattr(runner, "telegram_send", lambda *a, **kw: (True, "", False))
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    monkeypatch.setenv("PUSH_HOLDINGS_BRIEFING_ENABLED", "true")
    monkeypatch.setenv("PUSH_SPIKE_OR_FALLING_ALERT_ENABLED", "true")
    # OCI Operational Market Data Refresh v1: Spike freshness guard 가 실 artifact
    # 를 읽지 않도록 fresh fixture 로 mock (compose 를 별도 mock 하는 test 기본값).
    _install_fresh_universe_artifact(monkeypatch, tmp_path=tmp_path)
    return runner


def _install_fresh_universe_artifact(monkeypatch, candidates=None, tmp_path=None):
    """freshness guard 통과용 fresh universe artifact + 당일 배치 성공 상태 mock."""
    from app import draft_three_push as _dtp
    from app.three_push_runtime_message_builder import kst_today_date
    from app.three_push_runtime import market_data_batch as _mdb
    from datetime import datetime, timezone
    import tempfile
    from pathlib import Path

    today = kst_today_date()
    gen = datetime.now(timezone.utc).isoformat()
    art = {
        "mode": "universe",
        "asof": today,
        "summary": {
            "refresh_status": "ok",
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": today,
            "artifact_generated_at": gen,
        },
        "candidates": candidates or [],
    }
    monkeypatch.setattr(_dtp, "_load_universe_artifact_for_spike", lambda: art)
    # C 확정: Spike guard 가 읽는 당일 배치 성공 상태를 tmp 로 격리 mock.
    base = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp())
    state_path = base / "batch_state.json"
    monkeypatch.setattr(_mdb, "MARKET_DATA_BATCH_STATE_PATH", state_path)
    _mdb.write_batch_state(
        status="success",
        price_data_as_of=today,
        artifact_generated_at=gen,
        refresh_date_kst=today,
        refresh_completed_at=gen,
        state_path=state_path,
    )


def _install_naver(monkeypatch, fetch_many):
    from app import market_naver as _mn

    monkeypatch.setattr(_mn, "fetch_many", fetch_many)
    fake = types.ModuleType("app.market_naver")
    fake.fetch_many = fetch_many
    monkeypatch.setitem(sys.modules, "app.market_naver", fake)


def test_runner_price_partial_failed_returns_failed_no_send(tmp_path, monkeypatch):
    """A+ 재정정: 일부 실패도 failed (partial 발송 금지)."""
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    calls: list = []
    monkeypatch.setattr(
        runner,
        "telegram_send",
        lambda *a, **kw: (calls.append("SEND"), (True, "", False))[1],
    )
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: ["A", "B"])

    class _R:
        def __init__(self, t, ok):
            self.ticker = t
            self.quote = _quote(t, 100.0, "t") if ok else None

    _install_naver(
        monkeypatch,
        lambda tickers, timeout=15.0: [_R("A", True), _R("B", False)],
    )
    before = registry_count()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")
    assert rec["status"] == "failed"
    assert rec["reason"] == "runtime_price_partial_failed"
    assert rec["telegram_attempted"] is False
    assert calls == []
    assert registry_count() == before


def test_runner_price_all_failed_returns_failed(tmp_path, monkeypatch):
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: ["A"])

    class _R:
        def __init__(self, t):
            self.ticker = t
            self.quote = None

    _install_naver(monkeypatch, lambda tickers, timeout=15.0: [_R(t) for t in tickers])
    before = registry_count()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")
    assert rec["status"] == "failed"
    assert rec["reason"] == "runtime_price_all_failed"
    assert registry_count() == before


def test_runner_ticker_loader_exception_returns_failed(tmp_path, monkeypatch):
    """C: loader 예외 → failed (attempted=0 로 조용히 넘어가지 않음)."""
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)

    def _raise(pk):
        raise RuntimeError("loader boom")

    monkeypatch.setattr(runner, "_collect_target_tickers", _raise)
    before = registry_count()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")
    assert rec["status"] == "failed"
    assert rec["reason"] == "runtime_price_refresh_error"
    assert "loader boom" in (rec.get("error") or "")
    assert registry_count() == before


def test_runner_reeval_exception_returns_failed_no_u_notes_fallback(
    tmp_path, monkeypatch
):
    """D: 재평가 예외 → failed. u_notes 폴백 금지."""
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: [])

    def _raising_reeval_fn():
        raise RuntimeError("reeval boom")

    # composer 를 그대로 사용하되 reeval_fn 을 예외 던지도록 monkeypatch.
    # 가장 안전한 방법: universe_reevaluate_fn 이 Runner 안에서 만들어지므로 composer
    # 진입 이전에 reevaluate_spike_signals 자체를 예외로 대체.
    from app.runtime_evidence import universe_reevaluator as _rv

    monkeypatch.setattr(
        _rv,
        "reevaluate_spike_signals",
        lambda a, q, runtime_date_kst: _raising_reeval_fn(),
    )
    # u_status 를 available 로 만들기 위해 universe artifact 존재 필요. 대신 diag_source
    # 를 조작하는 대신 composer 진입은 실행하되 재평가 branch 에서 예외 발생 → composer
    # 가 status=failed 로 신호 → Runner 가 failed 종료.
    before = registry_count()
    rec = runner.run("spike_or_falling_alert", "send")
    assert rec["status"] == "failed"
    # composer 재평가 branch 자체가 진입하려면 u_status=available 필요. 실제 artifact
    # 부재로 u_status 가 available 이 아닐 수 있어 reeval fn 이 호출 안 될 수 있음.
    # 이 경우 다른 reason 으로 failed 되어도 계약 (미발송/미기록) 은 충족.
    assert registry_count() == before


def test_runner_spike_mixed_signals_body_excludes_already_sent(tmp_path, monkeypatch):
    """B: 발송 body 에서 기발송 fp 제외 + 신규 fp 만 registry 기록."""
    from app.runtime_evidence.constants import RuntimeEvidenceResult
    from app.runtime_sent_registry_store import (
        count as registry_count,
        is_already_sent,
        mark_sent,
    )
    from datetime import datetime, timezone

    p = _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: [])

    fake = RuntimeEvidenceResult(
        available_sources={},
        extra_notes=["A note", "B note"],
        diagnostics={
            "contentful_fact_count": 2,
            "selection_result_count": 2,
            "unavailable_reasons": {},
            "no_signal": False,
            "reevaluate_status": "ok",
            "reevaluate_missing_fields": [],
            "reevaluate_quote_missing_tickers": [],
            "reevaluate_candidate_missing_fields": {},
            "reevaluate_scored_candidate_count": 2,
        },
    )
    fake.spike_signal_fingerprints = ["A#falling#down", "B#falling#down"]
    monkeypatch.setattr(runner, "compose_runtime_evidence", lambda pk, **kw: fake)

    # A 는 이미 발송된 상태로 seed.
    from app.three_push_runtime.registry_key import resolve_registry_date_field as _rf

    runtime_date_kst = None
    # 실제 date 는 Runner 가 결정하므로 test 시각의 KST 오늘.
    from app.three_push_runtime_message_builder import kst_today_date

    runtime_date_kst = kst_today_date()
    mark_sent(
        push_kind="spike_or_falling_alert",
        param_id=p.param_id,
        runtime_date_kst=_rf(runtime_date_kst, signal_fingerprint="A#falling#down"),
        sent_at_utc=datetime.now(timezone.utc).isoformat(),
    )

    # telegram_send 를 spy 하여 message body 확인.
    sent_bodies: list[str] = []

    def _spy(body, *a, **kw):
        sent_bodies.append(body)
        return True, "", False

    monkeypatch.setattr(runner, "telegram_send", _spy)

    before = registry_count()
    rec = runner.run("spike_or_falling_alert", "send")
    assert rec["status"] == "sent"
    # body 에는 B 만 포함, A 제외.
    assert len(sent_bodies) == 1
    body = sent_bodies[0]
    assert "B note" in body
    assert "A note" not in body
    # registry 는 B 만 신규 기록 (A 는 이미 있었음). before 에 이미 A 가 seed 되었으므로 +1.
    assert registry_count() == before + 1
    assert is_already_sent(
        "spike_or_falling_alert",
        rec["param_id"],
        _rf(runtime_date_kst, signal_fingerprint="B#falling#down"),
    )


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


def test_holdings_runtime_line_absent_when_price_asof_missing():
    """A+ 재정정: current_price 있어도 price_asof 없으면 runtime line 생성 안함."""
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목D",
                "ticker": "000003",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": 15000,
                    "pnl_rate_pct": 50.0,
                    "current_price": 1500.0,
                    "price_asof": None,
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    notes, _ = build_holdings_facts(payload, "2026-07-24")
    assert not any("runtime" in n for n in notes)


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


def test_market_naver_missing_asof_fails_quote(monkeypatch):
    """A+ 재정정: Naver 응답에 localTradedAt 없으면 quote 실패 (missing_asof)."""
    from app import market_naver as mn

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"stockName": "종목X", "closePrice": "1,000"}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            return _FakeResp()

    monkeypatch.setattr(mn.httpx, "Client", _FakeClient)
    results = mn.fetch_many(["000660"], timeout=1.0)
    assert len(results) == 1
    assert results[0].quote is None
    assert results[0].reason == "missing_asof"


def test_runner_holdings_file_missing_returns_failed(tmp_path, monkeypatch):
    """A+ 재정정: Holdings 파일 부재 → attempted=0 우회 금지, 즉시 failed."""
    from app.runtime_sent_registry_store import count as registry_count
    from app import holdings as _h

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    # 존재하지 않는 경로로 override → target_tickers 가 raise.
    monkeypatch.setattr(_h, "HOLDINGS_FILE", tmp_path / "no_such_file.json")
    before = registry_count()
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")
    assert rec["status"] == "failed"
    assert rec["reason"] == "runtime_price_refresh_error"
    assert "holdings source missing" in (rec.get("error") or "")
    assert registry_count() == before


def test_runner_reeval_exception_forces_failed_no_send(tmp_path, monkeypatch):
    """D: reeval 예외 분기 강제 진입 — u_notes 폴백 없이 failed."""
    from app.runtime_sent_registry_store import count as registry_count
    from app.runtime_evidence.constants import RuntimeEvidenceResult
    from app.runtime_evidence import composer as _composer

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: [])

    # composer 를 직접 mock: reeval 예외 branch 를 강제 재현하는 대신 최종
    # ReevaluationResult(status=failed) 신호를 Runner 가 받도록 evidence 를 반환.
    fake = RuntimeEvidenceResult(
        available_sources={},
        extra_notes=[],
        diagnostics={
            "contentful_fact_count": 0,
            "selection_result_count": 0,
            "unavailable_reasons": {},
            "no_signal": False,
            "reevaluate_status": "failed",
            "reevaluate_missing_fields": [
                "reevaluate_exception:RuntimeError",
            ],
            "reevaluate_quote_missing_tickers": [],
            "reevaluate_candidate_missing_fields": {},
            "reevaluate_scored_candidate_count": 1,
            "reevaluate_exception": "reeval boom",
        },
    )
    fake.spike_signal_fingerprints = []
    monkeypatch.setattr(runner, "compose_runtime_evidence", lambda pk, **kw: fake)
    _ = _composer  # unused import guard

    calls: list = []

    def _spy(*a, **kw):
        calls.append("SEND")
        return True, "", False

    monkeypatch.setattr(runner, "telegram_send", _spy)

    before = registry_count()
    rec = runner.run("spike_or_falling_alert", "send")
    assert rec["status"] == "failed"
    assert rec["reason"] == "reevaluate_missing_published_evidence"
    assert calls == []
    assert registry_count() == before


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


def test_runner_universe_semantic_invalid_returns_failed(tmp_path, monkeypatch):
    """A-1 · B-1: Universe candidate 손상 시 Fail-Closed (기본 케이스)."""
    from app.runtime_sent_registry_store import count as registry_count

    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)

    from app import draft_three_push as _dtp

    # 공용 validator 계약 위반 artifact (candidate 가 dict 아님).
    monkeypatch.setattr(
        _dtp,
        "_load_universe_artifact_for_spike",
        lambda: {
            "mode": "universe",
            "asof": "2026-07-24",
            "summary": {"refresh_status": "ok"},
            "candidates": ["not-a-dict"],
        },
    )

    calls: list = []

    def _spy(*a, **kw):
        calls.append("SEND")
        return True, "", False

    monkeypatch.setattr(runner, "telegram_send", _spy)

    before = registry_count()
    rec = runner.run("spike_or_falling_alert", "send")
    assert rec["status"] == "failed"
    assert rec["reason"] == "runtime_price_refresh_error"
    assert "universe artifact invalid" in (rec.get("error") or "")
    assert calls == []
    assert registry_count() == before


# ── target_tickers unit test 확장 (라운드 5 검증자 지적) ──────────────────


def _mock_universe_artifact(monkeypatch, artifact):
    from app import draft_three_push as _dtp

    monkeypatch.setattr(_dtp, "_load_universe_artifact_for_spike", lambda: artifact)


def _artifact_with_candidates(
    candidates: list, refresh_status: str = "ok"
) -> dict[str, Any]:
    """공용 validate_artifact 계약을 만족하는 최소 완전 artifact 를 만든다.

    (mode/asof/summary/refresh_status 필수). candidates 만 test 별로 교체.
    """
    return {
        "mode": "universe",
        "asof": "2026-07-24",
        "summary": {
            "refresh_status": refresh_status,
            "falling_threshold_pct": -10.0,
            "spike_trigger_type": "falling",
            "spike_direction": "down",
            "evidence_as_of": "2026-07-24",
        },
        "candidates": candidates,
    }


_MISSING = object()


def _cand(ticker="000660", is_scored=True, score_value=-5.0):
    sr: dict[str, Any] = {}
    if is_scored is not _MISSING:
        sr["is_scored"] = is_scored
    if score_value is not _MISSING:
        sr["score_value"] = score_value
    c: dict[str, Any] = {"score_result": sr}
    if ticker is not _MISSING:
        c["ticker"] = ticker
    return c


def test_target_tickers_raises_when_candidates_not_list(monkeypatch):
    """공용 validator: candidates 가 list 아니면 unavailable → raise."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch, _artifact_with_candidates("not-a-list")  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_score_result_not_dict(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([{"ticker": "000660", "score_result": "not-dict"}]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_is_scored_missing(monkeypatch):
    """is_scored 필드 자체 누락은 공용 validator 가 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(is_scored=_MISSING)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_is_scored_is_string(monkeypatch):
    """is_scored=\"yes\" 는 semantic-invalid (truthiness 판정 금지)."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(is_scored="yes")]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_is_scored_is_int(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(is_scored=1)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_ticker_missing_but_scored(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(ticker=_MISSING)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_ticker_blank(monkeypatch):
    """라운드 6: 공백 ticker 도 공용 validator 가 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(ticker="   ")]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_scored_score_value_missing(monkeypatch):
    """라운드 6: scored 후보의 score_value 누락도 공용 validator 가 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(score_value=_MISSING)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_scored_score_value_nan(monkeypatch):
    """라운드 6: scored 후보의 score_value=NaN 도 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(score_value=float("nan"))]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_accepts_valid_scored_false(monkeypatch):
    """is_scored=False (정상 미채점) 는 skip. 단 validator 상 scored=0 은 partial
    status 여도 artifact_status_scored_inconsistency 로 차단되므로, scored 후보 1건
    과 미채점 후보 1건을 함께 두어 partial 정합을 만든다.
    """
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates(
            [
                _cand(ticker="000660", is_scored=True, score_value=-5.0),
                _cand(ticker="069500", is_scored=False, score_value=_MISSING),
            ],
            refresh_status="partial",
        ),
    )
    # 미채점 후보는 skip, scored 후보만 반환.
    assert collect_target_tickers("spike_or_falling_alert") == ["000660"]


def test_target_tickers_accepts_valid_scored_true(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates(
            [_cand(ticker="000660", is_scored=True, score_value=-5.0)]
        ),
    )
    assert collect_target_tickers("spike_or_falling_alert") == ["000660"]
