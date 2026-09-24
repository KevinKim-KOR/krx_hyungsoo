"""테스트가 라이브 `state/`·`logs/` 에 쓰는 것을 **쓰는 순간** 막는 가드 (POC4-01 설계자 판정 2026-09-24).

전체 회귀가 맥북 라이브 경로 5곳(시장 DB · NAV 요약 · 실행 기록 · 로그 2개)에 썼다. 지금까지는 경로를
하나씩 monkeypatch 하고 파일 하나씩 감시했다 — 새 경로가 생길 때마다 뚫렸다("한 통로 막기").

그래서 **쓰기 연산 자체**에 건다. 대상 경로를 풀어서 라이브 루트 아래면 즉시 `LiveStateWriteError`.

- `open`/`io.open`/`_io.open` 쓰기 모드(w·a·x·+) · `os.open` 쓰기 플래그
- `os.replace`·`os.rename`(출발·도착 모두) · `os.remove`·`os.unlink`·`os.rmdir` · `os.mkdir`(없는 경로)
  · `os.truncate` · `os.chmod` · `os.utime` · `os.symlink`(만드는 쪽) · `os.link`(원본·만드는 쪽 모두 —
  라이브 파일의 하드링크는 라이브 파일 그 자체다) · 있으면 `os.chown`·`lchown`·`lchmod`·`chflags`·
  `lchflags`·`mkfifo`·`mknod`. 같은 함수를 원본 모듈(`posix`·`nt`)에서 직접 불러도 막힌다.
- 경로 판정 — `file:` URI(`//localhost` · `%XX` · `?query`)를 SQLite 처럼 풀고, 심볼릭 링크를 먼저 따라간
  뒤 비교한다. 문자열로 안 맞으면 가장 가까운 실제 조상 폴더의 (장치, inode) 를 라이브 루트와 비교한다
  — 대소문자만 다른 경로 · macOS firmlink(`/System/Volumes/Data/...`) 같은 별칭도 라이브로 본다.
- `sqlite3.connect`(·`sqlite3.dbapi2.connect`·`_sqlite3.connect`) — 라이브 DB 경로로 오는 연결
  (설계자 확정 2026-09-24 `READONLY_SESSION_COPY`):
  * **기존 호환 목록**(`tests/_live_db_legacy_readers.txt`)의 테스트만 세션 임시 사본을 읽기 전용(mode=ro)
    으로 연다. 운영 조회 함수의 경로 기본값이 함수 정의 시점에 묶여 있어 테스트에서 경로를 못 바꾸는
    기존 테스트들이다(처음 열 때 `CREATE TABLE IF NOT EXISTS` — 이미 있는 테이블이면 읽기 전용에서도 통과).
  * 목록 밖의 테스트(= 새 테스트)는 라이브 DB 를 여는 순간 `LiveStateWriteError` — 자체 임시 DB·고정
    fixture 를 써야 한다.
  * 사본은 세션에서 처음 필요할 때 한 번 만든다. 라이브 DB 의 복사 전후 sha256 이 같고 사본 sha256 이
    그와 같아야 하며, 사본은 `PRAGMA integrity_check` 가 `ok` 여야 한다. 아니면 즉시 실패. 사본 파일은
    읽기 전용(0444)으로 두고, 사본 경로로 직접 열거나 쓰거나 지우는 것도 라이브와 똑같이 막는다.
    세션이 끝날 때 사본 sha256 을 다시 재서 만들 때와 같은지 본다(`recheck_copies`).
  * 쓰기(INSERT·DELETE·새 테이블 등)는 즉시 `attempt to write a readonly database` 로 실패한다 —
    사고를 낸 `reset_state_for_testing()` 인자 누락 같은 패턴이 조용히 통과하지 않고, 사본이 바뀌지
    않으니 테스트끼리 데이터가 새지도 않는다. 라이브 DB 파일은 사본을 만들 때 읽기만 한다.
  * 가드를 거친 모든 연결에 SQLite authorizer · trace callback 을 건다 — `ATTACH '<경로>'`·`VACUUM INTO`
    로 라이브 DB 나 사본을 붙이는 것을 거부한다(SQL 안에서 파일을 여는 길은 `sqlite3.connect` 를 거치지
    않는다). `ATTACH ?`(매개변수)·식은 준비 때 경로를 모르므로 실행 직전 값이 채워진 SQL(앞 주석 제외)
    로 판정하고, 대상이 문자열 하나가 아니면(식) 판정 불가로 본다 — 그 별칭의 접근을 모두 거부하고
    기록한다. 이때 SQLite 는 대상 파일을 한 번 연다(읽기 전용 URI 가 아니고 없는 경로면 빈 파일이 생긴다).
  * 목록 갱신 — `KRX_LIVE_DB_READERS_RECORD=<파일>` 로 전체 테스트를 돌리면 사본을 쓴 테스트 id 를
    그 파일에 적는다(이 모드에서는 목록 밖도 허용). 목록은 줄이기만 한다(새 테스트 추가 금지).
- 막은 연산은 모두 기록한다(`take_blocks`). 앱 코드가 `except Exception` 으로 가드 오류를 삼켜도
  conftest 가 그 테스트를 실패시킨다.

파일 읽기는 막지 않는다. `tmp_path` 등 저장소 밖 경로는 영향이 없다. 하위 프로세스는 이 가드 밖이라
`conftest.py` 의 세션 전후 hash 비교가 따로 잡는다. 감시 코드만 `real_connect` 로 라이브 파일을
`mode=ro` 로 본다. 가드가 보지 못하는 것(저장소 코드·테스트에 사용처 0): `io.FileIO(...)` 직접 생성 ·
`sqlite3.Connection(...)` 직접 생성 · 파일 디스크립터로 부르는 연산(`os.fchmod`·`os.ftruncate`·
`os.chmod(fd)` 등) · 세션 전부터 있던 하드링크. 파일 생성·삭제·크기·mtime 변경은 세션 전후 비교로
사후에 잡히지만, 권한·소유자·플래그만 바꾸는 것과 빈 폴더는 그 비교에도 안 잡힌다.
"""

