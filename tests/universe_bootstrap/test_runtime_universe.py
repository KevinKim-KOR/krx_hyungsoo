"""Runtime Universe composer tests (지시문 §33.3)."""

from __future__ import annotations

from typing import Any, Optional

from app.runtime_evidence.constants import (
    SRC_KR_REALTIME,
    SRC_UNIVERSE_MOMENTUM,
)
from app.runtime_evidence.universe_momentum import compose_universe_momentum


def _artifact(
    asof: str = "2026-07-16",
    candidates: Optional[list[dict[str, Any]]] = None,
    status: str = "ok",
) -> dict[str, Any]:
    return {
        "engine_id": "momentum_engine",
        "engine_version": "v1",
        "mode": "universe",
        "asof": asof,
        "summary": {
            "refresh_status": status,
            "total_candidates": len(candidates or []),
        },
        "candidates": candidates or [],
    }


def _scored_candidate(
    rank: int, ticker: str, name: str, score: float
) -> dict[str, Any]:
    return {
        "candidate_id": f"universe|{ticker}||",
        "ticker": ticker,
        "name": name,
        "mode": "universe",
        "rank": rank,
        "score_result": {
            "is_scored": True,
            "score_value": score,
            "score_unit": "%",
            "score_basis_text": "pykrx 1개월 수익률",
            "ranking_basis": "one_month_return_pct",
        },
        "price_history_basis": {
            "base_date": "2026-06-16",
            "base_close": 100.0,
            "latest_date": "2026-07-16",
            "latest_close": 100.0 * (1 + score / 100.0),
        },
    }


# ── 33.3.1 artifact 없음 → unavailable ──


def test_universe_unavailable_when_artifact_missing() -> None:
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: None)
    assert status == "unavailable"
    assert notes == []
    assert diag["universe_snapshot_status"] == "unavailable"
    assert diag["universe_artifact_present"] is False


# ── 33.3.2 invalid artifact ──


def test_universe_unavailable_when_mode_mismatch() -> None:
    art = _artifact()
    art["mode"] = "holdings"
    status, _n, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "unavailable"
    assert diag["universe_snapshot_reason"] == "artifact_mode_mismatch"


# ── 33.3.3 as-of 없음 ──


def test_universe_unavailable_when_asof_missing() -> None:
    art = _artifact(asof="")
    status, _n, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "unavailable"
    assert diag["universe_snapshot_reason"] == "artifact_asof_missing"


# ── 33.3.4 failed artifact ──


def test_universe_unavailable_when_refresh_status_failed() -> None:
    art = _artifact(status="failed")
    status, _n, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "unavailable"
    assert diag["universe_snapshot_reason"] == "artifact_refresh_status_failed"


# ── 33.3.5 정상 후보 0건 → available + no_signal=true ──


def test_universe_available_no_signal_when_zero_candidates() -> None:
    art = _artifact(candidates=[])
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "available"
    assert notes == []
    assert diag["universe_snapshot_status"] == "available"
    assert diag["no_signal"] is True
    assert diag["universe_candidate_count"] == 0
    assert diag["universe_selected_count"] == 0
    assert diag["universe_contentful_fact_count"] == 0


# ── 33.3.6 정상 후보 1건 → available + selection>=1 + fact>=1 ──


def test_universe_available_with_one_candidate() -> None:
    art = _artifact(candidates=[_scored_candidate(1, "A", "A_name", 5.0)])
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "available"
    assert diag["universe_snapshot_status"] == "available"
    assert diag["no_signal"] is False
    assert diag["universe_selected_count"] >= 1
    assert diag["universe_contentful_fact_count"] >= 1
    assert any("A_name" in n and "2026-07-16" in n for n in notes)


# ── 33.3.7 candidate 순서 유지 (검증자 재정정: artifact 순서 그대로, Runtime 재정렬 X) ──


