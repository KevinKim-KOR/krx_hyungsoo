"""POC7-02 결과 회수 · 대조(PLAN §2-4 · 판정 §1 · §3) — USB 의 result_<n> 폴더를 맥북 사례에 한 번만 보관.

```text
대조   hashes.json ↔ result.json · one_page.html · main_raw.json 바이트 / 사례 · 묶음 id / 폴더 이름 · 실행 id
       / 실행기가 본 묶음 파일 해시 = 맥북 manifest(묶음 바뀜 기록은 예외로 보관) / 실행 코드 해시 = manifest
       / 맥북 묶음(zip) 안 파일 = manifest / 잠근 채점 메모 = 묶음에 적힌 해시 · 묶음보다 먼저 잠금
       / 본 요약 기록 = 받은 원문(main_raw.json) · 세기 토큰 · Ollama 판 · digest 필수 · 결과 안에서 서로 같음
       / '그 묶음에 들어간' judge 로 원값에서 다시 구분 · '그 묶음에 들어간' render 로 한 장을 다시 만들어 같은 바이트
꺼짐   result.json · hashes.json 이 다 쓰이지 않은 폴더도 시작 표지를 확인해 INCOMPLETE_RECORD 로 바이트 그대로 보관
       · 한 장 · 결과 · 해시는 이름 바꾸기 전 임시 파일(.<이름>.part)도 읽는다(다 썼으면 그대로 검증 · 검증자 r2 F5)
       · hashes.json 만 있고 result.json 이 없거나, 결과에 원문이 있는데 원문이 없으면 복사 누락 · 깨진 result.json 은
       복사 손상으로 거부 · 기록 미완의 한 장은 결과 기록으로 다시 만들어 대조
순서   앞 묶음이 모두 회수돼야(다시 실행 멈춤 기록만은 아님) 뒤 묶음 결과를 받는다 · 같은 폴더의 같은 묶음 앞 결과를 먼저
       · 기록 미완 뒤 같은 실행(같은 실행 id)의 완전한 폴더(표지 정체 칸이 같을 때) · 더 담긴 기록 미완(앞서 받은 바이트와
       같을 때)은 대신 받는다 · 실행 id 가 다르면 언제나 다른 시도(손상 추정으로 합치지 않음 · 검증자 r4 F13)
       · 두 번째 본 요약 시도는 거부하지 않고 보관해 나중에 받은 쪽에 attempt_conflict 로 표시(고르지 않음 · report 는
       회수 순서와 상관없이 시도 수로 판정을 막음 · 검증자 r1 F2)
보관   cases/<사례>/runs/<묶음>__<실행 id>[__incomplete<n>]/ — 숨김 폴더에 다 쓴 뒤 이름을 바꾼다(끊겨도 반쪽 기록 없음)
       result.json · one_page.html · main_raw.json · main_started.json · hashes.json · merge.json
```

밖(USB) 폴더는 보통 파일만 읽는다(링크 · 폴더 · 너무 큰 파일 거부). 어긋나면 보관하지 않고 CheckRequired.
남는 한계: USB 의 결과를 사람이 일부러 고치고 해시까지 다시 맞추면(내용 · 시각 등) 막지 못한다(실수 · 손상 · 뒤섞임만 잡음).
"""

from __future__ import annotations

import os
import re
import stat
import sys
import time
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.entry_timing.protocol import (
    CheckRequired,
    dumps,
    inside,
    real_root,
)
from app.ml_evidence import store
from app.review_summary.bundle import (
    SHIPPED,
    bundles_of,
    merged_runs,
    publish_dir,
    read_bundle,
    stop_kind,
)
from app.review_summary.case import case_dir, check_lock, iso, kst_now
from app.review_summary.merge_checks import (
    INCOMPLETE,
    MAIN_RAW,
    MAIN_STARTED,
    RUN,
    _check_marker,
    _check_marker_run,
    _check_raw,
    _json,
    _check_body,
    _try_json,
    clock_notes,
)

