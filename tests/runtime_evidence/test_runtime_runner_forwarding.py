"""Runner record 진단 필드 forward 실행 회귀 (FIX r6 검증자 지적 대응).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path

from app.runtime_evidence_composer import (
    RuntimeEvidenceResult,
    SRC_HOLDINGS,
    SRC_MARKET_DISCOVERY,
    SRC_NAV_DISCOUNT,
)


def test_holdings_briefing_runner_record_forwards_all_diagnostics_r6(
    tmp_path: Path, monkeypatch
) -> None:
    """FIX r6: runner 실행 후 record 에 진단 10 필드 실제 전달.

    monkeypatch 로 compose_runtime_evidence + 부수효과 (DB write / Telegram) 를
    차단하고 실제 run() 을 호출해 반환된 record 를 검사.
    """
    from app.three_push_runtime_param import RuntimeParam
    import scripts.run_three_push_runtime_oci as runner_mod

    fake_evidence = RuntimeEvidenceResult(
        available_sources={
            SRC_HOLDINGS: "available",
            SRC_NAV_DISCOUNT: "available",
            SRC_MARKET_DISCOVERY: "available",
        },
        extra_notes=["KODEX 200 (2026-07-11 기준): Market Discovery TOP1."],
        diagnostics={
            "contentful_fact_count": 1,
            "selection_result_count": 1,
            "unavailable_reasons": {},
            "holdings_snapshot_status": "available",
            "holdings_snapshot_reason": "",
            "holdings_loaded_count": 35,
            "holdings_evidence_item_count": 35,
            "holdings_contentful_fact_count": 35,
            "nav_contentful_fact_count": 32,
            "holdings_selection_result_count": 35,
            "rendered_holdings_fact_count": 35,
            "private_fields_exposed": False,
            "raw_identifier_exposed": False,
        },
    )
    fake_param = RuntimeParam(
        param_id="test-p",
        created_at="2026-07-11T00:00:00+00:00",
        approved_at="2026-07-11T00:00:00+00:00",
        approved_by="test",
        param_source="manual",
        enabled_push_kinds=["holdings_briefing"],
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
        runner_mod, "build_runtime_message", lambda **kw: "test body 2026-07-11"
    )

    record = runner_mod.run("holdings_briefing", "dry-run")

    assert record["holdings_snapshot_status"] == "available"
    assert record["holdings_snapshot_reason"] == ""
    assert record["holdings_loaded_count"] == 35
    assert record["holdings_evidence_item_count"] == 35
    assert record["holdings_contentful_fact_count"] == 35
    assert record["nav_contentful_fact_count"] == 32
    assert record["holdings_selection_result_count"] == 35
    assert record["rendered_holdings_fact_count"] == 35
    assert record["private_fields_exposed"] is False
    assert record["raw_identifier_exposed"] is False
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False