from __future__ import annotations

import _io
import _sqlite3
import builtins
import hashlib
import io
import os
import re
import shutil
import sqlite3
import sqlite3.dbapi2
import sys
import tempfile
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NoReturn, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_ROOTS = (PROJECT_ROOT / "state", PROJECT_ROOT / "logs")
LEGACY_READERS_FILE = Path(__file__).resolve().parent / "_live_db_legacy_readers.txt"
RECORD_ENV = "KRX_LIVE_DB_READERS_RECORD"

_OS_MOD = sys.modules[os.name]  # posix · nt — os.open 의 원본 모듈
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_real = {
    "open": builtins.open,
    "io_open": io.open,
    "_io_open": _io.open,
    "os_open": os.open,
    "osmod_open": _OS_MOD.open,
    "replace": os.replace,
    "rename": os.rename,
    "remove": os.remove,
    "unlink": os.unlink,
    "rmdir": os.rmdir,
    "mkdir": os.mkdir,
    "truncate": os.truncate,
    "chmod": os.chmod,
    "utime": os.utime,
    "link": os.link,
    "symlink": os.symlink,
    "connect": sqlite3.connect,
    "dbapi2_connect": sqlite3.dbapi2.connect,
    "_sqlite3_connect": _sqlite3.connect,
}
# 가드 목록 밖이던 메타데이터·특수 파일 연산 — 있는 것만 (플랫폼마다 다르다)
_EXTRA_OS = tuple(
    n
    for n in ("chown", "lchown", "lchmod", "chflags", "lchflags", "mkfifo", "mknod")
    if hasattr(os, n)
)
_real.update({n: getattr(os, n) for n in _EXTRA_OS})
_state = {
    "installed": False,
    "suspended": 0,
    "sqlite_dir": None,
    "current_test": None,
    "copy_ids": set(),
}
_redirects: dict[str, Path] = {}
_copy_reports: dict[str, dict] = {}
_copy_failures: list[str] = []
_blocks: list[dict] = []


def _load_legacy_readers() -> frozenset[str]:
    if not LEGACY_READERS_FILE.exists():
        return frozenset()
    lines = LEGACY_READERS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(s.strip() for s in lines if s.strip() and not s.startswith("#"))


LEGACY_READERS = _load_legacy_readers()


