"""POC6-13 C — 외장 장치 사본 · 해시 대조 · 빈 칸 복원 · 거부 경로 시험.

tmp git 저장소 · tmp 가짜 연구 폴더 · tmp '외장' 경로(장치 검사는 주입) · 가짜 봉인 확인만 쓴다.
실제 외장 장치 · 라이브 state · 봉인 DB 접근 0. 계약 출처: PLAN V1 §4 · PLAN 판정(2026-10-28) §2 · §4.
"""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.forward_auto import backup as B
from app.forward_auto import backup_source as SRC
from app.forward_auto import status as ST
from app.ml_evidence import store

KST = timezone(timedelta(hours=9))
EVENING = datetime(2026, 10, 29, 16, 0, tzinfo=KST)
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def git(repo, *args):
    r = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, env=ENV
    )
    return r.stdout.decode().strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    (r / "app").mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    (r / "app" / "a.py").write_text("v1\n")
    git(r, "add", "app/a.py")
    git(r, "commit", "-q", "-m", "c1")
    c1 = git(r, "rev-parse", "HEAD")
    (r / "app" / "a.py").write_text("v2\n")
    git(r, "commit", "-q", "-am", "c2")
    c2 = git(r, "rev-parse", "HEAD")
    git(r, "checkout", "-q", "-b", "research/poc6-10-local")
    (r / "app" / "b.py").write_text("local\n")
    git(r, "add", "app/b.py")
    git(r, "commit", "-q", "-m", "c3")
    c3 = git(r, "rev-parse", "HEAD")
    git(r, "checkout", "-q", "main")
    for name in SRC.TARGETS:
        d = r / SRC.RESEARCH_REL / name / "20261025T000000Z_x"
        (d / "runs").mkdir(parents=True)
        code = {
            "sha256": {
                "app/a.py": hashlib.sha256(b"v2\n").hexdigest(),
                "app/gone.py": "0" * 64,
            }
        }
        (d / "protocol.json").write_text(json.dumps({"code": code}))
        (d / "runs" / "out.json").write_bytes(f"{name} 결과".encode() * 50)
        (r / SRC.RESEARCH_REL / name / ".run.lock").write_text("")
    (r / SRC.SEALED_REL).write_bytes(b"SQLite format 3\x00" + os.urandom(4096))
    monkeypatch.setattr(
        SRC, "COMMITS", {c1: "c1", c2: "c2(코드 해시 일치)", c3: "c3(로컬 브랜치)"}
    )
    return r, (c1, c2, c3)


@pytest.fixture
def ext(tmp_path, monkeypatch):
    t = tmp_path / "EXT"
    t.mkdir()
    ok = {
        "ok": True,
        "mount": "/Volumes/EXT",
        "device": "disk9s1",
        "volume_uuid": "U",
        "bus": "USB",
        "fs": "apfs",
        "internal": False,
    }
    monkeypatch.setattr(
        SRC, "device_check", lambda target, repo, disk_info=None, **kw: dict(ok)
    )
    return t


def seal(p):
    return {"file_sha256": store.sha256_file(p), "content_sha256": "c" * 64}


def run(repo, target, t=EVENING, **kw):
    return B.run(
        repo,
        target,
        clock=lambda: t,
        seal=seal,
        awake_fn=lambda: nullcontext(True),
        **kw,
    )


def verify(repo, target, bid, **kw):
    return B.verify(
        repo,
        target,
        bid,
        clock=lambda: EVENING,
        awake_fn=lambda: nullcontext(True),
        **kw,
    )


def dest(target):
    return Path(target).joinpath(*B.DEST)


def _sha(p: Path) -> str:
    """기록까지 함께 바뀐 경우를 흉내 낼 때 쓰는 현재 파일 해시."""
    return store.sha256_bytes(Path(p).read_bytes())


# ── 목적지 검사 ──────────────────────────────────────────────────────────────


def test_device_check_refuses_internal_unknown_and_same_volume(tmp_path):
    repo = tmp_path
    assert not SRC.device_check(tmp_path / "없음", repo)["ok"]
    assert "내부 디스크" in SRC.device_check(tmp_path, repo)["reason"]
    vol = dict(
        mount_fn=lambda p: Path("/Volumes/EXT"),
        dev_fn=lambda p: 1 if str(p) == "/Volumes/EXT" else 2,
    )
    assert (
        "확인 불가"
        in SRC.device_check(tmp_path, repo, lambda mp: None, **vol)["reason"]
    )
    assert (
        "내부 장치"
        in SRC.device_check(tmp_path, repo, lambda mp: {"Internal": True}, **vol)[
            "reason"
        ]
    )
    assert (
        "내부 장치" in SRC.device_check(tmp_path, repo, lambda mp: {}, **vol)["reason"]
    )
    good = SRC.device_check(
        tmp_path,
        repo,
        lambda mp: {"Internal": False, "DeviceIdentifier": "disk9s1"},
        **vol,
    )
    assert (
        good["ok"] and good["device"] == "disk9s1" and good["mount"] == "/Volumes/EXT"
    )
    image = {"Internal": False, "BusProtocol": "Disk Image"}
    assert (
        "디스크 이미지"
        in SRC.device_check(tmp_path, repo, lambda mp: image, **vol)["reason"]
    )
    apfs = {"Internal": False, "APFSPhysicalStores": [{"APFSPhysicalStore": "disk8s2"}]}

    def on_internal(x):
        return apfs if isinstance(x, Path) else {"Internal": True}

    def on_external(x):
        return (
            apfs if isinstance(x, Path) else {"Internal": False, "BusProtocol": "USB"}
        )

    assert not SRC.device_check(tmp_path, repo, on_internal, **vol)["ok"]
    assert SRC.device_check(tmp_path, repo, on_external, **vol)["ok"]
    same = dict(vol, dev_fn=lambda p: 1)
    assert (
        "같은 볼륨"
        in SRC.device_check(tmp_path, repo, lambda mp: {"Internal": False}, **same)[
            "reason"
        ]
    )


