"""Runtime Evidence DB Connection v1 — runner dry-run 자동 회귀 test.

지시문 §15.12/13 · 검증자 A-1 지적: runtime runner 의 dry-run 실행이 실제
Telegram 호출 · sent registry write 없이 status/history 만 기록하는지 확인.

기존 test 는 Composer/diagnosis pure test 만 다뤘고, runner 통합 경로 자동
회귀는 없었다. 이번 test 로 다음을 보장:
- runner run(push_kind, mode="dry-run") 완료 후 telegram_send 미호출.
- sent_registry 카운트가 변하지 않음.
- runtime_execution_status DB 에 1 row 신규 insert.
- history JSONL 에 1 line append.
- record 에 신규 diagnostics 필드 포함 (contentful_fact_count 등).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.runtime_execution_status_store import latest_execution_status
from app.runtime_param_store import activate_param_version, create_param_version
from app.runtime_sent_registry_store import count as registry_count
from app.three_push_runtime_param import build_manual_seed_param


def _seed_active_param(_tmp_path: Path) -> str:
    """conftest fixture 로 격리된 tmp runtime_state DB 에 PARAM seed."""
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")
    return param.param_id


def _install_telegram_and_registry_spies(monkeypatch, tmp_path: Path):
    """Telegram/registry 를 spy 로 대체. runner 는 dry-run 이므로 애초에 호출 안 될 것."""
    from scripts import run_three_push_runtime_oci as runner

    telegram_calls: list = []

    def _fake_telegram_send(*args, **kwargs):
        telegram_calls.append(("telegram_send", args, kwargs))
        return True, ""

    monkeypatch.setattr(runner, "telegram_send", _fake_telegram_send)

    # history JSONL 도 tmp 로 리다이렉트해서 실제 파일 오염 방지.
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")

    return telegram_calls


def test_runner_dry_run_market_briefing_no_telegram_no_registry_write(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_active_param(tmp_path)
    telegram_calls = _install_telegram_and_registry_spies(monkeypatch, tmp_path)
    registry_before = registry_count()

    # runner import 는 spy 설치 뒤에 (module-level 호출 회피 위해).
    from scripts.run_three_push_runtime_oci import run

    record = run("market_briefing", "dry-run")

    # Telegram 미호출.
    assert telegram_calls == []
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False

    # sent registry 불변.
    assert registry_count() == registry_before

    # runtime_execution_status DB 에 1 row 신규 insert (기존 계약 유지).
    latest = latest_execution_status()
    assert latest is not None
    assert latest["push_kind"] == "market_briefing"
    assert latest["mode"] == "dry-run"

    # record 에 신규 diagnostics 필드 존재.
    assert "contentful_fact_count" in record
    assert "selection_result_count" in record
    assert "unavailable_reasons" in record


def test_runner_dry_run_holdings_briefing_holdings_source_missing_reported(
    tmp_path: Path, monkeypatch
) -> None:
    """Composer 는 Holdings 파일 부재 시 holdings_source_missing 을 unavailable_reasons
    로 기록해야 한다.

    실제 PC 에는 `state/holdings/holdings_latest.json` 이 존재할 수 있으므로 이 test
    는 명시적으로 부재하는 tmp path 로 monkeypatch 한다 (composer default 참조 우회).
    """
    _seed_active_param(tmp_path)
    telegram_calls = _install_telegram_and_registry_spies(monkeypatch, tmp_path)
    registry_before = registry_count()

    # Composer default 가 참조하는 HOLDINGS_FILE 을 tmp 부재 path 로 override.
    from app import holdings as _holdings

    monkeypatch.setattr(_holdings, "HOLDINGS_FILE", tmp_path / "no_holdings.json")
    from app import runtime_evidence_composer as _rec

    monkeypatch.setattr(_rec, "HOLDINGS_FILE", tmp_path / "no_holdings.json")

    from scripts.run_three_push_runtime_oci import run

    record = run("holdings_briefing", "dry-run")

    # Holdings source missing 이 record 에 기록됨.
    unavail = record.get("unavailable_reasons") or {}
    from app.runtime_evidence_composer import (
        REASON_SOURCE_MISSING_HOLDINGS,
        SRC_HOLDINGS,
    )

    assert unavail.get(SRC_HOLDINGS) == REASON_SOURCE_MISSING_HOLDINGS
    # B-6 정정 r2: dry-run 은 Telegram spy 미호출 + sent_registry 불변을 직접 assert.
    assert telegram_calls == []
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False
    assert registry_count() == registry_before


def test_runner_dry_run_spike_all_unavailable_no_topn_calls(
    tmp_path: Path, monkeypatch
) -> None:
    """B-6: Spike 는 market_discovery 를 호출하지 않아야 함 (compute_topn 미호출).

    runner 는 Composer 를 통해 접근하므로 여기서는 record 결과로 확인.
    """
    _seed_active_param(tmp_path)
    telegram_calls = _install_telegram_and_registry_spies(monkeypatch, tmp_path)
    registry_before = registry_count()

    from scripts.run_three_push_runtime_oci import run

    record = run("spike_or_falling_alert", "dry-run")
    assert record["contentful_fact_count"] == 0
    assert record["selection_result_count"] == 0
    # B-6 정정 r2: Telegram spy 미호출 + sent_registry 불변 직접 assert.
    assert telegram_calls == []
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False
    assert registry_count() == registry_before


def test_runner_dry_run_history_jsonl_appended(tmp_path: Path, monkeypatch) -> None:
    """runtime history JSONL 이 dry-run 후에 실제로 append 되는지 확인."""
    _seed_active_param(tmp_path)
    _install_telegram_and_registry_spies(monkeypatch, tmp_path)
    from scripts import run_three_push_runtime_oci as runner

    history_path = tmp_path / "history.jsonl"
    assert not history_path.exists()

    runner.run("market_briefing", "dry-run")

    assert history_path.exists()
    lines = [
        ln for ln in history_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["push_kind"] == "market_briefing"
    assert entry["mode"] == "dry-run"
