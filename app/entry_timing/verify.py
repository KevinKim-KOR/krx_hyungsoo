"""verify — 저장 산출물을 독립 경로(verify_calc · verify_records)로 다시 만들어 전부 대조한다(쓰기 = 기록 한 개).

```text
실행 기록 활성 잠금 runs 바로 아래 실제 실행 폴더 = 이 실행 하나(r2 F6 · r3 F9 · r4 F11 · 심볼릭 링크 거부)
         폴더 파일 = 정해진 5개 + 프로그램 임시 이름만
         완료 기록 = 이름이 붙은 뒤 잰 완료 경과 ≤ 예산 · run.json 해시(r3 F7)
         run.json 칸 = 정해진 칸 · id · 잠금 · 상태 · 예산 = 잠금 ·
         경과 = 0 이상 실제 숫자 ≤ 예산(r2 F5) · 판정 = 다시 계산 · 필수 파일 3개 해시 전부(검증자 r1 F1)
잠금     설정(recipe) = 지금 설정 · 기대값 = 고정 기대값 · 분모 전체 = 다시 센 분모 · 주 기록 해시 · 분류표 해시 = 다시 만든 값
입력     봉인 확인(전후) = 잠금 봉인 · 기본정보 CSV 해시 · 분류표(봉인 판 전체 지수명) · 기대 수
주 기록   뼈대(신호 · D' · D+1 · D'+1 · 간격 · 구간 · 하위 기간)부터 다시 만든 주 기록 전체 = weeks.json(분모 갈래 포함 · F2)
보고     다시 만든 보고 전체(결과 · 분모 · 구간 · 상태 · id) = report.json · 그 보고로 다시 쓴 글 = report.md(바이트)
POC6     weekly_selection.data.build_panel 의 O* · 체결 가능 · 구간을 쓴 칸(옮김 민감도 칸 포함)마다 대조
실패     어떤 중단이든 FAILED 기록 · MISMATCH · FAILED = 결과서에서 판정 D(실행 · 검산 불성립)
기록 자리 활성 잠금 verify/ = 연구 폴더 아래 실제 폴더일 때만 기록(검증자 r5 F12) · 확인은 대조 전 · 쓰기 직전 두 번
         연구 폴더 · 잠금 · verify/ 가 실제 경로가 아니면 아무것도 쓰지 않고 CheckRequired(기록 없는 거부)
```
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app import krx_sealed_reader as K
from app.entry_timing import classify as CL
from app.entry_timing import flow as FW
from app.entry_timing import report as RP
from app.entry_timing import study as ST
from app.entry_timing import verify_calc as VC
from app.entry_timing import verify_records as VRR
from app.entry_timing import weekly as WK
from app.entry_timing.protocol import (
    BENCH,
    RUN_DIR_FILES,
    RUN_FILES,
    RUN_ID,
    SCHEMA,
    TMP_NAME,
    SHIFT_MAX,
    STATES,
    VARIANTS,
    CheckRequired,
    Config,
    code_hashes,
    dumps,
    inside,
    new_id,
    read_inside,
    recipe,
    regular_inside,
    write_once,
)
from app.ml_evidence import store

TOL = 1e-12
SEAL_KEYS = ("file_sha256", "content_sha256", "member_dates", "first_date", "last_date")
RUN_KEYS = {
    "schema",
    "run_id",
    "lock_id",
    "status",
    "created_at",
    "elapsed_s",
    "budget_s",
    "judgment",
    "manifest",
}


def diff(a: Any, b: Any, path: str = "") -> list[str]:
    """구조 전체 대조(실수 = 허용 1e-12 · 나머지 = 같음) — 다른 곳 경로 목록."""
    if isinstance(a, bool) or isinstance(b, bool):
        return [] if a == b and type(a) is type(b) else [path]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if abs(float(a) - float(b)) <= TOL else [path]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}{{keys}}"]
        out: list[str] = []
        for k in sorted(a):
            out += diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [f"{path}[len]"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path]


def verify(cfg: Config, now: datetime, run_id: Optional[str] = None) -> dict:
    with FW.run_lock(cfg.root) as root:
        lock_dir, proto = FW.active_lock(root)
        # runs = 실제 폴더를 확인한 뒤 이름만 읽음(링크 너머 목록을 보지 않음 · r6 F13)
        names = FW._runs(root, lock_dir)
        if not names:
            raise CheckRequired("실행 기록이 없다")
        if run_id is not None and (
            Path(run_id).name != run_id or run_id in ("", ".", "..")
        ):
            raise CheckRequired(
                f"실행 id 는 활성 잠금 runs 바로 아래 이름만(r3 F9): {run_id!r}"
            )
        name = names[-1] if run_id is None else run_id
        if name not in names:
            raise CheckRequired(f"실행 기록이 없다: {name}")
        run_dir = lock_dir / "runs" / name
        # 기록 자리 = 연구 폴더 아래 실제 폴더(대조 전 · r5 F12) — 아니면 기록 없이 거부
        vdir = inside(root, lock_dir / "verify", make=True)
        vid = new_id(now)
        target = vdir / f"{run_dir.name}_{vid}.json"
        try:
            record = _verify(cfg, now, proto, root, lock_dir, run_dir, names, vid)
        except BaseException as e:  # 어떤 중단이든 기록(안전한 자리일 때만)
            failed = {
                "schema": SCHEMA["verify"],
                "verify_id": vid,
                "run_id": run_dir.name,
                "lock_id": proto["lock_id"],
                "created_at": now.isoformat(),
                "status": "FAILED",
                "error": f"{type(e).__name__}: {e}"[:500],
            }
            try:
                write_once(root, target, dumps(failed))
            except (OSError, CheckRequired):  # 기록 실패가 원래 오류를 가리지 않게
                pass
            raise
        write_once(root, target, dumps(record))  # 쓰기 직전 자리 다시 확인
        return record


def _lock_expected_ok(cfg: Config, proto: dict) -> bool:
    want = None if cfg.expected is None else FW.roundtrip(cfg.expected)
    if proto.get("expected") != want:
        return False
    try:
        FW.check_expected(proto["counts"], proto.get("expected"))
    except CheckRequired:
        return False
    return True


def _paths_real(root: Path, run_dir: Path) -> tuple[bool, Any]:
    """실행 폴더가 연구 폴더 아래 실제 폴더(r4 F11 · runs 바로 아래 이름은 실행 id 검사 r3 F9).

    쓰기와 같은 규칙(protocol.inside · 링크를 따라가지 않음). 연구 폴더 · 잠금 · protocol.json · runs 는
    run_lock · FW.locks · FW._runs 가 읽기 전에 거부한다(r5 F12 · r6 F13).
    """
    try:
        inside(root, run_dir)
        return True, {"run": True}
    except CheckRequired:
        return False, {"run": False}


def _real_dir(p: Path) -> bool:
    return not p.is_symlink() and p.is_dir()  # 링크면 따라가지 않고 거짓


def _run_dir_files(root: Path, run_dir: Path) -> tuple[bool, Any]:
    """실행 폴더 = 정해진 5개 + 프로그램 임시 이름(이름 전체 대조)만 · 모두 보통 파일 · 하드 링크가 폴더 안.

    실제 폴더로 확인된 실행 폴더에서만 부른다(r3 F7 · F9 · r4 F11 · r6 F13).
    """
    names = sorted(os.listdir(run_dir))
    listed = [n for n in names if not n.startswith(".")]
    hidden = [n for n in names if n.startswith(".")]
    ok = listed == sorted(RUN_DIR_FILES)
    for n in names:
        tmp = TMP_NAME.fullmatch(n)
        if n.startswith(".") and not tmp:
            ok = False
            continue
        try:
            regular_inside(root, run_dir / n, tmp.group(1) if tmp else None)
        except (OSError, CheckRequired):
            ok = False
    return ok, {"files": listed, "hidden": hidden}


def _read(root: Path, path: Path) -> Optional[bytes]:
    """확인을 통과한 파일만 읽는다 · 없거나 확인 실패면 None(읽지 않음 · r6 F13)."""
    try:
        return read_inside(root, path)
    except (FileNotFoundError, CheckRequired):
        return None


def _completed_ok(
    blob: Optional[bytes], run_blob: bytes, run_dir: Path, run: dict, proto: dict
) -> tuple[bool, Any]:
    """완료 기록 = 이름이 붙은 뒤 잰 완료 경과 ≤ 예산 · run.json 해시 · id(검증자 r3 F7)."""
    if blob is None:
        return False, {"completed": "없음 또는 확인 실패(읽지 않음)"}
    try:
        c = json.loads(blob.decode("utf-8"))
    except ValueError as e:
        return False, {"completed": f"읽을 수 없음 {type(e).__name__}"}
    if not isinstance(c, dict):
        return False, {"completed": "모양이 다름"}
    done, elapsed = c.get("done_elapsed_s"), run.get("elapsed_s")
    keys = {
        "schema",
        "run_id",
        "lock_id",
        "done_elapsed_s",
        "budget_s",
        "run_json_sha256",
    }
    ok = (
        set(c) == keys
        and c["schema"] == SCHEMA["completed"]
        and c["run_id"] == run_dir.name
        and c["lock_id"] == proto["lock_id"]
        and c["budget_s"] == proto["recipe"]["budget_s"]
        and c["run_json_sha256"] == store.sha256_bytes(run_blob)
        and isinstance(done, (int, float))
        and not isinstance(done, bool)
        and math.isfinite(done)
        and isinstance(elapsed, (int, float))
        and not isinstance(elapsed, bool)
        and elapsed <= done <= proto["recipe"]["budget_s"]
    )
    return ok, {"done_elapsed_s": repr(done)}


def _record(proto: dict, run_dir: Path, vid: str, now: datetime, checks: list) -> dict:
    ok = all(c["ok"] for c in checks)
    return {
        "schema": SCHEMA["verify"],
        "verify_id": vid,
        "run_id": run_dir.name,
        "lock_id": proto["lock_id"],
        "created_at": now.isoformat(),
        "status": "VERIFIED_OK" if ok else "MISMATCH",
        "checks": checks,
    }


def _verify(
    cfg: Config,
    now: datetime,
    proto: dict,
    root: Path,
    lock_dir: Path,
    run_dir: Path,
    names: list[str],
    vid: str,
) -> dict:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    lock_recipe = proto["recipe"]
    runs_dir = lock_dir / "runs"
    check(
        "single_run_in_lock",  # 잠금당 공식 실행 1회 · 항목 전부 실제 폴더(PLAN §4 · §5 · r2 F6 · r4 F11)
        # 실행 id 꼴 이름만(앞 실행 판정과 같은 규칙 · r6 검토)
        names == [run_dir.name]
        and bool(RUN_ID.fullmatch(run_dir.name))
        and all(_real_dir(runs_dir / n) for n in names),
        {"runs": names},
    )
    path_ok, path_detail = _paths_real(root, run_dir)
    check("paths_real", path_ok, path_detail)
    # 실행 폴더 위치를 확인 못 함 → 목록 · 내용을 읽지 않고 불일치(r6 F13)
    if not path_ok:
        return _record(proto, run_dir, vid, now, checks)
    check("run_dir_files", *_run_dir_files(root, run_dir))
    # 확인을 통과한 파일만 읽는다(링크 · 밖 하드 링크 · 없는 파일 = None · 내용을 읽지 않음)
    blobs = {k: _read(root, run_dir / k) for k in RUN_DIR_FILES}
    if blobs["run.json"] is None:
        check("run_record", False, {"run.json": "없음 또는 확인 실패(읽지 않음)"})
        return _record(proto, run_dir, vid, now, checks)
    run = json.loads(blobs["run.json"].decode("utf-8"))
    if run.get("status") != "OK":
        raise CheckRequired(f"실행 상태 {run.get('status')} — 검산 대상 아님")
    check(
        "run_completed",
        *_completed_ok(blobs["completed.json"], blobs["run.json"], run_dir, run, proto),
    )
    man = run.get("manifest") or {}
    files = {
        k: None if blobs[k] is None else store.sha256_bytes(blobs[k]) for k in RUN_FILES
    }
    check(
        "run_manifest_complete",
        set(man) == set(RUN_FILES) and all(files[k] == man.get(k) for k in RUN_FILES),
        {"manifest": sorted(man)},
    )
    check(
        "run_record",
        set(run) == RUN_KEYS
        and run["schema"] == SCHEMA["run"]
        and run["run_id"] == run_dir.name
        and run["lock_id"] == proto["lock_id"]
        and run["budget_s"] == lock_recipe["budget_s"],
    )
    elapsed = run.get("elapsed_s")
    check(
        "elapsed_within_budget",  # 실제 숫자 · 0 이상 · 유한 · 예산 이하(검증자 r2 F5)
        isinstance(elapsed, (int, float))
        and not isinstance(elapsed, bool)
        and math.isfinite(elapsed)
        and 0 <= elapsed <= lock_recipe["budget_s"],
        {"elapsed_s": repr(elapsed)},  # inf · NaN 도 기록할 수 있게 글자로
    )
    check("code_hashes_match_lock", code_hashes(cfg.repo) == proto["code"])
    check("lock_recipe", lock_recipe == FW.roundtrip(recipe(cfg)))
    check("lock_expected", _lock_expected_ok(cfg, proto))
    before = K.verify_sealed_source(
        cfg.db, version_id=cfg.version, expected_content_sha256=cfg.content_sha
    )
    check(
        "seal_matches_lock",
        {k: before[k] for k in SEAL_KEYS} == proto["inputs"]["seal"]
        and str(cfg.db) == proto["inputs"]["db"]
        and cfg.version == proto["inputs"]["version"],
    )
    check(
        "csv_matches_lock",
        store.sha256_file(Path(cfg.csv_path)) == proto["inputs"]["csv_sha256"]
        and str(cfg.csv_path) == proto["inputs"]["csv_path"],
    )
    dictionary = CL.load_dictionary(Path(cfg.csv_path))
    src = VC.Source(cfg)
    K.assert_same_source(
        before,
        K.verify_sealed_source(
            cfg.db, version_id=cfg.version, expected_content_sha256=cfg.content_sha
        ),
    )
    names = {x[5] for x in src.raw.values() if x[5]}
    table = {
        n: list(CL.label(n, dictionary)) for n in sorted(names) if n not in dictionary
    }
    check(
        "classification_table",
        not diff(table, proto["classification"])
        and store.sha256_bytes(dumps(table))
        == proto["inputs"]["classification_sha256"],
    )
    tc = WK.table_counts(table)
    exp = (proto.get("expected") or {}).get("classification")
    check("classification_counts", not exp or tc == exp)
    wks = VC.weeks(src, cfg, dictionary)
    check("weeks_count", len(wks) == proto["weeks_n"])
    check(
        "lock_weeks_sha",
        store.sha256_bytes(dumps(wks)) == proto["inputs"]["weeks_sha256"],
    )
    cnt = FW.roundtrip(VRR.counts(src, wks, cfg.spans, tc))
    cd = diff(cnt, proto["counts"], "counts")
    check("lock_counts", not cd, cd[:10])
    res, rows = VC.evaluate(src, wks, cfg, ST.METHOD)
    recs = FW.roundtrip(VRR.records(wks, rows))
    stored_weeks = blobs["weeks.json"]
    wd = (
        ["weeks.json 읽지 않음"]
        if stored_weeks is None
        else diff(recs, json.loads(stored_weeks.decode("utf-8")), "weeks")
    )
    check("weeks_recomputed", not wd, wd[:10])
    expected_rep = FW.roundtrip(
        {
            "schema": SCHEMA["report"],
            "run_id": run_dir.name,
            "lock_id": proto["lock_id"],
            "result": res,
            "counts": cnt,
            "spans": cfg.spans,
            "states": STATES,
        }
    )
    stored = (
        {}
        if blobs["report.json"] is None
        else json.loads(blobs["report.json"].decode("utf-8"))
    )
    rd = diff(expected_rep, stored, "report")
    check("report_json_recomputed", not rd, rd[:10])
    status = expected_rep["result"]["judgment"]["status"]
    check(
        "judgment",
        status == stored.get("result", {}).get("judgment", {}).get("status")
        and status == run.get("judgment"),
        {"recomputed": status},
    )
    md = RP.markdown(expected_rep).encode("utf-8")
    check("report_md_rendered", md == blobs["report.md"])
    if cfg.cross_check_poc6:
        check("poc6_build_panel_cells", *_poc6_cells(cfg, src, wks, rows["MAIN"]))
    return _record(proto, run_dir, vid, now, checks)


def _poc6_cells(
    cfg: Config, src: VC.Source, wks: list[dict], main_rows: list[dict]
) -> tuple[bool, Any]:
    """POC6 build_panel(LightGBM · torch 를 올림)과 쓴 칸의 O* · 체결 가능 · 구간 대조.

    칸 = 모든 주의 후보 · 069500 의 D+1 · D'+1 + D'+1 체결 불가 짝의 옮김 민감도 칸(최대 5거래일).
    """
    from app.weekly_selection import data as P6

    p6 = P6.build_panel(Path(cfg.db), cfg.version, cfg.content_sha)
    ci, pos = p6.ci, {d: i for i, d in enumerate(p6.axis)}
    cells = set()
    for w in wks:
        codes = {BENCH} | {
            c for v in VARIANTS for _, c, _ in w["variants"][v]["candidates"]
        }
        cells |= {(c, d) for c in codes for d in (w["e1"], w["e2"])}
    for r, w in zip(main_rows, wks):
        for _rank, code, why, _nx in r["excluded_pairs"]:
            if why == "NOT_EXEC_E2":
                i2 = src.pos[w["e2"]]
                last = min(i2 + SHIFT_MAX, len(src.axis) - 1)
                cells |= {(code, src.axis[i]) for i in range(i2 + 1, last + 1)}
    bad = []
    for code, d in sorted(cells):
        o, x = src.o_star_exec(code, d)
        j, i = ci[code], pos[d]
        o6 = float(p6.O[j, i]) if np.isfinite(p6.O[j, i]) else None
        s6 = int(p6.seg[j, i]) if p6.has_row[j, i] else None
        if o != o6 or x != bool(p6.exec_ok[j, i]) or src.seg(code, d) != s6:
            bad.append([code, d])
    return not bad, {"cells": len(cells), "mismatch": bad[:10]}