class LiveStateWriteError(AssertionError):
    """테스트가 라이브 state/logs 경로에 쓰려 했다 — tmp_path 로 격리해야 한다."""


def _record(op: str, target, message: str) -> None:
    _blocks.append(
        {
            "test": _state["current_test"],
            "op": op,
            "target": str(target),
            "message": message.splitlines()[0],
        }
    )


def _block(op: str, target, message: str) -> NoReturn:
    _record(op, target, message)
    raise LiveStateWriteError(message)


def take_blocks() -> list[dict]:
    """지금까지 막은 연산 목록을 돌려주고 비운다 — conftest 가 테스트마다 확인한다."""
    out = list(_blocks)
    _blocks.clear()
    return out


def _as_path(target) -> Path | None:
    """연산 대상 → 절대 경로. SQLite `file:` URI 는 SQLite 와 같은 규칙으로 푼다."""
    if isinstance(target, int):  # 파일 디스크립터
        return None
    if isinstance(target, bytes):
        target = os.fsdecode(target)
    if not isinstance(target, (str, os.PathLike)):
        return None
    text = os.fspath(target)
    if text.startswith("file:"):
        text = text[len("file:") :].split("#", 1)[0].split("?", 1)[0]  # noqa: E203
        if text.startswith("//"):  # authority — SQLite 는 비었거나 localhost 만 받는다
            text = "/" + text[2:].partition("/")[2]
        text = urllib.parse.unquote(text)
        if re.match(r"^/[A-Za-z]:", text):  # file:///C:/... (Windows)
            text = text[1:]
    if text in ("", ":memory:"):
        return None
    path = Path(text)
    return path if path.is_absolute() else Path.cwd() / path


def _ids(path, follow: bool = True) -> tuple[int, int] | None:
    try:
        st = os.stat(path) if follow else os.lstat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino)


def _under(path: Path, roots, follow: bool = True) -> Path | None:
    """path 가 roots 중 하나의 아래면 그 root 기준 정식 경로, 아니면 None.

    심볼릭 링크를 먼저 따라간 뒤(`resolve`) 문자열로 비교하고, 안 맞으면 가장 가까운 실제 조상부터
    위로 (장치, inode) 를 비교한다 — 대소문자만 다른 경로 · firmlink 도 같은 폴더로 본다.
    `follow=False` 는 마지막 이름을 링크 그 자체로 본다 — unlink·rename 처럼 링크만 바꾸는 연산은
    링크가 라이브를 가리켜도 라이브를 건드리지 않는다(pytest 가 tmp 의 링크를 지우는 경우 등).
    """
    if follow or path.name in ("", ".", ".."):
        try:
            path = path.resolve()
        except (OSError, RuntimeError):
            pass
        start = path
    else:
        try:
            start = path.parent.resolve()
        except (OSError, RuntimeError):
            start = path.parent
        path = start / path.name
    for root in roots:
        if path == root or path.is_relative_to(root):
            return path
    root_by_id = {i: r for r in roots if (i := _ids(r)) is not None}
    if not root_by_id:
        return None
    probe = start
    while not os.path.lexists(probe) and probe != probe.parent:
        probe = probe.parent
    for anc in (probe, *probe.parents):
        root = root_by_id.get(_ids(anc))
        if root is not None:
            return root / path.relative_to(anc)
    return None


def _live_path(target, follow: bool = True) -> Path | None:
    path = _as_path(target)
    return None if path is None else _under(path, LIVE_ROOTS, follow)


def is_live(target, follow: bool = True) -> bool:
    return _live_path(target, follow) is not None


def _is_copy(target, follow: bool = True) -> bool:
    """세션 사본 파일(또는 그 별칭·하드링크)인가 — 사본도 라이브처럼 지킨다."""
    if not _state["copy_ids"]:
        return False
    path = _as_path(target)
    return path is not None and _ids(path, follow) in _state["copy_ids"]


def _fd_dir(dir_fd: int) -> str | None:
    """`dir_fd` 가 가리키는 폴더의 실제 경로 (Linux /proc · macOS F_GETPATH)."""
    try:
        return os.readlink(f"/proc/self/fd/{dir_fd}")
    except OSError:
        pass
    try:
        import fcntl

        raw = fcntl.fcntl(dir_fd, getattr(fcntl, "F_GETPATH"), bytes(1024))
        return raw.split(b"\0", 1)[0].decode()
    except (OSError, AttributeError, ValueError):
        return None