def test_universe_candidate_order_preserved_from_artifact() -> None:
    """검증자 재정정: Runtime 은 artifact.candidates 순서 그대로 사용.

    producer 가 이미 rank 순으로 정렬해 저장하므로 Runtime 이 재정렬하지 않는다.
    artifact 에 저장된 순서 (C→A→B) 가 그대로 사용자 문장에 반영돼야 함.
    """
    art = _artifact(
        candidates=[
            _scored_candidate(3, "C", "C_name", 1.0),
            _scored_candidate(1, "A", "A_name", 5.0),
            _scored_candidate(2, "B", "B_name", 3.0),
        ]
    )
    _s, notes, _d = compose_universe_momentum(artifact_loader=lambda: art)
    # artifact 저장 순서 그대로: C, A, B (Runtime 재정렬 없음).
    assert notes[0].startswith("C_name")
    assert notes[1].startswith("A_name")
    assert notes[2].startswith("B_name")


# ── 33.3.8 기존 표시 제한 유지 (5개) ──


def test_universe_display_limit() -> None:
    art = _artifact(
        candidates=[
            _scored_candidate(i, f"T{i}", f"T{i}_name", 10.0 - i) for i in range(1, 11)
        ]
    )
    _s, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert len(notes) == 5
    assert diag["universe_selected_count"] == 5
    assert diag["universe_candidate_count"] == 10


# ── 33.3.9 artifact 에 없는 값 미생성 ──


def test_universe_no_extra_calculation() -> None:
    """artifact 에 score_value 만 있으면 그 값만 사용. 추가 계산 X."""
    art = _artifact(candidates=[_scored_candidate(1, "A", "A_name", 12.3456)])
    _s, notes, _d = compose_universe_momentum(artifact_loader=lambda: art)
    # 12.35% 로 반올림 표시 (fmt_pct).
    assert "12.35%" in notes[0] or "+12.35%" in notes[0]


# ── 33.3.10 Runtime producer 미호출 ──
# ── 33.3.11 Runtime 외부 API 미호출 ──


def test_universe_composer_no_external_side_effects() -> None:
    """compose_universe_momentum 는 artifact_loader 만 호출 · producer/pykrx 호출 X."""
    calls: list[str] = []

    def _loader() -> Optional[dict]:
        calls.append("loader")
        return None

    compose_universe_momentum(artifact_loader=_loader)
    # loader 한 번만 호출됐는지 확인 (외부 API 호출 없음).
    assert calls == ["loader"]


# ── 33.3.12~14 raw source key / push_kind / reason code 미노출 ──


def test_universe_notes_no_raw_identifier() -> None:
    art = _artifact(candidates=[_scored_candidate(1, "A", "A_name", 5.0)])
    _s, notes, _d = compose_universe_momentum(artifact_loader=lambda: art)
    text = "\n".join(notes)
    for kw in (
        "universe_momentum_snapshot",
        "spike_or_falling_alert",
        "kr_realtime_price_snapshot",
        "unavailable_not_implemented",
        "artifact_refresh_status_failed",
    ):
        assert kw not in text


# ── 33.3.15 Holdings 개인정보 미노출 (Universe artifact 는 원래 개인정보 없음) ──


def test_universe_notes_no_holdings_privacy() -> None:
    art = _artifact(candidates=[_scored_candidate(1, "A", "A_name", 5.0)])
    _s, notes, _d = compose_universe_momentum(artifact_loader=lambda: art)
    text = "\n".join(notes)
    for kw in ("quantity", "avg_buy_price", "invested_amount", "account_group"):
        assert kw not in text


# ── 33.3.16 금지 문구 미노출 ──


def test_universe_notes_no_forbidden_wording() -> None:
    from app.three_push_runner_common import FORBIDDEN_PHRASES

    art = _artifact(candidates=[_scored_candidate(1, "A", "A_name", 5.0)])
    _s, notes, _d = compose_universe_momentum(artifact_loader=lambda: art)
    text = "\n".join(notes)
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, f"FORBIDDEN_PHRASE {phrase!r} leaked"


# ── 33.3.17 diagnostics boolean 계약 ──


