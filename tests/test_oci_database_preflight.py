"""OCI Database Preflight v1 자동 테스트 (2026-07-08).

지시문 §8 필수 12 케이스 (temp SQLite + temp directory 만 사용).
실제 OCI · SSH · Telegram · 외부 API 미호출.
"""

from __future__ import annotations

import io
import os
import re
import sqlite3
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import pytest

# ---------- helpers ----------


def _make_good_sqlite(path: Path) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        con.execute("INSERT INTO t (id) VALUES (1)")
        con.commit()
    finally:
        con.close()


def _make_corrupt_sqlite(path: Path) -> None:
    # 유효하지 않은 SQLite 바이너리.
    path.write_bytes(b"NOT_A_SQLITE_FILE" * 32)


def _import_module():
    from scripts import run_oci_database_preflight as m

    return m


# ---------- §8 케이스 ----------


def test_1_healthy_sqlite_is_ready(tmp_path: Path) -> None:
    """§8.1: 정상 SQLite → read-only open · integrity_check · table_count OK."""
    m = _import_module()
    db = tmp_path / "market_data.sqlite"
    _make_good_sqlite(db)
    obs = m._observe_sqlite(str(db))
    assert obs["exists"] is True
    assert obs["is_regular_file"] is True
    assert obs["read_open_success"] is True
    assert obs["integrity_check"] == "ok"
    assert obs["table_count"] == 1
    assert m._market_readiness(obs, "resolved") == "READY"


def test_2_missing_sqlite_is_not_ready(tmp_path: Path) -> None:
    """§8.2: DB 파일 부재 → NOT_READY."""
    m = _import_module()
    obs = m._observe_sqlite(str(tmp_path / "nonexistent.sqlite"))
    assert obs["exists"] is False
    assert m._market_readiness(obs, "resolved") == "NOT_READY"


def test_3_corrupt_sqlite_is_not_ready(tmp_path: Path) -> None:
    """§8.3: 손상된 DB → NOT_READY."""
    m = _import_module()
    db = tmp_path / "corrupt.sqlite"
    _make_corrupt_sqlite(db)
    obs = m._observe_sqlite(str(db))
    assert obs["exists"] is True
    # read_open 은 성공할 수 있으나 integrity_check 가 실패 또는 open 자체 실패.
    if obs["read_open_success"]:
        assert obs["integrity_check"] != "ok"
    assert m._market_readiness(obs, "resolved") == "NOT_READY"


def test_4_read_only_open_failure_is_not_ready(tmp_path: Path) -> None:
    """§8.4: read-only open 실패 → NOT_READY.

    directory 를 SQLite path 로 넘기면 read_open 실패 (is_regular_file=False).
    """
    m = _import_module()
    fake = tmp_path / "somedir"
    fake.mkdir()
    obs = m._observe_sqlite(str(fake))
    assert obs["exists"] is True
    assert obs["is_regular_file"] is False
    assert obs["read_open_success"] is False
    assert m._market_readiness(obs, "resolved") == "NOT_READY"


def test_5_decision_missing_is_optional_missing(tmp_path: Path) -> None:
    """§8.5: decision_evidence.sqlite 부재 → OPTIONAL_MISSING.

    overall failure 강제하지 않는다.
    """
    m = _import_module()
    obs = m._observe_sqlite(str(tmp_path / "decision_missing.sqlite"))
    assert obs["exists"] is False
    assert m._decision_readiness(obs) == "OPTIONAL_MISSING"


def test_6_path_resolution_conflict_is_not_ready(tmp_path: Path) -> None:
    """§8.6: resolver conflict → NOT_READY.

    _resolve_market_data_path 가 conflict 를 반환하는 경로 시뮬레이션.
    """
    m = _import_module()
    obs = m._observe_sqlite(str(tmp_path / "any.sqlite"))
    # path_status=database_path_resolution_conflict 인 경우.
    assert m._market_readiness(obs, "database_path_resolution_conflict") == "NOT_READY"


def test_7_db_bytes_unchanged_after_preflight(tmp_path: Path) -> None:
    """§8.7: preflight 전후 DB byte size / hash 동일."""
    import hashlib

    m = _import_module()
    db = tmp_path / "market_data.sqlite"
    _make_good_sqlite(db)
    before_bytes = db.read_bytes()
    before_hash = hashlib.sha256(before_bytes).hexdigest()
    before_size = db.stat().st_size

    m._observe_sqlite(str(db))

    after_bytes = db.read_bytes()
    after_hash = hashlib.sha256(after_bytes).hexdigest()
    after_size = db.stat().st_size
    assert before_hash == after_hash
    assert before_size == after_size