RESULT_DIR = re.compile(r"result_\d{1,3}")
MAX_BYTES = 64 * 1024 * 1024
# 실행기가 다 쓴 뒤 이름을 바꾸는 기록(표지는 따로)
ATOMIC = ("one_page.html", "result.json", "hashes.json")
# 결과 파일의 사본 이름(Windows '둘 다 유지' = 'result (2).json' · 복사본 · Finder 'result 2.json' 등) — 결과 폴더 둘을
# 하나로 겹쳐 복사한 흔적. OS 가 붙이는 '._이름' · .DS_Store · Thumbs.db · desktop.ini 는 해당 없음.
COPY_TRACE = re.compile(
    r"\.?(main_started|main_raw|one_page|result|hashes)\b.*\.(json|html|part)"
)


def _read_outside(d: Path, name: str, required: bool = True) -> Optional[bytes]:
    """USB 폴더의 보통 파일만(링크 · 폴더 · FIFO · 너무 큰 파일 거부 · 링크를 따라가지 않고 연다)."""
    p = d / name
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        if not required:
            return None
        raise CheckRequired(f"결과 폴더에 {name} 이 없음") from None
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
        raise CheckRequired(f"보통 파일이 아니거나 너무 큼: {name}")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as fh:
        got = os.fstat(fh.fileno())
        if (got.st_dev, got.st_ino) != (st.st_dev, st.st_ino):
            raise CheckRequired(f"확인한 파일과 연 파일이 다름: {name}")
        return fh.read()


def _load(name: str, src: bytes) -> types.ModuleType:
    """묶음에 들어간 코드(해시 대조를 마친 바이트)를 모듈로 — 표준 라이브러리만 쓰는 파일."""
    mod = types.ModuleType(name.removesuffix(".py"))
    exec(compile(src, name, "exec"), mod.__dict__)
    return mod


def shipped_code(b: dict[str, Any]) -> tuple[types.ModuleType, types.ModuleType]:
    """(judge, render) — 그 묶음에 들어간 사본. render 가 부르는 review_judge 도 그 사본으로 잇는다."""
    files = b["manifest"].get("files") or {}
    shipped = b["shipped"]
    if sorted(shipped) != sorted([*files, "manifest.json"]):
        raise CheckRequired("맥북 묶음(zip)의 파일 목록이 manifest 와 다름")
    for n, want in files.items():
        if store.sha256_bytes(shipped[n]) != want:
            raise CheckRequired(f"맥북 묶음(zip)의 {n} 이 manifest 와 다름")
    judge = _load("review_judge.py", shipped["review_judge.py"])
    saved = sys.modules.get("review_judge")
    sys.modules["review_judge"] = judge
    try:
        render = _load("review_render.py", shipped["review_render.py"])
    finally:
        if saved is None:
            sys.modules.pop("review_judge", None)
        else:
            sys.modules["review_judge"] = saved
    return judge, render


def _folder(rd: Path) -> tuple[dict[str, bytes], list[str], dict[str, bytes]]:
    """USB 결과 폴더 — (이름 → 바이트, 임시 파일에서 읽은 이름, 남은 표지 임시 파일).

    한 장 · 결과 · 해시는 이름이 없으면 같은 이름의 임시 파일(.<이름>.part · 이름 바꾸기 전 꺼짐)을 읽는다.
    시작 표지의 임시 파일은 표지로 쓰지 않는다(이름을 못 바꿨으면 본 요약을 부르지 않았다 · 증거로만 보관)."""
    known = {n for k in (MAIN_STARTED, MAIN_RAW, *ATOMIC) for n in (k, f".{k}.part")}
    traces = sorted(
        n for n in os.listdir(rd) if n not in known and COPY_TRACE.fullmatch(n)
    )
    # 두 시도의 결과 폴더가 겹쳐 하나만 보이면 시도를 하나로 셀 수 있다(검증자 r4 F13 같은 종류)
    if traces:
        raise CheckRequired(
            f"결과 폴더에 결과 파일의 사본 이름이 있음({', '.join(traces)}) — 같은 이름의 결과 폴더를 겹쳐 복사한"
            " 흔적일 수 있음 · 풀기 폴더마다 결과 폴더를 따로 가져오세요(설계자 판단)"
        )
    got: dict[str, bytes] = {}
    parts: list[str] = []
    for n in (MAIN_STARTED, MAIN_RAW, *ATOMIC):
        b = _read_outside(rd, n, required=False)
        if b is None and n in ATOMIC:
            b = _read_outside(rd, f".{n}.part", required=False)
            if b is not None:
                parts.append(n)
        if b is not None:
            got[n] = b
    left = _read_outside(rd, f".{MAIN_STARTED}.part", required=False)
    return got, parts, ({f".{MAIN_STARTED}.part": left} if left is not None else {})