def _anchor(target, dir_fd):
    """`dir_fd` 기준 상대 경로는 그 폴더 기준으로 푼다 (shutil.rmtree 등)."""
    if dir_fd is None or isinstance(target, int):
        return target
    text = os.fsdecode(target)
    if os.path.isabs(text):
        return text
    base = _fd_dir(dir_fd)
    return os.path.join(base, text) if base else None


def _check(op: str, *targets, dir_fd=None, follow: bool = True) -> None:
    if _state["suspended"]:
        return
    for target in targets:
        target = _anchor(target, dir_fd)
        if target is None:
            continue
        if is_live(target, follow):
            _block(
                op,
                target,
                f"테스트가 라이브 경로에 쓰려 했다 ({op}): {target}\n"
                "tmp_path 로 격리하라 (tests/_live_guard.py).",
            )
        if _is_copy(target, follow):
            _block(
                op,
                target,
                f"테스트가 라이브 DB 세션 사본을 바꾸려 했다 ({op}): {target}\n"
                "사본은 읽기 전용이다 (tests/_live_guard.py).",
            )


def _guarded_open(file, mode="r", *args, **kwargs):
    if any(c in mode for c in "wax+"):
        _check(f"open mode={mode}", file)
    return _real["open"](file, mode, *args, **kwargs)


def _guarded_io_open(file, mode="r", *args, **kwargs):
    if any(c in mode for c in "wax+"):
        _check(f"io.open mode={mode}", file)
    return _real["io_open"](file, mode, *args, **kwargs)


def _guarded_os_open(path, flags, *args, **kwargs):
    if flags & _WRITE_FLAGS:
        follow = not flags & getattr(os, "O_NOFOLLOW", 0)
        _check("os.open", path, dir_fd=kwargs.get("dir_fd"), follow=follow)
    return _real["os_open"](path, flags, *args, **kwargs)


def _two(name):
    """replace·rename — 출발·도착 모두. 이름(링크 포함) 자체를 옮기므로 마지막 링크는 따라가지 않는다."""

    def _wrapped(src, dst, *args, **kwargs):
        _check(f"os.{name}", src, dir_fd=kwargs.get("src_dir_fd"), follow=False)
        _check(f"os.{name}", dst, dir_fd=kwargs.get("dst_dir_fd"), follow=False)
        return _real[name](src, dst, *args, **kwargs)

    return _wrapped


def _guarded_symlink(src, dst, *args, **kwargs):
    """symlink — 만들어지는 쪽(dst)만 본다. 링크를 따라가는 쓰기는 따라간 경로로 다시 판정된다."""
    _check("os.symlink", dst, dir_fd=kwargs.get("dir_fd"), follow=False)
    return _real["symlink"](src, dst, *args, **kwargs)


def _guarded_link(src, dst, *args, **kwargs):
    """link — 원본도 본다. 라이브 파일의 하드링크는 경로만 다른 라이브 파일이다."""
    follow = kwargs.get("follow_symlinks", True)
    _check("os.link", src, dir_fd=kwargs.get("src_dir_fd"), follow=follow)
    _check("os.link", dst, dir_fd=kwargs.get("dst_dir_fd"), follow=False)
    return _real["link"](src, dst, *args, **kwargs)


# 링크 자체를 대상으로 하는 연산 — 링크를 지우거나(remove·unlink·rmdir) 링크 자체의 속성을 바꾸거나
# (lchown·lchmod·lchflags) 새 이름을 만드는(mkfifo·mknod) 연산은 마지막 링크를 따라가지 않는다.
_NO_FOLLOW_OPS = (
    "remove",
    "unlink",
    "rmdir",
    "lchown",
    "lchmod",
    "lchflags",
    "mkfifo",
    "mknod",
)


def _one(name):
    def _wrapped(path, *args, **kwargs):
        follow = name not in _NO_FOLLOW_OPS and kwargs.get("follow_symlinks", True)
        _check(f"os.{name}", path, dir_fd=kwargs.get("dir_fd"), follow=follow)
        return _real[name](path, *args, **kwargs)

    return _wrapped