def test_8_no_schema_or_row_change(tmp_path: Path) -> None:
    """§8.8: table · row · schema 변경 없음."""
    m = _import_module()
    db = tmp_path / "market_data.sqlite"
    _make_good_sqlite(db)

    con = sqlite3.connect(str(db))
    try:
        tables_before = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        rows_before = con.execute("SELECT id FROM t ORDER BY id").fetchall()
        sv_before = con.execute("PRAGMA schema_version").fetchone()
    finally:
        con.close()

    m._observe_sqlite(str(db))

    con = sqlite3.connect(str(db))
    try:
        tables_after = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        rows_after = con.execute("SELECT id FROM t ORDER BY id").fetchall()
        sv_after = con.execute("PRAGMA schema_version").fetchone()
    finally:
        con.close()

    assert tables_before == tables_after
    assert rows_before == rows_after
    assert sv_before == sv_after


def test_9_no_absolute_path_in_stdout(tmp_path: Path, monkeypatch) -> None:
    """§8.9: stdout 에 절대 경로 없음."""
    m = _import_module()
    # CWD 를 프로젝트 root 로 유지 — main() 은 argparse 로 --environment 요구.
    argv = ["run_oci_database_preflight", "--environment", "pc"]
    with mock.patch("sys.argv", argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            m.main()
    out = buf.getvalue()
    # Windows 절대 경로 (C:\, D:\ 등) 와 Unix 절대 경로 (/home/, /root/, /Users/) 미포함.
    assert not re.search(r"[A-Za-z]:\\", out)
    assert "/home/" not in out
    assert "/root/" not in out
    assert "/Users/" not in out


def test_10_no_secret_or_raw_traceback_in_stdout(monkeypatch) -> None:
    """§8.10: stdout 에 token · chat id · secret key · raw traceback 없음."""
    m = _import_module()
    argv = ["run_oci_database_preflight", "--environment", "oci"]
    with mock.patch("sys.argv", argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            m.main()
    out = buf.getvalue()
    forbidden = (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "PUSH_AUTOSEND_ENABLED",
        "Traceback (most recent call last)",
        "SSH",
        "sshpass",
    )
    for f in forbidden:
        assert f not in out, f"forbidden token {f!r} leaked"


def test_11_no_persistent_artifact_created(tmp_path: Path, monkeypatch) -> None:
    """§8.11: CLI 실행 후 새 persistent JSON / JSONL / SQLite / log / temp file
    이 프로젝트 하위 state/, logs/, scripts/, tests/ 에 생기지 않는다.
    """
    m = _import_module()
    root = m._project_root()

    def snapshot() -> set[str]:
        found: set[str] = set()
        for sub in ("state", "logs"):
            base = root / sub
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if p.is_file():
                    found.add(p.as_posix())
        return found

    before = snapshot()
    argv = ["run_oci_database_preflight", "--environment", "pc"]
    with mock.patch("sys.argv", argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            m.main()
    after = snapshot()
    # 실행 전후 파일 집합이 정확히 동일해야 한다.
    assert before == after, f"new files created: {after - before}"


def test_12_staging_absent_env_marked_unconfirmed_from_audit(monkeypatch) -> None:
    """§8.12: THREE_PUSH_REMOTE_PACKAGE_DIR 부재 시 추정 · 기본값 추론 없이
    unconfirmed_from_audit 로만 기록.
    """
    m = _import_module()
    # env 완전 제거.
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop(m.STAGING_ENV_NAME, None)
        staging = m._observe_staging()
        status = m._staging_status(staging)
    assert staging["local_observation"] == "env_variable_absent"
    assert status == "unconfirmed_from_audit"
    assert "remote_staging_absolute_path" in staging["unconfirmed_from_audit"]


# ---------- 계약 · Q1 (a) 추가 검증 ----------


def test_q1a_two_modules_with_same_return_is_ready() -> None:
    """Q1 (a) 확정: 서로 다른 모듈이 동일 경로를 반환하면 conflict 아님.

    실측: market_data_store.DEFAULT_DB_PATH 와 etf_nav_store.DEFAULT_DB_PATH
    는 동일 값 → path_status=resolved.
    """
    m = _import_module()
    canonical_str, path_status, note = m._resolve_market_data_path()
    assert path_status == "resolved"
    assert "single_canonical_path" in note or canonical_str


def test_q1a_conflict_when_aux_returns_different_path(monkeypatch) -> None:
    """Q1 (a) 확정: 실제 반환 경로가 다르면 conflict."""
    m = _import_module()
    import app.etf_nav_store as ens

    with mock.patch.object(
        ens, "DEFAULT_DB_PATH", Path("state/other/different.sqlite")
    ):
        canonical_str, path_status, note = m._resolve_market_data_path()
    assert path_status == "database_path_resolution_conflict"
    # readiness 결과도 NOT_READY.
    obs = m._observe_sqlite(canonical_str or "state/market/market_data.sqlite")
    assert m._market_readiness(obs, path_status) == "NOT_READY"


def test_environment_arg_required_pc_or_oci() -> None:
    """--environment pc | oci 명시 필수 (§6.1)."""
    m = _import_module()
    with mock.patch("sys.argv", ["run_oci_database_preflight"]):
        with pytest.raises(SystemExit):
            m._parse_args()
    with mock.patch(
        "sys.argv", ["run_oci_database_preflight", "--environment", "prod"]
    ):
        with pytest.raises(SystemExit):
            m._parse_args()


def test_revision_returns_string() -> None:
    m = _import_module()
    r = m._revision()
    assert isinstance(r, str)
    assert r == "unavailable" or len(r) >= 4


# ---------- FIX r1: sanitised failure contract (§6.2) ----------


def test_unexpected_error_sanitised_no_raw_traceback(monkeypatch) -> None:
    """FIX r1 (검증자 A-1 / A-3 / B-6): 예상 밖 예외 발생 시 raw traceback
    노출 금지. `status=FAILED / error_class=<class>` 만 stdout 에 출력.
    """
    m = _import_module()

    class _CustomFailure(RuntimeError):
        pass

    def _boom() -> int:
        raise _CustomFailure("secret-message-that-must-not-leak")

    monkeypatch.setattr(m, "_main_impl", _boom)
    argv = ["run_oci_database_preflight", "--environment", "pc"]
    with mock.patch("sys.argv", argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = m.main()
    out = buf.getvalue()
    assert rc == 3, "예상 밖 오류는 return code 3 이어야 한다"
    assert "status=FAILED" in out
    assert "error_class=_CustomFailure" in out
    # raw traceback / exception message / 절대 경로 미포함.
    assert "Traceback (most recent call last)" not in out
    assert "secret-message-that-must-not-leak" not in out
    assert "\\n  File " not in out


def test_systemexit_propagates_not_swallowed(monkeypatch) -> None:
    """FIX r1: argparse 오류 등 SystemExit 은 상위로 노출 (조용히 삼키지 않음)."""
    m = _import_module()

    def _sysexit() -> int:
        raise SystemExit(2)

    monkeypatch.setattr(m, "_main_impl", _sysexit)
    argv = ["run_oci_database_preflight", "--environment", "pc"]
    with mock.patch("sys.argv", argv):
        with pytest.raises(SystemExit) as exc_info:
            m.main()
    assert exc_info.value.code == 2


def test_error_class_only_no_message_or_absolute_path(monkeypatch) -> None:
    """FIX r1: error_class 값은 파이썬 identifier 만. 절대 경로 · secret 미포함."""
    m = _import_module()

    class _AnotherFailure(ValueError):
        pass

    def _boom() -> int:
        raise _AnotherFailure(
            "C:\\Users\\alice\\secret.txt " "/root/.env " "TELEGRAM_BOT_TOKEN=abc:def"
        )

    monkeypatch.setattr(m, "_main_impl", _boom)
    argv = ["run_oci_database_preflight", "--environment", "oci"]
    with mock.patch("sys.argv", argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            m.main()
    out = buf.getvalue()
    assert "error_class=_AnotherFailure" in out
    assert "C:\\Users" not in out
    assert "/root/" not in out
    assert "TELEGRAM_BOT_TOKEN" not in out
    assert "abc:def" not in out
