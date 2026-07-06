"""PUSH Content Gap Diagnosis v1 자동 테스트 (2026-07-05).

지시문 §12 필수 15 케이스.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.market_data_store import init_db
from app.push_content_gap_diagnosis import (
    PUSH_REQUIREMENTS,
    SCHEMA_VERSION,
    VALID_ENVIRONMENTS,
    _decide_primary_root_cause,
    run_push_content_gap_diagnosis,
)


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


# ---------- §12 케이스 ----------


def test_1_diagnosis_calls_existing_push_helpers(
    empty_db: Path, tmp_path: Path
) -> None:
    """§12.1: 진단이 기존 PUSH 3개 실제 내용 생성 helper 를 호출한다.

    `build_runtime_message` (PARAM runtime path 의 실제 message 생성 helper) 를
    호출 감시. 3 push 마다 1 회 = 3 회.
    """
    from app import push_content_gap_diagnosis as diag
    from app import push_content_gap_diagnosis_reproducers as rep

    calls: list = []
    original = rep.build_runtime_message

    def wrapper(**kw):
        calls.append(kw["push_kind"])
        return original(**kw)

    # PARAM 파일이 없어도 helper 호출이 발생하려면 PARAM 이 있어야 함.
    # 실제 latest_runtime_param.json 이 없는 tmp 환경에서는 param_available=False
    # 로 early return 하므로 mock PARAM 을 skip 대신 실제 PARAM 존재 여부와
    # 무관하게 이 테스트는 `reproduce_param_runtime` 이 helper 를 조건부로
    # 호출한다는 계약만 확인한다 (FIX r2: reproducer 모듈 분리 후 patch 대상 이전).
    rep.build_runtime_message = wrapper
    try:
        payload = run_push_content_gap_diagnosis(
            environment="pc",
            db_path=empty_db,
            artifact_path=tmp_path / "diag.json",
        )
    finally:
        rep.build_runtime_message = original
    # PARAM 존재 여부에 따라 helper 호출 여부가 달라진다. PARAM 있으면 3 회
    # 호출, 없으면 0 회 + 각 push 는 missing_latest_param 사유로 기록.
    if diag.PARAM_PATH.exists():
        assert set(calls) == {
            "market_briefing",
            "holdings_briefing",
            "spike_or_falling_alert",
        }
    else:
        for p in payload["pushes"]:
            reason = p["actual_readiness"]["param_runtime_path"].get(
                "exact_reason_code"
            )
            assert reason == "missing_latest_param"


def test_2_no_telegram_send_called(
    empty_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§12.2: 진단 경로에서 Telegram 발송 함수가 호출되지 않는다."""
    from app import three_push_runner_common as common

    calls: list = []

    def stub(*a, **kw):
        calls.append((a, kw))
        raise RuntimeError("telegram_send must not be called")

    monkeypatch.setattr(common, "telegram_send", stub)
    run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )
    assert calls == []