def _guarded_mkdir(path, *args, **kwargs):
    anchored = _anchor(path, kwargs.get("dir_fd"))
    if anchored is not None and not os.path.exists(anchored):
        _check("os.mkdir", anchored, follow=False)
    return _real["mkdir"](path, *args, **kwargs)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with _real["open"](path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_copy(src: Path, dst: Path) -> dict:
    """src 를 dst 로 복사하고 검증한다 — 실패하면 `LiveStateWriteError`.

    복사 전후 src sha256 이 같아야 하고(복사 중 라이브가 바뀌지 않음), dst sha256 이 그와 같아야
    하며, dst 는 `PRAGMA integrity_check` 가 `ok` 여야 한다.
    """
    t0 = time.perf_counter()
    before = _sha256(src)
    shutil.copyfile(src, dst)
    after = _sha256(src)
    copied = _sha256(dst)
    if before != after:
        raise LiveStateWriteError(f"사본을 만드는 동안 라이브 DB 가 바뀌었다: {src}")
    if copied != before:
        raise LiveStateWriteError(f"사본 sha256 이 라이브와 다르다: {dst}")
    try:
        con = _real["connect"](f"file:{dst}?mode=ro", uri=True)
        try:
            rows = [r[0] for r in con.execute("PRAGMA integrity_check")]
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        raise LiveStateWriteError(f"사본 integrity 검사 실패: {exc}") from exc
    if rows != ["ok"]:
        raise LiveStateWriteError(f"사본 integrity 검사 실패: {rows[:5]}")
    return {
        "source": str(src),
        "copy": str(dst),
        "source_sha256_before": before,
        "source_sha256_after": after,
        "copy_sha256": copied,
        "integrity_check": "ok",
        "seconds": round(time.perf_counter() - t0, 2),
    }


def _sandbox_copy(live: Path) -> Path:
    """라이브 DB 의 세션 사본 경로. 처음 부를 때 한 번 복사·검증한다(라이브는 읽기만).

    검증을 통과한 사본은 읽기 전용(0444)으로 두고 (장치, inode) 를 등록해 가드가 지킨다.
    """
    key = str(live)
    if key not in _redirects:
        if _state["sqlite_dir"] is None:
            _state["sqlite_dir"] = Path(
                tempfile.mkdtemp(prefix="krx_live_db_sandbox_")
            ).resolve()
        copy = _state["sqlite_dir"] / live.relative_to(PROJECT_ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        if live.exists():
            try:
                report = verified_copy(live, copy)
            except LiveStateWriteError as exc:
                _copy_failures.append(f"{key}: {exc}")
                _record("session copy check", live, str(exc))
                raise
            _real["chmod"](copy, 0o444)
            _state["copy_ids"].add(_ids(copy))
            _copy_reports[key] = report
        _redirects[key] = copy
    return _redirects[key]


def set_current_test(nodeid: Optional[str]) -> None:
    """conftest 의 `pytest_runtest_protocol` 이 테스트마다 부른다(설정·본문·정리 전체)."""
    _state["current_test"] = nodeid


def _allow_session_copy(path: Path) -> None:
    """기존 호환 목록의 테스트만 세션 사본을 쓴다. 목록 밖이면 즉시 실패."""
    nodeid = _state["current_test"]
    record = os.environ.get(RECORD_ENV)
    if record:
        with _real["open"](record, "a", encoding="utf-8") as fh:
            fh.write(f"{nodeid}\n")
        return
    if nodeid not in LEGACY_READERS:
        _block(
            "sqlite3.connect",
            path,
            f"라이브 DB 를 열려 했다: {path} (테스트 {nodeid})\n"
            "새 테스트는 자체 임시 DB·고정 fixture 를 쓴다 — 세션 사본은 "
            "tests/_live_db_legacy_readers.txt 의 기존 테스트에만 허용된다.",
        )


_ATTACH_SQL = re.compile(
    r"^\s*ATTACH\s+(?:DATABASE\s+)?(?P<target>'(?:[^']|'')*'|.+?)\s+AS\s+"
    r"(?P<alias>\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|\w+)",
    re.IGNORECASE | re.DOTALL,
)
_MAIN_SCHEMAS = ("main", "temp")
_SQL_STRING = re.compile(r"'(?:[^']|'')*'", re.DOTALL)
_LEADING_NOISE = re.compile(r"(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*", re.DOTALL)


def _sql_literal(target: str) -> str | None:
    """ATTACH 대상이 **문자열 하나**면 그 값. `'a' || 'b'` 같은 식은 None(판정 불가)."""
    target = target.strip()
    if _SQL_STRING.fullmatch(target):
        return target[1:-1].replace("''", "'")
    return None


def _hits_live_or_copy(target) -> bool:
    try:
        return is_live(target) or _is_copy(target)
    except Exception:  # noqa: BLE001 — 판정할 수 없으면 막는다
        return True


def _sqlite_hooks():
    """연결마다 authorizer · trace callback 한 쌍 — SQL 안에서 파일을 붙이는 길을 막는다.

    `ATTACH '<경로>'`(문자열) · `VACUUM INTO` 는 authorizer 가 준비·실행 때 경로를 받아 바로 거부한다.
    `ATTACH ?`(매개변수) · 식은 준비 때 경로를 모른다 — 실행 직전 trace 가 값이 채워진 SQL 을 보고
    라이브·사본(또는 판정 불가)이면 기록하고 그 별칭의 모든 접근을 authorizer 가 거부한다.
    두 콜백은 연결 객체를 잡지 않는다(순환 참조로 연결이 늦게 닫히지 않게).
    """
    denied: set[str] = set()  # 막은 ATTACH 별칭(소문자) · "*" = main·temp 밖 전부

    def authorizer(action, arg1, arg2, dbname, source):
        if _state["suspended"]:
            return sqlite3.SQLITE_OK
        if denied and dbname:
            name = dbname.lower()
            if name in denied or ("*" in denied and name not in _MAIN_SCHEMAS):
                return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_DETACH and arg1:
            denied.discard(arg1.lower())
            return sqlite3.SQLITE_OK
        if action != sqlite3.SQLITE_ATTACH:
            return sqlite3.SQLITE_OK
        if denied:  # 막은 별칭이 붙어 있는 동안은 VACUUM · 다른 ATTACH 도 거부
            return sqlite3.SQLITE_DENY
        if arg1 and _hits_live_or_copy(arg1):
            _record(
                "sqlite ATTACH",
                arg1,
                f"ATTACH·VACUUM INTO 로 라이브 DB·사본을 붙이려 했다: {arg1}",
            )
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK  # arg1 None = 매개변수·식 → 아래 trace 가 본다

    def trace(sql):
        if _state["suspended"]:
            return
        body = sql[_LEADING_NOISE.match(sql).end() :]  # noqa: E203 — 앞 주석·공백
        if body[:6].upper() != "ATTACH":
            return
        m = _ATTACH_SQL.match(body)
        literal = _sql_literal(m.group("target")) if m else None
        if literal is not None and not _hits_live_or_copy(literal):
            return
        denied.add(m.group("alias").strip('"`[]').lower() if m else "*")
        _record(
            "sqlite ATTACH",
            literal if literal is not None else body[:200],
            "ATTACH(매개변수·식)로 라이브 DB·사본(또는 판정 불가 대상)을 붙이려 했다 — "
            "그 별칭의 접근을 모두 거부한다",
        )

    return authorizer, trace


def _guarded_connect(database, *args, **kwargs):
    path = _as_path(database)
    if path is not None and not _state["suspended"]:
        target = None
        live = _under(path, LIVE_ROOTS)
        if live is not None:
            _allow_session_copy(live)
            target = _sandbox_copy(live)
        elif _is_copy(path):  # 사본을 경로로 직접 여는 것도 목록 테스트만 · 읽기 전용
            _allow_session_copy(path)
            target = path
        if target is not None:
            text = (
                os.fsdecode(database)
                if isinstance(database, bytes)
                else os.fspath(database)
            )
            query = ""
            if text.startswith("file:") and "?" in text:
                query = text.split("?", 1)[1].split("#", 1)[0]
            params = [q for q in query.split("&") if q and not q.startswith("mode=")]
            database = f"file:{target}?" + "&".join(params + ["mode=ro"])
            kwargs["uri"] = True
    con = _real["connect"](database, *args, **kwargs)
    authorizer, trace = _sqlite_hooks()
    con.set_authorizer(authorizer)
    con.set_trace_callback(trace)
    return con


def real_connect(*args, **kwargs):
    """감시 전용 — 라이브 DB 를 사본이 아니라 **실제 파일**로 연다. `mode=ro` 로만 쓸 것."""
    return _real["connect"](*args, **kwargs)


def sqlite_redirects() -> dict[str, Path]:
    return dict(_redirects)


def copy_reports() -> dict[str, dict]:
    """세션에서 만든 사본마다 복사 전후 sha256 · integrity 결과."""
    return {k: dict(v) for k, v in _copy_reports.items()}


def copy_failures() -> list[str]:
    """사본 검사(hash·integrity)가 실패한 기록 — 앱 코드가 예외를 삼켜도 남는다."""
    return list(_copy_failures)


def recheck_copies(reports: Optional[dict[str, dict]] = None) -> list[dict]:
    """세션 끝 — 사본 sha256 을 다시 재서 만들 때와 비교한다."""
    out = []
    for key, report in (reports if reports is not None else _copy_reports).items():
        copy = Path(report["copy"])
        now = _sha256(copy) if copy.exists() else None
        out.append(
            {
                "source": key,
                "copy_sha256": report["copy_sha256"],
                "now_sha256": now,
                "same": now == report["copy_sha256"],
            }
        )
    return out


_OS_NAMES = (
    "replace",
    "rename",
    "remove",
    "unlink",
    "rmdir",
    "truncate",
    "chmod",
    "utime",
    "link",
    "symlink",
    "mkdir",
    *_EXTRA_OS,
)


def _os_wrapper(name: str):
    if name in ("replace", "rename"):
        return _two(name)
    return {
        "link": _guarded_link,
        "symlink": _guarded_symlink,
        "mkdir": _guarded_mkdir,
    }.get(name) or _one(name)


def install() -> None:
    """프로세스 전체에 가드를 건다. 두 번 불러도 한 번만 건다."""
    if _state["installed"]:
        return
    builtins.open = _guarded_open
    io.open = _guarded_io_open
    _io.open = _guarded_open
    os.open = _guarded_os_open
    _OS_MOD.open = _guarded_os_open
    for (
        name
    ) in _OS_NAMES:  # os.X 와 원본 모듈(posix·nt)의 X 를 같이 — 직접 부르는 길도 막는다
        wrapper = _os_wrapper(name)
        setattr(os, name, wrapper)
        if hasattr(_OS_MOD, name):
            setattr(_OS_MOD, name, wrapper)
    sqlite3.connect = _guarded_connect
    sqlite3.dbapi2.connect = _guarded_connect
    _sqlite3.connect = _guarded_connect
    _state["installed"] = True


def uninstall() -> None:
    if not _state["installed"]:
        return
    builtins.open = _real["open"]
    io.open = _real["io_open"]
    _io.open = _real["_io_open"]
    os.open = _real["os_open"]
    _OS_MOD.open = _real["osmod_open"]
    for name in _OS_NAMES:
        setattr(os, name, _real[name])
        if hasattr(_OS_MOD, name):
            setattr(_OS_MOD, name, _real[name])
    sqlite3.connect = _real["connect"]
    sqlite3.dbapi2.connect = _real["dbapi2_connect"]
    _sqlite3.connect = _real["_sqlite3_connect"]
    _state["installed"] = False
    if _state["sqlite_dir"] is not None:
        for copy in _redirects.values():
            if copy.exists():
                os.chmod(copy, 0o644)
        shutil.rmtree(_state["sqlite_dir"], ignore_errors=True)
        _state["sqlite_dir"] = None
        _state["copy_ids"].clear()
        _redirects.clear()
        _copy_reports.clear()


def installed() -> bool:
    return _state["installed"] and builtins.open is _guarded_open


@contextmanager
def suspended() -> Iterator[None]:
    """가드 자체 테스트가, 가드가 뚫렸을 때 남은 탐침 파일을 치울 때만 쓴다."""
    _state["suspended"] += 1
    try:
        yield
    finally:
        _state["suspended"] -= 1