def test_no_external_device_waits_and_writes_nothing_anywhere(repo, tmp_path):
    r, _ = repo
    target = tmp_path / "internal_folder"
    target.mkdir()
    out = run(r, target)
    assert out["status"] == "WAITING_TARGET" and list(target.iterdir()) == []
    assert ST.backup_state(ST.Paths.default(r).ops)["state"] == "WAITING_TARGET"


def test_start_is_refused_inside_the_automation_window(repo, ext):
    r, _ = repo
    out = run(r, ext, t=datetime(2026, 10, 29, 11, 0, tzinfo=KST))
    assert out["status"] == "REFUSED" and list(ext.iterdir()) == []


# ── 복사 · 복원 ──────────────────────────────────────────────────────────────


def test_copy_hash_then_restore_verified_and_code_gaps_kept(repo, ext):
    r, (c1, c2, c3) = repo
    out = run(r, ext)
    assert out["status"] == "COPY_HASH_OK"
    final = dest(ext) / out["backup_id"]
    assert sorted(p.name for p in final.iterdir()) == sorted(
        [
            B.DB_NAME,
            B.TAR_NAME,
            B.BUNDLE_NAME,
            "env.json",
            "inputs.json",
            "manifest.json",
        ]
    )
    assert not list(dest(ext).glob("*.partial"))
    m = json.loads((final / "manifest.json").read_text())
    assert len(m["files"]) == 8 and all(
        f["rel"].startswith(SRC.RESEARCH_REL) for f in m["files"]
    )
    assert not any(".run.lock" in f["rel"] for f in m["files"])
    assert {x["best_commit"] for x in m["code_refs"]} == {c2}
    assert all(
        (x["matched"], x["gap_files"]) == (1, 1) for x in m["code_refs"]
    )  # 공백은 그대로 기록
    res = verify(r, ext, out["backup_id"])
    assert (
        res["status"] == "RESTORE_VERIFIED"
        and res["files"] == 8
        and res["commits"] == 3
    )
    ops = ST.Paths.default(r).ops
    assert not (ops / "restore" / out["backup_id"]).exists()  # 자기 임시 칸만 정리
    assert ST.backup_state(ops)["state"] == "RESTORE_VERIFIED"
    assert (r / SRC.SEALED_REL).is_file() and (
        r / SRC.RESEARCH_REL / "poc6_08"
    ).is_dir()  # 원본 그대로


def test_source_changed_while_packing_is_not_completed(repo, ext, monkeypatch):
    r, _ = repo
    real = SRC.inventory

    def stale(repo_):
        inv = real(repo_)
        inv[0] = dict(inv[0], mtime_ns=inv[0]["mtime_ns"] - 1)
        return inv

    monkeypatch.setattr(SRC, "inventory", stale)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "바뀜" in out["error"]
    assert (
        list(dest(ext).glob("*.partial"))
        and not (dest(ext) / out["backup_id"]).exists()
    )
    assert ST.backup_state(ST.Paths.default(r).ops)["state"] == "COPY_INCOMPLETE"


def test_destination_bytes_damaged_after_write_stays_partial(repo, ext, monkeypatch):
    r, _ = repo
    real = B._write

    def damage(*a):
        out = real(*a)
        part = a[3]
        p = part / B.TAR_NAME
        data = bytearray(p.read_bytes())
        data[600] ^= 0xFF
        p.write_bytes(bytes(data))
        return out

    monkeypatch.setattr(B, "_write", damage)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "목적지 해시 다름" in out["error"]
    assert not (dest(ext) / out["backup_id"]).exists()


def test_same_id_is_never_overwritten(repo, ext, monkeypatch):
    r, _ = repo

    class Fixed:
        hex = "deadbeef" * 4

    monkeypatch.setattr(B.uuid, "uuid4", lambda: Fixed)
    first = run(r, ext)
    assert first["status"] == "COPY_HASH_OK"
    before = (dest(ext) / first["backup_id"] / "manifest.json").read_bytes()
    second = run(r, ext)
    assert second["status"] == "REFUSED"
    assert (dest(ext) / first["backup_id"] / "manifest.json").read_bytes() == before


def test_sealed_hash_mismatch_is_not_completed(repo, ext):
    r, _ = repo
    out = B.run(
        r,
        ext,
        clock=lambda: EVENING,
        seal=lambda p: {"file_sha256": "0" * 64},
        awake_fn=lambda: nullcontext(True),
    )
    assert out["status"] == "COPY_INCOMPLETE" and "봉인" in out["error"]


def test_symlink_in_target_folder_stops_inventory(repo, tmp_path):
    r, _ = repo
    (r / SRC.RESEARCH_REL / "poc6_09" / "link.json").symlink_to(tmp_path)
    with pytest.raises(SRC.BackupError):
        SRC.inventory(r)


def test_verify_detects_damaged_copy_and_missing_commit(repo, ext, monkeypatch):
    r, _ = repo
    git(r, "checkout", "-q", "-b", "other")  # 저장소에는 있고 bundle 브랜치 밖인 커밋
    (r / "app" / "c.py").write_text("other\n")
    git(r, "add", "app/c.py")
    git(r, "commit", "-q", "-m", "c4")
    c4 = git(r, "rev-parse", "HEAD")
    git(r, "checkout", "-q", "main")
    monkeypatch.setattr(SRC, "COMMITS", dict(SRC.COMMITS, **{c4: "bundle 밖 커밋"}))
    out = run(r, ext)
    assert out["status"] == "COPY_HASH_OK"
    res = verify(r, ext, out["backup_id"])
    assert res["status"] == "RESTORE_FAILED" and "bundle 에 없는 커밋 1" in res["error"]
    monkeypatch.setattr(
        SRC, "COMMITS", {k: v for k, v in SRC.COMMITS.items() if k != c4}
    )
    out2 = run(r, ext)
    p = dest(ext) / out2["backup_id"] / B.DB_NAME
    p.write_bytes(p.read_bytes()[:-1] + b"X")
    res2 = verify(r, ext, out2["backup_id"])
    assert res2["status"] == "RESTORE_FAILED" and "해시 다름" in res2["error"]


