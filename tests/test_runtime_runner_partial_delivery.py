"""Runtime runner partial delivery integration test (Holdings Controlled Send v1 FIX r2).

계약:
- telegram_send 가 (False, "partial_delivery_at_chunk_N_of_M: ...", True) 반환 시
  runner record 는 partial_delivery=True + telegram_sent=False
  + status=failed + reason=telegram_send_error
- sent registry 는 mark_sent 미호출 (delta 0)
- history JSONL 에 record 1 line append (partial_delivery 필드 포함)
"""

from __future__ import annotations

import json
from pathlib import Path

from app.runtime_param_store import activate_param_version, create_param_version
from app.runtime_sent_registry_store import count as registry_count
from app.three_push_runtime_param import build_manual_seed_param


def _seed_active_param() -> str:
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")
    return param.param_id


def test_runner_partial_delivery_records_flag_and_no_registry_write(
    tmp_path: Path, monkeypatch
) -> None:
    """2번째 chunk 실패 시 partial_delivery=true · registry 불변 · history append 검증."""
    _seed_active_param()
    from scripts import run_three_push_runtime_oci as runner

    calls: list[str] = []

    def _fake_telegram_send(text: str):
        calls.append(text)
        return (
            False,
            "partial_delivery_at_chunk_2_of_2: other_non_secret_error: HTTP 500",
            True,
        )

    monkeypatch.setattr(runner, "telegram_send", _fake_telegram_send)
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")

    registry_before = registry_count()

    record = runner.run("market_briefing", "send")

    # 요약 record 검증.
    assert record["status"] == "failed"
    assert record["reason"] == "telegram_send_error"
    assert record["telegram_attempted"] is True
    assert record["telegram_sent"] is False
    assert record["partial_delivery"] is True
    assert record["error"] is not None
    assert record["error"].startswith("partial_delivery_at_chunk_2_of_2")

    # Registry 불변.
    assert registry_count() == registry_before

    # history JSONL 에 partial_delivery 필드 포함.
    hist_lines = (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(hist_lines) == 1
    hist_record = json.loads(hist_lines[-1])
    assert hist_record["partial_delivery"] is True
    assert hist_record["telegram_sent"] is False
    assert hist_record["status"] == "failed"


def test_runner_first_chunk_fail_partial_false_and_no_registry_write(
    tmp_path: Path, monkeypatch
) -> None:
    """1번째 chunk 부터 실패 → partial_delivery=false · registry 불변."""
    _seed_active_param()
    from scripts import run_three_push_runtime_oci as runner

    def _fake_telegram_send(text: str):
        return (
            False,
            "partial_delivery_at_chunk_1_of_2: other_non_secret_error: HTTP 400",
            False,
        )

    monkeypatch.setattr(runner, "telegram_send", _fake_telegram_send)
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")

    registry_before = registry_count()

    record = runner.run("market_briefing", "send")

    assert record["status"] == "failed"
    assert record["reason"] == "telegram_send_error"
    assert record["telegram_attempted"] is True
    assert record["telegram_sent"] is False
    assert record["partial_delivery"] is False
    assert registry_count() == registry_before


def test_runner_all_chunks_success_partial_false_and_registry_write(
    tmp_path: Path, monkeypatch
) -> None:
    """전 chunk 성공 → partial_delivery=false · sent=true · registry +1."""
    _seed_active_param()
    from scripts import run_three_push_runtime_oci as runner

    def _fake_telegram_send(text: str):
        return True, None, False

    monkeypatch.setattr(runner, "telegram_send", _fake_telegram_send)
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")

    # send mode 진입을 위해 autosend flag 활성.
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    monkeypatch.setenv("PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED", "true")

    registry_before = registry_count()

    record = runner.run("market_briefing", "send")

    assert record["status"] == "sent"
    assert record["telegram_attempted"] is True
    assert record["telegram_sent"] is True
    assert record["partial_delivery"] is False
    assert record["error"] is None
    assert registry_count() == registry_before + 1
