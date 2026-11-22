"""prepare(잠금 · 성과 계산 0) · run(공식 1회) — PLAN §5 · 판정 §2(잠근 뒤 공식 실행 한 번).

```text
prepare  입력 해시(봉인 파일 · 내용 · 기본정보 CSV) → 판 → 주 기록 → 분모 · 분류표(PLAN §1-4 · §2-1 기대값과 대조)
         → 체결 가능 짝 · 평가 가능 주 · 주 기록 해시(결정 포함) · 분류표를 잠금에 적는다 · 성과 · 판정 계산 없음
         정정 잠금(코드 결함만) = 사유 + 앞 잠금에 실행이 있고 코드 · 환경이 바뀜 + 입력 · 설정 · 분모 · 주 기록 같음
run      실행 id 전: 잠금 하나 · 그 잠금의 실행 0 · 코드 해시 · 환경 · 설정이 잠금과 같음(아니면 기록 없이 거부)
         실행 id 뒤: 입력 · 봉인 · 분모 · 분류표 · 주 기록 해시 대조 → 모든 계산(지표 · 부트스트랩 · 판정 · 기록 · 글)
         → 결과 파일 3개 쓰기(해시 다시 대조) → run.json(OK) 임시 파일까지 다 쓰고 fsync → 예산 판정(넘으면 FAILED)
         → 이름 붙이기 = 실행 완료 → 링크 직후 · 정리 전에 잰 완료 경과로 예산 다시 판정(검증자 r3 F7 · r4 F10)
           · 이하 → completed.json(완료 경과 · run.json 해시) · 넘음 → budget_exceeded.json + 오류
         실행 성립 = run.json(OK) + completed.json(완료 경과 ≤ 예산) + 초과 표시 없음. completed.json 이 없거나
         쓰다 멈추면 성립하지 않는다(닫힌 쪽으로 실패 · 검산이 거부) · completed.json 쓰기는 완료 뒤 기록이다
         모든 중단(예외 · Ctrl-C) = FAILED 기록(원자 쓰기라 조각이 남지 않음 · 검증자 r1 F4) · 다시 실행 거부
위치     연구 폴더(자신 · 상위) = 심볼릭 링크 · '..' 없는 실제 경로 · 확인한 그 경로 하나로 모든 읽기 · 쓰기
         그 아래 잠금(사슬 전체) · protocol.json · runs · 실행 · .run.lock 도 링크 거부(검증자 r5 F12)
         모든 쓰기는 protocol.write_once · stage_once · link_name 이 쓰기 직전에 다시 확인 · 어긋나면 쓰지 않고 거부
         (FAILED 기록도 안전한 자리가 확인될 때만 · 아니면 기록 없이 원래 오류)
         정정 잠금의 '앞 실행' = 실행 id 꼴 이름 · 실제 폴더 · run.json 보통 파일만
```
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import stat
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from app.entry_timing import classify as CL
from app.entry_timing import data as DA
from app.entry_timing import report as RP
from app.entry_timing import study as ST
from app.entry_timing import weekly as WK
from app.entry_timing.protocol import (
    PROTOCOL_ID,
    RUN_ID,
    SCHEMA,
    STATES,
    Busy,
    CheckRequired,
    Config,
    code_hashes,
    discard,
    dumps,
    env,
    inside,
    link_name,
    new_id,
    read_json_inside,
    real_root,
    regular_inside,
    recipe,
    stage_once,
    write_once,
)
from app.ml_evidence import store

LOCK_NAME = ".run.lock"


@contextlib.contextmanager
def run_lock(root: Path) -> Iterator[Path]:
    """연구 폴더 잠금 · 돌려주는 값 = 확인한 연구 폴더(모든 읽기 · 쓰기의 바탕 · r5 F12 · r5 검토).

    잠금 파일도 다른 파일과 같은 규칙(보통 파일 · 링크 아님 · 하드 링크가 폴더 안)을 연 앞에 확인한다.
    링크를 따라가지 않고 막히지 않게 열고(FIFO 대기 없음), 연 파일을 다시 확인한 뒤 잠근다(r6 검토).
    """
    base = real_root(root)
    lock_file = base / LOCK_NAME
    bad = (
        f"잠금 파일이 보통 파일이 아님(링크 · FIFO · 폴더 · 밖 하드 링크): {LOCK_NAME}"
    )
    if _present(lock_file):
        try:
            regular_inside(base, lock_file)
        except CheckRequired:
            raise CheckRequired(bad) from None
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(lock_file, flags, 0o644)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise CheckRequired(bad)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("같은 연구 폴더에서 다른 실행이 진행 중") from None
        yield base
    finally:
        os.close(fd)  # 닫으면 잠금이 풀린다


def _present(p: Path) -> bool:
    """이름이 있는가(링크를 따라가지 않음) · 없음만 거짓 · 권한 등으로 못 보면 거부(없음과 구분 · r6 검토)."""
    try:
        os.lstat(p)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        raise CheckRequired(f"확인할 수 없음({type(e).__name__}): {p.name}") from e


def roundtrip(obj: Any) -> Any:
    """잠금 파일과 같은 모양(JSON 왕복)으로 비교한다."""
    return json.loads(dumps(obj).decode("utf-8"))


def locks(root: Path) -> list[tuple[Path, dict]]:
    """잠금 사슬 순서(첫 잠금 → 그것을 정정한 잠금 → …). 폴더 이름 순서는 쓰지 않는다
    (같은 초에 만든 잠금은 이름 뒤 무작위 글자로 순서가 뒤바뀔 수 있다)."""
    found: dict[str, tuple[Path, dict]] = {}
    base = real_root(root)
    for e in sorted(base.iterdir()):
        # 연구 폴더 안 링크는 따라가지 않고 거부(r5 F12 · r6 F13) · 숨김 이름(.run.lock 등)은 잠금 아님
        if e.is_symlink():
            raise CheckRequired(f"연구 폴더 안 심볼릭 링크: {e.name}")
        p = e / "protocol.json"
        if e.name.startswith(".") or not e.is_dir() or not _present(p):
            continue
        try:
            # 잠금 폴더 = 실제 폴더 · protocol.json = 보통 파일(링크 · 밖 하드 링크 거부) 확인 뒤에만 읽음
            proto = read_json_inside(base, p)
            lid = proto["lock_id"]
        except (OSError, ValueError, KeyError, TypeError) as err:
            raise CheckRequired(f"잠금 파일을 읽을 수 없음: {e.name}") from err
        corr = proto.get("corrects")
        if corr is not None and not (
            isinstance(corr, dict) and isinstance(corr.get("lock_id"), str)
        ):
            raise CheckRequired(f"잠금의 정정 칸 모양이 다름: {p.parent.name}")
        if p.parent.name != lid or lid in found:
            raise CheckRequired(f"잠금 폴더 이름 ≠ lock_id 또는 중복: {p.parent.name}")
        found[lid] = (p.parent, proto)
    if not found:
        return []
    by_prev: dict = {}
    for lid, (_, proto) in found.items():
        prev = (proto.get("corrects") or {}).get("lock_id")
        if prev in by_prev or (prev is not None and prev not in found):
            raise CheckRequired(
                "잠금 사슬이 어긋남(같은 잠금을 둘이 정정 · 없는 잠금을 정정)"
            )
        by_prev[prev] = lid
    chain, cur = [], by_prev.get(None)
    while cur is not None:
        chain.append(found[cur])
        cur = by_prev.get(cur)
    if len(chain) != len(found):
        raise CheckRequired("잠금 사슬이 어긋남(사슬 밖 잠금)")
    return chain


def active_lock(root: Path) -> tuple[Path, dict]:
    found = locks(root)
    if not found:
        raise CheckRequired("잠금이 없다 — prepare 먼저")
    return found[-1]


def _runs(root: Path, lock_dir: Path) -> list[str]:
    d = lock_dir / "runs"
    if not _present(d):  # 이름만 본다(링크를 따라가지 않음)
        return []
    inside(root, d)  # runs = 실제 폴더(r5 F12)
    return sorted(p.name for p in d.iterdir())


def _is_run(root: Path, d: Path) -> bool:
    """공식 실행 폴더 = 실행 id 꼴 이름 · 실제 폴더 · run.json 보통 파일(정정 잠금의 '앞 실행' · r5 검토)."""
    if not RUN_ID.fullmatch(d.name):
        return False
    try:
        # 폴더 · 파일 모두 링크를 따라가지 않고 확인
        regular_inside(root, d / "run.json")
    except (OSError, CheckRequired):
        return False
    return True


def build_inputs(cfg: Config) -> dict[str, Any]:
    """판 · 주 기록 · 분모 · 분류표(prepare · run 이 같은 함수로 만든다)."""
    csv_sha = store.sha256_file(Path(cfg.csv_path))
    if cfg.csv_sha is not None and csv_sha != cfg.csv_sha:
        raise CheckRequired("기본정보 CSV 해시가 고정값과 다름")
    dictionary = CL.load_dictionary(Path(cfg.csv_path))
    panel = DA.load(cfg)
    weeks = WK.build(panel, dictionary, cfg)
    table = WK.classification_table(panel, dictionary)
    cnt = WK.counts(panel, weeks, cfg.spans)
    cnt["classification"] = WK.table_counts(table)
    meta = {
        "db": str(cfg.db),
        "version": cfg.version,
        "seal": panel.seal,
        "csv_path": str(cfg.csv_path),
        "csv_sha256": csv_sha,
        "weeks_sha256": store.sha256_bytes(dumps(weeks)),
        "classification_sha256": store.sha256_bytes(dumps(table)),
    }
    return {"panel": panel, "weeks": weeks, "counts": cnt, "table": table, "meta": meta}


def check_expected(cnt: dict, expected: dict | None) -> None:
    if not expected:
        return
    bad = []
    for span, exp in expected.items():
        for key, val in exp.items():
            got = cnt.get(span, {}).get(key)
            if got != val:
                bad.append(f"{span}.{key}: 기대 {val} · 실측 {got}")
    if bad:
        raise CheckRequired("분모가 PLAN §1-4 잠금 기대값과 다름 — " + " / ".join(bad))


def prepare(cfg: Config, now: datetime, correction_reason: str | None = None) -> dict:
    with run_lock(cfg.root) as root:
        found = locks(root)
        if found and not correction_reason:
            raise CheckRequired(
                "잠금이 이미 있다 — 코드 결함 정정만 --correction-reason 으로"
            )
        if correction_reason and not found:
            raise CheckRequired("첫 잠금에는 정정 사유를 쓰지 않는다")
        built = build_inputs(cfg)
        check_expected(built["counts"], cfg.expected)
        rec, code, environment = recipe(cfg), code_hashes(cfg.repo), env()
        corrects = None
        if found:
            prev_dir, prev = found[-1]
            # 앞 실행 = 실제 실행 폴더만(낯선 항목 · 링크 · .DS_Store 는 세지 않음)
            prior_runs = [
                n for n in _runs(root, prev_dir) if _is_run(root, prev_dir / "runs" / n)
            ]
            if not prior_runs:
                raise CheckRequired(
                    "정정 잠금은 앞 잠금의 실행이 있을 때만(결함이 드러난 뒤)"
                )
            changed = sorted(k for k in code if code[k] != prev["code"].get(k))
            if not changed and environment == prev["env"]:
                raise CheckRequired("정정 잠금인데 코드 · 환경이 앞 잠금과 같다")
            same = (
                prev["recipe"] == roundtrip(rec)
                and prev["counts"] == roundtrip(built["counts"])
                and prev["inputs"] == roundtrip(built["meta"])
            )
            if not same:
                raise CheckRequired(
                    "정정 잠금은 앞 잠금과 입력 · 설정 · 분모 · 주 기록이 같아야 함"
                )
            corrects = {
                "lock_id": prev["lock_id"],
                "reason": correction_reason,
                "changed_code": changed,
                "env_changed": environment != prev["env"],
                "prior_runs": prior_runs,
            }
        lock_id = new_id(now)
        proto = {
            "schema": SCHEMA["protocol"],
            "protocol_id": PROTOCOL_ID,
            "lock_id": lock_id,
            "created_at": now.isoformat(),
            "inputs": built["meta"],
            "recipe": rec,
            "expected": cfg.expected,
            "counts": built["counts"],
            "classification": built["table"],
            "weeks_n": len(built["weeks"]),
            "code": code,
            "env": environment,
            "corrects": corrects,
        }
        write_once(root, root / lock_id / "protocol.json", dumps(proto))
        return {"lock_id": lock_id, "counts": built["counts"], "corrects": corrects}


def _failed(
    root: Path, out: Path, proto: dict, run_id: str, now: datetime, e: BaseException
) -> None:
    try:  # 이미 있으면 FileExistsError(이름만 봄) · 자리가 안전하지 않으면 CheckRequired → 기록 없이 넘김
        write_once(
            root,
            out / "run.json",
            dumps(
                {
                    "schema": SCHEMA["run"],
                    "run_id": run_id,
                    "lock_id": proto["lock_id"],
                    "status": "FAILED",
                    "created_at": now.isoformat(),
                    "error": f"{type(e).__name__}: {e}"[:500],
                }
            ),
        )
    # 기록 쓰기 실패 · 안전한 자리 없음(r5 F12)이 원래 오류를 가리지 않게(r3 F8) — 다시 실행은 거부된다
    except (OSError, CheckRequired):
        pass


def run(cfg: Config, now: datetime) -> dict:
    t0 = time.monotonic()
    with run_lock(cfg.root) as root:
        lock_dir, proto = active_lock(root)
        # runs 위치 확인도 여기서(실행 id 전 · r5 F12)
        if _runs(root, lock_dir):
            raise CheckRequired(
                "이 잠금의 공식 실행이 이미 있다(1회) — 코드 결함이면 정정 잠금"
            )
        if code_hashes(cfg.repo) != proto["code"]:
            raise CheckRequired("코드 해시가 잠금과 다름(실행 전 거부)")
        if env() != proto["env"]:
            raise CheckRequired("환경이 잠금과 다름(실행 전 거부)")
        if roundtrip(recipe(cfg)) != proto["recipe"]:
            raise CheckRequired("설정(recipe)이 잠금과 다름(실행 전 거부)")
        run_id = new_id(now)
        out = lock_dir / "runs" / run_id
        tmp = None
        try:
            built = build_inputs(cfg)
            if roundtrip(built["meta"]) != proto["inputs"]:
                raise CheckRequired(
                    "입력(봉인 · CSV · 주 기록 · 분류표 해시)이 잠금과 다름"
                )
            if roundtrip(built["counts"]) != proto["counts"]:
                raise CheckRequired("분모가 잠금과 다름")
            ev = ST.evaluate(built["panel"], built["weeks"], cfg)
            rep = {
                "schema": SCHEMA["report"],
                "run_id": run_id,
                "lock_id": proto["lock_id"],
                "result": ev["result"],
                "counts": proto["counts"],
                "spans": cfg.spans,
                "states": STATES,
            }
            rep = roundtrip(
                rep
            )  # 저장 모양(JSON 키 = 문자열)으로 글을 쓴다 — verify 가 같은 모양에서 다시 쓴다
            payloads = {
                "weeks.json": dumps(RP.week_records(built["weeks"], ev["rows"])),
                "report.json": dumps(rep),
                "report.md": RP.markdown(rep).encode("utf-8"),
            }
            manifest = {k: store.sha256_bytes(v) for k, v in payloads.items()}
            for k, v in payloads.items():
                if write_once(root, out / k, v) != manifest[k]:
                    raise CheckRequired(f"쓴 파일 해시가 다름: {k}")
            elapsed = time.monotonic() - t0
            summary = dumps(
                {
                    "schema": SCHEMA["run"],
                    "run_id": run_id,
                    "lock_id": proto["lock_id"],
                    "status": "OK",
                    "created_at": now.isoformat(),
                    "elapsed_s": elapsed,
                    "budget_s": cfg.budget_s,
                    "judgment": ev["result"]["judgment"]["status"],
                    "manifest": manifest,
                }
            )
            result = json.loads(summary.decode("utf-8"))
            tmp = stage_once(root, out / "run.json", summary)
            # 결과 파일 · run.json 임시 파일까지 다 쓰고 fsync 한 뒤(r1 F3 · r2 F5 · POC6-20 F1 · F2)
            final = time.monotonic() - t0
            if final > cfg.budget_s:
                raise CheckRequired(
                    f"시간 예산 초과({final:.0f}s > {cfg.budget_s:.0f}s)"
                )
            link_name(root, tmp, out / "run.json")  # 이름이 붙는 순간 = 실행 완료
            # 링크 직후 · 임시 이름 정리 전에 잰 완료 경과(r3 F7 · r4 F10)
            done = time.monotonic() - t0
            discard(root, tmp)
            tmp = None
            record = {
                "run_id": run_id,
                "lock_id": proto["lock_id"],
                "done_elapsed_s": done,
                "budget_s": cfg.budget_s,
                "run_json_sha256": store.sha256_bytes(summary),
            }
            if done > cfg.budget_s:
                write_once(
                    root,
                    out / "budget_exceeded.json",
                    dumps({"schema": SCHEMA["budget_exceeded"], **record}),
                )
                raise CheckRequired(
                    f"시간 예산 초과(완료 {done:.0f}s > {cfg.budget_s:.0f}s)"
                )
            write_once(
                root,
                out / "completed.json",
                dumps({"schema": SCHEMA["completed"], **record}),
            )
            return result
        # Ctrl-C 포함 — 실행 id 를 정한 뒤의 모든 중단을 기록
        except BaseException as e:
            try:
                if tmp is not None:
                    # 판정 전 임시 run.json(OK)은 이름을 붙이지 않고 지운다
                    discard(root, tmp)
            finally:
                # 정리가 어떻게 끝나도 기록(r3 F8) · 안전한 자리일 때만(r5 F12)
                _failed(root, out, proto, run_id, now, e)
            raise
