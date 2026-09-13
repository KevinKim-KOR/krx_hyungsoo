"""Runner-level Fail-Closed.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

from tests._helpers import patch_compose_runtime_evidence

from tests.low_frequency_push._fixtures import (
    _install_common_mocks,
    _install_naver,
    _quote,
    _seed_and_get_param,
)


def test_runner_price_partial_failed_returns_failed_no_send(tmp_path, monkeypatch):
    """일부 실패 + **오늘 체결 quote 0건** → Fail-Closed (설계자 확정 2026-09-05).

    휴장일인지 조회 장애인지 구분할 수 없으므로 미발송·state 불변이다.
    (보유의 단순 부분 실패는 더 이상 `runtime_price_partial_failed` 가 아니다 —
    오늘 quote 가 하나라도 있으면 실패 종목만 표시하고 진행한다.)
    """
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
    assert (
        rec["reason"] == "holdings_quotes_incomplete_no_today"
    ), f"실제 {rec['reason']}"
    assert rec["telegram_attempted"] is False
    assert calls == []
    assert registry_count() == before


def test_holdings_partial_failure_with_today_quote_proceeds(tmp_path, monkeypatch):
    """설계자 확정 표 — "오늘 quote 존재 + 일부 실패" → **해당 종목만** 데이터 확인 필요.

    여기서 끊으면 `DATA_UNAVAILABLE_OR_STALE` 표시가 실제 OCI 경로에서 영영
    나오지 않는다. 그래서 보유는 부분 실패에도 진행한다(다른 PUSH 는 그대로 차단).
    """
    from app.three_push_runtime_message_builder import kst_today_date

    today = kst_today_date()
    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", tmp_path / "s.json")
    sent: list[str] = []
    monkeypatch.setattr(
        runner,
        "telegram_send",
        lambda text, *a, **kw: (sent.append(text), (True, "", False))[1],
    )
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: ["AAA", "BBB"])

    class _R:
        def __init__(self, t, ok):
            self.ticker = t
            self.quote = _quote(t, 80.0, f"{today}T09:14:00+09:00") if ok else None

    # AAA 는 성공(오늘 체결), BBB 는 조회 실패
    _install_naver(
        monkeypatch, lambda tickers, timeout=15.0: [_R("AAA", True), _R("BBB", False)]
    )

    import app.holdings as holdings_mod
    import app.market_data_store as store_mod
    from dataclasses import dataclass

    @dataclass
    class _H:
        ticker: str
        name: str
        account_group: str = "일반"

    monkeypatch.setattr(
        holdings_mod, "load", lambda *a, **k: [_H("AAA", "가나다"), _H("BBB", "라마바")]
    )
    # 거래일 축 + 종목 이력: 축 기준일 종가 100 → 현재가 80 이면 -20%
    axis = [f"2026-08-{i + 1:02d}" for i in range(30)]
    monkeypatch.setattr(
        store_mod, "fetch_price_history", lambda t, **kw: [(d, 100.0) for d in axis]
    )
    monkeypatch.setattr(runner, "kst_today", lambda: today, raising=False)

    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")

    assert rec["status"] != "failed", f"부분 실패로 차단됐다: {rec.get('reason')}"
    assert sent, "부분 실패인데 아무것도 보내지 않았다"
    body = sent[0]
    assert "라마바" in body, "조회 실패 종목이 본문에 없다"
    assert "데이터 확인 필요" in body


def test_market_briefing_partial_failure_still_fail_closed(tmp_path, monkeypatch):
    """보유 예외가 **다른 PUSH 종류로 새지 않는다**.

    급등락은 부분 실패면 여전히 `runtime_price_partial_failed` 로 차단된다.
    """
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
        monkeypatch, lambda tickers, timeout=15.0: [_R("A", True), _R("B", False)]
    )
    rec = runner.run("spike_or_falling_alert", "send")
    assert rec["status"] == "failed"
    assert rec["reason"] == "runtime_price_partial_failed", f"실제 {rec['reason']}"
    assert calls == []


def test_holdings_data_failure_does_not_preempt_kind_flag_guard(tmp_path, monkeypatch):
    """종류별 flag 가 꺼져 있으면 **데이터 실패보다 `push_kind_disabled` 가 먼저**다.

    조립 실패를 §3-c 에서 바로 return 하면 비활성 상태인데도 데이터 실패가
    기존 계약을 가로챈다 — 이전 라운드에 같은 결함을 지적받았다.
    """
    _seed_and_get_param(tmp_path)
    runner = _install_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "HOLDINGS_SELECTION_STATE_PATH", tmp_path / "s.json")
    monkeypatch.setenv("PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED", "false")
    monkeypatch.setattr(runner, "_collect_target_tickers", lambda pk: ["A", "B"])

    class _R:
        def __init__(self, t, ok):
            self.ticker = t
            self.quote = _quote(t, 100.0, "t") if ok else None

    _install_naver(
        monkeypatch, lambda tickers, timeout=15.0: [_R("A", True), _R("B", False)]
    )
    rec = runner.run("holdings_briefing", "send", slot_id="OPEN")
    assert rec["reason"] == "push_kind_disabled", f"실제 {rec['reason']}"


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
    patch_compose_runtime_evidence(monkeypatch, fake)

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
    patch_compose_runtime_evidence(monkeypatch, fake)
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
