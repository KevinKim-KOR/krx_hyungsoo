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
