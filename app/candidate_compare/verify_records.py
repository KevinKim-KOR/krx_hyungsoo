"""검산 기록 · 화면 표시 확인 · 검산 지문(검증자 r1 F2 · r2 F5 · F6).

```text
마지막 잠금  잠금의 previous_lock 이어짐으로 정한다 — 폴더 이름(시각 ID) 순서를 쓰지 않는다(PC 시계를 뒤로 돌려도 같음)
             잠금을 못 읽거나 이어짐이 한 줄이 아니면 문제로 남긴다(검산 = 어긋남 · 화면 = 판정 안 보임)
검산 이어짐  새 기록(형식 v2) = 앞 기록(이어짐 끝)의 ID · 바이트 해시 · seq + 1 을 담는다(실행 잠금 안에서) · 칸이 빠지면 손상.
             첫 v2 기록 = 그때 있던 옛 형식(v1) 기록의 ID · 해시 목록(뒤에 생기거나 바뀐 v1 은 손상) · 이어짐 끝 표시 =
             verify/LAST.json 을 **기록보다 먼저** 쓴다(끝 기록 ID · seq · 해시 · 앞 ID · 앞 해시). 인정하는 상태는 둘 —
             표시 = 끝 기록 · 표시가 '끝 다음 기록'인데 그 파일이 없음(쓰다 멈춤 · 끝 기록을 지움 = 화면 숨김 · 다음 검산이
             그 차례로 이어 씀). 그 밖(끝 기록을 바꿈 · 옛 표시 등)은 손상(r3 F9 · 반박 검토)
             이어짐이 한 줄이 아니거나 기록을 못 읽으면 새 검산은 멈추고(확인 필요) 화면은 판정을 숨긴다
쓰기 안전    기록에 넣는 글은 깨진 유니코드를 이스케이프 · 기록할 수 없는 수(NaN · inf)는 글로(safe) — 쓰다가 예외로 끝내지 않음
검산 지문    검산이 가져다 쓰는 저장소 코드 전부(verify.py 에서 import 를 따라간 app/ 파일) + 실행 환경(python · numpy)
화면 표시    마지막 잠금의 실행 하나 · 그 실행의 가장 최근 검산 = VERIFIED_OK · 어긋남 0 · 지금 검산 지문
             · 지금 파일 6개 해시 = 그 기록 → 해시를 잰 그 바이트의 보고 · 그 밖(못 읽음 · 형식 틀림 포함) = None
```
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from app.candidate_compare.flow import runs
from app.candidate_compare.protocol import SCHEMA, CheckRequired, env
from app.entry_timing.protocol import RUN_ID, dumps, inside, read_inside
from app.ml_evidence import store

REPO = Path(__file__).resolve().parents[2]
VERIFY_ENTRY = "app/candidate_compare/verify.py"
FILES = (
    "lock.json",
    "started.json",
    "run.json",
    "weeks.json",
    "report.json",
    "report.md",
)


def paths(lock_dir: Path, run_dir: Path) -> dict[str, Path]:
    return {n: (lock_dir if n == "lock.json" else run_dir) / n for n in FILES}


def parse_obj(raw: bytes) -> tuple[Optional[dict], Optional[str]]:
    """JSON 객체 하나 — (객체, None) · JSON 아님 · 객체 아님 = (None, 사유)(예외로 끝내지 않음 · F5)."""
    try:
        obj = json.loads(raw)
    except Exception as e:  # ValueError · UnicodeDecodeError · RecursionError
        return None, f"JSON 아님({type(e).__name__})"
    if not isinstance(obj, dict):
        return None, f"객체 아님({type(obj).__name__})"
    return obj, None


def read_obj(root: Path, path: Path) -> tuple[Optional[dict], Optional[str]]:
    try:
        raw = read_inside(root, path)
    except (OSError, CheckRequired) as e:
        return None, f"읽기 실패({type(e).__name__})"
    return parse_obj(raw)


def exists(path: Path) -> Optional[bool]:
    """있음 · 없음 · 확인 불가(None · 권한 등 OSError)."""
    try:
        return path.exists()
    except OSError:
        return None


def _dirs(root: Path, parent: Path) -> list[Path]:
    """이름이 ID 꼴인 폴더(링크 아님) — 목록을 못 읽으면 OSError 를 그대로 올린다."""
    if not parent.exists():
        return []
    inside(root, parent)
    return sorted(
        p
        for p in parent.iterdir()
        if RUN_ID.fullmatch(p.name) and not p.is_symlink() and p.is_dir()
    )


def lock_chain(root: Path) -> tuple[Optional[Path], list[str], list[Path]]:
    """(마지막 잠금 · 문제 · 잠금 폴더) — previous_lock 이어짐의 끝(F6 · 시각 ID 순서 안 씀).

    잠금 폴더 = 이름이 ID 꼴인 폴더 중 lock.json 이나 runs 가 있는 것(실행 코드 `locks` 와 같은 범위 + 실행만 남은 폴더).
    문제가 있으면 마지막 잠금은 None(폴더가 하나뿐이면 그 폴더) · 목록 · 존재를 확인할 수 없음도 문제.
    """
    try:
        listed = _dirs(root, root / "locks")
    except (OSError, CheckRequired) as e:
        return None, [f"잠금 폴더 목록을 읽을 수 없음({type(e).__name__})"], []
    dirs, probs = [], []
    for d in listed:
        has = [exists(d / "lock.json"), exists(d / "runs")]
        if None in has:
            probs.append(f"잠금 {d.name} 폴더를 확인할 수 없음")
            dirs.append(d)
        elif any(has):
            dirs.append(d)
    if not dirs:
        return None, probs, []
    try:
        tip, more = _chain_of_locks(root, dirs)
    except Exception as e:  # 어떤 꼴의 잠금 파일이 와도 예외로 끝내지 않는다(r3 F8)
        return (
            None,
            probs + [f"잠금 이어짐 확인 중 형식 오류({type(e).__name__})"],
            dirs,
        )
    probs += more
    if not probs and tip is not None:
        return tip, [], dirs
    return (dirs[0] if len(dirs) == 1 else None), probs, dirs


def _chain_of_locks(root: Path, dirs: list[Path]) -> tuple[Optional[Path], list[str]]:
    by = {d.name: d for d in dirs}
    prev: dict[str, Optional[str]] = {}
    probs: list[str] = []
    for d in dirs:
        obj, why = read_obj(root, d / "lock.json")
        if obj is None:
            probs.append(f"잠금 {d.name} lock.json {why}")
            continue
        p = obj.get("previous_lock")
        # 칸이 빠지면 '첫 잠금'으로 읽지 않는다(r3 F9 같은 종류) · 목록 · 객체 값도 예외 없이(r3 F8)
        if (
            "previous_lock" not in obj
            or obj.get("lock_id") != d.name
            or not (p is None or (isinstance(p, str) and p in by))
        ):
            probs.append(f"잠금 {d.name} 의 ID · 앞 잠금 칸이 폴더와 맞지 않음")
            continue
        prev[d.name] = p
    if probs:
        return None, probs
    used = Counter(p for p in prev.values() if p is not None)
    first = [n for n, p in prev.items() if p is None]
    tips = [n for n in prev if n not in used]
    if len(first) != 1:
        probs.append(f"첫 잠금(앞 잠금 없음)이 {len(first)}개")
    probs += [
        f"잠금 {p} 를 앞 잠금으로 둔 잠금이 {c}개"
        for p, c in sorted(used.items())
        if c > 1
    ]
    if len(tips) != 1:
        probs.append(f"마지막 잠금(뒤 잠금 없음)이 {len(tips)}개")
    if probs:
        return None, probs
    seen: set[str] = set()
    n: Optional[str] = tips[0]
    while n is not None and n not in seen:
        seen.add(n)
        n = prev.get(n)
    if len(seen) != len(prev):
        return None, ["잠금 이어짐이 끊기거나 돎"]
    return by[tips[0]], []


# ── 검산 기록 이어짐 ─────────────────────────────────────────────────────────

SEQ_MAX = 2**53
VERIFY_SCHEMA = (
    "poc7_03_verify_v2"  # 이어짐 기록(r3 정정 뒤) · 옛 형식 = SCHEMA["verify"](v1)
)
CHAIN_KEYS = ("seq", "prev", "prev_sha")
LAST = "LAST.json"


def records(root: Path) -> tuple[list[tuple[str, bytes, dict]], list[str]]:
    """((파일 이름 · 바이트 · 객체) 목록, 못 읽은 것) — 이름이 ID 꼴인 .json 만 · 폴더를 못 읽으면 그 사실이 못 읽은 것."""
    vdir = root / "verify"
    try:
        if not vdir.exists():
            return [], []
        inside(root, vdir)
        entries = sorted(vdir.iterdir())
    except (OSError, CheckRequired) as e:
        return [], [f"verify 폴더({type(e).__name__})"]
    good, bad = [], []
    for f in entries:
        if f.suffix != ".json" or not RUN_ID.fullmatch(f.stem):
            continue
        try:
            if f.is_symlink() or not f.is_file():
                bad.append(f.name)
                continue
            raw = read_inside(root, f)
        except (OSError, CheckRequired):
            bad.append(f.name)
            continue
        obj, _why = parse_obj(raw)
        if obj is None:
            bad.append(f.name)
        else:
            good.append((f.name, raw, obj))
    return good, bad


def legacy_now(root: Path) -> dict[str, str]:
    """지금 있는 옛 형식(v1) 기록의 ID → 바이트 해시 — 첫 v2 기록에 남긴다."""
    good, _bad = records(root)
    return {
        n[:-5]: store.sha256_bytes(raw)
        for n, raw, v in good
        if v.get("schema") == SCHEMA["verify"]
    }


def history(root: Path) -> tuple[Optional[dict], list[str], list[dict]]:
    """(이어짐 끝 기록 · 문제 · 이어짐 기록들) — 어떤 꼴의 기록이 와도 예외로 끝내지 않는다(r3 F8 같은 종류)."""
    tip, probs, chain, _state = history_state(root)
    return tip, probs, chain


def history_state(root: Path) -> tuple[Optional[dict], list[str], list[dict], str]:
    """history + 끝 표시 상태('none' · 'tip' · 'pending' · 'broken')."""
    try:
        return _history(root)
    except Exception as e:
        return None, [f"검산 기록 확인 중 형식 오류({type(e).__name__})"], [], "broken"


def _history(root: Path) -> tuple[Optional[dict], list[str], list[dict], str]:
    """한 줄 조건(r2 F6 · r3 F9):

    - v2 기록은 seq · prev · prev_sha 칸이 모두 있어야 한다(빠지면 손상 — 옛 형식으로 건너뛰지 않음).
    - 첫 기록 = seq 1 · prev · prev_sha 가 명시적으로 없음(null) · legacy = 그때 있던 v1 기록 ID · 해시.
    - 나머지 = 앞 기록이 있고 seq = 앞 seq + 1 · 앞 기록 바이트 해시 = prev_sha · 갈라짐 · 끊김 없음 · 파일 이름 = ID.
    - v1 기록은 첫 기록의 legacy 에 같은 해시로 있어야 한다(뒤에 생기거나 바뀐 v1 = 손상) · 그 밖 형식 = 손상.
    - LAST.json(먼저 씀) = 끝 기록, 또는 끝 다음 기록인데 그 파일이 없음(쓰다 멈춤) · 이어짐이 없으면 없거나 첫 기록 대기.
    """
    good, bad = records(root)
    probs = [f"검산 기록을 읽을 수 없음: {', '.join(bad[:5])}"] if bad else []
    chain: dict[str, tuple[bytes, dict]] = {}
    legacy: dict[str, str] = {}
    for name, raw, v in good:
        vid, schema = name[:-5], v.get("schema")
        if schema == SCHEMA["verify"]:
            legacy[vid] = store.sha256_bytes(raw)
            continue
        if schema != VERIFY_SCHEMA:
            probs.append(f"검산 기록 {name} 의 형식을 알 수 없음")
            continue
        s, pv, ps = v.get("seq"), v.get("prev"), v.get("prev_sha")
        if (
            not all(k in v for k in CHAIN_KEYS)
            or not (type(s) is int and 1 <= s <= SEQ_MAX)
            or v.get("verify_id") != vid
            or not (pv is None or isinstance(pv, str))
            or not (ps is None or isinstance(ps, str))
        ):
            probs.append(f"검산 기록 {name} 의 이어짐 칸이 빠지거나 꼴이 다름")
            continue
        chain[vid] = (raw, v)
    if probs:
        return None, probs, [], "broken"
    last_path = root / "verify" / LAST
    tip = None
    if chain:
        used = Counter(v["prev"] for _r, v in chain.values())
        roots = [v for _r, v in chain.values() if v["prev"] is None]
        for vid, (_raw, v) in chain.items():
            pv, ps = v["prev"], v["prev_sha"]
            if pv is None:
                if (
                    v["seq"] != 1
                    or ps is not None
                    or not isinstance(v.get("legacy"), dict)
                ):
                    probs.append(f"검산 기록 {vid} — 첫 기록의 차례 · 칸이 맞지 않음")
            elif pv not in chain:
                probs.append(f"검산 기록 {vid} — 앞 기록 {pv} 가 없음")
            elif (
                chain[pv][1]["seq"] != v["seq"] - 1
                or store.sha256_bytes(chain[pv][0]) != ps
            ):
                probs.append(f"검산 기록 {vid} — 앞 기록과 차례 · 해시가 맞지 않음")
        if len(roots) != 1:
            probs.append(f"첫 검산 기록이 {len(roots)}개")
        probs += [
            f"검산 기록 {p} 를 앞으로 둔 기록이 {c}개"
            for p, c in used.items()
            if p and c > 1
        ]
        if probs:
            return None, probs, [], "broken"
        allowed = roots[0]["legacy"]
        probs += [
            f"옛 형식 기록 {vid} 가 첫 기록의 목록에 없거나 바뀜"
            for vid, sha in sorted(legacy.items())
            if allowed.get(vid) != sha
        ]
        tip = max(chain.values(), key=lambda rv: rv[1]["seq"])
        seen, n = 0, tip[1]
        while n is not None:
            seen += 1
            n = chain[n["prev"]][1] if n["prev"] else None
        if seen != len(chain):
            probs.append("검산 기록 이어짐이 끊기거나 돎")
        if probs:
            return None, probs, [], "broken"
    state, why = _mark_state(root, last_path, tip)
    if state is None:
        return None, [f"LAST.json 이 이어짐 끝과 맞지 않음({why})"], [], "broken"
    return (tip[1] if tip else None), [], [v for _r, v in chain.values()], state


MARK_KEYS = {"verify_id", "seq", "sha256", "prev", "prev_sha"}


def mark_of(
    verify_id: str, seq: int, sha: str, prev: Optional[str], prev_sha: Optional[str]
) -> dict:
    return {
        "verify_id": verify_id,
        "seq": seq,
        "sha256": sha,
        "prev": prev,
        "prev_sha": prev_sha,
    }


def _mark_state(
    root: Path, last_path: Path, tip: Optional[tuple[bytes, dict]]
) -> tuple[Optional[str], str]:
    """끝 표시 상태 — 'none'(이어짐 · 표시 모두 없음) · 'tip'(표시 = 끝 기록) · 'pending'(표시 = 끝 다음 기록 · 그 파일 없음
    = 쓰다 멈춤 · 끝 기록을 지움) · None(손상)."""
    there = exists(last_path)
    if there is None:
        return None, "확인할 수 없음"
    if there is False:
        return ("none", "") if tip is None else (None, "없음")
    try:
        raw = read_inside(root, last_path)
    except (OSError, CheckRequired) as e:
        return None, f"읽기 실패({type(e).__name__})"
    mark, why = parse_obj(raw)
    if mark is None:
        return None, why or "형식 틀림"
    try:
        canonical = raw == dumps(mark)
    except Exception:
        canonical = False
    if (
        not canonical  # 중복 칸 · 다른 꼴 · 다른 인코딩
        or set(mark) != MARK_KEYS
        or not isinstance(mark["verify_id"], str)
        or not RUN_ID.fullmatch(mark["verify_id"])
        or type(mark["seq"]) is not int
    ):
        return None, "꼴이 다름"
    if tip is not None:
        raw_t, v = tip
        here = mark_of(
            v["verify_id"],
            v["seq"],
            store.sha256_bytes(raw_t),
            v["prev"],
            v["prev_sha"],
        )
        if mark == here:
            return "tip", ""
        after = (mark["seq"], mark["prev"], mark["prev_sha"]) == (
            v["seq"] + 1,
            v["verify_id"],
            store.sha256_bytes(raw_t),
        )
    else:
        after = (mark["seq"], mark["prev"], mark["prev_sha"]) == (1, None, None)
    if after and exists(root / "verify" / f"{mark['verify_id']}.json") is False:
        return "pending", ""
    return None, "다른 기록"


def next_link(root: Path) -> dict[str, Any]:
    """새 검산 기록의 이어짐 칸 — 이어짐에 문제가 있으면 확인 필요로 멈춘다(차례를 이을 수 없음)."""
    tip, probs, _chain = history(root)
    if probs:
        raise CheckRequired(
            "검산 기록 이어짐을 확인할 수 없음 — " + " · ".join(probs[:3])
        )
    if tip is None:
        return {"seq": 1, "prev": None, "prev_sha": None, "legacy": legacy_now(root)}
    raw = read_inside(root, root / "verify" / f"{tip['verify_id']}.json")
    return {
        "seq": tip["seq"] + 1,
        "prev": tip["verify_id"],
        "prev_sha": store.sha256_bytes(raw),
    }


def write_last(root: Path, mark: dict) -> None:
    """이어짐 끝 표시를 바꾼다(기록보다 먼저) — 같은 폴더 임시 파일 · fsync · 이름 바꾸기."""
    vdir = inside(root, root / "verify", make=True)
    tmp = vdir / f".{LAST}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "xb") as fh:
        fh.write(dumps(mark))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, vdir / LAST)


def safe(obj: Any) -> Any:
    """기록에 쓸 수 있는 꼴 — 깨진 유니코드(짝 없는 서로게이트 등)는 이스케이프 · NaN · inf 는 글(r2 반박 1 · 6)."""
    if isinstance(obj, str):
        return obj.encode("utf-8", "backslashreplace").decode("utf-8")
    if isinstance(obj, float) and not math.isfinite(obj):
        return repr(obj)
    if isinstance(obj, dict):
        return {safe(str(k)): safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe(v) for v in obj]
    return obj


# ── 검산 지문 ─────────────────────────────────────────────────────────────────


def _module_files(repo: Path, mod: str) -> list[str]:
    parts = mod.split(".")
    out = []
    for k in range(1, len(parts) + 1):
        init = "/".join(parts[:k]) + "/__init__.py"
        if (repo / init).is_file():
            out.append(init)
    leaf = "/".join(parts) + ".py"
    if (repo / leaf).is_file():
        out.append(leaf)
    return out


def code_closure(repo: Path = REPO, entry: str = VERIFY_ENTRY) -> list[str]:
    """검산이 가져다 쓰는 저장소 코드 — entry 에서 `app` import 를 따라간 파일 전부(함수 안 import 포함)."""
    seen: set[str] = set()
    todo = [entry]
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        for node in ast.walk(ast.parse((repo / rel).read_text(encoding="utf-8"))):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                mods = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for m in mods:
                if m == "app" or m.startswith("app."):
                    todo += _module_files(repo, m)
    return sorted(seen)


def verify_code(repo: Path = REPO) -> tuple[str, list[str]]:
    """(검산 지문, 대상 파일) — 대상 파일 해시 + 실행 환경. 바뀌면 옛 검산 기록으로 판정을 보이지 않는다(F6)."""
    files = code_closure(repo)
    body = {
        "files": {rel: store.sha256_file(repo / rel) for rel in files},
        "env": env(),
        "sqlite": sqlite3.sqlite_version,
    }
    return store.sha256_bytes(dumps(body)), files


# ── 화면 표시 ─────────────────────────────────────────────────────────────────


def verified_report(
    root: Path, lock_dir: Path, run_dir: Path
) -> Optional[dict[str, Any]]:
    """검산 기록 이어짐의 **맨 끝 기록**(무엇에 대한 검산이든 가장 새것)이 이 실행의 VERIFIED_OK · 어긋남 0 · 지금 검산
    지문이고 지금 파일 6개 해시가 그 기록과 같으면 해시를 잰 그 바이트의 보고 · 아니면 None(기록을 못 읽거나 이어짐이
    깨져도 None). 실행을 정할 수 없었던 어긋남 기록(실행 ID 없음)도 더 새것이면 이긴다(반박 8)."""
    now_raw: dict[str, bytes] = {}
    for n, p in paths(lock_dir, run_dir).items():
        try:
            now_raw[n] = read_inside(root, p)
        except (OSError, CheckRequired):
            return None
    now_h = {n: store.sha256_bytes(b) for n, b in now_raw.items()}
    tip, probs, _chain, state = history_state(root)
    if probs or tip is None or state != "tip":  # 쓰다 멈춤 · 끝 기록을 지움 = 숨김
        return None
    if tip.get("run_id") != run_dir.name or tip.get("lock_id") != lock_dir.name:
        return None
    v = tip
    ok = (
        v.get("schema") == VERIFY_SCHEMA
        and v.get("status") == "VERIFIED_OK"
        and type(v.get("n_checks")) is int
        and v.get("n_checks") == 0
        and v.get("checks") == []
        and v.get("verify_code_sha256") == verify_code()[0]
        and v.get("files") == now_h
    )
    if not ok:
        return None
    rep, _why = parse_obj(now_raw["report.json"])
    return rep


def display_report(root: Path) -> Optional[dict[str, Any]]:
    """한 장 맨 위 판정 줄의 근거 — 마지막 잠금(이어짐)의 실행 하나의 검산된 보고 · 문제가 하나라도 있으면 None."""
    try:
        tip, probs, _dirs_ = lock_chain(root)
        if tip is None or probs:
            return None
        rds = runs(root, tip)
        if len(rds) != 1:
            return None
        return verified_report(root, tip, rds[0])
    except Exception:  # 화면 경로는 판정을 숨기는 쪽으로만 실패한다
        return None