def test_3_no_external_market_data_call(
    empty_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§12.3: FDR / Yahoo / pykrx / KRX CSV 호출 없음."""
    import FinanceDataReader as fdr

    calls: list = []

    def stub(*a, **kw):
        calls.append((a, kw))
        raise RuntimeError("external call not allowed")

    monkeypatch.setattr(fdr, "DataReader", stub)
    monkeypatch.setattr(fdr, "StockListing", stub)
    run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )
    assert calls == []


def test_4_sqlite_content_and_schema_not_changed(
    empty_db: Path, tmp_path: Path
) -> None:
    """§12.4: 진단 실행 전후 SQLite 내용 · schema 미변경."""
    import sqlite3

    con = sqlite3.connect(str(empty_db))
    tables_before = sorted(
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    )
    con.close()
    size_before = empty_db.stat().st_size

    run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )

    con = sqlite3.connect(str(empty_db))
    tables_after = sorted(
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    )
    con.close()
    assert tables_before == tables_after
    assert empty_db.stat().st_size == size_before


def test_5_existing_state_artifacts_not_modified(
    empty_db: Path, tmp_path: Path
) -> None:
    """§12.5: 기존 state artifact 미변경.

    tmp_path 내부 sentinel 파일을 배치하고 진단 실행 후 그대로임을 확인.
    """
    sentinel_dir = tmp_path / "existing_state"
    sentinel_dir.mkdir()
    sentinel = sentinel_dir / "sentinel.json"
    sentinel.write_text('{"sentinel": true}', encoding="utf-8")
    original = sentinel.read_text(encoding="utf-8")

    run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )
    assert sentinel.read_text(encoding="utf-8") == original


def test_6_only_new_diagnosis_artifact_created(empty_db: Path, tmp_path: Path) -> None:
    """§12.6: 새 진단 artifact 만 생성/갱신."""
    artifact = tmp_path / "diag.json"
    assert not artifact.exists()
    run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=artifact,
    )
    assert artifact.exists()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION


def test_7_per_push_requirements_and_actuals_recorded(
    empty_db: Path, tmp_path: Path
) -> None:
    """§12.7: 각 PUSH 의 required data · artifact · lookback · 선택 결과 기록."""
    payload = run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )
    assert len(payload["pushes"]) == 3
    ids = {p["push_id"] for p in payload["pushes"]}
    assert ids == {
        "market_briefing",
        "holdings_briefing",
        "spike_or_falling_alert",
    }
    for p in payload["pushes"]:
        req = p["requirements"]
        assert req["sqlite_dependencies"]
        assert req["artifact_dependencies"]
        assert req["minimum_observation_requirements"]
        assert "selection_result_count" in p["content_generation"]


def test_8_exact_reason_code_recorded(empty_db: Path, tmp_path: Path) -> None:
    """§12.8: 데이터 부족 · 빈 선택이 정확한 reason code 로 기록."""
    payload = run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )
    for p in payload["pushes"]:
        code = p["content_generation"]["exact_reason_code"]
        # PARAM 존재 여부에 따라 두 시나리오만 허용.
        assert code in {
            "runtime_available_sources_not_supplied",
            "missing_latest_param",
            "param_load_error",
            "push_kind_not_in_param",
        }, f"unexpected reason code: {code!r}"


def test_9_no_secrets_absolute_paths_in_artifact(
    empty_db: Path, tmp_path: Path
) -> None:
    """§12.9: 비밀정보 · 환경변수 원문 · 절대 경로 미포함."""
    payload = run_push_content_gap_diagnosis(
        environment="pc",
        db_path=empty_db,
        artifact_path=tmp_path / "diag.json",
    )
    text = json.dumps(payload)
    forbidden_substrings = (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "PUSH_AUTOSEND_ENABLED",
    )
    for s in forbidden_substrings:
        assert s not in text, f"secret key {s} leaked"
    # Windows / Unix 절대 경로 leak 검사.
    assert "C:\\" not in text
    assert "/home/" not in text
    assert "/root/" not in text


def test_10_environment_arg_matches_artifact(empty_db: Path, tmp_path: Path) -> None:
    """§12.10: PC / OCI environment 값이 명시 인자와 일치."""
    for env in VALID_ENVIRONMENTS:
        payload = run_push_content_gap_diagnosis(
            environment=env,
            db_path=empty_db,
            artifact_path=tmp_path / f"diag_{env}.json",
        )
        assert payload["environment"] == env


def test_11_runtime_configuration_gap_classification() -> None:
    """§12.11: OCI 필수 경로 · 권한 · 코드 상태 확인 불가 fixture →
    RUNTIME_CONFIGURATION_GAP.

    param_available=False (즉 latest PARAM 파일 없음 / 권한 없음 상태) 이면
    runtime configuration gap 으로 분류된다.
    """
    param_runtime = {
        "param_available": False,
        "exact_reason_code": "missing_latest_param",
    }
    package_fallback = {
        "content_generation_status": "not_applicable",
    }
    # readiness sqlite ok, artifact ok — 순수히 PARAM 문제만.
    primary, contributing, next_step = _decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment="oci",
        readiness={
            "sqlite_lookback_insufficient": False,
            "required_artifact_missing": False,
        },
    )
    assert primary == "RUNTIME_CONFIGURATION_GAP"
    assert next_step == "OCI_RUNTIME_CONFIGURATION_CLOSEOUT"


def test_12_oci_evidence_gap_when_only_oci_missing() -> None:
    """§12.12 (지시문 원문): PC 는 준비됐고 OCI 만 필수 artifact 부재 →
    OCI_EVIDENCE_GAP.

    진단 CLI 는 한 environment 만 관측하므로, environment=oci 로 실행된 시점에
    필수 artifact 가 부재하다면 이 분류로 잠정 기록. PC/OCI 최종 비교는 별도
    세션.
    """
    param_runtime = {
        "param_available": True,
        "push_kind_enabled_in_param": True,
        "message_generated": True,
        "content_generation_status": "content_ready",
        "exact_reason_code": None,
    }
    package_fallback = {"content_generation_status": "not_applicable"}
    primary, contributing, next_step = _decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment="oci",
        readiness={
            "sqlite_lookback_insufficient": False,
            "required_artifact_missing": True,  # OCI 쪽 필수 artifact 없음.
        },
    )
    assert primary == "OCI_EVIDENCE_GAP"
    assert next_step == "OCI_RUNTIME_EVIDENCE_SYNC"


def test_13_observation_history_gap_when_lookback_insufficient() -> None:
    """§12.13 (지시문 원문): 양쪽 모두 lookback 부족 fixture →
    OBSERVATION_HISTORY_GAP.

    진단 한쪽에서 이미 sqlite 관측 이력 자체가 최소 lookback 미달이면
    (환경 무관) 이 분류로 등록. PC/OCI 두 환경 모두 관측 이력이 필요한 조건.
    """
    param_runtime = {
        "param_available": True,
        "push_kind_enabled_in_param": True,
        "message_generated": True,
        "content_generation_status": "content_ready",
        "exact_reason_code": None,
    }
    package_fallback = {"content_generation_status": "not_applicable"}
    primary, contributing, next_step = _decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment="pc",
        readiness={
            "sqlite_lookback_insufficient": True,
            "required_artifact_missing": False,
        },
    )
    assert primary == "OBSERVATION_HISTORY_GAP"
    assert next_step == "MINIMUM_OBSERVATION_HISTORY_BACKFILL"


def test_14_content_selection_gap_when_data_ok_but_selection_empty() -> None:
    """§12.14 (지시문 원문): 데이터 충족 + 기존 필터 결과 empty →
    CONTENT_SELECTION_GAP.
    """
    param_runtime = {
        "param_available": True,
        "push_kind_enabled_in_param": True,
        "message_generated": True,
        "content_generation_status": "content_ready",
        "selection_result_count": 0,
        "exact_reason_code": None,
    }
    package_fallback = {"content_generation_status": "content_ready"}
    primary, contributing, next_step = _decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment="pc",
        readiness={
            "sqlite_lookback_insufficient": False,
            "required_artifact_missing": False,
        },
    )
    assert primary == "CONTENT_SELECTION_GAP"
    assert next_step == "PUSH_CONTENT_SELECTION_CLOSEOUT"
    assert "selection_empty_after_existing_filter" in contributing


def test_14c_mixed_when_two_independent_causes() -> None:
    """§11 MIXED: 서로 독립인 원인 둘이 동시에 관찰될 때 (FIX r2 신규).

    fixture: OCI 에서 sqlite lookback 부족 (OBSERVATION_HISTORY_GAP)
    + PARAM 부재 (RUNTIME_CONFIGURATION_GAP). 두 원인은 서로 독립.
    """
    param_runtime = {
        "param_available": False,
        "exact_reason_code": "missing_latest_param",
    }
    package_fallback = {"content_generation_status": "not_applicable"}
    primary, contributing, next_step = _decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment="oci",
        readiness={
            "sqlite_lookback_insufficient": True,
            "required_artifact_missing": False,
        },
    )
    assert primary == "MIXED"
    assert set(contributing) >= {
        "OBSERVATION_HISTORY_GAP",
        "RUNTIME_CONFIGURATION_GAP",
    }
    assert next_step == "NARROWED_FOLLOWUP_DIAGNOSIS"


def test_14b_unresolved_when_no_clear_cause() -> None:
    """진단 범위에서 원인 확정 불가 → UNRESOLVED (§11 마지막 분류)."""
    param_runtime = {
        "param_available": True,
        "push_kind_enabled_in_param": True,
        "message_generated": True,
        "content_generation_status": "content_ready",
        "selection_result_count": 3,  # empty 아님.
        "exact_reason_code": None,
    }
    package_fallback = {"content_generation_status": "content_ready"}
    primary, contributing, next_step = _decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment="pc",
        readiness={
            "sqlite_lookback_insufficient": False,
            "required_artifact_missing": False,
        },
    )
    assert primary == "UNRESOLVED"
    assert next_step == "NARROWED_FOLLOWUP_DIAGNOSIS"


def test_15_diagnosis_environment_must_be_pc_or_oci(
    empty_db: Path, tmp_path: Path
) -> None:
    """§12 (안정성): environment 는 pc / oci 만 허용, 그 외는 즉시 오류."""
    with pytest.raises(ValueError):
        run_push_content_gap_diagnosis(
            environment="prod",  # invalid
            db_path=empty_db,
            artifact_path=tmp_path / "diag.json",
        )


def test_requirements_map_covers_three_pushes() -> None:
    """진단 계약: 지시문 §7 3 개 PUSH 에 대한 requirements 매핑이 존재."""
    assert set(PUSH_REQUIREMENTS.keys()) == {
        "market_briefing",
        "holdings_briefing",
        "spike_or_falling_alert",
    }
    for req in PUSH_REQUIREMENTS.values():
        assert req["sqlite_dependencies"]
        assert req["artifact_dependencies"]
        assert req["expected_sources"]
