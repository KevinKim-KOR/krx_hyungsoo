"""테스트가 라이브 `state/`·`logs/` 에 쓰는 것을 **쓰는 순간** 막는 가드 (POC4-01 설계자 판정 2026-09-24).

전체 회귀가 맥북 라이브 경로 5곳(시장 DB · NAV 요약 · 실행 기록 · 로그 2개)에 썼다. 지금까지는 경로를
하나씩 monkeypatch 하고 파일 하나씩 감시했다 — 새 경로가 생길 때마다 뚫렸다("한 통로 막기").

그래서 **쓰기 연산 자체**에 건다. 대상 경로를 풀어서 라이브 루트 아래면 즉시 `LiveStateWriteError`.

- `open`/`io.open` 쓰기 모드(w·a·x·+) · `os.open` 쓰기 플래그
- `os.replace`·`os.rename`(출발·도착 모두) · `os.remove`·`os.unlink`·`os.rmdir` · `os.mkdir`(없는 경로)
  · `os.truncate` · `os.chmod` · `os.utime` · `os.link`·`os.symlink`(만드는 쪽)
- `sqlite3.connect` — 라이브 DB 경로로 오는 연결 (설계자 확정 2026-09-24 `READONLY_SESSION_COPY`):
  * **기존 호환 목록**(`tests/_live_db_legacy_readers.txt`)의 테스트만 세션 임시 사본을 읽기 전용(mode=ro)
    으로 연다. 운영 조회 함수의 경로 기본값이 함수 정의 시점에 묶여 있어 테스트에서 경로를 못 바꾸는
    기존 테스트들이다(처음 열 때 `CREATE TABLE IF NOT EXISTS` — 이미 있는 테이블이면 읽기 전용에서도 통과).
  * 목록 밖의 테스트(= 새 테스트)는 라이브 DB 를 여는 순간 `LiveStateWriteError` — 자체 임시 DB·고정
    fixture 를 써야 한다.
  * 사본은 세션에서 처음 필요할 때 한 번 만든다. 라이브 DB 의 복사 전후 sha256 이 같고 사본 sha256 이
    그와 같아야 하며, 사본은 `PRAGMA integrity_check` 가 `ok` 여야 한다. 아니면 즉시 실패.
  * 쓰기(INSERT·DELETE·새 테이블 등)는 즉시 `attempt to write a readonly database` 로 실패한다 —
    사고를 낸 `reset_state_for_testing()` 인자 누락 같은 패턴이 조용히 통과하지 않고, 사본이 바뀌지
    않으니 테스트끼리 데이터가 새지도 않는다. 라이브 DB 파일은 사본을 만들 때 읽기만 한다.
  * 목록 갱신 — `KRX_LIVE_DB_READERS_RECORD=<파일>` 로 전체 테스트를 돌리면 사본을 쓴 테스트 id 를
    그 파일에 적는다(이 모드에서는 목록 밖도 허용). 목록은 줄이기만 한다(새 테스트 추가 금지).

파일 읽기는 막지 않는다. `tmp_path` 등 저장소 밖 경로는 영향이 없다. 하위 프로세스는 이 가드 밖이라
`conftest.py` 의 세션 전후 hash 비교가 따로 잡는다. 감시 코드만 `real_connect` 로 라이브 파일을 본다.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import os
import shutil
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_ROOTS = (PROJECT_ROOT / "state", PROJECT_ROOT / "logs")
LEGACY_READERS_FILE = Path(__file__).resolve().parent / "_live_db_legacy_readers.txt"
RECORD_ENV = "KRX_LIVE_DB_READERS_RECORD"

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_real = {
    "open": builtins.open,
    "io_open": io.open,
    "os_open": os.open,
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
}
_state = {"installed": False, "suspended": 0, "sqlite_dir": None, "current_test": None}
_redirects: dict[str, Path] = {}
_copy_reports: dict[str, dict] = {}


def _load_legacy_readers() -> frozenset[str]:
    if not LEGACY_READERS_FILE.exists():
        return frozenset()
    lines = LEGACY_READERS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(s.strip() for s in lines if s.strip() and not s.startswith("#"))


LEGACY_READERS = _load_legacy_readers()


class LiveStateWriteError(AssertionError):
    """테스트가 라이브 state/logs 경로에 쓰려 했다 — tmp_path 로 격리해야 한다."""


def _as_path(target) -> Path | None:
    if isinstance(target, int):  # 파일 디스크립터
        return None
    if isinstance(target, bytes):
        target = target.decode()
    if not isinstance(target, (str, os.PathLike)):
        return None
    text = os.fspath(target)
    if text.startswith("file:"):
        text = text[len("file:") :].split("?", 1)[0]  # noqa: E203
    if text in ("", ":memory:"):
        return None
    return Path(os.path.abspath(text))


def is_live(target) -> bool:
    path = _as_path(target)
    if path is None:
        return False
    try:
        path = path.resolve()
    except OSError:
        pass
    return any(path == root or path.is_relative_to(root) for root in LIVE_ROOTS)


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


def _check(op: str, *targets, dir_fd=None) -> None:
    if _state["suspended"]:
        return
    for target in targets:
        target = _anchor(target, dir_fd)
        if target is not None and is_live(target):
            raise LiveStateWriteError(
                f"테스트가 라이브 경로에 쓰려 했다 ({op}): {target}\n"
                "tmp_path 로 격리하라 (tests/_live_guard.py)."
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
        _check("os.open", path, dir_fd=kwargs.get("dir_fd"))
    return _real["os_open"](path, flags, *args, **kwargs)


def _two(name):
    def _wrapped(src, dst, *args, **kwargs):
        _check(f"os.{name}", src, dir_fd=kwargs.get("src_dir_fd"))
        _check(f"os.{name}", dst, dir_fd=kwargs.get("dst_dir_fd"))
        return _real[name](src, dst, *args, **kwargs)

    return _wrapped


def _creates(name):
    """link·symlink — 새로 만들어지는 쪽(dst)만 본다. 원본을 가리키는 것은 쓰기가 아니다."""

    def _wrapped(src, dst, *args, **kwargs):
        _check(f"os.{name}", dst, dir_fd=kwargs.get("dst_dir_fd", kwargs.get("dir_fd")))
        return _real[name](src, dst, *args, **kwargs)

    return _wrapped


def _one(name):
    def _wrapped(path, *args, **kwargs):
        _check(f"os.{name}", path, dir_fd=kwargs.get("dir_fd"))
        return _real[name](path, *args, **kwargs)

    return _wrapped


def _guarded_mkdir(path, *args, **kwargs):
    anchored = _anchor(path, kwargs.get("dir_fd"))
    if anchored is not None and not os.path.exists(anchored):
        _check("os.mkdir", anchored)
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
    """라이브 DB 의 세션 사본 경로. 처음 부를 때 한 번 복사·검증한다(라이브는 읽기만)."""
    key = str(live)
    if key not in _redirects:
        if _state["sqlite_dir"] is None:
            _state["sqlite_dir"] = Path(tempfile.mkdtemp(prefix="krx_live_db_sandbox_"))
        copy = _state["sqlite_dir"] / live.relative_to(PROJECT_ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        if live.exists():
            _copy_reports[key] = verified_copy(live, copy)
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
        raise LiveStateWriteError(
            f"라이브 DB 를 열려 했다: {path} (테스트 {nodeid})\n"
            "새 테스트는 자체 임시 DB·고정 fixture 를 쓴다 — 세션 사본은 "
            "tests/_live_db_legacy_readers.txt 의 기존 테스트에만 허용된다."
        )


def _guarded_connect(database, *args, **kwargs):
    path = _as_path(database)
    if path is not None and not _state["suspended"] and is_live(path):
        _allow_session_copy(path)
        copy = _sandbox_copy(path.resolve())
        text = database.decode() if isinstance(database, bytes) else os.fspath(database)
        query = (
            text.split("?", 1)[1] if text.startswith("file:") and "?" in text else ""
        )
        params = [q for q in query.split("&") if q and not q.startswith("mode=")]
        database = f"file:{copy}?" + "&".join(params + ["mode=ro"])
        kwargs["uri"] = True
    return _real["connect"](database, *args, **kwargs)


def real_connect(*args, **kwargs):
    """감시 전용 — 라이브 DB 를 사본이 아니라 **실제 파일**로 연다. `mode=ro` 로만 쓸 것."""
    return _real["connect"](*args, **kwargs)


def sqlite_redirects() -> dict[str, Path]:
    return dict(_redirects)


def copy_reports() -> dict[str, dict]:
    """세션에서 만든 사본마다 복사 전후 sha256 · integrity 결과."""
    return {k: dict(v) for k, v in _copy_reports.items()}


def install() -> None:
    """프로세스 전체에 가드를 건다. 두 번 불러도 한 번만 건다."""
    if _state["installed"]:
        return
    builtins.open = _guarded_open
    io.open = _guarded_io_open
    os.open = _guarded_os_open
    os.replace = _two("replace")
    os.rename = _two("rename")
    os.remove = _one("remove")
    os.unlink = _one("unlink")
    os.rmdir = _one("rmdir")
    os.truncate = _one("truncate")
    os.chmod = _one("chmod")
    os.utime = _one("utime")
    os.link = _creates("link")
    os.symlink = _creates("symlink")
    os.mkdir = _guarded_mkdir
    sqlite3.connect = _guarded_connect
    _state["installed"] = True


def uninstall() -> None:
    if not _state["installed"]:
        return
    builtins.open = _real["open"]
    io.open = _real["io_open"]
    os.open = _real["os_open"]
    for name in (
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
    ):
        setattr(os, name, _real[name])
    os.mkdir = _real["mkdir"]
    sqlite3.connect = _real["connect"]
    _state["installed"] = False
    if _state["sqlite_dir"] is not None:
        shutil.rmtree(_state["sqlite_dir"], ignore_errors=True)
        _state["sqlite_dir"] = None
        _redirects.clear()
        _copy_reports.clear()


def installed() -> bool:
    return _state["installed"] and builtins.open is _guarded_open


@contextmanager
def suspended() -> Iterator[None]:
    """테스트 인프라가 **의도적으로** 라이브 파일을 되돌릴 때만 쓴다."""
    _state["suspended"] += 1
    try:
        yield
    finally:
        _state["suspended"] -= 1
