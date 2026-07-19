"""Spike Conditional Send v1 — no-signal 미발송 계약 fixture test.

지시문 §6 계약:
- artifact valid=true · candidate_count=0 · no_signal=true 시 sender 미호출
- registry 불변
- OCI active artifact 를 실제로 건드리지 않음

접근:
- `_load_universe_artifact_for_spike` 을 monkeypatch 하여 candidates=[] 인
  유효 artifact fixture 주입 → composer 가 `no_signal=True, universe_snapshot_status=available`
  로 진단.
- Runner send mode: no_signal=true 이지만 telegram_attempted 는 True 로 기록되고
  contentful_fact_count=0 이라도 sender 는 호출 가능 (계약 확인 필요).

이 test 는 send mode 에서도 no-signal 시 sender 가 호출되지 않고 registry 가
증가하지 않아야 함을 검증. 만약 현재 계약이 다르다면 test 실패로 결함이 드러남
(이번 STEP §10 "no-signal 시 sender 미호출" AC-6 요구).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.runtime_param_store import activate_param_version, create_param_version
from app.runtime_sent_registry_store import count as registry_count
from app.three_push_runtime_param import build_manual_seed_param

_NO_SIGNAL_ARTIFACT: dict[str, Any] = {
    "engine_id": "universe_momentum",
    "engine_version": "v1",
    "mode": "universe",
    "asof": "2026-07-18",
    "summary": {
        "refresh_status": "ok",
        "scored_count": 0,
        "total_count": 0,
        "top_candidate": None,
        "falling_candidate": None,
    },
    "candidates": [],
}


def _seed_active_param() -> str:
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")
    return param.param_id


def test_spike_no_signal_dry_run_no_send_no_registry(
    tmp_path: Path, monkeypatch
) -> None:
    """no-signal (candidates=[]) fixture 로 dry-run → sender 미호출 · registry 불변."""
    _seed_active_param()
    from app import draft_three_push as _dtp
    from scripts import run_three_push_runtime_oci as runner

    # 유효하지만 candidates 가 비어있는 artifact 주입.
    monkeypatch.setattr(
        _dtp,
        "_load_universe_artifact_for_spike",
        lambda: dict(_NO_SIGNAL_ARTIFACT),
    )
    # Telegram 및 history 격리.
    telegram_calls: list = []

    def _fake_send(*args, **kwargs):
        telegram_calls.append((args, kwargs))
        return True, None, False

    monkeypatch.setattr(runner, "telegram_send", _fake_send)
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")

    registry_before = registry_count()

    record = runner.run("spike_or_falling_alert", "dry-run")

    # no-signal 계약.
    assert record["universe_artifact_valid"] is True
    assert record["universe_candidate_count"] == 0
    assert record["no_signal"] is True
    # dry-run 이므로 애초에 sender 미호출.
    assert telegram_calls == []
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False
    # Registry 불변.
    assert registry_count() == registry_before


def test_spike_no_signal_send_mode_no_telegram_no_registry(
    tmp_path: Path, monkeypatch
) -> None:
    """send mode 진입해도 no-signal 이면 sender 미호출 · registry 불변.

    현재 runner 계약 (§5~§8) 상 no_signal=True 여도 telegram_send 는 호출되는지
    확인 필요. 만약 sender 가 호출되면 이 test 는 실패하여 결함을 드러냄.
    운영 계약상 no-signal 은 발송하지 않아야 하므로, 이 test 가 통과해야 §6/AC-6
    충족.
    """
    _seed_active_param()
    from app import draft_three_push as _dtp
    from scripts import run_three_push_runtime_oci as runner

    monkeypatch.setattr(
        _dtp,
        "_load_universe_artifact_for_spike",
        lambda: dict(_NO_SIGNAL_ARTIFACT),
    )
    telegram_calls: list = []

    def _fake_send(*args, **kwargs):
        telegram_calls.append((args, kwargs))
        return True, None, False

    monkeypatch.setattr(runner, "telegram_send", _fake_send)
    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")

    # send mode 진입 조건.
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    monkeypatch.setenv("PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED", "true")

    registry_before = registry_count()

    record = runner.run("spike_or_falling_alert", "send")

    # no-signal 계약 검증.
    assert record["universe_artifact_valid"] is True
    assert record["universe_candidate_count"] == 0
    assert record["no_signal"] is True
    # 핵심: sender 미호출 · registry 불변.
    assert (
        telegram_calls == []
    ), "no-signal 인데 sender 가 호출됨 — 운영 계약 위반 (§6/AC-6)"
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False
    assert registry_count() == registry_before
