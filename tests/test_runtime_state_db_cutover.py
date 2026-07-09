"""PARAM / Runtime State DB Cutover v1 — 전용 테스트.

- runtime_state_store: schema · flatten · reconstruct · idempotent version · registry.
- three_push_runtime_param DB layer: read_active_param_from_db · create_param_version_in_db.
- fail-closed 경로: DB 부재 / active pointer 부재.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import runtime_state_store as store
from app.three_push_runtime_param import (
    activate_param_version,
    build_manual_seed_param,
    create_param_version_in_db,
    read_active_param_from_db,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    store.reset_init_cache_for_testing()
    yield
    store.reset_init_cache_for_testing()


def _fresh_db(tmp_path: Path) -> Path:
    return tmp_path / "runtime_state.sqlite"


def test_init_db_creates_all_five_tables(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    store.init_db(p)
    tables = set(store.list_tables(p))
    assert set(store.TABLE_NAMES).issubset(tables)


def test_integrity_check_ok(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    store.init_db(p)
    assert store.integrity_check(p) == "ok"


def test_canonical_hash_stable_across_key_order(tmp_path: Path) -> None:
    d1 = {"b": 2, "a": 1, "c": {"x": True, "y": [1, 2]}}
    d2 = {"c": {"y": [1, 2], "x": True}, "a": 1, "b": 2}
    assert store.canonical_json_sha256(d1) == store.canonical_json_sha256(d2)


def test_flatten_and_reconstruct_roundtrip(tmp_path: Path) -> None:
    param = build_manual_seed_param()
    data = param.to_dict()
    version_id, source_hash, created = create_param_version_in_db(
        param, db_path=_fresh_db(tmp_path)
    )
    assert created is True
    activate_param_version(
        version_id,
        activated_at=datetime.now(timezone.utc).isoformat(),
        activated_by="test",
        db_path=_fresh_db(tmp_path).parent / "runtime_state.sqlite",
    )
    # read + reconstruct.
    p = _fresh_db(tmp_path).parent / "runtime_state.sqlite"
    reconstructed = read_active_param_from_db(p).to_dict()
    assert store.canonical_json_sha256(reconstructed) == source_hash
    assert store.canonical_json_sha256(reconstructed) == store.canonical_json_sha256(
        data
    )


def test_idempotent_version_reuse_by_hash(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    param = build_manual_seed_param()
    v1, h1, created1 = create_param_version_in_db(param, db_path=p)
    v2, h2, created2 = create_param_version_in_db(param, db_path=p)
    assert v1 == v2
    assert h1 == h2
    assert created1 is True
    assert created2 is False
    counts = store.table_row_counts(p)
    assert counts["runtime_param_version"] == 1


def test_registry_insert_or_ignore(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    ok1 = store.registry_insert(
        p,
        push_kind="market_briefing",
        param_id="param-xyz",
        runtime_date_kst="2026-07-09",
        sent_at_utc=now,
        inserted_at=now,
    )
    ok2 = store.registry_insert(
        p,
        push_kind="market_briefing",
        param_id="param-xyz",
        runtime_date_kst="2026-07-09",
        sent_at_utc=now,
        inserted_at=now,
    )
    assert ok1 is True
    assert ok2 is False
    assert store.registry_count(p) == 1
    assert store.registry_contains(p, "market_briefing", "param-xyz", "2026-07-09")


def test_execution_status_insert_and_latest(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    run_id = store.insert_execution_status(
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
    latest = store.latest_execution_status(p)
    assert latest is not None
    assert latest["run_id"] == run_id
    assert latest["push_kind"] == "holdings_briefing"


def test_read_active_param_fail_closed_when_db_missing(tmp_path: Path) -> None:
    p = tmp_path / "missing.sqlite"
    with pytest.raises(RuntimeError, match="runtime_state DB 부재"):
        read_active_param_from_db(p)


def test_read_active_param_fail_closed_when_pointer_missing(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    store.init_db(p)
    with pytest.raises(RuntimeError, match="runtime_param_active pointer 부재"):
        read_active_param_from_db(p)


def test_enabled_push_kinds_index_ordering_preserved(tmp_path: Path) -> None:
    p = _fresh_db(tmp_path)
    param = build_manual_seed_param(
        enabled_push_kinds=["spike_or_falling_alert", "market_briefing"]
    )
    version_id, _, _ = create_param_version_in_db(param, db_path=p)
    activate_param_version(
        version_id,
        activated_at=datetime.now(timezone.utc).isoformat(),
        activated_by="test",
        db_path=p,
    )
    reconstructed = read_active_param_from_db(p).to_dict()
    assert reconstructed["enabled_push_kinds"] == [
        "spike_or_falling_alert",
        "market_briefing",
    ]


def test_seed_cli_invokes_seed_then_verify(tmp_path: Path, monkeypatch) -> None:
    from scripts import run_runtime_state_db_cutover as cli

    p = _fresh_db(tmp_path)
    # override JSON source paths so the CLI uses this test fixture.
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
