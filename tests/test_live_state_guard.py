"""라이브 state/logs 쓰기 가드 역검증 (POC4-01 설계자 판정 2026-09-24 · 테스트 격리 결함).

가드가 빠지거나 무력화되면 아래 테스트가 **실패**해야 한다. 탐침 경로는 라이브 루트 아래에 없는
이름만 쓴다 — 가드가 망가져 실제로 써지더라도 기존 파일은 건드리지 않고, 만들어진 탐침은 지운다.
"""

from __future__ import annotations

import _sqlite3
import os
import sqlite3
import sqlite3.dbapi2
import sys
import uuid
from pathlib import Path

import pytest

from tests import _live_guard
from tests._live_guard import PROJECT_ROOT, LiveStateWriteError

# 호환 목록 상한 — 2026-09-24 실측(세션 사본을 연 기존 테스트 수). 목록은 줄이기만 한다.
LEGACY_READERS_CEILING = 229
LIVE_DB = PROJECT_ROOT / "state" / "market" / "market_data.sqlite"


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
        # 읽기 전용 사본 연결에서 SQL 로 라이브 DB·사본을 다시 붙여 쓰는 길도 막힌다.
        for target in (str(live), str(opened)):
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                con.execute(f"ATTACH DATABASE '{target}' AS again")
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
    if os.environ.get(_live_guard.RECORD_ENV):
        pytest.skip(
            "기록 모드는 목록을 강제하지 않는다 — 이 테스트를 목록 재현에 넣지 않는다"
        )
    assert _live_guard._state["current_test"] not in _live_guard.LEGACY_READERS
    with pytest.raises(LiveStateWriteError, match="새 테스트는 자체 임시 DB"):
        sqlite3.connect(str(LIVE_DB)).close()