def _stored(files: dict[str, bytes], parts: list[str]) -> dict[str, bytes]:
    """보관 이름 — 임시 파일에서 읽은 기록 미완 바이트는 원래 임시 이름으로(검증된 것과 섞이지 않게)."""
    return {(f".{k}.part" if k in parts else k): v for k, v in files.items()}


def _incomplete(  # noqa: C901 — 폴더 상태 하나하나를 차례로 본다
    root: Path,
    case_id: str,
    rd: Path,
    got: dict[str, bytes],
    parts: list[str],
    left: dict[str, bytes],
) -> dict[str, Any]:
    """결과 기록이 다 쓰이지 않은 폴더(꺼짐 · 창 닫힘) — 남은 바이트를 그대로 보관한다(첫 결과 보존 · 검증자 r2 F5).

    실행기는 hashes.json 을 마지막에 다 쓴 뒤에만 보이게 하므로, 그것이 있는데 result.json 이 없으면 복사 누락(거부).
    result.json 도 다 쓴 뒤에만 이름이 붙으므로 그 이름의 깨진 파일은 복사 손상(거부 · 임시 파일만 깨질 수 있음).
    누구의 기록인지는 시작 표지(있으면 필수 · 깨지면 거부)나 읽히는 result.json 으로 확인한다. 결과 기록이 있으면
    완료 경로와 같은 함수(_check_body)로 해시만 빼고 대조한다(검증자 r3 F10).
    """
    body, hraw = got.get("result.json"), got.get("hashes.json")
    if body is None and hraw is not None:
        raise CheckRequired(
            "result.json 이 빠짐(복사 누락) — 원래 결과 폴더 전체를 가져오세요"
        )
    mraw, raw_b = got.get(MAIN_STARTED), got.get(MAIN_RAW)
    claim = _try_json(body)
    if body is not None and claim is None and "result.json" not in parts:
        raise CheckRequired(
            "result.json 이 깨짐(복사 손상 · 실행기는 다 쓴 결과만 남김) — 원래 결과 폴더 전체를 다시 가져오세요"
        )
    marker: Optional[dict[str, Any]] = None
    if mraw is None:
        if raw_b is not None:
            raise CheckRequired(
                "받은 원문이 있는데 시작 표지(main_started.json)가 없음"
            )
        if claim is None:
            raise CheckRequired(
                "결과 폴더에 읽히는 결과 기록도 시작 표지도 없음(본 요약 전 멈춤 · 보관할 것 없음)"
            )
        if claim.get("main") is not None:
            raise CheckRequired(
                "본 요약 기록이 있는데 시작 표지(main_started.json)가 없음"
            )
        who = claim
    else:
        try:
            marker = _json(mraw, MAIN_STARTED)
        except CheckRequired:
            raise CheckRequired(
                "시작 표지(main_started.json)가 깨짐 — 실행기는 다 쓴 표지만 남긴다(손상 · 설계자 판단)"
            ) from None
        who = marker
    if who.get("case_id") != case_id:
        raise CheckRequired(f"다른 사례의 결과: {who.get('case_id')!r}")
    if not RUN.fullmatch(str(who.get("run_id") or "")):
        raise CheckRequired("결과 · 시작 표지의 실행 id 꼴이 다름")
    b = read_bundle(root, case_id, str(who.get("bundle_id") or ""))
    if marker is not None:
        _check_marker(marker, b["input"], case_id, rd.name)
    main = (claim or {}).get("main") or {}
    if claim is not None:
        if any(claim.get(k) != who.get(k) for k in ("case_id", "bundle_id", "run_id")):
            raise CheckRequired("result.json 이 시작 표지와 다른 실행의 것")
        if claim.get("result_dir") != rd.name:
            raise CheckRequired("결과 폴더 이름 · 실행 id 가 결과에 적힌 것과 다름")
        if main.get("raw_sha256") and raw_b is None:
            raise CheckRequired(
                "결과 기록에는 받은 원문이 있는데 main_raw.json 이 빠짐(복사 누락) — 원래 폴더 전체를 가져오세요"
            )
    check_lock(root, case_id, b["input"])
    raw = _try_json(raw_b)
    unparsed = raw_b is not None and raw is None  # 쓰는 도중 꺼짐 — 바이트 그대로 둔다
    if raw is not None and raw.get("run_id") != who["run_id"]:
        raise CheckRequired("받은 원문의 실행 id 가 시작 표지와 다름")
    page = got.get("one_page.html")
    # 한 장 쓰기 실패로 남은 임시 한 장은 증거로만 — 완료 경로와 같게(이름이 붙은 한 장은 그대로 대조)
    if "one_page.html" in parts and claim is not None and claim.get("render_error"):
        page = None
    checks: dict[str, Any] = {}
    if claim is not None:
        want = main.get("raw_sha256")
        if want and raw_b is not None and store.sha256_bytes(raw_b) != want:
            raise CheckRequired(
                "받은 원문이 결과 기록의 원문 해시와 다름(복사 손상) — 원래 폴더 전체를 가져오세요"
            )
        res_c = dict(claim)
        if marker is not None:
            res_c["_marker"] = marker
        _check_raw(res_c, raw)
        judge, render = shipped_code(b)
        checks = _check_body(res_c, b, judge, render, page, None, marker, raw)
    src = marker or {}
    cenv = (claim or {}).get("env") or {}
    res = {
        "run_id": who["run_id"],
        "bundle_id": who["bundle_id"],
        "status": INCOMPLETE,
        # 원값 대조를 통과한 결과 기록의 멈춤 종류(길이 · 새 묶음 근거 · 검증자 r3 F9 옆 칸)
        "stop": ((claim or {}).get("stop") or (claim or {}).get("status")),
        "trial": (claim or {}).get("trial"),
        "pre_main": (claim or {}).get("pre_main"),
        "env_gate": (claim or {}).get("env_gate"),
        "run_wall_s": (claim or {}).get("run_wall_s"),
        "started_at": src.get("at") or (claim or {}).get("started_at"),
        "ended_at": (claim or {}).get("ended_at"),
        "env": {
            "ollama_version": src.get("ollama_version") or cenv.get("ollama_version"),
            "model": {
                "digest": src.get("model_digest")
                or (cenv.get("model") or {}).get("digest")
            },
        },
    }
    note = "결과 기록이 다 쓰이지 않음(꺼짐 · 창 닫힘 · 깨진 해시) — 해시로 검증하지 못함 · 남은 바이트 그대로"
    return {
        "result": res,
        "files": {**_stored(got, parts), **left},
        "name": rd.name,
        "main_started": marker is not None,
        "has_output": (
            None
            if unparsed
            else bool(raw and raw.get("response")) or bool(main.get("content"))
        ),
        "prior_results": (claim or {}).get("prior_results") or [],
        "checks": {
            "status": INCOMPLETE,
            "main_status": None,
            "note": note,
            "raw_unparsed": unparsed,
            "result_unverified": body is not None,
            "hashes_broken": hraw is not None,
            "claimed_status": (claim or {}).get("status"),
            "claim_checked": claim is not None,
            "page_verified": True if checks.get("main") and page is not None else None,
            "from_part": parts,
            "clock": clock_notes(marker, b["input"], claim, raw) if marker else None,
        },
    }