def test_verify_refuses_partial_and_unsafe_tar_member(repo, ext, monkeypatch):
    r, _ = repo
    out = run(r, ext)
    bid = out["backup_id"]
    assert verify(r, ext, bid + ".partial")["status"] == "REFUSED"
    final = dest(ext) / bid
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        data = b"evil"
        info = tarfile.TarInfo("state/ml/research/poc6_08/../../../../evil.txt")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    (final / B.TAR_NAME).write_bytes(buf.getvalue())
    m = json.loads((final / "manifest.json").read_text())
    m["artifacts"][B.TAR_NAME]["sha256"] = hashlib.sha256(buf.getvalue()).hexdigest()
    (final / "manifest.json").write_text(json.dumps(m))
    first = verify(
        r, ext, bid
    )  # 외장 manifest 가 복사 때 기록한 해시와 다르면 먼저 막힌다
    assert (
        first["status"] == "RESTORE_FAILED" and "기록한 해시와 다름" in first["error"]
    )
    monkeypatch.setattr(  # 기록까지 변조 manifest 와 같아도 tar 항목 검사가 막는지
        B, "_recorded_manifest", lambda ops, b: _sha(final / "manifest.json")
    )
    res = verify(r, ext, bid)
    assert res["status"] == "RESTORE_FAILED" and "허용 밖" in res["error"]
    assert not (r.parent / "evil.txt").exists() and not list(r.parent.rglob("evil.txt"))


def test_verify_refuses_bad_id_and_window(repo, ext):
    r, _ = repo
    out = run(r, ext)
    assert verify(r, ext, "../../x")["status"] == "REFUSED"
    assert verify(r, ext, out["backup_id"] + "/..")["status"] == "REFUSED"
    early = B.verify(
        r,
        ext,
        out["backup_id"],
        clock=lambda: datetime(2026, 10, 29, 11, 0, tzinfo=KST),
        awake_fn=lambda: nullcontext(True),
    )
    assert early["status"] == "REFUSED"
    assert verify(r, ext, out["backup_id"])["status"] == "RESTORE_VERIFIED"


def test_tar_content_must_match_source_hashes_before_rename(repo, ext, monkeypatch):
    """목적지 묶음 해시끼리만 맞아도 안 된다 — tar 안 파일 = 원본에서 읽은 해시여야 COPY_HASH_OK."""
    r, _ = repo
    real = B._write

    def swap(*a):
        out = real(*a)
        part = a[3]
        p = part / B.TAR_NAME
        with tarfile.open(p, "r") as t:
            off = t.getmembers()[0].offset_data
        data = bytearray(p.read_bytes())
        data[off] ^= 0xFF  # 첫 파일 내용 1바이트
        p.write_bytes(bytes(data))
        out["manifest"]["artifacts"][B.TAR_NAME]["sha256"] = hashlib.sha256(
            bytes(data)
        ).hexdigest()
        return out

    monkeypatch.setattr(B, "_write", swap)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "원본 해시와 다름" in out["error"]
    assert not (dest(ext) / out["backup_id"]).exists()


@pytest.mark.parametrize(
    "name, ok",
    [
        ("state/ml/research/poc6_08/a.json", True),
        ("state/ml/research/poc6_08/../x", False),
        ("/state/ml/research/poc6_08/a.json", False),
        ("other/a.json", False),
        ("state/ml/research//poc6_08/a.json", False),
    ],
)
def test_safe_tar_names(name, ok):
    assert B._safe_name(name) is ok


def test_plan_writes_nothing_and_reports_target_wait(repo, tmp_path):
    r, _ = repo
    before = sorted(p for p in r.rglob("*"))
    out = SRC.plan(r, tmp_path)
    assert (
        out["files"] == 8
        and set(out["targets"]) == set(SRC.TARGETS)
        and not out["target"]["ok"]
    )
    assert sorted(p for p in r.rglob("*")) == before


# ── 검증자 r1 정정: 원본 · 목적지 링크 경계(F2 · F3) ───────────────────────


def test_target_root_symlink_is_refused(repo, ext, tmp_path):
    """대상 폴더 자체가 링크면 그 너머 파일을 묶지 않는다(F2)."""
    r, _ = repo
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.txt").write_text("범위 밖")
    root = r / SRC.RESEARCH_REL / "poc6_08"
    root.rename(tmp_path / "moved_08")
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SRC.BackupError, match="링크 경로"):
        SRC.inventory(r)
    with pytest.raises(SRC.BackupError):
        run(r, ext)
    assert not dest(ext).exists() or not any(dest(ext).iterdir())


def test_parent_folder_symlink_and_sealed_symlink_are_refused(repo, tmp_path):
    r, _ = repo
    real = tmp_path / "real_sealed.sqlite"
    sealed = r / SRC.SEALED_REL
    sealed.rename(real)
    sealed.symlink_to(real)
    with pytest.raises(SRC.BackupError, match="링크 경로"):
        SRC.sealed_path(r)
    research = r / SRC.RESEARCH_REL
    moved = tmp_path / "research_elsewhere"
    research.rename(moved)
    research.symlink_to(moved, target_is_directory=True)  # 상위 폴더가 링크
    with pytest.raises(SRC.BackupError, match="링크 경로"):
        SRC.inventory(r)


def test_file_swapped_for_symlink_after_listing_is_not_completed(
    repo, ext, tmp_path, monkeypatch
):
    r, _ = repo
    real_inv = SRC.inventory
    secret = tmp_path / "secret.txt"
    secret.write_text("범위 밖")

    def swap(repo_):
        inv = real_inv(repo_)
        p = r / inv[0]["rel"]
        p.unlink()
        p.symlink_to(secret)
        return inv

    monkeypatch.setattr(SRC, "inventory", swap)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "링크로 바뀜" in out["error"]


