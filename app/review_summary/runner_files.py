"""POC7-02 Windows PC 실행기의 파일 도구(실행 묶음의 `review_files.py`) — 표준 라이브러리만.

```text
쓰기     write_x = 새 파일만 · 다 쓰고 fsync(받은 원문 — 끊겨도 남은 바이트를 지킨다)
         write_new = 임시 이름(.<이름>.part)에 다 쓴 뒤 이름 바꿈(시작 표지 · 한 장 · 결과 · 해시 — 다 쓴 파일이거나
         없거나 · 덮지 않음 · 잠깐 막히면 다시 시도 · 검증자 r2 F5)
앞 결과  같은 묶음 폴더의 result_*(번호 순) — 상태 · 실행 id(결과 → 시작 표지 → 받은 원문) · 멈춤 종류 · 모델 digest
         · 결과는 이름 바꾸기 전 임시 파일(.result.json.part)도 읽는다(맥북 회수와 같은 해석 · 검증자 r3 F9)
         · 다른 묶음의 결과는 뺀다 · 기록 없는 폴더는 running.lock 으로 '다른 창 실행 중'인지 본다
```
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

MAIN_STARTED, MAIN_RAW = "main_started.json", "main_raw.json"
LOCK = "running.lock"  # 실행 내내 열어 둔다(Windows 는 열린 파일을 지우지 못함 = 아직 실행 중)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dump(obj: Any) -> bytes:
    return (
        json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_x(path: Path, data: bytes) -> str:
    """새 파일만 · 다 쓰고 디스크에 내린다(fsync) · 반환 sha256 — 꺼져도 쓴 만큼은 남게."""
    with open(path, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return sha_bytes(data)


def _sync_dir(d: Path) -> None:
    try:  # 이름 바꿈을 디스크에(POSIX) · Windows 는 폴더를 열 수 없어 건너뜀
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_new(path: Path, data: bytes, tries: int = 20, wait: float = 0.25) -> str:
    """다 쓴 파일만 그 이름으로 보인다 — 임시 이름(.<이름>.part)에 쓰고 fsync 뒤 이름을 바꾼다 · 덮지 않는다.

    이름 바꾸기가 잠깐 막히면(Windows 백신 · 동기화 프로그램의 파일 잡기 등) 짧게 다시 시도한다(검토 · F5 같은 종류)."""
    tmp = path.with_name(f".{path.name}.part")
    write_x(tmp, data)
    for k in range(tries):
        if os.path.lexists(path):
            raise FileExistsError(str(path))
        try:
            os.rename(tmp, path)  # Windows 는 이름이 있으면 실패(덮지 않음)
            break
        except FileExistsError:
            raise
        except OSError:
            if k == tries - 1:
                raise
            time.sleep(wait)
    _sync_dir(path.parent)
    return sha_bytes(data)


def _read_state(p: Path) -> tuple[str, Optional[dict[str, Any]]]:
    """('absent' 없음 · 'ok' 읽힘 · 'bad' 깨짐 · 'unreadable' 못 읽음(잠깐 잡힘 등 · 세 번 시도), 값)."""
    for k in range(3):
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "absent", None
        except ValueError:  # 글자 꼴이 깨짐
            return "bad", None
        except OSError:
            if k == 2:
                return "unreadable", None
            time.sleep(0.2)
            continue
        try:
            v = json.loads(text)
        except ValueError:
            return "bad", None
        return ("ok", v) if isinstance(v, dict) else ("bad", None)
    return "unreadable", None


def _read_json(p: Path) -> Optional[dict[str, Any]]:
    return _read_state(p)[1]


def prior_results(
    bdir: Path, mine: Path, bundle_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """같은 묶음 폴더의 앞 결과 — {dir, status, run_id, main_started, 멈춤 종류}(기록이 없는 폴더도 남긴다).

    결과 기록이 없으면 실행 id 를 시작 표지 · 받은 원문에서 읽는다(맥북이 그 폴더를 기록 미완으로 받은 뒤
    이 기록을 순서대로 받을 수 있게 · 검증자 r2 F5). 다른 묶음의 결과(같은 폴더에 다른 zip 을 덮어 풂)는 뺀다."""
    out = []
    for d in sorted(bdir.glob("result_*"), key=_dir_no):
        if d == mine or not d.is_dir():
            continue
        row: dict[str, Any] = {
            "dir": d.name,
            "main_started": (d / MAIN_STARTED).exists() or (d / MAIN_RAW).exists(),
        }
        st, r = _read_state(d / "result.json")
        part = False
        # 이름 바꾸기 전 꺼짐 — 다 쓴 임시 결과도 그 실행의 기록(회수와 같은 해석 · 검증자 r3 F9)
        if st == "absent":
            st, r = _read_state(d / ".result.json.part")
            part = st == "ok"
            # 임시 결과를 쓰다 꺼짐 = 기록 없음(본 요약 전이면 다시 돌며 모든 확인을 처음부터)
            if st == "bad":
                st = "absent"
        row["result_from_part"] = part
        # 이름이 붙은 결과가 깨졌거나 결과 · 임시 결과를 못 읽음 — 무슨 멈춤인지 모르므로 다시 돌리지 않는다
        row["unreadable"] = st in ("bad", "unreadable")
        who = r or _read_json(d / MAIN_STARTED) or _read_json(d / MAIN_RAW) or {}
        row["bundle_id"] = who.get("bundle_id")
        if bundle_id and row["bundle_id"] not in (None, bundle_id):
            continue  # 다른 묶음의 결과 — 이 묶음의 앞 결과가 아니다
        # 고정된 모델 = 합성 점검까지 간 실행(또는 본 요약 시작 표지)의 digest — 판 확인에서 멈춘 값은 쓰지 않는다
        mark = _read_json(d / MAIN_STARTED) or {}
        reached = r is not None and r.get("trial") is not None
        digest = (((r or {}).get("env") or {}).get("model") or {}).get("digest")
        row["model_digest"] = (digest if reached else None) or mark.get("model_digest")
        if r is not None:
            kinds = set(
                ((r.get("trial") or {}).get("gate") or {}).get("categories") or []
            )
            kinds |= set((r.get("pre_main") or {}).get("categories") or [])
            kinds |= set((r.get("env_gate") or {}).get("categories") or [])
            row.update(
                status=r.get("status"),
                stop=r.get("stop") or r.get("status"),
                run_id=r.get("run_id"),
                stop_categories=sorted(kinds),
            )
        else:
            row.update(status="NO_RECORD", stop=None, run_id=who.get("run_id"))
            row["stop_categories"] = []
            busy = not row["main_started"] and not row["unreadable"]
            row["running"] = busy and _held(d / LOCK)
        out.append(row)
    return out


def _dir_no(d: Path) -> int:
    """result_<n> 의 n — 폴더 번호 순(글자 순이면 result_10 이 result_2 앞)."""
    n = d.name.removeprefix("result_")
    return int(n) if n.isdigit() else 10**9


def _held(lock: Path) -> bool:
    """기록 없는 앞 폴더의 잠금을 지워 본다 — 지워지면(또는 없으면) 꺼진 실행, 못 지우면 다른 창이 실행 중."""
    try:
        lock.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return False


def new_result_dir(bdir: Path) -> Path:
    for n in range(1, 1000):
        d = bdir / f"result_{n}"
        try:
            d.mkdir()
            return d
        except FileExistsError:
            continue
    raise RuntimeError("결과 폴더 번호가 다 참")