def verify(root: Path, case_id: str, result_dir: Path) -> dict[str, Any]:
    """대조만(쓰기 없음) — 하나라도 어긋나면 CheckRequired."""
    rd = Path(result_dir)
    if rd.is_symlink() or not rd.is_dir() or not RESULT_DIR.fullmatch(rd.name):
        raise CheckRequired(f"결과 폴더가 아님(result_<n> 실제 폴더): {rd}")
    got, parts, left = _folder(rd)
    body, hraw = got.get("result.json"), got.get("hashes.json")
    hashes = _try_json(hraw)
    if body is None or hashes is None:  # 없거나 깨진 해시 = 기록 미완(검증자 r2 F5)
        return _incomplete(root, case_id, rd, got, parts, left)
    if store.sha256_bytes(body) != hashes.get("result.json"):
        raise CheckRequired("result.json 해시가 hashes.json 과 다름")
    res = _json(body, "result.json")
    if res.get("case_id") != case_id:
        raise CheckRequired(f"다른 사례의 결과: {res.get('case_id')!r}")
    if res.get("result_dir") != rd.name or not RUN.fullmatch(res.get("run_id") or ""):
        raise CheckRequired("결과 폴더 이름 · 실행 id 가 결과에 적힌 것과 다름")
    b = read_bundle(root, case_id, res.get("bundle_id") or "")
    files = b["manifest"].get("files") or {}
    check_lock(root, case_id, b["input"])
    judge, render = shipped_code(b)
    out_files: dict[str, Optional[bytes]] = {"result.json": body, "hashes.json": hraw}
    out_files.update(left)
    started_b, raw_b = got.get(MAIN_STARTED), got.get(MAIN_RAW)
    if raw_b is not None:
        if store.sha256_bytes(raw_b) != hashes.get(MAIN_RAW):
            raise CheckRequired("main_raw.json 해시가 hashes.json 과 다름")
        out_files[MAIN_RAW] = raw_b
    elif hashes.get(MAIN_RAW) is not None:
        raise CheckRequired("hashes.json 에 받은 원문이 있는데 파일이 없음")
    wrote_bad = bool((res.get("main") or {}).get("raw_write_error"))
    raw = _try_json(raw_b) if wrote_bad else (_json(raw_b, MAIN_RAW) if raw_b else None)
    marker: Optional[dict[str, Any]] = None
    # 시작 표지도 해시 · 실행 id · 폴더 · 설정 · 판으로 대조(검증자 r2 F7)
    if started_b is not None:
        if store.sha256_bytes(started_b) != hashes.get(MAIN_STARTED):
            raise CheckRequired("main_started.json 해시가 hashes.json 과 다름")
        out_files[MAIN_STARTED] = started_b
        marker = _json(started_b, MAIN_STARTED)
        _check_marker(marker, b["input"], case_id, rd.name)
        _check_marker_run(marker, res)
        res["_marker"] = marker
    elif hashes.get(MAIN_STARTED) is not None:
        raise CheckRequired("hashes.json 에 시작 표지가 있는데 파일이 없음")
    _check_raw(res, raw)
    page = got.get("one_page.html")
    # 이름 바꾸기 실패로 남은 한 장(쓰기 실패 기록 · 해시 없음) — 증거로만
    if "one_page.html" in parts and hashes.get("one_page.html") is None:
        out_files[".one_page.html.part"] = page
        parts = [n for n in parts if n != "one_page.html"]
        page = None
    checks: dict[str, Any] = {
        "status": res.get("status"),
        "stop": res.get("stop"),
        "from_part": parts,
        "raw_write_error": (res.get("main") or {}).get("raw_write_error"),
        "raw_unparsed": raw_b is not None and raw is None,
        "clock": (clock_notes(marker, b["input"], res, raw) if marker else None),
        "repo_code_same_as_bundle": all(
            store.sha256_bytes(p.read_bytes()) == files.get(n)
            for n, p in SHIPPED.items()
        ),
    }
    if (res.get("stop") or res.get("status")) == "BUNDLE_CHANGED":
        checks["changed_files"] = sorted(
            n for n in files if (res.get("files") or {}).get(n) != files[n]
        )
    checks.update(_check_body(res, b, judge, render, page, hashes, marker, raw))
    if res.get("main") is not None:
        out_files["one_page.html"] = page  # type: ignore[assignment]
    started = marker is not None or raw is not None or res.get("main") is not None
    return {
        "result": res,
        "files": {k: v for k, v in out_files.items() if v is not None},
        "checks": checks,
        "name": rd.name,
        "main_started": started,
        "has_output": bool(raw and raw.get("response"))
        or bool((res.get("main") or {}).get("content")),  # 원문 쓰기 실패여도 받은 본문
        "prior_results": res.get("prior_results") or [],
    }