@pytest.mark.parametrize("which", [0, 1])
def test_destination_symlink_inside_external_is_refused(repo, ext, tmp_path, which):
    """외장 목적지 아래 백업 폴더(어느 단계든)가 내부 경로로 향하는 링크면 쓰지 않는다(F3)."""
    r, _ = repo
    internal = tmp_path / "internal_disk"
    internal.mkdir()
    base = ext
    for part in B.DEST[:which]:
        base = base / part
        base.mkdir()
    (base / B.DEST[which]).symlink_to(internal, target_is_directory=True)
    out = run(r, ext)
    assert out["status"] == "WAITING_TARGET" and "링크" in out["reason"]
    assert list(internal.iterdir()) == []
    assert ST.backup_state(ST.Paths.default(r).ops)["state"] == "WAITING_TARGET"


def test_verify_refuses_destination_symlink_and_non_external(repo, ext, monkeypatch):
    r, _ = repo
    out = run(r, ext)
    bid = out["backup_id"]
    final = dest(ext) / bid
    moved = ext / "moved_final"
    final.rename(moved)
    final.symlink_to(moved, target_is_directory=True)
    assert verify(r, ext, bid)["status"] == "REFUSED"
    final.unlink()
    moved.rename(final)
    monkeypatch.setattr(
        SRC, "device_check", lambda *a, **k: {"ok": False, "reason": "내부 장치"}
    )
    res = verify(r, ext, bid)
    assert res["status"] == "REFUSED" and "목적지 장치 아님" in res["reason"]


# ── 검증자 r2 정정: 외장 사본 안 파일 링크 · 다른 장치(F3 잔여) ─────────────────


def _to_internal_link(f: Path, internal: Path) -> None:
    """내용 · manifest · 기록은 그대로 두고 본문만 내부 경로로 옮긴 뒤 원위치에 링크."""
    internal.mkdir(exist_ok=True)
    f.rename(internal / f.name)
    f.symlink_to(internal / f.name)


@pytest.mark.parametrize("name", [*B.ARTIFACTS, "manifest.json"])
def test_verify_refuses_file_symlink_to_internal_copy(repo, ext, tmp_path, name):
    """외장에는 링크만 있고 본문이 내부 경로면 RESTORE_VERIFIED 가 아니다."""
    r, _ = repo
    out = run(r, ext)
    assert out["status"] == "COPY_HASH_OK"
    _to_internal_link(dest(ext) / out["backup_id"] / name, tmp_path / "internal")
    res = verify(r, ext, out["backup_id"])
    assert res["status"] == "RESTORE_FAILED" and "링크" in res["error"]
    assert ST.backup_state(ST.Paths.default(r).ops)["state"] == "RESTORE_FAILED"
    assert not (ST.Paths.default(r).ops / "restore" / out["backup_id"]).exists()


@pytest.mark.parametrize("name", [B.DB_NAME, B.TAR_NAME, "manifest.json"])
def test_copy_refuses_written_file_swapped_for_internal_symlink(
    repo, ext, tmp_path, monkeypatch, name
):
    """이름 바꾸기 전 대조에서 목적지 파일이 내부 경로 링크면 COPY_HASH_OK 가 아니다."""
    r, _ = repo
    real = B._write

    def swap(*a):
        out = real(*a)
        _to_internal_link(a[3] / name, tmp_path / "internal")
        return out

    monkeypatch.setattr(B, "_write", swap)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "링크" in out["error"]
    assert not (dest(ext) / out["backup_id"]).exists()


def test_copy_and_verify_require_files_on_the_target_device(repo, ext, monkeypatch):
    """목적지 장치와 다른 장치의 파일(그 아래 다른 마운트 등)은 외장 사본으로 대조 · 복원 확인하지 않는다."""
    r, _ = repo
    ok = run(r, ext)
    assert ok["status"] == "COPY_HASH_OK"
    real = B._device
    monkeypatch.setattr(B, "_device", lambda p: real(p) + 1)
    res = verify(r, ext, ok["backup_id"])
    assert res["status"] == "RESTORE_FAILED" and "일반 파일이 아님" in res["error"]
    bad = run(r, ext)
    assert bad["status"] == "COPY_INCOMPLETE" and "일반 파일이 아님" in bad["error"]
    assert not (dest(ext) / bad["backup_id"]).exists()


