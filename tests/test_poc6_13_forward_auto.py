"""POC6-13 A · B — 자동 실행 창 · 시도 판단 · 완료 판정 · 상태 · 알림 · 자식 정리 · LaunchAgent · 업로드 목록 재사용.

tmp 폴더 · 가짜 시계 · 가짜 자식 결과 · 가짜 caffeinate(tmp 셸 스크립트) · 05 가짜 원격만 쓴다.
실제 06 산출물 읽기는 06 시험 세계(tmp · 실제 forward.run)로 확인한다. 라이브 state · SSH · launchctl 쓰기 0.
계약 출처: 설계 V1 §3 ~ §5 · §8 · PLAN V1 §2 ~ §3 · PLAN 판정(2026-10-28) §3 · §4 · §5.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.forward_auto import launchd, runner
from app.forward_auto import schedule as S
from app.forward_auto import status as ST
from app.forward_auto import view
from app.forward_compare import archive, records
from app.ml_evidence import store, transfer
from tests.test_poc6_06_forward_core import R, TICKERS, _artifact_manifest
from tests.test_poc6_06_forward_core import D as D06

# 06 시험 세계(tmp · 실제 forward.run) 재사용 — fixture 로만 쓴다
from tests.test_poc6_06_forward_flow import base  # noqa: F401
from tests.test_poc6_06_forward_flow import world  # noqa: F401
from tests.test_poc6_05_evidence_store import FakeRemote
from app.forward_compare import protocol as P

KST = timezone(timedelta(hours=9))


def k(y, mo, d, h, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=KST)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def paths(tmp_path):
    p = ST.Paths(
        repo=tmp_path,
        research=tmp_path / "r",
        evidence=tmp_path / "ev",
        ops=tmp_path / "ops",
    )
    p.research.mkdir()
    p.evidence.mkdir()
    return p


# ── 창 · 일정 · 사유 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "t, win",
    [
        (k(2026, 10, 29, 9, 59, 59), S.BEFORE),
        (k(2026, 10, 29, 10, 0), S.OPEN),
        (k(2026, 10, 29, 15, 19, 59), S.OPEN),
        (k(2026, 10, 29, 15, 20), S.CLOSED),
    ],
)
def test_window_boundaries(t, win):
    assert S.window(t) == win
    assert S.window(t.astimezone(timezone.utc)) == win


def test_reason_is_a_time_estimate_and_naive_time_is_refused():
    assert S.reason(k(2026, 10, 29, 10, 5)) == "SCHEDULED"
    assert S.reason(k(2026, 10, 29, 10, 7)) == "SCHEDULED"
    assert S.reason(k(2026, 10, 29, 10, 7, 1)) == "CATCH_UP"
    assert S.reason(k(2026, 10, 29, 11, 0)) == "CATCH_UP"
    assert S.next_slot(k(2026, 10, 29, 15, 26)) == k(2026, 10, 30, 10, 5)
    with pytest.raises(ValueError):
        S.window(datetime(2026, 10, 29, 10, 0))


@pytest.mark.parametrize(
    "t, ok", [((9, 59), True), ((10, 0), False), ((15, 44), False), ((15, 45), True)]
)
def test_backup_start_block(t, ok):
    assert S.backup_allowed(k(2026, 10, 29, *t)) is ok


# ── 06 결과 → 시도 결과 ──────────────────────────────────────────────────────


def child(result, rc=0, timed_out=False):
    return runner.Child(rc, result, timed_out, "", "")


@pytest.mark.parametrize(
    "c, want",
    [
        (child({"status": "OK", "publication_confirmed": True}), "RECORDED_NEW"),
        (child({"status": "OK", "publication_confirmed": False}), "CHECK_REQUIRED"),
        (child({"status": "OK"}), "CHECK_REQUIRED"),
        (
            child({"status": "OK", "publication_confirmed": True}, rc=1),
            "CHECK_REQUIRED",
        ),
        (child({"status": "ALREADY_RECORDED"}), "ALREADY_RECORDED"),
        (child({"status": "NO_INPUT"}, rc=2), "INPUT_PENDING"),
        (child({"status": "NO_EVIDENCE"}, rc=2), "INPUT_PENDING"),
        (child({"status": "PENDING_CALENDAR"}, rc=2), "CALENDAR_UNKNOWN"),
        (child({"status": "BUSY"}, rc=3), "OTHER_RUN_BUSY"),
        (child({"status": "SKIPPED_TOO_LATE"}, rc=2), "TOO_LATE"),
        (
            child(
                {"status": "CHECK_REQUIRED", "error": "OCI 목록 조회 실패(rc 255)"},
                rc=2,
            ),
            "CHECK_REQUIRED",
        ),
        (child({"status": "NO_MODEL"}, rc=2), "CHECK_REQUIRED"),
        (child({"status": "FAILED"}, rc=1), "CALL_FAILED"),
        (child({"status": "WHAT"}), "CALL_FAILED"),
        (child(None, rc=1), "CALL_FAILED"),
        (child(None, rc=None, timed_out=True), "CALL_TIMEOUT"),
    ],
)
def test_predict_outcome_never_reads_exit_zero_as_success(c, want):
    assert runner.predict_outcome(c)[0] == want


def test_archive_outcome_separates_partial_and_failed():
    ok = {
        "status": "OK",
        "uploads": {
            "a": {"status": "OK"},
            "b": {"status": "OK", "already_on_oci": True},
        },
    }
    assert runner.archive_outcome(child(ok))[0] == "ARCHIVED_OK"
    assert (
        runner.archive_outcome(child({"status": "SKIPPED_NO_NEW", "uploads": {}}))[0]
        == "ARCHIVED_OK"
    )
    part = {
        "status": "OK",
        "uploads": {"a": {"status": "OK"}, "b": {"status": "CHECK_REQUIRED"}},
    }
    assert runner.archive_outcome(child(part))[0] == "ARCHIVE_PARTIAL"
    bad = runner.archive_outcome(
        child({"status": "CHECK_REQUIRED", "error": "object 올리기 실패(rc 1)"}, rc=2)
    )
    assert bad == ("ARCHIVE_FAILED", "object 올리기 실패(rc 1)")
    assert runner.archive_outcome(child(None, timed_out=True))[0] == "ARCHIVE_TIMEOUT"
    assert runner.parse_result('x\nRESULT {"status": "OK"}\n') == {"status": "OK"}
    assert (
        runner.parse_result("RESULT [1]") is None
        and runner.parse_result("none") is None
    )


# ── 자식 실행 · 프로세스 그룹 정리 · caffeinate 생애 ────────────────────────────


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # 좀비(부모가 거두기 전)는 끝난 것으로 본다
        out = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
        )
        return bool(out.stdout.strip()) and not out.stdout.strip().startswith("Z")
    except OSError:
        return True


def _wait_gone(pid, s=5.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return False


def test_run_child_timeout_kills_its_own_group_including_grandchild(tmp_path):
    pidf = tmp_path / "g.pid"
    code = (
        "import subprocess,sys,time;"
        f"p=subprocess.Popen(['sleep','30']);open({str(pidf)!r},'w').write(str(p.pid));"
        "print('working',flush=True);time.sleep(30)"
    )
    c = runner.run_child(
        [sys.executable, "-c", code], cwd=tmp_path, timeout_s=1.5, grace_s=1
    )
    assert c.timed_out and c.result is None
    assert _wait_gone(int(pidf.read_text()))


def test_run_child_reads_last_result_and_cleans_leftover_grandchild(tmp_path):
    pidf = tmp_path / "g.pid"
    code = (
        "import subprocess,json;"
        f"p=subprocess.Popen(['sleep','30']);open({str(pidf)!r},'w').write(str(p.pid));"
        "print('RESULT '+json.dumps({'status':'NO_INPUT'}));raise SystemExit(2)"
    )
    c = runner.run_child([sys.executable, "-c", code], cwd=tmp_path, timeout_s=20)
    assert (c.rc, c.result, c.timed_out) == (2, {"status": "NO_INPUT"}, False)
    assert _wait_gone(int(pidf.read_text()))


def test_run_child_interrupted_by_signal_leaves_no_child(tmp_path):
    """자동화 자신이 끊기면(SIGTERM → SystemExit · Ctrl-C) 자식 그룹을 정리하고 다시 올린다."""
    pidf = tmp_path / "c.pid"

    class Interrupting(subprocess.Popen):
        first = True

        def wait(self, timeout=None):
            if Interrupting.first and timeout is not None and timeout > 10:
                Interrupting.first = False
                end = time.monotonic() + 5
                while not pidf.exists() and time.monotonic() < end:
                    time.sleep(0.05)  # 자식이 실제로 시작한 뒤 끊김
                raise SystemExit(143)
            return super().wait(timeout)

    code = (
        f"import os,time;open({str(pidf)!r},'w').write(str(os.getpid()));time.sleep(30)"
    )
    with pytest.raises(SystemExit):
        runner.run_child(
            [sys.executable, "-c", code], cwd=tmp_path, timeout_s=60, popen=Interrupting
        )
    end = time.monotonic() + 5
    while not pidf.exists() and time.monotonic() < end:
        time.sleep(0.05)
    assert _wait_gone(int(pidf.read_text()))


def test_leftover_ignoring_sigterm_is_killed_after_grace(tmp_path):
    pidf = tmp_path / "g.pid"
    stubborn = (
        "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
    )
    code = (
        "import subprocess,sys,time;"
        f"p=subprocess.Popen([sys.executable,'-c',{stubborn!r}]);"
        f"open({str(pidf)!r},'w').write(str(p.pid));time.sleep(0.5)"
    )
    c = runner.run_child(
        [sys.executable, "-c", code], cwd=tmp_path, timeout_s=20, grace_s=1
    )
    assert not c.timed_out and c.rc == 0
    assert _wait_gone(int(pidf.read_text()))


@pytest.fixture
def fake_caffeinate(tmp_path, monkeypatch):
    pidf, argf = tmp_path / "caf.pid", tmp_path / "caf.args"
    sh = tmp_path / "caffeinate"
    sh.write_text(f'#!/bin/sh\necho "$@" > {argf}\necho $$ > {pidf}\nexec sleep 30\n')
    sh.chmod(0o755)
    return sh, pidf, argf


def _started(pidf, s=5.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        if pidf.exists() and pidf.read_text().strip():
            return int(pidf.read_text())
        time.sleep(0.05)
    raise AssertionError("caffeinate 가 뜨지 않음")


def test_awake_lives_only_during_the_job_even_on_error(fake_caffeinate):
    sh, pidf, argf = fake_caffeinate
    with runner.awake(binary=str(sh)) as on:
        pid = _started(pidf)
        assert on and _alive(pid)
    assert _wait_gone(pid)
    assert argf.read_text().split() == ["-i", "-w", str(os.getpid())]
    pidf.unlink()
    with pytest.raises(RuntimeError):
        with runner.awake(binary=str(sh)):
            pid2 = _started(pidf)
            raise RuntimeError("작업 실패")
    assert _wait_gone(pid2)
    with runner.awake(binary=str(sh.parent / "없음")) as on:
        assert on is False  # 띄우지 못하면 작업은 계속 · 기록만 False


def test_job_timeout_leaves_no_child_and_no_caffeinate(
    paths, fake_caffeinate, monkeypatch
):
    sh, pidf, _ = fake_caffeinate
    script = paths.repo / runner.SCRIPT_06
    script.parent.mkdir(parents=True)
    script.write_text("import time\nprint('started', flush=True)\ntime.sleep(60)\n")
    monkeypatch.setattr(S, "PREDICT_TIMEOUT_S", 1)
    end = runner.job(
        paths,
        ST.PREDICT,
        clock=Clock(k(2026, 10, 29, 10, 5)),
        popen=subprocess.Popen,
        awake_fn=lambda: runner.awake(binary=str(sh)),
        python=sys.executable,
    )
    assert (
        end["outcome"] == "CALL_TIMEOUT" and end["timed_out"] and end["awake"] is True
    )
    assert _wait_gone(int(pidf.read_text()))
    a = ST.load_attempts(paths.ops, "2026-10-29")
    assert [x["outcome"] for x in a] == ["CALL_TIMEOUT"] and a[0][
        "reason"
    ] == "SCHEDULED"
    assert a[0]["command"] == [runner.SCRIPT_06, "run", "--pull"]


# ── tick 판단(06 결과 · 06 산출물 읽기는 가짜) ───────────────────────────────


class World:
    """06 쪽 상태(오늘 실행 기록 · 완료 · 보관 대기)와 06 자식 결과를 흉내 낸다."""

    def __init__(
        self,
        monkeypatch,
        *,
        done=False,
        pending=False,
        cutoff="2026-10-29T06:30:00.000000Z",
    ):
        self.done, self.pending, self.cutoff = done, pending, cutoff
        self.runs, self.calls, self.results = [], [], []
        monkeypatch.setattr(
            ST.view,
            "runs_on",
            lambda root, day: [r for r in self.runs if r["today_kst"] == day],
        )
        monkeypatch.setattr(ST.view, "completion", self.completion)
        monkeypatch.setattr(ST.view, "archive_pending", self.archive_pending)
        monkeypatch.setattr(runner, "run_child", self.run_child)

    def completion(self, root, D):
        n = 24 if self.done else 20
        return {
            "D": D,
            "total": 24,
            "recorded": n,
            "method_failed": [],
            "missing": [],
            "done": self.done,
            "first_visible": None,
            "last_visible": None,
            "cohort_id": "cohort_v1",
        }

    def archive_pending(self, root, ev, confirmed):
        return {
            "unregistered": 3 if self.pending else 0,
            "registered": 1,
            "unconfirmed": [],
            "not_allowed": [],
            "pending": self.pending,
        }

    def run_child(self, argv, *, cwd, timeout_s, env=None, popen=None):
        self.calls.append((argv[2:], cwd, timeout_s, env.get("PYTHONIOENCODING")))
        r = (
            self.results.pop(0)
            if self.results
            else child({"status": "OK", "publication_confirmed": True})
        )
        if argv[2] == "run":
            self.runs.append(
                {
                    "today_kst": self.day,
                    "D": "2026-10-28",
                    "close_cutoff_at": self.cutoff,
                    "id": "r1",
                }
            )
        return r


def do_tick(paths, w, t, notes=None):
    w.day = S.day(t)
    notes = [] if notes is None else notes

    def notify(msg):
        notes.append(msg)
        return "REQUESTED_DELIVERY_UNKNOWN"

    from contextlib import nullcontext

    return runner.tick(
        paths,
        clock=Clock(t),
        awake_fn=lambda: nullcontext(True),
        notify=notify,
        python="/py",
    )


def test_before_window_calls_nothing(paths, monkeypatch):
    w = World(monkeypatch, pending=True)
    out = do_tick(paths, w, k(2026, 10, 29, 9, 30))
    assert out["actions"] == [] and w.calls == [] and out["predict"] == "BEFORE_WINDOW"
    assert (paths.ops / "latest.json").is_file() and (
        paths.ops / "latest.txt"
    ).is_file()


def test_in_window_predict_then_archive_with_absolute_child(paths, monkeypatch):
    w = World(monkeypatch, pending=True)
    out = do_tick(paths, w, k(2026, 10, 29, 10, 5))
    assert [c[0] for c in w.calls] == [["run", "--pull"], ["archive", "--upload"]]
    assert (
        w.calls[0][1] == paths.repo
        and w.calls[0][2] == S.PREDICT_TIMEOUT_S
        and w.calls[1][2] == S.ARCHIVE_TIMEOUT_S
    )
    assert w.calls[0][3] == "utf-8"
    assert [a["outcome"] for a in out["actions"]] == ["RECORDED_NEW", "ARCHIVED_OK"]


def test_predict_done_still_retries_pending_archive(paths, monkeypatch):
    """판정 §5-2 — 예측 완료면 예측 호출만 건너뛰고 보관 대기는 따로 처리한다."""
    w = World(monkeypatch, done=True, pending=True)
    w.runs.append(
        {
            "today_kst": "2026-10-29",
            "D": "2026-10-28",
            "close_cutoff_at": w.cutoff,
            "id": "m",
        }
    )
    w.results = [
        child({"status": "CHECK_REQUIRED", "error": "object 올리기 실패(rc 1)"}, rc=2)
    ]
    notes = []
    out = do_tick(paths, w, k(2026, 10, 29, 10, 5), notes)
    assert [c[0] for c in w.calls] == [["archive", "--upload"]]
    assert out["predict"] == "DONE" and out["archive"] == "ARCHIVE_PENDING"
    assert [n for n in notes if "보관" in n] == [
        "전향 기록 보관 실패 · 확인 run_forward_auto.py status"
    ]
    out2 = do_tick(paths, w, k(2026, 10, 29, 12, 5), notes)  # 다음 일정: 보관만 다시
    assert [c[0] for c in w.calls] == [["archive", "--upload"]] * 2 and out2[
        "predict"
    ] == "DONE"


def test_attempt_cap_and_gap_and_closed_window(paths, monkeypatch):
    w = World(monkeypatch)
    w.results = [child({"status": "NO_INPUT"}, rc=2) for _ in range(6)]
    for t in [(10, 5), (10, 10), (12, 5), (14, 35), (14, 55), (15, 10), (15, 19)]:
        do_tick(paths, w, k(2026, 10, 29, *t))
    assert len(w.calls) == 4  # 10:10 은 15분 간격 · 15:19 는 4회 소진
    out = do_tick(paths, w, k(2026, 10, 29, 15, 25))
    assert out["predict"] == "AUTO_WINDOW_CLOSED" and len(w.calls) == 4


def test_auto_window_closed_is_not_deadline_until_real_cutoff(paths, monkeypatch):
    """판정 §5-3 — 15:20 = AUTO_WINDOW_CLOSED · DEADLINE_PASSED 는 실제 close_cutoff_at 뒤에만."""
    w = World(monkeypatch)
    w.results = [child({"status": "NO_INPUT"}, rc=2)]
    do_tick(paths, w, k(2026, 10, 29, 10, 5))
    notes = []
    assert (
        do_tick(paths, w, k(2026, 10, 29, 15, 25), notes)["predict"]
        == "AUTO_WINDOW_CLOSED"
    )
    assert (
        do_tick(paths, w, k(2026, 10, 29, 15, 29, 59), notes)["predict"]
        == "AUTO_WINDOW_CLOSED"
    )
    assert (
        do_tick(paths, w, k(2026, 10, 29, 15, 30), notes)["predict"]
        == "DEADLINE_PASSED"
    )
    assert (
        len([n for n in notes if "AUTO_WINDOW_CLOSED" in n]) == 1
    )  # 같은 상태는 한 번만
    assert len([n for n in notes if "DEADLINE_PASSED" in n]) == 1


def test_saturday_friday_d_closes_window_without_deadline(paths, monkeypatch):
    w = World(monkeypatch, cutoff="2026-11-02T06:30:00.000000Z")  # 금 D → 월 15:30 마감
    w.results = [child({"status": "NO_INPUT"}, rc=2)]
    do_tick(paths, w, k(2026, 10, 31, 10, 5))
    out = do_tick(paths, w, k(2026, 10, 31, 16, 0))
    assert out["predict"] == "AUTO_WINDOW_CLOSED"
    ev = ST.evaluate(paths, k(2026, 10, 31, 16, 0))
    assert "실제 마감 11-02 15:30" in ST.predict_line(ev["predict"])


def test_unknown_d_is_reported_not_declared_missing(paths, monkeypatch):
    w = World(monkeypatch)
    w.results = [
        child({"status": "CHECK_REQUIRED", "error": "OCI 목록 조회 실패(rc 255)"}, rc=2)
    ]
    orig = w.run_child

    def no_run_doc(argv, **kw):  # 수신 실패 = 06 run 기록 없음
        r = orig(argv, **kw)
        w.runs.clear()
        return r

    monkeypatch.setattr(runner, "run_child", no_run_doc)
    notes = []
    out = do_tick(paths, w, k(2026, 10, 29, 10, 5), notes)
    assert out["predict"] == "RETRY_PENDING"
    ev = ST.evaluate(paths, k(2026, 10, 29, 16, 0))
    assert ev["predict"][
        "state"
    ] == "AUTO_WINDOW_CLOSED" and "필요 기준일 확인 불가" in ST.predict_line(ev["predict"])
    assert any(
        "D 확인 불가 확인 필요" in n for n in notes
    )  # 오늘 날짜를 D 로 쓰지 않음
    assert not any("D=2026-10-29" in n for n in notes)


def test_lock_held_coalesces_without_calls(paths, monkeypatch):
    w = World(monkeypatch)
    paths.ops.mkdir()
    with store.file_lock(paths.ops / ".auto.lock") as ok:
        assert ok
        out = do_tick(paths, w, k(2026, 10, 29, 10, 5))
    assert out["status"] == "COALESCED" and w.calls == []
    assert list((paths.ops / "attempts" / "2026-10-29").glob("*.coalesced.json"))


def test_interrupted_attempt_counts_and_is_notified(paths, monkeypatch):
    World(monkeypatch)
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    ST.write_once(
        ST.attempt_dir(paths.ops, "2026-10-29") / "x.start.json",
        {
            "id": "x",
            "kind": ST.PREDICT,
            "started_at": "2026-10-29T01:05:00.000000Z",
            "pid": dead.pid,
        },
    )
    ev = ST.evaluate(paths, k(2026, 10, 29, 10, 6))
    assert ev["predict"]["attempts"] == 1 and ev["predict"]["outcomes"] == [
        "INTERRUPTED"
    ]
    assert any("중단" in m for _, m in ST.notifications(ev))
    # pid 가 다시 쓰여도(살아 있는 내 pid) 잠금을 쥔 tick 이 없으면 중단으로 읽는다
    ST.write_once(
        ST.attempt_dir(paths.ops, "2026-10-29") / "y.start.json",
        {
            "id": "y",
            "kind": ST.PREDICT,
            "started_at": "2026-10-29T01:06:00.000000Z",
            "pid": os.getpid(),
        },
    )
    assert [a["outcome"] for a in ST.load_attempts(paths.ops, "2026-10-29")] == [
        "INTERRUPTED"
    ] * 2
    with store.file_lock(paths.ops / ".auto.lock") as ok:  # 다른 tick 이 실행 중
        assert ok
        assert {a["outcome"] for a in ST.load_attempts(paths.ops, "2026-10-29")} == {
            "RUNNING"
        }
        inside = ST.load_attempts(paths.ops, "2026-10-29", in_tick=True)
        assert {a["outcome"] for a in inside} == {"INTERRUPTED"}


def test_next_day_shows_past_day_and_notifies_once(paths, monkeypatch):
    w = World(monkeypatch)
    w.results = [child({"status": "CALL"}, rc=1)]
    do_tick(paths, w, k(2026, 10, 29, 10, 5))
    notes = []
    do_tick(paths, w, k(2026, 10, 30, 9, 0), notes)
    txt = (paths.ops / "latest.txt").read_text(encoding="utf-8")
    assert (
        "지난 날 2026-10-29 DEADLINE_PASSED" in txt
    )  # 그날 D 의 실제 마감(10-29 15:30)이 지남
    assert len([n for n in notes if "지난 자동 점검" in n]) == 1
    do_tick(paths, w, k(2026, 10, 30, 9, 1), notes)
    assert len([n for n in notes if "지난 자동 점검" in n]) == 1
    # 두 번째 tick 뒤에도 지난 날이 사라지지 않는다(검토 지적)
    txt2 = (paths.ops / "latest.txt").read_text(encoding="utf-8")
    assert "지난 날 2026-10-29 DEADLINE_PASSED" in txt2


def test_past_weekday_without_records_is_reported_weekend_is_not(paths, monkeypatch):
    w = World(monkeypatch)
    w.results = [child({"status": "NO_INPUT"}, rc=2)]
    do_tick(paths, w, k(2026, 10, 29, 10, 5))  # 목 — 자동화 첫 기록일
    notes = []
    do_tick(
        paths, w, k(2026, 11, 2, 9, 0), notes
    )  # 월 09:00 — 금 · 토 · 일 은 기록 없음
    txt = (paths.ops / "latest.txt").read_text(encoding="utf-8")
    for d in ("2026-10-30", "2026-10-31", "2026-11-01"):
        assert f"지난 날 {d} 자동 호출 기록 없음" in txt
    past = [n for n in notes if "지난 자동 점검" in n]
    assert (
        len(past) == 1
        and "2026-10-30 자동 호출 기록 없음(거래일 여부 미확인)" in past[0]
    )
    assert "2026-10-31" not in past[0] and "2026-11-01" not in past[0]
    assert "지난 날 2026-10-28" not in txt  # 첫 기록일 전은 요약하지 않음


def test_status_evaluation_writes_nothing(paths, monkeypatch):
    w = World(monkeypatch)
    do_tick(paths, w, k(2026, 10, 29, 10, 5))
    before = {p: p.stat().st_mtime_ns for p in paths.ops.rglob("*")}
    ev = ST.evaluate(paths, k(2026, 10, 29, 11, 0))
    ST.render(ev)
    assert {p: p.stat().st_mtime_ns for p in paths.ops.rglob("*")} == before


def test_notify_failure_is_recorded_not_hidden(paths, monkeypatch):
    def broken(argv, **kw):
        raise OSError("없음")

    assert ST.osascript_notify("x", runner=broken) == "NOTIFY_FAILED"
    ok = ST.osascript_notify(
        'a "q"', runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0)
    )
    assert ok == "REQUESTED_DELIVERY_UNKNOWN"


# ── 실제 06 산출물 읽기(06 시험 세계 · 실제 forward.run) ─────────────────────


def test_real_06_records_drive_completion_and_receipt_is_required(world):  # noqa: F811
    ev, root = world
    runs = view.runs_on(root, "2026-10-23")
    need = view.needed_d(runs)
    assert need["D"] == D06 and need["close_cutoff_at"]
    comp = view.completion(root, D06)
    prims = records.primaries(root)
    want = sum(1 for t in TICKERS if (t, D06) in prims)
    assert comp["recorded"] == want and comp["total"] == len(TICKERS) == 24
    assert comp["done"] == (want == 24 and not comp["method_failed"])
    assert (
        view.completion(root, "2026-10-21")["recorded"] == 0
    )  # 다른 D 의 영수증은 세지 않음
    for rp in (root / "predictions").glob("*/*.receipt.json"):
        rp.unlink()  # exit 0 · 예측 파일만 있고 공개 확인 영수증 없음
    gone = view.completion(root, D06)
    assert gone["recorded"] == 0 and not gone["done"]


def test_real_06_archive_pending_until_confirmed(world):  # noqa: F811
    ev, root = world
    p = view.archive_pending(root, ev, set())
    assert p["pending"] and p["unregistered"] > 0
    status, m = archive.register(
        root, ev, now=datetime(2026, 10, 23, 3, tzinfo=timezone.utc), code_commit="t"
    )
    assert status == "OK"
    assert view.archive_pending(root, ev, set())["unconfirmed"] == [m["run_id"]]
    assert not view.archive_pending(root, ev, {m["run_id"]})["pending"]


def test_06_cli_archive_upload_lists_oci_once(
    world, tmp_path, monkeypatch  # noqa: F811
):
    from scripts import run_forward_compare as rfc

    ev, root = world
    rem = FakeRemote(tmp_path / "oci")
    monkeypatch.setattr(transfer, "default_remote", lambda: rem)
    out = rfc._archive(root, ev, True, None)
    assert out["status"] == "OK" and all(
        u["status"] == "OK" for u in out["uploads"].values()
    )
    assert (
        sum(1 for c in rem.calls if c[0] == "ssh" and c[1].endswith(" list-runs")) == 1
    )


# ── 업로드 작업당 원격 목록 1회(판정 §3) ──────────────────────────────────────


T1 = datetime(2026, 10, 23, 2, tzinfo=timezone.utc)


def _bundles(pc, oci, n, on_oci):
    ids = []
    for i in range(n):
        data = P.dumps(P.doc("cohort", tickers=list(TICKERS), variant=i))
        m = _artifact_manifest({f"{R}/cohort_v1/cohort.json": data}, pc)
        m["run_id"] = store.new_run_id(T1 + timedelta(seconds=i))
        store.publish_run(pc, m, clock=lambda: T1)
        if on_oci(i):
            store.put_bytes(oci, data)
            mb = (pc / "runs" / m["run_id"] / "manifest.json").read_bytes()
            rec = {
                "site": "OCI",
                "source_site": "PC",
                "received_at": store.iso(T1),
                "upload_id": "up_x",
            }
            store.publish_copied(oci, mb, lambda: rec)
        ids.append(m["run_id"])
    return ids


def _lists(rem):
    return sum(1 for c in rem.calls if c[0] == "ssh" and c[1].endswith(" list-runs"))


def test_many_bundles_one_listing_and_existing_checks_kept(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 175, lambda i: i < 172)
    rem = FakeRemote(oci)
    out = transfer.upload_research_many(root=pc, remote=rem, run_ids=ids, now=T1)
    assert _lists(rem) == 1
    assert all(
        out[i]["status"] == "OK" and out[i].get("already_on_oci") for i in ids[:172]
    )
    assert all(
        out[i]["status"] == "OK" and out[i]["accept"]["status"] == "OK"
        for i in ids[172:]
    )
    assert {r.run_id for r in store.list_runs(oci)[0]} == set(ids)
    assert transfer.upload_research_many(root=pc, remote=rem, run_ids=[], now=T1) == {}
    assert _lists(rem) == 1  # 올릴 묶음이 없으면 조회도 없음


def test_listing_failure_raises_and_uploads_nothing(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 3, lambda i: False)

    class Down(FakeRemote):
        def ssh(self, cmd, timeout):
            self.calls.append(("ssh", cmd))
            return 255, b""

    rem = Down(oci)
    with pytest.raises(store.EvidenceError):
        transfer.upload_research_many(root=pc, remote=rem, run_ids=ids, now=T1)
    assert (
        not any(c[0] == "scp_to" for c in rem.calls) and store.list_runs(oci)[0] == []
    )


def test_damaged_remote_copy_is_repaired_within_one_listing(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 2, lambda i: True)
    m = store.list_runs(oci)[0][0].manifest
    obj = store.object_path(oci, store.manifest_object_shas(m)[0])
    os.chmod(obj, 0o644)
    obj.write_bytes(b"tampered")
    rem = FakeRemote(oci)
    out = transfer.upload_research_many(root=pc, remote=rem, run_ids=ids, now=T1)
    assert (
        _lists(rem) == 1
        and out[ids[0]]["repair_of_oci_copy"]
        and out[ids[0]]["status"] == "OK"
    )
    assert store.damaged_objects(oci, m) == []


def test_failure_midway_keeps_earlier_uploads_and_next_job_lists_again(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 3, lambda i: False)

    class Flaky(FakeRemote):
        def scp_to(self, local_paths, remote_dir, timeout):
            if sum(1 for c in self.calls if c[0] == "scp_to") >= 2:
                self.calls.append(("scp_to", "fail"))
                return 1
            return super().scp_to(local_paths, remote_dir, timeout)

    with pytest.raises(store.EvidenceError) as ei:
        transfer.upload_research_many(root=pc, remote=Flaky(oci), run_ids=ids, now=T1)
    assert [r.run_id for r in store.list_runs(oci)[0]] == ids[
        :1
    ]  # 실패한 묶음은 공개되지 않음
    res = ei.value.results
    assert res[ids[0]]["status"] == "OK" and {res[i]["status"] for i in ids[1:]} == {
        "FAILED"
    }
    rem = FakeRemote(oci)
    out = transfer.upload_research_many(root=pc, remote=rem, run_ids=ids, now=T1)
    assert (
        _lists(rem) == 1
        and out[ids[0]]["already_on_oci"]
        and all(out[i]["status"] == "OK" for i in ids)
    )


def test_one_failing_bundle_does_not_block_later_bundles(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 3, lambda i: False)
    bad = set(store.manifest_object_shas(store.list_runs(pc)[0][1].manifest))

    class OneBad(FakeRemote):
        def scp_to(self, local_paths, remote_dir, timeout):
            if {Path(p).name for p in local_paths} & bad:
                return 1
            return super().scp_to(local_paths, remote_dir, timeout)

    rem = OneBad(oci)
    with pytest.raises(store.EvidenceError, match="업로드 실패 1/3"):
        transfer.upload_research_many(root=pc, remote=rem, run_ids=ids, now=T1)
    assert {r.run_id for r in store.list_runs(oci)[0]} == {ids[0], ids[2]}
    assert _lists(rem) == 1


def test_other_uploader_after_listing_is_handled_by_existing_rules(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 1, lambda i: False)

    class Race(FakeRemote):
        def ssh(self, cmd, timeout):
            if cmd.startswith("mkdir -p ") and not getattr(self, "raced", False):
                self.raced = True  # 목록을 읽은 뒤 다른 실행이 같은 묶음을 먼저 올림
                _bundles_copy(pc, oci, ids[0])
            return super().ssh(cmd, timeout)

    out = transfer.upload_research_many(root=pc, remote=Race(oci), run_ids=ids, now=T1)
    assert out[ids[0]]["status"] == "OK" and out[ids[0]]["accept"]["created"] is False


def _bundles_copy(pc, oci, rid):
    run = next(r for r in store.list_runs(pc)[0] if r.run_id == rid)
    for s in store.manifest_object_shas(run.manifest):
        store.put_bytes(oci, store.read_object(pc, s))
    mb = (pc / "runs" / rid / "manifest.json").read_bytes()
    store.publish_copied(
        oci,
        mb,
        lambda: {
            "site": "OCI",
            "source_site": "PC",
            "received_at": store.iso(T1),
            "upload_id": "up_y",
        },
    )


def test_single_upload_without_listing_is_unchanged(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    ids = _bundles(pc, oci, 1, lambda i: False)
    rem = FakeRemote(oci)
    rep = transfer.upload_research(root=pc, remote=rem, run_id=ids[0], now=T1)
    assert rep["status"] == "OK" and _lists(rem) == 1


# ── LaunchAgent ──────────────────────────────────────────────────────────────


class Launchctl:
    def __init__(self, loaded=False):
        self.loaded, self.calls = loaded, []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        if argv[1] == "print":
            return subprocess.CompletedProcess(argv, 0 if self.loaded else 113)
        if argv[1] == "bootstrap":
            self.loaded = True
        if argv[1] == "bootout":
            self.loaded = False
        return subprocess.CompletedProcess(argv, 0)


def test_check_reports_launchd_last_exit_code(tmp_path):
    def lc(argv, **kw):
        out = b"state = not running\n\tlast exit code = 78: EX_CONFIG\n"
        return subprocess.CompletedProcess(argv, 0, stdout=out)

    st = launchd.check(sys.executable, tmp_path, home=tmp_path / "home", runner=lc)
    assert st["loaded"] is True and st["last_exit"] == 78 and st["log_dir"] is False
    ev = {
        "evaluated_at": "2026-10-29T01:00:00.000000Z",
        "day": "2026-10-29",
        "next_slot": "2026-10-29T03:05:00.000000Z",
        "predict": {"state": "BEFORE_WINDOW", "attempts": 0, "need": None},
        "archive": {"state": "ARCHIVED", "attempts": 0},
        "backup": {"state": "WAITING_TARGET"},
        "launchd": st,
    }
    assert "마지막 종료 코드 78" in ST.render(ev)


def test_plist_is_absolute_scheduled_and_without_keepalive(tmp_path):
    body = plistlib.loads(launchd.render(sys.executable, tmp_path))
    assert (
        body["Label"] == launchd.LABEL
        and body["RunAtLoad"] is True
        and "KeepAlive" not in body
    )
    assert [(x["Hour"], x["Minute"]) for x in body["StartCalendarInterval"]] == [
        (10, 5),
        (12, 5),
        (14, 35),
        (15, 25),
    ]
    assert (
        all(Path(a).is_absolute() for a in body["ProgramArguments"][:2])
        and body["ProgramArguments"][2] == "tick"
    )
    assert body["WorkingDirectory"] == str(tmp_path.resolve())


def test_install_dry_run_writes_nothing_and_apply_writes_only_own_plist(tmp_path):
    home, lc = tmp_path / "home", Launchctl()
    dry = launchd.install(sys.executable, tmp_path, apply=False, home=home, runner=lc)
    assert dry["status"] == "DRY_RUN" and dry["creates_dir"] and not home.exists()
    assert all(c[1] == "print" for c in lc.calls)
    assert dry["creates_log_dir"] and not (tmp_path / ST.OPS_REL).exists()
    ok = launchd.install(sys.executable, tmp_path, apply=True, home=home, runner=lc)
    assert ok["status"] == "OK" and sorted(
        p.name for p in (home / "Library" / "LaunchAgents").iterdir()
    ) == [f"{launchd.LABEL}.plist"]
    assert (
        tmp_path / ST.OPS_REL
    ).is_dir()  # launchd 는 로그 폴더를 만들지 않으므로 설치가 먼저 만든다
    assert ok["after"]["log_dir"] is True
    other = launchd.install(
        sys.executable, tmp_path / "x", apply=True, home=home, runner=lc
    )
    assert other["status"] == "REFUSED"
    gone = launchd.uninstall(apply=True, home=home, runner=lc)
    assert (
        gone["status"] == "OK"
        and not launchd.plist_path(home).exists()
        and not lc.loaded
    )


# ── 검증자 r1 정정: 중단 시 SIGTERM 무시 손자(F1) · 해제 실패(F4) ─────────────


def test_interrupt_also_kills_grandchild_ignoring_sigterm(tmp_path):
    pidf = tmp_path / "g.pid"
    stubborn = (
        "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"
    )
    code = (
        "import subprocess,sys,time;"
        f"p=subprocess.Popen([sys.executable,'-c',{stubborn!r}]);"
        f"open({str(pidf)!r},'w').write(str(p.pid));time.sleep(60)"
    )

    class Interrupting(subprocess.Popen):
        first = True

        def wait(self, timeout=None):
            if Interrupting.first and timeout is not None and timeout > 10:
                Interrupting.first = False
                end = time.monotonic() + 5
                while not pidf.exists() and time.monotonic() < end:
                    time.sleep(0.05)
                time.sleep(0.3)  # 손자가 SIGTERM 무시를 설정할 시간
                raise SystemExit(143)
            return super().wait(timeout)

    with pytest.raises(SystemExit):
        runner.run_child(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            timeout_s=60,
            grace_s=1,
            popen=Interrupting,
        )
    assert _wait_gone(int(pidf.read_text()))


class StuckLaunchctl(Launchctl):
    """bootout 을 거절하고 작업이 계속 올라 있는 launchd."""

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        if argv[1] == "print":
            return subprocess.CompletedProcess(argv, 0 if self.loaded else 113)
        if argv[1] == "bootout":
            return subprocess.CompletedProcess(argv, 5)
        if argv[1] == "bootstrap":
            self.loaded = True
        return subprocess.CompletedProcess(argv, 0)


def test_uninstall_failure_is_not_reported_ok_and_keeps_plist(tmp_path):
    home = tmp_path / "home"
    lc = StuckLaunchctl()
    assert (
        launchd.install(sys.executable, tmp_path, apply=True, home=home, runner=lc)[
            "status"
        ]
        == "OK"
    )
    out = launchd.uninstall(apply=True, home=home, runner=lc)
    assert out["status"] == "FAILED" and out["bootout_rc"] == 5
    assert out["loaded_after"] is True and launchd.plist_path(home).is_file()

    def broken(argv, **kw):
        if argv[1] in ("bootout", "print"):
            raise OSError("launchctl 없음")
        return subprocess.CompletedProcess(argv, 0)

    unknown = launchd.uninstall(apply=True, home=home, runner=broken)
    assert unknown["status"] == "FAILED" and unknown["loaded_after"] is None
    assert launchd.plist_path(home).is_file()


def test_uninstall_when_not_loaded_removes_only_own_plist(tmp_path):
    home, lc = tmp_path / "home", Launchctl()
    launchd.install(sys.executable, tmp_path, apply=True, home=home, runner=lc)
    lc.loaded = False  # 이미 내려가 있음(bootout 이 '없음'으로 실패해도 결과는 해제됨)
    out = launchd.uninstall(apply=True, home=home, runner=lc)
    assert out["status"] == "OK" and not launchd.plist_path(home).exists()


# ── 검증자 r2 정정: launchctl 조회 오류 ≠ 서비스 없음(F4 잔여) ─────────────────


@pytest.mark.parametrize(
    "probe, status, after",
    [
        (113, "OK", False),  # 서비스 없음(맥북 실측 응답 코드)
        (0, "FAILED", True),
        (1, "FAILED", None),  # 조회 오류(예: Operation not permitted)
        (112, "FAILED", None),  # 잘못된 도메인
        (OSError, "FAILED", None),
    ],
)
def test_uninstall_ok_only_when_service_absence_is_confirmed(
    tmp_path, probe, status, after
):
    home = tmp_path / "home"
    p = launchd.plist_path(home)
    p.parent.mkdir(parents=True)
    p.write_bytes(b"plist")

    def lc(argv, **kw):
        if argv[1] == "bootout":
            return subprocess.CompletedProcess(argv, 5)
        if probe is OSError:
            raise OSError("launchctl 실행 불가")
        err = b"Operation not permitted" if probe == 1 else b""
        return subprocess.CompletedProcess(argv, probe, b"", err)

    out = launchd.uninstall(apply=True, home=home, runner=lc)
    assert out["status"] == status and out["loaded_after"] is after
    assert p.exists() is (status == "FAILED")


def test_check_and_status_show_unknown_registration_not_inactive(tmp_path):
    def failing(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, b"", b"Operation not permitted")

    st = launchd.check(sys.executable, tmp_path, home=tmp_path / "h", runner=failing)
    assert st["loaded"] is None and st["last_exit"] is None
    ev = {
        "evaluated_at": "2026-10-29T01:00:00.000000Z",
        "day": "2026-10-29",
        "next_slot": "2026-10-29T03:05:00.000000Z",
        "predict": {"state": "BEFORE_WINDOW", "attempts": 0, "need": None},
        "archive": {"state": "ARCHIVED", "attempts": 0},
        "backup": {"state": "WAITING_TARGET"},
        "launchd": st,
    }
    assert "등록 확인 불가" in ST.render(ev)
    ev["launchd"] = launchd.check(
        sys.executable, tmp_path, home=tmp_path / "h", runner=Launchctl()
    )
    assert ev["launchd"]["loaded"] is False
    line = ST.render(ev).splitlines()[1]
    assert "확인 불가" not in line and "활성" not in line


def test_cli_uninstall_failure_exits_nonzero(monkeypatch, capsys):
    from scripts import run_forward_auto as cli

    monkeypatch.setattr(
        cli.launchd, "uninstall", lambda apply: {"status": "FAILED", "path": "x"}
    )
    assert cli.main(["uninstall", "--apply"]) == 2
    assert '"status": "FAILED"' in capsys.readouterr().out
    monkeypatch.setattr(cli.launchd, "uninstall", lambda apply: {"status": "OK"})
    assert cli.main(["uninstall", "--apply"]) == 0


# ── 독립 검토(r2 정정 뒤) 같은 종류: 알림 실패 · caffeinate 즉시 종료 ─────────────


def test_failed_notification_is_not_marked_sent_and_is_retried(tmp_path):
    paths = ST.Paths(tmp_path, tmp_path, tmp_path, tmp_path / "ops")
    ev = {
        "day": "2026-10-29",
        "next_slot": "2026-10-29T05:35:00.000000Z",
        "predict": {"state": "ATTEMPTS_EXHAUSTED", "need": {"D": "2026-10-28"}},
        "archive": {},
        "past": [],
    }
    first = ST.send_new(paths, ev, lambda msg: "NOTIFY_FAILED")
    assert first and first[0]["result"] == "NOTIFY_FAILED"
    again = ST.send_new(paths, ev, lambda msg: "REQUESTED_DELIVERY_UNKNOWN")
    assert [x["result"] for x in again] == ["REQUESTED_DELIVERY_UNKNOWN"]
    assert ST.send_new(paths, ev, lambda msg: "REQUESTED_DELIVERY_UNKNOWN") == []


def test_awake_is_false_when_caffeinate_exited_immediately():
    class Exited:
        def poll(self):
            return 1

    with runner.awake(popen=lambda *a, **k: Exited()) as aw:
        assert aw is False