def _order(
    base: Path, case_id: str, bid: str, v: dict[str, Any], runs: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """회수 순서(검증자 r1 F2 · r2 F5) — 회수 순서로 '첫 결과'를 정하지 않는다. 반환 = 이 폴더가 대신할 기록 미완.

    - 앞 묶음이 모두 회수돼 있어야 한다(다시 실행 멈춤(ALREADY_RAN · 기록 미완 포함) 기록만으로는 회수가 아니다).
    - 같은 폴더의 같은 묶음 앞 결과(기록이 있는 것)가 먼저 회수돼 있어야 한다. 정체(묶음)를 남기지 못하고 모델도 부르지
      않은 앞 결과(묶음 입력을 못 읽음 · 정체 전 중단)는 받을 수 없으므로 건너뛴다(검토 B).
    - 같은 실행은 한 번 — 단 기록 미완 뒤 같은 실행의 더 담긴 복사본 · 완전한 폴더는 받는다(_check_replace).
    - 두 번째 본 요약 시도(같은 묶음을 두 번 풀기 등)는 거절하지 않고 보관해 '설계자 판단'으로 표시한다.
    """
    order = bundles_of(base, case_id)
    merged = {r.get("bundle_id") for r in runs if stop_kind(r) != "ALREADY_RAN"}
    earlier = order[: order.index(bid)] if bid in order else []
    missing = [b for b in earlier if b not in merged]
    if missing:
        raise CheckRequired(f"앞 묶음 결과를 먼저 회수해야 함: {', '.join(missing)}")
    rid = v["result"]["run_id"]
    same = [r for r in runs if r.get("run_id") == rid]
    if same and any(r.get("status") != INCOMPLETE for r in same):
        raise FileExistsError(f"같은 실행이 이미 보관됨: {rid}")
    have = {r.get("run_id") for r in runs if r.get("bundle_id") == bid}
    for p in v.get("prior_results") or []:
        if p.get("bundle_id") not in (None, bid):
            continue  # 같은 폴더에 풀린 다른 묶음의 결과 — 그 묶음의 순서다
        if not p.get("main_started") and (
            p.get("status") == "NO_RECORD"
            or (p.get("bundle_id") is None and not p.get("stop_categories"))
        ):
            continue  # 본 요약 전에 꺼진 빈 폴더 · 정체 없이 모델을 부르지 않은 멈춤 — 보관할 수 없다
        if p.get("run_id") is None:
            raise CheckRequired(
                f"같은 폴더의 앞 결과({p.get('dir')})의 실행 id 를 알 수 없음(시작 표지 손상) — 설계자 판단"
            )
        if p.get("run_id") not in have:
            raise CheckRequired(
                f"같은 폴더의 앞 결과({p.get('dir')})를 먼저 회수해야 함"
            )
    if not same:
        return None
    replaced = {r.get("replaces") for r in same}
    return next(r for r in same if r.get("record_dir") not in replaced)


def _plain(name: str) -> str:
    return name[1:-5] if name.startswith(".") and name.endswith(".part") else name


def _same_name(name: str) -> str:
    """대신 받기 비교 이름 — 표지 임시 파일은 표지가 아니라 증거라 그 이름 그대로, 나머지 임시 파일은 원래 이름."""
    return name if name == f".{MAIN_STARTED}.part" else _plain(name)


# 실행의 정체 — 실행 id 는 무작위 · 시각을 담아 한 실행에 하나다. 판 · 설정 · 시각이 다른 보관 표지는 손상으로 보고 기록만.
IDENTITY = ("case_id", "bundle_id", "run_id", "result_dir")


def _kept(base: Path, cdir: Path, old: dict[str, Any]) -> dict[str, bytes]:
    """앞서 보관한 기록 미완 바이트 — 원래 이름으로(표지 임시 파일은 표지가 아니다 · 증거 이름 그대로)."""
    d = inside(base, cdir / "runs" / old["record_dir"])
    out = {}
    for n in os.listdir(d):
        if n == "merge.json":
            continue
        out[_same_name(n)] = (d / n).read_bytes()
    return out


def _check_replace(
    base: Path, cdir: Path, old: dict[str, Any], v: dict[str, Any]
) -> list[str]:
    """기록 미완을 대신 받을 수 있는가 · 반환 = 앞서 보관한 바이트와 달랐던 파일(검증 못 한 것 · 기록만).

    해시로 검증된 완전한 폴더: 앞서 받은 시작 표지의 정체 칸(사례 · 묶음 · 실행 id · 결과 폴더)만 같으면 받는다
    (판 · 설정 · 시각 등 나머지 칸 · 결과 · 원문 · 한 장이 달라도 — 손상 복사본이 원본을 막지 않게 · 검증자 r3 F10).
    기록 미완 → 기록 미완은 더 담긴 복사본이고 앞서 받은 표지 · 결과 · 원문이 같을 때만(깨진 원문은 새 원문의 앞부분이면 같음).
    실행 id 가 다른 기록은 대신 받지 않는다 — 같은 초에 시작한 다른 시도와 실행 id 손상 복사본을 구별할 근거가 없어
    둘 다 시도로 세고 판정을 막는다(검증자 r4 F13 · 손상 추정으로 시도를 합치지 않음)."""
    kept = _kept(base, cdir, old)
    new = {_same_name(n): b for n, b in v["files"].items()}
    full = v["result"]["status"] != INCOMPLETE
    km, nm = kept.get(MAIN_STARTED), new.get(MAIN_STARTED)
    if km is not None:
        a, b = _try_json(km) or {}, _try_json(nm) or {}
        same_id = nm is not None and all(a.get(k) == b.get(k) for k in IDENTITY)
        if not (same_id if full else km == nm):
            raise CheckRequired(
                f"앞서 기록 미완으로 보관한 {MAIN_STARTED} 이 이 폴더와 다름 — 설계자 판단"
            )
    differs = sorted(n for n in kept if n != "hashes.json" and kept[n] != new.get(n))
    if full:
        return differs
    lacking = [n for n in kept if n != "hashes.json" and n not in new]
    if lacking:
        raise FileExistsError(
            f"같은 실행의 기록 미완이 이미 보관됨(더 담긴 복사본이 아님): {old['run_id']}"
        )
    grew = False  # 끊긴 원문이 더 길게 이어진 복사본(같은 앞부분)
    for name in ("result.json", MAIN_RAW):
        if name not in kept:
            continue
        kb, nb = kept[name], new[name]
        if kb == nb:
            continue
        if name == MAIN_RAW and nb.startswith(kb) and _try_json(kb) is None:
            grew = True
            continue
        if name == MAIN_RAW and kb.startswith(nb) and _try_json(nb) is None:
            raise FileExistsError(  # 더 짧게 끊긴 복사본 — 순서를 바꿔 받아도 남는 것은 긴 원문(검토 순서)
                f"같은 실행의 기록 미완이 이미 보관됨(더 담긴 복사본이 아님): {old['run_id']}"
            )
        raise CheckRequired(
            f"앞서 기록 미완으로 보관한 {name} 이 이 폴더와 다름 — 설계자 판단"
        )
    if not (set(new) - set(kept)) and not grew:
        raise FileExistsError(
            f"같은 실행의 기록 미완이 이미 보관됨(더 담긴 복사본이 아님): {old['run_id']}"
        )
    return differs


def merge(
    root: Path, case_id: str, result_dir: Path, now: Optional[datetime] = None
) -> Path:
    """대조가 다 맞을 때만 맥북 사례에 한 번 보관 · 반환 보관 폴더."""
    t0, m0 = now or kst_now(), time.monotonic()
    base = real_root(root)
    v = verify(base, case_id, result_dir)
    res = v["result"]
    bid, rid = res["bundle_id"], res["run_id"]
    runs = merged_runs(base, case_id, every=True)
    replaces = _order(base, case_id, bid, v, runs)
    cdir = case_dir(base, case_id)
    differs = _check_replace(base, cdir, replaces, v) if replaces is not None else []
    others = [
        r
        for r in merged_runs(base, case_id)
        if r.get("main_started") and r.get("run_id") != rid
    ]
    conflict = bool(v["main_started"] and others)
    if res["status"] != INCOMPLETE:
        rdir = f"{bid}__{rid}"
    else:
        k = sum(1 for r in runs if r.get("run_id") == rid)
        rdir = f"{bid}__{rid}__incomplete" + (str(k + 1) if k else "")
    env = res.get("env") or {}
    page = v["files"].get("one_page.html")
    record = {
        "case_id": case_id,
        "bundle_id": bid,
        "run_id": rid,
        "result_dir": v["name"],
        # 이 실행이 본 같은 묶음 앞 결과(실행 순서 · 벽시계 대신 · 검증자 r3 F12)
        "prior_runs": [
            p.get("run_id")
            for p in v.get("prior_results") or []
            if p.get("run_id") and p.get("bundle_id") == bid
        ],
        "record_dir": rdir,
        "replaces": replaces["record_dir"] if replaces else None,
        "kept_differs": differs,  # 대신 받은 기록 미완에서 바이트가 달랐던 파일(검증 못 한 보관본)
        "started_at": res.get("started_at"),
        "ended_at": res.get("ended_at"),
        "run_wall_s": res.get("run_wall_s"),
        "status": res.get("status"),
        # 무슨 멈춤이었는지(안내 중 중단 · 기록 미완이어도 · 검토 A) — 상태 글자 대신 이것으로 판단
        "stop_kind": res.get("stop") or res.get("status"),
        "claimed_status": v["checks"].get("claimed_status"),
        "main_started": v["main_started"],
        "has_output": v["has_output"],
        "main_status": v["checks"].get("main_status"),
        "has_main": v["checks"].get("main_status") is not None,
        "attempt_conflict": conflict,
        "other_main_attempts": (
            [
                {"run_id": r.get("run_id"), "started_at": r.get("started_at")}
                for r in others
            ]
            if conflict
            else []
        ),
        "trial_categories": ((res.get("trial") or {}).get("gate") or {}).get(
            "categories"
        ),
        "pre_main_categories": (res.get("pre_main") or {}).get("categories"),
        "env_gate_categories": (res.get("env_gate") or {}).get("categories"),
        "one_page_sha256": store.sha256_bytes(page) if page is not None else None,
        "ollama_version": env.get("ollama_version"),
        "model_digest": (env.get("model") or {}).get("digest"),
        "checks": v["checks"],
        "dev_started_at": iso(t0),
    }
    files = {k: b for k, b in v["files"].items() if b is not None}
    record["dev_ms"] = round((time.monotonic() - m0) * 1000)
    files["merge.json"] = dumps(record)
    return publish_dir(base, inside(base, cdir / "runs", make=True), rdir, files)