def test_universe_diagnostics_boolean_contract() -> None:
    for scenario, artifact in [
        ("missing", None),
        ("empty", _artifact(candidates=[])),
        ("one", _artifact(candidates=[_scored_candidate(1, "A", "A_name", 5.0)])),
    ]:
        _s, _n, diag = compose_universe_momentum(artifact_loader=lambda a=artifact: a)
        for k in ("universe_artifact_present", "universe_artifact_valid", "no_signal"):
            assert isinstance(diag[k], bool), f"{scenario}: {k} = {diag[k]!r}"


# ── 33.3.18 runner diagnostics forwarding 실행 검증 ──


def test_spike_runner_record_forwards_universe_diagnostics(
    tmp_path, monkeypatch
) -> None:
    """FIX r6 유형 test: run() 실행 후 record 에 universe 진단 필드 실제 전달."""
    from app.runtime_evidence.constants import RuntimeEvidenceResult
    from app.three_push_runtime_param import RuntimeParam
    import scripts.run_three_push_runtime_oci as runner_mod

    fake_evidence = RuntimeEvidenceResult(
        available_sources={
            SRC_UNIVERSE_MOMENTUM: "available",
            SRC_KR_REALTIME: "unavailable_external_fetch_required",
        },
        extra_notes=["A_name (2026-07-16 기준): 1개월 +5.00%."],
        diagnostics={
            "contentful_fact_count": 1,
            "selection_result_count": 1,
            "unavailable_reasons": {
                SRC_KR_REALTIME: "unavailable_external_fetch_required"
            },
            "universe_artifact_present": True,
            "universe_artifact_valid": True,
            "universe_artifact_status": "ok",
            "universe_artifact_asof": "2026-07-16",
            "universe_candidate_count": 3,
            "universe_selected_count": 1,
            "universe_contentful_fact_count": 1,
            "universe_snapshot_status": "available",
            "universe_snapshot_reason": "",
            "no_signal": False,
        },
    )
    fake_param = RuntimeParam(
        param_id="test-p",
        created_at="2026-07-16T00:00:00+00:00",
        approved_at="2026-07-16T00:00:00+00:00",
        approved_by="test",
        param_source="manual",
        enabled_push_kinds=["spike_or_falling_alert"],
        runtime_policy={},
        evidence_policy={},
        safety_policy={},
    )
    monkeypatch.setattr(
        runner_mod, "compose_runtime_evidence", lambda pk: fake_evidence
    )
    monkeypatch.setattr(
        runner_mod, "read_active_param_dict", lambda: fake_param.to_dict()
    )
    monkeypatch.setattr(runner_mod, "param_from_dict", lambda d: fake_param)
    monkeypatch.setattr(runner_mod, "insert_status_from_record", lambda r: None)
    monkeypatch.setattr(runner_mod, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setattr(
        runner_mod, "telegram_send", lambda *a, **kw: (False, "blocked_by_test")
    )
    monkeypatch.setattr(
        runner_mod, "build_runtime_message", lambda **kw: "test body 2026-07-16"
    )

    record = runner_mod.run("spike_or_falling_alert", "dry-run")

    assert record["universe_snapshot_status"] == "available"
    assert record["universe_snapshot_reason"] == ""
    assert record["universe_artifact_present"] is True
    assert record["universe_artifact_valid"] is True
    assert record["universe_candidate_count"] == 3
    assert record["universe_selected_count"] == 1
    assert record["universe_contentful_fact_count"] == 1
    assert record["no_signal"] is False
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False


# ── 33.3.19 · 33.3.20 회귀는 기존 runtime evidence test 로 이미 커버 ──


def test_market_briefing_still_reachable_via_composer() -> None:
    """spike composer 추가 후 market_briefing 이 여전히 정상 반환하는지 얕은 확인."""
    from app.runtime_evidence import compose_runtime_evidence

    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=None,
        holdings_file=None,
        topn_fn=lambda **_: {"status": "empty", "asof": None, "candidates": []},
    )
    # 회귀: market_briefing 은 spike 로직에 영향받지 않음.
    assert result.diagnostics["push_kind"] == "market_briefing"