def test_verify_reads_only_the_fixed_artifacts(repo, ext, monkeypatch):
    """manifest 의 묶음 목록이 정해진 5개가 아니면(복사 기록까지 함께 바뀐 경우 포함) 복원 확인하지 않는다."""
    r, _ = repo
    out = run(r, ext)
    final = dest(ext) / out["backup_id"]
    m = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    m["artifacts"]["../../outside.bin"] = m["artifacts"].pop("env.json")
    (final / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    monkeypatch.setattr(
        B, "_recorded_manifest", lambda ops, b: _sha(final / "manifest.json")
    )
    res = verify(r, ext, out["backup_id"])
    assert res["status"] == "RESTORE_FAILED" and "정해진 5개" in res["error"]


# ── 독립 검토(r2 정정 뒤) 같은 종류: 외장끼리 비교 · 원본 상위 링크 · 기록 읽기 오류 · git 조회 실패 ──


def test_manifest_damaged_after_write_is_not_completed(repo, ext, monkeypatch):
    """manifest 는 쓴 바이트의 해시와 대조한다 — 목적지에서 쓴 뒤 바뀌면 COPY_HASH_OK 가 아니다."""
    r, _ = repo
    real = B._write

    def damage(*a):
        out = real(*a)
        p = a[3] / "manifest.json"
        p.write_bytes(p.read_bytes()[:-2])
        return out

    monkeypatch.setattr(B, "_write", damage)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "쓴 내용과 다름" in out["error"]
    assert not (dest(ext) / out["backup_id"]).exists()


def test_expected_hash_is_from_written_bytes_not_destination(repo, ext, monkeypatch):
    """env · inputs 를 쓴 뒤 manifest 를 만들기 전에 목적지가 바뀌어도, 목적지끼리 비교해 통과시키지 않는다."""
    r, _ = repo
    real_sha = store.sha256_file

    def sha(p):
        p = Path(p)
        if p.parent.name.endswith(".partial"):
            for n in ("env.json", "inputs.json"):
                if (p.parent / n).exists():
                    (p.parent / n).write_bytes(b"{}")
        return real_sha(p)

    monkeypatch.setattr(store, "sha256_file", sha)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "목적지 해시 다름" in out["error"]
    assert not (dest(ext) / out["backup_id"]).exists()


def test_sealed_swapped_for_link_after_listing_is_not_completed(
    repo, ext, tmp_path, monkeypatch
):
    """봉인 DB 확인(`sealed_path`) 뒤 복사 전에 링크로 바뀌면 복사하지 않는다(복사 직전 재확인)."""
    r, _ = repo
    real_sp = SRC.sealed_path

    def swap(repo_):
        p = real_sp(repo_)
        moved = tmp_path / "sealed_elsewhere.sqlite"
        p.rename(moved)
        p.symlink_to(moved)
        return p

    monkeypatch.setattr(SRC, "sealed_path", swap)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "링크로 바뀜" in out["error"]


def test_verify_requires_the_fixed_commits(repo, ext, monkeypatch):
    """manifest 의 커밋 목록이 비거나 다르면(복사 기록까지 함께 바뀐 경우 포함) '커밋 확인'으로 보고하지 않는다."""
    r, _ = repo
    out = run(r, ext)
    final = dest(ext) / out["backup_id"]
    m = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    m["commits"] = {}
    (final / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    monkeypatch.setattr(
        B, "_recorded_manifest", lambda ops, b: _sha(final / "manifest.json")
    )
    res = verify(r, ext, out["backup_id"])
    assert res["status"] == "RESTORE_FAILED" and "커밋 목록" in res["error"]


def test_source_parent_folder_swapped_for_link_after_listing(
    repo, ext, tmp_path, monkeypatch
):
    """목록 뒤 원본 상위 폴더가 범위 밖 링크로 바뀌면(크기 · 수정 시각 같음) 묶지 않는다."""
    r, _ = repo
    real_inv = SRC.inventory
    d = r / SRC.RESEARCH_REL / "poc6_08" / "20261025T000000Z_x" / "runs"
    outside = tmp_path / "outside_runs"

    def swap(repo_):
        inv = real_inv(repo_)
        shutil.copytree(d, outside)
        f = outside / "out.json"
        st = f.stat()
        f.write_bytes(b"Z" * st.st_size)
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
        shutil.rmtree(d)
        d.symlink_to(outside, target_is_directory=True)
        return inv

    monkeypatch.setattr(SRC, "inventory", swap)
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "링크로 바뀜" in out["error"]
    assert not (dest(ext) / out["backup_id"]).exists()


@pytest.mark.parametrize("how", ["unreadable", "no_hash"])
def test_copy_record_read_failure_stops_verify(repo, ext, how):
    """복사 기록이 있는데 읽지 못하거나 해시가 없으면 manifest 대조를 건너뛰지 않는다."""
    r, _ = repo
    out = run(r, ext)
    bid = out["backup_id"]
    ops = ST.Paths.default(r).ops
    (rec,) = (ops / "backup").glob(f"{bid}.*.COPY_HASH_OK.json")
    if how == "unreadable":
        os.chmod(rec, 0)
    else:
        body = json.loads(rec.read_text(encoding="utf-8"))
        body.pop("manifest_sha256")
        os.chmod(rec, 0o644)
        rec.write_text(json.dumps(body), encoding="utf-8")
    try:
        res = verify(r, ext, bid)
    finally:
        os.chmod(rec, 0o644)
    assert res["status"] == "RESTORE_FAILED" and "복사 기록" in res["error"]


@pytest.mark.parametrize("body", [b"{broken", b"[1, 2]"])
def test_unreadable_record_makes_backup_state_check_required(repo, ext, body):
    """읽지 못한 단계 기록이 있으면 그보다 앞선 단계(RESTORE_VERIFIED 등)를 마지막으로 보이지 않는다."""
    r, _ = repo
    out = run(r, ext)
    assert verify(r, ext, out["backup_id"])["status"] == "RESTORE_VERIFIED"
    ops = ST.Paths.default(r).ops
    (ops / "backup" / f"{out['backup_id']}.99.RESTORE_FAILED.json").write_bytes(body)
    st = ST.backup_state(ops)
    assert st["state"] == "CHECK_REQUIRED" and "1개" in st["detail"]


def test_git_query_failure_is_not_recorded_as_fact(repo, ext, monkeypatch):
    """git 조회 실패는 빈 출력('없음' · '공백')이 아니라 COPY_INCOMPLETE."""
    r, _ = repo
    with pytest.raises(SRC.BackupError):
        SRC.git_bytes(["show", "0" * 40 + ":x"], r)
    monkeypatch.setitem(SRC.COMMITS, "1" * 40, "없는 커밋")
    out = run(r, ext)
    assert out["status"] == "COPY_INCOMPLETE" and "git ls-tree 실패" in out["error"]
    monkeypatch.delitem(SRC.COMMITS, "1" * 40)

    def no_heads(args, cwd):
        return b"" if args[:2] == ["bundle", "list-heads"] else SRC.git_bytes(args, cwd)

    out = run(r, ext, git=no_heads)
    assert out["status"] == "COPY_INCOMPLETE" and "머리 목록" in out["error"]
    assert ST.backup_state(ST.Paths.default(r).ops)["state"] == "COPY_INCOMPLETE"


# ── C 보완: 별도 PC 공유 폴더(SMB · 보완 판정 2026-10-29) ─────────────────────────
# 가짜 마운트 표 · 주소 확인으로 tmp 폴더를 smbfs 공유처럼 보이게 한다(실제 SMB 호환성 확인 아님).

APPROVED = "//192.168.0.10/krxbackup"
REAL_DEVICE_CHECK = SRC.device_check
REAL_DEV = SRC._dev


@pytest.fixture
def share(tmp_path, monkeypatch):
    t = (tmp_path / "SHARE").resolve()
    t.mkdir()
    state = {
        "rows": [
            {"source": "/dev/disk3s1", "mount": "/", "fs": "apfs"},
            {
                "source": "//smbuser-x7@192.168.0.10/krxbackup",
                "mount": str(t),
                "fs": "smbfs",
            },
        ],
        "addrs": {
            "192.168.0.10": {"192.168.0.10"},
            "desktop-pc.local": {"192.168.0.10"},
        },
        "own": {"127.0.0.1", "::1", "192.168.0.5"},
    }
    monkeypatch.setattr(SRC, "mount_table", lambda: state["rows"])
    monkeypatch.setattr(SRC, "resolve_host", lambda n: state["addrs"].get(n))
    monkeypatch.setattr(SRC, "own_addresses", lambda: state["own"])

    def fake_dev(p):  # 공유 아래는 다른 장치로 보이게(저장소와 같은 tmp 장치라서)
        q = Path(p).resolve()
        if q.name == "shadow" or t / "shadow" in q.parents:
            return 991  # 공유 마운트 위가 아닌 자리(가림 폴더)
        if state.get("same_volume"):
            return REAL_DEV(p)
        return 990 if q == t or t in q.parents else REAL_DEV(p)

    monkeypatch.setattr(SRC, "_dev", fake_dev)

    def no_external(*a, **k):
        raise AssertionError("PC 공유 경로에서 외장 장치 검사를 쓰면 안 됨")

    monkeypatch.setattr(SRC, "device_check", no_external)
    return t, state


def _smb(state, source):
    state["rows"][1]["source"] = source


@pytest.mark.parametrize(
    "case, approved, change, reason",
    [
        ("승인 서버 · 공유", APPROVED, None, None),
        ("별칭 = 같은 주소", "//desktop-pc.local/krxbackup", None, None),
        ("다른 공유", "//192.168.0.10/other", None, "공유 이름"),
        (
            "다른 서버",
            "//192.168.0.99/krxbackup",
            ("addrs", "192.168.0.99"),
            "다른 서버",
        ),
        ("별칭 주소 확인 불가", "//unknown-pc/krxbackup", None, "다른 서버"),
        ("서버 주소 확인 불가", APPROVED, ("drop", "192.168.0.10"), "주소 확인 불가"),
        ("localhost", "//localhost/krxbackup", ("smb", "localhost"), "localhost"),
        ("맥북 자신", "//192.168.0.5/krxbackup", ("smb", "192.168.0.5"), "맥북 자신"),
        ("공인 주소", "//8.8.8.8/krxbackup", ("smb", "8.8.8.8"), "로컬 네트워크"),
        ("마운트 표 확인 불가", APPROVED, ("rows", None), "마운트 표"),
        ("자기 주소 확인 불가", APPROVED, ("own", None), "자기 주소"),
        ("공유 해제 · 로컬 폴더만", APPROVED, ("unmount", None), "SMB 공유 아님"),
        ("다른 네트워크 공유(AFP)", APPROVED, ("fs", "afpfs"), "SMB 공유 아님"),
        ("저장소와 같은 볼륨", APPROVED, ("same_volume", True), "같은 볼륨"),
    ],
)
def test_share_check_accepts_only_the_approved_smb_share(
    repo, share, case, approved, change, reason
):
    r, _ = repo
    t, state = share
    kind, val = change or (None, None)
    if kind == "addrs":
        state["addrs"][val] = {val}
    elif kind == "drop":
        state["addrs"].pop(val)
    elif kind == "smb":
        state["addrs"][val] = {"127.0.0.1" if val == "localhost" else val}
        _smb(state, f"//u@{val}/krxbackup")
    elif kind == "rows":
        state["rows"] = None
    elif kind == "own":
        state["own"] = None
    elif kind == "unmount":
        state["rows"] = state["rows"][:1]
    elif kind == "fs":
        state["rows"][1]["fs"] = val
    elif kind == "same_volume":
        state["same_volume"] = True
    res = SRC.share_check(t, r, approved)
    if reason is None:
        assert res["ok"] and res["kind"] == "PC_SHARE" and res["fs"] == "smbfs"
        assert "smbuser-x7" not in json.dumps(
            res
        )  # 마운트 원문의 사용자 부분을 기록하지 않음
    else:
        assert not res["ok"] and reason in res["reason"], res


def test_share_check_requires_target_inside_the_share(repo, share, tmp_path):
    r, _ = repo
    t, state = share
    other = tmp_path / "local_only"
    other.mkdir()
    assert "SMB 공유 아님" in SRC.share_check(other, r, APPROVED)["reason"]
    inside = t / "sub"
    inside.mkdir()
    assert SRC.share_check(inside, r, APPROVED)["ok"]
    shadow = t / "shadow"  # 표로는 공유 안이지만 실제 장치가 다른 자리
    shadow.mkdir()
    assert "마운트 위에 있지 않음" in SRC.share_check(shadow, r, APPROVED)["reason"]


@pytest.mark.parametrize(
    "spec", ["//user@pc/share", "//pc:445/share", "//fe80::1/share", "pc", "//pc/a/b"]
)
def test_parse_share_refuses_credentials_and_bad_forms(spec):
    with pytest.raises(SRC.BackupError):
        SRC.parse_share(spec)


def test_share_specs_and_mount_lines_are_parsed():
    assert SRC.parse_share("//PC/Backup") == ("pc", "backup")
    assert SRC.smb_source("//DOM;user@Desktop-PC._smb._tcp.local/My%20Backup") == (
        "desktop-pc._smb._tcp.local",
        "my backup",
    )
    assert SRC.smb_source("/dev/disk3s1") is None
    out = (
        "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n"
        "map auto_home on /System/Volumes/Data/home (autofs, automounted, nobrowse)\n"
        "//u@192.168.0.10/krxbackup on /Volumes/krx backup (smbfs, nodev, nosuid, mounted by u)\n"
    ).encode()
    rows = SRC.mount_table(lambda *a, **k: subprocess.CompletedProcess(a, 0, out))
    assert rows[1] == {
        "source": "map auto_home",
        "mount": "/System/Volumes/Data/home",
        "fs": "autofs",
    }
    assert rows[2]["mount"] == "/Volumes/krx backup" and rows[2]["fs"] == "smbfs"
    assert (
        SRC.mount_table(lambda *a, **k: subprocess.CompletedProcess(a, 1, b"")) is None
    )

    def boom(*a, **k):
        raise OSError("mount 없음")

    assert SRC.mount_table(boom) is None and SRC.own_addresses(boom) is None


def test_pc_share_copy_then_restore_and_damage_is_refused(repo, share):
    r, _ = repo
    t, _ = share
    out = run(r, t, pc_share=APPROVED)
    assert out["status"] == "COPY_HASH_OK" and out["sync"]
    ops = ST.Paths.default(r).ops
    (rec,) = (ops / "backup").glob(f"{out['backup_id']}.*.COPY_HASH_OK.json")
    body = rec.read_text(encoding="utf-8")
    assert (
        '"kind": "PC_SHARE"' in body and "smbuser-x7" not in body and '"sync"' in body
    )
    res = verify(r, t, out["backup_id"], pc_share=APPROVED)
    assert res["status"] == "RESTORE_VERIFIED" and res["commits"] == 3
    p = dest(t) / out["backup_id"] / B.DB_NAME
    p.write_bytes(p.read_bytes()[:-1] + b"X")
    bad = verify(r, t, out["backup_id"], pc_share=APPROVED)
    assert bad["status"] == "RESTORE_FAILED" and "해시 다름" in bad["error"]
    assert (dest(t) / out["backup_id"]).is_dir()  # 복원 실패로 사본을 지우지 않음


def test_pc_share_unmounted_leftover_folder_is_not_used(repo, share):
    """공유가 해제돼 같은 이름의 로컬 폴더만 남으면 쓰지도 · 복원하지도 않는다."""
    r, _ = repo
    t, state = share
    out = run(r, t, pc_share=APPROVED)
    assert out["status"] == "COPY_HASH_OK"
    state["rows"] = state["rows"][:1]
    res = verify(r, t, out["backup_id"], pc_share=APPROVED)
    assert res["status"] == "REFUSED" and "PC 공유 아님" in res["reason"]
    before = sorted(x.name for x in dest(t).iterdir())
    again = run(r, t, pc_share=APPROVED)
    assert again["status"] == "WAITING_TARGET" and "SMB 공유 아님" in again["reason"]
    assert sorted(x.name for x in dest(t).iterdir()) == before


def test_external_and_share_checks_do_not_stand_in_for_each_other(
    repo, share, monkeypatch
):
    r, _ = repo
    t, _ = share
    bad = run(r, t, pc_share="//user@192.168.0.10/krxbackup")
    assert bad["status"] == "REFUSED" and "사용자" in bad["reason"]
    monkeypatch.setattr(SRC, "device_check", REAL_DEVICE_CHECK)

    def no_share(*a, **k):
        raise AssertionError("--pc-share 없이 공유 검사를 쓰면 안 됨")

    monkeypatch.setattr(SRC, "share_check", no_share)
    out = run(
        r, t, disk_info=lambda p: None
    )  # 플래그 없음 = 외장 검사 → 공유는 통과 못 함
    assert out["status"] == "WAITING_TARGET"


@pytest.mark.parametrize(
    "err, fsync_ok, expect",
    [
        (errno.ENOTSUP, True, "fsync"),
        (errno.EINVAL, True, "fsync"),
        (errno.EIO, True, None),
        (errno.ENOTCONN, True, None),
        (errno.ENOTSUP, False, None),  # 대신한 fsync 도 실패 → 실패
    ],
)
def test_full_sync_falls_back_only_when_unsupported(
    tmp_path, monkeypatch, err, fsync_ok, expect
):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")

    def no_full(fd, op, *a):
        raise OSError(err, os.strerror(err))

    def bad_fsync(fd):
        raise OSError(errno.EIO, "fsync 실패")

    monkeypatch.setattr(B.fcntl, "fcntl", no_full)
    if not fsync_ok:
        monkeypatch.setattr(B.os, "fsync", bad_fsync)
    fd = os.open(f, os.O_RDONLY)
    try:
        if expect:
            assert B._fsync_full(fd) == expect
        else:
            with pytest.raises(OSError):
                B._fsync_full(fd)
    finally:
        os.close(fd)


def test_sync_or_connection_failure_on_share_is_not_completed(repo, share, monkeypatch):
    r, _ = repo
    t, _ = share
    real = B.fcntl.fcntl

    def unsupported(fd, op, *a):
        if op == getattr(B.fcntl, "F_FULLFSYNC", None):
            raise OSError(errno.ENOTSUP, "미지원")
        return real(fd, op, *a)

    monkeypatch.setattr(B.fcntl, "fcntl", unsupported)
    ok = run(r, t, pc_share=APPROVED)
    assert ok["status"] == "COPY_HASH_OK" and set(ok["sync"]) == {
        "fsync",
        "rename_dir:fsync",
    }

    def io_error(fd, op, *a):
        if op == getattr(B.fcntl, "F_FULLFSYNC", None):
            raise OSError(errno.EIO, "입출력 오류")
        return real(fd, op, *a)

    monkeypatch.setattr(B.fcntl, "fcntl", io_error)
    bad = run(r, t, pc_share=APPROVED)
    assert (
        bad["status"] == "COPY_INCOMPLETE" and not (dest(t) / bad["backup_id"]).exists()
    )
    real_write = B._write

    def dropped(*a):  # 쓰는 중 연결 끊김
        real_write(*a)
        raise OSError(errno.ENOTCONN, "연결 끊김")

    monkeypatch.setattr(B, "_write", dropped)
    gone = run(r, t, pc_share=APPROVED)
    assert (
        gone["status"] == "COPY_INCOMPLETE"
        and not (dest(t) / gone["backup_id"]).exists()
    )


# ── 검증자 C-F1 정정: 이름 바꾼 뒤 실패한 사본은 완료 대상이 아니다 ─────────────────


@pytest.mark.parametrize("point", ["before_rename", "after_rename"])
def test_sync_failure_around_rename_is_never_a_completed_copy(
    repo, share, monkeypatch, point
):
    """폴더 동기화 입출력 오류가 이름 바꾸기 전 · 뒤 어디서 나도 COPY_INCOMPLETE ·
    최종 이름 폴더 없음(.partial 로 남음) · verify 거부 · 마지막 상태 = COPY_INCOMPLETE."""
    r, _ = repo
    t, _ = share
    real = B._fsync_dir

    def failing(folder):
        is_parent = not Path(folder).name.endswith(".partial")
        if (point == "after_rename") == is_parent:
            raise OSError(errno.EIO, "동기화 입출력 오류")
        return real(folder)

    monkeypatch.setattr(B, "_fsync_dir", failing)
    out = run(r, t, pc_share=APPROVED)
    bid = out["backup_id"]
    assert out["status"] == "COPY_INCOMPLETE"
    assert not (dest(t) / bid).exists() and (dest(t) / f"{bid}.partial").is_dir()
    if point == "after_rename":
        assert ".partial 로 되돌림" in out["after_rename"]
    monkeypatch.setattr(B, "_fsync_dir", real)
    res = verify(r, t, bid, pc_share=APPROVED)
    assert res["status"] == "REFUSED"
    ops = ST.Paths.default(r).ops
    assert ST.backup_state(ops)["state"] == "COPY_INCOMPLETE"
    assert not list((ops / "backup").glob(f"{bid}.*.COPY_HASH_OK.json"))


def test_final_folder_left_without_copy_record_is_refused(repo, share, monkeypatch):
    """되돌리기마저 실패해 최종 이름 폴더가 남아도, COPY_HASH_OK 기록이 없으면 복원 확인 대상이 아니다."""
    r, _ = repo
    t, _ = share
    real_fsync_dir, real_rename = B._fsync_dir, B.os.rename

    def parent_fails(folder):
        if not Path(folder).name.endswith(".partial"):
            raise OSError(errno.EIO, "동기화 입출력 오류")
        return real_fsync_dir(folder)

    def no_undo(src, dst):
        if str(dst).endswith(".partial"):
            raise OSError(errno.EIO, "되돌리기 실패")
        return real_rename(src, dst)

    monkeypatch.setattr(B, "_fsync_dir", parent_fails)
    monkeypatch.setattr(B.os, "rename", no_undo)
    out = run(r, t, pc_share=APPROVED)
    bid = out["backup_id"]
    assert out["status"] == "COPY_INCOMPLETE" and "되돌리지 못함" in out["after_rename"]
    assert (dest(t) / bid).is_dir()
    monkeypatch.setattr(B, "_fsync_dir", real_fsync_dir)
    monkeypatch.setattr(B.os, "rename", real_rename)
    res = verify(r, t, bid, pc_share=APPROVED)
    assert res["status"] == "REFUSED" and "COPY_HASH_OK 아님" in res["reason"]
    assert ST.backup_state(ST.Paths.default(r).ops)["state"] == "COPY_INCOMPLETE"


def test_copy_success_record_missing_or_not_last_is_refused(repo, ext, monkeypatch):
    """폴더가 있어도 복사 성공 기록이 없거나(기록 쓰기 실패 · 삭제) 마지막 복사 기록이 아니면 거부."""
    r, _ = repo
    real = B._record

    def no_ok_record(ops, bid, stage, now, **d):
        if stage == "COPY_HASH_OK":
            raise OSError(errno.EIO, "기록 쓰기 실패")
        return real(ops, bid, stage, now, **d)

    monkeypatch.setattr(B, "_record", no_ok_record)
    with pytest.raises(OSError):
        run(r, ext)
    monkeypatch.setattr(B, "_record", real)
    (left,) = [x for x in dest(ext).iterdir() if not x.name.endswith(".partial")]
    res = verify(r, ext, left.name)
    assert res["status"] == "REFUSED" and "COPY_HASH_OK 아님" in res["reason"]
    ok = run(r, ext)
    ops = ST.Paths.default(r).ops
    B._record(
        ops, ok["backup_id"], "COPY_INCOMPLETE", EVENING, detail="뒤에 남은 미완료"
    )
    res2 = verify(r, ext, ok["backup_id"])
    assert res2["status"] == "REFUSED" and "COPY_INCOMPLETE" in res2["reason"]
    for f in (ops / "backup").glob(f"{ok['backup_id']}.*.json"):
        f.unlink()
    res3 = verify(r, ext, ok["backup_id"])
    assert res3["status"] == "REFUSED" and "복사 기록 없음" in res3["reason"]


def test_record_gone_after_check_does_not_skip_manifest_match(repo, ext, monkeypatch):
    """확인 뒤 복사 기록이 사라져도(안쪽 방어) 대조 없이 복원 확인으로 진행하지 않는다."""
    r, _ = repo
    out = run(r, ext)
    monkeypatch.setattr(B, "_copy_refusal", lambda ops, bid: None)
    monkeypatch.setattr(B, "_recorded_manifest", lambda ops, bid: None)
    res = verify(r, ext, out["backup_id"])
    assert res["status"] == "RESTORE_FAILED" and "복사 완료 기록 없음" in res["error"]
