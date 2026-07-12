"""PARAM / Runtime State DB Cutover v1 — 전용 테스트 (Refactor v1 재구성).

- runtime_state_db: schema · integrity · canonical hash.
- runtime_param_store: flatten · reconstruct · idempotent version · active pointer · fail-closed.
- runtime_sent_registry_store: insert or ignore · duplicate guard.
- runtime_execution_status_store: insert · latest 조회.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import runtime_state_db as db_helper
from app.runtime_execution_status_store import (
    insert_execution_status,
    insert_status_from_record,
    latest_execution_status,
)
from app.runtime_param_store import (
    activate_param_version,
    create_param_version,
    read_active_param_dict,
)
from app.runtime_sent_registry_store import (
    contains as registry_contains,
    count as registry_count,
    insert as registry_insert,
)
from app.three_push_runtime_param import build_manual_seed_param, from_dict


@pytest.fixture(autouse=True)
def _reset_cache():
    db_helper.reset_init_cache_for_testing()
    yield
    db_helper.reset_init_cache_for_testing()


def _fresh_db(tmp_path: Path) -> Path:
    return tmp_path / "runtime_state.sqlite"


def test_init_db_creates_all_five_tables(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    db_helper.init_db(p)
    tables = set(db_helper.list_tables(p))
    assert set(db_helper.TABLE_NAMES).issubset(tables)


def test_integrity_check_ok(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    db_helper.init_db(p)
    assert db_helper.integrity_check(p) == "ok"


def test_canonical_hash_stable_across_key_order(tmp_path: Path) -> None:
    d1 = {"b": 2, "a": 1, "c": {"x": True, "y": [1, 2]}}
    d2 = {"c": {"y": [1, 2], "x": True}, "a": 1, "b": 2}
    assert db_helper.canonical_json_sha256(d1) == db_helper.canonical_json_sha256(d2)


def test_flatten_and_reconstruct_roundtrip(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    param = build_manual_seed_param()
    data = param.to_dict()
    version_id, source_hash, created = create_param_version(data, db_path=p)
    assert created is True
    activate_param_version(
        version_id,
        activated_at=datetime.now(timezone.utc).isoformat(),
        activated_by="test",
        db_path=p,
    )
    reconstructed = read_active_param_dict(p)
    assert db_helper.canonical_json_sha256(reconstructed) == source_hash
    assert db_helper.canonical_json_sha256(
        reconstructed
    ) == db_helper.canonical_json_sha256(data)
    # Semantic dataclass roundtrip.
    param2 = from_dict(reconstructed)
    assert param2.param_id == param.param_id
    assert param2.enabled_push_kinds == param.enabled_push_kinds


def test_idempotent_version_reuse_by_hash(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    param = build_manual_seed_param()
    v1, h1, created1 = create_param_version(param.to_dict(), db_path=p)
    v2, h2, created2 = create_param_version(param.to_dict(), db_path=p)
    assert v1 == v2
    assert h1 == h2
    assert created1 is True
    assert created2 is False
    counts = db_helper.table_row_counts(p)
    assert counts["runtime_param_version"] == 1


def test_registry_insert_or_ignore(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    ok1 = registry_insert(
        p,
        push_kind="market_briefing",
        param_id="param-xyz",
        runtime_date_kst="2026-07-09",
        sent_at_utc=now,
        inserted_at=now,
    )
    ok2 = registry_insert(
        p,
        push_kind="market_briefing",
        param_id="param-xyz",
        runtime_date_kst="2026-07-09",
        sent_at_utc=now,
        inserted_at=now,
    )
    assert ok1 is True
    assert ok2 is False
    assert registry_count(p) == 1
    assert registry_contains(p, "market_briefing", "param-xyz", "2026-07-09")


def test_execution_status_insert_and_latest(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    run_id = insert_execution_status(
        p,
        push_kind="holdings_briefing",
        mode="dry-run",
        status="dry_run_success",
        reason=None,
        started_at=now,
        finished_at=now,
        runtime_kst=now,
        runtime_date_kst="2026-07-09",
        param_id="param-xyz",
        param_source="manual_seed",
        message_text_length=100,
        availability_available=0,
        availability_unavailable_or_other=0,
        duplicate_key="holdings_briefing::param-xyz::2026-07-09",
        telegram_attempted=False,
        telegram_sent=False,
        error=None,
        inserted_at=now,
    )
    assert run_id >= 1
    latest = latest_execution_status(p)
    assert latest is not None
    assert latest["run_id"] == run_id
    assert latest["push_kind"] == "holdings_briefing"


def test_insert_status_from_record_maps_availability(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    record = {
        "push_kind": "market_briefing",
        "mode": "send",
        "status": "sent",
        "reason": None,
        "started_at": "2026-07-09T00:00:00+00:00",
        "finished_at": "2026-07-09T00:00:01+00:00",
        "runtime_kst": "2026-07-09T09:00:00+09:00",
        "runtime_date_kst": "2026-07-09",
        "param_id": "param-abc",
        "param_source": "manual_seed",
        "message_text_length": 42,
        "availability": {"available": 1, "unavailable_or_other": 2},
        "duplicate_key": "market_briefing::param-abc::2026-07-09",
        "telegram_attempted": True,
        "telegram_sent": True,
        "error": None,
    }
    rid = insert_status_from_record(record, db_path=p)
    assert rid >= 1
    latest = latest_execution_status(p)
    assert latest is not None
    assert latest["availability_available"] == 1
    assert latest["availability_unavailable_or_other"] == 2


def test_read_active_param_fail_closed_when_db_missing(tmp_path: Path) -> None:
    p = tmp_path / "missing.sqlite"
    with pytest.raises(RuntimeError, match="runtime_state DB 부재"):
        read_active_param_dict(p)


def test_read_active_param_fail_closed_when_pointer_missing(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    db_helper.init_db(p)
    with pytest.raises(RuntimeError, match="runtime_param_active pointer 부재"):
        read_active_param_dict(p)


def test_enabled_push_kinds_index_ordering_preserved(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    param = build_manual_seed_param(
        enabled_push_kinds=["spike_or_falling_alert", "market_briefing"]
    )
    version_id, _, _ = create_param_version(param.to_dict(), db_path=p)
    activate_param_version(
        version_id,
        activated_at=datetime.now(timezone.utc).isoformat(),
        activated_by="test",
        db_path=p,
    )
    reconstructed = read_active_param_dict(p)
    assert reconstructed["enabled_push_kinds"] == [
        "spike_or_falling_alert",
        "market_briefing",
    ]


def test_seed_cli_invokes_seed_then_verify(tmp_path: Path, monkeypatch) -> None:
    from scripts import run_runtime_state_db_cutover as cli

    p = _fresh_db(tmp_path)
    src_dir = tmp_path / "state" / "three_push" / "params"
    src_dir.mkdir(parents=True)
    src_json = src_dir / "latest_runtime_param.json"
    param = build_manual_seed_param()
    src_json.write_text(
        json.dumps(param.to_dict(), ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(cli, "_LATEST_PARAM_JSON", src_json)
    monkeypatch.setattr(cli, "_STATUS_JSON", tmp_path / "no_status.json")
    monkeypatch.setattr(cli, "_REGISTRY_JSON", tmp_path / "no_registry.json")

    exit_code = cli.main(["seed", "--db-path", str(p)])
    assert exit_code == 0
    exit_code = cli.main(["verify", "--db-path", str(p)])
    assert exit_code == 0
