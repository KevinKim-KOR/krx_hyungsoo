"""테스트가 라이브 `state/`·`logs/` 에 쓰는 것을 **쓰는 순간** 막는 가드 (POC4-01 설계자 판정 2026-09-24).

전체 회귀가 맥북 라이브 경로 5곳(시장 DB · NAV 요약 · 실행 기록 · 로그 2개)에 썼다. 지금까지는 경로를
하나씩 monkeypatch 하고 파일 하나씩 감시했다 — 새 경로가 생길 때마다 뚫렸다("한 통로 막기").

그래서 **쓰기 연산 자체**에 건다. 대상 경로를 풀어서 라이브 루트 아래면 즉시 `LiveStateWriteError`.

- `open`/`io.open` 쓰기 모드(w·a·x·+) · `os.open` 쓰기 플래그
- `os.replace`·`os.rename`(출발·도착 모두) · `os.remove`·`os.unlink`·`os.rmdir` · `os.mkdir`(없는 경로)
  · `os.truncate` · `os.chmod` · `os.utime` · `os.link`·`os.symlink`(만드는 쪽)
- `sqlite3.connect` — 라이브 DB 경로로 오는 연결은 **세션 임시 사본을 읽기 전용(mode=ro)** 으로 연다.
  기존 테스트 96건이 운영 조회 함수로 라이브 시장 DB 를 rw 로 열어 **읽고** 있었다(처음 열 때
  `CREATE TABLE IF NOT EXISTS` — 이미 있는 테이블이면 읽기 전용에서도 통과). 경로 기본값이 함수 정의
  시점에 묶여 있어 모듈 상수 monkeypatch 로는 못 돌린다 → 연결 층에서 돌린다. 읽기는 그대로 되고,
  **쓰기(INSERT·DELETE·새 테이블 등)는 즉시 `attempt to write a readonly database` 로 실패**한다 —
  사고를 낸 `reset_state_for_testing()` 인자 누락 같은 패턴이 조용히 통과하지 않고, 사본이 바뀌지
  않으니 테스트끼리 데이터가 새지도 않는다. 라이브 DB 파일은 테스트가 열지 않는다.

파일 읽기는 막지 않는다. `tmp_path` 등 저장소 밖 경로는 영향이 없다. 하위 프로세스는 이 가드 밖이라
`conftest.py` 의 세션 전후 hash 비교가 따로 잡는다. 감시 코드만 `real_connect` 로 라이브 파일을 본다.
"""

from __future__ import annotations

import builtins
import io
import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_ROOTS = (PROJECT_ROOT / "state", PROJECT_ROOT / "logs")

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
_state = {"installed": False, "suspended": 0, "sqlite_dir": None}
_redirects: dict[str, Path] = {}


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


def _sandbox_copy(live: Path) -> Path:
    """라이브 DB 의 세션 사본 경로. 처음 부를 때 한 번 복사한다(라이브는 읽기만)."""
    key = str(live)
    if key not in _redirects:
        if _state["sqlite_dir"] is None:
            _state["sqlite_dir"] = Path(tempfile.mkdtemp(prefix="krx_live_db_sandbox_"))
        copy = _state["sqlite_dir"] / live.relative_to(PROJECT_ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        if live.exists():
            shutil.copyfile(live, copy)
        _redirects[key] = copy
    return _redirects[key]


def _guarded_connect(database, *args, **kwargs):
    path = _as_path(database)
    if path is not None and not _state["suspended"] and is_live(path):
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
