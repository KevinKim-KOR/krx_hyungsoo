"""POC6-13 — tick(한 번 깨어날 때) · 06 자식 실행 · 작업 생애 유휴 절전 방지 · 시도 기록(PLAN §3-2).

```text
예측(A)  창 안 · 오늘 미완료 · 오늘 자동 예측 < 4 · 직전 예측에서 15분 → `run --pull`(20분 상한)
보관(B)  창 안 · 보관 대기 · 오늘 자동 보관 < 4 · (방금 예측 또는 직전 보관에서 15분) → `archive --upload`(10분)
         예측이 완료여도 보관 대기는 따로 처리한다(판정 §5-2). 15:20 뒤에는 둘 다 새로 시작하지 않는다.
정리     자식은 새 세션(프로세스 그룹 = 자식 pid) — 상한 초과면 그 그룹에만 SIGTERM → 30초 → SIGKILL.
         다른 실행 프로세스 · 06 잠금은 건드리지 않는다. caffeinate 는 작업 동안만(판정 §4).
```
06 산출물은 읽기만 한다. 성공 판정은 종료 코드가 아니라 RESULT · 06 주 기록 · 영수증(status.evaluate)이다.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from app.forward_auto import schedule as S
from app.forward_auto import status as ST
from app.ml_evidence import store

CAFFEINATE = "/usr/bin/caffeinate"
SCRIPT_06 = "scripts/run_forward_compare.py"
PREDICT_MAP = {
    "ALREADY_RECORDED": "ALREADY_RECORDED",
    "ALREADY": "ALREADY_RECORDED",
    "NO_INPUT": "INPUT_PENDING",
    "NO_EVIDENCE": "INPUT_PENDING",
    "PENDING_CALENDAR": "CALENDAR_UNKNOWN",
    "BUSY": "OTHER_RUN_BUSY",
    "SKIPPED_TOO_LATE": "TOO_LATE",
    "CHECK_REQUIRED": "CHECK_REQUIRED",
    "NO_MODEL": "CHECK_REQUIRED",
    "PARTIAL": "CHECK_REQUIRED",
    "FAILED": "CALL_FAILED",
}


@dataclass
class Child:
    rc: Optional[int]
    result: Optional[dict]
    timed_out: bool
    stdout_tail: str
    stderr_tail: str


def parse_result(text: str) -> Optional[dict]:
    for line in reversed(text.splitlines()):
        if line.startswith("RESULT "):
            try:
                v = json.loads(line[7:])
            except ValueError:
                return None
            return v if isinstance(v, dict) else None
    return None


def _killpg(pgid: int, sig: int) -> bool:
    """그룹에 신호 — 그룹이 아직 있으면 True."""
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _reap_group(pgid: int, grace_s: float) -> None:
    """자기 그룹에 남은 프로세스: SIGTERM → grace 안에 없어지지 않으면 SIGKILL."""
    if not _killpg(pgid, signal.SIGTERM):
        return
    end = time.monotonic() + grace_s
    while time.monotonic() < end:
        if not _killpg(pgid, 0):
            return
        time.sleep(0.1)
    _killpg(pgid, signal.SIGKILL)


def run_child(
    argv: list[str],
    *,
    cwd: Path,
    timeout_s: float,
    env: Optional[dict] = None,
    popen: Callable = subprocess.Popen,
    grace_s: float = S.KILL_GRACE_S,
) -> Child:
    """자식을 새 세션으로 띄워 **자식의 끝**만 기다린다(출력은 임시 파일 — 손자가 출력 통로를 붙잡아도
    기다림이 늘지 않음). 상한 초과 · 끝난 뒤 남은 자기 그룹만 정리한다."""
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        p = popen(
            argv, cwd=str(cwd), env=env, stdout=fo, stderr=fe, start_new_session=True
        )
        timed_out = False
        try:
            p.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=grace_s)
            except subprocess.TimeoutExpired:
                _killpg(p.pid, signal.SIGKILL)
                p.wait()
        except (
            BaseException
        ):  # 자동화 자신이 끊길 때(SIGTERM · Ctrl-C) 자식 · 손자를 남기지 않음
            _killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=min(grace_s, 5))
            except subprocess.TimeoutExpired:
                _killpg(p.pid, signal.SIGKILL)
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            # 자식이 SIGTERM 으로 끝나도 SIGTERM 을 무시하는 손자가 그룹에 남을 수 있다 → SIGKILL 까지
            _reap_group(p.pid, min(grace_s, 5))
            raise
        _reap_group(p.pid, min(grace_s, 5))  # 끝난 뒤 그룹에 남은 손자(ssh · scp 등)만
        fo.seek(0)
        fe.seek(0)
        text = fo.read().decode("utf-8", "replace")
        etext = fe.read().decode("utf-8", "replace")
    return Child(
        p.returncode, parse_result(text), timed_out, text[-2000:], etext[-2000:]
    )


@contextlib.contextmanager
def awake(
    *, popen: Callable = subprocess.Popen, binary: str = CAFFEINATE
) -> Iterator[bool]:
    """작업 생애 동안만 유휴 절전 방지(`caffeinate -i -w <이 프로세스>`) — 끝나면 반드시 종료."""
    proc = None
    try:
        proc = popen(
            [binary, "-i", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        proc = None
    try:
        yield proc is not None and proc.poll() is None  # 바로 끝난 caffeinate 는 '깨어 있음' 아님
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def predict_outcome(c: Child) -> tuple[str, Optional[str]]:
    if c.timed_out:
        return "CALL_TIMEOUT", f"{S.PREDICT_TIMEOUT_S // 60}분 상한 초과"
    r = c.result
    if r is None:
        return "CALL_FAILED", f"RESULT 줄 없음(rc {c.rc})"
    s = r.get("status")
    if s == "OK":
        if r.get("publication_confirmed") is True and c.rc == 0:
            return "RECORDED_NEW", None
        return "CHECK_REQUIRED", "OK 이지만 공개 확인 없음"
    if s not in PREDICT_MAP:
        return "CALL_FAILED", f"알 수 없는 상태 {s}"
    return PREDICT_MAP[s], r.get("error")


def archive_outcome(c: Child) -> tuple[str, Optional[str]]:
    if c.timed_out:
        return "ARCHIVE_TIMEOUT", f"{S.ARCHIVE_TIMEOUT_S // 60}분 상한 초과"
    r = c.result
    if r is None:
        return "ARCHIVE_FAILED", f"RESULT 줄 없음(rc {c.rc})"
    if r.get("status") not in ("OK", "SKIPPED_NO_NEW"):
        detail = (r.get("detail") or {}).get("reason")
        return "ARCHIVE_FAILED", r.get("error") or detail or str(r.get("status"))
    ups = r.get("uploads") or {}
    bad = [
        k
        for k, u in ups.items()
        if not (isinstance(u, dict) and u.get("status") == "OK")
    ]
    if bad:
        return "ARCHIVE_PARTIAL", f"업로드 OK 아님 {len(bad)}/{len(ups)}"
    return "ARCHIVED_OK", None


def _attempt_id(now: datetime, kind: str) -> str:
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%S}Z_{uuid.uuid4().hex[:8]}_{kind.lower()}"


def child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    path = env.get("PATH", "")
    for d in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        if d not in path.split(":"):
            path = f"{path}:{d}" if path else d
    env["PATH"] = path
    return env


def job(
    paths: ST.Paths,
    kind: str,
    *,
    clock: Callable[[], datetime],
    popen: Callable,
    awake_fn: Callable,
    python: str,
) -> dict[str, Any]:
    """시작 기록 → (작업 동안만 caffeinate) 06 자식 → 끝 기록. 06 산출물은 건드리지 않는다."""
    started = clock()
    aid = _attempt_id(started, kind)
    args = ["run", "--pull"] if kind == ST.PREDICT else ["archive", "--upload"]
    timeout = S.PREDICT_TIMEOUT_S if kind == ST.PREDICT else S.ARCHIVE_TIMEOUT_S
    folder = ST.attempt_dir(paths.ops, S.day(started))
    start = {
        "schema": "poc6_13_attempt_start_v1",
        "id": aid,
        "kind": kind,
        "day": S.day(started),
        "started_at": store.iso(started),
        "reason": S.reason(started),
        "reason_note": "시각으로 한 추정(깨어남 이벤트 확인 아님)",
        "pid": os.getpid(),
        "command": [SCRIPT_06, *args],
    }
    ST.write_once(folder / f"{aid}.start.json", start)
    end: dict[str, Any] = {"schema": "poc6_13_attempt_end_v1", "id": aid, "kind": kind}
    try:
        with awake_fn() as aw:
            c = run_child(
                [python, str(paths.repo / SCRIPT_06), *args],
                cwd=paths.repo,
                timeout_s=timeout,
                env=child_env(),
                popen=popen,
            )
        outcome, err = (predict_outcome if kind == ST.PREDICT else archive_outcome)(c)
        end.update(
            rc=c.rc,
            timed_out=c.timed_out,
            outcome=outcome,
            error=err,
            result=c.result,
            awake=aw,
            stderr_tail=(
                c.stderr_tail[-600:]
                if outcome in ST.FAIL_OUTCOMES | ST.ARCHIVE_FAIL
                else None
            ),
        )
    except Exception as e:  # noqa: BLE001 — 자동화 자체 실패도 끝 기록으로 남긴다
        end.update(
            outcome="CALL_FAILED" if kind == ST.PREDICT else "ARCHIVE_FAILED",
            error=f"{type(e).__name__}: {str(e)[:300]}",
        )
    end["ended_at"] = store.iso(clock())
    ST.write_once(folder / f"{aid}.end.json", end)
    return end


def _last_start(atts: list[dict], kind: str) -> Optional[datetime]:
    ks = [a for a in atts if a.get("kind") == kind]
    return ST.view.parse_time(ks[-1].get("started_at")) if ks else None


def tick(
    paths: ST.Paths,
    *,
    clock: Callable[[], datetime] = store.utc_now,
    popen: Callable = subprocess.Popen,
    awake_fn: Optional[Callable] = None,
    notify: Callable[[str], str] = ST.osascript_notify,
    launchd: Optional[dict] = None,
    python: str = sys.executable,
) -> dict[str, Any]:
    """launchd 가 부르는 한 번. 자동 잠금을 못 잡으면 겹침 기록만 남긴다(06 호출 0)."""
    awake_fn = awake_fn or (lambda: awake(popen=popen))
    paths.ops.mkdir(parents=True, exist_ok=True)
    with store.file_lock(paths.ops / ".auto.lock", wait_s=0.0) as ok:
        now = clock()
        if not ok:
            aid = _attempt_id(now, "coalesced")
            ST.write_once(
                ST.attempt_dir(paths.ops, S.day(now)) / f"{aid}.coalesced.json",
                {"schema": "poc6_13_coalesced_v1", "id": aid, "at": store.iso(now)},
            )
            return {"status": "COALESCED", "id": aid}
        actions = []
        ev = ST.evaluate(paths, now, launchd=launchd, in_tick=True)
        atts = ST.load_attempts(paths.ops, S.day(now), in_tick=True)
        ran = False
        n_pred = sum(1 for a in atts if a.get("kind") == ST.PREDICT)
        if (
            S.window(now) == S.OPEN
            and ev["predict"]["state"] not in ("DONE", "DEADLINE_PASSED")
            and n_pred < S.MAX_PREDICT
            and S.gap_ok(now, _last_start(atts, ST.PREDICT))
        ):
            kw = dict(clock=clock, popen=popen, awake_fn=awake_fn, python=python)
            actions.append(job(paths, ST.PREDICT, **kw))
            ran = True
            ev = ST.evaluate(paths, clock(), launchd=launchd, in_tick=True)
        later = clock()
        atts = ST.load_attempts(paths.ops, S.day(later), in_tick=True)
        n_arch = sum(1 for a in atts if a.get("kind") == ST.ARCHIVE)
        if (
            S.window(later) == S.OPEN
            and ev["archive"].get("pending")
            and n_arch < S.MAX_ARCHIVE
            and (ran or S.gap_ok(later, _last_start(atts, ST.ARCHIVE)))
        ):
            kw = dict(clock=clock, popen=popen, awake_fn=awake_fn, python=python)
            actions.append(job(paths, ST.ARCHIVE, **kw))
        ev = ST.evaluate(paths, clock(), launchd=launchd, in_tick=True)
        ev["notified"] = ST.send_new(paths, ev, notify)
        ST.save_latest(paths, ev)
        return {
            "status": "OK",
            "actions": [
                {k: a.get(k) for k in ("id", "kind", "outcome", "error")}
                for a in actions
            ],
            "predict": ev["predict"]["state"],
            "archive": ev["archive"]["state"],
            "notified": len(ev["notified"]),
        }