# ── 검증자 재정정 신규 tests ──


def test_universe_unavailable_when_refresh_status_unknown() -> None:
    """검증자 재정정: refresh_status allowlist = {ok, partial}. 미지 값 → unavailable."""
    art = _artifact(status="mystery")
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "unavailable"
    assert notes == []
    assert diag["universe_snapshot_status"] == "unavailable"
    assert diag["universe_snapshot_reason"] == "artifact_refresh_status_unknown"


def test_universe_unavailable_when_reader_raises() -> None:
    """검증자 재정정: reader 예외는 Runtime 까지 전파 X · unavailable 로 처리."""

    def _bad_loader() -> Optional[dict]:
        raise RuntimeError("reader boom")

    status, notes, diag = compose_universe_momentum(artifact_loader=_bad_loader)
    assert status == "unavailable"
    assert notes == []
    assert diag["universe_snapshot_status"] == "unavailable"
    assert "artifact_loader_error" in diag["universe_snapshot_reason"]


def test_universe_unavailable_when_candidate_shape_broken() -> None:
    """검증자 REJECTED r2: candidate 구조 손상 (ticker 부재) → unavailable."""
    art = _artifact(
        candidates=[
            {"name": "no_ticker"},  # ticker 필드 없음.
        ]
    )
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "unavailable"
    assert notes == []
    assert diag["universe_snapshot_status"] == "unavailable"
    assert "candidate_ticker_missing" in diag["universe_snapshot_reason"]


def test_universe_unavailable_when_all_candidates_unscored() -> None:
    """검증자 REJECTED r5 재정정: refresh_status=ok 인데 scored 0건은 이제
    validator 단계에서 `artifact_status_scored_inconsistency` 로 차단.

    Publication↔Runtime 판정 일치화 (§AC-32) — Runtime 도 동일 사유 unavailable.
    """
    unscored = {
        "candidate_id": "universe|X||",
        "ticker": "X",
        "name": "X_name",
        "mode": "universe",
        "is_available": True,
        "score_result": {
            "is_scored": False,
            "score_basis_text": "pykrx 1개월 수익률",
            "exclusion_reason": "insufficient_price_history",
        },
    }
    art = _artifact(candidates=[unscored])
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    assert status == "unavailable"
    assert notes == []
    assert diag["universe_snapshot_reason"] == "artifact_status_scored_inconsistency"
    # validator 실패 시 candidate_count 은 부분 meta 로 유지되므로 정확값 assert 안 함.
    assert diag["universe_selected_count"] == 0
    assert diag["universe_contentful_fact_count"] == 0


def test_universe_unscored_candidate_skipped_no_internal_reason_leak() -> None:
    """검증자 재정정: 미채점 후보의 exclusion_reason 은 사용자 문장에 노출 X.

    표시할 값이 없는 후보는 skip → 후보 존재하지만 fact 0 → §24 계약상 unavailable.
    """
    unscored_candidate = {
        "candidate_id": "universe|X||",
        "ticker": "X",
        "name": "X_name",
        "mode": "universe",
        "is_available": True,
        "score_result": {
            "is_scored": False,
            "score_basis_text": "pykrx 1개월 수익률",
            "exclusion_reason": "SECRET_INTERNAL_REASON_CODE_ZZZ",
        },
    }
    art = _artifact(candidates=[unscored_candidate])
    status, notes, diag = compose_universe_momentum(artifact_loader=lambda: art)
    text = "\n".join(notes)
    # 내부 reason code 노출 금지.
    assert "SECRET_INTERNAL_REASON_CODE_ZZZ" not in text
    assert "exclusion_reason" not in text
    # 후보 존재 + 표시 가능 fact 0 → unavailable (§24 위반 방지).
    assert status == "unavailable"
    assert notes == []
    assert diag["universe_selected_count"] == 0
    assert diag["universe_contentful_fact_count"] == 0
