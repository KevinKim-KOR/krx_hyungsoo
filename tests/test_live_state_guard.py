"""라이브 state/logs 쓰기 가드 역검증 (POC4-01 설계자 판정 2026-09-24 · 테스트 격리 결함).

가드가 빠지거나 무력화되면 아래 테스트가 **실패**해야 한다. 탐침 경로는 라이브 루트 아래에 없는
이름만 쓴다 — 가드가 망가져 실제로 써지더라도 기존 파일은 건드리지 않고, 만들어진 탐침은 지운다.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

from tests import _live_guard
from tests._live_guard import PROJECT_ROOT, LiveStateWriteError

# 호환 목록 상한 — 2026-09-24 실측(세션 사본을 연 기존 테스트 수). 목록은 줄이기만 한다.
LEGACY_READERS_CEILING = 229


def _probe(root: str, suffix: str = ".txt") -> Path:
    return PROJECT_ROOT / root / f"__live_guard_probe_{uuid.uuid4().hex}{suffix}"


def _cleanup(path: Path) -> None:
    with _live_guard.suspended():
        if path.is_dir():
            path.rmdir()
        elif path.exists():
            path.unlink()


def test_guard_is_installed_for_the_whole_session():
    assert _live_guard.installed(), "conftest 가 가드를 걸지 않았다"


@pytest.mark.parametrize("root", ["state", "logs"])
@pytest.mark.parametrize("mode", ["w", "a", "x", "r+"])
def test_open_for_write_under_live_root_is_blocked(root, mode):
    probe = _probe(root)
    try:
        with pytest.raises(LiveStateWriteError):
            open(probe, mode).close()
        assert not probe.exists(), "가드가 막기 전에 파일이 생겼다"
    finally:
        _cleanup(probe)


def test_pathlib_and_os_level_writes_are_blocked(tmp_path):
    probe = _probe("state")
    src = tmp_path / "src.txt"
    src.write_text("x", encoding="utf-8")
    try:
        with pytest.raises(LiveStateWriteError):
            probe.write_text("x", encoding="utf-8")
        with pytest.raises(LiveStateWriteError):
            os.replace(src, probe)
        with pytest.raises(LiveStateWriteError):
            os.open(probe, os.O_WRONLY | os.O_CREAT)
        with pytest.raises(LiveStateWriteError):
            os.remove(probe)  # 없는 탐침 — 가드가 빠지면 FileNotFoundError 로 실패한다
        with pytest.raises(LiveStateWriteError):
            probe.mkdir()
        assert src.exists() and not probe.exists()
    finally:
        _cleanup(probe)


def test_reads_and_tmp_writes_are_allowed(tmp_path):
    live_file = next(
        (p for p in (PROJECT_ROOT / "state").rglob("*.json") if p.is_file()), None
    )
    if live_file is not None:
        with open(live_file, "rb") as fh:
            fh.read(1)
    target = tmp_path / "ok.txt"
    target.write_text("ok", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "ok"


@pytest.mark.parametrize("uri", [False, True])
def test_live_sqlite_opens_a_read_only_session_copy(uri):
    """라이브 DB 로 오는 연결은 세션 사본을 **읽기 전용**으로 연다 — 읽기는 되고 쓰기는 즉시 실패.

    쓰기를 시도하기 **전에** 연결 경로부터 확인한다. 가드가 꺼져 라이브 파일이 열렸으면
    아무것도 쓰지 않고 실패한다(역검증이 라이브 DB 를 바꾸지 않게).
    """
    live = PROJECT_ROOT / "state" / "market" / "market_data.sqlite"
    if not live.exists():
        pytest.skip("라이브 시장 DB 가 없다")
    rel = "state/market/market_data.sqlite"
    con = sqlite3.connect(f"file:{rel}?mode=rw" if uri else rel, uri=uri)
    try:
        opened = Path(con.execute("PRAGMA database_list").fetchone()[2]).resolve()
        assert opened != live.resolve(), "라이브 DB 파일을 직접 열었다"
        assert not _live_guard.is_live(opened)
        assert con.execute("SELECT count(*) FROM etf_master").fetchone()[0] >= 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            con.execute(f"CREATE TABLE __live_guard_probe_{uuid.uuid4().hex} (x)")
    finally:
        con.close()


def test_session_fingerprint_watches_the_five_incident_paths():
    conftest = sys.modules.get("tests.conftest") or sys.modules["conftest"]
    watched = set(conftest._LIVE_WATCH_FILES) | set(conftest._LIVE_WATCH_DIRS)
    assert watched == {
        "state/market/market_data.sqlite",
        "state/market/nav_discount_refresh_latest.json",
        "logs/oci_market_data_batch.log",
        "logs/three_push_runtime_cron.log",
        "state/runs",
    }


# --- 설계자 확정 (2026-09-24) READONLY_SESSION_COPY 조건 ---------------------------------


def test_test_outside_legacy_list_cannot_open_live_db():
    """새 테스트(호환 목록 밖)는 라이브 DB 를 여는 순간 실패한다 — 자체 임시 DB·고정 fixture 를 쓴다.

    가드가 빠지면 연결이 열리고(쓰지는 않는다) 예외가 없으니 이 테스트가 실패한다.
    """
    live = PROJECT_ROOT / "state" / "market" / "market_data.sqlite"
    assert _live_guard._state["current_test"] not in _live_guard.LEGACY_READERS
    with pytest.raises(LiveStateWriteError, match="새 테스트는 자체 임시 DB"):
        sqlite3.connect(str(live)).close()


def test_legacy_list_never_grows():
    """호환 목록은 줄이기만 한다 — 새 테스트를 넣어 사본을 쓰게 하면 실패한다."""
    readers = _live_guard.LEGACY_READERS
    assert 0 < len(readers) <= LEGACY_READERS_CEILING
    assert all(r.startswith("tests/") and "::" in r for r in readers)


def _small_db(path: Path) -> Path:
    con = _live_guard.real_connect(str(path))
    con.execute("CREATE TABLE t (x INTEGER, y TEXT)")
    con.executemany("INSERT INTO t VALUES (?, ?)", [(i, "v" * 200) for i in range(400)])
    con.commit()
    con.close()
    return path


def test_verified_copy_reports_hashes_and_integrity(tmp_path):
    src = _small_db(tmp_path / "src.sqlite")
    report = _live_guard.verified_copy(src, tmp_path / "copy.sqlite")
    assert report["source_sha256_before"] == report["source_sha256_after"]
    assert report["copy_sha256"] == report["source_sha256_before"]
    assert report["integrity_check"] == "ok"


def test_verified_copy_fails_when_source_changes_during_copy(tmp_path, monkeypatch):
    src = _small_db(tmp_path / "src.sqlite")
    real_copy = _live_guard.shutil.copyfile

    def _copy_then_touch_source(a, b, *args, **kwargs):
        out = real_copy(a, b, *args, **kwargs)
        with open(a, "ab") as fh:
            fh.write(b"x")
        return out

    monkeypatch.setattr(_live_guard.shutil, "copyfile", _copy_then_touch_source)
    with pytest.raises(LiveStateWriteError, match="바뀌었다"):
        _live_guard.verified_copy(src, tmp_path / "copy.sqlite")


def test_verified_copy_fails_on_corrupted_database(tmp_path):
    src = _small_db(tmp_path / "src.sqlite")
    raw = bytearray(src.read_bytes())
    page = 4096
    start, end = page * 2, page * 3
    raw[start:end] = os.urandom(page)  # 데이터 페이지를 망가뜨린다
    src.write_bytes(bytes(raw))
    with pytest.raises(LiveStateWriteError, match="integrity"):
        _live_guard.verified_copy(src, tmp_path / "copy.sqlite")
