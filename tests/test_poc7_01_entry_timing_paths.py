"""POC7-01 연구 폴더 위치 · 읽기 · 쓰기 경계 시험(검증자 r5 F12 · r6 F13 · 독립 검토 재현) — 합성 봉인 DB 만.

본 시험 파일 `tests/test_poc7_01_entry_timing.py` 의 도우미 · 가짜 봉인 DB fixture · 감사 훅을 쓴다
(KS-10 시험 1,500줄 미만으로 나눔 · 라이브 DB · 실제 연구 폴더를 열지 않음).
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import signal
from pathlib import Path

import pytest

from app.entry_timing import flow as FW
from app.entry_timing import protocol as P
from app.entry_timing import report as RP
from app.entry_timing import study as ST
from app.entry_timing import verify as VR
from app.entry_timing.protocol import CheckRequired, dumps, read_json
from tests import test_poc7_01_entry_timing as M

world = M.world  # 가짜 봉인 DB fixture(본 시험 파일과 같은 것)
NOW, _cfg, _failed, _ok_run = M.NOW, M._cfg, M._failed, M._ok_run
_no_touch, _rewrite_run_json = M._no_touch, M._rewrite_run_json


def test_f13_runs_symlink_refused_before_listing(world):
    tmp_path, db, content = world
    cfg, lock_dir, _out = _ok_run(tmp_path, db, content, "f13_runs")
    runs = lock_dir / "runs"
    away = tmp_path / "away_runs" / "runs"
    away.parent.mkdir()
    runs.rename(away)
    runs.symlink_to(away, target_is_directory=True)  # 검증자 r6 재현 1
    before = _tree(tmp_path)
    with _no_touch(away, runs) as seen:
        with pytest.raises(CheckRequired, match="실제 폴더"):
            VR.verify(cfg, NOW)
        with pytest.raises(CheckRequired, match="실제 폴더"):
            FW.run(cfg, NOW)
        with pytest.raises(CheckRequired, match="실제 폴더"):
            FW.prepare(cfg, NOW, "정정")  # 앞 잠금 runs 를 읽기 전에 거부
    assert seen == [] and _tree(tmp_path) == before  # 밖을 읽지도 쓰지도 않음


# --- 검증자 r5 F12 재현 · 같은 종류 층 ----------------------------------------------


def _tree(base: Path) -> dict:
    """링크를 따라가지 않는 파일 목록(이름 · 링크 여부 · 크기) — 어디에도 쓰지 않았는지 본다."""
    out = {}
    for d, dirs, files in os.walk(base):
        for n in dirs + files:
            q = Path(d) / n
            st = q.lstat()
            out[str(q.relative_to(base))] = (
                q.is_symlink(),
                0 if q.is_dir() else st.st_size,
            )
    return out


def _unsafe(tmp_path, cfg, lock_dir, layer):
    """layer 하나를 연구 폴더 밖을 가리키는 링크로 바꾼다 · 그 설정을 돌려준다."""
    root = Path(cfg.root)
    away = tmp_path / f"away_{layer}"
    away.mkdir()
    if layer == "parent":  # 연구 폴더의 상위 경로가 링크
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        return dataclasses.replace(cfg, root=alias / root.name)
    if layer == "verify":  # 검산 기록 자리만 링크(r5 재현 2)
        (lock_dir / "verify").symlink_to(away, target_is_directory=True)
        return cfg
    if layer == "verify_file":  # 기록 자리가 보통 파일
        (lock_dir / "verify").write_bytes(b"")
        return cfg
    if layer == "verify_dangling":  # 기록 자리가 끊어진 링크
        (lock_dir / "verify").symlink_to(away / "none", target_is_directory=True)
        return cfg
    target = {"lock": lock_dir, "protocol": lock_dir / "protocol.json", "root": root}[
        layer
    ]
    moved = away / target.name
    target.rename(moved)
    target.symlink_to(moved, target_is_directory=moved.is_dir())
    return cfg


@pytest.mark.parametrize(
    "layer",
    ["lock", "protocol", "verify", "verify_file", "verify_dangling", "root", "parent"],
)
def test_f12_unsafe_location_refused_without_any_write(world, layer):
    tmp_path, db, content = world
    cfg, lock_dir, _out = _ok_run(tmp_path, db, content, f"f12_{layer}")
    bad = _unsafe(tmp_path, cfg, lock_dir, layer)
    before = _tree(tmp_path)
    with pytest.raises(CheckRequired):
        VR.verify(bad, NOW)
    with pytest.raises(CheckRequired):
        FW.run(bad, NOW)
    with pytest.raises(CheckRequired):
        FW.prepare(bad, NOW, "정정")
    assert _tree(tmp_path) == before  # 연구 폴더 안팎 어디에도 기록 없음


def test_f12_new_root_under_linked_parent_not_created(world):
    tmp_path, db, content = world
    alias = tmp_path / "alias_new"
    alias.symlink_to(tmp_path, target_is_directory=True)
    cfg = _cfg(tmp_path, db, content, root=alias / "fresh")
    with pytest.raises(CheckRequired, match="심볼릭 링크"):
        FW.prepare(cfg, NOW)
    assert not (tmp_path / "fresh").exists()  # 링크된 상위 밑에 폴더를 만들지 않음


def test_f12_run_lock_file_symlink_refused(world):
    tmp_path, db, content = world
    cfg, _lock_dir, _out = _ok_run(tmp_path, db, content, "f12_lockfile")
    lock_file = Path(cfg.root) / FW.LOCK_NAME
    lock_file.unlink()
    outside = tmp_path / "outside.lock"
    lock_file.symlink_to(outside)
    with pytest.raises(CheckRequired, match="잠금 파일"):
        VR.verify(cfg, NOW)
    assert not outside.exists()


def test_f12_runs_symlink_before_run_refused_before_run_id(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f12_pre")
    lock = FW.prepare(cfg, NOW)
    away = tmp_path / "away_pre"
    away.mkdir()
    (Path(cfg.root) / lock["lock_id"] / "runs").symlink_to(
        away, target_is_directory=True
    )
    with pytest.raises(CheckRequired):
        FW.run(cfg, NOW)
    assert list(away.iterdir()) == []


@pytest.mark.parametrize("ends", ["write", "interrupt"])
def test_f12_runs_swapped_during_run_writes_nothing_outside(world, monkeypatch, ends):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / f"f12_mid{ends}")
    lock = FW.prepare(cfg, NOW)
    runs = Path(cfg.root) / lock["lock_id"] / "runs"
    away = tmp_path / "away_mid" / "runs"
    away.parent.mkdir()
    real = ST.evaluate

    def swap(*a, **k):  # 실행 id 를 정한 뒤 runs 를 밖으로 돌림
        runs.mkdir(exist_ok=True)
        runs.rename(away)
        runs.symlink_to(away, target_is_directory=True)
        if ends == "interrupt":
            raise KeyboardInterrupt
        return real(*a, **k)

    monkeypatch.setattr(ST, "evaluate", swap)
    want = KeyboardInterrupt if ends == "interrupt" else CheckRequired
    with pytest.raises(want):  # 원래 중단이 그대로(FAILED 를 쓸 안전한 자리 없음)
        FW.run(cfg, NOW)
    assert list(away.iterdir()) == []  # 결과 · FAILED 기록 모두 밖에 쓰지 않음


def test_f12_run_dir_swapped_before_name_link_refused(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f12_link")
    lock = FW.prepare(cfg, NOW)
    runs = Path(cfg.root) / lock["lock_id"] / "runs"
    away = tmp_path / "away_link" / "runs"
    away.parent.mkdir()
    real = FW.stage_once

    def stage_then_swap(root, path, data):
        tmp = real(root, path, data)
        if (
            Path(path).name == "run.json"
        ):  # 임시 파일 뒤 · 이름 붙이기 전에 runs 를 밖으로
            runs.rename(away)
            runs.symlink_to(away, target_is_directory=True)
        return tmp

    monkeypatch.setattr(FW, "stage_once", stage_then_swap)
    with pytest.raises(CheckRequired, match="실제 폴더"):
        FW.run(cfg, NOW)
    run_dir = next(away.iterdir())
    assert not (run_dir / "run.json").exists()  # 밖으로 돌린 폴더에 이름을 붙이지 않음
    assert list(
        run_dir.glob(".run.json.*.tmp")
    )  # 정리도 밖을 건드리지 않고 남겨 둠(r6 검토)


@pytest.mark.parametrize("ends", ["record", "error"])
def test_f12_verify_dir_swapped_during_verify_writes_nothing_outside(
    world, monkeypatch, ends
):
    tmp_path, db, content = world
    cfg, lock_dir, _out = _ok_run(tmp_path, db, content, f"f12_v{ends}")
    away = tmp_path / f"away_v{ends}"
    away.mkdir()
    real = VR._verify

    def swap(*a, **k):
        (lock_dir / "verify").rmdir()
        (lock_dir / "verify").symlink_to(away, target_is_directory=True)
        if ends == "error":
            raise RuntimeError("중단")
        return real(*a, **k)

    monkeypatch.setattr(VR, "_verify", swap)
    with pytest.raises(CheckRequired if ends == "record" else RuntimeError):
        VR.verify(cfg, NOW)
    assert list(away.iterdir()) == []


def test_f12_write_once_only_inside_real_root(world):
    tmp_path, _db, _content = world
    root = tmp_path / "f12_w"
    root.mkdir()
    away = tmp_path / "away_w"
    away.mkdir()
    (root / "x").symlink_to(away, target_is_directory=True)
    with pytest.raises(CheckRequired):
        P.write_once(root, root / "x" / "a.json", b"{}")
    with pytest.raises(CheckRequired, match="밖"):
        P.write_once(root, tmp_path / "b.json", b"{}")
    with pytest.raises(CheckRequired, match="'..'"):
        P.write_once(root, root / ".." / "b.json", b"{}")  # 글자로는 안 · 실제로는 위
    assert list(away.iterdir()) == [] and not (tmp_path / "b.json").exists()
    assert P.write_once(root, root / "y" / "c.json", b"{}") and (root / "y").is_dir()


def test_f12_root_swapped_during_run_writes_nothing_outside(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f12_rootmid")
    FW.prepare(cfg, NOW)
    root = Path(cfg.root)
    away = tmp_path / "away_rootmid" / root.name
    away.parent.mkdir()
    real = ST.evaluate

    def swap(*a, **k):  # 실행 중 연구 폴더 자체를 밖으로 돌림
        root.rename(away)
        root.symlink_to(away, target_is_directory=True)
        return real(*a, **k)

    monkeypatch.setattr(ST, "evaluate", swap)
    with pytest.raises(CheckRequired, match="심볼릭 링크"):
        FW.run(cfg, NOW)
    assert not list(away.rglob("runs/*/*"))  # 결과 · FAILED 기록 모두 밖에 쓰지 않음


def test_f12_completed_record_location_rechecked_before_link(world, monkeypatch):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f12_done")
    lock = FW.prepare(cfg, NOW)
    runs = Path(cfg.root) / lock["lock_id"] / "runs"
    away = tmp_path / "away_done" / "runs"
    away.parent.mkdir()
    real = P.stage_once

    def stage_then_swap(root, path, data):
        tmp = real(root, path, data)
        if Path(path).name == "completed.json":  # 완료 기록 임시 파일 뒤 · 이름 전에
            runs.rename(away)
            runs.symlink_to(away, target_is_directory=True)
        return tmp

    monkeypatch.setattr(P, "stage_once", stage_then_swap)
    with pytest.raises(CheckRequired, match="실제 폴더"):
        FW.run(cfg, NOW)
    run_dir = next(away.iterdir())
    assert (run_dir / "run.json").exists() and not (run_dir / "completed.json").exists()


def test_f12_dotdot_after_link_refused_without_any_write(world):
    tmp_path, db, content = world
    cfg, lock_dir, out = _ok_run(tmp_path, db, content, "deep/r")  # 링크 너머 실제 실행
    (tmp_path / "deep" / "sub").mkdir()
    alias = tmp_path / "alias_dd"
    alias.symlink_to(tmp_path / "deep" / "sub", target_is_directory=True)
    bad = dataclasses.replace(
        cfg, root=alias / ".." / "r"
    )  # 글자로는 tmp/r · 실제로는 tmp/deep/r
    before = _tree(tmp_path)
    for call in (
        lambda: VR.verify(bad, NOW),
        lambda: FW.run(bad, NOW),
        lambda: FW.prepare(bad, NOW),
    ):
        with pytest.raises(CheckRequired, match="'..'"):
            call()
    assert _tree(tmp_path) == before


def test_f12_dotdot_cannot_approve_outside_copy(world):
    tmp_path, db, content = world
    cfg, lock_dir, out = _ok_run(tmp_path, db, content, "elsewhere/out")
    shutil.copytree(tmp_path / "elsewhere" / "out", tmp_path / "out", symlinks=True)
    real_cfg = dataclasses.replace(cfg, root=tmp_path / "out")
    (tmp_path / "out" / lock_dir.name / "runs" / out.name / "report.md").write_text("x")
    assert "report_md_rendered" in _failed(
        VR.verify(real_cfg, NOW)
    )  # 실제 폴더 = 불일치
    (tmp_path / "elsewhere" / "sub").mkdir()
    alias = tmp_path / "alias_cp"
    alias.symlink_to(tmp_path / "elsewhere" / "sub", target_is_directory=True)
    bad = dataclasses.replace(cfg, root=alias / ".." / "out")  # 읽기는 깨끗한 밖 사본
    with pytest.raises(CheckRequired, match="'..'"):
        VR.verify(bad, NOW)
    recs = list((tmp_path / "out" / lock_dir.name / "verify").iterdir())
    assert [read_json(p)["status"] for p in recs] == ["MISMATCH"]  # 승인 기록 없음


def test_f12_symlink_loop_root_refused_and_original_error_kept(world, monkeypatch):
    tmp_path, db, content = world
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    looped = _cfg(tmp_path, db, content, root=loop / "out")
    with pytest.raises(CheckRequired, match="링크 고리"):
        FW.prepare(looped, NOW)
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "f12_loopmid")
    FW.prepare(cfg, NOW)
    root = Path(cfg.root)

    def swap(*a, **k):  # 실행 중 연구 폴더를 자기 자신을 가리키는 링크로
        root.rename(tmp_path / "moved_loop")
        root.symlink_to(root)
        raise KeyboardInterrupt

    monkeypatch.setattr(ST, "evaluate", swap)
    with pytest.raises(KeyboardInterrupt):  # 고리가 원래 중단을 가리지 않음
        FW.run(cfg, NOW)


@pytest.mark.parametrize(
    "stray", ["ds_store", "symlink", "no_run_json", "run_json_link", "odd_name"]
)
def test_correction_needs_real_prior_run_folder(world, monkeypatch, stray):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / f"prior_{stray}")
    lock = FW.prepare(cfg, NOW)
    runs = Path(cfg.root) / lock["lock_id"] / "runs"
    runs.mkdir()
    name = "20261122T030000Z_deadbeef"
    if stray == "ds_store":
        (runs / ".DS_Store").write_bytes(b"")
    elif stray == "symlink":
        away = tmp_path / f"away_{stray}"
        (away / "x").mkdir(parents=True)
        (away / "x" / "run.json").write_text("{}")
        (runs / name).symlink_to(away / "x", target_is_directory=True)
    elif stray == "no_run_json":
        (runs / name).mkdir()
    elif stray == "run_json_link":
        (runs / name).mkdir()
        (tmp_path / "outside_run.json").write_text("{}")
        (runs / name / "run.json").symlink_to(tmp_path / "outside_run.json")
    else:  # 실행 id 꼴이 아닌 실제 폴더
        (runs / "notes").mkdir()
        (runs / "notes" / "run.json").write_text("{}")
    real = FW.code_hashes
    monkeypatch.setattr(
        FW, "code_hashes", lambda repo: {**real(repo), "app/entry_timing/flow.py": "x"}
    )  # 코드가 바뀐 상황
    with pytest.raises(CheckRequired, match="실행이 있을 때만"):
        FW.prepare(cfg, NOW, "결함")


def test_f11_hidden_name_with_newline_rejected(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f11_nl")
    (out / f".run.json.{'a' * 32}.tmp\n").write_bytes(
        b""
    )  # 프로그램이 만들 수 없는 이름
    assert _failed(VR.verify(cfg, NOW)) == ["run_dir_files"]


def test_lock_with_malformed_corrects_refused(world):
    tmp_path, db, content = world
    cfg = _cfg(tmp_path, db, content, root=tmp_path / "bad_corr")
    lock = FW.prepare(cfg, NOW)
    p = Path(cfg.root) / lock["lock_id"] / "protocol.json"
    proto = read_json(p)
    proto["corrects"] = "앞 잠금"
    p.unlink()
    p.write_bytes(P.dumps(proto))
    with pytest.raises(CheckRequired, match="정정 칸"):
        VR.verify(cfg, NOW)


def test_f12_outside_lock_anywhere_in_chain_refused(world, monkeypatch):
    tmp_path, db, content = world
    cfg, lock_dir, _out = _ok_run(tmp_path, db, content, "f12_chain")
    real = FW.code_hashes
    monkeypatch.setattr(
        FW, "code_hashes", lambda repo: {**real(repo), "app/entry_timing/flow.py": "x"}
    )  # 코드가 바뀐 상황 → 정정 잠금 · 실행
    FW.prepare(cfg, NOW, "결함")
    FW.run(cfg, NOW)
    away = tmp_path / "away_chain"
    away.mkdir()
    moved = away / lock_dir.name
    lock_dir.rename(moved)
    lock_dir.symlink_to(moved, target_is_directory=True)  # 사슬 앞 잠금만 밖으로
    before = _tree(tmp_path)
    with _no_touch(moved, lock_dir) as seen:
        with pytest.raises(CheckRequired, match="심볼릭 링크"):
            VR.verify(cfg, NOW)
    assert seen == [] and _tree(tmp_path) == before


# --- 검증자 r6 F13 재현 · 같은 종류(확인 뒤에만 읽기) -------------------------------


def test_f13_audit_hook_sees_reads_through_link(tmp_path):
    away = tmp_path / "away"
    away.mkdir()
    (away / "x.json").write_text("{}")
    link = tmp_path / "link"
    link.symlink_to(away, target_is_directory=True)
    with _no_touch(away, link) as seen:
        (link / "x.json").read_bytes()
        list(link.iterdir())
    assert [e for e, _ in seen] == [
        "open",
        "os.listdir",
    ]  # 감시 장치가 실제로 잡는지 대조


@pytest.mark.parametrize("name", sorted(P.RUN_DIR_FILES))
def test_f13_run_file_symlink_never_read(world, name):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, f"f13_{name}")
    copy_ = tmp_path / f"outside_{name}"
    copy_.write_bytes((out / name).read_bytes())  # 바이트까지 같은 밖 사본
    (out / name).unlink()
    (out / name).symlink_to(copy_)  # 검증자 r6 재현 2(report.json) · 다섯 파일 모두
    with _no_touch(copy_, out / name) as seen:
        rec = VR.verify(cfg, NOW)
    assert rec["status"] == "MISMATCH" and "run_dir_files" in _failed(rec)
    assert seen == []  # 밖 파일을 열지 않음


@pytest.mark.parametrize("by_id", [False, True])
def test_f13_run_dir_symlink_never_listed_or_read(world, by_id):
    tmp_path, db, content = world
    cfg, lock_dir, out = _ok_run(tmp_path, db, content, f"f13_dir{by_id}")
    away = tmp_path / f"away_dir{by_id}" / out.name
    away.parent.mkdir()
    out.rename(away)
    out.symlink_to(away, target_is_directory=True)
    with _no_touch(away, out) as seen:
        rec = VR.verify(cfg, NOW, run_id=out.name if by_id else None)
    assert rec["status"] == "MISMATCH" and "paths_real" in _failed(rec)
    assert seen == []  # 목록도 내용도 읽지 않음


def test_f13_hard_link_to_outside_file_not_read(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f13_hard")
    outside = tmp_path / "outside_report.json"
    outside.write_bytes((out / "report.json").read_bytes())
    (out / "report.json").unlink()
    os.link(outside, out / "report.json")  # 같은 바이트 · 밖 파일과 이어진 이름
    failed = _failed(VR.verify(cfg, NOW))
    assert "run_dir_files" in failed and "report_json_recomputed" in failed  # 읽지 않음


def test_f13_hard_link_protocol_refused(world):
    tmp_path, db, content = world
    cfg, lock_dir, _out = _ok_run(tmp_path, db, content, "f13_hardp")
    os.link(lock_dir / "protocol.json", tmp_path / "outside_protocol.json")
    with pytest.raises(CheckRequired, match="하드 링크"):
        VR.verify(cfg, NOW)


def test_f13_leftover_tmp_twin_still_verified(world):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, "f13_twin")
    os.link(
        out / "report.json", out / f".report.json.{'b' * 32}.tmp"
    )  # 정리 실패로 남은 짝
    assert VR.verify(cfg, NOW)["status"] == "VERIFIED_OK"


def test_f13_foreign_symlink_in_root_refused_without_reading(world):
    tmp_path, db, content = world
    cfg, _lock_dir, _out = _ok_run(tmp_path, db, content, "f13_rootlink")
    away = tmp_path / "away_rootlink"
    away.mkdir()
    (away / "protocol.json").write_text("{}")
    link = Path(cfg.root) / "20261122T040000Z_00000000"
    link.symlink_to(away, target_is_directory=True)
    with _no_touch(away, link) as seen:
        with pytest.raises(CheckRequired, match="심볼릭 링크"):
            VR.verify(cfg, NOW)
    assert seen == []


# --- r6 독립 검토 재현(잠금 파일 · 실행 폴더 이름 · 못 읽는 잠금) ---------------------------


@pytest.mark.parametrize("kind", ["fifo", "dir", "hardlink", "symlink"])
def test_run_lock_file_must_be_regular_inside(world, kind):
    tmp_path, db, content = world
    cfg, _lock_dir, _out = _ok_run(tmp_path, db, content, f"lk_{kind}")
    lf = Path(cfg.root) / FW.LOCK_NAME
    lf.unlink()
    outside = tmp_path / f"outside_{kind}.lock"
    outside.write_text("")
    if kind == "fifo":
        os.mkfifo(lf)  # 열면 끝없이 기다리는 자리
    elif kind == "dir":
        lf.mkdir()
    elif kind == "hardlink":
        os.link(outside, lf)  # 밖 파일과 이어진 이름
    else:
        lf.symlink_to(outside)

    def stuck(*_a):
        raise TimeoutError("잠금 파일에서 멈춤")

    old = signal.signal(signal.SIGALRM, stuck)
    signal.alarm(20)
    try:
        with _no_touch(lf, outside) as seen:
            for call in (
                lambda: VR.verify(cfg, NOW),
                lambda: FW.run(cfg, NOW),
                lambda: FW.prepare(cfg, NOW, "정정"),
            ):
                with pytest.raises(CheckRequired, match="잠금 파일"):
                    call()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    assert seen == []  # 열지 않고 거부(멈추지 않음)


def test_run_lock_busy_while_held_and_free_after(world):
    tmp_path, db, content = world
    cfg, _lock_dir, _out = _ok_run(tmp_path, db, content, "busy")
    with FW.run_lock(cfg.root):
        with pytest.raises(P.Busy):
            VR.verify(cfg, NOW)
    assert VR.verify(cfg, NOW)["status"] == "VERIFIED_OK"


@pytest.mark.parametrize("new", ["notes", ".hidden"])
def test_run_dir_name_must_be_run_id(world, new):
    tmp_path, db, content = world
    cfg, _lock_dir, out = _ok_run(tmp_path, db, content, f"nm_{new.strip('.')}")
    dst = out.parent / new
    out.rename(dst)  # 이름을 바꾸고 id · 해시를 모두 맞춰 위조
    rep = json.loads((dst / "report.json").read_text(encoding="utf-8"))
    rep["run_id"] = new
    (dst / "report.json").write_bytes(dumps(rep))
    (dst / "report.md").write_bytes(RP.markdown(FW.roundtrip(rep)).encode("utf-8"))
    done = json.loads((dst / "completed.json").read_text(encoding="utf-8"))
    done["run_id"] = new
    (dst / "completed.json").write_bytes(dumps(done))
    run_json = json.loads((dst / "run.json").read_text(encoding="utf-8"))
    run_json["run_id"] = new
    for k in ("report.json", "report.md"):
        run_json["manifest"][k] = VR.store.sha256_bytes((dst / k).read_bytes())
    _rewrite_run_json(dst, run_json)
    assert _failed(VR.verify(cfg, NOW, run_id=new)) == ["single_run_in_lock"]


def test_unreadable_lock_refused_not_skipped(world, monkeypatch):
    tmp_path, db, content = world
    cfg, _lock_dir, _out = _ok_run(tmp_path, db, content, "perm")
    real = FW.code_hashes
    monkeypatch.setattr(
        FW, "code_hashes", lambda repo: {**real(repo), "app/entry_timing/flow.py": "x"}
    )
    newest = Path(cfg.root) / FW.prepare(cfg, NOW, "결함")["lock_id"]
    newest.chmod(0)  # 최신 정정 잠금을 못 읽게
    try:
        with pytest.raises(CheckRequired, match="확인할 수 없음"):
            VR.verify(cfg, NOW)  # 건너뛰고 옛 잠금을 승인하지 않음
    finally:
        newest.chmod(0o755)


def test_hidden_folder_in_root_is_not_a_lock(world):
    tmp_path, db, content = world
    cfg, lock_dir, _out = _ok_run(tmp_path, db, content, "hid")
    shutil.copytree(
        lock_dir, Path(cfg.root) / ".backup"
    )  # 숨김 이름 = 잠금 아님 · 읽지 않음
    assert VR.verify(cfg, NOW)["status"] == "VERIFIED_OK"


def test_verify_unknown_run_id_refused(world):
    tmp_path, db, content = world
    cfg, _lock_dir, _out = _ok_run(tmp_path, db, content, "unk")
    with pytest.raises(CheckRequired, match="실행 기록이 없다"):
        VR.verify(cfg, NOW, run_id="20261122T000000Z_00000000")
