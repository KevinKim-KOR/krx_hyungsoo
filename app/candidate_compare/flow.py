"""prepare(잠금 · 성과 계산 0) · run(공식 1회) — PLAN §4 '예산' · 판정 §3.

```text
prepare  봉인 확인 → 주 기록(전체 후보 · 공통 후보군 · 두 기준 선정) → 분모 대조(PLAN §1-4)
         → 자리 판정 수(편입 · 청산 가능 여부 · 가격 · 수익률 없음) → 잠금(설정 · 코드 해시 · 환경 · 주 기록 해시)
         잠금이 이미 있으면 거부 · 정정 잠금 = 사유 + 앞 잠금에 실행이 있음 + 코드 해시가 바뀜(코드 결함만)
run      잠금 하나(가장 최근) · 그 잠금의 실행 0 · 코드 해시 · 환경 · 설정이 잠금과 같음 → 아니면 기록 없이 거부
         주 기록 해시 대조 → 평가 · 지표 · 판정 → weeks.json · report.json · report.md → run.json(OK · 파일 해시)
         실행 id 를 만든 뒤 오류 = run.json(FAILED) — 그 잠금으로 다시 실행하지 않는다(정정 잠금 필요)
쓰기     모두 entry_timing.protocol.write_once(연구 폴더 안 실제 폴더 · 새 파일만 · 원자적)
```
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from app.candidate_compare import population as PO
from app.candidate_compare import report as RP
from app.candidate_compare import study as ST
from app.candidate_compare.protocol import (
    PROTOCOL_ID,
    SCHEMA,
    CheckRequired,
    Config,
    code_hashes,
    env,
    recipe,
)
from app.entry_timing.protocol import (
    RUN_ID,
    dumps,
    inside,
    new_id,
    read_json_inside,
    real_root,
    write_once,
)
from app.ml_evidence import store


def roundtrip(obj: Any) -> Any:
    """잠금 파일과 같은 모양(JSON 왕복 · 튜플 → 리스트)으로 맞춘다."""
    return json.loads(dumps(obj))


@contextlib.contextmanager
def run_lock(root: Path) -> Iterator[Path]:
    """같은 연구 폴더에서 한 번에 한 실행(파일 잠금) · 확인한 실제 경로를 돌려준다."""
    base = real_root(root)
    fd = os.open(base / ".run.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise CheckRequired("다른 실행이 진행 중") from e
        yield base
    finally:
        os.close(fd)


def _dirs(root: Path, parent: Path) -> list[Path]:
    if not parent.exists():
        return []
    inside(root, parent)
    return sorted(
        p
        for p in parent.iterdir()
        if RUN_ID.fullmatch(p.name) and not p.is_symlink() and p.is_dir()
    )


def locks(root: Path) -> list[tuple[Path, dict]]:
    out = []
    for d in _dirs(root, root / "locks"):
        f = d / "lock.json"
        if f.exists():
            out.append((d, read_json_inside(root, f)))
    return out


def runs(root: Path, lock_dir: Path) -> list[Path]:
    return _dirs(root, lock_dir / "runs")


def run_status(root: Path, run_dir: Path) -> str:
    """실행 폴더 상태 — run.json 의 status · 없으면 STARTED(시작 표지만 · 실행 미완)."""
    f = run_dir / "run.json"
    if not f.exists():
        return "STARTED"
    return str(read_json_inside(root, f).get("status"))


def slot_counts(data: PO.Data, weeks: list[dict]) -> dict[str, dict[str, Any]]:
    """자리 판정 수(가격 · 수익률 없이) — 편입 OK · 현금 · 미확인 · 청산 미확인 · 기본 평가 불가 주."""
    pos = {d: i for i, d in enumerate(data.axis)}
    out: dict[str, dict[str, Any]] = {}
    for w in weeks:
        c = out.setdefault(
            w["span"],
            {
                "assigned": 0,
                "entry_ok": 0,
                "cash": 0,
                "entry_unknown": 0,
                "exit_unknown": 0,
                "weeks_with_unknown": 0,
            },
        )
        if w["status"] != "OK":
            continue
        e1, e2 = pos[w["entry"]], pos[w["exit"]]
        bad = False
        for code in w["a"] + w["b"]:
            s = ST.slot(data, code, e1, e2)
            c["assigned"] += 1
            c["entry_ok"] += int(s["entry"] == ST.ENTRY_OK)
            c["cash"] += int(s["entry"] == ST.ENTRY_CASH)
            c["entry_unknown"] += int(s["entry"] == ST.ENTRY_UNKNOWN)
            c["exit_unknown"] += int(s["exit"] == ST.EXIT_UNKNOWN)
            bad = bad or ST.unknown(s)
        c["weeks_with_unknown"] += int(bad)
    return out


def build_inputs(cfg: Config) -> tuple[PO.Data, list[dict], dict, dict]:
    data = PO.load(cfg)
    weeks = PO.build_weeks(data, cfg)
    cnt = PO.counts(weeks, cfg.spans)
    PO.check_expected(cnt, cfg.expected)
    return data, weeks, cnt, slot_counts(data, weeks)


def prepare(
    cfg: Config, now: datetime, correction_reason: Optional[str] = None
) -> dict:
    with run_lock(cfg.root) as root:
        have = locks(root)
        prev = have[-1] if have else None
        if prev is not None:
            if not correction_reason:
                raise CheckRequired(
                    "잠금이 이미 있음 — 정정 잠금은 사유(코드 결함)가 필요"
                )
            changed = prev[1]["code_hashes"] != code_hashes(cfg.repo)
            failed = any(run_status(root, r) != "OK" for r in runs(root, prev[0]))
            if not (changed or failed):
                raise CheckRequired(
                    "코드가 바뀌지 않았고 앞 실행도 실패가 아님 — 정정 잠금은 코드 결함 정정 · 실패 실행에만"
                )
        data, weeks, cnt, slots = build_inputs(cfg)
        lock_id = new_id(now)
        lock = {
            "schema": SCHEMA["lock"],
            "protocol": PROTOCOL_ID,
            "lock_id": lock_id,
            "created_at": now.isoformat(timespec="seconds"),
            "recipe": recipe(cfg),
            "seal": data.panel.seal,
            "code_hashes": code_hashes(cfg.repo),
            "env": env(),
            "counts": cnt,
            "slot_counts": slots,
            "weeks_sha256": store.sha256_bytes(dumps(weeks)),
            "correction_reason": correction_reason,
            "previous_lock": prev[1]["lock_id"] if prev else None,
        }
        write_once(root, root / "locks" / lock_id / "lock.json", dumps(lock))
        return lock


def _failed(
    root: Path, run_dir: Path, run_id: str, lock_id: str, now: datetime, err: Exception
) -> None:
    with contextlib.suppress(Exception):
        write_once(
            root,
            run_dir / "run.json",
            dumps(
                {
                    "schema": SCHEMA["run"],
                    "status": "FAILED",
                    "run_id": run_id,
                    "lock_id": lock_id,
                    "error": f"{type(err).__name__}: {err}"[:500],
                    "at": now.isoformat(timespec="seconds"),
                }
            ),
        )


def run(cfg: Config, now: datetime) -> dict:
    with run_lock(cfg.root) as root:
        have = locks(root)
        if not have:
            raise CheckRequired("잠금이 없음 — prepare 먼저")
        lock_dir, lock = have[-1]
        if runs(root, lock_dir):
            raise CheckRequired(
                "이 잠금으로 이미 실행함 — 다시 실행은 정정 잠금(코드 결함)으로만"
            )
        if lock["code_hashes"] != code_hashes(cfg.repo):
            raise CheckRequired("코드 해시가 잠금과 다름")
        if lock["env"] != env():
            raise CheckRequired("실행 환경(python · numpy)이 잠금과 다름")
        if lock["recipe"] != roundtrip(recipe(cfg)):
            raise CheckRequired("설정이 잠금과 다름")
        # 결과 계산 전 확인 — 여기서 멈추면 기록을 남기지 않는다(잠금은 그대로)
        data, weeks, cnt, slots = build_inputs(cfg)
        if store.sha256_bytes(dumps(weeks)) != lock["weeks_sha256"]:
            raise CheckRequired("주 기록이 잠금과 다름")
        if roundtrip(cnt) != lock["counts"] or roundtrip(slots) != lock["slot_counts"]:
            raise CheckRequired("분모 · 자리 판정 수가 잠금과 다름")
        run_id = new_id(now)
        run_dir = lock_dir / "runs" / run_id
        # 결과 계산 직전 표지 — 이것이 있으면 이 잠금은 쓰인 것(실패 기록을 못 남겨도 다시 실행 거부)
        write_once(
            root,
            run_dir / "started.json",
            dumps(
                {
                    "run_id": run_id,
                    "lock_id": lock["lock_id"],
                    "at": now.isoformat(timespec="seconds"),
                }
            ),
        )
        try:
            ev = ST.evaluate(data, weeks, cfg)
            verdict = ST.judge(ev["main"], ev["alt"], cfg)
            rep = {
                "schema": SCHEMA["report"],
                "protocol": PROTOCOL_ID,
                "lock_id": lock["lock_id"],
                "run_id": run_id,
                "verdict": verdict,
                "main": ev["main"],
                "alt": ev["alt"],
                "cost40": ev["cost40"],
                "aux": ev["aux"],
                "counts": cnt,
                "slot_counts": slots,
                "worked_case": ST.worked_case(data, weeks, ev["rows"]),
                "seal": data.panel.seal,
            }
            files = {
                "weeks.json": dumps({"weeks": weeks, "rows": ev["rows"]}),
                "report.json": dumps(rep),
                "report.md": RP.render(rep).encode("utf-8"),
            }
            hashes = {
                name: write_once(root, run_dir / name, b) for name, b in files.items()
            }
            write_once(
                root,
                run_dir / "run.json",
                dumps(
                    {
                        "schema": SCHEMA["run"],
                        "status": "OK",
                        "run_id": run_id,
                        "lock_id": lock["lock_id"],
                        "files": hashes,
                        "at": now.isoformat(timespec="seconds"),
                    }
                ),
            )
            return {
                "run_id": run_id,
                "lock_id": lock["lock_id"],
                "verdict": verdict,
                "dir": str(run_dir),
            }
        except BaseException as e:
            _failed(root, run_dir, run_id, lock["lock_id"], now, e)
            raise