def test_legacy_list_never_grows():
    """호환 목록은 줄이기만 한다 — 새 테스트를 넣어 사본을 쓰게 하면 실패한다.

    파일은 정렬·중복 0 을 유지한다(설계자 확인 2026-09-24). 항목 바꿔치기는 이 테스트가
    잡지 못한다 — 목록 파일 변경 diff 로 본다.
    """
    readers = _live_guard.LEGACY_READERS
    assert 0 < len(readers) <= LEGACY_READERS_CEILING
    assert all(r.startswith("tests/") and "::" in r for r in readers)
    raw = [
        line.strip()
        for line in _live_guard.LEGACY_READERS_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert raw == sorted(set(raw)), "목록 파일은 정렬·중복 0 이어야 한다"


def _small_db(path: Path) -> Path:
    con = sqlite3.connect(str(path))
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


# --- 사전 점검(2026-09-24)에서 찾은 우회 경로 — 가드가 막는지 역검증 ------------------------


def _skip_in_record_mode() -> None:
    if os.environ.get(_live_guard.RECORD_ENV):
        pytest.skip("기록 모드는 목록을 강제하지 않는다")


def test_attach_and_vacuum_into_cannot_reach_live_db(tmp_path):
    """SQL 안에서 파일을 여는 길(ATTACH · VACUUM INTO)은 `sqlite3.connect` 를 거치지 않는다.

    - 경로 문자열 ATTACH · VACUUM INTO → authorizer 가 바로 거부(파일을 열지 않는다)
    - 매개변수 · 앞에 주석이 붙은 · 식(`'a' || 'b'`) ATTACH → 준비 때 경로를 모른다. 실행 직전에 값이
      채워진 SQL 로 판정해 기록하고 그 별칭 접근을 전부 거부한다(conftest 가 그 테스트를 실패시킨다).
      라이브 DB 를 실제로 열지 않게 라이브 루트 아래 **없는** 탐침을 읽기 전용 URI 로 붙인다.
    - 임시 파일 ATTACH · 대상 없는 VACUUM 은 그대로 된다
    가드가 빠지면 문자열 ATTACH 가 라이브 DB 를 열기만 하고(쓰지 않는다) 예외가 없어 실패한다.
    """
    if not LIVE_DB.exists():
        pytest.skip("라이브 시장 DB 가 없다")
    con = sqlite3.connect(str(tmp_path / "t.sqlite"))
    uri_con = sqlite3.connect(f"file:{tmp_path / 'u.sqlite'}", uri=True)
    probe = _probe("state", ".sqlite")
    ro_probe = f"file:{probe}?mode=ro"
    _live_guard.take_blocks()
    try:
        con.execute("CREATE TABLE t (x)")
        for c, target in ((con, str(LIVE_DB)), (uri_con, f"file:{LIVE_DB}?mode=ro")):
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                c.execute(f"ATTACH DATABASE '{target}' AS live")
        head, tail = ro_probe[:12], ro_probe[12:]
        for n, (sql, params) in enumerate(
            (
                ("ATTACH DATABASE ? AS p", (ro_probe,)),
                ("/* 주석 */ ATTACH ? AS p", (ro_probe,)),
                (f"ATTACH '{head}' || '{tail}' AS p", ()),
            )
        ):
            c = sqlite3.connect(f"file:{tmp_path / f'p{n}.sqlite'}", uri=True)
            try:
                with pytest.raises(sqlite3.OperationalError, match="unable to open"):
                    c.execute(sql, params)
            finally:
                c.close()
        assert not probe.exists(), "ATTACH 가 라이브 루트에 파일을 만들었다"
        con.execute(
            f"ATTACH ('{tmp_path}' || '/e.sqlite') AS expr"
        )  # 대상 판정 불가 → 막는다
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            con.execute("CREATE TABLE expr.t (x)")
        con.execute("DETACH DATABASE expr")
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("VACUUM INTO ?", (str(probe),))
        assert not probe.exists(), "VACUUM INTO 가 라이브 루트에 파일을 만들었다"
        ops = [b["op"] for b in _live_guard.take_blocks()]
        assert ops.count("sqlite ATTACH") == 7, ops
        con.execute("ATTACH DATABASE ? AS ok", (str(tmp_path / "ok.sqlite"),))
        con.execute("CREATE TABLE ok.t (x)")
        con.execute("VACUUM")
    finally:
        con.close()
        uri_con.close()
        _cleanup(probe)


def test_os_module_originals_are_guarded(tmp_path):
    """`posix.unlink` 처럼 원본 모듈을 직접 부르거나, 목록 밖이던 메타데이터 연산도 막는다."""
    osmod = sys.modules[os.name]
    probe = _probe("state")
    src = tmp_path / "src.txt"
    src.write_text("x", encoding="utf-8")
    try:
        with pytest.raises(LiveStateWriteError):
            osmod.rename(src, probe)
        with pytest.raises(LiveStateWriteError):
            osmod.unlink(probe)  # 없는 탐침 — 가드가 빠지면 FileNotFoundError
        if hasattr(os, "mkfifo"):
            with pytest.raises(LiveStateWriteError):
                os.mkfifo(probe)
        if hasattr(os, "chown"):
            with pytest.raises(LiveStateWriteError):
                os.chown(probe, -1, -1)
        assert not probe.exists()
    finally:
        _cleanup(probe)


def test_other_sqlite_entry_points_are_guarded():
    """`sqlite3.connect` 만 바꾸면 `sqlite3.dbapi2.connect`·`_sqlite3.connect` 는 라이브를 그대로 연다."""
    _skip_in_record_mode()
    for connect in (sqlite3.dbapi2.connect, _sqlite3.connect):
        with pytest.raises(LiveStateWriteError, match="새 테스트는 자체 임시 DB"):
            connect(str(LIVE_DB)).close()


def _aliases(tmp_path: Path) -> dict[str, str]:
    """같은 라이브 시장 DB 를 가리키는 다른 표기 — 이 기계에서 실제로 성립하는 것만."""
    live = str(LIVE_DB)
    out = {
        "file://localhost URI": f"file://localhost{live}",
        "%-encoded URI": "file:" + live.replace("/state/", "/st%61te/"),
    }
    link = tmp_path / "lnk"
    os.symlink(LIVE_DB.parent, link)
    out["symlink then .."] = f"{link}/../market/{LIVE_DB.name}"
    upper = live.replace("/state/", "/STATE/")
    if os.path.exists(upper):  # 대소문자 구분 없는 파일시스템
        out["case variant"] = upper
    firm = "/System/Volumes/Data" + live
    if os.path.exists(firm):  # macOS firmlink
        out["firmlink"] = firm
    return out


def test_aliased_live_paths_are_still_live(tmp_path):
    """문자열로만 비교하면 대소문자 · firmlink · URI 표기 · 심볼릭 링크 뒤 `..` 로 라이브를 연다."""
    if os.name != "posix" or not LIVE_DB.exists():
        pytest.skip("POSIX 경로 표기 · 라이브 시장 DB 필요")
    _skip_in_record_mode()
    for name, alias in _aliases(tmp_path).items():
        assert _live_guard.is_live(alias), name
        with pytest.raises(LiveStateWriteError, match="새 테스트는 자체 임시 DB"):
            sqlite3.connect(alias, uri=alias.startswith("file:")).close()


def test_case_variant_new_file_under_live_root_is_blocked():
    if not os.path.exists(PROJECT_ROOT / "STATE"):
        pytest.skip("대소문자를 구분하는 파일시스템")
    probe = _probe("state")
    try:
        with pytest.raises(LiveStateWriteError):
            open(str(probe).replace("/state/", "/STATE/"), "w").close()
        assert not probe.exists()
    finally:
        _cleanup(probe)


def test_hard_link_to_a_live_file_is_blocked(tmp_path):
    """라이브 파일의 하드링크는 경로만 다른 라이브 파일이다 — 만드는 순간 막는다."""
    if not LIVE_DB.exists():
        pytest.skip("라이브 시장 DB 가 없다")
    alias = tmp_path / "alias.sqlite"
    with pytest.raises(LiveStateWriteError):
        os.link(LIVE_DB, alias)
    assert not alias.exists()


def test_session_copy_is_read_only_and_guarded():
    """사본 경로로 직접 열기 · 쓰기 · 권한 바꾸기도 막는다 — 사본이 바뀌면 다음 테스트가 바뀐 데이터를 읽는다."""
    if not LIVE_DB.exists():
        pytest.skip("라이브 시장 DB 가 없다")
    _skip_in_record_mode()
    copy = _live_guard._sandbox_copy(
        LIVE_DB
    )  # 세션 사본(없으면 지금 만든다 — 라이브는 읽기만)
    assert copy.stat().st_mode & 0o222 == 0, "사본이 읽기 전용이 아니다"
    with pytest.raises(LiveStateWriteError, match="새 테스트는 자체 임시 DB"):
        sqlite3.connect(str(copy)).close()
    for attempt in (
        lambda: open(copy, "r+b"),
        lambda: os.chmod(copy, 0o644),
        lambda: os.utime(copy),
    ):
        with pytest.raises(LiveStateWriteError, match="세션 사본"):
            attempt()
    assert all(r["same"] for r in _live_guard.recheck_copies())


def test_copy_recheck_reports_a_changed_copy(tmp_path):
    src = _small_db(tmp_path / "src.sqlite")
    copy = tmp_path / "copy.sqlite"
    report = _live_guard.verified_copy(src, copy)
    assert _live_guard.recheck_copies({"k": report})[0]["same"]
    with open(copy, "ab") as fh:
        fh.write(b"x")
    assert not _live_guard.recheck_copies({"k": report})[0]["same"]


def test_blocked_operation_is_recorded_even_if_swallowed():
    """앱 코드가 `except Exception` 으로 가드 오류를 삼켜도 기록이 남는다 — conftest 가 그 테스트를 실패시킨다."""
    probe = _probe("state")
    _live_guard.take_blocks()
    try:
        try:
            open(probe, "w").close()
        except Exception:  # noqa: BLE001 — 앱 코드의 넓은 except 흉내
            pass
        blocks = _live_guard.take_blocks()
        assert [b["op"] for b in blocks] == ["open mode=w"]
        assert blocks[0]["test"].endswith(
            "test_blocked_operation_is_recorded_even_if_swallowed"
        )
        assert not probe.exists()
    finally:
        _cleanup(probe)


def test_removing_a_tmp_symlink_to_live_is_allowed(tmp_path):
    """링크만 옮기거나 지우는 연산은 라이브를 건드리지 않는다 — pytest 가 tmp 의 링크를 지울 때
    막히면 안 된다. 링크를 따라가 쓰는 것은 막는다."""
    link = tmp_path / "to_live"
    os.symlink(PROJECT_ROOT / "state", link)
    name = f"__live_guard_probe_{uuid.uuid4().hex}.txt"
    try:
        with pytest.raises(LiveStateWriteError):
            open(link / name, "w").close()
        assert not (PROJECT_ROOT / "state" / name).exists()
        moved = tmp_path / "moved"
        os.rename(link, moved)
        os.unlink(moved)
        assert (PROJECT_ROOT / "state").is_dir()
    finally:
        _cleanup(PROJECT_ROOT / "state" / name)
