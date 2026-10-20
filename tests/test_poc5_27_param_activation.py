"""POC5-27 — PC 에서 OCI 운영 기준(PARAM) 실제 활성화(PLAN §4 · §6 · 판정 §1 ~ §6).

OCI 쪽은 PC 와 다른 임시 DB(임시 home)다. 원격 읽기 문자열은 로컬 bash 로 진짜 실행하고, OCI 쪽
도구는 같은 임시 DB 로 프로세스 안에서 돌린다. 실제 OCI · 라이브 DB 에는 닿지 않는다.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_three_push_param as param_api
from app import oci_startup_status as oss
from app import runtime_param_store as store
from app import three_push_param_activation as act
from app.oci_status_rows import _compare_values
from app.three_push_runtime_param import build_manual_seed_param
from scripts import apply_three_push_param_oci as tool

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "apply_three_push_param_oci.py"
B_KINDS = ["market_briefing", "holdings_briefing"]  # 기본 4종과 2개 다름


def _param(**kw):
    return build_manual_seed_param(**kw).to_dict()


def _home(tmp_path) -> Path:
    home = tmp_path / "oci_home"
    (home / "state" / "runtime").mkdir(parents=True)
    (home / "state" / "three_push" / "params").mkdir(parents=True)
    return home


def _db(home: Path) -> Path:
    return home / "state" / "runtime" / "runtime_state.sqlite"


def _seed(db: Path, param: dict) -> str:
    vid, _, _ = store.create_param_version(param, db_path=db)
    store.activate_param_version(vid, activated_by="seed_for_test", db_path=db)
    return vid


def _versions(db: Path) -> int:
    with store.connection(db) as con:
        return con.execute("SELECT COUNT(*) FROM runtime_param_version").fetchone()[0]


def _digest(db: Path) -> tuple[str, int]:
    return hashlib.sha256(db.read_bytes()).hexdigest(), os.stat(db).st_mtime_ns


def _run_tool(fn, *a, **k) -> tuple[int, dict, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(*a, **k)
    out = buf.getvalue()
    return code, act._parse_result(out) or {}, out


def _write(path: Path, d: dict) -> Path:
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return path


# ── OCI 쪽 도구(프로세스 안 · 임시 DB) ─────────────────────────────────────────


def test_tool_same_values_writes_nothing(tmp_path):
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    before_ptr = store.get_active_pointer(db)
    digest = _digest(db)
    req = _param(enabled_push_kinds=list(reversed(_param()["enabled_push_kinds"])))
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["n"]) == (0, "SAME", 14)
    assert (
        store.get_active_pointer(db) == before_ptr
        and before_ptr["active_param_version_id"] == vid
    )
    assert _versions(db) == 1 and _digest(db) == digest  # 새 버전 0 · 포인터 그대로


def test_tool_activates_requested_values_and_reads_back(tmp_path):
    db = _db(_home(tmp_path))
    _seed(db, _param())
    req = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"]) == (0, "ACTIVATED")
    ptr = store.get_active_pointer(db)
    assert ptr["active_param_version_id"] == req["param_id"] == res["version_id"]
    assert ptr["activated_by"] == "pc_param_apply"
    assert _versions(db) == 2
    active = store.read_active_param_dict(db)
    assert set(active["enabled_push_kinds"]) == set(B_KINDS)
    rows = act._rows_to_values(res["rows"])
    assert _compare_values(act.pc_values(req), rows)[1] == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("safety_policy"),
        lambda d: d.update(enabled_push_kinds=["not_a_kind"]),
        lambda d: d["runtime_policy"].update(token="x"),
        lambda d: d.update(schema_version="v0"),
    ],
)
def test_tool_validation_failure_keeps_pointer(tmp_path, mutate):
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    req = _param(enabled_push_kinds=B_KINDS)
    mutate(req)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["stage"], res["previous_kept"]) == (
        2,
        "FAILED",
        "validate",
        True,
    )
    assert store.get_active_pointer(db)["active_param_version_id"] == vid
    assert _versions(db) == 1


def test_tool_publishes_only_the_content_pc_sent(tmp_path):
    """--expect-sha256: 전달된 파일이 PC 가 보낸 바이트와 다르면 쓰기 전에 실패(다른 값 대신 발행 없음)."""
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    path = _write(tmp_path / "r.json", _param(enabled_push_kinds=B_KINDS))
    other = hashlib.sha256(b"what the PC sent").hexdigest()
    code, res, _ = _run_tool(tool.apply_file, path, db=db, expect_sha256=other)
    assert (code, res["result"], res["stage"], res["error"]) == (
        2,
        "FAILED",
        "validate",
        "content_mismatch",
    )
    assert store.get_active_pointer(db)["active_param_version_id"] == vid
    assert _versions(db) == 1
    same = hashlib.sha256(path.read_bytes()).hexdigest()
    code, res, _ = _run_tool(tool.apply_file, path, db=db, expect_sha256=same)
    assert (code, res["result"]) == (0, "ACTIVATED")


def _hold_writer_lock(db: Path):
    """다른 실행이 잡고 있는 잠금(같은 파일 · 다른 열린 파일)."""
    import fcntl

    path = tool._lock_path(db)
    assert path == db.parents[1] / "three_push" / "params" / ".param_apply.lock"
    fh = open(path, "a", encoding="utf-8")
    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fh


def test_tool_does_not_overlap_a_running_apply(tmp_path):
    """앞 실행이 잠금을 잡고 있으면 발행 · 복구 모두 손대지 않고 UNCONFIRMED(busy) — 기다리지 않는다."""
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    other, _, _ = store.create_param_version(
        _param(enabled_push_kinds=B_KINDS), db_path=db
    )
    before = _digest(db)
    fh = _hold_writer_lock(db)
    try:
        req = _write(tmp_path / "r.json", _param(enabled_push_kinds=B_KINDS))
        code, res, _ = _run_tool(tool.apply_file, req, db=db)
        assert (code, res["result"], res["stage"]) == (3, "UNCONFIRMED", "busy")
        code, res, _ = _run_tool(tool.activate_version, other, db=db)
        assert (code, res["result"], res["stage"]) == (3, "UNCONFIRMED", "busy")
        assert _digest(db) == before
    finally:
        fh.close()
    code, res, _ = _run_tool(tool.apply_file, req, db=db)  # 풀리면 그대로 진행
    assert res["result"] == "ACTIVATED"
    assert store.get_active_pointer(db)["active_param_version_id"] != vid


def test_tool_empty_policy_is_rejected_before_switch(tmp_path):
    """빈 정책은 검증을 통과하지만 DB 로 다시 만들면 키가 없어 러너가 멈춘다 — 전환 전에 거른다."""
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    req = _param()
    req["evidence_policy"] = {}
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["stage"]) == (2, "FAILED", "candidate")
    assert res["error"].startswith("candidate_invalid")
    assert store.get_active_pointer(db)["active_param_version_id"] == vid


def test_tool_missing_file_and_db(tmp_path):
    db = _db(_home(tmp_path))
    code, res, _ = _run_tool(tool.apply_file, tmp_path / "none.json", db=db)
    assert (code, res["result"], res["error"]) == (2, "FAILED", "missing_file")
    req = _write(tmp_path / "r.json", _param())
    code, res, _ = _run_tool(tool.apply_file, req, db=db)
    assert (res["result"], res["stage"], res["error"]) == (
        "FAILED",
        "precheck",
        "db_missing",
    )
    assert not db.exists()  # 새 DB 를 만들지 않는다


def test_tool_activate_error_with_pointer_kept_is_failed(tmp_path, monkeypatch):
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())

    def _boom(*a, **k):
        raise RuntimeError("locked")

    monkeypatch.setattr(store, "activate_param_version", _boom)
    req = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["stage"], res["previous_kept"]) == (
        2,
        "FAILED",
        "activate",
        True,
    )
    assert store.get_active_pointer(db)["active_param_version_id"] == vid


@pytest.mark.parametrize("moved_to", ["requested", "other"])
def test_tool_activate_error_after_pointer_moved_is_not_failed(
    tmp_path, monkeypatch, moved_to
):
    """전환 함수가 오류를 냈어도 포인터가 움직였으면 '기존 값 그대로'(FAILED)라고 하지 않는다.

    요청 버전으로 움직였으면 다시 읽어 확인(ACTIVATED) · 다른 버전이면 확인 불가(UNCONFIRMED).
    """
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    other, _, _ = store.create_param_version(
        _param(enabled_push_kinds=["market_briefing"]), db_path=db
    )
    real = store.activate_param_version

    def _switch_then_boom(version_id, **k):
        real(version_id if moved_to == "requested" else other, **k)
        raise RuntimeError("late error")

    monkeypatch.setattr(store, "activate_param_version", _switch_then_boom)
    req = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    if moved_to == "requested":
        assert (code, res["result"]) == (0, "ACTIVATED")
    else:
        assert (code, res["result"], res["stage"]) == (3, "UNCONFIRMED", "activate")
    assert store.get_active_pointer(db)["active_param_version_id"] != vid


def _flaky_readback(monkeypatch, *, wrong=None, fail_at=None):
    """`_read_active` 를 n 번째 호출에서만 바꾼다(1 = 적용 전 읽기 · 2 = 전환 뒤 다시 읽기)."""
    real = tool._read_active
    calls = {"n": 0}

    def fake(db):
        calls["n"] += 1
        if calls["n"] == fail_at:
            raise RuntimeError("read failed")
        if wrong is not None and calls["n"] == 2:
            return wrong
        return real(db)

    monkeypatch.setattr(tool, "_read_active", fake)


def test_tool_readback_mismatch_rolls_back_and_confirms_previous(tmp_path, monkeypatch):
    db = _db(_home(tmp_path))
    a = _param()
    vid_a = _seed(db, a)
    _flaky_readback(monkeypatch, wrong=_param(enabled_push_kinds=["market_briefing"]))
    req = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["stage"], res["previous_kept"]) == (
        2,
        "FAILED",
        "readback",
        True,
    )
    ptr = store.get_active_pointer(db)
    assert ptr["active_param_version_id"] == vid_a
    assert ptr["activated_by"] == "pc_param_apply:rollback"


def test_tool_readback_error_is_unconfirmed_without_rollback(tmp_path, monkeypatch):
    db = _db(_home(tmp_path))
    _seed(db, _param())
    _flaky_readback(monkeypatch, fail_at=2)
    req = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["stage"]) == (3, "UNCONFIRMED", "readback")
    # 단순 읽기 실패로 되돌리지 않는다 — 실제로는 전환돼 있다.
    assert store.get_active_pointer(db)["active_param_version_id"] == req["param_id"]


def test_tool_rollback_not_confirmed_is_unconfirmed(tmp_path, monkeypatch):
    db = _db(_home(tmp_path))
    _seed(db, _param())
    wrong = _param(enabled_push_kinds=["market_briefing"])
    real = tool._read_active
    calls = {"n": 0}

    def fake(dbp):
        calls["n"] += 1
        return wrong if calls["n"] >= 2 else real(dbp)  # 되돌린 뒤에도 다른 값

    monkeypatch.setattr(tool, "_read_active", fake)
    req = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "r.json", req), db=db)
    assert (code, res["result"], res["stage"]) == (3, "UNCONFIRMED", "rollback")


def test_tool_list_is_read_only_and_marks_active(tmp_path):
    db = _db(_home(tmp_path))
    a = _param()
    vid_a = _seed(db, a)
    b = _param(enabled_push_kinds=B_KINDS)
    vid_b, _, _ = store.create_param_version(b, db_path=db)
    digest = _digest(db)
    code, res, out = _run_tool(tool.list_versions, db)
    assert (code, res["result"], res["count"]) == (0, "LIST", 2)
    assert f"* {vid_a}" in out and "지금 활성값과 다른 값 0개" in out
    assert f"  {vid_b}" in out and "지금 활성값과 다른 값 2개" in out
    assert _digest(db) == digest  # mode=ro


def test_tool_restore_activates_existing_version(tmp_path):
    db = _db(_home(tmp_path))
    vid_a = _seed(db, _param())
    b = _param(enabled_push_kinds=B_KINDS)
    code, res, _ = _run_tool(tool.apply_file, _write(tmp_path / "b.json", b), db=db)
    assert res["result"] == "ACTIVATED"
    code, res, _ = _run_tool(tool.activate_version, vid_a, db=db)
    assert (code, res["result"]) == (0, "ACTIVATED")
    ptr = store.get_active_pointer(db)
    assert (ptr["active_param_version_id"], ptr["activated_by"]) == (
        vid_a,
        "operator_restore",
    )
    assert _versions(db) == 2  # 새 버전을 만들지 않는다
    code, res, _ = _run_tool(tool.activate_version, vid_a, db=db)
    assert (code, res["result"]) == (0, "SAME")
    code, res, _ = _run_tool(tool.activate_version, "param-none", db=db)
    assert (code, res["result"], res["error"]) == (2, "FAILED", "unknown_version")


def test_tool_restore_rejects_version_the_runner_cannot_read(tmp_path):
    """복구도 발행과 같은 후보 검사 — 러너가 못 읽을 버전(빈 정책)으로 바꾸지 않는다."""
    db = _db(_home(tmp_path))
    vid = _seed(db, _param())
    broken = _param()
    broken["evidence_policy"] = {}
    bad, _, _ = store.create_param_version(broken, db_path=db)
    code, res, _ = _run_tool(tool.activate_version, bad, db=db)
    assert (code, res["result"], res["stage"]) == (2, "FAILED", "candidate")
    assert store.get_active_pointer(db)["active_param_version_id"] == vid


@pytest.mark.parametrize(
    "a_kw, b_mut",
    [
        ({}, None),
        (
            {},
            lambda d: d.update(
                enabled_push_kinds=list(reversed(d["enabled_push_kinds"]))
            ),
        ),
        ({}, lambda d: d.update(enabled_push_kinds=B_KINDS)),
        ({}, lambda d: d["safety_policy"].update(block_secret_exposure=False)),
        ({}, lambda d: d["runtime_policy"].update(data_unavailable_behavior="skip")),
    ],
)
def test_tool_comparison_matches_pc_row(a_kw, b_mut):
    """도구의 유효값 비교 = PC ① 행 비교(`_compare_values`) — 같은 수 · 같은 다름."""
    a, b = _param(**a_kw), _param()
    if b_mut:
        b_mut(b)
    assert tool._diff(tool._effective(a), tool._effective(b)) == _compare_values(
        act.pc_values(a), act.pc_values(b)
    )


# ── 업로드 위치에서 실행하는 계약(원격 실행 계약 시험과 같은 방식) ─────────────────


def test_tool_runs_from_upload_path_with_project_root(tmp_path):
    deep = tmp_path / "state" / "three_push" / "params"
    deep.mkdir(parents=True)
    up = deep / ".apply_three_push_param_oci.py"
    shutil.copy(TOOL, up)
    r = subprocess.run(
        [
            sys.executable,
            str(up),
            "--json",
            str(tmp_path / "none.json"),
            "--project-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "ModuleNotFoundError" not in r.stderr
    assert r.returncode == 2 and "missing_file" in r.stdout
    r = subprocess.run(
        [sys.executable, str(up), "--json", "x.json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode != 0 and "--project-root" in r.stderr


def test_tool_source_contract():
    src = TOOL.read_text(encoding="utf-8")
    code_lines = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("parents[" in ln for ln in code_lines)
    assert "_bootstrap(" in src
    # OCI 에 이미 있는 저장 함수만 쓴다(새 app 모듈을 import 하지 않는다).
    imports = {
        ln.split(" import ")[0].split()[-1]
        for ln in src.splitlines()
        if " import " in ln and ln.strip().startswith("from app")
    }
    assert imports <= {"app.runtime_param_store", "app.three_push_runtime_param"}


# ── PC 적용 순서(가짜 원격 · 읽기는 로컬 bash 로 진짜) ─────────────────────────


class FakeRemote:
    """명령별 기록 · 원격 읽기는 진짜 블록을 bash 로 · 도구 실행은 같은 임시 DB 로 프로세스 안."""

    def __init__(self, tmp_path, home: Path, *, deliver_ok=True, scp_rc=0):
        self.home, self.db = home, _db(home)
        self.params = home / "state" / "three_push" / "params"
        self.calls: list[tuple] = []
        self.deliver_ok, self.scp_rc = deliver_ok, scp_rc
        self.read_fail = False
        self.tool_mode = (
            "real"  # real | ambiguous_after_switch | ambiguous_no_run | fake:<json>
        )
        self.pc_json: Path | None = None
        self.t = 0.0

    def remote(self) -> act.Remote:
        return act.Remote(
            ssh=self.ssh,
            scp=self.scp,
            deliver=self.deliver,
            remote_dir=str(self.params),
            clock=lambda: self.t,
            sleep=lambda s: self.calls.append(("sleep", s)),
        )

    def ssh(self, cmd: str, timeout: float):
        if "sqlite3.connect" in cmd:  # 읽기 블록
            self.calls.append(("read",))
            if self.read_fail:
                return 255, ""
            out = subprocess.run(
                ["bash", "-c", cmd], capture_output=True, text=True, timeout=30
            )
            return out.returncode, out.stdout
        if cmd.startswith("rm -f "):
            self.calls.append(("rm", cmd))
            return 0, ""
        assert "venv/bin/python" in cmd and "--json" in cmd and "--project-root" in cmd
        self.calls.append(("tool", cmd))
        if self.tool_mode.startswith("fake:"):
            return 2, "RESULT " + self.tool_mode[5:]
        if self.tool_mode == "ambiguous_no_run":
            return 255, ""
        argv = shlex.split(cmd.split(" && ", 1)[1])
        json_path = Path(argv[argv.index("--json") + 1])
        exp = (
            argv[argv.index("--expect-sha256") + 1]
            if "--expect-sha256" in argv
            else None
        )
        code, _, out = _run_tool(
            tool.apply_file, json_path, db=self.db, expect_sha256=exp
        )
        if self.tool_mode == "ambiguous_after_switch":
            return 255, ""
        return code, out

    def scp(self, local: Path, remote_path: str, timeout: float) -> int:
        self.calls.append(("scp", remote_path))
        return self.scp_rc

    def deliver(self, timeout: float) -> bool:
        self.calls.append(("deliver",))
        if self.deliver_ok and self.pc_json is not None:
            shutil.copy(self.pc_json, self.params / "latest_runtime_param.json")
        return self.deliver_ok

    def writes(self) -> list[tuple]:
        return [c for c in self.calls if c[0] in ("deliver", "scp", "tool", "rm")]


@pytest.fixture
def oci(tmp_path, monkeypatch):
    home = _home(tmp_path)
    monkeypatch.setattr(act, "REMOTE_ROOT", str(home))
    fake = FakeRemote(tmp_path, home)
    return fake


def _pc(tmp_path, fake: FakeRemote, d: dict) -> dict:
    fake.pc_json = _write(tmp_path / "pc_latest.json", d)
    return d


def test_activate_same_values_no_remote_write(tmp_path, oci):
    _seed(oci.db, _param())
    digest = _digest(oci.db)
    out = act.activate(_pc(tmp_path, oci, _param()), oci.remote())
    assert (out.result, out.stage, out.n, out.diff) == (
        act.ACTIVE_SAME,
        "precheck",
        14,
        0,
    )
    assert oci.writes() == [] and _digest(oci.db) == digest
    assert out.values is not None and out.read_at


def test_activate_different_values_publishes_and_confirms(tmp_path, oci):
    _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    out = act.activate(pc, oci.remote())
    assert (out.result, out.stage, out.diff) == (act.ACTIVATED, "apply", 0)
    kinds = [c[0] for c in oci.writes()]
    assert kinds == ["deliver", "scp", "tool", "rm"]
    tool_cmd = next(c[1] for c in oci.calls if c[0] == "tool")
    assert tool_cmd == (
        f"cd {oci.home} && venv/bin/python {oci.params}/.apply_three_push_param_oci.py "
        f"--json {oci.params}/latest_runtime_param.json --project-root {oci.home}"
    )
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == pc["param_id"]
    # 원격 명령에 러너 · cron · 발송이 없다.
    for c in oci.calls:
        text = " ".join(str(x) for x in c)
        assert "run_three_push_runtime_oci" not in text and "crontab" not in text


def test_activate_precheck_read_failure_writes_nothing(tmp_path, oci):
    _seed(oci.db, _param())
    oci.read_fail = True
    out = act.activate(
        _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS)), oci.remote()
    )
    assert (out.result, out.stage, out.values) == (act.FAILED, "precheck", None)
    assert oci.writes() == []


@pytest.mark.parametrize(
    "deliver_ok, scp_rc, stage, expect",
    [(False, 0, "deliver", ["deliver"]), (True, 1, "upload", ["deliver", "scp", "rm"])],
)
def test_activate_failure_before_switch_keeps_previous(
    tmp_path, oci, deliver_ok, scp_rc, stage, expect
):
    vid = _seed(oci.db, _param())
    oci.deliver_ok, oci.scp_rc = deliver_ok, scp_rc
    out = act.activate(
        _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS)), oci.remote()
    )
    assert (out.result, out.stage) == (act.FAILED, stage)
    assert [c[0] for c in oci.writes()] == expect
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == vid


def test_activate_tool_failed_with_previous_kept(tmp_path, oci):
    vid = _seed(oci.db, _param())
    oci.tool_mode = "fake:" + json.dumps(
        {"result": "FAILED", "stage": "candidate", "previous_kept": True}
    )
    out = act.activate(
        _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS)), oci.remote()
    )
    assert (out.result, out.stage) == (act.FAILED, "apply:candidate")
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == vid


def test_activate_does_not_trust_tool_report_with_other_values(tmp_path, oci):
    """도구가 ACTIVATED 라고 해도 함께 온 값이 요청과 다르면 믿지 않고 읽기만 다시(성공 판정 = 실제 값)."""
    vid = _seed(oci.db, _param())
    wrong_rows = tool._rows(_param(enabled_push_kinds=["market_briefing"]))
    oci.tool_mode = "fake:" + json.dumps({"result": "ACTIVATED", "rows": wrong_rows})
    out = act.activate(
        _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS)), oci.remote()
    )
    assert out.result == act.UNCONFIRMED  # 실제 OCI 는 그대로(가짜 보고)
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == vid


def test_activate_content_mismatch_fails_before_any_db_write(tmp_path, oci):
    """전달된 파일이 PC 가 보낸 내용과 다르면 도구가 쓰기 전에 거른다 → 적용 실패(기존 값 그대로)."""
    vid = _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    out = act.activate(pc, oci.remote(), expect_sha256="0" * 64)
    assert (out.result, out.stage) == (act.FAILED, "apply:validate")
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == vid
    assert _versions(oci.db) == 1


def test_activate_while_previous_run_holds_lock_reads_instead(tmp_path, oci):
    """앞 실행이 OCI 에서 아직 돌면 도구는 busy · PC 는 읽기만 다시 → 요청값이 아니면 확인 불가."""
    vid = _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    fh = _hold_writer_lock(oci.db)
    try:
        out = act.activate(pc, oci.remote())
    finally:
        fh.close()
    assert out.result == act.UNCONFIRMED
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == vid
    assert _versions(oci.db) == 1


def test_tool_command_quotes_every_path(oci):
    """원격 명령의 경로는 따옴표로 감싼다 — 공백 · ; 가 있어도 한 인자로 남는다."""
    remote = oci.remote()
    remote.remote_dir = "/srv/a b;touch x"
    cmd = act._tool_command(remote, "/srv/a b;touch x/.t.py", "ab" * 32)
    cd, rest = cmd.split(" && ", 1)
    assert shlex.split(cd) == ["cd", act.REMOTE_ROOT]
    argv = shlex.split(rest)
    assert argv[1] == "/srv/a b;touch x/.t.py"
    assert (
        argv[argv.index("--json") + 1] == "/srv/a b;touch x/latest_runtime_param.json"
    )
    assert argv[argv.index("--expect-sha256") + 1] == "ab" * 32


def test_activate_ambiguous_but_switched_is_confirmed_by_read(tmp_path, oci):
    _seed(oci.db, _param())
    oci.tool_mode = "ambiguous_after_switch"
    out = act.activate(
        _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS)), oci.remote()
    )
    assert (out.result, out.stage) == (act.ACTIVATED, "reconcile")
    assert [c for c in oci.calls if c[0] == "tool"] and len(
        [c for c in oci.calls if c[0] == "tool"]
    ) == 1


def test_activate_ambiguous_and_unreadable_is_unconfirmed_not_failed(tmp_path, oci):
    _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    oci.tool_mode = "ambiguous_after_switch"
    remote = oci.remote()
    real_ssh = remote.ssh

    def ssh(cmd, timeout):
        if "sqlite3.connect" in cmd and any(c[0] == "tool" for c in oci.calls):
            oci.calls.append(("read",))
            return 255, ""
        return real_ssh(cmd, timeout)

    remote.ssh = ssh
    out = act.activate(pc, remote)
    assert (out.result, out.values) == (act.UNCONFIRMED, None)
    # 실제로는 전환돼 있다 — '기존 값 유지'로 보고하지 않았다 · 자동 재적용 없음.
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == pc["param_id"]
    assert len([c for c in oci.calls if c[0] == "tool"]) == 1
    assert [c[1] for c in oci.calls if c[0] == "sleep"] == [2.0, 5.0]


def test_activate_ambiguous_with_old_values_is_unconfirmed(tmp_path, oci):
    vid = _seed(oci.db, _param())
    oci.tool_mode = "ambiguous_no_run"
    out = act.activate(
        _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS)), oci.remote()
    )
    assert (
        out.result == act.UNCONFIRMED
    )  # 이전 값이 읽혀도 '기존 값 유지'로 단정하지 않는다
    assert store.get_active_pointer(oci.db)["active_param_version_id"] == vid


def test_rerun_after_unconfirmed_reads_first_and_writes_nothing(tmp_path, oci):
    _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    oci.tool_mode = "ambiguous_after_switch"
    oci.read_fail = False
    first = act.activate(pc, oci.remote())
    assert first.result in (act.ACTIVATED, act.UNCONFIRMED)
    oci.calls.clear()
    again = act.activate(pc, oci.remote())
    assert again.result == act.ACTIVE_SAME and oci.writes() == []


def test_activate_budget_stops_before_any_write(tmp_path, oci):
    _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    remote = oci.remote()
    ticks = iter([0.0, 60.0])
    remote.clock = lambda: next(ticks, 60.0)
    out = act.activate(pc, remote)
    assert (out.result, out.stage) == (act.FAILED, "budget")
    assert oci.writes() == []


def test_activate_unexpected_error_after_tool_start_is_unconfirmed(
    tmp_path, oci, monkeypatch
):
    _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))

    def _boom(out):
        raise RuntimeError("parse")

    monkeypatch.setattr(act, "_parse_result", _boom)
    out = act.activate(pc, oci.remote())
    assert (out.result, out.stage) == (act.UNCONFIRMED, "error")


def test_activate_unexpected_error_before_tool_is_failed(tmp_path, oci, monkeypatch):
    _seed(oci.db, _param())
    pc = _pc(tmp_path, oci, _param(enabled_push_kinds=B_KINDS))
    remote = oci.remote()

    def _boom(*a):
        raise RuntimeError("scp")

    remote.scp = _boom
    out = act.activate(pc, remote)
    assert (out.result, out.stage) == (act.FAILED, "error")


# ── API ─────────────────────────────────────────────────────────────────────


FORBIDDEN_IN_RESPONSE = (
    "param-",
    "ssh",
    "scp",
    "/home/",
    "latest_runtime_param",
    "venv",
)


@pytest.fixture
def client():
    from app.api import app

    return TestClient(app)


@pytest.fixture
def api_oci(tmp_path, oci, monkeypatch):
    """API 가 쓰는 원격을 가짜로 · PC 쪽 sync 는 가짜 전달로 · ① 캐시는 기동 때 값."""
    monkeypatch.setattr(act, "default_remote", lambda deliver: oci.remote())
    oci.pc_json = param_api._LATEST_PATH
    snap = oss.OciStartupSnapshot(
        checked_at="2026-10-20T00:00:05+00:00",
        reachable=True,
        overall="OPERATING",
        summary_line="ok",
        crontab_active=True,
        jobs=[oss.OciJobStatus("crontab", "SUCCESS", "ok")],
        note="n",
        oci_param_values=None,
        oci_param_read_at=None,
    )
    monkeypatch.setattr(oss, "_snapshot", snap)
    return oci


def _row(client) -> dict:
    return client.get("/oci/startup-status").json()["jobs"][-1]


def test_api_apply_same_values_records_and_updates_row(client, api_oci):
    _seed(api_oci.db, _param())
    r = client.post("/three-push/param/apply")
    body = r.json()
    assert (
        r.status_code == 200
        and body["status"] == "active_same"
        and body["oci_verified"]
    )
    assert (
        body["message"]
        == "OCI 활성값이 이미 지금 기준과 같습니다 (14/14). 새로 바꾼 것은 없습니다."
    )
    assert not any(x in r.text for x in FORBIDDEN_IN_RESPONSE)
    assert (body["compared"], body["differing"]) == (14, 0)
    assert len(body["checked_at"]) == len(
        "2026-10-20 10:12"
    )  # 이 요청에서 읽은 시각(KST)
    assert api_oci.writes() == []
    rec = json.loads(param_api._ACTIVATION_STATUS_PATH.read_text("utf-8"))
    assert set(rec) == {"result", "stage", "n", "diff", "started_at", "completed_at"}
    state = client.get("/three-push/param/state").json()
    assert (state["status"], state["message"]) == (body["status"], body["message"])
    row = _row(client)
    assert row["status"] == "SUCCESS" and "적용 때 확인" in row["detail"]


def test_api_apply_different_values_activates(client, api_oci):
    _seed(api_oci.db, _param(enabled_push_kinds=B_KINDS))  # OCI 는 2종 · PC 는 기본 4종
    r = client.post("/three-push/param/apply")
    body = r.json()
    assert body["status"] == "activated", body
    assert "다시 읽어 같음을 확인했습니다 (14/14)" in body["message"]
    assert not any(x in r.text for x in FORBIDDEN_IN_RESPONSE)
    active = store.read_active_param_dict(api_oci.db)
    assert len(active["enabled_push_kinds"]) == 4
    # PC 가 보낸 JSON 바이트의 SHA-256 을 도구에 넘겨 대조하게 한다(다른 값 대신 발행 없음).
    tool_cmd = next(c[1] for c in api_oci.calls if c[0] == "tool")
    want = hashlib.sha256(param_api._LATEST_PATH.read_bytes()).hexdigest()
    assert f"--expect-sha256 {want}" in tool_cmd
    assert _row(client)["status"] == "SUCCESS"


def test_api_apply_unconfirmed_marks_row_unknown(client, api_oci):
    _seed(api_oci.db, _param(enabled_push_kinds=B_KINDS))
    api_oci.tool_mode = "ambiguous_no_run"
    body = client.post("/three-push/param/apply").json()
    assert body["status"] == "unconfirmed" and not body["oci_verified"]
    # 확인하지 못했으면 비교 수 · 시각을 채우지 않는다(읽지 않은 값 없음 · 판정 §3).
    assert (body["compared"], body["differing"], body["checked_at"]) == (
        None,
        None,
        None,
    )
    row = _row(client)
    assert row["status"] == "UNKNOWN" and row["detail"].startswith(
        "적용 뒤 OCI 활성값을 확인하지 못함"
    )


def test_api_row_appears_after_apply_even_if_startup_read_failed(
    client, api_oci, monkeypatch
):
    """기동 때 OCI 를 못 읽었어도 적용 요청에서 읽은 값은 ① '운영 기준 활성' 행으로 보인다."""
    from dataclasses import replace

    monkeypatch.setattr(oss, "_snapshot", replace(oss._snapshot, reachable=False))
    jobs = client.get("/oci/startup-status").json()["jobs"]
    assert "param_active" not in [j["job"] for j in jobs]
    _seed(api_oci.db, _param())
    assert client.post("/three-push/param/apply").json()["status"] == "active_same"
    row = _row(client)
    assert row["job"] == "param_active" and row["status"] == "SUCCESS"


def test_api_apply_without_oci_connection_fails_before_write(client, monkeypatch):
    """conftest 가 실제 연결을 막는다 — 연결 준비 실패는 OCI 에 쓰기 전 실패 · ① 은 그대로."""
    before = oss.get_snapshot()
    body = client.post("/three-push/param/apply").json()
    assert body["status"] == "failed"
    assert (body["compared"], body["differing"], body["checked_at"]) == (
        None,
        None,
        None,
    )
    assert body["message"] == (
        "OCI 에 적용하지 못했습니다 (OCI 활성값을 먼저 읽지 못함). 기존 OCI 활성값이 그대로입니다."
    )
    assert oss.get_snapshot() == before


def test_api_apply_busy_when_locked(client):
    assert param_api._APPLY_LOCK.acquire(blocking=False)
    try:
        body = client.post("/three-push/param/apply").json()
    finally:
        param_api._APPLY_LOCK.release()
    assert body["status"] == "busy"


def test_api_state_old_delivery_record_is_not_called_unapplied(client):
    """판정 §5 — 예전 '전달' 기록은 '이전 전달 기록 · 활성화 확인 없음'(미적용으로 단정하지 않음)."""
    param_api._SYNC_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    param_api._SYNC_STATUS_PATH.write_text(
        json.dumps(
            {
                "status": "success",
                "verify_status": "success",
                "completed_at": "2026-10-04T02:09:42+00:00",
            }
        ),
        "utf-8",
    )
    state = client.get("/three-push/param/state").json()
    assert state["status"] == "delivered_only"
    assert state["message"].startswith(
        "이전 전달 기록(2026-10-04 11:09) · 활성화 확인 없음"
    )
    assert "미적용" not in state["message"]
    param_api._SYNC_STATUS_PATH.unlink()
    assert client.get("/three-push/param/state").json()["status"] == "not_applied"
    param_api._ACTIVATION_STATUS_PATH.write_text("{broken", "utf-8")
    assert (
        client.get("/three-push/param/state").json()["status"]
        == "verification_required"
    )
    # 모르는 결과 값은 손상으로 — '기존 값 그대로' 같은 근거 없는 문구를 만들지 않는다.
    param_api._ACTIVATION_STATUS_PATH.write_text(
        json.dumps({"result": "applied", "completed_at": "2026-10-20T01:00:00+00:00"}),
        "utf-8",
    )
    state = client.get("/three-push/param/state").json()
    assert state["status"] == "verification_required"
    assert "그대로" not in state["message"]


_GOOD_RECORD = {
    "result": "active_same",
    "stage": "precheck",
    "n": 14,
    "diff": 0,
    "started_at": "2026-10-20T01:00:00+00:00",
    "completed_at": "2026-10-20T01:00:05+00:00",
}


@pytest.mark.parametrize(
    "broken",
    [
        {"result": []},
        {"result": {}},
        {"result": 1},
        {"result": None},
        {"result": True},
        {"result": "applied"},
        {"stage": []},
        {"stage": {"x": 1}},
        {"n": "14"},
        {"n": [14]},
        {"n": True},
        {"n": -1},
        {"completed_at": []},
        {"completed_at": {}},
        {"completed_at": 5},
    ],
)
def test_api_state_broken_activation_record_is_verification_required(client, broken):
    """검증자 F2 — 기록의 값 종류와 상관없이 손상은 '확인 필요'(HTTP 200 · 예외 · 엉뚱한 문구 없음)."""
    param_api._ACTIVATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    param_api._ACTIVATION_STATUS_PATH.write_text(
        json.dumps({**_GOOD_RECORD, **broken}), "utf-8"
    )
    r = client.get("/three-push/param/state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "verification_required" and not body["oci_verified"]
    assert "그대로" not in body["message"]


def test_api_state_good_activation_record_control(client):
    """대조군 — 우리가 쓰는 꼴(빈 시각 · 비교 수 없음 포함)은 그대로 결과를 보인다."""
    param_api._ACTIVATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    for rec, at in (
        (_GOOD_RECORD, "2026-10-20 10:00"),
        ({**_GOOD_RECORD, "n": None, "completed_at": None}, None),
    ):
        param_api._ACTIVATION_STATUS_PATH.write_text(json.dumps(rec), "utf-8")
        body = client.get("/three-push/param/state").json()
        assert (body["status"], body["applied_at"], body["oci_verified"]) == (
            "active_same",
            at,
            True,
        )


@pytest.mark.parametrize("completed_at", [[], {"a": 1}, 5, "not-a-time"])
def test_api_state_old_delivery_record_with_broken_time_is_200(client, completed_at):
    """예전 전달 기록의 시각이 문자열이 아니어도 상태 조회는 실패하지 않는다('시각 모름')."""
    param_api._SYNC_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    param_api._SYNC_STATUS_PATH.write_text(
        json.dumps({"status": "success", "completed_at": completed_at}), "utf-8"
    )
    r = client.get("/three-push/param/state")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "delivered_only"
    assert r.json()["message"].startswith("이전 전달 기록(시각 모름)")


def test_api_state_while_apply_in_progress_is_busy_not_previous_success(
    client, api_oci, monkeypatch
):
    """검증자 F1 전제 — 적용이 진행 중이면 상태 조회는 지난 성공 기록이 아니라 '적용 중'.

    실제 POST 를 스레드로 띄워 OCI 읽기에서 멈춰 둔 채 GET 을 부른다.
    """
    _seed(api_oci.db, _param())
    param_api._ACTIVATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    param_api._ACTIVATION_STATUS_PATH.write_text(
        json.dumps({**_GOOD_RECORD, "result": "activated"}), "utf-8"
    )
    assert client.get("/three-push/param/state").json()["status"] == "activated"
    entered, release = threading.Event(), threading.Event()
    real_ssh = api_oci.ssh

    def _slow_ssh(cmd, timeout):
        if "sqlite3.connect" in cmd:
            entered.set()
            assert release.wait(30)
        return real_ssh(cmd, timeout)

    api_oci.ssh = _slow_ssh
    box: dict = {}
    worker = threading.Thread(
        target=lambda: box.update(r=client.post("/three-push/param/apply"))
    )
    worker.start()
    try:
        assert entered.wait(30)
        body = client.get("/three-push/param/state").json()
        assert (body["status"], body["oci_verified"]) == ("busy", False)
        assert body["message"] == param_api._BUSY_MESSAGE
    finally:
        release.set()
        worker.join(60)
    assert box["r"].json()["status"] == "active_same"
    assert client.get("/three-push/param/state").json()["status"] == "active_same"


# ── sync: 확인한 뒤에만 교체(판정 §5) ─────────────────────────────────────────


@pytest.fixture
def sync_mod(tmp_path, monkeypatch):
    import app.three_push_runner_common as common

    monkeypatch.setattr(
        common, "load_dotenv_file", lambda *a, **k: None
    )  # .env 를 읽지 않는다
    from scripts import sync_three_push_runtime_param as sync

    latest = _write(tmp_path / "latest_runtime_param.json", _param())
    monkeypatch.setattr(sync, "_LATEST_PATH", latest)
    monkeypatch.setattr(sync, "_SYNC_STATUS_PATH", tmp_path / "sync_status.json")
    monkeypatch.setattr(
        sys, "argv", ["sync", "--ssh-target", "t", "--remote-dir", "/r"]
    )
    return sync


def _run_sync(
    sync, monkeypatch, fail: str | None = None
) -> tuple[list[str], dict, int]:
    seen: list[str] = []

    def fake_run(cmd, timeout=60):
        text = " ".join(cmd)
        step = (
            "verify_upload"
            if "verify_three_push_param_oci.py" in text and cmd[0] == "scp"
            else (
                "verify"
                if "verify_three_push_param_oci.py" in text
                else (
                    "mv"
                    if " mv " in f" {cmd[-1]} " or cmd[-1].startswith("mv ")
                    else "scp" if cmd[0] == "scp" else "mkdir"
                )
            )
        )
        assert "BatchMode=yes" in text and "ConnectTimeout=8" in text
        if step == "verify":  # 교체 전 tmp 파일을 검사한다(최종 파일이 아니라)
            assert cmd[-1].endswith("--path /r/latest_runtime_param.json.tmp")
        seen.append(step)
        return (1, "", "x") if step == fail else (0, "", "")

    monkeypatch.setattr(sync, "_run", fake_run)
    code = 0
    try:
        sync.main()
    except SystemExit as e:
        code = int(e.code or 0)
    return seen, json.loads(sync._SYNC_STATUS_PATH.read_text("utf-8")), code


def test_sync_verifies_tmp_before_rename(sync_mod, monkeypatch):
    seen, rec, code = _run_sync(sync_mod, monkeypatch)
    assert seen == ["mkdir", "scp", "verify_upload", "verify", "mv"]
    assert (rec["status"], rec["verify_status"], rec["upload_status"], code) == (
        "success",
        "success",
        "ok",
        0,
    )


@pytest.mark.parametrize("fail", ["verify_upload", "verify"])
def test_sync_failed_verify_never_renames(sync_mod, monkeypatch, fail):
    seen, rec, code = _run_sync(sync_mod, monkeypatch, fail=fail)
    assert "mv" not in seen and rec["status"] == "failed" and code == 1


def test_sync_missing_verify_script_is_failure(sync_mod, monkeypatch, tmp_path):
    monkeypatch.setattr(sync_mod, "_VERIFY_SCRIPT_LOCAL", tmp_path / "none.py")
    seen, rec, code = _run_sync(sync_mod, monkeypatch)
    assert "mv" not in seen and (rec["status"], rec["verify_status"]) == (
        "failed",
        "skipped",
    )


def test_sync_step_timeout_is_failure_not_crash(sync_mod, monkeypatch):
    """단계 제한 시간을 넘기면 예외로 멈추지 않고 rc 124 → 그 단계 실패로 기록된다."""

    def _slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=k.get("timeout", 1))

    monkeypatch.setattr(sync_mod.subprocess, "run", _slow)
    assert sync_mod._run(["ssh", "t", "true"], timeout=6) == (124, "", "timeout 6s")
    with pytest.raises(SystemExit):
        sync_mod.main()
    rec = json.loads(sync_mod._SYNC_STATUS_PATH.read_text("utf-8"))
    assert rec["status"] == "failed"


def test_sync_uses_same_ssh_key_and_quotes_paths(sync_mod, monkeypatch):
    """전달도 PC 의 다른 OCI 호출과 같은 키(`OCI_SSH_KEY_PATH`) · 원격 경로는 따옴표로."""
    monkeypatch.setenv("OCI_SSH_KEY_PATH", "/keys/oci key")
    monkeypatch.setattr(
        sys, "argv", ["sync", "--ssh-target", "t", "--remote-dir", "/r d"]
    )
    cmds: list[list[str]] = []

    def fake_run(cmd, timeout=60):
        cmds.append(cmd)
        return 0, "", ""

    monkeypatch.setattr(sync_mod, "_run", fake_run)
    sync_mod.main()
    assert len(cmds) == 5
    for cmd in cmds:
        assert cmd[cmd.index("-i") + 1] == "/keys/oci key"
    ssh_cmds = [shlex.split(c[-1]) for c in cmds if c[0] == "ssh"]
    assert ssh_cmds[0] == ["mkdir", "-p", "/r d"]
    assert ssh_cmds[-1] == [
        "mv",
        "/r d/latest_runtime_param.json.tmp",
        "/r d/latest_runtime_param.json",
    ]


def test_sync_step_timeouts_fit_delivery_budget(sync_mod):
    total = (
        sync_mod._TIMEOUT_MKDIR
        + sync_mod._TIMEOUT_SCP
        + sync_mod._TIMEOUT_VERIFY_UPLOAD
        + sync_mod._TIMEOUT_VERIFY
        + sync_mod._TIMEOUT_MV
    )
    assert total < act.DELIVER_TIMEOUT_S
    worst = (
        act.READ_TIMEOUT_S
        + act.DELIVER_TIMEOUT_S
        + act.UPLOAD_TIMEOUT_S
        + act.APPLY_TIMEOUT_S
    )
    assert worst < act.TOTAL_BUDGET_S < 120  # 화면 제한 120초 안


# ── 복구 절차(판정 §4) — 문서의 명령 모양 그대로 격리 루트에서 ─────────────────────


def test_documented_restore_procedure_on_isolated_root(tmp_path):
    """임시 업로드 → --list → 고른 --activate-version → 활성값 확인 → 정리(RESULT 복구 절차).

    OCI 의 `/home/ubuntu/krx_hyungsoo` 대신 격리 루트(`app` 은 저장소 링크 · DB 는 임시)를 쓴다.
    실제 운영 정책은 바꾸지 않는다.
    """
    root = tmp_path / "krx_hyungsoo"
    (root / "state" / "runtime").mkdir(parents=True)
    params = root / "state" / "three_push" / "params"
    params.mkdir(parents=True)
    (root / "app").symlink_to(ROOT / "app")
    (root / "venv" / "bin").mkdir(parents=True)
    (root / "venv" / "bin" / "python").symlink_to(sys.executable)
    db = _db(root)
    vid_a = _seed(db, _param())
    b = _param(enabled_push_kinds=B_KINDS)
    vid_b, _, _ = store.create_param_version(b, db_path=db)
    store.activate_param_version(vid_b, activated_by="seed_for_test", db_path=db)

    up = params / ".apply_three_push_param_oci.py"
    shutil.copy(TOOL, up)  # = scp scripts/apply_three_push_param_oci.py → OCI 임시 경로

    def remote(cmd: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=60
        )

    listed = remote(
        f"cd {root} && venv/bin/python state/three_push/params/.apply_three_push_param_oci.py "
        f"--list --project-root {root}"
    )
    assert listed.returncode == 0, listed.stderr
    assert f"* {vid_b}" in listed.stdout and f"  {vid_a}" in listed.stdout

    restored = remote(
        f"cd {root} && venv/bin/python state/three_push/params/.apply_three_push_param_oci.py "
        f"--activate-version {vid_a} --project-root {root}"
    )
    assert restored.returncode == 0, restored.stderr
    assert act._parse_result(restored.stdout)["result"] == "ACTIVATED"
    ptr = store.get_active_pointer(db)
    assert (ptr["active_param_version_id"], ptr["activated_by"]) == (
        vid_a,
        "operator_restore",
    )

    assert remote(f"rm -f {up}").returncode == 0  # 정리
    assert not up.exists()
